# ABOUTME: Item effect system for applying consumable effects to creatures
# ABOUTME: Handles healing potions, damage items, buffs, condition removal, and spell scrolls

from typing import Dict, Any, Optional, List
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.creature import Creature
from dnd_engine.utils.events import Event, EventType, EventBus


class ItemEffectResult:
    """Result of applying an item effect"""
    def __init__(
        self,
        success: bool,
        effect_type: str,
        amount: int = 0,
        dice_notation: Optional[str] = None,
        message: str = ""
    ):
        self.success = success
        self.effect_type = effect_type
        self.amount = amount
        self.dice_notation = dice_notation
        self.message = message


def apply_item_effect(
    item_info: Dict[str, Any],
    target: Creature,
    dice_roller: Optional[DiceRoller] = None,
    event_bus: Optional[EventBus] = None
) -> ItemEffectResult:
    """
    Apply an item's effect to a target creature.

    Supported effect types:
    - healing: Restores HP (e.g., healing potions)
    - damage: Deals damage (e.g., alchemist's fire, acid vial)
    - condition_removal: Removes status conditions (e.g., elixir of health)
    - buff: Adds temporary conditions/effects (e.g., antitoxin, potion of heroism)
    - spell: Placeholder for spell scrolls (not yet implemented)

    Args:
        item_info: Item data from items.json
        target: Creature to apply the effect to
        dice_roller: DiceRoller instance (creates new one if not provided)
        event_bus: Optional event bus for emitting events

    Returns:
        ItemEffectResult describing what happened

    Example:
        >>> item_info = {"effect_type": "healing", "healing": "2d4+2", "name": "Potion of Healing"}
        >>> result = apply_item_effect(item_info, character)
        >>> print(result.message)  # "Healed for 7 HP (rolled 2d4+2)"
    """
    if dice_roller is None:
        dice_roller = DiceRoller()

    effect_type = item_info.get("effect_type")
    item_name = item_info.get("name", "Unknown Item")

    if effect_type == "healing":
        return _apply_healing_effect(item_info, target, dice_roller, event_bus)
    elif effect_type == "damage":
        return _apply_damage_effect(item_info, target, dice_roller, event_bus)
    elif effect_type == "condition_removal":
        return _apply_condition_removal_effect(item_info, target, event_bus)
    elif effect_type == "buff":
        return _apply_buff_effect(item_info, target, event_bus)
    elif effect_type == "spell":
        return _apply_spell_effect(item_info, target, dice_roller, event_bus)
    else:
        # Unknown or unimplemented effect type
        return ItemEffectResult(
            success=False,
            effect_type=effect_type or "unknown",
            message=f"{item_name} has no implemented effect"
        )


def _apply_healing_effect(
    item_info: Dict[str, Any],
    target: Creature,
    dice_roller: DiceRoller,
    event_bus: Optional[EventBus]
) -> ItemEffectResult:
    """
    Apply a healing effect to a target.

    Args:
        item_info: Item data containing "healing" dice notation
        target: Creature to heal
        dice_roller: DiceRoller for rolling healing dice
        event_bus: Optional event bus for emitting HEALING_RECEIVED event

    Returns:
        ItemEffectResult with healing details
    """
    healing_dice = item_info.get("healing", "1d4")
    item_name = item_info.get("name", "Unknown Healing Item")

    # Roll healing dice
    healing_roll = dice_roller.roll(healing_dice)
    healing_amount = healing_roll.total

    # Store HP before healing to calculate actual healing
    hp_before = target.current_hp

    # Apply healing - use Character.recover_hp if available (handles unconscious/death saves)
    # Otherwise fall back to Creature.heal for non-Characters
    if hasattr(target, 'recover_hp'):
        actual_healing = target.recover_hp(healing_amount)
    else:
        target.heal(healing_amount)
        actual_healing = target.current_hp - hp_before

    # Emit healing event if event bus provided
    if event_bus is not None:
        event = Event(
            type=EventType.HEALING_DONE,
            data={
                "target": target.name,
                "item": item_name,
                "healing_dice": healing_dice,
                "healing_rolled": healing_amount,
                "healing_actual": actual_healing,
                "hp_before": hp_before,
                "hp_after": target.current_hp
            }
        )
        event_bus.emit(event)

    # Build result message
    if actual_healing == 0:
        if not target.is_alive:
            message = f"{target.name} is dead and cannot be healed"
        else:
            message = f"{target.name} is already at full health ({target.current_hp}/{target.max_hp} HP)"
    else:
        message = f"{target.name} healed for {actual_healing} HP (rolled {healing_dice}: {healing_amount})"
        if actual_healing < healing_amount:
            message += f" - capped at max HP"

    return ItemEffectResult(
        success=actual_healing > 0,
        effect_type="healing",
        amount=actual_healing,
        dice_notation=healing_dice,
        message=message
    )


