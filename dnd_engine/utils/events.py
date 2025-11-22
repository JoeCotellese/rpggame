# ABOUTME: Event bus system for pub/sub messaging between game components
# ABOUTME: Enables loose coupling between game engine, LLM enhancement, and UI layers

from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Any
import logging


logger = logging.getLogger(__name__)


class EventType(Enum):
    """
    Types of events that can occur in the game.

    Events enable loose coupling between systems by allowing components
    to react to game state changes without direct dependencies.
    """
    # Combat events
    COMBAT_START = "combat_start"
    COMBAT_END = "combat_end"
    COMBAT_FLED = "combat_fled"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    ATTACK_ROLL = "attack_roll"
    SAVING_THROW = "saving_throw"
    DAMAGE_DEALT = "damage_dealt"
    DAMAGE_TAKEN = "damage_taken"
    HEALING_DONE = "healing_done"
    CHARACTER_DEATH = "character_death"
    SNEAK_ATTACK = "sneak_attack"
    DEATH_SAVE = "death_save"
    SPELL_SAVE = "spell_save"
    DAMAGE_AT_ZERO_HP = "damage_at_zero_hp"
    MASSIVE_DAMAGE_DEATH = "massive_damage_death"
    CHARACTER_STABILIZED = "character_stabilized"

    # Exploration events
    ROOM_ENTER = "room_enter"
    ITEM_ACQUIRED = "item_acquired"

    # Inventory events
    ITEM_EQUIPPED = "item_equipped"
    ITEM_UNEQUIPPED = "item_unequipped"
    ITEM_USED = "item_used"
    GOLD_ACQUIRED = "gold_acquired"
    CONDITION_APPLIED = "condition_applied"
    CONDITION_REMOVED = "condition_removed"
    BUFF_APPLIED = "buff_applied"

    # Character progression events
    LEVEL_UP = "level_up"
    FEATURE_GRANTED = "feature_granted"

    # Skill check events
    SKILL_CHECK = "skill_check"
    ABILITY_CHECK = "ability_check"

    # LLM enhancement events
    ENHANCEMENT_STARTED = "enhancement_started"
    DESCRIPTION_ENHANCED = "description_enhanced"

    # Reset system events
    RESET_STARTED = "reset_started"
    RESET_COMPLETE = "reset_complete"

    # Rest system events
    SHORT_REST = "short_rest"
    LONG_REST = "long_rest"
    SPELLS_PREPARED = "spells_prepared"

    # Spellcasting events
    SPELL_CAST = "spell_cast"

    # Time tracking events
    TIME_ADVANCED = "time_advanced"
    HOUR_PASSED = "hour_passed"
    EFFECT_EXPIRED = "effect_expired"


@dataclass
class Event:
    """
    Represents a game event with associated data.

    Events are emitted by game systems and can be subscribed to by
    other components (LLM enhancement, UI, logging, etc.).
    """
    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """String representation of the event"""
        return f"Event({self.type.name}, data={self.data})"


# Type alias for event handler functions
EventHandler = Callable[[Event], None]


class EventBus:
    """
    Central event bus for pub/sub messaging.

    Components can:
    - Subscribe to event types with handler functions
    - Emit events that trigger all subscribed handlers
    - Unsubscribe when no longer interested

    This enables loose coupling: the game engine emits events without
    knowing what systems are listening, and systems can react to events
    without modifying the game engine.
    """

    def __init__(self):
        """Initialize the event bus."""
        # Map of event type -> list of handler functions
        self._subscribers: Dict[EventType, List[EventHandler]] = {}

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """
        Subscribe to an event type.

        Args:
            event_type: The type of event to subscribe to
            handler: Function to call when event is emitted
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """
        Unsubscribe from an event type.

        Args:
            event_type: The type of event to unsubscribe from
            handler: The handler function to remove
        """
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
            except ValueError:
                # Handler wasn't in the list, that's okay
                pass

    def emit(self, event: Event) -> None:
        """
        Emit an event to all subscribers.

        All handlers subscribed to the event type will be called with the event.
        If a handler raises an exception, it's logged but doesn't prevent
        other handlers from running.

        Args:
            event: The event to emit
        """
        # Log the event if debug mode is enabled
        from dnd_engine.utils.logging_config import get_logging_config
        logging_config = get_logging_config()
        if logging_config and logging_config.debug_enabled:
            logging_config.log_event(event.type.name, event.data)

        if event.type not in self._subscribers:
            return

        for handler in self._subscribers[event.type]:
            try:
                handler(event)
            except Exception as e:
                # Log the exception but continue calling other handlers
                logger.error(
                    f"Error in event handler for {event.type.value}: {e}",
                    exc_info=True
                )

    def clear_subscribers(self, event_type: EventType) -> None:
        """
        Remove all subscribers for an event type.

        Args:
            event_type: The event type to clear
        """
        if event_type in self._subscribers:
            self._subscribers[event_type].clear()

    def subscriber_count(self, event_type: EventType) -> int:
        """
        Get the number of subscribers for an event type.

        Args:
            event_type: The event type to check

        Returns:
            Number of subscribers
        """
        return len(self._subscribers.get(event_type, []))

    def clear_all(self) -> None:
        """Remove all subscribers from all event types."""
        self._subscribers.clear()
