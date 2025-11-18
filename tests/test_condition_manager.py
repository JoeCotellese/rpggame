# ABOUTME: Unit tests for condition management system
# ABOUTME: Tests condition loading, turn-start effects, and ability check-based removal

import pytest
from pathlib import Path
from dnd_engine.systems.condition_manager import ConditionManager, ConditionEffectResult, AbilityCheckResult
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.core.dice import DiceRoller


class TestConditionManagerInit:
    """Test ConditionManager initialization and data loading"""

    def test_init_with_default_conditions_file(self):
        """Test that ConditionManager loads default conditions file"""
        manager = ConditionManager()
        assert manager.conditions_data is not None
        assert "on_fire" in manager.conditions_data

    def test_init_with_dice_roller(self):
        """Test initialization with custom DiceRoller"""
        dice_roller = DiceRoller(seed=42)
        manager = ConditionManager(dice_roller=dice_roller)
        assert manager.dice_roller == dice_roller

    def test_conditions_data_structure(self):
        """Test that loaded conditions have expected structure"""
        manager = ConditionManager()
        on_fire = manager.conditions_data["on_fire"]

        assert "name" in on_fire
        assert "description" in on_fire
        assert "turn_start_effect" in on_fire
        assert "can_end_early" in on_fire


class TestGetConditionInfo:
    """Test getting condition information"""

    def test_get_existing_condition(self):
        """Test getting info for an existing condition"""
        manager = ConditionManager()
        info = manager.get_condition_info("on_fire")

        assert info is not None
        assert info["name"] == "On Fire"

    def test_get_nonexistent_condition(self):
        """Test getting info for a condition that doesn't exist"""
        manager = ConditionManager()
        info = manager.get_condition_info("nonexistent_condition")

        assert info is None

    def test_condition_info_has_turn_start_effect(self):
        """Test that on_fire has turn_start_effect"""
        manager = ConditionManager()
        info = manager.get_condition_info("on_fire")

        assert "turn_start_effect" in info
        assert info["turn_start_effect"]["type"] == "damage"
        assert info["turn_start_effect"]["damage"] == "1d4"
        assert info["turn_start_effect"]["damage_type"] == "fire"

    def test_condition_info_has_early_removal(self):
        """Test that on_fire has can_end_early"""
        manager = ConditionManager()
        info = manager.get_condition_info("on_fire")

        assert "can_end_early" in info
        assert info["can_end_early"]["method"] == "ability_check"
        assert info["can_end_early"]["ability"] == "dexterity"
        assert info["can_end_early"]["dc"] == 10


class TestConditionChecks:
    """Test condition check methods"""

    def test_has_turn_start_effect(self):
        """Test checking if condition has turn-start effect"""
        manager = ConditionManager()

        assert manager.has_turn_start_effect("on_fire") is True

    def test_has_turn_start_effect_nonexistent(self):
        """Test checking turn-start effect for nonexistent condition"""
        manager = ConditionManager()

        assert manager.has_turn_start_effect("nonexistent") is False

    def test_can_attempt_early_removal(self):
        """Test checking if condition can be removed early"""
        manager = ConditionManager()

        assert manager.can_attempt_early_removal("on_fire") is True

    def test_can_attempt_early_removal_nonexistent(self):
        """Test checking early removal for nonexistent condition"""
        manager = ConditionManager()

        assert manager.can_attempt_early_removal("nonexistent") is False


