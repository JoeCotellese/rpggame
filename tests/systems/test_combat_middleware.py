# ABOUTME: Unit tests for combat middleware pattern components
# ABOUTME: Tests validation, logging, resource cleanup, and middleware chain execution

from unittest.mock import Mock, patch

import pytest

from dnd_engine.core.character import Character
from dnd_engine.core.game_state import GameState
from dnd_engine.systems.action_economy import ActionType, TurnState
from dnd_engine.systems.combat_middleware import (
    ActionEconomyMiddleware,
    ActionResult,
    CombatActionContext,
    CombatActionExecutor,
    LoggingMiddleware,
    ResourceCleanupMiddleware,
    TurnValidationMiddleware,
)


@pytest.fixture
def mock_game_state():
    """Create a mock game state for testing."""
    game_state = Mock(spec=GameState)
    game_state.in_combat = True
    game_state.initiative_tracker = Mock()
    game_state.event_bus = Mock()
    return game_state


@pytest.fixture
def mock_character():
    """Create a mock character for testing."""
    character = Mock(spec=Character)
    character.name = "TestHero"
    character.is_alive = True
    return character


@pytest.fixture
def mock_combatant(mock_character):
    """Create a mock combatant wrapper."""
    combatant = Mock()
    combatant.creature = mock_character
    return combatant


@pytest.fixture
def mock_turn_state():
    """Create a mock turn state."""
    turn_state = Mock(spec=TurnState)
    turn_state.is_action_available = Mock(return_value=True)
    turn_state.consume_action = Mock(return_value=True)
    return turn_state


class TestCombatActionContext:
    """Test the CombatActionContext data class."""

    def test_context_creation(self, mock_game_state, mock_character):
        """Test creating a combat action context."""
        context = CombatActionContext(
            game_state=mock_game_state,
            actor=mock_character,
            action_type=ActionType.ACTION,
            action_name="attack",
            details={"target": "goblin"}
        )

        assert context.game_state == mock_game_state
        assert context.actor == mock_character
        assert context.action_type == ActionType.ACTION
        assert context.action_name == "attack"
        assert context.details == {"target": "goblin"}
        assert context.result == ActionResult.SUCCESS
        assert context.error_message is None
        assert context.resources_consumed == []

    def test_context_with_resources(self, mock_game_state, mock_character):
        """Test context with pre-consumed resources."""
        resources = [("spell_slots_level_1", 1)]
        context = CombatActionContext(
            game_state=mock_game_state,
            actor=mock_character,
            action_type=ActionType.ACTION,
            action_name="cast_spell",
            details={},
            resources_consumed=resources
        )

        assert context.resources_consumed == resources


