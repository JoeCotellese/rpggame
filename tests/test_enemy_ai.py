# ABOUTME: Unit tests for enemy AI decision-making system.
# ABOUTME: Verifies condition removal decisions and target selection behavior.

import pytest

from dnd_engine.systems.ai.enemy_ai import EnemyAI
from dnd_engine.systems.ai.targeting import LowestHPStrategy, RandomStrategy


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
        enemy_above_threshold = MockCreature("Goblin", current_hp=5, max_hp=10, conditions={"on_fire"})
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
