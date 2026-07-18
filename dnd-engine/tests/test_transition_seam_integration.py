# ABOUTME: Tests for the node<->grid transition seam (issue #684 slice 4).
# ABOUTME: Covers registry node resolution, both seam directions, round trip, and save/load.

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from dnd_engine.core.game_state import GameState
from dnd_engine.core.node_surface import NodeActionError
from dnd_engine.core.room_registry import RoomRegistry
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus, EventType

# test_party and node_game come from tests/conftest.py


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


class TestForwardSeam:
    """A node's authored transition loads the target grid dungeon at its start room."""

    def _gate(self, game):
        return game.dungeon["nodes"]["lab_gate"]["transition"]

    def test_gated_success_enters_grid_at_start_room(self, node_game):
        node_game.enter_node("lab_gate")
        # DC 1 with a non-negative modifier cannot fail (d20 minimum is 1)
        self._gate(node_game)["gate"]["dc"] = 1
        hero = node_game.party.characters[0]
        events = []
        node_game.event_bus.subscribe(EventType.ROOM_ENTER, events.append)

        result = node_game.node_actions.transition(hero)

        assert result["success"] is True
        assert result["prose"].startswith("The gate groans open")
        assert result["check"]["skill"] == "athletics"
        assert result["dungeon"] == "lab_dungeon"
        assert result["location_id"] == "lab_entry"

        assert not node_game.is_node_surface()
        assert node_game.dungeon_name == "lab_dungeon"
        assert node_game.current_room_id == "lab_entry"
        assert node_game.current_node_id is None
        assert node_game.previous_node_id is None

        assert len(events) == 1
        assert events[0].data["room_id"] == "lab_entry"
        assert events[0].data["dungeon_id"] == "lab_dungeon"

    def test_forward_seam_advances_time(self, node_game):
        node_game.enter_node("lab_gate")
        self._gate(node_game)["gate"]["dc"] = 1
        before = node_game.time_manager.elapsed_minutes
        node_game.node_actions.transition(node_game.party.characters[0])
        assert node_game.time_manager.elapsed_minutes == before + 10

    def test_gated_failure_is_a_narrative_beat_not_a_move(self, node_game):
        node_game.enter_node("lab_gate")
        # DC 40 cannot be reached by d20 + a level-1 modifier
        self._gate(node_game)["gate"]["dc"] = 40
        hero = node_game.party.characters[0]
        events = []
        node_game.event_bus.subscribe(EventType.ROOM_ENTER, events.append)
        before = node_game.time_manager.elapsed_minutes

        result = node_game.node_actions.transition(hero)

        assert result["success"] is False
        assert result["prose"].startswith("You heave at the gate")
        assert result["check"]["dc"] == 40
        assert node_game.is_node_surface()
        assert node_game.current_node_id == "lab_gate"
        assert events == []
        assert node_game.time_manager.elapsed_minutes == before

    def test_ungated_transition_needs_no_check(self, node_game):
        node_game.enter_node("lab_gate")
        del self._gate(node_game)["gate"]
        result = node_game.node_actions.transition(node_game.party.characters[0])
        assert result["success"] is True
        assert result["check"] is None
        assert node_game.current_room_id == "lab_entry"

    def test_check_routes_through_make_skill_check(self, node_game):
        """The gate must resolve via Character.make_skill_check (the d20-test
        primitive), not a private dice path."""
        node_game.enter_node("lab_gate")
        hero = node_game.party.characters[0]
        calls = {}
        original = hero.make_skill_check

        def spy(skill, dc, skills_data, **kwargs):
            calls["skill"] = skill
            calls["dc"] = dc
            return original(skill, dc, skills_data, **kwargs)

        hero.make_skill_check = spy

        node_game.node_actions.transition(hero)

        assert calls == {"skill": "athletics", "dc": 10}

    def test_node_without_transition_raises(self, node_game):
        hero = node_game.party.characters[0]
        with pytest.raises(NodeActionError, match="lab_square"):
            node_game.node_actions.transition(hero)

    def test_unknown_gate_skill_raises_node_action_error(self, node_game):
        node_game.enter_node("lab_gate")
        self._gate(node_game)["gate"]["skill"] = "Athletics"
        with pytest.raises(NodeActionError, match="Athletics"):
            node_game.node_actions.transition(node_game.party.characters[0])

    def test_unknown_target_raises_without_state_change(self, node_game):
        node_game.enter_node("lab_gate")
        self._gate(node_game)["gate"]["dc"] = 1
        self._gate(node_game)["to"] = "no_such_dungeon"
        with pytest.raises(NodeActionError, match="no_such_dungeon"):
            node_game.node_actions.transition(node_game.party.characters[0])
        assert node_game.is_node_surface()
        assert node_game.current_node_id == "lab_gate"
        assert node_game.dungeon_name == "lab_settlement"

    def test_transition_off_surface_raises(self, grid_game):
        with pytest.raises(RuntimeError, match="not a node surface"):
            grid_game.node_actions.transition(grid_game.party.characters[0])

    def test_transition_blocked_in_combat(self, node_game):
        node_game.enter_node("lab_gate")
        node_game.in_combat = True
        with pytest.raises(RuntimeError, match="combat"):
            node_game.node_actions.transition(node_game.party.characters[0])


