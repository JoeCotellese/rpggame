# ABOUTME: Integration tests for resource pool save/load functionality
# ABOUTME: Tests serialization and deserialization of resource pools in save files

import pytest
import json
import tempfile
from pathlib import Path

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.party import Party
from dnd_engine.core.game_state import GameState
from dnd_engine.systems.resources import ResourcePool
from dnd_engine.core.save_manager import SaveManager
from dnd_engine.rules.loader import DataLoader


class TestResourcePoolSerialization:
    """Test resource pool serialization"""

    @pytest.fixture
    def save_manager(self):
        """Create a temporary save manager for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield SaveManager(Path(tmpdir))

    @pytest.fixture
    def character_with_resources(self):
        """Create a character with resource pools"""
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        character = Character(
            name="Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16
        )

        # Add resource pools
        second_wind = ResourcePool(
            name="second_wind",
            current=1,
            maximum=1,
            recovery_type="short_rest"
        )
        action_surge = ResourcePool(
            name="action_surge",
            current=1,
            maximum=1,
            recovery_type="short_rest"
        )

        character.add_resource_pool(second_wind)
        character.add_resource_pool(action_surge)

        return character

    def test_serialize_character_with_resources(self, save_manager, character_with_resources):
        """Test that character with resources serializes correctly"""
        serialized = save_manager._serialize_character(character_with_resources)

        assert "resource_pools" in serialized
        assert isinstance(serialized["resource_pools"], list)
        assert len(serialized["resource_pools"]) == 2

    def test_serialize_resource_pools_structure(self, save_manager, character_with_resources):
        """Test that resource pools are serialized with correct structure"""
        serialized = save_manager._serialize_character(character_with_resources)
        pools = serialized["resource_pools"]

        # Find the second_wind pool
        second_wind = next(p for p in pools if p["name"] == "second_wind")

        assert second_wind["name"] == "second_wind"
        assert second_wind["current"] == 1
        assert second_wind["maximum"] == 1
        assert second_wind["recovery_type"] == "short_rest"

    def test_serialize_resource_pool_with_used_resources(self, save_manager, character_with_resources):
        """Test serializing a resource pool with used resources"""
        # Use some resources
        character_with_resources.use_resource("second_wind")

        serialized = save_manager._serialize_character(character_with_resources)
        pools = serialized["resource_pools"]

        second_wind = next(p for p in pools if p["name"] == "second_wind")
        assert second_wind["current"] == 0  # Should reflect the use

    def test_serialize_character_with_no_resources(self, save_manager):
        """Test serializing character with no resource pools"""
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        character = Character(
            name="Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16
        )

        serialized = save_manager._serialize_character(character)

        assert "resource_pools" in serialized
        assert serialized["resource_pools"] == []


class TestResourcePoolDeserialization:
    """Test resource pool deserialization"""

    @pytest.fixture
    def save_manager(self):
        """Create a temporary save manager for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield SaveManager(Path(tmpdir))

    def test_deserialize_character_with_resources(self, save_manager):
        """Test deserializing a character with resource pools"""
        char_data = {
            "name": "Fighter",
            "character_class": "fighter",
            "level": 1,
            "race": "human",
            "xp": 0,
            "max_hp": 12,
            "current_hp": 12,
            "ac": 16,
            "abilities": {
                "strength": 16,
                "dexterity": 14,
                "constitution": 14,
                "intelligence": 10,
                "wisdom": 12,
                "charisma": 8
            },
            "inventory": {
                "items": [],
                "equipped": {"weapon": None, "armor": None},
                "currency": {"gold": 0, "silver": 0, "copper": 0, "electrum": 0, "platinum": 0}
            },
            "conditions": [],
            "resource_pools": [
                {
                    "name": "second_wind",
                    "current": 0,
                    "maximum": 1,
                    "recovery_type": "short_rest"
                },
                {
                    "name": "action_surge",
                    "current": 1,
                    "maximum": 1,
                    "recovery_type": "short_rest"
                }
            ]
        }

        character = save_manager._deserialize_character(char_data)

        assert len(character.resource_pools) == 2
        assert "second_wind" in character.resource_pools
        assert "action_surge" in character.resource_pools

    def test_deserialize_resource_pool_values(self, save_manager):
        """Test that deserialized resource pool has correct values"""
        char_data = {
            "name": "Fighter",
            "character_class": "fighter",
            "level": 1,
            "race": "human",
            "xp": 0,
            "max_hp": 12,
            "current_hp": 12,
            "ac": 16,
            "abilities": {
                "strength": 16,
                "dexterity": 14,
                "constitution": 14,
                "intelligence": 10,
                "wisdom": 12,
                "charisma": 8
            },
            "inventory": {
                "items": [],
                "equipped": {"weapon": None, "armor": None},
                "currency": {"gold": 0, "silver": 0, "copper": 0, "electrum": 0, "platinum": 0}
            },
            "conditions": [],
            "resource_pools": [
                {
                    "name": "ki_points",
                    "current": 3,
                    "maximum": 5,
                    "recovery_type": "long_rest"
                }
            ]
        }

        character = save_manager._deserialize_character(char_data)
        ki_pool = character.get_resource_pool("ki_points")

        assert ki_pool is not None
        assert ki_pool.name == "ki_points"
        assert ki_pool.current == 3
        assert ki_pool.maximum == 5
        assert ki_pool.recovery_type == "long_rest"

    def test_deserialize_character_with_no_resources(self, save_manager):
        """Test deserializing character with no resource pools in save"""
        char_data = {
            "name": "Fighter",
            "character_class": "fighter",
            "level": 1,
            "race": "human",
            "xp": 0,
            "max_hp": 12,
            "current_hp": 12,
            "ac": 16,
            "abilities": {
                "strength": 16,
                "dexterity": 14,
                "constitution": 14,
                "intelligence": 10,
                "wisdom": 12,
                "charisma": 8
            },
            "inventory": {
                "items": [],
                "equipped": {"weapon": None, "armor": None},
                "currency": {"gold": 0, "silver": 0, "copper": 0, "electrum": 0, "platinum": 0}
            },
            "conditions": []
            # No resource_pools key - simulate older save file
        }

        character = save_manager._deserialize_character(char_data)

        assert len(character.resource_pools) == 0

    def test_deserialize_character_with_empty_resources(self, save_manager):
        """Test deserializing character with empty resource list"""
        char_data = {
            "name": "Fighter",
            "character_class": "fighter",
            "level": 1,
            "race": "human",
            "xp": 0,
            "max_hp": 12,
            "current_hp": 12,
            "ac": 16,
            "abilities": {
                "strength": 16,
                "dexterity": 14,
                "constitution": 14,
                "intelligence": 10,
                "wisdom": 12,
                "charisma": 8
            },
            "inventory": {
                "items": [],
                "equipped": {"weapon": None, "armor": None},
                "currency": {"gold": 0, "silver": 0, "copper": 0, "electrum": 0, "platinum": 0}
            },
            "conditions": [],
            "resource_pools": []
        }

        character = save_manager._deserialize_character(char_data)

        assert len(character.resource_pools) == 0


