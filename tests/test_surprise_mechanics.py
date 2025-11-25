# ABOUTME: Unit tests for surprise mechanics - alert state and surprise rounds
# ABOUTME: Tests room alert tracking, surprise checks, and condition application

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.utils.events import EventBus


@pytest.fixture
def game_state():
    """Create a fresh game state for testing."""
    party = Party()
    abilities = Abilities(16, 14, 14, 10, 12, 8)  # str, dex, con, int, wis, cha
    party.add_character(Character(
        name="Theron",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=12,
        ac=16
    ))

    event_bus = EventBus()
    gs = GameState(party=party, event_bus=event_bus, dungeon_name="test_dungeon")
    return gs


class TestRoomAlertState:
    """Test room alert state tracking."""

    def test_room_starts_unalerted(self, game_state):
        """Rooms should start in unalerted state."""
        assert game_state.is_room_alerted() is False

    def test_set_room_alerted(self, game_state):
        """Setting a room as alerted should persist."""
        game_state.set_room_alerted(alert_source="test_trigger")

        assert game_state.is_room_alerted() is True
        room = game_state.get_current_room()
        assert room["alert_source"] == "test_trigger"

    def test_set_specific_room_alerted(self, game_state):
        """Can alert a specific room by ID."""
        # Get a different room ID
        current_room = game_state.current_room_id
        all_rooms = list(game_state.dungeon["rooms"].keys())
        other_rooms = [r for r in all_rooms if r != current_room]

        # Skip test if only one room
        if not other_rooms:
            pytest.skip("Test dungeon has only one room")

        other_room = other_rooms[0]
        game_state.set_room_alerted(room_id=other_room, alert_source="noise")

        # Current room should still be unalerted
        assert game_state.is_room_alerted() is False
        # Other room should be alerted
        assert game_state.is_room_alerted(room_id=other_room) is True


class TestSurpriseChecks:
    """Test surprise check mechanics."""

    def test_alerted_room_prevents_surprise(self, game_state):
        """Alerted rooms should prevent surprise."""
        game_state.set_room_alerted(alert_source="prior_combat")

        # Create some enemies
        game_state.active_enemies = [
            game_state.data_loader.create_monster("goblin")
        ]

        result = game_state._check_for_surprise()

        assert result["party_surprised"] is False
        assert result["enemies_surprised"] is False

    def test_successful_stealth_surprises_enemies(self, game_state, monkeypatch):
        """High stealth rolls should surprise enemies."""
        # Mock successful stealth check (always roll high)
        def mock_make_skill_check(self, skill, dc, skills_data, **kwargs):
            return {
                "skill": skill,
                "dc": dc,
                "roll": 20,
                "modifier": 2,
                "total": 22,
                "success": True
            }

        monkeypatch.setattr(Character, "make_skill_check", mock_make_skill_check)

        # Create some enemies
        game_state.active_enemies = [
            game_state.data_loader.create_monster("goblin")
        ]

        result = game_state._check_for_surprise()

        assert result["enemies_surprised"] is True
        assert result["party_surprised"] is False

    def test_failed_stealth_prevents_surprise(self, game_state, monkeypatch):
        """Failed stealth checks should prevent surprise."""
        # Mock failed stealth check (always roll low)
        def mock_make_skill_check(self, skill, dc, skills_data, **kwargs):
            return {
                "skill": skill,
                "dc": dc,
                "roll": 1,
                "modifier": 0,
                "total": 1,
                "success": False
            }

        monkeypatch.setattr(Character, "make_skill_check", mock_make_skill_check)

        # Create some enemies
        game_state.active_enemies = [
            game_state.data_loader.create_monster("goblin")
        ]

        result = game_state._check_for_surprise()

        assert result["enemies_surprised"] is False
        assert result["party_surprised"] is False

    def test_group_stealth_one_failure_detects_party(self, game_state, monkeypatch):
        """If one party member fails stealth, entire party is detected."""
        # Add a second party member
        abilities = Abilities(8, 18, 10, 12, 14, 10)  # str, dex, con, int, wis, cha
        game_state.party.add_character(Character(
            name="Lira",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities,
            max_hp=8,
            ac=14
        ))

        # Track which character is being checked
        call_count = [0]

        def mock_make_skill_check(self, skill, dc, skills_data, **kwargs):
            call_count[0] += 1
            # First character succeeds, second fails
            if call_count[0] == 1:
                return {"skill": skill, "dc": dc, "roll": 20, "modifier": 2, "total": 22, "success": True}
            else:
                return {"skill": skill, "dc": dc, "roll": 1, "modifier": 0, "total": 1, "success": False}

        monkeypatch.setattr(Character, "make_skill_check", mock_make_skill_check)

        # Create some enemies
        game_state.active_enemies = [
            game_state.data_loader.create_monster("goblin")
        ]

        result = game_state._check_for_surprise()

        # One failure means no surprise
        assert result["enemies_surprised"] is False


