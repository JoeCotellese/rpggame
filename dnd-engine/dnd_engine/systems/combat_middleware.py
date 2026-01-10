# ABOUTME: Middleware pattern for combat action execution with validation, logging, and resource cleanup
# ABOUTME: Eliminates boilerplate from combat handlers via reusable middleware chain

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dnd_engine.core.character import Character
    from dnd_engine.game_state import GameState

from dnd_engine.systems.action_economy import ActionType


class ActionResult(Enum):
    """Result of a combat action execution."""

    SUCCESS = "success"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class CombatActionContext:
    """
    Context passed through middleware chain during combat action execution.

    Contains all state needed to validate, execute, and clean up a combat action.
    Middleware can inspect/modify this context as it passes through the chain.
    """

    game_state: "GameState"
    actor: "Character"  # Who is taking the action
    action_type: ActionType  # ACTION, BONUS_ACTION, etc.
    action_name: str  # "attack", "cast_spell", "use_item" for logging
    details: dict[str, Any]  # Action-specific data
    result: ActionResult = ActionResult.SUCCESS
    error_message: str | None = None

    # Resources to refund on failure/cancellation
    # Format: List of (resource_pool_name, amount) tuples
    resources_consumed: list[tuple[str, int]] = field(default_factory=list)


class CombatMiddleware(ABC):
    """
    Base class for combat action middleware.

    Middleware processes actions in a chain, each having the opportunity to:
    - Validate preconditions (turn validation, action economy)
    - Perform side effects (logging, resource tracking)
    - Short-circuit execution (return False to abort)
    - Clean up after execution (refund resources on failure)
    """

    @abstractmethod
    def process(self, context: CombatActionContext, next_middleware: Callable) -> bool:
        """
        Process the action context.

        Args:
            context: The action context containing all state
            next_middleware: Callable to invoke next middleware in chain

        Returns:
            True to continue, False to abort action
        """
        pass


class TurnValidationMiddleware(CombatMiddleware):
    """
    Validates it's the actor's turn before allowing action.

    Checks:
    - Combat is active
    - It's the actor's turn in initiative order
    - Actor is alive/conscious
    """

    def process(self, context: CombatActionContext, next_middleware: Callable) -> bool:
        # Check if in combat
        if not context.game_state.in_combat:
            context.result = ActionResult.FAILED
            context.error_message = "You're not in combat!"
            return False

        # Check if it's this actor's turn
        current = context.game_state.initiative_tracker.get_current_combatant()
        if current.creature != context.actor:
            # Generate helpful error message about whose turn it is
            from dnd_engine.core.character import Character

            if isinstance(current.creature, Character):
                turn_name = current.creature.name
            else:
                # It's an enemy - get display name if possible
                turn_name = getattr(current.creature, "name", "enemy")

            context.result = ActionResult.FAILED
            context.error_message = f"It's {turn_name}'s turn, not {context.actor.name}'s!"
            return False

        # Check if actor is alive
        if not context.actor.is_alive:
            context.result = ActionResult.FAILED
            context.error_message = f"{context.actor.name} is not conscious!"
            return False

        # All validations passed - continue to next middleware
        return next_middleware(context, next_middleware)


class ActionEconomyMiddleware(CombatMiddleware):
    """
    Validates and consumes action economy (action/bonus action).

    Checks if the requested action type is available and consumes it.
    This middleware does NOT refund actions on failure - actions are
    consumed once validation passes.
    """

    def process(self, context: CombatActionContext, next_middleware: Callable) -> bool:
        turn_state = context.game_state.initiative_tracker.get_current_turn_state()
        if not turn_state:
            context.result = ActionResult.FAILED
            context.error_message = "Unable to get current turn state!"
            return False

        # Check if action is available
        if not turn_state.is_action_available(context.action_type):
            action_name = context.action_type.name.replace("_", " ").title()
            context.result = ActionResult.FAILED
            context.error_message = f"You don't have an {action_name} available this turn!"
            return False

        # Consume the action
        if not turn_state.consume_action(context.action_type):
            context.result = ActionResult.FAILED
            context.error_message = "Failed to consume action!"
            return False

        # Action consumed successfully - continue to next middleware
        return next_middleware(context, next_middleware)


