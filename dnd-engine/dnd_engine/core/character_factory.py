# ABOUTME: Character creation factory for D&D 5E character generation
# ABOUTME: Handles ability rolling, assignment, racial bonuses, and stat calculations

from typing import Any

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.inventory import EquipmentSlot
from dnd_engine.systems.resources import ResourcePool


class CharacterFactory:
    """
    Factory class for creating D&D 5E characters.

    Handles:
    - Rolling ability scores (4d6 drop lowest)
    - Auto-assigning abilities based on class priorities
    - Swapping abilities
    - Applying racial bonuses
    - Calculating derived stats (HP, AC, attack bonus)
    - Applying starting equipment
    - Interactive character creation flow
    """

    def __init__(self, dice_roller: DiceRoller | None = None):
        """
        Initialize the character factory.

        Args:
            dice_roller: Optional DiceRoller instance (creates new one if not provided)
        """
        self.dice_roller = dice_roller if dice_roller is not None else DiceRoller()

    @staticmethod
    def roll_ability_score(dice_roller: DiceRoller) -> tuple[int, list[int]]:
        """
        Roll 4d6, drop lowest, return score and dice rolled.

        Args:
            dice_roller: DiceRoller instance to use for rolling

        Returns:
            Tuple of (final_score, list_of_four_dice)

        Example:
            (15, [6, 5, 4, 2])
        """
        # Roll 4 dice
        dice = [dice_roller._roll_die(6) for _ in range(4)]

        # Drop lowest and sum the rest
        sorted_dice = sorted(dice, reverse=True)
        score = sum(sorted_dice[:3])

        return score, dice

    @staticmethod
    def roll_all_abilities(dice_roller: DiceRoller) -> list[tuple[int, list[int]]]:
        """
        Roll six ability scores.

        Args:
            dice_roller: DiceRoller instance to use for rolling

        Returns:
            List of 6 tuples (score, dice_rolls)
        """
        return [CharacterFactory.roll_ability_score(dice_roller) for _ in range(6)]

    @staticmethod
    def auto_assign_abilities(scores: list[int], class_data: dict[str, Any]) -> dict[str, int]:
        """
        Auto-assign scores to abilities based on class priorities.

        Args:
            scores: List of rolled scores (will be sorted high to low)
            class_data: Class definition from classes.json

        Returns:
            Dict mapping ability names to scores
            Example: {"strength": 15, "dexterity": 13, ...}
        """
        # Sort scores from highest to lowest
        sorted_scores = sorted(scores, reverse=True)

        # Get ability priorities from class data
        priorities = class_data.get(
            "ability_priorities",
            ["strength", "constitution", "dexterity", "wisdom", "intelligence", "charisma"],
        )

        # Assign scores to abilities based on priorities
        abilities = {}
        for i, ability in enumerate(priorities):
            abilities[ability] = sorted_scores[i]

        return abilities

    @staticmethod
    def swap_abilities(abilities: dict[str, int], ability1: str, ability2: str) -> dict[str, int]:
        """
        Swap two ability scores.

        Args:
            abilities: Current ability assignments
            ability1: First ability to swap (e.g., "strength")
            ability2: Second ability to swap (e.g., "dexterity")

        Returns:
            Updated abilities dict

        Raises:
            ValueError: If ability names are invalid
        """
        valid_abilities = [
            "strength",
            "dexterity",
            "constitution",
            "intelligence",
            "wisdom",
            "charisma",
        ]

        if ability1 not in valid_abilities:
            raise ValueError(f"Invalid ability name: {ability1}")
        if ability2 not in valid_abilities:
            raise ValueError(f"Invalid ability name: {ability2}")

        # Create a copy and swap
        new_abilities = abilities.copy()
        new_abilities[ability1], new_abilities[ability2] = abilities[ability2], abilities[ability1]

        return new_abilities

    @staticmethod
    def apply_racial_bonuses(
        abilities: dict[str, int], race_data: dict[str, Any]
    ) -> dict[str, int]:
        """
        Apply racial ability score bonuses.

        Args:
            abilities: Current ability scores
            race_data: Race definition with ability_bonuses

        Returns:
            Updated abilities with bonuses applied
        """
        bonuses = race_data.get("ability_bonuses", {})
        new_abilities = abilities.copy()

        for ability, bonus in bonuses.items():
            if ability in new_abilities:
                new_abilities[ability] += bonus

        return new_abilities

    @staticmethod
    def calculate_ability_modifier(score: int) -> int:
        """
        Calculate ability modifier from score.

        Args:
            score: Ability score (3-20)

        Returns:
            Modifier: (score - 10) // 2
        """
        return (score - 10) // 2

    @staticmethod
    def calculate_hp(class_data: dict[str, Any], con_modifier: int, level: int = 1) -> int:
        """
        Calculate starting HP.

        Args:
            class_data: Class definition with hit_die
            con_modifier: Constitution modifier
            level: Character level (default 1)

        Returns:
            Starting HP (max_hit_die + con_mod)
        """
        # Parse hit die (e.g., "1d10" -> 10)
        hit_die = class_data.get("hit_die", "1d8")
        max_hit_die = int(hit_die.split("d")[1])

        # At level 1, always take max hit die
        hp = max_hit_die + con_modifier

        return max(1, hp)  # Minimum 1 HP

    @staticmethod
    def calculate_ac(equipped_armor: dict[str, Any] | None, dex_modifier: int) -> int:
        """
        Calculate armor class.

        Args:
            equipped_armor: Armor item data or None
            dex_modifier: Dexterity modifier

        Returns:
            AC value

        Note:
            Heavy armor (like chain mail) doesn't add DEX
        """
        if equipped_armor is None:
            # No armor: 10 + DEX modifier
            return 10 + dex_modifier

        base_ac = equipped_armor.get("ac", 10)
        add_dex = equipped_armor.get("ac_bonus_dex", False)

        if add_dex:
            return base_ac + dex_modifier
        else:
            return base_ac

    @staticmethod
    def apply_starting_equipment(
        character: Character, class_data: dict[str, Any], items_data: dict[str, Any]
    ) -> None:
        """
        Add starting equipment to character inventory and equip.

        Automatically includes appropriate ammunition for ranged weapons
        that have the "ammunition" property.

        Args:
            character: Character object
            class_data: Class definition with starting_equipment
            items_data: Full items.json data

        Side Effects:
            - Adds items to character.inventory
            - Equips weapon and armor automatically
            - Adds ammunition for ranged weapons
        """
        starting_equipment = class_data.get("starting_equipment", [])
        weapons_needing_ammo: list[str] = []

        for item_id in starting_equipment:
            # Determine category
            category = None
            if item_id in items_data.get("weapons", {}):
                category = "weapons"
            elif item_id in items_data.get("armor", {}):
                category = "armor"
            elif item_id in items_data.get("consumables", {}):
                category = "consumables"
            elif item_id in items_data.get("tools", {}):
                category = "tools"
            elif item_id in items_data.get("ammunition", {}):
                category = "ammunition"

            if category:
                # Get default quantity for ammunition items
                quantity = 1
                if category == "ammunition":
                    ammo_data = items_data.get("ammunition", {}).get(item_id, {})
                    quantity = ammo_data.get("quantity", 20)

                character.inventory.add_item(item_id, category, quantity=quantity)

                # Auto-equip weapon and armor
                if category == "weapons":
                    if character.inventory.get_equipped_item(EquipmentSlot.WEAPON) is None:
                        character.inventory.equip_item(item_id, EquipmentSlot.WEAPON)
                    # Track weapons that need ammunition
                    weapon_data = items_data.get("weapons", {}).get(item_id, {})
                    if "ammunition" in weapon_data.get("properties", []):
                        weapons_needing_ammo.append(item_id)
                elif (
                    category == "armor"
                    and character.inventory.get_equipped_item(EquipmentSlot.ARMOR) is None
                ):
                    character.inventory.equip_item(item_id, EquipmentSlot.ARMOR)

        # Auto-add ammunition for weapons that require it
        CharacterFactory._add_starting_ammunition(character, weapons_needing_ammo, items_data)

        # Add starting gold
        starting_gold = class_data.get("starting_gold", 0)
        if starting_gold > 0:
            character.inventory.add_gold(starting_gold)

    @staticmethod
    def _add_starting_ammunition(
        character: Character, weapons_needing_ammo: list[str], items_data: dict[str, Any]
    ) -> None:
        """
        Add starting ammunition for ranged weapons.

        Searches the ammunition category for ammo compatible with each weapon
        and adds the default quantity if not already in inventory.

        Args:
            character: Character to add ammunition to
            weapons_needing_ammo: List of weapon IDs that require ammunition
            items_data: Full items.json data
        """
        ammo_data = items_data.get("ammunition", {})

        for weapon_id in weapons_needing_ammo:
            # Find compatible ammunition for this weapon
            for ammo_id, ammo_info in ammo_data.items():
                compatible_weapons = ammo_info.get("compatible_weapons", [])
                if weapon_id in compatible_weapons:
                    # Only add if character doesn't already have this ammo type
                    if not character.inventory.has_item(ammo_id):
                        quantity = ammo_info.get("quantity", 20)
                        character.inventory.add_item(ammo_id, "ammunition", quantity=quantity)
                    break  # Only need one type of compatible ammo per weapon

    @staticmethod
    def initialize_spellcasting(
        character: Character,
        class_data: dict[str, Any],
        spells_data: dict[str, Any],
    ) -> None:
        """
        Initialize spellcasting properties for spellcasting classes.

        Sets up spellcasting_ability, known_spells, and prepared_spells based on
        class spellcasting metadata. Auto-selects first N available spells.

        Args:
            character: Character object to initialize spellcasting for
            class_data: Class definition with optional spellcasting metadata
            spells_data: All spell definitions from spells.json

        Side Effects:
            - Sets character.spellcasting_ability
            - Populates character.known_spells with appropriate spell IDs
            - Populates character.prepared_spells (same as known_spells for wizards)
        """
        # Check if class has spellcasting
        spellcasting = class_data.get("spellcasting")
        if not spellcasting:
            return

        # Set spellcasting ability
        character.spellcasting_ability = spellcasting["ability"]

        # Get spells for this class and level
        class_name = class_data["name"].lower()
        available_spells = []

        # Find all spells this class can learn
        for spell_id, spell_data in spells_data.items():
            spell_classes = spell_data.get("classes", [])
            spell_level = spell_data.get("level", 0)

            # Check if spell is available to this class
            if class_name in spell_classes:
                # Wizards can learn all wizard spells up to their highest spell slot level
                # For level 1 wizard, that's 1st level spells and cantrips
                # For level 2, still 1st level and cantrips
                # For level 3, 2nd level, 1st level, and cantrips
                max_spell_level = (character.level + 1) // 2  # 1->1, 2->1, 3->2, etc.
                if spell_level <= max_spell_level:
                    available_spells.append((spell_id, spell_data, spell_level))

        # Separate cantrips from leveled spells
        cantrip_list = [(s[0], s[1]) for s in available_spells if s[2] == 0]
        leveled_spell_list = [(s[0], s[1]) for s in available_spells if s[2] > 0]

        # Determine how many cantrips and spells the character knows
        cantrips_known_count = spellcasting.get("cantrips_known", {}).get(str(character.level), 0)

        # For wizards, use spells_in_spellbook
        if spellcasting.get("spells_known_type") == "spellbook":
            spells_known_count = spellcasting.get("spells_in_spellbook", {}).get(
                str(character.level), 0
            )
        else:
            # For sorcerers/bards who know a limited number of spells
            spells_known_count = spellcasting.get("spells_known", {}).get(str(character.level), 0)

        # Auto-select first N spells
        cantrips = [s[0] for s in cantrip_list]
        leveled_spells = [s[0] for s in leveled_spell_list]
        character.known_spells = (
            cantrips[:cantrips_known_count] + leveled_spells[:spells_known_count]
        )
        # Cantrips are always prepared
        character.prepared_spells = (
            cantrips[:cantrips_known_count] + leveled_spells[:spells_known_count]
        )

    @staticmethod
    def initialize_class_resources(
        character: Character, class_data: dict[str, Any], level: int
    ) -> None:
        """
        Initialize resource pools from class features.

        Iterates through all class features up to the character's level and creates
        resource pools for any features that have a "resource" definition.

        Args:
            character: Character object to add resource pools to
            class_data: Class definition with features_by_level
            level: Character level (determines which features are available)

        Side Effects:
            - Adds ResourcePool instances to character.resource_pools
        """
        features_by_level = class_data.get("features_by_level", {})

        # Track resource pools we've already added to avoid duplicates
        added_pools = set()

        # Iterate through each level from 1 to character level
        for lvl in range(1, level + 1):
            features = features_by_level.get(str(lvl), [])

            for feature in features:
                if "resource" in feature:
                    resource_data = feature["resource"]
                    pool_name = resource_data["pool"]

                    # Check if pool already exists
                    existing_pool = character.get_resource_pool(pool_name)

                    if existing_pool is not None:
                        # Update existing pool with new maximum (for spell slot upgrades)
                        existing_pool.maximum = resource_data["max_uses"]
                        existing_pool.current = resource_data["max_uses"]
                    elif pool_name not in added_pools:
                        # Only add pool if we haven't already added it
                        # (e.g., multiple features might share the same pool)
                        pool = ResourcePool(
                            name=pool_name,
                            current=resource_data["max_uses"],
                            maximum=resource_data["max_uses"],
                            recovery_type=resource_data["recovery"],
                        )
                        character.add_resource_pool(pool)
                        added_pools.add(pool_name)

    def create_character(
        self,
        class_name: str,
        race_name: str,
        data_loader: DataLoader,
        level: int = 1,
        name: str | None = None,
        abilities: dict[str, int] | None = None,
        skill_proficiencies: list[str] | None = None,
        expertise_skills: list[str] | None = None,
    ) -> Character:
        """
        Create a character with all proficiencies and equipment - no UI dependencies.

        This is the core character creation method that should be used by all callers.
        It handles all the setup that was previously duplicated across debug_console,
        character_wizard, and migration code.

        Args:
            class_name: Character class (e.g., "fighter", "rogue", "wizard")
            race_name: Character race (e.g., "human", "elf", "dwarf")
            data_loader: DataLoader for accessing game data
            level: Starting level (default 1)
            name: Character name (generates random name if not provided)
            abilities: Pre-rolled abilities dict (rolls new if not provided)
            skill_proficiencies: Skill proficiencies (auto-selects if not provided)
            expertise_skills: Expertise skills (auto-selects for rogues if not provided)

        Returns:
            Fully initialized Character with all proficiencies, equipment, and resources
        """
        # Load required data
        races_data = data_loader.load_races()
        classes_data = data_loader.load_classes()
        items_data = data_loader.load_items()
        spells_data = data_loader.load_spells()

        # Validate class and race
        class_name = class_name.lower()
        race_name = race_name.lower()

        if class_name not in classes_data:
            raise ValueError(f"Invalid class: {class_name}. Available: {list(classes_data.keys())}")
        if race_name not in races_data:
            raise ValueError(f"Invalid race: {race_name}. Available: {list(races_data.keys())}")

        class_data = classes_data[class_name]
        race_data = races_data[race_name]

        # Generate name if not provided
        if name is None:
            name_prefixes = [
                "Brave",
                "Bold",
                "Mighty",
                "Swift",
                "Wise",
                "Dark",
                "Noble",
                "Silent",
            ]
            name_suffixes = [
                "blade",
                "heart",
                "shield",
                "storm",
                "wind",
                "fire",
                "shadow",
                "light",
            ]
            import random

            name = f"{random.choice(name_prefixes)}{random.choice(name_suffixes)}"

        # Roll abilities if not provided
        abilities_pre_provided = abilities is not None
        if abilities is None:
            all_rolls = self.roll_all_abilities(self.dice_roller)
            scores = [score for score, _ in all_rolls]
            abilities = self.auto_assign_abilities(scores, class_data)

        # Apply racial bonuses only if we rolled new abilities
        # (pre-provided abilities are assumed to already have bonuses applied)
        if not abilities_pre_provided:
            abilities = self.apply_racial_bonuses(abilities, race_data)

        # Create abilities object
        abilities_obj = Abilities(
            strength=abilities["strength"],
            dexterity=abilities["dexterity"],
            constitution=abilities["constitution"],
            intelligence=abilities["intelligence"],
            wisdom=abilities["wisdom"],
            charisma=abilities["charisma"],
        )

        # Calculate HP
        con_modifier = self.calculate_ability_modifier(abilities["constitution"])
        hp = self.calculate_hp(class_data, con_modifier, level=1)

        # Calculate AC based on starting armor
        starting_equipment = class_data.get("starting_equipment", [])
        armor_id = None
        for item_id in starting_equipment:
            if item_id in items_data.get("armor", {}):
                armor_id = item_id
                break

        armor_data = items_data["armor"].get(armor_id) if armor_id else None
        ac = self.calculate_ac(armor_data, abilities_obj.dex_mod)

        # Get speed from race data (default 30 ft if not specified)
        speed = race_data.get("speed", 30)

        # Auto-select skill proficiencies if not provided
        if skill_proficiencies is None:
            skill_profs = class_data.get("skill_proficiencies", {})
            num_skills = skill_profs.get("choose", 0)
            available_skills = skill_profs.get("from", [])
            skill_proficiencies = available_skills[:num_skills]

        # Auto-select expertise for rogues if not provided
        if expertise_skills is None and class_name == "rogue":
            expertise_skills = skill_proficiencies[:2] if skill_proficiencies else []
        elif expertise_skills is None:
            expertise_skills = []

        # Get all proficiencies from class data
        weapon_proficiencies = class_data.get("weapon_proficiencies", [])
        armor_proficiencies = class_data.get("armor_proficiencies", [])
        tool_proficiencies = class_data.get("tool_proficiencies", [])
        saving_throw_proficiencies = class_data.get("saving_throw_proficiencies", [])

        # Get character class enum
        character_class_enum = CharacterClass[class_name.upper()]

        # Create character
        character = Character(
            name=name,
            character_class=character_class_enum,
            level=1,  # Start at level 1, will level up below
            abilities=abilities_obj,
            max_hp=hp,
            ac=ac,
            xp=0,
            skill_proficiencies=skill_proficiencies,
            expertise_skills=expertise_skills,
            weapon_proficiencies=weapon_proficiencies,
            armor_proficiencies=armor_proficiencies,
            tool_proficiencies=tool_proficiencies,
            saving_throw_proficiencies=saving_throw_proficiencies,
            speed=speed,
        )

        # Store race and darkvision
        character.race = race_name
        character.darkvision_range = race_data.get("darkvision_range", 0)

        # Level up character to target level
        for _ in range(1, level):
            character.level += 1
            character._increase_hp(data_loader)

        # Initialize class resources and spellcasting
        self.initialize_class_resources(character, class_data, level)
        self.initialize_spellcasting(character, class_data, spells_data)

        # Apply starting equipment
        self.apply_starting_equipment(character, class_data, items_data)

        return character

