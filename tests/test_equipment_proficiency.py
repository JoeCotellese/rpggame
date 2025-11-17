"""Unit tests for equipment proficiency system"""

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.rules.loader import DataLoader


@pytest.fixture
def items_data():
    """Load items data for testing weapon/armor proficiency"""
    loader = DataLoader()
    return loader.load_items()


@pytest.fixture
def fighter_proficient():
    """Create a fighter character (proficient with simple and martial weapons and heavy armor)"""
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
    """Create a wizard character (not proficient with martial weapons or heavy armor)"""
    abilities = Abilities(10, 14, 12, 16, 13, 10)
    return Character(
        name="Gandalf",
        character_class=CharacterClass.FIGHTER,  # Using FIGHTER as only available class
        level=1,
        abilities=abilities,
        max_hp=6,
        ac=10,
        weapon_proficiencies=["simple"],
        armor_proficiencies=["light"]
    )


@pytest.fixture
def rogue_partial_proficiency():
    """Create a rogue-like character (proficient with simple and martial, but not heavy armor)"""
    abilities = Abilities(10, 16, 12, 14, 13, 10)
    return Character(
        name="Shadowstrike",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=8,
        ac=10,
        weapon_proficiencies=["simple", "martial"],
        armor_proficiencies=["light", "medium"]
    )


class TestWeaponProficiency:
    """Test weapon proficiency checking"""

    def test_fighter_proficient_with_longsword(self, fighter_proficient, items_data):
        """Fighter should be proficient with longsword (martial weapon)"""
        assert fighter_proficient.is_proficient_with_weapon("longsword", items_data) is True

    def test_fighter_proficient_with_dagger(self, fighter_proficient, items_data):
        """Fighter should be proficient with dagger (simple weapon)"""
        assert fighter_proficient.is_proficient_with_weapon("dagger", items_data) is True

    def test_fighter_proficient_with_greataxe(self, fighter_proficient, items_data):
        """Fighter should be proficient with greataxe (martial weapon)"""
        assert fighter_proficient.is_proficient_with_weapon("greataxe", items_data) is True

    def test_wizard_proficient_with_dagger(self, wizard_unproficient, items_data):
        """Wizard should be proficient with dagger (simple weapon)"""
        assert wizard_unproficient.is_proficient_with_weapon("dagger", items_data) is True

    def test_wizard_not_proficient_with_longsword(self, wizard_unproficient, items_data):
        """Wizard should NOT be proficient with longsword (martial weapon)"""
        assert wizard_unproficient.is_proficient_with_weapon("longsword", items_data) is False

    def test_wizard_not_proficient_with_greataxe(self, wizard_unproficient, items_data):
        """Wizard should NOT be proficient with greataxe (martial weapon)"""
        assert wizard_unproficient.is_proficient_with_weapon("greataxe", items_data) is False

    def test_weapon_proficiency_with_shortsword(self, fighter_proficient, items_data):
        """Fighter should be proficient with shortsword (martial weapon)"""
        assert fighter_proficient.is_proficient_with_weapon("shortsword", items_data) is True

    def test_weapon_proficiency_with_ranged_simple(self, wizard_unproficient, items_data):
        """Wizard should be proficient with shortbow (simple ranged weapon)"""
        assert wizard_unproficient.is_proficient_with_weapon("shortbow", items_data) is True

    def test_weapon_proficiency_with_ranged_martial(self, wizard_unproficient, items_data):
        """Wizard should NOT be proficient with longbow (martial ranged weapon)"""
        assert wizard_unproficient.is_proficient_with_weapon("longbow", items_data) is False

    def test_weapon_not_found_raises_error(self, fighter_proficient, items_data):
        """Should raise KeyError if weapon doesn't exist"""
        with pytest.raises(KeyError):
            fighter_proficient.is_proficient_with_weapon("nonexistent_weapon", items_data)

    def test_character_with_no_weapon_proficiencies(self, items_data):
        """Character with empty weapon_proficiencies list should not be proficient"""
        abilities = Abilities(10, 10, 10, 10, 10, 10)
        character = Character(
            name="Helpless",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=10,
            weapon_proficiencies=[]
        )
        assert character.is_proficient_with_weapon("longsword", items_data) is False

    def test_character_default_no_weapon_proficiencies(self, items_data):
        """Character created without specifying proficiencies should have empty list"""
        abilities = Abilities(10, 10, 10, 10, 10, 10)
        character = Character(
            name="Untrained",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=10
        )
        assert character.weapon_proficiencies == []
        assert character.is_proficient_with_weapon("longsword", items_data) is False


