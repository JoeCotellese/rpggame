# ABOUTME: Unit tests for AggressiveAdvance — the verbatim port of the Layer 3 close-distance loop.
# ABOUTME: Issue #647 commit 2 — covers the same scenarios as test_enemy_turn_movement.py at planner level.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dnd_engine.core.creature import Abilities, Creature, MovementMode
from dnd_engine.core.position import Position
from dnd_engine.systems.ai.context import TurnContext
from dnd_engine.systems.ai.strategies.aggressive import (
    HARD_STEP_CEILING,
    AggressiveAdvance,
)


@dataclass
class _StubState:
    data_loader: Any = None


def _make_creature(name: str, x: int, y: int, speed: int = 30) -> Creature:
    c = Creature(
        name=name,
        max_hp=20,
        ac=15,
        abilities=Abilities(
            strength=10, dexterity=10, constitution=10,
            intelligence=10, wisdom=10, charisma=10,
        ),
        speed=speed,
    )
    c.position = Position(x, y)
    return c


def _ctx(actor: Creature, *, target_pool: list[Creature] | None = None) -> TurnContext:
    return TurnContext.build(
        _StubState(),
        actor,
        target_pool=target_pool or [],
        monster_data={},
    )


class TestAggressiveAdvancePlan:
    def test_empty_path_when_already_in_reach(self):
        actor = _make_creature("Goblin", 0, 0)
        target = _make_creature("Brick", 1, 0)
        plan = AggressiveAdvance().plan(_ctx(actor), target, reach_ft=5)
        assert plan.path == []
        assert plan.mode == MovementMode.WALK
        assert plan.intent_phase == "close"

    def test_straight_line_path_toward_distant_target(self):
        actor = _make_creature("Goblin", 0, 0)
        target = _make_creature("Brick", 5, 0)
        plan = AggressiveAdvance().plan(_ctx(actor), target, reach_ft=5)
        # speed 30 → 6 tile budget. Stops when within 5 ft (1 tile away).
        # From (0,0) toward (5,0), stops at (4,0): distance to (5,0) is 5 ft.
        assert plan.path == [Position(1, 0), Position(2, 0), Position(3, 0), Position(4, 0)]

    def test_diagonal_path_uses_kings_move(self):
        actor = _make_creature("Goblin", 0, 0)
        target = _make_creature("Brick", 4, 4)
        plan = AggressiveAdvance().plan(_ctx(actor), target, reach_ft=5)
        # Greedy diagonal: (1,1), (2,2), (3,3). At (3,3), Chebyshev distance
        # to (4,4) is max(|1|,|1|) = 1 tile = 5 ft → in reach.
        assert plan.path == [Position(1, 1), Position(2, 2), Position(3, 3)]

    def test_speed_bounded_truncation(self):
        actor = _make_creature("Goblin", 0, 0, speed=10)
        target = _make_creature("Brick", 20, 0)
        plan = AggressiveAdvance().plan(_ctx(actor), target, reach_ft=5)
        # speed 10 → 2 tile budget; target stays far away.
        assert len(plan.path) == 2
        assert plan.path == [Position(1, 0), Position(2, 0)]

    def test_zero_speed_yields_empty_path(self):
        actor = _make_creature("Goblin", 0, 0, speed=0)
        target = _make_creature("Brick", 10, 0)
        plan = AggressiveAdvance().plan(_ctx(actor), target, reach_ft=5)
        assert plan.path == []

    def test_hard_ceiling_caps_long_paths(self):
        actor = _make_creature("FastGoblin", 0, 0, speed=120)
        target = _make_creature("Brick", 100, 0)  # very far
        plan = AggressiveAdvance().plan(_ctx(actor), target, reach_ft=5)
        # speed 120 → 24 raw tile budget, but capped at HARD_STEP_CEILING=12.
        assert len(plan.path) <= HARD_STEP_CEILING
        assert len(plan.path) == HARD_STEP_CEILING

    def test_actor_without_position_returns_empty(self):
        actor = _make_creature("Goblin", 0, 0)
        actor.position = None
        target = _make_creature("Brick", 5, 0)
        plan = AggressiveAdvance().plan(_ctx(actor), target, reach_ft=5)
        assert plan.path == []

    def test_target_without_position_returns_empty(self):
        actor = _make_creature("Goblin", 0, 0)
        target = _make_creature("Brick", 5, 0)
        target.position = None
        plan = AggressiveAdvance().plan(_ctx(actor), target, reach_ft=5)
        assert plan.path == []

    def test_path_stops_when_reach_window_entered(self):
        actor = _make_creature("Goblin", 0, 0)
        target = _make_creature("Brick", 3, 0)
        plan = AggressiveAdvance().plan(_ctx(actor), target, reach_ft=5)
        # From (0,0), step to (1,0): distance to (3,0) is 10 ft. Step to (2,0):
        # distance is 5 ft → in reach. Path stops at (2,0).
        assert plan.path == [Position(1, 0), Position(2, 0)]

    def test_strategy_name(self):
        assert AggressiveAdvance().name == "aggressive"
