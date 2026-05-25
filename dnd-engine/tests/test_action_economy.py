# ABOUTME: Unit tests for action economy tracking system
# ABOUTME: Tests action types, turn state, and integration with initiative tracker

import pytest

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.systems.action_economy import ActionType, TurnState
from dnd_engine.systems.initiative import InitiativeTracker


class TestActionType:
    """Test the ActionType enum"""

    def test_action_types_exist(self):
        """Test that all required action types are defined"""
        assert ActionType.ACTION
        assert ActionType.BONUS_ACTION
        assert ActionType.REACTION
        assert ActionType.FREE_OBJECT
        assert ActionType.NO_ACTION

    def test_action_type_values(self):
        """Test that action types have correct string values"""
        assert ActionType.ACTION.value == "action"
        assert ActionType.BONUS_ACTION.value == "bonus_action"
        assert ActionType.REACTION.value == "reaction"
        assert ActionType.FREE_OBJECT.value == "free_object"
        assert ActionType.NO_ACTION.value == "no_action"


class TestTurnState:
    """Test the TurnState class"""

    def test_initial_state(self):
        """Test that new turn state has all actions available"""
        turn = TurnState()

        assert turn.action_available is True
        assert turn.bonus_action_available is True
        assert turn.reaction_available is True
        assert turn.free_object_interaction_used is False

    def test_consume_action(self):
        """Test consuming the main action"""
        turn = TurnState()

        # First consumption should succeed
        result = turn.consume_action(ActionType.ACTION)
        assert result is True
        assert turn.action_available is False

        # Second consumption should fail
        result = turn.consume_action(ActionType.ACTION)
        assert result is False

    def test_consume_bonus_action(self):
        """Test consuming the bonus action"""
        turn = TurnState()

        # First consumption should succeed
        result = turn.consume_action(ActionType.BONUS_ACTION)
        assert result is True
        assert turn.bonus_action_available is False

        # Second consumption should fail
        result = turn.consume_action(ActionType.BONUS_ACTION)
        assert result is False

    def test_consume_reaction(self):
        """Test consuming the reaction slot"""
        turn = TurnState()

        # First consumption should succeed
        result = turn.consume_action(ActionType.REACTION)
        assert result is True
        assert turn.reaction_available is False

        # Second consumption should fail (one Reaction per round)
        result = turn.consume_action(ActionType.REACTION)
        assert result is False

    def test_consume_free_object(self):
        """Test consuming the free object interaction"""
        turn = TurnState()

        # First consumption should succeed
        result = turn.consume_action(ActionType.FREE_OBJECT)
        assert result is True
        assert turn.free_object_interaction_used is True

        # Second consumption should fail
        result = turn.consume_action(ActionType.FREE_OBJECT)
        assert result is False

    def test_consume_no_action(self):
        """Test that NO_ACTION is always available"""
        turn = TurnState()

        # Should always succeed, no matter how many times called
        for _ in range(10):
            result = turn.consume_action(ActionType.NO_ACTION)
            assert result is True

    def test_is_action_available(self):
        """Test checking action availability without consuming"""
        turn = TurnState()

        # All actions available initially
        assert turn.is_action_available(ActionType.ACTION) is True
        assert turn.is_action_available(ActionType.BONUS_ACTION) is True
        assert turn.is_action_available(ActionType.REACTION) is True
        assert turn.is_action_available(ActionType.FREE_OBJECT) is True
        assert turn.is_action_available(ActionType.NO_ACTION) is True

        # Consume action and verify
        turn.consume_action(ActionType.ACTION)
        assert turn.is_action_available(ActionType.ACTION) is False
        assert turn.is_action_available(ActionType.BONUS_ACTION) is True  # Still available
        assert turn.is_action_available(ActionType.REACTION) is True  # Still available

    def test_reset(self):
        """Test resetting all actions"""
        turn = TurnState()

        # Consume all actions
        turn.consume_action(ActionType.ACTION)
        turn.consume_action(ActionType.BONUS_ACTION)
        turn.consume_action(ActionType.REACTION)
        turn.consume_action(ActionType.FREE_OBJECT)

        # Verify all consumed
        assert turn.action_available is False
        assert turn.bonus_action_available is False
        assert turn.reaction_available is False
        assert turn.free_object_interaction_used is True

        # Reset
        turn.reset()

        # Verify all available again
        assert turn.action_available is True
        assert turn.bonus_action_available is True
        assert turn.reaction_available is True
        assert turn.free_object_interaction_used is False

    def test_has_any_action(self):
        """Test checking if any actions remain"""
        turn = TurnState()

        # Initially has actions
        assert turn.has_any_action() is True

        # Still has actions after consuming one
        turn.consume_action(ActionType.ACTION)
        assert turn.has_any_action() is True

        # No actions after consuming both
        turn.consume_action(ActionType.BONUS_ACTION)
        assert turn.has_any_action() is False

    def test_actions_are_independent(self):
        """Test that different action types don't affect each other"""
        turn = TurnState()

        # Consume main action
        turn.consume_action(ActionType.ACTION)

        # Bonus action and free object should still be available
        assert turn.is_action_available(ActionType.BONUS_ACTION) is True
        assert turn.is_action_available(ActionType.FREE_OBJECT) is True

        # Should be able to consume them
        assert turn.consume_action(ActionType.BONUS_ACTION) is True
        assert turn.consume_action(ActionType.FREE_OBJECT) is True

    def test_str_representation(self):
        """Test string representation of turn state"""
        turn = TurnState()

        # With all actions available
        str_repr = str(turn)
        assert "Action" in str_repr
        assert "Bonus Action" in str_repr
        assert "Reaction" in str_repr
        assert "Free Object" in str_repr

        # After consuming everything
        turn.consume_action(ActionType.ACTION)
        turn.consume_action(ActionType.BONUS_ACTION)
        turn.consume_action(ActionType.REACTION)
        turn.consume_action(ActionType.FREE_OBJECT)

        str_repr = str(turn)
        assert "No actions" in str_repr
        assert "Movement:" in str_repr


