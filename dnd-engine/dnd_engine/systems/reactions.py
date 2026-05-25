# ABOUTME: Trigger->Reaction dispatcher for D&D 5E combat
# ABOUTME: Routes named triggers to subscribed Reaction handlers in initiative order

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from dnd_engine.systems.action_economy import ActionType

if TYPE_CHECKING:
    from dnd_engine.core.creature import Creature
    from dnd_engine.systems.initiative import InitiativeTracker


class Trigger(str, Enum):
    """Named triggers a creature can subscribe a Reaction to.

    Each value is a free-standing event in combat that one or more
    creatures may want to respond to with their once-per-round
    Reaction. The SRD enumerates Reaction surfaces by example
    (Shield, Counterspell, Opportunity Attack) rather than by a
    fixed catalog, so this enum starts with the three the engine
    needs first and is meant to grow as more Reaction-shaped
    features land.
    """

    OPPORTUNITY_PROVOKED = "opportunity_provoked"
    WOULD_BE_HIT = "would_be_hit"
    SPELL_CAST_OBSERVED = "spell_cast_observed"


@dataclass
class TriggerContext:
    """Payload passed to every eligible Reaction handler when a trigger fires.

    Handlers read these fields to decide whether to react and what to
    do. ``source`` is the creature that caused the trigger (e.g., the
    attacker that hit you, the caster of the spell you saw). ``payload``
    carries trigger-specific data (the attack roll, the spell level,
    the destination tile) — the schema is owned by the publisher of
    the trigger, not by the dispatcher.
    """

    trigger: Trigger
    source: Creature | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReactionOutcome:
    """Result of a Reaction handler invocation.

    Setting ``reacted=True`` tells the dispatcher to consume the
    reactor's Reaction slot for this round. A handler that declines
    (``reacted=False``) costs the reactor nothing and a later trigger
    in the same round can still fire their Reaction.

    ``description`` is a short human-readable summary for logs / the
    event bus. ``data`` is a free-form bag the publisher and the
    handler agree on (e.g., the +5 AC bonus Shield grants, the spell
    that Counterspell stopped).
    """

    reacted: bool
    description: str = ""
    data: dict[str, Any] = field(default_factory=dict)


ReactionHandler = Callable[[TriggerContext], ReactionOutcome]


@dataclass
class _Subscription:
    """Internal record: a creature's handler for one trigger."""

    creature: Creature
    trigger: Trigger
    handler: ReactionHandler


class ReactionDispatcher:
    """Routes named triggers to subscribed Reaction handlers.

    The dispatcher is the engine-side enforcement point for the SRD's
    "you can't take another Reaction until the start of your next
    turn" rule. Per-creature slots live on
    ``InitiativeTracker.turn_states[creature].reaction_available``
    and are reset by the existing ``InitiativeTracker.next_turn`` ->
    ``TurnState.reset()`` path, so this dispatcher only has to *check
    and consume* the slot, never reset it.

    Reaction resolution order is initiative order (highest first) per
    SRD's general timing convention for simultaneous fan-out. The SRD
    also stipulates Reactions resolve "immediately after the trigger
    unless the Reaction's description says otherwise" — this
    dispatcher honors the default (synchronous, in-call resolution);
    a future per-handler `timing` field can carve out the
    "before-trigger" exceptions (e.g., Shield's AC bonus must apply to
    the very attack that triggered it).
    """

    def __init__(self, tracker: InitiativeTracker):
        self._tracker = tracker
        self._subs: list[_Subscription] = []

    @property
    def tracker(self) -> InitiativeTracker:
        """The initiative tracker this dispatcher is bound to.

        Exposed read-only so trigger publishers (e.g.,
        ``publish_movement_provoke``) and integration code can consult
        per-actor turn state without reaching into the private
        ``_tracker`` field.
        """
        return self._tracker

    def register(
        self,
        creature: Creature,
        trigger: Trigger,
        handler: ReactionHandler,
    ) -> None:
        """Subscribe ``creature``'s ``handler`` to ``trigger``.

        Multiple subscriptions for the same (creature, trigger) pair
        are allowed but only the most-recently-registered handler
        fires — creatures generally have one Reaction option active
        per trigger at a time, and "last wins" matches the way
        features replace each other (e.g., upgrading Shield to a
        higher-level variant). Unregister explicitly if a creature
        needs to drop a subscription mid-combat.
        """
        self._subs.append(_Subscription(creature, trigger, handler))

    def unregister(self, creature: Creature) -> None:
        """Drop every subscription held by ``creature``.

        Call when a combatant is removed from the initiative order so
        their handlers don't accumulate across encounters.
        """
        self._subs = [s for s in self._subs if s.creature is not creature]

    def publish(self, context: TriggerContext) -> list[ReactionOutcome]:
        """Fire eligible Reactions for ``context.trigger`` in initiative order.

        A reactor is eligible if all hold:

        - they have a subscription for ``context.trigger``,
        - they are alive (``creature.is_alive``),
        - their ``TurnState.reaction_available`` is True.

        Each eligible handler is invoked with ``context``. Handlers
        that return ``ReactionOutcome(reacted=True)`` consume the
        Reaction slot; ``reacted=False`` leaves the slot intact for a
        later trigger in the same round.

        When the reactor is not the currently-active combatant, the
        tracker is paused (``InitiativeTracker.pause_for_reaction``)
        for the duration of the handler call so that downstream code
        reading ``get_current_combatant()`` sees the reactor, not the
        interrupted creature. The pause is released before the next
        handler runs, so reactor ordering remains pure initiative
        order and the interrupted creature's ``TurnState`` is never
        touched.

        Returns the outcomes from handlers that actually reacted, in
        resolution order. An empty list means no one reacted (either
        no subscribers or every subscriber declined / was ineligible).
        """
        outcomes: list[ReactionOutcome] = []
        for creature, handler in self._eligible_in_initiative_order(context.trigger):
            turn_state = self._tracker.turn_states.get(creature)
            if turn_state is None or not turn_state.reaction_available:
                continue
            if not creature.is_alive:
                continue

            current = self._tracker.get_current_combatant()
            interrupts_another_turn = current is not None and current.creature is not creature
            if interrupts_another_turn:
                self._tracker.pause_for_reaction(creature)
            try:
                outcome = handler(context)
            finally:
                if interrupts_another_turn:
                    self._tracker.resume_paused_turn()

            if outcome.reacted:
                turn_state.consume_action(ActionType.REACTION)
                outcomes.append(outcome)
        return outcomes

    def _eligible_in_initiative_order(
        self, trigger: Trigger
    ) -> list[tuple[Creature, ReactionHandler]]:
        """Walk the tracker's initiative order, yielding subscribed reactors.

        "Last subscription wins" for (creature, trigger) — see
        ``register``. Creatures not in initiative are skipped (they
        have no TurnState slot to consume).
        """
        per_creature: dict[Creature, ReactionHandler] = {}
        for sub in self._subs:
            if sub.trigger == trigger:
                per_creature[sub.creature] = sub.handler

        ordered: list[tuple[Creature, ReactionHandler]] = []
        for entry in self._tracker.get_all_combatants():
            handler = per_creature.get(entry.creature)
            if handler is not None:
                ordered.append((entry.creature, handler))
        return ordered
