# ABOUTME: Unit tests for character vault UI functionality in MainMenuV2
# ABOUTME: Tests questionary-based character selection and display formatting

from unittest.mock import Mock, patch

import pytest

from terminal_client.ui.main_menu_v2 import MainMenuV2


@pytest.fixture
def basic_character_info():
    """Create basic character info dict."""
    return {
        "id": "char-123",
        "name": "Thorin",
        "class": "Fighter",
        "level": 5,
        "race": "Dwarf",
        "times_used": 0,
        "save_slots_used": [],
    }


@pytest.fixture
def used_character_info():
    """Create character info dict for character in active saves."""
    return {
        "id": "char-456",
        "name": "Elara",
        "class": "Wizard",
        "level": 7,
        "race": "Elf",
        "times_used": 3,
        "save_slots_used": [1, 3],
    }


@pytest.fixture
def character_list(basic_character_info, used_character_info):
    """Create list of character info dicts."""
    return [basic_character_info, used_character_info]


class TestBuildCharacterChoiceDisplay:
    """Test character choice display string building."""

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    def test_basic_character_display(self, basic_character_info):
        """Test display string for character not in any saves."""
        menu = MainMenuV2()
        result = menu._build_character_choice_display(basic_character_info)

        assert "Thorin" in result
        assert "Level 5" in result
        assert "Dwarf" in result
        assert "Fighter" in result
        # Should not show slot info when not used
        assert "slots" not in result.lower()

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    def test_used_character_display(self, used_character_info):
        """Test display string for character in active saves."""
        menu = MainMenuV2()
        result = menu._build_character_choice_display(used_character_info)

        assert "Elara" in result
        assert "Level 7" in result
        assert "Elf" in result
        assert "Wizard" in result
        # Should show slot usage
        assert "slots" in result.lower()
        assert "1" in result
        assert "3" in result


class TestSelectCharacterForDeletion:
    """Test questionary-based character selection for deletion."""

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch("terminal_client.ui.main_menu_v2.questionary")
    def test_select_character_shows_all_characters(self, mock_questionary, character_list):
        """Test that all characters are shown in selection."""
        menu = MainMenuV2()

        mock_questionary.select.return_value.ask.return_value = character_list[0]
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)

        result = menu._select_character_for_deletion(character_list)

        assert result == character_list[0]
        mock_questionary.select.assert_called_once()
        # Verify 2 characters + back option = 3 choices
        choice_calls = mock_questionary.Choice.call_args_list
        assert len(choice_calls) == 3

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch("terminal_client.ui.main_menu_v2.questionary")
    def test_select_character_returns_none_on_back(self, mock_questionary, character_list):
        """Test that selecting back returns None."""
        menu = MainMenuV2()

        mock_questionary.select.return_value.ask.return_value = "back"
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)

        result = menu._select_character_for_deletion(character_list)

        assert result is None

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch("terminal_client.ui.main_menu_v2.questionary")
    def test_select_character_handles_keyboard_interrupt(self, mock_questionary, character_list):
        """Test that keyboard interrupt returns None."""
        menu = MainMenuV2()

        mock_questionary.select.return_value.ask.side_effect = KeyboardInterrupt
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)

        result = menu._select_character_for_deletion(character_list)

        assert result is None

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch("terminal_client.ui.main_menu_v2.questionary")
    def test_select_character_handles_eof_error(self, mock_questionary, character_list):
        """Test that EOF error returns None."""
        menu = MainMenuV2()

        mock_questionary.select.return_value.ask.side_effect = EOFError
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)

        result = menu._select_character_for_deletion(character_list)

        assert result is None

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch("terminal_client.ui.main_menu_v2.print_status_message")
    def test_select_character_shows_warning_when_empty(self, mock_print):
        """Test warning message when no characters in vault."""
        menu = MainMenuV2()

        result = menu._select_character_for_deletion([])

        assert result is None
        mock_print.assert_called_with("No characters in vault.", "warning")


