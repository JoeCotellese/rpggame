# ABOUTME: Integration tests for the Arden(node) <-> crypt(grid) seam using real campaign content.
# ABOUTME: Arden is a node surface; the Town Gate transitions into the crypt and the crypt exits back to the node.

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


def _town(test_party):
    return GameState(
        party=test_party,
        dungeon_name="town_of_arden",
        campaign_id="the_unquiet_dead",
        event_bus=EventBus(),
        data_loader=DataLoader(),
    )


def _crypt(test_party):
    return GameState(
        party=test_party,
        dungeon_name="crypt",
        campaign_id="the_unquiet_dead",
        event_bus=EventBus(),
        data_loader=DataLoader(),
    )


class TestCrossDungeonNavigation:
    """Navigation across the Arden node surface <-> crypt grid seam."""

    def test_start_on_town_node_surface(self, test_party):
        """Arden loads as a node surface; the party starts at the town square."""
        game_state = _town(test_party)

        assert game_state.is_node_surface()
        assert game_state.current_node_id == "arden.town_square"
        assert game_state.current_room_id is None
        assert game_state.dungeon_name == "town_of_arden"

    def test_town_gate_transition_enters_crypt(self, test_party):
        """The Town Gate node transitions onto the crypt grid at its entrance (forward seam)."""
        game_state = _town(test_party)

        game_state.enter_node("arden.town_road")
        result = game_state.node_actions.transition(game_state.party.get_living_members()[0])

        assert result["success"] is True
        assert game_state.dungeon_name == "crypt"
        assert game_state.current_room_id == "crypt.graveyard_entrance"
        assert not game_state.is_node_surface()

    def test_crypt_exit_reenters_town_node_surface(self, test_party):
        """Moving north out of the crypt lands on the Arden node surface (reverse seam)."""
        game_state = _crypt(test_party)
        assert game_state.current_room_id == "crypt.graveyard_entrance"

        success = game_state.move("north", check_for_enemies=False)

        assert success is True
        assert game_state.is_node_surface()
        assert game_state.current_node_id == "arden.town_road"
        assert game_state.current_room_id is None
        assert game_state.dungeon_name == "town_of_arden"

    def test_round_trip_preserves_crypt_room_state(self, test_party):
        """Crypt -> Arden node -> crypt, preserving crypt room state across the seam."""
        game_state = _crypt(test_party)

        # Mark the entrance searched before leaving.
        game_state.get_current_room()["searched"] = True

        # Up to the node surface via the reverse seam.
        game_state.move("north", check_for_enemies=False)
        assert game_state.current_node_id == "arden.town_road"

        # Back down through the Town Gate transition.
        result = game_state.node_actions.transition(game_state.party.get_living_members()[0])
        assert result["success"] is True
        assert game_state.dungeon_name == "crypt"
        assert game_state.current_room_id == "crypt.graveyard_entrance"

        # The searched flag survived the round trip.
        assert game_state.get_current_room()["searched"] is True

    def test_room_info_after_cross_dungeon_move(self, test_party):
        """After entering the crypt from town, room info reflects the crypt entrance."""
        game_state = _town(test_party)

        game_state.enter_node("arden.town_road")
        game_state.node_actions.transition(game_state.party.get_living_members()[0])

        room = game_state.get_current_room()
        assert room["id"] == "crypt.graveyard_entrance"
        assert room["name"] == "Overgrown Graveyard"
        assert room["location_type"] == "dungeon"
        assert room["parent"] == "crypt"

    def test_crypt_exits_after_arrival(self, test_party):
        """The crypt entrance exposes its interior exit and the road back to the Arden node."""
        game_state = _crypt(test_party)

        room = game_state.get_current_room()
        exits = room.get("exits", {})

        # Interior exit down, plus the north exit that names the Arden Town Gate node.
        assert "down" in exits
        assert "north" in exits
        assert exits["down"] == "crypt.hall_of_the_dead"
        assert exits["north"]["destination"] == "arden.town_road"
