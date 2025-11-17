"""Unit tests for CharacterFactory class"""

import pytest
from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.dice import DiceRoller
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.inventory import EquipmentSlot


class TestRollAbilityScore:
    """Test rolling a single ability score (4d6 drop lowest)"""

    def test_roll_returns_score_and_four_dice(self):
        """Verify roll returns a score and exactly 4 dice"""
        dice_roller = DiceRoller(seed=42)
        score, dice = CharacterFactory.roll_ability_score(dice_roller)

        assert isinstance(score, int)
        assert isinstance(dice, list)
        assert len(dice) == 4

    def test_all_dice_are_valid(self):
        """Verify all dice are between 1-6"""
        dice_roller = DiceRoller(seed=42)
        score, dice = CharacterFactory.roll_ability_score(dice_roller)

        for die in dice:
            assert 1 <= die <= 6

    def test_lowest_die_is_dropped(self):
        """Verify score equals sum of top 3 dice"""
        dice_roller = DiceRoller(seed=42)
        score, dice = CharacterFactory.roll_ability_score(dice_roller)

        sorted_dice = sorted(dice, reverse=True)
        expected_score = sum(sorted_dice[:3])

        assert score == expected_score

    def test_score_range(self):
        """Verify score is in valid range (3-18)"""
        dice_roller = DiceRoller(seed=42)
        for _ in range(100):
            score, dice = CharacterFactory.roll_ability_score(dice_roller)
            assert 3 <= score <= 18


class TestRollAllAbilities:
    """Test rolling all six ability scores"""

    def test_returns_six_rolls(self):
        """Verify exactly 6 scores are returned"""
        dice_roller = DiceRoller(seed=42)
        rolls = CharacterFactory.roll_all_abilities(dice_roller)

        assert len(rolls) == 6

    def test_each_roll_has_score_and_dice(self):
        """Verify each roll has a score and 4 dice"""
        dice_roller = DiceRoller(seed=42)
        rolls = CharacterFactory.roll_all_abilities(dice_roller)

        for score, dice in rolls:
            assert isinstance(score, int)
            assert isinstance(dice, list)
            assert len(dice) == 4


class TestAutoAssignAbilities:
    """Test auto-assigning scores based on class priorities"""

    def test_fighter_gets_highest_in_strength(self):
        """Verify Fighter gets highest score in STR"""
        scores = [15, 14, 13, 12, 11, 10]
        class_data = {
            "ability_priorities": ["strength", "constitution", "dexterity", "wisdom", "intelligence", "charisma"]
        }

        abilities = CharacterFactory.auto_assign_abilities(scores, class_data)

        assert abilities["strength"] == 15

    def test_scores_assigned_in_priority_order(self):
        """Verify scores are assigned in descending order of priority"""
        scores = [18, 16, 14, 12, 10, 8]
        class_data = {
            "ability_priorities": ["strength", "constitution", "dexterity", "wisdom", "intelligence", "charisma"]
        }

        abilities = CharacterFactory.auto_assign_abilities(scores, class_data)

        assert abilities["strength"] == 18
        assert abilities["constitution"] == 16
        assert abilities["dexterity"] == 14
        assert abilities["wisdom"] == 12
        assert abilities["intelligence"] == 10
        assert abilities["charisma"] == 8

    def test_all_abilities_assigned(self):
        """Verify all six abilities are assigned"""
        scores = [15, 14, 13, 12, 11, 10]
        class_data = {
            "ability_priorities": ["strength", "constitution", "dexterity", "wisdom", "intelligence", "charisma"]
        }

        abilities = CharacterFactory.auto_assign_abilities(scores, class_data)

        expected_abilities = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
        for ability in expected_abilities:
            assert ability in abilities

    def test_handles_unsorted_scores(self):
        """Verify function sorts scores before assignment"""
        scores = [10, 15, 12, 14, 8, 13]  # Unsorted
        class_data = {
            "ability_priorities": ["strength", "constitution", "dexterity", "wisdom", "intelligence", "charisma"]
        }

        abilities = CharacterFactory.auto_assign_abilities(scores, class_data)

        # Should assign highest to first priority
        assert abilities["strength"] == 15


