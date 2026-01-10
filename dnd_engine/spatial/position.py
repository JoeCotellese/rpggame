# ABOUTME: Position and Direction primitives for 2D grid-based spatial system
# ABOUTME: Immutable Position supports arithmetic, distance calculations, and direction vectors

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterator


class Direction(Enum):
    """Cardinal and intercardinal directions for movement."""

    NORTH = (0, -1)
    SOUTH = (0, 1)
    EAST = (1, 0)
    WEST = (-1, 0)
    NORTHEAST = (1, -1)
    NORTHWEST = (-1, -1)
    SOUTHEAST = (1, 1)
    SOUTHWEST = (-1, 1)

    @property
    def dx(self) -> int:
        """X component of direction vector."""
        return self.value[0]

    @property
    def dy(self) -> int:
        """Y component of direction vector."""
        return self.value[1]

    @property
    def is_diagonal(self) -> bool:
        """Check if this is a diagonal direction."""
        return abs(self.dx) + abs(self.dy) == 2

    @classmethod
    def cardinal(cls) -> list[Direction]:
        """Return only cardinal directions (N, S, E, W)."""
        return [cls.NORTH, cls.SOUTH, cls.EAST, cls.WEST]

    @classmethod
    def all_directions(cls) -> list[Direction]:
        """Return all 8 directions."""
        return list(cls)

    @classmethod
    def from_delta(cls, dx: int, dy: int) -> Direction | None:
        """Get direction from delta values, normalized to unit vector."""
        if dx == 0 and dy == 0:
            return None
        # Normalize to -1, 0, or 1
        norm_dx = 0 if dx == 0 else (1 if dx > 0 else -1)
        norm_dy = 0 if dy == 0 else (1 if dy > 0 else -1)
        for direction in cls:
            if direction.value == (norm_dx, norm_dy):
                return direction
        return None


@dataclass(frozen=True, slots=True)
class Position:
    """
    Immutable 2D grid position.

    Supports arithmetic operations for movement calculations and
    distance methods for range checking in combat.
    """

    x: int
    y: int

    def __add__(self, other: Position | Direction | tuple[int, int]) -> Position:
        """Add another position, direction, or tuple to get new position."""
        if isinstance(other, Position):
            return Position(self.x + other.x, self.y + other.y)
        elif isinstance(other, Direction):
            return Position(self.x + other.dx, self.y + other.dy)
        elif isinstance(other, tuple) and len(other) == 2:
            return Position(self.x + other[0], self.y + other[1])
        return NotImplemented

    def __sub__(self, other: Position | tuple[int, int]) -> Position:
        """Subtract to get relative position or delta."""
        if isinstance(other, Position):
            return Position(self.x - other.x, self.y - other.y)
        elif isinstance(other, tuple) and len(other) == 2:
            return Position(self.x - other[0], self.y - other[1])
        return NotImplemented

    def __iter__(self) -> Iterator[int]:
        """Allow unpacking as (x, y) tuple."""
        yield self.x
        yield self.y

    def move(self, direction: Direction) -> Position:
        """Return new position after moving in direction."""
        return self + direction

    def distance_to(self, other: Position) -> float:
        """Euclidean distance to another position."""
        dx = other.x - self.x
        dy = other.y - self.y
        return (dx * dx + dy * dy) ** 0.5

    def manhattan_distance(self, other: Position) -> int:
        """Manhattan (taxicab) distance - no diagonal movement."""
        return abs(other.x - self.x) + abs(other.y - self.y)

    def chebyshev_distance(self, other: Position) -> int:
        """
        Chebyshev distance - diagonal movement costs same as cardinal.

        This is the standard D&D 5E distance calculation where
        diagonal movement = 1 square = 5 feet.
        """
        return max(abs(other.x - self.x), abs(other.y - self.y))

    def grid_distance_feet(self, other: Position, feet_per_tile: int = 5) -> int:
        """
        Distance in feet for D&D 5E rules.

        Uses Chebyshev distance (diagonal = 1 tile) multiplied by
        feet per tile (default 5ft per tile).
        """
        return self.chebyshev_distance(other) * feet_per_tile

    def is_adjacent(self, other: Position, include_diagonal: bool = True) -> bool:
        """Check if other position is adjacent (1 tile away)."""
        if include_diagonal:
            return self.chebyshev_distance(other) == 1
        else:
            return self.manhattan_distance(other) == 1

    def direction_to(self, other: Position) -> Direction | None:
        """Get direction from this position toward other position."""
        dx = other.x - self.x
        dy = other.y - self.y
        return Direction.from_delta(dx, dy)

    def neighbors(self, include_diagonal: bool = True) -> list[Position]:
        """Get all adjacent positions."""
        directions = (
            Direction.all_directions() if include_diagonal else Direction.cardinal()
        )
        return [self + d for d in directions]

    def in_bounds(self, width: int, height: int) -> bool:
        """Check if position is within grid bounds (0 to width-1, 0 to height-1)."""
        return 0 <= self.x < width and 0 <= self.y < height

    def __str__(self) -> str:
        return f"({self.x}, {self.y})"

    def __repr__(self) -> str:
        return f"Position(x={self.x}, y={self.y})"
