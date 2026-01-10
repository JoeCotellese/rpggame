# ABOUTME: Tests for layout schema Pydantic models.
# ABOUTME: Validates room layout parsing and validation logic.

"""Tests for layout_schema.py."""

import pytest
from client_2d.integration.layout_schema import (
    EntityPositions,
    LightSource,
    RoomLayout,
    SpawnPoints,
    TileType,
)
from pydantic import ValidationError


class TestTileType:
    """Tests for TileType enum."""

    def test_tile_values(self):
        """Tile types have expected integer values."""
        assert TileType.FLOOR == 0
        assert TileType.WALL == 1
        assert TileType.DOOR == 2
        assert TileType.WATER == 3
        assert TileType.PIT == 4


class TestSpawnPoints:
    """Tests for SpawnPoints model."""

    def test_parse_from_lists(self):
        """Spawn points parse from JSON list format."""
        data = {
            "player": [10, 5],
            "exits": {"north": [10, 0], "south": [10, 14]},
        }
        spawn = SpawnPoints.model_validate(data)
        assert spawn.player == (10, 5)
        assert spawn.exits["north"] == (10, 0)
        assert spawn.exits["south"] == (10, 14)

    def test_empty_exits(self):
        """Spawn points work with no exits."""
        spawn = SpawnPoints(player=(5, 5))
        assert spawn.exits == {}


class TestEntityPositions:
    """Tests for EntityPositions model."""

    def test_parse_from_lists(self):
        """Entity positions parse from JSON list format."""
        data = {
            "enemies": [[5, 5], [10, 8]],
            "items": [[3, 3]],
        }
        entities = EntityPositions.model_validate(data)
        assert entities.enemies == [(5, 5), (10, 8)]
        assert entities.items == [(3, 3)]

    def test_defaults_to_empty(self):
        """Entity positions default to empty lists."""
        entities = EntityPositions()
        assert entities.enemies == []
        assert entities.items == []


class TestLightSource:
    """Tests for LightSource model."""

    def test_default_values(self):
        """Light source has sensible defaults."""
        light = LightSource(x=5, y=5)
        assert light.type == "torch"
        assert light.radius == 20

    def test_custom_values(self):
        """Light source accepts custom values."""
        light = LightSource(x=10, y=8, type="lantern", radius=30)
        assert light.type == "lantern"
        assert light.radius == 30


class TestRoomLayout:
    """Tests for RoomLayout model."""

    @pytest.fixture
    def valid_layout_data(self):
        """Valid layout data for testing."""
        return {
            "width": 10,
            "height": 8,
            "tiles": [
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            ],
            "spawn_points": {
                "player": [5, 4],
                "exits": {"north": [5, 0]},
            },
        }

    def test_parse_valid_layout(self, valid_layout_data):
        """Valid layout parses successfully."""
        layout = RoomLayout.model_validate(valid_layout_data)
        assert layout.width == 10
        assert layout.height == 8
        assert len(layout.tiles) == 8
        assert len(layout.tiles[0]) == 10

    def test_dimension_mismatch_height(self, valid_layout_data):
        """Rejects layout with wrong height."""
        valid_layout_data["height"] = 10  # Wrong
        with pytest.raises(ValidationError) as exc_info:
            RoomLayout.model_validate(valid_layout_data)
        assert "height" in str(exc_info.value).lower()

    def test_dimension_mismatch_width(self, valid_layout_data):
        """Rejects layout with wrong row width."""
        valid_layout_data["tiles"][3] = [0, 0, 0]  # Too short
        with pytest.raises(ValidationError) as exc_info:
            RoomLayout.model_validate(valid_layout_data)
        assert "width" in str(exc_info.value).lower()

    def test_spawn_out_of_bounds(self, valid_layout_data):
        """Rejects spawn point outside room."""
        valid_layout_data["spawn_points"]["player"] = [100, 100]
        with pytest.raises(ValidationError) as exc_info:
            RoomLayout.model_validate(valid_layout_data)
        assert "out of bounds" in str(exc_info.value).lower()

    def test_get_tile(self, valid_layout_data):
        """get_tile returns correct tile type."""
        layout = RoomLayout.model_validate(valid_layout_data)
        assert layout.get_tile(0, 0) == TileType.WALL
        assert layout.get_tile(1, 1) == TileType.FLOOR
        # Out of bounds returns WALL
        assert layout.get_tile(-1, 0) == TileType.WALL
        assert layout.get_tile(100, 100) == TileType.WALL

    def test_is_walkable(self, valid_layout_data):
        """is_walkable correctly identifies walkable tiles."""
        layout = RoomLayout.model_validate(valid_layout_data)
        assert layout.is_walkable(1, 1) is True  # Floor
        assert layout.is_walkable(0, 0) is False  # Wall

    def test_is_blocking(self, valid_layout_data):
        """is_blocking correctly identifies blocking tiles."""
        layout = RoomLayout.model_validate(valid_layout_data)
        assert layout.is_blocking(0, 0) is True  # Wall
        assert layout.is_blocking(1, 1) is False  # Floor

    def test_with_entity_positions(self, valid_layout_data):
        """Layout accepts entity positions."""
        valid_layout_data["entity_positions"] = {
            "enemies": [[3, 3], [7, 5]],
            "items": [[5, 5]],
        }
        layout = RoomLayout.model_validate(valid_layout_data)
        assert len(layout.entity_positions.enemies) == 2
        assert len(layout.entity_positions.items) == 1

    def test_with_light_sources(self, valid_layout_data):
        """Layout accepts light sources."""
        valid_layout_data["light_sources"] = [
            {"x": 5, "y": 4, "type": "torch", "radius": 20}
        ]
        layout = RoomLayout.model_validate(valid_layout_data)
        assert len(layout.light_sources) == 1
        assert layout.light_sources[0].x == 5

    def test_zero_dimensions_rejected(self):
        """Rejects zero or negative dimensions."""
        with pytest.raises(ValidationError):
            RoomLayout(
                width=0,
                height=5,
                tiles=[],
                spawn_points={"player": (0, 0), "exits": {}},
            )