class TestResourcePoolRoundTrip:
    """Test saving and loading characters with resources"""

    @pytest.fixture
    def save_manager(self):
        """Create a temporary save manager for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield SaveManager(Path(tmpdir))

    def test_save_and_load_character_with_resources(self, save_manager):
        """Test full save and load cycle with resource pools"""
        # Create character with resources
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        character = Character(
            name="Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16
        )

        second_wind = ResourcePool(
            name="second_wind",
            current=0,  # Used
            maximum=1,
            recovery_type="short_rest"
        )
        character.add_resource_pool(second_wind)

        # Serialize
        serialized = save_manager._serialize_character(character)

        # Deserialize
        loaded_character = save_manager._deserialize_character(serialized)

        # Verify
        assert len(loaded_character.resource_pools) == 1
        loaded_pool = loaded_character.get_resource_pool("second_wind")
        assert loaded_pool is not None
        assert loaded_pool.current == 0  # Should be used
        assert loaded_pool.maximum == 1

    def test_save_and_load_preserves_partial_usage(self, save_manager):
        """Test that partial resource usage is preserved through save/load"""
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        character = Character(
            name="Wizard",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=6,
            ac=12
        )

        ki_points = ResourcePool(
            name="ki_points",
            current=2,
            maximum=5,
            recovery_type="short_rest"
        )
        character.add_resource_pool(ki_points)

        # Round trip
        serialized = save_manager._serialize_character(character)
        loaded = save_manager._deserialize_character(serialized)

        loaded_pool = loaded.get_resource_pool("ki_points")
        assert loaded_pool.current == 2
        assert loaded_pool.maximum == 5

    def test_save_and_load_multiple_resources(self, save_manager):
        """Test saving and loading multiple resource pools"""
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        character = Character(
            name="Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16
        )

        pools = [
            ResourcePool("second_wind", 1, 1, "short_rest"),
            ResourcePool("action_surge", 0, 1, "short_rest"),
            ResourcePool("indomitable", 1, 1, "long_rest")
        ]

        for pool in pools:
            character.add_resource_pool(pool)

        # Round trip
        serialized = save_manager._serialize_character(character)
        loaded = save_manager._deserialize_character(serialized)

        # Verify all pools loaded
        assert len(loaded.resource_pools) == 3
        assert loaded.get_resource_pool("second_wind").current == 1
        assert loaded.get_resource_pool("action_surge").current == 0
        assert loaded.get_resource_pool("indomitable").recovery_type == "long_rest"
