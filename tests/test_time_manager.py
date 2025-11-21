"""
Unit tests for the TimeManager system and duration parsing.

Tests cover:
- Duration string parsing to minutes
- Active effect creation and management
- Time advancement and effect expiration
- Concentration spell handling
- Event emission
"""

import pytest
from dnd_engine.systems.time_manager import (
    TimeManager,
    ActiveEffect,
    EffectType,
    parse_duration_to_minutes,
    format_minutes_to_display
)
from dnd_engine.utils.events import EventBus, EventType


class TestDurationParsing:
    """Test duration string parsing."""

    def test_parse_seconds(self):
        """Test parsing seconds to minutes."""
        assert parse_duration_to_minutes("6 seconds") == 0.1
        assert parse_duration_to_minutes("30 seconds") == 0.5

    def test_parse_minutes(self):
        """Test parsing minutes."""
        assert parse_duration_to_minutes("1 minute") == 1.0
        assert parse_duration_to_minutes("10 minutes") == 10.0

    def test_parse_hours(self):
        """Test parsing hours to minutes."""
        assert parse_duration_to_minutes("1 hour") == 60.0
        assert parse_duration_to_minutes("8 hours") == 480.0

    def test_parse_rounds(self):
        """Test parsing rounds to minutes (1 round = 6 seconds = 0.1 minutes)."""
        assert parse_duration_to_minutes("1 round") == 0.1
        assert parse_duration_to_minutes("10 rounds") == 1.0

    def test_parse_with_concentration_prefix(self):
        """Test parsing with 'Concentration, up to' prefix."""
        assert parse_duration_to_minutes("Concentration, up to 1 minute") == 1.0
        assert parse_duration_to_minutes("concentration, up to 1 hour") == 60.0

    def test_parse_with_up_to_prefix(self):
        """Test parsing with 'up to' prefix."""
        assert parse_duration_to_minutes("up to 1 hour") == 60.0
        assert parse_duration_to_minutes("up to 10 minutes") == 10.0

    def test_parse_invalid_strings(self):
        """Test parsing invalid duration strings returns None."""
        assert parse_duration_to_minutes("") is None
        assert parse_duration_to_minutes(None) is None
        assert parse_duration_to_minutes("instantaneous") is None
        assert parse_duration_to_minutes("until dispelled") is None

    def test_parse_decimal_values(self):
        """Test parsing decimal duration values."""
        assert parse_duration_to_minutes("1.5 hours") == 90.0
        assert parse_duration_to_minutes("0.5 minutes") == 0.5


class TestFormatMinutes:
    """Test minutes formatting to display strings."""

    def test_format_seconds(self):
        """Test formatting sub-minute durations."""
        assert format_minutes_to_display(0.1) == "6 seconds"
        assert format_minutes_to_display(0.5) == "30 seconds"

    def test_format_minutes(self):
        """Test formatting minute durations."""
        assert format_minutes_to_display(1.0) == "1 minute"
        assert format_minutes_to_display(10.0) == "10 minutes"
        assert format_minutes_to_display(1.5) == "1.5 minutes"

    def test_format_hours(self):
        """Test formatting hour durations."""
        assert format_minutes_to_display(60.0) == "1 hour"
        assert format_minutes_to_display(120.0) == "2 hours"

    def test_format_hours_and_minutes(self):
        """Test formatting mixed hour and minute durations."""
        assert format_minutes_to_display(90.0) == "1 hour, 30 minutes"
        assert format_minutes_to_display(125.0) == "2 hours, 5 minutes"


class TestActiveEffect:
    """Test ActiveEffect dataclass."""

    def test_create_effect(self):
        """Test creating an active effect."""
        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Bless",
            duration_minutes=10.0,
            remaining_minutes=10.0,
            target_name="Gandalf",
            description="Gain +1d4 to attacks and saves"
        )

        assert effect.effect_type == EffectType.SPELL
        assert effect.source == "Bless"
        assert effect.duration_minutes == 10.0
        assert effect.remaining_minutes == 10.0
        assert effect.target_name == "Gandalf"
        assert not effect.is_expired

    def test_effect_expiration(self):
        """Test effect expiration."""
        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Shield",
            duration_minutes=1.0,
            remaining_minutes=0.5,
            target_name="Aragorn"
        )

        # Advance time by 0.3 minutes - should not expire
        expired = effect.advance_time(0.3)
        assert not expired
        assert effect.remaining_minutes == 0.2

        # Advance time by 0.3 minutes - should expire
        expired = effect.advance_time(0.3)
        assert expired
        assert effect.is_expired

    def test_concentration_effect(self):
        """Test concentration effect creation."""
        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Haste",
            duration_minutes=10.0,
            remaining_minutes=10.0,
            target_name="Legolas",
            concentration=True,
            caster_name="Gandalf"
        )

        assert effect.concentration
        assert effect.caster_name == "Gandalf"

    def test_time_remaining_display(self):
        """Test time remaining display strings."""
        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Light",
            duration_minutes=60.0,
            remaining_minutes=60.0,
            target_name="Frodo"
        )

        assert "hour" in effect.get_time_remaining_display()

        effect.remaining_minutes = 1.0
        assert "minute" in effect.get_time_remaining_display()

        effect.remaining_minutes = 0.1
        assert "seconds" in effect.get_time_remaining_display()

        effect.remaining_minutes = 0.0
        assert effect.get_time_remaining_display() == "Expired"


