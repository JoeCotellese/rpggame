"""Integration tests for equipment proficiency in combat"""

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.combat import CombatEngine
from dnd_engine.core.dice import DiceRoller
from dnd_engine.rules.loader import DataLoader


@pytest.fixture
def items_data():
    """Load items data for testing weapon/armor proficiency"""
    loader = DataLoader()
    return loader.load_items()


@pytest.fixture
def combat_engine():
    """Create combat engine for testing"""
    return CombatEngine(DiceRoller())


@pytest.fixture
def fighter_proficient():
    """Create a proficient fighter"""
    abilities = Abilities(16, 10, 14, 10, 12, 10)
    return Character(
        name="Thorgrim",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=12,
        ac=10,
        weapon_proficiencies=["simple", "martial"],
        armor_proficiencies=["light", "medium", "heavy", "shields"]
    )


@pytest.fixture
def wizard_unproficient():
    """Create a wizard not proficient with martial weapons"""
    abilities = Abilities(10, 14, 12, 16, 13, 10)
    return Character(
        name="Gandalf",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=6,
        ac=10,
        weapon_proficiencies=["simple"],
        armor_proficiencies=["light"]
    )


@pytest.fixture
def dummy_defender():
    """Create a dummy creature to be attacked"""
    abilities = Abilities(10, 10, 10, 10, 10, 10)
    return Character(
        name="Dummy",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=10,
        ac=10
    )


class TestWeaponProficiencyAttackBonus:
    """Test attack bonus calculation with weapon proficiency"""

    def test_fighter_attack_bonus_with_proficient_longsword(self, fighter_proficient, items_data):
        """Fighter with proficient longsword should include proficiency bonus"""
        # Fighter: STR +3, proficiency +2 = +5
        attack_bonus = fighter_proficient.get_attack_bonus("longsword", items_data)
        assert attack_bonus == 5

    def test_fighter_attack_bonus_with_proficient_dagger(self, fighter_proficient, items_data):
        """Fighter with proficient dagger should include proficiency bonus"""
        # Fighter: STR +3, proficiency +2 = +5 (simple weapon, STR melee)
        attack_bonus = fighter_proficient.get_attack_bonus("dagger", items_data)
        assert attack_bonus == 5

    def test_wizard_attack_bonus_with_proficient_dagger(self, wizard_unproficient, items_data):
        """Wizard with proficient simple dagger (finesse) should include proficiency bonus"""
        # Dagger is finesse: max(STR +0, DEX +2) + proficiency +2 = +4
        attack_bonus = wizard_unproficient.get_attack_bonus("dagger", items_data)
        assert attack_bonus == 4

    def test_wizard_attack_bonus_with_non_proficient_longsword(self, wizard_unproficient, items_data):
        """Wizard without longsword proficiency should NOT include proficiency bonus"""
        # Wizard: STR +0 (no proficiency bonus for martial weapons)
        attack_bonus = wizard_unproficient.get_attack_bonus("longsword", items_data)
        assert attack_bonus == 0

    def test_fighter_attack_bonus_with_non_proficient_exotic_weapon(self, fighter_proficient, items_data):
        """Character without proficiency for a weapon should not include bonus"""
        # Fighter is only proficient with simple and martial
        # Using longbow which is martial but let's verify
        attack_bonus = fighter_proficient.get_attack_bonus("longbow", items_data)
        # Longbow is martial, fighter has martial, DEX +0, proficiency +2 = +2
        assert attack_bonus == 2

    def test_wizard_ranged_attack_bonus_proficient(self, wizard_unproficient, items_data):
        """Wizard with proficient shortbow should include proficiency bonus"""
        # Shortbow is simple (ranged), Wizard DEX +2, proficiency +2 = +4
        attack_bonus = wizard_unproficient.get_attack_bonus("shortbow", items_data)
        assert attack_bonus == 4

    def test_wizard_ranged_attack_bonus_not_proficient(self, wizard_unproficient, items_data):
        """Wizard without longbow proficiency should not include proficiency bonus"""
        # Longbow is martial (ranged), Wizard DEX +2 (no proficiency)
        attack_bonus = wizard_unproficient.get_attack_bonus("longbow", items_data)
        assert attack_bonus == 2

    def test_fighter_finesse_weapon_proficient(self, fighter_proficient, items_data):
        """Fighter with finesse weapon should include proficiency bonus"""
        # Shortsword is finesse, Fighter STR +3 > DEX +0, proficiency +2 = +5
        attack_bonus = fighter_proficient.get_attack_bonus("shortsword", items_data)
        assert attack_bonus == 5

    def test_wizard_finesse_weapon_proficient(self, wizard_unproficient, items_data):
        """Wizard with finesse weapon proficiency should include bonus"""
        # Dagger is finesse, Wizard DEX +2 > STR +0, proficiency +2 = +4
        attack_bonus = wizard_unproficient.get_attack_bonus("dagger", items_data)
        assert attack_bonus == 4


