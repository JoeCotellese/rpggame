# ABOUTME: AggressiveAdvance — verbatim port of the Layer 3 greedy close-distance loop (#641).
# ABOUTME: Issue #647 — the default MovementStrategy. Plans a greedy path toward the primary target.

"""AggressiveAdvance — close-distance via greedy stepping.

This is the planner half of the Layer 3 loop in
`game_state.py:5164–5302`. It produces a tile path that greedy-steps
the actor toward the primary target until either the target enters
reach or the step budget is exhausted. The execution-side concerns
(blocked tiles, terrain cost, opportunity attacks, mid-loop kills)
are handled by `pipeline.execute`, which walks the path one tile at
a time via `GameState.attempt_combat_step`.

Behavioral parity with the original loop:

* Greedy king's-move: `dx, dy = sign(target.x - actor.x),
  sign(target.y - actor.y)`.
* Step budget: `min(actor.speed // 5, 12)`. The 12-tile hard ceiling
  matches the original `max_steps = 12` guard.
* Empty path when the actor is already in reach.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dnd_engine.core.creature import MovementMode
from dnd_engine.core.distance import distance_in_feet
from dnd_engine.core.position import Position
from dnd_engine.systems.ai.movement_strategy import MovePlan

if TYPE_CHECKING:
    from dnd_engine.core.creature import Creature
    from dnd_engine.systems.ai.context import TurnContext


HARD_STEP_CEILING = 12
"""Anti-runaway cap on the planned path length. Speed 30 only needs 6
steps to reach 30 ft; this ceiling fires only for very fast actors and
matches the original `max_steps = 12` guard in the Layer 3 loop."""


class AggressiveAdvance:
    """Greedy close-distance planner — pluggable default strategy."""

    name = "aggressive"

    def plan(
        self,
        ctx: TurnContext,
        primary_target: Creature,
        reach_ft: int,
    ) -> MovePlan:
        """Return a greedy tile path toward `primary_target`.

        Empty path means the actor is already within `reach_ft` or no
        legal step is possible (no positions, zero step budget).
        """
        actor = ctx.actor
        if actor.position is None or primary_target.position is None:
            return MovePlan(path=[], mode=MovementMode.WALK, intent_phase="close")

        if _in_reach(actor.position, primary_target.position, reach_ft):
            return MovePlan(path=[], mode=MovementMode.WALK, intent_phase="close")

        max_steps = min(actor.speed // 5, HARD_STEP_CEILING)
        if max_steps <= 0:
            return MovePlan(path=[], mode=MovementMode.WALK, intent_phase="close")

        path: list[Position] = []
        current = actor.position
        target = primary_target.position
        for _ in range(max_steps):
            dx = _sign(target.x - current.x)
            dy = _sign(target.y - current.y)
            if dx == 0 and dy == 0:
                break  # standing on the target tile (shouldn't happen)
            current = Position(current.x + dx, current.y + dy)
            path.append(current)
            if _in_reach(current, target, reach_ft):
                break

        return MovePlan(path=path, mode=MovementMode.WALK, intent_phase="close")


def _sign(delta: int) -> int:
    if delta > 0:
        return 1
    if delta < 0:
        return -1
    return 0


def _in_reach(a: Position, b: Position, reach_ft: int) -> bool:
    return distance_in_feet(a.x, a.y, b.x, b.y) <= reach_ft
