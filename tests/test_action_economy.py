# ABOUTME: Unit tests for action economy tracking system
# ABOUTME: Tests action types, turn state, and integration with initiative tracker

import pytest
from dnd_engine.systems.action_economy import ActionType, TurnState
from dnd_engine.systems.initiative import InitiativeTracker
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.core.dice import DiceRoller


class TestActionType:
    """Test the ActionType enum"""

    def test_action_types_exist(self):
        """Test that all required action types are defined"""
        assert ActionType.ACTION
        assert ActionType.BONUS_ACTION
        assert ActionType.FREE_OBJECT
        assert ActionType.NO_ACTION

    def test_action_type_values(self):
        """Test that action types have correct string values"""
        assert ActionType.ACTION.value == "action"
        assert ActionType.BONUS_ACTION.value == "bonus_action"
        assert ActionType.FREE_OBJECT.value == "free_object"
        assert ActionType.NO_ACTION.value == "no_action"


class TestTurnState:
    """Test the TurnState class"""

    def test_initial_state(self):
        """Test that new turn state has all actions available"""
        turn = TurnState()

        assert turn.action_available is True
        assert turn.bonus_action_available is True
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
        assert turn.is_action_available(ActionType.FREE_OBJECT) is True
        assert turn.is_action_available(ActionType.NO_ACTION) is True

        # Consume action and verify
        turn.consume_action(ActionType.ACTION)
        assert turn.is_action_available(ActionType.ACTION) is False
        assert turn.is_action_available(ActionType.BONUS_ACTION) is True  # Still available

    def test_reset(self):
        """Test resetting all actions"""
        turn = TurnState()

        # Consume all actions
        turn.consume_action(ActionType.ACTION)
        turn.consume_action(ActionType.BONUS_ACTION)
        turn.consume_action(ActionType.FREE_OBJECT)

        # Verify all consumed
        assert turn.action_available is False
        assert turn.bonus_action_available is False
        assert turn.free_object_interaction_used is True

        # Reset
        turn.reset()

        # Verify all available again
        assert turn.action_available is True
        assert turn.bonus_action_available is True
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
        assert "Free Object" in str_repr

        # After consuming everything
        turn.consume_action(ActionType.ACTION)
        turn.consume_action(ActionType.BONUS_ACTION)
        turn.consume_action(ActionType.FREE_OBJECT)

        str_repr = str(turn)
        assert "No actions remaining" in str_repr


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
        first_combatant = tracker.get_current_combatant()
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
