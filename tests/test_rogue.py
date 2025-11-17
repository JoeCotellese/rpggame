# ABOUTME: Unit tests for Rogue class mechanics and features
# ABOUTME: Tests cover Sneak Attack, Expertise, and Rogue-specific abilities

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.combat import CombatEngine
from dnd_engine.core.dice import DiceRoller
from dnd_engine.rules.loader import DataLoader


class TestCharacterClassRogue:
    """Tests for Rogue character class enum"""

    def test_rogue_enum_exists(self):
        """Test that ROGUE is in CharacterClass enum"""
        assert hasattr(CharacterClass, "ROGUE")
        assert CharacterClass.ROGUE.value == "rogue"

    def test_rogue_enum_value(self):
        """Test Rogue enum value is correct"""
        rogue = CharacterClass.ROGUE
        assert rogue.value == "rogue"
        assert str(rogue.value) == "rogue"


class TestSneakAttack:
    """Tests for Rogue Sneak Attack mechanics"""

    def test_rogue_gets_sneak_attack_at_level_1(self):
        """Test Rogue gets 1d6 sneak attack at level 1"""
        abilities = Abilities(strength=10, dexterity=16, constitution=14, intelligence=12, wisdom=13, charisma=8)
        rogue = Character(
            name="Test Rogue",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities,
            max_hp=8,
            ac=14
        )
        assert rogue.get_sneak_attack_dice() == "1d6"

    def test_rogue_sneak_attack_scales_by_level(self):
        """Test Sneak Attack dice scale with level"""
        abilities = Abilities(strength=10, dexterity=16, constitution=14, intelligence=12, wisdom=13, charisma=8)

        test_cases = [
            (1, "1d6"),
            (3, "2d6"),
            (5, "3d6"),
            (7, "4d6"),
            (9, "5d6"),
            (11, "6d6"),
            (13, "7d6"),
            (15, "8d6"),
            (17, "9d6"),
            (19, "10d6"),
        ]

        for level, expected_dice in test_cases:
            rogue = Character(
                name="Test Rogue",
                character_class=CharacterClass.ROGUE,
                level=level,
                abilities=abilities,
                max_hp=8,
                ac=14
            )
            assert rogue.get_sneak_attack_dice() == expected_dice, f"Level {level} should have {expected_dice}"

    def test_fighter_no_sneak_attack(self):
        """Test Fighter class cannot use Sneak Attack"""
        abilities = Abilities(strength=16, dexterity=13, constitution=14, intelligence=10, wisdom=12, charisma=8)
        fighter = Character(
            name="Test Fighter",
            character_class=CharacterClass.FIGHTER,
            level=3,
            abilities=abilities,
            max_hp=30,
            ac=18
        )
        assert fighter.get_sneak_attack_dice() is None

    def test_can_sneak_attack_with_advantage(self):
        """Test Rogue can use sneak attack when attack has advantage"""
        abilities = Abilities(strength=10, dexterity=16, constitution=14, intelligence=12, wisdom=13, charisma=8)
        rogue = Character(
            name="Test Rogue",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities,
            max_hp=8,
            ac=14
        )
        assert rogue.can_sneak_attack(has_advantage=True) is True

    def test_cannot_sneak_attack_without_conditions(self):
        """Test Rogue cannot use sneak attack without advantage or ally"""
        abilities = Abilities(strength=10, dexterity=16, constitution=14, intelligence=12, wisdom=13, charisma=8)
        rogue = Character(
            name="Test Rogue",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities,
            max_hp=8,
            ac=14
        )
        assert rogue.can_sneak_attack(has_advantage=False, ally_nearby=False) is False

    def test_cannot_sneak_attack_with_disadvantage(self):
        """Test Rogue cannot use sneak attack if attack has disadvantage"""
        abilities = Abilities(strength=10, dexterity=16, constitution=14, intelligence=12, wisdom=13, charisma=8)
        rogue = Character(
            name="Test Rogue",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities,
            max_hp=8,
            ac=14
        )
        assert rogue.can_sneak_attack(has_advantage=True, has_disadvantage=True) is False

    def test_sneak_attack_with_ally_nearby(self):
        """Test Rogue can use sneak attack when ally is nearby"""
        abilities = Abilities(strength=10, dexterity=16, constitution=14, intelligence=12, wisdom=13, charisma=8)
        rogue = Character(
            name="Test Rogue",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities,
            max_hp=8,
            ac=14
        )
        assert rogue.can_sneak_attack(has_advantage=False, ally_nearby=True) is True

    def test_fighter_cannot_sneak_attack(self):
        """Test Fighter cannot use sneak attack"""
        abilities = Abilities(strength=16, dexterity=13, constitution=14, intelligence=10, wisdom=12, charisma=8)
        fighter = Character(
            name="Test Fighter",
            character_class=CharacterClass.FIGHTER,
            level=3,
            abilities=abilities,
            max_hp=30,
            ac=18
        )
        assert fighter.can_sneak_attack(has_advantage=True) is False


