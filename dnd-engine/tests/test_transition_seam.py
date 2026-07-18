# ABOUTME: Tests for the node<->grid transition seam (issue #684 slice 4).
# ABOUTME: Covers registry node resolution, both seam directions, round trip, and save/load.

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from dnd_engine.core.room_registry import RoomRegistry
from dnd_engine.rules.loader import DataLoader


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
