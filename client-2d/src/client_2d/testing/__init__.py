# ABOUTME: Testing module for headless game testing and Claude-driven playtesting.
# ABOUTME: Provides StateRenderer, CommandProcessor, and TestHarness classes.

"""Testing module for headless game testing."""

from client_2d.testing.command_processor import (
    Command,
    CommandProcessor,
    CommandResult,
    CommandType,
)
from client_2d.testing.state_renderer import Entity, StateRenderer
from client_2d.testing.test_harness import GameState, TestHarness, create_demo_game_state

__all__ = [
    "Command",
    "CommandProcessor",
    "CommandResult",
    "CommandType",
    "Entity",
    "GameState",
    "StateRenderer",
    "TestHarness",
    "create_demo_game_state",
]
