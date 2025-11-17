# ABOUTME: Player Character class extending Creature
# ABOUTME: Adds class, level, XP, proficiency bonus, combat bonuses, and skill tracking

from enum import Enum
from typing import Optional
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.core.dice import DiceRoller
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
        race: str = "human",
        skill_proficiencies: Optional[list[str]] = None
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
            skill_proficiencies: List of skill names the character is proficient in
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
        self.skill_proficiencies = skill_proficiencies if skill_proficiencies is not None else []
        self._dice_roller = DiceRoller()

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

    def gain_xp(self, amount: int) -> None:
        """
        Add experience points.

        Args:
            amount: XP to add
        """
        self.xp += amount

    def get_skill_modifier(self, skill: str, skills_data: dict) -> int:
        """
        Calculate skill check modifier for a given skill.

        The modifier is the ability modifier plus proficiency bonus if proficient.

        Args:
            skill: Skill name (e.g., "acrobatics", "stealth")
            skills_data: Skills data dictionary loaded from skills.json

        Returns:
            Total skill modifier (ability mod + proficiency if proficient)

        Raises:
            KeyError: If skill is not found in skills_data
        """
        if skill not in skills_data:
            raise KeyError(f"Unknown skill: {skill}")

        skill_info = skills_data[skill]
        ability_key = skill_info["ability"]

        # Get the ability modifier
        ability_mod = getattr(self.abilities, f"{ability_key}_mod")

        # Add proficiency bonus if proficient
        modifier = ability_mod
        if skill in self.skill_proficiencies:
            modifier += self.proficiency_bonus

        return modifier

    def make_skill_check(self, skill: str, dc: int, skills_data: dict, advantage: bool = False, disadvantage: bool = False) -> dict:
        """
        Roll a skill check against a difficulty class (DC).

        Args:
            skill: Skill name (e.g., "stealth", "perception")
            dc: Difficulty class to check against
            skills_data: Skills data dictionary loaded from skills.json
            advantage: Whether to roll with advantage (roll twice, take higher)
            disadvantage: Whether to roll with disadvantage (roll twice, take lower)

        Returns:
            Dictionary containing:
                - "skill": skill name
                - "ability": ability used for this skill
                - "dc": difficulty class
                - "roll": the d20 roll result (before modifier)
                - "modifier": skill modifier applied
                - "total": total result (roll + modifier)
                - "success": whether the check succeeded
                - "proficient": whether the character is proficient in this skill

        Raises:
            KeyError: If skill is not found in skills_data
        """
        if skill not in skills_data:
            raise KeyError(f"Unknown skill: {skill}")

        skill_info = skills_data[skill]
        modifier = self.get_skill_modifier(skill, skills_data)

        # Roll the d20
        dice_roll = self._dice_roller.roll("1d20", advantage=advantage, disadvantage=disadvantage)

        # Extract the d20 roll result (before modifier is added)
        roll_result = dice_roll.total - dice_roll.modifier  # Get just the die result
        total = roll_result + modifier

        return {
            "skill": skill,
            "ability": skill_info["ability"],
            "dc": dc,
            "roll": roll_result,
            "modifier": modifier,
            "total": total,
            "success": total >= dc,
            "proficient": skill in self.skill_proficiencies
        }

    def __str__(self) -> str:
        """String representation of the character"""
        status = "alive" if self.is_alive else "dead"
        return (
            f"{self.name} - Level {self.level} {self.character_class.value.title()} "
            f"(HP: {self.current_hp}/{self.max_hp}, AC: {self.ac}, XP: {self.xp}, {status})"
        )
