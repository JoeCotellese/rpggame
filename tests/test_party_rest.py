# ABOUTME: Unit tests for GameState.party_rest() method
# ABOUTME: Tests rest mechanics including HP recovery, resource recovery, and event emission

import pytest
from unittest.mock import Mock, patch

from dnd_engine.core.character import Character
from dnd_engine.core.game_state import (
    CharacterRestResult,
    GameState,
    PartyRestResult,
)
from dnd_engine.core.party import Party
from dnd_engine.utils.events import EventBus, EventType


@pytest.fixture
def mock_character():
    """Create a mock character for testing."""
    char = Mock(spec=Character)
    char.name = "TestHero"
    char.current_hp = 5
    char.max_hp = 10
    return char


@pytest.fixture
def mock_party(mock_character):
    """Create a mock party with one character."""
    party = Mock(spec=Party)
    party.characters = [mock_character]
    return party


@pytest.fixture
def game_state_with_mock_party(mock_party):
    """Create a GameState with a mock party."""
    with patch("dnd_engine.core.game_state.DataLoader"):
        with patch("dnd_engine.core.game_state.RoomRegistry"):
            event_bus = EventBus()
            gs = GameState(
                party=mock_party,
                dungeon_name="test_dungeon",
                event_bus=event_bus
            )
            return gs


class TestPartyRestResult:
    """Tests for PartyRestResult dataclass."""

    def test_rest_duration_display_short(self):
        """Short rest displays as '1 hour'."""
        result = PartyRestResult(
            rest_type="short",
            rest_duration_minutes=60,
            character_results=[]
        )
        assert result.rest_duration_display == "1 hour"

    def test_rest_duration_display_long(self):
        """Long rest displays as '8 hours'."""
        result = PartyRestResult(
            rest_type="long",
            rest_duration_minutes=480,
            character_results=[]
        )
        assert result.rest_duration_display == "8 hours"

    def test_rest_duration_display_custom_hours(self):
        """Custom duration displays correctly for whole hours."""
        result = PartyRestResult(
            rest_type="short",
            rest_duration_minutes=120,
            character_results=[]
        )
        assert result.rest_duration_display == "2 hours"

    def test_rest_duration_display_custom_mixed(self):
        """Custom duration displays hours and minutes."""
        result = PartyRestResult(
            rest_type="short",
            rest_duration_minutes=90,
            character_results=[]
        )
        assert result.rest_duration_display == "1h 30m"


