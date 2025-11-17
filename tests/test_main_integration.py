# ABOUTME: Integration tests for main.py game flow
# ABOUTME: Tests full startup sequence with different configurations

import os
from unittest.mock import MagicMock, Mock, patch

import pytest

from dnd_engine.main import main


class TestFullStartupSequence:
    """Test complete startup sequence with mocked dependencies."""

    @patch("dnd_engine.main.CLI")
    @patch("dnd_engine.main.GameState")
    @patch("dnd_engine.main.Party")
    @patch("dnd_engine.main.CharacterFactory")
    @patch("dnd_engine.main.LLMEnhancer")
    @patch("dnd_engine.main.create_llm_provider")
    @patch("dnd_engine.main.DataLoader")
    @patch("builtins.input", return_value="")
    @patch("sys.argv", ["dnd-game"])
    def test_full_flow_with_openai(
        self,
        mock_input,
        mock_loader_class,
        mock_create_llm,
        mock_enhancer_class,
        mock_factory_class,
        mock_party_class,
        mock_game_state_class,
        mock_cli_class,
        capsys
    ):
        """Test complete flow: args → data → LLM (OpenAI) → character → game."""
        # Setup data loader
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load_races.return_value = {
            "human": {"name": "Human", "ability_bonuses": {}}
        }
        mock_loader.load_classes.return_value = {
            "fighter": {"name": "Fighter"}
        }

        # Setup LLM provider (OpenAI)
        mock_provider = MagicMock()
        mock_provider.get_provider_name.return_value = "OpenAI (gpt-4o-mini)"
        mock_create_llm.return_value = mock_provider

        # Setup character creation
        mock_character = MagicMock()
        mock_character.name = "TestChar"
        mock_character.race = "human"

        mock_factory = MagicMock()
        mock_factory.create_character_interactive.return_value = mock_character
        mock_factory_class.return_value = mock_factory

        # Setup game state and CLI
        mock_party = MagicMock()
        mock_party_class.return_value = mock_party

        mock_game_state = MagicMock()
        mock_game_state_class.return_value = mock_game_state

        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        # Run main
        main()

        # Verify the complete flow
        captured = capsys.readouterr()

        # 1. Banner displayed
        assert "D&D 5E Terminal Adventure" in captured.out

        # 2. Configuration check
        assert "Checking configuration..." in captured.out

        # 3. Data loaded
        assert "✓ Data files loaded" in captured.out

        # 4. LLM provider initialized
        assert "✓ LLM provider: OpenAI" in captured.out

        # 5. Character creation prompt
        assert "Let's create your character!" in captured.out

        # 6. Character created message
        assert "Character created: TestChar" in captured.out

        # 7. Adventure start prompt
        assert "Press Enter to begin your adventure" in captured.out

        # 8. Verify components created in order
        mock_loader_class.assert_called_once()
        mock_create_llm.assert_called_once()
        mock_enhancer_class.assert_called_once()
        mock_factory.create_character_interactive.assert_called_once()
        mock_party_class.assert_called_once_with(characters=[mock_character])
        mock_game_state_class.assert_called_once()
        mock_cli_class.assert_called_once()
        mock_cli.run.assert_called_once()

    @patch("dnd_engine.main.CLI")
    @patch("dnd_engine.main.GameState")
    @patch("dnd_engine.main.Party")
    @patch("dnd_engine.main.CharacterFactory")
    @patch("dnd_engine.main.LLMEnhancer")
    @patch("dnd_engine.main.create_llm_provider")
    @patch("dnd_engine.main.DataLoader")
    @patch("builtins.input", return_value="")
    @patch("sys.argv", ["dnd-game", "--llm-provider", "anthropic"])
    def test_full_flow_with_anthropic(
        self,
        mock_input,
        mock_loader_class,
        mock_create_llm,
        mock_enhancer_class,
        mock_factory_class,
        mock_party_class,
        mock_game_state_class,
        mock_cli_class,
        capsys
    ):
        """Test complete flow with Anthropic provider."""
        # Setup data loader
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load_races.return_value = {
            "elf": {"name": "Elf", "ability_bonuses": {}}
        }
        mock_loader.load_classes.return_value = {
            "fighter": {"name": "Fighter"}
        }

        # Setup LLM provider (Anthropic)
        mock_provider = MagicMock()
        mock_provider.get_provider_name.return_value = "Anthropic (claude-3-5-haiku-20241022)"
        mock_create_llm.return_value = mock_provider

        # Setup character creation
        mock_character = MagicMock()
        mock_character.name = "Legolas"
        mock_character.race = "elf"

        mock_factory = MagicMock()
        mock_factory.create_character_interactive.return_value = mock_character
        mock_factory_class.return_value = mock_factory

        # Setup game components
        mock_party_class.return_value = MagicMock()
        mock_game_state_class.return_value = MagicMock()
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        # Run main
        main()

        # Verify Anthropic provider was used
        captured = capsys.readouterr()
        assert "✓ LLM provider: Anthropic" in captured.out

        # Verify LLM enhancer was created
        mock_enhancer_class.assert_called_once()

        # Verify game ran
        mock_cli.run.assert_called_once()

    @patch("dnd_engine.main.CLI")
    @patch("dnd_engine.main.GameState")
    @patch("dnd_engine.main.Party")
    @patch("dnd_engine.main.CharacterFactory")
    @patch("dnd_engine.main.LLMEnhancer")
    @patch("dnd_engine.main.create_llm_provider")
    @patch("dnd_engine.main.DataLoader")
    @patch("builtins.input", return_value="")
    @patch("sys.argv", ["dnd-game", "--no-llm"])
    def test_full_flow_without_llm(
        self,
        mock_input,
        mock_loader_class,
        mock_create_llm,
        mock_enhancer_class,
        mock_factory_class,
        mock_party_class,
        mock_game_state_class,
        mock_cli_class,
        capsys
    ):
        """Test complete flow without LLM (--no-llm flag)."""
        # Setup data loader
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load_races.return_value = {
            "dwarf": {"name": "Dwarf", "ability_bonuses": {}}
        }
        mock_loader.load_classes.return_value = {
            "fighter": {"name": "Fighter"}
        }

        # Setup character creation
        mock_character = MagicMock()
        mock_character.name = "Gimli"
        mock_character.race = "dwarf"

        mock_factory = MagicMock()
        mock_factory.create_character_interactive.return_value = mock_character
        mock_factory_class.return_value = mock_factory

        # Setup game components
        mock_party_class.return_value = MagicMock()
        mock_game_state_class.return_value = MagicMock()
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        # Run main
        main()

        # Verify LLM was disabled
        captured = capsys.readouterr()
        assert "⚠ LLM disabled (--no-llm flag)" in captured.out

        # Verify LLM enhancer was NOT created
        mock_enhancer_class.assert_not_called()

        # Verify create_llm_provider was NOT called (disabled by flag)
        mock_create_llm.assert_not_called()

        # Verify game still ran
        mock_cli.run.assert_called_once()


