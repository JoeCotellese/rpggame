# ABOUTME: Detection spell effect handler for Detect Magic, Identify, etc.
# ABOUTME: Reveals magical properties, hidden information, and creature types.

from typing import TYPE_CHECKING, Any

from .base import SpellEffect, SpellEffectResult

if TYPE_CHECKING:
    from dnd_engine.core.creature import Creature
    from dnd_engine.core.game_state import GameState
    from dnd_engine.systems.time_manager import ActiveEffect


class DetectionEffect(SpellEffect):
    """
    Handler for spells that detect or reveal information.

    Supported spells:
    - Detect Magic: Sense presence of magic, identify schools
    - Identify: Learn properties of magical items
    - See Invisibility: See invisible creatures and objects
    - Detect Evil and Good: Sense aberrations, celestials, etc.

    Effect data stored in ActiveEffect:
    - reveals: List of what can be detected (e.g., "magical_items", "invisible")
    - range_ft: Detection range
    - requires_concentration: Whether caster must focus
    """

    effect_type = "detection"

    def apply(
        self,
        spell_data: dict[str, Any],
        caster: "Creature",
        target: "Creature | None",
        game_state: "GameState",
    ) -> SpellEffectResult:
        """Apply detection effect when spell is cast."""
        effect_config = spell_data.get("effect", {})
        spell_name = spell_data.get("name", "Unknown Spell")

        # What this spell reveals
        reveals = effect_config.get("reveals", ["magical_auras"])
        range_ft = effect_config.get("range_ft", 30)

        # Build message and perform initial detection
        message, detected_items = self._perform_detection(
            spell_name, caster, reveals, range_ft, game_state
        )

        return SpellEffectResult(
            success=True,
            message=message,
            effect_data={
                "spell_name": spell_name,
                "reveals": reveals,
                "range_ft": range_ft,
                "caster_name": caster.name,
                "detected_items": detected_items,
            },
        )

    def _perform_detection(
        self,
        spell_name: str,
        caster: "Creature",
        reveals: list[str],
        range_ft: int,
        game_state: "GameState",
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Perform the detection and build result message.

        Returns:
            Tuple of (message, list of detected items)
        """
        detected_items: list[dict[str, Any]] = []
        messages: list[str] = []

        spell_lower = spell_name.lower()

        # Opening flavor text
        if "detect magic" in spell_lower:
            messages.append(
                f"{caster.name}'s senses expand, becoming attuned to magical energies."
            )
        elif "identify" in spell_lower:
            messages.append(
                f"{caster.name} focuses intently, magical insights flooding their mind."
            )
        elif "see invisibility" in spell_lower:
            messages.append(
                f"{caster.name}'s eyes shimmer briefly as they gain supernatural sight."
            )
        else:
            messages.append(
                f"{caster.name} extends their magical senses outward."
            )

        # Check for magical items if that's what we reveal
        if "magical_items" in reveals or "magical_auras" in reveals:
            magical_items = self._detect_magical_items(caster, game_state)
            if magical_items:
                detected_items.extend(magical_items)
                item_names = [item["name"] for item in magical_items]
                messages.append(
                    f"Magical auras detected: {', '.join(item_names)}."
                )
            else:
                messages.append("No magical auras are detected nearby.")

        # Check for magical effects in the room/area
        if "magical_effects" in reveals or "magical_auras" in reveals:
            magical_effects = self._detect_magical_effects(game_state)
            if magical_effects:
                detected_items.extend(magical_effects)
                effect_names = [e["name"] for e in magical_effects]
                messages.append(
                    f"Active magical effects: {', '.join(effect_names)}."
                )

        # Check for invisible creatures
        if "invisible_creatures" in reveals:
            invisible = self._detect_invisible(game_state)
            if invisible:
                detected_items.extend(invisible)
                messages.append(
                    f"Invisible presences detected: {len(invisible)}."
                )

        return " ".join(messages), detected_items

    def _detect_magical_items(
        self,
        caster: "Creature",
        game_state: "GameState",
    ) -> list[dict[str, Any]]:
        """Detect magical items in party inventory."""
        magical_items: list[dict[str, Any]] = []

        # Check party members' inventories
        for character in game_state.party.characters:
            if not hasattr(character, "inventory"):
                continue

            # Inventory stores items in a dict keyed by item_id
            inventory = character.inventory
            if not hasattr(inventory, "items"):
                continue

            for item_id, _inv_item in inventory.items.items():
                # Try to load full item data to check if magical
                item_data = game_state.data_loader.get_item_by_id(item_id)
                if not item_data:
                    continue

                is_magical = (
                    item_data.get("magical", False)
                    or item_data.get("rarity", "common") != "common"
                    or item_data.get("magic_bonus", 0) > 0
                )

                if is_magical:
                    magical_items.append({
                        "type": "item",
                        "name": item_data.get("name", item_id),
                        "owner": character.name,
                        "school": item_data.get("school", "unknown"),
                    })

        return magical_items

    def _detect_magical_effects(
        self,
        game_state: "GameState",
    ) -> list[dict[str, Any]]:
        """Detect active magical effects in the area."""
        from dnd_engine.systems.time_manager import EffectType

        magical_effects: list[dict[str, Any]] = []

        for effect in game_state.time_manager.get_all_effects():
            if effect.effect_type == EffectType.SPELL:
                magical_effects.append({
                    "type": "effect",
                    "name": effect.source,
                    "target": effect.target_name,
                    "remaining": effect.remaining_value,
                })

        return magical_effects

    def _detect_invisible(
        self,
        game_state: "GameState",
    ) -> list[dict[str, Any]]:
        """Detect invisible creatures."""
        invisible: list[dict[str, Any]] = []

        # Check monsters in current room
        if hasattr(game_state, "current_room") and game_state.current_room:
            room = game_state.current_room
            monsters = getattr(room, "monsters", [])
            for monster in monsters:
                conditions = getattr(monster, "conditions", [])
                if "invisible" in conditions:
                    invisible.append({
                        "type": "creature",
                        "name": monster.name,
                    })

        return invisible

    def query(
        self,
        game_state: "GameState",
        query_type: str,
        **kwargs: Any,
    ) -> Any:
        """
        Query detection effects.

        Supported queries:
        - "can_detect": Check if caster can detect a specific type
          kwargs: detection_type (str), character_name (str)
        - "get_detected_items": Get list of detected magical items
          kwargs: character_name (str, optional)
        - "is_item_magical": Check if a specific item is detected as magical
          kwargs: item_name (str)
        """
        if query_type == "can_detect":
            return self._can_detect(
                game_state,
                kwargs.get("detection_type"),
                kwargs.get("character_name"),
            )
        elif query_type == "get_detected_items":
            return self._get_detected_items(
                game_state,
                kwargs.get("character_name"),
            )
        elif query_type == "is_item_magical":
            return self._is_item_detected_magical(
                game_state,
                kwargs.get("item_name"),
            )
        return None

    def _can_detect(
        self,
        game_state: "GameState",
        detection_type: str | None,
        character_name: str | None,
    ) -> bool:
        """Check if a character has a detection effect active."""
        if not detection_type:
            return False

        from dnd_engine.systems.time_manager import EffectType

        for effect in game_state.time_manager.get_all_effects():
            if effect.effect_type != EffectType.SPELL:
                continue

            if character_name and effect.effect_data.get("caster_name") != character_name:
                continue

            reveals = effect.effect_data.get("reveals", [])
            if detection_type in reveals:
                return True

        return False

    def _get_detected_items(
        self,
        game_state: "GameState",
        character_name: str | None,
    ) -> list[dict[str, Any]]:
        """Get all items detected by active detection spells."""
        from dnd_engine.systems.time_manager import EffectType

        all_detected: list[dict[str, Any]] = []

        for effect in game_state.time_manager.get_all_effects():
            if effect.effect_type != EffectType.SPELL:
                continue

            if character_name and effect.effect_data.get("caster_name") != character_name:
                continue

            detected = effect.effect_data.get("detected_items", [])
            all_detected.extend(detected)

        return all_detected

    def _is_item_detected_magical(
        self,
        game_state: "GameState",
        item_name: str | None,
    ) -> bool:
        """Check if a specific item has been detected as magical."""
        if not item_name:
            return False

        detected_items = self._get_detected_items(game_state, None)
        item_lower = item_name.lower()

        for item in detected_items:
            if item.get("type") == "item":
                if item.get("name", "").lower() == item_lower:
                    return True

        return False

    def on_expire(
        self,
        effect: "ActiveEffect",
        game_state: "GameState",
    ) -> str | None:
        """Return message when detection effect expires."""
        spell_name = effect.effect_data.get("spell_name", "The detection spell")
        caster_name = effect.effect_data.get("caster_name", "The caster")

        return (
            f"{caster_name}'s magical senses return to normal as "
            f"{spell_name} ends."
        )