class TestPartyRestValidation:
    """Tests for party_rest input validation."""

    def test_invalid_rest_type_raises(self, game_state_with_mock_party):
        """Invalid rest type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid rest_type"):
            game_state_with_mock_party.party_rest("medium")

    def test_valid_short_rest_type(self, game_state_with_mock_party, mock_character):
        """Short rest type is accepted."""
        mock_character.take_short_rest.return_value = {
            "character": "TestHero",
            "hp_recovered": 3,
            "resources_recovered": {}
        }
        result = game_state_with_mock_party.party_rest("short")
        assert result.rest_type == "short"

    def test_valid_long_rest_type(self, game_state_with_mock_party, mock_character):
        """Long rest type is accepted."""
        mock_character.take_long_rest.return_value = {
            "character": "TestHero",
            "hp_recovered": 5,
            "resources_recovered": {"spell_slots": True}
        }
        result = game_state_with_mock_party.party_rest("long")
        assert result.rest_type == "long"


class TestPartyRestShort:
    """Tests for short rest functionality."""

    def test_short_rest_calls_character_method(
        self, game_state_with_mock_party, mock_character
    ):
        """Short rest calls take_short_rest on each character."""
        mock_character.take_short_rest.return_value = {
            "character": "TestHero",
            "hp_recovered": 3,
            "resources_recovered": {}
        }
        game_state_with_mock_party.party_rest("short")
        mock_character.take_short_rest.assert_called_once()
        mock_character.take_long_rest.assert_not_called()

    def test_short_rest_duration(self, game_state_with_mock_party, mock_character):
        """Short rest has 60 minute duration."""
        mock_character.take_short_rest.return_value = {
            "character": "TestHero",
            "hp_recovered": 0,
            "resources_recovered": {}
        }
        result = game_state_with_mock_party.party_rest("short")
        assert result.rest_duration_minutes == 60

    def test_short_rest_advances_time(self, game_state_with_mock_party, mock_character):
        """Short rest advances game time by 60 minutes."""
        mock_character.take_short_rest.return_value = {
            "character": "TestHero",
            "hp_recovered": 0,
            "resources_recovered": {}
        }
        initial_time = game_state_with_mock_party.time_manager.elapsed_minutes
        game_state_with_mock_party.party_rest("short")
        assert (
            game_state_with_mock_party.time_manager.elapsed_minutes
            == initial_time + 60
        )


class TestPartyRestLong:
    """Tests for long rest functionality."""

    def test_long_rest_calls_character_method(
        self, game_state_with_mock_party, mock_character
    ):
        """Long rest calls take_long_rest on each character."""
        mock_character.take_long_rest.return_value = {
            "character": "TestHero",
            "hp_recovered": 5,
            "resources_recovered": {"spell_slots": True}
        }
        game_state_with_mock_party.party_rest("long")
        mock_character.take_long_rest.assert_called_once()
        mock_character.take_short_rest.assert_not_called()

    def test_long_rest_duration(self, game_state_with_mock_party, mock_character):
        """Long rest has 480 minute duration."""
        mock_character.take_long_rest.return_value = {
            "character": "TestHero",
            "hp_recovered": 5,
            "resources_recovered": {}
        }
        result = game_state_with_mock_party.party_rest("long")
        assert result.rest_duration_minutes == 480

    def test_long_rest_advances_time(self, game_state_with_mock_party, mock_character):
        """Long rest advances game time by 480 minutes."""
        mock_character.take_long_rest.return_value = {
            "character": "TestHero",
            "hp_recovered": 5,
            "resources_recovered": {}
        }
        initial_time = game_state_with_mock_party.time_manager.elapsed_minutes
        game_state_with_mock_party.party_rest("long")
        assert (
            game_state_with_mock_party.time_manager.elapsed_minutes
            == initial_time + 480
        )


class TestPartyRestResults:
    """Tests for rest result aggregation."""

    def test_character_result_hp_tracking(
        self, game_state_with_mock_party, mock_character
    ):
        """Character result tracks HP before and after."""
        mock_character.current_hp = 5  # Before rest
        mock_character.take_short_rest.return_value = {
            "character": "TestHero",
            "hp_recovered": 3,
            "resources_recovered": {}
        }
        # Simulate HP change during rest
        def update_hp():
            mock_character.current_hp = 8
            return {
                "character": "TestHero",
                "hp_recovered": 3,
                "resources_recovered": {}
            }
        mock_character.take_short_rest.side_effect = update_hp

        result = game_state_with_mock_party.party_rest("short")
        char_result = result.character_results[0]

        assert char_result.hp_before == 5
        assert char_result.hp_after == 8
        assert char_result.hp_recovered == 3

    def test_character_result_resources(
        self, game_state_with_mock_party, mock_character
    ):
        """Character result includes resources recovered."""
        mock_character.take_long_rest.return_value = {
            "character": "TestHero",
            "hp_recovered": 5,
            "resources_recovered": {"spell_slots": True, "hit_dice": 2}
        }
        result = game_state_with_mock_party.party_rest("long")
        char_result = result.character_results[0]

        assert char_result.resources_recovered == {
            "spell_slots": True,
            "hit_dice": 2
        }

    def test_can_prepare_spells_flag(
        self, game_state_with_mock_party, mock_character
    ):
        """Character result includes can_prepare_spells flag."""
        mock_character.take_long_rest.return_value = {
            "character": "TestHero",
            "hp_recovered": 5,
            "resources_recovered": {},
            "can_prepare_spells": True
        }
        result = game_state_with_mock_party.party_rest("long")
        char_result = result.character_results[0]

        assert char_result.can_prepare_spells is True


class TestPartyRestEvents:
    """Tests for rest event emission."""

    def test_short_rest_emits_event(self, game_state_with_mock_party, mock_character):
        """Short rest emits SHORT_REST event."""
        mock_character.take_short_rest.return_value = {
            "character": "TestHero",
            "hp_recovered": 3,
            "resources_recovered": {}
        }
        events = []
        game_state_with_mock_party.event_bus.subscribe(
            EventType.SHORT_REST,
            lambda e: events.append(e)
        )

        game_state_with_mock_party.party_rest("short")

        assert len(events) == 1
        assert events[0].type == EventType.SHORT_REST
        assert events[0].data["rest_type"] == "short"

    def test_long_rest_emits_event(self, game_state_with_mock_party, mock_character):
        """Long rest emits LONG_REST event."""
        mock_character.take_long_rest.return_value = {
            "character": "TestHero",
            "hp_recovered": 5,
            "resources_recovered": {}
        }
        events = []
        game_state_with_mock_party.event_bus.subscribe(
            EventType.LONG_REST,
            lambda e: events.append(e)
        )

        game_state_with_mock_party.party_rest("long")

        assert len(events) == 1
        assert events[0].type == EventType.LONG_REST
        assert events[0].data["rest_type"] == "long"

    def test_event_contains_party_info(
        self, game_state_with_mock_party, mock_character
    ):
        """Rest event contains party member names."""
        mock_character.take_short_rest.return_value = {
            "character": "TestHero",
            "hp_recovered": 3,
            "resources_recovered": {}
        }
        events = []
        game_state_with_mock_party.event_bus.subscribe(
            EventType.SHORT_REST,
            lambda e: events.append(e)
        )

        game_state_with_mock_party.party_rest("short")

        assert "party" in events[0].data
        assert "TestHero" in events[0].data["party"]

    def test_event_contains_recovery_data(
        self, game_state_with_mock_party, mock_character
    ):
        """Rest event contains HP and resource recovery data."""
        mock_character.take_short_rest.return_value = {
            "character": "TestHero",
            "hp_recovered": 3,
            "resources_recovered": {"action_surge": True}
        }
        events = []
        game_state_with_mock_party.event_bus.subscribe(
            EventType.SHORT_REST,
            lambda e: events.append(e)
        )

        game_state_with_mock_party.party_rest("short")

        assert events[0].data["hp_recovered"]["TestHero"] == 3
        assert events[0].data["resources_recovered"]["TestHero"] == {
            "action_surge": True
        }


class TestPartyRestMultipleCharacters:
    """Tests for rest with multiple party members."""

    def test_rest_applies_to_all_characters(self):
        """Rest is applied to all party members."""
        char1 = Mock(spec=Character)
        char1.name = "Fighter"
        char1.current_hp = 5
        char1.max_hp = 15
        char1.take_short_rest.return_value = {
            "character": "Fighter",
            "hp_recovered": 5,
            "resources_recovered": {}
        }

        char2 = Mock(spec=Character)
        char2.name = "Wizard"
        char2.current_hp = 3
        char2.max_hp = 8
        char2.take_short_rest.return_value = {
            "character": "Wizard",
            "hp_recovered": 2,
            "resources_recovered": {}
        }

        party = Mock(spec=Party)
        party.characters = [char1, char2]

        with patch("dnd_engine.core.game_state.DataLoader"):
            with patch("dnd_engine.core.game_state.RoomRegistry"):
                gs = GameState(
                    party=party,
                    dungeon_name="test_dungeon",
                    event_bus=EventBus()
                )

        result = gs.party_rest("short")

        assert len(result.character_results) == 2
        char1.take_short_rest.assert_called_once()
        char2.take_short_rest.assert_called_once()

        # Verify both characters are in results
        names = [r.character_name for r in result.character_results]
        assert "Fighter" in names
        assert "Wizard" in names
