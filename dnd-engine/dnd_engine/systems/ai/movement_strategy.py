# ABOUTME: MovementStrategy Protocol and MovePlan dataclass — pluggable monster movement AI.
# ABOUTME: Issue #647 — lets monsters.json wire a per-monster strategy (aggressive, skirmisher, etc.).

"""Pluggable movement strategy seam.

A `MovementStrategy` is a stateless component that, given a
`TurnContext` and a primary target, returns a `MovePlan` describing
the tile path the actor should take this turn (plus optional
mode/phase metadata). Strategies are pure planners — they do not
mutate state and do not call `attempt_combat_step`. `pipeline.execute`
consumes the plan and performs the actual stepping.

`MovementStrategy` is a `typing.Protocol`, not an ABC, so strategies
are duck-typed: any object with a `name: str` attribute and a `plan(...)`
method satisfies the seam. This keeps content authors (likely just
data + a small class) free of inheritance ceremony.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

from dnd_engine.core.creature import MovementMode
from dnd_engine.core.position import Position

if TYPE_CHECKING:
    from dnd_engine.core.creature import Creature
    from dnd_engine.systems.ai.context import TurnContext


IntentPhase = Literal["close", "engage", "retreat"]


@dataclass(frozen=True)
class MovePlan:
    """The path and metadata a `MovementStrategy` returns.

    `path` is the ordered list of destination tiles excluding the
    actor's starting tile. An empty path means the strategy chose
    not to move (e.g. already in reach, no legal moves).

    `intent_phase` lets the pipeline distinguish close-then-attack
    plans from attack-then-retreat plans without inspecting paths.
    """

    path: list[Position] = field(default_factory=list)
    mode: MovementMode = MovementMode.WALK
    intent_phase: IntentPhase = "close"


@runtime_checkable
class MovementStrategy(Protocol):
    """A pluggable per-monster movement planner.

    Implementations live under `systems/ai/strategies/` and are
    registered with `pipeline.STRATEGY_REGISTRY` so monsters.json
    entries can opt in via `ai.movement_strategy`.
    """

    name: str

    def plan(
        self,
        ctx: TurnContext,
        primary_target: Creature,
        reach_ft: int,
    ) -> MovePlan:
        """Return a `MovePlan` for this turn.

        Args:
            ctx: The turn context, including actor, target pool, and
                monster-data dict (for content-driven knobs).
            primary_target: The creature the actor is focused on this
                turn — typically pre-selected by the targeting layer.
            reach_ft: The actor's effective reach in feet for the
                chosen action.

        Returns:
            A `MovePlan` whose `path` may be empty (no movement
            planned) or non-empty (tile-by-tile destinations).
        """
        ...