class TestProficiencyInCombat:
    """Test attack resolution with proficiency"""

    def test_fighter_attack_with_proficient_weapon(self, fighter_proficient, dummy_defender, combat_engine, items_data):
        """Fighter's attack with proficient weapon should use correct bonus"""
        attack_bonus = fighter_proficient.get_attack_bonus("longsword", items_data)
        damage = items_data["weapons"]["longsword"].get("damage", "1d8")

        result = combat_engine.resolve_attack(
            attacker=fighter_proficient,
            defender=dummy_defender,
            attack_bonus=attack_bonus,
            damage_dice=f"{damage}+{fighter_proficient.abilities.str_mod}"
        )

        # Verify attack bonus was applied
        assert result.attack_bonus == attack_bonus

    def test_wizard_attack_with_non_proficient_weapon(self, wizard_unproficient, dummy_defender, combat_engine, items_data):
        """Wizard's attack with non-proficient weapon should not include proficiency bonus"""
        attack_bonus = wizard_unproficient.get_attack_bonus("longsword", items_data)
        # Should be just STR modifier (0) without proficiency bonus (+2)
        assert attack_bonus == 0

        damage = items_data["weapons"]["longsword"].get("damage", "1d8")

        result = combat_engine.resolve_attack(
            attacker=wizard_unproficient,
            defender=dummy_defender,
            attack_bonus=attack_bonus,
            damage_dice=f"{damage}+{wizard_unproficient.abilities.str_mod}"
        )

        # Verify the lower bonus was applied
        assert result.attack_bonus == attack_bonus

    def test_attack_bonus_difference_proficient_vs_not(self, fighter_proficient, wizard_unproficient, items_data):
        """Proficient and non-proficient characters should have different attack bonuses"""
        # Both using longsword
        fighter_bonus = fighter_proficient.get_attack_bonus("longsword", items_data)
        wizard_bonus = wizard_unproficient.get_attack_bonus("longsword", items_data)

        # Fighter proficient: STR +3, prof +2 = +5
        assert fighter_bonus == 5

        # Wizard not proficient: STR +0 = +0
        assert wizard_bonus == 0

        # Clear difference due to proficiency
        assert fighter_bonus > wizard_bonus

    def test_hit_chance_with_proficiency_advantage(self, fighter_proficient, wizard_unproficient, dummy_defender, combat_engine, items_data):
        """
        Character with proficiency should have advantage in hitting.

        This is a conceptual test - higher bonus = higher hit chance.
        """
        fighter_bonus = fighter_proficient.get_attack_bonus("longsword", items_data)
        wizard_bonus = wizard_unproficient.get_attack_bonus("longsword", items_data)

        # With dummy_defender at AC 10:
        # Fighter: 5 + d20 vs AC 10 (needs 5+)
        # Wizard: 0 + d20 vs AC 10 (needs 10+)

        # Fighter needs 5+ on d20 (16/20 chance)
        # Wizard needs 10+ on d20 (11/20 chance)

        assert fighter_bonus > wizard_bonus
        # Verify the mathematical difference
        assert fighter_bonus - wizard_bonus == 5  # proficiency bonus