class TestSwapAbilities:
    """Test swapping two ability scores"""

    def test_values_are_swapped(self):
        """Verify two ability values are correctly swapped"""
        abilities = {
            "strength": 15,
            "dexterity": 13,
            "constitution": 14,
            "intelligence": 10,
            "wisdom": 12,
            "charisma": 8
        }

        new_abilities = CharacterFactory.swap_abilities(abilities, "strength", "dexterity")

        assert new_abilities["strength"] == 13
        assert new_abilities["dexterity"] == 15

    def test_other_abilities_unchanged(self):
        """Verify other abilities remain unchanged"""
        abilities = {
            "strength": 15,
            "dexterity": 13,
            "constitution": 14,
            "intelligence": 10,
            "wisdom": 12,
            "charisma": 8
        }

        new_abilities = CharacterFactory.swap_abilities(abilities, "strength", "dexterity")

        assert new_abilities["constitution"] == 14
        assert new_abilities["intelligence"] == 10
        assert new_abilities["wisdom"] == 12
        assert new_abilities["charisma"] == 8

    def test_invalid_ability_raises_error(self):
        """Verify invalid ability name raises ValueError"""
        abilities = {
            "strength": 15,
            "dexterity": 13,
            "constitution": 14,
            "intelligence": 10,
            "wisdom": 12,
            "charisma": 8
        }

        with pytest.raises(ValueError, match="Invalid ability name"):
            CharacterFactory.swap_abilities(abilities, "invalid", "dexterity")

        with pytest.raises(ValueError, match="Invalid ability name"):
            CharacterFactory.swap_abilities(abilities, "strength", "invalid")


class TestApplyRacialBonuses:
    """Test applying racial ability score bonuses"""

    def test_mountain_dwarf_bonuses(self):
        """Verify Mountain Dwarf applies +2 STR, +2 CON"""
        abilities = {
            "strength": 13,
            "dexterity": 12,
            "constitution": 13,
            "intelligence": 10,
            "wisdom": 11,
            "charisma": 8
        }

        race_data = {
            "ability_bonuses": {
                "strength": 2,
                "constitution": 2
            }
        }

        new_abilities = CharacterFactory.apply_racial_bonuses(abilities, race_data)

        assert new_abilities["strength"] == 15
        assert new_abilities["constitution"] == 15
        assert new_abilities["dexterity"] == 12  # Unchanged

    def test_human_bonuses(self):
        """Verify Human applies +1 to all abilities"""
        abilities = {
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10
        }

        race_data = {
            "ability_bonuses": {
                "strength": 1,
                "dexterity": 1,
                "constitution": 1,
                "intelligence": 1,
                "wisdom": 1,
                "charisma": 1
            }
        }

        new_abilities = CharacterFactory.apply_racial_bonuses(abilities, race_data)

        for ability in abilities:
            assert new_abilities[ability] == 11

    def test_original_values_preserved(self):
        """Verify original dict is not modified"""
        abilities = {
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10
        }

        race_data = {
            "ability_bonuses": {
                "strength": 2
            }
        }

        new_abilities = CharacterFactory.apply_racial_bonuses(abilities, race_data)

        # Original should be unchanged
        assert abilities["strength"] == 10
        # New should have bonus
        assert new_abilities["strength"] == 12


class TestCalculateAbilityModifier:
    """Test ability modifier calculation"""

    def test_score_10_11_gives_zero(self):
        """Verify scores 10-11 give +0 modifier"""
        assert CharacterFactory.calculate_ability_modifier(10) == 0
        assert CharacterFactory.calculate_ability_modifier(11) == 0

    def test_score_12_13_gives_plus_one(self):
        """Verify scores 12-13 give +1 modifier"""
        assert CharacterFactory.calculate_ability_modifier(12) == 1
        assert CharacterFactory.calculate_ability_modifier(13) == 1

    def test_score_14_15_gives_plus_two(self):
        """Verify scores 14-15 give +2 modifier"""
        assert CharacterFactory.calculate_ability_modifier(14) == 2
        assert CharacterFactory.calculate_ability_modifier(15) == 2

    def test_score_8_9_gives_minus_one(self):
        """Verify scores 8-9 give -1 modifier"""
        assert CharacterFactory.calculate_ability_modifier(8) == -1
        assert CharacterFactory.calculate_ability_modifier(9) == -1

    def test_score_20_gives_plus_five(self):
        """Verify score 20 gives +5 modifier"""
        assert CharacterFactory.calculate_ability_modifier(20) == 5

    def test_score_3_gives_minus_four(self):
        """Verify score 3 gives -4 modifier"""
        assert CharacterFactory.calculate_ability_modifier(3) == -4