class TestExpertise:
    """Tests for Rogue Expertise system"""

    def test_rogue_has_expertise_skills(self):
        """Test Rogue can have expertise skills"""
        abilities = Abilities(strength=10, dexterity=16, constitution=14, intelligence=12, wisdom=13, charisma=8)
        rogue = Character(
            name="Test Rogue",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities,
            max_hp=8,
            ac=14,
            skill_proficiencies=["stealth", "perception", "acrobatics", "deception"],
            expertise_skills=["stealth", "acrobatics"]
        )
        assert rogue.expertise_skills == ["stealth", "acrobatics"]

    def test_expertise_doubles_proficiency_bonus(self):
        """Test expertise doubles proficiency bonus for skill checks"""
        abilities = Abilities(strength=10, dexterity=16, constitution=14, intelligence=12, wisdom=13, charisma=8)
        rogue = Character(
            name="Test Rogue",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities,
            max_hp=8,
            ac=14,
            skill_proficiencies=["stealth", "perception"],
            expertise_skills=["stealth"]
        )

        # Load skills data
        data_loader = DataLoader()
        skills_data = data_loader.load_skills()

        # Stealth with expertise (should use 2x proficiency)
        stealth_mod_with_expertise = rogue.get_skill_modifier("stealth", skills_data)
        # DEX mod (3) + 2x proficiency bonus (2*2=4) = 7
        assert stealth_mod_with_expertise == 7

        # Perception without expertise (should use 1x proficiency)
        perception_mod_no_expertise = rogue.get_skill_modifier("perception", skills_data)
        # WIS mod (1) + proficiency bonus (2) = 3
        assert perception_mod_no_expertise == 3

    def test_fighter_no_expertise(self):
        """Test Fighter doesn't get double proficiency bonus"""
        abilities = Abilities(strength=16, dexterity=13, constitution=14, intelligence=10, wisdom=12, charisma=8)
        fighter = Character(
            name="Test Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=18,
            skill_proficiencies=["athletics", "perception"]
        )

        # Load skills data
        data_loader = DataLoader()
        skills_data = data_loader.load_skills()

        # Athletics without expertise (Fighter doesn't have expertise)
        athletics_mod = fighter.get_skill_modifier("athletics", skills_data)
        # STR mod (3) + proficiency bonus (2) = 5
        assert athletics_mod == 5


class TestRogueClassData:
    """Tests for Rogue class data from classes.json"""

    def test_rogue_class_data_loads(self):
        """Test Rogue class data can be loaded"""
        data_loader = DataLoader()
        classes_data = data_loader.load_classes()
        assert "rogue" in classes_data

    def test_rogue_hit_die_is_d8(self):
        """Test Rogue uses d8 hit die"""
        data_loader = DataLoader()
        classes_data = data_loader.load_classes()
        rogue_data = classes_data["rogue"]
        assert rogue_data["hit_die"] == "1d8"

    def test_rogue_dex_primary_ability(self):
        """Test Rogue primary ability is Dexterity"""
        data_loader = DataLoader()
        classes_data = data_loader.load_classes()
        rogue_data = classes_data["rogue"]
        assert rogue_data["primary_ability"] == "dex"

    def test_rogue_saving_throw_proficiencies(self):
        """Test Rogue has DEX and INT saving throw proficiencies"""
        data_loader = DataLoader()
        classes_data = data_loader.load_classes()
        rogue_data = classes_data["rogue"]
        assert "dex" in rogue_data["saving_throw_proficiencies"]
        assert "int" in rogue_data["saving_throw_proficiencies"]

    def test_rogue_light_armor_only(self):
        """Test Rogue can only wear light armor"""
        data_loader = DataLoader()
        classes_data = data_loader.load_classes()
        rogue_data = classes_data["rogue"]
        armor_profs = rogue_data["armor_proficiencies"]
        assert armor_profs == ["light"]

    def test_rogue_weapon_proficiencies(self):
        """Test Rogue has appropriate weapon proficiencies"""
        data_loader = DataLoader()
        classes_data = data_loader.load_classes()
        rogue_data = classes_data["rogue"]
        weapon_profs = rogue_data["weapon_proficiencies"]
        assert "simple" in weapon_profs
        assert "rapiers" in weapon_profs
        assert "shortswords" in weapon_profs
        assert "hand_crossbows" in weapon_profs

    def test_rogue_skill_proficiencies_count(self):
        """Test Rogue chooses 4 skill proficiencies"""
        data_loader = DataLoader()
        classes_data = data_loader.load_classes()
        rogue_data = classes_data["rogue"]
        skill_profs = rogue_data["skill_proficiencies"]
        assert skill_profs["choose"] == 4
        assert len(skill_profs["from"]) > 4

    def test_rogue_starting_equipment_includes_rapier(self):
        """Test Rogue starting equipment includes rapier"""
        data_loader = DataLoader()
        classes_data = data_loader.load_classes()
        rogue_data = classes_data["rogue"]
        assert "rapier" in rogue_data["starting_equipment"]

    def test_rogue_starting_equipment_includes_leather_armor(self):
        """Test Rogue starting equipment includes leather armor"""
        data_loader = DataLoader()
        classes_data = data_loader.load_classes()
        rogue_data = classes_data["rogue"]
        assert "leather_armor" in rogue_data["starting_equipment"]

    def test_rogue_has_sneak_attack_feature(self):
        """Test Rogue has Sneak Attack at level 1"""
        data_loader = DataLoader()
        classes_data = data_loader.load_classes()
        rogue_data = classes_data["rogue"]
        features = rogue_data["features_by_level"]["1"]
        feature_names = [f["name"] for f in features]
        assert "Sneak Attack" in feature_names

    def test_rogue_has_expertise_feature(self):
        """Test Rogue has Expertise at level 1"""
        data_loader = DataLoader()
        classes_data = data_loader.load_classes()
        rogue_data = classes_data["rogue"]
        features = rogue_data["features_by_level"]["1"]
        feature_names = [f["name"] for f in features]
        assert "Expertise" in feature_names


