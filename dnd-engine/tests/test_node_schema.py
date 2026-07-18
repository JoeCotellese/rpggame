# ABOUTME: Tests for the node-surface location schema (issue #684 slice 1).
# ABOUTME: Covers surface discrimination, nodes validation, and gated-action prose rules.

import copy
import json

import pytest

from dnd_engine.core.room_registry import RoomRegistry
from dnd_engine.rules.loader import DataLoader
from dnd_engine.rules.node_schema import (
    NODE_ACTION_VOCABULARY,
    NodeSchemaError,
    validate_location_surface,
    validate_node_location,
)


@pytest.fixture
def loader():
    return DataLoader()


def _minimal_settlement() -> dict:
    """A minimal valid node-surface location for mutation in tests."""
    return {
        "id": "test_settlement",
        "name": "Test Settlement",
        "surface": "node",
        "start_node": "square",
        "nodes": {
            "square": {
                "name": "The Square",
                "blurb": "A quiet square.",
                "description": "You stand in a quiet square.",
                "npcs": [],
                "actions": ["gather_rumors"],
            },
        },
    }


def _write_dungeon(tmp_path, name: str, data: dict) -> None:
    dungeon_dir = tmp_path / "content" / "dungeons"
    dungeon_dir.mkdir(parents=True, exist_ok=True)
    (dungeon_dir / f"{name}.json").write_text(json.dumps(data))


class TestLabSettlementFixture:
    """The lab settlement fixture loads and passes validation."""

    def test_fixture_loads(self, loader):
        data = loader.load_dungeon("lab_settlement")
        assert data["surface"] == "node"
        assert data["start_node"] in data["nodes"]

    def test_fixture_has_prose_on_every_node(self, loader):
        data = loader.load_dungeon("lab_settlement")
        for node_id, node in data["nodes"].items():
            assert node["name"], node_id
            assert node["blurb"], node_id
            assert node["description"], node_id

    def test_fixture_exercises_gated_action_and_transition(self, loader):
        """The lab fixture must cover the shapes later slices build on."""
        data = loader.load_dungeon("lab_settlement")
        nodes = data["nodes"].values()
        gated = [
            a for n in nodes for a in n.get("actions", []) if isinstance(a, dict) and a.get("gate")
        ]
        transitions = [n["transition"] for n in nodes if "transition" in n]
        assert gated, "fixture needs at least one skill-gated action"
        assert transitions, "fixture needs at least one transition"


class TestGridPathUnchanged:
    """Grid dungeons (no surface key) load exactly as before."""

    def test_standalone_grid_dungeon_loads(self, loader):
        data = loader.load_dungeon("test_dungeon")
        assert "rooms" in data
        assert "surface" not in data

    def test_campaign_grid_dungeon_loads(self, loader):
        data = loader.load_dungeon("crypt", campaign_id="the_unquiet_dead")
        assert "rooms" in data


class TestSurfaceDispatch:
    """validate_location_surface is the single entry point for surface handling."""

    def test_missing_surface_passes(self):
        validate_location_surface({"rooms": {}})  # legacy grid; should not raise

    def test_explicit_grid_surface_passes(self):
        validate_location_surface({"surface": "grid", "rooms": {}})  # should not raise

    def test_node_surface_dispatches_to_node_validation(self):
        data = _minimal_settlement()
        del data["start_node"]
        with pytest.raises(NodeSchemaError, match="start_node"):
            validate_location_surface(data)

    def test_unknown_surface_rejected(self):
        with pytest.raises(NodeSchemaError, match="surface"):
            validate_location_surface({"surface": "holodeck"})

    def test_non_dict_passes_through(self):
        validate_location_surface([])  # legacy tolerance; should not raise

    def test_loader_rejects_typoed_surface(self, loader, tmp_path, monkeypatch):
        """A typo like surface:"nodes" must fail loudly, not load as a grid."""
        bad = _minimal_settlement()
        bad["surface"] = "nodes"
        _write_dungeon(tmp_path, "typo_settlement", bad)
        monkeypatch.setattr(loader, "data_path", tmp_path)

        with pytest.raises(NodeSchemaError, match="surface"):
            loader.load_dungeon("typo_settlement")

    def test_loader_tolerates_non_dict_top_level(self, loader, tmp_path, monkeypatch):
        """Non-object top-level JSON keeps its legacy behavior: returned as-is."""
        dungeon_dir = tmp_path / "content" / "dungeons"
        dungeon_dir.mkdir(parents=True)
        (dungeon_dir / "weird.json").write_text("[]")
        monkeypatch.setattr(loader, "data_path", tmp_path)

        assert loader.load_dungeon("weird") == []