class TestArmorProficiency:
    """Test armor proficiency checking"""

    def test_fighter_proficient_with_chain_mail(self, fighter_proficient, items_data):
        """Fighter should be proficient with chain mail (heavy armor)"""
        assert fighter_proficient.is_proficient_with_armor("chain_mail", items_data) is True

    def test_fighter_proficient_with_leather_armor(self, fighter_proficient, items_data):
        """Fighter should be proficient with leather armor (light armor)"""
        assert fighter_proficient.is_proficient_with_armor("leather_armor", items_data) is True

    def test_wizard_proficient_with_leather_armor(self, wizard_unproficient, items_data):
        """Wizard should be proficient with leather armor (light armor)"""
        assert wizard_unproficient.is_proficient_with_armor("leather_armor", items_data) is True

    def test_wizard_not_proficient_with_chain_mail(self, wizard_unproficient, items_data):
        """Wizard should NOT be proficient with chain mail (heavy armor)"""
        assert wizard_unproficient.is_proficient_with_armor("chain_mail", items_data) is False

    def test_rogue_proficient_with_leather_armor(self, rogue_partial_proficiency, items_data):
        """Rogue should be proficient with leather armor (light armor)"""
        assert rogue_partial_proficiency.is_proficient_with_armor("leather_armor", items_data) is True

    def test_rogue_not_proficient_with_chain_mail(self, rogue_partial_proficiency, items_data):
        """Rogue should NOT be proficient with chain mail (heavy armor)"""
        assert rogue_partial_proficiency.is_proficient_with_armor("chain_mail", items_data) is False

    def test_rogue_proficient_with_scale_mail(self, rogue_partial_proficiency, items_data):
        """Rogue should be proficient with scale mail (medium armor)"""
        assert rogue_partial_proficiency.is_proficient_with_armor("scale_mail", items_data) is True

    def test_armor_not_found_raises_error(self, fighter_proficient, items_data):
        """Should raise KeyError if armor doesn't exist"""
        with pytest.raises(KeyError):
            fighter_proficient.is_proficient_with_armor("nonexistent_armor", items_data)

    def test_character_with_no_armor_proficiencies(self, items_data):
        """Character with empty armor_proficiencies list should not be proficient"""
        abilities = Abilities(10, 10, 10, 10, 10, 10)
        character = Character(
            name="Naked",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=10,
            armor_proficiencies=[]
        )
        assert character.is_proficient_with_armor("leather_armor", items_data) is False

    def test_character_default_no_armor_proficiencies(self, items_data):
        """Character created without specifying armor proficiencies should have empty list"""
        abilities = Abilities(10, 10, 10, 10, 10, 10)
        character = Character(
            name="Untrained",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=10
        )
        assert character.armor_proficiencies == []
        assert character.is_proficient_with_armor("leather_armor", items_data) is False


class TestProficiencyIntegration:
    """Test proficiency integration with character creation"""

    def test_fighter_has_correct_weapon_proficiencies(self, fighter_proficient):
        """Fighter should have simple and martial weapon proficiencies"""
        assert "simple" in fighter_proficient.weapon_proficiencies
        assert "martial" in fighter_proficient.weapon_proficiencies

    def test_fighter_has_correct_armor_proficiencies(self, fighter_proficient):
        """Fighter should have light, medium, heavy, and shields proficiencies"""
        assert "light" in fighter_proficient.armor_proficiencies
        assert "medium" in fighter_proficient.armor_proficiencies
        assert "heavy" in fighter_proficient.armor_proficiencies
        assert "shields" in fighter_proficient.armor_proficiencies

    def test_wizard_limited_weapon_proficiencies(self, wizard_unproficient):
        """Wizard should only have simple weapon proficiency"""
        assert "simple" in wizard_unproficient.weapon_proficiencies
        assert "martial" not in wizard_unproficient.weapon_proficiencies

    def test_wizard_limited_armor_proficiencies(self, wizard_unproficient):
        """Wizard should only have light armor proficiency"""
        assert "light" in wizard_unproficient.armor_proficiencies
        assert "medium" not in wizard_unproficient.armor_proficiencies
        assert "heavy" not in wizard_unproficient.armor_proficiencies

    def test_proficiencies_with_all_weapons(self, fighter_proficient, items_data):
        """Fighter with martial and simple proficiency should be proficient with all weapons"""
        weapons = items_data.get("weapons", {})
        for weapon_id in weapons:
            assert fighter_proficient.is_proficient_with_weapon(weapon_id, items_data), f"Fighter not proficient with {weapon_id}"

    def test_proficiencies_with_all_armor(self, fighter_proficient, items_data):
        """Fighter with all armor proficiencies should be proficient with all armor"""
        armors = items_data.get("armor", {})
        for armor_id in armors:
            assert fighter_proficient.is_proficient_with_armor(armor_id, items_data), f"Fighter not proficient with {armor_id}"

    def test_wizard_proficiency_partial_weapons(self, wizard_unproficient, items_data):
        """Wizard should be proficient with some weapons but not others"""
        # Proficient: dagger, shortbow (simple)
        assert wizard_unproficient.is_proficient_with_weapon("dagger", items_data) is True
        assert wizard_unproficient.is_proficient_with_weapon("shortbow", items_data) is True

        # Not proficient: longsword, longbow (martial)
        assert wizard_unproficient.is_proficient_with_weapon("longsword", items_data) is False
        assert wizard_unproficient.is_proficient_with_weapon("longbow", items_data) is False

    def test_wizard_proficiency_partial_armor(self, wizard_unproficient, items_data):
        """Wizard should be proficient with light armor but not heavy"""
        # Proficient: leather_armor (light)
        assert wizard_unproficient.is_proficient_with_armor("leather_armor", items_data) is True

        # Not proficient: chain_mail (heavy)
        assert wizard_unproficient.is_proficient_with_armor("chain_mail", items_data) is False
