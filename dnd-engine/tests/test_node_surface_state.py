# ABOUTME: Tests for GameState node-surface state and navigation API (issue #684 slice 2).
# ABOUTME: Covers node init, list/enter/current node, grid-method degradation, and reset.

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
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
def node_game(test_party):
    return GameState(
        party=test_party,
        dungeon_name="lab_settlement",
        event_bus=EventBus(),
        data_loader=DataLoader(),
    )


@pytest.fixture
def grid_game(test_party):
    return GameState(
        party=test_party,
        dungeon_name="test_dungeon",
        event_bus=EventBus(),
        data_loader=DataLoader(),
    )


class TestNodeSurfaceInit:
    def test_starts_at_start_node(self, node_game):
        assert node_game.is_node_surface()
        assert node_game.surface == "node"
        assert node_game.current_node_id == "lab_square"

    def test_no_current_room_on_node_surface(self, node_game):
        assert node_game.current_room_id is None

    def test_grid_game_unaffected(self, grid_game):
        assert not grid_game.is_node_surface()
        assert grid_game.surface == "grid"
        assert grid_game.current_node_id is None
        assert grid_game.current_room_id == grid_game.dungeon["start_room"]


class TestNodeNavigation:
    def test_list_nodes_returns_id_name_blurb_in_authored_order(self, node_game):
        nodes = node_game.list_nodes()
        assert [n["id"] for n in nodes] == ["lab_square", "lab_tavern", "lab_gate"]
        for node in nodes:
            assert node["name"]
            assert node["blurb"]
            assert set(node) == {"id", "name", "blurb"}

    def test_current_node_returns_node_with_id(self, node_game):
        node = node_game.current_node()
        assert node["id"] == "lab_square"
        assert node["name"] == "Lab Square"
        assert node["description"]

    def test_enter_node_moves_and_returns_context(self, node_game):
        context = node_game.enter_node("lab_tavern")
        assert node_game.current_node_id == "lab_tavern"
        assert node_game.previous_node_id == "lab_square"
        assert context["id"] == "lab_tavern"
        assert context["name"] == "The Testing Tankard"
        assert context["description"]
        assert context["actions"] == ["talk", "shop", "rest"]
        assert context["npcs"] == []

    def test_enter_node_unknown_id_raises(self, node_game):
        with pytest.raises(ValueError, match="nowhere"):
            node_game.enter_node("nowhere")
        assert node_game.current_node_id == "lab_square"

    def test_enter_node_emits_room_enter_event(self, node_game):
        """Nodes unify with rooms at the event level so quest auto-activation
        and narrative listeners work unchanged on node surfaces."""
        events = []
        node_game.event_bus.subscribe(EventType.ROOM_ENTER, events.append)

        node_game.enter_node("lab_gate")

        assert len(events) == 1
        assert events[0].data["room_id"] == "lab_gate"
        assert events[0].data["room_name"] == "The Old Gate"

    def test_enter_node_includes_npcs_present(self, node_game):
        class StubNPC:
            def __init__(self):
                self.id = "stub_npc"
                self.name = "Stubby"
                self.display_name = "Stubby the Stub"

        class StubNPCManager:
            def get_npcs_in_room(self, room_guid):
                return [StubNPC()] if room_guid == "lab_tavern" else []

        node_game.npc_manager = StubNPCManager()

        context = node_game.enter_node("lab_tavern")
        assert context["npcs"] == [
            {"id": "stub_npc", "name": "Stubby", "display_name": "Stubby the Stub"}
        ]

    def test_node_api_raises_on_grid_surface(self, grid_game):
        with pytest.raises(RuntimeError, match="node"):
            grid_game.current_node()
        with pytest.raises(RuntimeError, match="node"):
            grid_game.list_nodes()
        with pytest.raises(RuntimeError, match="node"):
            grid_game.enter_node("anywhere")


class TestGridMachineryDormant:
    """On a node surface the tile-grid machinery must degrade cleanly."""

    def test_move_returns_false(self, node_game):
        assert node_game.move("north") is False
        assert node_game.current_node_id == "lab_square"

    def test_get_current_room_raises_clear_error(self, node_game):
        with pytest.raises(RuntimeError, match="node surface"):
            node_game.get_current_room()

    def test_get_available_exits_empty(self, node_game):
        assert node_game.get_available_exits() == {}

    def test_get_available_actions_empty(self, node_game):
        assert node_game.get_available_actions() == []

    def test_start_does_not_crash(self, node_game):
        node_game.start()  # no enemies, no perception sweep; should not raise
        assert node_game.in_combat is False


class TestResetDungeon:
    def test_reset_on_node_surface_returns_to_start_node(self, node_game):
        node_game.enter_node("lab_gate")
        node_game.reset_dungeon()
        assert node_game.current_node_id == "lab_square"
        assert node_game.previous_node_id is None
        assert node_game.current_room_id is None

    def test_reset_to_missing_dungeon_leaves_state_intact(self, grid_game):
        """A failed reset must not half-mutate: name and dungeon stay paired."""
        old_name = grid_game.dungeon_name
        old_dungeon = grid_game.dungeon
        old_room = grid_game.current_room_id

        with pytest.raises(FileNotFoundError):
            grid_game.reset_dungeon("no_such_dungeon")

        assert grid_game.dungeon_name == old_name
        assert grid_game.dungeon is old_dungeon
        assert grid_game.current_room_id == old_room

    def test_reset_grid_to_node_dungeon_switches_surface(self, grid_game):
        grid_game.reset_dungeon("lab_settlement")
        assert grid_game.is_node_surface()
        assert grid_game.current_node_id == "lab_square"
        assert grid_game.current_room_id is None
