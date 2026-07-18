# ABOUTME: Tests for the node<->grid transition seam (issue #684 slice 4).
# ABOUTME: Covers registry node resolution, both seam directions, round trip, and save/load.

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.core.room_registry import RoomRegistry
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus, EventType


@pytest.fixture
def test_party():
    abilities = Abilities(
        strength=14,
        dexterity=12,
        constitution=13,
        intelligence=10,
        wisdom=11,
        charisma=8,
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


@pytest.fixture
def grid_game(test_party):
    """Start inside the lab dungeon, whose 'up' exit names the lab_gate node."""
    return GameState(
        party=test_party,
        dungeon_name="lab_dungeon",
        event_bus=EventBus(),
        data_loader=DataLoader(),
    )


@pytest.fixture
def node_game(test_party):
    return GameState(
        party=test_party,
        dungeon_name="lab_settlement",
        event_bus=EventBus(),
        data_loader=DataLoader(),
    )


@pytest.fixture
def temp_dungeons_dir():
    """A dungeons dir holding one settlement (node surface) and one grid dungeon."""
    with TemporaryDirectory() as tmpdir:
        dungeons_path = Path(tmpdir)

        settlement = {
            "id": "test_settlement",
            "surface": "node",
            "start_node": "settle.square",
            "nodes": {
                "settle.square": {
                    "name": "Settlement Square",
                    "blurb": "The square.",
                    "description": "A quiet square.",
                },
                "settle.gate": {
                    "name": "Settlement Gate",
                    "blurb": "The gate.",
                    "description": "A rusted gate.",
                    "transition": {"to": "test_crypt"},
                },
            },
        }
        with open(dungeons_path / "test_settlement.json", "w") as f:
            json.dump(settlement, f)

        crypt = {
            "id": "test_crypt",
            "name": "Test Crypt",
            "start_room": "crypt.entrance",
            "rooms": {
                "crypt.entrance": {
                    "name": "Crypt Entrance",
                    "description": "A dark entrance",
                    "exits": {"up": "settle.gate"},
                },
            },
        }
        with open(dungeons_path / "test_crypt.json", "w") as f:
            json.dump(crypt, f)

        yield dungeons_path


class TestRegistryNodeIndex:
    def test_node_resolves_to_its_settlement(self, temp_dungeons_dir):
        registry = RoomRegistry(dungeons_path=temp_dungeons_dir)
        assert registry.get_dungeon_for_node("settle.square") == "test_settlement"
        assert registry.get_dungeon_for_node("settle.gate") == "test_settlement"

    def test_unknown_node_resolves_to_none(self, temp_dungeons_dir):
        registry = RoomRegistry(dungeons_path=temp_dungeons_dir)
        assert registry.get_dungeon_for_node("settle.nowhere") is None

    def test_room_ids_are_not_nodes(self, temp_dungeons_dir):
        """Rooms and nodes stay separate concepts in the registry."""
        registry = RoomRegistry(dungeons_path=temp_dungeons_dir)
        assert registry.get_dungeon_for_node("crypt.entrance") is None

    def test_room_lookups_unaffected(self, temp_dungeons_dir):
        registry = RoomRegistry(dungeons_path=temp_dungeons_dir)
        assert registry.get_dungeon_for_room("crypt.entrance") == "test_crypt"
        assert registry.get_room("crypt.entrance")["name"] == "Crypt Entrance"

    def test_unprefixed_node_ids_resolve(self):
        """The lab fixture's node ids carry no dot prefix; the node index is
        keyed by full id, so they resolve where the room prefix map cannot."""
        dungeons_path = DataLoader().data_path / "content" / "dungeons"
        registry = RoomRegistry(dungeons_path=dungeons_path)
        assert registry.get_dungeon_for_node("lab_gate") == "lab_settlement"
        assert registry.get_dungeon_for_node("lab_square") == "lab_settlement"


class TestReverseSeam:
    """A grid exit whose destination is a node id re-enters the settlement."""

    def test_grid_exit_reenters_settlement_at_named_node(self, grid_game):
        events = []
        grid_game.event_bus.subscribe(EventType.ROOM_ENTER, events.append)

        assert grid_game.move("up") is True

        assert grid_game.is_node_surface()
        assert grid_game.dungeon_name == "lab_settlement"
        assert grid_game.current_node_id == "lab_gate"
        assert grid_game.current_room_id is None
        assert grid_game.previous_room_id is None
        assert grid_game.previous_node_id is None
        assert grid_game.last_entry_direction is None

        assert len(events) == 1
        assert events[0].data["room_id"] == "lab_gate"
        assert events[0].data["room_name"] == "The Old Gate"
        assert events[0].data["dungeon_id"] == "lab_settlement"

    def test_reverse_seam_advances_time(self, grid_game):
        before = grid_game.time_manager.elapsed_minutes
        grid_game.move("up")
        assert grid_game.time_manager.elapsed_minutes == before + 10

    def test_dict_form_exit_destination(self, grid_game):
        grid_game.dungeon["rooms"]["lab_entry"]["exits"]["door"] = {"destination": "lab_gate"}
        assert grid_game.move("door") is True
        assert grid_game.current_node_id == "lab_gate"

    def test_locked_exit_still_blocks_before_resolution(self, grid_game):
        grid_game.dungeon["rooms"]["lab_entry"]["exits"]["up"] = {
            "destination": "lab_gate",
            "locked": True,
        }
        assert grid_game.move("up") is False
        assert not grid_game.is_node_surface()
        assert grid_game.current_room_id == "lab_entry"

    def test_move_to_node_without_registry_fails_gracefully(self, grid_game):
        grid_game.room_registry = None
        assert grid_game.move("up") is False
        assert not grid_game.is_node_surface()
        assert grid_game.current_room_id == "lab_entry"

    def test_unknown_destination_still_fails(self, grid_game):
        grid_game.dungeon["rooms"]["lab_entry"]["exits"]["down"] = "no_such_place"
        assert grid_game.move("down") is False
        assert grid_game.current_room_id == "lab_entry"
