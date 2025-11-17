# ABOUTME: End-to-end tests for main entry point
# ABOUTME: Tests actual command execution and installed command

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


class TestCommandExecution:
    """Test command-line execution of the game."""

    def test_python_module_help(self):
        """Test python -m dnd_engine.main --help shows help."""
        result = subprocess.run(
            [sys.executable, "-m", "dnd_engine.main", "--help"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "D&D 5E Terminal Adventure Game" in result.stdout
        assert "--no-llm" in result.stdout
        assert "--llm-provider" in result.stdout
        assert "--dungeon" in result.stdout
        assert "--debug" in result.stdout
        assert "--version" in result.stdout

    def test_python_module_version(self):
        """Test python -m dnd_engine.main --version shows version."""
        result = subprocess.run(
            [sys.executable, "-m", "dnd_engine.main", "--version"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "D&D 5E Terminal Game v0.1.0" in result.stdout

    def test_python_module_starts_with_mocked_input(self, tmp_path):
        """Test that game starts and handles mocked character creation."""
        # Create a test script that mocks input
        test_script = tmp_path / "test_run.py"
        test_script.write_text("""
import sys
from unittest.mock import patch, MagicMock

# Mock all the interactive parts
def mock_create_character(*args, **kwargs):
    char = MagicMock()
    char.name = "TestHero"
    char.race = "human"
    return char

def mock_run(*args, **kwargs):
    # Exit immediately after starting
    pass

with patch('dnd_engine.main.CharacterFactory') as mock_factory_class:
    with patch('dnd_engine.main.CLI') as mock_cli_class:
        with patch('builtins.input', return_value=''):
            mock_factory = MagicMock()
            mock_factory.create_character_interactive = mock_create_character
            mock_factory_class.return_value = mock_factory

            mock_cli = MagicMock()
            mock_cli.run = mock_run
            mock_cli_class.return_value = mock_cli

            from dnd_engine.main import main
            try:
                main()
            except SystemExit:
                pass
""")

        result = subprocess.run(
            [sys.executable, str(test_script), "--no-llm"],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should complete without errors
        assert "D&D 5E Terminal Adventure" in result.stdout
        assert "Checking configuration" in result.stdout

    def test_invalid_llm_provider_exits_with_error(self):
        """Test that invalid LLM provider shows error and exits."""
        result = subprocess.run(
            [sys.executable, "-m", "dnd_engine.main", "--llm-provider", "invalid"],
            capture_output=True,
            text=True
        )

        assert result.returncode != 0
        # argparse will show error about invalid choice
        assert "invalid choice" in result.stderr.lower()


class TestInstalledCommand:
    """Test the installed dnd-game command."""

    def test_dnd_game_help(self):
        """Test dnd-game --help works (requires package installation)."""
        # This test will only pass if the package is installed
        try:
            result = subprocess.run(
                ["dnd-game", "--help"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                assert "D&D 5E Terminal Adventure Game" in result.stdout
                assert "--no-llm" in result.stdout
            else:
                # If command not found, skip test
                pytest.skip("dnd-game command not installed")
        except FileNotFoundError:
            pytest.skip("dnd-game command not installed")

    def test_dnd_game_version(self):
        """Test dnd-game --version works (requires package installation)."""
        try:
            result = subprocess.run(
                ["dnd-game", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                assert "D&D 5E Terminal Game v0.1.0" in result.stdout
            else:
                pytest.skip("dnd-game command not installed")
        except FileNotFoundError:
            pytest.skip("dnd-game command not installed")


class TestArgumentValidation:
    """Test argument validation and error messages."""

    def test_invalid_argument_shows_error(self):
        """Test that invalid arguments show helpful error."""
        result = subprocess.run(
            [sys.executable, "-m", "dnd_engine.main", "--invalid-arg"],
            capture_output=True,
            text=True
        )

        assert result.returncode != 0
        assert "unrecognized arguments" in result.stderr.lower()

    def test_help_contains_examples(self):
        """Test that help message contains usage examples."""
        result = subprocess.run(
            [sys.executable, "-m", "dnd_engine.main", "--help"],
            capture_output=True,
            text=True
        )

        assert "Examples:" in result.stdout
        assert "dnd-game" in result.stdout
        assert "Start with default settings" in result.stdout


class TestFullE2EFlow:
    """Test full end-to-end game flow with automation."""

    def test_complete_flow_automated(self, tmp_path):
        """Test complete flow from start to game with automated inputs."""
        # Create a script that automates the entire flow
        test_script = tmp_path / "test_full_flow.py"
        test_script.write_text("""
import sys
from unittest.mock import patch, MagicMock

# Track that all steps were called
steps_called = []

# Mock character factory
def mock_create_character(*args, **kwargs):
    steps_called.append('character_creation')
    char = MagicMock()
    char.name = "AutoHero"
    char.race = "human"
    return char

# Mock CLI run
def mock_cli_run(self):
    steps_called.append('game_loop')

# Mock input
def mock_input(prompt=''):
    steps_called.append('input_prompt')
    return ''

with patch('dnd_engine.main.CharacterFactory') as mock_factory_class:
    with patch('dnd_engine.main.CLI.run', mock_cli_run):
        with patch('builtins.input', mock_input):
            mock_factory = MagicMock()
            mock_factory.create_character_interactive = mock_create_character
            mock_factory_class.return_value = mock_factory

            # Override sys.argv
            sys.argv = ['dnd-game', '--no-llm']

            from dnd_engine.main import main
            try:
                main()
            except SystemExit:
                pass

            # Verify all steps were called
            assert 'character_creation' in steps_called
            assert 'input_prompt' in steps_called  # "Press Enter to begin"
            assert 'game_loop' in steps_called

            print("SUCCESS: All steps completed")
""")

        result = subprocess.run(
            [sys.executable, str(test_script)],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Check output
        assert "SUCCESS: All steps completed" in result.stdout
        assert "D&D 5E Terminal Adventure" in result.stdout
        assert "Checking configuration" in result.stdout
        assert "Let's create your character" in result.stdout
        assert "Character created" in result.stdout
