# ABOUTME: Unit tests for main.py entry point
# ABOUTME: Tests argument parsing, initialization, error handling, and configuration

import argparse
import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

from dnd_engine.main import (
    initialize_data_loader,
    initialize_llm,
    main,
    parse_arguments,
    print_banner,
)


class TestArgumentParsing:
    """Test command-line argument parsing."""

    def test_parse_arguments_defaults(self):
        """Test that default arguments are parsed correctly."""
        with patch("sys.argv", ["dnd-game"]):
            args = parse_arguments()
            assert args.no_llm is False
            assert args.llm_provider is None
            assert args.dungeon == "goblin_warren"
            assert args.debug is False

    def test_parse_arguments_no_llm_flag(self):
        """Test --no-llm flag sets correct value."""
        with patch("sys.argv", ["dnd-game", "--no-llm"]):
            args = parse_arguments()
            assert args.no_llm is True

    def test_parse_arguments_llm_provider_openai(self):
        """Test --llm-provider openai sets correct value."""
        with patch("sys.argv", ["dnd-game", "--llm-provider", "openai"]):
            args = parse_arguments()
            assert args.llm_provider == "openai"

    def test_parse_arguments_llm_provider_anthropic(self):
        """Test --llm-provider anthropic sets correct value."""
        with patch("sys.argv", ["dnd-game", "--llm-provider", "anthropic"]):
            args = parse_arguments()
            assert args.llm_provider == "anthropic"

    def test_parse_arguments_llm_provider_none(self):
        """Test --llm-provider none sets correct value."""
        with patch("sys.argv", ["dnd-game", "--llm-provider", "none"]):
            args = parse_arguments()
            assert args.llm_provider == "none"

    def test_parse_arguments_dungeon(self):
        """Test --dungeon flag sets correct value."""
        with patch("sys.argv", ["dnd-game", "--dungeon", "crypt"]):
            args = parse_arguments()
            assert args.dungeon == "crypt"

    def test_parse_arguments_debug(self):
        """Test --debug flag sets correct value."""
        with patch("sys.argv", ["dnd-game", "--debug"]):
            args = parse_arguments()
            assert args.debug is True

    def test_parse_arguments_version(self):
        """Test --version flag exits with version."""
        with patch("sys.argv", ["dnd-game", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                parse_arguments()
            assert exc_info.value.code == 0

    def test_parse_arguments_help(self):
        """Test --help flag shows help message."""
        with patch("sys.argv", ["dnd-game", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                parse_arguments()
            assert exc_info.value.code == 0

    def test_parse_arguments_invalid_provider(self):
        """Test invalid LLM provider shows error."""
        with patch("sys.argv", ["dnd-game", "--llm-provider", "invalid"]):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_parse_arguments_combined(self):
        """Test multiple arguments combined."""
        with patch("sys.argv", [
            "dnd-game",
            "--llm-provider", "anthropic",
            "--dungeon", "dragon_lair",
            "--debug"
        ]):
            args = parse_arguments()
            assert args.llm_provider == "anthropic"
            assert args.dungeon == "dragon_lair"
            assert args.debug is True


class TestPrintBanner:
    """Test banner display."""

    def test_print_banner_output(self, capsys):
        """Test that banner prints correctly."""
        print_banner()
        captured = capsys.readouterr()
        assert "D&D 5E Terminal Adventure" in captured.out
        assert "Version 0.1.0" in captured.out
        assert "╔" in captured.out
        assert "╚" in captured.out


class TestDataLoaderInitialization:
    """Test data loader initialization."""

    @patch("dnd_engine.main.DataLoader")
    def test_initialize_data_loader_success(self, mock_loader_class, capsys):
        """Test successful data loader initialization."""
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader

        loader = initialize_data_loader()

        captured = capsys.readouterr()
        assert "✓ Data files loaded" in captured.out
        assert loader == mock_loader

    @patch("dnd_engine.main.DataLoader")
    def test_initialize_data_loader_file_not_found(self, mock_loader_class, capsys):
        """Test data loader initialization with missing files."""
        mock_loader_class.side_effect = FileNotFoundError("Data files not found")

        with pytest.raises(SystemExit) as exc_info:
            initialize_data_loader()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "✗ ERROR: Data files not found" in captured.out
        assert "Please ensure the game is installed correctly" in captured.out


class TestLLMInitialization:
    """Test LLM provider initialization."""

    def test_initialize_llm_with_no_llm_flag(self, capsys):
        """Test LLM initialization with --no-llm flag."""
        args = argparse.Namespace(no_llm=True, llm_provider=None)
        provider = initialize_llm(args)

        assert provider is None
        captured = capsys.readouterr()
        assert "⚠ LLM disabled (--no-llm flag)" in captured.out

    def test_initialize_llm_with_provider_none(self, capsys):
        """Test LLM initialization with --llm-provider none."""
        args = argparse.Namespace(no_llm=False, llm_provider="none")
        provider = initialize_llm(args)

        assert provider is None
        captured = capsys.readouterr()
        assert "⚠ LLM disabled (--llm-provider none)" in captured.out

    @patch("dnd_engine.main.create_llm_provider")
    def test_initialize_llm_with_valid_provider(self, mock_create, capsys):
        """Test LLM initialization with valid provider."""
        mock_provider = MagicMock()
        mock_provider.get_provider_name.return_value = "OpenAI"
        mock_create.return_value = mock_provider

        args = argparse.Namespace(no_llm=False, llm_provider="openai")
        provider = initialize_llm(args)

        assert provider == mock_provider
        captured = capsys.readouterr()
        assert "✓ LLM provider: OpenAI" in captured.out

    @patch("dnd_engine.main.create_llm_provider")
    def test_initialize_llm_no_api_key(self, mock_create, capsys):
        """Test LLM initialization with no API key configured."""
        mock_create.return_value = None

        args = argparse.Namespace(no_llm=False, llm_provider="openai")
        provider = initialize_llm(args)

        assert provider is None
        captured = capsys.readouterr()
        assert "⚠ LLM disabled (no API key configured)" in captured.out
        assert "Set OPENAI_API_KEY or ANTHROPIC_API_KEY" in captured.out

    @patch("dnd_engine.main.create_llm_provider")
    def test_initialize_llm_exception(self, mock_create, capsys):
        """Test LLM initialization with exception."""
        mock_create.side_effect = Exception("Connection error")

        args = argparse.Namespace(no_llm=False, llm_provider="openai")
        provider = initialize_llm(args)

        assert provider is None
        captured = capsys.readouterr()
        assert "⚠ LLM initialization failed" in captured.out
        assert "Continuing with basic descriptions" in captured.out


class TestMainFunction:
    """Test main function integration."""

    @patch("dnd_engine.main.CLI")
    @patch("dnd_engine.main.GameState")
    @patch("dnd_engine.main.Party")
    @patch("dnd_engine.main.show_save_load_menu")
    @patch("dnd_engine.main.SaveManager")
    @patch("dnd_engine.main.create_new_party")
    @patch("dnd_engine.main.LLMEnhancer")
    @patch("dnd_engine.main.EventBus")
    @patch("dnd_engine.main.initialize_llm")
    @patch("dnd_engine.main.initialize_data_loader")
    @patch("dnd_engine.main.parse_arguments")
    @patch("builtins.input")
    def test_main_successful_flow(
        self,
        mock_input,
        mock_parse_args,
        mock_init_loader,
        mock_init_llm,
        mock_event_bus,
        mock_llm_enhancer,
        mock_create_party,
        mock_save_manager_class,
        mock_show_save_menu,
        mock_party_class,
        mock_game_state_class,
        mock_cli_class,
        capsys
    ):
        """Test successful main flow."""
        # Mock inputs for "Press Enter to begin your adventure"
        mock_input.side_effect = [""]

        # Setup mocks
        mock_args = MagicMock(debug=False, dungeon="goblin_warren")
        mock_parse_args.return_value = mock_args

        mock_loader = MagicMock()
        mock_init_loader.return_value = mock_loader

        mock_provider = MagicMock()
        mock_init_llm.return_value = mock_provider

        mock_bus = MagicMock()
        mock_event_bus.return_value = mock_bus

        # Mock save manager to return no saves (start new game)
        mock_save_manager = MagicMock()
        mock_save_manager_class.return_value = mock_save_manager
        mock_show_save_menu.return_value = None  # Start new game

        # Mock party creation
        mock_party = MagicMock()
        mock_party_class.return_value = mock_party
        mock_create_party.return_value = mock_party

        mock_game_state = MagicMock()
        mock_game_state_class.return_value = mock_game_state

        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        # Run main
        main()

        # Verify flow
        mock_parse_args.assert_called_once()
        mock_init_loader.assert_called_once()
        mock_init_llm.assert_called_once_with(mock_args)
        mock_event_bus.assert_called_once()
        mock_llm_enhancer.assert_called_once_with(mock_provider, mock_bus)
        mock_save_manager_class.assert_called_once()
        mock_show_save_menu.assert_called_once_with(mock_save_manager)
        mock_create_party.assert_called_once_with(mock_args, mock_loader)
        mock_game_state_class.assert_called_once_with(
            party=mock_party,
            dungeon_name="goblin_warren",
            event_bus=mock_bus,
            data_loader=mock_loader
        )
        # CLI now receives llm_enhancer as well
        mock_cli_class.assert_called_once()
        args, kwargs = mock_cli_class.call_args
        assert args[0] == mock_game_state
        assert 'llm_enhancer' in kwargs
        mock_cli.run.assert_called_once()

        # Verify output
        captured = capsys.readouterr()
        assert "Checking configuration..." in captured.out

    @patch("dnd_engine.main.show_save_load_menu")
    @patch("dnd_engine.main.SaveManager")
    @patch("dnd_engine.main.EventBus")
    @patch("dnd_engine.main.initialize_llm")
    @patch("dnd_engine.main.initialize_data_loader")
    @patch("dnd_engine.main.parse_arguments")
    def test_main_keyboard_interrupt(
        self,
        mock_parse_args,
        mock_init_loader,
        mock_init_llm,
        mock_event_bus,
        mock_save_manager_class,
        mock_show_save_menu,
        capsys
    ):
        """Test main handles keyboard interrupt gracefully."""
        mock_args = MagicMock(debug=False)
        mock_parse_args.return_value = mock_args
        mock_init_loader.return_value = MagicMock()
        mock_init_llm.return_value = None
        mock_event_bus.return_value = MagicMock()
        mock_save_manager_class.return_value = MagicMock()

        # Make save/load menu raise KeyboardInterrupt
        mock_show_save_menu.side_effect = KeyboardInterrupt()

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Game interrupted" in captured.out
        assert "Thanks for playing!" in captured.out

    @patch("dnd_engine.main.show_save_load_menu")
    @patch("dnd_engine.main.SaveManager")
    @patch("dnd_engine.main.EventBus")
    @patch("dnd_engine.main.initialize_llm")
    @patch("dnd_engine.main.initialize_data_loader")
    @patch("dnd_engine.main.parse_arguments")
    def test_main_exception_without_debug(
        self,
        mock_parse_args,
        mock_init_loader,
        mock_init_llm,
        mock_event_bus,
        mock_save_manager_class,
        mock_show_save_menu,
        capsys
    ):
        """Test main handles exceptions without debug mode."""
        mock_args = MagicMock(debug=False)
        mock_parse_args.return_value = mock_args
        mock_init_loader.return_value = MagicMock()
        mock_init_llm.return_value = None
        mock_event_bus.return_value = MagicMock()
        mock_save_manager_class.return_value = MagicMock()

        # Make save/load menu raise exception
        mock_show_save_menu.side_effect = Exception("Test error")

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Test error" in captured.out
        assert "Use --debug flag for detailed error information" in captured.out

    @patch("dnd_engine.main.show_save_load_menu")
    @patch("dnd_engine.main.SaveManager")
    @patch("dnd_engine.main.EventBus")
    @patch("dnd_engine.main.initialize_llm")
    @patch("dnd_engine.main.initialize_data_loader")
    @patch("dnd_engine.main.parse_arguments")
    def test_main_exception_with_debug(
        self,
        mock_parse_args,
        mock_init_loader,
        mock_init_llm,
        mock_event_bus,
        mock_save_manager_class,
        mock_show_save_menu
    ):
        """Test main re-raises exceptions in debug mode."""
        mock_args = MagicMock(debug=True)
        mock_parse_args.return_value = mock_args
        mock_init_loader.return_value = MagicMock()
        mock_init_llm.return_value = None
        mock_event_bus.return_value = MagicMock()
        mock_save_manager_class.return_value = MagicMock()

        # Make save/load menu raise exception
        mock_show_save_menu.side_effect = Exception("Test error")

        with pytest.raises(Exception) as exc_info:
            main()

        assert str(exc_info.value) == "Test error"

    @patch("dnd_engine.main.LLMEnhancer")
    @patch("dnd_engine.main.CLI")
    @patch("dnd_engine.main.GameState")
    @patch("dnd_engine.main.Party")
    @patch("dnd_engine.main.show_save_load_menu")
    @patch("dnd_engine.main.SaveManager")
    @patch("dnd_engine.main.create_new_party")
    @patch("dnd_engine.main.EventBus")
    @patch("dnd_engine.main.initialize_llm")
    @patch("dnd_engine.main.initialize_data_loader")
    @patch("dnd_engine.main.parse_arguments")
    @patch("builtins.input")
    def test_main_no_llm_provider(
        self,
        mock_input,
        mock_parse_args,
        mock_init_loader,
        mock_init_llm,
        mock_event_bus,
        mock_create_party,
        mock_save_manager_class,
        mock_show_save_menu,
        mock_party_class,
        mock_game_state_class,
        mock_cli_class,
        mock_llm_enhancer_class
    ):
        """Test main flow without LLM provider (no enhancer created)."""
        # Mock inputs for "Press Enter to begin your adventure"
        mock_input.side_effect = [""]

        mock_args = MagicMock(debug=False, dungeon="goblin_warren")
        mock_parse_args.return_value = mock_args

        mock_loader = MagicMock()
        mock_init_loader.return_value = mock_loader

        # No LLM provider
        mock_init_llm.return_value = None

        mock_bus = MagicMock()
        mock_event_bus.return_value = mock_bus

        # Mock save manager to return no saves (start new game)
        mock_save_manager = MagicMock()
        mock_save_manager_class.return_value = mock_save_manager
        mock_show_save_menu.return_value = None  # Start new game

        # Mock party creation
        mock_party = MagicMock()
        mock_party_class.return_value = mock_party
        mock_create_party.return_value = mock_party

        mock_game_state = MagicMock()
        mock_game_state_class.return_value = mock_game_state

        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        # Run main
        main()

        # Verify LLM enhancer was NOT created
        mock_llm_enhancer_class.assert_not_called()

        # Verify game still runs
        mock_cli.run.assert_called_once()


class TestMultiCharacterPartyCreation:
    """Test multi-character party creation flow."""

    @patch("dnd_engine.main.CLI")
    @patch("dnd_engine.main.GameState")
    @patch("dnd_engine.main.Party")
    @patch("dnd_engine.main.show_save_load_menu")
    @patch("dnd_engine.main.SaveManager")
    @patch("dnd_engine.main.CharacterFactory")
    @patch("dnd_engine.main.EventBus")
    @patch("dnd_engine.main.initialize_llm")
    @patch("dnd_engine.main.initialize_data_loader")
    @patch("dnd_engine.main.parse_arguments")
    @patch("builtins.input")
    def test_single_character_party(
        self,
        mock_input,
        mock_parse_args,
        mock_init_loader,
        mock_init_llm,
        mock_event_bus,
        mock_factory_class,
        mock_save_manager_class,
        mock_show_save_menu,
        mock_party_class,
        mock_game_state_class,
        mock_cli_class
    ):
        """Test creating a party with a single character."""
        # Mock inputs: party size = 1, then press Enter to start
        mock_input.side_effect = ["1", ""]  # Party size, then press Enter to start

        mock_args = MagicMock(no_llm=True, debug=False, dungeon="goblin_warren")
        mock_parse_args.return_value = mock_args

        mock_loader = MagicMock()
        mock_loader.load_races.return_value = {"human": {"name": "Human"}}
        mock_loader.load_classes.return_value = {"fighter": {"name": "Fighter"}}
        mock_init_loader.return_value = mock_loader
        mock_init_llm.return_value = None
        mock_event_bus.return_value = MagicMock()

        # Mock save manager to return no saves (start new game)
        mock_save_manager = MagicMock()
        mock_save_manager_class.return_value = mock_save_manager
        mock_show_save_menu.return_value = None  # Start new game

        # Mock character factory
        mock_factory = MagicMock()
        mock_character = MagicMock()
        mock_character.name = "Thorin"
        mock_character.race = "human"
        mock_character.max_hp = 12
        mock_character.armor_class = 16
        mock_factory.create_character_interactive.return_value = mock_character
        mock_factory_class.return_value = mock_factory

        mock_party = MagicMock()
        mock_party_class.return_value = mock_party

        mock_game_state = MagicMock()
        mock_game_state_class.return_value = mock_game_state

        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        # Run main
        main()

        # Verify party created with one character
        mock_party_class.assert_called_once()
        call_args = mock_party_class.call_args
        assert len(call_args.kwargs["characters"]) == 1
        assert call_args.kwargs["characters"][0] == mock_character

    @patch("dnd_engine.main.CLI")
    @patch("dnd_engine.main.GameState")
    @patch("dnd_engine.main.Party")
    @patch("dnd_engine.main.show_save_load_menu")
    @patch("dnd_engine.main.SaveManager")
    @patch("dnd_engine.main.CharacterFactory")
    @patch("dnd_engine.main.EventBus")
    @patch("dnd_engine.main.initialize_llm")
    @patch("dnd_engine.main.initialize_data_loader")
    @patch("dnd_engine.main.parse_arguments")
    @patch("builtins.input")
    def test_multi_character_party(
        self,
        mock_input,
        mock_parse_args,
        mock_init_loader,
        mock_init_llm,
        mock_event_bus,
        mock_factory_class,
        mock_save_manager_class,
        mock_show_save_menu,
        mock_party_class,
        mock_game_state_class,
        mock_cli_class
    ):
        """Test creating a party with multiple characters."""
        # Mock inputs: party size = 4, then press Enter to start
        mock_input.side_effect = ["4", ""]

        mock_args = MagicMock(no_llm=True, debug=False, dungeon="goblin_warren")
        mock_parse_args.return_value = mock_args

        mock_loader = MagicMock()
        mock_loader.load_races.return_value = {"human": {"name": "Human"}}
        mock_loader.load_classes.return_value = {"fighter": {"name": "Fighter"}}
        mock_init_loader.return_value = mock_loader
        mock_init_llm.return_value = None
        mock_event_bus.return_value = MagicMock()

        # Mock save manager to return no saves (start new game)
        mock_save_manager = MagicMock()
        mock_save_manager_class.return_value = mock_save_manager
        mock_show_save_menu.return_value = None  # Start new game

        # Mock character factory to create 4 different characters
        mock_factory = MagicMock()
        characters = []
        for i in range(4):
            char = MagicMock()
            char.name = f"Character{i+1}"
            char.race = "human"
            char.max_hp = 12
            char.armor_class = 16
            characters.append(char)

        mock_factory.create_character_interactive.side_effect = characters
        mock_factory_class.return_value = mock_factory

        mock_party = MagicMock()
        mock_party_class.return_value = mock_party

        mock_game_state = MagicMock()
        mock_game_state_class.return_value = mock_game_state

        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        # Run main
        main()

        # Verify character creation called 4 times
        assert mock_factory.create_character_interactive.call_count == 4

        # Verify party created with 4 characters
        mock_party_class.assert_called_once()
        call_args = mock_party_class.call_args
        assert len(call_args.kwargs["characters"]) == 4
        for i, char in enumerate(characters):
            assert call_args.kwargs["characters"][i] == char

    @patch("dnd_engine.main.CLI")
    @patch("dnd_engine.main.GameState")
    @patch("dnd_engine.main.Party")
    @patch("dnd_engine.main.show_save_load_menu")
    @patch("dnd_engine.main.SaveManager")
    @patch("dnd_engine.main.CharacterFactory")
    @patch("dnd_engine.main.EventBus")
    @patch("dnd_engine.main.initialize_llm")
    @patch("dnd_engine.main.initialize_data_loader")
    @patch("dnd_engine.main.parse_arguments")
    @patch("builtins.input")
    def test_invalid_party_size_then_valid(
        self,
        mock_input,
        mock_parse_args,
        mock_init_loader,
        mock_init_llm,
        mock_event_bus,
        mock_factory_class,
        mock_save_manager_class,
        mock_show_save_menu,
        mock_party_class,
        mock_game_state_class,
        mock_cli_class,
        capsys
    ):
        """Test that invalid party sizes are rejected."""
        # Try invalid inputs first, then valid
        mock_input.side_effect = ["0", "5", "abc", "2", ""]

        mock_args = MagicMock(no_llm=True, debug=False, dungeon="goblin_warren")
        mock_parse_args.return_value = mock_args

        mock_loader = MagicMock()
        mock_loader.load_races.return_value = {"human": {"name": "Human"}}
        mock_loader.load_classes.return_value = {"fighter": {"name": "Fighter"}}
        mock_init_loader.return_value = mock_loader
        mock_init_llm.return_value = None
        mock_event_bus.return_value = MagicMock()

        # Mock save manager to return no saves (start new game)
        mock_save_manager = MagicMock()
        mock_save_manager_class.return_value = mock_save_manager
        mock_show_save_menu.return_value = None  # Start new game

        # Mock character factory
        mock_factory = MagicMock()
        char1 = MagicMock(name="Hero1", race="human", max_hp=12, armor_class=16)
        char2 = MagicMock(name="Hero2", race="human", max_hp=12, armor_class=16)
        mock_factory.create_character_interactive.side_effect = [char1, char2]
        mock_factory_class.return_value = mock_factory

        mock_party_class.return_value = MagicMock()
        mock_game_state_class.return_value = MagicMock()
        mock_cli_class.return_value = MagicMock()

        # Run main
        main()

        # Check output for error messages
        captured = capsys.readouterr()
        assert "Please enter a number between 1 and 4" in captured.out
        assert "Please enter a valid number" in captured.out

        # Verify party created with 2 characters
        call_args = mock_party_class.call_args
        assert len(call_args.kwargs["characters"]) == 2
