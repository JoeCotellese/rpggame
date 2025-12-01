# ABOUTME: Tests for campaign progression system
# ABOUTME: Verifies campaign definition loading, progress tracking, and unlock logic

import json
import tempfile
from pathlib import Path

import pytest

from dnd_engine.core.campaign_progress import (
    CampaignDefinition,
    CampaignProgress,
    CampaignProgressTracker,
)


@pytest.fixture
def sample_campaign_data() -> dict:
    """Sample campaign definition for testing."""
    return {
        "id": "test_campaign",
        "name": "Test Campaign",
        "description": "A test campaign",
        "level_range": "1-3",
        "estimated_playtime": "1-2 hours",
        "starting_room": "dungeon1.entrance",
        "dungeons": {
            "dungeon1": {
                "name": "First Dungeon",
                "order": 1,
                "unlocked_by_default": True,
                "completion_criteria": {
                    "boss_defeated": True,
                    "required_quest_items": ["quest_key"],
                },
                "unlocks": ["dungeon2"],
            },
            "dungeon2": {
                "name": "Second Dungeon",
                "order": 2,
                "unlocked_by_default": False,
                "completion_criteria": {
                    "boss_defeated": True,
                },
                "unlocks": ["dungeon3"],
            },
            "dungeon3": {
                "name": "Final Dungeon",
                "order": 3,
                "unlocked_by_default": False,
                "completion_criteria": {
                    "boss_defeated": True,
                },
                "unlocks": [],
                "final_dungeon": True,
            },
        },
    }


