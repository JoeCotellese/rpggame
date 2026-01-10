# ABOUTME: Unit tests for room registry that maps room GUIDs to dungeon files.
# ABOUTME: Tests prefix mapping, room lookup, and cross-dungeon navigation support.

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from dnd_engine.core.room_registry import RoomRegistry


@pytest.fixture
def temp_dungeons_dir():
    """Create a temporary directory with test dungeon files."""
    with TemporaryDirectory() as tmpdir:
        dungeons_path = Path(tmpdir)

        # Create crypt dungeon
        crypt = {
            "id": "test_crypt",
            "name": "Test Crypt",
            "start_room": "crypt.entrance",
            "rooms": {
                "crypt.entrance": {
                    "id": "crypt.entrance",
                    "location_type": "dungeon",
                    "parent": "test_crypt",
                    "name": "Crypt Entrance",
                    "description": "A dark entrance",
                    "exits": {"down": "crypt.hall"},
                },
                "crypt.hall": {
                    "id": "crypt.hall",
                    "location_type": "dungeon",
                    "parent": "test_crypt",
                    "name": "Crypt Hall",
                    "description": "A dusty hall",
                    "exits": {"up": "crypt.entrance"},
                },
            },
        }
        with open(dungeons_path / "test_crypt.json", "w") as f:
            json.dump(crypt, f)

        # Create town dungeon
        town = {
            "id": "test_town",
            "name": "Test Town",
            "start_room": "town.square",
            "rooms": {
                "town.square": {
                    "id": "town.square",
                    "location_type": "settlement",
                    "parent": "test_town",
                    "name": "Town Square",
                    "description": "A bustling square",
                    "exits": {"gate": "town.gate"},
                },
                "town.gate": {
                    "id": "town.gate",
                    "location_type": "settlement",
                    "parent": "test_town",
                    "name": "Town Gate",
                    "description": "The town gate",
                    "exits": {"square": "town.square", "road": "crypt.entrance"},
                },
            },
        }
        with open(dungeons_path / "test_town.json", "w") as f:
            json.dump(town, f)

        yield dungeons_path