def _apply_damage_effect(
    item_info: Dict[str, Any],
    target: Creature,
    dice_roller: DiceRoller,
    event_bus: Optional[EventBus]
) -> ItemEffectResult:
    """
    Apply a damage effect to a target.

    Used for thrown items like alchemist's fire, acid vials, holy water.

    Args:
        item_info: Item data containing "damage" dice notation and "damage_type"
        target: Creature to damage
        dice_roller: DiceRoller for rolling damage dice
        event_bus: Optional event bus for emitting DAMAGE_DEALT event

    Returns:
        ItemEffectResult with damage details
    """
    damage_dice = item_info.get("damage", "1d4")
    damage_type = item_info.get("damage_type", "fire")
    item_name = item_info.get("name", "Unknown Damage Item")

    # Roll damage dice
    damage_roll = dice_roller.roll(damage_dice)
    damage_amount = damage_roll.total

    # Check for resistance to this damage type
    resistance_condition = f"has_resistance_{damage_type}"
    has_resistance = target.has_condition(resistance_condition)

    # Halve damage if resistant
    if has_resistance:
        damage_amount = damage_amount // 2  # Integer division for D&D rules

    # Apply damage
    hp_before = target.current_hp
    target.take_damage(damage_amount)
    actual_damage = hp_before - target.current_hp

    # Emit damage event if event bus provided
    if event_bus is not None:
        event = Event(
            type=EventType.DAMAGE_DEALT,
            data={
                "target": target.name,
                "item": item_name,
                "damage_dice": damage_dice,
                "damage_type": damage_type,
                "damage_rolled": damage_roll.total,  # Original rolled damage
                "damage_after_resistance": damage_amount,  # After resistance applied
                "damage_actual": actual_damage,  # After all reductions
                "has_resistance": has_resistance,
                "hp_before": hp_before,
                "hp_after": target.current_hp
            }
        )
        event_bus.emit(event)

    # Build result message
    damage_roll_str = f"rolled {damage_dice}: {damage_roll.total}"

    if actual_damage == 0:
        # Show resistance if it caused the damage to be 0
        if has_resistance and damage_roll.total > 0:
            message = f"{target.name} takes no damage ({damage_roll_str}, halved by resistance)"
        else:
            message = f"{target.name} takes no damage"
    else:
        # If resistance was applied, show the halving
        if has_resistance:
            message = f"{target.name} takes {actual_damage} {damage_type} damage ({damage_roll_str}, halved by resistance)"
        else:
            message = f"{target.name} takes {actual_damage} {damage_type} damage ({damage_roll_str})"

        if not target.is_alive:
            message += " - KILLED!"

    return ItemEffectResult(
        success=actual_damage > 0,
        effect_type="damage",
        amount=actual_damage,
        dice_notation=damage_dice,
        message=message
    )


def _apply_condition_removal_effect(
    item_info: Dict[str, Any],
    target: Creature,
    event_bus: Optional[EventBus]
) -> ItemEffectResult:
    """
    Apply a condition removal effect to a target.

    Removes specific status conditions like poisoned, diseased, etc.

    Args:
        item_info: Item data containing "removes_conditions" list
        target: Creature to remove conditions from
        event_bus: Optional event bus for emitting CONDITION_REMOVED event

    Returns:
        ItemEffectResult with condition removal details
    """
    item_name = item_info.get("name", "Unknown Curative Item")
    conditions_to_remove = item_info.get("removes_conditions", [])

    if not conditions_to_remove:
        return ItemEffectResult(
            success=False,
            effect_type="condition_removal",
            message=f"{item_name} has no conditions specified to remove"
        )

    # Track which conditions were actually removed
    removed_conditions = []
    for condition in conditions_to_remove:
        if target.has_condition(condition):
            target.remove_condition(condition)
            removed_conditions.append(condition)

    # Emit event if any conditions were removed
    if event_bus is not None and removed_conditions:
        event = Event(
            type=EventType.CONDITION_REMOVED,
            data={
                "target": target.name,
                "item": item_name,
                "conditions_removed": removed_conditions
            }
        )
        event_bus.emit(event)

    # Build result message
    if not removed_conditions:
        message = f"{target.name} has none of the conditions that {item_name} can cure"
    else:
        conditions_str = ", ".join(removed_conditions)
        message = f"{target.name} is cured of: {conditions_str}"

    return ItemEffectResult(
        success=len(removed_conditions) > 0,
        effect_type="condition_removal",
        amount=len(removed_conditions),
        message=message
    )


