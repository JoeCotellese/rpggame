# ABOUTME: Unit tests for Creature and Character classes
# ABOUTME: Tests HP management, abilities, modifiers, damage, healing, and death

import pytest
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.core.character import Character, CharacterClass


class TestAbilities:
    """Test the Abilities dataclass"""

    def test_abilities_creation(self):
        """Test creating abilities"""
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=15,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        assert abilities.strength == 16
        assert abilities.dexterity == 14

    def test_ability_modifiers(self):
        """Test ability score to modifier conversion"""
        test_cases = [
            (1, -5),
            (3, -4),
            (8, -1),
            (10, 0),
            (11, 0),
            (12, 1),
            (16, 3),
            (20, 5),
        ]

        for score, expected_mod in test_cases:
            abilities = Abilities(
                strength=score,
                dexterity=10,
                constitution=10,
                intelligence=10,
                wisdom=10,
                charisma=10
            )
            assert abilities.str_mod == expected_mod

    def test_all_ability_modifiers(self):
        """Test that all ability modifiers are calculated correctly"""
        abilities = Abilities(
            strength=16,  # +3
            dexterity=14,  # +2
            constitution=15,  # +2
            intelligence=10,  # +0
            wisdom=12,  # +1
            charisma=8  # -1
        )

        assert abilities.str_mod == 3
        assert abilities.dex_mod == 2
        assert abilities.con_mod == 2
        assert abilities.int_mod == 0
        assert abilities.wis_mod == 1
        assert abilities.cha_mod == -1


