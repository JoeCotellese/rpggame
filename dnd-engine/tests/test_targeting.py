# ABOUTME: Unit tests for enemy AI targeting strategies.
# ABOUTME: Verifies target selection logic for different AI behaviors.

import pytest

from dnd_engine.systems.ai.targeting import (
    INT_BESTIAL_MAX,
    LowestHPStrategy,
    RandomStrategy,
    RecentAttacker,
    SmartTargetingStrategy,
    TargetingStrategy,
    get_strategy_for_intelligence,
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


class TestSmartTargetingStrategy:
    """Test cases for SmartTargetingStrategy with intelligence-based behavior."""

    # --- Intelligence Tier Tests ---

    def test_bestial_intelligence_uses_random_targeting(self):
        """Test that INT <= 4 (bestial) uses random targeting."""
        # With INT 3 (wolf-like), should use random targeting
        strategy = SmartTargetingStrategy(intelligence=3, retaliation_weight=0)
        targets = [
            MockCharacter("Fighter", 20, 30),
            MockCharacter("Wizard", 5, 15),  # Lowest HP
            MockCharacter("Rogue", 10, 20),
        ]

        # Run many trials to verify random distribution
        selection_counts = {target.name: 0 for target in targets}
        num_trials = 1000

        for _ in range(num_trials):
            target = strategy.select_target(targets)
            selection_counts[target.name] += 1

        # Each target should be selected at least once (random distribution)
        for count in selection_counts.values():
            assert count > 0

        # Distribution should be roughly equal (unlike LowestHP which always picks Wizard)
        expected = num_trials / len(targets)
        for count in selection_counts.values():
            assert 0.60 * expected <= count <= 1.40 * expected

    def test_basic_tactics_intelligence_uses_lowest_hp(self):
        """Test that INT 5-9 uses lowest HP targeting."""
        strategy = SmartTargetingStrategy(intelligence=7, retaliation_weight=0)
        targets = [
            MockCharacter("Fighter", 20, 30),
            MockCharacter("Wizard", 5, 15),
            MockCharacter("Rogue", 10, 20),
        ]

        target = strategy.select_target(targets)

        assert target.name == "Wizard"
        assert target.current_hp == 5

    def test_tactical_intelligence_uses_lowest_hp(self):
        """Test that INT >= 10 uses lowest HP targeting."""
        strategy = SmartTargetingStrategy(intelligence=12, retaliation_weight=0)
        targets = [
            MockCharacter("Fighter", 20, 30),
            MockCharacter("Wizard", 5, 15),
            MockCharacter("Rogue", 10, 20),
        ]

        target = strategy.select_target(targets)

        assert target.name == "Wizard"
        assert target.current_hp == 5

    def test_intelligence_boundary_at_4(self):
        """Test INT exactly at bestial threshold (4) uses random."""
        strategy = SmartTargetingStrategy(intelligence=INT_BESTIAL_MAX, retaliation_weight=0)
        targets = [
            MockCharacter("Fighter", 20, 30),
            MockCharacter("Wizard", 5, 15),
        ]

        # INT 4 should use random - run multiple times to verify not always picking lowest
        selection_counts = {target.name: 0 for target in targets}
        for _ in range(100):
            target = strategy.select_target(targets)
            selection_counts[target.name] += 1

        # Should have some distribution (not 100% Wizard like lowest HP)
        assert selection_counts["Fighter"] > 0

    def test_intelligence_boundary_at_5(self):
        """Test INT 5 uses lowest HP (basic tactics)."""
        strategy = SmartTargetingStrategy(intelligence=5, retaliation_weight=0)
        targets = [
            MockCharacter("Fighter", 20, 30),
            MockCharacter("Wizard", 5, 15),
        ]

        # INT 5 should consistently pick lowest HP
        for _ in range(10):
            target = strategy.select_target(targets)
            assert target.name == "Wizard"

    # --- Retaliation Tests ---

    def test_retaliation_against_recent_attacker(self):
        """Test that creature retaliates against who recently attacked them."""
        recent_attacker = RecentAttacker(attacker_name="Fighter", damage_dealt=10)
        # Use 100% retaliation to make test deterministic
        strategy = SmartTargetingStrategy(
            intelligence=7, recent_attacker=recent_attacker, retaliation_weight=1.0
        )
        targets = [
            MockCharacter("Fighter", 20, 30),  # Recent attacker
            MockCharacter("Wizard", 5, 15),  # Lowest HP (would normally be targeted)
            MockCharacter("Rogue", 10, 20),
        ]

        target = strategy.select_target(targets)

        # Should retaliate against Fighter, not target lowest HP Wizard
        assert target.name == "Fighter"

    def test_no_retaliation_when_weight_zero(self):
        """Test no retaliation when weight is 0."""
        recent_attacker = RecentAttacker(attacker_name="Fighter", damage_dealt=10)
        strategy = SmartTargetingStrategy(
            intelligence=7, recent_attacker=recent_attacker, retaliation_weight=0
        )
        targets = [
            MockCharacter("Fighter", 20, 30),
            MockCharacter("Wizard", 5, 15),
        ]

        # Should always target lowest HP, never retaliate
        for _ in range(10):
            target = strategy.select_target(targets)
            assert target.name == "Wizard"

    def test_retaliation_fallback_when_attacker_not_in_targets(self):
        """Test fallback to base behavior when attacker is dead/not available."""
        recent_attacker = RecentAttacker(attacker_name="Cleric", damage_dealt=5)
        strategy = SmartTargetingStrategy(
            intelligence=7, recent_attacker=recent_attacker, retaliation_weight=1.0
        )
        targets = [
            MockCharacter("Fighter", 20, 30),
            MockCharacter("Wizard", 5, 15),  # Cleric not in targets
        ]

        target = strategy.select_target(targets)

        # Cleric not available, should fall back to lowest HP
        assert target.name == "Wizard"

    def test_retaliation_case_insensitive(self):
        """Test that attacker name matching is case-insensitive."""
        recent_attacker = RecentAttacker(attacker_name="FIGHTER", damage_dealt=10)
        strategy = SmartTargetingStrategy(
            intelligence=7, recent_attacker=recent_attacker, retaliation_weight=1.0
        )
        targets = [
            MockCharacter("Fighter", 20, 30),  # Different case
            MockCharacter("Wizard", 5, 15),
        ]

        target = strategy.select_target(targets)

        assert target.name == "Fighter"

    def test_bestial_high_retaliation_chance(self):
        """Test that bestial creatures have high retaliation by default."""
        strategy = SmartTargetingStrategy(intelligence=3)

        assert strategy.retaliation_weight == SmartTargetingStrategy.BESTIAL_RETALIATION_CHANCE
        assert strategy.retaliation_weight == 0.70

    def test_basic_tactics_moderate_retaliation_chance(self):
        """Test that INT 5-9 has moderate retaliation by default."""
        strategy = SmartTargetingStrategy(intelligence=7)

        assert strategy.retaliation_weight == SmartTargetingStrategy.BASIC_RETALIATION_CHANCE
        assert strategy.retaliation_weight == 0.40

    def test_tactical_low_retaliation_chance(self):
        """Test that INT >= 10 has lower retaliation by default."""
        strategy = SmartTargetingStrategy(intelligence=12)

        assert strategy.retaliation_weight == SmartTargetingStrategy.TACTICAL_RETALIATION_CHANCE
        assert strategy.retaliation_weight == 0.20

    def test_custom_retaliation_weight_override(self):
        """Test that custom retaliation weight overrides default."""
        strategy = SmartTargetingStrategy(intelligence=3, retaliation_weight=0.5)

        # Should use custom value, not bestial default
        assert strategy.retaliation_weight == 0.5

    # --- Edge Cases ---

    def test_single_target(self):
        """Test with only one target available."""
        strategy = SmartTargetingStrategy(intelligence=7)
        targets = [MockCharacter("Fighter", 20, 30)]

        target = strategy.select_target(targets)

        assert target.name == "Fighter"

    def test_empty_targets_raises_error(self):
        """Test that empty target list raises ValueError."""
        strategy = SmartTargetingStrategy(intelligence=7)
        targets = []

        with pytest.raises(ValueError, match="Cannot select target from empty list"):
            strategy.select_target(targets)

    def test_no_recent_attacker(self):
        """Test behavior when no recent attacker info."""
        strategy = SmartTargetingStrategy(intelligence=7, recent_attacker=None)
        targets = [
            MockCharacter("Fighter", 20, 30),
            MockCharacter("Wizard", 5, 15),
        ]

        target = strategy.select_target(targets)

        # Should use base behavior (lowest HP for INT 7)
        assert target.name == "Wizard"


class TestGetStrategyForIntelligence:
    """Test cases for factory function."""

    def test_returns_smart_targeting_strategy(self):
        """Test that factory returns SmartTargetingStrategy."""
        strategy = get_strategy_for_intelligence(intelligence=7)

        assert isinstance(strategy, SmartTargetingStrategy)

    def test_passes_intelligence_to_strategy(self):
        """Test that intelligence is passed to strategy."""
        strategy = get_strategy_for_intelligence(intelligence=12)

        assert strategy.intelligence == 12

    def test_passes_recent_attacker_to_strategy(self):
        """Test that recent attacker info is passed."""
        attacker = RecentAttacker(attacker_name="Fighter", damage_dealt=5)
        strategy = get_strategy_for_intelligence(intelligence=7, recent_attacker=attacker)

        assert strategy.recent_attacker == attacker

    def test_passes_custom_retaliation_weight(self):
        """Test that custom retaliation weight is passed."""
        strategy = get_strategy_for_intelligence(intelligence=7, retaliation_weight=0.8)

        assert strategy.retaliation_weight == 0.8


class TestRecentAttacker:
    """Test cases for RecentAttacker dataclass."""

    def test_creation(self):
        """Test basic creation of RecentAttacker."""
        attacker = RecentAttacker(attacker_name="Fighter", damage_dealt=15)

        assert attacker.attacker_name == "Fighter"
        assert attacker.damage_dealt == 15
        assert attacker.rounds_ago == 0  # Default value

    def test_with_rounds_ago(self):
        """Test RecentAttacker with rounds_ago specified."""
        attacker = RecentAttacker(attacker_name="Wizard", damage_dealt=8, rounds_ago=2)

        assert attacker.attacker_name == "Wizard"
        assert attacker.damage_dealt == 8
        assert attacker.rounds_ago == 2