class TestHandleCharacterVault:
    """Test character vault management flow."""

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch("terminal_client.ui.main_menu_v2.questionary")
    @patch("terminal_client.ui.main_menu_v2.print_section")
    @patch("terminal_client.ui.main_menu_v2.console")
    def test_vault_shows_action_menu(self, mock_console, mock_print_section, mock_questionary):
        """Test that vault shows action selection."""
        menu = MainMenuV2()
        menu.vault = Mock()
        menu.vault.list_characters.return_value = []

        # Return "back" immediately
        mock_questionary.select.return_value.ask.return_value = "back"
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)

        menu.handle_character_vault()

        mock_questionary.select.assert_called()
        call_args = mock_questionary.select.call_args
        assert "What would you like to do?" in str(call_args)

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch.object(MainMenuV2, "_create_character_interactive")
    @patch("terminal_client.ui.main_menu_v2.questionary")
    @patch("terminal_client.ui.main_menu_v2.print_section")
    @patch("terminal_client.ui.main_menu_v2.print_status_message")
    @patch("terminal_client.ui.main_menu_v2.console")
    def test_vault_create_action_calls_wizard(
        self,
        mock_console,
        mock_print_status,
        mock_print_section,
        mock_questionary,
        mock_create,
    ):
        """Test that create action calls character wizard."""
        menu = MainMenuV2()
        menu.vault = Mock()
        menu.vault.list_characters.return_value = []

        mock_char = Mock()
        mock_char.name = "TestChar"
        mock_create.return_value = mock_char

        # First select: create, Second select: back
        mock_questionary.select.return_value.ask.side_effect = ["create", None]
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)

        menu.handle_character_vault()

        mock_create.assert_called_once()
        menu.vault.add_character.assert_called_once_with(mock_char)

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch.object(MainMenuV2, "_select_character_for_deletion")
    @patch("terminal_client.ui.main_menu_v2.questionary")
    @patch("terminal_client.ui.main_menu_v2.print_section")
    @patch("terminal_client.ui.main_menu_v2.print_status_message")
    @patch("terminal_client.ui.main_menu_v2.console")
    def test_vault_delete_uses_character_selector(
        self,
        mock_console,
        mock_print_status,
        mock_print_section,
        mock_questionary,
        mock_select,
        basic_character_info,
    ):
        """Test that delete action uses character selector."""
        menu = MainMenuV2()
        menu.vault = Mock()
        menu.vault.list_characters.return_value = [basic_character_info]

        mock_select.return_value = basic_character_info

        # First select: delete, confirm: yes, Second select: back
        mock_questionary.select.return_value.ask.side_effect = ["delete", None]
        mock_questionary.confirm.return_value.ask.return_value = True
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)

        menu.handle_character_vault()

        mock_select.assert_called_once()
        menu.vault.delete_character.assert_called_once_with(basic_character_info["id"])

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch.object(MainMenuV2, "_select_character_for_deletion")
    @patch("terminal_client.ui.main_menu_v2.questionary")
    @patch("terminal_client.ui.main_menu_v2.print_section")
    @patch("terminal_client.ui.main_menu_v2.console")
    def test_vault_delete_respects_cancel_confirmation(
        self,
        mock_console,
        mock_print_section,
        mock_questionary,
        mock_select,
        basic_character_info,
    ):
        """Test that canceling confirmation does not delete."""
        menu = MainMenuV2()
        menu.vault = Mock()
        menu.vault.list_characters.return_value = [basic_character_info]

        mock_select.return_value = basic_character_info

        # First select: delete, confirm: no, Second select: back
        mock_questionary.select.return_value.ask.side_effect = ["delete", None]
        mock_questionary.confirm.return_value.ask.return_value = False
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)

        menu.handle_character_vault()

        mock_questionary.confirm.assert_called_once()
        menu.vault.delete_character.assert_not_called()

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch.object(MainMenuV2, "_select_character_for_deletion")
    @patch("terminal_client.ui.main_menu_v2.questionary")
    @patch("terminal_client.ui.main_menu_v2.print_section")
    @patch("terminal_client.ui.main_menu_v2.console")
    def test_vault_delete_cancel_at_selection(
        self,
        mock_console,
        mock_print_section,
        mock_questionary,
        mock_select,
        basic_character_info,
    ):
        """Test that canceling at character selection does not prompt confirm."""
        menu = MainMenuV2()
        menu.vault = Mock()
        menu.vault.list_characters.return_value = [basic_character_info]

        mock_select.return_value = None  # User pressed back

        # First select: delete, Second select: back
        mock_questionary.select.return_value.ask.side_effect = ["delete", None]
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)

        menu.handle_character_vault()

        mock_select.assert_called_once()
        mock_questionary.confirm.assert_not_called()
        menu.vault.delete_character.assert_not_called()

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch("terminal_client.ui.main_menu_v2.questionary")
    @patch("terminal_client.ui.main_menu_v2.print_section")
    @patch("terminal_client.ui.main_menu_v2.console")
    def test_vault_hides_delete_when_empty(
        self, mock_console, mock_print_section, mock_questionary
    ):
        """Test that delete option is not shown when vault is empty."""
        menu = MainMenuV2()
        menu.vault = Mock()
        menu.vault.list_characters.return_value = []

        mock_questionary.select.return_value.ask.return_value = "back"
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)

        menu.handle_character_vault()

        # Check choice calls - should not include delete
        choice_calls = mock_questionary.Choice.call_args_list
        choice_titles = [call.kwargs.get("title", "") for call in choice_calls]
        assert not any("delete" in title.lower() for title in choice_titles)

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch("terminal_client.ui.main_menu_v2.questionary")
    @patch("terminal_client.ui.main_menu_v2.print_section")
    @patch("terminal_client.ui.main_menu_v2.console")
    def test_vault_shows_delete_when_has_characters(
        self, mock_console, mock_print_section, mock_questionary, character_list
    ):
        """Test that delete option is shown when vault has characters."""
        menu = MainMenuV2()
        menu.vault = Mock()
        menu.vault.list_characters.return_value = character_list

        mock_questionary.select.return_value.ask.return_value = "back"
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)

        menu.handle_character_vault()

        # Check choice calls - should include delete
        choice_calls = mock_questionary.Choice.call_args_list
        choice_titles = [call.kwargs.get("title", "") for call in choice_calls]
        assert any("delete" in title.lower() for title in choice_titles)

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch("terminal_client.ui.main_menu_v2.questionary")
    @patch("terminal_client.ui.main_menu_v2.print_section")
    @patch("terminal_client.ui.main_menu_v2.console")
    def test_vault_handles_keyboard_interrupt(
        self, mock_console, mock_print_section, mock_questionary
    ):
        """Test that keyboard interrupt exits gracefully."""
        menu = MainMenuV2()
        menu.vault = Mock()
        menu.vault.list_characters.return_value = []

        mock_questionary.select.return_value.ask.side_effect = KeyboardInterrupt
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)

        # Should not raise
        menu.handle_character_vault()

    @patch.object(MainMenuV2, "__init__", lambda x: None)
    @patch("terminal_client.ui.main_menu_v2.questionary")
    @patch("terminal_client.ui.main_menu_v2.print_section")
    @patch("terminal_client.ui.main_menu_v2.console")
    def test_vault_handles_eof_error(self, mock_console, mock_print_section, mock_questionary):
        """Test that EOF error exits gracefully."""
        menu = MainMenuV2()
        menu.vault = Mock()
        menu.vault.list_characters.return_value = []

        mock_questionary.select.return_value.ask.side_effect = EOFError
        mock_questionary.Choice = Mock(side_effect=lambda **kwargs: kwargs)

        # Should not raise
        menu.handle_character_vault()
