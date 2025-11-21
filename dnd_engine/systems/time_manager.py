# ABOUTME: Time tracking system for managing game time and timed effects
# ABOUTME: Handles duration parsing, active effect tracking, and automatic expiration

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import re


class EffectType(str, Enum):
    """Types of timed effects that can be tracked."""
    SPELL = "spell"
    CONDITION = "condition"
    BUFF = "buff"
    DEBUFF = "debuff"
    POISON = "poison"
    DISEASE = "disease"


@dataclass
class ActiveEffect:
    """
    Represents a timed effect active on a character.

    Attributes:
        effect_type: Type of effect (spell, condition, buff, etc.)
        source: What created this effect (spell name, item name, etc.)
        duration_minutes: Total duration in minutes
        remaining_minutes: Minutes remaining before expiration
        target_name: Name of the character affected
        description: Human-readable description of the effect
        concentration: Whether this effect requires concentration
        caster_name: Name of the caster (for concentration checks)
        effect_data: Additional data specific to the effect
    """
    effect_type: EffectType
    source: str
    duration_minutes: float
    remaining_minutes: float
    target_name: str
    description: str = ""
    concentration: bool = False
    caster_name: Optional[str] = None
    effect_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure remaining_minutes doesn't exceed duration."""
        if self.remaining_minutes > self.duration_minutes:
            self.remaining_minutes = self.duration_minutes

    @property
    def is_expired(self) -> bool:
        """Check if the effect has expired."""
        return self.remaining_minutes <= 0

    def advance_time(self, minutes: float) -> bool:
        """
        Advance time and return True if effect expired.

        Args:
            minutes: Number of minutes to advance

        Returns:
            True if effect expired, False otherwise
        """
        self.remaining_minutes -= minutes
        return self.is_expired

    def get_time_remaining_display(self) -> str:
        """Get a human-readable time remaining string."""
        if self.remaining_minutes <= 0:
            return "Expired"

        minutes = self.remaining_minutes

        # Convert to appropriate unit
        if minutes < 1:
            seconds = int(minutes * 60)
            return f"{seconds} seconds"
        elif minutes < 60:
            if minutes == int(minutes):
                return f"{int(minutes)} minute{'s' if minutes != 1 else ''}"
            else:
                return f"{minutes:.1f} minutes"
        else:
            hours = minutes / 60
            if hours == int(hours):
                return f"{int(hours)} hour{'s' if hours != 1 else ''}"
            else:
                return f"{hours:.1f} hours"


def parse_duration_to_minutes(duration_string: str) -> Optional[float]:
    """
    Parse a duration string to minutes.

    Supports formats like:
    - "1 minute", "10 minutes"
    - "1 hour", "8 hours"
    - "1 round", "10 rounds" (1 round = 6 seconds = 0.1 minutes)
    - "up to 1 hour" (extracts "1 hour")
    - "Concentration, up to 1 minute" (extracts "1 minute")

    Args:
        duration_string: Duration string to parse

    Returns:
        Duration in minutes, or None if unparseable
    """
    if not duration_string:
        return None

    # Normalize string
    duration_string = duration_string.lower().strip()

    # Remove "up to", "concentration", commas
    duration_string = re.sub(r'(up to|concentration|,)', '', duration_string).strip()

    # Pattern: number + unit
    # Matches: "1 minute", "10 minutes", "1.5 hours"
    pattern = r'(\d+(?:\.\d+)?)\s*(second|seconds|minute|minutes|min|hour|hours|hr|round|rounds)'
    match = re.search(pattern, duration_string)

    if not match:
        return None

    value = float(match.group(1))
    unit = match.group(2)

    # Convert to minutes
    if unit in ['second', 'seconds']:
        return value / 60.0
    elif unit in ['minute', 'minutes', 'min']:
        return value
    elif unit in ['hour', 'hours', 'hr']:
        return value * 60.0
    elif unit in ['round', 'rounds']:
        # 1 round = 6 seconds = 0.1 minutes
        return value * 0.1

    return None


