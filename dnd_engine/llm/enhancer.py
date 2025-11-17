# ABOUTME: LLM enhancer that subscribes to game events and generates narrative descriptions
# ABOUTME: Coordinates async LLM calls with synchronous event bus using background thread

import asyncio
import threading
from typing import Dict, Optional

from ..utils.events import Event, EventBus, EventType
from .base import LLMProvider
from .prompts import (
    build_combat_action_prompt,
    build_death_prompt,
    build_room_description_prompt,
    build_victory_prompt,
)


class LLMEnhancer:
    """
    Coordinates LLM enhancement of game events.

    Subscribes to game events and enhances descriptions using LLM.
    Falls back to basic descriptions if LLM unavailable or fails.
    """

    def __init__(
        self,
        provider: Optional[LLMProvider],
        event_bus: EventBus,
        enable_cache: bool = True
    ) -> None:
        """
        Initialize LLM enhancer.

        Args:
            provider: LLM provider or None to disable
            event_bus: Game event bus to subscribe to
            enable_cache: Whether to cache enhanced descriptions
        """
        self.provider = provider
        self.event_bus = event_bus
        self.cache: Optional[Dict[str, str]] = {} if enable_cache else None

        # Create background event loop for async tasks
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None

        if provider:
            # Start background event loop
            self._start_event_loop()

            # Subscribe to events
            self.event_bus.subscribe(
                EventType.ROOM_ENTER,
                self._handle_room_enter
            )
            self.event_bus.subscribe(
                EventType.DAMAGE_DEALT,
                self._handle_combat_action
            )
            self.event_bus.subscribe(
                EventType.COMBAT_END,
                self._handle_victory
            )
            self.event_bus.subscribe(
                EventType.CHARACTER_DEATH,
                self._handle_death
            )

    def _start_event_loop(self) -> None:
        """Start background thread with event loop for async tasks."""
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()

        # Wait for loop to be ready
        while self._loop is None:
            pass

    def _schedule_async(self, coro):
        """Schedule a coroutine to run in the background event loop."""
        if self._loop and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(coro, self._loop)

    def shutdown(self) -> None:
        """Shutdown the background event loop."""
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._loop_thread:
                self._loop_thread.join(timeout=1.0)

    def _handle_room_enter(self, event: Event) -> None:
        """
        Handle room enter event (synchronous wrapper).

        Args:
            event: ROOM_ENTER event with room data
        """
        # Schedule async task in background event loop
        self._schedule_async(self._enhance_room_description(event))

    def _handle_combat_action(self, event: Event) -> None:
        """
        Handle combat action event (synchronous wrapper).

        Args:
            event: DAMAGE_DEALT event with combat data
        """
        self._schedule_async(self._enhance_combat_action(event))

    def _handle_victory(self, event: Event) -> None:
        """
        Handle combat victory event (synchronous wrapper).

        Args:
            event: COMBAT_END event with combat data
        """
        self._schedule_async(self._enhance_victory(event))

    def _handle_death(self, event: Event) -> None:
        """
        Handle character death event (synchronous wrapper).

        Args:
            event: CHARACTER_DEATH event with character data
        """
        self._schedule_async(self._enhance_death(event))

    async def _enhance_room_description(self, event: Event) -> None:
        """
        Enhance room description when player enters.

        Args:
            event: ROOM_ENTER event with room data
        """
        if not self.provider:
            return

        room_data = event.data
        cache_key = f"room_{room_data.get('id', 'unknown')}"

        # Check cache
        if self.cache is not None and cache_key in self.cache:
            enhanced = self.cache[cache_key]
        else:
            # Generate enhancement
            prompt = build_room_description_prompt(room_data)
            enhanced = await self.provider.generate(prompt)

            # Fallback if generation failed
            if not enhanced:
                enhanced = room_data.get("description", "You enter a room.")

            # Cache result
            if self.cache is not None:
                self.cache[cache_key] = enhanced

        # Emit enhanced description
        self.event_bus.emit(Event(
            EventType.DESCRIPTION_ENHANCED,
            {"type": "room", "text": enhanced}
        ))

    async def _enhance_combat_action(self, event: Event) -> None:
        """
        Enhance combat action narration.

        Args:
            event: DAMAGE_DEALT event with combat data
        """
        if not self.provider:
            return

        # Emit started event immediately
        self.event_bus.emit(Event(
            EventType.ENHANCEMENT_STARTED,
            {"type": "combat"}
        ))

        action_data = event.data
        prompt = build_combat_action_prompt(action_data)
        enhanced = await self.provider.generate(prompt, temperature=0.8)

        # Fallback
        if not enhanced:
            attacker = action_data.get("attacker", "Someone")
            target = action_data.get("target", "the enemy")
            damage = action_data.get("damage", 0)
            enhanced = f"{attacker} strikes {target} for {damage} damage!"

        # Emit enhanced narration
        self.event_bus.emit(Event(
            EventType.DESCRIPTION_ENHANCED,
            {"type": "combat", "text": enhanced}
        ))

    async def _enhance_victory(self, event: Event) -> None:
        """
        Enhance combat victory narration.

        Args:
            event: COMBAT_END event with combat data
        """
        if not self.provider:
            return

        combat_data = event.data
        prompt = build_victory_prompt(combat_data)
        enhanced = await self.provider.generate(prompt)

        # Fallback
        if not enhanced:
            enhanced = "Victory! The enemies have been defeated."

        self.event_bus.emit(Event(
            EventType.DESCRIPTION_ENHANCED,
            {"type": "victory", "text": enhanced}
        ))

    async def _enhance_death(self, event: Event) -> None:
        """
        Enhance character death narration.

        Args:
            event: CHARACTER_DEATH event with character data
        """
        if not self.provider:
            return

        # Emit started event immediately
        self.event_bus.emit(Event(
            EventType.ENHANCEMENT_STARTED,
            {"type": "death"}
        ))

        character_data = event.data
        prompt = build_death_prompt(character_data)
        enhanced = await self.provider.generate(prompt, temperature=0.6)

        # Fallback
        if not enhanced:
            name = character_data.get("name", "The hero")
            enhanced = f"{name} has fallen..."

        self.event_bus.emit(Event(
            EventType.DESCRIPTION_ENHANCED,
            {"type": "death", "text": enhanced}
        ))
