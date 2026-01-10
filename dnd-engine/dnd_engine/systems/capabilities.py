# ABOUTME: Capability system for determining what actions are available to the party.
# ABOUTME: Bridges spell effects, items, and racial traits to room interactions.

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dnd_engine.core.game_state import GameState


class Capability(str, Enum):
    """
    Standard capability vocabulary.

    These capabilities can be granted by spells, items, or racial traits,
    and are required by room interactions.
    """

    # Illumination capabilities
    LIGHT_SOURCE = "light_source"  # Light, torches, lanterns
    DARKVISION = "darkvision"  # Racial darkvision, Darkvision spell

    # Manipulation capabilities
    REACH_30FT = "reach_30ft"  # Mage Hand
    REACH_60FT = "reach_60ft"  # Telekinesis
    MANIPULATE_HEAVY = "manipulate_heavy"  # Telekinesis (500 lbs)

    # Movement capabilities
    FLIGHT = "flight"  # Fly spell, wings
    CLIMB_WALLS = "climb_walls"  # Spider Climb
    WATER_BREATHING = "water_breathing"  # Water Breathing spell

    # Detection capabilities
    SENSE_MAGIC = "sense_magic"  # Detect Magic
    SEE_INVISIBLE = "see_invisible"  # See Invisibility
    SENSE_TRAPS = "sense_traps"  # Find Traps

    # Access capabilities
    OPEN_LOCKS = "open_locks"  # Knock spell
    PASS_WALLS = "pass_walls"  # Passwall, Etherealness

    # Communication capabilities
    SPEAK_LANGUAGES = "speak_languages"  # Comprehend Languages, Tongues
    SPEAK_ANIMALS = "speak_animals"  # Speak with Animals
    SPEAK_DEAD = "speak_dead"  # Speak with Dead

    # Size/form capabilities
    TINY_SIZE = "tiny_size"  # Reduce, polymorph
    SQUEEZE_SMALL = "squeeze_small"  # Can fit through small spaces


@dataclass
class CapabilitySource:
    """Describes where a capability comes from."""
    capability: Capability
    source_type: str  # "spell", "item", "racial", "class"
    source_name: str  # e.g., "Mage Hand", "Torch", "Darkvision (Elf)"
    character_name: str | None  # Who has it, or None for party-wide
    duration: str | None  # e.g., "1 hour", "permanent", None for always


