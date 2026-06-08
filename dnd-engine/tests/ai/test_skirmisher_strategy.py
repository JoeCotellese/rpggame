# ABOUTME: Unit tests for Skirmisher — the close-attack-retreat MovementStrategy (#649).
# ABOUTME: Covers both plan() (close phase) and plan_retreat() (hit-and-run withdrawal).

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dnd_engine.core.creature import Abilities, Creature, MovementMode
from dnd_engine.core.position import Position
from dnd_engine.systems.ai.context import TurnContext
from dnd_engine.systems.ai.strategies.aggressive import HARD_STEP_CEILING
from dnd_engine.systems.ai.strategies.skirmisher import Skirmisher


@dataclass
class _StubState:
    data_loader: Any = None


def _make_creature(name: str, x: int, y: int, speed: int = 30) -> Creature:
    c = Creature(
        name=name,
        max_hp=20,
        ac=15,
        abilities=Abilities(
            strength=10,
            dexterity=10,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
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


class TestSkirmisherClosePhase:
    """plan() mirrors AggressiveAdvance: greedy king's-move to reach."""

    def test_strategy_name(self):
        assert Skirmisher().name == "skirmisher"

    def test_empty_path_when_already_in_reach(self):
        actor = _make_creature("Goblin", 0, 0)
        target = _make_creature("Brick", 1, 0)
        plan = Skirmisher().plan(_ctx(actor), target, reach_ft=5)
        assert plan.path == []
        assert plan.mode == MovementMode.WALK
        assert plan.intent_phase == "close"

    def test_straight_line_path_toward_distant_target(self):
        actor = _make_creature("Goblin", 0, 0)
        target = _make_creature("Brick", 5, 0)
        plan = Skirmisher().plan(_ctx(actor), target, reach_ft=5)
        assert plan.path == [
            Position(1, 0),
            Position(2, 0),
            Position(3, 0),
            Position(4, 0),
        ]

    def test_zero_speed_yields_empty_path(self):
        actor = _make_creature("Goblin", 0, 0, speed=0)
        target = _make_creature("Brick", 10, 0)
        plan = Skirmisher().plan(_ctx(actor), target, reach_ft=5)
        assert plan.path == []

    def test_hard_ceiling_caps_long_paths(self):
        actor = _make_creature("FastGoblin", 0, 0, speed=120)
        target = _make_creature("Brick", 100, 0)
        plan = Skirmisher().plan(_ctx(actor), target, reach_ft=5)
        assert len(plan.path) == HARD_STEP_CEILING

    def test_actor_without_position_returns_empty(self):
        actor = _make_creature("Goblin", 0, 0)
        actor.position = None
        target = _make_creature("Brick", 5, 0)
        plan = Skirmisher().plan(_ctx(actor), target, reach_ft=5)
        assert plan.path == []


class TestSkirmisherRetreat:
    """plan_retreat() is the new surface: greedy opposite-king's-move away.

    Stops adding tiles as soon as the target is out of reach from the
    candidate tile (no point in over-running), and respects the
    remaining movement budget.
    """

    def test_retreat_stops_at_first_out_of_reach_tile(self):
        # Actor adjacent to target (just landed the attack). Speed 30,
        # already used 20 ft closing → 10 ft (2 tiles) remaining.
        # One step south escapes the 5 ft reach.
        actor = _make_creature("Goblin", 5, 9)
        target = _make_creature("Brick", 5, 10)
        retreat = Skirmisher().plan_retreat(
            _ctx(actor),
            target,
            reach_ft=5,
            budget_used_ft=20,
        )
        assert retreat is not None
        assert retreat.path == [Position(5, 8)]
        assert retreat.mode == MovementMode.WALK
        assert retreat.intent_phase == "retreat"

    def test_retreat_extends_when_first_step_still_in_reach(self):
        # Reach 10 ft: one diagonal step away (Chebyshev 10 ft) is still
        # in reach, so the path keeps going until truly out.
        actor = _make_creature("Goblin", 4, 4, speed=30)
        target = _make_creature("Brick", 5, 5)
        retreat = Skirmisher().plan_retreat(
            _ctx(actor),
            target,
            reach_ft=10,
            budget_used_ft=5,
        )
        assert retreat is not None
        # (3,3) → distance 10 ft (still in reach). (2,2) → 15 ft (out).
        assert retreat.path == [Position(3, 3), Position(2, 2)]

    def test_retreat_respects_remaining_budget(self):
        # Long reach + tight budget: would need 2 tiles to escape but
        # only 1 tile of movement remains.
        actor = _make_creature("Goblin", 4, 4, speed=30)
        target = _make_creature("Brick", 5, 5)
        retreat = Skirmisher().plan_retreat(
            _ctx(actor),
            target,
            reach_ft=10,
            budget_used_ft=25,
        )
        assert retreat is not None
        assert retreat.path == [Position(3, 3)]  # one tile only

    def test_retreat_returns_none_when_budget_exhausted(self):
        actor = _make_creature("Goblin", 5, 9, speed=30)
        target = _make_creature("Brick", 5, 10)
        retreat = Skirmisher().plan_retreat(
            _ctx(actor),
            target,
            reach_ft=5,
            budget_used_ft=30,
        )
        assert retreat is None

    def test_retreat_returns_none_when_budget_below_one_tile(self):
        actor = _make_creature("Goblin", 5, 9, speed=30)
        target = _make_creature("Brick", 5, 10)
        retreat = Skirmisher().plan_retreat(
            _ctx(actor),
            target,
            reach_ft=5,
            budget_used_ft=26,  # 4 ft remaining
        )
        assert retreat is None

    def test_retreat_returns_none_when_actor_has_no_position(self):
        actor = _make_creature("Goblin", 5, 9)
        actor.position = None
        target = _make_creature("Brick", 5, 10)
        retreat = Skirmisher().plan_retreat(
            _ctx(actor),
            target,
            reach_ft=5,
            budget_used_ft=0,
        )
        assert retreat is None

    def test_retreat_returns_none_when_target_has_no_position(self):
        actor = _make_creature("Goblin", 5, 9)
        target = _make_creature("Brick", 5, 10)
        target.position = None
        retreat = Skirmisher().plan_retreat(
            _ctx(actor),
            target,
            reach_ft=5,
            budget_used_ft=0,
        )
        assert retreat is None

    def test_retreat_empty_when_already_out_of_reach(self):
        # Actor at long range — no retreat planning needed. Returns
        # an empty MovePlan rather than None so the caller can still
        # log "already disengaged" without special-casing.
        actor = _make_creature("Goblin", 0, 0)
        target = _make_creature("Brick", 10, 10)  # Chebyshev 50 ft
        retreat = Skirmisher().plan_retreat(
            _ctx(actor),
            target,
            reach_ft=5,
            budget_used_ft=0,
        )
        assert retreat is not None
        assert retreat.path == []
        assert retreat.intent_phase == "retreat"

    def test_retreat_caps_at_hard_step_ceiling(self):
        # Pathological speed; retreat should never plan more than 12
        # tiles even with abundant budget.
        actor = _make_creature("FastGoblin", 5, 9, speed=200)
        target = _make_creature("Brick", 5, 10)
        retreat = Skirmisher().plan_retreat(
            _ctx(actor),
            target,
            reach_ft=100,  # never out of reach
            budget_used_ft=0,
        )
        assert retreat is not None
        assert len(retreat.path) == HARD_STEP_CEILING

    def test_retreat_diagonal_away_from_target(self):
        # Actor northwest of target; retreat goes further NW.
        actor = _make_creature("Goblin", 5, 5)
        target = _make_creature("Brick", 6, 6)
        retreat = Skirmisher().plan_retreat(
            _ctx(actor),
            target,
            reach_ft=5,
            budget_used_ft=20,
        )
        assert retreat is not None
        # (4,4) → Chebyshev 10 ft from (6,6) → out of reach.
        assert retreat.path == [Position(4, 4)]
