# ABOUTME: Initiative tracking system for turn-based combat
# ABOUTME: Manages turn order, round counting, and combatant lifecycle

from dataclasses import dataclass
from typing import List, Optional
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.creature import Creature


@dataclass
class InitiativeEntry:
    """
    Represents a combatant in the initiative order.

    Combines a creature with their initiative roll for sorting and tracking.
    """
    creature: Creature
    initiative_roll: int

    @property
    def initiative_total(self) -> int:
        """
        Calculate total initiative (roll + dexterity modifier).

        Returns:
            Total initiative value for sorting
        """
        return self.initiative_roll + self.creature.initiative_modifier

    def __str__(self) -> str:
        """String representation of the initiative entry"""
        return f"{self.creature.name}: {self.initiative_roll}+{self.creature.initiative_modifier}={self.initiative_total}"


class InitiativeTracker:
    """
    Manages initiative order and turn tracking for combat.

    D&D 5E initiative rules:
    - Each combatant rolls 1d20 + DEX modifier
    - Combatants act in order from highest to lowest initiative
    - Ties are broken by DEX modifier (higher goes first)
    - Turn order cycles through all combatants
    - Round increments when all combatants have acted
    """

    def __init__(self, dice_roller: Optional[DiceRoller] = None):
        """
        Initialize the initiative tracker.

        Args:
            dice_roller: DiceRoller instance (creates new one if not provided)
        """
        self.dice_roller = dice_roller if dice_roller is not None else DiceRoller()
        self.combatants: List[InitiativeEntry] = []
        self.current_turn_index: int = 0
        self.round_number: int = 0

    def add_combatant(self, creature: Creature) -> InitiativeEntry:
        """
        Add a combatant and roll their initiative.

        Automatically sorts the initiative order after adding.

        Args:
            creature: The creature to add to initiative

        Returns:
            The created InitiativeEntry
        """
        # Roll initiative (1d20 + DEX modifier)
        roll = self.dice_roller.roll("1d20")
        initiative_roll = roll.total

        entry = InitiativeEntry(creature=creature, initiative_roll=initiative_roll)
        self.combatants.append(entry)

        # Sort by initiative (highest first), ties broken by DEX modifier
        self._sort_initiative()

        return entry

    def remove_combatant(self, creature: Creature) -> None:
        """
        Remove a combatant from initiative (e.g., when defeated).

        Adjusts current turn index if necessary.

        Args:
            creature: The creature to remove
        """
        # Find the index of the combatant to remove
        remove_index = None
        for i, entry in enumerate(self.combatants):
            if entry.creature == creature:
                remove_index = i
                break

        if remove_index is None:
            return  # Not found, nothing to do

        # If removing a combatant before the current turn, adjust index
        if remove_index < self.current_turn_index:
            self.current_turn_index -= 1

        # If removing the current combatant at the end of the list, wrap around
        elif remove_index == self.current_turn_index and remove_index == len(self.combatants) - 1:
            self.current_turn_index = 0

        # Remove the combatant
        self.combatants.pop(remove_index)

        # Ensure index is valid
        if self.combatants and self.current_turn_index >= len(self.combatants):
            self.current_turn_index = 0

    def get_current_combatant(self) -> Optional[InitiativeEntry]:
        """
        Get the combatant whose turn it currently is.

        Returns:
            Current combatant's InitiativeEntry, or None if no combatants
        """
        if not self.combatants:
            return None

        return self.combatants[self.current_turn_index]

    def next_turn(self) -> None:
        """
        Advance to the next turn.

        Cycles through all combatants. When reaching the end,
        wraps back to the first combatant and increments the round.
        """
        if not self.combatants:
            return

        self.current_turn_index += 1

        # Wrap around to start of initiative order
        if self.current_turn_index >= len(self.combatants):
            self.current_turn_index = 0
            self.round_number += 1

    def get_all_combatants(self) -> List[InitiativeEntry]:
        """
        Get all combatants in initiative order.

        Returns:
            List of all InitiativeEntry objects
        """
        return self.combatants.copy()

    def is_combat_over(self) -> bool:
        """
        Check if combat should end.

        Combat ends when there are 0 or 1 combatants remaining.

        Returns:
            True if combat should end
        """
        return len(self.combatants) <= 1

    def _sort_initiative(self) -> None:
        """
        Sort combatants by initiative order.

        Sorts by total initiative (descending), with ties broken by DEX modifier.
        """
        self.combatants.sort(
            key=lambda entry: (
                entry.initiative_total,
                entry.creature.initiative_modifier
            ),
            reverse=True
        )

    def __str__(self) -> str:
        """String representation of the initiative tracker"""
        if not self.combatants:
            return "Initiative: (no combatants)"

        lines = [f"Round {self.round_number} - Initiative Order:"]
        for i, entry in enumerate(self.combatants):
            marker = "→" if i == self.current_turn_index else " "
            lines.append(f"{marker} {entry}")

        return "\n".join(lines)
