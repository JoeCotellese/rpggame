# ABOUTME: Unit tests for Character subclass field and related features
# ABOUTME: Tests subclass tracking, Fast Hands feature, and save/load functionality

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.party import Party
from dnd_engine.core.game_state import GameState
from dnd_engine.core.save_manager import SaveManager
from pathlib import Path
import tempfile
import shutil


class TestCharacterSubclass:
    """Test Character subclass field"""

    @pytest.fixture
    def abilities(self):
        """Create test abilities"""
        return Abilities(
            strength=10, dexterity=16, constitution=12,
            intelligence=10, wisdom=10, charisma=8
        )

    def test_character_with_subclass(self, abilities):
        """Test creating character with subclass"""
        character = Character(
            name="Sneaky",
            character_class=CharacterClass.ROGUE,
            level=3,
            abilities=abilities,
            max_hp=20,
            ac=14,
            subclass="thief"
        )

        assert character.subclass == "thief"

    def test_character_without_subclass(self, abilities):
        """Test creating character without subclass (defaults to None)"""
        character = Character(
            name="Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16
        )

        assert character.subclass is None


class TestFastHands:
    """Test Thief Fast Hands feature detection"""

    @pytest.fixture
    def abilities(self):
        """Create test abilities"""
        return Abilities(
            strength=10, dexterity=16, constitution=12,
            intelligence=10, wisdom=10, charisma=8
        )

    def test_thief_level_3_has_fast_hands(self, abilities):
        """Test that level 3+ Thief has Fast Hands"""
        character = Character(
            name="Sneaky",
            character_class=CharacterClass.ROGUE,
            level=3,
            abilities=abilities,
            max_hp=20,
            ac=14,
            subclass="thief"
        )

        assert character.has_fast_hands() is True

    def test_thief_level_5_has_fast_hands(self, abilities):
        """Test that higher level Thief still has Fast Hands"""
        character = Character(
            name="Sneaky",
            character_class=CharacterClass.ROGUE,
            level=5,
            abilities=abilities,
            max_hp=30,
            ac=14,
            subclass="thief"
        )

        assert character.has_fast_hands() is True

    def test_thief_level_2_no_fast_hands(self, abilities):
        """Test that level 2 Thief doesn't have Fast Hands yet"""
        character = Character(
            name="Sneaky",
            character_class=CharacterClass.ROGUE,
            level=2,
            abilities=abilities,
            max_hp=15,
            ac=14,
            subclass="thief"
        )

        assert character.has_fast_hands() is False

    def test_rogue_without_thief_subclass_no_fast_hands(self, abilities):
        """Test that Rogue without Thief subclass doesn't have Fast Hands"""
        character = Character(
            name="Assassin",
            character_class=CharacterClass.ROGUE,
            level=3,
            abilities=abilities,
            max_hp=20,
            ac=14,
            subclass="assassin"
        )

        assert character.has_fast_hands() is False

    def test_rogue_no_subclass_no_fast_hands(self, abilities):
        """Test that Rogue with no subclass doesn't have Fast Hands"""
        character = Character(
            name="Rogue",
            character_class=CharacterClass.ROGUE,
            level=3,
            abilities=abilities,
            max_hp=20,
            ac=14,
            subclass=None
        )

        assert character.has_fast_hands() is False

    def test_fighter_no_fast_hands(self, abilities):
        """Test that non-Rogue classes don't have Fast Hands"""
        character = Character(
            name="Fighter",
            character_class=CharacterClass.FIGHTER,
            level=5,
            abilities=abilities,
            max_hp=40,
            ac=16,
            subclass="champion"
        )

        assert character.has_fast_hands() is False


