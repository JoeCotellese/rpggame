# ABOUTME: Targeting requirements service for spells and items
# ABOUTME: Provides API for CLI to query targeting requirements without interpreting game data

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ValidTargets(Enum):
    """
    Types of valid targets for spells and items.

    Used by CLI to determine what target selection prompt to show,
    without CLI needing to interpret game data directly.
    """

    SELF = "self"  # Caster only
    ALLY = "ally"  # Allies (including self)
    ENEMY = "enemy"  # Enemies only
    AREA = "area"  # Area effect (all enemies)
    ANY = "any"  # Any creature


@dataclass
class TargetingRequirements:
    """
    Targeting requirements for a spell or item.

    Provides all information CLI needs to handle target selection
    without interpreting game data directly. The game engine translates
    spell/item data into these requirements.

    Attributes:
        valid_targets: What type of targets are allowed
        needs_target_selection: Whether CLI should prompt for target
        can_target_self: Whether caster can be a valid target
        is_area_effect: Whether this affects all valid targets
        missing_target_type: Warning flag if data was missing target_type
    """

    valid_targets: ValidTargets
    needs_target_selection: bool
    can_target_self: bool
    is_area_effect: bool
    missing_target_type: bool = field(default=False)

    def is_valid_target_type(self, target_type: str) -> bool:
        """
        Check if a given target type is valid for this spell/item.

        Args:
            target_type: "self", "ally", or "enemy"

        Returns:
            True if the target type is valid
        """
        if self.valid_targets == ValidTargets.SELF:
            return target_type == "self"
        elif self.valid_targets == ValidTargets.ALLY:
            # Ally spells can target self or allies
            return target_type in ("self", "ally")
        elif self.valid_targets == ValidTargets.ENEMY:
            return target_type == "enemy"
        elif self.valid_targets == ValidTargets.AREA:
            # Area effects target all enemies, no individual selection
            return target_type == "enemy"
        elif self.valid_targets == ValidTargets.ANY:
            # Any can target anyone
            return target_type in ("self", "ally", "enemy")
        return False

    def get_prompt_type(self) -> str | None:
        """
        Get the type of prompt CLI should show.

        Returns:
            "enemy" for enemy selection, "ally" for ally selection,
            "any" for any creature selection, or None if no prompt needed.
        """
        if not self.needs_target_selection:
            return None

        if self.valid_targets == ValidTargets.ENEMY:
            return "enemy"
        elif self.valid_targets == ValidTargets.ALLY:
            return "ally"
        elif self.valid_targets == ValidTargets.ANY:
            return "any"
        return None


def get_spell_targeting_requirements(spell_data: dict[str, Any]) -> TargetingRequirements:
    """
    Get targeting requirements for a spell.

    Translates spell data into targeting requirements that CLI can use
    without needing to interpret game data directly.

    Args:
        spell_data: Spell data dictionary (from spells.json or similar)

    Returns:
        TargetingRequirements for the spell
    """
    target_type = spell_data.get("target_type")
    missing_target_type = target_type is None

    # Default to enemy if missing (matches current CLI behavior)
    if target_type is None:
        target_type = "enemy"

    return _create_targeting_requirements(target_type, missing_target_type)


def get_item_targeting_requirements(item_data: dict[str, Any]) -> TargetingRequirements:
    """
    Get targeting requirements for an item.

    Translates item data into targeting requirements that CLI can use
    without needing to interpret game data directly.

    Args:
        item_data: Item data dictionary (from items.json or similar)

    Returns:
        TargetingRequirements for the item
    """
    target_type = item_data.get("target_type")

    # Items default to self if missing (matches current CLI behavior)
    if target_type is None:
        target_type = "self"

    return _create_targeting_requirements(target_type, missing_target_type=False)


def _create_targeting_requirements(
    target_type: str, missing_target_type: bool = False
) -> TargetingRequirements:
    """
    Create targeting requirements from a target_type string.

    Internal helper that maps target_type values to TargetingRequirements.

    Args:
        target_type: "self", "ally", "enemy", "area", or "any"
        missing_target_type: Whether the original data was missing target_type

    Returns:
        TargetingRequirements for the target type
    """
    if target_type == "self":
        return TargetingRequirements(
            valid_targets=ValidTargets.SELF,
            needs_target_selection=False,
            can_target_self=True,
            is_area_effect=False,
            missing_target_type=missing_target_type,
        )
    elif target_type == "ally":
        return TargetingRequirements(
            valid_targets=ValidTargets.ALLY,
            needs_target_selection=True,
            can_target_self=True,  # Can heal/buff yourself
            is_area_effect=False,
            missing_target_type=missing_target_type,
        )
    elif target_type == "enemy":
        return TargetingRequirements(
            valid_targets=ValidTargets.ENEMY,
            needs_target_selection=True,
            can_target_self=False,
            is_area_effect=False,
            missing_target_type=missing_target_type,
        )
    elif target_type == "area":
        return TargetingRequirements(
            valid_targets=ValidTargets.AREA,
            needs_target_selection=False,
            can_target_self=False,
            is_area_effect=True,
            missing_target_type=missing_target_type,
        )
    elif target_type == "any":
        return TargetingRequirements(
            valid_targets=ValidTargets.ANY,
            needs_target_selection=True,
            can_target_self=True,
            is_area_effect=False,
            missing_target_type=missing_target_type,
        )
    else:
        # Unknown target_type - default to enemy
        return TargetingRequirements(
            valid_targets=ValidTargets.ENEMY,
            needs_target_selection=True,
            can_target_self=False,
            is_area_effect=False,
            missing_target_type=True,  # Mark as problematic
        )