class TestCalculateHP:
    """Test HP calculation"""

    def test_fighter_with_con_plus_two(self):
        """Verify Fighter (d10) with CON +2 = 12 HP"""
        class_data = {"hit_die": "1d10"}
        con_modifier = 2

        hp = CharacterFactory.calculate_hp(class_data, con_modifier)

        assert hp == 12  # 10 (max d10) + 2 (CON)

    def test_con_modifier_applied(self):
        """Verify CON modifier is correctly applied"""
        class_data = {"hit_die": "1d8"}
        con_modifier = 3

        hp = CharacterFactory.calculate_hp(class_data, con_modifier)

        assert hp == 11  # 8 (max d8) + 3 (CON)

    def test_negative_con_modifier(self):
        """Verify negative CON modifier works (minimum 1 HP)"""
        class_data = {"hit_die": "1d6"}
        con_modifier = -10  # Should result in minimum 1 HP

        hp = CharacterFactory.calculate_hp(class_data, con_modifier)

        assert hp == 1  # Minimum HP


class TestCalculateAC:
    """Test AC calculation"""

    def test_chain_mail_ignores_dex(self):
        """Verify heavy armor (chain mail) doesn't add DEX"""
        armor = {"ac": 16, "ac_bonus_dex": False}
        dex_modifier = 3

        ac = CharacterFactory.calculate_ac(armor, dex_modifier)

        assert ac == 16  # No DEX bonus

    def test_leather_armor_adds_dex(self):
        """Verify light armor (leather) adds DEX modifier"""
        armor = {"ac": 11, "ac_bonus_dex": True}
        dex_modifier = 3

        ac = CharacterFactory.calculate_ac(armor, dex_modifier)

        assert ac == 14  # 11 + 3

    def test_no_armor_uses_10_plus_dex(self):
        """Verify no armor = 10 + DEX"""
        dex_modifier = 2

        ac = CharacterFactory.calculate_ac(None, dex_modifier)

        assert ac == 12  # 10 + 2


class TestApplyStartingEquipment:
    """Test applying starting equipment"""

    def test_all_items_added_to_inventory(self):
        """Verify all starting equipment is added"""
        data_loader = DataLoader()
        items_data = data_loader.load_items()
        classes_data = data_loader.load_classes()

        from dnd_engine.core.creature import Abilities
        character = Character(
            name="Test",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(10, 10, 10, 10, 10, 10),
            max_hp=10,
            ac=10
        )

        CharacterFactory.apply_starting_equipment(character, classes_data["fighter"], items_data)

        # Should have longsword, chain_mail, and 5 potions
        assert character.inventory.has_item("longsword")
        assert character.inventory.has_item("chain_mail")
        assert character.inventory.get_item_quantity("potion_of_healing") == 5

    def test_weapon_and_armor_auto_equipped(self):
        """Verify weapon and armor are auto-equipped"""
        data_loader = DataLoader()
        items_data = data_loader.load_items()
        classes_data = data_loader.load_classes()

        from dnd_engine.core.creature import Abilities
        character = Character(
            name="Test",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(10, 10, 10, 10, 10, 10),
            max_hp=10,
            ac=10
        )

        CharacterFactory.apply_starting_equipment(character, classes_data["fighter"], items_data)

        assert character.inventory.get_equipped_item(EquipmentSlot.WEAPON) == "longsword"
        assert character.inventory.get_equipped_item(EquipmentSlot.ARMOR) == "chain_mail"

    def test_starting_gold_added(self):
        """Verify starting gold is added"""
        data_loader = DataLoader()
        items_data = data_loader.load_items()
        classes_data = data_loader.load_classes()

        from dnd_engine.core.creature import Abilities
        character = Character(
            name="Test",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(10, 10, 10, 10, 10, 10),
            max_hp=10,
            ac=10
        )

        CharacterFactory.apply_starting_equipment(character, classes_data["fighter"], items_data)

        assert character.inventory.gold == 10
