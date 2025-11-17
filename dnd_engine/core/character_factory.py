# ABOUTME: Character creation factory for D&D 5E character generation
# ABOUTME: Handles ability rolling, assignment, racial bonuses, and stat calculations

from typing import Dict, Any, List, Tuple, Optional
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.inventory import Inventory, EquipmentSlot


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
            9. Apply starting equipment
            10. Display character sheet
            11. Return Character
        """
        # Load data
        races_data = data_loader.load_races()
        classes_data = data_loader.load_classes()
        items_data = data_loader.load_items()

        # Step 1: Get character name
        print("\n" + "=" * 60)
        print("CHARACTER CREATION")
        print("=" * 60)
        name = input("\nWhat is your character's name? ").strip()
        while not name:
            print("Name cannot be empty.")
            name = input("What is your character's name? ").strip()

        # Step 2: Choose race
        print("\nChoose your race:")
        race_list = list(races_data.keys())
        for i, race_id in enumerate(race_list, 1):
            race = races_data[race_id]
            bonuses = ", ".join([f"+{v} {k.upper()[:3]}" for k, v in race["ability_bonuses"].items()])
            print(f"  {i}. {race['name']} ({bonuses})")

        race_choice = None
        while race_choice is None:
            try:
                choice = input("\nEnter number (1-{}): ".format(len(race_list))).strip()
                idx = int(choice) - 1
                if 0 <= idx < len(race_list):
                    race_choice = race_list[idx]
                else:
                    print(f"Please enter a number between 1 and {len(race_list)}.")
            except ValueError:
                print("Please enter a valid number.")

        race_data = races_data[race_choice]
        print(f"\nYou chose: {race_data['name']}")

        # Step 3: Choose class (MVP: Fighter only)
        print("\nChoose your class:")
        class_list = list(classes_data.keys())
        for i, class_id in enumerate(class_list, 1):
            cls = classes_data[class_id]
            print(f"  {i}. {cls['name']} ({cls['description']})")

        class_choice = class_list[0]  # For MVP, auto-select Fighter
        if len(class_list) == 1:
            print(f"\nClass: {classes_data[class_choice]['name']} (MVP: Fighter only)")
        else:
            # Future: Allow class selection
            class_choice_idx = None
            while class_choice_idx is None:
                try:
                    choice = input("\nEnter number (1-{}): ".format(len(class_list))).strip()
                    idx = int(choice) - 1
                    if 0 <= idx < len(class_list):
                        class_choice_idx = idx
                        class_choice = class_list[idx]
                    else:
                        print(f"Please enter a number between 1 and {len(class_list)}.")
                except ValueError:
                    print("Please enter a valid number.")

        class_data = classes_data[class_choice]

        # Step 4: Roll ability scores
        print("\n" + "-" * 60)
        print("Rolling ability scores...")
        print("-" * 60)

        all_rolls = self.roll_all_abilities(self.dice_roller)
        scores = []

        for i, (score, dice) in enumerate(all_rolls, 1):
            dropped = min(dice)
            print(f"Roll {i}: {sorted(dice, reverse=True)} = {score} (dropped {dropped})")
            scores.append(score)

        print(f"\nYour rolled scores: {sorted(scores, reverse=True)}")

        # Step 5: Auto-assign abilities
        print("\n" + "-" * 60)
        print(f"Auto-assigning scores based on {class_data['name']} class priorities...")
        print("-" * 60)

        abilities = self.auto_assign_abilities(scores, class_data)

        for ability, score in abilities.items():
            modifier = self.calculate_ability_modifier(score)
            sign = "+" if modifier >= 0 else ""
            print(f"{ability.upper()[:3]}: {score} ({sign}{modifier})")

        # Step 6: Allow ability swaps
        print("\n" + "-" * 60)
        print("You can now swap any two abilities if desired.")
        print("-" * 60)

        while True:
            swap = input("\nWould you like to swap any two abilities? (y/n): ").strip().lower()
            if swap not in ["y", "yes", "n", "no"]:
                print("Please enter 'y' or 'n'.")
                continue

            if swap in ["n", "no"]:
                break

            # Get abilities to swap
            ability1 = input("Enter first ability to swap (STR/DEX/CON/INT/WIS/CHA): ").strip().lower()
            ability2 = input("Enter second ability to swap (STR/DEX/CON/INT/WIS/CHA): ").strip().lower()

            # Map short forms to full names
            ability_map = {
                "str": "strength", "dex": "dexterity", "con": "constitution",
                "int": "intelligence", "wis": "wisdom", "cha": "charisma"
            }

            ability1_full = ability_map.get(ability1, ability1)
            ability2_full = ability_map.get(ability2, ability2)

            try:
                abilities = self.swap_abilities(abilities, ability1_full, ability2_full)
                print(f"\nSwapping {ability1_full.upper()} ({abilities[ability1_full]}) with {ability2_full.upper()} ({abilities[ability2_full]})...")
                print("\nUpdated abilities:")
                for ability, score in abilities.items():
                    modifier = self.calculate_ability_modifier(score)
                    sign = "+" if modifier >= 0 else ""
                    print(f"{ability.upper()[:3]}: {score} ({sign}{modifier})")
            except ValueError as e:
                print(f"Error: {e}")

        # Step 7: Apply racial bonuses
        print("\n" + "-" * 60)
        print(f"Applying {race_data['name']} racial bonuses...")
        print("-" * 60)

        abilities_before = abilities.copy()
        abilities = self.apply_racial_bonuses(abilities, race_data)

        for ability, final_score in abilities.items():
            original = abilities_before[ability]
            bonus = final_score - original
            if bonus > 0:
                modifier = self.calculate_ability_modifier(final_score)
                sign = "+" if modifier >= 0 else ""
                print(f"{ability.upper()[:3]}: {original} + {bonus} = {final_score} ({sign}{modifier})")
            else:
                modifier = self.calculate_ability_modifier(final_score)
                sign = "+" if modifier >= 0 else ""
                print(f"{ability.upper()[:3]}: {final_score} ({sign}{modifier})")

        # Step 8: Calculate derived stats
        print("\n" + "-" * 60)
        print("Calculating character stats...")
        print("-" * 60)

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

        print(f"Hit Points: {hp} ({class_data['hit_die']} max + {con_modifier} CON)")
        print(f"Armor Class: {ac}" + (f" ({armor_data['name']})" if armor_data else " (no armor)"))
        print(f"Attack Bonus: +{attack_bonus} (proficiency +{proficiency_bonus}, STR +{str_modifier})")
        print(f"Damage: {damage_dice}+{str_modifier}" + (f" {weapon_data['damage_type']} ({weapon_data['name']})" if weapon_data else ""))

        # Step 9: Create character and apply starting equipment
        character = Character(
            name=name,
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities_obj,
            max_hp=hp,
            ac=ac,
            xp=0
        )

        # Store race (will add field to Character class)
        character.race = race_choice

        print("\n" + "-" * 60)
        print("Adding starting equipment...")
        print("-" * 60)

        self.apply_starting_equipment(character, class_data, items_data)

        # Display equipped items
        print("\nEquipped:")
        weapon_equipped = character.inventory.get_equipped_item(EquipmentSlot.WEAPON)
        armor_equipped = character.inventory.get_equipped_item(EquipmentSlot.ARMOR)

        if weapon_equipped:
            weapon_info = items_data["weapons"][weapon_equipped]
            print(f"  Weapon: {weapon_info['name']} ({weapon_info['damage']} {weapon_info['damage_type']})")
        else:
            print("  Weapon: (none)")

        if armor_equipped:
            armor_info = items_data["armor"][armor_equipped]
            print(f"  Armor: {armor_info['name']} (AC {armor_info['ac']})")
        else:
            print("  Armor: (none)")

        # Display inventory
        print("\nInventory:")
        consumables = character.inventory.get_items_by_category("consumables")
        if consumables:
            for inv_item in consumables:
                item_info = items_data["consumables"][inv_item.item_id]
                qty_str = f" x{inv_item.quantity}" if inv_item.quantity > 1 else ""
                print(f"  {item_info['name']}{qty_str}")
        else:
            print("  (no items)")

        print(f"\nGold: {character.inventory.gold} gp")

        # Step 10: Display character sheet
        print("\n" + "=" * 60)
        print("CHARACTER SHEET")
        print("=" * 60)
        print(f"Name: {character.name}")
        print(f"Race: {race_data['name']}")
        print(f"Class: {class_data['name']} (Level 1)")
        print()
        print("ABILITIES:")
        for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            score = getattr(abilities_obj, ability)
            modifier = self.calculate_ability_modifier(score)
            sign = "+" if modifier >= 0 else ""
            print(f"  {ability.upper()[:3]}: {score} ({sign}{modifier})")
        print()
        print("COMBAT STATS:")
        print(f"  HP: {character.current_hp}/{character.max_hp}")
        print(f"  AC: {character.ac}")
        print(f"  Attack: +{attack_bonus} to hit, {damage_dice}+{str_modifier} damage")
        print(f"  Initiative: +{abilities_obj.dex_mod}")
        print()
        print("EQUIPMENT:")
        if weapon_equipped:
            print(f"  Weapon: {items_data['weapons'][weapon_equipped]['name']}")
        if armor_equipped:
            print(f"  Armor: {items_data['armor'][armor_equipped]['name']}")
        if consumables:
            items_str = ", ".join([f"{items_data['consumables'][item.item_id]['name']} x{item.quantity}" if item.quantity > 1 else items_data['consumables'][item.item_id]['name'] for item in consumables])
            print(f"  Items: {items_str}")
        print()
        print("=" * 60)

        input("\nPress Enter to begin your adventure...")

        return character
