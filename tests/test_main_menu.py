# ABOUTME: Unit tests for MainMenu class
# ABOUTME: Tests menu display, input handling, and navigation logic

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from pathlib import Path

from dnd_engine.ui.main_menu import MainMenu
from dnd_engine.core.campaign import Campaign
from dnd_engine.core.campaign_manager import CampaignManager
from dnd_engine.core.character_vault import CharacterVault
from dnd_engine.core.game_state import GameState


@pytest.fixture
def temp_campaign_dir(tmp_path):
    """Create temporary campaign directory"""
    campaign_dir = tmp_path / "campaigns"
    campaign_dir.mkdir()
    return campaign_dir


@pytest.fixture
def temp_vault_dir(tmp_path):
    """Create temporary vault directory"""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    return vault_dir


@pytest.fixture
def campaign_manager(temp_campaign_dir):
    """Create CampaignManager with temp directory"""
    return CampaignManager(campaigns_dir=temp_campaign_dir)


@pytest.fixture
def character_vault(temp_vault_dir):
    """Create CharacterVault with temp directory"""
    return CharacterVault(vault_dir=temp_vault_dir)


@pytest.fixture
def main_menu(campaign_manager, character_vault):
    """Create MainMenu instance"""
    return MainMenu(
        campaign_manager=campaign_manager,
        character_vault=character_vault
    )


@pytest.fixture
def sample_campaign():
    """Create a sample campaign for testing"""
    return Campaign(
        name="Test Campaign",
        created_at=datetime.now() - timedelta(days=5),
        last_played=datetime.now() - timedelta(hours=2),
        playtime_seconds=3600 * 6 + 60 * 23,  # 6h 23m
        current_dungeon="test_dungeon",
        party_character_ids=["char1", "char2"]
    )


class TestMainMenuInit:
    """Test MainMenu initialization"""

    def test_init_with_managers(self, campaign_manager, character_vault):
        """Test initialization with provided managers"""
        menu = MainMenu(
            campaign_manager=campaign_manager,
            character_vault=character_vault
        )

        assert menu.campaign_manager == campaign_manager
        assert menu.character_vault == character_vault

    def test_init_creates_default_managers(self):
        """Test that initialization creates default managers if not provided"""
        menu = MainMenu()

        assert menu.campaign_manager is not None
        assert menu.character_vault is not None
        assert isinstance(menu.campaign_manager, CampaignManager)
        assert isinstance(menu.character_vault, CharacterVault)


class TestShowMainMenu:
    """Test main menu display and input handling"""

    @patch('dnd_engine.ui.main_menu.console')
    def test_show_displays_menu_options(self, mock_console, main_menu):
        """Test that main menu displays all options"""
        mock_console.input.return_value = "6"  # Exit

        choice = main_menu.show()

        assert choice == "exit"
        # Verify console.print was called (menu was displayed)
        assert mock_console.print.called

    @patch('dnd_engine.ui.main_menu.console')
    def test_show_maps_choices_correctly(self, mock_console, main_menu):
        """Test that menu choices map to correct actions"""
        test_cases = [
            ("1", "quick_start"),
            ("2", "continue"),
            ("3", "new"),
            ("4", "load"),
            ("5", "vault"),
            ("6", "exit")
        ]

        for input_val, expected_output in test_cases:
            mock_console.input.return_value = input_val
            choice = main_menu.show()
            assert choice == expected_output

    @patch('dnd_engine.ui.main_menu.console')
    def test_show_handles_invalid_input(self, mock_console, main_menu):
        """Test that invalid input returns None"""
        mock_console.input.return_value = "99"

        choice = main_menu.show()

        assert choice is None


class TestShowContinuePreview:
    """Test continue campaign preview"""

    @patch('dnd_engine.ui.main_menu.console')
    def test_show_continue_preview_no_campaigns(self, mock_console, main_menu):
        """Test preview when no campaigns exist"""
        result = main_menu.show_continue_preview()

        assert result is None

    @patch('dnd_engine.ui.main_menu.console')
    def test_show_continue_preview_with_campaign(
        self,
        mock_console,
        main_menu,
        campaign_manager,
        sample_campaign
    ):
        """Test preview with existing campaign"""
        # Create a campaign
        campaign_manager.create_campaign(
            name=sample_campaign.name,
            dungeon_name=sample_campaign.current_dungeon,
            party_character_ids=sample_campaign.party_character_ids
        )

        # User confirms
        mock_console.input.return_value = "y"

        result = main_menu.show_continue_preview()

        assert result == sample_campaign.name

    @patch('dnd_engine.ui.main_menu.console')
    def test_show_continue_preview_user_cancels(
        self,
        mock_console,
        main_menu,
        campaign_manager,
        sample_campaign
    ):
        """Test preview when user cancels"""
        # Create a campaign
        campaign_manager.create_campaign(
            name=sample_campaign.name,
            dungeon_name=sample_campaign.current_dungeon,
            party_character_ids=sample_campaign.party_character_ids
        )

        # User cancels
        mock_console.input.return_value = "n"

        result = main_menu.show_continue_preview()

        assert result is None

    @patch('dnd_engine.ui.main_menu.console')
    def test_show_continue_preview_empty_confirm(
        self,
        mock_console,
        main_menu,
        campaign_manager,
        sample_campaign
    ):
        """Test that empty input (Enter) defaults to Yes"""
        # Create a campaign
        campaign_manager.create_campaign(
            name=sample_campaign.name,
            dungeon_name=sample_campaign.current_dungeon,
            party_character_ids=sample_campaign.party_character_ids
        )

        # User presses Enter (empty string)
        mock_console.input.return_value = ""

        result = main_menu.show_continue_preview()

        assert result == sample_campaign.name


