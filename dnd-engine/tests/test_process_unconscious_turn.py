# ABOUTME: Unit tests for GameState.process_unconscious_turn() method
# ABOUTME: Tests death saving throw processing for unconscious characters during combat

from unittest.mock import patch

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.game_state import (
    DeathSaveTurnResult,
    GameState,
)
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.action_economy import TurnState
from dnd_engine.systems.initiative import InitiativeEntry, InitiativeTracker
from dnd_engine.utils.events import EventBus


class TestProcessUnconsciousTurn:
    """Tests for GameState.process_unconscious_turn() method."""

    @pytest.fixture
    def event_bus(self):
        """Create event bus for testing."""
        return EventBus()

    @pytest.fixture
    def data_loader(self):
        """Create data loader."""
        return DataLoader()

    @pytest.fixture
    def dice_roller(self):
        """Create seeded dice roller for predictable results."""
        return DiceRoller(seed=42)

    @pytest.fixture
    def fighter(self):
        """Create a fighter character."""
        return Character(
            name="Conan",
            character_class=CharacterClass.FIGHTER,
            level=3,
            abilities=Abilities(16, 12, 14, 10, 10, 10),
            max_hp=28,
            ac=16,
        )

    @pytest.fixture
    def unconscious_fighter(self):
        """Create an unconscious fighter (0 HP)."""
        char = Character(
            name="Fallen",
            character_class=CharacterClass.FIGHTER,
            level=3,
            abilities=Abilities(16, 12, 14, 10, 10, 10),
            max_hp=28,
            ac=16,
        )
        char.current_hp = 0
        return char

    @pytest.fixture
    def goblin(self):
        """Create a goblin enemy."""
        return Creature(
            name="Goblin", max_hp=7, ac=13, abilities=Abilities(8, 14, 10, 10, 8, 8)
        )

    @pytest.fixture
    def game_state_unconscious_first(
        self, unconscious_fighter, goblin, event_bus, data_loader, dice_roller
    ):
        """Create game state with unconscious character going first."""
        party = Party([unconscious_fighter])
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller,
        )
        game_state.active_enemies = [goblin]
        game_state.in_combat = True

        # Set up initiative with unconscious fighter going first
        game_state.initiative_tracker = InitiativeTracker(dice_roller=dice_roller)
        fighter_entry = InitiativeEntry(creature=unconscious_fighter, initiative_roll=20)
        goblin_entry = InitiativeEntry(creature=goblin, initiative_roll=10)
        game_state.initiative_tracker.combatants = [fighter_entry, goblin_entry]
        game_state.initiative_tracker.turn_states[unconscious_fighter] = TurnState()
        game_state.initiative_tracker.turn_states[goblin] = TurnState()
        game_state.initiative_tracker.round_number = 1

        return game_state

    @pytest.fixture
    def game_state_conscious_first(
        self, fighter, goblin, event_bus, data_loader, dice_roller
    ):
        """Create game state with conscious character going first."""
        party = Party([fighter])
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller,
        )
        game_state.active_enemies = [goblin]
        game_state.in_combat = True

        # Set up initiative with conscious fighter going first
        game_state.initiative_tracker = InitiativeTracker(dice_roller=dice_roller)
        fighter_entry = InitiativeEntry(creature=fighter, initiative_roll=20)
        goblin_entry = InitiativeEntry(creature=goblin, initiative_roll=10)
        game_state.initiative_tracker.combatants = [fighter_entry, goblin_entry]
        game_state.initiative_tracker.turn_states[fighter] = TurnState()
        game_state.initiative_tracker.turn_states[goblin] = TurnState()
        game_state.initiative_tracker.round_number = 1

        return game_state

    def test_returns_none_when_not_in_combat(self, fighter, event_bus, data_loader, dice_roller):
        """Should return None when not in combat."""
        party = Party([fighter])
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller,
        )
        game_state.in_combat = False

        result = game_state.process_unconscious_turn()

        assert result is None

    def test_returns_none_when_not_unconscious_player_turn(
        self, game_state_conscious_first
    ):
        """Should return None when current turn is a conscious player."""
        result = game_state_conscious_first.process_unconscious_turn()

        assert result is None

    def test_returns_none_when_enemy_turn(
        self, game_state_unconscious_first, unconscious_fighter, goblin
    ):
        """Should return None when it's an enemy's turn."""
        # Advance to goblin's turn
        game_state_unconscious_first.initiative_tracker.combatants = [
            InitiativeEntry(creature=goblin, initiative_roll=20),
            InitiativeEntry(creature=unconscious_fighter, initiative_roll=10),
        ]

        result = game_state_unconscious_first.process_unconscious_turn()

        assert result is None

    def test_makes_death_save_on_unconscious_turn(
        self, game_state_unconscious_first, unconscious_fighter
    ):
        """Should make death save and return result when unconscious player's turn."""
        with patch.object(
            unconscious_fighter,
            "make_death_save",
            return_value={
                "roll": 15,
                "success": True,
                "natural_20": False,
                "natural_1": False,
                "successes": 1,
                "failures": 0,
                "stabilized": False,
                "dead": False,
                "conscious": False,
            },
        ) as mock_save:
            result = game_state_unconscious_first.process_unconscious_turn()

            mock_save.assert_called_once()
            assert isinstance(result, DeathSaveTurnResult)
            assert result.character_name == "Fallen"
            assert result.roll == 15
            assert result.success is True
            assert result.successes == 1
            assert result.turn_advanced is True

    def test_advances_turn_after_death_save(
        self, game_state_unconscious_first, unconscious_fighter, goblin
    ):
        """Should advance initiative after processing death save."""
        # Before: unconscious fighter's turn
        current_before = game_state_unconscious_first.initiative_tracker.get_current_combatant()
        assert current_before.creature == unconscious_fighter

        with patch.object(
            unconscious_fighter,
            "make_death_save",
            return_value={
                "roll": 12,
                "success": True,
                "natural_20": False,
                "natural_1": False,
                "successes": 1,
                "failures": 0,
                "stabilized": False,
                "dead": False,
                "conscious": False,
            },
        ):
            game_state_unconscious_first.process_unconscious_turn()

        # After: goblin's turn
        current_after = game_state_unconscious_first.initiative_tracker.get_current_combatant()
        assert current_after.creature == goblin

    def test_stabilized_character_skips_roll(
        self, game_state_unconscious_first, unconscious_fighter
    ):
        """Stabilized character should skip death save roll."""
        unconscious_fighter.stabilized = True

        result = game_state_unconscious_first.process_unconscious_turn()

        assert isinstance(result, DeathSaveTurnResult)
        assert result.already_stabilized is True
        assert result.roll == 0
        assert result.stabilized is True

    def test_natural_20_result(self, game_state_unconscious_first, unconscious_fighter):
        """Natural 20 should be reflected in result."""
        with patch.object(
            unconscious_fighter,
            "make_death_save",
            return_value={
                "roll": 20,
                "success": True,
                "natural_20": True,
                "natural_1": False,
                "successes": 0,
                "failures": 0,
                "stabilized": False,
                "dead": False,
                "conscious": True,
            },
        ):
            result = game_state_unconscious_first.process_unconscious_turn()

            assert result.natural_20 is True
            assert result.conscious is True

    def test_natural_1_result(self, game_state_unconscious_first, unconscious_fighter):
        """Natural 1 should be reflected in result."""
        with patch.object(
            unconscious_fighter,
            "make_death_save",
            return_value={
                "roll": 1,
                "success": False,
                "natural_20": False,
                "natural_1": True,
                "successes": 0,
                "failures": 2,
                "stabilized": False,
                "dead": False,
                "conscious": False,
            },
        ):
            result = game_state_unconscious_first.process_unconscious_turn()

            assert result.natural_1 is True
            assert result.failures == 2

    def test_death_result(self, game_state_unconscious_first, unconscious_fighter):
        """Death (3 failures) should be reflected in result."""
        unconscious_fighter.death_save_failures = 2

        with patch.object(
            unconscious_fighter,
            "make_death_save",
            return_value={
                "roll": 5,
                "success": False,
                "natural_20": False,
                "natural_1": False,
                "successes": 0,
                "failures": 3,
                "stabilized": False,
                "dead": True,
                "conscious": False,
            },
        ):
            result = game_state_unconscious_first.process_unconscious_turn()

            assert result.dead is True
            assert result.failures == 3

    def test_stabilization_result(
        self, game_state_unconscious_first, unconscious_fighter
    ):
        """Stabilization (3 successes) should be reflected in result."""
        unconscious_fighter.death_save_successes = 2

        with patch.object(
            unconscious_fighter,
            "make_death_save",
            return_value={
                "roll": 15,
                "success": True,
                "natural_20": False,
                "natural_1": False,
                "successes": 3,
                "failures": 0,
                "stabilized": True,
                "dead": False,
                "conscious": False,
            },
        ):
            result = game_state_unconscious_first.process_unconscious_turn()

            assert result.stabilized is True
            assert result.successes == 3
