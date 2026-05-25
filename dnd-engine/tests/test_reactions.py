# ABOUTME: Unit tests for the trigger->Reaction dispatcher
# ABOUTME: Verifies per-creature consumption, initiative ordering, and trigger isolation

from __future__ import annotations

import pytest

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.systems.action_economy import ActionType
from dnd_engine.systems.initiative import InitiativeTracker
from dnd_engine.systems.reactions import (
    ReactionDispatcher,
    ReactionHandler,
    ReactionOutcome,
    Trigger,
    TriggerContext,
)


def _make_creature(name: str, hp: int = 20, dex: int = 10) -> Creature:
    abilities = Abilities(10, dex, 10, 10, 10, 10)
    return Creature(name, max_hp=hp, ac=15, abilities=abilities)


def _make_tracker(*creatures: Creature, initiatives: list[int] | None = None) -> InitiativeTracker:
    """Build a tracker with deterministic initiative.

    Adds each creature, then overwrites ``initiative_roll`` from the
    ``initiatives`` list (high first matches list order) so tests can
    assert ordering without flake.
    """
    tracker = InitiativeTracker(DiceRoller(seed=1))
    for creature in creatures:
        tracker.add_combatant(creature)
    if initiatives is not None:
        assert len(initiatives) == len(creatures)
        for creature, roll in zip(creatures, initiatives, strict=True):
            for entry in tracker.combatants:
                if entry.creature is creature:
                    entry.initiative_roll = roll
        tracker._sort_initiative()
        tracker.current_turn_index = 0
    return tracker


def _reacts_with(description: str, **data) -> ReactionHandler:
    def handler(context: TriggerContext) -> ReactionOutcome:
        return ReactionOutcome(reacted=True, description=description, data=data)

    return handler


def _declines(context: TriggerContext) -> ReactionOutcome:
    return ReactionOutcome(reacted=False)


class TestTriggerEnum:
    def test_initial_triggers(self):
        """The three triggers callers need first are all present."""
        assert Trigger.OPPORTUNITY_PROVOKED.value == "opportunity_provoked"
        assert Trigger.WOULD_BE_HIT.value == "would_be_hit"
        assert Trigger.SPELL_CAST_OBSERVED.value == "spell_cast_observed"


class TestSubscription:
    def test_register_then_publish_invokes_handler(self):
        reactor = _make_creature("Wizard")
        attacker = _make_creature("Goblin")
        tracker = _make_tracker(reactor, attacker)
        dispatcher = ReactionDispatcher(tracker)

        dispatcher.register(reactor, Trigger.WOULD_BE_HIT, _reacts_with("Shield"))
        outcomes = dispatcher.publish(
            TriggerContext(trigger=Trigger.WOULD_BE_HIT, source=attacker)
        )

        assert len(outcomes) == 1
        assert outcomes[0].description == "Shield"

    def test_no_subscribers_returns_empty(self):
        attacker = _make_creature("Goblin")
        tracker = _make_tracker(attacker)
        dispatcher = ReactionDispatcher(tracker)

        outcomes = dispatcher.publish(TriggerContext(trigger=Trigger.WOULD_BE_HIT))

        assert outcomes == []

    def test_unregister_removes_creatures_subscriptions(self):
        reactor = _make_creature("Wizard")
        tracker = _make_tracker(reactor)
        dispatcher = ReactionDispatcher(tracker)

        dispatcher.register(reactor, Trigger.WOULD_BE_HIT, _reacts_with("Shield"))
        dispatcher.unregister(reactor)
        outcomes = dispatcher.publish(TriggerContext(trigger=Trigger.WOULD_BE_HIT))

        assert outcomes == []

    def test_last_subscription_wins_for_same_creature_and_trigger(self):
        """Re-subscribing the same creature/trigger pair replaces the handler.

        Matches how features upgrade: the new variant overrides the old.
        """
        reactor = _make_creature("Wizard")
        tracker = _make_tracker(reactor)
        dispatcher = ReactionDispatcher(tracker)

        dispatcher.register(reactor, Trigger.WOULD_BE_HIT, _reacts_with("OldShield"))
        dispatcher.register(reactor, Trigger.WOULD_BE_HIT, _reacts_with("NewShield"))
        outcomes = dispatcher.publish(TriggerContext(trigger=Trigger.WOULD_BE_HIT))

        assert len(outcomes) == 1
        assert outcomes[0].description == "NewShield"


