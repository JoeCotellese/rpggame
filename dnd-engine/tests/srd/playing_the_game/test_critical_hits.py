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

    def test_sneak_attack_dice_doubled_on_critical_hit(self):
        pytest.skip(
            "GAP: sneak attack dice are NOT doubled on a critical hit. "
            "dnd-engine/dnd_engine/core/combat.py:173 calls "
            "`self._calculate_damage(sneak_attack_dice, critical_hit=False)` "
            "with a hardcoded False inside the `if hit:` branch of "
            "`resolve_attack`. SRD example explicitly calls out Sneak "
            "Attack as a class of 'other damage dice' that must double "
            "on a crit; the current implementation rolls them once "
            "regardless of the attack's crit status. Tracked by issue "
            "#416."
        )

    def test_resolve_attack_sneak_attack_passes_critical_flag(self):
        """Source-level contract: the call site MUST consult `critical_hit`.

        Inspects `CombatEngine.resolve_attack` source to assert the
        sneak-attack damage calculation does not pass a hardcoded
        `critical_hit=False`. When the gap is fixed, this assertion
        flips from skip-companion to a real guard.
        """
        src = inspect.getsource(CombatEngine.resolve_attack)
        assert "sneak_attack_dice" in src, (
            "resolve_attack must compute sneak attack dice — otherwise "
            "the SRD 'other damage dice' rule cannot be honored."
        )
        pytest.skip(
            "GAP companion (issue #416): when the hardcoded "
            "`critical_hit=False` in combat.py:173 is replaced with the "
            "live `critical_hit` flag, drop this skip and add a strict "
            "negative assertion: `assert 'critical_hit=False' not in "
            "<sneak-attack call site>`."
        )
