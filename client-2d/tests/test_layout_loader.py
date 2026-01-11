# ABOUTME: Tests for layout loader functionality.
# ABOUTME: Tests loading from files and procedural fallback generation.

"""Tests for layout_loader.py."""

import json
import tempfile
from pathlib import Path

import pytest
from client_2d.integration.layout_loader import LayoutLoader, generate_basic_room
from client_2d.integration.layout_schema import TileType


class TestGenerateBasicRoom:
    """Tests for generate_basic_room function."""

    def test_creates_correct_dimensions(self):
        """Generated room has correct dimensions."""
        layout = generate_basic_room(20, 15, {})
        assert layout.width == 20
        assert layout.height == 15
        assert len(layout.tiles) == 15
        assert len(layout.tiles[0]) == 20

    def test_walls_around_border(self):
        """Generated room has walls around border."""
        layout = generate_basic_room(10, 8, {})
        # Top row all walls
        assert all(t == TileType.WALL.value for t in layout.tiles[0])
        # Bottom row all walls
        assert all(t == TileType.WALL.value for t in layout.tiles[7])
        # Left column all walls
        assert all(layout.tiles[y][0] == TileType.WALL.value for y in range(8))
        # Right column all walls
        assert all(layout.tiles[y][9] == TileType.WALL.value for y in range(8))

    def test_floor_in_interior(self):
        """Generated room has floor in interior."""
        layout = generate_basic_room(10, 8, {})
        # Interior should be floor
        assert layout.tiles[1][1] == TileType.FLOOR.value
        assert layout.tiles[3][5] == TileType.FLOOR.value

    def test_player_spawn_in_center(self):
        """Player spawns in center of room."""
        layout = generate_basic_room(20, 16, {})
        px, py = layout.spawn_points.player
        assert px == 10  # width // 2
        assert py == 8  # height // 2

    def test_north_exit_creates_doorway(self):
        """North exit creates doorway in top wall."""
        layout = generate_basic_room(20, 15, {"north": "other_room"})
        center_x = 10
        # Top center should be door
        assert layout.tiles[0][center_x] == TileType.DOOR.value
        assert layout.spawn_points.exits["north"] == (center_x, 0)

    def test_south_exit_creates_doorway(self):
        """South exit creates doorway in bottom wall."""
        layout = generate_basic_room(20, 15, {"south": "other_room"})
        center_x = 10
        assert layout.tiles[14][center_x] == TileType.DOOR.value
        assert layout.spawn_points.exits["south"] == (center_x, 14)

    def test_east_exit_creates_doorway(self):
        """East exit creates doorway in right wall."""
        layout = generate_basic_room(20, 16, {"east": "other_room"})
        center_y = 8
        assert layout.tiles[center_y][19] == TileType.DOOR.value
        assert layout.spawn_points.exits["east"] == (19, center_y)

    def test_west_exit_creates_doorway(self):
        """West exit creates doorway in left wall."""
        layout = generate_basic_room(20, 16, {"west": "other_room"})
        center_y = 8
        assert layout.tiles[center_y][0] == TileType.DOOR.value
        assert layout.spawn_points.exits["west"] == (0, center_y)

    def test_multiple_exits(self):
        """Multiple exits create multiple doorways."""
        exits = {"north": "a", "south": "b", "east": "c", "west": "d"}
        layout = generate_basic_room(20, 16, exits)
        assert len(layout.spawn_points.exits) == 4
        # All should have door tiles
        for _direction, pos in layout.spawn_points.exits.items():
            x, y = pos
            assert layout.tiles[y][x] == TileType.DOOR.value


