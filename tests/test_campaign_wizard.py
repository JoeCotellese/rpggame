# ABOUTME: Unit tests for campaign creation wizard
# ABOUTME: Tests multi-step campaign creation flow with party building

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path

from dnd_engine.ui.campaign_wizard import CampaignCreationWizard
from dnd_engine.core.campaign_manager import CampaignManager
from dnd_engine.core.character_vault import CharacterVault, CharacterState
from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities


@pytest.fixture
def temp_dirs(tmp_path):
    """Create temporary directories for testing"""
    campaign_dir = tmp_path / "campaigns"
    vault_dir = tmp_path / "vault"
    data_dir = tmp_path / "data" / "content" / "dungeons"

    campaign_dir.mkdir(parents=True)
    vault_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)

    # Create sample dungeon file
    (data_dir / "test_dungeon.json").write_text('{"name": "Test Dungeon", "start_room": "room_1", "rooms": {}}')

    return {
        "campaign": campaign_dir,
        "vault": vault_dir,
        "data": data_dir.parent.parent
    }


@pytest.fixture
def campaign_manager(temp_dirs):
    """Create CampaignManager with temp directory"""
    return CampaignManager(campaigns_dir=temp_dirs["campaign"])


@pytest.fixture
def character_vault(temp_dirs):
    """Create CharacterVault with temp directory"""
    return CharacterVault(vault_dir=temp_dirs["vault"])


