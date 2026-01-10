# ABOUTME: Base classes for spell effect handlers.
# ABOUTME: Defines SpellEffect ABC and SpellEffectResult for the plugin architecture.

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dnd_engine.core.creature import Creature
    from dnd_engine.core.game_state import GameState
    from dnd_engine.systems.time_manager import ActiveEffect


@dataclass
class SpellEffectResult:
    """Result of applying a spell effect."""

    success: bool
    message: str
    effect_data: dict[str, Any] = field(default_factory=dict)


class SpellEffect(ABC):
    """
    Base class for spell effect handlers.

    Each handler manages a category of spell effects (e.g., illumination, detection).
    Spell JSON data declares an effect_type that maps to a registered handler.

    To add a new effect type:
    1. Create a new module in dnd_engine/spells/effects/
    2. Subclass SpellEffect and set the effect_type class attribute
    3. Implement the apply() method
    4. Register the handler in effects/__init__.py
    5. Add effect_type to spell data in spells.json
    """

    effect_type: str  # Must match spell JSON "effect.effect_type"

    @abstractmethod
    def apply(
        self,
        spell_data: dict[str, Any],
        caster: "Creature",
        target: "Creature | None",
        game_state: "GameState",
    ) -> SpellEffectResult:
        """
        Called when the spell is cast.

        Args:
            spell_data: Full spell definition from spells.json
            caster: The creature casting the spell
            target: The target creature (may be None for self-targeted spells)
            game_state: Current game state for accessing other systems

        Returns:
            SpellEffectResult with success status, message, and effect_data
            to store in the ActiveEffect
        """
        ...

    def query(
        self,
        game_state: "GameState",
        query_type: str,
        **kwargs: Any,
    ) -> Any:
        """
        Called by game systems to check effect status.

        Override this to provide custom query handling for your effect type.
        Common query_type values might be:
        - "get_light_level" for illumination effects
        - "has_capability" for manipulation effects
        - "get_revealed_info" for detection effects

        Args:
            game_state: Current game state
            query_type: String identifying what information is requested
            **kwargs: Additional context for the query

        Returns:
            Query-specific result, or None if query not supported
        """
        return None

    def on_expire(
        self,
        effect: "ActiveEffect",
        game_state: "GameState",
    ) -> str | None:
        """
        Called when the spell effect expires.

        Override to perform cleanup or provide expiration message.

        Args:
            effect: The ActiveEffect that is expiring
            game_state: Current game state

        Returns:
            Optional message to display, or None
        """
        return None

    def get_available_actions(
        self,
        effect: "ActiveEffect",
        game_state: "GameState",
    ) -> list[dict[str, Any]]:
        """
        Return actions this effect enables while active.

        For spells like Mage Hand that grant new interaction options,
        return a list of action definitions that the UI can present.

        Args:
            effect: The active spell effect
            game_state: Current game state

        Returns:
            List of action dicts with keys:
            - "id": Unique action identifier
            - "name": Display name
            - "description": What the action does
            - "handler": Method name to call on this effect class
        """
        return []

    def handle_action(
        self,
        action_id: str,
        effect: "ActiveEffect",
        game_state: "GameState",
        **kwargs: Any,
    ) -> SpellEffectResult:
        """
        Handle a spell-granted action.

        Called when player uses an action from get_available_actions().

        Args:
            action_id: The action identifier
            effect: The active spell effect
            game_state: Current game state
            **kwargs: Action-specific parameters

        Returns:
            SpellEffectResult describing the outcome
        """
        return SpellEffectResult(
            success=False,
            message=f"Action '{action_id}' not implemented for {self.effect_type}",
        )
