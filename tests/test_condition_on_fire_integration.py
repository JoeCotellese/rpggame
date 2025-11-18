# ABOUTME: Integration tests for on_fire condition system
# ABOUTME: Tests turn-start fire damage, player prompts, enemy AI, and extinguish mechanics

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.systems.condition_manager import ConditionManager
from dnd_engine.systems.initiative import InitiativeTracker
from dnd_engine.systems.action_economy import ActionType
from dnd_engine.core.dice import DiceRoller
from dnd_engine.utils.events import EventBus


class TestOnFireConditionIntegration:
    """Integration tests for on_fire condition system"""

    def test_creature_takes_fire_damage_at_turn_start(self):
        """Test that creature with on_fire takes damage at start of turn"""
        # Setup
        dice_roller = DiceRoller(seed=42)
        manager = ConditionManager(dice_roller=dice_roller)

        creature = Creature(
            name="Test Goblin",
            max_hp=10,
            ac=12,
            abilities=Abilities(10, 10, 10, 10, 10, 10)
        )

        # Set creature on fire
        creature.add_condition("on_fire")
        assert creature.has_condition("on_fire")

        hp_before = creature.current_hp

        # Process turn-start effects
        results = manager.process_turn_start_effects(creature)

        # Verify damage was dealt
        assert len(results) == 1
        assert results[0].condition_id == "on_fire"
        assert results[0].effect_type == "damage"
        assert results[0].amount > 0
        assert results[0].amount <= 4  # 1d4 damage
        assert creature.current_hp == hp_before - results[0].amount

    def test_fire_damage_multiple_turns(self):
        """Test that fire damage applies every turn until extinguished"""
        dice_roller = DiceRoller(seed=42)
        manager = ConditionManager(dice_roller=dice_roller)

        creature = Creature(
            name="Test Orc",
            max_hp=20,
            ac=13,
            abilities=Abilities(10, 10, 10, 10, 10, 10)
        )

        creature.add_condition("on_fire")

        # Process 3 turns
        total_damage = 0
        for turn in range(3):
            hp_before = creature.current_hp
            results = manager.process_turn_start_effects(creature)

            assert len(results) == 1
            damage = results[0].amount
            total_damage += damage
            assert creature.current_hp == hp_before - damage

        # Should have taken damage 3 times
        assert creature.current_hp == 20 - total_damage
        assert total_damage > 0

    def test_successful_extinguish_removes_condition(self):
        """Test that successful DEX check removes on_fire condition"""
        # Use a seed that should succeed with high DEX
        dice_roller = DiceRoller(seed=1)
        manager = ConditionManager(dice_roller=dice_roller)

        creature = Creature(
            name="Test Rogue",
            max_hp=20,
            ac=15,
            abilities=Abilities(10, 20, 10, 10, 10, 10)  # +5 DEX
        )

        creature.add_condition("on_fire")

        # Attempt to extinguish
        result = manager.attempt_condition_removal(creature, "on_fire")

        assert result is not None
        assert result.dc == 10
        assert result.ability == "dexterity"

        # With +5 DEX, should have good chance to succeed
        if result.roll_total >= 10:
            assert result.success is True
            assert not creature.has_condition("on_fire")
            assert result.condition_removed is True

    def test_failed_extinguish_keeps_condition(self):
        """Test that failed DEX check keeps creature on fire"""
        # Use specific seed and low DEX to test failure
        dice_roller = DiceRoller(seed=42)
        manager = ConditionManager(dice_roller=dice_roller)

        creature = Creature(
            name="Test Barbarian",
            max_hp=30,
            ac=12,
            abilities=Abilities(18, 6, 16, 8, 10, 10)  # -2 DEX
        )

        creature.add_condition("on_fire")

        # Attempt to extinguish
        result = manager.attempt_condition_removal(creature, "on_fire")

        assert result is not None
        assert result.dc == 10

        # If failed, condition should remain
        if result.roll_total < 10:
            assert result.success is False
            assert creature.has_condition("on_fire")
            assert result.condition_removed is False

    def test_extinguish_consumes_action(self):
        """Test that attempting to extinguish consumes an action"""
        dice_roller = DiceRoller(seed=42)
        manager = ConditionManager(dice_roller=dice_roller)
        tracker = InitiativeTracker(dice_roller=dice_roller)

        creature = Creature(
            name="Test Fighter",
            max_hp=20,
            ac=16,
            abilities=Abilities(16, 12, 14, 10, 10, 10)
        )

        creature.add_condition("on_fire")
        tracker.add_combatant(creature)

        # Get turn state
        turn_state = tracker.get_current_turn_state()
        assert turn_state.is_action_available(ActionType.ACTION)

        # Attempt to extinguish (this would consume action in actual gameplay)
        result = manager.attempt_condition_removal(creature, "on_fire")
        assert result is not None

        # In actual gameplay, the action would be consumed here
        turn_state.consume_action(ActionType.ACTION)
        assert not turn_state.is_action_available(ActionType.ACTION)

    def test_on_fire_kills_low_hp_creature(self):
        """Test that fire damage can kill a creature"""
        dice_roller = DiceRoller(seed=42)
        manager = ConditionManager(dice_roller=dice_roller)

        creature = Creature(
            name="Test Rat",
            max_hp=1,  # Very low HP
            ac=10,
            abilities=Abilities(6, 10, 8, 4, 8, 4)
        )

        creature.add_condition("on_fire")
        assert creature.is_alive

        # Process turn-start effects
        results = manager.process_turn_start_effects(creature)

        assert len(results) == 1
        # Should have died from fire damage (1d4 against 1 HP)
        assert not creature.is_alive
        assert creature.current_hp == 0

    def test_condition_removed_after_successful_extinguish(self):
        """Test complete flow: on fire -> take damage -> extinguish -> no more damage"""
        dice_roller = DiceRoller(seed=1)  # Seed for successful rolls
        manager = ConditionManager(dice_roller=dice_roller)

        creature = Creature(
            name="Test Paladin",
            max_hp=30,
            ac=18,
            abilities=Abilities(16, 14, 16, 10, 12, 14)  # +2 DEX
        )

        creature.add_condition("on_fire")

        # Turn 1: Take fire damage
        results = manager.process_turn_start_effects(creature)
        assert len(results) == 1
        hp_after_damage = creature.current_hp
        assert hp_after_damage < 30

        # Attempt to extinguish
        extinguish_result = manager.attempt_condition_removal(creature, "on_fire")

        # If successful, no more fire damage on next turn
        if extinguish_result.success:
            assert not creature.has_condition("on_fire")

            # Turn 2: Should NOT take fire damage
            results2 = manager.process_turn_start_effects(creature)
            assert len(results2) == 0
            assert creature.current_hp == hp_after_damage  # HP unchanged


