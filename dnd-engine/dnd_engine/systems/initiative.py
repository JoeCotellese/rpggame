# ABOUTME: Initiative tracking system for turn-based combat
# ABOUTME: Manages turn order, round counting, and combatant lifecycle

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from dnd_engine.core.creature import Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.systems.action_economy import TurnState

if TYPE_CHECKING:
    from dnd_engine.systems.time_manager import TimeManager


@dataclass
class InitiativeEntry:
    """
    Represents a combatant in the initiative order.

    Combines a creature with their initiative roll for sorting and tracking.
    Also includes display metadata like combat numbers for duplicate enemy names.
    """

    creature: Creature
    initiative_roll: int
    combat_number: int | None = None  # Assigned for enemies with duplicate names
    display_name: str | None = None  # Full display name (e.g., "Goblin 2")

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
        name = self.display_name if self.display_name else self.creature.name
        return f"{name}: {self.initiative_roll}+{self.creature.initiative_modifier}={self.initiative_total}"


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

    def __init__(
        self, dice_roller: DiceRoller | None = None, time_manager: Optional["TimeManager"] = None
    ):
        """
        Initialize the initiative tracker.

        Args:
            dice_roller: DiceRoller instance (creates new one if not provided)
            time_manager: TimeManager instance for tracking combat time (optional)
        """
        self.dice_roller = dice_roller if dice_roller is not None else DiceRoller()
        self.time_manager = time_manager
        self.combatants: list[InitiativeEntry] = []
        self.current_turn_index: int = 0
        self.round_number: int = 0
        self.total_turns_taken: int = 0  # Track total number of turns for narrative context
        self.turn_states: dict[
            Creature, TurnState
        ] = {}  # Maps creature instance to their turn state
        # LIFO stack of suspended turn indices. Pushed by
        # pause_for_reaction so that a Reaction firing mid-turn can
        # treat the reactor as the current combatant for the duration
        # of its handler, then resume the interrupted turn.
        self._pause_stack: list[int] = []

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

        # Initialize turn state for this combatant with their movement speed
        self.turn_states[creature] = TurnState(movement_remaining=creature.speed)

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
        removed_entry = self.combatants.pop(remove_index)

        # Remove their turn state
        if removed_entry.creature in self.turn_states:
            del self.turn_states[removed_entry.creature]

        # Ensure index is valid
        if self.combatants and self.current_turn_index >= len(self.combatants):
            self.current_turn_index = 0

        # Reset turn state for the new current combatant
        # This handles the case where removing a combatant shifts us to a different turn
        current = self.get_current_combatant()
        if current and current.creature in self.turn_states:
            self.turn_states[current.creature].reset(speed=current.creature.speed)
            self._expire_per_turn_action_state(current.creature)

    def get_current_combatant(self) -> InitiativeEntry | None:
        """
        Get the combatant whose turn it currently is.

        Returns:
            Current combatant's InitiativeEntry, or None if no combatants
        """
        if not self.combatants:
            return None

        return self.combatants[self.current_turn_index]

    def get_current_turn_state(self) -> TurnState | None:
        """
        Get the turn state for the current combatant.

        Returns:
            TurnState for the current combatant, or None if no combatants
        """
        current = self.get_current_combatant()
        if current is None:
            return None

        return self.turn_states.get(current.creature)

    def next_turn(self) -> None:
        """
        Advance to the next turn.

        Cycles through all combatants. When reaching the end,
        wraps back to the first combatant and increments the round.
        Resets actions for the new turn.
        """
        if not self.combatants:
            return

        self.current_turn_index += 1
        self.total_turns_taken += 1

        # Wrap around to start of initiative order
        if self.current_turn_index >= len(self.combatants):
            self.current_turn_index = 0
            self.round_number += 1

            # Advance effects for combat round (6 seconds = 0.1 minutes)
            if self.time_manager:
                # Advance round-based effects (Shield: 1 round)
                self.time_manager.advance_round(1)
                # Advance time-based effects (Mage Armor: 8 hours)
                self.time_manager.advance_time(0.1, reason="combat_round")

        # Reset actions and movement for the new turn
        current = self.get_current_combatant()
        if current and current.creature in self.turn_states:
            self.turn_states[current.creature].reset(speed=current.creature.speed)
            self._expire_per_turn_action_state(current.creature)

    def _expire_per_turn_action_state(self, actor: Creature) -> None:
        """Expire SRD "until the start of your next turn" benefits.

        Called when ``actor``'s own next turn begins. Two cleanups:

        - Dodge (SRD § Actions › Dodge): the dodger's ``is_dodging``
          flag is cleared. The benefit's window ends here regardless
          of whether any incoming attack consumed it.
        - Help (SRD § Actions › Help): any ally still carrying
          ``pending_help_from is actor`` (i.e., a help grant from this
          actor that the ally never spent on an attack or ability
          check) is cleared. Matches the SRD cap of "by the start of
          your next turn."
        """
        actor.is_dodging = False
        for entry in self.combatants:
            if entry.creature.pending_help_from is actor:
                entry.creature.pending_help_from = None

    def pause_for_reaction(self, reactor: Creature) -> None:
        """
        Suspend the current turn so a Reaction can resolve as ``reactor``.

        Pushes ``current_turn_index`` onto the pause stack and points
        the tracker at ``reactor``'s entry. Unlike ``next_turn``, this
        does NOT call ``TurnState.reset()`` — the SRD guarantees the
        reactor consumes only their Reaction slot, not a fresh turn,
        and the interrupted creature must resume on the same
        ``TurnState`` they had before the pause.

        Args:
            reactor: The creature whose Reaction is firing. Must be
                in the initiative order.

        Raises:
            ValueError: ``reactor`` is not a registered combatant.
        """
        reactor_index = next(
            (i for i, e in enumerate(self.combatants) if e.creature is reactor),
            None,
        )
        if reactor_index is None:
            raise ValueError(
                f"Cannot pause for reaction: {reactor.name!r} is not in initiative."
            )

        self._pause_stack.append(self.current_turn_index)
        self.current_turn_index = reactor_index

    def resume_paused_turn(self) -> None:
        """
        Restore the turn that was suspended by ``pause_for_reaction``.

        Pops the pause stack and restores ``current_turn_index``. Does
        not touch the resumed creature's ``TurnState`` — they pick
        back up wherever the Reaction interrupted them.

        Raises:
            RuntimeError: ``resume_paused_turn`` was called without a
                matching ``pause_for_reaction``.
        """
        if not self._pause_stack:
            raise RuntimeError(
                "resume_paused_turn called without a matching "
                "pause_for_reaction (pause stack is empty)."
            )
        self.current_turn_index = self._pause_stack.pop()

    @property
    def is_paused_for_reaction(self) -> bool:
        """True while at least one turn is suspended for a Reaction."""
        return bool(self._pause_stack)

    def get_all_combatants(self) -> list[InitiativeEntry]:
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
            key=lambda entry: (entry.initiative_total, entry.creature.initiative_modifier),
            reverse=True,
        )

    def assign_combat_numbers(self, player_creatures: list[Creature]) -> None:
        """
        Assign combat numbers to enemies with duplicate names.

        Players don't get numbers - only enemies do. This creates display
        names like "Goblin 1", "Goblin 2", etc.

        Args:
            player_creatures: List of player character creatures (won't get numbers)
        """
        # Track count per enemy name
        name_counts: dict[str, int] = {}
        name_current: dict[str, int] = {}

        # First pass: count how many of each enemy name
        for entry in self.combatants:
            if entry.creature not in player_creatures:
                name = entry.creature.name
                name_counts[name] = name_counts.get(name, 0) + 1

        # Second pass: assign numbers and display names
        for entry in self.combatants:
            if entry.creature in player_creatures:
                # Player character - no number
                entry.combat_number = None
                entry.display_name = entry.creature.name
            else:
                # Enemy - assign number
                name = entry.creature.name
                name_current[name] = name_current.get(name, 0) + 1
                entry.combat_number = name_current[name]
                entry.display_name = f"{name} {entry.combat_number}"

    def find_combatant_by_reference(
        self, ref: str, player_creatures: list[Creature] | None = None
    ) -> InitiativeEntry | None:
        """
        Find a combatant by various reference formats.

        Supports:
        - Pure number: "2" -> enemy with combat number 2
        - Name with number: "goblin 2" -> enemy named "Goblin" with number 2
        - Just name: "frodo" -> character named "Frodo"

        Args:
            ref: The reference string (case-insensitive)
            player_creatures: Optional list of player creatures to help disambiguate

        Returns:
            The matching InitiativeEntry, or None if not found
        """
        ref = ref.strip().lower()

        # Try to parse as pure number first
        try:
            num = int(ref)
            for entry in self.combatants:
                if entry.combat_number == num and entry.creature.is_alive:
                    return entry
            return None
        except ValueError:
            pass

        # Try "name number" format (e.g., "goblin 2")
        parts = ref.split()
        if len(parts) >= 2:
            try:
                num = int(parts[-1])
                name_part = " ".join(parts[:-1])
                for entry in self.combatants:
                    if (
                        entry.combat_number == num
                        and entry.creature.name.lower() == name_part
                        and entry.creature.is_alive
                    ):
                        return entry
            except ValueError:
                pass

        # Try exact name match (for players or when there's only one enemy with that name)
        for entry in self.combatants:
            if entry.creature.name.lower() == ref and entry.creature.is_alive:
                return entry

        return None

    def __str__(self) -> str:
        """String representation of the initiative tracker"""
        if not self.combatants:
            return "Initiative: (no combatants)"

        lines = [f"Round {self.round_number} - Initiative Order:"]
        for i, entry in enumerate(self.combatants):
            marker = "→" if i == self.current_turn_index else " "
            lines.append(f"{marker} {entry}")

        return "\n".join(lines)