class TestDungeonSelection:
    """Test dungeon selection and loading."""

    @patch("dnd_engine.main.CLI")
    @patch("dnd_engine.main.GameState")
    @patch("dnd_engine.main.Party")
    @patch("dnd_engine.main.CharacterFactory")
    @patch("dnd_engine.main.create_llm_provider")
    @patch("dnd_engine.main.DataLoader")
    @patch("builtins.input", return_value="")
    @patch("sys.argv", ["dnd-game", "--dungeon", "goblin_warren", "--no-llm"])
    def test_valid_dungeon_loads(
        self,
        mock_input,
        mock_loader_class,
        mock_create_llm,
        mock_factory_class,
        mock_party_class,
        mock_game_state_class,
        mock_cli_class
    ):
        """Test that valid dungeon name loads correctly."""
        # Setup mocks
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load_races.return_value = {"human": {"name": "Human"}}
        mock_loader.load_classes.return_value = {"fighter": {"name": "Fighter"}}

        mock_character = MagicMock()
        mock_character.name = "Hero"
        mock_character.race = "human"

        mock_factory = MagicMock()
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

        # Verify GameState was created with correct dungeon
        mock_game_state_class.assert_called_once()
        call_kwargs = mock_game_state_class.call_args[1]
        assert call_kwargs["dungeon_name"] == "goblin_warren"

    @patch("dnd_engine.main.CLI")
    @patch("dnd_engine.main.GameState")
    @patch("dnd_engine.main.Party")
    @patch("dnd_engine.main.CharacterFactory")
    @patch("dnd_engine.main.create_llm_provider")
    @patch("dnd_engine.main.DataLoader")
    @patch("builtins.input", return_value="")
    @patch("sys.argv", ["dnd-game", "--dungeon", "dragon_lair", "--no-llm"])
    def test_custom_dungeon_loads(
        self,
        mock_input,
        mock_loader_class,
        mock_create_llm,
        mock_factory_class,
        mock_party_class,
        mock_game_state_class,
        mock_cli_class
    ):
        """Test that custom dungeon name is passed to GameState."""
        # Setup mocks
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load_races.return_value = {"human": {"name": "Human"}}
        mock_loader.load_classes.return_value = {"fighter": {"name": "Fighter"}}

        mock_character = MagicMock()
        mock_character.name = "Dragonslayer"
        mock_character.race = "human"

        mock_factory = MagicMock()
        mock_factory.create_character_interactive.return_value = mock_character
        mock_factory_class.return_value = mock_factory

        mock_party_class.return_value = MagicMock()
        mock_game_state_class.return_value = MagicMock()
        mock_cli_class.return_value = MagicMock()

        # Run main
        main()

        # Verify GameState was created with custom dungeon
        call_kwargs = mock_game_state_class.call_args[1]
        assert call_kwargs["dungeon_name"] == "dragon_lair"

    @patch("dnd_engine.main.CharacterFactory")
    @patch("dnd_engine.main.create_llm_provider")
    @patch("dnd_engine.main.DataLoader")
    @patch("builtins.input", return_value="")
    @patch("sys.argv", ["dnd-game", "--dungeon", "invalid_dungeon", "--no-llm"])
    def test_invalid_dungeon_shows_error(
        self,
        mock_input,
        mock_loader_class,
        mock_create_llm,
        mock_factory_class,
        capsys
    ):
        """Test that invalid dungeon name shows error from GameState."""
        # Setup data loader
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load_races.return_value = {"human": {"name": "Human"}}
        mock_loader.load_classes.return_value = {"fighter": {"name": "Fighter"}}

        # Setup character creation
        mock_character = MagicMock()
        mock_character.name = "Hero"
        mock_character.race = "human"

        mock_factory = MagicMock()
        mock_factory.create_character_interactive.return_value = mock_character
        mock_factory_class.return_value = mock_factory

        # GameState will raise error for invalid dungeon
        with patch("dnd_engine.main.GameState") as mock_game_state_class:
            mock_game_state_class.side_effect = FileNotFoundError(
                "Dungeon 'invalid_dungeon' not found"
            )

            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "✗ Error:" in captured.out
            assert "invalid_dungeon" in captured.out


