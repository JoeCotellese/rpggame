# ABOUTME: Player Character class extending Creature
# ABOUTME: Adds class, level, XP, proficiency bonus, and combat bonuses

from enum import Enum
from typing import Optional
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.systems.inventory import Inventory


class CharacterClass(Enum):
    """Available character classes (MVP: Fighter only)"""
    FIGHTER = "fighter"


class Character(Creature):
    """
    Player character class.

    Extends Creature with player-specific features:
    - Character class and level
    - Experience points
    - Proficiency bonus
    - Attack and damage bonuses
    - Inventory management
    """

    def __init__(
        self,
        name: str,
        character_class: CharacterClass,
        level: int,
        abilities: Abilities,
        max_hp: int,
        ac: int,
        current_hp: int | None = None,
        xp: int = 0,
        inventory: Optional[Inventory] = None,
        race: str = "human"
    ):
        """
        Initialize a player character.

        Args:
            name: Character's name
            character_class: Character class (Fighter for MVP)
            level: Character level (1-3 for MVP)
            abilities: Ability scores
            max_hp: Maximum hit points
            ac: Armor class
            current_hp: Starting HP (defaults to max_hp)
            xp: Starting experience points
            inventory: Inventory instance (creates new one if not provided)
            race: Character race (human, mountain_dwarf, high_elf, halfling)
        """
        super().__init__(
            name=name,
            max_hp=max_hp,
            ac=ac,
            abilities=abilities,
            current_hp=current_hp
        )

        self.character_class = character_class
        self.level = level
        self.xp = xp
        self.race = race
        self.inventory = inventory if inventory is not None else Inventory()

    @property
    def proficiency_bonus(self) -> int:
        """
        Calculate proficiency bonus based on level.

        D&D 5E proficiency bonus:
        - Levels 1-4: +2
        - Levels 5-8: +3
        - Levels 9-12: +4
        - And so on...

        Returns:
            Proficiency bonus for the character's level
        """
        return 2 + (self.level - 1) // 4

    @property
    def melee_attack_bonus(self) -> int:
        """
        Calculate melee attack bonus.

        For fighters: proficiency bonus + Strength modifier

        Returns:
            Total attack bonus for melee attacks
        """
        return self.proficiency_bonus + self.abilities.str_mod

    @property
    def melee_damage_bonus(self) -> int:
        """
        Calculate melee damage bonus.

        Damage bonus is typically just the Strength modifier.

        Returns:
            Damage bonus for melee attacks
        """
        return self.abilities.str_mod

    @property
    def ranged_attack_bonus(self) -> int:
        """
        Calculate ranged attack bonus.

        For ranged weapons: proficiency bonus + Dexterity modifier

        Returns:
            Total attack bonus for ranged attacks
        """
        return self.proficiency_bonus + self.abilities.dex_mod

    @property
    def finesse_attack_bonus(self) -> int:
        """
        Calculate finesse attack bonus.

        For finesse weapons: proficiency bonus + higher of STR or DEX modifiers

        Returns:
            Total attack bonus for finesse attacks
        """
        ability_mod = max(self.abilities.str_mod, self.abilities.dex_mod)
        return self.proficiency_bonus + ability_mod

    def get_attack_bonus(self, weapon_id: str, items_data: dict) -> int:
        """
        Get appropriate attack bonus based on equipped weapon properties.

        Determines the correct attack type (STR melee, DEX ranged, or finesse)
        based on the weapon's properties and applies the appropriate modifier.

        Args:
            weapon_id: ID of the weapon (e.g., "longsword", "longbow")
            items_data: Dictionary of all items data from items.json

        Returns:
            Attack bonus for the weapon (includes proficiency bonus)

        Raises:
            KeyError: If weapon_id doesn't exist in items_data
        """
        # Get weapon data from items.json
        weapon_data = items_data.get("weapons", {}).get(weapon_id)
        if not weapon_data:
            raise KeyError(f"Weapon '{weapon_id}' not found in items data")

        properties = weapon_data.get("properties", [])
        category = weapon_data.get("category", "melee")

        # Determine attack type based on weapon properties
        if "finesse" in properties:
            # Finesse weapon: use highest of STR or DEX
            return self.finesse_attack_bonus
        elif category == "ranged":
            # Ranged weapon: use DEX
            return self.ranged_attack_bonus
        else:
            # Standard melee (STR): use STR
            return self.melee_attack_bonus

    def get_damage_bonus(self, weapon_id: str, items_data: dict) -> int:
        """
        Get damage bonus based on weapon properties.

        Determines the appropriate ability modifier (STR or DEX) based on the
        weapon's type and properties.

        Args:
            weapon_id: ID of the weapon (e.g., "longsword", "longbow")
            items_data: Dictionary of all items data from items.json

        Returns:
            Damage bonus modifier for the weapon

        Raises:
            KeyError: If weapon_id doesn't exist in items_data
        """
        # Get weapon data from items.json
        weapon_data = items_data.get("weapons", {}).get(weapon_id)
        if not weapon_data:
            raise KeyError(f"Weapon '{weapon_id}' not found in items data")

        properties = weapon_data.get("properties", [])
        category = weapon_data.get("category", "melee")

        # Determine damage bonus based on weapon type
        if "finesse" in properties:
            # Finesse weapon: use highest of STR or DEX
            return max(self.abilities.str_mod, self.abilities.dex_mod)
        elif category == "ranged":
            # Ranged weapon: use DEX
            return self.abilities.dex_mod
        else:
            # Standard melee: use STR
            return self.abilities.str_mod

    def gain_xp(self, amount: int) -> None:
        """
        Add experience points.

        Args:
            amount: XP to add
        """
        self.xp += amount

    def __str__(self) -> str:
        """String representation of the character"""
        status = "alive" if self.is_alive else "dead"
        return (
            f"{self.name} - Level {self.level} {self.character_class.value.title()} "
            f"(HP: {self.current_hp}/{self.max_hp}, AC: {self.ac}, XP: {self.xp}, {status})"
        )