class TestTurnValidationMiddleware:
    """Test turn validation middleware."""

    def test_valid_turn(self, mock_game_state, mock_character, mock_combatant):
        """Test validation passes when it's the actor's turn."""
        mock_game_state.initiative_tracker.get_current_combatant.return_value = mock_combatant

        middleware = TurnValidationMiddleware()
        context = CombatActionContext(
            game_state=mock_game_state,
            actor=mock_character,
            action_type=ActionType.ACTION,
            action_name="attack",
            details={}
        )

        next_middleware = Mock(return_value=True)
        result = middleware.process(context, next_middleware)

        assert result is True
        assert context.result == ActionResult.SUCCESS
        assert context.error_message is None
        next_middleware.assert_called_once()

    def test_not_in_combat(self, mock_game_state, mock_character):
        """Test validation fails when not in combat."""
        mock_game_state.in_combat = False

        middleware = TurnValidationMiddleware()
        context = CombatActionContext(
            game_state=mock_game_state,
            actor=mock_character,
            action_type=ActionType.ACTION,
            action_name="attack",
            details={}
        )

        next_middleware = Mock()
        result = middleware.process(context, next_middleware)

        assert result is False
        assert context.result == ActionResult.FAILED
        assert "not in combat" in context.error_message.lower()
        next_middleware.assert_not_called()

    def test_wrong_turn(self, mock_game_state, mock_character):
        """Test validation fails when it's not the actor's turn."""
        other_character = Mock(spec=Character)
        other_character.name = "OtherHero"
        other_combatant = Mock()
        other_combatant.creature = other_character

        mock_game_state.initiative_tracker.get_current_combatant.return_value = other_combatant

        middleware = TurnValidationMiddleware()
        context = CombatActionContext(
            game_state=mock_game_state,
            actor=mock_character,
            action_type=ActionType.ACTION,
            action_name="attack",
            details={}
        )

        next_middleware = Mock()
        result = middleware.process(context, next_middleware)

        assert result is False
        assert context.result == ActionResult.FAILED
        assert "turn" in context.error_message.lower()
        next_middleware.assert_not_called()

    def test_actor_not_alive(self, mock_game_state, mock_character, mock_combatant):
        """Test validation fails when actor is not alive."""
        mock_character.is_alive = False
        mock_game_state.initiative_tracker.get_current_combatant.return_value = mock_combatant

        middleware = TurnValidationMiddleware()
        context = CombatActionContext(
            game_state=mock_game_state,
            actor=mock_character,
            action_type=ActionType.ACTION,
            action_name="attack",
            details={}
        )

        next_middleware = Mock()
        result = middleware.process(context, next_middleware)

        assert result is False
        assert context.result == ActionResult.FAILED
        assert "not conscious" in context.error_message.lower()
        next_middleware.assert_not_called()


class TestActionEconomyMiddleware:
    """Test action economy middleware."""

    def test_action_available(self, mock_game_state, mock_character, mock_turn_state):
        """Test action consumption when action is available."""
        mock_game_state.initiative_tracker.get_current_turn_state.return_value = mock_turn_state

        middleware = ActionEconomyMiddleware()
        context = CombatActionContext(
            game_state=mock_game_state,
            actor=mock_character,
            action_type=ActionType.ACTION,
            action_name="attack",
            details={}
        )

        next_middleware = Mock(return_value=True)
        result = middleware.process(context, next_middleware)

        assert result is True
        assert context.result == ActionResult.SUCCESS
        mock_turn_state.is_action_available.assert_called_once_with(ActionType.ACTION)
        mock_turn_state.consume_action.assert_called_once_with(ActionType.ACTION)
        next_middleware.assert_called_once()

    def test_action_not_available(self, mock_game_state, mock_character, mock_turn_state):
        """Test failure when action is not available."""
        mock_turn_state.is_action_available.return_value = False
        mock_game_state.initiative_tracker.get_current_turn_state.return_value = mock_turn_state

        middleware = ActionEconomyMiddleware()
        context = CombatActionContext(
            game_state=mock_game_state,
            actor=mock_character,
            action_type=ActionType.ACTION,
            action_name="attack",
            details={}
        )

        next_middleware = Mock()
        result = middleware.process(context, next_middleware)

        assert result is False
        assert context.result == ActionResult.FAILED
        assert "available" in context.error_message.lower()
        mock_turn_state.consume_action.assert_not_called()
        next_middleware.assert_not_called()

    def test_no_turn_state(self, mock_game_state, mock_character):
        """Test failure when turn state is unavailable."""
        mock_game_state.initiative_tracker.get_current_turn_state.return_value = None

        middleware = ActionEconomyMiddleware()
        context = CombatActionContext(
            game_state=mock_game_state,
            actor=mock_character,
            action_type=ActionType.ACTION,
            action_name="attack",
            details={}
        )

        next_middleware = Mock()
        result = middleware.process(context, next_middleware)

        assert result is False
        assert context.result == ActionResult.FAILED
        assert "turn state" in context.error_message.lower()
        next_middleware.assert_not_called()


