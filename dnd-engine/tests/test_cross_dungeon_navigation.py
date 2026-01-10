# ABOUTME: Integration tests for cross-dungeon navigation using room GUIDs.
# ABOUTME: Tests moving between town and crypt dungeons via the room registry.

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus


@pytest.fixture
def test_party():
    """Create a simple test party."""
    abilities = Abilities(
        strength=10, dexterity=14, constitution=14, intelligence=10, wisdom=12, charisma=10
    )
    character = Character(
        name="Test Hero",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=12,
        ac=16,
    )
    return Party([character])


class TestCrossDungeonNavigation:
    """Test navigation between different dungeons using room GUIDs."""

    def test_start_in_town_navigate_to_crypt(self, test_party):
        """Test starting in town and navigating to crypt."""
        event_bus = EventBus()
        data_loader = DataLoader()

        # Start in town
        game_state = GameState(
            party=test_party,
            dungeon_name="town_of_arden",
            campaign_id="the_unquiet_dead",
            event_bus=event_bus,
            data_loader=data_loader,
        )

        # Should start in town square
        assert game_state.current_room_id == "arden.town_square"
        assert game_state.dungeon_name == "town_of_arden"

        # Move south to town road
        success = game_state.move("south", check_for_enemies=False)
        assert success is True
        assert game_state.current_room_id == "arden.town_road"

        # Move south to crypt (cross-dungeon)
        success = game_state.move("south", check_for_enemies=False)
        assert success is True
        assert game_state.current_room_id == "crypt.graveyard_entrance"
        assert game_state.dungeon_name == "crypt"

    def test_start_in_crypt_navigate_to_town(self, test_party):
        """Test starting in crypt and navigating back to town."""
        event_bus = EventBus()
        data_loader = DataLoader()

        # Start in crypt
        game_state = GameState(
            party=test_party,
            dungeon_name="crypt",
            campaign_id="the_unquiet_dead",
            event_bus=event_bus,
            data_loader=data_loader,
        )

        # Should start in graveyard entrance
        assert game_state.current_room_id == "crypt.graveyard_entrance"
        assert game_state.dungeon_name == "crypt"

        # Move north to town (cross-dungeon)
        success = game_state.move("north", check_for_enemies=False)
        assert success is True
        assert game_state.current_room_id == "arden.town_road"
        assert game_state.dungeon_name == "town_of_arden"

    def test_round_trip_navigation(self, test_party):
        """Test navigating from town to crypt and back."""
        event_bus = EventBus()
        data_loader = DataLoader()

        # Start in town
        game_state = GameState(
            party=test_party,
            dungeon_name="town_of_arden",
            campaign_id="the_unquiet_dead",
            event_bus=event_bus,
            data_loader=data_loader,
        )

        # Go to crypt (south twice)
        game_state.move("south", check_for_enemies=False)
        game_state.move("south", check_for_enemies=False)
        assert game_state.current_room_id == "crypt.graveyard_entrance"

        # Go back to town (north)
        game_state.move("north", check_for_enemies=False)
        assert game_state.current_room_id == "arden.town_road"
        assert game_state.dungeon_name == "town_of_arden"

        # Go back to crypt again (south)
        game_state.move("south", check_for_enemies=False)
        assert game_state.current_room_id == "crypt.graveyard_entrance"
        assert game_state.dungeon_name == "crypt"

    def test_dungeon_state_preserved_across_transitions(self, test_party):
        """Test that dungeon state is preserved when moving between dungeons."""
        event_bus = EventBus()
        data_loader = DataLoader()

        # Start in crypt
        game_state = GameState(
            party=test_party,
            dungeon_name="crypt",
            campaign_id="the_unquiet_dead",
            event_bus=event_bus,
            data_loader=data_loader,
        )

        # Mark current room as searched
        room = game_state.get_current_room()
        room["searched"] = True

        # Go to town (north)
        game_state.move("north", check_for_enemies=False)
        assert game_state.current_room_id == "arden.town_road"

        # Go back to crypt (south)
        game_state.move("south", check_for_enemies=False)

        # The searched flag should still be set
        room = game_state.get_current_room()
        assert room["searched"] is True

    def test_room_info_after_cross_dungeon_move(self, test_party):
        """Test that room info is correct after cross-dungeon moves."""
        event_bus = EventBus()
        data_loader = DataLoader()

        # Start in town
        game_state = GameState(
            party=test_party,
            dungeon_name="town_of_arden",
            campaign_id="the_unquiet_dead",
            event_bus=event_bus,
            data_loader=data_loader,
        )

        # Navigate to crypt (south twice)
        game_state.move("south", check_for_enemies=False)
        game_state.move("south", check_for_enemies=False)

        # Check room info
        room = game_state.get_current_room()
        assert room["id"] == "crypt.graveyard_entrance"
        assert room["name"] == "Overgrown Graveyard"
        assert room["location_type"] == "dungeon"
        assert room["parent"] == "crypt"

    def test_exits_available_after_cross_dungeon_move(self, test_party):
        """Test that exits are correctly reported after cross-dungeon moves."""
        event_bus = EventBus()
        data_loader = DataLoader()

        # Start in town
        game_state = GameState(
            party=test_party,
            dungeon_name="town_of_arden",
            campaign_id="the_unquiet_dead",
            event_bus=event_bus,
            data_loader=data_loader,
        )

        # Navigate to crypt (south twice)
        game_state.move("south", check_for_enemies=False)
        game_state.move("south", check_for_enemies=False)

        # Check exits
        room = game_state.get_current_room()
        exits = room.get("exits", {})

        # Should have exit down to hall_of_the_dead and north back to town
        assert "down" in exits
        assert "north" in exits

        # Verify exit destinations
        assert exits["down"] == "crypt.hall_of_the_dead"
        north_exit = exits["north"]
        assert north_exit["destination"] == "arden.town_road"
