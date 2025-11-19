# Integration tests for CampaignManager

import pytest
import json
from pathlib import Path
from datetime import datetime
from dnd_engine.core.campaign_manager import CampaignManager
from dnd_engine.core.campaign import Campaign
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.utils.events import EventBus
from dnd_engine.rules.loader import DataLoader
from dnd_engine.core.dice import DiceRoller


@pytest.fixture
def temp_campaigns_dir(tmp_path):
    """Create temporary campaigns directory."""
    return tmp_path / "campaigns"


@pytest.fixture
def campaign_manager(temp_campaigns_dir):
    """Create CampaignManager with temporary directory."""
    return CampaignManager(campaigns_dir=temp_campaigns_dir)


@pytest.fixture
def sample_character():
    """Create a sample character for testing."""
    abilities = Abilities(
        strength=16,
        dexterity=14,
        constitution=15,
        intelligence=10,
        wisdom=12,
        charisma=8
    )

    return Character(
        name="Test Hero",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=12,
        ac=16,
        xp=0
    )


@pytest.fixture
def sample_game_state(sample_character):
    """Create a sample game state for testing."""
    party = Party([sample_character])
    event_bus = EventBus()
    data_loader = DataLoader()
    dice_roller = DiceRoller()

    # Use an existing dungeon file
    game_state = GameState(
        party=party,
        dungeon_name="goblin_warren",  # Use existing dungeon
        event_bus=event_bus,
        data_loader=data_loader,
        dice_roller=dice_roller
    )

    return game_state


class TestCampaignManagerBasics:
    """Test basic CampaignManager functionality."""

    def test_create_campaign_manager(self, campaign_manager, temp_campaigns_dir):
        """Test creating a campaign manager creates directory structure."""
        assert temp_campaigns_dir.exists()
        assert temp_campaigns_dir.is_dir()

    def test_create_simple_campaign(self, campaign_manager, temp_campaigns_dir):
        """Test creating a basic campaign."""
        campaign = campaign_manager.create_campaign(name="Test Campaign")

        assert campaign.name == "Test Campaign"
        assert campaign.playtime_seconds == 0
        assert campaign.current_dungeon is None
        assert campaign.party_character_ids == []

        # Verify directory structure
        campaign_dir = temp_campaigns_dir / "test_campaign"
        assert campaign_dir.exists()
        assert (campaign_dir / "saves").exists()
        assert (campaign_dir / "party").exists()
        assert (campaign_dir / "campaign.json").exists()

    def test_create_campaign_with_metadata(self, campaign_manager):
        """Test creating campaign with dungeon and party."""
        campaign = campaign_manager.create_campaign(
            name="Full Campaign",
            dungeon_name="tomb_of_horrors",
            party_character_ids=["aria", "zephyr"]
        )

        assert campaign.name == "Full Campaign"
        assert campaign.current_dungeon == "tomb_of_horrors"
        assert campaign.party_character_ids == ["aria", "zephyr"]

    def test_create_duplicate_campaign_raises_error(self, campaign_manager):
        """Test that creating duplicate campaign name raises error."""
        campaign_manager.create_campaign(name="Duplicate Test")

        with pytest.raises(ValueError, match="already exists"):
            campaign_manager.create_campaign(name="Duplicate Test")

    def test_create_campaign_empty_name_raises_error(self, campaign_manager):
        """Test that empty campaign name raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            campaign_manager.create_campaign(name="")

        with pytest.raises(ValueError, match="cannot be empty"):
            campaign_manager.create_campaign(name="   ")

    def test_sanitize_campaign_name(self, campaign_manager, temp_campaigns_dir):
        """Test that campaign names are sanitized for filesystem."""
        campaign = campaign_manager.create_campaign(name="Test: Campaign!")

        # Directory should have sanitized name
        campaign_dir = temp_campaigns_dir / "test_campaign"
        assert campaign_dir.exists()

        # But campaign.name should preserve original
        assert campaign.name == "Test: Campaign!"

    def test_load_campaign(self, campaign_manager):
        """Test loading campaign metadata."""
        created = campaign_manager.create_campaign(
            name="Load Test",
            dungeon_name="test_dungeon"
        )

        loaded = campaign_manager.load_campaign("Load Test")

        assert loaded.name == created.name
        assert loaded.current_dungeon == created.current_dungeon
        assert abs((loaded.created_at - created.created_at).total_seconds()) < 1

    def test_load_nonexistent_campaign_raises_error(self, campaign_manager):
        """Test loading campaign that doesn't exist."""
        with pytest.raises(FileNotFoundError, match="not found"):
            campaign_manager.load_campaign("Nonexistent")

    def test_list_campaigns_empty(self, campaign_manager):
        """Test listing campaigns when none exist."""
        campaigns = campaign_manager.list_campaigns()
        assert campaigns == []

    def test_list_campaigns_single(self, campaign_manager):
        """Test listing a single campaign."""
        campaign_manager.create_campaign(name="Test Campaign")

        campaigns = campaign_manager.list_campaigns()

        assert len(campaigns) == 1
        assert campaigns[0].name == "Test Campaign"

    def test_list_campaigns_multiple(self, campaign_manager):
        """Test listing multiple campaigns."""
        campaign_manager.create_campaign(name="Campaign 1")
        campaign_manager.create_campaign(name="Campaign 2")
        campaign_manager.create_campaign(name="Campaign 3")

        campaigns = campaign_manager.list_campaigns()

        assert len(campaigns) == 3
        names = [c.name for c in campaigns]
        assert "Campaign 1" in names
        assert "Campaign 2" in names
        assert "Campaign 3" in names

    def test_list_campaigns_sorted_by_last_played(self, campaign_manager):
        """Test that campaigns are sorted by most recently played."""
        import time

        campaign_manager.create_campaign(name="Old Campaign")
        time.sleep(0.1)  # Ensure different timestamps
        campaign_manager.create_campaign(name="New Campaign")

        campaigns = campaign_manager.list_campaigns()

        # Most recent should be first
        assert campaigns[0].name == "New Campaign"
        assert campaigns[1].name == "Old Campaign"

    def test_delete_campaign(self, campaign_manager, temp_campaigns_dir):
        """Test deleting a campaign."""
        campaign_manager.create_campaign(name="Delete Me")

        campaign_dir = temp_campaigns_dir / "delete_me"
        assert campaign_dir.exists()

        result = campaign_manager.delete_campaign("Delete Me")
        assert result is True
        assert not campaign_dir.exists()

    def test_delete_nonexistent_campaign(self, campaign_manager):
        """Test deleting campaign that doesn't exist."""
        result = campaign_manager.delete_campaign("Nonexistent")
        assert result is False

    def test_get_most_recent_campaign_empty(self, campaign_manager):
        """Test getting most recent campaign when none exist."""
        recent = campaign_manager.get_most_recent_campaign()
        assert recent is None

    def test_get_most_recent_campaign(self, campaign_manager):
        """Test getting most recent campaign."""
        import time

        campaign_manager.create_campaign(name="Old")
        time.sleep(0.1)
        campaign_manager.create_campaign(name="Recent")

        recent = campaign_manager.get_most_recent_campaign()

        assert recent is not None
        assert recent.name == "Recent"


