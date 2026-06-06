# ABOUTME: decide / execute pipeline + strategy registry for the enemy-turn AI (#647).
# ABOUTME: Wraps MovementStrategy lookup, Intent construction, and tile-by-tile execution.

"""decide / execute pipeline for enemy turns.

`pipeline.decide(ctx)` consults the actor's `monsters.json` entry
for an `ai.movement_strategy` name, looks the strategy up in
`STRATEGY_REGISTRY` (falling back to `"aggressive"` and logging a
warning on miss), and asks it to plan a path. The output is an
`Intent` carrying the resulting `MoveStep`s.

`pipeline.execute(intent, state, enemy, ...)` walks each `MoveStep`
path one tile at a time via `GameState.attempt_combat_step`, so the
per-step CREATURE_MOVED event publication, opportunity-attack
provocation, and Difficult Terrain cost continue to flow through the
existing primitive. Execution stops on:

* a living target entering reach (in_reach_targets populated);
* no remaining movement budget;
* two consecutive step failures (anti-stuck guard, matching the
  original Layer 3 loop).

This commit ships the seam wired only for the movement phase.
Attack resolution remains in `process_enemy_turn` for now —
`Intent` already models `AttackStep`, so a later commit can extend
`execute` to drive attacks too.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from dnd_engine.core.distance import distance_in_feet
from dnd_engine.core.position import Position
from dnd_engine.systems.ai.intent import Intent, MoveStep, WaitStep
from dnd_engine.systems.ai.strategies.aggressive import AggressiveAdvance

if TYPE_CHECKING:
    from dnd_engine.core.creature import Creature
    from dnd_engine.core.game_state import GameState
    from dnd_engine.systems.ai.context import TurnContext
    from dnd_engine.systems.ai.movement_strategy import MovementStrategy

logger = logging.getLogger(__name__)

DEFAULT_STRATEGY = "aggressive"

STRATEGY_REGISTRY: dict[str, MovementStrategy] = {
    "aggressive": AggressiveAdvance(),
}


def get_strategy(name: str) -> MovementStrategy:
    """Look up a movement strategy by name; fall back to the default.

    Logs a warning when the name is missing from the registry — a
    common drift mode for data-authored monsters.
    """
    strategy = STRATEGY_REGISTRY.get(name)
    if strategy is None:
        logger.warning(
            "Unknown movement strategy '%s'; falling back to '%s'.",
            name,
            DEFAULT_STRATEGY,
        )
        strategy = STRATEGY_REGISTRY[DEFAULT_STRATEGY]
    return strategy


def _select_primary_target(ctx: TurnContext) -> Creature | None:
    """Pick the nearest target by Chebyshev distance, tie-break by name.

    Mirrors the existing Layer 3 loop's `pc.name` tiebreaker — load-
    bearing so the actor doesn't oscillate between equidistant PCs.
    """
    actor = ctx.actor
    if actor.position is None:
        return None
    candidates = [pc for pc in ctx.target_pool if pc.position is not None]
    if not candidates:
        return None
    actor_pos = actor.position
    return min(
        candidates,
        key=lambda pc: (
            distance_in_feet(actor_pos.x, actor_pos.y, pc.position.x, pc.position.y),
            pc.name,
        ),
    )


def _in_reach(a: Position, b: Position, reach_ft: int) -> bool:
    return distance_in_feet(a.x, a.y, b.x, b.y) <= reach_ft


def decide(ctx: TurnContext) -> Intent:
    """Build the turn's Intent from `ctx`.

    Currently produces the movement phase only — attack and
    condition-removal steps are still handled by `process_enemy_turn`.
    Returns:

    * `Intent(steps=[WaitStep("no_targets")])` — empty target pool.
    * `Intent(steps=[])` — no actionable attack data or already in reach.
    * `Intent(steps=[MoveStep(path=...)])` — movement planned.
    """
    if not ctx.target_pool:
        return Intent(steps=[WaitStep(reason="no_targets")], rationale="no living targets")

    if ctx.action_data is None or ctx.reach_ft is None or ctx.is_ranged:
        return Intent(steps=[], rationale="no melee movement needed")

    primary_target = _select_primary_target(ctx)
    if primary_target is None:
        return Intent(steps=[], rationale="no candidate with position")

    actor_pos = ctx.actor.position
    target_pos = primary_target.position
    if actor_pos is None or target_pos is None:
        return Intent(steps=[], rationale="no spatial context")

    if _in_reach(actor_pos, target_pos, ctx.reach_ft):
        return Intent(steps=[], rationale="already in reach")

    strategy_name = ctx.monster_data.get("ai", {}).get("movement_strategy", DEFAULT_STRATEGY)
    strategy = get_strategy(strategy_name)
    plan = strategy.plan(ctx, primary_target, ctx.reach_ft)

    if not plan.path:
        return Intent(steps=[], rationale=f"{strategy.name} returned empty path")

    return Intent(
        steps=[MoveStep(path=list(plan.path), mode=plan.mode)],
        rationale=f"close to {primary_target.name} via {strategy.name}",
    )


@dataclass
class MovementExecution:
    """Outcome of walking the MoveSteps in an Intent.

    Surfaces enough state for `process_enemy_turn` to decide between
    EnemyTurnAction.MOVED, NO_REACHABLE_TARGET, and falling through
    to attack resolution.
    """

    moved_squares: int = 0
    final_position: Position | None = None
    in_reach_targets: list[Creature] = field(default_factory=list)
    stopped_reason: str = ""


def execute(
    intent: Intent,
    state: GameState,
    enemy: Creature,
    *,
    reach_ft: int | None = None,
    target_pool: list[Creature] | None = None,
) -> MovementExecution:
    """Walk the MoveSteps in `intent` via `GameState.attempt_combat_step`.

    Args:
        intent: The plan produced by `decide`.
        state: The active game state.
        enemy: The acting enemy.
        reach_ft: Effective reach for the chosen action. When set
            with `target_pool`, execution stops as soon as any
            target enters reach.
        target_pool: Living-target pool for the in-reach check.

    Returns:
        A `MovementExecution` capturing moved squares, final
        position, in-reach targets at end of execution, and a
        stop-reason string.
    """
    result = MovementExecution(final_position=enemy.position)
    if enemy.position is None or not intent.steps:
        return result
    enemy_eid = state.spatial.occupant_at(enemy.position)
    if enemy_eid is None:
        result.stopped_reason = "no_entity_id"
        return result

    consecutive_failures = 0
    pool = target_pool or []
    for step in intent.steps:
        if not isinstance(step, MoveStep):
            continue
        for target_tile in step.path:
            # Check reach BEFORE moving — if a target is already in
            # reach (e.g. a PC moved closer between turns), short-
            # circuit so the actor can attack this turn.
            if reach_ft is not None and pool:
                in_reach_now = _filter_in_reach(enemy.position, pool, reach_ft)
                if in_reach_now:
                    result.in_reach_targets = in_reach_now
                    result.stopped_reason = "in_reach"
                    return _finalize(result, enemy)

            dx = _sign(target_tile.x - enemy.position.x)
            dy = _sign(target_tile.y - enemy.position.y)
            if dx == 0 and dy == 0:
                continue

            move_result = state.attempt_combat_step(enemy_eid, dx, dy)
            if move_result.ok:
                result.moved_squares += 1
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if move_result.reason == "no movement remaining":
                    result.stopped_reason = "no_movement_remaining"
                    return _finalize(result, enemy)
                if consecutive_failures >= 2:
                    result.stopped_reason = "blocked"
                    return _finalize(result, enemy)

    # Final reach check after walking the full intent.
    if reach_ft is not None and pool and enemy.position is not None:
        result.in_reach_targets = _filter_in_reach(enemy.position, pool, reach_ft)
    if result.in_reach_targets:
        result.stopped_reason = "in_reach"
    elif not result.stopped_reason:
        result.stopped_reason = "exhausted"
    return _finalize(result, enemy)


def _filter_in_reach(
    actor_pos: Position,
    pool: list[Creature],
    reach_ft: int,
) -> list[Creature]:
    return [
        pc for pc in pool
        if pc.position is not None
        and distance_in_feet(actor_pos.x, actor_pos.y, pc.position.x, pc.position.y) <= reach_ft
    ]


def _finalize(result: MovementExecution, enemy: Creature) -> MovementExecution:
    if enemy.position is not None:
        result.final_position = enemy.position
    return result


def _sign(delta: int) -> int:
    if delta > 0:
        return 1
    if delta < 0:
        return -1
    return 0
