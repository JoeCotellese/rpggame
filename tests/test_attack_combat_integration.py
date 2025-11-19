"""Integration tests for attack system with combat"""

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.core.combat import CombatEngine
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.inventory import Inventory, EquipmentSlot


@pytest.fixture
def data_loader():
    """Load game data"""
    return DataLoader()


@pytest.fixture
def items_data(data_loader):
    """Load items data"""
    return data_loader.load_items()


@pytest.fixture
def combat_engine():
    """Create combat engine"""
    return CombatEngine()


@pytest.fixture
def dex_fighter():
    """Create a DEX-focused fighter for ranged combat"""
    abilities = Abilities(
        strength=10,  # +0 modifier
        dexterity=16,  # +3 modifier
        constitution=14,
        intelligence=10,
        wisdom=12,
        charisma=10
    )
    fighter = Character(
        name="Archer",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=12,
        ac=10,
        weapon_proficiencies=["simple", "martial"],
        armor_proficiencies=["light", "medium", "heavy", "shields"]
    )
    # Equip longbow
    fighter.inventory.add_item("longbow", "weapons", 1)
    fighter.inventory.equip_item("longbow", EquipmentSlot.WEAPON)
    return fighter


@pytest.fixture
def str_fighter():
    """Create a STR-focused fighter for melee combat"""
    abilities = Abilities(
        strength=16,  # +3 modifier
        dexterity=10,  # +0 modifier
        constitution=14,
        intelligence=10,
        wisdom=12,
        charisma=10
    )
    fighter = Character(
        name="Swordmaster",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=12,
        ac=10,
        weapon_proficiencies=["simple", "martial"],
        armor_proficiencies=["light", "medium", "heavy", "shields"]
    )
    # Equip longsword
    fighter.inventory.add_item("longsword", "weapons", 1)
    fighter.inventory.equip_item("longsword", EquipmentSlot.WEAPON)
    return fighter


@pytest.fixture
def finesse_fighter():
    """Create a fighter with high DEX for finesse weapons"""
    abilities = Abilities(
        strength=12,  # +1 modifier
        dexterity=16,  # +3 modifier
        constitution=14,
        intelligence=10,
        wisdom=12,
        charisma=10
    )
    fighter = Character(
        name="Duelist",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=12,
        ac=10,
        weapon_proficiencies=["simple", "martial"],
        armor_proficiencies=["light", "medium", "heavy", "shields"]
    )
    # Equip rapier (doesn't exist in items.json but shortsword is finesse)
    fighter.inventory.add_item("shortsword", "weapons", 1)
    fighter.inventory.equip_item("shortsword", EquipmentSlot.WEAPON)
    return fighter


@pytest.fixture
def enemy():
    """Create a generic enemy for testing"""
    abilities = Abilities(
        strength=10,
        dexterity=10,
        constitution=11,
        intelligence=3,
        wisdom=10,
        charisma=3
    )
    return Creature(
        name="Goblin",
        max_hp=7,
        ac=15,
        abilities=abilities
    )


class TestRangedAttackInCombat:
    """Integration tests for ranged combat"""

    def test_dex_fighter_ranged_attack(
        self, dex_fighter, enemy, items_data, combat_engine
    ):
        """Verify DEX fighter can make effective ranged attack"""
        # Get attack bonus using DEX
        attack_bonus = dex_fighter.get_attack_bonus("longbow", items_data)
        assert attack_bonus == 5  # +3 (DEX) + 2 (prof)

        # Simulate attack
        result = combat_engine.resolve_attack(
            attacker=dex_fighter,
            defender=enemy,
            attack_bonus=attack_bonus,
            damage_dice="1d8+3",
            apply_damage=False  # Don't apply damage yet
        )

        # Attack should hit more often with DEX-based roll
        assert result.attacker_name == "Archer"
        assert result.defender_name == "Goblin"

    def test_dex_fighter_ranged_damage_uses_dex(
        self, dex_fighter, items_data
    ):
        """Verify ranged damage bonus uses DEX"""
        damage_bonus = dex_fighter.get_damage_bonus("longbow", items_data)
        assert damage_bonus == 3  # DEX modifier

    def test_ranged_attack_with_correct_damage_dice(
        self, dex_fighter, enemy, items_data, combat_engine
    ):
        """Verify ranged attack uses correct damage dice from item data"""
        weapon_data = items_data.get("weapons", {}).get("longbow", {})
        damage_dice = weapon_data.get("damage", "1d8")
        damage_bonus = dex_fighter.get_damage_bonus("longbow", items_data)
        full_damage_dice = f"{damage_dice}+{damage_bonus}"

        assert damage_dice == "1d8"
        assert full_damage_dice == "1d8+3"


class TestFinesseAttackInCombat:
    """Integration tests for finesse weapon combat"""

    def test_finesse_fighter_uses_higher_ability(
        self, finesse_fighter, items_data
    ):
        """Verify finesse fighter uses highest of STR/DEX"""
        # Finesse fighter has DEX +3, STR +1
        attack_bonus = finesse_fighter.get_attack_bonus("shortsword", items_data)
        # Should use DEX: +3 + 2 (prof) = 5
        assert attack_bonus == 5

    def test_finesse_damage_bonus_uses_higher_ability(
        self, finesse_fighter, items_data
    ):
        """Verify finesse weapon uses higher of STR/DEX for damage"""
        # Finesse fighter has DEX +3, STR +1
        damage_bonus = finesse_fighter.get_damage_bonus("shortsword", items_data)
        # Should use DEX: +3
        assert damage_bonus == 3


