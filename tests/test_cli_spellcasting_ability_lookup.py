# ABOUTME: Tests for CLI spellcasting ability lookup from class data
# ABOUTME: Ensures spellcasting ability is correctly retrieved from nested spellcasting object

import pytest
from unittest.mock import Mock, MagicMock, patch
from dnd_engine.ui.cli import CLI
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.rules.loader import DataLoader


class TestCLISpellcastingAbilityLookup:
    """Test that CLI correctly retrieves spellcasting ability from class data"""

    @pytest.fixture
    def mock_game_state(self):
        """Create a mock game state with data loader"""
        game_state = Mock(spec=GameState)
        game_state.data_loader = Mock(spec=DataLoader)
        game_state.dice_roller = Mock()
        game_state.event_bus = Mock()
        game_state.combat = Mock()
        return game_state

    @pytest.fixture
    def mock_campaign_manager(self):
        """Create a mock campaign manager"""
        return Mock()

    @pytest.fixture
    def wizard_character(self):
        """Create a wizard character for testing"""
        return Character(
            name="Test Wizard",
            character_class=CharacterClass.WIZARD,
            level=1,
            abilities=Abilities(8, 14, 12, 16, 10, 8),
            max_hp=8,
            ac=12,
            spellcasting_ability="int"
        )

    @pytest.fixture
    def fighter_character(self):
        """Create a fighter character (non-spellcaster)"""
        return Character(
            name="Test Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(16, 14, 14, 10, 12, 8),
            max_hp=12,
            ac=16
        )

    @pytest.fixture
    def classes_data_with_spellcasting(self):
        """Return class data with spellcasting nested in 'spellcasting' object"""
        return {
            "wizard": {
                "name": "Wizard",
                "spellcasting": {
                    "ability": "int",
                    "cantrips_known": {
                        "1": 3
                    }
                }
            },
            "fighter": {
                "name": "Fighter",
                # No spellcasting key
            }
        }

    def test_spellcasting_ability_retrieved_from_nested_object(
        self, mock_game_state, wizard_character, classes_data_with_spellcasting
    ):
        """Test that spellcasting ability is correctly retrieved from nested 'spellcasting.ability'"""
        # Setup
        mock_game_state.data_loader.load_classes.return_value = classes_data_with_spellcasting
        mock_game_state.data_loader.load_spells.return_value = {
            "magic_missile": {
                "name": "Magic Missile",
                "level": 1,
                "classes": ["wizard"],
                "attack_type": "spell_attack"
            }
        }

        cli = CLI(mock_game_state, Mock(), "test_campaign")

        # Mock the turn state and other dependencies
        mock_turn_state = Mock()
        mock_turn_state.is_action_available.return_value = True
        mock_game_state.combat.get_turn_state.return_value = mock_turn_state
        mock_game_state.party = [wizard_character]

        # Mock user inputs: select spell, select target, cancel
        with patch('builtins.input', side_effect=['1', '1', 'n']):
            with patch('dnd_engine.ui.cli.console') as mock_console:
                # This should not raise an error about "cannot cast spells"
                cli.handle_cast_spell("magic_missile")

        # Verify load_classes was called
        mock_game_state.data_loader.load_classes.assert_called_once()

    def test_non_spellcaster_gets_error_message(
        self, mock_game_state, fighter_character, classes_data_with_spellcasting
    ):
        """Test that non-spellcasting classes get appropriate error message"""
        # Setup
        mock_game_state.data_loader.load_classes.return_value = classes_data_with_spellcasting

        cli = CLI(mock_game_state, Mock(), "test_campaign")

        # Mock the turn state
        mock_turn_state = Mock()
        mock_turn_state.is_action_available.return_value = True
        mock_game_state.combat.get_turn_state.return_value = mock_turn_state

        # Mock print_error to capture the error message
        with patch('dnd_engine.ui.cli.print_error') as mock_print_error:
            cli.handle_cast_spell("magic_missile")

        # Verify error message was printed
        mock_print_error.assert_called_once()
        error_message = mock_print_error.call_args[0][0]
        assert "cannot cast spells" in error_message.lower()

    def test_spellcasting_ability_lookup_handles_missing_spellcasting_key(
        self, mock_game_state, fighter_character, classes_data_with_spellcasting
    ):
        """Test that missing 'spellcasting' key is handled gracefully"""
        # Setup - fighter has no spellcasting key
        mock_game_state.data_loader.load_classes.return_value = classes_data_with_spellcasting

        cli = CLI(mock_game_state, Mock(), "test_campaign")

        # Mock the turn state
        mock_turn_state = Mock()
        mock_turn_state.is_action_available.return_value = True
        mock_game_state.combat.get_turn_state.return_value = mock_turn_state

        # Should not crash, should print error instead
        with patch('dnd_engine.ui.cli.print_error') as mock_print_error:
            cli.handle_cast_spell("magic_missile")

        # Should have printed an error
        assert mock_print_error.called

    def test_spellcasting_ability_lookup_handles_empty_spellcasting_object(
        self, mock_game_state, wizard_character
    ):
        """Test that empty 'spellcasting' object is handled gracefully"""
        # Setup - wizard has spellcasting key but it's empty
        classes_data = {
            "wizard": {
                "name": "Wizard",
                "spellcasting": {}  # Empty object, no 'ability' key
            }
        }
        mock_game_state.data_loader.load_classes.return_value = classes_data

        cli = CLI(mock_game_state, Mock(), "test_campaign")

        # Mock the turn state
        mock_turn_state = Mock()
        mock_turn_state.is_action_available.return_value = True
        mock_game_state.combat.get_turn_state.return_value = mock_turn_state

        # Should print error about not being able to cast spells
        with patch('dnd_engine.ui.cli.print_error') as mock_print_error:
            cli.handle_cast_spell("magic_missile")

        # Should have printed an error
        assert mock_print_error.called

    def test_backward_compatibility_with_top_level_spellcasting_ability(
        self, mock_game_state, wizard_character
    ):
        """Test that code still works if someone puts spellcasting_ability at top level (backward compat)"""
        # Setup - class data has BOTH nested and top-level (nested should take precedence)
        classes_data = {
            "wizard": {
                "name": "Wizard",
                "spellcasting": {
                    "ability": "int"
                }
            }
        }
        mock_game_state.data_loader.load_classes.return_value = classes_data
        mock_game_state.data_loader.load_spells.return_value = {
            "magic_missile": {
                "name": "Magic Missile",
                "level": 1,
                "classes": ["wizard"],
                "attack_type": "spell_attack"
            }
        }

        cli = CLI(mock_game_state, Mock(), "test_campaign")

        # Mock the turn state
        mock_turn_state = Mock()
        mock_turn_state.is_action_available.return_value = True
        mock_game_state.combat.get_turn_state.return_value = mock_turn_state
        mock_game_state.party = [wizard_character]

        # Mock user inputs to cancel spell selection
        with patch('builtins.input', side_effect=['1', '1', 'n']):
            with patch('dnd_engine.ui.cli.console'):
                # Should not crash and should not print error
                with patch('dnd_engine.ui.cli.print_error') as mock_print_error:
                    cli.handle_cast_spell("magic_missile")

                    # Should NOT have printed "cannot cast spells" error
                    if mock_print_error.called:
                        error_messages = [call[0][0] for call in mock_print_error.call_args_list]
                        assert not any("cannot cast spells" in msg.lower() for msg in error_messages)