class TestLayoutLoader:
    """Tests for LayoutLoader class."""

    @pytest.fixture
    def temp_content_dir(self):
        """Create a temporary content directory with test dungeon."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = Path(tmpdir)

            # Create campaign structure
            campaign_dir = content_path / "campaigns" / "test_campaign" / "dungeons"
            campaign_dir.mkdir(parents=True)

            # Create a dungeon with layout
            dungeon_with_layout = {
                "name": "Test Dungeon",
                "rooms": {
                    "test.entrance": {
                        "name": "Entrance",
                        "exits": {"north": "test.main"},
                        "layout": {
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
                                [1, 1, 1, 1, 2, 1, 1, 1, 1, 1],
                            ],
                            "spawn_points": {
                                "player": [5, 4],
                                "exits": {"north": [4, 7]},
                            },
                            "entity_positions": {
                                "enemies": [[3, 3]],
                                "items": [[7, 5]],
                            },
                        },
                    },
                    "test.main": {
                        "name": "Main Room",
                        "exits": {"south": "test.entrance"},
                        # No layout - should need fallback
                    },
                },
            }

            with open(campaign_dir / "test_dungeon.json", "w") as f:
                json.dump(dungeon_with_layout, f)

            yield content_path

    def test_load_room_with_layout(self, temp_content_dir):
        """Loads room layout from dungeon file."""
        loader = LayoutLoader(temp_content_dir)
        layout = loader.load_room_layout(
            "test_dungeon", "test.entrance", campaign_id="test_campaign"
        )

        assert layout is not None
        assert layout.width == 10
        assert layout.height == 8
        assert layout.spawn_points.player == (5, 4)
        assert len(layout.entity_positions.enemies) == 1

    def test_returns_none_for_room_without_layout(self, temp_content_dir):
        """Returns None when room has no layout field."""
        loader = LayoutLoader(temp_content_dir)
        layout = loader.load_room_layout(
            "test_dungeon", "test.main", campaign_id="test_campaign"
        )
        assert layout is None

    def test_returns_none_for_missing_room(self, temp_content_dir):
        """Returns None when room doesn't exist."""
        loader = LayoutLoader(temp_content_dir)
        layout = loader.load_room_layout(
            "test_dungeon", "nonexistent.room", campaign_id="test_campaign"
        )
        assert layout is None

    def test_returns_none_for_missing_dungeon(self, temp_content_dir):
        """Returns None when dungeon file doesn't exist."""
        loader = LayoutLoader(temp_content_dir)
        layout = loader.load_room_layout(
            "nonexistent", "test.entrance", campaign_id="test_campaign"
        )
        assert layout is None

    def test_caches_loaded_layouts(self, temp_content_dir):
        """Caches layouts after first load."""
        loader = LayoutLoader(temp_content_dir)

        layout1 = loader.load_room_layout(
            "test_dungeon", "test.entrance", campaign_id="test_campaign"
        )
        layout2 = loader.load_room_layout(
            "test_dungeon", "test.entrance", campaign_id="test_campaign"
        )

        assert layout1 is layout2  # Same object from cache

    def test_clear_cache(self, temp_content_dir):
        """clear_cache removes cached layouts."""
        loader = LayoutLoader(temp_content_dir)

        layout1 = loader.load_room_layout(
            "test_dungeon", "test.entrance", campaign_id="test_campaign"
        )
        loader.clear_cache()
        layout2 = loader.load_room_layout(
            "test_dungeon", "test.entrance", campaign_id="test_campaign"
        )

        assert layout1 is not layout2  # Different objects

    def test_load_with_fallback_uses_layout(self, temp_content_dir):
        """load_room_with_fallback returns layout when present."""
        loader = LayoutLoader(temp_content_dir)
        layout = loader.load_room_with_fallback(
            "test_dungeon", "test.entrance", campaign_id="test_campaign"
        )

        assert layout.width == 10  # From file, not default

    def test_load_with_fallback_generates_when_missing(self, temp_content_dir):
        """load_room_with_fallback generates layout when missing."""
        loader = LayoutLoader(temp_content_dir)
        layout = loader.load_room_with_fallback(
            "test_dungeon",
            "test.main",
            campaign_id="test_campaign",
            default_width=25,
            default_height=20,
            exits={"south": "test.entrance"},
        )

        assert layout.width == 25
        assert layout.height == 20
        assert "south" in layout.spawn_points.exits

    def test_get_room_data(self, temp_content_dir):
        """get_room_data returns raw room dict."""
        loader = LayoutLoader(temp_content_dir)
        data = loader.get_room_data(
            "test_dungeon", "test.entrance", campaign_id="test_campaign"
        )

        assert data is not None
        assert data["name"] == "Entrance"
        assert "layout" in data