@pytest.fixture
def campaigns_dir(sample_campaign_data) -> Path:
    """Create temporary campaigns directory with test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        campaigns_path = Path(tmpdir)
        campaign_file = campaigns_path / "test_campaign.json"
        with open(campaign_file, "w") as f:
            json.dump(sample_campaign_data, f)
        yield campaigns_path


class TestCampaignDefinition:
    """Tests for CampaignDefinition dataclass."""

    def test_from_dict(self, sample_campaign_data):
        """Test loading campaign definition from dictionary."""
        definition = CampaignDefinition.from_dict(sample_campaign_data)

        assert definition.id == "test_campaign"
        assert definition.name == "Test Campaign"
        assert len(definition.dungeons) == 3
        assert "dungeon1" in definition.dungeons
        assert definition.dungeons["dungeon1"].unlocked_by_default is True
        assert definition.dungeons["dungeon2"].unlocked_by_default is False

    def test_dungeon_completion_criteria(self, sample_campaign_data):
        """Test that completion criteria are parsed correctly."""
        definition = CampaignDefinition.from_dict(sample_campaign_data)

        dungeon1 = definition.dungeons["dungeon1"]
        assert dungeon1.boss_defeated_required is True
        assert dungeon1.required_quest_items == ["quest_key"]

        dungeon2 = definition.dungeons["dungeon2"]
        assert dungeon2.boss_defeated_required is True
        assert dungeon2.required_quest_items == []

    def test_final_dungeon_flag(self, sample_campaign_data):
        """Test that final_dungeon flag is parsed."""
        definition = CampaignDefinition.from_dict(sample_campaign_data)

        assert definition.dungeons["dungeon1"].final_dungeon is False
        assert definition.dungeons["dungeon3"].final_dungeon is True


class TestCampaignProgress:
    """Tests for CampaignProgress dataclass."""

    def test_to_dict_and_from_dict(self):
        """Test serialization round-trip."""
        progress = CampaignProgress(
            campaign_id="test_campaign",
            completed_dungeons=["dungeon1"],
            unlocked_dungeons=["dungeon1", "dungeon2"],
            boss_defeats={"dungeon1": True},
        )

        data = progress.to_dict()
        restored = CampaignProgress.from_dict(data)

        assert restored.campaign_id == progress.campaign_id
        assert restored.completed_dungeons == progress.completed_dungeons
        assert restored.unlocked_dungeons == progress.unlocked_dungeons
        assert restored.boss_defeats == progress.boss_defeats


class TestCampaignProgressTracker:
    """Tests for CampaignProgressTracker class."""

    def test_load_campaign_definition(self, campaigns_dir):
        """Test loading campaign definition from file."""
        tracker = CampaignProgressTracker(campaigns_dir)
        definition = tracker.load_campaign_definition("test_campaign")

        assert definition is not None
        assert definition.id == "test_campaign"
        assert len(definition.dungeons) == 3

    def test_load_nonexistent_campaign(self, campaigns_dir):
        """Test loading non-existent campaign returns None."""
        tracker = CampaignProgressTracker(campaigns_dir)
        definition = tracker.load_campaign_definition("nonexistent")

        assert definition is None

    def test_list_available_campaigns(self, campaigns_dir):
        """Test listing available campaigns."""
        tracker = CampaignProgressTracker(campaigns_dir)
        campaigns = tracker.list_available_campaigns()

        assert len(campaigns) == 1
        assert campaigns[0].id == "test_campaign"

    def test_create_initial_progress(self, campaigns_dir):
        """Test creating initial progress for a campaign."""
        tracker = CampaignProgressTracker(campaigns_dir)
        progress = tracker.create_initial_progress("test_campaign")

        assert progress is not None
        assert progress.campaign_id == "test_campaign"
        assert progress.completed_dungeons == []
        assert "dungeon1" in progress.unlocked_dungeons
        assert "dungeon2" not in progress.unlocked_dungeons

    def test_dungeon_state_tracking(self, campaigns_dir):
        """Test dungeon state (locked/unlocked/completed)."""
        tracker = CampaignProgressTracker(campaigns_dir)
        progress = tracker.create_initial_progress("test_campaign")

        assert tracker.get_dungeon_state(progress, "dungeon1") == "unlocked"
        assert tracker.get_dungeon_state(progress, "dungeon2") == "locked"
        assert tracker.get_dungeon_state(progress, "dungeon3") == "locked"

    def test_check_dungeon_completion_all_criteria(self, campaigns_dir):
        """Test completion check with all criteria met."""
        tracker = CampaignProgressTracker(campaigns_dir)
        progress = tracker.create_initial_progress("test_campaign")

        # Missing boss defeat and quest item
        assert not tracker.check_dungeon_completion(
            progress, "dungeon1", boss_defeated=False, inventory_item_ids=[]
        )

        # Has quest item but no boss defeat
        assert not tracker.check_dungeon_completion(
            progress, "dungeon1", boss_defeated=False, inventory_item_ids=["quest_key"]
        )

        # Boss defeated but no quest item
        assert not tracker.check_dungeon_completion(
            progress, "dungeon1", boss_defeated=True, inventory_item_ids=[]
        )

        # All criteria met
        assert tracker.check_dungeon_completion(
            progress, "dungeon1", boss_defeated=True, inventory_item_ids=["quest_key"]
        )

    def test_complete_dungeon_unlocks_next(self, campaigns_dir):
        """Test that completing a dungeon unlocks the next one."""
        tracker = CampaignProgressTracker(campaigns_dir)
        progress = tracker.create_initial_progress("test_campaign")

        # Record boss defeat
        tracker.record_boss_defeat(progress, "dungeon1")

        # Complete dungeon1 with quest item
        newly_unlocked = tracker.complete_dungeon(
            progress, "dungeon1", inventory_item_ids=["quest_key"]
        )

        assert "dungeon1" in progress.completed_dungeons
        assert "dungeon2" in newly_unlocked
        assert "dungeon2" in progress.unlocked_dungeons
        assert tracker.get_dungeon_state(progress, "dungeon1") == "completed"
        assert tracker.get_dungeon_state(progress, "dungeon2") == "unlocked"

    def test_complete_dungeon_without_criteria_fails(self, campaigns_dir):
        """Test that completing dungeon without criteria doesn't unlock next."""
        tracker = CampaignProgressTracker(campaigns_dir)
        progress = tracker.create_initial_progress("test_campaign")

        # Try to complete without boss defeat
        newly_unlocked = tracker.complete_dungeon(
            progress, "dungeon1", inventory_item_ids=["quest_key"]
        )

        assert newly_unlocked == []
        assert "dungeon1" not in progress.completed_dungeons

    def test_campaign_complete_check(self, campaigns_dir):
        """Test checking if campaign is complete."""
        tracker = CampaignProgressTracker(campaigns_dir)
        progress = tracker.create_initial_progress("test_campaign")

        assert not tracker.is_campaign_complete(progress)

        # Complete all dungeons
        progress.completed_dungeons = ["dungeon1", "dungeon2", "dungeon3"]

        assert tracker.is_campaign_complete(progress)

    def test_get_ordered_dungeons(self, campaigns_dir):
        """Test getting dungeons in order."""
        tracker = CampaignProgressTracker(campaigns_dir)
        ordered = tracker.get_ordered_dungeons("test_campaign")

        assert len(ordered) == 3
        assert ordered[0][0] == "dungeon1"
        assert ordered[1][0] == "dungeon2"
        assert ordered[2][0] == "dungeon3"


