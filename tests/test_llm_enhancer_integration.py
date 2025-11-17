"""Integration tests for LLM enhancer with event bus."""

import asyncio
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from dnd_engine.llm.base import LLMProvider
from dnd_engine.utils.events import Event, EventBus, EventType


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, response: Optional[str] = "Enhanced description") -> None:
        super().__init__(api_key="test", model="test")
        self.response = response
        self.call_count = 0
        self.last_prompt: Optional[str] = None

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7
    ) -> Optional[str]:
        """Mock generate method."""
        self.call_count += 1
        self.last_prompt = prompt
        await asyncio.sleep(0.01)  # Simulate async call
        return self.response

    def get_provider_name(self) -> str:
        """Return mock provider name."""
        return "Mock Provider"


class TestLLMEnhancer:
    """Test LLM enhancer integration with event bus."""

    @pytest.mark.asyncio
    async def test_enhancer_subscribes_to_events(self) -> None:
        """Test that enhancer subscribes to correct event types."""
        from dnd_engine.llm.enhancer import LLMEnhancer

        mock_provider = MockLLMProvider()
        event_bus = EventBus()
        enhancer = LLMEnhancer(mock_provider, event_bus)

        # Verify subscriptions
        assert event_bus.subscriber_count(EventType.ROOM_ENTER) > 0
        assert event_bus.subscriber_count(EventType.DAMAGE_DEALT) > 0
        assert event_bus.subscriber_count(EventType.COMBAT_END) > 0
        assert event_bus.subscriber_count(EventType.CHARACTER_DEATH) > 0

    @pytest.mark.asyncio
    async def test_enhancer_room_description(self) -> None:
        """Test room description enhancement."""
        from dnd_engine.llm.enhancer import LLMEnhancer

        mock_provider = MockLLMProvider(response="A dark and foreboding chamber.")
        event_bus = EventBus()
        enhancer = LLMEnhancer(mock_provider, event_bus)

        # Track enhanced descriptions
        enhanced_descriptions = []

        def capture_enhancement(event: Event) -> None:
            enhanced_descriptions.append(event.data)

        event_bus.subscribe(EventType.DESCRIPTION_ENHANCED, capture_enhancement)

        # Emit room enter event
        room_data = {
            "id": "room_1",
            "name": "Torture Chamber",
            "description": "A dark room"
        }
        event_bus.emit(Event(EventType.ROOM_ENTER, room_data))

        # Wait for async processing
        await asyncio.sleep(0.1)

        # Verify enhancement was emitted
        assert len(enhanced_descriptions) > 0
        assert enhanced_descriptions[0]["type"] == "room"
        assert "dark and foreboding" in enhanced_descriptions[0]["text"]

    @pytest.mark.asyncio
    async def test_enhancer_combat_action(self) -> None:
        """Test combat action enhancement."""
        from dnd_engine.llm.enhancer import LLMEnhancer

        mock_provider = MockLLMProvider(
            response="The sword slashes through the air!"
        )
        event_bus = EventBus()
        enhancer = LLMEnhancer(mock_provider, event_bus)

        enhanced_descriptions = []

        def capture_enhancement(event: Event) -> None:
            enhanced_descriptions.append(event.data)

        event_bus.subscribe(EventType.DESCRIPTION_ENHANCED, capture_enhancement)

        # Emit damage dealt event
        action_data = {
            "attacker": "Thorin",
            "target": "Goblin",
            "weapon": "longsword",
            "damage": 8,
            "hit": True
        }
        event_bus.emit(Event(EventType.DAMAGE_DEALT, action_data))

        # Wait for async processing
        await asyncio.sleep(0.1)

        # Verify enhancement
        assert len(enhanced_descriptions) > 0
        assert enhanced_descriptions[0]["type"] == "combat"
        assert "sword slashes" in enhanced_descriptions[0]["text"]

    @pytest.mark.asyncio
    async def test_enhancer_caching(self) -> None:
        """Test that room descriptions are cached."""
        from dnd_engine.llm.enhancer import LLMEnhancer

        mock_provider = MockLLMProvider(response="Cached description")
        event_bus = EventBus()
        enhancer = LLMEnhancer(mock_provider, event_bus, enable_cache=True)

        room_data = {
            "id": "room_1",
            "name": "Chamber",
            "description": "A room"
        }

        # Emit same room twice
        event_bus.emit(Event(EventType.ROOM_ENTER, room_data))
        await asyncio.sleep(0.1)

        event_bus.emit(Event(EventType.ROOM_ENTER, room_data))
        await asyncio.sleep(0.1)

        # LLM should only be called once due to caching
        assert mock_provider.call_count == 1

    @pytest.mark.asyncio
    async def test_enhancer_no_caching(self) -> None:
        """Test that caching can be disabled."""
        from dnd_engine.llm.enhancer import LLMEnhancer

        mock_provider = MockLLMProvider(response="Not cached")
        event_bus = EventBus()
        enhancer = LLMEnhancer(mock_provider, event_bus, enable_cache=False)

        room_data = {
            "id": "room_1",
            "name": "Chamber",
            "description": "A room"
        }

        # Emit same room twice
        event_bus.emit(Event(EventType.ROOM_ENTER, room_data))
        await asyncio.sleep(0.1)

        event_bus.emit(Event(EventType.ROOM_ENTER, room_data))
        await asyncio.sleep(0.1)

        # LLM should be called twice without caching
        assert mock_provider.call_count == 2

    @pytest.mark.asyncio
    async def test_enhancer_fallback_on_failure(self) -> None:
        """Test fallback to basic description when LLM fails."""
        from dnd_engine.llm.enhancer import LLMEnhancer

        # Provider that returns None (simulates failure)
        mock_provider = MockLLMProvider(response=None)
        event_bus = EventBus()
        enhancer = LLMEnhancer(mock_provider, event_bus)

        enhanced_descriptions = []

        def capture_enhancement(event: Event) -> None:
            enhanced_descriptions.append(event.data)

        event_bus.subscribe(EventType.DESCRIPTION_ENHANCED, capture_enhancement)

        # Emit room enter event
        room_data = {
            "id": "room_1",
            "name": "Chamber",
            "description": "A dark room"
        }
        event_bus.emit(Event(EventType.ROOM_ENTER, room_data))

        # Wait for async processing
        await asyncio.sleep(0.1)

        # Verify fallback description is used
        assert len(enhanced_descriptions) > 0
        assert "dark room" in enhanced_descriptions[0]["text"]

    @pytest.mark.asyncio
    async def test_enhancer_none_provider(self) -> None:
        """Test that enhancer with None provider doesn't crash."""
        from dnd_engine.llm.enhancer import LLMEnhancer

        event_bus = EventBus()
        enhancer = LLMEnhancer(None, event_bus)

        # Should not subscribe to events when provider is None
        assert event_bus.subscriber_count(EventType.ROOM_ENTER) == 0

    @pytest.mark.asyncio
    async def test_enhancer_victory(self) -> None:
        """Test combat victory enhancement."""
        from dnd_engine.llm.enhancer import LLMEnhancer

        mock_provider = MockLLMProvider(
            response="The heroes stand victorious!"
        )
        event_bus = EventBus()
        enhancer = LLMEnhancer(mock_provider, event_bus)

        enhanced_descriptions = []

        def capture_enhancement(event: Event) -> None:
            enhanced_descriptions.append(event.data)

        event_bus.subscribe(EventType.DESCRIPTION_ENHANCED, capture_enhancement)

        # Emit combat end event
        combat_data = {
            "enemies": ["Goblin", "Orc"],
            "final_blow": "Thorin struck down the orc"
        }
        event_bus.emit(Event(EventType.COMBAT_END, combat_data))

        # Wait for async processing
        await asyncio.sleep(0.1)

        # Verify enhancement
        assert len(enhanced_descriptions) > 0
        assert enhanced_descriptions[0]["type"] == "victory"
        assert "victorious" in enhanced_descriptions[0]["text"]

    @pytest.mark.asyncio
    async def test_enhancer_death(self) -> None:
        """Test character death enhancement."""
        from dnd_engine.llm.enhancer import LLMEnhancer

        mock_provider = MockLLMProvider(
            response="The hero falls, their quest unfulfilled."
        )
        event_bus = EventBus()
        enhancer = LLMEnhancer(mock_provider, event_bus)

        enhanced_descriptions = []

        def capture_enhancement(event: Event) -> None:
            enhanced_descriptions.append(event.data)

        event_bus.subscribe(EventType.DESCRIPTION_ENHANCED, capture_enhancement)

        # Emit character death event
        character_data = {
            "name": "Thorin",
            "cause": "fell to a goblin's blade"
        }
        event_bus.emit(Event(EventType.CHARACTER_DEATH, character_data))

        # Wait for async processing
        await asyncio.sleep(0.1)

        # Verify enhancement
        assert len(enhanced_descriptions) > 0
        assert enhanced_descriptions[0]["type"] == "death"
        assert "falls" in enhanced_descriptions[0]["text"]
