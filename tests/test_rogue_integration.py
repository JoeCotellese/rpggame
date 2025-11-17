# ABOUTME: Integration tests for Rogue character creation, features, and combat
# ABOUTME: Tests the full flow of creating a Rogue and using their abilities in game scenarios

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.combat import CombatEngine
from dnd_engine.core.dice import DiceRoller
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.inventory import Inventory, EquipmentSlot
from dnd_engine.utils.events import EventBus, EventType


class TestRogueCharacterCreation:
    """Integration tests for creating Rogue characters"""

    def test_create_basic_rogue(self):
        """Test creating a basic Rogue character"""
        abilities = Abilities(
            strength=10,
            dexterity=16,
            constitution=14,
            intelligence=12,
            wisdom=13,
            charisma=8
        )
        rogue = Character(
            name="Test Rogue",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities,
            max_hp=8,
            ac=14,
            skill_proficiencies=["stealth", "acrobatics", "perception", "deception"],
            expertise_skills=["stealth", "acrobatics"]
        )

        assert rogue.character_class == CharacterClass.ROGUE
        assert rogue.level == 1
        assert rogue.name == "Test Rogue"
        assert len(rogue.skill_proficiencies) == 4
        assert len(rogue.expertise_skills) == 2

    def test_rogue_with_starting_equipment(self):
        """Test Rogue starts with appropriate equipment"""
        data_loader = DataLoader()
        classes_data = data_loader.load_classes()
        items_data = data_loader.load_items()

        abilities = Abilities(
            strength=10,
            dexterity=16,
            constitution=14,
            intelligence=12,
            wisdom=13,
            charisma=8
        )
        rogue = Character(
            name="Test Rogue",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities,
            max_hp=8,
            ac=14,
            inventory=Inventory()
        )

        # Apply starting equipment
        from dnd_engine.core.character_factory import CharacterFactory
        rogue_data = classes_data["rogue"]
        CharacterFactory.apply_starting_equipment(rogue, rogue_data, items_data)

        # Check equipment
        assert rogue.inventory.get_equipped_item(EquipmentSlot.WEAPON) is not None
        assert rogue.inventory.get_equipped_item(EquipmentSlot.ARMOR) is not None

        # Verify specific items in inventory
        weapons = rogue.inventory.get_items_by_category("weapons")
        armor = rogue.inventory.get_items_by_category("armor")
        consumables = rogue.inventory.get_items_by_category("consumables")
        tools = rogue.inventory.get_items_by_category("tools")

        assert len(weapons) >= 2  # rapier and shortbow
        assert len(armor) >= 1  # leather_armor
        # Consumables are stacked with quantity, so we check total quantity
        total_consumables = sum(item.quantity for item in consumables)
        assert total_consumables >= 2  # 2 potions of healing
        assert len(tools) >= 1  # thieves_tools

    def test_rogue_ability_score_distribution(self):
        """Test Rogue prioritizes DEX > CON > INT"""
        from dnd_engine.core.character_factory import CharacterFactory

        # Rolled scores sorted high to low: [15, 14, 13, 12, 10, 8]
        rolled_scores = [15, 14, 13, 12, 10, 8]

        data_loader = DataLoader()
        classes_data = data_loader.load_classes()
        rogue_data = classes_data["rogue"]

        abilities = CharacterFactory.auto_assign_abilities(rolled_scores, rogue_data)

        # Verify priorities: DEX > CON > INT > CHA > WIS > STR
        assert abilities["dexterity"] == 15
        assert abilities["constitution"] == 14
        assert abilities["intelligence"] == 13
        assert abilities["charisma"] == 12
        assert abilities["wisdom"] == 10
        assert abilities["strength"] == 8