class TestShowCampaignList:
    """Test campaign list display"""

    @patch('dnd_engine.ui.main_menu.console')
    def test_show_campaign_list_empty(self, mock_console, main_menu):
        """Test list when no campaigns exist"""
        result = main_menu.show_campaign_list()

        assert result is None

    @patch('dnd_engine.ui.main_menu.console')
    def test_show_campaign_list_single_campaign(
        self,
        mock_console,
        main_menu,
        campaign_manager,
        sample_campaign
    ):
        """Test list with one campaign"""
        # Create campaign
        campaign_manager.create_campaign(
            name=sample_campaign.name,
            dungeon_name=sample_campaign.current_dungeon,
            party_character_ids=sample_campaign.party_character_ids
        )

        # User selects first campaign
        mock_console.input.return_value = "1"

        result = main_menu.show_campaign_list()

        assert result == sample_campaign.name

    @patch('dnd_engine.ui.main_menu.console')
    def test_show_campaign_list_multiple_campaigns(
        self,
        mock_console,
        main_menu,
        campaign_manager
    ):
        """Test list with multiple campaigns"""
        # Create multiple campaigns
        campaign_manager.create_campaign("Campaign 1", "dungeon1", ["char1"])
        campaign_manager.create_campaign("Campaign 2", "dungeon2", ["char2"])
        campaign_manager.create_campaign("Campaign 3", "dungeon3", ["char3"])

        # User selects second campaign
        mock_console.input.return_value = "2"

        result = main_menu.show_campaign_list()

        assert result == "Campaign 2"

    @patch('dnd_engine.ui.main_menu.console')
    def test_show_campaign_list_user_backs_out(
        self,
        mock_console,
        main_menu,
        campaign_manager
    ):
        """Test user pressing 'B' to go back"""
        campaign_manager.create_campaign("Test Campaign", "dungeon", [])

        # User presses 'B'
        mock_console.input.return_value = "b"

        result = main_menu.show_campaign_list()

        assert result is None

    @patch('dnd_engine.ui.main_menu.console')
    def test_show_campaign_list_invalid_number(
        self,
        mock_console,
        main_menu,
        campaign_manager
    ):
        """Test invalid campaign number"""
        campaign_manager.create_campaign("Test Campaign", "dungeon", [])

        # User enters invalid number
        mock_console.input.return_value = "99"

        result = main_menu.show_campaign_list()

        assert result is None

    @patch('dnd_engine.ui.main_menu.console')
    def test_show_campaign_list_invalid_input(
        self,
        mock_console,
        main_menu,
        campaign_manager
    ):
        """Test non-numeric input"""
        campaign_manager.create_campaign("Test Campaign", "dungeon", [])

        # User enters invalid text
        mock_console.input.return_value = "abc"

        result = main_menu.show_campaign_list()

        assert result is None