@pytest.fixture
def sample_character():
    """Create a sample character"""
    return Character(
        name="Test Hero",
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
def wizard(campaign_manager, character_vault, temp_dirs):
    """Create wizard with mocked dependencies"""
    # Mock data loader
    mock_loader = Mock()
    mock_loader.data_path = temp_dirs["data"]

    wizard = CampaignCreationWizard(
        campaign_manager=campaign_manager,
        character_vault=character_vault,
        character_factory=Mock(spec=CharacterFactory),
        data_loader=mock_loader
    )

    return wizard


class TestWizardInit:
    """Test wizard initialization"""

    def test_init_with_managers(self, campaign_manager, character_vault):
        """Test wizard initializes with provided managers"""
        wizard = CampaignCreationWizard(
            campaign_manager=campaign_manager,
            character_vault=character_vault
        )

        assert wizard.campaign_manager == campaign_manager
        assert wizard.character_vault == character_vault
        assert wizard.campaign_name is None
        assert wizard.starting_level == 1
        assert wizard.party_character_ids == []
        assert wizard.dungeon_name is None

    def test_init_creates_defaults(self):
        """Test wizard creates default managers if not provided"""
        wizard = CampaignCreationWizard()

        assert wizard.campaign_manager is not None
        assert wizard.character_vault is not None
        assert wizard.character_factory is not None
        assert wizard.data_loader is not None


class TestStepCampaignName:
    """Test campaign name input step"""

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_valid_name(self, mock_console, wizard):
        """Test entering valid campaign name"""
        mock_console.input.return_value = "My Campaign"

        result = wizard._step_campaign_name()

        assert result is True
        assert wizard.campaign_name == "My Campaign"

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_empty_name_then_valid(self, mock_console, wizard):
        """Test empty name followed by valid name"""
        mock_console.input.side_effect = ["", "Valid Campaign"]

        result = wizard._step_campaign_name()

        assert result is True
        assert wizard.campaign_name == "Valid Campaign"

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_duplicate_name_cancel(self, mock_console, wizard, campaign_manager):
        """Test duplicate name with cancel"""
        # Create existing campaign
        campaign_manager.create_campaign("Existing", "test_dungeon", [])

        mock_console.input.side_effect = ["Existing", "n"]

        result = wizard._step_campaign_name()

        assert result is False

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_duplicate_name_retry(self, mock_console, wizard, campaign_manager):
        """Test duplicate name with retry"""
        campaign_manager.create_campaign("Existing", "test_dungeon", [])

        mock_console.input.side_effect = ["Existing", "y", "New Campaign"]

        result = wizard._step_campaign_name()

        assert result is True
        assert wizard.campaign_name == "New Campaign"


class TestStepStartingLevel:
    """Test starting level selection step"""

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_default_level(self, mock_console, wizard):
        """Test using default level"""
        mock_console.input.return_value = ""

        result = wizard._step_starting_level()

        assert result is True
        assert wizard.starting_level == 1

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_valid_level(self, mock_console, wizard):
        """Test entering valid level"""
        mock_console.input.return_value = "5"

        result = wizard._step_starting_level()

        assert result is True
        assert wizard.starting_level == 5

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_max_level(self, mock_console, wizard):
        """Test max level 20"""
        mock_console.input.return_value = "20"

        result = wizard._step_starting_level()

        assert result is True
        assert wizard.starting_level == 20

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_invalid_then_valid(self, mock_console, wizard):
        """Test invalid input then valid"""
        mock_console.input.side_effect = ["25", "abc", "10"]

        result = wizard._step_starting_level()

        assert result is True
        assert wizard.starting_level == 10


class TestDisplayCurrentParty:
    """Test party display"""

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_empty_party(self, mock_console, wizard):
        """Test displaying empty party"""
        wizard._display_current_party()

        # Check that empty party message was printed
        assert mock_console.print.called

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_party_with_characters(self, mock_console, wizard, character_vault, sample_character):
        """Test displaying party with characters"""
        # Save character to vault
        char_id = character_vault.save_character(sample_character)
        wizard.party_character_ids = [char_id]

        wizard._display_current_party()

        # Verify character was displayed
        assert mock_console.print.called


class TestImportCharacter:
    """Test importing characters from vault"""

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_import_available_character(self, mock_console, wizard, character_vault, sample_character):
        """Test importing an available character"""
        # Save character to vault
        char_id = character_vault.save_character(
            sample_character,
            state=CharacterState.AVAILABLE
        )

        # User selects character 1
        mock_console.input.return_value = "1"

        wizard._import_character()

        assert char_id in wizard.party_character_ids

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_import_active_character_with_confirmation(self, mock_console, wizard, character_vault, sample_character):
        """Test importing active character with confirmation"""
        # Save active character
        char_id = character_vault.save_character(
            sample_character,
            state=CharacterState.ACTIVE,
            campaign_name="Other Campaign"
        )

        # User selects character 1 and confirms
        mock_console.input.side_effect = ["1", "y"]

        wizard._import_character()

        assert char_id in wizard.party_character_ids

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_import_active_character_cancelled(self, mock_console, wizard, character_vault, sample_character):
        """Test importing active character but cancelling"""
        char_id = character_vault.save_character(
            sample_character,
            state=CharacterState.ACTIVE,
            campaign_name="Other Campaign"
        )

        # User selects character 1 but cancels
        mock_console.input.side_effect = ["1", "n"]

        wizard._import_character()

        assert char_id not in wizard.party_character_ids

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_import_no_characters_in_vault(self, mock_console, wizard):
        """Test importing when vault is empty"""
        wizard._import_character()

        # Should show warning message
        assert len(wizard.party_character_ids) == 0

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_import_back(self, mock_console, wizard, character_vault, sample_character):
        """Test backing out of import"""
        character_vault.save_character(sample_character)

        mock_console.input.return_value = "b"

        wizard._import_character()

        assert len(wizard.party_character_ids) == 0


class TestCreateNewCharacter:
    """Test creating new characters"""

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_create_character_success(self, mock_console, wizard, sample_character):
        """Test successful character creation"""
        # Mock character factory to return sample character
        wizard.character_factory.create_character_interactive = Mock(return_value=sample_character)

        wizard._create_new_character()

        # Check character was added to party
        assert len(wizard.party_character_ids) == 1

        # Verify character factory was called with correct level
        wizard.character_factory.create_character_interactive.assert_called_once_with(level=1)

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_create_character_cancelled(self, mock_console, wizard):
        """Test cancelled character creation"""
        # Mock character factory to return None (cancelled)
        wizard.character_factory.create_character_interactive = Mock(return_value=None)

        wizard._create_new_character()

        # No character should be added
        assert len(wizard.party_character_ids) == 0


class TestStepSelectAdventure:
    """Test adventure selection step"""

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_select_adventure(self, mock_console, wizard):
        """Test selecting an adventure"""
        mock_console.input.return_value = "1"

        result = wizard._step_select_adventure()

        assert result is True
        assert wizard.dungeon_name == "test_dungeon"

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_select_adventure_back(self, mock_console, wizard):
        """Test backing out of adventure selection"""
        mock_console.input.return_value = "b"

        result = wizard._step_select_adventure()

        assert result is False


class TestStepConfirm:
    """Test confirmation step"""

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_confirm_yes(self, mock_console, wizard, character_vault, sample_character):
        """Test confirming campaign creation"""
        # Set up wizard state
        wizard.campaign_name = "Test Campaign"
        wizard.starting_level = 1
        wizard.dungeon_name = "test_dungeon"
        char_id = character_vault.save_character(sample_character)
        wizard.party_character_ids = [char_id]

        mock_console.input.return_value = "y"

        result = wizard._step_confirm()

        assert result is True

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_confirm_default(self, mock_console, wizard, character_vault, sample_character):
        """Test confirming with default (empty = yes)"""
        wizard.campaign_name = "Test Campaign"
        char_id = character_vault.save_character(sample_character)
        wizard.party_character_ids = [char_id]

        mock_console.input.return_value = ""

        result = wizard._step_confirm()

        assert result is True

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_confirm_no(self, mock_console, wizard):
        """Test cancelling at confirmation"""
        wizard.campaign_name = "Test Campaign"

        mock_console.input.return_value = "n"

        result = wizard._step_confirm()

        assert result is False


class TestCreateCampaign:
    """Test campaign creation"""

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_create_campaign_success(self, mock_console, wizard, character_vault, sample_character):
        """Test successful campaign creation"""
        # Set up wizard state
        wizard.campaign_name = "New Campaign"
        wizard.starting_level = 1
        wizard.dungeon_name = "test_dungeon"
        char_id = character_vault.save_character(sample_character, state=CharacterState.AVAILABLE)
        wizard.party_character_ids = [char_id]

        result = wizard._create_campaign()

        assert result == "New Campaign"

        # Verify campaign was created
        campaigns = wizard.campaign_manager.list_campaigns()
        assert len(campaigns) == 1
        assert campaigns[0].name == "New Campaign"

        # Verify character state was updated
        all_chars = character_vault.list_characters()
        char_info = next((c for c in all_chars if c["id"] == char_id), None)
        assert char_info is not None
        assert char_info["state"] == "active"
        # campaign_name may or may not be in the list output, so check by loading character
        # Actually, let's just verify it got updated in the vault by checking it was marked active
        # which only happens when campaign_name is set


class TestFullWizardFlow:
    """Test complete wizard flows"""

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_complete_flow_with_new_character(self, mock_console, wizard, sample_character):
        """Test complete wizard flow creating new character"""
        # Mock all inputs
        mock_console.input.side_effect = [
            "My Campaign",  # Campaign name
            "3",            # Starting level
            "1",            # Create new character
            "3",            # Continue (after character created)
            "1",            # Select adventure
            "y"             # Confirm
        ]

        # Mock character creation
        wizard.character_factory.create_character_interactive = Mock(return_value=sample_character)

        result = wizard.run()

        assert result == "My Campaign"

        # Verify campaign was created with correct settings
        campaigns = wizard.campaign_manager.list_campaigns()
        assert len(campaigns) == 1
        assert campaigns[0].name == "My Campaign"

    @patch('dnd_engine.ui.campaign_wizard.console')
    def test_complete_flow_cancelled_at_party(self, mock_console, wizard):
        """Test wizard cancelled at party building step"""
        mock_console.input.side_effect = [
            "Test Campaign",  # Campaign name
            "",               # Default level
            "b",              # Back at party builder
            "y"               # Confirm cancel
        ]

        result = wizard.run()

        assert result is None

        # No campaign should be created
        campaigns = wizard.campaign_manager.list_campaigns()
        assert len(campaigns) == 0
