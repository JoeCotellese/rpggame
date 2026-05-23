# ABOUTME: Per-combat registry of creature placements plus spatial queries.
# ABOUTME: Distance/adjacency delegate to core.distance; LoS uses Bresenham vs Map.is_blocking.

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from dnd_engine.core.distance import chebyshev_distance, is_adjacent
from dnd_engine.core.map import Map
from dnd_engine.core.position import Position


class SpatialIndex:
    """
    Engine-side registry mapping entity ids to grid Positions, plus spatial queries.

    Maintains two synchronized dicts as its core invariant:
        _by_entity[entity_id] == position  iff  _by_position[position] == entity_id
    Every mutation updates both sides atomically; readers may rely on the
    invariant in any externally observable state.

    Mutations (`place`, `move`, `remove`) reject blocking tiles via
    ``Map.is_blocking`` and reject double-occupancy. Queries (`distance`,
    `is_adjacent`, `tiles_in_range`, `has_line_of_sight`) are pure functions
    over the supplied positions and the underlying map; they do not require
    either position to be a placed occupant.
    """

    def __init__(self, map: Map) -> None:
        self._map = map
        self._by_entity: dict[str, Position] = {}
        self._by_position: dict[Position, str] = {}

    # ------------------------------------------------------------------ #
    # Mutations
    # ------------------------------------------------------------------ #

    def place(self, entity_id: str, position: Position) -> None:
        """Place a new occupant at ``position``.

        Raises:
            ValueError: If ``entity_id`` is already placed, ``position`` is
                blocking per ``map.is_blocking``, or another entity already
                occupies ``position``.
        """
        if entity_id in self._by_entity:
            raise ValueError(f"entity {entity_id!r} is already placed")
        if self._map.is_blocking(position.x, position.y):
            raise ValueError(f"position {position!r} is blocking")
        if position in self._by_position:
            raise ValueError(
                f"position {position!r} is occupied by "
                f"{self._by_position[position]!r}"
            )
        self._by_entity[entity_id] = position
        self._by_position[position] = entity_id

    def move(self, entity_id: str, position: Position) -> None:
        """Move an existing occupant to ``position``.

        Moving to the entity's current position is a no-op.

        Raises:
            KeyError: If ``entity_id`` is not currently placed.
            ValueError: If ``position`` is blocking or occupied by another
                entity.
        """
        if entity_id not in self._by_entity:
            raise KeyError(entity_id)
        current = self._by_entity[entity_id]
        if position == current:
            return
        if self._map.is_blocking(position.x, position.y):
            raise ValueError(f"position {position!r} is blocking")
        occupant = self._by_position.get(position)
        if occupant is not None and occupant != entity_id:
            raise ValueError(
                f"position {position!r} is occupied by {occupant!r}"
            )
        del self._by_position[current]
        self._by_entity[entity_id] = position
        self._by_position[position] = entity_id

    def remove(self, entity_id: str) -> None:
        """Remove a placed occupant.

        No-op if ``entity_id`` is not placed; cleanup paths can call this
        unconditionally without guarding.
        """
        position = self._by_entity.pop(entity_id, None)
        if position is not None:
            # Defensive: only drop the reverse entry if it still points at us
            # (the invariant guarantees it does, but guarding keeps stray
            # external corruption from cascading).
            if self._by_position.get(position) == entity_id:
                del self._by_position[position]

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def position_of(self, entity_id: str) -> Position | None:
        """Return the placed position of ``entity_id``, or ``None``."""
        return self._by_entity.get(entity_id)

    def occupant_at(self, position: Position) -> str | None:
        """Return the entity id occupying ``position``, or ``None``."""
        return self._by_position.get(position)

    def occupants(self) -> Mapping[str, Position]:
        """Read-only view of all placements.

        Returns a ``MappingProxyType`` so callers cannot mutate the internal
        registry through the returned mapping.
        """
        return MappingProxyType(self._by_entity)

    def distance(self, a: Position, b: Position) -> int:
        """Chebyshev distance in tiles (D&D 5E grid rule)."""
        return chebyshev_distance(a.x, a.y, b.x, b.y)

    def distance_in_feet(self, a: Position, b: Position) -> int:
        """Chebyshev distance converted to feet (5 ft per tile)."""
        return self.distance(a, b) * 5

    def is_adjacent(self, a: Position, b: Position) -> bool:
        """True iff the two positions are exactly one tile apart (Chebyshev=1)."""
        # ``core.distance.is_adjacent`` uses Chebyshev <= 1, which includes
        # the same-square case. The plan-03 contract excludes same-square.
        return is_adjacent(a.x, a.y, b.x, b.y) and a != b

    def tiles_in_range(self, origin: Position, range_feet: int) -> set[Position]:
        """All tiles within Chebyshev ``range_feet // 5`` of ``origin``.

        Includes ``origin`` itself. Does not filter by walkability — callers
        decide whether to drop blocking tiles.
        """
        r = range_feet // 5
        return {
            Position(origin.x + dx, origin.y + dy)
            for dx in range(-r, r + 1)
            for dy in range(-r, r + 1)
        }

    def has_line_of_sight(self, a: Position, b: Position) -> bool:
        """True iff no intermediate tile on the Bresenham line a→b blocks.

        Endpoints ``a`` and ``b`` are NOT checked — occupants live on
        walkable tiles by construction. Identical positions return True.
        Diagonal corner-cutting is NOT yet enforced; P7 will tighten this.
        """
        if a == b:
            return True
        for x, y in _bresenham_line(a.x, a.y, b.x, b.y):
            if (x, y) == (a.x, a.y) or (x, y) == (b.x, b.y):
                continue
            if self._map.is_blocking(x, y):
                return False
        return True


def _bresenham_line(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """Integer Bresenham line from (x0, y0) to (x1, y1), inclusive of both endpoints.

    Standard 8-octant integer algorithm. Returns the tiles in order from
    start to end. For degenerate (start == end) inputs, returns ``[(x0, y0)]``.
    """
    points: list[tuple[int, int]] = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    while True:
        points.append((x, y))
        if x == x1 and y == y1:
            return points
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
