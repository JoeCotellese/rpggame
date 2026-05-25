# ABOUTME: Integration test for Disengage suppressing Opportunity Attacks
# ABOUTME: Disengage action sets a turn-state flag the OA publish path consults

from __future__ import annotations

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.position import Position
from dnd_engine.systems.actions import disengage
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


class TestDisengageSuppressesOpportunityAttacks:
    def test_disengaged_mover_does_not_provoke_oa(self):
        """SRD: After Disengage, the actor's movement doesn't provoke
        Opportunity Attacks for the rest of the turn."""
        reactor = _make_creature("Fighter")
        mover = _make_creature("Goblin")
        tracker = _make_tracker(reactor, mover)
        dispatcher = ReactionDispatcher(tracker)
        register_default_opportunity_attack(
            dispatcher, reactor, get_position=lambda: Position(5, 5)
        )

        # Goblin takes Disengage on their turn.
        mover_turn = tracker.turn_states[mover]
        ok, _ = disengage(mover_turn)
        assert ok is True
        assert mover_turn.disengaged_this_turn is True

        # Goblin moves out of Fighter's reach — would normally provoke.
        outcomes = publish_movement_provoke(
            dispatcher,
            mover=mover,
            from_position=Position(6, 5),
            to_position=Position(8, 5),
        )

        assert outcomes == []
        # Reaction slot is intact — no OA fired.
        assert tracker.turn_states[reactor].reaction_available is True

    def test_non_disengaged_mover_still_provokes_oa(self):
        """Sanity check: without Disengage, the same movement provokes
        (so the suppression is the difference, not a coincidence)."""
        reactor = _make_creature("Fighter")
        mover = _make_creature("Goblin")
        tracker = _make_tracker(reactor, mover)
        dispatcher = ReactionDispatcher(tracker)
        register_default_opportunity_attack(
            dispatcher, reactor, get_position=lambda: Position(5, 5)
        )

        # Mover does NOT disengage.
        outcomes = publish_movement_provoke(
            dispatcher,
            mover=mover,
            from_position=Position(6, 5),
            to_position=Position(8, 5),
        )

        assert len(outcomes) == 1
        assert outcomes[0].reacted is True

    def test_disengage_flag_only_suppresses_for_one_turn(self):
        """Disengage applies for the rest of the actor's turn. When
        TurnState.reset is called for the actor's next turn, the flag
        clears and subsequent moves provoke again."""
        reactor = _make_creature("Fighter")
        mover = _make_creature("Goblin")
        tracker = _make_tracker(reactor, mover)
        dispatcher = ReactionDispatcher(tracker)
        register_default_opportunity_attack(
            dispatcher, reactor, get_position=lambda: Position(5, 5)
        )

        # Disengage this turn — provoking move is suppressed.
        mover_turn = tracker.turn_states[mover]
        disengage(mover_turn)
        outcomes_now = publish_movement_provoke(
            dispatcher, mover=mover,
            from_position=Position(6, 5), to_position=Position(8, 5),
        )
        assert outcomes_now == []

        # Mover's next turn begins — flag clears.
        mover_turn.reset(speed=mover.speed)
        assert mover_turn.disengaged_this_turn is False

        # Same provoking move now triggers the OA.
        outcomes_next = publish_movement_provoke(
            dispatcher, mover=mover,
            from_position=Position(6, 5), to_position=Position(8, 5),
        )
        assert len(outcomes_next) == 1
        assert outcomes_next[0].reacted is True