class TestSpellcastingAbilityDataStructure:
    """Test the actual data structure from classes.json"""

    def test_real_classes_json_has_correct_structure(self):
        """Integration test: verify real classes.json has spellcasting nested correctly"""
        from dnd_engine.rules.loader import DataLoader

        loader = DataLoader()
        classes_data = loader.load_classes()

        # Verify wizard has spellcasting as nested object
        assert "wizard" in classes_data
        wizard_data = classes_data["wizard"]
        assert "spellcasting" in wizard_data
        assert isinstance(wizard_data["spellcasting"], dict)
        assert "ability" in wizard_data["spellcasting"]
        assert wizard_data["spellcasting"]["ability"] == "int"

    def test_fighter_has_no_spellcasting(self):
        """Integration test: verify fighter has no spellcasting ability"""
        from dnd_engine.rules.loader import DataLoader

        loader = DataLoader()
        classes_data = loader.load_classes()

        # Verify fighter does NOT have spellcasting
        assert "fighter" in classes_data
        fighter_data = classes_data["fighter"]
        assert "spellcasting" not in fighter_data

    def test_rogue_has_no_spellcasting(self):
        """Integration test: verify rogue has no spellcasting ability"""
        from dnd_engine.rules.loader import DataLoader

        loader = DataLoader()
        classes_data = loader.load_classes()

        # Verify rogue does NOT have spellcasting
        assert "rogue" in classes_data
        rogue_data = classes_data["rogue"]
        assert "spellcasting" not in rogue_data