class TestLoggingMiddleware:
    """Test logging middleware."""

    @patch('dnd_engine.utils.logging_config.get_logging_config')
    def test_logging_success(self, mock_get_logging, mock_game_state, mock_character):
        """Test action is logged when logging is available."""
        mock_logger = Mock()
        mock_get_logging.return_value = mock_logger

        middleware = LoggingMiddleware()
        context = CombatActionContext(
            game_state=mock_game_state,
            actor=mock_character,
            action_type=ActionType.ACTION,
            action_name="attack",
            details={"target": "goblin"}
        )

        next_middleware = Mock(return_value=True)
        result = middleware.process(context, next_middleware)

        assert result is True
        mock_logger.log_player_action.assert_called_once_with(
            character="TestHero",
            action="attack",
            details="target=goblin"
        )
        next_middleware.assert_called_once()

    @patch('dnd_engine.utils.logging_config.get_logging_config')
    def test_logging_not_configured(self, mock_get_logging, mock_game_state, mock_character):
        """Test middleware continues when logging is not configured."""
        mock_get_logging.return_value = None

        middleware = LoggingMiddleware()
        context = CombatActionContext(
            game_state=mock_game_state,
            actor=mock_character,
            action_type=ActionType.ACTION,
            action_name="attack",
            details={}
        )

        next_middleware = Mock(return_value=True)
        result = middleware.process(context, next_middleware)

        assert result is True
        next_middleware.assert_called_once()

    @patch('dnd_engine.utils.logging_config.get_logging_config')
    def test_logging_failure_doesnt_break_chain(self, mock_get_logging, mock_game_state, mock_character):
        """Test middleware continues even if logging throws exception."""
        mock_logger = Mock()
        mock_logger.log_player_action.side_effect = Exception("Logging failed")
        mock_get_logging.return_value = mock_logger

        middleware = LoggingMiddleware()
        context = CombatActionContext(
            game_state=mock_game_state,
            actor=mock_character,
            action_type=ActionType.ACTION,
            action_name="attack",
            details={}
        )

        next_middleware = Mock(return_value=True)
        result = middleware.process(context, next_middleware)

        # Should continue despite logging failure
        assert result is True
        next_middleware.assert_called_once()


class TestResourceCleanupMiddleware:
    """Test resource cleanup middleware."""

    def test_successful_action_no_refund(self, mock_game_state, mock_character):
        """Test resources are not refunded on successful action."""
        mock_pool = Mock()
        mock_pool.current = 5
        mock_character.get_resource_pool.return_value = mock_pool

        middleware = ResourceCleanupMiddleware()
        context = CombatActionContext(
            game_state=mock_game_state,
            actor=mock_character,
            action_type=ActionType.ACTION,
            action_name="cast_spell",
            details={},
            resources_consumed=[("spell_slots_level_1", 1)]
        )

        next_middleware = Mock(return_value=True)
        result = middleware.process(context, next_middleware)

        assert result is True
        assert context.result == ActionResult.SUCCESS
        # Resource should NOT be refunded
        assert mock_pool.current == 5
        next_middleware.assert_called_once()

    def test_failed_action_refunds_resources(self, mock_game_state, mock_character):
        """Test resources are refunded on failed action."""
        mock_pool = Mock()
        mock_pool.current = 5
        mock_character.get_resource_pool.return_value = mock_pool

        middleware = ResourceCleanupMiddleware()
        context = CombatActionContext(
            game_state=mock_game_state,
            actor=mock_character,
            action_type=ActionType.ACTION,
            action_name="cast_spell",
            details={},
            resources_consumed=[("spell_slots_level_1", 1)]
        )

        def fail_next(ctx, _):
            ctx.result = ActionResult.FAILED
            return False

        result = middleware.process(context, fail_next)

        assert result is False
        # Resource SHOULD be refunded
        assert mock_pool.current == 6
        mock_character.get_resource_pool.assert_called_once_with("spell_slots_level_1")

    def test_cancelled_action_refunds_resources(self, mock_game_state, mock_character):
        """Test resources are refunded on cancelled action."""
        mock_pool = Mock()
        mock_pool.current = 3
        mock_character.get_resource_pool.return_value = mock_pool

        middleware = ResourceCleanupMiddleware()
        context = CombatActionContext(
            game_state=mock_game_state,
            actor=mock_character,
            action_type=ActionType.ACTION,
            action_name="cast_spell",
            details={},
            resources_consumed=[("spell_slots_level_2", 1)]
        )

        def cancel_next(ctx, _):
            ctx.result = ActionResult.CANCELLED
            return False

        result = middleware.process(context, cancel_next)

        assert result is False
        # Resource SHOULD be refunded
        assert mock_pool.current == 4

    def test_multiple_resources_refunded(self, mock_game_state, mock_character):
        """Test multiple resources are refunded together."""
        mock_pool1 = Mock()
        mock_pool1.current = 5
        mock_pool2 = Mock()
        mock_pool2.current = 3

        def get_pool(name):
            if name == "resource1":
                return mock_pool1
            elif name == "resource2":
                return mock_pool2
            return None

        mock_character.get_resource_pool.side_effect = get_pool

        middleware = ResourceCleanupMiddleware()
        context = CombatActionContext(
            game_state=mock_game_state,
            actor=mock_character,
            action_type=ActionType.ACTION,
            action_name="use_item",
            details={},
            resources_consumed=[("resource1", 2), ("resource2", 1)]
        )

        def fail_next(ctx, _):
            ctx.result = ActionResult.FAILED
            return False

        middleware.process(context, fail_next)

        # Both resources should be refunded
        assert mock_pool1.current == 7  # 5 + 2
        assert mock_pool2.current == 4  # 3 + 1


