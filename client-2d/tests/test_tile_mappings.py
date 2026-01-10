# ABOUTME: Unit tests for tile mappings and Stone Soup sprite integration.
# ABOUTME: Tests mapping loading, resolution priority, and fallback behavior.

"""Tests for tile mappings and Stone Soup sprite integration."""

import json
import tempfile
from pathlib import Path

import pytest
from client_2d.assets.asset_manager import AssetManager
from client_2d.assets.sprite_resolver import SpriteResolver


@pytest.fixture
def temp_assets_with_mappings():
    """Create a temporary assets directory with tile mappings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        assets_path = Path(tmpdir)

        # Create directory structure
        (assets_path / "sprites" / "monsters" / "undead").mkdir(parents=True)
        (assets_path / "sprites" / "monsters" / "beast").mkdir(parents=True)
        (assets_path / "sprites" / "characters").mkdir(parents=True)
        (assets_path / "sprites" / "items" / "weapons").mkdir(parents=True)
        (assets_path / "sprites" / "effects" / "damage").mkdir(parents=True)
        (assets_path / "stonesoup" / "monster" / "undead").mkdir(parents=True)
        (assets_path / "stonesoup" / "monster" / "beast").mkdir(parents=True)
        (assets_path / "stonesoup" / "player" / "base").mkdir(parents=True)
        (assets_path / "stonesoup" / "item" / "weapon").mkdir(parents=True)
        (assets_path / "stonesoup" / "dungeon" / "floor").mkdir(parents=True)
        (assets_path / "stonesoup" / "dungeon" / "wall").mkdir(parents=True)
        (assets_path / "stonesoup" / "effect").mkdir(parents=True)
        (assets_path / "tilesets").mkdir(parents=True)
        (assets_path / "ui").mkdir(parents=True)

        # Create Stone Soup sprites
        (assets_path / "stonesoup" / "monster" / "undead" / "skeleton_small.png").touch()
        (assets_path / "stonesoup" / "monster" / "undead" / "ghoul.png").touch()
        (assets_path / "stonesoup" / "monster" / "beast" / "wolf.png").touch()
        (assets_path / "stonesoup" / "player" / "base" / "human_m.png").touch()
        (assets_path / "stonesoup" / "player" / "base" / "elf_high_m.png").touch()
        (assets_path / "stonesoup" / "item" / "weapon" / "long_sword1.png").touch()
        (assets_path / "stonesoup" / "dungeon" / "floor" / "rect_gray0.png").touch()
        (assets_path / "stonesoup" / "dungeon" / "wall" / "brick_gray0.png").touch()
        (assets_path / "stonesoup" / "effect" / "slash.png").touch()

        # Create fallback sprites (existing system)
        (assets_path / "sprites" / "monsters" / "undead" / "_fallback.png").touch()
        (assets_path / "sprites" / "monsters" / "_fallback_generic.png").touch()
        (assets_path / "sprites" / "characters" / "_fallback_humanoid.png").touch()
        (assets_path / "sprites" / "characters" / "fighter.png").touch()

        # Create tile_mappings.json
        mappings = {
            "_meta": {
                "description": "Test mappings",
                "source": "Test",
            },
            "monsters": {
                "skeleton": "monster/undead/skeleton_small.png",
                "ghoul": "monster/undead/ghoul.png",
                "wolf": "monster/beast/wolf.png",
                "ghost": "monster/undead/ghost.png",  # Missing file
            },
            "characters": {
                "fighter": "player/base/human_m.png",
                "wizard": "player/base/elf_high_m.png",
            },
            "items": {
                "longsword": "item/weapon/long_sword1.png",
            },
            "terrain": {
                "floor_stone": "dungeon/floor/rect_gray0.png",
                "wall_brick": "dungeon/wall/brick_gray0.png",
            },
            "effects": {
                "damage_slash": "effect/slash.png",
            },
            "decorations": {
                "chest": "dungeon/chest/chest.png",  # Missing file
            },
        }
        with open(assets_path / "tile_mappings.json", "w") as f:
            json.dump(mappings, f)

        yield assets_path


@pytest.fixture
def temp_assets_no_mappings():
    """Create a temporary assets directory without tile mappings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        assets_path = Path(tmpdir)

        # Create directory structure
        (assets_path / "sprites" / "monsters" / "undead").mkdir(parents=True)
        (assets_path / "sprites" / "characters").mkdir(parents=True)

        # Create fallback sprites only
        (assets_path / "sprites" / "monsters" / "undead" / "skeleton.png").touch()
        (assets_path / "sprites" / "monsters" / "undead" / "_fallback.png").touch()
        (assets_path / "sprites" / "monsters" / "_fallback_generic.png").touch()
        (assets_path / "sprites" / "characters" / "fighter.png").touch()
        (assets_path / "sprites" / "characters" / "_fallback_humanoid.png").touch()

        yield assets_path


