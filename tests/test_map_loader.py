# ABOUTME: Unit tests for MapLoader and map creation utilities
# ABOUTME: Tests JSON map loading, spawn points, regions, and connections

import json
import pytest
from pathlib import Path

from dnd_engine.spatial import (
    Position,
    TileType,
    MapLoader,
    LoadedMap,
    SpawnPoint,
    MapRegion,
    create_simple_map,
    create_map_from_string,
)


class TestMapLoader:
    """Tests for MapLoader class."""

    def test_load_simple_map(self):
        """Test loading a simple map from dict."""
        data = {
            "name": "Test Map",
            "tiles": [
                "#####",
                "#...#",
                "#.@.#",
                "#...#",
                "#####",
            ],
        }

        loader = MapLoader()
        result = loader.load_from_dict(data)

        assert result.tile_map.width == 5
        assert result.tile_map.height == 5
        assert result.tile_map.name == "Test Map"

    def test_walls_are_walls(self):
        """Test that # characters become wall tiles."""
        data = {
            "tiles": [
                "#####",
                "#...#",
                "#####",
            ],
        }

        loader = MapLoader()
        result = loader.load_from_dict(data)

        # Check corners are walls
        assert result.tile_map.get_tile(Position(0, 0)).tile_type == TileType.WALL
        assert result.tile_map.get_tile(Position(4, 0)).tile_type == TileType.WALL

        # Check center is floor
        assert result.tile_map.get_tile(Position(2, 1)).tile_type == TileType.FLOOR

    def test_door_tiles(self):
        """Test door tiles are parsed correctly."""
        data = {
            "tiles": [
                "#####",
                "#...#",
                "##+ #",
                "#...#",
                "#####",
            ],
        }

        loader = MapLoader()
        result = loader.load_from_dict(data)

        door_tile = result.tile_map.get_tile(Position(2, 2))
        assert door_tile.tile_type == TileType.DOOR_CLOSED
        assert not door_tile.is_walkable

    def test_player_spawn_point(self):
        """Test player spawn point is detected."""
        data = {
            "tiles": [
                "#####",
                "#.@.#",
                "#####",
            ],
        }

        loader = MapLoader()
        result = loader.load_from_dict(data)

        # Should have one spawn point for player
        assert len(result.spawn_points) == 1
        spawn = result.spawn_points[0]
        assert spawn.entity_type == "player"
        assert spawn.position == Position(2, 1)
        assert spawn.display_char == "@"

    def test_monster_spawn_point(self):
        """Test monster spawn point is detected."""
        data = {
            "tiles": [
                "#####",
                "#.G.#",
                "#####",
            ],
        }

        loader = MapLoader()
        result = loader.load_from_dict(data)

        assert len(result.spawn_points) == 1
        spawn = result.spawn_points[0]
        assert spawn.entity_type == "monster"
        assert spawn.entity_id == "goblin"
        assert spawn.position == Position(2, 1)

    def test_custom_legend(self):
        """Test custom legend overrides defaults."""
        data = {
            "tiles": [
                "#####",
                "#.X.#",
                "#####",
            ],
            "legend": {
                "X": {"type": "chest"},
            },
        }

        loader = MapLoader()
        result = loader.load_from_dict(data)

        chest_tile = result.tile_map.get_tile(Position(2, 1))
        assert chest_tile.tile_type == TileType.CHEST

    def test_custom_spawn_in_legend(self):
        """Test custom spawn definition in legend."""
        data = {
            "tiles": [
                "#####",
                "#.Z.#",
                "#####",
            ],
            "legend": {
                "Z": {
                    "type": "floor",
                    "spawn": {
                        "type": "monster",
                        "id": "zombie",
                        "char": "Z",
                        "name": "Shambling Zombie",
                    },
                },
            },
        }

        loader = MapLoader()
        result = loader.load_from_dict(data)

        assert len(result.spawn_points) == 1
        spawn = result.spawn_points[0]
        assert spawn.entity_id == "zombie"
        assert spawn.display_name == "Shambling Zombie"

    def test_regions_as_dict(self):
        """Test parsing regions from dict format."""
        data = {
            "tiles": [
                "##########",
                "#........#",
                "#........#",
                "##########",
            ],
            "regions": {
                "main_hall": {
                    "x1": 1,
                    "y1": 1,
                    "x2": 8,
                    "y2": 2,
                    "description": "The main hall",
                },
            },
        }

        loader = MapLoader()
        result = loader.load_from_dict(data)

        assert len(result.regions) == 1
        region = result.regions[0]
        assert region.name == "main_hall"
        assert region.x1 == 1
        assert region.y2 == 2
        assert region.description == "The main hall"

    def test_regions_as_list(self):
        """Test parsing regions from list format."""
        data = {
            "tiles": [
                "##########",
                "#........#",
                "##########",
            ],
            "regions": [
                {"name": "room1", "x1": 1, "y1": 1, "x2": 4, "y2": 1},
                {"name": "room2", "x1": 5, "y1": 1, "x2": 8, "y2": 1},
            ],
        }

        loader = MapLoader()
        result = loader.load_from_dict(data)

        assert len(result.regions) == 2

    def test_region_contains(self):
        """Test region containment check."""
        region = MapRegion(name="test", x1=5, y1=5, x2=10, y2=10)

        assert region.contains(Position(5, 5))  # Corner
        assert region.contains(Position(7, 7))  # Middle
        assert region.contains(Position(10, 10))  # Other corner
        assert not region.contains(Position(4, 5))  # Outside
        assert not region.contains(Position(11, 5))  # Outside

    def test_connections(self):
        """Test parsing map connections."""
        data = {
            "tiles": [
                "#####",
                "#...#",
                "#.>.#",
                "#####",
            ],
            "connections": [
                {
                    "x": 2,
                    "y": 2,
                    "target_map": "level_2",
                    "target_x": 5,
                    "target_y": 5,
                    "type": "stairs_down",
                },
            ],
        }

        loader = MapLoader()
        result = loader.load_from_dict(data)

        assert len(result.connections) == 1
        conn = result.connections[0]
        assert conn.position == Position(2, 2)
        assert conn.target_map == "level_2"
        assert conn.target_position == Position(5, 5)
        assert conn.connection_type == "stairs_down"

    def test_multiple_spawns(self):
        """Test map with multiple spawn points."""
        data = {
            "tiles": [
                "#########",
                "#.@.G.S.#",
                "#########",
            ],
        }

        loader = MapLoader()
        result = loader.load_from_dict(data)

        assert len(result.spawn_points) == 3

        # Check we have player, goblin, and skeleton
        types = {sp.entity_type for sp in result.spawn_points}
        assert "player" in types
        assert "monster" in types

        ids = {sp.entity_id for sp in result.spawn_points if sp.entity_id}
        assert "goblin" in ids
        assert "skeleton" in ids

    def test_spawn_entities(self):
        """Test spawning entities onto the map."""
        data = {
            "tiles": [
                "#####",
                "#.@.#",
                "#.G.#",
                "#####",
            ],
        }

        loader = MapLoader()
        result = loader.load_from_dict(data)

        spawned = loader.spawn_entities(result)

        assert len(spawned) == 2
        assert result.tile_map.get_entity_at(Position(2, 1)) is not None  # Player
        assert result.tile_map.get_entity_at(Position(2, 2)) is not None  # Goblin

    def test_spawn_entities_skip_players(self):
        """Test spawning entities but skipping players."""
        data = {
            "tiles": [
                "#####",
                "#.@.#",
                "#.G.#",
                "#####",
            ],
        }

        loader = MapLoader()
        result = loader.load_from_dict(data)

        spawned = loader.spawn_entities(result, spawn_players=False)

        assert len(spawned) == 1
        assert result.tile_map.get_entity_at(Position(2, 1)) is None  # No player
        assert result.tile_map.get_entity_at(Position(2, 2)) is not None  # Goblin

    def test_explicit_dimensions(self):
        """Test that explicit width/height override tile dimensions."""
        data = {
            "tiles": [
                "#####",
                "#...#",
            ],
            "width": 10,
            "height": 5,
        }

        loader = MapLoader()
        result = loader.load_from_dict(data)

        assert result.tile_map.width == 10
        assert result.tile_map.height == 5

    def test_load_laboratory_map(self, tmp_path):
        """Test loading the laboratory grid map file."""
        # Create a test map file
        map_data = {
            "name": "Test Lab",
            "tiles": [
                "########",
                "#......#",
                "#..@...#",
                "#....G.#",
                "########",
            ],
        }

        map_file = tmp_path / "test_lab.json"
        with open(map_file, "w") as f:
            json.dump(map_data, f)

        loader = MapLoader(base_path=tmp_path)
        result = loader.load_from_file("test_lab.json")

        assert result.tile_map.name == "Test Lab"
        assert result.tile_map.width == 8
        assert len(result.spawn_points) == 2


