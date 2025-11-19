# Unit tests for Campaign data model

import pytest
from datetime import datetime, timedelta
from dnd_engine.core.campaign import Campaign, SaveSlotMetadata


class TestCampaign:
    """Test Campaign data model."""

    def test_create_campaign(self):
        """Test creating a campaign with minimal data."""
        now = datetime.now()
        campaign = Campaign(
            name="Test Campaign",
            created_at=now,
            last_played=now
        )

        assert campaign.name == "Test Campaign"
        assert campaign.created_at == now
        assert campaign.last_played == now
        assert campaign.playtime_seconds == 0
        assert campaign.current_dungeon is None
        assert campaign.current_room is None
        assert campaign.party_character_ids == []
        assert campaign.save_version == "1.0.0"

    def test_create_campaign_with_all_data(self):
        """Test creating a campaign with all fields populated."""
        now = datetime.now()
        campaign = Campaign(
            name="Full Campaign",
            created_at=now,
            last_played=now,
            playtime_seconds=3600,
            current_dungeon="tomb_of_horrors",
            current_room="room_12",
            party_character_ids=["aria", "zephyr"],
            save_version="1.0.0"
        )

        assert campaign.name == "Full Campaign"
        assert campaign.playtime_seconds == 3600
        assert campaign.current_dungeon == "tomb_of_horrors"
        assert campaign.current_room == "room_12"
        assert campaign.party_character_ids == ["aria", "zephyr"]

    def test_to_dict(self):
        """Test serializing campaign to dictionary."""
        now = datetime.now()
        campaign = Campaign(
            name="Test Campaign",
            created_at=now,
            last_played=now,
            playtime_seconds=7200,
            current_dungeon="lost_mine",
            current_room="room_5",
            party_character_ids=["thorin"],
            save_version="1.0.0"
        )

        data = campaign.to_dict()

        assert data["name"] == "Test Campaign"
        assert data["created_at"] == now.isoformat()
        assert data["last_played"] == now.isoformat()
        assert data["playtime_seconds"] == 7200
        assert data["current_dungeon"] == "lost_mine"
        assert data["current_room"] == "room_5"
        assert data["party_character_ids"] == ["thorin"]
        assert data["save_version"] == "1.0.0"

    def test_from_dict(self):
        """Test deserializing campaign from dictionary."""
        now = datetime.now()
        data = {
            "name": "Test Campaign",
            "created_at": now.isoformat(),
            "last_played": now.isoformat(),
            "playtime_seconds": 1800,
            "current_dungeon": "tomb",
            "current_room": "room_1",
            "party_character_ids": ["aria", "zephyr"],
            "save_version": "1.0.0"
        }

        campaign = Campaign.from_dict(data)

        assert campaign.name == "Test Campaign"
        assert abs((campaign.created_at - now).total_seconds()) < 1
        assert abs((campaign.last_played - now).total_seconds()) < 1
        assert campaign.playtime_seconds == 1800
        assert campaign.current_dungeon == "tomb"
        assert campaign.current_room == "room_1"
        assert campaign.party_character_ids == ["aria", "zephyr"]
        assert campaign.save_version == "1.0.0"

    def test_from_dict_minimal(self):
        """Test deserializing campaign with minimal data."""
        now = datetime.now()
        data = {
            "name": "Minimal Campaign",
            "created_at": now.isoformat(),
            "last_played": now.isoformat()
        }

        campaign = Campaign.from_dict(data)

        assert campaign.name == "Minimal Campaign"
        assert campaign.playtime_seconds == 0
        assert campaign.current_dungeon is None
        assert campaign.current_room is None
        assert campaign.party_character_ids == []
        assert campaign.save_version == "1.0.0"

    def test_get_playtime_display_seconds(self):
        """Test playtime display for seconds."""
        campaign = Campaign(
            name="Test",
            created_at=datetime.now(),
            last_played=datetime.now(),
            playtime_seconds=45
        )
        assert campaign.get_playtime_display() == "45s"

    def test_get_playtime_display_minutes(self):
        """Test playtime display for minutes only."""
        campaign = Campaign(
            name="Test",
            created_at=datetime.now(),
            last_played=datetime.now(),
            playtime_seconds=180  # 3 minutes
        )
        assert campaign.get_playtime_display() == "3m"

    def test_get_playtime_display_hours_minutes(self):
        """Test playtime display for hours and minutes."""
        campaign = Campaign(
            name="Test",
            created_at=datetime.now(),
            last_played=datetime.now(),
            playtime_seconds=22980  # 6h 23m
        )
        assert campaign.get_playtime_display() == "6h 23m"

    def test_get_playtime_display_hours_only(self):
        """Test playtime display for exact hours."""
        campaign = Campaign(
            name="Test",
            created_at=datetime.now(),
            last_played=datetime.now(),
            playtime_seconds=10800  # 3h
        )
        assert campaign.get_playtime_display() == "3h"

    def test_get_playtime_display_days_hours(self):
        """Test playtime display for days and hours."""
        campaign = Campaign(
            name="Test",
            created_at=datetime.now(),
            last_played=datetime.now(),
            playtime_seconds=97200  # 1d 3h
        )
        assert campaign.get_playtime_display() == "1d 3h"

    def test_get_playtime_display_days_only(self):
        """Test playtime display for exact days."""
        campaign = Campaign(
            name="Test",
            created_at=datetime.now(),
            last_played=datetime.now(),
            playtime_seconds=172800  # 2d
        )
        assert campaign.get_playtime_display() == "2d"

    def test_get_last_played_display_just_now(self):
        """Test last played display for very recent."""
        campaign = Campaign(
            name="Test",
            created_at=datetime.now(),
            last_played=datetime.now()
        )
        assert campaign.get_last_played_display() == "just now"

    def test_get_last_played_display_minutes(self):
        """Test last played display for minutes ago."""
        campaign = Campaign(
            name="Test",
            created_at=datetime.now(),
            last_played=datetime.now() - timedelta(minutes=15)
        )
        assert campaign.get_last_played_display() == "15 minutes ago"

    def test_get_last_played_display_one_minute(self):
        """Test last played display for one minute (singular)."""
        campaign = Campaign(
            name="Test",
            created_at=datetime.now(),
            last_played=datetime.now() - timedelta(minutes=1)
        )
        assert campaign.get_last_played_display() == "1 minute ago"

    def test_get_last_played_display_hours(self):
        """Test last played display for hours ago."""
        campaign = Campaign(
            name="Test",
            created_at=datetime.now(),
            last_played=datetime.now() - timedelta(hours=3)
        )
        assert campaign.get_last_played_display() == "3 hours ago"

    def test_get_last_played_display_one_hour(self):
        """Test last played display for one hour (singular)."""
        campaign = Campaign(
            name="Test",
            created_at=datetime.now(),
            last_played=datetime.now() - timedelta(hours=1)
        )
        assert campaign.get_last_played_display() == "1 hour ago"

    def test_get_last_played_display_days(self):
        """Test last played display for days ago."""
        campaign = Campaign(
            name="Test",
            created_at=datetime.now(),
            last_played=datetime.now() - timedelta(days=5)
        )
        assert campaign.get_last_played_display() == "5 days ago"

    def test_get_last_played_display_one_day(self):
        """Test last played display for one day (singular)."""
        campaign = Campaign(
            name="Test",
            created_at=datetime.now(),
            last_played=datetime.now() - timedelta(days=1)
        )
        assert campaign.get_last_played_display() == "1 day ago"

    def test_get_last_played_display_months(self):
        """Test last played display for months ago."""
        campaign = Campaign(
            name="Test",
            created_at=datetime.now(),
            last_played=datetime.now() - timedelta(days=90)  # ~3 months
        )
        assert campaign.get_last_played_display() == "3 months ago"

    def test_get_last_played_display_years(self):
        """Test last played display for years ago."""
        campaign = Campaign(
            name="Test",
            created_at=datetime.now(),
            last_played=datetime.now() - timedelta(days=730)  # ~2 years
        )
        assert campaign.get_last_played_display() == "2 years ago"

    def test_roundtrip_serialization(self):
        """Test that to_dict -> from_dict preserves all data."""
        now = datetime.now()
        original = Campaign(
            name="Roundtrip Test",
            created_at=now,
            last_played=now,
            playtime_seconds=12345,
            current_dungeon="test_dungeon",
            current_room="test_room",
            party_character_ids=["char1", "char2", "char3"],
            save_version="1.0.0"
        )

        # Serialize and deserialize
        data = original.to_dict()
        restored = Campaign.from_dict(data)

        # Verify all fields match
        assert restored.name == original.name
        assert abs((restored.created_at - original.created_at).total_seconds()) < 1
        assert abs((restored.last_played - original.last_played).total_seconds()) < 1
        assert restored.playtime_seconds == original.playtime_seconds
        assert restored.current_dungeon == original.current_dungeon
        assert restored.current_room == original.current_room
        assert restored.party_character_ids == original.party_character_ids
        assert restored.save_version == original.save_version


