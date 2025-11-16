# ABOUTME: Unit tests for JSON data loaders
# ABOUTME: Tests loading monsters, items, and dungeons from JSON files

import pytest
from pathlib import Path
from dnd_engine.rules.loader import DataLoader
from dnd_engine.core.creature import Creature


class TestDataLoader:
    """Test the DataLoader class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.loader = DataLoader()
        self.data_path = Path(__file__).parent.parent / "dnd_engine" / "data"

    def test_loader_creation(self):
        """Test creating a data loader"""
        assert self.loader is not None

    def test_load_monsters(self):
        """Test loading monsters from JSON"""
        monsters = self.loader.load_monsters()

        assert monsters is not None
        assert len(monsters) > 0
        assert "goblin" in monsters
        assert "bandit" in monsters

    def test_create_monster_from_data(self):
        """Test creating a Creature from monster data"""
        monsters = self.loader.load_monsters()
        goblin_data = monsters["goblin"]

        goblin = self.loader.create_monster("goblin")

        assert isinstance(goblin, Creature)
        assert goblin.name == "Goblin"
        assert goblin.ac == 15
        assert goblin.is_alive

    def test_monster_abilities(self):
        """Test that monster abilities are loaded correctly"""
        goblin = self.loader.create_monster("goblin")

        assert goblin.abilities.strength == 8
        assert goblin.abilities.dexterity == 14
        assert goblin.abilities.constitution == 10

    def test_monster_hp_from_dice(self):
        """Test that monster HP is rolled from dice notation"""
        goblin = self.loader.create_monster("goblin")

        # Goblin has 2d6 HP, so between 2 and 12
        assert 2 <= goblin.max_hp <= 12
        assert goblin.current_hp == goblin.max_hp

    def test_multiple_monsters_different_hp(self):
        """Test that multiple instances get different HP rolls"""
        goblins = [self.loader.create_monster("goblin") for _ in range(10)]

        # Very unlikely all 10 have the same HP
        hp_values = [g.max_hp for g in goblins]
        assert len(set(hp_values)) > 1

    def test_load_nonexistent_monster(self):
        """Test loading a monster that doesn't exist"""
        with pytest.raises(KeyError):
            self.loader.create_monster("dragon")

    def test_monster_actions(self):
        """Test that monster actions are loaded"""
        monsters = self.loader.load_monsters()
        goblin_data = monsters["goblin"]

        assert "actions" in goblin_data
        assert len(goblin_data["actions"]) > 0
        assert goblin_data["actions"][0]["name"] == "Scimitar"

    def test_load_items(self):
        """Test loading items from JSON"""
        items = self.loader.load_items()

        assert items is not None
        assert "weapons" in items
        assert "armor" in items
        assert "consumables" in items

    def test_load_specific_item(self):
        """Test loading a specific item"""
        items = self.loader.load_items()

        longsword = items["weapons"]["longsword"]
        assert longsword["name"] == "Longsword"
        assert longsword["damage"] == "1d8"
        assert longsword["damage_type"] == "slashing"

    def test_load_dungeon(self):
        """Test loading a dungeon from JSON"""
        dungeon = self.loader.load_dungeon("goblin_warren")

        assert dungeon is not None
        assert dungeon["name"] == "Goblin Warren"
        assert "rooms" in dungeon
        assert "start_room" in dungeon

    def test_dungeon_rooms(self):
        """Test that dungeon rooms are loaded correctly"""
        dungeon = self.loader.load_dungeon("goblin_warren")

        assert "entrance" in dungeon["rooms"]
        entrance = dungeon["rooms"]["entrance"]

        assert "name" in entrance
        assert "description" in entrance
        assert "exits" in entrance
        assert "enemies" in entrance

    def test_dungeon_connections(self):
        """Test that dungeon room connections are valid"""
        dungeon = self.loader.load_dungeon("goblin_warren")
        rooms = dungeon["rooms"]

        # Check that all exits point to valid rooms
        for room_id, room_data in rooms.items():
            for direction, target_room in room_data["exits"].items():
                assert target_room in rooms, f"Exit {direction} from {room_id} points to invalid room {target_room}"

    def test_dungeon_start_room_exists(self):
        """Test that the dungeon's start room exists"""
        dungeon = self.loader.load_dungeon("goblin_warren")

        start_room = dungeon["start_room"]
        assert start_room in dungeon["rooms"]

    def test_load_classes(self):
        """Test loading character classes"""
        classes = self.loader.load_classes()

        assert classes is not None
        assert "fighter" in classes
        assert classes["fighter"]["name"] == "Fighter"