class TestInitiativeTrackerActions:
    """Test action tracking integration with InitiativeTracker"""

    def test_turn_states_created_for_combatants(self):
        """Test that turn states are created when adding combatants"""
        tracker = InitiativeTracker()
        abilities = Abilities(10, 10, 10, 10, 10, 10)

        hero = Creature("Hero", max_hp=20, ac=15, abilities=abilities)
        enemy = Creature("Goblin", max_hp=7, ac=15, abilities=abilities)

        tracker.add_combatant(hero)
        tracker.add_combatant(enemy)

        # Verify turn states exist (keys are creature instances, not names)
        assert hero in tracker.turn_states
        assert enemy in tracker.turn_states

        # Verify they are TurnState instances
        assert isinstance(tracker.turn_states[hero], TurnState)
        assert isinstance(tracker.turn_states[enemy], TurnState)

    def test_get_current_turn_state(self):
        """Test getting the turn state for the current combatant"""
        tracker = InitiativeTracker()
        abilities = Abilities(10, 10, 10, 10, 10, 10)

        hero = Creature("Hero", max_hp=20, ac=15, abilities=abilities)
        tracker.add_combatant(hero)

        # Get current turn state
        turn_state = tracker.get_current_turn_state()

        assert turn_state is not None
        assert isinstance(turn_state, TurnState)
        assert turn_state.action_available is True

    def test_turn_state_resets_on_new_turn(self):
        """Test that turn state resets when advancing to a new turn"""
        tracker = InitiativeTracker()
        abilities = Abilities(10, 10, 10, 10, 10, 10)

        hero = Creature("Hero", max_hp=20, ac=15, abilities=abilities)
        enemy = Creature("Goblin", max_hp=7, ac=15, abilities=abilities)

        tracker.add_combatant(hero)
        tracker.add_combatant(enemy)

        # Get first combatant's turn state and consume actions
        tracker.get_current_combatant()
        turn_state = tracker.get_current_turn_state()

        turn_state.consume_action(ActionType.ACTION)
        turn_state.consume_action(ActionType.BONUS_ACTION)

        assert turn_state.action_available is False
        assert turn_state.bonus_action_available is False

        # Advance turn
        tracker.next_turn()

        # Second combatant's turn state should be fresh
        second_turn_state = tracker.get_current_turn_state()
        assert second_turn_state.action_available is True
        assert second_turn_state.bonus_action_available is True

        # Advance back to first combatant
        tracker.next_turn()

        # First combatant's turn state should be reset
        first_turn_state_again = tracker.get_current_turn_state()
        assert first_turn_state_again.action_available is True
        assert first_turn_state_again.bonus_action_available is True

    def test_turn_state_removed_with_combatant(self):
        """Test that turn state is removed when combatant is removed"""
        tracker = InitiativeTracker()
        abilities = Abilities(10, 10, 10, 10, 10, 10)

        hero = Creature("Hero", max_hp=20, ac=15, abilities=abilities)
        enemy = Creature("Goblin", max_hp=7, ac=15, abilities=abilities)

        tracker.add_combatant(hero)
        tracker.add_combatant(enemy)

        assert enemy in tracker.turn_states

        # Remove goblin
        tracker.remove_combatant(enemy)

        # Turn state should be removed
        assert enemy not in tracker.turn_states

    def test_turn_state_persists_across_rounds(self):
        """Test that turn state is properly managed across multiple rounds"""
        tracker = InitiativeTracker()
        abilities = Abilities(10, 10, 10, 10, 10, 10)

        char1 = Creature("Fighter", max_hp=20, ac=15, abilities=abilities)
        char2 = Creature("Rogue", max_hp=15, ac=14, abilities=abilities)

        tracker.add_combatant(char1)
        tracker.add_combatant(char2)

        # Round 1 - First combatant
        turn1 = tracker.get_current_turn_state()
        turn1.consume_action(ActionType.ACTION)
        assert turn1.action_available is False

        tracker.next_turn()

        # Round 1 - Second combatant
        turn2 = tracker.get_current_turn_state()
        turn2.consume_action(ActionType.BONUS_ACTION)
        assert turn2.bonus_action_available is False

        tracker.next_turn()  # This should wrap and increment round

        # Round 2 - First combatant (should be reset)
        turn3 = tracker.get_current_turn_state()
        assert turn3.action_available is True
        assert turn3.bonus_action_available is True

        # Verify we're in round 2
        assert tracker.round_number == 1  # 0-indexed

    def test_empty_tracker_turn_state(self):
        """Test getting turn state from empty tracker"""
        tracker = InitiativeTracker()

        turn_state = tracker.get_current_turn_state()
        assert turn_state is None

    def test_reaction_resets_when_creatures_turn_comes_around(self):
        """Reaction slot resets on the reactor's own next turn (SRD)."""
        tracker = InitiativeTracker()
        abilities = Abilities(10, 10, 10, 10, 10, 10)

        hero = Creature("Hero", max_hp=20, ac=15, abilities=abilities)
        enemy = Creature("Goblin", max_hp=7, ac=15, abilities=abilities)

        tracker.add_combatant(hero)
        tracker.add_combatant(enemy)

        # Consume reaction on whichever creature is up first.
        first_state = tracker.get_current_turn_state()
        assert first_state.consume_action(ActionType.REACTION) is True
        assert first_state.reaction_available is False

        # Advancing to the *other* creature must not refill our slot.
        tracker.next_turn()
        # The reference to first_state is the same instance held in
        # tracker.turn_states[first_creature]; it must still be empty.
        assert first_state.reaction_available is False

        # Round-trip back to the original creature; reset must refill it.
        tracker.next_turn()
        assert first_state.reaction_available is True