class LoggingMiddleware(CombatMiddleware):
    """
    Logs all combat actions for analytics.

    Logs action before execution. Does not prevent action from proceeding
    if logging fails (logging is non-critical).
    """

    def process(self, context: CombatActionContext, next_middleware: Callable) -> bool:
        from dnd_engine.utils.logging_config import get_logging_config

        logging_config = get_logging_config()
        if logging_config:
            try:
                # Format details dict as string for logging
                details_str = ", ".join(f"{k}={v}" for k, v in context.details.items())
                logging_config.log_player_action(
                    character=context.actor.name, action=context.action_name, details=details_str
                )
            except Exception:
                # Don't let logging failures break combat
                pass

        # Continue to next middleware regardless of logging success
        return next_middleware(context, next_middleware)


class ResourceCleanupMiddleware(CombatMiddleware):
    """
    Refunds consumed resources if action fails or is cancelled.

    This middleware wraps the rest of the chain and examines the result
    after execution. If the action failed or was cancelled, it refunds
    any resources that were consumed before the failure.

    This eliminates manual refund code scattered throughout handlers.
    """

    def process(self, context: CombatActionContext, next_middleware: Callable) -> bool:
        # Execute rest of chain
        success = next_middleware(context, next_middleware)

        # If action failed/cancelled, refund consumed resources
        if context.result in (ActionResult.CANCELLED, ActionResult.FAILED):
            for resource_name, amount in context.resources_consumed:
                pool = context.actor.get_resource_pool(resource_name)
                if pool:
                    pool.current += amount

        return success


class CombatActionExecutor:
    """
    Executes combat actions through a middleware chain.

    This class coordinates the middleware pattern, building a chain of
    middleware components and executing actions through them. Handlers
    pass their action logic as a callable, and the executor handles all
    the boilerplate (validation, logging, cleanup).

    Example:
        executor = CombatActionExecutor(game_state)
        context = executor.execute(
            actor=player,
            action_type=ActionType.ACTION,
            action_name="attack",
            action_handler=lambda ctx: perform_attack(ctx),
            target="goblin"
        )
        if context.result == ActionResult.SUCCESS:
            print("Attack succeeded!")
    """

    def __init__(self, game_state: "GameState"):
        """
        Initialize executor with game state and default middleware stack.

        Args:
            game_state: The game state containing combat state, initiative, etc.
        """
        self.game_state = game_state
        self.middleware_stack: list[CombatMiddleware] = [
            TurnValidationMiddleware(),
            ActionEconomyMiddleware(),
            LoggingMiddleware(),
            ResourceCleanupMiddleware(),
        ]

    def execute(
        self,
        actor: "Character",
        action_type: ActionType,
        action_name: str,
        action_handler: Callable[[CombatActionContext], bool],
        resources_consumed: list[tuple[str, int]] | None = None,
        **details,
    ) -> CombatActionContext:
        """
        Execute a combat action through the middleware chain.

        Args:
            actor: Character taking the action
            action_type: Type of action (ACTION, BONUS_ACTION)
            action_name: Name for logging ("attack", "cast_spell", "use_item")
            action_handler: Function that performs the actual action
            resources_consumed: List of (resource_pool_name, amount) consumed before execution
            **details: Additional action-specific data for logging

        Returns:
            CombatActionContext with execution results

        The action_handler receives the context and should:
        - Perform the actual action logic
        - Update context.result if action fails/cancelled
        - Update context.error_message if action fails
        - Return True if action should continue, False to abort
        """
        context = CombatActionContext(
            game_state=self.game_state,
            actor=actor,
            action_type=action_type,
            action_name=action_name,
            details=details,
            resources_consumed=resources_consumed or [],
        )

        # Build and execute middleware chain
        def execute_chain(
            ctx: CombatActionContext, remaining_middleware: list[CombatMiddleware]
        ) -> bool:
            if not remaining_middleware:
                # End of middleware chain - execute actual action
                return action_handler(ctx)

            current = remaining_middleware[0]
            rest = remaining_middleware[1:]
            return current.process(ctx, lambda c, _: execute_chain(c, rest))

        execute_chain(context, self.middleware_stack)
        return context