class TestSurfaceDiscrimination:
    def test_unknown_surface_value_rejected(self):
        data = _minimal_settlement()
        data["surface"] = "holodeck"
        with pytest.raises(NodeSchemaError, match="surface"):
            validate_node_location(data)

    def test_rooms_and_nodes_are_mutually_exclusive(self):
        data = _minimal_settlement()
        data["rooms"] = {"square_room": {}}
        with pytest.raises(NodeSchemaError, match="rooms"):
            validate_node_location(data)

    def test_node_surface_requires_nodes(self):
        data = _minimal_settlement()
        del data["nodes"]
        with pytest.raises(NodeSchemaError, match="nodes"):
            validate_node_location(data)


class TestStartNode:
    def test_start_node_required(self):
        data = _minimal_settlement()
        del data["start_node"]
        with pytest.raises(NodeSchemaError, match="start_node"):
            validate_node_location(data)

    def test_start_node_must_exist(self):
        data = _minimal_settlement()
        data["start_node"] = "nowhere"
        with pytest.raises(NodeSchemaError, match="start_node"):
            validate_node_location(data)


class TestNodeProse:
    @pytest.mark.parametrize("missing", ["name", "blurb", "description"])
    def test_prose_fields_required(self, missing):
        data = _minimal_settlement()
        del data["nodes"]["square"][missing]
        with pytest.raises(NodeSchemaError, match=missing):
            validate_node_location(data)

    @pytest.mark.parametrize("missing", ["name", "blurb", "description"])
    def test_prose_fields_must_be_nonempty(self, missing):
        data = _minimal_settlement()
        data["nodes"]["square"][missing] = ""
        with pytest.raises(NodeSchemaError, match=missing):
            validate_node_location(data)


class TestNodeKeys:
    """Unknown keys fail at load so typos can't silently drop content."""

    def test_typoed_key_rejected(self):
        data = _minimal_settlement()
        data["nodes"]["square"]["transtion"] = {"to": "test_dungeon"}
        with pytest.raises(NodeSchemaError, match="transtion"):
            validate_node_location(data)

    def test_quest_hook_allowed(self):
        data = _minimal_settlement()
        data["nodes"]["square"]["quest_hook"] = "investigate_crypt"
        validate_node_location(data)  # should not raise


class TestActionVocabulary:
    def test_vocabulary_contents(self):
        assert NODE_ACTION_VOCABULARY == {
            "talk",
            "shop",
            "rest",
            "gather_rumors",
            "read_job_board",
        }

    def test_simple_vocabulary_actions_accepted(self):
        data = _minimal_settlement()
        data["nodes"]["square"]["actions"] = sorted(NODE_ACTION_VOCABULARY)
        validate_node_location(data)  # should not raise

    def test_unknown_string_action_rejected(self):
        data = _minimal_settlement()
        data["nodes"]["square"]["actions"] = ["dance"]
        with pytest.raises(NodeSchemaError, match="dance"):
            validate_node_location(data)

    def test_bare_examine_string_rejected(self):
        """examine_* is a skill check; without object form there is nowhere
        for the gate and its two prose branches to live."""
        data = _minimal_settlement()
        data["nodes"]["square"]["actions"] = ["examine_door"]
        with pytest.raises(NodeSchemaError, match="examine_door"):
            validate_node_location(data)

    def test_examine_object_with_gate_and_prose_accepted(self):
        data = _minimal_settlement()
        data["nodes"]["square"]["actions"] = [
            {
                "id": "examine_door",
                "gate": {"skill": "religion", "dc": 12},
                "on_success": "The symbol is a ward of Durgon.",
                "on_failure": "The scratches mean nothing to you.",
            }
        ]
        validate_node_location(data)  # should not raise

    def test_examine_object_without_gate_rejected(self):
        """The examine invariant holds in object form too, not only string form."""
        data = _minimal_settlement()
        data["nodes"]["square"]["actions"] = [{"id": "examine_door"}]
        with pytest.raises(NodeSchemaError, match="gate"):
            validate_node_location(data)

    def test_unknown_object_action_id_rejected(self):
        data = _minimal_settlement()
        data["nodes"]["square"]["actions"] = [
            {"id": "moonwalk", "on_success": "x", "on_failure": "y"}
        ]
        with pytest.raises(NodeSchemaError, match="moonwalk"):
            validate_node_location(data)