class TestMovementTracking:
    """Test movement tracking in TurnState and InitiativeTracker"""

    def test_initial_movement(self):
        """Test that TurnState initializes with default movement"""
        turn = TurnState()
        assert turn.movement_remaining == 30

    def test_custom_initial_movement(self):
        """Test that TurnState can be initialized with custom movement"""
        turn = TurnState(movement_remaining=25)
        assert turn.movement_remaining == 25

    def test_consume_movement_success(self):
        """Test successful movement consumption"""
        turn = TurnState(movement_remaining=30)
        result = turn.consume_movement(5)
        assert result is True
        assert turn.movement_remaining == 25

    def test_consume_movement_failure(self):
        """Test movement consumption fails when insufficient"""
        turn = TurnState(movement_remaining=5)
        result = turn.consume_movement(10)
        assert result is False
        assert turn.movement_remaining == 5  # Unchanged

    def test_consume_movement_exact(self):
        """Test consuming exactly remaining movement"""
        turn = TurnState(movement_remaining=10)
        result = turn.consume_movement(10)
        assert result is True
        assert turn.movement_remaining == 0

    def test_reset_restores_movement_with_speed(self):
        """Test that reset restores movement to creature's speed"""
        turn = TurnState(movement_remaining=5)
        turn.reset(speed=25)  # Dwarf speed
        assert turn.movement_remaining == 25

    def test_movement_str_representation(self):
        """Test that movement is shown in string representation"""
        turn = TurnState(movement_remaining=30)
        str_repr = str(turn)
        assert "Movement: 30 ft" in str_repr

    def test_initiative_tracker_initializes_movement_from_speed(self):
        """Test that InitiativeTracker uses creature's speed for movement"""
        tracker = InitiativeTracker()
        abilities = Abilities(10, 10, 10, 10, 10, 10)

        # Create creatures with different speeds
        human = Creature("Human Fighter", max_hp=20, ac=15, abilities=abilities, speed=30)
        dwarf = Creature("Dwarf Cleric", max_hp=20, ac=15, abilities=abilities, speed=25)

        tracker.add_combatant(human)
        tracker.add_combatant(dwarf)

        # Check movement is set from creature's speed
        assert tracker.turn_states[human].movement_remaining == 30
        assert tracker.turn_states[dwarf].movement_remaining == 25

    def test_initiative_tracker_resets_movement_with_speed(self):
        """Test that movement resets to creature's speed on turn advance"""
        tracker = InitiativeTracker()
        abilities = Abilities(10, 10, 10, 10, 10, 10)

        dwarf = Creature("Dwarf", max_hp=20, ac=15, abilities=abilities, speed=25)
        human = Creature("Human", max_hp=20, ac=15, abilities=abilities, speed=30)

        tracker.add_combatant(dwarf)
        tracker.add_combatant(human)

        # Get first combatant and their speed
        first_combatant = tracker.get_current_combatant()
        first_speed = first_combatant.creature.speed

        # Consume some movement for first combatant
        first_state = tracker.get_current_turn_state()
        first_state.consume_movement(10)
        assert first_state.movement_remaining == first_speed - 10

        # Advance to next turn
        tracker.next_turn()

        # Next combatant should have full movement based on their speed
        second_state = tracker.get_current_turn_state()
        second_combatant = tracker.get_current_combatant()
        assert second_state.movement_remaining == second_combatant.creature.speed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