class TestMeleeAttackInCombat:
    """Integration tests for melee combat"""

    def test_str_fighter_melee_attack(
        self, str_fighter, enemy, items_data, combat_engine
    ):
        """Verify STR fighter makes effective melee attack"""
        attack_bonus = str_fighter.get_attack_bonus("longsword", items_data)
        assert attack_bonus == 5  # +3 (STR) + 2 (prof)

        result = combat_engine.resolve_attack(
            attacker=str_fighter,
            defender=enemy,
            attack_bonus=attack_bonus,
            damage_dice="1d8+3",
            apply_damage=False
        )

        assert result.attacker_name == "Swordmaster"
        assert result.defender_name == "Goblin"

    def test_str_fighter_damage_uses_str(self, str_fighter, items_data):
        """Verify STR melee damage uses STR modifier"""
        damage_bonus = str_fighter.get_damage_bonus("longsword", items_data)
        assert damage_bonus == 3  # STR modifier

    def test_longsword_damage_dice(self, str_fighter, items_data):
        """Verify longsword uses correct damage dice"""
        weapon_data = items_data.get("weapons", {}).get("longsword", {})
        damage_dice = weapon_data.get("damage", "1d8")
        assert damage_dice == "1d8"


class TestWeaponVariety:
    """Test various weapon types"""

    def test_greataxe_str_attack(self, str_fighter, items_data):
        """Verify greataxe (STR only) uses STR"""
        attack_bonus = str_fighter.get_attack_bonus("greataxe", items_data)
        assert attack_bonus == 5  # +3 (STR) + 2 (prof)

    def test_greataxe_str_damage(self, str_fighter, items_data):
        """Verify greataxe damage uses STR"""
        damage_bonus = str_fighter.get_damage_bonus("greataxe", items_data)
        assert damage_bonus == 3  # STR modifier

    def test_dagger_as_melee(self, str_fighter, items_data):
        """Verify dagger (finesse) works with STR when higher"""
        attack_bonus = str_fighter.get_attack_bonus("dagger", items_data)
        assert attack_bonus == 5  # +3 (STR) + 2 (prof)

    def test_dagger_as_ranged(self, dex_fighter, items_data):
        """Verify dagger (finesse) works with DEX when higher"""
        attack_bonus = dex_fighter.get_attack_bonus("dagger", items_data)
        assert attack_bonus == 5  # +3 (DEX) + 2 (prof)

    def test_light_crossbow_ranged(self, dex_fighter, items_data):
        """Verify light crossbow uses DEX"""
        attack_bonus = dex_fighter.get_attack_bonus("light_crossbow", items_data)
        assert attack_bonus == 5  # +3 (DEX) + 2 (prof)

    def test_shortbow_ranged(self, dex_fighter, items_data):
        """Verify shortbow uses DEX"""
        attack_bonus = dex_fighter.get_attack_bonus("shortbow", items_data)
        assert attack_bonus == 5  # +3 (DEX) + 2 (prof)


class TestBackwardCompatibilityInCombat:
    """Verify backward compatibility with existing system"""

    def test_melee_properties_match_longsword(self, str_fighter, items_data):
        """Verify old melee properties match new system for longsword"""
        # Old system
        old_attack = str_fighter.melee_attack_bonus
        old_damage = str_fighter.melee_damage_bonus

        # New system for longsword
        new_attack = str_fighter.get_attack_bonus("longsword", items_data)
        new_damage = str_fighter.get_damage_bonus("longsword", items_data)

        assert old_attack == new_attack
        assert old_damage == new_damage

    def test_unequipped_weapon_uses_melee_bonus(self, str_fighter, items_data):
        """Verify fallback when no weapon equipped"""
        # Remove equipped weapon
        str_fighter.inventory.unequip_item(EquipmentSlot.WEAPON)

        # Should still be able to attack with melee bonus
        assert str_fighter.melee_attack_bonus == 5
        assert str_fighter.melee_damage_bonus == 3

    def test_wizard_with_negative_str_generates_valid_dice_notation(self, combat_engine, items_data):
        """Test that wizard with negative STR modifier generates valid dice notation (1d8-1 not 1d8+-1)"""
        # Create a wizard with low STR (typical for spellcasters)
        abilities = Abilities(
            strength=8,   # -1 modifier
            dexterity=14,  # +2 modifier
            constitution=12,
            intelligence=16,
            wisdom=10,
            charisma=10
        )
        wizard = Character(
            name="Tim",
            character_class=CharacterClass.WIZARD,
            level=1,
            abilities=abilities,
            max_hp=7,
            ac=12,
            weapon_proficiencies=["simple"],
            armor_proficiencies=[]
        )

        # Create a goblin target
        goblin = Creature(
            name="Goblin",
            max_hp=7,
            ac=15,
            abilities=Abilities(
                strength=8,
                dexterity=14,
                constitution=10,
                intelligence=10,
                wisdom=8,
                charisma=8
            )
        )

        # Verify wizard has negative damage bonus
        assert wizard.melee_damage_bonus == -1

        # Import the formatting function that the CLI uses
        from dnd_engine.core.dice import format_dice_with_modifier

        # This is what the CLI does for unequipped attacks
        damage_dice = format_dice_with_modifier("1d8", wizard.melee_damage_bonus)

        # Should generate "1d8-1" not "1d8+-1"
        assert damage_dice == "1d8-1"

        # Verify the notation can be successfully parsed and used in combat
        result = combat_engine.resolve_attack(
            attacker=wizard,
            defender=goblin,
            attack_bonus=wizard.melee_attack_bonus,
            damage_dice=damage_dice,
            apply_damage=False  # Don't actually apply damage, just test notation
        )

        # If we got here without raising ValueError, the notation was valid
        assert result is not None
