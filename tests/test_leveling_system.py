# ABOUTME: Unit tests for character leveling system
# ABOUTME: Tests XP thresholds, level-up mechanics, HP increases, and feature granting

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus, Event, EventType


class TestLevelingSystem:
    """Test character leveling system"""

    def setup_method(self):
        """Set up test fixtures"""
        self.data_loader = DataLoader()
        self.event_bus = EventBus()
        self.events_received = []

        # Subscribe to events
        self.event_bus.subscribe(EventType.LEVEL_UP, self._capture_event)
        self.event_bus.subscribe(EventType.FEATURE_GRANTED, self._capture_event)

        # Create a test character
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=14,  # +2 modifier
            intelligence=10,
            wisdom=12,
            charisma=8
        )

        self.character = Character(
            name="Test Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16,
            xp=0
        )

    def _capture_event(self, event: Event):
        """Capture events for testing"""
        self.events_received.append(event)

    def test_progression_data_loads(self):
        """Test that progression.json loads correctly"""
        progression = self.data_loader.load_progression()

        assert "xp_by_level" in progression
        assert "proficiency_by_level" in progression
        assert progression["xp_by_level"]["1"] == 0
        assert progression["xp_by_level"]["2"] == 300
        assert progression["xp_by_level"]["20"] == 355000

    def test_no_level_up_with_insufficient_xp(self):
        """Test that character doesn't level up without enough XP"""
        self.character.gain_xp(200)  # Need 300 for level 2

        leveled_up = self.character.check_for_level_up(self.data_loader, self.event_bus)

        assert not leveled_up
        assert self.character.level == 1
        assert len(self.events_received) == 0

    def test_level_up_at_300_xp(self):
        """Test that character levels up from 1 to 2 at 300 XP"""
        self.character.gain_xp(300)

        leveled_up = self.character.check_for_level_up(self.data_loader, self.event_bus)

        assert leveled_up
        assert self.character.level == 2
        assert self.character.xp == 300

    def test_level_up_increases_hp(self):
        """Test that HP increases on level-up"""
        initial_hp = self.character.max_hp
        self.character.gain_xp(300)

        self.character.check_for_level_up(self.data_loader, self.event_bus)

        assert self.character.max_hp > initial_hp
        # Should increase by at least 1 (minimum)
        assert self.character.max_hp >= initial_hp + 1

    def test_hp_increase_includes_con_modifier(self):
        """Test that HP increase includes CON modifier"""
        initial_hp = self.character.max_hp
        self.character.gain_xp(300)

        self.character.check_for_level_up(self.data_loader, self.event_bus)

        # Fighter has d10 hit die, CON +2
        # Minimum increase is 1 + 2 = 3 (if we rolled 1 on d10)
        # Maximum increase is 10 + 2 = 12
        hp_increase = self.character.max_hp - initial_hp
        assert hp_increase >= 3  # min (1 + CON +2)
        assert hp_increase <= 12  # max (d10=10 + CON +2)

    def test_current_hp_increases_with_max_hp(self):
        """Test that current HP also increases on level-up"""
        self.character.current_hp = self.character.max_hp
        initial_current_hp = self.character.current_hp

        self.character.gain_xp(300)
        self.character.check_for_level_up(self.data_loader, self.event_bus)

        # Current HP should increase by same amount as max HP
        assert self.character.current_hp > initial_current_hp

    def test_proficiency_bonus_stays_at_2_for_levels_1_4(self):
        """Test that proficiency bonus is +2 for levels 1-4"""
        # Level 1
        assert self.character.proficiency_bonus == 2

        # Level 2
        self.character.gain_xp(300)
        self.character.check_for_level_up(self.data_loader, self.event_bus)
        assert self.character.proficiency_bonus == 2

        # Level 3
        self.character.gain_xp(900)
        self.character.check_for_level_up(self.data_loader, self.event_bus)
        assert self.character.proficiency_bonus == 2

        # Level 4
        self.character.gain_xp(2700)
        self.character.check_for_level_up(self.data_loader, self.event_bus)
        assert self.character.proficiency_bonus == 2

    def test_proficiency_bonus_increases_at_level_5(self):
        """Test that proficiency bonus increases to +3 at level 5"""
        self.character.gain_xp(6500)  # XP for level 5

        while self.character.check_for_level_up(self.data_loader, self.event_bus):
            pass

        assert self.character.level == 5
        assert self.character.proficiency_bonus == 3

    def test_proficiency_bonus_increases_at_level_9(self):
        """Test that proficiency bonus increases to +4 at level 9"""
        self.character.gain_xp(48000)  # XP for level 9

        while self.character.check_for_level_up(self.data_loader, self.event_bus):
            pass

        assert self.character.level == 9
        assert self.character.proficiency_bonus == 4

    def test_proficiency_bonus_increases_at_level_13(self):
        """Test that proficiency bonus increases to +5 at level 13"""
        self.character.gain_xp(120000)  # XP for level 13

        while self.character.check_for_level_up(self.data_loader, self.event_bus):
            pass

        assert self.character.level == 13
        assert self.character.proficiency_bonus == 5

    def test_proficiency_bonus_increases_at_level_17(self):
        """Test that proficiency bonus increases to +6 at level 17"""
        self.character.gain_xp(225000)  # XP for level 17

        while self.character.check_for_level_up(self.data_loader, self.event_bus):
            pass

        assert self.character.level == 17
        assert self.character.proficiency_bonus == 6

    def test_multiple_level_ups_from_large_xp_gain(self):
        """Test that character can level up multiple times from single XP gain"""
        # Give enough XP to go from level 1 to level 5
        self.character.gain_xp(6500)

        # Level up as many times as possible
        level_ups = 0
        while self.character.check_for_level_up(self.data_loader, self.event_bus):
            level_ups += 1

        assert self.character.level == 5
        assert level_ups == 4  # Leveled up 4 times (1→2, 2→3, 3→4, 4→5)

    def test_cannot_exceed_level_20(self):
        """Test that character cannot level beyond 20"""
        # Set character to level 20
        self.character.level = 20
        self.character.gain_xp(400000)  # More than enough XP

        leveled_up = self.character.check_for_level_up(self.data_loader, self.event_bus)

        assert not leveled_up
        assert self.character.level == 20

    def test_level_up_event_emitted(self):
        """Test that LEVEL_UP event is emitted"""
        self.character.gain_xp(300)
        self.character.check_for_level_up(self.data_loader, self.event_bus)

        level_up_events = [e for e in self.events_received if e.type == EventType.LEVEL_UP]
        assert len(level_up_events) == 1

        event_data = level_up_events[0].data
        assert event_data["character"] == "Test Fighter"
        assert event_data["old_level"] == 1
        assert event_data["new_level"] == 2
        assert event_data["hp_increase"] > 0

    def test_class_features_granted_at_level_2(self):
        """Test that fighter gets Action Surge at level 2"""
        self.character.gain_xp(300)
        self.character.check_for_level_up(self.data_loader, self.event_bus)

        # Check for feature granted events
        feature_events = [e for e in self.events_received if e.type == EventType.FEATURE_GRANTED]

        # Fighter gets Action Surge at level 2
        assert len(feature_events) == 1
        assert feature_events[0].data["feature"] == "Action Surge"
        assert feature_events[0].data["level"] == 2

    def test_resource_pool_added_for_action_surge(self):
        """Test that Action Surge resource pool is created at level 2"""
        self.character.gain_xp(300)
        self.character.check_for_level_up(self.data_loader, self.event_bus)

        assert "action_surge" in self.character.resource_pools
        pool = self.character.resource_pools["action_surge"]
        assert pool.current == 1
        assert pool.maximum == 1
        assert pool.recovery_type == "short_rest"

    def test_hp_minimum_one_per_level(self):
        """Test that HP increases by at least 1 even with negative CON modifier"""
        # Create character with very low CON (-5 modifier)
        abilities = Abilities(
            strength=16, dexterity=14, constitution=1,  # CON 1 = -5 modifier
            intelligence=10, wisdom=12, charisma=8
        )
        weak_char = Character(
            name="Weak Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=16,
            xp=0
        )

        initial_hp = weak_char.max_hp
        weak_char.gain_xp(300)
        weak_char.check_for_level_up(self.data_loader, self.event_bus)

        # Should still gain at least 1 HP
        assert weak_char.max_hp >= initial_hp + 1

    def test_level_2_to_3_at_900_xp(self):
        """Test leveling from 2 to 3 at 900 XP"""
        # Start at level 2 with 300 XP
        self.character.level = 2
        self.character.xp = 300

        # Add enough to reach level 3
        self.character.gain_xp(600)  # Total 900 XP

        leveled_up = self.character.check_for_level_up(self.data_loader, self.event_bus)

        assert leveled_up
        assert self.character.level == 3
        assert self.character.xp == 900

    def test_exact_xp_threshold_levels_up(self):
        """Test that having exactly the threshold XP triggers level-up"""
        self.character.xp = 0
        self.character.gain_xp(300)  # Exactly 300

        leveled_up = self.character.check_for_level_up(self.data_loader, self.event_bus)

        assert leveled_up
        assert self.character.level == 2

    def test_one_xp_below_threshold_does_not_level_up(self):
        """Test that being 1 XP below threshold doesn't trigger level-up"""
        self.character.gain_xp(299)  # One short of 300

        leveled_up = self.character.check_for_level_up(self.data_loader, self.event_bus)

        assert not leveled_up
        assert self.character.level == 1