class TestTimeManager:
    """Test TimeManager system."""

    def test_create_time_manager(self):
        """Test creating a TimeManager."""
        tm = TimeManager()
        assert tm.elapsed_minutes == 0.0
        assert len(tm.active_effects) == 0

    def test_advance_time(self):
        """Test advancing time."""
        tm = TimeManager()
        expired = tm.advance_time(10.0, reason="test")

        assert tm.elapsed_minutes == 10.0
        assert len(expired) == 0

    def test_elapsed_time_display(self):
        """Test elapsed time display formatting."""
        tm = TimeManager()

        # Test minutes
        tm.advance_time(30.0)
        display = tm.get_elapsed_time_display()
        assert "30 minutes" in display

        # Test hours
        tm.advance_time(60.0)
        display = tm.get_elapsed_time_display()
        assert "1 hour" in display
        assert "30 minutes" in display

        # Test days
        tm.advance_time(24 * 60)  # 24 hours
        display = tm.get_elapsed_time_display()
        assert "1 day" in display

    def test_add_effect(self):
        """Test adding effects to TimeManager."""
        tm = TimeManager()
        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Mage Armor",
            duration_minutes=480.0,
            remaining_minutes=480.0,
            target_name="Wizard"
        )

        tm.add_effect(effect)
        assert len(tm.active_effects) == 1
        assert tm.active_effects[0] == effect

    def test_effect_expiration_on_time_advance(self):
        """Test effects expire when time advances."""
        tm = TimeManager()
        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Shield of Faith",
            duration_minutes=10.0,
            remaining_minutes=10.0,
            target_name="Paladin"
        )

        tm.add_effect(effect)
        assert len(tm.active_effects) == 1

        # Advance time partially
        expired = tm.advance_time(5.0)
        assert len(expired) == 0
        assert len(tm.active_effects) == 1
        assert effect.remaining_minutes == 5.0

        # Advance time to expiration
        expired = tm.advance_time(5.0)
        assert len(expired) == 1
        assert expired[0] == effect
        assert len(tm.active_effects) == 0

    def test_multiple_effects(self):
        """Test managing multiple effects."""
        tm = TimeManager()

        effect1 = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Bless",
            duration_minutes=10.0,
            remaining_minutes=10.0,
            target_name="Cleric"
        )

        effect2 = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Guidance",
            duration_minutes=1.0,
            remaining_minutes=1.0,
            target_name="Cleric"
        )

        tm.add_effect(effect1)
        tm.add_effect(effect2)
        assert len(tm.active_effects) == 2

        # Advance time - only effect2 should expire
        expired = tm.advance_time(1.0)
        assert len(expired) == 1
        assert expired[0] == effect2
        assert len(tm.active_effects) == 1

    def test_replace_same_effect(self):
        """Test that adding the same effect (same source and target) replaces the old one."""
        tm = TimeManager()

        effect1 = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Light",
            duration_minutes=60.0,
            remaining_minutes=30.0,  # Half expired
            target_name="Torch"
        )

        effect2 = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Light",
            duration_minutes=60.0,
            remaining_minutes=60.0,  # Fresh cast
            target_name="Torch"
        )

        tm.add_effect(effect1)
        assert len(tm.active_effects) == 1

        # Add same effect - should replace
        tm.add_effect(effect2)
        assert len(tm.active_effects) == 1
        assert tm.active_effects[0].remaining_minutes == 60.0

    def test_remove_effect(self):
        """Test removing a specific effect."""
        tm = TimeManager()
        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Detect Magic",
            duration_minutes=10.0,
            remaining_minutes=10.0,
            target_name="Wizard"
        )

        tm.add_effect(effect)
        assert len(tm.active_effects) == 1

        removed = tm.remove_effect("Wizard", "Detect Magic")
        assert removed == effect
        assert len(tm.active_effects) == 0

    def test_remove_nonexistent_effect(self):
        """Test removing an effect that doesn't exist."""
        tm = TimeManager()
        removed = tm.remove_effect("Nobody", "Nothing")
        assert removed is None

    def test_concentration_breaking(self):
        """Test breaking concentration removes all concentration effects from caster."""
        tm = TimeManager()

        effect1 = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Haste",
            duration_minutes=10.0,
            remaining_minutes=10.0,
            target_name="Fighter",
            concentration=True,
            caster_name="Wizard"
        )

        effect2 = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Fly",
            duration_minutes=10.0,
            remaining_minutes=10.0,
            target_name="Rogue",
            concentration=True,
            caster_name="Wizard"
        )

        # Non-concentration effect from same caster
        effect3 = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Mage Armor",
            duration_minutes=480.0,
            remaining_minutes=480.0,
            target_name="Wizard",
            concentration=False
        )

        tm.add_effect(effect1)
        tm.add_effect(effect2)
        tm.add_effect(effect3)
        assert len(tm.active_effects) == 3

        # Break concentration - should remove effect1 and effect2, but not effect3
        removed = tm.remove_concentration_effects("Wizard")
        assert len(removed) == 2
        assert effect1 in removed
        assert effect2 in removed
        assert len(tm.active_effects) == 1
        assert tm.active_effects[0] == effect3

    def test_get_effects_for_character(self):
        """Test getting effects for a specific character."""
        tm = TimeManager()

        effect1 = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Bless",
            duration_minutes=10.0,
            remaining_minutes=10.0,
            target_name="Fighter"
        )

        effect2 = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Shield of Faith",
            duration_minutes=10.0,
            remaining_minutes=10.0,
            target_name="Fighter"
        )

        effect3 = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Bless",
            duration_minutes=10.0,
            remaining_minutes=10.0,
            target_name="Cleric"
        )

        tm.add_effect(effect1)
        tm.add_effect(effect2)
        tm.add_effect(effect3)

        fighter_effects = tm.get_effects_for_character("Fighter")
        assert len(fighter_effects) == 2
        assert effect1 in fighter_effects
        assert effect2 in fighter_effects

        cleric_effects = tm.get_effects_for_character("Cleric")
        assert len(cleric_effects) == 1
        assert effect3 in cleric_effects

    def test_clear_all_effects(self):
        """Test clearing all effects."""
        tm = TimeManager()

        for i in range(3):
            effect = ActiveEffect(
                effect_type=EffectType.SPELL,
                source=f"Spell{i}",
                duration_minutes=10.0,
                remaining_minutes=10.0,
                target_name="Target"
            )
            tm.add_effect(effect)

        assert len(tm.active_effects) == 3

        tm.clear_all_effects()
        assert len(tm.active_effects) == 0


