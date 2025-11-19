# Unit tests for SaveSlot data model

import pytest
from datetime import datetime, timedelta
from dnd_engine.core.save_slot import SaveSlot


class TestSaveSlot:
    """Test SaveSlot data model functionality."""

    def test_create_empty_slot(self):
        """Test creating an empty save slot."""
        slot = SaveSlot.create_empty(1)

        assert slot.slot_number == 1
        assert slot.is_empty()
        assert slot.adventure_name is None
        assert slot.party_composition == []
        assert slot.playtime_seconds == 0
        assert slot.custom_name is None

    def test_empty_slot_display_name(self):
        """Test display name for empty slot."""
        slot = SaveSlot.create_empty(1)

        assert slot.get_display_name() == "Empty Slot 1"
        assert slot.generate_auto_name() == "Empty Slot 1"

    def test_custom_name_override(self):
        """Test that custom name overrides auto-generated name."""
        slot = SaveSlot.create_empty(1)
        slot.adventure_name = "Tomb of Horrors"
        slot.party_composition = ["Aria", "Zephyr"]
        slot.adventure_progress = "Room 12"
        slot.playtime_seconds = 7200  # 2 hours

        slot.custom_name = "My Epic Adventure"

        assert slot.get_display_name() == "My Epic Adventure"
        assert "Tomb of Horrors" in slot.generate_auto_name()

    def test_auto_name_generation_full_party(self):
        """Test auto-name generation with full adventure info."""
        slot = SaveSlot(
            slot_number=1,
            created_at=datetime.now(),
            last_played=datetime.now(),
            playtime_seconds=9000,  # 2h 30m
            adventure_name="Lost Mine of Phandelver",
            adventure_progress="Room 5",
            party_composition=["Aria", "Zephyr"],
            party_levels=[3, 3]
        )

        name = slot.generate_auto_name()

        assert "Lost Mine of Phandelver" in name
        assert "Aria, Zephyr" in name
        assert "Room 5" in name
        assert "2h 30m" in name

    def test_auto_name_generation_solo(self):
        """Test auto-name generation with solo character."""
        slot = SaveSlot(
            slot_number=1,
            created_at=datetime.now(),
            last_played=datetime.now(),
            playtime_seconds=2700,  # 45m
            adventure_name="Tomb of Horrors",
            adventure_progress="Level 3",
            party_composition=["Solo Ranger"],
            party_levels=[3]
        )

        name = slot.generate_auto_name()

        assert "Tomb of Horrors" in name
        assert "Solo Ranger" in name
        assert "Level 3" in name
        assert "45m" in name

    def test_auto_name_generation_large_party(self):
        """Test auto-name generation with large party (4+ characters)."""
        slot = SaveSlot(
            slot_number=1,
            created_at=datetime.now(),
            last_played=datetime.now(),
            playtime_seconds=1800,  # 30m
            adventure_name="Waterdeep",
            adventure_progress="Quest 2",
            party_composition=["Aria", "Zephyr", "Thorne", "Luna"],
            party_levels=[2, 2, 3, 2]
        )

        name = slot.generate_auto_name()

        assert "Waterdeep" in name
        assert "Aria, Zephyr +2" in name  # First 2 + count
        assert "Quest 2" in name

    def test_auto_name_generation_no_progress(self):
        """Test auto-name when adventure_progress is None."""
        slot = SaveSlot(
            slot_number=1,
            created_at=datetime.now(),
            last_played=datetime.now(),
            playtime_seconds=600,
            adventure_name="New Adventure",
            adventure_progress=None,
            party_composition=["Hero"],
            party_levels=[5]
        )

        name = slot.generate_auto_name()

        assert "New Adventure" in name
        assert "Hero" in name
        assert "Level 5" in name  # Should use level when progress is None

    def test_playtime_formatting(self):
        """Test various playtime formatting scenarios."""
        test_cases = [
            (0, "0m"),
            (30, "30s"),
            (90, "1m"),
            (3600, "1h"),
            (5400, "1h 30m"),
            (86400, "1d"),
            (90000, "1d 1h"),
        ]

        for seconds, expected in test_cases:
            slot = SaveSlot.create_empty(1)
            slot.playtime_seconds = seconds
            formatted = slot._format_playtime()
            assert formatted == expected, f"Expected {expected}, got {formatted} for {seconds}s"

    def test_last_played_display(self):
        """Test last played relative time display."""
        now = datetime.now()

        # Just now
        slot = SaveSlot(
            slot_number=1,
            created_at=now,
            last_played=now,
        )
        assert slot.get_last_played_display() == "just now"

        # Minutes ago
        slot.last_played = now - timedelta(minutes=5)
        assert "5 minutes ago" in slot.get_last_played_display()

        # Hours ago
        slot.last_played = now - timedelta(hours=2)
        assert "2 hours ago" in slot.get_last_played_display()

        # Days ago
        slot.last_played = now - timedelta(days=3)
        assert "3 days ago" in slot.get_last_played_display()

    def test_to_dict_from_dict_roundtrip(self):
        """Test serialization and deserialization."""
        original = SaveSlot(
            slot_number=5,
            created_at=datetime.now(),
            last_played=datetime.now(),
            playtime_seconds=1234,
            adventure_name="Test Adventure",
            adventure_progress="Room 42",
            party_composition=["Alice", "Bob"],
            party_levels=[4, 5],
            custom_name="Custom Name",
            save_version="2.0.0"
        )

        # Serialize
        data = original.to_dict()

        # Deserialize
        restored = SaveSlot.from_dict(data)

        # Verify all fields match
        assert restored.slot_number == original.slot_number
        assert restored.playtime_seconds == original.playtime_seconds
        assert restored.adventure_name == original.adventure_name
        assert restored.adventure_progress == original.adventure_progress
        assert restored.party_composition == original.party_composition
        assert restored.party_levels == original.party_levels
        assert restored.custom_name == original.custom_name
        assert restored.save_version == original.save_version

    def test_is_empty_logic(self):
        """Test is_empty() logic."""
        # Empty slot
        slot = SaveSlot.create_empty(1)
        assert slot.is_empty()

        # Slot with adventure
        slot.adventure_name = "Some Adventure"
        assert not slot.is_empty()

        # Even if other fields are set, adventure_name is the key
        slot2 = SaveSlot.create_empty(2)
        slot2.party_composition = ["Hero"]
        slot2.playtime_seconds = 1000
        assert slot2.is_empty()  # Still empty without adventure_name