class TestSeamResolutionRobustness:
    """Review findings: resolution and failure paths must degrade cleanly."""

    def test_prefix_shadowed_node_id_still_resolves(self, grid_game, temp_dungeons_dir):
        """A grid dungeon sharing the settlement's dotted prefix must not
        shadow node destinations (the slice-6 arden.* hazard): when the
        prefix-resolved dungeon lacks the room, resolution falls through to
        the node index instead of failing."""
        annex = {
            "name": "Settle Annex",
            "start_room": "settle.annex",
            "rooms": {
                "settle.annex": {
                    "name": "Annex Hall",
                    "description": "A hall sharing the settlement prefix",
                    "exits": {},
                },
            },
        }
        with open(temp_dungeons_dir / "settle_annex.json", "w") as f:
            json.dump(annex, f)

        registry = RoomRegistry(dungeons_path=temp_dungeons_dir)
        # The prefix map resolves "settle." ids to the annex grid dungeon
        assert registry.get_dungeon_for_room("settle.gate") == "settle_annex"

        grid_game.room_registry = registry
        grid_game.dungeon["rooms"]["lab_entry"]["exits"]["down"] = "settle.gate"

        assert grid_game.move("down") is True
        assert grid_game.is_node_surface()
        assert grid_game.dungeon_name == "test_settlement"
        assert grid_game.current_node_id == "settle.gate"

    def test_failed_move_does_not_stale_flee_direction(self, grid_game):
        grid_game.dungeon["rooms"]["lab_entry"]["exits"]["down"] = "no_such_place"
        assert grid_game.last_entry_direction is None
        assert grid_game.move("down") is False
        assert grid_game.last_entry_direction is None

    def test_transition_target_missing_start_room_fails_without_state_change(self, node_game):
        node_game.enter_node("lab_gate")
        node_game.dungeon["nodes"]["lab_gate"]["transition"]["gate"]["dc"] = 1
        node_game.dungeon["nodes"]["lab_gate"]["transition"]["to"] = "broken"
        # Seed the registry cache with a dungeon that authors no start_room
        node_game.room_registry._loaded_dungeons["broken"] = {
            "name": "Broken",
            "rooms": {"b1": {"name": "B1", "description": "x", "exits": {}}},
        }
        with pytest.raises(NodeActionError, match="broken"):
            node_game.node_actions.transition(node_game.party.characters[0])
        assert node_game.is_node_surface()
        assert node_game.dungeon_name == "lab_settlement"
        assert node_game.current_node_id == "lab_gate"

    def test_flee_across_seam_lands_on_node_surface(self, grid_game):
        """Fleeing combat through a node-bound exit crosses the seam instead
        of crashing on the tile-room API."""
        grid_game.last_entry_direction = "down"  # reverse is "up", the node exit
        grid_game.in_combat = True
        grid_game.active_enemies = []

        result = grid_game.flee_combat()

        assert result["success"] is True
        assert result["retreat_room"] == "The Old Gate"
        assert grid_game.is_node_surface()
        assert grid_game.current_node_id == "lab_gate"


class TestRoundTrip:
    """The slice gate: settlement -> dungeon -> back to the originating node,
    with state preserved on both sides of the seam."""

    def test_round_trip_preserves_state_on_both_sides(self, node_game):
        settlement = node_game.dungeon
        hero = node_game.party.characters[0]
        node_game.enter_node("lab_gate")
        # DC 1 with a non-negative modifier cannot fail (d20 minimum is 1)
        settlement["nodes"]["lab_gate"]["transition"]["gate"]["dc"] = 1

        result = node_game.node_actions.transition(hero)
        assert result["success"] is True

        # Mutate dungeon-side state before returning
        dungeon_side = node_game.dungeon
        dungeon_side["rooms"]["lab_entry"]["searched"] = True

        assert node_game.move("up") is True

        # Back at the originating node, on the same settlement dict:
        # session mutations (including the forced DC) survived the seam
        assert node_game.dungeon is settlement
        assert node_game.current_node_id == "lab_gate"
        assert node_game.is_node_surface()

        # Cross again: the dungeon side is the same dict too
        result = node_game.node_actions.transition(hero)
        assert result["success"] is True
        assert node_game.dungeon is dungeon_side
        assert node_game.dungeon["rooms"]["lab_entry"]["searched"] is True

    def test_round_trip_keeps_party_and_clock(self, node_game):
        hero = node_game.party.characters[0]
        hero.current_hp = 5
        node_game.enter_node("lab_gate")
        node_game.dungeon["nodes"]["lab_gate"]["transition"]["gate"]["dc"] = 1

        node_game.node_actions.transition(hero)
        node_game.move("up")

        assert node_game.party.characters[0] is hero
        assert hero.current_hp == 5
        # enter_node is free; each seam crossing costs 10 minutes
        assert node_game.time_manager.elapsed_minutes == 20


class TestSaveLoadAcrossSeam:
    def test_save_in_dungeon_load_and_return_to_settlement(self, node_game, tmp_path):
        from dnd_engine.core.save_slot_manager import SaveSlotManager

        hero = node_game.party.characters[0]
        node_game.enter_node("lab_gate")
        node_game.dungeon["nodes"]["lab_gate"]["transition"]["gate"]["dc"] = 1
        node_game.node_actions.transition(hero)
        node_game.dungeon["rooms"]["lab_entry"]["searched"] = True

        manager = SaveSlotManager(saves_dir=tmp_path)
        manager.save_game(1, node_game)
        loaded, _ = manager.load_game(1)

        assert loaded.dungeon_name == "lab_dungeon"
        assert loaded.current_room_id == "lab_entry"
        assert loaded.current_node_id is None
        assert loaded.dungeon["rooms"]["lab_entry"]["searched"] is True

        assert loaded.move("up") is True
        assert loaded.is_node_surface()
        assert loaded.dungeon_name == "lab_settlement"
        assert loaded.current_node_id == "lab_gate"
