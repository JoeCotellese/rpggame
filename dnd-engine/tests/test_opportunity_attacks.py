# ABOUTME: Unit tests for Opportunity Attack scaffolding on the ReactionDispatcher
# ABOUTME: Verifies reach-check geometry, slot consumption, and per-reactor eligibility

from __future__ import annotations

import pytest

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.position import Position
from dnd_engine.systems.action_economy import ActionType
from dnd_engine.systems.initiative import InitiativeTracker
from dnd_engine.systems.opportunity_attacks import (
    publish_movement_provoke,
    register_default_opportunity_attack,
)
from dnd_engine.systems.reactions import ReactionDispatcher


def _make_creature(name: str) -> Creature:
    abilities = Abilities(10, 10, 10, 10, 10, 10)
    return Creature(name, max_hp=20, ac=15, abilities=abilities)


def _make_tracker(*creatures: Creature) -> InitiativeTracker:
    tracker = InitiativeTracker(DiceRoller(seed=1))
    for creature in creatures:
        tracker.add_combatant(creature)
    return tracker


class TestRegisterDefaultOpportunityAttack:
    def test_mover_leaving_reach_provokes_reaction(self):
        reactor = _make_creature("Fighter")
        mover = _make_creature("Goblin")
        tracker = _make_tracker(reactor, mover)
        dispatcher = ReactionDispatcher(tracker)
        register_default_opportunity_attack(
            dispatcher, reactor, get_position=lambda: Position(5, 5)
        )

        # Goblin starts adjacent to Fighter, then steps to a non-adjacent tile.
        outcomes = publish_movement_provoke(
            dispatcher,
            mover=mover,
            from_position=Position(6, 5),
            to_position=Position(8, 5),
        )

        assert len(outcomes) == 1
        outcome = outcomes[0]
        assert outcome.reacted is True
        assert outcome.data["attacker"] is reactor
        assert outcome.data["target"] is mover
        assert outcome.data["attack_kind"] == "melee_opportunity"
        assert outcome.data["reach_feet"] == 5

    def test_lateral_move_keeping_adjacency_does_not_provoke(self):
        reactor = _make_creature("Fighter")
        mover = _make_creature("Goblin")
        tracker = _make_tracker(reactor, mover)
        dispatcher = ReactionDispatcher(tracker)
        register_default_opportunity_attack(
            dispatcher, reactor, get_position=lambda: Position(5, 5)
        )

        # Goblin slides around the Fighter but stays within 5 ft.
        outcomes = publish_movement_provoke(
            dispatcher,
            mover=mover,
            from_position=Position(6, 5),
            to_position=Position(6, 6),
        )

        assert outcomes == []
        assert tracker.turn_states[reactor].reaction_available is True

    def test_move_starting_out_of_reach_does_not_provoke(self):
        """Entering reach (or moving while already out of reach) is not an OA.

        SRD: "an OA fires when a creature you can see *leaves* your
        reach." Approaching is not a provoke; the trigger has to be a
        reach-to-no-reach transition.
        """
        reactor = _make_creature("Fighter")
        mover = _make_creature("Goblin")
        tracker = _make_tracker(reactor, mover)
        dispatcher = ReactionDispatcher(tracker)
        register_default_opportunity_attack(
            dispatcher, reactor, get_position=lambda: Position(5, 5)
        )

        # Goblin was already non-adjacent and stays non-adjacent.
        outcomes = publish_movement_provoke(
            dispatcher,
            mover=mover,
            from_position=Position(10, 10),
            to_position=Position(11, 10),
        )

        assert outcomes == []

    def test_move_entering_reach_does_not_provoke(self):
        reactor = _make_creature("Fighter")
        mover = _make_creature("Goblin")
        tracker = _make_tracker(reactor, mover)
        dispatcher = ReactionDispatcher(tracker)
        register_default_opportunity_attack(
            dispatcher, reactor, get_position=lambda: Position(5, 5)
        )

        # Goblin steps from non-adjacent into adjacency.
        outcomes = publish_movement_provoke(
            dispatcher,
            mover=mover,
            from_position=Position(7, 5),
            to_position=Position(6, 5),
        )

        assert outcomes == []
        assert tracker.turn_states[reactor].reaction_available is True

    def test_reactor_does_not_oa_itself(self):
        """A creature moving itself cannot trigger its own OA."""
        reactor = _make_creature("Fighter")
        tracker = _make_tracker(reactor)
        dispatcher = ReactionDispatcher(tracker)
        register_default_opportunity_attack(
            dispatcher, reactor, get_position=lambda: Position(5, 5)
        )

        outcomes = publish_movement_provoke(
            dispatcher,
            mover=reactor,
            from_position=Position(6, 5),
            to_position=Position(8, 5),
        )

        assert outcomes == []
        assert tracker.turn_states[reactor].reaction_available is True

    def test_unplaced_reactor_does_not_react(self):
        """When get_position returns None, the reactor has no reach to defend."""
        reactor = _make_creature("Fighter")
        mover = _make_creature("Goblin")
        tracker = _make_tracker(reactor, mover)
        dispatcher = ReactionDispatcher(tracker)
        register_default_opportunity_attack(
            dispatcher, reactor, get_position=lambda: None
        )

        outcomes = publish_movement_provoke(
            dispatcher,
            mover=mover,
            from_position=Position(6, 5),
            to_position=Position(8, 5),
        )

        assert outcomes == []
        assert tracker.turn_states[reactor].reaction_available is True

    def test_reach_weapon_provokes_at_extended_range(self):
        """A 10 ft reach weapon threatens 2 squares, not 1."""
        reactor = _make_creature("Fighter")
        mover = _make_creature("Goblin")
        tracker = _make_tracker(reactor, mover)
        dispatcher = ReactionDispatcher(tracker)
        register_default_opportunity_attack(
            dispatcher,
            reactor,
            get_position=lambda: Position(5, 5),
            reach_feet=10,
        )

        # Goblin was 10 ft away (2 squares); steps to 15 ft (3 squares).
        outcomes = publish_movement_provoke(
            dispatcher,
            mover=mover,
            from_position=Position(7, 5),
            to_position=Position(8, 5),
        )

        assert len(outcomes) == 1
        assert outcomes[0].data["reach_feet"] == 10


