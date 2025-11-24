# ABOUTME: Time tracking system for managing game time and timed effects
# ABOUTME: Handles duration parsing, active effect tracking, and automatic expiration

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from enum import Enum
import re
import logging

if TYPE_CHECKING:
    from dnd_engine.utils.events import EventBus

logger = logging.getLogger(__name__)


class EffectType(str, Enum):
    """Types of timed effects that can be tracked."""
    SPELL = "spell"
    CONDITION = "condition"
    BUFF = "buff"
    DEBUFF = "debuff"
    POISON = "poison"
    DISEASE = "disease"


class ModifierType(str, Enum):
    """Types of stat modifiers that effects can apply."""
    AC_SET_BASE = "ac_set_base"      # Set base AC (Mage Armor: 13 + DEX)
    AC_BONUS = "ac_bonus"            # Add to AC (Shield: +5)
    ATTACK_BONUS = "attack_bonus"    # Add to attack rolls (Bless: +1d4)
    SAVE_BONUS = "save_bonus"        # Add to saves (Bless: +1d4)
    SPEED_BONUS = "speed_bonus"      # Add to movement (Longstrider: +10)


@dataclass
class ActiveEffect:
    """
    Represents a timed effect active on a character.

    Supports both time-based (minutes/hours) and round-based (combat) durations.
    This allows short combat effects (Shield: 1 round) to work differently from
    long exploration buffs (Mage Armor: 8 hours).

    Attributes:
        effect_type: Type of effect (spell, condition, buff, etc.)
        source: What created this effect (spell name, item name, etc.)
        duration_type: How duration is tracked ("rounds", "minutes", "hours", "permanent")
        duration_value: Total duration in the appropriate unit
        remaining_value: Remaining duration before expiration
        target_name: Name of the character affected
        description: Human-readable description of the effect
        concentration: Whether this effect requires concentration
        caster_name: Name of the caster (for concentration checks)
        effect_data: Additional data specific to the effect
    """
    effect_type: EffectType
    source: str
    duration_type: str  # "rounds", "minutes", "hours", "permanent"
    duration_value: float
    remaining_value: float
    target_name: str
    description: str = ""
    concentration: bool = False
    caster_name: Optional[str] = None
    effect_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure remaining_value doesn't exceed duration."""
        if self.remaining_value > self.duration_value:
            self.remaining_value = self.duration_value

    @property
    def is_expired(self) -> bool:
        """Check if the effect has expired."""
        return self.remaining_value <= 0

    def advance_time(self, minutes: float) -> bool:
        """
        Advance time-based duration and return True if effect expired.

        Only affects effects with duration_type "minutes" or "hours".
        Round-based effects are unaffected.

        Args:
            minutes: Number of minutes to advance

        Returns:
            True if effect expired, False otherwise
        """
        if self.duration_type == "minutes":
            self.remaining_value -= minutes
        elif self.duration_type == "hours":
            self.remaining_value -= minutes / 60.0
        # Round-based effects don't advance with time
        return self.is_expired

    def advance_rounds(self, rounds: int = 1) -> bool:
        """
        Advance round-based duration and return True if effect expired.

        Only affects effects with duration_type "rounds".
        Time-based effects are unaffected.

        Args:
            rounds: Number of combat rounds to advance

        Returns:
            True if effect expired, False otherwise
        """
        if self.duration_type == "rounds":
            self.remaining_value -= rounds
        # Time-based effects don't advance with rounds
        return self.is_expired

    def get_time_remaining_display(self) -> str:
        """Get a human-readable time remaining string."""
        if self.remaining_value <= 0:
            return "Expired"

        remaining = self.remaining_value

        # Format based on duration type
        if self.duration_type == "rounds":
            rounds = int(remaining)
            if rounds == 1:
                return "1 round"
            else:
                return f"{rounds} rounds"
        elif self.duration_type == "hours":
            hours = remaining
            if hours == int(hours):
                return f"{int(hours)} hour{'s' if hours != 1 else ''}"
            else:
                return f"{hours:.1f} hours"
        else:  # minutes
            minutes = remaining
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


def parse_duration(duration_string: str) -> Optional[tuple[str, float]]:
    """
    Parse a duration string to (duration_type, duration_value).

    Supports formats like:
    - "1 round", "10 rounds" -> ("rounds", 10)
    - "1 minute", "10 minutes" -> ("minutes", 10)
    - "1 hour", "8 hours" -> ("hours", 8)
    - "up to 1 hour" (extracts "1 hour")
    - "Concentration, up to 1 minute" (extracts "1 minute")

    Args:
        duration_string: Duration string to parse

    Returns:
        Tuple of (duration_type, duration_value), or None if unparseable
        duration_type: "rounds", "minutes", "hours"
        duration_value: numeric value in that unit
    """
    if not duration_string:
        return None

    # Normalize string
    duration_string = duration_string.lower().strip()

    # Remove "up to", "concentration", commas
    duration_string = re.sub(r'(up to|concentration|,)', '', duration_string).strip()

    # Pattern: number + unit
    pattern = r'(\d+(?:\.\d+)?)\s*(second|seconds|minute|minutes|min|hour|hours|hr|round|rounds)'
    match = re.search(pattern, duration_string)

    if not match:
        return None

    value = float(match.group(1))
    unit = match.group(2)

    # Determine duration type and convert value to appropriate unit
    if unit in ['round', 'rounds']:
        return ("rounds", value)
    elif unit in ['second', 'seconds']:
        # Convert seconds to minutes for consistency
        return ("minutes", value / 60.0)
    elif unit in ['minute', 'minutes', 'min']:
        return ("minutes", value)
    elif unit in ['hour', 'hours', 'hr']:
        return ("hours", value)

    return None


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

    def __init__(self, event_bus: Optional["EventBus"] = None) -> None:
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
            minutes: Number of minutes to advance (must be positive)
            reason: Reason for time advancement (for events)

        Returns:
            List of effects that expired during this advancement
        """
        if minutes <= 0:
            if minutes < 0:
                logger.warning(f"Attempted to advance time by negative amount: {minutes} minutes (reason: {reason})")
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

    def advance_round(self, rounds: int = 1) -> List[ActiveEffect]:
        """
        Advance combat rounds and process round-based effect expirations.

        This is separate from advance_time() to handle effects that expire
        based on combat rounds (like Shield: 1 round) vs exploration time
        (like Mage Armor: 8 hours).

        Args:
            rounds: Number of combat rounds to advance

        Returns:
            List of effects that expired during this advancement
        """
        if rounds <= 0:
            return []

        # Track expired effects
        expired_effects = []

        # Advance all active round-based effects
        for effect in self.active_effects[:]:  # Copy list to allow modification
            if effect.advance_rounds(rounds):
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
                            "effect_type": effect.effect_type.value,
                            "reason": "round_ended"
                        }
                    ))

        return expired_effects

    def add_effect(self, effect: ActiveEffect) -> None:
        """
        Add a new timed effect to track.

        If an effect with the same source and target already exists, it will be
        replaced with the new effect. This allows recasting the same spell on the
        same target to refresh its duration.

        Examples:
            - Casting "Light" on Torch1, then "Light" on Torch1 again -> replaces
            - Casting "Light" on Torch1, then "Light" on Torch2 -> both active
            - Casting "Bless" on Fighter, then "Bless" on Fighter -> replaces

        Args:
            effect: The effect to add
        """
        # Check if target already has this effect from same source
        # If so, replace it with the new one (recasting refreshes duration)
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
