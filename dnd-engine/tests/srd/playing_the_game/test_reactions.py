# ABOUTME: SRD conformance audit for "Playing the Game > Reactions".
# ABOUTME: Cross-references docs/srd/playing-the-game/reactions.md against engine code.

"""SRD conformance: Reactions.

Maps every rule in `docs/srd/playing-the-game/reactions.md` to a test.
Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dnd_engine.systems.action_economy import TurnState

pytestmark = pytest.mark.srd(
    "playing-the-game/reactions.md",
    lines="1438-1451",
)


SPELLS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "spells.json"
)


class TestReaction_Definition:
    """SRD § Playing the Game › Reactions › Definition.

    > Certain special abilities, spells, and situations allow you to
    > take a special action called a Reaction.
    """

    def test_reaction_casting_time_is_a_recognized_spell_timing(self) -> None:
        """At least one SRD spell declares `casting_time: "1 reaction"`.

        Data-parity check: the SRD's "spells [...] allow you to take a
        special action called a Reaction" clause shows up as a real
        casting-time string on at least one spell in `spells.json`
        (e.g., Shield). Confirms the catalog encodes the trigger
        surface, even though the engine's turn loop does not yet
        consume it (see TestReaction_OncePerRound below).
        """
        spells = json.loads(SPELLS_JSON.read_text())
        reaction_spells = [
            (sid, sdata.get("name"))
            for sid, sdata in spells.items()
            if sdata.get("casting_time") == "1 reaction"
        ]
        assert reaction_spells, (
            "Expected at least one spell with `casting_time: '1 reaction'` "
            "in spells.json (e.g., shield)."
        )

    def test_reaction_action_type_is_modeled_in_action_economy(self) -> None:
        """ActionType enumerates REACTION; TurnState tracks reaction_available.

        SRD requires the "special action called a Reaction" to be a
        first-class member of the action economy. Closes the original
        gap captured under issue #412.
        """
        from dnd_engine.systems.action_economy import ActionType

        assert ActionType.REACTION.value == "reaction"
        turn = TurnState()
        assert hasattr(turn, "reaction_available")
        assert turn.reaction_available is True


class TestReaction_TriggerResponse:
    """SRD § Playing the Game › Reactions › Trigger Response.

    > A Reaction is an instant response to a trigger of some kind,
    > which can occur on your turn or on someone else's.
    """

    def test_reaction_can_fire_outside_the_reactors_turn(self) -> None:
        """A Reaction subscribed to a trigger fires regardless of whose turn it is.

        Wizard is second in initiative. Goblin (whose turn it is)
        provokes ``OPPORTUNITY_PROVOKED``; Wizard's handler fires
        even though it is the Goblin's turn, and the Wizard's
        Reaction slot is consumed. Closes #429.
        """
        from dnd_engine.core.creature import Abilities, Creature
        from dnd_engine.core.dice import DiceRoller
        from dnd_engine.systems.initiative import InitiativeTracker
        from dnd_engine.systems.reactions import (
            ReactionDispatcher,
            ReactionOutcome,
            Trigger,
            TriggerContext,
        )

        abilities = Abilities(10, 10, 10, 10, 10, 10)
        goblin = Creature("Goblin", max_hp=10, ac=15, abilities=abilities)
        wizard = Creature("Wizard", max_hp=10, ac=15, abilities=abilities)
        tracker = InitiativeTracker(DiceRoller(seed=1))
        tracker.add_combatant(goblin)
        tracker.add_combatant(wizard)
        # Pin Goblin first in initiative deterministically.
        for entry in tracker.combatants:
            entry.initiative_roll = 20 if entry.creature is goblin else 10
        tracker._sort_initiative()
        tracker.current_turn_index = 0
        # Sanity: the Goblin is the active turn, Wizard is the reactor.
        assert tracker.get_current_combatant().creature is goblin

        dispatcher = ReactionDispatcher(tracker)
        dispatcher.register(
            wizard,
            Trigger.OPPORTUNITY_PROVOKED,
            lambda ctx: ReactionOutcome(reacted=True, description="OA"),
        )

        outcomes = dispatcher.publish(
            TriggerContext(trigger=Trigger.OPPORTUNITY_PROVOKED, source=goblin)
        )

        assert len(outcomes) == 1
        assert tracker.turn_states[wizard].reaction_available is False

    def test_reaction_can_fire_during_the_reactors_own_turn(self) -> None:
        """A reactor may consume its Reaction on its own turn.

        The SRD explicitly allows this (e.g., an OA provoked during
        your turn by another creature's forced movement). The
        dispatcher gates only on ``reaction_available``, not on whose
        turn it is. Closes #429.
        """
        from dnd_engine.core.creature import Abilities, Creature
        from dnd_engine.core.dice import DiceRoller
        from dnd_engine.systems.initiative import InitiativeTracker
        from dnd_engine.systems.reactions import (
            ReactionDispatcher,
            ReactionOutcome,
            Trigger,
            TriggerContext,
        )

        abilities = Abilities(10, 10, 10, 10, 10, 10)
        fighter = Creature("Fighter", max_hp=10, ac=15, abilities=abilities)
        tracker = InitiativeTracker(DiceRoller(seed=1))
        tracker.add_combatant(fighter)
        assert tracker.get_current_combatant().creature is fighter

        dispatcher = ReactionDispatcher(tracker)
        dispatcher.register(
            fighter,
            Trigger.OPPORTUNITY_PROVOKED,
            lambda ctx: ReactionOutcome(reacted=True, description="OA"),
        )

        outcomes = dispatcher.publish(
            TriggerContext(trigger=Trigger.OPPORTUNITY_PROVOKED)
        )

        assert len(outcomes) == 1
        assert tracker.turn_states[fighter].reaction_available is False


class TestReaction_OpportunityAttackIsMostCommon:
    """SRD § Playing the Game › Reactions › OA is the most common type.

    > The Opportunity Attack, described later in "Playing the Game,"
    > is the most common type of Reaction.
    """

    def test_opportunity_attack_path_exists_in_engine(self) -> None:
        """`GameState.flee_combat` is the engine's OA-equivalent path.

        The SRD's "OA is the most common Reaction" framing is honored
        in spirit: there *is* an OA fan-out path on the engine side.
        Behavioral gaps (no Reaction consumption, no per-creature
        triggering, no visibility check) are audited in the
        melee-attacks conformance file. This test guards that the
        callable still exists so the citation in those skips stays
        accurate.
        """
        import inspect

        from dnd_engine.core.game_state import GameState

        assert callable(getattr(GameState, "flee_combat", None))
        src = inspect.getsource(GameState.flee_combat)
        assert "opportunity_attacks" in src, (
            "flee_combat must continue to surface an "
            "`opportunity_attacks` field — the conformance audit for "
            "melee-attacks anchors its OA citations here."
        )


class TestReaction_OncePerRound:
    """SRD § Playing the Game › Reactions › Once-per-round limit.

    > When you take a Reaction, you can't take another one until the
    > start of your next turn.
    """

    def test_turn_state_tracks_reaction_slot(self) -> None:
        """`TurnState` exposes a `reaction_available` field.

        SRD requires per-creature state that records "did this
        creature already use its Reaction this round?". `TurnState`
        now carries `reaction_available` alongside the existing
        action / bonus_action / free-object / movement slots.

        Closes the original gap captured under issue #412.
        """
        turn = TurnState()
        assert hasattr(turn, "reaction_available")
        assert turn.reaction_available is True

    def test_reaction_consumed_blocks_a_second_reaction_same_round(self) -> None:
        """Consuming the Reaction slot blocks a second Reaction this round.

        SRD: "When you take a Reaction, you can't take another one
        until the start of your next turn." A second
        ``consume_action(REACTION)`` in the same turn must return
        ``False``.
        """
        from dnd_engine.systems.action_economy import ActionType

        turn = TurnState()
        assert turn.consume_action(ActionType.REACTION) is True
        assert turn.reaction_available is False
        assert turn.consume_action(ActionType.REACTION) is False
        assert turn.is_action_available(ActionType.REACTION) is False

    def test_reaction_resets_at_start_of_next_turn(self) -> None:
        """`TurnState.reset()` restores the Reaction slot.

        SRD's "until the start of your next turn" phrasing requires a
        reaction flag that is cleared by the same path that resets
        the rest of the action economy. ``InitiativeTracker.next_turn``
        invokes ``.reset()`` on the incoming combatant, so resetting
        the reaction flag there enforces the once-per-round rule.
        """
        from dnd_engine.systems.action_economy import ActionType

        turn = TurnState()
        turn.consume_action(ActionType.REACTION)
        assert turn.reaction_available is False

        turn.reset()
        assert turn.reaction_available is True
        assert turn.is_action_available(ActionType.REACTION) is True


class TestReaction_InterruptedTurnContinuation:
    """SRD § Playing the Game › Reactions › Interrupted-turn continuation.

    > If the reaction interrupts another creature's turn, that
    > creature can continue its turn right after the Reaction.
    """

    def test_interrupted_turn_resumes_after_reaction_resolves(self) -> None:
        """The interrupted creature resumes on the same TurnState.

        Goblin is mid-turn: their Action has been spent, their
        Movement is half-consumed. A WOULD_BE_HIT trigger fires the
        Wizard's Shield reaction. After the dispatcher returns:

        - the Wizard's Reaction slot is consumed,
        - the Goblin remains the current combatant,
        - the Goblin's TurnState (action + movement) is unchanged,
        - the pause stack is empty.

        Closes #430.
        """
        from dnd_engine.core.creature import Abilities, Creature
        from dnd_engine.core.dice import DiceRoller
        from dnd_engine.systems.action_economy import ActionType
        from dnd_engine.systems.initiative import InitiativeTracker
        from dnd_engine.systems.reactions import (
            ReactionDispatcher,
            ReactionOutcome,
            Trigger,
            TriggerContext,
        )

        abilities = Abilities(10, 10, 10, 10, 10, 10)
        goblin = Creature("Goblin", max_hp=10, ac=15, abilities=abilities)
        wizard = Creature("Wizard", max_hp=10, ac=15, abilities=abilities)
        tracker = InitiativeTracker(DiceRoller(seed=1))
        tracker.add_combatant(goblin)
        tracker.add_combatant(wizard)
        for entry in tracker.combatants:
            entry.initiative_roll = 20 if entry.creature is goblin else 10
        tracker._sort_initiative()
        tracker.current_turn_index = 0
        # Goblin is mid-turn: action spent, half movement spent.
        tracker.turn_states[goblin].consume_action(ActionType.ACTION)
        tracker.turn_states[goblin].consume_movement(15)

        dispatcher = ReactionDispatcher(tracker)
        observed_current: list[str] = []

        def shield(ctx: TriggerContext) -> ReactionOutcome:
            observed_current.append(tracker.get_current_combatant().creature.name)
            return ReactionOutcome(reacted=True, description="Shield")

        dispatcher.register(wizard, Trigger.WOULD_BE_HIT, shield)
        dispatcher.publish(
            TriggerContext(trigger=Trigger.WOULD_BE_HIT, source=goblin)
        )

        assert observed_current == ["Wizard"]
        assert tracker.get_current_combatant().creature is goblin
        assert tracker.is_paused_for_reaction is False
        assert tracker.turn_states[goblin].action_available is False
        assert tracker.turn_states[goblin].movement_remaining == 15
        assert tracker.turn_states[wizard].reaction_available is False


class TestReaction_TimingDefault:
    """SRD § Playing the Game › Reactions › Default timing.

    > In terms of timing, a Reaction takes place immediately after
    > its trigger unless the Reaction's description says otherwise.
    """

    def test_reaction_resolves_immediately_after_trigger_by_default(self) -> None:
        """``ReactionDispatcher.publish`` resolves Reactions inline.

        The default-timing rule is "Reactions resolve immediately
        after their trigger." The dispatcher honors this by invoking
        handlers synchronously inside ``publish`` — when control
        returns to the caller, all eligible Reactions have already
        run. Closes #429.
        """
        from dnd_engine.core.creature import Abilities, Creature
        from dnd_engine.core.dice import DiceRoller
        from dnd_engine.systems.initiative import InitiativeTracker
        from dnd_engine.systems.reactions import (
            ReactionDispatcher,
            ReactionOutcome,
            Trigger,
            TriggerContext,
        )

        abilities = Abilities(10, 10, 10, 10, 10, 10)
        reactor = Creature("Reactor", max_hp=10, ac=15, abilities=abilities)
        tracker = InitiativeTracker(DiceRoller(seed=1))
        tracker.add_combatant(reactor)
        dispatcher = ReactionDispatcher(tracker)

        call_order: list[str] = []

        def handler(ctx: TriggerContext) -> ReactionOutcome:
            call_order.append("handler")
            return ReactionOutcome(reacted=True)

        dispatcher.register(reactor, Trigger.WOULD_BE_HIT, handler)
        call_order.append("before_publish")
        dispatcher.publish(TriggerContext(trigger=Trigger.WOULD_BE_HIT))
        call_order.append("after_publish")

        assert call_order == ["before_publish", "handler", "after_publish"]

    def test_reaction_description_can_override_default_timing(self) -> None:
        pytest.skip(
            "GAP: per-handler timing metadata (before / after trigger) "
            "is not yet modeled. The dispatcher's default is "
            "'immediately after trigger' (verified by the test above); "
            "the SRD carve-out for handlers that resolve *before* the "
            "trigger (e.g., Shield's AC bonus must apply to the very "
            "attack that triggered it) requires either a `timing` "
            "field on registration or a two-phase publish. Tracked "
            "under issue #429 as a follow-up to the base dispatcher; "
            "scheduled for the Shield implementation slice."
        )