class TestTimeManagerEvents:
    """Test TimeManager event emission."""

    def test_time_advanced_event(self):
        """Test TIME_ADVANCED event is emitted."""
        event_bus = EventBus()
        events_received = []

        def handler(event):
            events_received.append(event)

        event_bus.subscribe(EventType.TIME_ADVANCED, handler)

        tm = TimeManager(event_bus=event_bus)
        tm.advance_time(10.0, reason="test")

        assert len(events_received) == 1
        assert events_received[0].type == EventType.TIME_ADVANCED
        assert events_received[0].data["minutes"] == 10.0
        assert events_received[0].data["reason"] == "test"

    def test_hour_passed_event(self):
        """Test HOUR_PASSED event is emitted when crossing hour boundary."""
        event_bus = EventBus()
        events_received = []

        def handler(event):
            events_received.append(event)

        event_bus.subscribe(EventType.HOUR_PASSED, handler)

        tm = TimeManager(event_bus=event_bus)

        # Advance 30 minutes - no hour passed
        tm.advance_time(30.0)
        assert len(events_received) == 0

        # Advance 40 more minutes - crosses hour boundary
        tm.advance_time(40.0)
        assert len(events_received) == 1
        assert events_received[0].type == EventType.HOUR_PASSED
        assert events_received[0].data["hours"] == 1

    def test_multiple_hours_passed_event(self):
        """Test HOUR_PASSED event handles multiple hours."""
        event_bus = EventBus()
        events_received = []

        def handler(event):
            events_received.append(event)

        event_bus.subscribe(EventType.HOUR_PASSED, handler)

        tm = TimeManager(event_bus=event_bus)

        # Advance 150 minutes (2.5 hours)
        tm.advance_time(150.0)
        assert len(events_received) == 1
        assert events_received[0].data["hours"] == 2

    def test_effect_expired_event(self):
        """Test EFFECT_EXPIRED event is emitted when effect expires."""
        event_bus = EventBus()
        events_received = []

        def handler(event):
            events_received.append(event)

        event_bus.subscribe(EventType.EFFECT_EXPIRED, handler)

        tm = TimeManager(event_bus=event_bus)

        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Shield",
            duration_minutes=1.0,
            remaining_minutes=1.0,
            target_name="Wizard"
        )

        tm.add_effect(effect)

        # Advance time to expire effect
        tm.advance_time(1.0)

        assert len(events_received) == 1
        assert events_received[0].type == EventType.EFFECT_EXPIRED
        assert events_received[0].data["source"] == "Shield"
        assert events_received[0].data["target_name"] == "Wizard"

    def test_concentration_broken_event(self):
        """Test EFFECT_EXPIRED event includes reason when concentration is broken."""
        event_bus = EventBus()
        events_received = []

        def handler(event):
            events_received.append(event)

        event_bus.subscribe(EventType.EFFECT_EXPIRED, handler)

        tm = TimeManager(event_bus=event_bus)

        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Haste",
            duration_minutes=10.0,
            remaining_minutes=10.0,
            target_name="Fighter",
            concentration=True,
            caster_name="Wizard"
        )

        tm.add_effect(effect)

        # Break concentration
        tm.remove_concentration_effects("Wizard")

        assert len(events_received) == 1
        assert events_received[0].type == EventType.EFFECT_EXPIRED
        assert events_received[0].data["reason"] == "concentration_broken"
