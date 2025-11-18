# ABOUTME: Condition management system for D&D 5E status effects
# ABOUTME: Handles turn-start effects, ability checks to remove conditions, and data-driven condition definitions

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.creature import Creature
from dnd_engine.utils.events import Event, EventType, EventBus


@dataclass
class ConditionEffectResult:
    """Result of processing a condition effect"""
    condition_id: str
    effect_type: str
    success: bool
    amount: int = 0
    message: str = ""
    condition_removed: bool = False


@dataclass
class AbilityCheckResult:
    """Result of an ability check attempt"""
    condition_id: str
    success: bool
    roll_total: int
    dc: int
    ability: str
    message: str
    condition_removed: bool = False


class ConditionManager:
    """
    Manages D&D 5E conditions and their effects.

    Handles:
    - Loading condition definitions from JSON
    - Processing turn-start effects (damage, etc.)
    - Ability checks to remove conditions
    - Condition metadata and information
    """

    def __init__(
        self,
        conditions_file: Optional[Path] = None,
        dice_roller: Optional[DiceRoller] = None,
        event_bus: Optional[EventBus] = None
    ):
        """
        Initialize the ConditionManager.

        Args:
            conditions_file: Path to conditions.json (defaults to SRD conditions)
            dice_roller: DiceRoller instance (creates new one if not provided)
            event_bus: Optional event bus for emitting events
        """
        self.dice_roller = dice_roller or DiceRoller()
        self.event_bus = event_bus

        # Load conditions data
        if conditions_file is None:
            conditions_file = Path(__file__).parent.parent / "data" / "srd" / "conditions.json"

        with open(conditions_file, 'r') as f:
            data = json.load(f)
            self.conditions_data: Dict[str, Any] = data.get("conditions", {})

    def get_condition_info(self, condition_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a condition.

        Args:
            condition_id: The condition identifier (e.g., "on_fire")

        Returns:
            Dictionary with condition data, or None if not found
        """
        return self.conditions_data.get(condition_id)

    def has_turn_start_effect(self, condition_id: str) -> bool:
        """
        Check if a condition has a turn-start effect.

        Args:
            condition_id: The condition identifier

        Returns:
            True if the condition has a turn_start_effect defined
        """
        condition_info = self.get_condition_info(condition_id)
        if not condition_info:
            return False
        return "turn_start_effect" in condition_info

    def can_attempt_early_removal(self, condition_id: str) -> bool:
        """
        Check if a condition can be removed early via ability check.

        Args:
            condition_id: The condition identifier

        Returns:
            True if the condition has early removal option
        """
        condition_info = self.get_condition_info(condition_id)
        if not condition_info:
            return False
        return "can_end_early" in condition_info

    def process_turn_start_effects(
        self,
        creature: Creature
    ) -> List[ConditionEffectResult]:
        """
        Process all turn-start effects for a creature's conditions.

        Args:
            creature: The creature to process effects for

        Returns:
            List of ConditionEffectResult for each effect processed
        """
        results = []

        for condition_id in list(creature.conditions):
            if not self.has_turn_start_effect(condition_id):
                continue

            result = self._process_single_turn_start_effect(creature, condition_id)
            if result:
                results.append(result)

        return results

    def _process_single_turn_start_effect(
        self,
        creature: Creature,
        condition_id: str
    ) -> Optional[ConditionEffectResult]:
        """
        Process the turn-start effect for a single condition.

        Args:
            creature: The creature to process the effect for
            condition_id: The condition to process

        Returns:
            ConditionEffectResult or None if no effect
        """
        condition_info = self.get_condition_info(condition_id)
        if not condition_info:
            return None

        turn_start_effect = condition_info.get("turn_start_effect")
        if not turn_start_effect:
            return None

        effect_type = turn_start_effect.get("type")

        if effect_type == "damage":
            return self._apply_damage_effect(creature, condition_id, turn_start_effect)

        # Future: handle other effect types (healing, stat changes, etc.)
        return None

    def _apply_damage_effect(
        self,
        creature: Creature,
        condition_id: str,
        effect_data: Dict[str, Any]
    ) -> ConditionEffectResult:
        """
        Apply a damage effect to a creature.

        Args:
            creature: The creature to damage
            condition_id: The condition causing the damage
            effect_data: The effect data from the condition

        Returns:
            ConditionEffectResult with damage details
        """
        damage_dice = effect_data.get("damage", "1d4")
        damage_type = effect_data.get("damage_type", "untyped")
        message_template = effect_data.get("message", "{creature_name} takes {damage} damage")

        # Roll damage
        damage_roll = self.dice_roller.roll(damage_dice)
        damage_amount = damage_roll.total

        # Apply damage
        hp_before = creature.current_hp
        creature.take_damage(damage_amount)

        # Format message
        message = message_template.format(
            creature_name=creature.name,
            damage=damage_amount,
            damage_type=damage_type
        )

        # Emit event if event bus is available
        if self.event_bus:
            self.event_bus.emit(Event(
                EventType.DAMAGE_TAKEN,
                {
                    "creature": creature,
                    "damage": damage_amount,
                    "damage_type": damage_type,
                    "source": f"condition:{condition_id}"
                }
            ))

        return ConditionEffectResult(
            condition_id=condition_id,
            effect_type="damage",
            success=True,
            amount=damage_amount,
            message=message
        )

    def attempt_condition_removal(
        self,
        creature: Creature,
        condition_id: str
    ) -> Optional[AbilityCheckResult]:
        """
        Attempt to remove a condition via ability check.

        Args:
            creature: The creature attempting to remove the condition
            condition_id: The condition to remove

        Returns:
            AbilityCheckResult with check details, or None if not applicable
        """
        condition_info = self.get_condition_info(condition_id)
        if not condition_info:
            return None

        removal_info = condition_info.get("can_end_early")
        if not removal_info or removal_info.get("method") != "ability_check":
            return None

        # Get check parameters
        ability = removal_info.get("ability", "dexterity")
        dc = removal_info.get("dc", 10)

        # Get ability modifier
        ability_mod = self._get_ability_modifier(creature, ability)

        # Roll ability check (d20 + modifier)
        check_roll = self.dice_roller.roll("1d20")
        roll_total = check_roll.total + ability_mod

        # Determine success
        success = roll_total >= dc

        # Remove condition if successful
        condition_removed = False
        if success:
            creature.remove_condition(condition_id)
            condition_removed = True
            message_template = removal_info.get("success_message", "✅ {creature_name} succeeds!")
            message = message_template.format(creature_name=creature.name)
        else:
            message_template = removal_info.get("failure_message",
                "❌ {creature_name} fails (rolled {roll} vs DC {dc})")
            message = message_template.format(
                creature_name=creature.name,
                roll=roll_total,
                dc=dc
            )

        # Emit event if event bus is available
        if self.event_bus:
            self.event_bus.emit(Event(
                EventType.ABILITY_CHECK,
                {
                    "creature": creature,
                    "ability": ability,
                    "dc": dc,
                    "roll": roll_total,
                    "success": success,
                    "purpose": f"remove_condition:{condition_id}"
                }
            ))

        return AbilityCheckResult(
            condition_id=condition_id,
            success=success,
            roll_total=roll_total,
            dc=dc,
            ability=ability,
            message=message,
            condition_removed=condition_removed
        )

    def _get_ability_modifier(self, creature: Creature, ability: str) -> int:
        """
        Get the ability modifier for a creature.

        Args:
            creature: The creature
            ability: Ability name (strength, dexterity, etc.)

        Returns:
            The ability modifier
        """
        ability_map = {
            "strength": creature.abilities.str_mod,
            "dexterity": creature.abilities.dex_mod,
            "constitution": creature.abilities.con_mod,
            "intelligence": creature.abilities.int_mod,
            "wisdom": creature.abilities.wis_mod,
            "charisma": creature.abilities.cha_mod
        }

        return ability_map.get(ability.lower(), 0)

    def get_removal_prompt_info(self, condition_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information for prompting a creature about removing a condition.

        Args:
            condition_id: The condition identifier

        Returns:
            Dict with prompt info (ability, DC, action cost, etc.) or None
        """
        condition_info = self.get_condition_info(condition_id)
        if not condition_info:
            return None

        removal_info = condition_info.get("can_end_early")
        if not removal_info:
            return None

        return {
            "condition_name": condition_info.get("name", condition_id),
            "method": removal_info.get("method"),
            "ability": removal_info.get("ability"),
            "dc": removal_info.get("dc"),
            "action_cost": removal_info.get("action_cost"),
            "description": condition_info.get("description", "")
        }
