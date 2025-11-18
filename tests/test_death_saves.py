"""
Unit tests for death saving throw mechanics.

Tests D&D 5E death save rules:
- Rolling death saves (success/failure, nat 20/nat 1)
- Death save state tracking
- Damage at 0 HP
- Massive damage instant death
- Healing and stabilization
- Character state properties (unconscious, dead)
"""

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.utils.events import EventBus, EventType
from unittest.mock import Mock, patch


@pytest.fixture
def abilities():
    """Standard ability scores for testing."""
    return Abilities(
        strength=14,
        dexterity=12,
        constitution=13,
        intelligence=10,
        wisdom=11,
        charisma=8
    )


@pytest.fixture
def character(abilities):
    """Create a test character."""
    return Character(
        name="TestHero",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=10,
        ac=16,
        current_hp=10
    )


@pytest.fixture
def event_bus():
    """Create an event bus for testing."""
    return EventBus()


class TestDeathSaveState:
    """Test death save state tracking."""

    def test_initial_death_save_state(self, character):
        """Characters should start with no death saves."""
        assert character.death_save_successes == 0
        assert character.death_save_failures == 0
        assert character.stabilized == False

    def test_unconscious_at_zero_hp(self, character):
        """Character at 0 HP should be unconscious."""
        character.current_hp = 0
        assert character.is_unconscious == True
        assert character.is_dead == False
        # Note: is_alive is False at 0 HP (from Creature), but is_dead checks death saves
        assert character.is_alive == False  # 0 HP means not alive by Creature definition
        # But not truly dead yet (can be saved)
        assert character.death_save_failures < 3

    def test_dead_at_three_failures(self, character):
        """Character with 3 failures should be dead."""
        character.current_hp = 0
        character.death_save_failures = 3
        assert character.is_unconscious == False  # Dead, not unconscious
        assert character.is_dead == True
        assert character.is_alive == False

    def test_not_unconscious_with_hp(self, character):
        """Character with HP > 0 should not be unconscious."""
        character.current_hp = 5
        assert character.is_unconscious == False

    def test_reset_death_saves(self, character):
        """reset_death_saves should clear all death save state."""
        character.death_save_successes = 2
        character.death_save_failures = 1
        character.stabilized = True

        character.reset_death_saves()

        assert character.death_save_successes == 0
        assert character.death_save_failures == 0
        assert character.stabilized == False


