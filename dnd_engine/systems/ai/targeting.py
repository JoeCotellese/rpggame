# ABOUTME: Targeting strategy implementations for enemy AI.
# ABOUTME: Provides different algorithms for selecting which character to attack.

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass

# Intelligence thresholds for targeting behavior
INT_BESTIAL_MAX = 4  # INT <= 4: bestial/mindless (random targeting)
INT_TACTICAL_MIN = 10  # INT >= 10: tactical (strategic targeting)


@dataclass
class RecentAttacker:
    """Represents information about who recently attacked an enemy."""

    attacker_name: str
    damage_dealt: int
    rounds_ago: int = 0


class TargetingStrategy(ABC):
    """Base class for target selection strategies."""

    @abstractmethod
    def select_target(self, available_targets: list) -> object:
        """
        Select a target from the available targets.

        Args:
            available_targets: List of potential targets (Characters)

        Returns:
            The selected target
        """
        pass


class LowestHPStrategy(TargetingStrategy):
    """Always target the character with the lowest current HP."""

    def select_target(self, available_targets: list) -> object:
        """
        Select the target with the lowest current HP.

        Args:
            available_targets: List of potential targets (Characters)

        Returns:
            The character with the lowest current HP

        Raises:
            ValueError: If available_targets is empty
        """
        if not available_targets:
            raise ValueError("Cannot select target from empty list")

        return min(available_targets, key=lambda c: c.current_hp)


class RandomStrategy(TargetingStrategy):
    """Select a random target from available targets."""

    def select_target(self, available_targets: list) -> object:
        """
        Select a random target.

        Args:
            available_targets: List of potential targets (Characters)

        Returns:
            A randomly selected character

        Raises:
            ValueError: If available_targets is empty
        """
        if not available_targets:
            raise ValueError("Cannot select target from empty list")

        return random.choice(available_targets)


class SmartTargetingStrategy(TargetingStrategy):
    """
    Intelligence-based targeting that considers who recently attacked.

    Behavior varies by intelligence:
    - INT <= 4 (bestial): Random targeting with high retaliation chance (70%)
    - INT 5-9 (basic tactics): Lowest HP targeting with moderate retaliation (40%)
    - INT >= 10 (tactical): Lowest HP targeting with lower retaliation (20%)

    Retaliation means preferring to attack whoever damaged the creature last.
    """

    # Default retaliation weights by intelligence tier
    BESTIAL_RETALIATION_CHANCE = 0.70  # Instinctive response to threats
    BASIC_RETALIATION_CHANCE = 0.40  # Some tactical awareness
    TACTICAL_RETALIATION_CHANCE = 0.20  # Strategic over emotional

    def __init__(
        self,
        intelligence: int,
        recent_attacker: RecentAttacker | None = None,
        retaliation_weight: float | None = None,
    ):
        """
        Initialize smart targeting strategy.

        Args:
            intelligence: The creature's INT score (determines base behavior)
            recent_attacker: Info about who last damaged this creature
            retaliation_weight: Override default retaliation chance (0.0-1.0).
                               If None, uses intelligence-based default.
        """
        self.intelligence = intelligence
        self.recent_attacker = recent_attacker

        # Determine retaliation weight based on intelligence if not overridden
        if retaliation_weight is not None:
            self.retaliation_weight = retaliation_weight
        elif intelligence <= INT_BESTIAL_MAX:
            self.retaliation_weight = self.BESTIAL_RETALIATION_CHANCE
        elif intelligence >= INT_TACTICAL_MIN:
            self.retaliation_weight = self.TACTICAL_RETALIATION_CHANCE
        else:
            self.retaliation_weight = self.BASIC_RETALIATION_CHANCE

    def select_target(self, available_targets: list) -> object:
        """
        Select target based on intelligence and recent attackers.

        Args:
            available_targets: List of potential targets (Characters)

        Returns:
            The selected target

        Raises:
            ValueError: If available_targets is empty
        """
        if not available_targets:
            raise ValueError("Cannot select target from empty list")

        # Single target - no choice needed
        if len(available_targets) == 1:
            return available_targets[0]

        # Check for retaliation opportunity
        if self.recent_attacker and self.retaliation_weight > 0:
            # Find the recent attacker in available targets
            attacker_target = self._find_target_by_name(
                available_targets, self.recent_attacker.attacker_name
            )
            if attacker_target:
                # Roll for retaliation
                if random.random() < self.retaliation_weight:
                    return attacker_target

        # Base targeting behavior based on intelligence
        if self.intelligence <= INT_BESTIAL_MAX:
            # Bestial: random targeting
            return random.choice(available_targets)
        else:
            # Basic tactics and above: target lowest HP
            return min(available_targets, key=lambda c: c.current_hp)

    def _find_target_by_name(self, targets: list, name: str) -> object | None:
        """Find a target by name (case-insensitive)."""
        name_lower = name.lower()
        for target in targets:
            if target.name.lower() == name_lower:
                return target
        return None


def get_strategy_for_intelligence(
    intelligence: int,
    recent_attacker: RecentAttacker | None = None,
    retaliation_weight: float | None = None,
) -> TargetingStrategy:
    """
    Factory function to create appropriate targeting strategy based on intelligence.

    Args:
        intelligence: Creature's INT score
        recent_attacker: Info about who last attacked this creature
        retaliation_weight: Optional override for retaliation chance

    Returns:
        Appropriate TargetingStrategy instance
    """
    return SmartTargetingStrategy(
        intelligence=intelligence,
        recent_attacker=recent_attacker,
        retaliation_weight=retaliation_weight,
    )