class TestRoomRegistry:
    """Tests for RoomRegistry class."""

    def test_scan_dungeons_builds_prefix_mapping(self, temp_dungeons_dir):
        """Test that scanning dungeons builds the prefix-to-dungeon mapping."""
        registry = RoomRegistry(temp_dungeons_dir)

        # Should have found both prefixes
        prefixes = registry.get_all_prefixes()
        assert "crypt" in prefixes
        assert "town" in prefixes

    def test_get_dungeon_for_room_returns_correct_dungeon(self, temp_dungeons_dir):
        """Test getting dungeon name from room GUID."""
        registry = RoomRegistry(temp_dungeons_dir)

        assert registry.get_dungeon_for_room("crypt.entrance") == "test_crypt"
        assert registry.get_dungeon_for_room("crypt.hall") == "test_crypt"
        assert registry.get_dungeon_for_room("town.square") == "test_town"
        assert registry.get_dungeon_for_room("town.gate") == "test_town"

    def test_get_dungeon_for_unknown_room_returns_none(self, temp_dungeons_dir):
        """Test that unknown room prefixes return None."""
        registry = RoomRegistry(temp_dungeons_dir)

        assert registry.get_dungeon_for_room("unknown.room") is None
        assert registry.get_dungeon_for_room("no_prefix") is None

    def test_load_dungeon_returns_dungeon_data(self, temp_dungeons_dir):
        """Test loading a dungeon by name."""
        registry = RoomRegistry(temp_dungeons_dir)

        dungeon = registry.load_dungeon("test_crypt")
        assert dungeon is not None
        assert dungeon["name"] == "Test Crypt"
        assert "crypt.entrance" in dungeon["rooms"]

    def test_load_dungeon_caches_result(self, temp_dungeons_dir):
        """Test that loaded dungeons are cached."""
        registry = RoomRegistry(temp_dungeons_dir)

        dungeon1 = registry.load_dungeon("test_crypt")
        dungeon2 = registry.load_dungeon("test_crypt")

        # Should be same object (cached)
        assert dungeon1 is dungeon2

    def test_load_unknown_dungeon_returns_none(self, temp_dungeons_dir):
        """Test that loading unknown dungeon returns None."""
        registry = RoomRegistry(temp_dungeons_dir)

        assert registry.load_dungeon("nonexistent") is None

    def test_get_room_returns_room_data(self, temp_dungeons_dir):
        """Test getting room data by GUID."""
        registry = RoomRegistry(temp_dungeons_dir)

        room = registry.get_room("crypt.entrance")
        assert room is not None
        assert room["name"] == "Crypt Entrance"
        assert room["id"] == "crypt.entrance"

    def test_get_room_loads_dungeon_if_needed(self, temp_dungeons_dir):
        """Test that get_room loads dungeon if not already loaded."""
        registry = RoomRegistry(temp_dungeons_dir)

        # Dungeon not loaded yet
        assert "test_town" not in registry._loaded_dungeons

        # Getting room should load dungeon
        room = registry.get_room("town.square")
        assert room is not None
        assert "test_town" in registry._loaded_dungeons

    def test_get_unknown_room_returns_none(self, temp_dungeons_dir):
        """Test that getting unknown room returns None."""
        registry = RoomRegistry(temp_dungeons_dir)

        assert registry.get_room("unknown.room") is None
        assert registry.get_room("crypt.nonexistent") is None

    def test_room_exists_returns_correct_boolean(self, temp_dungeons_dir):
        """Test checking if rooms exist."""
        registry = RoomRegistry(temp_dungeons_dir)

        assert registry.room_exists("crypt.entrance") is True
        assert registry.room_exists("town.square") is True
        assert registry.room_exists("unknown.room") is False
        assert registry.room_exists("crypt.nonexistent") is False

    def test_get_dungeon_data_for_room(self, temp_dungeons_dir):
        """Test getting full dungeon data for a room."""
        registry = RoomRegistry(temp_dungeons_dir)

        dungeon = registry.get_dungeon_data_for_room("crypt.entrance")
        assert dungeon is not None
        assert dungeon["id"] == "test_crypt"
        assert "crypt.entrance" in dungeon["rooms"]
        assert "crypt.hall" in dungeon["rooms"]

    def test_skips_generated_dungeons(self, temp_dungeons_dir):
        """Test that generated dungeons are skipped during scanning."""
        # Create a generated dungeon
        generated = {
            "name": "Generated",
            "start_room": "gen.room1",
            "rooms": {"gen.room1": {"name": "Generated Room"}},
        }
        with open(temp_dungeons_dir / "generated_test.json", "w") as f:
            json.dump(generated, f)

        registry = RoomRegistry(temp_dungeons_dir)

        # Should not have the "gen" prefix
        assert "gen" not in registry.get_all_prefixes()

    def test_handles_rooms_without_prefix(self, temp_dungeons_dir):
        """Test handling of legacy room IDs without GUID prefix."""
        # Create dungeon with legacy room IDs
        legacy = {
            "name": "Legacy",
            "start_room": "entrance",
            "rooms": {"entrance": {"name": "Entrance"}, "hallway": {"name": "Hallway"}},
        }
        with open(temp_dungeons_dir / "legacy_dungeon.json", "w") as f:
            json.dump(legacy, f)

        registry = RoomRegistry(temp_dungeons_dir)

        # Legacy rooms should not create prefix entries
        assert registry.get_dungeon_for_room("entrance") is None
        assert registry.get_dungeon_for_room("hallway") is None


class TestRoomRegistryWithRealData:
    """Integration tests using real dungeon data."""

    def test_crypt_dungeon_registered(self):
        """Test that the real crypt dungeon is properly registered."""
        from dnd_engine.rules.loader import DataLoader

        loader = DataLoader()
        content_path = loader.data_path / "content"

        registry = RoomRegistry(
            campaign_id="the_unquiet_dead",
            content_path=content_path,
        )

        # Should find crypt rooms
        assert registry.get_dungeon_for_room("crypt.graveyard_entrance") == "crypt"
        assert registry.room_exists("crypt.family_shrine")

    def test_town_dungeon_registered(self):
        """Test that the town of Arden is properly registered."""
        from dnd_engine.rules.loader import DataLoader

        loader = DataLoader()
        content_path = loader.data_path / "content"

        registry = RoomRegistry(
            campaign_id="the_unquiet_dead",
            content_path=content_path,
        )

        # Should find town rooms
        assert registry.get_dungeon_for_room("arden.town_square") == "town_of_arden"
        assert registry.room_exists("arden.town_road")

    def test_cross_dungeon_exit_resolution(self):
        """Test that exits between dungeons can be resolved."""
        from dnd_engine.rules.loader import DataLoader

        loader = DataLoader()
        content_path = loader.data_path / "content"

        registry = RoomRegistry(
            campaign_id="the_unquiet_dead",
            content_path=content_path,
        )

        # Get the town road room (connects to crypt)
        town_road = registry.get_room("arden.town_road")
        assert town_road is not None

        # Check the exit to crypt (south direction)
        graveyard_exit = town_road["exits"].get("south")
        assert graveyard_exit is not None
        destination = graveyard_exit["destination"]

        # Should be able to resolve the destination room
        assert registry.room_exists(destination)
        crypt_entrance = registry.get_room(destination)
        assert crypt_entrance is not None
        assert crypt_entrance["name"] == "Overgrown Graveyard"
