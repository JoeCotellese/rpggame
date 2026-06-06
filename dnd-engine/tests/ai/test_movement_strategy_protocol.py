# ABOUTME: Unit tests for the MovementStrategy Protocol seam and MovePlan dataclass (#647).
# ABOUTME: Verifies runtime_checkable Protocol matches duck-typed stubs.

from __future__ import annotations

import pytest

from dnd_engine.core.creature import MovementMode
from dnd_engine.core.position import Position
from dnd_engine.systems.ai.movement_strategy import MovementStrategy, MovePlan


class TestMovePlan:
    def test_default_path_empty(self):
        plan = MovePlan()
        assert plan.path == []
        assert plan.mode == MovementMode.WALK
        assert plan.intent_phase == "close"

    def test_carries_path_and_mode(self):
        plan = MovePlan(
            path=[Position(1, 0), Position(2, 0)],
            mode=MovementMode.FLY,
            intent_phase="retreat",
        )
        assert plan.path == [Position(1, 0), Position(2, 0)]
        assert plan.mode == MovementMode.FLY
        assert plan.intent_phase == "retreat"

    def test_is_frozen(self):
        plan = MovePlan()
        with pytest.raises((AttributeError, TypeError)):
            plan.mode = MovementMode.FLY  # type: ignore[misc]


class _StubStrategy:
    """Duck-typed strategy stub — no inheritance, just the shape."""

    name = "stub"

    def plan(self, ctx, primary_target, reach_ft):  # noqa: ARG002
        return MovePlan(path=[Position(1, 0)])


class _MissingPlanMethod:
    """A class that has `name` but not `plan`."""

    name = "broken"


class TestMovementStrategyProtocol:
    def test_stub_satisfies_protocol(self):
        stub = _StubStrategy()
        assert isinstance(stub, MovementStrategy)

    def test_missing_plan_method_fails_protocol(self):
        broken = _MissingPlanMethod()
        assert not isinstance(broken, MovementStrategy)

    def test_stub_plan_returns_move_plan(self):
        stub = _StubStrategy()
        result = stub.plan(ctx=None, primary_target=None, reach_ft=5)
        assert isinstance(result, MovePlan)
        assert result.path == [Position(1, 0)]