class TestSaveSlotMetadata:
    """Test SaveSlotMetadata model."""

    def test_create_save_slot_metadata(self):
        """Test creating save slot metadata."""
        now = datetime.now()
        slot = SaveSlotMetadata(
            slot_name="save_auto",
            created_at=now,
            location="Tomb - Room 12",
            party_hp_summary="Aria 23/30, Zephyr 18/18",
            save_type="auto"
        )

        assert slot.slot_name == "save_auto"
        assert slot.created_at == now
        assert slot.location == "Tomb - Room 12"
        assert slot.party_hp_summary == "Aria 23/30, Zephyr 18/18"
        assert slot.save_type == "auto"

    def test_create_save_slot_metadata_minimal(self):
        """Test creating save slot with minimal data."""
        now = datetime.now()
        slot = SaveSlotMetadata(
            slot_name="test_save",
            created_at=now
        )

        assert slot.slot_name == "test_save"
        assert slot.created_at == now
        assert slot.location is None
        assert slot.party_hp_summary is None
        assert slot.save_type == "manual"

    def test_save_slot_to_dict(self):
        """Test serializing save slot to dictionary."""
        now = datetime.now()
        slot = SaveSlotMetadata(
            slot_name="save_quick",
            created_at=now,
            location="Lost Mine - Room 5",
            party_hp_summary="Thorin 45/45",
            save_type="quick"
        )

        data = slot.to_dict()

        assert data["slot_name"] == "save_quick"
        assert data["created_at"] == now.isoformat()
        assert data["location"] == "Lost Mine - Room 5"
        assert data["party_hp_summary"] == "Thorin 45/45"
        assert data["save_type"] == "quick"

    def test_save_slot_from_dict(self):
        """Test deserializing save slot from dictionary."""
        now = datetime.now()
        data = {
            "slot_name": "save_manual_123",
            "created_at": now.isoformat(),
            "location": "Dungeon - Room 8",
            "party_hp_summary": "Party healthy",
            "save_type": "manual"
        }

        slot = SaveSlotMetadata.from_dict(data)

        assert slot.slot_name == "save_manual_123"
        assert abs((slot.created_at - now).total_seconds()) < 1
        assert slot.location == "Dungeon - Room 8"
        assert slot.party_hp_summary == "Party healthy"
        assert slot.save_type == "manual"

    def test_get_time_display_just_now(self):
        """Test time display for very recent save."""
        slot = SaveSlotMetadata(
            slot_name="test",
            created_at=datetime.now()
        )
        assert slot.get_time_display() == "just now"

    def test_get_time_display_minutes(self):
        """Test time display for minutes ago."""
        slot = SaveSlotMetadata(
            slot_name="test",
            created_at=datetime.now() - timedelta(minutes=5)
        )
        assert slot.get_time_display() == "5 minutes ago"

    def test_get_time_display_hours(self):
        """Test time display for hours ago."""
        slot = SaveSlotMetadata(
            slot_name="test",
            created_at=datetime.now() - timedelta(hours=2)
        )
        assert slot.get_time_display() == "2 hours ago"

    def test_get_time_display_yesterday(self):
        """Test time display for yesterday."""
        slot = SaveSlotMetadata(
            slot_name="test",
            created_at=datetime.now() - timedelta(days=1)
        )
        assert slot.get_time_display() == "yesterday"

    def test_get_time_display_days(self):
        """Test time display for days ago."""
        slot = SaveSlotMetadata(
            slot_name="test",
            created_at=datetime.now() - timedelta(days=3)
        )
        assert slot.get_time_display() == "3 days ago"

    def test_get_time_display_weeks(self):
        """Test time display for weeks ago."""
        slot = SaveSlotMetadata(
            slot_name="test",
            created_at=datetime.now() - timedelta(days=14)
        )
        assert slot.get_time_display() == "2 weeks ago"

    def test_get_time_display_old_date(self):
        """Test time display for old saves shows formatted date."""
        old_date = datetime(2024, 6, 15, 14, 30)
        slot = SaveSlotMetadata(
            slot_name="test",
            created_at=old_date
        )
        display = slot.get_time_display()
        # Should show formatted date like "Jun 15, 2024 at 02:30 PM"
        assert "Jun 15, 2024" in display or "6/15/2024" in display or "2024" in display