class TestActionsShape:
    def test_actions_string_rejected(self):
        data = _minimal_settlement()
        data["nodes"]["square"]["actions"] = "talk"
        with pytest.raises(NodeSchemaError, match="actions"):
            validate_node_location(data)

    def test_actions_non_iterable_rejected_as_schema_error(self):
        data = _minimal_settlement()
        data["nodes"]["square"]["actions"] = 5
        with pytest.raises(NodeSchemaError, match="actions"):
            validate_node_location(data)


class TestGatedActionProse:
    """AC: every skill-gated action authors success AND failure prose."""

    @pytest.mark.parametrize("missing", ["on_success", "on_failure"])
    def test_gated_action_requires_both_prose_branches(self, missing):
        action = {
            "id": "examine_door",
            "gate": {"skill": "religion", "dc": 12},
            "on_success": "You see it.",
            "on_failure": "You see nothing.",
        }
        del action[missing]
        data = _minimal_settlement()
        data["nodes"]["square"]["actions"] = [action]
        with pytest.raises(NodeSchemaError, match=missing):
            validate_node_location(data)

    def test_gate_requires_skill_and_dc(self):
        data = _minimal_settlement()
        data["nodes"]["square"]["actions"] = [
            {
                "id": "examine_door",
                "gate": {"skill": "religion"},
                "on_success": "x",
                "on_failure": "y",
            }
        ]
        with pytest.raises(NodeSchemaError, match="dc"):
            validate_node_location(data)

    def test_boolean_dc_rejected(self):
        """bool is a subclass of int; dc: true must not validate as DC 1."""
        data = _minimal_settlement()
        data["nodes"]["square"]["actions"] = [
            {
                "id": "examine_door",
                "gate": {"skill": "religion", "dc": True},
                "on_success": "x",
                "on_failure": "y",
            }
        ]
        with pytest.raises(NodeSchemaError, match="dc"):
            validate_node_location(data)

    def test_zero_dc_accepted(self):
        data = _minimal_settlement()
        data["nodes"]["square"]["actions"] = [
            {
                "id": "examine_door",
                "gate": {"skill": "religion", "dc": 0},
                "on_success": "x",
                "on_failure": "y",
            }
        ]
        validate_node_location(data)  # should not raise


class TestTransition:
    def test_transition_requires_destination(self):
        data = _minimal_settlement()
        data["nodes"]["square"]["transition"] = {}
        with pytest.raises(NodeSchemaError, match="to"):
            validate_node_location(data)

    def test_ungated_transition_accepted(self):
        data = _minimal_settlement()
        data["nodes"]["square"]["transition"] = {"to": "test_dungeon"}
        validate_node_location(data)  # should not raise

    @pytest.mark.parametrize("missing", ["on_success", "on_failure"])
    def test_gated_transition_requires_both_prose_branches(self, missing):
        transition = {
            "to": "test_dungeon",
            "gate": {"skill": "religion", "dc": 12},
            "on_success": "The door opens.",
            "on_failure": "The door resists.",
        }
        del transition[missing]
        data = _minimal_settlement()
        data["nodes"]["square"]["transition"] = transition
        with pytest.raises(NodeSchemaError, match=missing):
            validate_node_location(data)


class TestLoaderIntegration:
    """load_dungeon validates node-surface files at load time."""

    def test_invalid_node_file_raises_at_load(self, loader, tmp_path, monkeypatch):
        bad = copy.deepcopy(_minimal_settlement())
        bad["start_node"] = "nowhere"
        _write_dungeon(tmp_path, "bad_settlement", bad)
        monkeypatch.setattr(loader, "data_path", tmp_path)

        with pytest.raises(NodeSchemaError, match="start_node"):
            loader.load_dungeon("bad_settlement")


class TestRoomRegistryValidation:
    """The registry load path enforces the same surface validation as DataLoader."""

    def test_registry_rejects_invalid_node_file(self, tmp_path):
        bad = _minimal_settlement()
        bad["start_node"] = "nowhere"
        (tmp_path / "bad_settlement.json").write_text(json.dumps(bad))
        registry = RoomRegistry(dungeons_path=tmp_path)

        with pytest.raises(NodeSchemaError, match="start_node"):
            registry.load_dungeon("bad_settlement")

    def test_registry_loads_valid_node_file(self, tmp_path):
        good = _minimal_settlement()
        (tmp_path / "good_settlement.json").write_text(json.dumps(good))
        registry = RoomRegistry(dungeons_path=tmp_path)

        data = registry.load_dungeon("good_settlement")
        assert data is not None
        assert data["surface"] == "node"