class TestRealCampaign:
    """Test with the actual 'the_unquiet_dead' campaign."""

    def test_load_unquiet_dead_campaign(self):
        """Test loading the real campaign file."""
        tracker = CampaignProgressTracker()
        definition = tracker.load_campaign_definition("the_unquiet_dead")

        assert definition is not None
        assert definition.id == "the_unquiet_dead"
        assert definition.name == "The Unquiet Dead"
        assert "the_unquiet_dead_crypt" in definition.dungeons
        assert "cult_hideout" in definition.dungeons
        assert "temple_of_durgon" in definition.dungeons

    def test_unquiet_dead_unlock_chain(self):
        """Test the unlock chain for The Unquiet Dead."""
        tracker = CampaignProgressTracker()
        progress = tracker.create_initial_progress("the_unquiet_dead")

        # Only crypt should be unlocked initially
        assert tracker.is_dungeon_unlocked(progress, "the_unquiet_dead_crypt")
        assert not tracker.is_dungeon_unlocked(progress, "cult_hideout")
        assert not tracker.is_dungeon_unlocked(progress, "temple_of_durgon")

        # Simulate completing crypt with journal
        tracker.record_boss_defeat(progress, "the_unquiet_dead_crypt")
        newly_unlocked = tracker.complete_dungeon(
            progress, "the_unquiet_dead_crypt", inventory_item_ids=["gorgus_journal"]
        )

        assert "cult_hideout" in newly_unlocked
        assert tracker.is_dungeon_unlocked(progress, "cult_hideout")


class TestAllCampaignFilesValid:
    """Test that all campaign JSON files in the campaigns directory are valid."""

    def test_all_campaign_files_load_successfully(self):
        """Test that every campaign JSON file can be loaded without errors."""
        tracker = CampaignProgressTracker()
        campaigns = tracker.list_available_campaigns()

        # Should have at least one campaign
        assert len(campaigns) > 0, "No campaigns found!"

        for campaign in campaigns:
            # Each campaign should have required fields
            assert campaign.id, "Campaign missing id"
            assert campaign.name, f"Campaign {campaign.id} missing name"
            assert campaign.starting_room, f"Campaign {campaign.id} missing starting_room"

            # Dungeons should be a dict, not a list
            assert isinstance(
                campaign.dungeons, dict
            ), f"Campaign {campaign.id}: dungeons should be dict, got {type(campaign.dungeons)}"
            assert len(campaign.dungeons) > 0, f"Campaign {campaign.id} has no dungeons"

            # Each dungeon should have required fields
            for dungeon_id, dungeon in campaign.dungeons.items():
                assert dungeon.name, f"Dungeon {dungeon_id} missing name"
                assert isinstance(
                    dungeon.order, int
                ), f"Dungeon {dungeon_id} order should be int"
                assert isinstance(
                    dungeon.unlocks, list
                ), f"Dungeon {dungeon_id} unlocks should be list"

    def test_all_campaigns_create_valid_progress(self):
        """Test that initial progress can be created for all campaigns."""
        tracker = CampaignProgressTracker()
        campaigns = tracker.list_available_campaigns()

        for campaign in campaigns:
            progress = tracker.create_initial_progress(campaign.id)
            assert progress is not None, f"Failed to create progress for {campaign.id}"
            assert progress.campaign_id == campaign.id

            # Should have at least one unlocked dungeon
            assert (
                len(progress.unlocked_dungeons) > 0
            ), f"Campaign {campaign.id} has no initially unlocked dungeons"

    def test_all_campaigns_have_starting_dungeon(self):
        """Test that all campaigns have a valid starting dungeon."""
        tracker = CampaignProgressTracker()
        campaigns = tracker.list_available_campaigns()

        for campaign in campaigns:
            progress = tracker.create_initial_progress(campaign.id)
            ordered = tracker.get_ordered_dungeons(campaign.id)

            # Find first unlocked dungeon
            starting_dungeon = None
            for dungeon_id, _ in ordered:
                if tracker.is_dungeon_unlocked(progress, dungeon_id):
                    starting_dungeon = dungeon_id
                    break

            assert (
                starting_dungeon is not None
            ), f"Campaign {campaign.id} has no unlocked starting dungeon"


