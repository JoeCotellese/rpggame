# ABOUTME: SRD conformance audit for "Playing the Game > Melee Attacks".
# ABOUTME: Cross-references docs/srd/playing-the-game/melee-attacks.md against engine code.

"""SRD conformance: Melee Attacks.

Maps every rule in `docs/srd/playing-the-game/melee-attacks.md` to a
test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dnd_engine.core.combat import CombatEngine
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.scenarios.script_executor import _attack_range_for

pytestmark = pytest.mark.srd(
    "playing-the-game/melee-attacks.md",
    lines="2085-2115",
)


MONSTERS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "monsters.json"
)


def _make_engine_and_combatants() -> tuple[CombatEngine, Creature, Creature]:
    """Fighter-vs-goblin fixture mirroring the ranged-attacks pilot."""
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


class TestMeleeAttack_Definition:
    """SRD § Playing the Game › Melee Attacks › Definition.

    > A melee attack allows you to attack a target within your reach. A
    > melee attack typically uses a handheld weapon or an Unarmed
    > Strike. Many monsters make melee attacks with claws, teeth, or
    > other body parts. A few spells also involve melee attacks.
    """

    def test_resolve_attack_supports_melee_weapon_damage(self):
        """Engine resolves a melee weapon attack and surfaces hit + damage.

        The SRD's broad definition is satisfied by the engine accepting
        a melee weapon's damage dice (longsword: 1d8) on its core
        attack surface.
        """
        engine, fighter, goblin = _make_engine_and_combatants()

        result = engine.resolve_attack(
            attacker=fighter,
            defender=goblin,
            attack_bonus=5,
            damage_dice="1d8+3",
        )

        assert result.attack_roll >= 1
        assert hasattr(result, "hit")
        assert hasattr(result, "damage")


class TestReach_DefaultFiveFeet:
    """SRD § Playing the Game › Melee Attacks › Reach (default).

    > A creature has a 5-foot reach and can thus attack targets within
    > 5 feet when making a melee attack.
    """

    def test_melee_weapon_defaults_to_five_foot_reach(self):
        """`_attack_range_for(longsword)` returns (5, 5).

        Verifies the default-reach contract used by the scenario
        script executor when validating attack distances. Longsword has
        no `range`, no `thrown` property, so the helper falls through
        to the melee default.
        """
        longsword = {
            "name": "Longsword",
            "category": "melee",
            "properties": ["versatile"],
        }

        assert _attack_range_for(longsword) == (5, 5)

    def test_unspecified_weapon_falls_back_to_five_foot_reach(self):
        """Missing weapon data still yields 5-ft reach.

        Unarmed Strikes and partial item rows must not silently widen
        reach. The helper's `not weapon_data` branch defends this.
        """
        assert _attack_range_for(None) == (5, 5)
        assert _attack_range_for({}) == (5, 5)


class TestReach_GreaterThanFiveFeet:
    """SRD § Playing the Game › Melee Attacks › Reach (creatures with more).

    > Certain creatures have melee attacks with a reach greater than 5
    > feet, as noted in their descriptions.
    """

    def test_monster_data_encodes_extended_reach(self):
        """monsters.json carries explicit `reach` per attack action.

        Data-parity check: at least one monster action declares a
        reach greater than the default. Confirms the SRD's "noted in
        their descriptions" clause is reflected in the catalog.
        """
        monsters = json.loads(MONSTERS_JSON.read_text())

        extended = [
            (mid, action["name"], action["reach"])
            for mid, mdata in monsters.items()
            for action in (mdata.get("actions") or [])
            if action.get("reach") and action["reach"] != "5 ft."
        ]

        assert extended, (
            "Expected at least one monster action with reach > 5 ft. "
            "in monsters.json (e.g., bearded_devil: Glaive 10 ft.)."
        )

    def test_extended_reach_data_is_consumed_by_attack_resolution(self):
        pytest.skip(
            "GAP: monster `reach` data in monsters.json is not read by "
            'any attack-resolution code path. Grep for `"reach"` '
            "across dnd-engine/dnd_engine/ outside of monsters.json "
            "returns only script_executor._attack_range_for, which "
            "operates on items.json (player weapons), not monster "
            "actions. A bearded devil's Glaive (10 ft. reach) and a "
            "goblin's Scimitar (5 ft. reach) behave identically. "
            "Combat is room-scoped with no per-creature positions on "
            "the engine side, so reach is effectively a flavor field. "
            "Tracked by issue #411."
        )


class TestOpportunityAttacks_Triggering:
    """SRD § Playing the Game › Melee Attacks › Opportunity Attacks (trigger).

    > Combatants watch for enemies to drop their guard. If you move
    > heedlessly past your foes, you put yourself in danger by
    > provoking an Opportunity Attack.
    > [...]
    > You can make an Opportunity Attack when a creature that you can
    > see leaves your reach.
    """

    def test_fleeing_party_provokes_one_attack_per_living_enemy(self):
        """`flee_combat` exposes the OA fan-out contract.

        This is the engine's only OA-equivalent today: a batch reaction
        triggered by `flee_combat()`. Each living enemy makes one
        attack against a random living party member (game_state.py
        :4222-4264). The mechanic captures the SRD's spirit (movement
        out of reach provokes) for the flee case only. We assert the
        callable exists and returns the documented OA payload shape —
        full behavioral exercise lives in integration tests that own
        a full GameState fixture.
        """
        import inspect

        from dnd_engine.core.game_state import GameState

        assert callable(getattr(GameState, "flee_combat", None))
        src = inspect.getsource(GameState.flee_combat)
        assert "opportunity_attacks" in src, (
            "flee_combat must surface an `opportunity_attacks` field "
            "documenting per-enemy OA results."
        )
        assert "living_enemies" in src and "resolve_attack" in src, (
            "flee_combat must iterate living enemies and resolve one "
            "attack per enemy to model OA fan-out."
        )

    def test_tactical_movement_out_of_reach_provokes_opportunity_attack(self):
        pytest.skip(
            "GAP: OAs do not fire on normal tactical movement during "
            "combat. The engine's only OA path is "
            "dnd_engine/core/game_state.py:4190 `flee_combat()`, which "
            "fires when the *party as a whole* attempts to retreat to "
            "the previous room. There is no per-creature position "
            "model on the engine side during combat (room-scoped), so "
            "a creature moving out of an adjacent enemy's reach during "
            "its own turn does not provoke. Tracked by issue #413 "
            "(depends on #412 Reaction economy)."
        )


class TestOpportunityAttacks_Avoidance:
    """SRD § Playing the Game › Melee Attacks › Avoiding OAs.

    > You can avoid provoking an Opportunity Attack by taking the
    > Disengage action. You also don't provoke an Opportunity Attack
    > when you Teleport or when you are moved without using your
    > movement, action, Bonus Action, or Reaction.
    """

    def test_disengage_action_prevents_opportunity_attack(self):
        pytest.skip(
            "GAP: Disengage is not a playable action. The string "
            "'Disengage' appears only as flavor text in "
            "dnd_engine/data/srd/classes.json (rogue cunning action) "
            "and dnd_engine/data/srd/monsters.json (goblin Nimble "
            "Escape, spy). No action handler, dispatcher, or "
            "movement-flag is wired up — a player cannot choose "
            "Disengage to avoid OAs. Tracked by issue #414 "
            "(depends on #413 per-creature OAs)."
        )

    def test_involuntary_movement_does_not_provoke(self):
        pytest.skip(
            "GAP: dependent on per-creature OA system existing first. "
            "SRD carves out exceptions for Teleport and movement "
            "that doesn't use the creature's own action economy "
            "(e.g., shoved, hurled by an explosion). The engine has "
            "no OA system on tactical movement, so the exception is "
            "moot until that's built. Tracked under issue #413."
        )


class TestOpportunityAttacks_Mechanics:
    """SRD § Playing the Game › Melee Attacks › Making an OA.

    > You can make an Opportunity Attack when a creature that you can
    > see leaves your reach. To make the attack, take a Reaction to
    > make one melee attack with a weapon or an Unarmed Strike against
    > that creature. The attack occurs right before it leaves your
    > reach.
    """

    def test_opportunity_attack_consumes_attackers_reaction(self):
        pytest.skip(
            "GAP: Reaction economy is not modeled. `flee_combat()` "
            "fans out one attack per living enemy without checking or "
            "consuming a Reaction (dnd_engine/core/game_state.py:4222"
            "-4264). An enemy could in principle OA on every flee and "
            "still react to other triggers in the same round. Tracked "
            "by issue #412. Cross-link from "
            "docs/srd/playing-the-game/reactions.md when that section "
            "is audited."
        )

    def test_opportunity_attack_requires_seeing_the_provoker(self):
        pytest.skip(
            "GAP: visibility is not consulted by `flee_combat()`. The "
            "SRD requires that the OA-maker can see the creature "
            "leaving reach (e.g., an invisible creature provokes no "
            "OA from a sighted-only enemy). Engine-side combat has "
            "no visibility/perception query exposed to attack "
            "resolution. Tracked under issue #413 (per-creature OA "
            "system is the prerequisite)."
        )
