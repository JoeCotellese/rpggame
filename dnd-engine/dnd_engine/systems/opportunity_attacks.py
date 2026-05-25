# ABOUTME: Opportunity Attack scaffolding on top of ReactionDispatcher
# ABOUTME: Default OA handler reacts when a mover leaves the reactor's reach

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from dnd_engine.core.distance import distance_in_feet
from dnd_engine.systems.reactions import (
    ReactionOutcome,
    Trigger,
    TriggerContext,
)

if TYPE_CHECKING:
    from dnd_engine.core.creature import Creature
    from dnd_engine.core.position import Position
    from dnd_engine.systems.reactions import ReactionDispatcher


# Canonical payload keys for OPPORTUNITY_PROVOKED triggers. Published
# by movement code and consumed by registered OA handlers. Centralized
# here so callers don't drift on the schema.
PAYLOAD_FROM_POSITION = "from_position"
PAYLOAD_TO_POSITION = "to_position"


def publish_movement_provoke(
    dispatcher: ReactionDispatcher,
    mover: Creature,
    from_position: Position,
    to_position: Position,
) -> list[ReactionOutcome]:
    """Publish an ``OPPORTUNITY_PROVOKED`` trigger for a single tactical move.

    Convenience wrapper around ``dispatcher.publish`` that pins the
    payload schema used by ``register_default_opportunity_attack``.
    Movement code calls this after a successful step; handlers decide
    individually whether the mover left *their* reach.

    Args:
        dispatcher: The shared ReactionDispatcher for this combat.
        mover: The creature that just moved (becomes ``ctx.source``).
        from_position: Where the mover was before the step.
        to_position: Where the mover is now.

    Returns:
        The list of ReactionOutcomes from handlers that actually
        reacted, in initiative order. Empty when no eligible reactor
        threatened the mover at ``from_position``.
    """
    return dispatcher.publish(
        TriggerContext(
            trigger=Trigger.OPPORTUNITY_PROVOKED,
            source=mover,
            payload={
                PAYLOAD_FROM_POSITION: from_position,
                PAYLOAD_TO_POSITION: to_position,
            },
        )
    )


def register_default_opportunity_attack(
    dispatcher: ReactionDispatcher,
    reactor: Creature,
    get_position: Callable[[], Position | None],
    reach_feet: int = 5,
) -> None:
    """Register the default OA reaction for ``reactor``.

    The handler fires (consuming the Reaction slot) iff:
        - the mover was within ``reach_feet`` of the reactor at
          ``from_position``, AND
        - the mover is outside ``reach_feet`` at ``to_position``,
        - AND the reactor is itself placed on the grid,
        - AND the mover is not the reactor (a creature can't OA itself).

    When all checks pass, the outcome carries attack metadata in
    ``data`` so a downstream slice can resolve the actual attack roll
    without redoing the geometry:

        ``{"attacker": reactor, "target": mover, "attack_kind":
        "melee_opportunity", "reach_feet": reach_feet}``

    ``get_position`` is injected (rather than taking a SpatialIndex
    directly) so the helper doesn't pull in GameState plumbing — tests
    can pass a plain lambda and production code can curry in
    ``SpatialIndex.position_of`` lookups.

    Args:
        dispatcher: The shared ReactionDispatcher for this combat.
        reactor: The creature whose Reaction may fire.
        get_position: Zero-arg callable that returns ``reactor``'s
            current Position (or ``None`` if unplaced). Called once
            per trigger so the reach check uses fresh coordinates
            even when the reactor moved.
        reach_feet: The reactor's melee reach. Defaults to 5 ft (a
            single square), matching the SRD default for an unarmed
            strike / non-reach weapon. Pass 10 (or larger) for reach
            weapons / large creatures.
    """

    def handler(context: TriggerContext) -> ReactionOutcome:
        mover = context.source
        if mover is None or mover is reactor:
            return ReactionOutcome(reacted=False)

        from_pos = context.payload.get(PAYLOAD_FROM_POSITION)
        to_pos = context.payload.get(PAYLOAD_TO_POSITION)
        reactor_pos = get_position()
        if from_pos is None or to_pos is None or reactor_pos is None:
            return ReactionOutcome(reacted=False)

        was_in_reach = (
            distance_in_feet(reactor_pos.x, reactor_pos.y, from_pos.x, from_pos.y)
            <= reach_feet
        )
        still_in_reach = (
            distance_in_feet(reactor_pos.x, reactor_pos.y, to_pos.x, to_pos.y)
            <= reach_feet
        )
        if not (was_in_reach and not still_in_reach):
            return ReactionOutcome(reacted=False)

        return ReactionOutcome(
            reacted=True,
            description=f"{reactor.name} takes an opportunity attack on {mover.name}",
            data={
                "attacker": reactor,
                "target": mover,
                "attack_kind": "melee_opportunity",
                "reach_feet": reach_feet,
            },
        )

    dispatcher.register(reactor, Trigger.OPPORTUNITY_PROVOKED, handler)
