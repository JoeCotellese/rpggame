# ABOUTME: Unit tests for visible items functionality in search and take commands
# ABOUTME: Tests visible/hidden item separation, fuzzy matching, and take all command

import pytest
from unittest.mock import Mock, patch, MagicMock

from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.utils.events import EventBus


@pytest.fixture
def sample_character():
    """Create a sample character for testing"""
    return Character(
        name="Test Fighter",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=Abilities(
            strength=15,
            dexterity=14,
            constitution=13,
            intelligence=10,
            wisdom=12,
            charisma=8
        ),
        max_hp=12,
        ac=16
    )


@pytest.fixture
def game_state_with_visible_items(sample_character):
    """Create game state with a room containing visible and hidden items"""
    party = Party([sample_character])
    event_bus = EventBus()

    # Mock the data loader
    with patch('dnd_engine.core.game_state.DataLoader') as mock_loader_class:
        mock_loader = Mock()
        mock_loader.load_dungeon.return_value = {
            "name": "Test Dungeon",
            "start_room": "entrance",
            "rooms": {
                "entrance": {
                    "name": "Entrance Hall",
                    "description": "A dusty entrance with broken vials on the floor.",
                    "exits": {},
                    "searchable": True,
                    "searched": False,
                    "items": [
                        {
                            "type": "item",
                            "id": "longsword",
                            "visible": True
                        },
                        {
                            "type": "item",
                            "id": "potion_of_healing",
                            "visible": False
                        },
                        {
                            "type": "currency",
                            "gold": 20,
                            "silver": 15,
                            "visible": True
                        },
                        {
                            "type": "item",
                            "id": "scroll_of_magic_missile",
                            "visible": False
                        }
                    ]
                }
            }
        }
        mock_loader.load_skills.return_value = {}
        mock_loader.load_items.return_value = {
            "weapons": {
                "longsword": {"name": "Longsword", "type": "martial weapon"}
            },
            "consumables": {
                "potion_of_healing": {"name": "Potion of Healing", "type": "potion"},
                "scroll_of_magic_missile": {"name": "Scroll of Magic Missile", "type": "scroll"}
            },
            "armor": {}
        }
        mock_loader_class.return_value = mock_loader

        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus
        )

    game_state.current_room_id = "entrance"
    return game_state


class TestVisibleItems:
    """Test visible items functionality"""

    def test_get_available_items_returns_visible_items_without_search(self, game_state_with_visible_items):
        """Test that visible items are available without searching"""
        available = game_state_with_visible_items.get_available_items_in_room()

        # Should return only visible items before searching
        assert len(available) == 2
        visible_ids = [item.get("id") for item in available if item.get("type") == "item"]
        assert "longsword" in visible_ids
        assert "potion_of_healing" not in visible_ids
        assert "scroll_of_magic_missile" not in visible_ids

    def test_get_available_items_returns_all_after_search(self, game_state_with_visible_items):
        """Test that all items are available after searching"""
        # Mark room as searched
        room = game_state_with_visible_items.get_current_room()
        room["searched"] = True

        available = game_state_with_visible_items.get_available_items_in_room()

        # Should return all items after searching
        assert len(available) == 4
        item_ids = [item.get("id") for item in available if item.get("type") == "item"]
        assert "longsword" in item_ids
        assert "potion_of_healing" in item_ids
        assert "scroll_of_magic_missile" in item_ids

    def test_search_room_separates_visible_and_hidden_items(self, game_state_with_visible_items):
        """Test that search_room returns separate visible and hidden item lists"""
        result = game_state_with_visible_items.search_room()

        assert result["success"] is True
        assert "visible_items" in result
        assert "hidden_items" in result

        # Check visible items
        visible_ids = [item.get("id") for item in result["visible_items"] if item.get("type") == "item"]
        assert "longsword" in visible_ids

        # Check hidden items
        hidden_ids = [item.get("id") for item in result["hidden_items"] if item.get("type") == "item"]
        assert "potion_of_healing" in hidden_ids
        assert "scroll_of_magic_missile" in hidden_ids

    def test_search_room_with_skill_check_reveals_hidden_items(self, game_state_with_visible_items, sample_character):
        """Test that successful skill check reveals hidden items"""
        # Add search_checks to the room
        room = game_state_with_visible_items.get_current_room()
        room["search_checks"] = [
            {
                "skill": "investigation",
                "dc": 10,
                "on_success": "You find hidden items!",
                "on_failure": "You find nothing hidden."
            }
        ]

        # Mock the skill check to succeed
        with patch.object(sample_character, 'make_skill_check') as mock_check:
            mock_check.return_value = {
                "success": True,
                "roll": 15,
                "modifier": 2,
                "total": 17
            }

            result = game_state_with_visible_items.search_room(sample_character)

            assert result["success"] is True
            assert len(result["hidden_items"]) == 2  # Two hidden items

    def test_search_room_failed_skill_check_only_shows_visible(self, game_state_with_visible_items, sample_character):
        """Test that failed skill check only reveals visible items"""
        # Add search_checks to the room
        room = game_state_with_visible_items.get_current_room()
        room["search_checks"] = [
            {
                "skill": "investigation",
                "dc": 20,
                "on_success": "You find hidden items!",
                "on_failure": "You find nothing hidden."
            }
        ]

        # Mock the skill check to fail
        with patch.object(sample_character, 'make_skill_check') as mock_check:
            mock_check.return_value = {
                "success": False,
                "roll": 5,
                "modifier": 0,
                "total": 5
            }

            result = game_state_with_visible_items.search_room(sample_character)

            assert result["success"] is False
            assert len(result["items"]) == 2  # Only visible items
            assert len(result["hidden_items"]) == 0  # No hidden items revealed


