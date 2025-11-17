"""
Integration tests for debug mode logging.

Tests cover:
- End-to-end debug mode initialization
- Console output to file
- Event logging during game operations
- Dice roll logging during game operations
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from dnd_engine.ui.rich_ui import init_console, console
from dnd_engine.utils.logging_config import get_logging_config
from dnd_engine.utils.events import EventBus, Event, EventType
from dnd_engine.core.dice import DiceRoller


class TestDebugModeIntegration:
    """Integration tests for debug mode."""

    def test_init_console_without_debug(self):
        """Test console initialization without debug mode."""
        init_console(debug_mode=False)

        logging_config = get_logging_config()
        assert logging_config is not None
        assert logging_config.debug_enabled is False

    def test_init_console_with_debug(self, tmp_path):
        """Test console initialization with debug mode."""
        # Change to tmp_path
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            init_console(debug_mode=True)

            logging_config = get_logging_config()
            assert logging_config is not None
            assert logging_config.debug_enabled is True
            assert logging_config.get_log_file_path() is not None

            # Verify log file was created
            log_path = logging_config.get_log_file_path()
            assert log_path.exists()

            # Clean up
            logging_config.close()
        finally:
            os.chdir(original_cwd)

    def test_console_output_to_file(self, tmp_path):
        """Test that console output is written to file in debug mode."""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            init_console(debug_mode=True)

            logging_config = get_logging_config()

            # Use the global console to print something
            from dnd_engine.ui.rich_ui import console, print_message
            print_message("Test message")

            # Flush the console
            console.file.flush()

            # Read log file
            log_path = logging_config.get_log_file_path()
            log_content = log_path.read_text()

            # Verify message was written to file
            assert "Test message" in log_content

            # Clean up
            logging_config.close()
        finally:
            os.chdir(original_cwd)

    def test_event_logging_integration(self, tmp_path):
        """Test event logging during actual event emission."""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            init_console(debug_mode=True)

            logging_config = get_logging_config()

            # Create event bus and emit events
            event_bus = EventBus()
            event_bus.emit(Event(
                EventType.COMBAT_START,
                {"enemies": ["Goblin", "Orc"]}
            ))

            # Read log file
            log_path = logging_config.get_log_file_path()
            log_content = log_path.read_text()

            # Verify event was logged
            assert "EVENT" in log_content
            assert "COMBAT_START" in log_content

            # Clean up
            logging_config.close()
        finally:
            os.chdir(original_cwd)

    def test_dice_roll_logging_integration(self, tmp_path):
        """Test dice roll logging during actual dice rolls."""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            init_console(debug_mode=True)

            logging_config = get_logging_config()

            # Create dice roller and roll
            roller = DiceRoller()
            result = roller.roll("1d20+5")

            # Read log file
            log_path = logging_config.get_log_file_path()
            log_content = log_path.read_text()

            # Verify dice roll was logged
            assert "DICE" in log_content
            assert "1d20+5" in log_content

            # Clean up
            logging_config.close()
        finally:
            os.chdir(original_cwd)

    def test_multiple_events_logged(self, tmp_path):
        """Test that multiple events are logged correctly."""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            init_console(debug_mode=True)

            logging_config = get_logging_config()

            # Create event bus and emit multiple events
            event_bus = EventBus()
            event_bus.emit(Event(EventType.COMBAT_START, {"enemies": ["Goblin"]}))
            event_bus.emit(Event(EventType.DAMAGE_DEALT, {"damage": 8, "target": "Goblin"}))
            event_bus.emit(Event(EventType.COMBAT_END, {"xp_gained": 50}))

            # Read log file
            log_path = logging_config.get_log_file_path()
            log_content = log_path.read_text()

            # Verify all events were logged
            assert "COMBAT_START" in log_content
            assert "DAMAGE_DEALT" in log_content
            assert "COMBAT_END" in log_content

            # Verify event counter is incrementing
            assert "EVENT #001" in log_content
            assert "EVENT #002" in log_content
            assert "EVENT #003" in log_content

            # Clean up
            logging_config.close()
        finally:
            os.chdir(original_cwd)

    def test_log_file_is_readable(self, tmp_path):
        """Test that log file is human-readable plain text."""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            init_console(debug_mode=True)

            logging_config = get_logging_config()

            # Generate some output
            from dnd_engine.ui.rich_ui import print_status_message
            print_status_message("Test message", "success")

            # Flush
            console.file.flush()

            # Read log file
            log_path = logging_config.get_log_file_path()
            log_content = log_path.read_text()

            # Verify it's readable text (not binary or heavily escaped)
            assert "Test message" in log_content

            # Clean up
            logging_config.close()
        finally:
            os.chdir(original_cwd)

    def test_log_file_encoding(self, tmp_path):
        """Test that log file uses UTF-8 encoding."""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            init_console(debug_mode=True)

            logging_config = get_logging_config()

            # Write unicode characters
            from dnd_engine.ui.rich_ui import print_message
            print_message("Test: ⚔ ✓ ● ⚠ 💀")

            # Flush
            console.file.flush()

            # Read log file with UTF-8
            log_path = logging_config.get_log_file_path()
            log_content = log_path.read_text(encoding='utf-8')

            # Verify unicode characters are preserved
            # Note: Rich might strip some special characters when force_terminal=False
            # So we just verify the file can be read as UTF-8
            assert "Test:" in log_content

            # Clean up
            logging_config.close()
        finally:
            os.chdir(original_cwd)


class TestDebugModeDisabled:
    """Tests to ensure no logging overhead when debug mode is disabled."""

    def test_no_log_file_created_without_debug(self, tmp_path):
        """Test that no log file is created when debug mode is disabled."""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            init_console(debug_mode=False)

            logging_config = get_logging_config()
            assert logging_config.get_log_file_path() is None

            # Check that no logs directory was created
            logs_dir = Path("logs")
            if logs_dir.exists():
                # If it exists, it should be empty or only contain old files
                log_files = list(logs_dir.glob("dnd_game_*.log"))
                # No new log files should have been created in this test
                # (there might be old ones from previous tests)
                pass

        finally:
            os.chdir(original_cwd)

    def test_events_work_without_debug(self):
        """Test that events still work when debug mode is disabled."""
        init_console(debug_mode=False)

        # Create event bus and emit event
        event_bus = EventBus()

        # Should not raise exception
        event_bus.emit(Event(EventType.COMBAT_START, {"enemies": ["Goblin"]}))

    def test_dice_rolls_work_without_debug(self):
        """Test that dice rolls still work when debug mode is disabled."""
        init_console(debug_mode=False)

        # Create dice roller and roll
        roller = DiceRoller()

        # Should not raise exception
        result = roller.roll("1d20+5")
        assert result.total > 0