class TestSlotConsumption:
    def test_reacting_consumes_reaction_slot(self):
        reactor = _make_creature("Wizard")
        tracker = _make_tracker(reactor)
        dispatcher = ReactionDispatcher(tracker)

        dispatcher.register(reactor, Trigger.WOULD_BE_HIT, _reacts_with("Shield"))
        dispatcher.publish(TriggerContext(trigger=Trigger.WOULD_BE_HIT))

        assert tracker.turn_states[reactor].reaction_available is False

    def test_second_publish_same_round_does_not_refire(self):
        """SRD: 'you can't take another one until the start of your next turn'."""
        reactor = _make_creature("Wizard")
        tracker = _make_tracker(reactor)
        dispatcher = ReactionDispatcher(tracker)

        dispatcher.register(reactor, Trigger.WOULD_BE_HIT, _reacts_with("Shield"))
        dispatcher.publish(TriggerContext(trigger=Trigger.WOULD_BE_HIT))
        outcomes = dispatcher.publish(TriggerContext(trigger=Trigger.WOULD_BE_HIT))

        assert outcomes == []

    def test_declined_handler_does_not_consume_slot(self):
        reactor = _make_creature("Wizard")
        tracker = _make_tracker(reactor)
        dispatcher = ReactionDispatcher(tracker)

        dispatcher.register(reactor, Trigger.WOULD_BE_HIT, _declines)
        outcomes = dispatcher.publish(TriggerContext(trigger=Trigger.WOULD_BE_HIT))

        assert outcomes == []
        assert tracker.turn_states[reactor].reaction_available is True

    def test_slot_already_consumed_skips_handler(self):
        """A handler must not be invoked when the slot is already spent.

        Otherwise a declining handler called twice could cost CPU /
        produce log noise without consuming anything. Eligibility is
        gated *before* invocation.
        """
        reactor = _make_creature("Wizard")
        tracker = _make_tracker(reactor)
        dispatcher = ReactionDispatcher(tracker)
        tracker.turn_states[reactor].consume_action(ActionType.REACTION)

        invocations: list[TriggerContext] = []

        def handler(context: TriggerContext) -> ReactionOutcome:
            invocations.append(context)
            return ReactionOutcome(reacted=False)

        dispatcher.register(reactor, Trigger.WOULD_BE_HIT, handler)
        dispatcher.publish(TriggerContext(trigger=Trigger.WOULD_BE_HIT))

        assert invocations == []

    def test_slot_resets_when_reactors_own_turn_comes_around(self):
        """Integration with InitiativeTracker.next_turn: slot refills on own turn."""
        reactor = _make_creature("Wizard")
        other = _make_creature("Goblin")
        # Reactor first in initiative so its first turn is already current.
        tracker = _make_tracker(reactor, other, initiatives=[20, 10])
        dispatcher = ReactionDispatcher(tracker)

        dispatcher.register(reactor, Trigger.WOULD_BE_HIT, _reacts_with("Shield"))
        dispatcher.publish(TriggerContext(trigger=Trigger.WOULD_BE_HIT))
        assert tracker.turn_states[reactor].reaction_available is False

        # Advance to other creature: reactor's slot must stay empty.
        tracker.next_turn()
        assert tracker.turn_states[reactor].reaction_available is False
        outcomes_mid = dispatcher.publish(TriggerContext(trigger=Trigger.WOULD_BE_HIT))
        assert outcomes_mid == []

        # Advance back to reactor: TurnState.reset() refills the slot.
        tracker.next_turn()
        assert tracker.turn_states[reactor].reaction_available is True
        outcomes_next = dispatcher.publish(TriggerContext(trigger=Trigger.WOULD_BE_HIT))
        assert len(outcomes_next) == 1