class TestErrorRecovery:
    """Test error handling and recovery."""

    @patch("dnd_engine.main.DataLoader")
    @patch("sys.argv", ["dnd-game"])
    def test_missing_data_files_exits_gracefully(self, mock_loader_class, capsys):
        """Test that missing data files show helpful error."""
        mock_loader_class.side_effect = FileNotFoundError(
            "Data directory not found: dnd_engine/data/"
        )

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "✗ Error: Data files not found" in captured.out
        assert "Please ensure the game is installed correctly" in captured.out

    @patch("dnd_engine.main.CharacterFactory")
    @patch("dnd_engine.main.create_llm_provider")
    @patch("dnd_engine.main.DataLoader")
    @patch("sys.argv", ["dnd-game", "--no-llm", "--debug"])
    def test_debug_mode_shows_full_traceback(
        self,
        mock_loader_class,
        mock_create_llm,
        mock_factory_class
    ):
        """Test that debug mode re-raises exceptions for full traceback."""
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader

        mock_factory = MagicMock()
        mock_factory.create_character_interactive.side_effect = ValueError("Test error")
        mock_factory_class.return_value = mock_factory

        # In debug mode, exception should be re-raised
        with pytest.raises(ValueError) as exc_info:
            main()

        assert str(exc_info.value) == "Test error"