class TestFuzzyMatching:
    """Test fuzzy matching for item names"""

    def test_partial_name_match(self, game_state_with_visible_items):
        """Test that partial names match items"""
        # Mark room as searched so all items are available
        room = game_state_with_visible_items.get_current_room()
        room["searched"] = True

        available = game_state_with_visible_items.get_available_items_in_room()

        # Test partial match - "sword" should match "longsword"
        item_name = "sword"
        item_name_lower = item_name.lower()

        found = None
        for item in available:
            if item["type"] == "item":
                item_id = item.get("id", "").lower().replace("_", " ")
                if item_name_lower in item_id:
                    found = item
                    break

        assert found is not None
        assert found["id"] == "longsword"

    def test_case_insensitive_match(self, game_state_with_visible_items):
        """Test that item matching is case insensitive"""
        room = game_state_with_visible_items.get_current_room()
        room["searched"] = True

        available = game_state_with_visible_items.get_available_items_in_room()

        # Test case insensitive - "LONGSWORD" should match "longsword"
        item_name = "LONGSWORD"
        item_name_lower = item_name.lower()

        found = None
        for item in available:
            if item["type"] == "item":
                item_id = item.get("id", "").lower()
                if item_id == item_name_lower:
                    found = item
                    break

        assert found is not None
        assert found["id"] == "longsword"


class TestTakeItem:
    """Test taking items with visible field"""

    def test_take_visible_item_without_search(self, game_state_with_visible_items, sample_character):
        """Test that visible items can be taken without searching"""
        # Try to take a visible item without searching
        success = game_state_with_visible_items.take_item("longsword", sample_character)

        assert success is True
        assert "longsword" in sample_character.inventory.items

    def test_cannot_take_hidden_item_without_search(self, game_state_with_visible_items, sample_character):
        """Test that hidden items cannot be taken without searching"""
        # Try to take a hidden item without searching
        success = game_state_with_visible_items.take_item("potion_of_healing", sample_character)

        # Should fail because item is hidden and room not searched
        assert success is False

    def test_can_take_hidden_item_after_search(self, game_state_with_visible_items, sample_character):
        """Test that hidden items can be taken after searching"""
        # Search the room first
        game_state_with_visible_items.search_room()

        # Now try to take the hidden item
        success = game_state_with_visible_items.take_item("potion_of_healing", sample_character)

        assert success is True
        assert "potion_of_healing" in sample_character.inventory.items
