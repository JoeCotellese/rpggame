# ABOUTME: Unit tests for enemy AI decision-making system.
# ABOUTME: Verifies condition removal decisions and target selection behavior.

from dataclasses import dataclass

import pytest

from dnd_engine.systems.ai.enemy_ai import EnemyAI
from dnd_engine.systems.ai.targeting import (
    LowestHPStrategy,
    RandomStrategy,
)


@dataclass
class MockCombatEvent:
    """Mock combat event for testing."""

    event_type: str
    attacker: str
    defender: str | None = None
    damage: int = 0


class MockCreature:
    """Mock creature for testing AI decisions."""

    def __init__(self, name: str, current_hp: int, max_hp: int, conditions=None):
        self.name = name
        self.current_hp = current_hp
        self.max_hp = max_hp
        self.conditions = conditions or set()


class MockCharacter:
    """Mock character for testing targeting."""

    def __init__(self, name: str, current_hp: int, max_hp: int):
        self.name = name
        self.current_hp = current_hp
        self.max_hp = max_hp


class TestEnemyAIConditionRemoval:
    """Test cases for enemy AI condition removal decisions."""

    def test_should_attempt_removal_on_fire_low_hp(self):
        """Test that enemy attempts to remove on_fire when HP <= 4."""
        ai = EnemyAI()
        enemy = MockCreature("Goblin", current_hp=4, max_hp=10, conditions={"on_fire"})

        result = ai.should_attempt_condition_removal(enemy)

        assert result is True

    def test_should_attempt_removal_on_fire_very_low_hp(self):
        """Test that enemy attempts to remove on_fire when HP is 1."""
        ai = EnemyAI()
        enemy = MockCreature("Goblin", current_hp=1, max_hp=10, conditions={"on_fire"})

        result = ai.should_attempt_condition_removal(enemy)

        assert result is True

    def test_should_not_attempt_removal_on_fire_high_hp(self):
        """Test that enemy does not attempt to remove on_fire when HP > 4."""
        ai = EnemyAI()
        enemy = MockCreature("Goblin", current_hp=5, max_hp=10, conditions={"on_fire"})

        result = ai.should_attempt_condition_removal(enemy)

        assert result is False

    def test_should_not_attempt_removal_on_fire_full_hp(self):
        """Test that enemy does not attempt to remove on_fire at full HP."""
        ai = EnemyAI()
        enemy = MockCreature("Goblin", current_hp=10, max_hp=10, conditions={"on_fire"})

        result = ai.should_attempt_condition_removal(enemy)

        assert result is False

    def test_should_not_attempt_removal_no_conditions(self):
        """Test that enemy does not attempt removal when no conditions."""
        ai = EnemyAI()
        enemy = MockCreature("Goblin", current_hp=4, max_hp=10, conditions=set())

        result = ai.should_attempt_condition_removal(enemy)

        assert result is False

    def test_should_not_attempt_removal_other_conditions(self):
        """Test that enemy does not attempt removal for other conditions."""
        ai = EnemyAI()
        enemy = MockCreature("Goblin", current_hp=4, max_hp=10, conditions={"stunned"})

        result = ai.should_attempt_condition_removal(enemy)

        assert result is False

    def test_critical_threshold_boundary(self):
        """Test the exact HP threshold (4) for condition removal."""
        ai = EnemyAI()

        # At threshold: should attempt
        enemy_at_threshold = MockCreature("Goblin", current_hp=4, max_hp=10, conditions={"on_fire"})
        assert ai.should_attempt_condition_removal(enemy_at_threshold) is True

        # Above threshold: should not attempt
        enemy_above_threshold = MockCreature(
            "Goblin", current_hp=5, max_hp=10, conditions={"on_fire"}
        )
        assert ai.should_attempt_condition_removal(enemy_above_threshold) is False