class TestCombatActionExecutor:
    """Test the complete combat action executor with middleware chain."""

    def test_full_chain_success(self, mock_game_state, mock_character, mock_combatant, mock_turn_state):
        """Test a successful action through the full middleware chain."""
        mock_game_state.initiative_tracker.get_current_combatant.return_value = mock_combatant
        mock_game_state.initiative_tracker.get_current_turn_state.return_value = mock_turn_state

        executor = CombatActionExecutor(mock_game_state)

        action_executed = False

        def action_handler(ctx):
            nonlocal action_executed
            action_executed = True
            return True

        with patch('dnd_engine.utils.logging_config.get_logging_config', return_value=None):
            context = executor.execute(
                actor=mock_character,
                action_type=ActionType.ACTION,
                action_name="attack",
                action_handler=action_handler,
                target="goblin"
            )

        assert context.result == ActionResult.SUCCESS
        assert action_executed is True
        mock_turn_state.is_action_available.assert_called_once_with(ActionType.ACTION)
        mock_turn_state.consume_action.assert_called_once_with(ActionType.ACTION)

    def test_full_chain_turn_validation_failure(self, mock_game_state, mock_character):
        """Test action fails at turn validation."""
        mock_game_state.in_combat = False

        executor = CombatActionExecutor(mock_game_state)

        action_executed = False

        def action_handler(ctx):
            nonlocal action_executed
            action_executed = True
            return True

        context = executor.execute(
            actor=mock_character,
            action_type=ActionType.ACTION,
            action_name="attack",
            action_handler=action_handler
        )

        assert context.result == ActionResult.FAILED
        assert "not in combat" in context.error_message.lower()
        assert action_executed is False

    def test_full_chain_with_resource_refund(self, mock_game_state, mock_character, mock_combatant, mock_turn_state):
        """Test resource refund works through full chain."""
        mock_game_state.initiative_tracker.get_current_combatant.return_value = mock_combatant
        mock_game_state.initiative_tracker.get_current_turn_state.return_value = mock_turn_state

        mock_pool = Mock()
        mock_pool.current = 5
        mock_character.get_resource_pool.return_value = mock_pool

        executor = CombatActionExecutor(mock_game_state)

        def failing_handler(ctx):
            ctx.result = ActionResult.FAILED
            ctx.error_message = "Action failed"
            return False

        with patch('dnd_engine.utils.logging_config.get_logging_config', return_value=None):
            context = executor.execute(
                actor=mock_character,
                action_type=ActionType.ACTION,
                action_name="cast_spell",
                action_handler=failing_handler,
                resources_consumed=[("spell_slots_level_1", 1)]
            )

        assert context.result == ActionResult.FAILED
        # Spell slot should be refunded
        assert mock_pool.current == 6
