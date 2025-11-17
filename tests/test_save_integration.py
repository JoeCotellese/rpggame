# ABOUTME: Integration tests for save/load functionality
# ABOUTME: Tests full save/load cycles and game flow with persistence

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from dnd_engine.core.save_manager import SaveManager
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.party import Party
from dnd_engine.core.game_state import GameState
from dnd_engine.systems.inventory import EquipmentSlot
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus


@pytest.fixture
def temp_saves_dir():
    """Create a temporary directory for save files."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def save_manager(temp_saves_dir):
    """Create a SaveManager with temporary directory."""
    return SaveManager(saves_dir=temp_saves_dir)


@pytest.fixture
def data_loader():
    """Create a DataLoader instance."""
    return DataLoader()


def create_test_party():
    """Create a test party with multiple characters."""
    abilities1 = Abilities(
        strength=16, dexterity=14, constitution=15,
        intelligence=10, wisdom=12, charisma=8
    )

    char1 = Character(
        name="Fighter", character_class=CharacterClass.FIGHTER,
        level=2, abilities=abilities1, max_hp=20, ac=16,
        current_hp=20, xp=300, race="human"
    )
    char1.inventory.add_item("longsword", "weapons", 1)
    char1.inventory.equip_item("longsword", EquipmentSlot.WEAPON)
    char1.inventory.add_gold(100)

    abilities2 = Abilities(
        strength=14, dexterity=16, constitution=14,
        intelligence=12, wisdom=13, charisma=10
    )

    char2 = Character(
        name="Scout", character_class=CharacterClass.FIGHTER,
        level=1, abilities=abilities2, max_hp=12, ac=15,
        current_hp=8, xp=50, race="high_elf"
    )
    char2.inventory.add_item("shortsword", "weapons", 1)
    char2.inventory.add_item("potion_healing", "consumables", 3)
    char2.inventory.equip_item("shortsword", EquipmentSlot.WEAPON)
    char2.inventory.add_gold(75)

    return Party(characters=[char1, char2])


class TestSaveLoadIntegration:
    """Integration tests for save/load functionality."""

    def test_full_save_load_cycle(self, save_manager, data_loader):
        """Test a complete save and load cycle."""
        # Create game state
        party = create_test_party()
        event_bus = EventBus()

        game_state = GameState(
            party=party,
            dungeon_name="goblin_warren",
            event_bus=event_bus,
            data_loader=data_loader
        )

        # Save the game
        save_path = save_manager.save_game(game_state, "integration_test")
        assert save_path.exists()

        # Load the game
        loaded_state = save_manager.load_game(
            "integration_test",
            event_bus=EventBus(),
            data_loader=DataLoader()
        )

        # Verify all data was preserved
        assert len(loaded_state.party.characters) == 2
        assert loaded_state.party.characters[0].name == "Fighter"
        assert loaded_state.party.characters[1].name == "Scout"
        assert loaded_state.dungeon_name == "goblin_warren"
        assert loaded_state.dungeon["name"] == "Goblin Warren"

    def test_save_after_combat(self, save_manager, data_loader):
        """Test saving after a combat encounter."""
        # Create game state
        party = create_test_party()
        game_state = GameState(
            party=party,
            dungeon_name="goblin_warren",
            event_bus=EventBus(),
            data_loader=data_loader
        )

        # Simulate combat damage
        game_state.party.characters[0].take_damage(5)
        game_state.party.characters[1].take_damage(3)

        # Add action history
        game_state.action_history.append("Fought goblins in the entrance")

        # Save the game
        save_manager.save_game(game_state, "after_combat")

        # Load the game
        loaded_state = save_manager.load_game("after_combat")

        # Verify damage was saved
        assert loaded_state.party.characters[0].current_hp == 15
        assert loaded_state.party.characters[1].current_hp == 5

        # Verify action history was saved
        assert "Fought goblins in the entrance" in loaded_state.action_history

    def test_save_after_room_progression(self, save_manager, data_loader):
        """Test saving after moving between rooms."""
        # Create game state
        party = create_test_party()
        game_state = GameState(
            party=party,
            dungeon_name="goblin_warren",
            event_bus=EventBus(),
            data_loader=data_loader
        )

        # Get initial room
        initial_room = game_state.current_room_id

        # Move to another room (if possible)
        current_room = game_state.get_current_room()
        exits = current_room.get("exits", {})

        if exits:
            # Move to first available exit
            direction = list(exits.keys())[0]
            game_state.move(direction)

            # Verify we moved
            assert game_state.current_room_id != initial_room

            # Save the game
            save_manager.save_game(game_state, "after_move")

            # Load the game
            loaded_state = save_manager.load_game("after_move")

            # Verify room position was saved
            assert loaded_state.current_room_id == game_state.current_room_id
            assert loaded_state.current_room_id != initial_room

    def test_save_with_items_acquired(self, save_manager, data_loader):
        """Test saving after acquiring items from searching."""
        # Create game state
        party = create_test_party()
        game_state = GameState(
            party=party,
            dungeon_name="goblin_warren",
            event_bus=EventBus(),
            data_loader=data_loader
        )

        # Record initial gold
        initial_gold = game_state.party.characters[0].inventory.gold

        # Manually mark room as searchable and add items
        current_room = game_state.get_current_room()
        current_room["searchable"] = True
        current_room["items"] = [{"type": "gold", "amount": 50}]

        # Search the room
        items_found = game_state.search_room()

        # Save the game
        save_manager.save_game(game_state, "after_search")

        # Load the game
        loaded_state = save_manager.load_game("after_search")

        # Verify searched state was saved
        loaded_room = loaded_state.get_current_room()
        assert loaded_room.get("searched") is True

        # Verify items/gold were saved
        assert len(items_found) > 0
        # Gold should have increased
        assert loaded_state.party.characters[0].inventory.gold > initial_gold

    def test_multiple_saves_different_names(self, save_manager, data_loader):
        """Test creating multiple save files with different names."""
        party = create_test_party()

        # Create multiple game states at different points
        game_state1 = GameState(
            party=party,
            dungeon_name="goblin_warren",
            event_bus=EventBus(),
            data_loader=data_loader
        )
        game_state1.party.characters[0].current_hp = 15

        # Save first state
        save_manager.save_game(game_state1, "save1")

        # Modify and save second state
        game_state1.party.characters[0].current_hp = 10
        save_manager.save_game(game_state1, "save2")

        # Load both saves
        loaded1 = save_manager.load_game("save1")
        loaded2 = save_manager.load_game("save2")

        # Verify they have different states
        assert loaded1.party.characters[0].current_hp == 15
        assert loaded2.party.characters[0].current_hp == 10

    def test_save_list_and_load_workflow(self, save_manager, data_loader):
        """Test the full workflow: save, list, select, load."""
        party = create_test_party()

        # Create multiple saves
        for i in range(3):
            game_state = GameState(
                party=party,
                dungeon_name="goblin_warren",
                event_bus=EventBus(),
                data_loader=data_loader
            )
            game_state.party.characters[0].current_hp = 20 - (i * 5)
            save_manager.save_game(game_state, f"save_{i}")

        # List saves
        saves = save_manager.list_saves()
        assert len(saves) == 3

        # Verify metadata
        for save in saves:
            assert "name" in save
            assert "party_names" in save
            assert save["party_size"] == 2
            assert "Fighter" in save["party_names"]
            assert "Scout" in save["party_names"]

        # Load specific save
        loaded = save_manager.load_game("save_1")
        assert loaded.party.characters[0].current_hp == 15

    def test_character_death_persists(self, save_manager, data_loader):
        """Test that character death state is correctly saved and loaded."""
        party = create_test_party()
        game_state = GameState(
            party=party,
            dungeon_name="goblin_warren",
            event_bus=EventBus(),
            data_loader=data_loader
        )

        # Kill second character
        game_state.party.characters[1].take_damage(100)
        assert not game_state.party.characters[1].is_alive

        # Save and load
        save_manager.save_game(game_state, "death_test")
        loaded_state = save_manager.load_game("death_test")

        # Verify death persisted
        assert not loaded_state.party.characters[1].is_alive
        assert loaded_state.party.characters[1].current_hp == 0

    def test_xp_and_level_persist(self, save_manager, data_loader):
        """Test that XP and level changes are saved."""
        party = create_test_party()
        game_state = GameState(
            party=party,
            dungeon_name="goblin_warren",
            event_bus=EventBus(),
            data_loader=data_loader
        )

        # Gain XP
        game_state.party.characters[0].gain_xp(200)
        initial_xp = game_state.party.characters[0].xp

        # Save and load
        save_manager.save_game(game_state, "xp_test")
        loaded_state = save_manager.load_game("xp_test")

        # Verify XP persisted
        assert loaded_state.party.characters[0].xp == initial_xp

    def test_conditions_persist(self, save_manager, data_loader):
        """Test that character conditions are saved and loaded."""
        party = create_test_party()
        game_state = GameState(
            party=party,
            dungeon_name="goblin_warren",
            event_bus=EventBus(),
            data_loader=data_loader
        )

        # Add conditions
        game_state.party.characters[0].add_condition("prone")
        game_state.party.characters[0].add_condition("blessed")

        # Save and load
        save_manager.save_game(game_state, "condition_test")
        loaded_state = save_manager.load_game("condition_test")

        # Verify conditions persisted
        assert loaded_state.party.characters[0].has_condition("prone")
        assert loaded_state.party.characters[0].has_condition("blessed")


class TestEndToEnd:
    """End-to-end tests simulating real gameplay scenarios."""

    def test_complete_gameplay_session(self, save_manager, data_loader):
        """Simulate a complete gameplay session with multiple actions."""
        # Start new game
        party = create_test_party()
        game_state = GameState(
            party=party,
            dungeon_name="goblin_warren",
            event_bus=EventBus(),
            data_loader=data_loader
        )

        # Action 1: Search the starting room (make it searchable first)
        current_room = game_state.get_current_room()
        current_room["searchable"] = True
        current_room["items"] = []
        game_state.search_room()

        # Action 2: Take some damage (simulate combat)
        game_state.party.characters[0].take_damage(5)

        # Action 3: Gain XP
        game_state.party.characters[0].gain_xp(50)
        game_state.party.characters[1].gain_xp(50)

        # Action 4: Use a healing potion (simulate)
        game_state.party.characters[1].heal(4)

        # Save the game
        save_manager.save_game(game_state, "session_save")

        # Simulate quitting and restarting
        del game_state

        # Load the saved game
        loaded_state = save_manager.load_game("session_save")

        # Verify all actions persisted
        assert loaded_state.get_current_room().get("searched") is True
        assert loaded_state.party.characters[0].current_hp == 15  # 20 - 5
        assert loaded_state.party.characters[0].xp == 350  # 300 + 50
        assert loaded_state.party.characters[1].xp == 100  # 50 + 50
        assert loaded_state.party.characters[1].current_hp == 12  # Was 8, healed 4

        # Continue playing from loaded state
        loaded_state.party.characters[0].gain_xp(100)

        # Save again with different name
        save_manager.save_game(loaded_state, "session_save_2")

        # Verify we can load the continued session
        final_state = save_manager.load_game("session_save_2")
        assert final_state.party.characters[0].xp == 450  # 350 + 100

    def test_autosave_scenario(self, save_manager, data_loader):
        """Test auto-save scenario (save with same name repeatedly)."""
        party = create_test_party()
        game_state = GameState(
            party=party,
            dungeon_name="goblin_warren",
            event_bus=EventBus(),
            data_loader=data_loader
        )

        # Simulate auto-saves at different points
        save_manager.save_game(game_state, "autosave", auto_save=True)

        # Make progress
        game_state.party.characters[0].take_damage(5)

        # Auto-save again (overwrites previous)
        save_manager.save_game(game_state, "autosave", auto_save=True)

        # Make more progress
        game_state.party.characters[0].gain_xp(100)

        # Auto-save again
        save_manager.save_game(game_state, "autosave", auto_save=True)

        # Load the auto-save
        loaded_state = save_manager.load_game("autosave")

        # Should have the latest state
        assert loaded_state.party.characters[0].current_hp == 15
        assert loaded_state.party.characters[0].xp == 400

    def test_save_corruption_recovery(self, save_manager, data_loader, temp_saves_dir):
        """Test graceful handling of corrupted save files."""
        party = create_test_party()
        game_state = GameState(
            party=party,
            dungeon_name="goblin_warren",
            event_bus=EventBus(),
            data_loader=data_loader
        )

        # Create a good save
        save_manager.save_game(game_state, "good_save")

        # Create a corrupted save
        corrupt_path = temp_saves_dir / "corrupt_save.json"
        with open(corrupt_path, 'w') as f:
            f.write("{invalid json content")

        # List saves should skip corrupted file
        saves = save_manager.list_saves()
        save_names = [s["name"] for s in saves]
        assert "good_save" in save_names
        assert "corrupt_save" not in save_names

        # Loading good save should still work
        loaded_state = save_manager.load_game("good_save")
        assert loaded_state.party.characters[0].name == "Fighter"

    def test_inventory_management_persists(self, save_manager, data_loader):
        """Test that inventory operations persist correctly."""
        party = create_test_party()
        game_state = GameState(
            party=party,
            dungeon_name="goblin_warren",
            event_bus=EventBus(),
            data_loader=data_loader
        )

        char = game_state.party.characters[0]

        # Add items
        char.inventory.add_item("potion_healing", "consumables", 5)

        # Equip/unequip
        char.inventory.unequip_item(EquipmentSlot.WEAPON)

        # Add/remove gold
        char.inventory.add_gold(50)
        char.inventory.remove_gold(25)

        # Save and load
        save_manager.save_game(game_state, "inventory_test")
        loaded_state = save_manager.load_game("inventory_test")

        loaded_char = loaded_state.party.characters[0]

        # Verify inventory changes persisted
        assert loaded_char.inventory.has_item("potion_healing")
        assert loaded_char.inventory.get_item_quantity("potion_healing") == 5
        assert loaded_char.inventory.get_equipped_item(EquipmentSlot.WEAPON) is None
        assert loaded_char.inventory.gold == 125  # 100 + 50 - 25
