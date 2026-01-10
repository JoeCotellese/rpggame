# ABOUTME: Utility spell effect handler for Prestidigitation, Mending, etc.
# ABOUTME: Handles minor magical effects that are primarily flavor or have limited mechanical impact.

from typing import TYPE_CHECKING, Any

from .base import SpellEffect, SpellEffectResult

if TYPE_CHECKING:
    from dnd_engine.core.creature import Creature
    from dnd_engine.core.game_state import GameState
    from dnd_engine.systems.time_manager import ActiveEffect


class UtilityEffect(SpellEffect):
    """
    Handler for minor utility spells with limited mechanical effects.

    Supported spells:
    - Prestidigitation: Minor magical tricks
    - Mending: Repair small breaks in objects
    - Druidcraft: Minor nature effects
    - Thaumaturgy: Minor divine effects

    These spells are primarily for flavor and roleplay, but may provide
    minor circumstantial benefits tracked via effect_data.
    """

    effect_type = "utility"

    def apply(
        self,
        spell_data: dict[str, Any],
        caster: "Creature",
        target: "Creature | None",
        game_state: "GameState",
    ) -> SpellEffectResult:
        """Apply utility effect when spell is cast."""
        effect_config = spell_data.get("effect", {})
        spell_name = spell_data.get("name", "Unknown Spell")

        # Get the utility type and any specific effect
        utility_type = effect_config.get("utility_type", "general")
        specific_effect = effect_config.get("specific_effect")

        # Build message based on spell and utility type
        message = self._build_cast_message(
            spell_name, caster.name, utility_type, specific_effect
        )

        # Determine what capabilities this grants
        capabilities = self._determine_capabilities(spell_name, utility_type)

        return SpellEffectResult(
            success=True,
            message=message,
            effect_data={
                "spell_name": spell_name,
                "utility_type": utility_type,
                "capabilities": capabilities,
                "caster_name": caster.name,
            },
        )

    def _build_cast_message(
        self,
        spell_name: str,
        caster_name: str,
        utility_type: str,
        specific_effect: str | None,
    ) -> str:
        """Build a descriptive message for the spell cast."""
        spell_lower = spell_name.lower()

        if "prestidigitation" in spell_lower:
            effects = [
                "A small sensory effect manifests - a spark, a puff of wind, "
                "a faint musical note.",
                "Colors shift and swirl briefly in the air around the caster.",
                "A harmless sensory effect creates a moment of wonder.",
            ]
            # Could randomize, but for now use first
            base_msg = effects[0]
            return (
                f"{caster_name} performs a minor magical trick. {base_msg} "
                "The magic lingers, ready for more tricks."
            )

        elif "mending" in spell_lower:
            return (
                f"{caster_name} touches the broken object, and magical energy "
                "flows into the damaged area. Small cracks seal, tears mend, "
                "and breaks rejoin seamlessly."
            )

        elif "druidcraft" in spell_lower:
            return (
                f"{caster_name} channels the magic of nature. A flower blooms, "
                "leaves rustle without wind, or the scent of rain fills the air."
            )

        elif "thaumaturgy" in spell_lower:
            return (
                f"{caster_name} invokes divine power. Flames flicker, a voice "
                "booms unnaturally loud, or the ground trembles slightly."
            )

        else:
            return (
                f"{caster_name} weaves a minor magical effect. "
                f"The {spell_name} takes hold."
            )

    def _determine_capabilities(
        self,
        spell_name: str,
        utility_type: str,
    ) -> list[str]:
        """Determine what capabilities this utility spell grants."""
        spell_lower = spell_name.lower()
        capabilities: list[str] = []

        if "prestidigitation" in spell_lower:
            capabilities = [
                "create_sensory_effect",
                "light_or_snuff",
                "clean_or_soil",
                "warm_or_chill",
                "flavor_food",
                "create_trinket",
                "create_mark",
            ]

        elif "mending" in spell_lower:
            capabilities = ["repair_object"]

        elif "druidcraft" in spell_lower:
            capabilities = [
                "predict_weather",
                "bloom_flower",
                "create_sensory_effect",
                "light_or_snuff",
            ]

        elif "thaumaturgy" in spell_lower:
            capabilities = [
                "boom_voice",
                "cause_tremors",
                "create_sensory_effect",
                "slam_door",
                "alter_flames",
                "alter_eye_appearance",
            ]

        return capabilities

    def query(
        self,
        game_state: "GameState",
        query_type: str,
        **kwargs: Any,
    ) -> Any:
        """
        Query utility effects.

        Supported queries:
        - "has_utility_capability": Check if a capability is available
          kwargs: capability (str), character_name (str, optional)
        - "get_available_tricks": Get list of available utility tricks
          kwargs: character_name (str, optional)
        """
        if query_type == "has_utility_capability":
            return self._has_capability(
                game_state,
                kwargs.get("capability"),
                kwargs.get("character_name"),
            )
        elif query_type == "get_available_tricks":
            return self._get_available_tricks(
                game_state,
                kwargs.get("character_name"),
            )
        return None

    def _has_capability(
        self,
        game_state: "GameState",
        capability: str | None,
        character_name: str | None,
    ) -> bool:
        """Check if a utility capability is active."""
        if not capability:
            return False

        from dnd_engine.systems.time_manager import EffectType

        for effect in game_state.time_manager.get_all_effects():
            if effect.effect_type != EffectType.SPELL:
                continue

            if character_name and effect.effect_data.get("caster_name") != character_name:
                continue

            capabilities = effect.effect_data.get("capabilities", [])
            if capability in capabilities:
                return True

        return False

    def _get_available_tricks(
        self,
        game_state: "GameState",
        character_name: str | None,
    ) -> list[str]:
        """Get all available utility tricks from active effects."""
        from dnd_engine.systems.time_manager import EffectType

        all_capabilities: set[str] = set()

        for effect in game_state.time_manager.get_all_effects():
            if effect.effect_type != EffectType.SPELL:
                continue

            if character_name and effect.effect_data.get("caster_name") != character_name:
                continue

            capabilities = effect.effect_data.get("capabilities", [])
            all_capabilities.update(capabilities)

        return list(all_capabilities)

    def get_available_actions(
        self,
        effect: "ActiveEffect",
        game_state: "GameState",
    ) -> list[dict[str, Any]]:
        """Return actions enabled by the utility effect."""
        actions: list[dict[str, Any]] = []
        capabilities = effect.effect_data.get("capabilities", [])

        # Map capabilities to user-friendly actions
        action_map = {
            "create_sensory_effect": {
                "id": "sensory_effect",
                "name": "Create sensory effect",
                "description": "Create a harmless sensory effect (sound, smell, visual)",
            },
            "repair_object": {
                "id": "repair",
                "name": "Mend object",
                "description": "Repair a single break or tear in an object",
            },
            "clean_or_soil": {
                "id": "clean_soil",
                "name": "Clean or soil",
                "description": "Instantly clean or soil an object no larger than 1 cubic foot",
            },
            "flavor_food": {
                "id": "flavor",
                "name": "Flavor food",
                "description": "Season or flavor up to 1 cubic foot of nonliving material",
            },
            "predict_weather": {
                "id": "predict_weather",
                "name": "Predict weather",
                "description": "Know what the weather will be for the next 24 hours",
            },
            "boom_voice": {
                "id": "boom_voice",
                "name": "Boom voice",
                "description": "Cause your voice to boom up to three times as loud",
            },
        }

        for cap in capabilities:
            if cap in action_map:
                action = action_map[cap].copy()
                action["handler"] = f"handle_{action['id']}"
                actions.append(action)

        return actions

    def handle_action(
        self,
        action_id: str,
        effect: "ActiveEffect",
        game_state: "GameState",
        **kwargs: Any,
    ) -> SpellEffectResult:
        """Handle a utility action."""
        spell_name = effect.effect_data.get("spell_name", "The spell")
        caster_name = effect.effect_data.get("caster_name", "The caster")

        # Generic handling for most utility actions - primarily flavor
        action_messages = {
            "sensory_effect": (
                f"{caster_name} creates a brief magical sensation - "
                "a flash of color, a whisper of sound, a momentary scent."
            ),
            "repair": (
                f"{caster_name} touches the damaged object. Magical energy "
                "knits the break together seamlessly."
            ),
            "clean_soil": (
                f"{caster_name} waves a hand, and the target becomes "
                "instantly clean (or dirty, as intended)."
            ),
            "flavor": (
                f"{caster_name} adds a touch of magic to the food, "
                "enhancing its flavor perfectly."
            ),
            "predict_weather": (
                f"{caster_name} senses the natural rhythms of the world. "
                "The weather for the next day becomes clear in their mind."
            ),
            "boom_voice": (
                f"{caster_name}'s next words BOOM with supernatural volume!"
            ),
        }

        message = action_messages.get(
            action_id,
            f"{caster_name} uses {spell_name} to create a minor magical effect.",
        )

        return SpellEffectResult(success=True, message=message)

    def on_expire(
        self,
        effect: "ActiveEffect",
        game_state: "GameState",
    ) -> str | None:
        """Return message when utility effect expires."""
        spell_name = effect.effect_data.get("spell_name", "The magical effect")

        # Most utility cantrips are instantaneous or have subtle endings
        if "prestidigitation" in spell_name.lower():
            return "The prestidigitation magic fades, any created marks or trinkets vanishing."
        elif "mending" in spell_name.lower():
            return None  # Mending is instantaneous, no expiration message
        else:
            return f"The {spell_name} effect fades away."
