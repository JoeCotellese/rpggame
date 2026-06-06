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
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from dnd_engine.core.distance import distance_in_feet
from dnd_engine.core.position import Position
from dnd_engine.systems.ai.intent import AttackStep, Intent, MoveStep, WaitStep
from dnd_engine.systems.ai.strategies.aggressive import AggressiveAdvance
from dnd_engine.systems.ai.strategies.skirmisher import Skirmisher

if TYPE_CHECKING:
    from dnd_engine.core.combat import AttackResult
    from dnd_engine.core.creature import Creature
    from dnd_engine.core.game_state import GameState
    from dnd_engine.systems.ai.context import TurnContext
    from dnd_engine.systems.ai.movement_strategy import MovementStrategy

AttackResolver = Callable[["Creature", str, dict], "AttackResult | None"]

logger = logging.getLogger(__name__)

DEFAULT_STRATEGY = "aggressive"

STRATEGY_REGISTRY: dict[str, MovementStrategy] = {
    "aggressive": AggressiveAdvance(),
    "skirmisher": Skirmisher(),
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

    Returns one of:

    * `Intent(steps=[WaitStep("no_targets")])` — empty target pool.
    * `Intent(steps=[])` — no actionable attack data, or aggressive
      monster already in reach (process_enemy_turn handles attack).
    * `Intent(steps=[MoveStep])` — aggressive close-distance plan.
    * `Intent(steps=[MoveStep, AttackStep, MoveStep])` — skirmisher
      close → attack → retreat (any element may be omitted when its
      phase is empty: e.g. already-in-reach skirmisher emits
      `[AttackStep, MoveStep(retreat)]`).

    Attack and condition-removal steps for non-skirmisher monsters
    still resolve inside `process_enemy_turn` for now.
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

    strategy_name = ctx.monster_data.get("ai", {}).get("movement_strategy", DEFAULT_STRATEGY)
    strategy = get_strategy(strategy_name)
    retreat_fn = getattr(strategy, "plan_retreat", None)
    already_in_reach = _in_reach(actor_pos, target_pos, ctx.reach_ft)

    # Aggressive monsters (and anything else without plan_retreat) keep
    # the original contract: already-in-reach falls through to
    # process_enemy_turn's attack flow with an empty Intent.
    if retreat_fn is None and already_in_reach:
        return Intent(steps=[], rationale="already in reach")

    if already_in_reach:
        close_path: list[Position] = []
    else:
        close_plan = strategy.plan(ctx, primary_target, ctx.reach_ft)
        close_path = list(close_plan.path)
        if not close_path:
            return Intent(steps=[], rationale=f"{strategy.name} returned empty path")

    steps: list = []
    rationale_phases: list[str] = []
    if close_path:
        steps.append(MoveStep(path=close_path))
        rationale_phases.append(f"close to {primary_target.name}")

    if retreat_fn is None:
        return Intent(
            steps=steps,
            rationale=f"close to {primary_target.name} via {strategy.name}",
        )

    steps.append(AttackStep(target_id=primary_target.name, action=ctx.action_data))
    rationale_phases.append("attack")

    post_close_position = close_path[-1] if close_path else actor_pos
    retreat_plan = retreat_fn(
        ctx, primary_target, ctx.reach_ft,
        budget_used_ft=len(close_path) * 5,
        from_position=post_close_position,
    )
    if retreat_plan is not None and retreat_plan.path:
        steps.append(MoveStep(path=list(retreat_plan.path)))
        rationale_phases.append("retreat")

    return Intent(
        steps=steps,
        rationale=f"skirmish ({strategy.name}): " + " → ".join(rationale_phases),
    )


@dataclass
class MovementExecution:
    """Outcome of executing an Intent.

    Surfaces enough state for `process_enemy_turn` to decide between
    EnemyTurnAction.MOVED, NO_REACHABLE_TARGET, and falling through
    to attack resolution. When the Intent included an AttackStep, the
    resolver's `AttackResult` is captured on `attack_outcome` so the
    caller can package the EnemyTurnResult directly without rerunning
    `combat_engine.resolve_attack`.
    """

    moved_squares: int = 0
    final_position: Position | None = None
    in_reach_targets: list[Creature] = field(default_factory=list)
    stopped_reason: str = ""
    attack_outcome: AttackResult | None = None


def execute(
    intent: Intent,
    state: GameState,
    enemy: Creature,
    *,
    reach_ft: int | None = None,
    target_pool: list[Creature] | None = None,
    attack_resolver: AttackResolver | None = None,
) -> MovementExecution:
    """Walk the Intent's steps against `state`.

    MoveStep paths walk one tile at a time via
    `GameState.attempt_combat_step` (preserving CREATURE_MOVED events,
    opportunity-attack triggers, and Difficult Terrain costs). The
    close phase short-circuits the per-tile loop as soon as a target
    enters reach so the actor can attack this turn.

    AttackStep is routed through `attack_resolver` when provided.
    Skirmisher-style retreat is short-circuited if the attack killed
    the target. Mid-retreat enemy death (e.g., via opportunity attack)
    halts cleanly with `stopped_reason="enemy_died_mid_retreat"`.

    Args:
        intent: The plan produced by `decide`.
        state: The active game state.
        enemy: The acting enemy.
        reach_ft: Effective reach for the chosen action. When set
            with `target_pool`, the close phase stops as soon as any
            target enters reach.
        target_pool: Living-target pool for the in-reach check and
            for resolving `AttackStep.target_id` to a `Creature`.
        attack_resolver: Optional callback that resolves an
            `AttackStep` against `state`. Signature:
            `(actor, target_id, action) -> AttackResult | None`.

    Returns:
        A `MovementExecution` capturing moved squares, final
        position, in-reach targets, the attack outcome (if any), and
        a stop-reason string.
    """
    result = MovementExecution(final_position=enemy.position)
    if enemy.position is None or not intent.steps:
        return result
    enemy_eid = state.spatial.occupant_at(enemy.position)
    if enemy_eid is None:
        result.stopped_reason = "no_entity_id"
        return result

    pool = target_pool or []
    consecutive_failures = 0
    is_close_phase = True
    retreat_walked = False

    for step in intent.steps:
        if isinstance(step, AttackStep):
            is_close_phase = False
            if attack_resolver is None:
                logger.warning(
                    "Pipeline encountered AttackStep but no "
                    "attack_resolver was provided; skipping.",
                )
                continue
            result.attack_outcome = attack_resolver(enemy, step.target_id, step.action)
            target = next(
                (c for c in pool if c.name == step.target_id),
                None,
            )
            if target is not None and not target.is_alive:
                result.stopped_reason = "target_killed_no_retreat"
                return _finalize(result, enemy)
            if not enemy.is_alive:
                result.stopped_reason = "enemy_died_mid_attack"
                return _finalize(result, enemy)
            continue

        if not isinstance(step, MoveStep):
            continue

        for target_tile in step.path:
            if is_close_phase and reach_ft is not None and pool:
                if _filter_in_reach(enemy.position, pool, reach_ft):
                    break

            dx = _sign(target_tile.x - enemy.position.x)
            dy = _sign(target_tile.y - enemy.position.y)
            if dx == 0 and dy == 0:
                continue

            move_result = state.attempt_combat_step(enemy_eid, dx, dy)
            if move_result.ok:
                result.moved_squares += 1
                consecutive_failures = 0
                if not enemy.is_alive:
                    result.stopped_reason = (
                        "enemy_died_mid_retreat" if not is_close_phase
                        else "enemy_died_mid_close"
                    )
                    return _finalize(result, enemy)
            else:
                consecutive_failures += 1
                if move_result.reason == "no movement remaining":
                    result.stopped_reason = "no_movement_remaining"
                    return _finalize(result, enemy)
                if consecutive_failures >= 2:
                    result.stopped_reason = "blocked"
                    return _finalize(result, enemy)

        if not is_close_phase:
            retreat_walked = True

    if reach_ft is not None and pool and enemy.position is not None:
        result.in_reach_targets = _filter_in_reach(enemy.position, pool, reach_ft)
    if not result.stopped_reason:
        if retreat_walked:
            result.stopped_reason = "retreated"
        elif result.in_reach_targets:
            result.stopped_reason = "in_reach"
        else:
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
