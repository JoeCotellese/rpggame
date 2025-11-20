# ABOUTME: Unit tests for the initiative system
# ABOUTME: Tests turn order tracking, round management, and combatant removal

import pytest
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.systems.initiative import InitiativeTracker, InitiativeEntry


class TestInitiativeTracker:
    """Test the InitiativeTracker class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.roller = DiceRoller(seed=42)
        self.tracker = InitiativeTracker(self.roller)

        # Create test creatures
        self.fighter_abilities = Abilities(
            strength=16,
            dexterity=14,  # +2
            constitution=15,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        self.fighter = Creature(
            name="Fighter",
            max_hp=20,
            ac=16,
            abilities=self.fighter_abilities
        )

        self.goblin_abilities = Abilities(
            strength=8,
            dexterity=14,  # +2
            constitution=10,
            intelligence=10,
            wisdom=8,
            charisma=8
        )
        self.goblin = Creature(
            name="Goblin",
            max_hp=7,
            ac=15,
            abilities=self.goblin_abilities
        )

        self.wizard_abilities = Abilities(
            strength=8,
            dexterity=16,  # +3
            constitution=12,
            intelligence=16,
            wisdom=12,
            charisma=10
        )
        self.wizard = Creature(
            name="Wizard",
            max_hp=15,
            ac=13,
            abilities=self.wizard_abilities
        )

    def test_tracker_creation(self):
        """Test creating an initiative tracker"""
        assert self.tracker.current_turn_index == 0
        assert self.tracker.round_number == 0
        assert len(self.tracker.combatants) == 0

    def test_add_combatant(self):
        """Test adding a combatant and rolling initiative"""
        self.tracker.add_combatant(self.fighter)

        assert len(self.tracker.combatants) == 1
        assert self.tracker.combatants[0].creature == self.fighter
        assert self.tracker.combatants[0].initiative_roll >= 1
        assert self.tracker.combatants[0].initiative_roll <= 20

    def test_add_multiple_combatants(self):
        """Test adding multiple combatants"""
        self.tracker.add_combatant(self.fighter)
        self.tracker.add_combatant(self.goblin)
        self.tracker.add_combatant(self.wizard)

        assert len(self.tracker.combatants) == 3

    def test_combatants_sorted_by_initiative(self):
        """Test that combatants are sorted by initiative (highest first)"""
        # Add combatants multiple times to test sorting
        for _ in range(5):
            tracker = InitiativeTracker()
            tracker.add_combatant(self.fighter)
            tracker.add_combatant(self.goblin)
            tracker.add_combatant(self.wizard)

            # Check that they're sorted (highest initiative first)
            for i in range(len(tracker.combatants) - 1):
                current = tracker.combatants[i]
                next_one = tracker.combatants[i + 1]

                current_total = current.initiative_roll + current.creature.initiative_modifier
                next_total = next_one.initiative_roll + next_one.creature.initiative_modifier

                assert current_total >= next_total

    def test_initiative_ties_broken_by_dex_modifier(self):
        """Test that ties are broken by dexterity modifier"""
        # Create creatures with same DEX to potentially tie
        creature1 = Creature("A", 10, 10, Abilities(10, 14, 10, 10, 10, 10))  # DEX +2
        creature2 = Creature("B", 10, 10, Abilities(10, 16, 10, 10, 10, 10))  # DEX +3

        # Use seeded roller to force same roll
        tracker = InitiativeTracker(DiceRoller(seed=100))
        tracker.add_combatant(creature1)

        # Reset seed to get same roll
        tracker.dice_roller = DiceRoller(seed=100)
        tracker.add_combatant(creature2)

        # If they rolled the same, higher DEX should be first
        if tracker.combatants[0].initiative_roll == tracker.combatants[1].initiative_roll:
            assert tracker.combatants[0].creature.initiative_modifier >= tracker.combatants[1].creature.initiative_modifier

    def test_get_current_combatant(self):
        """Test getting the current combatant"""
        self.tracker.add_combatant(self.fighter)
        self.tracker.add_combatant(self.goblin)

        current = self.tracker.get_current_combatant()
        assert current is not None
        assert current.creature in [self.fighter, self.goblin]

    def test_next_turn(self):
        """Test advancing to the next turn"""
        self.tracker.add_combatant(self.fighter)
        self.tracker.add_combatant(self.goblin)
        self.tracker.add_combatant(self.wizard)

        first = self.tracker.get_current_combatant()
        assert self.tracker.current_turn_index == 0

        self.tracker.next_turn()
        second = self.tracker.get_current_combatant()
        assert self.tracker.current_turn_index == 1
        assert first != second

    def test_next_turn_wraps_around(self):
        """Test that next_turn wraps back to the first combatant"""
        self.tracker.add_combatant(self.fighter)
        self.tracker.add_combatant(self.goblin)

        assert self.tracker.round_number == 0

        # Go through all combatants
        self.tracker.next_turn()  # Turn 1
        assert self.tracker.round_number == 0

        self.tracker.next_turn()  # Wrap to turn 0, increment round
        assert self.tracker.current_turn_index == 0
        assert self.tracker.round_number == 1

    def test_remove_combatant(self):
        """Test removing a combatant (e.g., when defeated)"""
        self.tracker.add_combatant(self.fighter)
        self.tracker.add_combatant(self.goblin)
        self.tracker.add_combatant(self.wizard)

        assert len(self.tracker.combatants) == 3

        self.tracker.remove_combatant(self.goblin)

        assert len(self.tracker.combatants) == 2
        assert all(c.creature != self.goblin for c in self.tracker.combatants)

    def test_remove_combatant_adjusts_turn_index(self):
        """Test that removing a combatant before current turn adjusts index"""
        self.tracker.add_combatant(self.fighter)
        self.tracker.add_combatant(self.goblin)
        self.tracker.add_combatant(self.wizard)

        # Move to turn 2
        self.tracker.next_turn()
        self.tracker.next_turn()
        assert self.tracker.current_turn_index == 2

        # Remove combatant at index 0 (before current turn)
        combatant_to_remove = self.tracker.combatants[0].creature
        self.tracker.remove_combatant(combatant_to_remove)

        # Index should be adjusted down
        assert self.tracker.current_turn_index == 1

    def test_is_combat_over_no_combatants(self):
        """Test that combat is over when no combatants"""
        assert self.tracker.is_combat_over() is True

    def test_is_combat_over_one_combatant(self):
        """Test that combat is over with only one combatant"""
        self.tracker.add_combatant(self.fighter)
        assert self.tracker.is_combat_over() is True

    def test_is_combat_over_multiple_combatants(self):
        """Test that combat continues with multiple combatants"""
        self.tracker.add_combatant(self.fighter)
        self.tracker.add_combatant(self.goblin)
        assert self.tracker.is_combat_over() is False

    def test_get_all_combatants(self):
        """Test getting all combatants"""
        self.tracker.add_combatant(self.fighter)
        self.tracker.add_combatant(self.goblin)

        combatants = self.tracker.get_all_combatants()
        assert len(combatants) == 2
        assert all(isinstance(c, InitiativeEntry) for c in combatants)

    def test_initiative_total_calculation(self):
        """Test that initiative total is calculated correctly"""
        self.tracker.add_combatant(self.fighter)

        entry = self.tracker.combatants[0]
        expected_total = entry.initiative_roll + self.fighter.initiative_modifier
        assert entry.initiative_total == expected_total

    def test_empty_tracker_next_turn(self):
        """Test that next_turn handles empty tracker gracefully"""
        # Should not crash with empty tracker
        self.tracker.next_turn()
        assert self.tracker.current_turn_index == 0

    def test_empty_tracker_get_current(self):
        """Test that get_current_combatant returns None when empty"""
        current = self.tracker.get_current_combatant()
        assert current is None

    def test_multiple_enemies_same_name_turn_states(self):
        """Test that multiple enemies with the same name have independent turn states (Issue #89)"""
        # Create two goblins with identical names
        goblin1 = Creature(
            name="Goblin",
            max_hp=7,
            ac=15,
            abilities=Abilities(8, 14, 10, 10, 8, 8)
        )
        goblin2 = Creature(
            name="Goblin",
            max_hp=7,
            ac=15,
            abilities=Abilities(8, 14, 10, 10, 8, 8)
        )

        # Add both goblins to initiative
        self.tracker.add_combatant(goblin1)
        self.tracker.add_combatant(goblin2)
        self.tracker.add_combatant(self.fighter)

        # Verify both goblins have their own turn states
        assert len(self.tracker.turn_states) == 3
        assert goblin1 in self.tracker.turn_states
        assert goblin2 in self.tracker.turn_states
        assert self.fighter in self.tracker.turn_states

        # Verify the turn states are different objects
        assert self.tracker.turn_states[goblin1] is not self.tracker.turn_states[goblin2]

        # Verify actions can be tracked independently
        goblin1_state = self.tracker.turn_states[goblin1]
        goblin2_state = self.tracker.turn_states[goblin2]

        # Use an action on goblin1's turn state
        from dnd_engine.systems.action_economy import ActionType
        success = goblin1_state.consume_action(ActionType.ACTION)
        assert success is True
        assert goblin1_state.action_available is False
        assert goblin2_state.action_available is True  # goblin2's state should be unaffected

    def test_multiple_enemies_same_name_remove_one(self):
        """Test that removing one enemy with duplicate name doesn't affect the other"""
        # Create two goblins with identical names
        goblin1 = Creature(
            name="Goblin",
            max_hp=7,
            ac=15,
            abilities=Abilities(8, 14, 10, 10, 8, 8)
        )
        goblin2 = Creature(
            name="Goblin",
            max_hp=7,
            ac=15,
            abilities=Abilities(8, 14, 10, 10, 8, 8)
        )

        # Add both goblins
        self.tracker.add_combatant(goblin1)
        self.tracker.add_combatant(goblin2)

        assert len(self.tracker.combatants) == 2
        assert len(self.tracker.turn_states) == 2

        # Remove goblin1
        self.tracker.remove_combatant(goblin1)

        # goblin2 should still be in combat with its own turn state
        assert len(self.tracker.combatants) == 1
        assert len(self.tracker.turn_states) == 1
        assert goblin1 not in self.tracker.turn_states
        assert goblin2 in self.tracker.turn_states
        assert self.tracker.combatants[0].creature == goblin2


class TestInitiativeEntry:
    """Test the InitiativeEntry class"""

    def test_initiative_entry_creation(self):
        """Test creating an initiative entry"""
        abilities = Abilities(10, 14, 10, 10, 10, 10)  # DEX +2
        creature = Creature("Goblin", 7, 15, abilities)

        entry = InitiativeEntry(creature=creature, initiative_roll=15)

        assert entry.creature == creature
        assert entry.initiative_roll == 15
        assert entry.initiative_total == 17  # 15 + 2 (DEX mod)

    def test_initiative_entry_comparison(self):
        """Test that initiative entries can be compared for sorting"""
        abilities1 = Abilities(10, 14, 10, 10, 10, 10)  # DEX +2
        creature1 = Creature("A", 10, 10, abilities1)
        entry1 = InitiativeEntry(creature1, 15)

        abilities2 = Abilities(10, 16, 10, 10, 10, 10)  # DEX +3
        creature2 = Creature("B", 10, 10, abilities2)
        entry2 = InitiativeEntry(creature2, 12)

        # Entry1: 15+2=17, Entry2: 12+3=15
        # Entry1 should be "greater" (higher initiative comes first)
        assert entry1.initiative_total > entry2.initiative_total