class TestDungeonCompletionDetection:
    """Tests for dungeon completion detection in GameState."""

    def test_boss_defeat_recorded_in_boss_room(self, campaigns_dir, sample_campaign_data):
        """Test that boss defeat is recorded when combat ends in boss_room."""
        from unittest.mock import MagicMock, patch

        from dnd_engine.core.character import Character, CharacterClass
        from dnd_engine.core.creature import Abilities
        from dnd_engine.core.party import Party
        from dnd_engine.utils.events import EventType

        # Create a character
        abilities = Abilities(10, 10, 10, 10, 10, 10)
        char = Character(
            name="Test Hero",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=10,
            current_hp=10,
        )
        party = Party([char])

        # Create campaign progress
        tracker = CampaignProgressTracker(campaigns_dir)
        progress = tracker.create_initial_progress("test_campaign")

        # Mock data loader and dungeon
        mock_loader = MagicMock()
        mock_loader.load_dungeon.return_value = {
            "id": "dungeon1",
            "name": "First Dungeon",
            "start_room": "dungeon1.entrance",
            "rooms": {
                "dungeon1.entrance": {
                    "id": "dungeon1.entrance",
                    "name": "Dungeon Entrance",
                    "enemies": [],
                    "exits": {"north": "dungeon1.boss_room"},
                },
                "dungeon1.boss_room": {
                    "id": "dungeon1.boss_room",
                    "name": "Boss Chamber",
                    "boss_room": True,
                    "enemies": [],
                    "exits": {},
                },
            },
        }
        mock_loader.load_monsters.return_value = {}
        mock_loader.data_path = campaigns_dir.parent

        # Patch GameState to use our mocks
        with patch.object(
            CampaignProgressTracker, "__init__", lambda self, path=None: None
        ):
            from dnd_engine.core.game_state import GameState

            # Create game state with campaign progress
            game_state = GameState(
                party=party,
                dungeon_name="dungeon1",
                data_loader=mock_loader,
                campaign_id="test_campaign",
                campaign_progress=progress,
            )

            # Manually set up campaign tracker
            game_state.campaign_tracker = tracker
            game_state.current_room_id = "dungeon1.boss_room"

            # Track events
            events_emitted = []

            def capture_event(event):
                events_emitted.append(event.type)

            game_state.event_bus.subscribe(EventType.BOSS_DEFEATED, capture_event)

            # Call boss defeat handler with mock enemy IDs
            game_state._handle_boss_defeat(["test_boss"])

            # Verify boss defeat was recorded
            assert progress.boss_defeats.get("dungeon1") is True
            assert EventType.BOSS_DEFEATED in events_emitted

    def test_dungeon_completion_unlocks_next(self, campaigns_dir, sample_campaign_data):
        """Test that completing a dungeon unlocks the next one."""
        tracker = CampaignProgressTracker(campaigns_dir)
        progress = tracker.create_initial_progress("test_campaign")

        # Record boss defeat
        tracker.record_boss_defeat(progress, "dungeon1")

        # Complete with required quest item
        newly_unlocked = tracker.complete_dungeon(
            progress, "dungeon1", inventory_item_ids=["quest_key"]
        )

        assert "dungeon1" in progress.completed_dungeons
        assert "dungeon2" in newly_unlocked
        assert "dungeon2" in progress.unlocked_dungeons

    def test_dungeon_not_completed_without_quest_item(
        self, campaigns_dir, sample_campaign_data
    ):
        """Test that dungeon isn't completed without required quest item."""
        tracker = CampaignProgressTracker(campaigns_dir)
        progress = tracker.create_initial_progress("test_campaign")

        # Record boss defeat but no quest item
        tracker.record_boss_defeat(progress, "dungeon1")

        # Try to complete without quest item
        newly_unlocked = tracker.complete_dungeon(
            progress, "dungeon1", inventory_item_ids=[]
        )

        assert "dungeon1" not in progress.completed_dungeons
        assert newly_unlocked == []
