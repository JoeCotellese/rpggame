# ABOUTME: Distance calculation utilities for grid-based tactical combat
# ABOUTME: Implements Chebyshev distance (diagonal movement costs 1 square)

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dnd_engine.core.map import Map
    from dnd_engine.core.position import Position


def chebyshev_distance(x1: int, y1: int, x2: int, y2: int) -> int:
    """
    Calculate Chebyshev distance between two grid positions.

    Chebyshev distance treats diagonal movement as costing 1 square,
    like a King moving in chess. This is simpler than D&D 5E's alternating
    diagonal rule (5-10-5-10) and commonly used in tactical games.

    Args:
        x1: X coordinate of first position
        y1: Y coordinate of first position
        x2: X coordinate of second position
        y2: Y coordinate of second position

    Returns:
        Distance in grid squares

    Example:
        >>> chebyshev_distance(0, 0, 3, 4)  # Move 3 right, 4 up
        4  # Max of horizontal and vertical distance
        >>> chebyshev_distance(0, 0, 3, 3)  # Diagonal
        3  # Diagonal counts as 1 per square
    """
    return max(abs(x2 - x1), abs(y2 - y1))


def is_adjacent(x1: int, y1: int, x2: int, y2: int) -> bool:
    """
    Check if two grid positions are adjacent (within melee range).

    Adjacent means Chebyshev distance of 1 or less, including diagonals.
    This is standard D&D melee range (5 ft = 1 square).

    Args:
        x1: X coordinate of first position
        y1: Y coordinate of first position
        x2: X coordinate of second position
        y2: Y coordinate of second position

    Returns:
        True if positions are adjacent (distance <= 1)

    Example:
        >>> is_adjacent(5, 5, 6, 5)  # 1 square right
        True
        >>> is_adjacent(5, 5, 6, 6)  # Diagonal
        True
        >>> is_adjacent(5, 5, 7, 5)  # 2 squares away
        False
    """
    return chebyshev_distance(x1, y1, x2, y2) <= 1


def distance_in_feet(x1: int, y1: int, x2: int, y2: int) -> int:
    """
    Calculate distance between grid positions in feet.

    Each grid square is 5 feet. Uses Chebyshev distance.

    Args:
        x1: X coordinate of first position
        y1: Y coordinate of first position
        x2: X coordinate of second position
        y2: Y coordinate of second position

    Returns:
        Distance in feet (multiples of 5)

    Example:
        >>> distance_in_feet(0, 0, 2, 3)
        15  # 3 squares * 5 ft
    """
    return chebyshev_distance(x1, y1, x2, y2) * 5


def shortest_route_squares(grid_map: Map, start: Position, target: Position) -> int | None:
    """
    Count the shortest legal grid route from ``start`` to ``target`` in squares.

    Implements the SRD § Playing on a Grid › Ranges rule ("Count by the
    shortest route") with the corner-blocking constraint from § Corners
    ("Diagonal movement can't cross the corner of a wall…"). Unlike
    ``chebyshev_distance``, this consultation of map geometry rejects
    diagonals whose cardinal neighbors are space-filling and rejects
    paths through blocking tiles.

    Performs a breadth-first search over 8-connected neighbors, treating
    every step (orthogonal or diagonal) as one square — matching the
    SRD's "diagonals cost the same as orthogonals" grid model. Stops
    counting in the target's space (i.e., the count is the number of
    steps to reach ``target``, not the number of tiles traversed).

    Args:
        grid_map: The map providing the ``is_blocking`` predicate.
        start: Origin position. May coincide with ``target``.
        target: Destination position.

    Returns:
        Number of grid squares along the shortest legal route, or
        ``None`` if no such route exists. ``0`` when ``start == target``.

    Example:
        With walls at ``(1, 0)`` and ``(0, 1)`` on a 3×3 floor, the
        diagonal ``(0, 0) → (1, 1)`` clips both walls' corners and is
        illegal; the orthogonal neighbors are also walls, so
        ``shortest_route_squares`` returns ``None`` (unreachable).
    """
    if start == target:
        return 0

    if grid_map.is_blocking(target.x, target.y):
        # A blocking target is unreachable — you cannot stop counting
        # inside a wall. Open-grid Chebyshev would silently return a
        # number; the map-aware helper refuses the malformed query.
        return None

    # BFS over 8-connected steps. Each entry is (x, y, steps_so_far).
    # ``visited`` keys are (x, y) tuples for cheap hashing.
    queue: deque[tuple[int, int, int]] = deque()
    queue.append((start.x, start.y, 0))
    visited: set[tuple[int, int]] = {(start.x, start.y)}

    while queue:
        x, y, steps = queue.popleft()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if (nx, ny) in visited:
                    continue
                if grid_map.is_blocking(nx, ny):
                    continue
                if (
                    dx != 0
                    and dy != 0
                    and (grid_map.is_blocking(x + dx, y) or grid_map.is_blocking(x, y + dy))
                ):
                    # Diagonal clips a wall corner — illegal route.
                    continue
                if nx == target.x and ny == target.y:
                    return steps + 1
                visited.add((nx, ny))
                queue.append((nx, ny, steps + 1))

    return None