class TestProcessTurnStartEffects:
    """Test processing turn-start effects"""

    def test_process_on_fire_damage(self):
        """Test that on_fire deals 1d4 fire damage"""
        dice_roller = DiceRoller(seed=42)
        manager = ConditionManager(dice_roller=dice_roller)

        creature = Creature(
            name="Test Goblin",
            max_hp=10,
            ac=12,
            abilities=Abilities(10, 10, 10, 10, 10, 10)
        )
        creature.add_condition("on_fire")

        hp_before = creature.current_hp
        results = manager.process_turn_start_effects(creature)

        assert len(results) == 1
        assert results[0].condition_id == "on_fire"
        assert results[0].effect_type == "damage"
        assert results[0].success is True
        assert results[0].amount > 0
        assert results[0].amount <= 4  # 1d4 max
        assert creature.current_hp < hp_before

    def test_process_multiple_conditions(self):
        """Test processing creature with multiple conditions"""
        dice_roller = DiceRoller(seed=42)
        manager = ConditionManager(dice_roller=dice_roller)

        creature = Creature(
            name="Test Goblin",
            max_hp=20,
            ac=12,
            abilities=Abilities(10, 10, 10, 10, 10, 10)
        )
        creature.add_condition("on_fire")
        # If we had other conditions, they would be processed too

        results = manager.process_turn_start_effects(creature)

        # Should only process conditions with turn_start_effect
        assert len(results) >= 1

    def test_process_no_conditions(self):
        """Test processing creature with no conditions"""
        manager = ConditionManager()

        creature = Creature(
            name="Test Goblin",
            max_hp=10,
            ac=12,
            abilities=Abilities(10, 10, 10, 10, 10, 10)
        )

        results = manager.process_turn_start_effects(creature)

        assert len(results) == 0

    def test_fire_damage_kills_creature(self):
        """Test that fire damage can kill a creature"""
        dice_roller = DiceRoller(seed=42)
        manager = ConditionManager(dice_roller=dice_roller)

        creature = Creature(
            name="Test Goblin",
            max_hp=1,  # Very low HP
            ac=12,
            abilities=Abilities(10, 10, 10, 10, 10, 10)
        )
        creature.add_condition("on_fire")

        results = manager.process_turn_start_effects(creature)

        assert len(results) == 1
        assert not creature.is_alive


class TestAttemptConditionRemoval:
    """Test attempting to remove conditions via ability check"""

    def test_attempt_removal_success(self):
        """Test successful condition removal (high DEX)"""
        # Use seed that will roll >= 10 for DC 10 check
        dice_roller = DiceRoller(seed=1)
        manager = ConditionManager(dice_roller=dice_roller)

        creature = Creature(
            name="Test Rogue",
            max_hp=20,
            ac=15,
            abilities=Abilities(10, 20, 10, 10, 10, 10)  # +5 DEX
        )
        creature.add_condition("on_fire")

        result = manager.attempt_condition_removal(creature, "on_fire")

        assert result is not None
        assert result.condition_id == "on_fire"
        assert result.dc == 10
        assert result.ability == "dexterity"
        # With +5 DEX, most d20 rolls will succeed DC 10
        # We'll check if the result is plausible
        assert result.roll_total >= 6  # minimum with +5 DEX

        # If successful, condition should be removed
        if result.success:
            assert not creature.has_condition("on_fire")
            assert result.condition_removed is True

    def test_attempt_removal_failure(self):
        """Test failed condition removal (low DEX)"""
        # Use seed that will likely fail with -2 DEX
        dice_roller = DiceRoller(seed=42)
        manager = ConditionManager(dice_roller=dice_roller)

        creature = Creature(
            name="Test Barbarian",
            max_hp=30,
            ac=12,
            abilities=Abilities(18, 6, 16, 8, 10, 10)  # -2 DEX
        )
        creature.add_condition("on_fire")

        result = manager.attempt_condition_removal(creature, "on_fire")

        assert result is not None
        assert result.condition_id == "on_fire"
        assert result.dc == 10
        assert result.ability == "dexterity"

        # Check if failure works correctly
        if not result.success:
            assert creature.has_condition("on_fire")
            assert result.condition_removed is False

    def test_attempt_removal_nonexistent_condition(self):
        """Test attempting to remove a condition that doesn't exist"""
        manager = ConditionManager()

        creature = Creature(
            name="Test Creature",
            max_hp=20,
            ac=12,
            abilities=Abilities(10, 10, 10, 10, 10, 10)
        )

        result = manager.attempt_condition_removal(creature, "nonexistent")

        assert result is None

    def test_attempt_removal_not_on_creature(self):
        """Test attempting to remove a condition creature doesn't have"""
        manager = ConditionManager()

        creature = Creature(
            name="Test Creature",
            max_hp=20,
            ac=12,
            abilities=Abilities(10, 10, 10, 10, 10, 10)
        )
        # Don't add the condition

        result = manager.attempt_condition_removal(creature, "on_fire")

        # Should still roll the check even if creature doesn't have it
        assert result is not None


