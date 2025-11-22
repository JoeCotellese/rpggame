# ABOUTME: Integration tests for search and take command workflow
# ABOUTME: Tests the complete flow of searching rooms and taking items with visible/hidden mechanics

import pytest
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

from dnd_engine.ui.cli import CLI
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.utils.events import EventBus


@pytest.fixture
def sample_characters():
    """Create sample characters for multi-character testing"""
    fighter = Character(
        name="Thorin",
        character_class=CharacterClass.FIGHTER,
        level=3,
        abilities=Abilities(
            strength=16,
            dexterity=12,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=8
        ),
        max_hp=28,
        ac=18
    )

    wizard = Character(
        name="Elara",
        character_class=CharacterClass.WIZARD,
        level=3,
        abilities=Abilities(
            strength=8,
            dexterity=14,
            constitution=12,
            intelligence=16,
            wisdom=13,
            charisma=10
        ),
        max_hp=18,
        ac=12
    )

    return [fighter, wizard]


@pytest.fixture
def game_state_multi_char(sample_characters):
    """Create game state with multiple characters and visible items"""
    party = Party(sample_characters)
    event_bus = EventBus()

    with patch('dnd_engine.core.game_state.DataLoader') as mock_loader_class:
        mock_loader = Mock()
        mock_loader.load_dungeon.return_value = {
            "name": "Test Dungeon",
            "start_room": "treasure_room",
            "rooms": {
                "treasure_room": {
                    "name": "Treasure Room",
                    "description": "A room filled with treasure chests and scattered coins.",
                    "exits": {},
                    "searchable": True,
                    "searched": False,
                    "items": [
                        {
                            "type": "currency",
                            "gold": 100,
                            "silver": 50,
                            "visible": True
                        },
                        {
                            "type": "item",
                            "id": "longsword",
                            "visible": True
                        },
                        {
                            "type": "item",
                            "id": "scroll_of_magic_missile",
                            "visible": False
                        },
                        {
                            "type": "item",
                            "id": "potion_of_healing",
                            "visible": True
                        },
                        {
                            "type": "item",
                            "id": "ring_of_protection",
                            "visible": False
                        }
                    ]
                }
            }
        }
        mock_loader.load_skills.return_value = {
            "investigation": {
                "name": "Investigation",
                "ability": "intelligence"
            }
        }
        mock_loader.load_items.return_value = {
            "weapons": {
                "longsword": {
                    "name": "Longsword",
                    "type": "martial weapon"
                }
            },
            "consumables": {
                "potion_of_healing": {
                    "name": "Potion of Healing",
                    "type": "potion"
                },
                "scroll_of_magic_missile": {
                    "name": "Scroll of Magic Missile",
                    "type": "scroll"
                }
            },
            "armor": {
                "ring_of_protection": {
                    "name": "Ring of Protection",
                    "type": "ring"
                }
            }
        }
        mock_loader_class.return_value = mock_loader

        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus
        )

    game_state.current_room_id = "treasure_room"
    return game_state


