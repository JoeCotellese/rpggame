# ABOUTME: Unit tests for GameState player condition removal methods
# ABOUTME: Tests get_removable_conditions() and attempt_player_condition_removal()

from unittest.mock import Mock

import pytest

from dnd_engine.core.character import Character
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import (
    GameState,
)
from dnd_engine.core.party import Party
from dnd_engine.systems.action_economy import ActionType, TurnState
from dnd_engine.systems.condition_manager import AbilityCheckResult


class TestGetRemovableConditions:
    """Test GameState.get_removable_conditions() method"""

    @pytest.fixture
    def mock_data_loader(self):
        """Create a mock data loader"""
        from pathlib import Path

        loader = Mock()
        loader.load_dungeon.return_value = {
            "name": "Test Dungeon",
            "rooms": {},
            "start_room": "entrance",
        }
        loader.data_path = Path("/nonexistent")
        return loader

    @pytest.fixture
    def character_on_fire(self):
        """Create a character with the on_fire condition"""
        abilities = Abilities(
            strength=10, dexterity=14, constitution=10, intelligence=10, wisdom=10, charisma=10
        )
        character = Character(
            name="TestHero",
            character_class="fighter",
            level=1,
            abilities=abilities,
            max_hp=20,
            ac=14,
            current_hp=15,
        )
        character.add_condition("on_fire")
        return character

    @pytest.fixture
    def turn_state_with_action(self):
        """Create a turn state with action available"""
        turn_state = TurnState()
        turn_state.action_available = True
        turn_state.bonus_action_available = True
        return turn_state

    @pytest.fixture
    def turn_state_no_action(self):
        """Create a turn state with no action available"""
        turn_state = TurnState()
        turn_state.action_available = False
        turn_state.bonus_action_available = True
        return turn_state

    def test_returns_removable_conditions_with_action_available(
        self, mock_data_loader, character_on_fire, turn_state_with_action
    ):
        """Test that removable conditions are returned when action is available"""
        party = Party()
        party.add_character(character_on_fire)
        game_state = GameState(
            party=party, dungeon_name="test_dungeon", data_loader=mock_data_loader
        )
        game_state.initiative_tracker = Mock()
        game_state.initiative_tracker.get_current_turn_state.return_value = turn_state_with_action

        options = game_state.get_removable_conditions(character_on_fire)

        assert len(options) == 1
        assert options[0].condition_id == "on_fire"
        assert options[0].condition_name == "On Fire"
        assert options[0].ability == "dexterity"
        assert options[0].dc == 10
        assert options[0].action_cost == ActionType.ACTION

    def test_returns_empty_when_no_action_available(
        self, mock_data_loader, character_on_fire, turn_state_no_action
    ):
        """Test that no options are returned when action is not available"""
        party = Party()
        party.add_character(character_on_fire)
        game_state = GameState(
            party=party, dungeon_name="test_dungeon", data_loader=mock_data_loader
        )
        game_state.initiative_tracker = Mock()
        game_state.initiative_tracker.get_current_turn_state.return_value = turn_state_no_action

        options = game_state.get_removable_conditions(character_on_fire)

        assert len(options) == 0

    def test_returns_empty_when_no_removable_conditions(
        self, mock_data_loader, turn_state_with_action
    ):
        """Test that no options are returned when creature has no removable conditions"""
        abilities = Abilities(
            strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10
        )
        character = Character(
            name="TestHero",
            character_class="fighter",
            level=1,
            abilities=abilities,
            max_hp=20,
            ac=14,
            current_hp=15,
        )
        # Add a condition that cannot be removed early (e.g., prone)
        character.add_condition("prone")

        party = Party()
        party.add_character(character)
        game_state = GameState(
            party=party, dungeon_name="test_dungeon", data_loader=mock_data_loader
        )
        game_state.initiative_tracker = Mock()
        game_state.initiative_tracker.get_current_turn_state.return_value = turn_state_with_action

        options = game_state.get_removable_conditions(character)

        assert len(options) == 0

    def test_returns_empty_when_no_conditions(self, mock_data_loader, turn_state_with_action):
        """Test that no options are returned when creature has no conditions"""
        abilities = Abilities(
            strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10
        )
        character = Character(
            name="TestHero",
            character_class="fighter",
            level=1,
            abilities=abilities,
            max_hp=20,
            ac=14,
            current_hp=15,
        )

        party = Party()
        party.add_character(character)
        game_state = GameState(
            party=party, dungeon_name="test_dungeon", data_loader=mock_data_loader
        )
        game_state.initiative_tracker = Mock()
        game_state.initiative_tracker.get_current_turn_state.return_value = turn_state_with_action

        options = game_state.get_removable_conditions(character)

        assert len(options) == 0


