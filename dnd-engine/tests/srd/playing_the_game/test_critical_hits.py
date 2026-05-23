# ABOUTME: SRD conformance audit for "Playing the Game > Critical Hits".
# ABOUTME: Cross-references docs/srd/playing-the-game/critical-hits.md against engine code.

"""SRD conformance: Critical Hits.

Maps every rule in `docs/srd/playing-the-game/critical-hits.md` to a
test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import inspect

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.combat import CombatEngine
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller

pytestmark = pytest.mark.srd(
    "playing-the-game/critical-hits.md",
    lines="2220-2227",
)


def _make_engine() -> CombatEngine:
    return CombatEngine(DiceRoller(seed=42))


def _make_combatants() -> tuple[Creature, Creature]:
    abilities = Abilities(
        strength=16, dexterity=14, constitution=15, intelligence=10, wisdom=12, charisma=8
    )
    fighter = Creature(name="Fighter", max_hp=20, ac=16, abilities=abilities)
    goblin = Creature(name="Goblin", max_hp=7, ac=15, abilities=abilities)
    return fighter, goblin


class TestCriticalHit_DoubleDice:
    """SRD § Playing the Game › Critical Hits › Double the dice.

    > When you score a Critical Hit, you deal extra damage. Roll the
    > attack's damage dice twice, add them together, and add any
    > relevant modifiers as normal.
    """

    def test_double_dice_helper_doubles_count(self):
        """`_double_damage_dice('1d8+3')` returns `'2d8+3'`.

        Deterministic unit test of the doubling helper used by
        `_calculate_damage` when `critical_hit=True`. Verifies the
        core SRD contract: dice count doubles, die size and modifier
        are unchanged.
        """
        engine = _make_engine()

        assert engine._double_damage_dice("1d8+3") == "2d8+3"
        assert engine._double_damage_dice("2d6+2") == "4d6+2"
        assert engine._double_damage_dice("1d10") == "2d10"

    def test_critical_hit_damage_uses_doubled_dice(self):
        """A nat-20 attack rolls `2dN` for damage, not `1dN`.

        Loops attacks until a nat 20 lands (matches the existing
        `test_combat.py` convention) and asserts the observed damage
        falls inside the doubled-dice range for 1d8+3 → 2d8+3.
        """
        engine = _make_engine()
        fighter, goblin = _make_combatants()

        for _ in range(200):
            result = engine.resolve_attack(
                attacker=fighter,
                defender=goblin,
                attack_bonus=5,
                damage_dice="1d8+3",
            )
            if result.critical_hit:
                # 2d8+3 → min 5 (2+3), max 19 (16+3).
                assert 5 <= result.damage <= 19
                return

        pytest.fail("Did not observe a natural 20 in 200 attacks.")


class TestCriticalHit_ModifierNotDoubled:
    """SRD § Playing the Game › Critical Hits › Modifier preserved.

    > ...add any relevant modifiers as normal.

    The example in the SRD says: 'if you score a Critical Hit with a
    Dagger, roll 2d4 for the damage rather than 1d4, and add your
    relevant ability modifier.' The modifier is added *once*, not
    doubled.
    """

    def test_modifier_is_not_doubled(self):
        """`_double_damage_dice('1d4+2')` returns `'2d4+2'` (not `'2d4+4'`).

        Defends the modifier-preservation contract that
        `_calculate_damage` depends on.
        """
        engine = _make_engine()

        assert engine._double_damage_dice("1d4+2") == "2d4+2"
        assert engine._double_damage_dice("3d6+5") == "6d6+5"
        assert engine._double_damage_dice("1d8-1") == "2d8-1"


class TestCriticalHit_DaggerExample:
    """SRD § Playing the Game › Critical Hits › Worked example.

    > For example, if you score a Critical Hit with a Dagger, roll 2d4
    > for the damage rather than 1d4, and add your relevant ability
    > modifier.
    """

    def test_dagger_crit_doubles_d4(self):
        """Dagger's `1d4` becomes `2d4` on a crit.

        Direct invocation of the doubling helper with the SRD's
        canonical example. The +mod is applied at the roll stage by
        `_calculate_damage`, so this test focuses on the dice-doubling
        the example calls out.
        """
        engine = _make_engine()

        assert engine._double_damage_dice("1d4") == "2d4"


class TestCriticalHit_ExtraDamageDiceAlsoDoubled:
    """SRD § Playing the Game › Critical Hits › Extra damage dice.

    > If the attack involves other damage dice, such as from the
    > Rogue's Sneak Attack feature, you also roll those dice twice.
    """

    def test_sneak_attack_dice_doubled_on_critical_hit(self, monkeypatch):
        """A nat-20 Sneak Attack rolls the sneak dice doubled.

        Builds a level-3 Rogue (sneak attack 2d6), spies on
        `_calculate_damage` to capture the dice notation and crit flag
        used for each call, then loops attacks with advantage until a
        critical hit lands with a sneak-attack proc. Asserts the spy
        recorded the sneak-attack dice being passed with
        `critical_hit=True`.
        """
        engine = _make_engine()

        rogue_abilities = Abilities(
            strength=10, dexterity=16, constitution=14, intelligence=12, wisdom=13, charisma=8
        )
        rogue = Character(
            name="Sneaky",
            character_class=CharacterClass.ROGUE,
            level=3,
            abilities=rogue_abilities,
            max_hp=20,
            ac=14,
        )
        target_abilities = Abilities(
            strength=8, dexterity=14, constitution=10, intelligence=10, wisdom=8, charisma=8
        )
        target = Creature(name="Dummy", max_hp=200, ac=10, abilities=target_abilities)

        damage_calls: list[tuple[str, bool]] = []
        original = engine._calculate_damage

        def spy(damage_dice: str, critical_hit: bool) -> int:
            damage_calls.append((damage_dice, critical_hit))
            return original(damage_dice, critical_hit)

        monkeypatch.setattr(engine, "_calculate_damage", spy)

        for _ in range(500):
            damage_calls.clear()
            result = engine.resolve_attack(
                attacker=rogue,
                defender=target,
                attack_bonus=5,
                damage_dice="1d8+3",
                advantage=True,
            )
            if result.critical_hit and result.sneak_attack_damage > 0:
                sneak_calls = [c for c in damage_calls if c[0] == result.sneak_attack_dice]
                assert sneak_calls, (
                    "Spy did not observe sneak attack dice flowing through "
                    "_calculate_damage — instrumentation broken."
                )
                assert all(c[1] is True for c in sneak_calls), (
                    f"Sneak attack dice {result.sneak_attack_dice} were rolled "
                    f"with critical_hit=False on a crit. Calls: {sneak_calls}"
                )
                return

        pytest.fail("Did not observe a critical hit with sneak attack in 500 attempts.")

    def test_resolve_attack_sneak_attack_passes_critical_flag(self):
        """Source-level contract: the call site MUST consult `critical_hit`.

        Inspects `CombatEngine.resolve_attack` source to assert the
        sneak-attack damage calculation does not pass a hardcoded
        `critical_hit=False`. Regression guard against the original
        #416 bug pattern.
        """
        src = inspect.getsource(CombatEngine.resolve_attack)
        assert "sneak_attack_dice" in src, (
            "resolve_attack must compute sneak attack dice — otherwise "
            "the SRD 'other damage dice' rule cannot be honored."
        )
        sneak_idx = src.index("sneak_attack_damage = self._calculate_damage(")
        call_site = src[sneak_idx : sneak_idx + 200]
        assert "critical_hit=False" not in call_site, (
            "Sneak attack damage must not be calculated with a hardcoded "
            "`critical_hit=False`; it must consult the live crit flag so "
            "the SRD 'other damage dice' rule fires on a nat 20."
        )
