# ABOUTME: Item effect system for applying consumable effects to creatures
# ABOUTME: Handles healing potions, buffs, and other consumable item effects

from typing import Dict, Any, Optional
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

    Currently supports:
    - Healing effects (restores HP)

    Future support:
    - Buffs/debuffs
    - Temporary HP
    - Condition removal

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
