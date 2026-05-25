# ABOUTME: MoveResult value object returned by GameState.attempt_combat_step.
# ABOUTME: Bundles the four facts a combat-move caller needs into one frozen contract.

from __future__ import annotations

from dataclasses import dataclass

from dnd_engine.core.position import Position


@dataclass(frozen=True, slots=True)
class MoveResult:
    """
    Outcome of an engine-validated combat step.

    Returned by :meth:`dnd_engine.core.game_state.GameState.attempt_combat_step`
    so a single call surfaces everything callers need to render the
    outcome of an attempted 5-foot step: whether it succeeded, a
    human-readable reason on failure, the post-attempt position, and
    the remaining movement budget for the current turn.

    Fields:
        ok: True if the step landed; False if any precondition rejected.
        reason: Human-readable failure reason (``"blocking"``, ``"occupied
            by <id>"``, ``"out of bounds"``, ``"no movement remaining"``,
            ``"not placed"``). ``None`` on success.
        position: The entity's position after the attempt. On failure
            this is the entity's CURRENT position when known; ``None``
            for the ``"not placed"`` path where no current position
            exists. On success it is the new destination.
        movement_remaining: Feet remaining in the current TurnState
            after the attempt. On failure this reflects the pool as it
            stood at rejection time — the cost is NOT deducted when the
            move is rejected. ``None`` for the ``"not placed"`` path
            where no turn state was consulted, distinguishing the
            soft-fail from a legitimate "pool exhausted" zero.
        blocker_entity_id: Entity id of the occupant that blocked the
            step. Populated only on the ``"occupied by <id>"`` failure
            path so consumers can route to entity-aware rendering
            without string-slicing ``reason``. ``None`` on every other
            outcome including success.

    Immutability (``frozen=True``) and ``slots=True`` keep the
    structure cheap to create per-step and safe to share across event
    subscribers without defensive copies.
    """

    ok: bool
    reason: str | None
    position: Position | None
    movement_remaining: int | None
    blocker_entity_id: str | None = None
