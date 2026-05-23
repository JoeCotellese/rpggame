# ABOUTME: Unit tests for the Position value object (plan-03 phase 1).
# ABOUTME: Covers construction, equality, hashing, immutability, addition, and displacement.

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from dnd_engine.core.position import Position


class TestPositionConstruction:
    """Constructing a Position stores x and y as integer fields."""

    def test_constructs_with_x_and_y(self) -> None:
        pos = Position(3, 4)
        assert pos.x == 3
        assert pos.y == 4


class TestPositionEquality:
    """Two Positions are equal iff both coordinates match."""

    def test_equal_when_both_coords_match(self) -> None:
        assert Position(1, 2) == Position(1, 2)

    def test_not_equal_when_coords_swapped(self) -> None:
        assert Position(1, 2) != Position(2, 1)


class TestPositionHashing:
    """Position is hashable so it can be used as a dict key or set member."""

    def test_usable_as_dict_key(self) -> None:
        d = {Position(0, 0): "origin"}
        assert d[Position(0, 0)] == "origin"


class TestPositionImmutability:
    """Position is frozen — attempting to mutate a field raises."""

    def test_mutating_x_raises_frozen_instance_error(self) -> None:
        pos = Position(3, 4)
        with pytest.raises(FrozenInstanceError):
            pos.x = 5  # type: ignore[misc]


class TestPositionAddition:
    """Adding two Positions returns a new Position with summed coordinates."""

    def test_adds_componentwise(self) -> None:
        assert Position(1, 2) + Position(3, 4) == Position(4, 6)

    def test_add_with_non_position_raises_type_error(self) -> None:
        with pytest.raises(TypeError):
            Position(1, 2) + 5  # type: ignore[operator]


class TestPositionDisplacementTo:
    """`displacement_to(other)` returns the (dx, dy) vector from self to other."""

    def test_positive_displacement(self) -> None:
        assert Position(1, 2).displacement_to(Position(4, 6)) == (3, 4)

    def test_negative_displacement(self) -> None:
        assert Position(0, 0).displacement_to(Position(-3, -2)) == (-3, -2)
