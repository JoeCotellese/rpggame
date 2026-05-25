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
    - One REACTION (Shield, Counterspell, Opportunity Attack, etc.) —
      fired in response to a trigger; one per round, resets at the
      start of the reactor's next turn
    - One FREE_OBJECT interaction (draw weapon, open door, etc.)
    - Any number of NO_ACTION activities (dropping items, speaking, etc.)
    """

    ACTION = "action"
    BONUS_ACTION = "bonus_action"
    REACTION = "reaction"
    FREE_OBJECT = "free_object"
    NO_ACTION = "no_action"


class Terrain(str, Enum):
    """
    Kinds of terrain a creature may move through, for movement-cost purposes.

    SRD: "Each foot of movement in difficult terrain costs 1 extra foot."
    So a 5-foot step through difficult terrain costs 10 feet of movement.
    """

    NORMAL = "normal"
    DIFFICULT = "difficult"


def cost_for(feet: int, terrain: Terrain) -> int:
    """
    Compute the movement-pool cost for traveling ``feet`` through ``terrain``.

    Difficult terrain costs 1 extra foot per foot moved (effectively 2x).
    Normal terrain costs exactly ``feet``.

    Args:
        feet: Distance the creature wants to travel, in feet.
        terrain: Terrain kind being traversed.

    Returns:
        The number of feet to deduct from the movement pool.
    """
    if terrain == Terrain.DIFFICULT:
        return feet * 2
    return feet


@dataclass
class TurnState:
    """
    Tracks available actions for a single combat turn.

    D&D 5E action economy rules:
    - Each turn gets: 1 action, 1 bonus action, 1 reaction, 1 free
      object interaction
    - Actions are consumed when used
    - The Reaction slot is per-round, not per-turn: it resets only
      when the reactor's own turn comes around again (SRD: "you can't
      take another one until the start of your next turn"). Because
      TurnState.reset() is invoked by InitiativeTracker.next_turn at
      the start of each creature's own turn, resetting the reaction
      slot there honors the once-per-round rule.
    - All other actions reset at the start of the next turn
    - Movement is tracked per turn (typically 30 ft, varies by creature speed)
    """

    action_available: bool = True
    bonus_action_available: bool = True
    reaction_available: bool = True
    free_object_interaction_used: bool = False
    movement_remaining: int = 30  # Movement in feet (5 ft = 1 grid square)
    speed: int = 30  # Cached effective Speed for this turn (feet). Used by
    # actions that scale to Speed: Dash adds it to the movement pool,
    # Stand Up costs half of it, Drop Prone is forbidden when it is 0.
    disengaged_this_turn: bool = False  # Set by the Disengage action;
    # consulted by the Opportunity Attack handler to suppress reactions
    # the actor's movement would otherwise provoke. Cleared by reset()
    # at the start of the actor's next turn — the SRD's "rest of the
    # turn" window naturally ends there.

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

        elif action_type == ActionType.REACTION:
            if self.reaction_available:
                self.reaction_available = False
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

    def consume_movement(
        self, feet: int = 5, terrain: Terrain = Terrain.NORMAL
    ) -> bool:
        """
        Consume movement from remaining movement pool.

        Args:
            feet: Amount of movement to consume (default 5 ft = 1 grid square)
            terrain: Terrain kind being traversed. Difficult terrain doubles
                the cost per foot (SRD: each foot in difficult terrain costs
                1 extra foot). Defaults to NORMAL so existing callers are
                unaffected.

        Returns:
            True if movement was available and consumed, False if insufficient.
            On insufficient movement, ``movement_remaining`` is NOT changed.

        Example:
            >>> turn = TurnState(movement_remaining=30)
            >>> turn.consume_movement(5)  # Move 1 square
            True
            >>> turn.movement_remaining
            25
            >>> turn.consume_movement(5, terrain=Terrain.DIFFICULT)
            True
            >>> turn.movement_remaining
            15
        """
        cost = cost_for(feet, terrain)
        if self.movement_remaining >= cost:
            self.movement_remaining -= cost
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
        elif action_type == ActionType.REACTION:
            return self.reaction_available
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
        self.reaction_available = True
        self.free_object_interaction_used = False
        self.movement_remaining = speed
        self.speed = speed
        self.disengaged_this_turn = False

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
        if self.reaction_available:
            parts.append("Reaction")
        if not self.free_object_interaction_used:
            parts.append("Free Object")

        action_str = ", ".join(parts) if parts else "No actions"
        return f"Available: {action_str} | Movement: {self.movement_remaining} ft"