def _apply_buff_effect(
    item_info: Dict[str, Any],
    target: Creature,
    event_bus: Optional[EventBus]
) -> ItemEffectResult:
    """
    Apply a buff effect to a target.

    # TODO: This is a simplified implementation that uses conditions to track buffs.
    # In the future, this should be replaced with a proper BuffManager system that:
    # - Tracks buff name, duration (rounds/minutes), and specific modifiers
    # - Handles buff expiration automatically
    # - Supports stacking rules and buff conflicts
    # - Provides query methods for "does this creature have advantage on X?"
    # See Option B in Phase 5 design discussion.

    Current implementation adds conditions with buff-specific names like:
    - "has_antitoxin" for advantage on poison saves
    - "has_resistance_fire" for fire resistance
    - "has_heroism" for temp HP and fear immunity

    Args:
        item_info: Item data containing buff configuration
        target: Creature to buff
        event_bus: Optional event bus for emitting BUFF_APPLIED event

    Returns:
        ItemEffectResult with buff details
    """
    item_name = item_info.get("name", "Unknown Buff Item")
    buff_type = item_info.get("buff_type")
    duration_minutes = item_info.get("duration_minutes", 60)

    if not buff_type:
        return ItemEffectResult(
            success=False,
            effect_type="buff",
            message=f"{item_name} has no buff_type specified"
        )

    # Simple condition-based buff tracking
    # Map buff_type to condition name
    buff_conditions = []

    if buff_type == "advantage_on_saves":
        save_type = item_info.get("save_type", "poison")
        condition_name = f"has_advantage_{save_type}_saves"
        target.add_condition(condition_name)
        buff_conditions.append(condition_name)

    elif buff_type == "resistance":
        damage_type = item_info.get("damage_type", "poison")
        condition_name = f"has_resistance_{damage_type}"
        target.add_condition(condition_name)
        buff_conditions.append(condition_name)

    elif buff_type == "temporary_hp":
        # TODO: Implement proper temporary HP system
        # For now, just add a condition indicating they have the buff
        target.add_condition("has_temporary_hp_buff")
        buff_conditions.append("has_temporary_hp_buff")

    # Add any extra conditions specified
    extra_conditions = item_info.get("adds_conditions", [])
    for condition in extra_conditions:
        target.add_condition(condition)
        buff_conditions.append(condition)

    # Emit event
    if event_bus is not None:
        event = Event(
            type=EventType.BUFF_APPLIED,
            data={
                "target": target.name,
                "item": item_name,
                "buff_type": buff_type,
                "duration_minutes": duration_minutes,
                "conditions_added": buff_conditions
            }
        )
        event_bus.emit(event)

    # Build result message
    duration_text = f"{duration_minutes} minutes" if duration_minutes < 60 else f"{duration_minutes // 60} hours"
    message = f"{target.name} gains {item_name} buff for {duration_text}"

    return ItemEffectResult(
        success=True,
        effect_type="buff",
        amount=duration_minutes,
        message=message
    )


def _apply_spell_effect(
    item_info: Dict[str, Any],
    target: Creature,
    dice_roller: DiceRoller,
    event_bus: Optional[EventBus]
) -> ItemEffectResult:
    """
    Apply a spell effect from a scroll or spell-effect potion.

    # TODO: This is a placeholder implementation.
    # When the spell system is implemented, this should:
    # - Look up the spell by spell_id
    # - Check if spell is on caster's class list
    # - Roll Intelligence check if not (DC = 10 + spell_level)
    # - Cast the spell with appropriate parameters
    # - Handle spell targeting, saving throws, etc.

    Args:
        item_info: Item data containing spell configuration
        target: Creature to apply spell effect to
        dice_roller: DiceRoller for ability checks
        event_bus: Optional event bus

    Returns:
        ItemEffectResult indicating spell system not implemented
    """
    item_name = item_info.get("name", "Unknown Spell Item")
    spell_id = item_info.get("spell_id", "unknown")

    return ItemEffectResult(
        success=False,
        effect_type="spell",
        message=f"{item_name} cannot be used - spell system not yet implemented (spell: {spell_id})"
    )