class TestCampaignManagerSaveLoad:
    """Test save/load functionality with CampaignManager."""

    def test_save_campaign_state_auto(self, campaign_manager, sample_game_state):
        """Test saving game state to auto-save slot."""
        campaign = campaign_manager.create_campaign(name="Save Test")

        save_path = campaign_manager.save_campaign_state(
            campaign_name="Save Test",
            game_state=sample_game_state,
            slot_name="auto",
            save_type="auto"
        )

        assert save_path.exists()
        assert save_path.name == "save_auto.json"

    def test_save_campaign_state_quick(self, campaign_manager, sample_game_state):
        """Test saving game state to quick-save slot."""
        campaign_manager.create_campaign(name="Quick Save Test")

        save_path = campaign_manager.save_campaign_state(
            campaign_name="Quick Save Test",
            game_state=sample_game_state,
            slot_name="quick",
            save_type="quick"
        )

        assert save_path.exists()
        assert save_path.name == "save_quick.json"

    def test_save_campaign_state_custom(self, campaign_manager, sample_game_state):
        """Test saving game state to custom named slot."""
        campaign_manager.create_campaign(name="Custom Save Test")

        save_path = campaign_manager.save_campaign_state(
            campaign_name="Custom Save Test",
            game_state=sample_game_state,
            slot_name="before_boss_fight",
            save_type="manual"
        )

        assert save_path.exists()
        assert "before_boss_fight" in save_path.name

    def test_save_updates_campaign_metadata(self, campaign_manager, sample_game_state):
        """Test that saving updates campaign metadata."""
        campaign = campaign_manager.create_campaign(name="Metadata Test")
        original_last_played = campaign.last_played

        import time
        time.sleep(0.1)  # Ensure timestamp difference

        campaign_manager.save_campaign_state(
            campaign_name="Metadata Test",
            game_state=sample_game_state,
            slot_name="auto"
        )

        # Reload campaign metadata
        updated = campaign_manager.load_campaign("Metadata Test")

        assert updated.last_played > original_last_played
        assert updated.current_dungeon == sample_game_state.dungeon_name
        assert updated.current_room == sample_game_state.current_room_id

    def test_load_campaign_state_auto(self, campaign_manager, sample_game_state):
        """Test loading game state from auto-save slot."""
        campaign_manager.create_campaign(name="Load Test")

        # Save first
        campaign_manager.save_campaign_state(
            campaign_name="Load Test",
            game_state=sample_game_state,
            slot_name="auto"
        )

        # Load
        loaded_state = campaign_manager.load_campaign_state(
            campaign_name="Load Test",
            slot_name="auto"
        )

        assert loaded_state is not None
        assert loaded_state.dungeon_name == sample_game_state.dungeon_name
        assert len(loaded_state.party.characters) == len(sample_game_state.party.characters)

    def test_load_campaign_state_updates_last_played(self, campaign_manager, sample_game_state):
        """Test that loading updates last_played timestamp."""
        campaign = campaign_manager.create_campaign(name="Timestamp Test")

        campaign_manager.save_campaign_state(
            campaign_name="Timestamp Test",
            game_state=sample_game_state,
            slot_name="auto"
        )

        original_last_played = campaign.last_played

        import time
        time.sleep(0.1)

        # Load the save
        campaign_manager.load_campaign_state(
            campaign_name="Timestamp Test",
            slot_name="auto"
        )

        # Check metadata was updated
        updated = campaign_manager.load_campaign("Timestamp Test")
        assert updated.last_played > original_last_played

    def test_list_save_slots_empty(self, campaign_manager):
        """Test listing save slots when none exist."""
        campaign_manager.create_campaign(name="No Saves")

        slots = campaign_manager.list_save_slots("No Saves")
        assert slots == []

    def test_list_save_slots_with_saves(self, campaign_manager, sample_game_state):
        """Test listing save slots."""
        campaign_manager.create_campaign(name="Multiple Saves")

        # Create multiple saves
        campaign_manager.save_campaign_state(
            campaign_name="Multiple Saves",
            game_state=sample_game_state,
            slot_name="auto",
            save_type="auto"
        )

        campaign_manager.save_campaign_state(
            campaign_name="Multiple Saves",
            game_state=sample_game_state,
            slot_name="quick",
            save_type="quick"
        )

        campaign_manager.save_campaign_state(
            campaign_name="Multiple Saves",
            game_state=sample_game_state,
            slot_name="manual_save",
            save_type="manual"
        )

        slots = campaign_manager.list_save_slots("Multiple Saves")

        assert len(slots) == 3

        # Verify we have all types
        save_types = [slot.save_type for slot in slots]
        assert "auto" in save_types
        assert "quick" in save_types
        assert "manual" in save_types

    def test_save_slot_sorting(self, campaign_manager, sample_game_state):
        """Test that save slots are sorted: auto, quick, then manual by date."""
        campaign_manager.create_campaign(name="Sort Test")

        import time

        # Create in reverse order to test sorting
        campaign_manager.save_campaign_state(
            campaign_name="Sort Test",
            game_state=sample_game_state,
            slot_name="manual_1",
            save_type="manual"
        )

        time.sleep(0.1)

        campaign_manager.save_campaign_state(
            campaign_name="Sort Test",
            game_state=sample_game_state,
            slot_name="quick",
            save_type="quick"
        )

        time.sleep(0.1)

        campaign_manager.save_campaign_state(
            campaign_name="Sort Test",
            game_state=sample_game_state,
            slot_name="auto",
            save_type="auto"
        )

        slots = campaign_manager.list_save_slots("Sort Test")

        # Auto should be first, quick second, manual third
        assert slots[0].save_type == "auto"
        assert slots[1].save_type == "quick"
        assert slots[2].save_type == "manual"