class TestSubclassSerialization:
    """Test saving and loading character with subclass"""

    @pytest.fixture
    def temp_saves_dir(self):
        """Create temporary directory for save files"""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        # Cleanup after test
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def abilities(self):
        """Create test abilities"""
        return Abilities(
            strength=10, dexterity=16, constitution=12,
            intelligence=10, wisdom=10, charisma=8
        )

    def test_save_and_load_character_with_subclass(self, temp_saves_dir, abilities):
        """Test that subclass is preserved through save/load"""
        # Create character with subclass
        thief = Character(
            name="Sneaky",
            character_class=CharacterClass.ROGUE,
            level=3,
            abilities=abilities,
            max_hp=20,
            ac=14,
            subclass="thief"
        )

        # Create party and game state
        party = Party()
        party.add_character(thief)
        game_state = GameState(party=party, dungeon_name="goblin_warren")

        # Save game
        save_manager = SaveManager(saves_dir=temp_saves_dir)
        save_manager.save_game(game_state, "test_save")

        # Load game
        loaded_state = save_manager.load_game("test_save")
        loaded_character = loaded_state.party.characters[0]

        # Verify subclass was preserved
        assert loaded_character.name == "Sneaky"
        assert loaded_character.subclass == "thief"
        assert loaded_character.has_fast_hands() is True

    def test_save_and_load_character_without_subclass(self, temp_saves_dir, abilities):
        """Test that character without subclass saves correctly"""
        # Create character without subclass
        fighter = Character(
            name="Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16
        )

        # Create party and game state
        party = Party()
        party.add_character(fighter)
        game_state = GameState(party=party, dungeon_name="goblin_warren")

        # Save game
        save_manager = SaveManager(saves_dir=temp_saves_dir)
        save_manager.save_game(game_state, "test_save")

        # Load game
        loaded_state = save_manager.load_game("test_save")
        loaded_character = loaded_state.party.characters[0]

        # Verify subclass is None
        assert loaded_character.name == "Fighter"
        assert loaded_character.subclass is None
        assert loaded_character.has_fast_hands() is False

    def test_load_old_save_without_subclass_field(self, temp_saves_dir, abilities):
        """Test that old saves without subclass field load correctly"""
        # Create a save file manually without subclass field (simulating old save)
        import json
        from datetime import datetime

        old_save_data = {
            "version": "1.0.0",
            "metadata": {
                "created": datetime.now().isoformat(),
                "last_played": datetime.now().isoformat(),
                "auto_save": False
            },
            "party": [
                {
                    "name": "OldRogue",
                    "character_class": "rogue",
                    "level": 3,
                    "race": "human",
                    # Note: no "subclass" field
                    "xp": 900,
                    "max_hp": 20,
                    "current_hp": 20,
                    "ac": 14,
                    "abilities": {
                        "strength": 10,
                        "dexterity": 16,
                        "constitution": 12,
                        "intelligence": 10,
                        "wisdom": 10,
                        "charisma": 8
                    },
                    "inventory": {
                        "items": [],
                        "equipped": {},
                        "currency": {
                            "copper": 0,
                            "silver": 0,
                            "electrum": 0,
                            "gold": 10,
                            "platinum": 0
                        }
                    },
                    "conditions": [],
                    "resource_pools": {}
                }
            ],
            "game_state": {
                "dungeon_name": "goblin_warren",
                "current_room_id": "entrance",
                "dungeon_state": {},
                "in_combat": False,
                "action_history": []
            }
        }

        # Write old save file
        save_path = temp_saves_dir / "old_save.json"
        with open(save_path, 'w') as f:
            json.dump(old_save_data, f, indent=2)

        # Load old save
        save_manager = SaveManager(saves_dir=temp_saves_dir)
        loaded_state = save_manager.load_game("old_save")
        loaded_character = loaded_state.party.characters[0]

        # Verify character loaded correctly with subclass = None
        assert loaded_character.name == "OldRogue"
        assert loaded_character.character_class == CharacterClass.ROGUE
        assert loaded_character.level == 3
        assert loaded_character.subclass is None  # Should default to None
        assert loaded_character.has_fast_hands() is False  # No Fast Hands without subclass
