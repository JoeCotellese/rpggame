"""Integration tests for character creation flow"""

import pytest
from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.character import CharacterClass
from dnd_engine.core.dice import DiceRoller
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.inventory import EquipmentSlot


class TestCharacterCreationIntegration:
    """Integration tests for complete character creation"""

    def test_create_mountain_dwarf_fighter(self):
        """Test creating a Mountain Dwarf Fighter with full flow"""
        data_loader = DataLoader()
        factory = CharacterFactory(dice_roller=DiceRoller(seed=42))

        # Roll abilities
        all_rolls = factory.roll_all_abilities(factory.dice_roller)
        scores = [score for score, _ in all_rolls]

        # Load data
        classes_data = data_loader.load_classes()
        races_data = data_loader.load_races()
        items_data = data_loader.load_items()

        # Auto-assign abilities
        abilities = factory.auto_assign_abilities(scores, classes_data["fighter"])

        # Apply racial bonuses (Mountain Dwarf: +2 STR, +2 CON)
        abilities = factory.apply_racial_bonuses(abilities, races_data["mountain_dwarf"])

        # Calculate derived stats
        con_modifier = factory.calculate_ability_modifier(abilities["constitution"])
        hp = factory.calculate_hp(classes_data["fighter"], con_modifier)

        # Get armor for AC calculation
        armor_data = items_data["armor"]["chain_mail"]
        dex_modifier = factory.calculate_ability_modifier(abilities["dexterity"])
        ac = factory.calculate_ac(armor_data, dex_modifier)

        # Verify character is valid
        assert hp >= 1
        assert ac >= 10
        assert all(ability in abilities for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"])

    def test_create_human_fighter(self):
        """Test creating a Human Fighter"""
        data_loader = DataLoader()
        factory = CharacterFactory(dice_roller=DiceRoller(seed=100))

        # Roll abilities
        all_rolls = factory.roll_all_abilities(factory.dice_roller)
        scores = [score for score, _ in all_rolls]

        # Load data
        classes_data = data_loader.load_classes()
        races_data = data_loader.load_races()

        # Auto-assign abilities
        abilities = factory.auto_assign_abilities(scores, classes_data["fighter"])

        # Apply racial bonuses (Human: +1 all)
        abilities_before = abilities.copy()
        abilities = factory.apply_racial_bonuses(abilities, races_data["human"])

        # Verify all abilities increased by 1
        for ability in abilities:
            assert abilities[ability] == abilities_before[ability] + 1

    def test_create_high_elf_fighter(self):
        """Test creating a High Elf Fighter"""
        data_loader = DataLoader()
        factory = CharacterFactory(dice_roller=DiceRoller(seed=200))

        # Roll abilities
        all_rolls = factory.roll_all_abilities(factory.dice_roller)
        scores = [score for score, _ in all_rolls]

        # Load data
        classes_data = data_loader.load_classes()
        races_data = data_loader.load_races()

        # Auto-assign abilities
        abilities = factory.auto_assign_abilities(scores, classes_data["fighter"])

        # Apply racial bonuses (High Elf: +2 DEX, +1 INT)
        abilities_before = abilities.copy()
        abilities = factory.apply_racial_bonuses(abilities, races_data["high_elf"])

        # Verify bonuses applied correctly
        assert abilities["dexterity"] == abilities_before["dexterity"] + 2
        assert abilities["intelligence"] == abilities_before["intelligence"] + 1

    def test_create_halfling_fighter(self):
        """Test creating a Halfling Fighter"""
        data_loader = DataLoader()
        factory = CharacterFactory(dice_roller=DiceRoller(seed=300))

        # Roll abilities
        all_rolls = factory.roll_all_abilities(factory.dice_roller)
        scores = [score for score, _ in all_rolls]

        # Load data
        classes_data = data_loader.load_classes()
        races_data = data_loader.load_races()

        # Auto-assign abilities
        abilities = factory.auto_assign_abilities(scores, classes_data["fighter"])

        # Apply racial bonuses (Halfling: +2 DEX, +1 CHA)
        abilities_before = abilities.copy()
        abilities = factory.apply_racial_bonuses(abilities, races_data["halfling"])

        # Verify bonuses applied correctly
        assert abilities["dexterity"] == abilities_before["dexterity"] + 2
        assert abilities["charisma"] == abilities_before["charisma"] + 1

    def test_multiple_ability_swaps(self):
        """Test swapping abilities multiple times"""
        data_loader = DataLoader()
        factory = CharacterFactory(dice_roller=DiceRoller(seed=42))

        # Roll abilities
        all_rolls = factory.roll_all_abilities(factory.dice_roller)
        scores = [score for score, _ in all_rolls]

        # Load data
        classes_data = data_loader.load_classes()

        # Auto-assign abilities
        abilities = factory.auto_assign_abilities(scores, classes_data["fighter"])

        # Swap STR and DEX
        original_str = abilities["strength"]
        original_dex = abilities["dexterity"]

        abilities = factory.swap_abilities(abilities, "strength", "dexterity")
        assert abilities["strength"] == original_dex
        assert abilities["dexterity"] == original_str

        # Swap WIS and CHA
        original_wis = abilities["wisdom"]
        original_cha = abilities["charisma"]

        abilities = factory.swap_abilities(abilities, "wisdom", "charisma")
        assert abilities["wisdom"] == original_cha
        assert abilities["charisma"] == original_wis

    def test_character_stats_calculated_correctly(self):
        """Test that all character stats are calculated correctly"""
        data_loader = DataLoader()
        factory = CharacterFactory(dice_roller=DiceRoller(seed=42))

        # Roll abilities
        all_rolls = factory.roll_all_abilities(factory.dice_roller)
        scores = [score for score, _ in all_rolls]

        # Load data
        classes_data = data_loader.load_classes()
        races_data = data_loader.load_races()
        items_data = data_loader.load_items()

        # Auto-assign and apply bonuses
        abilities = factory.auto_assign_abilities(scores, classes_data["fighter"])
        abilities = factory.apply_racial_bonuses(abilities, races_data["mountain_dwarf"])

        # Calculate all stats
        con_modifier = factory.calculate_ability_modifier(abilities["constitution"])
        hp = factory.calculate_hp(classes_data["fighter"], con_modifier)

        armor_data = items_data["armor"]["chain_mail"]
        dex_modifier = factory.calculate_ability_modifier(abilities["dexterity"])
        ac = factory.calculate_ac(armor_data, dex_modifier)

        str_modifier = factory.calculate_ability_modifier(abilities["strength"])
        attack_bonus = 2 + str_modifier  # Proficiency + STR mod

        # Verify all stats are valid
        assert hp == 10 + con_modifier  # Max d10 + CON
        assert ac == 16  # Chain mail, no DEX bonus
        assert attack_bonus >= 2  # At least proficiency bonus

    def test_starting_equipment_complete(self):
        """Test that starting equipment is complete and valid"""
        data_loader = DataLoader()
        factory = CharacterFactory(dice_roller=DiceRoller(seed=42))

        # Create character
        from dnd_engine.core.creature import Abilities
        from dnd_engine.core.character import Character

        character = Character(
            name="Test Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(15, 14, 13, 10, 12, 8),
            max_hp=12,
            ac=16
        )

        # Apply starting equipment
        classes_data = data_loader.load_classes()
        items_data = data_loader.load_items()
        factory.apply_starting_equipment(character, classes_data["fighter"], items_data)

        # Verify weapon equipped
        weapon = character.inventory.get_equipped_item(EquipmentSlot.WEAPON)
        assert weapon == "longsword"

        # Verify armor equipped
        armor = character.inventory.get_equipped_item(EquipmentSlot.ARMOR)
        assert armor == "chain_mail"

        # Verify consumables in inventory
        assert character.inventory.get_item_quantity("potion_of_healing") == 5

        # Verify starting gold
        assert character.inventory.gold == 10

    def test_character_is_playable_after_creation(self):
        """Test that created character has all required attributes"""
        data_loader = DataLoader()
        factory = CharacterFactory(dice_roller=DiceRoller(seed=42))

        # Roll and assign abilities
        all_rolls = factory.roll_all_abilities(factory.dice_roller)
        scores = [score for score, _ in all_rolls]

        classes_data = data_loader.load_classes()
        races_data = data_loader.load_races()
        items_data = data_loader.load_items()

        abilities = factory.auto_assign_abilities(scores, classes_data["fighter"])
        abilities = factory.apply_racial_bonuses(abilities, races_data["human"])

        # Calculate stats
        from dnd_engine.core.creature import Abilities
        from dnd_engine.core.character import Character

        abilities_obj = Abilities(
            strength=abilities["strength"],
            dexterity=abilities["dexterity"],
            constitution=abilities["constitution"],
            intelligence=abilities["intelligence"],
            wisdom=abilities["wisdom"],
            charisma=abilities["charisma"]
        )

        con_modifier = factory.calculate_ability_modifier(abilities["constitution"])
        hp = factory.calculate_hp(classes_data["fighter"], con_modifier)

        armor_data = items_data["armor"]["chain_mail"]
        ac = factory.calculate_ac(armor_data, abilities_obj.dex_mod)

        # Create character
        character = Character(
            name="Test Hero",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities_obj,
            max_hp=hp,
            ac=ac,
            race="human"
        )

        # Apply equipment
        factory.apply_starting_equipment(character, classes_data["fighter"], items_data)

        # Verify character is playable
        assert character.name == "Test Hero"
        assert character.race == "human"
        assert character.character_class == CharacterClass.FIGHTER
        assert character.level == 1
        assert character.is_alive
        assert character.max_hp >= 1
        assert character.ac >= 10
        assert character.proficiency_bonus == 2
        assert character.melee_attack_bonus >= 2
        assert character.inventory is not None
        assert character.inventory.get_equipped_item(EquipmentSlot.WEAPON) is not None
        assert character.inventory.get_equipped_item(EquipmentSlot.ARMOR) is not None
