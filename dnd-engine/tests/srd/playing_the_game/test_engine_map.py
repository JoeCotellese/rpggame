# ABOUTME: Tests for engine-side Map (plan-03 P2): tile/terrain queries, walkability.
# ABOUTME: Covers TileType enum, TerrainType re-export, Map construction, RoomLayout import.

from __future__ import annotations

import pytest

from dnd_engine.core.map import Map, TerrainType, TileType
from dnd_engine.systems.action_economy import Terrain


class TestTileTypeEnum:
    """TileType enum mirrors client tile semantics with lowercase JSON-friendly values."""

    def test_all_five_members_present(self) -> None:
        assert TileType.FLOOR.value == "floor"
        assert TileType.WALL.value == "wall"
        assert TileType.DOOR.value == "door"
        assert TileType.WATER.value == "water"
        assert TileType.PIT.value == "pit"

    def test_round_trip_from_string(self) -> None:
        assert TileType("floor") is TileType.FLOOR
        assert TileType("wall") is TileType.WALL
        assert TileType("door") is TileType.DOOR
        assert TileType("water") is TileType.WATER
        assert TileType("pit") is TileType.PIT


class TestTerrainTypeReExport:
    """TerrainType is re-exported from action_economy — one source of truth."""

    def test_terrain_type_is_action_economy_terrain(self) -> None:
        # Identity check: confirms re-export, not a duplicate enum.
        assert TerrainType is Terrain

    def test_members(self) -> None:
        assert TerrainType.NORMAL.value == "normal"
        assert TerrainType.DIFFICULT.value == "difficult"


@pytest.fixture
def basic_map() -> Map:
    """3x3 map with one floor, one wall, one water tile; other coords default to wall."""
    return Map(
        width=3,
        height=3,
        tiles={
            (0, 0): TileType.FLOOR,
            (1, 1): TileType.WALL,
            (2, 2): TileType.WATER,
        },
    )


class TestMapWalkability:
    """Walkable rules mirror client RoomLayout: FLOOR/DOOR/WATER walkable; WALL/PIT blocking."""

    def test_floor_is_walkable(self, basic_map: Map) -> None:
        assert basic_map.is_walkable(0, 0) is True

    def test_wall_is_not_walkable(self, basic_map: Map) -> None:
        assert basic_map.is_walkable(1, 1) is False

    def test_water_is_walkable(self, basic_map: Map) -> None:
        assert basic_map.is_walkable(2, 2) is True

    def test_out_of_bounds_high_is_not_walkable(self, basic_map: Map) -> None:
        assert basic_map.is_walkable(0, 5) is False

    def test_out_of_bounds_negative_is_not_walkable(self, basic_map: Map) -> None:
        assert basic_map.is_walkable(-1, 0) is False

    @pytest.mark.parametrize(
        "tile_type,expected_walkable",
        [
            (TileType.FLOOR, True),
            (TileType.DOOR, True),
            (TileType.WATER, True),
            (TileType.WALL, False),
            (TileType.PIT, False),
        ],
    )
    def test_walkable_by_tile_type(
        self, tile_type: TileType, expected_walkable: bool
    ) -> None:
        m = Map(width=1, height=1, tiles={(0, 0): tile_type})
        assert m.is_walkable(0, 0) is expected_walkable


class TestMapBlocking:
    """is_blocking is the dual of is_walkable for known tiles; out-of-bounds also blocks."""

    def test_wall_is_blocking(self, basic_map: Map) -> None:
        assert basic_map.is_blocking(1, 1) is True

    def test_floor_is_not_blocking(self, basic_map: Map) -> None:
        assert basic_map.is_blocking(0, 0) is False

    def test_out_of_bounds_is_blocking(self, basic_map: Map) -> None:
        assert basic_map.is_blocking(0, 5) is True

    @pytest.mark.parametrize(
        "tile_type,expected_blocking",
        [
            (TileType.WALL, True),
            (TileType.PIT, True),
            (TileType.FLOOR, False),
            (TileType.DOOR, False),
            (TileType.WATER, False),
        ],
    )
    def test_blocking_by_tile_type(
        self, tile_type: TileType, expected_blocking: bool
    ) -> None:
        m = Map(width=1, height=1, tiles={(0, 0): tile_type})
        assert m.is_blocking(0, 0) is expected_blocking