class TestCreateSimpleMap:
    """Tests for create_simple_map utility."""

    def test_create_simple_map(self):
        """Test creating a simple empty map."""
        tm = create_simple_map(10, 8, "Simple")

        assert tm.width == 10
        assert tm.height == 8
        assert tm.name == "Simple"

    def test_simple_map_with_walls(self):
        """Test simple map has wall border by default."""
        tm = create_simple_map(10, 8)

        # Check corners are walls
        assert tm.get_tile(Position(0, 0)).tile_type == TileType.WALL
        assert tm.get_tile(Position(9, 0)).tile_type == TileType.WALL
        assert tm.get_tile(Position(0, 7)).tile_type == TileType.WALL
        assert tm.get_tile(Position(9, 7)).tile_type == TileType.WALL

        # Check interior is floor
        assert tm.get_tile(Position(5, 4)).tile_type == TileType.FLOOR

    def test_simple_map_without_walls(self):
        """Test simple map without wall border."""
        tm = create_simple_map(10, 8, wall_border=False)

        # All should be floor
        assert tm.get_tile(Position(0, 0)).tile_type == TileType.FLOOR
        assert tm.get_tile(Position(5, 4)).tile_type == TileType.FLOOR


class TestCreateMapFromString:
    """Tests for create_map_from_string utility."""

    def test_create_from_string(self):
        """Test creating map from ASCII string."""
        map_str = """
#####
#...#
#.@.#
#...#
#####
"""
        result = create_map_from_string(map_str, "String Test")

        assert result.tile_map.width == 5
        assert result.tile_map.height == 5
        assert result.tile_map.name == "String Test"
        assert len(result.spawn_points) == 1

    def test_create_from_string_with_custom_legend(self):
        """Test creating map with custom legend."""
        map_str = """
#####
#.X.#
#####
"""
        result = create_map_from_string(
            map_str,
            legend={"X": {"type": "altar"}},
        )

        altar = result.tile_map.get_tile(Position(2, 1))
        assert altar.tile_type == TileType.ALTAR

    def test_multiline_string_whitespace(self):
        """Test that leading/trailing whitespace is handled."""
        map_str = """

#####
#...#
#####

"""
        result = create_map_from_string(map_str)

        # Should strip empty lines
        assert result.tile_map.height == 3


class TestMapValidation:
    """Tests for map validation and edge cases."""

    def test_empty_tiles_raises_error(self):
        """Test that empty tiles array raises error."""
        data = {"name": "Empty", "tiles": []}

        loader = MapLoader()
        with pytest.raises(ValueError, match="tiles"):
            loader.load_from_dict(data)

    def test_jagged_map_uses_max_width(self):
        """Test that jagged maps use maximum row width."""
        data = {
            "tiles": [
                "#####",
                "###",
                "#######",
            ],
        }

        loader = MapLoader()
        result = loader.load_from_dict(data)

        assert result.tile_map.width == 7
        assert result.tile_map.height == 3

    def test_unknown_char_becomes_floor(self):
        """Test that unknown characters default to floor."""
        data = {
            "tiles": [
                "#####",
                "#.?.#",  # ? is not in legend
                "#####",
            ],
        }

        loader = MapLoader()
        result = loader.load_from_dict(data)

        unknown = result.tile_map.get_tile(Position(2, 1))
        assert unknown.tile_type == TileType.FLOOR