class TestSurprisedCondition:
    """Test surprised condition application and handling."""

    def test_combat_start_applies_surprised_to_enemies(self, game_state, monkeypatch):
        """Surprised enemies should get the surprised condition."""
        # Mock successful stealth
        def mock_make_skill_check(self, skill, dc, skills_data, **kwargs):
            return {"skill": skill, "dc": dc, "roll": 20, "modifier": 2, "total": 22, "success": True}

        monkeypatch.setattr(Character, "make_skill_check", mock_make_skill_check)

        # Create enemies and start combat
        game_state.active_enemies = [
            game_state.data_loader.create_monster("goblin")
        ]
        game_state._start_combat()

        # Enemies should have surprised condition
        for enemy in game_state.active_enemies:
            assert "surprised" in enemy.conditions

    def test_combat_start_no_surprise_no_condition(self, game_state, monkeypatch):
        """If no surprise, creatures should not have surprised condition."""
        # Mock failed stealth
        def mock_make_skill_check(self, skill, dc, skills_data, **kwargs):
            return {"skill": skill, "dc": dc, "roll": 1, "modifier": 0, "total": 1, "success": False}

        monkeypatch.setattr(Character, "make_skill_check", mock_make_skill_check)

        # Create enemies and start combat
        game_state.active_enemies = [
            game_state.data_loader.create_monster("goblin")
        ]
        game_state._start_combat()

        # No surprised condition
        for enemy in game_state.active_enemies:
            assert "surprised" not in enemy.conditions


class TestLoudUnlockAlerts:
    """Test that loud unlock methods alert rooms."""

    def test_loud_unlock_alerts_destination_room(self, game_state, monkeypatch):
        """Loud unlock methods should alert the destination room."""
        # Mock successful skill check
        def mock_make_skill_check(self, skill, dc, skills_data, **kwargs):
            return {"skill": skill, "dc": dc, "roll": 15, "modifier": 3, "total": 18, "success": True}

        monkeypatch.setattr(Character, "make_skill_check", mock_make_skill_check)

        # Find a room with a locked door
        current_room = game_state.get_current_room()
        exits = current_room.get("exits", {})

        # Add a test locked door with loud unlock method if needed
        if "test_exit" not in exits:
            exits["test_exit"] = {
                "destination": "test_destination_room",
                "locked": True,
                "unlock_methods": [
                    {
                        "skill": "athletics",
                        "dc": 12,
                        "description": "break down the door",
                        "silent": False
                    }
                ]
            }
            # Add destination room if it doesn't exist
            if "test_destination_room" not in game_state.dungeon["rooms"]:
                game_state.dungeon["rooms"]["test_destination_room"] = {
                    "name": "Test Room",
                    "description": "A test room",
                    "exits": {}
                }

        # Attempt the loud unlock
        character = game_state.party.characters[0]
        result = game_state.attempt_unlock("test_exit", 0, character)

        assert result["success"] is True
        assert game_state.is_room_alerted(room_id="test_destination_room") is True

    def test_silent_unlock_does_not_alert(self, game_state, monkeypatch):
        """Silent unlock methods should not alert rooms."""
        # Mock successful skill check
        def mock_make_skill_check(self, skill, dc, skills_data, **kwargs):
            return {"skill": skill, "dc": dc, "roll": 15, "modifier": 3, "total": 18, "success": True}

        monkeypatch.setattr(Character, "make_skill_check", mock_make_skill_check)

        # Add a test locked door with silent unlock method
        current_room = game_state.get_current_room()
        exits = current_room.get("exits", {})

        exits["silent_exit"] = {
            "destination": "silent_destination_room",
            "locked": True,
            "unlock_methods": [
                {
                    "skill": "sleight_of_hand",
                    "dc": 12,
                    "description": "pick the lock",
                    "silent": True
                }
            ]
        }
        # Add destination room
        if "silent_destination_room" not in game_state.dungeon["rooms"]:
            game_state.dungeon["rooms"]["silent_destination_room"] = {
                "name": "Silent Room",
                "description": "A quiet room",
                "exits": {}
            }

        # Attempt the silent unlock
        character = game_state.party.characters[0]
        result = game_state.attempt_unlock("silent_exit", 0, character)

        assert result["success"] is True
        # Room should not be alerted
        assert game_state.is_room_alerted(room_id="silent_destination_room") is False
