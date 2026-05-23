# ABOUTME: Engine-side spatial Map mirroring the client's RoomLayout for tile/terrain queries.
# ABOUTME: Read model only — client RoomLayout still drives rendering; no mutation API here.

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from dnd_engine.systems.action_economy import Terrain as TerrainType

if TYPE_CHECKING:
    from client_2d.integration.layout_schema import RoomLayout


class TileType(str, Enum):
    """
    Engine-side tile kinds, mirroring the client's tile semantics.

    Lowercase string values keep tiles JSON-friendly and consistent with the
    plan-03 style used by ``Size``, ``MovementMode``, and ``Terrain``. The
    client enum (``client_2d.integration.layout_schema.TileType``) is an
    ``IntEnum``; ``Map.from_room_layout`` translates by enum *name*.
    """

    FLOOR = "floor"
    WALL = "wall"
    DOOR = "door"
    WATER = "water"
    PIT = "pit"


# Walkability rules mirror RoomLayout.is_walkable (layout_schema.py): floors,
# doors, and water are walkable; walls and pits block movement.
_WALKABLE_TILES: frozenset[TileType] = frozenset(
    {TileType.FLOOR, TileType.DOOR, TileType.WATER}
)

# SRD difficult-terrain rule: water counts as difficult terrain. The client
# does not yet model difficult terrain; the engine adds it here.
_DIFFICULT_TILES: frozenset[TileType] = frozenset({TileType.WATER})


__all__ = ["Map", "TerrainType", "TileType"]


class Map:
    """
    Engine read model of the spatial grid.

    Stores tiles sparsely as ``dict[(x, y), TileType]``. Coordinates inside
    ``(width, height)`` bounds but absent from the dict are treated as walls
    (blocking, not walkable) — callers should populate every walkable cell
    explicitly. Out-of-bounds coordinates are likewise treated as blocking.

    The Map is immutable: there is no ``set_tile`` API. To update, construct
    a new Map.
    """

    def __init__(
        self,
        width: int,
        height: int,
        tiles: dict[tuple[int, int], TileType],
    ) -> None:
        self.width = width
        self.height = height
        # Defensive copy so external mutation of the source dict doesn't bleed in.
        self._tiles: dict[tuple[int, int], TileType] = dict(tiles)

    @classmethod
    def from_room_layout(cls, layout: RoomLayout) -> Map:
        """
        Build an engine ``Map`` from a client ``RoomLayout``.

        ``RoomLayout.tiles`` is a ``list[list[int]]`` indexed ``[y][x]``,
        with values from the client's ``IntEnum`` ``TileType``. We translate
        by enum *name* (FLOOR, WALL, DOOR, WATER, PIT) so the engine's
        string-valued enum and the client's int-valued enum stay loosely
        coupled.
        """
        # Lazy import keeps the engine package from depending on client_2d at
        # import time. Tests using importorskip cover the real RoomLayout path.
        from client_2d.integration.layout_schema import TileType as ClientTileType

        tiles: dict[tuple[int, int], TileType] = {}
        for y, row in enumerate(layout.tiles):
            for x, raw in enumerate(row):
                client_tile = ClientTileType(raw)
                tiles[(x, y)] = TileType[client_tile.name]
        return cls(width=layout.width, height=layout.height, tiles=tiles)

    def _in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def tile_at(self, x: int, y: int) -> TileType | None:
        """Return the tile at ``(x, y)``, or ``None`` if out of bounds."""
        if not self._in_bounds(x, y):
            return None
        return self._tiles.get((x, y))

    def is_walkable(self, x: int, y: int) -> bool:
        """
        Return True if a creature can enter ``(x, y)`` by walking.

        Floors, doors, and water are walkable. Walls and pits are not.
        Out-of-bounds and missing tiles default to blocking (False).
        """
        if not self._in_bounds(x, y):
            return False
        tile = self._tiles.get((x, y))
        if tile is None:
            return False
        return tile in _WALKABLE_TILES

    def is_blocking(self, x: int, y: int) -> bool:
        """
        Return True if ``(x, y)`` blocks movement.

        Walls and pits block. Out-of-bounds and missing tiles also block
        (the engine treats unknown geometry as solid).
        """
        if not self._in_bounds(x, y):
            return True
        tile = self._tiles.get((x, y))
        if tile is None:
            return True
        return tile not in _WALKABLE_TILES

    def terrain_at(self, x: int, y: int) -> TerrainType:
        """
        Return the terrain category at ``(x, y)`` for movement-cost purposes.

        Water is ``DIFFICULT`` per the SRD; everything else (including
        out-of-bounds and unknown tiles) is ``NORMAL``. Callers should reject
        the move via ``is_walkable`` before relying on terrain cost.
        """
        if not self._in_bounds(x, y):
            return TerrainType.NORMAL
        tile = self._tiles.get((x, y))
        if tile in _DIFFICULT_TILES:
            return TerrainType.DIFFICULT
        return TerrainType.NORMAL
