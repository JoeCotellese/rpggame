# ABOUTME: Helper functions for gathering combat context data from various sources
# ABOUTME: Used by CombatContextBuilder to assemble complete context dictionaries

import logging
from typing import Any

from dnd_engine.core.character import Character
from dnd_engine.core.creature import Creature
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.inventory import EquipmentSlot

logger = logging.getLogger(__name__)


def get_weapon_context(
    attacker: Character | Creature,
    data_loader: DataLoader,
    action_data: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """
    Get weapon name and damage type for an attacker.

    Args:
        attacker: The attacking Character or Creature
        data_loader: DataLoader for accessing item data
        action_data: For spells or Creature actions, the action/spell dict

    Returns:
        Tuple of (weapon_name, damage_type)
            - weapon_name: Display name of weapon/spell/attack
            - damage_type: Type of damage or empty string
    """
    # If action_data is provided (spell or enemy action), use it directly
    if action_data:
        weapon_name = action_data.get("name", "attack")
        damage_type = action_data.get("damage_type", "")
        return weapon_name, damage_type

    # Check if attacker is a Character (player)
    if isinstance(attacker, Character):
        # Player character - get equipped weapon
        equipped_weapon = attacker.inventory.get_equipped_item(EquipmentSlot.WEAPON)
        if equipped_weapon:
            items_data = data_loader.load_items()
            weapon_data = items_data.get("weapons", {}).get(equipped_weapon, {})
            weapon_name = weapon_data.get("name", equipped_weapon)
            damage_type = weapon_data.get("damage_type", "bludgeoning")
            if not weapon_data:
                logger.warning(f"Weapon '{equipped_weapon}' not found in items data")
            return weapon_name, damage_type
        else:
            # Unarmed attack
            return "unarmed strike", "bludgeoning"
    else:
        # Enemy creature without action data
        return "attack", ""


def get_attacker_race(
    attacker: Character | Creature,
    data_loader: DataLoader,
    monster_cache: dict[str, dict[str, Any]] | None = None,
) -> str:
    """
    Get race or type for an attacker.

    For Characters: looks up race name in races data
    For Creatures: uses "type" field from monster data

    Args:
        attacker: The attacking Character or Creature
        data_loader: DataLoader for accessing race/monster data
        monster_cache: Optional pre-built cache of monster name -> monster data

    Returns:
        Race/type string (empty string if not found)
    """
    # Check if attacker is a Character (player)
    if isinstance(attacker, Character):
        races_data = data_loader.load_races()
        race_data = races_data.get(attacker.race, {})
        race_name = race_data.get("name", "")
        if not race_name:
            logger.warning(f"Race '{attacker.race}' not found in race data")
        return race_name
    else:
        # For enemies, use cache if available, otherwise search
        if monster_cache:
            monster_data = monster_cache.get(attacker.name, {})
        else:
            monsters = data_loader.load_monsters()
            monster_data = next(
                (mdata for mdata in monsters.values() if mdata["name"] == attacker.name),
                {},
            )

        if not monster_data:
            logger.warning(f"Monster '{attacker.name}' not found in monster data")
            return ""
        return monster_data.get("type", "")


def get_defender_armor(
    defender: Character | Creature,
    data_loader: DataLoader,
    monster_cache: dict[str, dict[str, Any]] | None = None,
) -> str:
    """
    Get armor description for a defender.

    For Characters: looks up equipped armor type
    For Creatures: uses ac_source from monster data

    Args:
        defender: The defending Character or Creature
        data_loader: DataLoader for accessing item/monster data
        monster_cache: Optional pre-built cache of monster name -> monster data

    Returns:
        Armor description string (empty string if none)
    """
    # Check if defender is a Character (player)
    if isinstance(defender, Character):
        equipped_armor = defender.inventory.get_equipped_item(EquipmentSlot.ARMOR)
        if equipped_armor:
            items_data = data_loader.load_items()
            armor_data = items_data.get("armor", {}).get(equipped_armor, {})
            armor_type = armor_data.get("armor_type", "")
            if not armor_data:
                logger.warning(f"Armor '{equipped_armor}' not found in items data")
            if armor_type:
                return f"{armor_type} armor"
        return ""
    else:
        # For enemies, use cache if available, otherwise search
        if monster_cache:
            monster_data = monster_cache.get(defender.name, {})
        else:
            monsters = data_loader.load_monsters()
            monster_data = next(
                (mdata for mdata in monsters.values() if mdata["name"] == defender.name),
                {},
            )

        if not monster_data:
            logger.warning(f"Monster '{defender.name}' not found in monster data")
            return ""

        ac_source = monster_data.get("ac_source", "")
        return ac_source if ac_source else ""
