# ABOUTME: LLM enhancer that subscribes to game events and generates narrative descriptions
# ABOUTME: Coordinates async LLM calls with synchronous event bus using task creation

import asyncio
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

        # Subscribe to events only if provider is available
        if provider:
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

    def _handle_room_enter(self, event: Event) -> None:
        """
        Handle room enter event (synchronous wrapper).

        Args:
            event: ROOM_ENTER event with room data
        """
        # Create async task for LLM generation
        asyncio.create_task(self._enhance_room_description(event))

    def _handle_combat_action(self, event: Event) -> None:
        """
        Handle combat action event (synchronous wrapper).

        Args:
            event: DAMAGE_DEALT event with combat data
        """
        asyncio.create_task(self._enhance_combat_action(event))

    def _handle_victory(self, event: Event) -> None:
        """
        Handle combat victory event (synchronous wrapper).

        Args:
            event: COMBAT_END event with combat data
        """
        asyncio.create_task(self._enhance_victory(event))

    def _handle_death(self, event: Event) -> None:
        """
        Handle character death event (synchronous wrapper).

        Args:
            event: CHARACTER_DEATH event with character data
        """
        asyncio.create_task(self._enhance_death(event))

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