class TestCampaignManagerEdgeCases:
    """Test edge cases and error handling."""

    def test_save_to_nonexistent_campaign(self, campaign_manager, sample_game_state):
        """Test saving to campaign that doesn't exist."""
        with pytest.raises(FileNotFoundError, match="not found"):
            campaign_manager.save_campaign_state(
                campaign_name="Nonexistent",
                game_state=sample_game_state
            )

    def test_load_from_nonexistent_campaign(self, campaign_manager):
        """Test loading from campaign that doesn't exist."""
        with pytest.raises(FileNotFoundError, match="not found"):
            campaign_manager.load_campaign_state(campaign_name="Nonexistent")

    def test_list_slots_for_nonexistent_campaign(self, campaign_manager):
        """Test listing slots for campaign that doesn't exist."""
        with pytest.raises(FileNotFoundError, match="not found"):
            campaign_manager.list_save_slots("Nonexistent")

    def test_campaign_name_with_spaces(self, campaign_manager, temp_campaigns_dir):
        """Test campaign with spaces in name."""
        campaign = campaign_manager.create_campaign(name="My Great Campaign")

        # Directory should use underscores
        campaign_dir = temp_campaigns_dir / "my_great_campaign"
        assert campaign_dir.exists()

        # But name should preserve spaces
        assert campaign.name == "My Great Campaign"

        # Should be able to load with original name
        loaded = campaign_manager.load_campaign("My Great Campaign")
        assert loaded.name == "My Great Campaign"

    def test_campaign_name_with_special_characters(self, campaign_manager):
        """Test campaign with special characters."""
        campaign = campaign_manager.create_campaign(name="Test: Campaign / 2024")

        # Should sanitize for directory but preserve original name
        assert campaign.name == "Test: Campaign / 2024"

        # Should be loadable
        loaded = campaign_manager.load_campaign("Test: Campaign / 2024")
        assert loaded.name == "Test: Campaign / 2024"