class TestMapTerrain:
    """WATER maps to DIFFICULT terrain; everything else to NORMAL."""

    def test_floor_is_normal_terrain(self, basic_map: Map) -> None:
        assert basic_map.terrain_at(0, 0) == TerrainType.NORMAL

    def test_water_is_difficult_terrain(self, basic_map: Map) -> None:
        assert basic_map.terrain_at(2, 2) == TerrainType.DIFFICULT

    def test_out_of_bounds_defaults_to_normal(self, basic_map: Map) -> None:
        # Out-of-bounds doesn't crash; engine spatial code rejects via is_walkable first.
        assert basic_map.terrain_at(0, 5) == TerrainType.NORMAL

    @pytest.mark.parametrize(
        "tile_type,expected_terrain",
        [
            (TileType.FLOOR, TerrainType.NORMAL),
            (TileType.DOOR, TerrainType.NORMAL),
            (TileType.WALL, TerrainType.NORMAL),
            (TileType.PIT, TerrainType.NORMAL),
            (TileType.WATER, TerrainType.DIFFICULT),
        ],
    )
    def test_terrain_by_tile_type(
        self, tile_type: TileType, expected_terrain: TerrainType
    ) -> None:
        m = Map(width=1, height=1, tiles={(0, 0): tile_type})
        assert m.terrain_at(0, 0) == expected_terrain


class TestMapTileAt:
    """tile_at returns the stored TileType, or None for out-of-bounds."""

    def test_in_bounds_returns_tile(self, basic_map: Map) -> None:
        assert basic_map.tile_at(0, 0) is TileType.FLOOR
        assert basic_map.tile_at(1, 1) is TileType.WALL
        assert basic_map.tile_at(2, 2) is TileType.WATER

    def test_out_of_bounds_returns_none(self, basic_map: Map) -> None:
        assert basic_map.tile_at(0, 5) is None
        assert basic_map.tile_at(-1, 0) is None


class TestMapMissingTileDefaultsToWall:
    """Coords inside bounds but absent from the tiles dict are treated as walls (blocking)."""

    def test_missing_tile_is_not_walkable(self) -> None:
        m = Map(width=3, height=3, tiles={})
        assert m.is_walkable(1, 1) is False

    def test_missing_tile_is_blocking(self) -> None:
        m = Map(width=3, height=3, tiles={})
        assert m.is_blocking(1, 1) is True


class TestMapFromRoomLayout:
    """Integration: build engine Map from a client RoomLayout (skip if client-2d absent)."""

    def test_from_room_layout_preserves_tiles(self) -> None:
        layout_schema = pytest.importorskip("client_2d.integration.layout_schema")
        ClientTileType = layout_schema.TileType
        RoomLayout = layout_schema.RoomLayout

        # 3x3 grid containing one of each tile type (PIT in last cell to fill).
        # Layout rows are list[list[int]], indexed [y][x].
        layout = RoomLayout(
            width=3,
            height=3,
            tiles=[
                [ClientTileType.FLOOR, ClientTileType.WALL, ClientTileType.DOOR],
                [ClientTileType.WATER, ClientTileType.PIT, ClientTileType.FLOOR],
                [ClientTileType.FLOOR, ClientTileType.FLOOR, ClientTileType.FLOOR],
            ],
            spawn_points={"player": (0, 0)},
        )

        m = Map.from_room_layout(layout)

        # Tile-by-tile correspondence (engine tiles indexed [x, y]; client [y][x]).
        expected = {
            (0, 0): TileType.FLOOR,
            (1, 0): TileType.WALL,
            (2, 0): TileType.DOOR,
            (0, 1): TileType.WATER,
            (1, 1): TileType.PIT,
            (2, 1): TileType.FLOOR,
            (0, 2): TileType.FLOOR,
            (1, 2): TileType.FLOOR,
            (2, 2): TileType.FLOOR,
        }
        for (x, y), expected_tile in expected.items():
            assert m.tile_at(x, y) is expected_tile, (
                f"mismatch at ({x},{y}): got {m.tile_at(x, y)!r}, expected {expected_tile!r}"
            )

    def test_from_room_layout_preserves_dimensions(self) -> None:
        layout_schema = pytest.importorskip("client_2d.integration.layout_schema")
        ClientTileType = layout_schema.TileType
        RoomLayout = layout_schema.RoomLayout

        layout = RoomLayout(
            width=2,
            height=2,
            tiles=[
                [ClientTileType.FLOOR, ClientTileType.FLOOR],
                [ClientTileType.FLOOR, ClientTileType.FLOOR],
            ],
            spawn_points={"player": (0, 0)},
        )
        m = Map.from_room_layout(layout)
        assert m.is_walkable(0, 0) is True
        assert m.is_walkable(1, 1) is True
        assert m.is_walkable(2, 0) is False  # out of bounds