class TestDeathSaveRolls:
    """Test death saving throw rolls."""

    def test_death_save_success(self, character, event_bus):
        """Rolling 10+ should be a success."""
        character.current_hp = 0

        with patch.object(character._dice_roller, 'roll') as mock_roll:
            mock_roll.return_value = Mock(total=15)
            result = character.make_death_save(event_bus)

        assert result["success"] == True
        assert result["roll"] == 15
        assert result["successes"] == 1
        assert result["failures"] == 0
        assert character.death_save_successes == 1

    def test_death_save_failure(self, character, event_bus):
        """Rolling 9 or less should be a failure."""
        character.current_hp = 0

        with patch.object(character._dice_roller, 'roll') as mock_roll:
            mock_roll.return_value = Mock(total=7)
            result = character.make_death_save(event_bus)

        assert result["success"] == False
        assert result["roll"] == 7
        assert result["successes"] == 0
        assert result["failures"] == 1
        assert character.death_save_failures == 1

    def test_death_save_natural_20(self, character, event_bus):
        """Natural 20 should restore 1 HP and consciousness."""
        character.current_hp = 0
        character.death_save_successes = 2
        character.death_save_failures = 1

        with patch.object(character._dice_roller, 'roll') as mock_roll:
            mock_roll.return_value = Mock(total=20)
            result = character.make_death_save(event_bus)

        assert result["natural_20"] == True
        assert result["conscious"] == True
        assert character.current_hp == 1
        # Death saves should be reset
        assert character.death_save_successes == 0
        assert character.death_save_failures == 0
        assert character.stabilized == False

    def test_death_save_natural_1(self, character, event_bus):
        """Natural 1 should count as 2 failures."""
        character.current_hp = 0

        with patch.object(character._dice_roller, 'roll') as mock_roll:
            mock_roll.return_value = Mock(total=1)
            result = character.make_death_save(event_bus)

        assert result["natural_1"] == True
        assert result["failures"] == 2
        assert character.death_save_failures == 2

    def test_three_successes_stabilizes(self, character, event_bus):
        """Three successes should stabilize the character."""
        character.current_hp = 0
        character.death_save_successes = 2

        with patch.object(character._dice_roller, 'roll') as mock_roll:
            mock_roll.return_value = Mock(total=15)
            result = character.make_death_save(event_bus)

        assert result["stabilized"] == True
        assert character.stabilized == True
        assert character.death_save_successes == 3

    def test_three_failures_means_death(self, character, event_bus):
        """Three failures should kill the character."""
        character.current_hp = 0
        character.death_save_failures = 2

        with patch.object(character._dice_roller, 'roll') as mock_roll:
            mock_roll.return_value = Mock(total=5)
            result = character.make_death_save(event_bus)

        assert result["dead"] == True
        assert character.is_dead == True
        assert character.death_save_failures == 3

    def test_cannot_make_death_save_when_conscious(self, character, event_bus):
        """Should raise error if trying to make death save while conscious."""
        character.current_hp = 5

        with pytest.raises(ValueError, match="cannot make death saves"):
            character.make_death_save(event_bus)

    def test_stabilized_no_more_death_saves(self, character, event_bus):
        """Stabilized characters don't roll death saves."""
        character.current_hp = 0
        character.stabilized = True

        result = character.make_death_save(event_bus)

        # Should return early without rolling
        assert result["stabilized"] == True
        assert result["roll"] == 0

    def test_death_save_emits_event(self, character, event_bus):
        """Death save should emit DEATH_SAVE event."""
        character.current_hp = 0
        events = []
        event_bus.subscribe(EventType.DEATH_SAVE, lambda e: events.append(e))

        with patch.object(character._dice_roller, 'roll') as mock_roll:
            mock_roll.return_value = Mock(total=12)
            character.make_death_save(event_bus)

        assert len(events) == 1
        assert events[0].type == EventType.DEATH_SAVE
        assert events[0].data["character"] == "TestHero"
        assert events[0].data["roll"] == 12


class TestDamageAtZeroHP:
    """Test taking damage while at 0 HP."""

    def test_damage_at_zero_hp_adds_failure(self, character, event_bus):
        """Taking damage at 0 HP should add 1 death save failure."""
        character.current_hp = 0

        character.take_damage(5, event_bus)

        assert character.death_save_failures == 1
        assert character.current_hp == 0

    def test_massive_damage_instant_death(self, character, event_bus):
        """Damage >= max HP at 0 HP should cause instant death."""
        character.current_hp = 0
        max_hp = character.max_hp

        character.take_damage(max_hp, event_bus)

        assert character.death_save_failures == 3
        assert character.is_dead == True

    def test_massive_damage_over_max_hp(self, character, event_bus):
        """Damage > max HP should also cause instant death."""
        character.current_hp = 0

        character.take_damage(50, event_bus)

        assert character.death_save_failures == 3
        assert character.is_dead == True

    def test_damage_at_zero_hp_emits_event(self, character, event_bus):
        """Damage at 0 HP should emit event."""
        character.current_hp = 0
        events = []
        event_bus.subscribe(EventType.DAMAGE_AT_ZERO_HP, lambda e: events.append(e))

        character.take_damage(5, event_bus)

        assert len(events) == 1
        assert events[0].data["character"] == "TestHero"
        assert events[0].data["damage"] == 5
        assert events[0].data["failures"] == 1

    def test_massive_damage_emits_event(self, character, event_bus):
        """Massive damage should emit special event."""
        character.current_hp = 0
        events = []
        event_bus.subscribe(EventType.MASSIVE_DAMAGE_DEATH, lambda e: events.append(e))

        character.take_damage(character.max_hp, event_bus)

        assert len(events) == 1
        assert events[0].data["character"] == "TestHero"
        assert events[0].data["damage"] == character.max_hp

    def test_normal_damage_doesnt_add_failure(self, character, event_bus):
        """Taking damage while conscious should not add death save failures."""
        character.current_hp = 8

        character.take_damage(5, event_bus)

        assert character.current_hp == 3
        assert character.death_save_failures == 0


