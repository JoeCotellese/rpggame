# ABOUTME: Processes commands from stdin for headless game testing.
# ABOUTME: Parses JSON commands and validates actions against game state.

"""Command processor for headless test harness."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from client_2d.core.constants import Direction


class CommandType(Enum):
    """Types of commands that can be processed."""

    MOVE = auto()
    ATTACK = auto()
    INTERACT = auto()
    WAIT = auto()
    GET_STATE = auto()
    QUIT = auto()
    UNKNOWN = auto()


@dataclass
class Command:
    """Parsed command with type and parameters."""

    command_type: CommandType
    direction: Direction | None = None
    target_id: str | None = None
    raw_action: str = ""

    @property
    def is_valid(self) -> bool:
        """Check if the command is valid and processable."""
        return self.command_type != CommandType.UNKNOWN


@dataclass
class CommandResult:
    """Result of processing a command."""

    success: bool
    message: str
    action_taken: str = ""


class CommandProcessor:
    """Processes JSON commands for the test harness.

    Accepts commands in the format:
        {"action": "move_north"}
        {"action": "attack", "target": "goblin_1"}
        {"action": "get_state"}
        {"action": "quit"}

    Validates commands against available actions and returns
    structured results.
    """

    # Map action strings to directions
    DIRECTION_MAP = {
        "move_north": Direction.NORTH,
        "move_south": Direction.SOUTH,
        "move_east": Direction.EAST,
        "move_west": Direction.WEST,
    }

    def parse_command(self, input_str: str) -> Command:
        """Parse a JSON command string into a Command object.

        Args:
            input_str: JSON string containing the command

        Returns:
            Parsed Command object
        """
        try:
            data = json.loads(input_str.strip())
        except json.JSONDecodeError:
            return Command(
                command_type=CommandType.UNKNOWN,
                raw_action=input_str,
            )

        if not isinstance(data, dict):
            return Command(command_type=CommandType.UNKNOWN, raw_action=input_str)

        action = data.get("action", "")

        # Meta commands
        if action == "get_state":
            return Command(command_type=CommandType.GET_STATE, raw_action=action)
        if action == "quit":
            return Command(command_type=CommandType.QUIT, raw_action=action)
        if action == "wait":
            return Command(command_type=CommandType.WAIT, raw_action=action)

        # Movement commands
        if action in self.DIRECTION_MAP:
            return Command(
                command_type=CommandType.MOVE,
                direction=self.DIRECTION_MAP[action],
                raw_action=action,
            )

        # Attack commands (attack_<target_id>)
        if action.startswith("attack_"):
            target_id = action[7:]  # Remove "attack_" prefix
            return Command(
                command_type=CommandType.ATTACK,
                target_id=target_id,
                raw_action=action,
            )

        # Attack with separate target field
        if action == "attack":
            target_id = data.get("target", "")
            if target_id:
                return Command(
                    command_type=CommandType.ATTACK,
                    target_id=target_id,
                    raw_action=action,
                )

        # Interact commands (interact_<target_id>)
        if action.startswith("interact_"):
            target_id = action[9:]  # Remove "interact_" prefix
            return Command(
                command_type=CommandType.INTERACT,
                target_id=target_id,
                raw_action=action,
            )

        # Interact with separate target field
        if action == "interact":
            target_id = data.get("target", "")
            if target_id:
                return Command(
                    command_type=CommandType.INTERACT,
                    target_id=target_id,
                    raw_action=action,
                )

        return Command(command_type=CommandType.UNKNOWN, raw_action=action)

    def validate_command(
        self, command: Command, available_actions: list[str]
    ) -> CommandResult:
        """Validate a command against available actions.

        Args:
            command: Parsed Command to validate
            available_actions: List of currently available action strings

        Returns:
            CommandResult indicating if the command is valid
        """
        if command.command_type == CommandType.UNKNOWN:
            return CommandResult(
                success=False,
                message=f"Unknown command: {command.raw_action}",
            )

        # Meta commands are always valid
        if command.command_type in (CommandType.GET_STATE, CommandType.QUIT):
            return CommandResult(
                success=True,
                message="OK",
                action_taken=command.raw_action,
            )

        # Wait is always valid
        if command.command_type == CommandType.WAIT:
            if "wait" in available_actions:
                return CommandResult(
                    success=True,
                    message="OK",
                    action_taken="wait",
                )
            return CommandResult(
                success=False,
                message="Wait action not available",
            )

        # Movement validation
        if command.command_type == CommandType.MOVE:
            if command.raw_action in available_actions:
                return CommandResult(
                    success=True,
                    message="OK",
                    action_taken=command.raw_action,
                )
            return CommandResult(
                success=False,
                message=f"Cannot move {command.direction.name.lower()}: blocked",
            )

        # Attack validation
        if command.command_type == CommandType.ATTACK:
            attack_action = f"attack_{command.target_id}"
            if attack_action in available_actions:
                return CommandResult(
                    success=True,
                    message="OK",
                    action_taken=attack_action,
                )
            return CommandResult(
                success=False,
                message=f"Cannot attack {command.target_id}: not adjacent or not visible",
            )

        # Interact validation
        if command.command_type == CommandType.INTERACT:
            interact_action = f"interact_{command.target_id}"
            if interact_action in available_actions:
                return CommandResult(
                    success=True,
                    message="OK",
                    action_taken=interact_action,
                )
            return CommandResult(
                success=False,
                message=f"Cannot interact with {command.target_id}: not adjacent or not visible",
            )

        return CommandResult(
            success=False,
            message=f"Unhandled command type: {command.command_type}",
        )

    def process_input(
        self, input_str: str, available_actions: list[str]
    ) -> tuple[Command, CommandResult]:
        """Parse and validate a command in one step.

        Args:
            input_str: Raw JSON input string
            available_actions: List of available action strings

        Returns:
            Tuple of (parsed Command, CommandResult)
        """
        command = self.parse_command(input_str)
        result = self.validate_command(command, available_actions)
        return command, result

    def format_error(self, result: CommandResult) -> dict[str, Any]:
        """Format a failed command result as JSON-serializable dict.

        Args:
            result: Failed CommandResult

        Returns:
            Dict suitable for JSON output
        """
        return {
            "error": True,
            "message": result.message,
        }

    def format_success(self, result: CommandResult) -> dict[str, Any]:
        """Format a successful command result as JSON-serializable dict.

        Args:
            result: Successful CommandResult

        Returns:
            Dict suitable for JSON output
        """
        return {
            "error": False,
            "action": result.action_taken,
        }