class TestAttemptPlayerConditionRemoval:
    """Test GameState.attempt_player_condition_removal() method"""

    @pytest.fixture
    def mock_data_loader(self):
        """Create a mock data loader"""
        from pathlib import Path

        loader = Mock()
        loader.load_dungeon.return_value = {
            "name": "Test Dungeon",
            "rooms": {},
            "start_room": "entrance",
        }
        loader.data_path = Path("/nonexistent")
        return loader

    @pytest.fixture
    def character_on_fire(self):
        """Create a character with the on_fire condition"""
        abilities = Abilities(
            strength=10, dexterity=14, constitution=10, intelligence=10, wisdom=10, charisma=10
        )
        character = Character(
            name="TestHero",
            character_class="fighter",
            level=1,
            abilities=abilities,
            max_hp=20,
            ac=14,
            current_hp=15,
        )
        character.add_condition("on_fire")
        return character

    @pytest.fixture
    def turn_state_with_action(self):
        """Create a turn state with action available"""
        turn_state = TurnState()
        turn_state.action_available = True
        turn_state.bonus_action_available = True
        return turn_state

    @pytest.fixture
    def turn_state_no_action(self):
        """Create a turn state with no action available"""
        turn_state = TurnState()
        turn_state.action_available = False
        turn_state.bonus_action_available = True
        return turn_state

    def test_successful_removal_attempt(
        self, mock_data_loader, character_on_fire, turn_state_with_action
    ):
        """Test successful condition removal attempt"""
        party = Party()
        party.add_character(character_on_fire)
        game_state = GameState(
            party=party, dungeon_name="test_dungeon", data_loader=mock_data_loader
        )
        game_state.initiative_tracker = Mock()
        game_state.initiative_tracker.get_current_turn_state.return_value = turn_state_with_action

        # Mock the condition manager to return successful removal
        mock_ability_result = AbilityCheckResult(
            condition_id="on_fire",
            success=True,
            roll_total=15,
            dc=10,
            ability="dexterity",
            message="TestHero successfully extinguishes the flames!",
            condition_removed=True,
        )
        game_state.condition_manager.attempt_condition_removal = Mock(
            return_value=mock_ability_result
        )

        result = game_state.attempt_player_condition_removal(character_on_fire, "on_fire")

        assert result.attempted is True
        assert result.success is True
        assert result.action_consumed == ActionType.ACTION
        assert result.condition_id == "on_fire"
        # Verify action was consumed
        assert turn_state_with_action.action_available is False

    def test_failed_removal_attempt(
        self, mock_data_loader, character_on_fire, turn_state_with_action
    ):
        """Test failed condition removal attempt (failed ability check)"""
        party = Party()
        party.add_character(character_on_fire)
        game_state = GameState(
            party=party, dungeon_name="test_dungeon", data_loader=mock_data_loader
        )
        game_state.initiative_tracker = Mock()
        game_state.initiative_tracker.get_current_turn_state.return_value = turn_state_with_action

        # Mock the condition manager to return failed removal
        mock_ability_result = AbilityCheckResult(
            condition_id="on_fire",
            success=False,
            roll_total=7,
            dc=10,
            ability="dexterity",
            message="TestHero fails to extinguish the flames (rolled 7 vs DC 10)",
            condition_removed=False,
        )
        game_state.condition_manager.attempt_condition_removal = Mock(
            return_value=mock_ability_result
        )

        result = game_state.attempt_player_condition_removal(character_on_fire, "on_fire")

        assert result.attempted is True
        assert result.success is False
        assert result.action_consumed == ActionType.ACTION
        # Verify action was still consumed
        assert turn_state_with_action.action_available is False

    def test_fails_when_no_action_available(
        self, mock_data_loader, character_on_fire, turn_state_no_action
    ):
        """Test that removal fails when no action is available"""
        party = Party()
        party.add_character(character_on_fire)
        game_state = GameState(
            party=party, dungeon_name="test_dungeon", data_loader=mock_data_loader
        )
        game_state.initiative_tracker = Mock()
        game_state.initiative_tracker.get_current_turn_state.return_value = turn_state_no_action

        result = game_state.attempt_player_condition_removal(character_on_fire, "on_fire")

        assert result.attempted is False
        assert result.success is False
        assert result.action_consumed is None
        assert "No Action available" in result.message

    def test_fails_for_non_removable_condition(self, mock_data_loader, turn_state_with_action):
        """Test that removal fails for conditions that can't be removed early"""
        abilities = Abilities(
            strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10
        )
        character = Character(
            name="TestHero",
            character_class="fighter",
            level=1,
            abilities=abilities,
            max_hp=20,
            ac=14,
            current_hp=15,
        )
        character.add_condition("prone")

        party = Party()
        party.add_character(character)
        game_state = GameState(
            party=party, dungeon_name="test_dungeon", data_loader=mock_data_loader
        )
        game_state.initiative_tracker = Mock()
        game_state.initiative_tracker.get_current_turn_state.return_value = turn_state_with_action

        result = game_state.attempt_player_condition_removal(character, "prone")

        assert result.attempted is False
        assert result.success is False
        assert result.action_consumed is None

    def test_fails_for_nonexistent_condition(self, mock_data_loader, turn_state_with_action):
        """Test that removal fails for a condition that doesn't exist"""
        abilities = Abilities(
            strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10
        )
        character = Character(
            name="TestHero",
            character_class="fighter",
            level=1,
            abilities=abilities,
            max_hp=20,
            ac=14,
            current_hp=15,
        )

        party = Party()
        party.add_character(character)
        game_state = GameState(
            party=party, dungeon_name="test_dungeon", data_loader=mock_data_loader
        )
        game_state.initiative_tracker = Mock()
        game_state.initiative_tracker.get_current_turn_state.return_value = turn_state_with_action

        result = game_state.attempt_player_condition_removal(character, "nonexistent_condition")

        assert result.attempted is False
        assert result.success is False
        assert result.action_consumed is None

    def test_fails_when_no_initiative_tracker(self, mock_data_loader, character_on_fire):
        """Test that removal fails when there's no initiative tracker"""
        party = Party()
        party.add_character(character_on_fire)
        game_state = GameState(
            party=party, dungeon_name="test_dungeon", data_loader=mock_data_loader
        )
        game_state.initiative_tracker = None

        result = game_state.attempt_player_condition_removal(character_on_fire, "on_fire")

        assert result.attempted is False
        assert result.success is False
        assert "turn state" in result.message.lower()
