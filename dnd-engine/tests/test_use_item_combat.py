# ABOUTME: Unit tests for GameState.use_item_combat() method
# ABOUTME: Tests consumable item use during combat with action economy validation

from unittest.mock import Mock, patch

import pytest

from dnd_engine.core.character import Character
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.systems.action_economy import ActionType, TurnState


class TestUseItemCombat:
    """Test GameState.use_item_combat() method"""

    @pytest.fixture
    def mock_data_loader(self):
        """Create a mock data loader with potion data"""
        from pathlib import Path

        loader = Mock()
        loader.load_items.return_value = {
            "consumables": {
                "potion_of_healing": {
                    "name": "Potion of Healing",
                    "effect_type": "healing",
                    "healing": "2d4+2",
                    "action_required": "action",
                },
                "antitoxin": {
                    "name": "Antitoxin",
                    "effect_type": "buff",
                    "action_required": "bonus_action",
                },
            }
        }
        # Mock dungeon loading
        loader.load_dungeon.return_value = {
            "name": "Test Dungeon",
            "rooms": {},
            "start_room": "entrance",
        }
        # Mock data_path for room registry (return non-existent path to skip)
        loader.data_path = Path("/nonexistent")
        return loader

    @pytest.fixture
    def character_with_potion(self):
        """Create a character with a potion in inventory"""
        abilities = Abilities(
            strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10
        )
        character = Character(
            name="TestHero",
            character_class="fighter",
            level=1,
            abilities=abilities,
            max_hp=20,
            ac=14,
            current_hp=10,  # Damaged
        )
        character.inventory.add_item("potion_of_healing", "consumables", quantity=1)
        return character

    @pytest.fixture
    def turn_state_with_action(self):
        """Create a turn state with action available"""
        turn_state = TurnState()
        turn_state.action_available = True
        turn_state.bonus_action_available = True
        return turn_state

    @pytest.fixture
    def turn_state_no_action(self):
        """Create a turn state with no action available"""
        turn_state = TurnState()
        turn_state.action_available = False
        turn_state.bonus_action_available = True
        return turn_state

    def test_successful_item_use_healing(
        self, mock_data_loader, character_with_potion, turn_state_with_action
    ):
        """Test successfully using a healing potion during combat"""
        # Setup game state
        game_state = Mock(spec=GameState)
        game_state.data_loader = mock_data_loader
        game_state.initiative_tracker = Mock()
        game_state.initiative_tracker.get_current_turn_state.return_value = turn_state_with_action
        game_state.dice_roller = Mock()
        game_state.event_bus = Mock()
        game_state.time_manager = Mock()

        # Call the actual method (need to use the real implementation)
        with patch("dnd_engine.systems.item_effects.apply_item_effect") as mock_apply:
            mock_effect_result = Mock()
            mock_effect_result.success = True
            mock_effect_result.effect_type = "healing"
            mock_effect_result.message = "You heal 8 HP"
            mock_effect_result.amount = 8
            mock_apply.return_value = mock_effect_result

            # Call the real method on a real GameState
            party = Party()
            party.add_character(character_with_potion)
            real_game_state = GameState(
                party=party, dungeon_name="test_dungeon", data_loader=mock_data_loader
            )
            real_game_state.initiative_tracker = Mock()
            real_game_state.initiative_tracker.get_current_turn_state.return_value = (
                turn_state_with_action
            )

            hp_before = character_with_potion.current_hp

            result = real_game_state.use_item_combat(
                user=character_with_potion,
                item_id="potion_of_healing",
                target=character_with_potion,
            )

            assert result.success is True
            assert result.item_name == "Potion of Healing"
            assert result.action_type == ActionType.ACTION
            assert result.user_name == "TestHero"
            assert result.target_name == "TestHero"
            assert result.effect_type == "healing"
            assert result.hp_before == hp_before

    def test_item_not_found(self, mock_data_loader, character_with_potion, turn_state_with_action):
        """Test using an item that doesn't exist in data"""
        party = Party()
        party.add_character(character_with_potion)
        game_state = GameState(
            party=party, dungeon_name="test_dungeon", data_loader=mock_data_loader
        )
        game_state.initiative_tracker = Mock()
        game_state.initiative_tracker.get_current_turn_state.return_value = turn_state_with_action

        result = game_state.use_item_combat(
            user=character_with_potion, item_id="nonexistent_potion", target=character_with_potion
        )

        assert result.success is False
        assert "not found" in result.error_message.lower()

    def test_no_action_available(
        self, mock_data_loader, character_with_potion, turn_state_no_action
    ):
        """Test that item use fails when no action is available"""
        party = Party()
        party.add_character(character_with_potion)
        game_state = GameState(
            party=party, dungeon_name="test_dungeon", data_loader=mock_data_loader
        )
        game_state.initiative_tracker = Mock()
        game_state.initiative_tracker.get_current_turn_state.return_value = turn_state_no_action

        result = game_state.use_item_combat(
            user=character_with_potion, item_id="potion_of_healing", target=character_with_potion
        )

        assert result.success is False
        assert "available" in result.error_message.lower()
        # Potion should still be in inventory
        assert character_with_potion.inventory.has_item("potion_of_healing")

    def test_item_not_in_inventory(self, mock_data_loader, turn_state_with_action):
        """Test using an item that's not in the character's inventory"""
        abilities = Abilities(
            strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10
        )
        character = Character(
            name="EmptyHero",
            character_class="fighter",
            level=1,
            abilities=abilities,
            max_hp=20,
            ac=14,
        )
        # No potion in inventory

        party = Party()
        party.add_character(character)
        game_state = GameState(
            party=party, dungeon_name="test_dungeon", data_loader=mock_data_loader
        )
        game_state.initiative_tracker = Mock()
        game_state.initiative_tracker.get_current_turn_state.return_value = turn_state_with_action

        result = game_state.use_item_combat(
            user=character, item_id="potion_of_healing", target=character
        )

        assert result.success is False
        assert "inventory" in result.error_message.lower()

    def test_action_consumed_on_success(
        self, mock_data_loader, character_with_potion, turn_state_with_action
    ):
        """Test that action is consumed when item is successfully used"""
        party = Party()
        party.add_character(character_with_potion)
        game_state = GameState(
            party=party, dungeon_name="test_dungeon", data_loader=mock_data_loader
        )
        game_state.initiative_tracker = Mock()
        game_state.initiative_tracker.get_current_turn_state.return_value = turn_state_with_action

        with patch("dnd_engine.systems.item_effects.apply_item_effect") as mock_apply:
            mock_effect_result = Mock()
            mock_effect_result.success = True
            mock_effect_result.effect_type = "healing"
            mock_effect_result.message = "You heal 8 HP"
            mock_effect_result.amount = 8
            mock_apply.return_value = mock_effect_result

            result = game_state.use_item_combat(
                user=character_with_potion,
                item_id="potion_of_healing",
                target=character_with_potion,
            )

            assert result.success is True
            # Action should have been consumed
            assert turn_state_with_action.action_available is False

    def test_bonus_action_item(self, mock_data_loader, turn_state_with_action):
        """Test using an item that requires a bonus action"""
        abilities = Abilities(
            strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10
        )
        character = Character(
            name="TestHero",
            character_class="fighter",
            level=1,
            abilities=abilities,
            max_hp=20,
            ac=14,
        )
        character.inventory.add_item("antitoxin", "consumables", quantity=1)

        party = Party()
        party.add_character(character)
        game_state = GameState(
            party=party, dungeon_name="test_dungeon", data_loader=mock_data_loader
        )
        game_state.initiative_tracker = Mock()
        game_state.initiative_tracker.get_current_turn_state.return_value = turn_state_with_action

        with patch("dnd_engine.systems.item_effects.apply_item_effect") as mock_apply:
            mock_effect_result = Mock()
            mock_effect_result.success = True
            mock_effect_result.effect_type = "buff"
            mock_effect_result.message = "You gain advantage on poison saves"
            mock_effect_result.amount = 0
            mock_apply.return_value = mock_effect_result

            result = game_state.use_item_combat(
                user=character, item_id="antitoxin", target=character
            )

            assert result.success is True
            assert result.action_type == ActionType.BONUS_ACTION
            # Bonus action should have been consumed
            assert turn_state_with_action.bonus_action_available is False
            # Regular action should still be available
            assert turn_state_with_action.action_available is True

    def test_item_used_event_emitted(
        self, mock_data_loader, character_with_potion, turn_state_with_action
    ):
        """Test that ITEM_USED event is emitted on successful use"""
        party = Party()
        party.add_character(character_with_potion)
        game_state = GameState(
            party=party, dungeon_name="test_dungeon", data_loader=mock_data_loader
        )
        game_state.initiative_tracker = Mock()
        game_state.initiative_tracker.get_current_turn_state.return_value = turn_state_with_action

        with patch("dnd_engine.systems.item_effects.apply_item_effect") as mock_apply:
            mock_effect_result = Mock()
            mock_effect_result.success = True
            mock_effect_result.effect_type = "healing"
            mock_effect_result.message = "You heal 8 HP"
            mock_effect_result.amount = 8
            mock_apply.return_value = mock_effect_result

            # Track emitted events
            emitted_events = []
            game_state.event_bus.emit = lambda e: emitted_events.append(e)

            result = game_state.use_item_combat(
                user=character_with_potion,
                item_id="potion_of_healing",
                target=character_with_potion,
            )

            assert result.success is True
            assert len(emitted_events) == 1
            event = emitted_events[0]
            assert event.data["item_name"] == "Potion of Healing"
            assert event.data["effect_type"] == "healing"

    def test_use_on_different_target(
        self, mock_data_loader, character_with_potion, turn_state_with_action
    ):
        """Test using a potion on a different character"""
        # Create a second character as target
        abilities = Abilities(
            strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10
        )
        target_character = Character(
            name="WoundedAlly",
            character_class="wizard",
            level=1,
            abilities=abilities,
            max_hp=15,
            ac=12,
            current_hp=5,  # Very damaged
        )

        party = Party()
        party.add_character(character_with_potion)
        party.add_character(target_character)
        game_state = GameState(
            party=party, dungeon_name="test_dungeon", data_loader=mock_data_loader
        )
        game_state.initiative_tracker = Mock()
        game_state.initiative_tracker.get_current_turn_state.return_value = turn_state_with_action

        with patch("dnd_engine.systems.item_effects.apply_item_effect") as mock_apply:
            mock_effect_result = Mock()
            mock_effect_result.success = True
            mock_effect_result.effect_type = "healing"
            mock_effect_result.message = "WoundedAlly heals 8 HP"
            mock_effect_result.amount = 8
            mock_apply.return_value = mock_effect_result

            result = game_state.use_item_combat(
                user=character_with_potion, item_id="potion_of_healing", target=target_character
            )

            assert result.success is True
            assert result.user_name == "TestHero"
            assert result.target_name == "WoundedAlly"
            assert result.hp_before == 5
            # Item should be removed from user's inventory
            assert not character_with_potion.inventory.has_item("potion_of_healing")

    def test_no_turn_state_returns_error(self, mock_data_loader, character_with_potion):
        """Test that missing turn state returns an error"""
        party = Party()
        party.add_character(character_with_potion)
        game_state = GameState(
            party=party, dungeon_name="test_dungeon", data_loader=mock_data_loader
        )
        game_state.initiative_tracker = Mock()
        game_state.initiative_tracker.get_current_turn_state.return_value = None

        result = game_state.use_item_combat(
            user=character_with_potion, item_id="potion_of_healing", target=character_with_potion
        )

        assert result.success is False
        assert "turn state" in result.error_message.lower()
        # Potion should still be in inventory
        assert character_with_potion.inventory.has_item("potion_of_healing")