class TestMultiCharacterPartyIntegration:
    """Integration tests for multi-character party creation and gameplay."""

    @patch("dnd_engine.main.CLI")
    @patch("dnd_engine.main.GameState")
    @patch("dnd_engine.main.Party")
    @patch("dnd_engine.main.CharacterFactory")
    @patch("dnd_engine.main.DataLoader")
    @patch("builtins.input")
    @patch("sys.argv", ["dnd-game", "--no-llm"])
    def test_create_four_character_party(
        self,
        mock_input,
        mock_loader_class,
        mock_factory_class,
        mock_party_class,
        mock_game_state_class,
        mock_cli_class,
        capsys
    ):
        """Test creating a full 4-character party and starting the game."""
        # Mock inputs: party size = 4, then press Enter to start
        mock_input.side_effect = ["4", ""]

        # Setup data loader
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load_races.return_value = {
            "human": {"name": "Human"},
            "elf": {"name": "Elf"},
            "dwarf": {"name": "Dwarf"}
        }
        mock_loader.load_classes.return_value = {
            "fighter": {"name": "Fighter"}
        }

        # Setup character creation for 4 characters
        mock_factory = MagicMock()
        characters = [
            MagicMock(name="Thorin", race="dwarf", max_hp=15, armor_class=18),
            MagicMock(name="Legolas", race="elf", max_hp=11, armor_class=16),
            MagicMock(name="Aragorn", race="human", max_hp=13, armor_class=17),
            MagicMock(name="Gimli", race="dwarf", max_hp=14, armor_class=18),
        ]
        mock_factory.create_character_interactive.side_effect = characters
        mock_factory_class.return_value = mock_factory

        # Setup game components
        mock_party = MagicMock()
        mock_party_class.return_value = mock_party

        mock_game_state = MagicMock()
        mock_game_state_class.return_value = mock_game_state

        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        # Run main
        main()

        # Verify output
        captured = capsys.readouterr()
        assert "How many characters in your party?" in captured.out
        assert "Let's create your party of 4!" in captured.out
        assert "CHARACTER 1 of 4" in captured.out
        assert "CHARACTER 2 of 4" in captured.out
        assert "CHARACTER 3 of 4" in captured.out
        assert "CHARACTER 4 of 4" in captured.out
        assert "PARTY ROSTER" in captured.out
        assert "Thorin" in captured.out
        assert "Legolas" in captured.out
        assert "Aragorn" in captured.out
        assert "Gimli" in captured.out

        # Verify character creation called 4 times
        assert mock_factory.create_character_interactive.call_count == 4

        # Verify party created with all 4 characters
        mock_party_class.assert_called_once()
        call_args = mock_party_class.call_args
        assert len(call_args.kwargs["characters"]) == 4

        # Verify game started
        mock_cli.run.assert_called_once()

    @patch("dnd_engine.main.CLI")
    @patch("dnd_engine.main.GameState")
    @patch("dnd_engine.main.Party")
    @patch("dnd_engine.main.CharacterFactory")
    @patch("dnd_engine.main.DataLoader")
    @patch("builtins.input")
    @patch("sys.argv", ["dnd-game", "--no-llm"])
    def test_single_character_party_no_roster(
        self,
        mock_input,
        mock_loader_class,
        mock_factory_class,
        mock_party_class,
        mock_game_state_class,
        mock_cli_class,
        capsys
    ):
        """Test that single character parties don't show roster (only multi-char)."""
        # Mock inputs: party size = 1, then press Enter to start
        mock_input.side_effect = ["1", ""]

        # Setup data loader
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load_races.return_value = {"human": {"name": "Human"}}
        mock_loader.load_classes.return_value = {"fighter": {"name": "Fighter"}}

        # Setup character creation
        mock_factory = MagicMock()
        character = MagicMock(name="Solo", race="human", max_hp=12, armor_class=16)
        mock_factory.create_character_interactive.return_value = character
        mock_factory_class.return_value = mock_factory

        # Setup game components
        mock_party_class.return_value = MagicMock()
        mock_game_state_class.return_value = MagicMock()
        mock_cli_class.return_value = MagicMock()

        # Run main
        main()

        # Verify output
        captured = capsys.readouterr()
        assert "Let's create your party of 1!" in captured.out
        assert "CHARACTER 1 of" not in captured.out  # Should not show character counter
        assert "PARTY ROSTER" not in captured.out  # Should not show roster for solo
        assert "Solo" in captured.out

    @patch("dnd_engine.main.CLI")
    @patch("dnd_engine.main.GameState")
    @patch("dnd_engine.main.Party")
    @patch("dnd_engine.main.CharacterFactory")
    @patch("dnd_engine.main.DataLoader")
    @patch("builtins.input")
    @patch("sys.argv", ["dnd-game", "--no-llm"])
    def test_party_passed_to_game_state(
        self,
        mock_input,
        mock_loader_class,
        mock_factory_class,
        mock_party_class,
        mock_game_state_class,
        mock_cli_class
    ):
        """Test that the created party is correctly passed to GameState."""
        # Mock inputs: party size = 2
        mock_input.side_effect = ["2", ""]

        # Setup data loader
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load_races.return_value = {"human": {"name": "Human"}}
        mock_loader.load_classes.return_value = {"fighter": {"name": "Fighter"}}

        # Setup character creation
        mock_factory = MagicMock()
        char1 = MagicMock(name="Hero1", race="human")
        char2 = MagicMock(name="Hero2", race="human")
        mock_factory.create_character_interactive.side_effect = [char1, char2]
        mock_factory_class.return_value = mock_factory

        # Setup game components
        mock_party = MagicMock()
        mock_party_class.return_value = mock_party

        mock_game_state = MagicMock()
        mock_game_state_class.return_value = mock_game_state

        mock_cli_class.return_value = MagicMock()

        # Run main
        main()

        # Verify Party was created with both characters
        mock_party_class.assert_called_once_with(characters=[char1, char2])

        # Verify GameState was initialized with the party
        mock_game_state_class.assert_called_once()
        call_kwargs = mock_game_state_class.call_args.kwargs
        assert call_kwargs["party"] == mock_party
        assert call_kwargs["dungeon_name"] == "goblin_warren"
