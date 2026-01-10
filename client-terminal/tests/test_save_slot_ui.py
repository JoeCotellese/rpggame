# ABOUTME: Unit tests for save slot UI functionality in MainMenuV2
# ABOUTME: Tests questionary-based slot selection and display formatting

from unittest.mock import Mock, patch

import pytest

from dnd_engine.core.save_slot import SaveSlot
from terminal_client.ui.main_menu_v2 import MainMenuV2


@pytest.fixture
def empty_slot():
    """Create an empty save slot."""
    slot = Mock(spec=SaveSlot)
    slot.slot_number = 1
    slot.is_empty.return_value = True
    slot.adventure_name = None
    slot.party_composition = []
    slot.party_levels = []
    slot._format_playtime.return_value = "0m"
    return slot


@pytest.fixture
def used_slot():
    """Create a save slot with game data."""
    slot = Mock(spec=SaveSlot)
    slot.slot_number = 2
    slot.is_empty.return_value = False
    slot.adventure_name = "Tomb of Horrors"
    slot.party_composition = ["Aria", "Zephyr"]
    slot.party_levels = [3, 3]
    slot._format_playtime.return_value = "2h 30m"
    slot.get_display_name.return_value = "Tomb of Horrors - Aria, Zephyr"
    return slot


@pytest.fixture
def mock_slot_manager(empty_slot, used_slot):
    """Create mock slot manager with test slots."""
    manager = Mock()
    slots = [empty_slot, used_slot]
    # Add more empty slots to fill to 10
    for i in range(3, 11):
        slot = Mock(spec=SaveSlot)
        slot.slot_number = i
        slot.is_empty.return_value = True
        slot.adventure_name = None
        slot.party_composition = []
        slot.party_levels = []
        slot._format_playtime.return_value = "0m"
        slots.append(slot)
    manager.list_slots.return_value = slots
    manager.get_slot.side_effect = lambda n: slots[n - 1]
    return manager


class TestBuildSlotChoiceDisplay:
    """Test slot choice display string building."""

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    def test_empty_slot_display(self, empty_slot):
        """Test display string for empty slot."""
        menu = MainMenuV2()
        result = menu._build_slot_choice_display(empty_slot)

        assert "Slot 1" in result
        assert "[Empty]" in result

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    def test_used_slot_display(self, used_slot):
        """Test display string for slot with saved game."""
        menu = MainMenuV2()
        result = menu._build_slot_choice_display(used_slot)

        assert "Slot 2" in result
        assert "Tomb of Horrors" in result
        assert "Aria, Zephyr" in result
        assert "Lvl 3" in result
        assert "2h 30m" in result

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    def test_used_slot_without_adventure_name(self, used_slot):
        """Test display string when adventure name is missing."""
        menu = MainMenuV2()
        used_slot.adventure_name = None

        result = menu._build_slot_choice_display(used_slot)

        assert "Unknown Adventure" in result


class TestSelectSaveSlot:
    """Test questionary-based save slot selection."""

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch("terminal_client.ui.main_menu_v2.questionary")
    def test_select_slot_shows_all_slots(self, mock_questionary, mock_slot_manager):
        """Test that all slots are shown in selection."""
        menu = MainMenuV2()
        menu.slot_manager = mock_slot_manager

        mock_questionary.select.return_value.ask.return_value = 2
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)

        result = menu._select_save_slot("Select a slot:")

        assert result == 2
        mock_questionary.select.assert_called_once()
        # Verify 10 slots + back option = 11 choices
        choice_calls = mock_questionary.Choice.call_args_list
        assert len(choice_calls) == 11

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch("terminal_client.ui.main_menu_v2.questionary")
    def test_select_slot_filters_empty_when_requested(
        self, mock_questionary, mock_slot_manager, used_slot
    ):
        """Test filtering to only non-empty slots."""
        menu = MainMenuV2()
        menu.slot_manager = mock_slot_manager
        # Only return the used slot when filtering
        mock_slot_manager.list_slots.return_value = [used_slot]

        mock_questionary.select.return_value.ask.return_value = 2
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)

        result = menu._select_save_slot("Select:", filter_empty=True)

        assert result == 2
        # Should have 1 slot + back = 2 choices
        choice_calls = mock_questionary.Choice.call_args_list
        assert len(choice_calls) == 2

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch("terminal_client.ui.main_menu_v2.questionary")
    def test_select_slot_disables_empty_when_not_allowed(self, mock_questionary, mock_slot_manager):
        """Test that empty slots are disabled when allow_empty=False."""
        menu = MainMenuV2()
        menu.slot_manager = mock_slot_manager

        mock_questionary.select.return_value.ask.return_value = 2
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)

        menu._select_save_slot("Select:", allow_empty=False)

        # Check that disabled='empty slot' was set for empty slots
        choice_calls = mock_questionary.Choice.call_args_list
        disabled_count = sum(
            1 for call in choice_calls if call.kwargs.get("disabled") == "empty slot"
        )
        # Should have 9 disabled empty slots (slot 2 is used)
        assert disabled_count == 9

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch("terminal_client.ui.main_menu_v2.questionary")
    def test_select_slot_returns_none_on_back(self, mock_questionary, mock_slot_manager):
        """Test that selecting back returns None."""
        menu = MainMenuV2()
        menu.slot_manager = mock_slot_manager

        mock_questionary.select.return_value.ask.return_value = None
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)

        result = menu._select_save_slot("Select:")

        assert result is None

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch("terminal_client.ui.main_menu_v2.questionary")
    def test_select_slot_handles_keyboard_interrupt(self, mock_questionary, mock_slot_manager):
        """Test that keyboard interrupt returns None."""
        menu = MainMenuV2()
        menu.slot_manager = mock_slot_manager

        mock_questionary.select.return_value.ask.side_effect = KeyboardInterrupt
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)

        result = menu._select_save_slot("Select:")

        assert result is None

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch("terminal_client.ui.main_menu_v2.print_status_message")
    def test_select_slot_shows_warning_when_no_slots(self, mock_print):
        """Test warning message when no slots match filter."""
        menu = MainMenuV2()
        menu.slot_manager = Mock()
        menu.slot_manager.list_slots.return_value = []

        result = menu._select_save_slot("Select:", filter_empty=True)

        assert result is None
        mock_print.assert_called_with("No saved games found.", "warning")


