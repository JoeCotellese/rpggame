# ABOUTME: Character creation factory for D&D 5E character generation
# ABOUTME: Handles ability rolling, assignment, racial bonuses, and stat calculations

from typing import Dict, Any, List, Tuple, Optional
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.inventory import Inventory, EquipmentSlot
from dnd_engine.systems.resources import ResourcePool
from dnd_engine.ui.rich_ui import (
    print_section,
    print_choice_menu,
    print_message,
    print_status_message,
    print_input_prompt,
    print_error,
    console
)


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

    def __init__(self, dice_roller: Optional[DiceRoller] = None):
        """
        Initialize the character factory.

        Args:
            dice_roller: Optional DiceRoller instance (creates new one if not provided)
        """
        self.dice_roller = dice_roller if dice_roller is not None else DiceRoller()

    @staticmethod
    def roll_ability_score(dice_roller: DiceRoller) -> Tuple[int, List[int]]:
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
    def roll_all_abilities(dice_roller: DiceRoller) -> List[Tuple[int, List[int]]]:
        """
        Roll six ability scores.

        Args:
            dice_roller: DiceRoller instance to use for rolling

        Returns:
            List of 6 tuples (score, dice_rolls)
        """
        return [CharacterFactory.roll_ability_score(dice_roller) for _ in range(6)]

    @staticmethod
    def auto_assign_abilities(
        scores: List[int],
        class_data: Dict[str, Any]
    ) -> Dict[str, int]:
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
        priorities = class_data.get("ability_priorities", [
            "strength", "constitution", "dexterity", "wisdom", "intelligence", "charisma"
        ])

        # Assign scores to abilities based on priorities
        abilities = {}
        for i, ability in enumerate(priorities):
            abilities[ability] = sorted_scores[i]

        return abilities

    @staticmethod
    def swap_abilities(
        abilities: Dict[str, int],
        ability1: str,
        ability2: str
    ) -> Dict[str, int]:
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
        valid_abilities = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]

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
        abilities: Dict[str, int],
        race_data: Dict[str, Any]
    ) -> Dict[str, int]:
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
    def calculate_hp(
        class_data: Dict[str, Any],
        con_modifier: int,
        level: int = 1
    ) -> int:
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
    def calculate_ac(
        equipped_armor: Optional[Dict[str, Any]],
        dex_modifier: int
    ) -> int:
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
    def select_skill_proficiencies(
        class_data: Dict[str, Any],
        skills_data: Dict[str, Any]
    ) -> List[str]:
        """
        Let player select skill proficiencies for their class.

        Args:
            class_data: Class definition with skill_proficiencies
            skills_data: Skills data from skills.json

        Returns:
            List of selected skill names (e.g., ["athletics", "perception"])

        Raises:
            ValueError: If class has no skill proficiencies defined
        """
        skill_profs = class_data.get("skill_proficiencies")
        if not skill_profs:
            return []

        # Get the number to choose and available skills
        num_to_choose = skill_profs.get("choose", 0)
        available_skills = skill_profs.get("from", [])

        if num_to_choose == 0 or not available_skills:
            return []

        # Display available skills with their abilities
        print_section(f"Choose {num_to_choose} Skill Proficiencies")

        options = []
        for i, skill_id in enumerate(available_skills, 1):
            skill_info = skills_data.get(skill_id, {})
            ability = skill_info.get("ability", "?").upper()
            skill_name = skill_info.get("name", skill_id.title())
            options.append({"number": str(i), "text": f"{skill_name} ({ability})"})

        print_choice_menu(f"Available Skills (Choose {num_to_choose})", options)

        selected = []
        while len(selected) < num_to_choose:
            remaining = num_to_choose - len(selected)
            prompt = f"Enter skill number (select {remaining} more)" if remaining > 1 else "Enter skill number"
            try:
                choice = print_input_prompt(prompt).strip()
                idx = int(choice) - 1
                if 0 <= idx < len(available_skills):
                    skill_id = available_skills[idx]
                    if skill_id not in selected:
                        selected.append(skill_id)
                        skill_name = skills_data[skill_id].get("name", skill_id.title())
                        print_status_message(f"Selected: {skill_name}", "success")
                    else:
                        print_status_message("You already selected that skill.", "warning")
                else:
                    print_status_message(f"Please enter a number between 1 and {len(available_skills)}.", "warning")
            except ValueError:
                print_status_message("Please enter a valid number.", "warning")

        return selected

    @staticmethod
    def select_expertise_skills(
        skill_proficiencies: List[str],
        skills_data: Dict[str, Any]
    ) -> List[str]:
        """
        Let Rogue player select expertise skills from their proficiencies.

        Rogues can choose 2 skills they are proficient in to have expertise in.
        With expertise, the proficiency bonus is doubled for those skills.

        Args:
            skill_proficiencies: List of skills the character is proficient in
            skills_data: Skills data from skills.json

        Returns:
            List of selected expertise skill names (should be 2 or fewer)
        """
        if not skill_proficiencies:
            return []

        num_expertise = min(2, len(skill_proficiencies))

        # Display available skills for expertise
        print_section(f"Choose {num_expertise} Skills for Expertise")
        print_message("With expertise, your proficiency bonus is doubled for these skills.\n")

        options = []
        for i, skill_id in enumerate(skill_proficiencies, 1):
            skill_info = skills_data.get(skill_id, {})
            ability = skill_info.get("ability", "?").upper()
            skill_name = skill_info.get("name", skill_id.title())
            options.append({"number": str(i), "text": f"{skill_name} ({ability})"})

        print_choice_menu(f"Available Skills for Expertise (Choose {num_expertise})", options)

        selected = []
        while len(selected) < num_expertise:
            remaining = num_expertise - len(selected)
            prompt = f"Enter skill number (select {remaining} more)" if remaining > 1 else "Enter skill number"
            try:
                choice = print_input_prompt(prompt).strip()
                idx = int(choice) - 1
                if 0 <= idx < len(skill_proficiencies):
                    skill_id = skill_proficiencies[idx]
                    if skill_id not in selected:
                        selected.append(skill_id)
                        skill_name = skills_data[skill_id].get("name", skill_id.title())
                        print_status_message(f"Selected expertise: {skill_name}", "success")
                    else:
                        print_status_message("You already selected that skill for expertise.", "warning")
                else:
                    print_status_message(f"Please enter a number between 1 and {len(skill_proficiencies)}.", "warning")
            except ValueError:
                print_status_message("Please enter a valid number.", "warning")

        return selected

    @staticmethod
    def apply_starting_equipment(
        character: Character,
        class_data: Dict[str, Any],
        items_data: Dict[str, Any]
    ) -> None:
        """
        Add starting equipment to character inventory and equip.

        Args:
            character: Character object
            class_data: Class definition with starting_equipment
            items_data: Full items.json data

        Side Effects:
            - Adds items to character.inventory
            - Equips weapon and armor automatically
        """
        starting_equipment = class_data.get("starting_equipment", [])

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

            if category:
                character.inventory.add_item(item_id, category, quantity=1)

                # Auto-equip weapon and armor
                if category == "weapons" and character.inventory.get_equipped_item(EquipmentSlot.WEAPON) is None:
                    character.inventory.equip_item(item_id, EquipmentSlot.WEAPON)
                elif category == "armor" and character.inventory.get_equipped_item(EquipmentSlot.ARMOR) is None:
                    character.inventory.equip_item(item_id, EquipmentSlot.ARMOR)

        # Add starting gold
        starting_gold = class_data.get("starting_gold", 0)
        if starting_gold > 0:
            character.inventory.add_gold(starting_gold)

    @staticmethod
    def initialize_class_resources(
        character: Character,
        class_data: Dict[str, Any],
        level: int
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

                    # Only add pool if we haven't already added it
                    # (e.g., multiple features might share the same pool)
                    if pool_name not in added_pools:
                        pool = ResourcePool(
                            name=pool_name,
                            current=resource_data["max_uses"],
                            maximum=resource_data["max_uses"],
                            recovery_type=resource_data["recovery"]
                        )
                        character.add_resource_pool(pool)
                        added_pools.add(pool_name)

    def create_character_interactive(
        self,
        ui,
        data_loader: DataLoader
    ) -> Character:
        """
        Full interactive character creation flow.

        Args:
            ui: UI instance for input/output
            data_loader: DataLoader for accessing races/classes/items

        Returns:
            Fully created Character object ready to play

        Flow:
            1. Get name
            2. Choose race
            3. Choose class
            4. Roll abilities (show results)
            5. Auto-assign (show assignments)
            6. Allow swaps
            7. Apply racial bonuses (show result)
            8. Calculate derived stats
            9. Select skill proficiencies
            10. Create character and apply starting equipment
            11. Display character sheet
            12. Return Character
        """
        # Load data
        races_data = data_loader.load_races()
        classes_data = data_loader.load_classes()
        items_data = data_loader.load_items()
        skills_data = data_loader.load_skills()

        # Step 1: Get character name
        print_section("CHARACTER CREATION", "Begin your adventure!")
        name = print_input_prompt("What is your character's name?").strip()
        while not name:
            print_status_message("Name cannot be empty.", "warning")
            name = print_input_prompt("What is your character's name?").strip()

        # Step 2: Choose race
        race_list = list(races_data.keys())
        options = []
        for i, race_id in enumerate(race_list, 1):
            race = races_data[race_id]
            bonuses = ", ".join([f"+{v} {k.upper()[:3]}" for k, v in race["ability_bonuses"].items()])
            options.append({"number": str(i), "text": f"{race['name']} ({bonuses})"})

        print_choice_menu("Choose Your Race", options)

        race_choice = None
        while race_choice is None:
            try:
                choice = print_input_prompt(f"Enter number (1-{len(race_list)})").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(race_list):
                    race_choice = race_list[idx]
                else:
                    print_status_message(f"Please enter a number between 1 and {len(race_list)}.", "warning")
            except ValueError:
                print_status_message("Please enter a valid number.", "warning")

        race_data = races_data[race_choice]
        print_status_message(f"You chose: {race_data['name']}", "success")

        # Step 3: Choose class (MVP: Fighter only)
        class_list = list(classes_data.keys())
        options = []
        for i, class_id in enumerate(class_list, 1):
            cls = classes_data[class_id]
            options.append({"number": str(i), "text": f"{cls['name']} ({cls['description']})"})

        print_choice_menu("Choose Your Class", options)

        class_choice = class_list[0]  # For MVP, auto-select Fighter
        if len(class_list) == 1:
            print_status_message(f"Class: {classes_data[class_choice]['name']} (MVP: Fighter only)", "info")
        else:
            # Future: Allow class selection
            class_choice_idx = None
            while class_choice_idx is None:
                try:
                    choice = print_input_prompt(f"Enter number (1-{len(class_list)})").strip()
                    idx = int(choice) - 1
                    if 0 <= idx < len(class_list):
                        class_choice_idx = idx
                        class_choice = class_list[idx]
                    else:
                        print_status_message(f"Please enter a number between 1 and {len(class_list)}.", "warning")
                except ValueError:
                    print_status_message("Please enter a valid number.", "warning")

        class_data = classes_data[class_choice]

        # Step 4: Roll ability scores
        print_section("Rolling Ability Scores")

        all_rolls = self.roll_all_abilities(self.dice_roller)
        scores = []
        roll_display = []

        for i, (score, dice) in enumerate(all_rolls, 1):
            dropped = min(dice)
            roll_display.append(f"Roll {i}: {sorted(dice, reverse=True)} = {score} (dropped {dropped})")
            scores.append(score)

        print_message("\n".join(roll_display))
        print_status_message(f"Your rolled scores: {sorted(scores, reverse=True)}", "info")

        # Step 5: Auto-assign abilities
        print_section(f"Assigning {class_data['name']} Class Priorities")

        abilities = self.auto_assign_abilities(scores, class_data)
        ability_display = []

        for ability, score in abilities.items():
            modifier = self.calculate_ability_modifier(score)
            sign = "+" if modifier >= 0 else ""
            ability_display.append(f"{ability.upper()[:3]}: {score} ({sign}{modifier})")

        print_message("\n".join(ability_display))

        # Step 6: Allow ability swaps
        print_section("Ability Swap (Optional)")

        while True:
            swap = print_input_prompt("Would you like to swap any two abilities? (y/n)").strip().lower()
            if swap not in ["y", "yes", "n", "no"]:
                print_status_message("Please enter 'y' or 'n'.", "warning")
                continue

            if swap in ["n", "no"]:
                break

            # Get abilities to swap
            ability1 = print_input_prompt("Enter first ability to swap (STR/DEX/CON/INT/WIS/CHA)").strip().lower()
            ability2 = print_input_prompt("Enter second ability to swap (STR/DEX/CON/INT/WIS/CHA)").strip().lower()

            # Map short forms to full names
            ability_map = {
                "str": "strength", "dex": "dexterity", "con": "constitution",
                "int": "intelligence", "wis": "wisdom", "cha": "charisma"
            }

            ability1_full = ability_map.get(ability1, ability1)
            ability2_full = ability_map.get(ability2, ability2)

            try:
                abilities = self.swap_abilities(abilities, ability1_full, ability2_full)
                print_status_message(f"Swapping {ability1_full.upper()} ({abilities[ability1_full]}) with {ability2_full.upper()} ({abilities[ability2_full]})", "success")
                ability_display = []
                for ability, score in abilities.items():
                    modifier = self.calculate_ability_modifier(score)
                    sign = "+" if modifier >= 0 else ""
                    ability_display.append(f"{ability.upper()[:3]}: {score} ({sign}{modifier})")
                print_message("\n".join(ability_display))
            except ValueError as e:
                print_error(str(e))

        # Step 7: Apply racial bonuses
        print_section(f"Applying {race_data['name']} Racial Bonuses")

        abilities_before = abilities.copy()
        abilities = self.apply_racial_bonuses(abilities, race_data)
        ability_display = []

        for ability, final_score in abilities.items():
            original = abilities_before[ability]
            bonus = final_score - original
            if bonus > 0:
                modifier = self.calculate_ability_modifier(final_score)
                sign = "+" if modifier >= 0 else ""
                ability_display.append(f"{ability.upper()[:3]}: {original} + {bonus} = {final_score} ({sign}{modifier})")
            else:
                modifier = self.calculate_ability_modifier(final_score)
                sign = "+" if modifier >= 0 else ""
                ability_display.append(f"{ability.upper()[:3]}: {final_score} ({sign}{modifier})")

        print_message("\n".join(ability_display))

        # Step 8: Calculate derived stats
        print_section("Calculating Character Stats")

        con_modifier = self.calculate_ability_modifier(abilities["constitution"])
        hp = self.calculate_hp(class_data, con_modifier)

        # Create abilities object
        abilities_obj = Abilities(
            strength=abilities["strength"],
            dexterity=abilities["dexterity"],
            constitution=abilities["constitution"],
            intelligence=abilities["intelligence"],
            wisdom=abilities["wisdom"],
            charisma=abilities["charisma"]
        )

        # Get starting equipment to calculate AC
        starting_equipment = class_data.get("starting_equipment", [])
        armor_id = None
        for item_id in starting_equipment:
            if item_id in items_data.get("armor", {}):
                armor_id = item_id
                break

        armor_data = items_data["armor"].get(armor_id) if armor_id else None
        ac = self.calculate_ac(armor_data, abilities_obj.dex_mod)

        str_modifier = abilities_obj.str_mod
        proficiency_bonus = 2  # Level 1
        attack_bonus = proficiency_bonus + str_modifier

        # Get weapon damage
        weapon_id = None
        for item_id in starting_equipment:
            if item_id in items_data.get("weapons", {}):
                weapon_id = item_id
                break

        weapon_data = items_data["weapons"].get(weapon_id) if weapon_id else None
        damage_dice = weapon_data.get("damage", "1d4") if weapon_data else "1d4"

        stats_display = [
            f"Hit Points: {hp} ({class_data['hit_die']} max + {con_modifier} CON)",
            f"Armor Class: {ac}" + (f" ({armor_data['name']})" if armor_data else " (no armor)"),
            f"Attack Bonus: +{attack_bonus} (proficiency +{proficiency_bonus}, STR +{str_modifier})",
            f"Damage: {damage_dice}+{str_modifier}" + (f" {weapon_data['damage_type']} ({weapon_data['name']})" if weapon_data else "")
        ]
        print_message("\n".join(stats_display))

        # Step 9: Select skill proficiencies
        print_section("Skill Proficiencies")
        skill_proficiencies = self.select_skill_proficiencies(class_data, skills_data)

        # Step 9b: Select expertise skills for Rogue
        expertise_skills = []
        if class_choice == "rogue":
            expertise_skills = self.select_expertise_skills(skill_proficiencies, skills_data)

        # Step 10: Create character and apply starting equipment
        # Get the CharacterClass enum value from the selected class_choice
        character_class_enum = CharacterClass[class_choice.upper()]

        # Get weapon and armor proficiencies from class data
        weapon_proficiencies = class_data.get("weapon_proficiencies", [])
        armor_proficiencies = class_data.get("armor_proficiencies", [])

        character = Character(
            name=name,
            character_class=character_class_enum,
            level=1,
            abilities=abilities_obj,
            max_hp=hp,
            ac=ac,
            xp=0,
            skill_proficiencies=skill_proficiencies,
            expertise_skills=expertise_skills,
            weapon_proficiencies=weapon_proficiencies,
            armor_proficiencies=armor_proficiencies
        )

        # Store race (will add field to Character class)
        character.race = race_choice

        # Initialize class resources (spell slots, ki points, etc.)
        self.initialize_class_resources(character, class_data, 1)

        print_section("Adding Starting Equipment")

        self.apply_starting_equipment(character, class_data, items_data)

        # Display equipped items and inventory
        weapon_equipped = character.inventory.get_equipped_item(EquipmentSlot.WEAPON)
        armor_equipped = character.inventory.get_equipped_item(EquipmentSlot.ARMOR)
        consumables = character.inventory.get_items_by_category("consumables")

        equipment_display = ["EQUIPPED:"]
        if weapon_equipped:
            weapon_info = items_data["weapons"][weapon_equipped]
            equipment_display.append(f"  Weapon: {weapon_info['name']} ({weapon_info['damage']} {weapon_info['damage_type']})")
        else:
            equipment_display.append("  Weapon: (none)")

        if armor_equipped:
            armor_info = items_data["armor"][armor_equipped]
            equipment_display.append(f"  Armor: {armor_info['name']} (AC {armor_info['ac']})")
        else:
            equipment_display.append("  Armor: (none)")

        equipment_display.append("\nINVENTORY:")
        if consumables:
            for inv_item in consumables:
                item_info = items_data["consumables"][inv_item.item_id]
                qty_str = f" x{inv_item.quantity}" if inv_item.quantity > 1 else ""
                equipment_display.append(f"  {item_info['name']}{qty_str}")
        else:
            equipment_display.append("  (no items)")

        equipment_display.append(f"\nGold: {character.inventory.gold} gp")
        print_message("\n".join(equipment_display))

        # Step 11: Display character sheet
        sheet_display = [
            f"Name: {character.name}",
            f"Race: {race_data['name']}",
            f"Class: {class_data['name']} (Level 1)",
            "",
            "ABILITIES:",
        ]

        for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            score = getattr(abilities_obj, ability)
            modifier = self.calculate_ability_modifier(score)
            sign = "+" if modifier >= 0 else ""
            sheet_display.append(f"  {ability.upper()[:3]}: {score} ({sign}{modifier})")

        # Add weapon and armor proficiencies to sheet
        if weapon_proficiencies or armor_proficiencies:
            sheet_display.append("")
            sheet_display.append("PROFICIENCIES:")
            if weapon_proficiencies:
                weapon_types = ", ".join([t.title() for t in weapon_proficiencies])
                sheet_display.append(f"  Weapons: {weapon_types}")
            if armor_proficiencies:
                armor_types = ", ".join([t.title() for t in armor_proficiencies])
                sheet_display.append(f"  Armor: {armor_types}")

        # Add skill proficiencies to sheet
        if skill_proficiencies:
            sheet_display.append("")
            sheet_display.append("SKILL PROFICIENCIES:")
            for skill_id in skill_proficiencies:
                skill_info = skills_data.get(skill_id, {})
                skill_name = skill_info.get("name", skill_id.title())
                sheet_display.append(f"  {skill_name}")

        sheet_display.extend([
            "",
            "COMBAT STATS:",
            f"  HP: {character.current_hp}/{character.max_hp}",
            f"  AC: {character.ac}",
            f"  Attack: +{attack_bonus} to hit, {damage_dice}+{str_modifier} damage",
            f"  Initiative: +{abilities_obj.dex_mod}",
            "",
            "EQUIPMENT:"
        ])

        if weapon_equipped:
            sheet_display.append(f"  Weapon: {items_data['weapons'][weapon_equipped]['name']}")
        if armor_equipped:
            sheet_display.append(f"  Armor: {items_data['armor'][armor_equipped]['name']}")
        if consumables:
            items_str = ", ".join([f"{items_data['consumables'][item.item_id]['name']} x{item.quantity}" if item.quantity > 1 else items_data['consumables'][item.item_id]['name'] for item in consumables])
            sheet_display.append(f"  Items: {items_str}")

        print_section("CHARACTER SHEET", "\n".join(sheet_display))

        print_input_prompt("Press Enter to begin your adventure")

        return character