class TestEnemyAITargetSelection:
    """Test cases for enemy AI target selection."""

    def test_select_target_with_default_strategy(self):
        """Test that default strategy (LowestHP) is used."""
        ai = EnemyAI()
        targets = [
            MockCharacter("Fighter", 20, 30),
            MockCharacter("Wizard", 5, 15),
            MockCharacter("Rogue", 10, 20),
        ]

        target = ai.select_target(targets)

        # Default strategy should select lowest HP
        assert target.name == "Wizard"
        assert target.current_hp == 5

    def test_select_target_with_custom_strategy(self):
        """Test target selection with custom strategy."""
        custom_strategy = LowestHPStrategy()
        ai = EnemyAI(targeting_strategy=custom_strategy)
        targets = [
            MockCharacter("Fighter", 20, 30),
            MockCharacter("Wizard", 5, 15),
        ]

        target = ai.select_target(targets)

        assert target.name == "Wizard"

    def test_select_target_with_random_strategy(self):
        """Test target selection with random strategy."""
        random_strategy = RandomStrategy()
        ai = EnemyAI(targeting_strategy=random_strategy)
        targets = [
            MockCharacter("Fighter", 20, 30),
            MockCharacter("Wizard", 5, 15),
        ]

        target = ai.select_target(targets)

        # Should return a valid target
        assert target in targets

    def test_select_target_empty_list_raises_error(self):
        """Test that empty target list raises ValueError."""
        ai = EnemyAI()
        targets = []

        with pytest.raises(ValueError):
            ai.select_target(targets)

    def test_select_target_single_option(self):
        """Test selecting from a single target."""
        ai = EnemyAI()
        targets = [MockCharacter("Fighter", 20, 30)]

        target = ai.select_target(targets)

        assert target.name == "Fighter"


class TestEnemyAIInitialization:
    """Test cases for EnemyAI initialization."""

    def test_init_with_no_strategy(self):
        """Test that EnemyAI uses LowestHPStrategy by default."""
        ai = EnemyAI()

        assert ai.targeting_strategy is not None
        assert isinstance(ai.targeting_strategy, LowestHPStrategy)

    def test_init_with_custom_strategy(self):
        """Test that EnemyAI accepts custom targeting strategy."""
        custom_strategy = RandomStrategy()
        ai = EnemyAI(targeting_strategy=custom_strategy)

        assert ai.targeting_strategy is custom_strategy
        assert isinstance(ai.targeting_strategy, RandomStrategy)


class TestEnemyAISmartTargeting:
    """Test cases for smart targeting based on intelligence."""

    def test_select_target_smart_with_low_intelligence(self):
        """Test smart targeting with bestial intelligence (INT <= 4) uses random."""
        ai = EnemyAI()
        targets = [
            MockCharacter("Fighter", 20, 30),
            MockCharacter("Wizard", 5, 15),
            MockCharacter("Rogue", 10, 20),
        ]

        # INT 3 (wolf-like) should use random targeting
        # Run multiple times to verify distribution
        selection_counts = {target.name: 0 for target in targets}
        for _ in range(100):
            target = ai.select_target_smart(
                available_targets=targets,
                enemy_intelligence=3,
                retaliation_weight=0,
            )
            selection_counts[target.name] += 1

        # Should have some distribution (not 100% Wizard)
        assert selection_counts["Fighter"] > 0

    def test_select_target_smart_with_tactical_intelligence(self):
        """Test smart targeting with tactical intelligence uses lowest HP."""
        ai = EnemyAI()
        targets = [
            MockCharacter("Fighter", 20, 30),
            MockCharacter("Wizard", 5, 15),
            MockCharacter("Rogue", 10, 20),
        ]

        target = ai.select_target_smart(
            available_targets=targets,
            enemy_intelligence=10,
            retaliation_weight=0,
        )

        assert target.name == "Wizard"
        assert target.current_hp == 5

    def test_select_target_smart_with_combat_history_retaliation(self):
        """Test smart targeting with retaliation from combat history."""
        ai = EnemyAI()
        targets = [
            MockCharacter("Fighter", 20, 30),
            MockCharacter("Wizard", 5, 15),
        ]

        # Create combat history showing Fighter attacked the Goblin
        combat_history = [
            MockCombatEvent(event_type="attack", attacker="Fighter", defender="Goblin", damage=8),
        ]

        target = ai.select_target_smart(
            available_targets=targets,
            enemy_intelligence=7,
            combat_history=combat_history,
            enemy_name="Goblin",
            retaliation_weight=1.0,  # 100% retaliation to make test deterministic
        )

        # Should retaliate against Fighter
        assert target.name == "Fighter"

    def test_select_target_smart_no_combat_history(self):
        """Test smart targeting without combat history."""
        ai = EnemyAI()
        targets = [
            MockCharacter("Fighter", 20, 30),
            MockCharacter("Wizard", 5, 15),
        ]

        target = ai.select_target_smart(
            available_targets=targets,
            enemy_intelligence=7,
            combat_history=None,
            enemy_name="Goblin",
        )

        # No recent attacker, should use base behavior (lowest HP)
        assert target.name == "Wizard"

    def test_select_target_smart_empty_targets_raises_error(self):
        """Test that empty target list raises ValueError."""
        ai = EnemyAI()

        with pytest.raises(ValueError):
            ai.select_target_smart(
                available_targets=[],
                enemy_intelligence=7,
            )