class TestRogueSkillsAndExpertise:
    """Integration tests for Rogue skills and expertise"""

    def test_rogue_expertise_skill_check(self):
        """Test Rogue makes skill checks with doubled proficiency for expertise"""
        data_loader = DataLoader()
        skills_data = data_loader.load_skills()

        abilities = Abilities(
            strength=10,
            dexterity=16,
            constitution=14,
            intelligence=12,
            wisdom=13,
            charisma=8
        )
        rogue = Character(
            name="Test Rogue",
            character_class=CharacterClass.ROGUE,
            level=5,
            abilities=abilities,
            max_hp=20,
            ac=14,
            skill_proficiencies=["stealth", "perception", "acrobatics"],
            expertise_skills=["stealth"]
        )

        # Stealth check with expertise (5th level has +3 proficiency)
        # DEX mod (3) + 2x proficiency (3*2=6) = 9
        stealth_result = rogue.make_skill_check("stealth", dc=10, skills_data=skills_data)
        assert stealth_result["proficient"] is True
        assert stealth_result["modifier"] == 9

        # Perception check without expertise
        # WIS mod (1) + proficiency (3) = 4
        perception_result = rogue.make_skill_check("perception", dc=10, skills_data=skills_data)
        assert perception_result["proficient"] is True
        assert perception_result["modifier"] == 4

    def test_rogue_stealth_check_with_advantage(self):
        """Test Rogue can make stealth checks with advantage"""
        data_loader = DataLoader()
        skills_data = data_loader.load_skills()

        abilities = Abilities(
            strength=10,
            dexterity=16,
            constitution=14,
            intelligence=12,
            wisdom=13,
            charisma=8
        )
        rogue = Character(
            name="Test Rogue",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities,
            max_hp=8,
            ac=14,
            skill_proficiencies=["stealth"]
        )

        result = rogue.make_skill_check("stealth", dc=12, skills_data=skills_data, advantage=True)
        assert "roll" in result
        assert "modifier" in result
        assert "success" in result
        assert "proficient" in result