class TestCreature:
    """Test the Creature base class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=15,
            intelligence=10,
            wisdom=12,
            charisma=8
        )

    def test_creature_creation(self):
        """Test creating a basic creature"""
        creature = Creature(
            name="Goblin",
            max_hp=7,
            ac=15,
            abilities=self.abilities
        )

        assert creature.name == "Goblin"
        assert creature.max_hp == 7
        assert creature.current_hp == 7
        assert creature.ac == 15
        assert creature.is_alive is True

    def test_creature_take_damage(self):
        """Test creature taking damage"""
        creature = Creature(
            name="Goblin",
            max_hp=10,
            ac=15,
            abilities=self.abilities
        )

        creature.take_damage(5)
        assert creature.current_hp == 5
        assert creature.is_alive is True

    def test_creature_death(self):
        """Test creature dying when HP reaches 0"""
        creature = Creature(
            name="Goblin",
            max_hp=10,
            ac=15,
            abilities=self.abilities
        )

        creature.take_damage(10)
        assert creature.current_hp == 0
        assert creature.is_alive is False

    def test_creature_overkill_damage(self):
        """Test that HP doesn't go below 0"""
        creature = Creature(
            name="Goblin",
            max_hp=10,
            ac=15,
            abilities=self.abilities
        )

        creature.take_damage(20)
        assert creature.current_hp == 0
        assert creature.is_alive is False

    def test_creature_healing(self):
        """Test creature healing"""
        creature = Creature(
            name="Goblin",
            max_hp=10,
            ac=15,
            abilities=self.abilities
        )

        creature.take_damage(7)
        assert creature.current_hp == 3

        creature.heal(4)
        assert creature.current_hp == 7

    def test_creature_overhealing(self):
        """Test that healing doesn't exceed max HP"""
        creature = Creature(
            name="Goblin",
            max_hp=10,
            ac=15,
            abilities=self.abilities
        )

        creature.take_damage(3)
        creature.heal(10)  # Try to heal for more than max
        assert creature.current_hp == 10

    def test_creature_cannot_heal_if_dead(self):
        """Test that dead creatures cannot be healed (requires resurrection)"""
        creature = Creature(
            name="Goblin",
            max_hp=10,
            ac=15,
            abilities=self.abilities
        )

        creature.take_damage(10)
        assert creature.is_alive is False

        creature.heal(5)
        # Should still be dead and at 0 HP
        assert creature.current_hp == 0
        assert creature.is_alive is False

    def test_creature_conditions(self):
        """Test adding and removing conditions"""
        creature = Creature(
            name="Fighter",
            max_hp=20,
            ac=16,
            abilities=self.abilities
        )

        assert not creature.has_condition("prone")

        creature.add_condition("prone")
        assert creature.has_condition("prone")

    def test_apply_condition_with_metadata(self):
        """Test applying conditions with duration and repeat save metadata"""
        creature = Creature(
            name="Fighter",
            max_hp=20,
            ac=16,
            abilities=self.abilities
        )

        creature.apply_condition_with_metadata(
            condition="paralyzed",
            duration_type="rounds",
            duration=10,
            dc=10,
            ability="constitution",
            allow_repeat_save=True,
            repeat_timing="end_of_turn"
        )

        assert creature.has_condition("paralyzed")
        metadata = creature.active_conditions["paralyzed"]
        assert metadata["duration_type"] == "rounds"
        assert metadata["duration_remaining"] == 10
        assert metadata["dc"] == 10
        assert metadata["ability"] == "constitution"
        assert metadata["allow_repeat_save"] is True
        assert metadata["repeat_timing"] == "end_of_turn"

    def test_can_take_actions_when_paralyzed(self):
        """Test that paralyzed creatures cannot take actions"""
        creature = Creature(
            name="Fighter",
            max_hp=20,
            ac=16,
            abilities=self.abilities
        )

        assert creature.can_take_actions() is True

        creature.add_condition("paralyzed")
        assert creature.can_take_actions() is False

    def test_can_take_actions_with_various_conditions(self):
        """Test incapacitating vs non-incapacitating conditions"""
        creature = Creature(
            name="Fighter",
            max_hp=20,
            ac=16,
            abilities=self.abilities
        )

        # Non-incapacitating conditions
        creature.add_condition("prone")
        assert creature.can_take_actions() is True

        creature.remove_condition("prone")
        creature.add_condition("poisoned")
        assert creature.can_take_actions() is True

        # Incapacitating conditions
        incapacitating = ["paralyzed", "stunned", "unconscious", "petrified"]
        for condition in incapacitating:
            creature.remove_condition("poisoned")
            creature.add_condition(condition)
            assert creature.can_take_actions() is False
            creature.remove_condition(condition)

    def test_process_end_of_turn_conditions_duration_countdown(self):
        """Test that round-based conditions countdown each turn"""
        creature = Creature(
            name="Fighter",
            max_hp=20,
            ac=16,
            abilities=self.abilities
        )

        creature.apply_condition_with_metadata(
            condition="paralyzed",
            duration_type="rounds",
            duration=3,
            dc=10,
            ability="constitution",
            allow_repeat_save=False
        )

        # After turn 1
        results = creature.process_end_of_turn_conditions()
        assert creature.has_condition("paralyzed")
        assert creature.active_conditions["paralyzed"]["duration_remaining"] == 2

        # After turn 2
        results = creature.process_end_of_turn_conditions()
        assert creature.has_condition("paralyzed")
        assert creature.active_conditions["paralyzed"]["duration_remaining"] == 1

        # After turn 3 - should expire
        results = creature.process_end_of_turn_conditions()
        assert not creature.has_condition("paralyzed")
        assert len(results) == 1
        assert results[0]["type"] == "duration_expired"
        assert results[0]["condition"] == "paralyzed"

    def test_process_end_of_turn_conditions_repeat_save_success(self):
        """Test that successful repeat saves remove conditions"""
        # Create creature with high CON (good chance to pass DC 10)
        high_con_abilities = Abilities(
            strength=10,
            dexterity=10,
            constitution=20,  # +5 modifier
            intelligence=10,
            wisdom=10,
            charisma=10
        )
        creature = Creature(
            name="Fighter",
            max_hp=20,
            ac=16,
            abilities=high_con_abilities
        )

        creature.apply_condition_with_metadata(
            condition="paralyzed",
            duration_type="rounds",
            duration=10,
            dc=10,
            ability="constitution",
            allow_repeat_save=True,
            repeat_timing="end_of_turn"
        )

        # Keep processing until save succeeds (high CON should eventually pass)
        max_attempts = 50
        for _ in range(max_attempts):
            results = creature.process_end_of_turn_conditions()
            if not creature.has_condition("paralyzed"):
                # Found a successful save
                assert len(results) > 0
                assert results[0]["type"] == "repeat_save_success"
                assert results[0]["condition"] == "paralyzed"
                break
        else:
            # Should have succeeded within 50 attempts with +5 modifier
            pytest.fail("Should have passed save within 50 attempts")

    def test_process_end_of_turn_conditions_repeat_save_failure(self):
        """Test that failed repeat saves keep condition active"""
        # Create creature with low CON (poor chance to pass DC 20)
        low_con_abilities = Abilities(
            strength=10,
            dexterity=10,
            constitution=3,  # -4 modifier
            intelligence=10,
            wisdom=10,
            charisma=10
        )
        creature = Creature(
            name="Weakling",
            max_hp=20,
            ac=16,
            abilities=low_con_abilities
        )

        creature.apply_condition_with_metadata(
            condition="paralyzed",
            duration_type="rounds",
            duration=10,
            dc=20,  # High DC
            ability="constitution",
            allow_repeat_save=True,
            repeat_timing="end_of_turn"
        )

        # Process several turns - should stay paralyzed
        for _ in range(5):
            initial_duration = creature.active_conditions["paralyzed"]["duration_remaining"]
            creature.process_end_of_turn_conditions()

            # Either still paralyzed (failed save) or removed (passed save - rare)
            if creature.has_condition("paralyzed"):
                # Failed save - with repeat saves enabled, duration does NOT decrement
                # The repeat save is the primary mechanism for ending the condition
                assert creature.active_conditions["paralyzed"]["duration_remaining"] == initial_duration

    def test_conditions_backward_compatibility(self):
        """Test that conditions property returns set of condition names"""
        creature = Creature(
            name="Fighter",
            max_hp=20,
            ac=16,
            abilities=self.abilities
        )

        creature.add_condition("prone")
        creature.add_condition("poisoned")

        # Should be able to access as set via conditions property
        assert isinstance(creature.conditions, set)
        assert "prone" in creature.conditions
        assert "poisoned" in creature.conditions
        assert len(creature.conditions) == 2
        assert "prone" in creature.conditions

        creature.remove_condition("prone")
        assert not creature.has_condition("prone")

    def test_creature_multiple_conditions(self):
        """Test managing multiple conditions"""
        creature = Creature(
            name="Fighter",
            max_hp=20,
            ac=16,
            abilities=self.abilities
        )

        creature.add_condition("prone")
        creature.add_condition("stunned")

        assert creature.has_condition("prone")
        assert creature.has_condition("stunned")
        assert len(creature.conditions) == 2

    def test_creature_initiative_modifier(self):
        """Test that initiative uses dexterity modifier"""
        creature = Creature(
            name="Goblin",
            max_hp=7,
            ac=15,
            abilities=self.abilities
        )

        # Initiative modifier should be dexterity modifier
        assert creature.initiative_modifier == self.abilities.dex_mod