class TestEnemyAIFindRecentAttacker:
    """Test cases for finding recent attackers from combat history."""

    def test_find_recent_attacker_basic(self):
        """Test finding most recent attacker from history."""
        ai = EnemyAI()
        combat_history = [
            MockCombatEvent(event_type="attack", attacker="Fighter", defender="Goblin", damage=5),
            MockCombatEvent(event_type="attack", attacker="Wizard", defender="Goblin", damage=8),
        ]

        result = ai._find_recent_attacker(combat_history, "Goblin")

        # Should find most recent (Wizard)
        assert result is not None
        assert result.attacker_name == "Wizard"
        assert result.damage_dealt == 8

    def test_find_recent_attacker_case_insensitive(self):
        """Test that enemy name matching is case-insensitive."""
        ai = EnemyAI()
        combat_history = [
            MockCombatEvent(event_type="attack", attacker="Fighter", defender="GOBLIN", damage=5),
        ]

        result = ai._find_recent_attacker(combat_history, "goblin")

        assert result is not None
        assert result.attacker_name == "Fighter"

    def test_find_recent_attacker_skips_zero_damage(self):
        """Test that attacks dealing 0 damage are skipped."""
        ai = EnemyAI()
        combat_history = [
            MockCombatEvent(event_type="attack", attacker="Fighter", defender="Goblin", damage=5),
            MockCombatEvent(
                event_type="attack", attacker="Wizard", defender="Goblin", damage=0
            ),  # Miss
        ]

        result = ai._find_recent_attacker(combat_history, "Goblin")

        # Should find Fighter (Wizard missed)
        assert result is not None
        assert result.attacker_name == "Fighter"

    def test_find_recent_attacker_includes_spell_events(self):
        """Test that spell events are considered for retaliation."""
        ai = EnemyAI()
        combat_history = [
            MockCombatEvent(event_type="spell", attacker="Wizard", defender="Goblin", damage=12),
        ]

        result = ai._find_recent_attacker(combat_history, "Goblin")

        assert result is not None
        assert result.attacker_name == "Wizard"
        assert result.damage_dealt == 12

    def test_find_recent_attacker_ignores_non_attack_events(self):
        """Test that non-attack events are ignored."""
        ai = EnemyAI()
        combat_history = [
            MockCombatEvent(event_type="attack", attacker="Fighter", defender="Goblin", damage=5),
            MockCombatEvent(event_type="heal", attacker="Cleric", defender="Fighter", damage=0),
            MockCombatEvent(event_type="death", attacker="", defender="Skeleton", damage=0),
        ]

        result = ai._find_recent_attacker(combat_history, "Goblin")

        assert result is not None
        assert result.attacker_name == "Fighter"

    def test_find_recent_attacker_no_attacks_on_enemy(self):
        """Test when no attacks targeted the specified enemy."""
        ai = EnemyAI()
        combat_history = [
            MockCombatEvent(event_type="attack", attacker="Fighter", defender="Skeleton", damage=5),
        ]

        result = ai._find_recent_attacker(combat_history, "Goblin")

        assert result is None

    def test_find_recent_attacker_empty_history(self):
        """Test with empty combat history."""
        ai = EnemyAI()

        result = ai._find_recent_attacker([], "Goblin")

        assert result is None

    def test_find_recent_attacker_defender_is_none(self):
        """Test handling events with no defender."""
        ai = EnemyAI()
        combat_history = [
            MockCombatEvent(event_type="attack", attacker="Fighter", defender=None, damage=5),
        ]

        result = ai._find_recent_attacker(combat_history, "Goblin")

        assert result is None
