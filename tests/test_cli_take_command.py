# ABOUTME: Unit tests for CLI take command with arrow key navigation
# ABOUTME: Tests the _prompt_item_to_take functionality and cancel handling

import pytest
from unittest.mock import Mock, patch, MagicMock
from dnd_engine.ui.cli import CLI
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.party import Party
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.utils.events import EventBus


class TestCLITakeCommand:
    """Test CLI take command with arrow key navigation"""

    @pytest.fixture
    def abilities(self):
        """Create test abilities"""
        return Abilities(16, 14, 15, 10, 12, 8)

    @pytest.fixture
    def character(self, abilities):
        """Create a test character"""
        return Character(
            name="Gandalf",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=20,
            ac=16
        )

    @pytest.fixture
    def party(self, character):
        """Create a party with one character"""
        return Party([character])

    @pytest.fixture
    def game_state(self, party):
        """Create a mock game state"""
        game_state = Mock(spec=GameState)
        game_state.party = party
        game_state.event_bus = Mock(spec=EventBus)
        game_state.data_loader = Mock()
        game_state.data_loader.load_items.return_value = {
            "consumables": {
                "potion_of_healing": {"name": "Potion of Healing", "effect_type": "healing", "healing": "2d4+2"}
            }
        }
        return game_state

    @pytest.fixture
    def cli(self, game_state):
        """Create a CLI instance"""
        return CLI(game_state, auto_save_enabled=False)

    def test_prompt_item_to_take_with_regular_item(self, cli, game_state):
        """Test selecting a regular item from the room"""
        # Mock available items
        game_state.get_available_items_in_room.return_value = [
            {"type": "item", "id": "potion_of_healing"}
        ]

        with patch('questionary.select') as mock_select:
            # Mock user selecting the potion
            mock_result = MagicMock()
            mock_result.ask.return_value = {"type": "item", "id": "potion_of_healing"}
            mock_select.return_value = mock_result

            result = cli._prompt_item_to_take()

            # Should return the item dict
            assert result == {"type": "item", "id": "potion_of_healing"}
            assert mock_select.called

    def test_prompt_item_to_take_with_currency(self, cli, game_state):
        """Test selecting currency from the room"""
        # Mock available items with currency
        game_state.get_available_items_in_room.return_value = [
            {"type": "currency", "gold": 30, "silver": 20}
        ]

        with patch('questionary.select') as mock_select:
            # Mock user selecting currency
            mock_result = MagicMock()
            mock_result.ask.return_value = {"type": "currency", "gold": 30, "silver": 20}
            mock_select.return_value = mock_result

            result = cli._prompt_item_to_take()

            # Should return the currency dict
            assert result["type"] == "currency"
            assert result["gold"] == 30
            assert result["silver"] == 20

    def test_prompt_item_to_take_with_gold(self, cli, game_state):
        """Test selecting gold from the room"""
        # Mock available items with gold
        game_state.get_available_items_in_room.return_value = [
            {"type": "gold", "amount": 50}
        ]

        with patch('questionary.select') as mock_select:
            # Mock user selecting gold
            mock_result = MagicMock()
            mock_result.ask.return_value = {"type": "gold", "amount": 50}
            mock_select.return_value = mock_result

            result = cli._prompt_item_to_take()

            # Should return the gold dict
            assert result["type"] == "gold"
            assert result["amount"] == 50

    def test_prompt_item_to_take_cancel(self, cli, game_state):
        """Test cancelling item selection"""
        # Mock available items
        game_state.get_available_items_in_room.return_value = [
            {"type": "item", "id": "potion_of_healing"}
        ]

        with patch('questionary.select') as mock_select:
            # Mock user selecting Cancel - questionary returns the string "Cancel" when value=None
            mock_result = MagicMock()
            mock_result.ask.return_value = "Cancel"
            mock_select.return_value = mock_result

            result = cli._prompt_item_to_take()

            # When user cancels, questionary.ask() can return "Cancel" string
            # The calling code should handle this
            assert result == "Cancel"

    def test_prompt_item_to_take_keyboard_interrupt(self, cli, game_state):
        """Test keyboard interrupt during selection"""
        # Mock available items
        game_state.get_available_items_in_room.return_value = [
            {"type": "item", "id": "potion_of_healing"}
        ]

        with patch('questionary.select') as mock_select:
            # Mock keyboard interrupt
            mock_result = MagicMock()
            mock_result.ask.side_effect = KeyboardInterrupt()
            mock_select.return_value = mock_result

            result = cli._prompt_item_to_take()

            # Should return None on interrupt
            assert result is None

    def test_prompt_item_to_take_no_items(self, cli, game_state):
        """Test when there are no items in the room"""
        # Mock no available items
        game_state.get_available_items_in_room.return_value = []

        # Mock current room
        game_state.get_current_room.return_value = {
            "searchable": False,
            "searched": False
        }

        with patch('dnd_engine.ui.cli.print_error') as mock_error:
            result = cli._prompt_item_to_take()

            # Should return None and print error
            assert result is None
            mock_error.assert_called()

    @patch('dnd_engine.ui.cli.print_error')
    def test_process_exploration_command_take_handles_cancel(self, mock_error, cli, game_state):
        """Test that 'take' command handles cancel correctly (regression test for bug)"""
        # Mock available items
        game_state.get_available_items_in_room.return_value = [
            {"type": "item", "id": "potion_of_healing"}
        ]

        with patch('questionary.select') as mock_select:
            # Mock user cancelling - returns "Cancel" string
            mock_result = MagicMock()
            mock_result.ask.return_value = "Cancel"
            mock_select.return_value = mock_result

            # This should not crash
            cli.process_exploration_command("take")

            # Should not call handle_take or show errors
            mock_error.assert_not_called()

    @patch('dnd_engine.ui.cli.CLI.handle_take')
    def test_process_exploration_command_take_with_currency(self, mock_handle_take, cli, game_state):
        """Test that 'take' command passes 'currency' for currency items (regression test for bug)"""
        # Mock available items with currency
        game_state.get_available_items_in_room.return_value = [
            {"type": "currency", "gold": 30, "silver": 20}
        ]

        with patch('questionary.select') as mock_select:
            # Mock user selecting currency
            mock_result = MagicMock()
            mock_result.ask.return_value = {"type": "currency", "gold": 30, "silver": 20}
            mock_select.return_value = mock_result

            cli.process_exploration_command("take")

            # Should call handle_take with "currency" as the item name
            mock_handle_take.assert_called_once_with("currency")

    @patch('dnd_engine.ui.cli.CLI.handle_take')
    def test_process_exploration_command_take_with_regular_item(self, mock_handle_take, cli, game_state):
        """Test that 'take' command passes item ID for regular items"""
        # Mock available items
        game_state.get_available_items_in_room.return_value = [
            {"type": "item", "id": "potion_of_healing"}
        ]

        with patch('questionary.select') as mock_select:
            # Mock user selecting item
            mock_result = MagicMock()
            mock_result.ask.return_value = {"type": "item", "id": "potion_of_healing"}
            mock_select.return_value = mock_result

            cli.process_exploration_command("take")

            # Should call handle_take with the item ID
            mock_handle_take.assert_called_once_with("potion_of_healing")

    def test_prompt_item_to_take_formats_currency_nicely(self, cli, game_state):
        """Test that currency is formatted nicely in the choices"""
        # Mock available items with mixed currency
        game_state.get_available_items_in_room.return_value = [
            {"type": "currency", "gold": 30, "silver": 20, "platinum": 2}
        ]

        with patch('questionary.select') as mock_select:
            mock_result = MagicMock()
            mock_result.ask.return_value = None
            mock_select.return_value = mock_result

            cli._prompt_item_to_take()

            # Check that the choice text was formatted nicely
            call_args = mock_select.call_args
            choices = call_args[1]['choices']

            # First choice should be the currency (before Cancel)
            currency_choice = choices[0]
            assert "30 gold" in currency_choice.title
            assert "20 silver" in currency_choice.title
            assert "2 platinum" in currency_choice.title

    def test_prompt_item_to_take_formats_items_nicely(self, cli, game_state):
        """Test that item names are formatted nicely (Title Case, no underscores)"""
        # Mock available items
        game_state.get_available_items_in_room.return_value = [
            {"type": "item", "id": "potion_of_healing"},
            {"type": "item", "id": "alchemists_fire"}
        ]

        with patch('questionary.select') as mock_select:
            mock_result = MagicMock()
            mock_result.ask.return_value = None
            mock_select.return_value = mock_result

            cli._prompt_item_to_take()

            # Check that item names were formatted
            call_args = mock_select.call_args
            choices = call_args[1]['choices']

            # Should have 2 items + Cancel = 3 choices
            assert len(choices) == 3
            assert "Potion Of Healing" in choices[0].title
            assert "Alchemists Fire" in choices[1].title
