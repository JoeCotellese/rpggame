# ABOUTME: Unit tests for auto-save functionality
# ABOUTME: Tests auto-save triggers, quick-save, and campaign integration

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from dnd_engine.ui.cli import CLI
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.campaign_manager import CampaignManager
from dnd_engine.utils.events import EventBus, Event, EventType


@pytest.fixture
def temp_campaign_dir(tmp_path):
    """Create temporary campaign directory"""
    campaign_dir = tmp_path / "campaigns"
    campaign_dir.mkdir()
    return campaign_dir


@pytest.fixture
def campaign_manager(temp_campaign_dir):
    """Create CampaignManager with temp directory"""
    return CampaignManager(campaigns_dir=temp_campaign_dir)


@pytest.fixture
def sample_character():
    """Create a sample character for testing"""
    return Character(
        name="Test Character",
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
def game_state(sample_character):
    """Create game state with party"""
    party = Party([sample_character])
    event_bus = EventBus()

    # Mock the data loader to avoid file dependencies
    with patch('dnd_engine.core.game_state.DataLoader') as mock_loader_class:
        mock_loader = Mock()
        mock_loader.load_dungeon.return_value = {
            "name": "Test Dungeon",
            "start_room": "room_1",
            "rooms": {
                "room_1": {
                    "name": "Test Room",
                    "description": "A test room",
                    "exits": []
                }
            }
        }
        mock_loader_class.return_value = mock_loader

        # Create game state with minimal dungeon
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus
        )

    game_state.current_room_id = "room_1"

    return game_state


@pytest.fixture
def cli_with_campaign(game_state, campaign_manager, temp_campaign_dir):
    """Create CLI with campaign integration"""
    # Create a campaign first
    campaign_name = "Test Campaign"
    campaign_manager.create_campaign(
        name=campaign_name,
        dungeon_name="test_dungeon",
        party_character_ids=[game_state.party.characters[0].name]
    )

    cli = CLI(
        game_state=game_state,
        campaign_manager=campaign_manager,
        campaign_name=campaign_name,
        auto_save_enabled=True,
        llm_enhancer=None
    )

    return cli


class TestAutoSaveIntegration:
    """Test auto-save integration with CampaignManager"""

    def test_cli_init_with_campaign_manager(self, cli_with_campaign):
        """Test CLI initializes with campaign manager"""
        assert cli_with_campaign.campaign_manager is not None
        assert cli_with_campaign.campaign_name == "Test Campaign"
        assert cli_with_campaign.auto_save_enabled is True

    def test_auto_save_creates_slot(self, cli_with_campaign, campaign_manager):
        """Test auto-save creates auto slot"""
        # Trigger auto-save
        cli_with_campaign._auto_save("test_trigger")

        # Check that auto save was created
        save_slots = campaign_manager.list_save_slots("Test Campaign")
        auto_saves = [s for s in save_slots if s.save_type == "auto"]

        assert len(auto_saves) == 1
        assert auto_saves[0].slot_name == "save_auto"

    def test_auto_save_disabled(self, game_state, campaign_manager):
        """Test auto-save respects disabled flag"""
        campaign_name = "Test Campaign 2"
        campaign_manager.create_campaign(
            name=campaign_name,
            dungeon_name="test_dungeon",
            party_character_ids=[]
        )

        cli = CLI(
            game_state=game_state,
            campaign_manager=campaign_manager,
            campaign_name=campaign_name,
            auto_save_enabled=False,
            llm_enhancer=None
        )

        # Trigger auto-save
        cli._auto_save("test_trigger")

        # Should not create save
        save_slots = campaign_manager.list_save_slots(campaign_name)
        assert len(save_slots) == 0