class TestMappingsLoading:
    """Tests for loading tile mappings from JSON."""

    def test_loads_mappings_on_init(self, temp_assets_with_mappings):
        """Should load mappings automatically on initialization."""
        resolver = SpriteResolver(assets_path=temp_assets_with_mappings)

        assert resolver.has_mappings is True

    def test_has_mappings_false_when_no_file(self, temp_assets_no_mappings):
        """Should report no mappings when file doesn't exist."""
        resolver = SpriteResolver(assets_path=temp_assets_no_mappings)

        assert resolver.has_mappings is False

    def test_mapping_categories_loaded(self, temp_assets_with_mappings):
        """Should expose loaded mapping categories."""
        resolver = SpriteResolver(assets_path=temp_assets_with_mappings)

        categories = resolver.mapping_categories

        assert "monsters" in categories
        assert "characters" in categories
        assert "terrain" in categories
        assert "_meta" not in categories  # Should skip meta

    def test_reload_mappings(self, temp_assets_with_mappings):
        """Should be able to reload mappings from a different file."""
        resolver = SpriteResolver(assets_path=temp_assets_with_mappings)

        # Create a new mappings file
        new_mappings = {"monsters": {"test": "test.png"}}
        new_file = temp_assets_with_mappings / "new_mappings.json"
        with open(new_file, "w") as f:
            json.dump(new_mappings, f)

        result = resolver.load_mappings(new_file)

        assert result is True
        assert "test" in resolver._mappings.get("monsters", {})

    def test_invalid_json_handled(self, temp_assets_with_mappings):
        """Should handle invalid JSON gracefully."""
        resolver = SpriteResolver(assets_path=temp_assets_with_mappings)

        # Write invalid JSON
        bad_file = temp_assets_with_mappings / "bad.json"
        bad_file.write_text("not valid json {{{")

        result = resolver.load_mappings(bad_file)

        assert result is False
        assert resolver.has_mappings is False


class TestMappedResolution:
    """Tests for sprite resolution with mappings."""

    def test_monster_resolves_from_mapping(self, temp_assets_with_mappings):
        """Should resolve monster sprite from Stone Soup mapping."""
        resolver = SpriteResolver(assets_path=temp_assets_with_mappings)

        path = resolver.get_monster_sprite_path("skeleton", "undead")

        assert path is not None
        assert "stonesoup" in str(path)
        assert path.name == "skeleton_small.png"

    def test_character_resolves_from_mapping(self, temp_assets_with_mappings):
        """Should resolve character sprite from Stone Soup mapping."""
        resolver = SpriteResolver(assets_path=temp_assets_with_mappings)

        path = resolver.get_character_sprite_path("fighter")

        assert path is not None
        assert "stonesoup" in str(path)
        assert path.name == "human_m.png"

    def test_item_resolves_from_mapping(self, temp_assets_with_mappings):
        """Should resolve item sprite from Stone Soup mapping."""
        resolver = SpriteResolver(assets_path=temp_assets_with_mappings)

        path = resolver.get_item_sprite_path("longsword", "weapons")

        assert path is not None
        assert "stonesoup" in str(path)
        assert path.name == "long_sword1.png"

    def test_terrain_resolves_from_mapping(self, temp_assets_with_mappings):
        """Should resolve terrain sprite from Stone Soup mapping."""
        resolver = SpriteResolver(assets_path=temp_assets_with_mappings)

        path = resolver.get_terrain_sprite_path("floor_stone")

        assert path is not None
        assert "stonesoup" in str(path)
        assert path.name == "rect_gray0.png"

    def test_effect_resolves_from_mapping(self, temp_assets_with_mappings):
        """Should resolve effect sprite from Stone Soup mapping."""
        resolver = SpriteResolver(assets_path=temp_assets_with_mappings)

        path = resolver.get_effect_sprite_path("damage_slash", "damage")

        assert path is not None
        assert "stonesoup" in str(path)
        assert path.name == "slash.png"


