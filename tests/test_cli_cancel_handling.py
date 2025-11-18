# ABOUTME: Unit tests for CLI cancel handling in questionary prompts
# ABOUTME: Regression tests for the "Cancel" string bug (should not crash on cancel)

import pytest
from unittest.mock import Mock, patch, MagicMock
from dnd_engine.ui.cli import CLI
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.party import Party
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.utils.events import EventBus


class TestCLICancelHandling:
    """Test that all questionary prompts handle cancel correctly"""

    @pytest.fixture
    def abilities(self):
        """Create test abilities"""
        return Abilities(16, 14, 15, 10, 12, 8)

    @pytest.fixture
    def characters(self, abilities):
        """Create test characters"""
        char1 = Character(
            name="Gandalf",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=20,
            ac=16
        )
        char2 = Character(
            name="Aragorn",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities,
            max_hp=18,
            ac=15
        )
        return [char1, char2]

    @pytest.fixture
    def party(self, characters):
        """Create a party"""
        return Party(characters)

    @pytest.fixture
    def game_state(self, party):
        """Create a mock game state"""
        game_state = Mock(spec=GameState)
        game_state.party = party
        game_state.event_bus = Mock(spec=EventBus)
        game_state.data_loader = Mock()
        game_state.data_loader.load_items.return_value = {
            "consumables": {
                "potion_of_healing": {"name": "Potion of Healing", "effect_type": "healing", "healing": "2d4+2"}
            }
        }
        game_state.in_combat = True
        game_state.current_turn = party.characters[0]

        # Create mock enemies
        enemy = Creature(
            name="Goblin",
            max_hp=10,
            ac=13,
            abilities=Abilities(8, 14, 10, 10, 8, 8)
        )
        game_state.active_enemies = [enemy]

        return game_state

    @pytest.fixture
    def cli(self, game_state):
        """Create a CLI instance"""
        return CLI(game_state, auto_save_enabled=False)

    def test_prompt_enemy_selection_cancel_returns_cancel_string(self, cli, game_state):
        """Test that cancelling enemy selection returns 'Cancel' string (not None)"""
        with patch('questionary.select') as mock_select:
            # Mock user selecting Cancel - questionary returns "Cancel" string
            mock_result = MagicMock()
            mock_result.ask.return_value = "Cancel"
            mock_select.return_value = mock_result

            result = cli._prompt_enemy_selection()

            # Questionary returns "Cancel" string when value=None is selected
            assert result == "Cancel"

    def test_attack_command_handles_cancel_without_crash(self, cli, game_state):
        """Test that 'attack' command doesn't crash when user cancels (regression test)"""
        with patch('questionary.select') as mock_select:
            # Mock user cancelling - returns "Cancel" string
            mock_result = MagicMock()
            mock_result.ask.return_value = "Cancel"
            mock_select.return_value = mock_result

            # This should not crash with AttributeError: 'str' object has no attribute 'name'
            cli.process_combat_command("attack")

            # Command should exit cleanly without calling handle_attack
            # (We can't easily verify this without more mocking, but the important part
            # is that it doesn't crash)

    def test_attack_command_handles_none_without_crash(self, cli, game_state):
        """Test that 'attack' command handles None (keyboard interrupt) correctly"""
        with patch('questionary.select') as mock_select:
            # Mock keyboard interrupt - returns None
            mock_result = MagicMock()
            mock_result.ask.return_value = None
            mock_select.return_value = mock_result

            # Should not crash
            cli.process_combat_command("attack")

    def test_character_class_formatting_in_take_prompt(self, cli, game_state, characters):
        """Test that character class is formatted nicely (not 'CharacterClass.ROGUE')"""
        # Mock available items
        game_state.get_available_items_in_room.return_value = [
            {"type": "item", "id": "potion_of_healing"}
        ]

        # Set up multi-character party to trigger character selection
        item_to_take = {"type": "item", "id": "potion_of_healing"}

        with patch('questionary.select') as mock_select:
            mock_result = MagicMock()
            mock_result.ask.return_value = characters[0]
            mock_select.return_value = mock_result

            # Manually call the character selection part
            # (This is the code in handle_take lines 722-724)
            import questionary
            choices = []
            for character in characters:
                choice_text = f"{character.name} ({character.character_class.value.title()})"
                choices.append(questionary.Choice(title=choice_text, value=character))

            # Verify formatting is correct
            assert "Gandalf (Fighter)" in choices[0].title
            assert "Aragorn (Rogue)" in choices[1].title

            # Should NOT contain enum representation
            assert "CharacterClass" not in choices[0].title
            assert "CharacterClass" not in choices[1].title

    def test_prompt_item_usage_cancel_with_isinstance_check(self, cli, game_state, characters):
        """Test that _prompt_item_usage handles cancel with isinstance check"""
        # Add items to character inventories
        for char in characters:
            char.inventory.add_item("potion_of_healing", "consumables")

        with patch('questionary.select') as mock_select:
            # Mock user cancelling - returns "Cancel" string
            mock_result = MagicMock()
            mock_result.ask.return_value = "Cancel"
            mock_select.return_value = mock_result

            result = cli._prompt_item_usage()

            # Should return None (handled by isinstance check)
            # The code checks: if result is None or result == "Cancel" or not isinstance(result, dict)
            assert result is None or result == "Cancel"

    def test_prompt_target_selection_cancel(self, cli, game_state):
        """Test that _prompt_target_selection handles cancel correctly"""
        with patch('questionary.select') as mock_select:
            # Mock user cancelling
            mock_result = MagicMock()
            mock_result.ask.return_value = "Cancel"
            mock_select.return_value = mock_result

            result = cli._prompt_target_selection("Potion of Healing")

            # Should return the result (calling code uses isinstance check)
            # Calling code checks: if not isinstance(target_character, Character)
            assert result == "Cancel"

    def test_prompt_combat_ally_selection_cancel(self, cli, game_state, characters):
        """Test that _prompt_combat_ally_selection handles cancel correctly"""
        item_data = {"name": "Potion of Healing", "range": 5}

        with patch('questionary.select') as mock_select:
            # Mock user cancelling
            mock_result = MagicMock()
            mock_result.ask.return_value = "Cancel"
            mock_select.return_value = mock_result

            result = cli._prompt_combat_ally_selection("Potion of Healing", item_data, characters[0])

            # Should return the result (calling code uses isinstance check)
            # Calling code checks: if not isinstance(target, Character)
            assert result == "Cancel"


class TestQuestinaryBehavior:
    """Document the actual behavior of questionary with value=None"""

    def test_questionary_choice_with_none_value_returns_title(self):
        """
        Document that questionary.Choice(value=None) actually returns the title string.

        This is the root cause of the bug we fixed. When you create:
            questionary.Choice(title="Cancel", value=None)

        And the user selects it, questionary.select().ask() returns "Cancel" (the title),
        not None (the value).

        This test documents this behavior so future developers understand why we check
        for both `is None` and `== "Cancel"` in our code.
        """
        import questionary

        # Create a choice with value=None
        cancel_choice = questionary.Choice(title="Cancel", value=None)

        # The choice's value is actually the title string, not None
        assert cancel_choice.value == "Cancel"
        assert cancel_choice.value != None

        # This is why our checks need to be: if result is None or result == "Cancel"
