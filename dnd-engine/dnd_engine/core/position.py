# ABOUTME: Position value object for plan-03's engine-side spatial model.
# ABOUTME: Frozen (x, y) grid coordinate with vector addition and displacement.

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Position:
    """
    Immutable grid coordinate in engine space (x, y).

    Foundation for the plan-03 spatial model — distance, line-of-sight,
    cover, opportunity-attack, and footprint logic will all consume
    Positions threaded through `Creature.position`. This value object
    intentionally exposes only the two operations the foundation slice
    needs: vector addition (to apply a displacement) and a displacement
    query (to ask "what vector goes from me to other?"). Distance metrics
    (Chebyshev, Manhattan) live in `dnd_engine.core.distance`.

    `@dataclass(frozen=True, slots=True)` provides immutability,
    structural equality, and a stable hash, so Positions work as dict
    keys and set members for spatial-index implementations later in
    the plan.
    """

    x: int
    y: int

    def __add__(self, other: Position) -> Position:
        """Return a new Position whose coordinates are the componentwise sum.

        Args:
            other: The Position to add to `self`.

        Returns:
            A new Position at `(self.x + other.x, self.y + other.y)`.

        Raises:
            TypeError: If `other` is not a Position.
        """
        if not isinstance(other, Position):
            raise TypeError(
                f"unsupported operand type(s) for +: 'Position' and '{type(other).__name__}'"
            )
        return Position(self.x + other.x, self.y + other.y)

    def displacement_to(self, other: Position) -> tuple[int, int]:
        """Return the (dx, dy) vector that would move `self` to `other`.

        Args:
            other: The destination Position.

        Returns:
            Tuple `(other.x - self.x, other.y - self.y)`.
        """
        return (other.x - self.x, other.y - self.y)