class TestAbilityModifiers:
    """Test ability modifier calculations"""

    def test_get_dexterity_modifier(self):
        """Test getting dexterity modifier"""
        manager = ConditionManager()

        creature = Creature(
            name="Test Rogue",
            max_hp=20,
            ac=15,
            abilities=Abilities(10, 18, 10, 10, 10, 10)  # +4 DEX
        )

        mod = manager._get_ability_modifier(creature, "dexterity")
        assert mod == 4

    def test_get_strength_modifier(self):
        """Test getting strength modifier"""
        manager = ConditionManager()

        creature = Creature(
            name="Test Barbarian",
            max_hp=30,
            ac=12,
            abilities=Abilities(20, 10, 16, 8, 10, 10)  # +5 STR
        )

        mod = manager._get_ability_modifier(creature, "strength")
        assert mod == 5

    def test_get_all_ability_modifiers(self):
        """Test getting all ability modifiers"""
        manager = ConditionManager()

        creature = Creature(
            name="Test Creature",
            max_hp=20,
            ac=12,
            abilities=Abilities(12, 14, 16, 8, 10, 18)
        )

        assert manager._get_ability_modifier(creature, "strength") == 1
        assert manager._get_ability_modifier(creature, "dexterity") == 2
        assert manager._get_ability_modifier(creature, "constitution") == 3
        assert manager._get_ability_modifier(creature, "intelligence") == -1
        assert manager._get_ability_modifier(creature, "wisdom") == 0
        assert manager._get_ability_modifier(creature, "charisma") == 4

    def test_get_invalid_ability_modifier(self):
        """Test getting modifier for invalid ability"""
        manager = ConditionManager()

        creature = Creature(
            name="Test Creature",
            max_hp=20,
            ac=12,
            abilities=Abilities(10, 10, 10, 10, 10, 10)
        )

        mod = manager._get_ability_modifier(creature, "invalid_ability")
        assert mod == 0  # Should return 0 for invalid ability


class TestGetRemovalPromptInfo:
    """Test getting removal prompt information"""

    def test_get_prompt_info_on_fire(self):
        """Test getting prompt info for on_fire condition"""
        manager = ConditionManager()

        info = manager.get_removal_prompt_info("on_fire")

        assert info is not None
        assert info["condition_name"] == "On Fire"
        assert info["method"] == "ability_check"
        assert info["ability"] == "dexterity"
        assert info["dc"] == 10
        assert info["action_cost"] == "action"
        assert "description" in info

    def test_get_prompt_info_nonexistent(self):
        """Test getting prompt info for nonexistent condition"""
        manager = ConditionManager()

        info = manager.get_removal_prompt_info("nonexistent")

        assert info is None


class TestConditionEffectResult:
    """Test ConditionEffectResult dataclass"""

    def test_create_result(self):
        """Test creating a ConditionEffectResult"""
        result = ConditionEffectResult(
            condition_id="on_fire",
            effect_type="damage",
            success=True,
            amount=3,
            message="Test message"
        )

        assert result.condition_id == "on_fire"
        assert result.effect_type == "damage"
        assert result.success is True
        assert result.amount == 3
        assert result.message == "Test message"
        assert result.condition_removed is False


class TestAbilityCheckResult:
    """Test AbilityCheckResult dataclass"""

    def test_create_result(self):
        """Test creating an AbilityCheckResult"""
        result = AbilityCheckResult(
            condition_id="on_fire",
            success=True,
            roll_total=15,
            dc=10,
            ability="dexterity",
            message="Success!",
            condition_removed=True
        )

        assert result.condition_id == "on_fire"
        assert result.success is True
        assert result.roll_total == 15
        assert result.dc == 10
        assert result.ability == "dexterity"
        assert result.message == "Success!"
        assert result.condition_removed is True