class TestHealingAndStabilization:
    """Test healing and stabilization mechanics."""

    def test_healing_resets_death_saves(self, character):
        """Healing from 0 HP should reset death saves."""
        character.current_hp = 0
        character.death_save_successes = 2
        character.death_save_failures = 1

        character.recover_hp(5)

        assert character.current_hp == 5
        assert character.death_save_successes == 0
        assert character.death_save_failures == 0
        assert character.stabilized == False

    def test_healing_when_conscious_doesnt_reset(self, character):
        """Healing while conscious should not affect death saves."""
        character.current_hp = 5
        character.death_save_successes = 2  # Shouldn't be set, but test anyway

        character.recover_hp(3)

        assert character.current_hp == 8
        # Death saves remain (even though they shouldn't exist)
        assert character.death_save_successes == 2

    def test_stabilize_character(self, character):
        """stabilize_character should set stabilized flag."""
        character.current_hp = 0

        character.stabilize_character()

        assert character.stabilized == True
        assert character.current_hp == 0  # Still at 0 HP

    def test_stabilize_only_works_at_zero_hp(self, character):
        """Stabilization should only work when unconscious."""
        character.current_hp = 5

        character.stabilize_character()

        # Should not set stabilized when conscious
        assert character.stabilized == False

    def test_add_death_save_failure(self, character):
        """add_death_save_failure should add failures."""
        character.add_death_save_failure(1)
        assert character.death_save_failures == 1

        character.add_death_save_failure(2)
        assert character.death_save_failures == 3


class TestDeathSaveEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_natural_1_on_last_failure_kills(self, character, event_bus):
        """Natural 1 with 2 failures should kill (adds 2 failures)."""
        character.current_hp = 0
        character.death_save_failures = 2

        with patch.object(character._dice_roller, 'roll') as mock_roll:
            mock_roll.return_value = Mock(total=1)
            result = character.make_death_save(event_bus)

        assert result["dead"] == True
        assert character.death_save_failures == 4  # 2 + 2 from nat 1

    def test_successive_damage_at_zero_hp(self, character, event_bus):
        """Multiple hits at 0 HP should stack failures."""
        character.current_hp = 0

        character.take_damage(5, event_bus)
        assert character.death_save_failures == 1

        character.take_damage(3, event_bus)
        assert character.death_save_failures == 2

        character.take_damage(4, event_bus)
        assert character.death_save_failures == 3
        assert character.is_dead == True

    def test_healing_1_hp_from_unconscious(self, character):
        """Healing to 1 HP should make character conscious."""
        character.current_hp = 0
        character.death_save_failures = 2

        character.recover_hp(1)

        assert character.current_hp == 1
        assert character.is_unconscious == False
        assert character.is_alive == True
        assert character.death_save_failures == 0

    def test_full_heal_from_unconscious(self, character):
        """Full heal from unconscious should reset everything."""
        character.current_hp = 0
        character.death_save_successes = 1
        character.death_save_failures = 1

        character.recover_hp()  # Full heal

        assert character.current_hp == character.max_hp
        assert character.death_save_successes == 0
        assert character.death_save_failures == 0
        assert character.stabilized == False
