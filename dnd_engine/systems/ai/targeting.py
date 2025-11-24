# ABOUTME: Targeting strategy implementations for enemy AI.
# ABOUTME: Provides different algorithms for selecting which character to attack.

from abc import ABC, abstractmethod
from typing import List
import random


class TargetingStrategy(ABC):
    """Base class for target selection strategies."""

    @abstractmethod
    def select_target(self, available_targets: List) -> object:
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

    def select_target(self, available_targets: List) -> object:
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

    def select_target(self, available_targets: List) -> object:
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
