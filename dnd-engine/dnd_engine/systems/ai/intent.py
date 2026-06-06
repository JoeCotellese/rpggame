# ABOUTME: Turn-intent dataclasses produced by pipeline.decide and consumed by pipeline.execute.
# ABOUTME: Issue #647 — splits process_enemy_turn into a decide/execute pipeline.

"""Intent value objects for the enemy-turn pipeline.

`Intent` is the output of `pipeline.decide(ctx)` and the input to
`pipeline.execute(intent, state)`. It carries an ordered list of
discrete `TurnStep`s — typically `[MoveStep, AttackStep]`, but a
skirmisher-style strategy emits `[MoveStep, AttackStep, MoveStep]`
(close → attack → retreat). Holding the plan as data rather than as
imperative control flow is what lets the AI become pluggable: a
strategy's only job is to populate the step list; execution is uniform.

All step types are frozen dataclasses so an Intent is value-equality
comparable, hashable into test caches, and safe to log verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dnd_engine.core.creature import MovementMode
from dnd_engine.core.position import Position


@dataclass(frozen=True)
class MoveStep:
    """A planned movement along a tile-by-tile path.

    The path is the *sequence of destination tiles*, not including the
    actor's starting tile. `execute` walks the path one tile at a time
    via `GameState.attempt_combat_step`, so per-tile semantics
    (CREATURE_MOVED publication, OA provocation, Difficult Terrain
    cost) flow through unchanged from the existing primitive.
    """

    path: list[Position] = field(default_factory=list)
    mode: MovementMode = MovementMode.WALK


@dataclass(frozen=True)
class AttackStep:
    """A planned attack against a specific target with a chosen action."""

    target_id: str
    action: dict[str, Any]


@dataclass(frozen=True)
class ConditionRemovalStep:
    """A planned attempt to remove a condition (e.g. on_fire) from the actor."""

    condition_id: str


@dataclass(frozen=True)
class WaitStep:
    """A planned wait — the actor takes no offensive or movement action this turn.

    `reason` distinguishes the surface meaning so the result packager
    can emit the correct `EnemyTurnAction` variant (NO_TARGETS,
    NO_REACHABLE_TARGET, INCAPACITATED, etc.).
    """

    reason: str


TurnStep = MoveStep | AttackStep | ConditionRemovalStep | WaitStep


@dataclass(frozen=True)
class Intent:
    """The full ordered plan for one enemy turn."""

    steps: list[TurnStep] = field(default_factory=list)
    rationale: str = ""