class TestEligibility:
    def test_dead_reactor_is_skipped(self):
        reactor = _make_creature("Wizard", hp=10)
        tracker = _make_tracker(reactor)
        dispatcher = ReactionDispatcher(tracker)
        reactor.current_hp = 0

        invocations: list[TriggerContext] = []

        def handler(context: TriggerContext) -> ReactionOutcome:
            invocations.append(context)
            return ReactionOutcome(reacted=True)

        dispatcher.register(reactor, Trigger.WOULD_BE_HIT, handler)
        outcomes = dispatcher.publish(TriggerContext(trigger=Trigger.WOULD_BE_HIT))

        assert invocations == []
        assert outcomes == []

    def test_creature_not_in_initiative_is_skipped(self):
        """A creature without a TurnState slot can't react.

        Reactions are an in-combat resource; non-combatants are not
        eligible. The dispatcher tolerates stale subscriptions
        (e.g., a creature was removed mid-encounter) by checking
        turn_states membership.
        """
        outside_creature = _make_creature("Bystander")
        tracker = _make_tracker()  # empty initiative
        dispatcher = ReactionDispatcher(tracker)

        dispatcher.register(outside_creature, Trigger.WOULD_BE_HIT, _reacts_with("Shield"))
        outcomes = dispatcher.publish(TriggerContext(trigger=Trigger.WOULD_BE_HIT))

        assert outcomes == []

    def test_unrelated_trigger_does_not_fire_handler(self):
        reactor = _make_creature("Wizard")
        tracker = _make_tracker(reactor)
        dispatcher = ReactionDispatcher(tracker)

        dispatcher.register(reactor, Trigger.WOULD_BE_HIT, _reacts_with("Shield"))
        outcomes = dispatcher.publish(
            TriggerContext(trigger=Trigger.OPPORTUNITY_PROVOKED)
        )

        assert outcomes == []
        assert tracker.turn_states[reactor].reaction_available is True


class TestInitiativeOrder:
    def test_outcomes_returned_in_initiative_order(self):
        first = _make_creature("HighInit")
        second = _make_creature("MidInit")
        third = _make_creature("LowInit")
        tracker = _make_tracker(first, second, third, initiatives=[20, 15, 5])
        dispatcher = ReactionDispatcher(tracker)

        dispatcher.register(third, Trigger.OPPORTUNITY_PROVOKED, _reacts_with("low"))
        dispatcher.register(first, Trigger.OPPORTUNITY_PROVOKED, _reacts_with("high"))
        dispatcher.register(second, Trigger.OPPORTUNITY_PROVOKED, _reacts_with("mid"))

        outcomes = dispatcher.publish(
            TriggerContext(trigger=Trigger.OPPORTUNITY_PROVOKED)
        )

        assert [o.description for o in outcomes] == ["high", "mid", "low"]

    def test_all_eligible_reactors_consume_their_own_slots(self):
        a = _make_creature("A")
        b = _make_creature("B")
        tracker = _make_tracker(a, b, initiatives=[20, 10])
        dispatcher = ReactionDispatcher(tracker)

        dispatcher.register(a, Trigger.OPPORTUNITY_PROVOKED, _reacts_with("a"))
        dispatcher.register(b, Trigger.OPPORTUNITY_PROVOKED, _reacts_with("b"))

        dispatcher.publish(TriggerContext(trigger=Trigger.OPPORTUNITY_PROVOKED))

        assert tracker.turn_states[a].reaction_available is False
        assert tracker.turn_states[b].reaction_available is False


class TestTriggerContext:
    def test_handler_observes_source_and_payload(self):
        reactor = _make_creature("Wizard")
        caster = _make_creature("EnemyCaster")
        tracker = _make_tracker(reactor, caster)
        dispatcher = ReactionDispatcher(tracker)

        observed: list[TriggerContext] = []

        def handler(context: TriggerContext) -> ReactionOutcome:
            observed.append(context)
            return ReactionOutcome(reacted=True)

        dispatcher.register(reactor, Trigger.SPELL_CAST_OBSERVED, handler)
        dispatcher.publish(
            TriggerContext(
                trigger=Trigger.SPELL_CAST_OBSERVED,
                source=caster,
                payload={"spell_id": "fireball", "level": 3},
            )
        )

        assert len(observed) == 1
        assert observed[0].source is caster
        assert observed[0].payload == {"spell_id": "fireball", "level": 3}


