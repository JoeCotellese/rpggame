# ABOUTME: Defers opportunity-attack decisions so a human can answer them.
# ABOUTME: Intercepts the engine's automatic handler and queues the choice instead.

"""Deferred opportunity attacks.

The engine resolves opportunity attacks automatically: a mover leaves your
reach, a handler fires, the attack happens. At a table that moment is a
*decision* — sometimes an agonising one, when you are holding your reaction for
a Shield you may need more.

Turning it back into a decision needs no engine change, because three pieces
already cooperate:

- ``ReactionDispatcher.register()`` is documented "last wins", so a handler
  registered after the engine's default takes precedence.
- ``publish()`` consumes the reaction slot only when a handler returns
  ``reacted=True``, so deferring costs the reactor nothing — which is exactly
  the SRD rule for a reaction you chose not to spend.
- ``publish()`` already brackets each handler in ``pause_for_reaction()`` /
  ``resume_paused_turn()``, so the tracker reports the reactor as current
  while the question is being raised.

So this module intercepts, records what *would* have happened, and lets the
session ask. The geometry itself is not reimplemented: the real decision of
whether an attack is provoked comes from
:func:`~dnd_engine.systems.opportunity_attacks.build_default_opportunity_handler`,
so there is exactly one copy of that rule.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from dnd_engine.systems.opportunity_attacks import (
    PAYLOAD_FROM_POSITION,
    PAYLOAD_TO_POSITION,
    build_default_opportunity_handler,
)
from dnd_engine.systems.reactions import ReactionOutcome, Trigger, TriggerContext

if TYPE_CHECKING:  # pragma: no cover - typing only
    from dnd_engine.core.creature import Creature
    from dnd_engine.core.position import Position
    from dnd_engine.systems.reactions import ReactionDispatcher

ATTACK_OPTION_ID = "attack"
DECLINE_OPTION_ID = "decline"


@dataclass
class PendingOpportunity:
    """One opportunity attack awaiting a human answer.

    Fields:
        reactor: The creature whose reaction would be spent.
        mover: The creature that left ``reactor``'s reach.
        from_position: Where the mover stood when the reach was threatened.
        to_position: Where the mover ended up.
        reach_feet: The reactor's reach, as used by the geometry check.
        decision_id: Correlates the question with its answer.
    """

    reactor: Creature
    mover: Creature
    from_position: Position | None
    to_position: Position | None
    reach_feet: int
    decision_id: str


@dataclass
class OpportunityQueue:
    """Opportunity attacks provoked during one action, in initiative order.

    ``publish()`` walks reactors in initiative order and this queue appends in
    the order handlers run, so initiative ordering is preserved without the
    queue having to know about it.
    """

    pending: list[PendingOpportunity] = field(default_factory=list)
    _counter: int = 0

    def next_decision_id(self) -> str:
        """Mint an id unique within this session."""
        self._counter += 1
        return f"oa-{self._counter}"

    def add(self, opportunity: PendingOpportunity) -> None:
        """Queue an opportunity for a human answer."""
        self.pending.append(opportunity)

    def find(self, decision_id: str) -> PendingOpportunity | None:
        """Look up a queued opportunity without removing it.

        Validation reads through this so a rejected answer cannot disturb the
        queue: removing and re-adding sent the entry to the back, silently
        reordering who gets asked next.
        """
        for opportunity in self.pending:
            if opportunity.decision_id == decision_id:
                return opportunity
        return None

    def take(self, decision_id: str) -> PendingOpportunity | None:
        """Remove and return the queued opportunity with this id."""
        for index, opportunity in enumerate(self.pending):
            if opportunity.decision_id == decision_id:
                return self.pending.pop(index)
        return None

    def peek(self) -> PendingOpportunity | None:
        """The opportunity that should be asked about next."""
        return self.pending[0] if self.pending else None

    def clear(self) -> None:
        """Drop everything queued — used when combat ends."""
        self.pending.clear()


def register_deferred_opportunity_attack(
    dispatcher: ReactionDispatcher,
    queue: OpportunityQueue,
    reactor: Creature,
    get_position: Callable[[], Position | None],
    reach_feet: int = 5,
    can_see: Callable[[Position], bool] | None = None,
) -> None:
    """Register a handler that queues the decision instead of taking it.

    Registered *after* the engine's default handler so it wins the "last
    registered" contest. When the underlying geometry says an attack is
    provoked, the opportunity is queued and the handler returns
    ``reacted=False`` — the engine resolves nothing and the reactor keeps its
    reaction until the player actually spends it.

    Args:
        dispatcher: The combat's shared dispatcher.
        queue: Where provoked-but-unanswered opportunities accumulate.
        reactor: The creature whose reaction is at stake.
        get_position: Returns the reactor's current position.
        reach_feet: The reactor's melee reach.
        can_see: Whether the reactor can see a given position. Passed straight
            through to the real handler, so the SRD "creature you can see"
            clause is enforced identically.
    """
    real_handler = build_default_opportunity_handler(
        reactor,
        get_position,
        reach_feet=reach_feet,
        can_see=can_see,
    )

    def deferring_handler(context: TriggerContext) -> ReactionOutcome:
        outcome = real_handler(context)
        if not outcome.reacted:
            # Not provoked at all — out of reach, can't see, self-move. Nothing
            # to ask about, and the slot stays untouched either way.
            return outcome

        mover = context.source
        if mover is None:
            return ReactionOutcome(reacted=False)

        queue.add(
            PendingOpportunity(
                reactor=reactor,
                mover=mover,
                from_position=context.payload.get(PAYLOAD_FROM_POSITION),
                to_position=context.payload.get(PAYLOAD_TO_POSITION),
                reach_feet=reach_feet,
                decision_id=queue.next_decision_id(),
            )
        )
        # False, deliberately: the engine must not resolve this attack, and the
        # reactor must not be charged for a reaction they have not yet chosen
        # to spend.
        return ReactionOutcome(reacted=False)

    dispatcher.register(reactor, Trigger.OPPORTUNITY_PROVOKED, deferring_handler)


def describe(opportunity: PendingOpportunity, mover_display_name: str) -> dict[str, Any]:
    """Build the player-facing wording for an opportunity decision.

    Kept here rather than in the session so the phrasing lives beside the rule
    it describes.
    """
    return {
        "prompt": (
            f"{mover_display_name} is leaving {opportunity.reactor.name}'s reach. "
            f"Take an opportunity attack?"
        ),
        "context": {
            "reactor": opportunity.reactor.name,
            "mover": mover_display_name,
            "reach_feet": opportunity.reach_feet,
        },
    }