class TestSlotConsumption:
    def test_provoking_oa_consumes_reactors_reaction_slot(self):
        reactor = _make_creature("Fighter")
        mover = _make_creature("Goblin")
        tracker = _make_tracker(reactor, mover)
        dispatcher = ReactionDispatcher(tracker)
        register_default_opportunity_attack(
            dispatcher, reactor, get_position=lambda: Position(5, 5)
        )

        publish_movement_provoke(
            dispatcher,
            mover=mover,
            from_position=Position(6, 5),
            to_position=Position(8, 5),
        )

        assert tracker.turn_states[reactor].reaction_available is False

    def test_second_provoke_same_round_does_not_fire_oa(self):
        """SRD once-per-round: a reactor can't OA twice between their turns."""
        reactor = _make_creature("Fighter")
        mover = _make_creature("Goblin")
        tracker = _make_tracker(reactor, mover)
        dispatcher = ReactionDispatcher(tracker)
        register_default_opportunity_attack(
            dispatcher, reactor, get_position=lambda: Position(5, 5)
        )

        publish_movement_provoke(
            dispatcher,
            mover=mover,
            from_position=Position(6, 5),
            to_position=Position(8, 5),
        )
        # Mover wanders back and leaves again in the same round.
        outcomes = publish_movement_provoke(
            dispatcher,
            mover=mover,
            from_position=Position(6, 5),
            to_position=Position(9, 5),
        )

        assert outcomes == []

    def test_oa_slot_already_consumed_blocks_handler(self):
        reactor = _make_creature("Fighter")
        mover = _make_creature("Goblin")
        tracker = _make_tracker(reactor, mover)
        dispatcher = ReactionDispatcher(tracker)
        register_default_opportunity_attack(
            dispatcher, reactor, get_position=lambda: Position(5, 5)
        )
        tracker.turn_states[reactor].consume_action(ActionType.REACTION)

        outcomes = publish_movement_provoke(
            dispatcher,
            mover=mover,
            from_position=Position(6, 5),
            to_position=Position(8, 5),
        )

        assert outcomes == []


class TestMultipleReactors:
    def test_only_threatening_reactors_react(self):
        """Two enemies, only one in reach — only that one reacts."""
        threat = _make_creature("Threat")
        bystander = _make_creature("Bystander")
        mover = _make_creature("Goblin")
        tracker = _make_tracker(threat, bystander, mover)
        dispatcher = ReactionDispatcher(tracker)
        register_default_opportunity_attack(
            dispatcher, threat, get_position=lambda: Position(5, 5)
        )
        register_default_opportunity_attack(
            dispatcher, bystander, get_position=lambda: Position(20, 20)
        )

        outcomes = publish_movement_provoke(
            dispatcher,
            mover=mover,
            from_position=Position(6, 5),
            to_position=Position(8, 5),
        )

        assert len(outcomes) == 1
        assert outcomes[0].data["attacker"] is threat
        assert tracker.turn_states[threat].reaction_available is False
        assert tracker.turn_states[bystander].reaction_available is True

    def test_two_threatening_reactors_both_oa(self):
        """A mover surrounded by two attackers provokes from both."""
        north = _make_creature("North")
        south = _make_creature("South")
        mover = _make_creature("Goblin")
        tracker = _make_tracker(north, south, mover)
        dispatcher = ReactionDispatcher(tracker)
        register_default_opportunity_attack(
            dispatcher, north, get_position=lambda: Position(5, 4)
        )
        register_default_opportunity_attack(
            dispatcher, south, get_position=lambda: Position(5, 6)
        )

        # Mover starts at (5,5) — adjacent to both — and bolts east to (8,5).
        outcomes = publish_movement_provoke(
            dispatcher,
            mover=mover,
            from_position=Position(5, 5),
            to_position=Position(8, 5),
        )

        assert len(outcomes) == 2
        attackers = {o.data["attacker"] for o in outcomes}
        assert attackers == {north, south}
        assert tracker.turn_states[north].reaction_available is False
        assert tracker.turn_states[south].reaction_available is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