class TestRogueInCombat:
    """Integration tests for Rogue in combat scenarios"""

    def test_rogue_sneak_attack_with_advantage(self):
        """Test Rogue uses sneak attack when attacking with advantage"""
        dice_roller = DiceRoller()
        combat = CombatEngine(dice_roller)
        event_bus = EventBus()

        # Create a level 3 Rogue
        rogue_abilities = Abilities(
            strength=10,
            dexterity=16,
            constitution=14,
            intelligence=12,
            wisdom=13,
            charisma=8
        )
        rogue = Character(
            name="Bob the Rogue",
            character_class=CharacterClass.ROGUE,
            level=3,
            abilities=rogue_abilities,
            max_hp=16,
            ac=14
        )

        # Create a target
        from dnd_engine.core.creature import Creature
        target_abilities = Abilities(
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=8,
            charisma=8
        )
        target = Creature(
            name="Goblin",
            max_hp=7,
            ac=15,
            abilities=target_abilities
        )

        # Attack with advantage multiple times to see if sneak attack procs
        sneak_attack_procs = 0
        for _ in range(10):
            result = combat.resolve_attack(
                attacker=rogue,
                defender=target,
                attack_bonus=5,  # +3 DEX, +2 proficiency
                damage_dice="1d8+3",  # Rapier + DEX
                advantage=True,
                event_bus=event_bus
            )

            if result.sneak_attack_damage > 0:
                sneak_attack_procs += 1
                assert result.sneak_attack_dice == "2d6"

        # With advantage, we should see sneak attack procs
        assert sneak_attack_procs > 0

    def test_rogue_multiple_weapon_attacks(self):
        """Test Rogue with rapier and shortbow"""
        data_loader = DataLoader()
        items_data = data_loader.load_items()

        abilities = Abilities(
            strength=10,
            dexterity=16,
            constitution=14,
            intelligence=12,
            wisdom=13,
            charisma=8
        )
        rogue = Character(
            name="Test Rogue",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities,
            max_hp=8,
            ac=14
        )

        # Get rapier attack bonus (finesse weapon)
        rapier_bonus = rogue.get_attack_bonus("rapier", items_data)
        # Should use finesse: max(STR, DEX) mod = 3, + proficiency 2 = 5
        assert rapier_bonus == 5

        # Get rapier damage bonus
        rapier_damage_bonus = rogue.get_damage_bonus("rapier", items_data)
        assert rapier_damage_bonus == 3  # max(STR, DEX) mod

        # Get shortbow attack bonus (ranged weapon)
        shortbow_bonus = rogue.get_attack_bonus("shortbow", items_data)
        # Should use DEX: 3 + proficiency 2 = 5
        assert shortbow_bonus == 5

        # Get shortbow damage bonus
        shortbow_damage_bonus = rogue.get_damage_bonus("shortbow", items_data)
        assert shortbow_damage_bonus == 3  # DEX mod

    def test_rogue_dex_saving_throw(self):
        """Test Rogue has proficiency in DEX saving throws"""
        abilities = Abilities(
            strength=10,
            dexterity=16,
            constitution=14,
            intelligence=12,
            wisdom=13,
            charisma=8
        )
        rogue = Character(
            name="Test Rogue",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities,
            max_hp=8,
            ac=14,
            saving_throw_proficiencies=["dex", "int"]
        )

        # DEX save: DEX mod (3) + proficiency (2) = 5
        dex_save = rogue.get_saving_throw_modifier("dex")
        assert dex_save == 5

        # INT save: INT mod (1) + proficiency (2) = 3
        int_save = rogue.get_saving_throw_modifier("int")
        assert int_save == 3

        # STR save: STR mod (0) without proficiency
        str_save = rogue.get_saving_throw_modifier("str")
        assert str_save == 0

    def test_rogue_vs_fighter_comparison(self):
        """Test Rogue and Fighter have different priorities and features"""
        rogue_abilities = Abilities(
            strength=8,
            dexterity=18,
            constitution=14,
            intelligence=12,
            wisdom=13,
            charisma=8
        )
        rogue = Character(
            name="Bob the Rogue",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=rogue_abilities,
            max_hp=8,
            ac=14
        )

        fighter_abilities = Abilities(
            strength=18,
            dexterity=8,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        fighter = Character(
            name="Alice the Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=fighter_abilities,
            max_hp=10,
            ac=18
        )

        # Rogue excels with DEX
        assert rogue.ranged_attack_bonus > fighter.ranged_attack_bonus
        # Rogue DEX mod (4) + proficiency (2) = 6 vs Fighter DEX mod (-1) + proficiency (2) = 1
        assert rogue.ranged_attack_bonus == 6
        assert fighter.ranged_attack_bonus == 1

        # Fighter excels with STR
        assert fighter.melee_attack_bonus > rogue.melee_attack_bonus
        # Fighter STR mod (4) + proficiency (2) = 6 vs Rogue STR mod (-1) + proficiency (2) = 1
        assert fighter.melee_attack_bonus == 6
        assert rogue.melee_attack_bonus == 1

        # Rogue gets sneak attack, Fighter doesn't
        assert rogue.get_sneak_attack_dice() is not None
        assert fighter.get_sneak_attack_dice() is None


class TestSneakAttackEvent:
    """Integration tests for Sneak Attack event emission"""

    def test_sneak_attack_event_emitted(self):
        """Test sneak attack events are emitted"""
        dice_roller = DiceRoller()
        combat = CombatEngine(dice_roller)
        event_bus = EventBus()

        # Track sneak attack events
        sneak_attack_events = []
        def capture_sneak_attack(event):
            sneak_attack_events.append(event)

        event_bus.subscribe(EventType.SNEAK_ATTACK, capture_sneak_attack)

        # Create a Rogue
        rogue_abilities = Abilities(
            strength=10,
            dexterity=16,
            constitution=14,
            intelligence=12,
            wisdom=13,
            charisma=8
        )
        rogue = Character(
            name="Bob the Rogue",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=rogue_abilities,
            max_hp=8,
            ac=14
        )

        # Create a target
        from dnd_engine.core.creature import Creature
        target_abilities = Abilities(
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=8,
            charisma=8
        )
        target = Creature(
            name="Goblin",
            max_hp=7,
            ac=15,
            abilities=target_abilities
        )

        # Attack with advantage (should trigger sneak attack if hit)
        result = combat.resolve_attack(
            attacker=rogue,
            defender=target,
            attack_bonus=5,
            damage_dice="1d8+3",
            advantage=True,
            event_bus=event_bus
        )

        # If sneak attack was applied, event should be emitted
        if result.sneak_attack_damage > 0:
            assert len(sneak_attack_events) > 0
            event = sneak_attack_events[0]
            assert event.data["character"] == "Bob the Rogue"
            assert event.data["dice"] == "1d6"
            assert event.data["damage"] > 0
