# ABOUTME: Base Creature class representing any living entity in the game
# ABOUTME: Handles HP, abilities, conditions, damage, and healing

from dataclasses import dataclass, field
from typing import Set


@dataclass
class Abilities:
    """
    D&D 5E ability scores (STR, DEX, CON, INT, WIS, CHA).

    Ability scores typically range from 1-20 for player characters and monsters.
    Each score provides a modifier calculated as: (score - 10) // 2
    """
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int

    @property
    def str_mod(self) -> int:
        """Calculate Strength modifier"""
        return (self.strength - 10) // 2

    @property
    def dex_mod(self) -> int:
        """Calculate Dexterity modifier"""
        return (self.dexterity - 10) // 2

    @property
    def con_mod(self) -> int:
        """Calculate Constitution modifier"""
        return (self.constitution - 10) // 2

    @property
    def int_mod(self) -> int:
        """Calculate Intelligence modifier"""
        return (self.intelligence - 10) // 2

    @property
    def wis_mod(self) -> int:
        """Calculate Wisdom modifier"""
        return (self.wisdom - 10) // 2

    @property
    def cha_mod(self) -> int:
        """Calculate Charisma modifier"""
        return (self.charisma - 10) // 2


class Creature:
    """
    Base class for all living entities (PCs, NPCs, monsters).

    Handles core D&D 5E mechanics: HP, AC, abilities, conditions, damage, and healing.
    """

    def __init__(
        self,
        name: str,
        max_hp: int,
        ac: int,
        abilities: Abilities,
        current_hp: int | None = None
    ):
        """
        Initialize a creature.

        Args:
            name: Creature's name
            max_hp: Maximum hit points
            ac: Armor class (target number for attacks)
            abilities: Ability scores (STR, DEX, CON, INT, WIS, CHA)
            current_hp: Starting HP (defaults to max_hp if not specified)
        """
        self.name = name
        self.max_hp = max_hp
        self.current_hp = current_hp if current_hp is not None else max_hp
        self.ac = ac
        self.abilities = abilities
        self.conditions: Set[str] = set()

    @property
    def is_alive(self) -> bool:
        """Check if the creature is alive (HP > 0)"""
        return self.current_hp > 0

    @property
    def initiative_modifier(self) -> int:
        """Initiative modifier (uses Dexterity)"""
        return self.abilities.dex_mod

    def take_damage(self, amount: int) -> None:
        """
        Apply damage to the creature.

        HP cannot go below 0.

        Args:
            amount: Amount of damage to apply
        """
        self.current_hp = max(0, self.current_hp - amount)

    def heal(self, amount: int) -> None:
        """
        Heal the creature.

        Cannot heal dead creatures (HP = 0).
        Cannot exceed max HP.

        Args:
            amount: Amount of HP to restore
        """
        if not self.is_alive:
            # Dead creatures cannot be healed (would need resurrection)
            return

        self.current_hp = min(self.max_hp, self.current_hp + amount)

    def add_condition(self, condition: str) -> None:
        """
        Add a condition to the creature (e.g., 'prone', 'stunned').

        Args:
            condition: Name of the condition to add
        """
        self.conditions.add(condition.lower())

    def remove_condition(self, condition: str) -> None:
        """
        Remove a condition from the creature.

        Args:
            condition: Name of the condition to remove
        """
        self.conditions.discard(condition.lower())

    def has_condition(self, condition: str) -> bool:
        """
        Check if the creature has a specific condition.

        Args:
            condition: Name of the condition to check

        Returns:
            True if the creature has the condition
        """
        return condition.lower() in self.conditions

    def make_saving_throw(
        self,
        ability: str,
        dc: int,
        advantage: bool = False,
        disadvantage: bool = False,
        event_bus=None
    ) -> dict:
        """
        Roll an ability saving throw against a DC.

        Basic implementation for creatures (monsters). Characters may override
        this to add proficiency bonuses.

        Args:
            ability: Ability to save with (e.g., "str", "dex", "con", "int", "wis", "cha")
            dc: Difficulty class to beat
            advantage: Roll with advantage (roll twice, take higher)
            disadvantage: Roll with disadvantage (roll twice, take lower)
            event_bus: Optional EventBus instance to emit saving throw event

        Returns:
            Dictionary with:
            - "success": bool (total >= dc)
            - "roll": int (the d20 roll before modifier)
            - "modifier": int (ability modifier)
            - "total": int (roll + modifier)
            - "dc": int (the DC that was beaten)
            - "ability": str (the ability that was saved with, in short form)

        Raises:
            ValueError: If ability name is invalid
        """
        from dnd_engine.core.dice import DiceRoller

        # Normalize ability to short name
        short_to_full = {
            "str": "strength", "dex": "dexterity", "con": "constitution",
            "int": "intelligence", "wis": "wisdom", "cha": "charisma"
        }
        full_to_short = {
            "strength": "str", "dexterity": "dex", "constitution": "con",
            "intelligence": "int", "wisdom": "wis", "charisma": "cha"
        }

        ability_lower = ability.lower()
        if ability_lower in short_to_full:
            ability_short = ability_lower
            ability_full = short_to_full[ability_lower]
        elif ability_lower in full_to_short:
            ability_short = full_to_short[ability_lower]
            ability_full = ability_lower
        else:
            raise ValueError(f"Invalid ability name: {ability}")

        # Get ability modifier
        if ability_full == "strength":
            modifier = self.abilities.str_mod
        elif ability_full == "dexterity":
            modifier = self.abilities.dex_mod
        elif ability_full == "constitution":
            modifier = self.abilities.con_mod
        elif ability_full == "intelligence":
            modifier = self.abilities.int_mod
        elif ability_full == "wisdom":
            modifier = self.abilities.wis_mod
        elif ability_full == "charisma":
            modifier = self.abilities.cha_mod
        else:
            raise ValueError(f"Invalid ability name: {ability}")

        # Roll the saving throw
        roller = DiceRoller()
        roll_result = roller.roll("d20", advantage=advantage, disadvantage=disadvantage)

        # Calculate total
        total = roll_result.total + modifier

        # Determine success
        success = total >= dc

        # Create result dict
        result = {
            "success": success,
            "roll": roll_result.rolls[0] if len(roll_result.rolls) == 1 else max(roll_result.rolls) if advantage else min(roll_result.rolls),
            "modifier": modifier,
            "total": total,
            "dc": dc,
            "ability": ability_short
        }

        return result

    def __str__(self) -> str:
        """String representation of the creature"""
        status = "alive" if self.is_alive else "dead"
        return f"{self.name} (HP: {self.current_hp}/{self.max_hp}, AC: {self.ac}, {status})"