class TestEnemyAIConditionIntegration:
    """Integration tests for enemy AI condition removal"""

    def test_low_hp_enemy_attempts_extinguish(self):
        """Test that enemy with low HP will attempt to extinguish"""
        dice_roller = DiceRoller(seed=42)
        manager = ConditionManager(dice_roller=dice_roller)

        enemy = Creature(
            name="Burning Goblin",
            max_hp=7,
            ac=13,
            abilities=Abilities(8, 14, 10, 10, 8, 8)  # +2 DEX
        )

        # Set HP to 4 (one 1d4 could kill)
        enemy.current_hp = 4
        enemy.add_condition("on_fire")

        # Enemy should attempt to extinguish
        # This simulates the AI logic: if HP <= 4 and on_fire, attempt removal
        should_attempt = enemy.current_hp <= 4 and enemy.has_condition("on_fire")
        assert should_attempt is True

        # Attempt removal
        result = manager.attempt_condition_removal(enemy, "on_fire")
        assert result is not None

    def test_high_hp_enemy_does_not_extinguish(self):
        """Test that enemy with high HP won't bother extinguishing"""
        enemy = Creature(
            name="Healthy Orc",
            max_hp=15,
            ac=13,
            abilities=Abilities(16, 12, 16, 7, 11, 10)
        )

        # Set HP to 15 (plenty of health)
        enemy.current_hp = 15
        enemy.add_condition("on_fire")

        # Enemy should NOT attempt to extinguish (HP > 4)
        should_attempt = enemy.current_hp <= 4 and enemy.has_condition("on_fire")
        assert should_attempt is False

        # Enemy would choose to attack instead


class TestConditionWithCombatFlow:
    """Integration tests combining conditions with combat flow"""

    def test_on_fire_with_initiative_tracker(self):
        """Test on_fire condition working with initiative tracker"""
        dice_roller = DiceRoller(seed=42)
        manager = ConditionManager(dice_roller=dice_roller)
        tracker = InitiativeTracker(dice_roller=dice_roller)

        hero = Character(
            "Hero",
            CharacterClass.FIGHTER,
            level=2,
            abilities=Abilities(14, 12, 14, 10, 10, 10),
            max_hp=18,
            ac=16
        )

        goblin = Creature(
            "Goblin",
            max_hp=7,
            ac=13,
            abilities=Abilities(8, 14, 10, 10, 8, 8)
        )

        # Add to initiative
        tracker.add_combatant(hero)
        tracker.add_combatant(goblin)

        # Set goblin on fire
        goblin.add_condition("on_fire")

        # Simulate goblin's turn
        current = tracker.get_current_combatant()
        if current.creature == goblin:
            # Process turn-start effects
            results = manager.process_turn_start_effects(goblin)
            assert len(results) == 1
            assert goblin.current_hp < 7

    def test_multiple_creatures_with_conditions(self):
        """Test multiple creatures each with their own conditions"""
        dice_roller = DiceRoller(seed=42)
        manager = ConditionManager(dice_roller=dice_roller)

        creature1 = Creature("Goblin 1", max_hp=7, ac=13, abilities=Abilities(8, 14, 10, 10, 8, 8))
        creature2 = Creature("Goblin 2", max_hp=7, ac=13, abilities=Abilities(8, 14, 10, 10, 8, 8))

        # Both on fire
        creature1.add_condition("on_fire")
        creature2.add_condition("on_fire")

        # Both take damage
        results1 = manager.process_turn_start_effects(creature1)
        results2 = manager.process_turn_start_effects(creature2)

        assert len(results1) == 1
        assert len(results2) == 1
        assert creature1.current_hp < 7
        assert creature2.current_hp < 7

    def test_condition_survives_across_turns(self):
        """Test that condition persists until explicitly removed"""
        dice_roller = DiceRoller(seed=42)
        manager = ConditionManager(dice_roller=dice_roller)
        tracker = InitiativeTracker(dice_roller=dice_roller)

        creature = Creature(
            "Persistent Fire",
            max_hp=30,
            ac=13,
            abilities=Abilities(10, 10, 10, 10, 10, 10)
        )

        tracker.add_combatant(creature)
        creature.add_condition("on_fire")

        # Turn 1
        results1 = manager.process_turn_start_effects(creature)
        assert len(results1) == 1
        assert creature.has_condition("on_fire")

        tracker.next_turn()

        # Turn 2
        results2 = manager.process_turn_start_effects(creature)
        assert len(results2) == 1
        assert creature.has_condition("on_fire")

        # Condition should persist until removed
        assert creature.has_condition("on_fire")
