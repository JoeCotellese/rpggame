# ABOUTME: Per-combat registry of creature placements plus spatial queries.
# ABOUTME: Distance/adjacency delegate to core.distance; LoS uses a supercover line vs Map.is_blocking.

from __future__ import annotations

from collections.abc import Iterator, Mapping
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
    `are_adjacent_tiles`, `tiles_in_range`, `has_line_of_sight`) are pure
    functions over the supplied positions and the underlying map; they do
    not require either position to be a placed occupant.

    Mutation failure-mode contract (deliberately asymmetric):

    - ``place(eid, pos)`` raises ``ValueError`` on conflict (already
      placed, blocking tile, occupied).
    - ``move(eid, pos)`` raises ``KeyError`` on a missing entity and
      ``ValueError`` on a blocking/occupied destination — the missing-
      entity case is a programmer error (you can't move what you haven't
      placed), distinct from the runtime "no path" cases.
    - ``remove(eid)`` is silent on a missing entity by design, so cleanup
      paths (game over, scenario reset, error handlers) can call it
      unconditionally without guarding.

    Consumers writing "teleport"-style helpers (remove-then-place) lose
    the missing-entity signal that ``move`` would surface — prefer
    ``move`` directly when the entity is known to be placed.
    """

    def __init__(self, grid_map: Map) -> None:
        # Parameter is ``grid_map`` rather than ``map`` to avoid shadowing the
        # ``map`` builtin within this scope — future maintenance that calls
        # ``list(map(...))`` inside the class would otherwise hit
        # ``TypeError: 'Map' object is not callable``.
        self._map = grid_map
        self._by_entity: dict[str, Position] = {}
        self._by_position: dict[Position, str] = {}
        self._occupants_view: MappingProxyType[str, Position] = MappingProxyType(
            self._by_entity
        )

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
        """Read-only LIVE view of all placements.

        Returns the same cached ``MappingProxyType`` on every call (so
        identity comparisons hold), backed directly by the internal
        ``_by_entity`` dict. Reflects subsequent mutations — callers that
        need a stable snapshot must materialize one with ``dict(view)``.
        Iterating the view while a separate code path mutates the index
        raises ``RuntimeError: dictionary changed size during iteration``;
        do not subscribe to events that may mutate the index while holding
        an active iterator over this view.
        """
        return self._occupants_view

    def distance(self, a: Position, b: Position) -> int:
        """Chebyshev distance in tiles (D&D 5E grid rule)."""
        return chebyshev_distance(a.x, a.y, b.x, b.y)

    def distance_in_feet(self, a: Position, b: Position) -> int:
        """Chebyshev distance converted to feet (5 ft per tile)."""
        return self.distance(a, b) * 5

    def are_adjacent_tiles(self, a: Position, b: Position) -> bool:
        """True iff the two positions are exactly one tile apart (Chebyshev=1).

        Same-tile (``a == b``) returns False — for the same-tile case, use
        ``distance(a, b) == 0`` explicitly. This deliberately differs from
        ``core.distance.is_adjacent`` which treats same-tile as adjacent
        under Chebyshev ≤ 1.
        """
        # ``core.distance.is_adjacent`` uses Chebyshev <= 1, which includes
        # the same-square case. The plan-03 contract excludes same-square.
        return is_adjacent(a.x, a.y, b.x, b.y) and a != b

    def tiles_in_range(self, origin: Position, range_feet: int) -> set[Position]:
        """All tiles within Chebyshev ``range_feet // 5`` of ``origin``.

        Includes ``origin`` itself. Does not filter by walkability — callers
        decide whether to drop blocking tiles. ``range_feet`` of 0 returns
        ``{origin}``.

        Raises:
            ValueError: If ``range_feet`` is negative.
        """
        if range_feet < 0:
            raise ValueError(
                f"range_feet must be non-negative, got {range_feet}"
            )
        r = range_feet // 5
        return {
            Position(origin.x + dx, origin.y + dy)
            for dx in range(-r, r + 1)
            for dy in range(-r, r + 1)
        }

    def has_line_of_sight(self, a: Position, b: Position) -> bool:
        """True iff no tile on the supercover line a→b blocks.

        If either endpoint is itself blocking per ``Map.is_blocking`` (wall,
        pit, out-of-bounds), returns False — you cannot see through or into
        solid geometry. Identical non-blocking positions return True; an
        identical blocking position returns False.

        The line uses a supercover (DDA-style) traversal so every tile the
        geometric segment clips is checked — a wall on a shallow-line tile
        will block LoS where a standard Bresenham walk would skip it.
        """
        if self._map.is_blocking(a.x, a.y) or self._map.is_blocking(b.x, b.y):
            return False
        if a == b:
            return True
        # Iterate the supercover lazily so we short-circuit on the first
        # blocking interior tile rather than materializing the whole path.
        # Endpoints are guaranteed non-blocking by the guard above; skip
        # the first (start) and stop short of the last (end) tile.
        line = _supercover_line(a.x, a.y, b.x, b.y)
        next(line, None)  # discard start endpoint
        previous: tuple[int, int] | None = None
        for tile in line:
            if previous is not None and self._map.is_blocking(*previous):
                return False
            previous = tile
        # ``previous`` is the end endpoint; already validated non-blocking.
        return True


def _supercover_line(
    x0: int, y0: int, x1: int, y1: int
) -> Iterator[tuple[int, int]]:
    """Supercover line traversal — yields every tile the segment from
    ``(x0, y0)`` to ``(x1, y1)`` geometrically touches, inclusive of both
    endpoints. Unlike standard Bresenham this never skips tiles the line
    clips through.

    Implemented as a generator so callers (notably
    :meth:`SpatialIndex.has_line_of_sight`) can short-circuit on the
    first blocking tile without building the full path list.

    Algorithm: take exactly ``1 + dx + dy`` steps, advancing one axis per
    step based on accumulated error. Visits the cells in a manner
    equivalent to a 2D DDA / Amanatides-Woo grid traversal for
    integer endpoints.
    """
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    x, y = x0, y0
    n = 1 + dx + dy
    x_inc = 1 if x1 > x0 else -1
    y_inc = 1 if y1 > y0 else -1
    error = dx - dy
    dx2 = dx * 2
    dy2 = dy * 2
    for _ in range(n):
        yield (x, y)
        if error > 0:
            x += x_inc
            error -= dy2
        else:
            y += y_inc
            error += dx2
