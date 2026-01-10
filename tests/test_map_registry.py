# ABOUTME: Unit tests for the dungeon map registry module
# ABOUTME: Verifies dungeon ID to grid map file mapping functionality

import pytest
from pathlib import Path

from dnd_engine.spatial.map_registry import (
    DUNGEON_GRID_MAPS,
    get_grid_map_path,
    has_grid_map,
)


class TestDungeonGridMaps:
    """Tests for the DUNGEON_GRID_MAPS registry."""

    def test_registry_is_dict(self):
        """Registry should be a dictionary."""
        assert isinstance(DUNGEON_GRID_MAPS, dict)

    def test_registry_contains_laboratory(self):
        """Registry should contain the poisoned laboratory."""
        assert "poisoned_laboratory" in DUNGEON_GRID_MAPS

    def test_registry_values_are_filenames(self):
        """All registry values should be JSON filenames."""
        for dungeon_id, filename in DUNGEON_GRID_MAPS.items():
            assert isinstance(filename, str)
            assert filename.endswith(".json"), (
                f"Grid map for {dungeon_id} should be a JSON file"
            )


class TestGetGridMapPath:
    """Tests for the get_grid_map_path function."""

    def test_returns_path_for_known_dungeon(self):
        """Should return a Path for a known dungeon."""
        result = get_grid_map_path("poisoned_laboratory")
        assert isinstance(result, Path)

    def test_path_points_to_maps_directory(self):
        """Path should point to the maps content directory."""
        result = get_grid_map_path("poisoned_laboratory")
        assert "data/content/maps" in str(result)

    def test_path_has_correct_filename(self):
        """Path should have the filename from the registry."""
        result = get_grid_map_path("poisoned_laboratory")
        assert result.name == "laboratory_grid.json"

    def test_returns_none_for_unknown_dungeon(self):
        """Should return None for an unknown dungeon."""
        result = get_grid_map_path("nonexistent_dungeon")
        assert result is None

    def test_returns_none_for_empty_string(self):
        """Should return None for empty dungeon ID."""
        result = get_grid_map_path("")
        assert result is None


class TestHasGridMap:
    """Tests for the has_grid_map function."""

    def test_returns_true_for_known_dungeon(self):
        """Should return True for a dungeon with a grid map."""
        assert has_grid_map("poisoned_laboratory") is True

    def test_returns_false_for_unknown_dungeon(self):
        """Should return False for a dungeon without a grid map."""
        assert has_grid_map("nonexistent_dungeon") is False

    def test_returns_false_for_empty_string(self):
        """Should return False for empty dungeon ID."""
        assert has_grid_map("") is False

    def test_returns_false_for_none_like_values(self):
        """Should handle None-like edge cases gracefully."""
        # Note: Type hints say str but testing defensive behavior
        assert has_grid_map("None") is False
        assert has_grid_map("null") is False
