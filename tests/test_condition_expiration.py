# ABOUTME: Tests for condition expiration outside combat and during rest.
# ABOUTME: Verifies fix for issue #276 - paralysis and timed conditions should expire.

"""
Tests for condition expiration behavior outside of combat.

Issue #276: Paralysis and timed conditions don't expire outside combat or during rest.

D&D 5E Rules:
- Conditions with durations should expire when time passes
- Long rest (8 hours) should clear temporary conditions
- Short rest (1 hour) should clear very short duration conditions
- When combat ends, round-based durations should convert to real time
"""

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature


class TestConditionExpirationDuringRest:
    """Tests for conditions expiring during short and long rests."""

    def create_test_character(self) -> Character:
        """Create a test character with standard stats."""
        return Character(
            name="Test Fighter",
            character_class=CharacterClass.FIGHTER,
            level=5,
            abilities=Abilities(16, 14, 14, 10, 12, 10),
            max_hp=44,
            ac=16,
            race="human",
        )

    def test_long_rest_clears_paralyzed_condition(self):
        """
        Long rest should clear the paralyzed condition.

        D&D 5E: Paralysis from ghoul claw lasts 1 minute (10 rounds).
        An 8-hour long rest vastly exceeds this duration.
        """
        character = self.create_test_character()

        # Apply paralyzed condition (like from a ghoul)
        character.apply_condition_with_metadata(
            condition="paralyzed",
            duration_type="rounds",
            duration=10,  # 1 minute = 10 rounds
            dc=10,
            ability="constitution",
            allow_repeat_save=True,
            repeat_timing="end_of_turn",
        )

        assert character.has_condition("paralyzed"), "Setup failed: condition not applied"

        # Take a long rest
        result = character.take_long_rest()

        # Paralysis should be cleared
        assert not character.has_condition("paralyzed"), (
            "Paralyzed condition should be cleared after long rest"
        )
        assert "paralyzed" in result["conditions_removed"], (
            "Long rest result should report paralyzed was removed"
        )

    def test_long_rest_clears_poisoned_condition(self):
        """Long rest should clear the poisoned condition."""
        character = self.create_test_character()

        character.apply_condition_with_metadata(
            condition="poisoned",
            duration_type="hours",
            duration=1,
            dc=12,
            ability="constitution",
            allow_repeat_save=False,
        )

        assert character.has_condition("poisoned")

        result = character.take_long_rest()

        assert not character.has_condition("poisoned"), (
            "Poisoned condition should be cleared after long rest"
        )
        assert "poisoned" in result["conditions_removed"]

    def test_long_rest_clears_frightened_condition(self):
        """Long rest should clear the frightened condition."""
        character = self.create_test_character()

        character.apply_condition_with_metadata(
            condition="frightened",
            duration_type="minutes",
            duration=10,
        )

        assert character.has_condition("frightened")

        result = character.take_long_rest()

        assert not character.has_condition("frightened")
        assert "frightened" in result["conditions_removed"]

    def test_long_rest_clears_stunned_condition(self):
        """Long rest should clear the stunned condition."""
        character = self.create_test_character()

        character.apply_condition_with_metadata(
            condition="stunned",
            duration_type="rounds",
            duration=3,
        )

        result = character.take_long_rest()

        assert not character.has_condition("stunned")
        assert "stunned" in result["conditions_removed"]

    def test_long_rest_does_not_clear_permanent_conditions(self):
        """
        Long rest should NOT clear permanent conditions like curses.

        Permanent conditions require specific removal (spell, quest, etc.)
        """
        character = self.create_test_character()

        # Apply a permanent curse
        character.apply_condition_with_metadata(
            condition="cursed",
            duration_type="permanent",
            duration=0,
        )

        result = character.take_long_rest()

        assert character.has_condition("cursed"), (
            "Permanent conditions should NOT be cleared by long rest"
        )
        assert "cursed" not in result["conditions_removed"]

    def test_long_rest_clears_multiple_conditions(self):
        """Long rest should clear all non-permanent conditions at once."""
        character = self.create_test_character()

        # Apply multiple conditions
        character.apply_condition_with_metadata(
            condition="paralyzed",
            duration_type="rounds",
            duration=10,
        )
        character.apply_condition_with_metadata(
            condition="poisoned",
            duration_type="hours",
            duration=2,
        )
        character.apply_condition_with_metadata(
            condition="blinded",
            duration_type="minutes",
            duration=5,
        )
        character.apply_condition_with_metadata(
            condition="cursed",
            duration_type="permanent",
            duration=0,
        )

        result = character.take_long_rest()

        # Non-permanent should be cleared
        assert not character.has_condition("paralyzed")
        assert not character.has_condition("poisoned")
        assert not character.has_condition("blinded")

        # Permanent should remain
        assert character.has_condition("cursed")

        # Check result contains all removed conditions
        assert "paralyzed" in result["conditions_removed"]
        assert "poisoned" in result["conditions_removed"]
        assert "blinded" in result["conditions_removed"]
        assert "cursed" not in result["conditions_removed"]

    def test_short_rest_clears_short_duration_conditions(self):
        """
        Short rest (1 hour) should clear conditions with short durations.

        Conditions lasting less than 1 hour should expire during short rest.
        """
        character = self.create_test_character()

        # Apply conditions with durations shorter than 1 hour
        character.apply_condition_with_metadata(
            condition="paralyzed",
            duration_type="rounds",
            duration=10,  # 1 minute
        )
        character.apply_condition_with_metadata(
            condition="frightened",
            duration_type="minutes",
            duration=10,  # 10 minutes
        )

        result = character.take_short_rest()

        # Both should be cleared (durations < 1 hour)
        assert not character.has_condition("paralyzed"), (
            "1-minute paralysis should expire during 1-hour short rest"
        )
        assert not character.has_condition("frightened"), (
            "10-minute frightened should expire during 1-hour short rest"
        )

    def test_short_rest_does_not_clear_long_duration_conditions(self):
        """
        Short rest should NOT clear conditions lasting longer than 1 hour.

        These conditions should persist until long rest or specific removal.
        """
        character = self.create_test_character()

        # Apply condition lasting multiple hours
        character.apply_condition_with_metadata(
            condition="poisoned",
            duration_type="hours",
            duration=8,  # 8 hours - longer than short rest
        )

        result = character.take_short_rest()

        # Should still be poisoned
        assert character.has_condition("poisoned"), (
            "8-hour poison should persist through 1-hour short rest"
        )

    def test_dead_character_conditions_not_processed(self):
        """Dead characters should retain conditions (they're dead, not resting)."""
        character = self.create_test_character()

        # Kill the character
        character.death_save_failures = 3

        character.apply_condition_with_metadata(
            condition="paralyzed",
            duration_type="rounds",
            duration=10,
        )

        result = character.take_long_rest()

        # Dead character can't benefit from rest - conditions remain
        # (This matches existing behavior where dead characters don't heal)
        assert character.has_condition("paralyzed"), (
            "Dead characters should not process condition expiration"
        )


