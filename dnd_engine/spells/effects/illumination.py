# ABOUTME: Illumination spell effect handler for Light, Dancing Lights, etc.
# ABOUTME: Provides light sources that modify effective lighting in areas.

from typing import TYPE_CHECKING, Any

from .base import SpellEffect, SpellEffectResult

if TYPE_CHECKING:
    from dnd_engine.core.creature import Creature
    from dnd_engine.core.game_state import GameState
    from dnd_engine.systems.time_manager import ActiveEffect


class IlluminationEffect(SpellEffect):
    """
    Handler for spells that provide illumination.

    Supported spells:
    - Light: Provides bright light in 20ft radius
    - Dancing Lights: Creates up to 4 dim light sources

    Effect data stored in ActiveEffect:
    - light_level: "bright" or "dim"
    - radius_ft: Light radius in feet
    """

    effect_type = "illumination"

    def apply(
        self,
        spell_data: dict[str, Any],
        caster: "Creature",
        target: "Creature | None",
        game_state: "GameState",
    ) -> SpellEffectResult:
        """Apply illumination effect when spell is cast."""
        effect_config = spell_data.get("effect", {})
        light_level = effect_config.get("light_level", "bright")
        radius_ft = effect_config.get("radius_ft", 20)

        spell_name = spell_data.get("name", "Unknown Spell")
        target_name = target.name if target else caster.name

        # Build descriptive message based on light level
        if light_level == "bright":
            message = (
                f"Bright light springs forth, illuminating a {radius_ft}-foot "
                f"radius around {target_name}."
            )
        else:
            message = (
                f"A soft glow appears, providing dim light in a {radius_ft}-foot "
                f"radius around {target_name}."
            )

        return SpellEffectResult(
            success=True,
            message=message,
            effect_data={
                "light_level": light_level,
                "radius_ft": radius_ft,
                "spell_name": spell_name,
            },
        )

    def query(
        self,
        game_state: "GameState",
        query_type: str,
        **kwargs: Any,
    ) -> Any:
        """
        Query illumination effects.

        Supported queries:
        - "get_light_level": Returns the highest light level from active effects
        - "has_light_source": Returns True if any illumination effect is active
        """
        if query_type == "get_light_level":
            return self._get_highest_light_level(game_state)
        elif query_type == "has_light_source":
            return self._has_light_source(game_state)
        return None

    def _get_highest_light_level(self, game_state: "GameState") -> str | None:
        """Get the highest light level from active illumination effects."""
        from dnd_engine.systems.time_manager import EffectType

        best_level = None
        for effect in game_state.time_manager.get_all_effects():
            if effect.effect_type != EffectType.SPELL:
                continue

            light_level = effect.effect_data.get("light_level")
            if light_level == "bright":
                return "bright"  # Can't get better than bright
            elif light_level == "dim" and best_level is None:
                best_level = "dim"

        return best_level

    def _has_light_source(self, game_state: "GameState") -> bool:
        """Check if any illumination spell effect is active."""
        from dnd_engine.systems.time_manager import EffectType

        for effect in game_state.time_manager.get_all_effects():
            if effect.effect_type != EffectType.SPELL:
                continue
            if effect.effect_data.get("light_level"):
                return True
        return False

    def on_expire(
        self,
        effect: "ActiveEffect",
        game_state: "GameState",
    ) -> str | None:
        """Return message when illumination effect expires."""
        spell_name = effect.effect_data.get("spell_name", "The light")
        return f"{spell_name} fades away, and darkness returns."
