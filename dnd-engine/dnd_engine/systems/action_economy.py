# ABOUTME: Action economy tracking for D&D 5E combat turns
# ABOUTME: Manages available actions, bonus actions, and free object interactions per turn

from dataclasses import dataclass
from enum import Enum


class ActionType(Enum):
    """
    Types of actions available during a combat turn in D&D 5E.

    Each turn, a character can take:
    - One ACTION (attack, cast spell, use item, etc.)
    - One BONUS_ACTION (if they have an ability that uses it)
    - One FREE_OBJECT interaction (draw weapon, open door, etc.)
    - Any number of NO_ACTION activities (dropping items, speaking, etc.)
    """

    ACTION = "action"
    BONUS_ACTION = "bonus_action"
    FREE_OBJECT = "free_object"
    NO_ACTION = "no_action"


@dataclass
class TurnState:
    """
    Tracks available actions for a single combat turn.

    D&D 5E action economy rules:
    - Each turn gets: 1 action, 1 bonus action, 1 free object interaction
    - Actions are consumed when used
    - All actions reset at the start of the next turn
    - Movement is tracked per turn (typically 30 ft, varies by creature speed)
    """

    action_available: bool = True
    bonus_action_available: bool = True
    free_object_interaction_used: bool = False
    movement_remaining: int = 30  # Movement in feet (5 ft = 1 grid square)

    def consume_action(self, action_type: ActionType) -> bool:
        """
        Attempt to consume an action.

        Args:
            action_type: The type of action to consume

        Returns:
            True if action was available and consumed, False if unavailable

        Example:
            >>> turn = TurnState()
            >>> turn.consume_action(ActionType.ACTION)
            True
            >>> turn.consume_action(ActionType.ACTION)  # Already used
            False
        """
        if action_type == ActionType.ACTION:
            if self.action_available:
                self.action_available = False
                return True
            return False

        elif action_type == ActionType.BONUS_ACTION:
            if self.bonus_action_available:
                self.bonus_action_available = False
                return True
            return False

        elif action_type == ActionType.FREE_OBJECT:
            if not self.free_object_interaction_used:
                self.free_object_interaction_used = True
                return True
            return False

        elif action_type == ActionType.NO_ACTION:
            # NO_ACTION activities are always available
            return True

        return False

    def consume_movement(self, feet: int = 5) -> bool:
        """
        Consume movement from remaining movement pool.

        Args:
            feet: Amount of movement to consume (default 5 ft = 1 grid square)

        Returns:
            True if movement was available and consumed, False if insufficient

        Example:
            >>> turn = TurnState(movement_remaining=30)
            >>> turn.consume_movement(5)  # Move 1 square
            True
            >>> turn.movement_remaining
            25
        """
        if self.movement_remaining >= feet:
            self.movement_remaining -= feet
            return True
        return False

    def is_action_available(self, action_type: ActionType) -> bool:
        """
        Check if an action type is available without consuming it.

        Args:
            action_type: The type of action to check

        Returns:
            True if the action is available
        """
        if action_type == ActionType.ACTION:
            return self.action_available
        elif action_type == ActionType.BONUS_ACTION:
            return self.bonus_action_available
        elif action_type == ActionType.FREE_OBJECT:
            return not self.free_object_interaction_used
        elif action_type == ActionType.NO_ACTION:
            return True
        return False

    def reset(self, speed: int = 30) -> None:
        """
        Reset all actions for a new turn.

        Called at the start of each turn to refresh available actions
        and movement.

        Args:
            speed: Creature's movement speed in feet (default 30)
        """
        self.action_available = True
        self.bonus_action_available = True
        self.free_object_interaction_used = False
        self.movement_remaining = speed

    def has_any_action(self) -> bool:
        """
        Check if any actions are still available.

        Returns:
            True if at least one action or bonus action is available
        """
        return self.action_available or self.bonus_action_available

    def __str__(self) -> str:
        """String representation of turn state"""
        parts = []
        if self.action_available:
            parts.append("Action")
        if self.bonus_action_available:
            parts.append("Bonus Action")
        if not self.free_object_interaction_used:
            parts.append("Free Object")

        action_str = ", ".join(parts) if parts else "No actions"
        return f"Available: {action_str} | Movement: {self.movement_remaining} ft"
