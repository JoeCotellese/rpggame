# ABOUTME: Tests for the campaign wizard's adventure listing (issue #684 slice 1).
# ABOUTME: Node-surface locations must not be selectable while the wizard drives the grid loop.

import json

import pytest

from dnd_engine.rules.loader import DataLoader
from terminal_client.ui.campaign_wizard import CampaignCreationWizard


@pytest.fixture
def wizard_with_mixed_content(tmp_path):
    dungeon_dir = tmp_path / "content" / "dungeons"
    dungeon_dir.mkdir(parents=True)

    grid = {"id": "grid_dungeon", "name": "Grid Dungeon", "start_room": "a", "rooms": {"a": {}}}
    (dungeon_dir / "grid_dungeon.json").write_text(json.dumps(grid))

    node = {
        "id": "node_settlement",
        "name": "Node Settlement",
        "surface": "node",
        "start_node": "square",
        "nodes": {
            "square": {
                "name": "Square",
                "blurb": "A square.",
                "description": "A quiet square.",
            }
        },
    }
    (dungeon_dir / "node_settlement.json").write_text(json.dumps(node))

    generated = dict(grid, id="generated_123")
    (dungeon_dir / "generated_123.json").write_text(json.dumps(generated))

    loader = DataLoader()
    loader.data_path = tmp_path
    return CampaignCreationWizard(data_loader=loader)


class TestAdventureListing:
    def test_grid_dungeons_listed(self, wizard_with_mixed_content):
        files = wizard_with_mixed_content._list_adventure_files()
        assert [f.stem for f in files] == ["grid_dungeon"]

    def test_node_surface_locations_excluded(self, wizard_with_mixed_content):
        """A node-surface file must not be selectable: the wizard starts the
        grid game loop, which requires rooms/start_room."""
        files = wizard_with_mixed_content._list_adventure_files()
        assert "node_settlement" not in [f.stem for f in files]

    def test_generated_dungeons_excluded(self, wizard_with_mixed_content):
        files = wizard_with_mixed_content._list_adventure_files()
        assert "generated_123" not in [f.stem for f in files]

    def test_unreadable_json_still_listed(self, tmp_path):
        """Malformed JSON keeps its legacy behavior (listed; fails later),
        rather than being silently hidden by the surface filter."""
        dungeon_dir = tmp_path / "content" / "dungeons"
        dungeon_dir.mkdir(parents=True)
        (dungeon_dir / "broken.json").write_text("{not json")

        loader = DataLoader()
        loader.data_path = tmp_path
        wizard = CampaignCreationWizard(data_loader=loader)

        files = wizard._list_adventure_files()
        assert [f.stem for f in files] == ["broken"]