class TestAutoSaveTriggers:
    """Test that auto-save triggers on correct events"""

    def test_combat_end_triggers_auto_save(self, cli_with_campaign, game_state):
        """Test combat end triggers auto-save"""
        event = Event(
            type=EventType.COMBAT_END,
            data={"xp_gained": 100, "xp_per_character": 50}
        )

        # Emit combat end event
        game_state.event_bus.emit(event)

        # Check auto-save was triggered
        save_slots = cli_with_campaign.campaign_manager.list_save_slots("Test Campaign")
        auto_saves = [s for s in save_slots if s.save_type == "auto"]
        assert len(auto_saves) == 1

    def test_room_enter_triggers_auto_save(self, cli_with_campaign, game_state):
        """Test room enter triggers auto-save"""
        event = Event(
            type=EventType.ROOM_ENTER,
            data={"room_id": "room_2"}
        )

        # Emit room enter event
        game_state.event_bus.emit(event)

        # Check auto-save was triggered
        save_slots = cli_with_campaign.campaign_manager.list_save_slots("Test Campaign")
        auto_saves = [s for s in save_slots if s.save_type == "auto"]
        assert len(auto_saves) == 1

    def test_level_up_triggers_auto_save(self, cli_with_campaign, game_state):
        """Test level up triggers auto-save"""
        event = Event(
            type=EventType.LEVEL_UP,
            data={"character": "Test Character", "new_level": 2, "hp_increase": 7}
        )

        # Emit level up event
        game_state.event_bus.emit(event)

        # Check auto-save was triggered
        save_slots = cli_with_campaign.campaign_manager.list_save_slots("Test Campaign")
        auto_saves = [s for s in save_slots if s.save_type == "auto"]
        assert len(auto_saves) == 1

    def test_long_rest_triggers_auto_save(self, cli_with_campaign, game_state):
        """Test long rest triggers auto-save"""
        event = Event(
            type=EventType.LONG_REST,
            data={"party": ["Test Character"], "rest_type": "long"}
        )

        # Emit long rest event
        game_state.event_bus.emit(event)

        # Check auto-save was triggered
        save_slots = cli_with_campaign.campaign_manager.list_save_slots("Test Campaign")
        auto_saves = [s for s in save_slots if s.save_type == "auto"]
        assert len(auto_saves) == 1

    def test_combat_fled_triggers_auto_save(self, cli_with_campaign, game_state):
        """Test combat fled triggers auto-save"""
        event = Event(
            type=EventType.COMBAT_FLED,
            data={"opportunity_attacks": 2}
        )

        # Emit combat fled event
        game_state.event_bus.emit(event)

        # Check auto-save was triggered
        save_slots = cli_with_campaign.campaign_manager.list_save_slots("Test Campaign")
        auto_saves = [s for s in save_slots if s.save_type == "auto"]
        assert len(auto_saves) == 1


class TestQuickSave:
    """Test quick-save functionality"""

    def test_quick_save_creates_slot(self, cli_with_campaign, campaign_manager):
        """Test quick-save creates quick slot"""
        cli_with_campaign.handle_quick_save()

        # Check that quick save was created
        save_slots = campaign_manager.list_save_slots("Test Campaign")
        quick_saves = [s for s in save_slots if s.save_type == "quick"]

        assert len(quick_saves) == 1
        assert quick_saves[0].slot_name == "save_quick"

    def test_quick_save_overwrites_previous(self, cli_with_campaign, campaign_manager):
        """Test quick-save overwrites previous quick-save"""
        # Create first quick-save
        cli_with_campaign.handle_quick_save()

        # Create second quick-save
        cli_with_campaign.handle_quick_save()

        # Should still only be one quick save
        save_slots = campaign_manager.list_save_slots("Test Campaign")
        quick_saves = [s for s in save_slots if s.save_type == "quick"]
        assert len(quick_saves) == 1

    @patch('dnd_engine.ui.cli.console')
    def test_quick_save_command_in_exploration(self, mock_console, cli_with_campaign):
        """Test 'qs' command triggers quick-save"""
        # Mock to prevent actual input loop
        cli_with_campaign.running = False

        # Process quick-save command
        cli_with_campaign.process_exploration_command("qs")

        # Check that quick save was created
        save_slots = cli_with_campaign.campaign_manager.list_save_slots("Test Campaign")
        quick_saves = [s for s in save_slots if s.save_type == "quick"]
        assert len(quick_saves) == 1


class TestManualSave:
    """Test manual named save functionality"""

    @patch('builtins.input', return_value="My Save")
    def test_manual_save_creates_slot(self, mock_input, cli_with_campaign, campaign_manager):
        """Test manual save creates named slot"""
        cli_with_campaign.handle_save()

        # Check that manual save was created
        save_slots = campaign_manager.list_save_slots("Test Campaign")
        manual_saves = [s for s in save_slots if s.save_type == "manual"]

        assert len(manual_saves) == 1
        assert "my_save" in manual_saves[0].slot_name.lower()

    @patch('builtins.input', return_value="")
    def test_manual_save_cancelled(self, mock_input, cli_with_campaign, campaign_manager):
        """Test manual save can be cancelled"""
        cli_with_campaign.handle_save()

        # Should not create save
        save_slots = campaign_manager.list_save_slots("Test Campaign")
        manual_saves = [s for s in save_slots if s.save_type == "manual"]
        assert len(manual_saves) == 0


class TestSaveSlotPriority:
    """Test that different save types coexist"""

    @patch('builtins.input', return_value="Manual Save 1")
    def test_multiple_save_types_coexist(self, mock_input, cli_with_campaign, campaign_manager):
        """Test auto, quick, and manual saves coexist"""
        # Create auto-save
        cli_with_campaign._auto_save("test")

        # Create quick-save
        cli_with_campaign.handle_quick_save()

        # Create manual save
        cli_with_campaign.handle_save()

        # Check all three exist
        save_slots = campaign_manager.list_save_slots("Test Campaign")
        assert len(save_slots) == 3

        save_types = {slot.save_type for slot in save_slots}
        assert save_types == {"auto", "quick", "manual"}
