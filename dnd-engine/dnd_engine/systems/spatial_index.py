# ABOUTME: Per-combat registry of creature placements plus spatial queries.
# ABOUTME: Distance/adjacency delegate to core.distance; LoS uses a supercover line vs Map.is_blocking.

from __future__ import annotations

from collections.abc import Iterator, Mapping
from types import MappingProxyType

from dnd_engine.core.creature import Size
from dnd_engine.core.distance import chebyshev_distance, is_adjacent
from dnd_engine.core.map import Map
from dnd_engine.core.position import Position


class SpatialIndex:
    """
    Engine-side registry mapping entity ids to grid Positions, plus spatial queries.

    Maintains synchronized dicts as its core invariant:
        _by_entity[entity_id] == anchor, and _by_position[tile] == entity_id
        for every tile in the entity's footprint (a creature's size, per the
        SRD Creature Size and Space table, determines whether that footprint
        is a single tile or an N x N block).
    Every mutation updates both sides atomically; readers may rely on the
    invariant in any externally observable state. Medium (and smaller)
    occupants claim exactly one tile, so the model degrades to the original
    one-tile-per-entity mapping.

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
        # ``_by_entity`` stores each entity's *anchor* (minimum-x / minimum-y
        # corner of its footprint); ``_by_position`` maps *every* tile a
        # footprint covers back to its entity. For Medium (1x1) occupants the
        # two are one-to-one, matching the original single-tile model.
        self._by_entity: dict[str, Position] = {}
        self._by_position: dict[Position, str] = {}
        self._size_by_entity: dict[str, Size] = {}
        self._occupants_view: MappingProxyType[str, Position] = MappingProxyType(self._by_entity)

    @staticmethod
    def footprint_tiles(anchor: Position, size: Size = Size.MEDIUM) -> frozenset[Position]:
        """Tiles a creature of ``size`` occupies when anchored at ``anchor``.

        The anchor is the minimum-x / minimum-y corner; the square block
        extends toward +x and +y. Medium (and smaller) sizes return just
        ``{anchor}``; Large/Huge/Gargantuan return the 2x2 / 3x3 / 4x4 block
        per the SRD Creature Size and Space table. Pure geometry — it does
        not consult map bounds or occupancy.
        """
        side = size.footprint
        return frozenset(
            Position(anchor.x + dx, anchor.y + dy) for dx in range(side) for dy in range(side)
        )

    # ------------------------------------------------------------------ #
    # Mutations
    # ------------------------------------------------------------------ #

    def place(
        self,
        entity_id: str,
        position: Position,
        size: Size = Size.MEDIUM,
        *,
        allow_overlap: bool = False,
    ) -> None:
        """Place a new occupant anchored at ``position``.

        ``size`` drives the footprint: Medium (the default) claims the single
        anchor tile, preserving the original single-tile behavior; Large+
        creatures claim their full N x N block (see ``footprint_tiles``). The
        anchor and the creature's size are retained so ``move`` and ``remove``
        can relocate or clear the whole footprint.

        ``allow_overlap`` widens the occupancy gate: when ``True``, footprint
        tiles already claimed by another entity are accepted (their reverse-
        index entry is left pointing at the original occupant, so
        ``occupant_at`` keeps resolving to the prior placer). Blocking-tile
        and duplicate-entity rejections still apply. The default preserves
        the original strict behavior.

        Raises:
            ValueError: If ``entity_id`` is already placed, or if *any* tile
                of the footprint is blocking per ``map.is_blocking`` (this
                also rejects footprints that spill off the map) or — unless
                ``allow_overlap`` is True — is already occupied by another
                entity.
        """
        if entity_id in self._by_entity:
            raise ValueError(f"entity {entity_id!r} is already placed")
        tiles = self.footprint_tiles(position, size)
        for tile in tiles:
            if self._map.is_blocking(tile.x, tile.y):
                raise ValueError(f"footprint tile {tile!r} is blocking")
            occupant = self._by_position.get(tile)
            if occupant is not None and not allow_overlap:
                raise ValueError(f"footprint tile {tile!r} is occupied by {occupant!r}")
        self._by_entity[entity_id] = position
        self._size_by_entity[entity_id] = size
        for tile in tiles:
            # When overlapping, leave the original occupant's reverse entry
            # in place so ``occupant_at`` keeps resolving to the prior
            # placer; the new entity's anchor still lives in ``_by_entity``.
            if tile not in self._by_position:
                self._by_position[tile] = entity_id

    def move(
        self,
        entity_id: str,
        position: Position,
        *,
        allow_overlap: bool = False,
    ) -> None:
        """Move an existing occupant so its footprint is anchored at ``position``.

        The creature's size is preserved from ``place``; the whole footprint
        relocates. Moving to the entity's current anchor is a no-op. Tiles the
        creature already occupies do not count as obstructions to itself, so a
        Large creature may slide into a position whose new block overlaps its
        old one.

        ``allow_overlap`` widens the occupancy gate the same way it does on
        ``place``: when ``True``, destination tiles already claimed by another
        entity are accepted (the prior occupant's reverse entry is preserved
        so ``occupant_at`` keeps resolving to them). Blocking-tile rejections
        still apply.

        Raises:
            KeyError: If ``entity_id`` is not currently placed.
            ValueError: If any tile of the destination footprint is blocking
                or — unless ``allow_overlap`` is True — occupied by another
                entity.
        """
        if entity_id not in self._by_entity:
            raise KeyError(entity_id)
        current = self._by_entity[entity_id]
        if position == current:
            return
        size = self._size_by_entity[entity_id]
        old_tiles = self.footprint_tiles(current, size)
        new_tiles = self.footprint_tiles(position, size)
        for tile in new_tiles:
            if self._map.is_blocking(tile.x, tile.y):
                raise ValueError(f"footprint tile {tile!r} is blocking")
            occupant = self._by_position.get(tile)
            if occupant is not None and occupant != entity_id and not allow_overlap:
                raise ValueError(f"footprint tile {tile!r} is occupied by {occupant!r}")
        # Vacate the old footprint first so an overlapping new block does not
        # collide with the creature's own former tiles, then claim the new one.
        for tile in old_tiles:
            if self._by_position.get(tile) == entity_id:
                del self._by_position[tile]
        self._by_entity[entity_id] = position
        for tile in new_tiles:
            # Skip tiles already claimed by another entity (only reachable
            # when allow_overlap=True) so we don't clobber the prior
            # occupant's reverse-index entry.
            if tile not in self._by_position:
                self._by_position[tile] = entity_id

    def remove(self, entity_id: str) -> None:
        """Remove a placed occupant, clearing every tile of its footprint.

        No-op if ``entity_id`` is not placed; cleanup paths can call this
        unconditionally without guarding.
        """
        position = self._by_entity.pop(entity_id, None)
        size = self._size_by_entity.pop(entity_id, None)
        if position is not None and size is not None:
            # Defensive: only drop reverse entries that still point at us
            # (the invariant guarantees they do, but guarding keeps stray
            # external corruption from cascading).
            for tile in self.footprint_tiles(position, size):
                if self._by_position.get(tile) == entity_id:
                    del self._by_position[tile]
                    # If another entity is anchored such that its
                    # footprint covers this tile (only possible after an
                    # ``allow_overlap`` placement), rebind the reverse
                    # entry so ``occupant_at`` keeps resolving to a
                    # live occupant.
                    for other_id, other_anchor in self._by_entity.items():
                        other_size = self._size_by_entity[other_id]
                        if tile in self.footprint_tiles(other_anchor, other_size):
                            self._by_position[tile] = other_id
                            break

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    @property
    def map(self) -> Map:
        """Read-only access to the underlying ``Map``.

        Consumers that need terrain or blocking queries against the same
        Map this index was built from should reach through this property
        rather than ``self._map`` — the underscore form is private to the
        index and may be replaced with a snapshot wrapper in future.
        """
        return self._map

    def position_of(self, entity_id: str) -> Position | None:
        """Return the anchor position of ``entity_id``, or ``None``.

        The anchor is the minimum-x / minimum-y corner of the footprint; for
        Large+ creatures the full set of occupied tiles is ``footprint_of``.
        """
        return self._by_entity.get(entity_id)

    def footprint_of(self, entity_id: str) -> frozenset[Position]:
        """Return every tile ``entity_id`` occupies, or an empty set if unplaced.

        A Medium occupant returns its single anchor tile; Large/Huge/
        Gargantuan creatures return their full N x N block.
        """
        anchor = self._by_entity.get(entity_id)
        if anchor is None:
            return frozenset()
        return self.footprint_tiles(anchor, self._size_by_entity[entity_id])

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
            raise ValueError(f"range_feet must be non-negative, got {range_feet}")
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


def _supercover_line(x0: int, y0: int, x1: int, y1: int) -> Iterator[tuple[int, int]]:
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
