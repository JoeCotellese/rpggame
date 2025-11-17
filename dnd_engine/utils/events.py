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
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    ATTACK_ROLL = "attack_roll"
    DAMAGE_DEALT = "damage_dealt"
    HEALING_DONE = "healing_done"
    CHARACTER_DEATH = "character_death"

    # Exploration events
    ROOM_ENTER = "room_enter"
    ITEM_ACQUIRED = "item_acquired"

    # Inventory events
    ITEM_EQUIPPED = "item_equipped"
    ITEM_UNEQUIPPED = "item_unequipped"
    ITEM_USED = "item_used"
    GOLD_ACQUIRED = "gold_acquired"

    # Character progression events
    LEVEL_UP = "level_up"

    # Skill check events
    SKILL_CHECK = "skill_check"

    # LLM enhancement events
    ENHANCEMENT_STARTED = "enhancement_started"
    DESCRIPTION_ENHANCED = "description_enhanced"


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