class TestCreatureConditionExpiration:
    """Tests for condition expiration on base Creature class."""

    def create_test_creature(self) -> Creature:
        """Create a test creature."""
        return Creature(
            name="Test Goblin",
            max_hp=7,
            ac=15,
            abilities=Abilities(8, 14, 10, 10, 8, 8),
        )

    def test_clear_expired_conditions_clears_timed_conditions(self):
        """
        Creature.clear_expired_conditions() should clear non-permanent conditions.

        This method can be called when combat ends or time passes.
        """
        creature = self.create_test_creature()

        creature.apply_condition_with_metadata(
            condition="paralyzed",
            duration_type="rounds",
            duration=10,
        )
        creature.apply_condition_with_metadata(
            condition="cursed",
            duration_type="permanent",
            duration=0,
        )

        removed = creature.clear_expired_conditions()

        assert not creature.has_condition("paralyzed")
        assert creature.has_condition("cursed")
        assert "paralyzed" in removed

    def test_clear_conditions_by_duration_clears_matching_durations(self):
        """
        Creature.clear_conditions_by_max_duration() clears conditions
        within a time threshold.

        Useful for short rest (clear conditions < 1 hour).
        """
        creature = self.create_test_creature()

        # 10 rounds = 1 minute
        creature.apply_condition_with_metadata(
            condition="paralyzed",
            duration_type="rounds",
            duration=10,
        )
        # 10 minutes
        creature.apply_condition_with_metadata(
            condition="frightened",
            duration_type="minutes",
            duration=10,
        )
        # 8 hours
        creature.apply_condition_with_metadata(
            condition="poisoned",
            duration_type="hours",
            duration=8,
        )

        # Clear conditions shorter than 60 minutes
        removed = creature.clear_conditions_by_max_duration(max_minutes=60)

        assert not creature.has_condition("paralyzed")  # 1 min < 60 min
        assert not creature.has_condition("frightened")  # 10 min < 60 min
        assert creature.has_condition("poisoned")  # 480 min > 60 min
        assert "paralyzed" in removed
        assert "frightened" in removed
        assert "poisoned" not in removed


