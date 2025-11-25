# ABOUTME: Unit tests for enemy AI targeting strategies.
# ABOUTME: Verifies target selection logic for different AI behaviors.

import pytest

from dnd_engine.systems.ai.targeting import (
    LowestHPStrategy,
    RandomStrategy,
    TargetingStrategy,
)


class MockCharacter:
    """Mock character for testing targeting."""

    def __init__(self, name: str, current_hp: int, max_hp: int):
        self.name = name
        self.current_hp = current_hp
        self.max_hp = max_hp


class TestLowestHPStrategy:
    """Test cases for LowestHPStrategy."""

    def test_select_lowest_hp_target(self):
        """Test that LowestHPStrategy selects the character with lowest HP."""
        strategy = LowestHPStrategy()
        targets = [
            MockCharacter("Fighter", 20, 30),
            MockCharacter("Wizard", 5, 15),
            MockCharacter("Rogue", 10, 20),
        ]

        target = strategy.select_target(targets)

        assert target.name == "Wizard"
        assert target.current_hp == 5

    def test_select_target_with_tied_hp(self):
        """Test behavior when multiple targets have the same lowest HP."""
        strategy = LowestHPStrategy()
        targets = [
            MockCharacter("Fighter", 10, 30),
            MockCharacter("Wizard", 5, 15),
            MockCharacter("Rogue", 5, 20),
        ]

        target = strategy.select_target(targets)

        # Should return one of the tied targets
        assert target.current_hp == 5
        assert target.name in ["Wizard", "Rogue"]

    def test_select_target_single_option(self):
        """Test selecting from a single target."""
        strategy = LowestHPStrategy()
        targets = [MockCharacter("Fighter", 20, 30)]

        target = strategy.select_target(targets)

        assert target.name == "Fighter"

    def test_select_target_empty_list_raises_error(self):
        """Test that empty target list raises ValueError."""
        strategy = LowestHPStrategy()
        targets = []

        with pytest.raises(ValueError, match="Cannot select target from empty list"):
            strategy.select_target(targets)


class TestRandomStrategy:
    """Test cases for RandomStrategy."""

    def test_select_random_target(self):
        """Test that RandomStrategy selects a valid target."""
        strategy = RandomStrategy()
        targets = [
            MockCharacter("Fighter", 20, 30),
            MockCharacter("Wizard", 5, 15),
            MockCharacter("Rogue", 10, 20),
        ]

        target = strategy.select_target(targets)

        # Target should be one of the available targets
        assert target in targets

    def test_select_target_single_option(self):
        """Test selecting from a single target."""
        strategy = RandomStrategy()
        targets = [MockCharacter("Fighter", 20, 30)]

        target = strategy.select_target(targets)

        assert target.name == "Fighter"

    def test_select_target_empty_list_raises_error(self):
        """Test that empty target list raises ValueError."""
        strategy = RandomStrategy()
        targets = []

        with pytest.raises(ValueError, match="Cannot select target from empty list"):
            strategy.select_target(targets)

    def test_randomness_distribution(self):
        """Test that random selection has reasonable distribution over many trials."""
        strategy = RandomStrategy()
        targets = [
            MockCharacter("Fighter", 20, 30),
            MockCharacter("Wizard", 5, 15),
            MockCharacter("Rogue", 10, 20),
        ]

        # Run many trials
        selection_counts = {target.name: 0 for target in targets}
        num_trials = 1000

        for _ in range(num_trials):
            target = strategy.select_target(targets)
            selection_counts[target.name] += 1

        # Each target should be selected at least once with high probability
        for count in selection_counts.values():
            assert count > 0

        # Distribution should be roughly equal (within reasonable bounds)
        expected = num_trials / len(targets)
        for count in selection_counts.values():
            # Allow 25% deviation from expected value
            assert 0.75 * expected <= count <= 1.25 * expected


class TestTargetingStrategy:
    """Test cases for TargetingStrategy base class."""

    def test_abstract_base_class(self):
        """Test that TargetingStrategy cannot be instantiated directly."""
        with pytest.raises(TypeError):
            TargetingStrategy()
