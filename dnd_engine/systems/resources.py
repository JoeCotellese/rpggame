# ABOUTME: Generic resource pool system for tracking limited-use class abilities
# ABOUTME: Manages resources like spell slots, ki points, rage uses, and bardic inspiration

from dataclasses import dataclass
from typing import Optional


@dataclass
class ResourcePool:
    """
    Generic resource pool for tracking limited-use abilities.

    Examples:
    - Spell slots: name="1st level slots", current=2, maximum=2
    - Ki points: name="ki", current=3, maximum=3
    - Rage: name="rage", current=2, maximum=2
    - Action Surge: name="action_surge", current=1, maximum=1
    """
    name: str
    current: int
    maximum: int
    recovery_type: str  # "short_rest", "long_rest", "daily", "permanent"

    def use(self, amount: int = 1) -> bool:
        """
        Use resources from the pool.

        Args:
            amount: Number of resources to use (default 1)

        Returns:
            True if successful, False if insufficient resources or invalid amount
        """
        if amount <= 0:
            return False
        if self.current >= amount:
            self.current -= amount
            return True
        return False

    def recover(self, amount: Optional[int] = None) -> int:
        """
        Recover resources. If amount is None, recover all.

        Args:
            amount: Number of resources to recover. If None, recovers all to maximum.

        Returns:
            Amount actually recovered
        """
        if amount is None:
            amount = self.maximum - self.current

        recovered = min(amount, self.maximum - self.current)
        self.current += recovered
        return recovered

    def is_available(self, amount: int = 1) -> bool:
        """
        Check if resource is available to use.

        Args:
            amount: Number of resources to check for (default 1)

        Returns:
            True if sufficient resources are available
        """
        return self.current >= amount

    def is_empty(self) -> bool:
        """
        Check if resource pool is depleted.

        Returns:
            True if no resources remain
        """
        return self.current == 0

    def is_full(self) -> bool:
        """
        Check if resource pool is at maximum.

        Returns:
            True if current equals maximum
        """
        return self.current == self.maximum

    def __str__(self) -> str:
        """String representation of the resource pool"""
        return f"{self.name}: {self.current}/{self.maximum}"