class TestSneakAttackInCombat:
    """Integration tests for Sneak Attack in combat"""

    def test_sneak_attack_adds_damage_to_attack(self):
        """Test sneak attack damage is added to attack result"""
        from dnd_engine.utils.events import EventBus

        dice_roller = DiceRoller()
        combat = CombatEngine(dice_roller)
        event_bus = EventBus()

        # Create a Rogue attacker
        rogue_abilities = Abilities(strength=10, dexterity=16, constitution=14, intelligence=12, wisdom=13, charisma=8)
        rogue = Character(
            name="Bob the Rogue",
            character_class=CharacterClass.ROGUE,
            level=3,
            abilities=rogue_abilities,
            max_hp=16,
            ac=14
        )

        # Create a goblin defender
        goblin_abilities = Abilities(strength=8, dexterity=14, constitution=10, intelligence=10, wisdom=8, charisma=8)
        from dnd_engine.core.creature import Creature
        goblin = Creature(
            name="Goblin",
            max_hp=7,
            ac=15,
            abilities=goblin_abilities
        )

        # Attack with advantage (triggers sneak attack)
        result = combat.resolve_attack(
            attacker=rogue,
            defender=goblin,
            attack_bonus=5,  # +3 DEX, +2 proficiency
            damage_dice="1d8+3",  # Rapier + DEX
            advantage=True,
            event_bus=event_bus
        )

        # If hit, should have sneak attack damage
        if result.hit:
            assert result.sneak_attack_dice == "2d6", f"Expected 2d6 for level 3, got {result.sneak_attack_dice}"
            assert result.sneak_attack_damage > 0, "Sneak attack damage should be > 0"
            assert result.total_damage == result.damage + result.sneak_attack_damage

    def test_sneak_attack_not_applied_without_advantage(self):
        """Test sneak attack is not applied without advantage or ally"""
        dice_roller = DiceRoller()
        combat = CombatEngine(dice_roller)

        # Create a Rogue attacker
        rogue_abilities = Abilities(strength=10, dexterity=16, constitution=14, intelligence=12, wisdom=13, charisma=8)
        rogue = Character(
            name="Bob the Rogue",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=rogue_abilities,
            max_hp=8,
            ac=14
        )

        # Create a goblin defender
        goblin_abilities = Abilities(strength=8, dexterity=14, constitution=10, intelligence=10, wisdom=8, charisma=8)
        from dnd_engine.core.creature import Creature
        goblin = Creature(
            name="Goblin",
            max_hp=7,
            ac=15,
            abilities=goblin_abilities
        )

        # Attack without advantage (no sneak attack)
        result = combat.resolve_attack(
            attacker=rogue,
            defender=goblin,
            attack_bonus=5,
            damage_dice="1d8+3",
            advantage=False
        )

        # Should not have sneak attack damage
        assert result.sneak_attack_damage == 0
        assert result.sneak_attack_dice is None


class TestRogueCombatStats:
    """Tests for Rogue combat stats and bonuses"""

    def test_rogue_uses_dex_for_finesse_weapons(self):
        """Test Rogue finesse attack bonus uses DEX"""
        abilities = Abilities(strength=10, dexterity=16, constitution=14, intelligence=12, wisdom=13, charisma=8)
        rogue = Character(
            name="Test Rogue",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities,
            max_hp=8,
            ac=14
        )

        # Finesse attack bonus should be: proficiency (2) + DEX mod (3) = 5
        assert rogue.finesse_attack_bonus == 5

    def test_rogue_ranged_attack_bonus(self):
        """Test Rogue ranged attack bonus uses DEX"""
        abilities = Abilities(strength=10, dexterity=16, constitution=14, intelligence=12, wisdom=13, charisma=8)
        rogue = Character(
            name="Test Rogue",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities,
            max_hp=8,
            ac=14
        )

        # Ranged attack bonus should be: proficiency (2) + DEX mod (3) = 5
        assert rogue.ranged_attack_bonus == 5
