# ABOUTME: Unit tests for the event bus system
# ABOUTME: Tests pub/sub functionality, event types, and event handling

import pytest
from typing import List
from dnd_engine.utils.events import EventBus, Event, EventType


class TestEvent:
    """Test the Event class"""

    def test_event_creation(self):
        """Test creating an event"""
        event = Event(
            type=EventType.DAMAGE_DEALT,
            data={'attacker': 'Fighter', 'defender': 'Goblin', 'damage': 7}
        )

        assert event.type == EventType.DAMAGE_DEALT
        assert event.data['attacker'] == 'Fighter'
        assert event.data['damage'] == 7

    def test_event_with_no_data(self):
        """Test creating an event without data"""
        event = Event(type=EventType.COMBAT_START)

        assert event.type == EventType.COMBAT_START
        assert event.data == {}

    def test_event_string_representation(self):
        """Test event string representation"""
        event = Event(
            type=EventType.ATTACK_ROLL,
            data={'roll': 15}
        )

        event_str = str(event)
        assert "ATTACK_ROLL" in event_str


class TestEventBus:
    """Test the EventBus class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.bus = EventBus()
        self.received_events: List[Event] = []

    def test_bus_creation(self):
        """Test creating an event bus"""
        assert self.bus is not None

    def test_subscribe_to_event(self):
        """Test subscribing to an event type"""
        def handler(event: Event):
            self.received_events.append(event)

        self.bus.subscribe(EventType.DAMAGE_DEALT, handler)

        # Emit an event
        event = Event(type=EventType.DAMAGE_DEALT, data={'damage': 5})
        self.bus.emit(event)

        assert len(self.received_events) == 1
        assert self.received_events[0].type == EventType.DAMAGE_DEALT

    def test_multiple_subscribers(self):
        """Test multiple subscribers to the same event"""
        results = []

        def handler1(event: Event):
            results.append('handler1')

        def handler2(event: Event):
            results.append('handler2')

        self.bus.subscribe(EventType.COMBAT_START, handler1)
        self.bus.subscribe(EventType.COMBAT_START, handler2)

        self.bus.emit(Event(type=EventType.COMBAT_START))

        assert len(results) == 2
        assert 'handler1' in results
        assert 'handler2' in results

    def test_subscribe_to_different_events(self):
        """Test subscribing to different event types"""
        damage_events = []
        heal_events = []

        def damage_handler(event: Event):
            damage_events.append(event)

        def heal_handler(event: Event):
            heal_events.append(event)

        self.bus.subscribe(EventType.DAMAGE_DEALT, damage_handler)
        self.bus.subscribe(EventType.HEALING_DONE, heal_handler)

        # Emit different events
        self.bus.emit(Event(type=EventType.DAMAGE_DEALT, data={'damage': 5}))
        self.bus.emit(Event(type=EventType.HEALING_DONE, data={'amount': 3}))
        self.bus.emit(Event(type=EventType.DAMAGE_DEALT, data={'damage': 2}))

        assert len(damage_events) == 2
        assert len(heal_events) == 1

    def test_unsubscribe_from_event(self):
        """Test unsubscribing from an event"""
        def handler(event: Event):
            self.received_events.append(event)

        # Subscribe
        self.bus.subscribe(EventType.DAMAGE_DEALT, handler)

        # Emit event - should be received
        self.bus.emit(Event(type=EventType.DAMAGE_DEALT))
        assert len(self.received_events) == 1

        # Unsubscribe
        self.bus.unsubscribe(EventType.DAMAGE_DEALT, handler)

        # Emit event - should NOT be received
        self.bus.emit(Event(type=EventType.DAMAGE_DEALT))
        assert len(self.received_events) == 1  # Still just 1

    def test_emit_to_no_subscribers(self):
        """Test emitting an event with no subscribers (should not error)"""
        # Should not raise an exception
        self.bus.emit(Event(type=EventType.COMBAT_START))

    def test_event_data_passed_to_handler(self):
        """Test that event data is correctly passed to handlers"""
        received_data = None

        def handler(event: Event):
            nonlocal received_data
            received_data = event.data

        self.bus.subscribe(EventType.ATTACK_ROLL, handler)

        test_data = {'attacker': 'Wizard', 'roll': 18}
        self.bus.emit(Event(type=EventType.ATTACK_ROLL, data=test_data))

        assert received_data == test_data

    def test_handler_exception_doesnt_break_bus(self):
        """Test that an exception in one handler doesn't prevent others from running"""
        results = []

        def failing_handler(event: Event):
            raise ValueError("Handler error!")

        def working_handler(event: Event):
            results.append('success')

        self.bus.subscribe(EventType.DAMAGE_DEALT, failing_handler)
        self.bus.subscribe(EventType.DAMAGE_DEALT, working_handler)

        # Should not raise, and working_handler should still run
        self.bus.emit(Event(type=EventType.DAMAGE_DEALT))

        assert 'success' in results

    def test_clear_all_subscribers(self):
        """Test clearing all subscribers for an event type"""
        def handler1(event: Event):
            self.received_events.append(event)

        def handler2(event: Event):
            self.received_events.append(event)

        self.bus.subscribe(EventType.COMBAT_START, handler1)
        self.bus.subscribe(EventType.COMBAT_START, handler2)

        # Clear all subscribers
        self.bus.clear_subscribers(EventType.COMBAT_START)

        # Emit event - should not be received
        self.bus.emit(Event(type=EventType.COMBAT_START))
        assert len(self.received_events) == 0

    def test_get_subscriber_count(self):
        """Test getting the number of subscribers for an event"""
        def handler1(event: Event):
            pass

        def handler2(event: Event):
            pass

        assert self.bus.subscriber_count(EventType.DAMAGE_DEALT) == 0

        self.bus.subscribe(EventType.DAMAGE_DEALT, handler1)
        assert self.bus.subscriber_count(EventType.DAMAGE_DEALT) == 1

        self.bus.subscribe(EventType.DAMAGE_DEALT, handler2)
        assert self.bus.subscriber_count(EventType.DAMAGE_DEALT) == 2

        self.bus.unsubscribe(EventType.DAMAGE_DEALT, handler1)
        assert self.bus.subscriber_count(EventType.DAMAGE_DEALT) == 1


class TestEventTypes:
    """Test that all required event types are defined"""

    def test_required_event_types_exist(self):
        """Test that all MVP event types are defined"""
        required_types = [
            'COMBAT_START',
            'COMBAT_END',
            'TURN_START',
            'TURN_END',
            'ATTACK_ROLL',
            'DAMAGE_DEALT',
            'HEALING_DONE',
            'CHARACTER_DEATH',
            'ROOM_ENTER',
            'ITEM_ACQUIRED',
            'LEVEL_UP',
            'SKILL_CHECK',
        ]

        for type_name in required_types:
            assert hasattr(EventType, type_name), f"EventType.{type_name} should be defined"

    def test_event_type_values(self):
        """Test that event types have appropriate values"""
        # Event types should be unique
        event_values = [e.value for e in EventType]
        assert len(event_values) == len(set(event_values)), "Event type values should be unique"