class TestConditionDurationConversion:
    """Tests for converting between duration types."""

    def create_test_creature(self) -> Creature:
        """Create a simple test creature."""
        return Creature(
            name="Test",
            max_hp=10,
            ac=10,
            abilities=Abilities(10, 10, 10, 10, 10, 10),
        )

    def test_rounds_to_minutes_conversion(self):
        """10 rounds = 1 minute in D&D 5E."""
        creature = self.create_test_creature()

        creature.apply_condition_with_metadata(
            condition="test",
            duration_type="rounds",
            duration=10,
        )

        # Get duration in minutes
        duration_minutes = creature.get_condition_duration_minutes("test")
        assert duration_minutes == 1, "10 rounds should equal 1 minute"

    def test_minutes_to_minutes_conversion(self):
        """Minutes should return as-is."""
        creature = self.create_test_creature()

        creature.apply_condition_with_metadata(
            condition="test",
            duration_type="minutes",
            duration=30,
        )

        duration_minutes = creature.get_condition_duration_minutes("test")
        assert duration_minutes == 30

    def test_hours_to_minutes_conversion(self):
        """1 hour = 60 minutes."""
        creature = self.create_test_creature()

        creature.apply_condition_with_metadata(
            condition="test",
            duration_type="hours",
            duration=2,
        )

        duration_minutes = creature.get_condition_duration_minutes("test")
        assert duration_minutes == 120, "2 hours should equal 120 minutes"

    def test_permanent_duration_returns_infinity(self):
        """Permanent conditions should return infinite duration."""
        creature = self.create_test_creature()

        creature.apply_condition_with_metadata(
            condition="cursed",
            duration_type="permanent",
            duration=0,
        )

        duration_minutes = creature.get_condition_duration_minutes("cursed")
        assert duration_minutes == float("inf"), (
            "Permanent conditions should have infinite duration"
        )


class TestConditionExpirationOnCombatEnd:
    """Tests for conditions expiring when combat ends."""

    def create_test_character(self) -> Character:
        """Create a test character with standard stats."""
        return Character(
            name="Test Fighter",
            character_class=CharacterClass.FIGHTER,
            level=5,
            abilities=Abilities(16, 14, 14, 10, 12, 10),
            max_hp=44,
            ac=16,
            race="human",
        )

    def test_short_duration_conditions_clear_on_combat_end(self):
        """
        Short duration conditions (< 5 minutes) should clear when combat ends.

        D&D 5E: Combat rounds are 6 seconds. A 10-round paralysis (1 minute)
        would naturally expire shortly after combat ends.
        """
        from dnd_engine.core.game_state import GameState
        from dnd_engine.core.party import Party

        character = self.create_test_character()
        party = Party([character])
        game_state = GameState(party, "test_dungeon")

        # Simulate being in combat
        game_state.in_combat = True
        game_state.active_enemies = []

        # Apply paralysis (10 rounds = 1 minute)
        character.apply_condition_with_metadata(
            condition="paralyzed",
            duration_type="rounds",
            duration=10,
            dc=10,
            ability="constitution",
            allow_repeat_save=True,
        )

        assert character.has_condition("paralyzed")

        # End combat
        game_state._end_combat()

        # Paralysis should be cleared (1 minute << 5 minute threshold)
        assert not character.has_condition("paralyzed"), (
            "Short duration conditions should clear when combat ends"
        )

    def test_permanent_conditions_persist_after_combat(self):
        """Permanent conditions should NOT be cleared when combat ends."""
        from dnd_engine.core.game_state import GameState
        from dnd_engine.core.party import Party

        character = self.create_test_character()
        party = Party([character])
        game_state = GameState(party, "test_dungeon")

        game_state.in_combat = True
        game_state.active_enemies = []

        # Apply a permanent curse
        character.apply_condition_with_metadata(
            condition="cursed",
            duration_type="permanent",
            duration=0,
        )

        game_state._end_combat()

        assert character.has_condition("cursed"), (
            "Permanent conditions should persist after combat ends"
        )

    def test_long_duration_conditions_persist_after_combat(self):
        """
        Long duration conditions (hours) should persist after combat.

        These require rest or specific removal, not just combat ending.
        """
        from dnd_engine.core.game_state import GameState
        from dnd_engine.core.party import Party

        character = self.create_test_character()
        party = Party([character])
        game_state = GameState(party, "test_dungeon")

        game_state.in_combat = True
        game_state.active_enemies = []

        # Apply a long-duration poison (8 hours)
        character.apply_condition_with_metadata(
            condition="poisoned",
            duration_type="hours",
            duration=8,
        )

        game_state._end_combat()

        assert character.has_condition("poisoned"), (
            "Long duration conditions should persist after combat"
        )