class TestCharacter:
    """Test the Character class (player character)"""

    def setup_method(self):
        """Set up test fixtures"""
        self.abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=15,
            intelligence=10,
            wisdom=12,
            charisma=8
        )

    def test_character_creation(self):
        """Test creating a character"""
        character = Character(
            name="Thorin",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=self.abilities,
            max_hp=12,
            ac=16
        )

        assert character.name == "Thorin"
        assert character.character_class == CharacterClass.FIGHTER
        assert character.level == 1
        assert character.xp == 0
        assert character.max_hp == 12
        assert character.current_hp == 12

    def test_character_proficiency_bonus(self):
        """Test proficiency bonus calculation by level"""
        test_cases = [
            (1, 2),
            (2, 2),
            (3, 2),
            (4, 2),
            (5, 3),
            (8, 3),
            (9, 4),
        ]

        for level, expected_bonus in test_cases:
            character = Character(
                name="Test",
                character_class=CharacterClass.FIGHTER,
                level=level,
                abilities=self.abilities,
                max_hp=10,
                ac=16
            )
            assert character.proficiency_bonus == expected_bonus

    def test_character_xp_gain(self):
        """Test gaining experience points"""
        character = Character(
            name="Thorin",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=self.abilities,
            max_hp=12,
            ac=16
        )

        character.gain_xp(100)
        assert character.xp == 100

        character.gain_xp(50)
        assert character.xp == 150

    def test_character_attack_bonus(self):
        """Test attack bonus calculation (proficiency + STR mod for melee)"""
        character = Character(
            name="Thorin",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=self.abilities,
            max_hp=12,
            ac=16
        )

        # Level 1 fighter: proficiency +2, STR mod +3 = +5
        assert character.melee_attack_bonus == 5

    def test_character_damage_bonus(self):
        """Test damage bonus calculation (STR mod)"""
        character = Character(
            name="Thorin",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=self.abilities,
            max_hp=12,
            ac=16
        )

        # Damage bonus should be strength modifier
        assert character.melee_damage_bonus == 3

    def test_character_inherits_creature_methods(self):
        """Test that Character inherits Creature functionality"""
        character = Character(
            name="Thorin",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=self.abilities,
            max_hp=12,
            ac=16
        )

        # Should have creature methods
        character.take_damage(5)
        assert character.current_hp == 7

        character.heal(3)
        assert character.current_hp == 10

        character.add_condition("prone")
        assert character.has_condition("prone")
