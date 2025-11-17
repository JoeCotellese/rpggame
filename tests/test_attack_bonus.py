"""Unit tests for attack bonus calculation system"""

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.inventory import Inventory, EquipmentSlot


@pytest.fixture
def items_data():
    """Load items data for testing weapon properties"""
    loader = DataLoader()
    return loader.load_items()


@pytest.fixture
def fighter_str_high():
    """Create a fighter with high STR, low DEX"""
    abilities = Abilities(
        strength=16,  # +3 modifier
        dexterity=10,  # +0 modifier
        constitution=14,
        intelligence=10,
        wisdom=12,
        charisma=10
    )
    return Character(
        name="Thorgrim",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=12,
        ac=10
    )


@pytest.fixture
def fighter_dex_high():
    """Create a fighter with high DEX, low STR"""
    abilities = Abilities(
        strength=10,  # +0 modifier
        dexterity=16,  # +3 modifier
        constitution=14,
        intelligence=10,
        wisdom=12,
        charisma=10
    )
    return Character(
        name="Shadowstrike",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=12,
        ac=10
    )


@pytest.fixture
def fighter_both_high():
    """Create a fighter with high STR and DEX"""
    abilities = Abilities(
        strength=16,  # +3 modifier
        dexterity=15,  # +2 modifier
        constitution=14,
        intelligence=10,
        wisdom=12,
        charisma=10
    )
    return Character(
        name="Champion",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=12,
        ac=10
    )


class TestRangedAttackBonus:
    """Test ranged_attack_bonus property"""

    def test_ranged_attack_bonus_uses_dex(self, fighter_str_high):
        """Verify ranged attack bonus uses DEX modifier"""
        # STR +3, DEX +0, prof +2 -> 0 + 2 = +2
        assert fighter_str_high.ranged_attack_bonus == 2

    def test_ranged_attack_bonus_with_high_dex(self, fighter_dex_high):
        """Verify ranged attack bonus is correct with high DEX"""
        # STR +0, DEX +3, prof +2 -> 3 + 2 = +5
        assert fighter_dex_high.ranged_attack_bonus == 5

    def test_ranged_attack_bonus_includes_proficiency(self, fighter_str_high):
        """Verify ranged attack bonus includes proficiency bonus"""
        # Proficiency bonus for level 1 is +2
        assert fighter_str_high.ranged_attack_bonus == 2

    def test_ranged_attack_bonus_scales_with_level(self):
        """Verify ranged attack bonus scales with character level"""
        abilities = Abilities(10, 15, 14, 10, 12, 10)
        # Level 1: prof +2, DEX 15 = +2 modifier
        fighter_l1 = Character("Test", CharacterClass.FIGHTER, 1, abilities, 12, 10)
        assert fighter_l1.ranged_attack_bonus == 4  # +2 (DEX) + 2 (prof)

        # Level 5: prof +3, DEX 15 = +2 modifier
        fighter_l5 = Character("Test", CharacterClass.FIGHTER, 5, abilities, 12, 10)
        assert fighter_l5.ranged_attack_bonus == 5  # +2 (DEX) + 3 (prof)


class TestFinesseAttackBonus:
    """Test finesse_attack_bonus property"""

    def test_finesse_uses_higher_ability(self, fighter_both_high):
        """Verify finesse attack bonus uses higher of STR or DEX"""
        # STR +3, DEX +2, prof +2 -> max(3, 2) + 2 = 5
        assert fighter_both_high.finesse_attack_bonus == 5

    def test_finesse_with_higher_str(self, fighter_str_high):
        """Verify finesse uses STR when it's higher"""
        # STR +3, DEX +0, prof +2 -> max(3, 0) + 2 = 5
        assert fighter_str_high.finesse_attack_bonus == 5

    def test_finesse_with_higher_dex(self, fighter_dex_high):
        """Verify finesse uses DEX when it's higher"""
        # STR +0, DEX +3, prof +2 -> max(0, 3) + 2 = 5
        assert fighter_dex_high.finesse_attack_bonus == 5

    def test_finesse_with_equal_abilities(self):
        """Verify finesse works with equal STR and DEX"""
        abilities = Abilities(14, 14, 14, 10, 12, 10)  # Both +2
        fighter = Character("Test", CharacterClass.FIGHTER, 1, abilities, 12, 10)
        # max(2, 2) + 2 = 4
        assert fighter.finesse_attack_bonus == 4


