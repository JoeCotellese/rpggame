# Test for item persistence across save/load cycles (Issue #166)

import tempfile
from pathlib import Path

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.core.save_slot_manager import SaveSlotManager
from dnd_engine.rules.loader import DataLoader


@pytest.fixture
def temp_saves_dir():
    """Create a temporary directory for saves."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "saves"


@pytest.fixture
def save_manager(temp_saves_dir):
    """Create a SaveSlotManager with temporary directory."""
    return SaveSlotManager(saves_dir=temp_saves_dir)


@pytest.fixture
def sample_character():
    """Create a sample character for testing."""
    abilities = Abilities(
        strength=16,
        dexterity=14,
        constitution=15,
        intelligence=8,
        wisdom=10,
        charisma=12
    )

    return Character(
        name="Test Hero",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=12,
        ac=16,
        current_hp=12,
        xp=0,
        race="Human"
    )


@pytest.fixture
def game_state_with_items(sample_character):
    """Create a game state with a room containing items."""
    party = Party([sample_character])
    data_loader = DataLoader()

    game_state = GameState(
        party=party,
        dungeon_name="test_dungeon",
        data_loader=data_loader
    )

    # Manually add items to the current room for testing
    room = game_state.get_current_room()
    room["items"] = [
        {"type": "currency", "gold": 100, "silver": 50, "copper": 10, "visible": True},
        {"type": "item", "id": "longsword", "visible": True},
        {"type": "item", "id": "potion_of_healing", "visible": True}
    ]

    return game_state


def test_items_persist_after_save_load(save_manager, game_state_with_items, sample_character):
    """Test that taken items do NOT respawn after save/load cycle (Issue #166)."""

    # Verify initial state - room has 3 items
    room = game_state_with_items.get_current_room()
    assert len(room["items"]) == 3

    # Take currency
    game_state_with_items.take_item("currency", sample_character)

    # Take longsword
    game_state_with_items.take_item("longsword", sample_character)

    # Verify items were removed
    room = game_state_with_items.get_current_room()
    assert len(room["items"]) == 1  # Only potion_of_healing remains
    remaining_item_ids = [item.get("id") for item in room["items"] if item.get("type") == "item"]
    assert "potion_of_healing" in remaining_item_ids
    assert "longsword" not in remaining_item_ids

    # Save the game
    save_manager.save_game(
        slot_number=1,
        game_state=game_state_with_items
    )

    # Load the game
    loaded_game_state = save_manager.load_game(
        slot_number=1,
        event_bus=game_state_with_items.event_bus,
        data_loader=game_state_with_items.data_loader,
        dice_roller=game_state_with_items.dice_roller
    )

    # Verify items are still gone after loading
    loaded_room = loaded_game_state.get_current_room()
    assert len(loaded_room["items"]) == 1  # Only potion_of_healing should remain

    loaded_item_ids = [item.get("id") for item in loaded_room["items"] if item.get("type") == "item"]
    assert "potion_of_healing" in loaded_item_ids
    assert "longsword" not in loaded_item_ids

    # Verify currency is not in room
    currency_items = [item for item in loaded_room["items"] if item.get("type") == "currency"]
    assert len(currency_items) == 0


def test_items_persist_across_multiple_save_load_cycles(save_manager, game_state_with_items, sample_character):
    """Test that items remain gone across multiple save/load cycles."""

    # Take all items one by one with saves in between
    room = game_state_with_items.get_current_room()
    initial_count = len(room["items"])
    assert initial_count == 3

    # Take currency and save
    game_state_with_items.take_item("currency", sample_character)
    save_manager.save_game(slot_number=2, game_state=game_state_with_items)

    # Load and verify
    loaded_gs = save_manager.load_game(
        slot_number=2,
        event_bus=game_state_with_items.event_bus,
        data_loader=game_state_with_items.data_loader,
        dice_roller=game_state_with_items.dice_roller
    )
    assert len(loaded_gs.get_current_room()["items"]) == 2

    # Take longsword and save
    loaded_gs.take_item("longsword", sample_character)
    save_manager.save_game(slot_number=2, game_state=loaded_gs)

    # Load and verify
    loaded_gs2 = save_manager.load_game(
        slot_number=2,
        event_bus=game_state_with_items.event_bus,
        data_loader=game_state_with_items.data_loader,
        dice_roller=game_state_with_items.dice_roller
    )
    assert len(loaded_gs2.get_current_room()["items"]) == 1

    # Take potion and save
    loaded_gs2.take_item("potion_of_healing", sample_character)
    save_manager.save_game(slot_number=2, game_state=loaded_gs2)

    # Final load and verify - room should be completely empty
    final_gs = save_manager.load_game(
        slot_number=2,
        event_bus=game_state_with_items.event_bus,
        data_loader=game_state_with_items.data_loader,
        dice_roller=game_state_with_items.dice_roller
    )
    assert len(final_gs.get_current_room()["items"]) == 0


def test_searched_flag_and_items_both_persist(save_manager, game_state_with_items, sample_character):
    """Test that both searched flag and items state persist together."""

    room = game_state_with_items.get_current_room()
    room["searchable"] = True
    room["searched"] = False

    # Search the room
    game_state_with_items.search_room()
    assert room["searched"] is True

    # Take an item
    game_state_with_items.take_item("longsword", sample_character)

    # Save
    save_manager.save_game(slot_number=3, game_state=game_state_with_items)

    # Load
    loaded_gs = save_manager.load_game(
        slot_number=3,
        event_bus=game_state_with_items.event_bus,
        data_loader=game_state_with_items.data_loader,
        dice_roller=game_state_with_items.dice_roller
    )

    loaded_room = loaded_gs.get_current_room()

    # Verify both searched flag AND item removal persisted
    assert loaded_room["searched"] is True
    assert len(loaded_room["items"]) == 2  # Currency and potion remain

    loaded_item_ids = [item.get("id") for item in loaded_room["items"] if item.get("type") == "item"]
    assert "longsword" not in loaded_item_ids