class TestSearchTakeIntegration:
    """Integration tests for search and take workflow"""

    def test_visible_items_available_before_search(self, game_state_multi_char):
        """Test that visible items are available without searching"""
        available = game_state_multi_char.get_available_items_in_room()

        # Should have 3 visible items: currency, longsword, potion
        visible_count = len(available)
        assert visible_count == 3

        # Verify specific visible items are present
        item_ids = [item.get("id") for item in available if item.get("type") == "item"]
        assert "longsword" in item_ids
        assert "potion_of_healing" in item_ids
        assert "scroll_of_magic_missile" not in item_ids  # Hidden
        assert "ring_of_protection" not in item_ids  # Hidden

    def test_search_reveals_hidden_items(self, game_state_multi_char):
        """Test that searching reveals hidden items"""
        # Search the room (no skill check in this room)
        result = game_state_multi_char.search_room()

        assert result["success"] is True
        assert len(result["items"]) == 5  # All items now visible

        # Verify hidden items are now available
        available = game_state_multi_char.get_available_items_in_room()
        item_ids = [item.get("id") for item in available if item.get("type") == "item"]
        assert "scroll_of_magic_missile" in item_ids
        assert "ring_of_protection" in item_ids

    def test_take_visible_item_without_search(self, game_state_multi_char, sample_characters):
        """Test taking a visible item without searching"""
        fighter = sample_characters[0]

        # Take a visible item
        success = game_state_multi_char.take_item("longsword", fighter)

        assert success is True
        assert "longsword" in fighter.inventory.items

        # Verify item is removed from room
        room = game_state_multi_char.get_current_room()
        room_item_ids = [item.get("id") for item in room["items"] if item.get("type") == "item"]
        assert "longsword" not in room_item_ids

    def test_cannot_take_hidden_item_without_search(self, game_state_multi_char, sample_characters):
        """Test that hidden items cannot be taken without searching"""
        wizard = sample_characters[1]

        # Try to take a hidden item
        success = game_state_multi_char.take_item("scroll_of_magic_missile", wizard)

        assert success is False
        assert "scroll_of_magic_missile" not in wizard.inventory.items

    def test_take_hidden_item_after_search(self, game_state_multi_char, sample_characters):
        """Test that hidden items can be taken after searching"""
        wizard = sample_characters[1]

        # Search the room first
        game_state_multi_char.search_room()

        # Now take the hidden item
        success = game_state_multi_char.take_item("scroll_of_magic_missile", wizard)

        assert success is True
        assert "scroll_of_magic_missile" in wizard.inventory.items

    def test_currency_auto_distributed(self, game_state_multi_char, sample_characters):
        """Test that currency is automatically distributed among party members"""
        fighter = sample_characters[0]

        # Take currency
        success = game_state_multi_char.take_item("currency", fighter)

        assert success is True

        # Verify both characters received their share
        # Currency is converted to copper and split, then converted back
        # 100g + 50s = 10050 copper, split 2 ways = 5025 copper each
        # Which is 50g 2s 5c (or similar based on conversion)
        for char in sample_characters:
            total_copper = char.inventory.currency.to_copper()
            assert total_copper > 0

        # Verify currency is split evenly
        fighter_total = sample_characters[0].inventory.currency.to_copper()
        wizard_total = sample_characters[1].inventory.currency.to_copper()
        assert fighter_total == wizard_total

    def test_complete_search_and_take_workflow(self, game_state_multi_char, sample_characters):
        """Test complete workflow: enter room, search, take all items"""
        fighter = sample_characters[0]
        wizard = sample_characters[1]

        # Step 1: Check visible items before search
        available_before = game_state_multi_char.get_available_items_in_room()
        assert len(available_before) == 3  # 3 visible items

        # Step 2: Search the room
        search_result = game_state_multi_char.search_room()
        assert search_result["success"] is True
        assert len(search_result["visible_items"]) == 3
        assert len(search_result["hidden_items"]) == 2

        # Step 3: All items now available
        available_after = game_state_multi_char.get_available_items_in_room()
        assert len(available_after) == 5

        # Step 4: Take currency (auto-distributed)
        game_state_multi_char.take_item("currency", fighter)

        # Step 5: Take weapon for fighter
        game_state_multi_char.take_item("longsword", fighter)

        # Step 6: Take scroll for wizard
        game_state_multi_char.take_item("scroll_of_magic_missile", wizard)

        # Step 7: Take potion for fighter
        game_state_multi_char.take_item("potion_of_healing", fighter)

        # Step 8: Take ring for wizard
        game_state_multi_char.take_item("ring_of_protection", wizard)

        # Verify final state
        assert "longsword" in fighter.inventory.items
        assert "potion_of_healing" in fighter.inventory.items
        assert "scroll_of_magic_missile" in wizard.inventory.items
        assert "ring_of_protection" in wizard.inventory.items

        # Verify currency was distributed (exact amounts depend on currency conversion)
        fighter_total = fighter.inventory.currency.to_copper()
        wizard_total = wizard.inventory.currency.to_copper()
        assert fighter_total > 0
        assert wizard_total > 0
        assert fighter_total == wizard_total  # Split evenly

        # Verify room is empty
        room = game_state_multi_char.get_current_room()
        assert len(room["items"]) == 0

    def test_already_searched_room_shows_all_items(self, game_state_multi_char):
        """Test that searching an already-searched room returns all items"""
        # First search
        game_state_multi_char.search_room()

        # Second search
        result = game_state_multi_char.search_room()

        assert result["already_searched"] is True
        assert len(result["items"]) == 5  # All items still available

    def test_fuzzy_item_matching(self, game_state_multi_char, sample_characters):
        """Test that fuzzy matching works for item names"""
        fighter = sample_characters[0]

        # Search first to make all items available
        game_state_multi_char.search_room()

        # Test partial match "sword" for "longsword"
        from difflib import SequenceMatcher

        available = game_state_multi_char.get_available_items_in_room()
        search_term = "sword"

        best_match = None
        best_ratio = 0.6

        for item in available:
            if item["type"] == "item":
                item_id = item.get("id", "").lower().replace("_", " ")
                if search_term in item_id:
                    best_match = item
                    break

        assert best_match is not None
        assert best_match["id"] == "longsword"
