# ABOUTME: Player Character class extending Creature
# ABOUTME: Adds class, level, XP, proficiency bonus, combat bonuses, and skill tracking

from enum import Enum
from typing import Optional, List, Dict, Any
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.systems.inventory import Inventory
from dnd_engine.systems.resources import ResourcePool


class CharacterClass(Enum):
    """Available character classes"""
    FIGHTER = "fighter"
    ROGUE = "rogue"
    WIZARD = "wizard"
    CLERIC = "cleric"


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
        subclass: Optional[str] = None,
        saving_throw_proficiencies: Optional[List[str]] = None,
        skill_proficiencies: Optional[list[str]] = None,
        expertise_skills: Optional[List[str]] = None,
        weapon_proficiencies: Optional[List[str]] = None,
        armor_proficiencies: Optional[List[str]] = None
    ):
        """
        Initialize a player character.

        Args:
            name: Character's name
            character_class: Character class (Fighter, Rogue, etc.)
            level: Character level (1-3 for MVP)
            abilities: Ability scores
            max_hp: Maximum hit points
            ac: Armor class
            current_hp: Starting HP (defaults to max_hp)
            xp: Starting experience points
            inventory: Inventory instance (creates new one if not provided)
            race: Character race (human, mountain_dwarf, high_elf, halfling)
            subclass: Character subclass/archetype (e.g., "thief" for Rogue at level 3+)
            saving_throw_proficiencies: List of abilities the character is proficient in saving throws for (e.g., ["str", "con"])
            skill_proficiencies: List of skill names the character is proficient in
            expertise_skills: List of skills with expertise (doubled proficiency bonus)
            weapon_proficiencies: List of weapon types the character is proficient in (e.g., ["simple", "martial"])
            armor_proficiencies: List of armor types the character is proficient in (e.g., ["light", "medium", "heavy", "shields"])
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
        self.subclass = subclass
        self.inventory = inventory if inventory is not None else Inventory()
        self.saving_throw_proficiencies = saving_throw_proficiencies if saving_throw_proficiencies is not None else []
        self.skill_proficiencies = skill_proficiencies if skill_proficiencies is not None else []
        self.expertise_skills = expertise_skills if expertise_skills is not None else []
        self.weapon_proficiencies = weapon_proficiencies if weapon_proficiencies is not None else []
        self.armor_proficiencies = armor_proficiencies if armor_proficiencies is not None else []
        self.resource_pools: Dict[str, ResourcePool] = {}
        self._dice_roller = DiceRoller()

        # Death saving throw state
        self.death_save_successes: int = 0
        self.death_save_failures: int = 0
        self.stabilized: bool = False

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

    def get_saving_throw_modifier(self, ability: str) -> int:
        """
        Calculate saving throw modifier for an ability.

        Returns the ability modifier plus proficiency bonus if the character
        is proficient in saving throws for that ability.

        Args:
            ability: Ability name (e.g., "str", "dex", "con", "int", "wis", "cha")
                    or full name (e.g., "strength", "dexterity")

        Returns:
            Saving throw modifier (ability_modifier + proficiency_bonus if proficient)

        Raises:
            ValueError: If ability name is invalid
        """
        # Map short ability names to full names and vice versa
        short_to_full = {
            "str": "strength", "dex": "dexterity", "con": "constitution",
            "int": "intelligence", "wis": "wisdom", "cha": "charisma"
        }
        full_to_short = {
            "strength": "str", "dexterity": "dex", "constitution": "con",
            "intelligence": "int", "wisdom": "wis", "charisma": "cha"
        }

        # Normalize to short ability name
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

        # Add proficiency bonus if proficient in this save (check short name)
        if ability_short in self.saving_throw_proficiencies:
            modifier += self.proficiency_bonus

        return modifier

    def make_saving_throw(
        self,
        ability: str,
        dc: int,
        advantage: bool = False,
        disadvantage: bool = False,
        event_bus=None
    ) -> Dict[str, Any]:
        """
        Roll a saving throw against a DC.

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
            - "modifier": int (saving throw modifier)
            - "total": int (roll + modifier)
            - "dc": int (the DC that was beaten)
            - "ability": str (the ability that was saved with, in short form)

        Raises:
            ValueError: If ability name is invalid
        """
        from dnd_engine.core.dice import DiceRoller
        from dnd_engine.utils.events import Event, EventType

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
        elif ability_lower in full_to_short:
            ability_short = full_to_short[ability_lower]
        else:
            raise ValueError(f"Invalid ability name: {ability}")

        # Roll the saving throw
        roller = DiceRoller()
        roll_result = roller.roll("d20", advantage=advantage, disadvantage=disadvantage)

        # Get the saving throw modifier
        modifier = self.get_saving_throw_modifier(ability)

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

        # Emit event if event bus is provided
        if event_bus is not None:
            event = Event(
                type=EventType.SAVING_THROW,
                data={
                    "character": self.name,
                    "ability": ability_short,
                    "dc": dc,
                    "roll": result["roll"],
                    "modifier": modifier,
                    "total": total,
                    "success": success
                }
            )
            event_bus.emit(event)

        return result

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

        Includes proficiency bonus only if character is proficient with the weapon.
        If not proficient, returns just the ability modifier without proficiency bonus.

        Args:
            weapon_id: ID of the weapon (e.g., "longsword", "longbow")
            items_data: Dictionary of all items data from items.json

        Returns:
            Attack bonus for the weapon (includes proficiency bonus only if proficient)

        Raises:
            KeyError: If weapon_id doesn't exist in items_data
        """
        # Get weapon data from items.json
        weapon_data = items_data.get("weapons", {}).get(weapon_id)
        if not weapon_data:
            raise KeyError(f"Weapon '{weapon_id}' not found in items data")

        properties = weapon_data.get("properties", [])
        category = weapon_data.get("category", "melee")

        # Check if character is proficient with this weapon
        is_proficient = self.is_proficient_with_weapon(weapon_id, items_data)

        # Determine attack type and base ability modifier
        if "finesse" in properties:
            # Finesse weapon: use highest of STR or DEX
            ability_mod = max(self.abilities.str_mod, self.abilities.dex_mod)
        elif category == "ranged":
            # Ranged weapon: use DEX
            ability_mod = self.abilities.dex_mod
        else:
            # Standard melee (STR): use STR
            ability_mod = self.abilities.str_mod

        # Add proficiency bonus only if proficient
        if is_proficient:
            return ability_mod + self.proficiency_bonus
        else:
            return ability_mod

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

    def is_proficient_with_weapon(self, weapon_id: str, items_data: dict) -> bool:
        """
        Check if character is proficient with a weapon.

        A character is proficient with a weapon if either:
        1. The weapon's type (simple or martial) is in the weapon_proficiencies list, OR
        2. The specific weapon name (e.g., "rapiers", "longswords") is in the list

        Args:
            weapon_id: ID of the weapon (e.g., "longsword", "dagger")
            items_data: Dictionary of all items data from items.json

        Returns:
            True if character is proficient with the weapon, False otherwise

        Raises:
            KeyError: If weapon_id doesn't exist in items_data
        """
        weapon_data = items_data.get("weapons", {}).get(weapon_id)
        if not weapon_data:
            raise KeyError(f"Weapon '{weapon_id}' not found in items data")

        weapon_type = weapon_data.get("weapon_type", "")
        # Check both weapon type (e.g., "martial") and specific weapon name (e.g., "rapiers")
        # Convert weapon_id to plural form for comparison (e.g., "rapier" -> "rapiers")
        weapon_name_plural = f"{weapon_id}s" if not weapon_id.endswith('s') else weapon_id
        return weapon_type in self.weapon_proficiencies or weapon_name_plural in self.weapon_proficiencies

    def is_proficient_with_armor(self, armor_id: str, items_data: dict) -> bool:
        """
        Check if character is proficient with armor.

        A character is proficient with armor if the armor's type (light, medium, heavy)
        or "shields" is in the character's armor_proficiencies list.

        Args:
            armor_id: ID of the armor (e.g., "chain_mail", "leather")
            items_data: Dictionary of all items data from items.json

        Returns:
            True if character is proficient with the armor, False otherwise

        Raises:
            KeyError: If armor_id doesn't exist in items_data
        """
        armor_data = items_data.get("armor", {}).get(armor_id)
        if not armor_data:
            raise KeyError(f"Armor '{armor_id}' not found in items data")

        armor_type = armor_data.get("armor_type", "")
        return armor_type in self.armor_proficiencies

    def gain_xp(self, amount: int) -> None:
        """
        Add experience points.

        Args:
            amount: XP to add
        """
        self.xp += amount

    def check_for_level_up(self, data_loader, event_bus=None) -> bool:
        """
        Check if character has enough XP to level up and execute level-up if so.

        Args:
            data_loader: DataLoader instance to access progression data
            event_bus: Optional EventBus to emit level-up events

        Returns:
            True if character leveled up, False otherwise
        """
        progression = data_loader.load_progression()
        next_level = self.level + 1

        # Check if we can level up (max level 20)
        if next_level > 20:
            return False

        next_level_xp = int(progression["xp_by_level"].get(str(next_level), 999999))

        if self.xp >= next_level_xp:
            self._level_up(data_loader, event_bus)
            return True

        return False

    def _level_up(self, data_loader, event_bus=None) -> None:
        """
        Perform level-up: increase level, HP, and grant class features.

        Args:
            data_loader: DataLoader instance to access class data
            event_bus: Optional EventBus to emit events
        """
        old_level = self.level
        old_max_hp = self.max_hp

        # Increase level
        self.level += 1

        # Increase HP
        self._increase_hp(data_loader)

        # Grant class features for new level
        self._grant_class_features(data_loader, event_bus)

        # Emit level-up event
        if event_bus is not None:
            from dnd_engine.utils.events import Event, EventType
            event_bus.emit(Event(
                type=EventType.LEVEL_UP,
                data={
                    "character": self.name,
                    "old_level": old_level,
                    "new_level": self.level,
                    "hp_increase": self.max_hp - old_max_hp
                }
            ))

    def _increase_hp(self, data_loader) -> None:
        """
        Increase max HP on level-up by rolling hit die + CON modifier.

        Args:
            data_loader: DataLoader instance to access class data
        """
        # Get hit die from class data
        classes_data = data_loader.load_classes()
        class_data = classes_data.get(self.character_class.value)

        if not class_data:
            # Fallback to d8 if class data not found
            hit_die = "1d8"
        else:
            hit_die = class_data.get("hit_die", "1d8")

        # Roll hit die and add CON modifier
        con_mod = self.abilities.con_mod
        hp_increase = self._dice_roller.roll(hit_die).total + con_mod

        # Minimum 1 HP per level
        hp_increase = max(1, hp_increase)

        # Increase max HP and current HP
        self.max_hp += hp_increase
        self.current_hp += hp_increase

    def _grant_class_features(self, data_loader, event_bus=None) -> None:
        """
        Grant new class features for current level.

        Args:
            data_loader: DataLoader instance to access class data
            event_bus: Optional EventBus to emit feature granted events
        """
        classes_data = data_loader.load_classes()
        class_data = classes_data.get(self.character_class.value)

        if not class_data:
            return

        features = class_data.get("features_by_level", {}).get(str(self.level), [])

        for feature in features:
            # If feature has resource pool, add it
            if "resource" in feature:
                resource = feature["resource"]
                pool = ResourcePool(
                    name=resource["pool"],
                    current=resource["max_uses"],
                    maximum=resource["max_uses"],
                    recovery_type=resource["recovery"]
                )
                self.add_resource_pool(pool)

            # Emit feature granted event
            if event_bus is not None:
                from dnd_engine.utils.events import Event, EventType
                event_bus.emit(Event(
                    type=EventType.FEATURE_GRANTED,
                    data={
                        "character": self.name,
                        "level": self.level,
                        "feature": feature["name"]
                    }
                ))

    def get_skill_modifier(self, skill: str, skills_data: dict) -> int:
        """
        Calculate skill check modifier for a given skill.

        The modifier is the ability modifier plus proficiency bonus if proficient.
        If the character has expertise in this skill, the proficiency bonus is doubled.

        Args:
            skill: Skill name (e.g., "acrobatics", "stealth")
            skills_data: Skills data dictionary loaded from skills.json

        Returns:
            Total skill modifier (ability mod + proficiency if proficient, doubled if expertise)

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
            # Check expertise (double proficiency bonus)
            if skill in self.expertise_skills:
                modifier += self.proficiency_bonus * 2
            else:
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

    def get_sneak_attack_dice(self) -> Optional[str]:
        """
        Get sneak attack dice for Rogue.

        Returns the damage dice for sneak attack based on character level.
        For non-Rogues, returns None.

        Returns:
            Sneak attack dice notation (e.g., "1d6", "2d6") or None if not a Rogue
        """
        if self.character_class != CharacterClass.ROGUE:
            return None

        # Sneak attack dice progression
        sneak_dice_map = {
            1: "1d6",
            3: "2d6",
            5: "3d6",
            7: "4d6",
            9: "5d6",
            11: "6d6",
            13: "7d6",
            15: "8d6",
            17: "9d6",
            19: "10d6"
        }

        # Find the highest level threshold we've met
        dice = "1d6"
        for level_threshold in sorted(sneak_dice_map.keys()):
            if self.level >= level_threshold:
                dice = sneak_dice_map[level_threshold]

        return dice

    def can_sneak_attack(self, has_advantage: bool = False, has_disadvantage: bool = False, ally_nearby: bool = False) -> bool:
        """
        Check if Rogue can use Sneak Attack.

        Sneak attack can be used if:
        - Character is a Rogue
        - Attack roll has advantage, OR
        - An ally is within 5 feet of target (not yet implemented)
        - AND the attack does not have disadvantage

        Args:
            has_advantage: Whether the attack roll has advantage
            has_disadvantage: Whether the attack roll has disadvantage
            ally_nearby: Whether an ally is within 5 feet of target (future implementation)

        Returns:
            True if sneak attack conditions are met, False otherwise
        """
        if self.character_class != CharacterClass.ROGUE:
            return False

        # Cannot use sneak attack with disadvantage
        if has_disadvantage:
            return False

        # Can use sneak attack if attack has advantage or ally is nearby
        return has_advantage or ally_nearby

    def has_fast_hands(self) -> bool:
        """
        Check if character has the Thief Fast Hands feature.

        Fast Hands is a Rogue (Thief) feature gained at level 3 that allows:
        - Using bonus action to make Dexterity (Sleight of Hand) check
        - Using bonus action to use thieves' tools
        - Using bonus action to take the Use an Object action

        The third ability allows Thieves to use consumable items (like potions)
        as a bonus action instead of an action.

        Returns:
            True if character is a level 3+ Rogue with Thief subclass
        """
        return (
            self.character_class == CharacterClass.ROGUE
            and self.level >= 3
            and self.subclass == "thief"
        )

    def add_resource_pool(self, pool: ResourcePool) -> None:
        """
        Add a resource pool to character.

        Args:
            pool: ResourcePool instance to add

        Side Effects:
            Stores the pool in resource_pools dictionary keyed by pool name
        """
        self.resource_pools[pool.name] = pool

    def use_resource(self, pool_name: str, amount: int = 1) -> bool:
        """
        Use resource from a pool.

        Args:
            pool_name: Name of the resource pool
            amount: Number of resources to use (default 1)

        Returns:
            True if resource was used, False if pool not found or insufficient resources
        """
        if pool_name in self.resource_pools:
            return self.resource_pools[pool_name].use(amount)
        return False

    def get_resource_pool(self, pool_name: str) -> Optional[ResourcePool]:
        """
        Get a resource pool by name.

        Args:
            pool_name: Name of the resource pool

        Returns:
            ResourcePool instance or None if not found
        """
        return self.resource_pools.get(pool_name)

    def get_spell_attack_bonus(self, ability: str) -> int:
        """
        Calculate spell attack bonus.

        Spell attack bonus = proficiency bonus + spellcasting ability modifier

        Args:
            ability: Spellcasting ability (e.g., "int", "wis", "cha")

        Returns:
            Total spell attack bonus

        Raises:
            ValueError: If ability name is invalid
        """
        # Map short ability names to full names
        short_to_full = {
            "str": "strength", "dex": "dexterity", "con": "constitution",
            "int": "intelligence", "wis": "wisdom", "cha": "charisma"
        }

        # Normalize to short ability name
        ability_lower = ability.lower()
        if ability_lower in short_to_full:
            ability_full = short_to_full[ability_lower]
        else:
            # Assume it's already a full name
            full_to_short = {v: k for k, v in short_to_full.items()}
            if ability_lower in full_to_short:
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

        return self.proficiency_bonus + modifier

    def get_spell_save_dc(self, ability: str) -> int:
        """
        Calculate spell save DC.

        Spell save DC = 8 + proficiency bonus + spellcasting ability modifier

        Args:
            ability: Spellcasting ability (e.g., "int", "wis", "cha")

        Returns:
            Spell save DC

        Raises:
            ValueError: If ability name is invalid
        """
        # Map short ability names to full names
        short_to_full = {
            "str": "strength", "dex": "dexterity", "con": "constitution",
            "int": "intelligence", "wis": "wisdom", "cha": "charisma"
        }

        # Normalize to short ability name
        ability_lower = ability.lower()
        if ability_lower in short_to_full:
            ability_full = short_to_full[ability_lower]
        else:
            # Assume it's already a full name
            full_to_short = {v: k for k, v in short_to_full.items()}
            if ability_lower in full_to_short:
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

        return 8 + self.proficiency_bonus + modifier

    def get_available_spell_slots(self, level: int) -> int:
        """
        Get the number of available spell slots for a given level.

        Args:
            level: Spell level (1-9)

        Returns:
            Number of available spell slots (0 if pool doesn't exist or is exhausted)
        """
        if level < 1 or level > 9:
            return 0

        pool_name = f"spell_slots_level_{level}"
        pool = self.resource_pools.get(pool_name)

        if pool is None:
            return 0

        return pool.current

    def use_spell_slot(self, level: int) -> bool:
        """
        Use a spell slot of the given level.

        Args:
            level: Spell level (1-9)

        Returns:
            True if spell slot was used successfully, False if no slots available
        """
        if level < 1 or level > 9:
            return False

        pool_name = f"spell_slots_level_{level}"
        return self.use_resource(pool_name, 1)

    @staticmethod
    def _level_to_ordinal(level: int) -> str:
        """
        Convert spell level number to ordinal string.

        Args:
            level: Spell level (0-9)

        Returns:
            Ordinal string (e.g., "1st", "2nd", "3rd", "4th")
        """
        if level == 0:
            return "cantrip"
        elif level == 1:
            return "1st"
        elif level == 2:
            return "2nd"
        elif level == 3:
            return "3rd"
        else:
            return f"{level}th"

    def scale_cantrip_damage(self, base_damage_dice: str) -> str:
        """
        Scale cantrip damage based on character level.

        D&D 5E cantrip scaling:
        - Levels 1-4: base damage (e.g., 1d10)
        - Levels 5-10: 2x base damage (e.g., 2d10)
        - Levels 11-16: 3x base damage (e.g., 3d10)
        - Levels 17-20: 4x base damage (e.g., 4d10)

        Args:
            base_damage_dice: Base damage dice (e.g., "1d10", "1d8")

        Returns:
            Scaled damage dice notation
        """
        import re

        # Determine scaling multiplier based on level
        if self.level >= 17:
            multiplier = 4
        elif self.level >= 11:
            multiplier = 3
        elif self.level >= 5:
            multiplier = 2
        else:
            multiplier = 1

        # Parse the base damage dice
        pattern = re.compile(r'^(\d*)d(\d+)(([+-])(\d+))?$', re.IGNORECASE)
        match = pattern.match(base_damage_dice.strip())

        if not match:
            # If we can't parse it, return as-is
            return base_damage_dice

        # Extract components
        count_str = match.group(1)
        count = int(count_str) if count_str else 1
        sides = match.group(2)
        modifier_part = match.group(3) if match.group(3) else ""

        # Apply multiplier to dice count
        scaled_count = count * multiplier

        # Reconstruct the notation
        return f"{scaled_count}d{sides}{modifier_part}"

    def take_damage(self, amount: int, event_bus=None) -> None:
        """
        Apply damage to the character.

        Handles D&D 5E death save mechanics:
        - If damage brings character to 0 HP, they fall unconscious
        - If damage at 0 HP: add 1 death save failure
        - If damage >= max HP at 0 HP: instant death (massive damage)

        Args:
            amount: Amount of damage to apply
            event_bus: Optional EventBus for event emission
        """
        from dnd_engine.utils.events import Event, EventType

        was_unconscious = self.is_unconscious

        # Apply damage (parent implementation)
        super().take_damage(amount)

        # Handle damage while at 0 HP
        if was_unconscious:
            # Check for massive damage (damage >= max HP = instant death)
            if amount >= self.max_hp:
                # Instant death
                self.death_save_failures = 3

                if event_bus is not None:
                    event_bus.emit(Event(
                        type=EventType.MASSIVE_DAMAGE_DEATH,
                        data={
                            "character": self.name,
                            "damage": amount,
                            "max_hp": self.max_hp
                        }
                    ))
            else:
                # Taking damage at 0 HP = 1 automatic death save failure
                self.add_death_save_failure(1)

                if event_bus is not None:
                    event_bus.emit(Event(
                        type=EventType.DAMAGE_AT_ZERO_HP,
                        data={
                            "character": self.name,
                            "damage": amount,
                            "failures": self.death_save_failures
                        }
                    ))

    def recover_hp(self, amount: Optional[int] = None) -> int:
        """
        Recover hit points.

        If recovering from 0 HP, resets death saves.

        Args:
            amount: Amount to heal (None = full heal)

        Returns:
            Amount actually healed
        """
        was_unconscious = (self.current_hp == 0)

        if amount is None:
            amount = self.max_hp - self.current_hp

        healed = min(amount, self.max_hp - self.current_hp)
        self.current_hp += healed

        # Reset death saves if regaining HP from unconscious
        if was_unconscious and self.current_hp > 0:
            self.reset_death_saves()

        return healed

    def recover_resources(self, rest_type: str) -> List[str]:
        """
        Recover resource pools based on rest type.

        Args:
            rest_type: "short_rest" or "long_rest"

        Returns:
            List of recovered resource pool names
        """
        recovered = []

        for pool_name, pool in self.resource_pools.items():
            if rest_type == "long_rest":
                # Long rest recovers both short_rest and long_rest resources
                if pool.recovery_type in ["short_rest", "long_rest"]:
                    pool.recover()
                    recovered.append(pool_name)
            elif rest_type == "short_rest":
                # Short rest only recovers short_rest resources
                if pool.recovery_type == "short_rest":
                    pool.recover()
                    recovered.append(pool_name)

        return recovered

    def take_short_rest(self) -> dict:
        """
        Take a short rest (1 hour).

        Effects:
        - Recover resources with recovery_type="short_rest"
        - Can spend Hit Dice to heal (not implemented in MVP)

        Returns:
            Dictionary containing:
            - "character": character name
            - "rest_type": "short"
            - "resources_recovered": list of recovered resource names
            - "hp_recovered": 0 (Hit Dice healing for future)
        """
        resources_recovered = self.recover_resources("short_rest")

        return {
            "character": self.name,
            "rest_type": "short",
            "resources_recovered": resources_recovered,
            "hp_recovered": 0  # Hit Dice healing for future
        }

    def take_long_rest(self) -> dict:
        """
        Take a long rest (8 hours).

        Effects:
        - Recover all HP
        - Recover all resources with recovery_type="long_rest" or "short_rest"
        - Recover half of spent Hit Dice (not implemented in MVP)

        Returns:
            Dictionary containing:
            - "character": character name
            - "rest_type": "long"
            - "hp_recovered": amount of HP recovered
            - "resources_recovered": list of recovered resource names
            - "conditions_removed": empty list (for future implementation)
        """
        hp_recovered = self.recover_hp()
        resources_recovered = self.recover_resources("long_rest")

        return {
            "character": self.name,
            "rest_type": "long",
            "hp_recovered": hp_recovered,
            "resources_recovered": resources_recovered,
            "conditions_removed": []  # Future
        }

    @property
    def is_unconscious(self) -> bool:
        """
        Check if the character is unconscious.

        A character is unconscious when:
        - HP is 0
        - AND has not reached 3 death save failures (which means death)

        Returns:
            True if unconscious but alive, False otherwise
        """
        return self.current_hp == 0 and self.death_save_failures < 3

    @property
    def is_dead(self) -> bool:
        """
        Check if the character is dead.

        A character is dead when:
        - They have 3 death save failures

        Returns:
            True if dead, False otherwise
        """
        return self.death_save_failures >= 3

    def make_death_save(self, event_bus=None) -> Dict[str, Any]:
        """
        Roll a death saving throw.

        D&D 5E death save rules:
        - Roll 1d20 (no modifiers)
        - 10+ = Success
        - 9 or less = Failure
        - Natural 20 = Regain 1 HP and become conscious
        - Natural 1 = Counts as 2 failures
        - 3 successes = Stabilized
        - 3 failures = Death

        Returns:
            Dictionary with:
            - "roll": int (the d20 roll)
            - "success": bool (whether the save succeeded)
            - "natural_20": bool (whether it was a nat 20)
            - "natural_1": bool (whether it was a nat 1)
            - "successes": int (total successes after this roll)
            - "failures": int (total failures after this roll)
            - "stabilized": bool (whether character is now stabilized)
            - "dead": bool (whether character is now dead)
            - "conscious": bool (whether character regained consciousness)
        """
        from dnd_engine.utils.events import Event, EventType

        # Cannot make death saves if not unconscious
        if not self.is_unconscious:
            raise ValueError(f"{self.name} cannot make death saves (not unconscious)")

        # Already stabilized characters don't make death saves
        if self.stabilized:
            return {
                "roll": 0,
                "success": True,
                "natural_20": False,
                "natural_1": False,
                "successes": self.death_save_successes,
                "failures": self.death_save_failures,
                "stabilized": True,
                "dead": False,
                "conscious": False
            }

        # Roll d20
        roll_result = self._dice_roller.roll("1d20")
        roll = roll_result.total

        # Check for natural 20 or 1
        natural_20 = (roll == 20)
        natural_1 = (roll == 1)

        # Determine success/failure
        success = roll >= 10
        conscious = False

        # Apply results
        if natural_20:
            # Natural 20: regain 1 HP and become conscious
            self.current_hp = 1
            self.reset_death_saves()
            conscious = True
        elif natural_1:
            # Natural 1: counts as 2 failures
            self.death_save_failures += 2
        elif success:
            # Success
            self.death_save_successes += 1
            # Check for stabilization (3 successes)
            if self.death_save_successes >= 3:
                self.stabilized = True
        else:
            # Failure
            self.death_save_failures += 1

        # Build result
        result = {
            "roll": roll,
            "success": success,
            "natural_20": natural_20,
            "natural_1": natural_1,
            "successes": self.death_save_successes,
            "failures": self.death_save_failures,
            "stabilized": self.stabilized,
            "dead": self.is_dead,
            "conscious": conscious
        }

        # Emit event
        if event_bus is not None:
            event = Event(
                type=EventType.DEATH_SAVE,
                data={
                    "character": self.name,
                    "roll": roll,
                    "success": success,
                    "natural_20": natural_20,
                    "natural_1": natural_1,
                    "successes": self.death_save_successes,
                    "failures": self.death_save_failures,
                    "stabilized": self.stabilized,
                    "dead": self.is_dead,
                    "conscious": conscious
                }
            )
            event_bus.emit(event)

        return result

    def reset_death_saves(self) -> None:
        """
        Reset death saving throws.

        Called when:
        - Character regains any HP
        - Natural 20 on death save
        """
        self.death_save_successes = 0
        self.death_save_failures = 0
        self.stabilized = False

    def add_death_save_failure(self, count: int = 1) -> None:
        """
        Add death save failure(s).

        Used when:
        - Character takes damage while at 0 HP (1 failure)
        - Massive damage (instant death)

        Args:
            count: Number of failures to add (default 1)
        """
        self.death_save_failures += count

    def stabilize_character(self) -> None:
        """
        Stabilize the character.

        Used when:
        - Ally uses Medicine check (DC 10) successfully
        - Character gets 3 death save successes
        """
        if self.current_hp == 0:
            self.stabilized = True

    def __str__(self) -> str:
        """String representation of the character"""
        status = "alive" if self.is_alive else "dead"
        return (
            f"{self.name} - Level {self.level} {self.character_class.value.title()} "
            f"(HP: {self.current_hp}/{self.max_hp}, AC: {self.ac}, XP: {self.xp}, {status})"
        )