def format_minutes_to_display(minutes: float) -> str:
    """
    Format minutes to a human-readable display string.

    Args:
        minutes: Number of minutes

    Returns:
        Human-readable string (e.g., "1 hour, 30 minutes")
    """
    if minutes < 1:
        seconds = int(minutes * 60)
        return f"{seconds} second{'s' if seconds != 1 else ''}"

    if minutes < 60:
        if minutes == int(minutes):
            return f"{int(minutes)} minute{'s' if minutes != 1 else ''}"
        else:
            return f"{minutes:.1f} minutes"

    hours = int(minutes // 60)
    remaining_minutes = int(minutes % 60)

    if remaining_minutes == 0:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    else:
        return f"{hours} hour{'s' if hours != 1 else ''}, {remaining_minutes} minute{'s' if remaining_minutes != 1 else ''}"


class TimeManager:
    """
    Manages game time and timed effects.

    Tracks elapsed time in minutes and manages active effects that expire
    over time. Emits events when time advances and effects expire.
    """

    def __init__(self, event_bus=None):
        """
        Initialize the TimeManager.

        Args:
            event_bus: Optional event bus for emitting time events
        """
        self.event_bus = event_bus
        self.elapsed_minutes: float = 0.0
        self.active_effects: List[ActiveEffect] = []

    def get_elapsed_time_display(self) -> str:
        """Get a human-readable display of elapsed game time."""
        total_minutes = self.elapsed_minutes

        days = int(total_minutes // (24 * 60))
        remaining_minutes = total_minutes % (24 * 60)
        hours = int(remaining_minutes // 60)
        minutes = int(remaining_minutes % 60)

        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0 or not parts:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")

        return ", ".join(parts)

    def advance_time(self, minutes: float, reason: str = "") -> List[ActiveEffect]:
        """
        Advance game time and process effect expirations.

        Args:
            minutes: Number of minutes to advance
            reason: Reason for time advancement (for events)

        Returns:
            List of effects that expired during this advancement
        """
        if minutes <= 0:
            return []

        old_elapsed = self.elapsed_minutes
        self.elapsed_minutes += minutes

        # Track expired effects
        expired_effects = []

        # Advance all active effects
        for effect in self.active_effects[:]:  # Copy list to allow modification
            if effect.advance_time(minutes):
                expired_effects.append(effect)
                self.active_effects.remove(effect)

                # Emit effect expired event
                if self.event_bus:
                    from dnd_engine.utils.events import EventType, Event
                    self.event_bus.emit(Event(
                        EventType.EFFECT_EXPIRED,
                        {
                            "effect": effect,
                            "target_name": effect.target_name,
                            "source": effect.source,
                            "effect_type": effect.effect_type.value
                        }
                    ))

        # Emit time advanced event
        if self.event_bus:
            from dnd_engine.utils.events import EventType, Event
            self.event_bus.emit(Event(
                EventType.TIME_ADVANCED,
                {
                    "minutes": minutes,
                    "elapsed_minutes": self.elapsed_minutes,
                    "reason": reason
                }
            ))

        # Check if we passed an hour boundary
        old_hours = int(old_elapsed // 60)
        new_hours = int(self.elapsed_minutes // 60)
        if new_hours > old_hours and self.event_bus:
            from dnd_engine.utils.events import EventType, Event
            hours_passed = new_hours - old_hours
            self.event_bus.emit(Event(
                EventType.HOUR_PASSED,
                {
                    "hours": hours_passed,
                    "total_hours": new_hours
                }
            ))

        return expired_effects

    def add_effect(self, effect: ActiveEffect) -> None:
        """
        Add a new timed effect to track.

        Args:
            effect: The effect to add
        """
        # Check if target already has this effect from same source
        # If so, replace it with the new one
        self.active_effects = [
            e for e in self.active_effects
            if not (e.target_name == effect.target_name and e.source == effect.source)
        ]

        self.active_effects.append(effect)

    def remove_effect(self, target_name: str, source: str) -> Optional[ActiveEffect]:
        """
        Remove a specific effect by target and source.

        Args:
            target_name: Name of the affected character
            source: Source of the effect (spell name, etc.)

        Returns:
            The removed effect, or None if not found
        """
        for effect in self.active_effects:
            if effect.target_name == target_name and effect.source == source:
                self.active_effects.remove(effect)
                return effect
        return None

    def remove_concentration_effects(self, caster_name: str) -> List[ActiveEffect]:
        """
        Remove all concentration effects from a specific caster.

        Args:
            caster_name: Name of the caster who lost concentration

        Returns:
            List of effects that were removed
        """
        removed = []
        for effect in self.active_effects[:]:
            if effect.concentration and effect.caster_name == caster_name:
                self.active_effects.remove(effect)
                removed.append(effect)

                # Emit effect expired event
                if self.event_bus:
                    from dnd_engine.utils.events import EventType, Event
                    self.event_bus.emit(Event(
                        EventType.EFFECT_EXPIRED,
                        {
                            "effect": effect,
                            "target_name": effect.target_name,
                            "source": effect.source,
                            "effect_type": effect.effect_type.value,
                            "reason": "concentration_broken"
                        }
                    ))

        return removed

    def get_effects_for_character(self, character_name: str) -> List[ActiveEffect]:
        """
        Get all active effects for a specific character.

        Args:
            character_name: Name of the character

        Returns:
            List of active effects on that character
        """
        return [e for e in self.active_effects if e.target_name == character_name]

    def get_all_effects(self) -> List[ActiveEffect]:
        """Get all active effects."""
        return self.active_effects.copy()

    def clear_all_effects(self) -> None:
        """Remove all active effects."""
        self.active_effects.clear()