class CapabilityResolver:
    """
    Resolves what capabilities are available to the party.

    Checks:
    - Active spell effects
    - Equipped items (torches, lanterns)
    - Racial traits (darkvision)
    - Class features
    """

    # Mapping of spell effect types to capabilities they grant
    SPELL_CAPABILITIES: dict[str, list[Capability]] = {
        "illumination": [Capability.LIGHT_SOURCE],
        "manipulation": [Capability.REACH_30FT],
        "detection": [Capability.SENSE_MAGIC],
    }

    # Items that grant capabilities when held/equipped
    ITEM_CAPABILITIES: dict[str, list[Capability]] = {
        "torch": [Capability.LIGHT_SOURCE],
        "lantern": [Capability.LIGHT_SOURCE],
        "lantern_hooded": [Capability.LIGHT_SOURCE],
        "lantern_bullseye": [Capability.LIGHT_SOURCE],
        "sunrod": [Capability.LIGHT_SOURCE],
    }

    # Racial traits that grant capabilities
    RACIAL_CAPABILITIES: dict[str, list[Capability]] = {
        "elf": [Capability.DARKVISION],
        "half-elf": [Capability.DARKVISION],
        "dwarf": [Capability.DARKVISION],
        "half-orc": [Capability.DARKVISION],
        "tiefling": [Capability.DARKVISION],
        "gnome": [Capability.DARKVISION],
    }

    def __init__(self, game_state: "GameState"):
        self.game_state = game_state

    def get_party_capabilities(self) -> list[CapabilitySource]:
        """Get all capabilities available to the party."""
        capabilities: list[CapabilitySource] = []

        # Check spell effects
        capabilities.extend(self._get_spell_capabilities())

        # Check equipped items
        capabilities.extend(self._get_item_capabilities())

        # Check racial traits
        capabilities.extend(self._get_racial_capabilities())

        return capabilities

    def has_capability(self, capability: Capability | str) -> bool:
        """Check if the party has a specific capability."""
        if isinstance(capability, str):
            try:
                capability = Capability(capability)
            except ValueError:
                return False

        for source in self.get_party_capabilities():
            if source.capability == capability:
                return True
        return False

    def get_capability_source(self, capability: Capability | str) -> CapabilitySource | None:
        """Get the source of a specific capability, if available."""
        if isinstance(capability, str):
            try:
                capability = Capability(capability)
            except ValueError:
                return None

        for source in self.get_party_capabilities():
            if source.capability == capability:
                return source
        return None

    def check_requirements(
        self,
        requires_any: list[str] | None = None,
        requires_all: list[str] | None = None,
    ) -> tuple[bool, list[str]]:
        """
        Check if party meets capability requirements.

        Args:
            requires_any: Party needs at least one of these capabilities
            requires_all: Party needs all of these capabilities

        Returns:
            Tuple of (met, missing_capabilities)
        """
        missing: list[str] = []

        if requires_all:
            for cap in requires_all:
                if not self.has_capability(cap):
                    missing.append(cap)
            if missing:
                return False, missing

        if requires_any:
            has_any = False
            for cap in requires_any:
                if self.has_capability(cap):
                    has_any = True
                    break
            if not has_any:
                return False, requires_any

        return True, []

    def _get_spell_capabilities(self) -> list[CapabilitySource]:
        """Get capabilities from active spell effects."""
        capabilities: list[CapabilitySource] = []

        from dnd_engine.systems.time_manager import EffectType

        for effect in self.game_state.time_manager.get_all_effects():
            if effect.effect_type != EffectType.SPELL:
                continue

            effect_data = effect.effect_data
            spell_name = effect_data.get("spell_name", effect.source)
            caster_name = effect_data.get("caster_name")

            # Check for light_level in illumination effects
            if effect_data.get("light_level") in ["bright", "dim"]:
                capabilities.append(CapabilitySource(
                    capability=Capability.LIGHT_SOURCE,
                    source_type="spell",
                    source_name=spell_name,
                    character_name=caster_name,
                    duration=f"{effect.remaining_value} {effect.remaining_unit}",
                ))

            # Check for manipulation capabilities
            spell_capabilities = effect_data.get("capabilities", [])
            if "interact_at_range" in spell_capabilities:
                range_ft = effect_data.get("range_ft", 30)
                cap = Capability.REACH_60FT if range_ft >= 60 else Capability.REACH_30FT
                capabilities.append(CapabilitySource(
                    capability=cap,
                    source_type="spell",
                    source_name=spell_name,
                    character_name=caster_name,
                    duration=f"{effect.remaining_value} {effect.remaining_unit}",
                ))

            # Check for detection capabilities
            reveals = effect_data.get("reveals", [])
            if "magical_items" in reveals or "magical_auras" in reveals:
                capabilities.append(CapabilitySource(
                    capability=Capability.SENSE_MAGIC,
                    source_type="spell",
                    source_name=spell_name,
                    character_name=caster_name,
                    duration=f"{effect.remaining_value} {effect.remaining_unit}",
                ))
            if "invisible_creatures" in reveals:
                capabilities.append(CapabilitySource(
                    capability=Capability.SEE_INVISIBLE,
                    source_type="spell",
                    source_name=spell_name,
                    character_name=caster_name,
                    duration=f"{effect.remaining_value} {effect.remaining_unit}",
                ))

        return capabilities

    def _get_item_capabilities(self) -> list[CapabilitySource]:
        """Get capabilities from equipped/held items."""
        capabilities: list[CapabilitySource] = []

        for character in self.game_state.party.characters:
            if not hasattr(character, "inventory"):
                continue

            inventory = character.inventory
            if not hasattr(inventory, "items"):
                continue

            for item_id, _inv_item in inventory.items.items():
                # Check if this item grants capabilities
                item_id_lower = item_id.lower()
                for item_pattern, caps in self.ITEM_CAPABILITIES.items():
                    if item_pattern in item_id_lower:
                        for cap in caps:
                            capabilities.append(CapabilitySource(
                                capability=cap,
                                source_type="item",
                                source_name=item_id,
                                character_name=character.name,
                                duration="while held",
                            ))

        return capabilities

    def _get_racial_capabilities(self) -> list[CapabilitySource]:
        """Get capabilities from racial traits."""
        capabilities: list[CapabilitySource] = []

        for character in self.game_state.party.characters:
            race = getattr(character, "race", None)
            if not race:
                continue

            race_lower = race.lower()
            for race_pattern, caps in self.RACIAL_CAPABILITIES.items():
                if race_pattern in race_lower:
                    for cap in caps:
                        capabilities.append(CapabilitySource(
                            capability=cap,
                            source_type="racial",
                            source_name=f"{cap.value.replace('_', ' ').title()} ({race})",
                            character_name=character.name,
                            duration="permanent",
                        ))

        return capabilities