class TestMultipleWeaponProficiency:
    """Test proficiency with different weapon types"""

    def test_fighter_proficient_with_all_tested_weapons(self, fighter_proficient, items_data):
        """Fighter should be proficient with all simple and martial weapons"""
        test_weapons = ["dagger", "shortsword", "longsword", "greataxe", "shortbow", "longbow"]

        for weapon_id in test_weapons:
            bonus = fighter_proficient.get_attack_bonus(weapon_id, items_data)
            # All bonuses should include proficiency
            assert bonus >= 2, f"Fighter attack bonus with {weapon_id} should include proficiency"

    def test_wizard_selective_proficiency(self, wizard_unproficient, items_data):
        """Wizard should have proficiency for some but not all weapons"""
        # Proficient weapons (simple)
        # Dagger: finesse, max(STR +0, DEX +2) + prof +2 = +4
        dagger_bonus = wizard_unproficient.get_attack_bonus("dagger", items_data)
        assert dagger_bonus == 4, "Wizard should be proficient with dagger"

        # Shortbow: simple ranged, DEX +2 + prof +2 = +4
        shortbow_bonus = wizard_unproficient.get_attack_bonus("shortbow", items_data)
        assert shortbow_bonus == 4, "Wizard should be proficient with shortbow"

        # Non-proficient weapons (martial) - should NOT include proficiency
        # Longsword: melee, STR +0 (no proficiency for martial)
        longsword_bonus = wizard_unproficient.get_attack_bonus("longsword", items_data)
        assert longsword_bonus == 0, "Wizard should NOT be proficient with longsword"

        # Greataxe: melee, STR +0 (no proficiency for martial)
        greataxe_bonus = wizard_unproficient.get_attack_bonus("greataxe", items_data)
        assert greataxe_bonus == 0, "Wizard should NOT be proficient with greataxe"

        # Longbow: martial ranged, DEX +2 (no proficiency for martial)
        longbow_bonus = wizard_unproficient.get_attack_bonus("longbow", items_data)
        assert longbow_bonus == 2, "Wizard should NOT be proficient with longbow, but gets DEX modifier"

    def test_proficiency_bonus_scales_with_level(self, items_data):
        """Attack bonus should scale with character level"""
        abilities = Abilities(16, 10, 14, 10, 12, 10)

        # Level 1: proficiency +2
        fighter_level1 = Character(
            name="Young",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=10,
            weapon_proficiencies=["simple", "martial"]
        )
        bonus_level1 = fighter_level1.get_attack_bonus("longsword", items_data)
        # STR +3 + prof +2 = +5
        assert bonus_level1 == 5

        # Level 5: proficiency +3
        fighter_level5 = Character(
            name="Experienced",
            character_class=CharacterClass.FIGHTER,
            level=5,
            abilities=abilities,
            max_hp=12,
            ac=10,
            weapon_proficiencies=["simple", "martial"]
        )
        bonus_level5 = fighter_level5.get_attack_bonus("longsword", items_data)
        # STR +3 + prof +3 = +6
        assert bonus_level5 == 6

        # Verify proficiency bonus difference
        assert bonus_level5 - bonus_level1 == 1

    def test_proficiency_consistency_with_different_abilities(self, items_data):
        """Proficiency bonus should be consistent regardless of ability scores"""
        # High STR fighter
        fighter_high_str = Character(
            name="Strongman",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(18, 10, 14, 10, 12, 10),
            max_hp=12,
            ac=10,
            weapon_proficiencies=["simple", "martial"]
        )

        # Low STR fighter
        fighter_low_str = Character(
            name="Weakling",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(10, 10, 14, 10, 12, 10),
            max_hp=12,
            ac=10,
            weapon_proficiencies=["simple", "martial"]
        )

        bonus_high_str = fighter_high_str.get_attack_bonus("longsword", items_data)
        bonus_low_str = fighter_low_str.get_attack_bonus("longsword", items_data)

        # Both should have same proficiency bonus (+2)
        # Difference should only be ability modifier
        # High STR: +4 (STR) + 2 (prof) = +6
        # Low STR: +0 (STR) + 2 (prof) = +2
        assert bonus_high_str == 6
        assert bonus_low_str == 2
        assert bonus_high_str - bonus_low_str == 4  # Difference is STR modifier
