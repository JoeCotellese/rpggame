# ABOUTME: Unit tests for the CommandProcessor class.
# ABOUTME: Validates command parsing, validation, and result formatting.

"""Tests for the CommandProcessor class."""

import pytest
from client_2d.core.constants import Direction
from client_2d.testing.command_processor import (
    Command,
    CommandProcessor,
    CommandResult,
    CommandType,
)


class TestCommandParsing:
    """Tests for command parsing."""

    @pytest.fixture
    def processor(self) -> CommandProcessor:
        """Create a CommandProcessor instance."""
        return CommandProcessor()

    def test_parse_move_north(self, processor: CommandProcessor):
        """Test parsing move_north command."""
        cmd = processor.parse_command('{"action": "move_north"}')

        assert cmd.command_type == CommandType.MOVE
        assert cmd.direction == Direction.NORTH
        assert cmd.raw_action == "move_north"

    def test_parse_move_south(self, processor: CommandProcessor):
        """Test parsing move_south command."""
        cmd = processor.parse_command('{"action": "move_south"}')

        assert cmd.command_type == CommandType.MOVE
        assert cmd.direction == Direction.SOUTH

    def test_parse_move_east(self, processor: CommandProcessor):
        """Test parsing move_east command."""
        cmd = processor.parse_command('{"action": "move_east"}')

        assert cmd.command_type == CommandType.MOVE
        assert cmd.direction == Direction.EAST

    def test_parse_move_west(self, processor: CommandProcessor):
        """Test parsing move_west command."""
        cmd = processor.parse_command('{"action": "move_west"}')

        assert cmd.command_type == CommandType.MOVE
        assert cmd.direction == Direction.WEST

    def test_parse_wait(self, processor: CommandProcessor):
        """Test parsing wait command."""
        cmd = processor.parse_command('{"action": "wait"}')

        assert cmd.command_type == CommandType.WAIT
        assert cmd.raw_action == "wait"

    def test_parse_get_state(self, processor: CommandProcessor):
        """Test parsing get_state command."""
        cmd = processor.parse_command('{"action": "get_state"}')

        assert cmd.command_type == CommandType.GET_STATE

    def test_parse_quit(self, processor: CommandProcessor):
        """Test parsing quit command."""
        cmd = processor.parse_command('{"action": "quit"}')

        assert cmd.command_type == CommandType.QUIT

    def test_parse_attack_inline(self, processor: CommandProcessor):
        """Test parsing attack with inline target."""
        cmd = processor.parse_command('{"action": "attack_goblin"}')

        assert cmd.command_type == CommandType.ATTACK
        assert cmd.target_id == "goblin"
        assert cmd.raw_action == "attack_goblin"

    def test_parse_attack_separate_target(self, processor: CommandProcessor):
        """Test parsing attack with separate target field."""
        cmd = processor.parse_command('{"action": "attack", "target": "skeleton"}')

        assert cmd.command_type == CommandType.ATTACK
        assert cmd.target_id == "skeleton"

    def test_parse_interact_inline(self, processor: CommandProcessor):
        """Test parsing interact with inline target."""
        cmd = processor.parse_command('{"action": "interact_chest"}')

        assert cmd.command_type == CommandType.INTERACT
        assert cmd.target_id == "chest"

    def test_parse_interact_separate_target(self, processor: CommandProcessor):
        """Test parsing interact with separate target field."""
        cmd = processor.parse_command('{"action": "interact", "target": "door"}')

        assert cmd.command_type == CommandType.INTERACT
        assert cmd.target_id == "door"

    def test_parse_invalid_json(self, processor: CommandProcessor):
        """Test parsing invalid JSON returns unknown command."""
        cmd = processor.parse_command("not valid json")

        assert cmd.command_type == CommandType.UNKNOWN
        assert not cmd.is_valid

    def test_parse_empty_action(self, processor: CommandProcessor):
        """Test parsing empty action."""
        cmd = processor.parse_command('{"action": ""}')

        assert cmd.command_type == CommandType.UNKNOWN

    def test_parse_unknown_action(self, processor: CommandProcessor):
        """Test parsing unknown action string."""
        cmd = processor.parse_command('{"action": "dance"}')

        assert cmd.command_type == CommandType.UNKNOWN
        assert cmd.raw_action == "dance"

    def test_parse_with_whitespace(self, processor: CommandProcessor):
        """Test parsing handles whitespace."""
        cmd = processor.parse_command('  {"action": "wait"}  \n')

        assert cmd.command_type == CommandType.WAIT


