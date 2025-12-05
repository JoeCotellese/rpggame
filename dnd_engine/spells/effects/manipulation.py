# ABOUTME: Manipulation spell effect handler for Mage Hand, Unseen Servant, etc.
# ABOUTME: Provides remote interaction capabilities during exploration.

from typing import TYPE_CHECKING, Any

from .base import SpellEffect, SpellEffectResult

if TYPE_CHECKING:
    from dnd_engine.core.creature import Creature
    from dnd_engine.core.game_state import GameState
    from dnd_engine.systems.time_manager import ActiveEffect


class ManipulationEffect(SpellEffect):
    """
    Handler for spells that enable remote manipulation.

    Supported spells:
    - Mage Hand: Spectral hand for manipulating objects at range
    - Unseen Servant: Invisible force that performs simple tasks

    Effect data stored in ActiveEffect:
    - capabilities: List of granted capabilities (e.g., "interact_at_range")
    - range_ft: Maximum range for manipulation
    - weight_limit_lb: Maximum weight that can be manipulated
    """

    effect_type = "manipulation"

    def apply(
        self,
        spell_data: dict[str, Any],
        caster: "Creature",
        target: "Creature | None",
        game_state: "GameState",
    ) -> SpellEffectResult:
        """Apply manipulation effect when spell is cast."""
        effect_config = spell_data.get("effect", {})
        spell_name = spell_data.get("name", "Unknown Spell")

        # Default capabilities based on spell
        capabilities = effect_config.get(
            "capabilities",
            ["interact_at_range", "trigger_pressure_plates"],
        )
        range_ft = effect_config.get("range_ft", spell_data.get("range_ft", 30))
        weight_limit_lb = effect_config.get("weight_limit_lb", 10)

        # Build descriptive message
        message = self._build_cast_message(spell_name, caster.name, range_ft)

        return SpellEffectResult(
            success=True,
            message=message,
            effect_data={
                "spell_name": spell_name,
                "capabilities": capabilities,
                "range_ft": range_ft,
                "weight_limit_lb": weight_limit_lb,
                "caster_name": caster.name,
            },
        )

    def _build_cast_message(
        self, spell_name: str, caster_name: str, range_ft: int
    ) -> str:
        """Build a descriptive message for the spell cast."""
        spell_lower = spell_name.lower()

        if "mage hand" in spell_lower:
            return (
                f"A spectral, floating hand appears near {caster_name}. "
                f"It can manipulate objects up to {range_ft} feet away."
            )
        elif "unseen servant" in spell_lower:
            return (
                f"An invisible force materializes, ready to serve {caster_name}. "
                f"It can perform simple tasks within {range_ft} feet."
            )
        else:
            return (
                f"{caster_name} gains the ability to manipulate objects "
                f"at a distance of up to {range_ft} feet."
            )

    def query(
        self,
        game_state: "GameState",
        query_type: str,
        **kwargs: Any,
    ) -> Any:
        """
        Query manipulation effects.

        Supported queries:
        - "has_capability": Check if a specific capability is active
          kwargs: capability (str), character_name (str, optional)
        - "get_manipulation_range": Get max manipulation range
          kwargs: character_name (str, optional)
        """
        if query_type == "has_capability":
            capability = kwargs.get("capability")
            character_name = kwargs.get("character_name")
            return self._has_capability(game_state, capability, character_name)
        elif query_type == "get_manipulation_range":
            character_name = kwargs.get("character_name")
            return self._get_manipulation_range(game_state, character_name)
        return None

    def _has_capability(
        self,
        game_state: "GameState",
        capability: str | None,
        character_name: str | None,
    ) -> bool:
        """Check if a manipulation capability is active."""
        if not capability:
            return False

        from dnd_engine.systems.time_manager import EffectType

        for effect in game_state.time_manager.get_all_effects():
            if effect.effect_type != EffectType.SPELL:
                continue

            # Filter by character if specified
            if character_name and effect.effect_data.get("caster_name") != character_name:
                continue

            capabilities = effect.effect_data.get("capabilities", [])
            if capability in capabilities:
                return True

        return False

    def _get_manipulation_range(
        self,
        game_state: "GameState",
        character_name: str | None,
    ) -> int:
        """Get the maximum manipulation range from active effects."""
        from dnd_engine.systems.time_manager import EffectType

        max_range = 0
        for effect in game_state.time_manager.get_all_effects():
            if effect.effect_type != EffectType.SPELL:
                continue

            # Filter by character if specified
            if character_name and effect.effect_data.get("caster_name") != character_name:
                continue

            range_ft = effect.effect_data.get("range_ft", 0)
            if range_ft > max_range:
                max_range = range_ft

        return max_range

    def get_available_actions(
        self,
        effect: "ActiveEffect",
        game_state: "GameState",
    ) -> list[dict[str, Any]]:
        """Return actions enabled by the manipulation effect."""
        actions = []
        capabilities = effect.effect_data.get("capabilities", [])
        spell_name = effect.effect_data.get("spell_name", "manipulation spell")

        if "interact_at_range" in capabilities:
            actions.append({
                "id": "manipulate_object",
                "name": f"Use {spell_name}",
                "description": (
                    f"Manipulate a small object at range "
                    f"(up to {effect.effect_data.get('weight_limit_lb', 10)} lbs)"
                ),
                "handler": "handle_manipulate_object",
            })

        if "trigger_pressure_plates" in capabilities:
            actions.append({
                "id": "trigger_trap",
                "name": "Trigger from distance",
                "description": "Safely trigger a pressure plate or trap from afar",
                "handler": "handle_trigger_trap",
            })

        return actions

    def handle_action(
        self,
        action_id: str,
        effect: "ActiveEffect",
        game_state: "GameState",
        **kwargs: Any,
    ) -> SpellEffectResult:
        """Handle a manipulation action."""
        if action_id == "manipulate_object":
            return self._handle_manipulate_object(effect, game_state, **kwargs)
        elif action_id == "trigger_trap":
            return self._handle_trigger_trap(effect, game_state, **kwargs)

        return SpellEffectResult(
            success=False,
            message=f"Unknown action: {action_id}",
        )

    def _handle_manipulate_object(
        self,
        effect: "ActiveEffect",
        game_state: "GameState",
        **kwargs: Any,
    ) -> SpellEffectResult:
        """Handle the manipulate_object action."""
        target_object = kwargs.get("target_object", "an object")
        spell_name = effect.effect_data.get("spell_name", "The spectral hand")

        return SpellEffectResult(
            success=True,
            message=f"{spell_name} reaches out and manipulates {target_object}.",
        )

    def _handle_trigger_trap(
        self,
        effect: "ActiveEffect",
        game_state: "GameState",
        **kwargs: Any,
    ) -> SpellEffectResult:
        """Handle the trigger_trap action."""
        spell_name = effect.effect_data.get("spell_name", "The spectral hand")

        return SpellEffectResult(
            success=True,
            message=(
                f"{spell_name} carefully prods the suspicious area, "
                "triggering any hidden mechanisms from a safe distance."
            ),
        )

    def on_expire(
        self,
        effect: "ActiveEffect",
        game_state: "GameState",
    ) -> str | None:
        """Return message when manipulation effect expires."""
        spell_name = effect.effect_data.get("spell_name", "The magical force")

        if "mage hand" in spell_name.lower():
            return "The spectral hand fades away into nothingness."
        elif "unseen servant" in spell_name.lower():
            return "The unseen servant dissipates, its service complete."
        else:
            return f"{spell_name} ends."