class TestFallbackWithMappings:
    """Tests for fallback behavior when mappings exist but files don't."""

    def test_falls_back_when_mapped_file_missing(self, temp_assets_with_mappings):
        """Should fall back to placeholder when mapped file doesn't exist."""
        resolver = SpriteResolver(assets_path=temp_assets_with_mappings)

        # ghost is mapped but the file doesn't exist
        path = resolver.get_monster_sprite_path("ghost", "undead")

        assert path is not None
        assert "stonesoup" not in str(path)
        assert path.name == "_fallback.png"

    def test_unmapped_entity_uses_fallback(self, temp_assets_with_mappings):
        """Should use fallback for entities not in mappings."""
        resolver = SpriteResolver(assets_path=temp_assets_with_mappings)

        # zombie is not in mappings at all
        path = resolver.get_monster_sprite_path("zombie", "undead")

        assert path is not None
        assert path.name == "_fallback.png"

    def test_terrain_returns_none_when_missing(self, temp_assets_with_mappings):
        """Should return None for unmapped terrain (no fallback)."""
        resolver = SpriteResolver(assets_path=temp_assets_with_mappings)

        path = resolver.get_terrain_sprite_path("floor_lava")

        assert path is None

    def test_decoration_returns_none_when_file_missing(
        self, temp_assets_with_mappings
    ):
        """Should return None when decoration mapped but file missing."""
        resolver = SpriteResolver(assets_path=temp_assets_with_mappings)

        # chest is mapped but file doesn't exist
        path = resolver.get_decoration_sprite_path("chest")

        assert path is None


class TestWithoutMappings:
    """Tests for behavior when no mappings file exists."""

    def test_still_uses_fallback_hierarchy(self, temp_assets_no_mappings):
        """Should use original fallback hierarchy without mappings."""
        resolver = SpriteResolver(assets_path=temp_assets_no_mappings)

        path = resolver.get_monster_sprite_path("skeleton", "undead")

        assert path is not None
        assert path.name == "skeleton.png"

    def test_character_uses_original_fallback(self, temp_assets_no_mappings):
        """Should use original character fallback without mappings."""
        resolver = SpriteResolver(assets_path=temp_assets_no_mappings)

        path = resolver.get_character_sprite_path("fighter")

        assert path is not None
        assert path.name == "fighter.png"


class TestAssetManagerWithMappings:
    """Tests for AssetManager integration with tile mappings."""

    def test_has_stonesoup_tiles_true(self, temp_assets_with_mappings):
        """Should report Stone Soup tiles available when mappings exist."""
        manager = AssetManager(assets_path=temp_assets_with_mappings)

        assert manager.has_stonesoup_tiles is True

    def test_has_stonesoup_tiles_false(self, temp_assets_no_mappings):
        """Should report no Stone Soup tiles when no mappings."""
        manager = AssetManager(assets_path=temp_assets_no_mappings)

        assert manager.has_stonesoup_tiles is False

    def test_validate_assets_includes_stonesoup(self, temp_assets_with_mappings):
        """Should validate Stone Soup directories."""
        manager = AssetManager(assets_path=temp_assets_with_mappings)

        validation = manager.validate_assets()

        assert "stonesoup" in validation
        assert "tile_mappings" in validation
        assert validation["stonesoup"] is True
        assert validation["tile_mappings"] is True

    def test_terrain_sprite_path(self, temp_assets_with_mappings):
        """Should get terrain sprite path through AssetManager."""
        manager = AssetManager(assets_path=temp_assets_with_mappings)

        path = manager.get_terrain_sprite_path("floor_stone")

        assert path is not None
        assert path.name == "rect_gray0.png"

    def test_decoration_sprite_path_tracks_missing(self, temp_assets_with_mappings):
        """Should track missing decorations."""
        manager = AssetManager(assets_path=temp_assets_with_mappings)

        # chest mapped but file missing
        path = manager.get_decoration_sprite_path("chest")

        assert path is None
        assert "decoration:chest" in manager.get_missing_assets()

    def test_item_sprite_path(self, temp_assets_with_mappings):
        """Should get item sprite path through AssetManager."""
        manager = AssetManager(assets_path=temp_assets_with_mappings)

        path = manager.get_item_sprite_path("longsword", "weapons")

        assert path is not None
        assert path.name == "long_sword1.png"

    def test_effect_sprite_path(self, temp_assets_with_mappings):
        """Should get effect sprite path through AssetManager."""
        manager = AssetManager(assets_path=temp_assets_with_mappings)

        path = manager.get_effect_sprite_path("damage_slash", "damage")

        assert path is not None
        assert path.name == "slash.png"


class TestCachingWithMappings:
    """Tests for caching behavior with mappings."""

    def test_caches_mapped_paths(self, temp_assets_with_mappings):
        """Should cache resolved mapped paths."""
        resolver = SpriteResolver(assets_path=temp_assets_with_mappings)

        resolver.get_monster_sprite_path("skeleton", "undead")
        resolver.get_monster_sprite_path("skeleton", "undead")

        # Should be cached after first call
        assert resolver.cache_size >= 1

    def test_clear_cache_clears_mapped(self, temp_assets_with_mappings):
        """Should clear cached mapped paths."""
        resolver = SpriteResolver(assets_path=temp_assets_with_mappings)

        resolver.get_monster_sprite_path("skeleton", "undead")
        resolver.clear_cache()

        assert resolver.cache_size == 0
