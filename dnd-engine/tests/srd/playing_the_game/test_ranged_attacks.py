# ABOUTME: SRD conformance audit for "Playing the Game > Ranged Attacks".
# ABOUTME: Cross-references docs/srd/playing-the-game/ranged-attacks.md against engine code.

"""SRD conformance: Ranged Attacks.

Maps every rule in `docs/srd/playing-the-game/ranged-attacks.md` to a
test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import pytest

from dnd_engine.core.combat import CombatEngine
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.systems.ranged_attacks import is_close_combat_ranged_disadvantage

pytestmark = pytest.mark.srd(
    "playing-the-game/ranged-attacks.md",
    lines="2052-2084",
)


def _make_engine_and_combatants() -> tuple[CombatEngine, Creature, Creature]:
    """Fighter-vs-goblin fixture mirroring tests/test_combat.py conventions."""
    engine = CombatEngine(DiceRoller(seed=42))
    fighter_abilities = Abilities(
        strength=16,
        dexterity=14,
        constitution=15,
        intelligence=10,
        wisdom=12,
        charisma=8,
    )
    goblin_abilities = Abilities(
        strength=8,
        dexterity=14,
        constitution=10,
        intelligence=10,
        wisdom=8,
        charisma=8,
    )
    fighter = Creature(name="Fighter", max_hp=20, ac=16, abilities=fighter_abilities)
    goblin = Creature(name="Goblin", max_hp=7, ac=15, abilities=goblin_abilities)
    return engine, fighter, goblin


class TestRange_TwoRangeWeapons:
    """SRD § Playing the Game › Ranged Attacks › Range (two-range weapons).

    > Some ranged attacks, such as those made with a Longbow, have two
    > ranges. The smaller number is the normal range, and the larger
    > number is the long range. Your attack roll has Disadvantage when
    > your target is beyond normal range, and you can't attack a target
    > beyond long range.
    """

    def test_disadvantage_flag_produces_disadvantaged_attack(self):
        """Engine surface honors `disadvantage=True` on resolve_attack().

        Verifies the d20 mechanism: when a caller determines a ranged
        attack is at long range and opts in via the flag, the engine
        produces a disadvantaged attack roll.
        """
        engine, fighter, goblin = _make_engine_and_combatants()

        result = engine.resolve_attack(
            attacker=fighter,
            defender=goblin,
            attack_bonus=5,
            damage_dice="1d8+3",
            disadvantage=True,
        )

        assert result.disadvantage is True
        assert 1 <= result.attack_roll <= 20

    def test_engine_auto_computes_long_range_disadvantage_from_positions(self):
        pytest.skip(
            "GAP: engine's execute_player_attack does not compute distance "
            "or auto-set disadvantage from attacker/target positions. "
            "Clients compute it themselves — see "
            "client-2d/src/client_2d/session.py:993 "
            "(`in_long_range = distance_ft > normal_range`) and "
            "dnd_engine/scenarios/script_executor.py:214 "
            "(`last_attack_disadvantage = distance > normal_range`). "
            "A new third-party client would silently miss the rule. "
            "Open question: should the engine own positional checks?"
        )

    def test_attack_beyond_long_range_is_rejected_by_engine(self):
        pytest.skip(
            "GAP: engine accepts any distance. Range rejection lives at "
            "the client layer: client-2d/src/client_2d/session.py:982 "
            "(`if distance_ft > max_range: return 'Out of range!'`) and "
            "dnd_engine/scenarios/script_executor.py:207 "
            "(`if distance > max_range: ... last_attack_error = ...`). "
            "Engine performs no check, so a buggy or new client could "
            "execute attacks from arbitrary distances."
        )


class TestRange_SingleRangeAttacks:
    """SRD § Playing the Game › Ranged Attacks › Range (single-range attacks).

    > If a ranged attack, such as one made with a spell, has a single
    > range, you can't attack a target beyond this range.
    """

    def test_single_range_spell_attack_rejected_beyond_range(self):
        pytest.skip(
            "GAP: spell-range enforcement not yet audited. Weapon ranges "
            "are enforced (partially, at client layer); spell attack "
            "ranges may use a different code path. Requires the "
            "spellcasting SRD section audit to confirm/deny. Cross-link "
            "from docs/srd/playing-the-game/spellcasting/ when audited."
        )


class TestCloseCombat:
    """SRD § Playing the Game › Ranged Attacks › Ranged Attacks in Close Combat.

    > When you make a ranged attack roll with a weapon, a spell, or
    > some other means, you have Disadvantage on the roll if you are
    > within 5 feet of an enemy who can see you and doesn't have the
    > Incapacitated condition.
    """

    def test_attacker_within_5ft_of_seeing_enemy_has_disadvantage(self):
        """Adjacent (≤5 ft / Chebyshev 1) hostile creature imposes disadvantage."""
        _, _, goblin = _make_engine_and_combatants()
        # Fighter at (5,5), goblin one square east — 5 ft.
        enemies = [((6, 5), goblin)]
        assert is_close_combat_ranged_disadvantage((5, 5), enemies) is True

    def test_no_disadvantage_when_adjacent_enemy_is_incapacitated(self):
        """SRD carve-out: Incapacitated enemy doesn't impose disadvantage."""
        _, _, goblin = _make_engine_and_combatants()
        goblin.add_condition("incapacitated")
        enemies = [((6, 5), goblin)]
        assert is_close_combat_ranged_disadvantage((5, 5), enemies) is False

    def test_no_disadvantage_when_adjacent_enemy_cannot_see_attacker(self):
        """SRD carve-out: enemy that can't see the attacker doesn't threaten.

        Exercises both engine-side blindness (Blinded condition) and the
        caller-supplied visibility hook (e.g. attacker is invisible).
        """
        _, _, goblin = _make_engine_and_combatants()

        # Blinded enemy: engine-tracked condition, no callback needed.
        goblin.add_condition("blinded")
        enemies = [((6, 5), goblin)]
        assert is_close_combat_ranged_disadvantage((5, 5), enemies) is False
        goblin.remove_condition("blinded")

        # Invisible attacker: visibility callback returns False for any enemy.
        assert (
            is_close_combat_ranged_disadvantage(
                (5, 5),
                enemies,
                attacker_visible_to=lambda _enemy: False,
            )
            is False
        )
