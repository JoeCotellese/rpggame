# ABOUTME: Spell dataclass for D&D 5E spells
# ABOUTME: Handles spell metadata, casting mechanics, and effects

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class SpellSchool(str, Enum):
    """The eight schools of magic in D&D 5E."""
    ABJURATION = "abjuration"
    CONJURATION = "conjuration"
    DIVINATION = "divination"
    ENCHANTMENT = "enchantment"
    EVOCATION = "evocation"
    ILLUSION = "illusion"
    NECROMANCY = "necromancy"
    TRANSMUTATION = "transmutation"


class CastingTime(str, Enum):
    """Common casting time types."""
    ACTION = "1 action"
    BONUS_ACTION = "1 bonus action"
    REACTION = "1 reaction"
    MINUTE = "1 minute"
    MINUTES_10 = "10 minutes"
    HOUR = "1 hour"
    HOURS_8 = "8 hours"
    HOURS_12 = "12 hours"
    HOURS_24 = "24 hours"


class SpellComponent(str, Enum):
    """Spell component types."""
    VERBAL = "V"
    SOMATIC = "S"
    MATERIAL = "M"


class DurationType(str, Enum):
    """Spell duration types."""
    INSTANTANEOUS = "Instantaneous"
    CONCENTRATION = "Concentration"
    TIMED = "Timed"
    UNTIL_DISPELLED = "Until dispelled"
    SPECIAL = "Special"


@dataclass
class SpellComponents:
    """Components required to cast a spell."""
    verbal: bool = False
    somatic: bool = False
    material: bool = False
    material_description: Optional[str] = None
    material_cost: Optional[int] = None
    material_consumed: bool = False


@dataclass
class SpellDamage:
    """Damage information for a spell."""
    dice: str  # e.g., "1d6", "2d8+5"
    damage_type: str  # e.g., "fire", "cold", "radiant"
    higher_levels: Optional[str] = None  # e.g., "1d6 per slot level above 1st"


@dataclass
class SpellHealing:
    """Healing information for a spell."""
    dice: str  # e.g., "1d8", "2d4+2"
    higher_levels: Optional[str] = None


@dataclass
class SavingThrow:
    """Saving throw information for a spell."""
    ability: str  # "strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"
    on_success: str  # "half", "none", "negates", etc.


@dataclass
class Spell:
    """
    Represents a D&D 5E spell with all its properties.

    Attributes:
        id: Unique identifier (lowercase_snake_case)
        name: Display name of the spell
        level: Spell level (0 for cantrips, 1-9 for leveled spells)
        school: School of magic
        casting_time: Time required to cast
        range_ft: Range in feet (0 for self, -1 for touch)
        components: Components required
        duration: How long the spell lasts
        duration_value: Specific duration value (e.g., "1 minute", "10 rounds")
        concentration: Whether the spell requires concentration
        ritual: Whether the spell can be cast as a ritual
        description: Full spell description
        damage: Damage information (if applicable)
        healing: Healing information (if applicable)
        saving_throw: Saving throw information (if applicable)
        attack_type: "melee" or "ranged" spell attack (if applicable)
        area_of_effect: Area of effect (e.g., "20-foot radius sphere")
        higher_levels: Description of how spell scales at higher levels
        classes: List of classes that can cast this spell
        source: Source book reference
    """
    id: str
    name: str
    level: int
    school: SpellSchool
    casting_time: str
    range_ft: int
    components: SpellComponents
    duration: DurationType
    description: str

    # Optional attributes
    duration_value: Optional[str] = None
    concentration: bool = False
    ritual: bool = False
    damage: Optional[SpellDamage] = None
    healing: Optional[SpellHealing] = None
    saving_throw: Optional[SavingThrow] = None
    attack_type: Optional[str] = None  # "melee" or "ranged"
    area_of_effect: Optional[str] = None
    higher_levels: Optional[str] = None
    classes: List[str] = field(default_factory=list)
    source: str = "D&D 5E SRD (CC BY 4.0)"

    def is_cantrip(self) -> bool:
        """Return True if this is a cantrip (level 0 spell)."""
        return self.level == 0

    def requires_attack_roll(self) -> bool:
        """Return True if this spell requires an attack roll."""
        return self.attack_type is not None

    def requires_saving_throw(self) -> bool:
        """Return True if this spell requires a saving throw."""
        return self.saving_throw is not None

    def has_damage(self) -> bool:
        """Return True if this spell deals damage."""
        return self.damage is not None

    def has_healing(self) -> bool:
        """Return True if this spell provides healing."""
        return self.healing is not None

    def is_aoe(self) -> bool:
        """Return True if this spell has an area of effect."""
        return self.area_of_effect is not None

    def get_range_description(self) -> str:
        """Get a human-readable range description."""
        if self.range_ft == 0:
            return "Self"
        elif self.range_ft == -1:
            return "Touch"
        else:
            return f"{self.range_ft} feet"

    def get_components_description(self) -> str:
        """Get a human-readable components description."""
        components = []
        if self.components.verbal:
            components.append("V")
        if self.components.somatic:
            components.append("S")
        if self.components.material:
            if self.components.material_description:
                components.append(f"M ({self.components.material_description})")
            else:
                components.append("M")
        return ", ".join(components) if components else "None"

    def get_duration_description(self) -> str:
        """Get a human-readable duration description."""
        if self.duration == DurationType.INSTANTANEOUS:
            return "Instantaneous"
        elif self.concentration:
            return f"Concentration, up to {self.duration_value}"
        elif self.duration_value:
            return self.duration_value
        else:
            return self.duration.value