class TestGetAttackBonus:
    """Test get_attack_bonus() method"""

    def test_melee_str_weapon(self, fighter_str_high, items_data):
        """Verify melee STR weapon uses STR modifier"""
        # Longsword: melee, no finesse
        # STR +3, prof +2 = 5
        bonus = fighter_str_high.get_attack_bonus("longsword", items_data)
        assert bonus == 5

    def test_ranged_weapon(self, fighter_dex_high, items_data):
        """Verify ranged weapon uses DEX modifier"""
        # Longbow: ranged, no finesse
        # DEX +3, prof +2 = 5
        bonus = fighter_dex_high.get_attack_bonus("longbow", items_data)
        assert bonus == 5

    def test_finesse_weapon_uses_higher(self, fighter_both_high, items_data):
        """Verify finesse weapon uses higher of STR/DEX"""
        # Shortsword: finesse
        # max(STR +3, DEX +2) + prof +2 = 5
        bonus = fighter_both_high.get_attack_bonus("shortsword", items_data)
        assert bonus == 5

    def test_finesse_with_higher_dex(self, fighter_dex_high, items_data):
        """Verify finesse weapon uses DEX when it's higher"""
        # Shortsword: finesse
        # DEX +3, prof +2 = 5
        bonus = fighter_dex_high.get_attack_bonus("shortsword", items_data)
        assert bonus == 5

    def test_dagger_finesse(self, fighter_str_high, items_data):
        """Verify dagger (finesse) uses STR when higher"""
        # Dagger: finesse
        # STR +3, prof +2 = 5
        bonus = fighter_str_high.get_attack_bonus("dagger", items_data)
        assert bonus == 5

    def test_greataxe_str_only(self, fighter_str_high, items_data):
        """Verify greataxe (no finesse) uses STR"""
        # Greataxe: melee, no finesse
        # STR +3, prof +2 = 5
        bonus = fighter_str_high.get_attack_bonus("greataxe", items_data)
        assert bonus == 5

    def test_light_crossbow_ranged(self, fighter_dex_high, items_data):
        """Verify light crossbow uses DEX"""
        # Light Crossbow: ranged
        # DEX +3, prof +2 = 5
        bonus = fighter_dex_high.get_attack_bonus("light_crossbow", items_data)
        assert bonus == 5

    def test_shortbow_ranged(self, fighter_dex_high, items_data):
        """Verify shortbow uses DEX"""
        # Shortbow: ranged
        # DEX +3, prof +2 = 5
        bonus = fighter_dex_high.get_attack_bonus("shortbow", items_data)
        assert bonus == 5

    def test_invalid_weapon_raises_error(self, fighter_str_high, items_data):
        """Verify invalid weapon ID raises KeyError"""
        with pytest.raises(KeyError):
            fighter_str_high.get_attack_bonus("fake_weapon", items_data)


class TestGetDamageBonus:
    """Test get_damage_bonus() method"""

    def test_melee_str_weapon_damage(self, fighter_str_high, items_data):
        """Verify melee STR weapon uses STR modifier for damage"""
        # Longsword: melee, no finesse
        # STR +3
        bonus = fighter_str_high.get_damage_bonus("longsword", items_data)
        assert bonus == 3

    def test_ranged_weapon_damage(self, fighter_dex_high, items_data):
        """Verify ranged weapon uses DEX modifier for damage"""
        # Longbow: ranged
        # DEX +3
        bonus = fighter_dex_high.get_damage_bonus("longbow", items_data)
        assert bonus == 3

    def test_finesse_weapon_damage_uses_higher(self, fighter_both_high, items_data):
        """Verify finesse weapon damage uses higher of STR/DEX"""
        # Shortsword: finesse
        # max(STR +3, DEX +2) = 3
        bonus = fighter_both_high.get_damage_bonus("shortsword", items_data)
        assert bonus == 3

    def test_dagger_damage_finesse(self, fighter_dex_high, items_data):
        """Verify dagger damage uses DEX when higher"""
        # Dagger: finesse
        # max(STR +0, DEX +3) = 3
        bonus = fighter_dex_high.get_damage_bonus("dagger", items_data)
        assert bonus == 3

    def test_light_crossbow_damage(self, fighter_dex_high, items_data):
        """Verify crossbow uses DEX for damage"""
        # Light Crossbow: ranged
        # DEX +3
        bonus = fighter_dex_high.get_damage_bonus("light_crossbow", items_data)
        assert bonus == 3

    def test_invalid_weapon_raises_error(self, fighter_str_high, items_data):
        """Verify invalid weapon ID raises KeyError"""
        with pytest.raises(KeyError):
            fighter_str_high.get_damage_bonus("fake_weapon", items_data)


class TestBackwardCompatibility:
    """Test that old attack bonus properties still work"""

    def test_melee_attack_bonus_still_works(self, fighter_str_high):
        """Verify melee_attack_bonus property still functions"""
        # STR +3, prof +2 = 5
        assert fighter_str_high.melee_attack_bonus == 5

    def test_melee_damage_bonus_still_works(self, fighter_str_high):
        """Verify melee_damage_bonus property still functions"""
        # STR +3
        assert fighter_str_high.melee_damage_bonus == 3

    def test_old_methods_match_new_for_str_melee(
        self, fighter_str_high, items_data
    ):
        """Verify old melee properties match new get_attack_bonus for STR melee"""
        longsword_bonus = fighter_str_high.get_attack_bonus(
            "longsword", items_data
        )
        assert longsword_bonus == fighter_str_high.melee_attack_bonus

        longsword_dmg = fighter_str_high.get_damage_bonus("longsword", items_data)
        assert longsword_dmg == fighter_str_high.melee_damage_bonus