class TestHandleLoadGame:
    """Test load game flow with questionary."""

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch.object(MainMenuV2, "_select_save_slot")
    @patch("terminal_client.ui.main_menu_v2.print_section")
    @patch("terminal_client.ui.main_menu_v2.console")
    def test_load_game_uses_slot_selector(
        self, mock_console, mock_print_section, mock_select, used_slot
    ):
        """Test that load game uses the slot selector."""
        menu = MainMenuV2()
        menu.slot_manager = Mock()
        menu.slot_manager.get_slot.return_value = used_slot
        menu.slot_manager.load_game.return_value = (Mock(), None)
        mock_select.return_value = 2

        menu.handle_load_game()

        mock_select.assert_called_once_with(
            "Select a saved game to load:", filter_empty=True, allow_empty=False
        )

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch.object(MainMenuV2, "_select_save_slot")
    @patch("terminal_client.ui.main_menu_v2.print_section")
    @patch("terminal_client.ui.main_menu_v2.console")
    def test_load_game_returns_none_on_cancel(self, mock_console, mock_print_section, mock_select):
        """Test that canceling slot selection returns None."""
        menu = MainMenuV2()
        mock_select.return_value = None

        result = menu.handle_load_game()

        assert result is None


class TestHandleManageSlots:
    """Test manage slots flow with questionary."""

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch("terminal_client.ui.main_menu_v2.questionary")
    @patch("terminal_client.ui.main_menu_v2.print_section")
    @patch("terminal_client.ui.main_menu_v2.console")
    def test_manage_slots_shows_action_menu(
        self, mock_console, mock_print_section, mock_questionary
    ):
        """Test that manage slots shows action selection."""
        menu = MainMenuV2()

        # Return None (back) immediately
        mock_questionary.select.return_value.ask.return_value = None
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)

        menu.handle_manage_slots()

        mock_questionary.select.assert_called()
        # Verify action choices were presented
        call_args = mock_questionary.select.call_args
        assert "What would you like to do?" in str(call_args)

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch.object(MainMenuV2, "_select_save_slot")
    @patch("terminal_client.ui.main_menu_v2.questionary")
    @patch("terminal_client.ui.main_menu_v2.print_section")
    @patch("terminal_client.ui.main_menu_v2.print_status_message")
    @patch("terminal_client.ui.main_menu_v2.console")
    def test_manage_slots_rename_uses_slot_selector(
        self, mock_console, mock_print, mock_print_section, mock_questionary, mock_select, used_slot
    ):
        """Test that rename action uses slot selector."""
        menu = MainMenuV2()
        menu.slot_manager = Mock()

        # First call: rename action, Second call: back
        mock_questionary.select.return_value.ask.side_effect = ["rename", None]
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)
        mock_select.return_value = 2
        mock_console.input.return_value = "New Name"

        menu.handle_manage_slots()

        mock_select.assert_called_once_with(
            "Select slot to rename:", filter_empty=False, allow_empty=False
        )
        menu.slot_manager.rename_slot.assert_called_once_with(2, "New Name")

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch.object(MainMenuV2, "_select_save_slot")
    @patch("terminal_client.ui.main_menu_v2.questionary")
    @patch("terminal_client.ui.main_menu_v2.print_section")
    @patch("terminal_client.ui.main_menu_v2.print_status_message")
    @patch("terminal_client.ui.main_menu_v2.console")
    def test_manage_slots_clear_with_confirmation(
        self, mock_console, mock_print, mock_print_section, mock_questionary, mock_select, used_slot
    ):
        """Test that clear action asks for confirmation."""
        menu = MainMenuV2()
        menu.slot_manager = Mock()
        menu.slot_manager.get_slot.return_value = used_slot

        # First select: clear, confirm: yes, Second select: back
        mock_questionary.select.return_value.ask.side_effect = ["clear", None]
        mock_questionary.confirm.return_value.ask.return_value = True
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)
        mock_select.return_value = 2
        mock_console.input.return_value = ""

        menu.handle_manage_slots()

        mock_questionary.confirm.assert_called_once()
        menu.slot_manager.clear_slot.assert_called_once_with(2)