class TestShowCampaignSaveSlots:
    """Test save slot selection"""

    @patch('dnd_engine.ui.main_menu.console')
    def test_show_save_slots_nonexistent_campaign(self, mock_console, main_menu):
        """Test with campaign that doesn't exist"""
        result = main_menu.show_campaign_save_slots("NonexistentCampaign")

        assert result is None

    @patch('dnd_engine.ui.main_menu.console')
    def test_show_save_slots_no_saves(
        self,
        mock_console,
        main_menu,
        campaign_manager
    ):
        """Test with campaign that has no saves"""
        campaign_manager.create_campaign("Empty Campaign", "dungeon", [])

        result = main_menu.show_campaign_save_slots("Empty Campaign")

        assert result is None

    @patch('dnd_engine.ui.main_menu.console')
    def test_show_save_slots_with_saves(
        self,
        mock_console,
        main_menu,
        campaign_manager
    ):
        """Test with campaign that has save slots"""
        # Create campaign and save
        campaign_manager.create_campaign("Test Campaign", "dungeon", ["char1"])

        # Create a mock game state (we'll need this for saving)
        mock_game_state = Mock(spec=GameState)
        mock_game_state.party = Mock()
        mock_game_state.party.characters = []
        mock_game_state.dungeon_name = "dungeon"
        mock_game_state.current_room_id = "room_1"
        mock_game_state.dungeon = {"rooms": {}}
        mock_game_state.action_history = []
        mock_game_state.last_entry_direction = None
        mock_game_state.in_combat = False

        campaign_manager.save_campaign_state(
            "Test Campaign",
            mock_game_state,
            slot_name="auto",
            save_type="auto"
        )

        # User selects first save slot
        mock_console.input.return_value = "1"

        result = main_menu.show_campaign_save_slots("Test Campaign")

        assert result == "save_auto"

    @patch('dnd_engine.ui.main_menu.console')
    def test_show_save_slots_user_backs_out(
        self,
        mock_console,
        main_menu,
        campaign_manager
    ):
        """Test user backing out of save slot selection"""
        campaign_manager.create_campaign("Test Campaign", "dungeon", ["char1"])

        mock_game_state = Mock(spec=GameState)
        mock_game_state.party = Mock()
        mock_game_state.party.characters = []
        mock_game_state.dungeon_name = "dungeon"
        mock_game_state.current_room_id = "room_1"
        mock_game_state.dungeon = {"rooms": {}}
        mock_game_state.action_history = []
        mock_game_state.last_entry_direction = None
        mock_game_state.in_combat = False

        campaign_manager.save_campaign_state(
            "Test Campaign",
            mock_game_state,
            slot_name="auto",
            save_type="auto"
        )

        # User presses 'B'
        mock_console.input.return_value = "back"

        result = main_menu.show_campaign_save_slots("Test Campaign")

        assert result is None


class TestHandleContinueLastCampaign:
    """Test continue last campaign flow"""

    @patch('dnd_engine.ui.main_menu.console')
    def test_handle_continue_no_campaigns(self, mock_console, main_menu):
        """Test continue when no campaigns exist"""
        result = main_menu.handle_continue_last_campaign()

        assert result is None

    @patch('dnd_engine.ui.main_menu.console')
    def test_handle_continue_user_cancels_preview(
        self,
        mock_console,
        main_menu,
        campaign_manager
    ):
        """Test user cancelling at preview stage"""
        campaign_manager.create_campaign("Test Campaign", "dungeon", [])

        # User cancels preview
        mock_console.input.return_value = "n"

        result = main_menu.handle_continue_last_campaign()

        assert result is None


class TestHandleLoadCampaign:
    """Test load campaign flow"""

    @patch('dnd_engine.ui.main_menu.console')
    def test_handle_load_no_campaigns(self, mock_console, main_menu):
        """Test load when no campaigns exist"""
        result = main_menu.handle_load_campaign()

        assert result is None

    @patch('dnd_engine.ui.main_menu.console')
    def test_handle_load_user_backs_from_campaign_list(
        self,
        mock_console,
        main_menu,
        campaign_manager
    ):
        """Test user backing out from campaign list"""
        campaign_manager.create_campaign("Test Campaign", "dungeon", [])

        # User backs out
        mock_console.input.return_value = "b"

        result = main_menu.handle_load_campaign()

        assert result is None


class TestHandleQuickStart:
    """Test quick start flow"""

    def test_handle_quick_start_not_implemented(self, main_menu):
        """Test that quick start returns None (not yet implemented)"""
        result = main_menu.handle_quick_start()

        assert result is None


class TestHandleCharacterVault:
    """Test character vault navigation"""

    def test_handle_character_vault_not_implemented(self, main_menu):
        """Test that character vault shows info message"""
        # Should not raise exception
        main_menu.handle_character_vault()


class TestRunMainMenuLoop:
    """Test main menu loop"""

    @patch('dnd_engine.ui.main_menu.console')
    @patch.object(MainMenu, 'show')
    def test_run_exits_on_exit_choice(self, mock_show, mock_console, main_menu):
        """Test that run exits when user selects exit"""
        mock_show.return_value = "exit"

        result = main_menu.run()

        assert result is None

    @patch('dnd_engine.ui.main_menu.console')
    @patch.object(MainMenu, 'show')
    def test_run_handles_invalid_choice(self, mock_show, mock_console, main_menu):
        """Test that run handles invalid choices gracefully"""
        # First return invalid, then exit
        mock_show.side_effect = [None, "exit"]
        mock_console.input.return_value = ""  # For "press enter to continue"

        result = main_menu.run()

        assert result is None
        assert mock_show.call_count == 2