class TestMidTurnPauseAndResume:
    """Reactions firing on someone else's turn pause the active turn.

    SRD § Reactions › Interrupted-turn continuation:
    > If the reaction interrupts another creature's turn, that
    > creature can continue its turn right after the Reaction.
    """

    def test_handler_observes_reactor_as_current_combatant(self):
        goblin = _make_creature("Goblin")
        wizard = _make_creature("Wizard")
        # Goblin first in initiative — its turn is current.
        tracker = _make_tracker(goblin, wizard, initiatives=[20, 10])
        dispatcher = ReactionDispatcher(tracker)
        assert tracker.get_current_combatant().creature is goblin

        observed: list[Creature] = []

        def handler(ctx: TriggerContext) -> ReactionOutcome:
            observed.append(tracker.get_current_combatant().creature)
            return ReactionOutcome(reacted=True)

        dispatcher.register(wizard, Trigger.WOULD_BE_HIT, handler)
        dispatcher.publish(
            TriggerContext(trigger=Trigger.WOULD_BE_HIT, source=goblin)
        )

        assert observed == [wizard]

    def test_current_combatant_restored_after_publish(self):
        goblin = _make_creature("Goblin")
        wizard = _make_creature("Wizard")
        tracker = _make_tracker(goblin, wizard, initiatives=[20, 10])
        dispatcher = ReactionDispatcher(tracker)

        dispatcher.register(wizard, Trigger.WOULD_BE_HIT, _reacts_with("Shield"))
        dispatcher.publish(TriggerContext(trigger=Trigger.WOULD_BE_HIT))

        assert tracker.get_current_combatant().creature is goblin
        assert tracker.is_paused_for_reaction is False

    def test_interrupted_creature_turn_state_unchanged(self):
        """The interrupted creature must resume on the same TurnState."""
        goblin = _make_creature("Goblin")
        wizard = _make_creature("Wizard")
        tracker = _make_tracker(goblin, wizard, initiatives=[20, 10])
        dispatcher = ReactionDispatcher(tracker)
        # Goblin mid-turn: action spent, half movement spent.
        tracker.turn_states[goblin].consume_action(ActionType.ACTION)
        tracker.turn_states[goblin].consume_movement(15)

        dispatcher.register(wizard, Trigger.WOULD_BE_HIT, _reacts_with("Shield"))
        dispatcher.publish(TriggerContext(trigger=Trigger.WOULD_BE_HIT))

        assert tracker.turn_states[goblin].action_available is False
        assert tracker.turn_states[goblin].movement_remaining == 15

    def test_no_pause_when_reactor_is_current_combatant(self):
        """A reactor on their own turn doesn't trigger a pause swap.

        Slice spec: pause only when reactor != current actor. Without
        this guard the dispatcher would self-pause and the stack would
        grow even for own-turn reactions.
        """
        fighter = _make_creature("Fighter")
        tracker = _make_tracker(fighter)
        dispatcher = ReactionDispatcher(tracker)
        assert tracker.get_current_combatant().creature is fighter

        observed_paused: list[bool] = []

        def handler(ctx: TriggerContext) -> ReactionOutcome:
            observed_paused.append(tracker.is_paused_for_reaction)
            return ReactionOutcome(reacted=True)

        dispatcher.register(fighter, Trigger.OPPORTUNITY_PROVOKED, handler)
        dispatcher.publish(TriggerContext(trigger=Trigger.OPPORTUNITY_PROVOKED))

        assert observed_paused == [False]
        assert tracker.is_paused_for_reaction is False

    def test_pause_released_even_when_handler_raises(self):
        """Pause stack must unwind even when a handler errors out.

        Without try/finally, a buggy reactor would strand the tracker
        in a paused state, corrupting all subsequent
        get_current_combatant calls.
        """
        goblin = _make_creature("Goblin")
        wizard = _make_creature("Wizard")
        tracker = _make_tracker(goblin, wizard, initiatives=[20, 10])
        dispatcher = ReactionDispatcher(tracker)

        def boom(ctx: TriggerContext) -> ReactionOutcome:
            raise RuntimeError("handler exploded")

        dispatcher.register(wizard, Trigger.WOULD_BE_HIT, boom)

        with pytest.raises(RuntimeError, match="handler exploded"):
            dispatcher.publish(TriggerContext(trigger=Trigger.WOULD_BE_HIT))

        assert tracker.is_paused_for_reaction is False
        assert tracker.get_current_combatant().creature is goblin


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
