# ABOUTME: Skirmisher — hit-and-run MovementStrategy that closes, attacks, then retreats.
# ABOUTME: Issue #649. Provides both plan() (close) and plan_retreat() (withdraw out of reach).

"""Skirmisher — the close-attack-retreat planner.

Skirmisher monsters (e.g. goblins) follow a tactical loop: close on
the primary target to deliver a single attack, then withdraw back
out of melee reach the same turn. The withdrawal step provokes an
opportunity attack, which is the price the skirmisher pays for the
tactical advantage.

The close phase (`plan`) is identical in shape to AggressiveAdvance:
a greedy king's-move toward the primary target, bounded by step
budget and `HARD_STEP_CEILING`.

The retreat phase (`plan_retreat`) is the new surface this strategy
introduces. It returns an opposite-direction path that stops as soon
as the target is out of reach from the candidate tile (no point in
over-running) while respecting the movement budget already consumed
by the close phase. `pipeline.decide` discovers it via `getattr`, so
AggressiveAdvance is unaffected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dnd_engine.core.creature import MovementMode
from dnd_engine.core.position import Position
from dnd_engine.systems.ai.movement_strategy import MovePlan
from dnd_engine.systems.ai.strategies.aggressive import (
    HARD_STEP_CEILING,
    _in_reach,
    _sign,
)

if TYPE_CHECKING:
    from dnd_engine.core.creature import Creature
    from dnd_engine.systems.ai.context import TurnContext


class Skirmisher:
    """Close-attack-retreat planner; goblins and similar nimble foes."""

    name = "skirmisher"

    def plan(
        self,
        ctx: TurnContext,
        primary_target: Creature,
        reach_ft: int,
    ) -> MovePlan:
        """Greedy king's-move close-to-reach path.

        Mirrors AggressiveAdvance: an empty path means the actor is
        already in reach or no legal step is possible.
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
                break
            current = Position(current.x + dx, current.y + dy)
            path.append(current)
            if _in_reach(current, target, reach_ft):
                break

        return MovePlan(path=path, mode=MovementMode.WALK, intent_phase="close")

    def plan_retreat(
        self,
        ctx: TurnContext,
        primary_target: Creature,
        reach_ft: int,
        budget_used_ft: int,
        *,
        from_position: Position | None = None,
    ) -> MovePlan | None:
        """Plan an opposite-direction path that breaks the target's reach.

        `from_position` is the post-close position the retreat starts
        from. When omitted, falls back to `ctx.actor.position` — which
        is correct only when the actor hasn't closed yet (unit tests
        and already-in-reach skirmishers).

        Returns None when planning is impossible — no remaining budget,
        no spatial context. Returns a `MovePlan` with `path == []` when
        the actor is already disengaged so the caller can still see the
        intent phase.
        """
        actor = ctx.actor
        origin = from_position if from_position is not None else actor.position
        if origin is None or primary_target.position is None:
            return None

        remaining_ft = actor.speed - budget_used_ft
        if remaining_ft < 5:
            return None

        max_steps = min(remaining_ft // 5, HARD_STEP_CEILING)
        if max_steps <= 0:
            return None

        if not _in_reach(origin, primary_target.position, reach_ft):
            return MovePlan(path=[], mode=MovementMode.WALK, intent_phase="retreat")

        path: list[Position] = []
        current = origin
        target = primary_target.position
        for _ in range(max_steps):
            dx = -_sign(target.x - current.x)
            dy = -_sign(target.y - current.y)
            if dx == 0 and dy == 0:
                break
            current = Position(current.x + dx, current.y + dy)
            path.append(current)
            if not _in_reach(current, target, reach_ft):
                break

        return MovePlan(path=path, mode=MovementMode.WALK, intent_phase="retreat")