class TestCommandValidation:
    """Tests for command validation."""

    @pytest.fixture
    def processor(self) -> CommandProcessor:
        """Create a CommandProcessor instance."""
        return CommandProcessor()

    @pytest.fixture
    def standard_actions(self) -> list[str]:
        """Standard available actions for testing."""
        return ["move_north", "move_south", "move_east", "wait"]

    def test_validate_valid_movement(
        self, processor: CommandProcessor, standard_actions: list[str]
    ):
        """Test validating a valid movement command."""
        cmd = Command(
            command_type=CommandType.MOVE,
            direction=Direction.NORTH,
            raw_action="move_north",
        )
        result = processor.validate_command(cmd, standard_actions)

        assert result.success
        assert result.action_taken == "move_north"

    def test_validate_blocked_movement(
        self, processor: CommandProcessor, standard_actions: list[str]
    ):
        """Test validating blocked movement returns failure."""
        cmd = Command(
            command_type=CommandType.MOVE,
            direction=Direction.WEST,
            raw_action="move_west",
        )
        result = processor.validate_command(cmd, standard_actions)

        assert not result.success
        assert "blocked" in result.message.lower()

    def test_validate_wait(
        self, processor: CommandProcessor, standard_actions: list[str]
    ):
        """Test validating wait command."""
        cmd = Command(command_type=CommandType.WAIT, raw_action="wait")
        result = processor.validate_command(cmd, standard_actions)

        assert result.success
        assert result.action_taken == "wait"

    def test_validate_get_state_always_valid(self, processor: CommandProcessor):
        """Test get_state is always valid regardless of available actions."""
        cmd = Command(command_type=CommandType.GET_STATE, raw_action="get_state")
        result = processor.validate_command(cmd, [])  # Empty available actions

        assert result.success

    def test_validate_quit_always_valid(self, processor: CommandProcessor):
        """Test quit is always valid regardless of available actions."""
        cmd = Command(command_type=CommandType.QUIT, raw_action="quit")
        result = processor.validate_command(cmd, [])

        assert result.success

    def test_validate_valid_attack(self, processor: CommandProcessor):
        """Test validating attack on adjacent target."""
        available = ["move_north", "attack_goblin", "wait"]
        cmd = Command(
            command_type=CommandType.ATTACK,
            target_id="goblin",
            raw_action="attack_goblin",
        )
        result = processor.validate_command(cmd, available)

        assert result.success
        assert result.action_taken == "attack_goblin"

    def test_validate_invalid_attack(self, processor: CommandProcessor):
        """Test validating attack on non-adjacent target."""
        available = ["move_north", "wait"]  # No attack_goblin
        cmd = Command(
            command_type=CommandType.ATTACK,
            target_id="goblin",
            raw_action="attack_goblin",
        )
        result = processor.validate_command(cmd, available)

        assert not result.success
        assert "not adjacent" in result.message.lower()

    def test_validate_valid_interact(self, processor: CommandProcessor):
        """Test validating interact with adjacent item."""
        available = ["move_north", "interact_chest", "wait"]
        cmd = Command(
            command_type=CommandType.INTERACT,
            target_id="chest",
            raw_action="interact_chest",
        )
        result = processor.validate_command(cmd, available)

        assert result.success
        assert result.action_taken == "interact_chest"

    def test_validate_unknown_command(self, processor: CommandProcessor):
        """Test validating unknown command returns failure."""
        cmd = Command(command_type=CommandType.UNKNOWN, raw_action="invalid")
        result = processor.validate_command(cmd, ["wait"])

        assert not result.success
        assert "unknown" in result.message.lower()


class TestProcessInput:
    """Tests for the combined process_input method."""

    @pytest.fixture
    def processor(self) -> CommandProcessor:
        """Create a CommandProcessor instance."""
        return CommandProcessor()

    def test_process_valid_input(self, processor: CommandProcessor):
        """Test processing valid input end-to-end."""
        available = ["move_north", "move_south", "wait"]
        cmd, result = processor.process_input(
            '{"action": "move_north"}', available
        )

        assert cmd.command_type == CommandType.MOVE
        assert result.success
        assert result.action_taken == "move_north"

    def test_process_invalid_json(self, processor: CommandProcessor):
        """Test processing invalid JSON."""
        cmd, result = processor.process_input("bad json", ["wait"])

        assert cmd.command_type == CommandType.UNKNOWN
        assert not result.success

    def test_process_blocked_action(self, processor: CommandProcessor):
        """Test processing action that's not available."""
        available = ["move_south", "wait"]  # No north
        cmd, result = processor.process_input(
            '{"action": "move_north"}', available
        )

        assert cmd.command_type == CommandType.MOVE
        assert not result.success


class TestResultFormatting:
    """Tests for result formatting."""

    @pytest.fixture
    def processor(self) -> CommandProcessor:
        """Create a CommandProcessor instance."""
        return CommandProcessor()

    def test_format_error(self, processor: CommandProcessor):
        """Test formatting error result."""
        result = CommandResult(success=False, message="Cannot move: wall")
        formatted = processor.format_error(result)

        assert formatted["error"] is True
        assert formatted["message"] == "Cannot move: wall"

    def test_format_success(self, processor: CommandProcessor):
        """Test formatting success result."""
        result = CommandResult(
            success=True, message="OK", action_taken="move_north"
        )
        formatted = processor.format_success(result)

        assert formatted["error"] is False
        assert formatted["action"] == "move_north"


class TestCommandIsValid:
    """Tests for Command.is_valid property."""

    def test_move_command_is_valid(self):
        """Test move command is valid."""
        cmd = Command(
            command_type=CommandType.MOVE,
            direction=Direction.NORTH,
            raw_action="move_north",
        )
        assert cmd.is_valid

    def test_unknown_command_is_invalid(self):
        """Test unknown command is invalid."""
        cmd = Command(command_type=CommandType.UNKNOWN, raw_action="garbage")
        assert not cmd.is_valid
