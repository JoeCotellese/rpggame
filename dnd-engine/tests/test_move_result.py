# ABOUTME: Tests for MoveResult value object — plan-03 P5 combat-step return contract.
# ABOUTME: Pins construction, immutability, equality, and field layout.

from __future__ import annotations

import pytest

from dnd_engine.core.move_result import MoveResult
from dnd_engine.core.position import Position


class TestMoveResultConstruction:
    def test_construct_success_result(self) -> None:
        result = MoveResult(
            ok=True,
            reason=None,
            position=Position(2, 3),
            movement_remaining=25,
        )
        assert result.ok is True
        assert result.reason is None
        assert result.position == Position(2, 3)
        assert result.movement_remaining == 25

    def test_construct_failure_result(self) -> None:
        result = MoveResult(
            ok=False,
            reason="blocking",
            position=Position(1, 1),
            movement_remaining=30,
        )
        assert result.ok is False
        assert result.reason == "blocking"
        assert result.position == Position(1, 1)
        assert result.movement_remaining == 30


class TestMoveResultImmutability:
    def test_cannot_mutate_fields(self) -> None:
        result = MoveResult(
            ok=True, reason=None, position=Position(0, 0), movement_remaining=30
        )
        with pytest.raises((AttributeError, TypeError)):
            result.ok = False  # type: ignore[misc]

    def test_no_dunder_dict_due_to_slots(self) -> None:
        """slots=True means instances have no __dict__."""
        result = MoveResult(
            ok=True, reason=None, position=Position(0, 0), movement_remaining=30
        )
        assert not hasattr(result, "__dict__")


class TestMoveResultEquality:
    def test_equal_instances_compare_equal(self) -> None:
        a = MoveResult(
            ok=True, reason=None, position=Position(1, 2), movement_remaining=20
        )
        b = MoveResult(
            ok=True, reason=None, position=Position(1, 2), movement_remaining=20
        )
        assert a == b

    def test_different_position_not_equal(self) -> None:
        a = MoveResult(
            ok=True, reason=None, position=Position(1, 2), movement_remaining=20
        )
        b = MoveResult(
            ok=True, reason=None, position=Position(2, 2), movement_remaining=20
        )
        assert a != b

    def test_different_movement_remaining_not_equal(self) -> None:
        a = MoveResult(
            ok=True, reason=None, position=Position(1, 2), movement_remaining=20
        )
        b = MoveResult(
            ok=True, reason=None, position=Position(1, 2), movement_remaining=15
        )
        assert a != b
