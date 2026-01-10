# ABOUTME: Unit tests for the asset manager and sprite resolver.
# ABOUTME: Tests sprite fallback hierarchy and asset path resolution.

"""Tests for AssetManager and SpriteResolver."""

import tempfile
from pathlib import Path

import pytest
from client_2d.assets.asset_manager import AssetManager
from client_2d.assets.sprite_resolver import SpriteResolver


@pytest.fixture
def temp_assets_dir():
    """Create a temporary assets directory structure for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        assets_path = Path(tmpdir)

        # Create directory structure
        (assets_path / "sprites" / "monsters" / "undead").mkdir(parents=True)
        (assets_path / "sprites" / "monsters" / "beast").mkdir(parents=True)
        (assets_path / "sprites" / "monsters" / "humanoid").mkdir(parents=True)
        (assets_path / "sprites" / "characters").mkdir(parents=True)
        (assets_path / "sprites" / "items" / "weapons").mkdir(parents=True)
        (assets_path / "sprites" / "effects" / "damage").mkdir(parents=True)
        (assets_path / "tilesets").mkdir(parents=True)
        (assets_path / "maps" / "crypt").mkdir(parents=True)
        (assets_path / "ui").mkdir(parents=True)

        # Create some test sprite files
        # Exact match sprites
        (assets_path / "sprites" / "monsters" / "undead" / "skeleton.png").touch()
        (assets_path / "sprites" / "monsters" / "humanoid" / "goblin.png").touch()
        (assets_path / "sprites" / "characters" / "fighter.png").touch()
        (assets_path / "sprites" / "characters" / "wizard.png").touch()

        # Fallback sprites
        (assets_path / "sprites" / "monsters" / "undead" / "_fallback.png").touch()
        (assets_path / "sprites" / "monsters" / "_fallback_generic.png").touch()
        (assets_path / "sprites" / "characters" / "_fallback_humanoid.png").touch()

        # Tilesets and maps
        (assets_path / "tilesets" / "dungeon_basic.png").touch()
        (assets_path / "maps" / "crypt" / "entrance.tmx").touch()

        yield assets_path


class TestSpriteResolverMonsters:
    """Tests for monster sprite resolution."""

    def test_exact_match_found(self, temp_assets_dir):
        """Should return exact sprite path when it exists."""
        resolver = SpriteResolver(assets_path=temp_assets_dir)

        path = resolver.get_monster_sprite_path("skeleton", "undead")

        assert path is not None
        assert path.name == "skeleton.png"

    def test_category_fallback_when_no_exact_match(self, temp_assets_dir):
        """Should return category fallback when no exact match."""
        resolver = SpriteResolver(assets_path=temp_assets_dir)

        # zombie.png doesn't exist, but undead/_fallback.png does
        path = resolver.get_monster_sprite_path("zombie", "undead")

        assert path is not None
        assert path.name == "_fallback.png"
        assert "undead" in str(path)

    def test_generic_fallback_when_no_category_fallback(self, temp_assets_dir):
        """Should return generic fallback when no category fallback."""
        resolver = SpriteResolver(assets_path=temp_assets_dir)

        # beast category has no _fallback.png
        path = resolver.get_monster_sprite_path("wolf", "beast")

        assert path is not None
        assert path.name == "_fallback_generic.png"

    def test_none_when_no_fallback_exists(self, temp_assets_dir):
        """Should return None when no sprite or fallback exists."""
        # Remove the generic fallback
        (temp_assets_dir / "sprites" / "monsters" / "_fallback_generic.png").unlink()

        resolver = SpriteResolver(assets_path=temp_assets_dir)

        path = resolver.get_monster_sprite_path("wolf", "beast")

        assert path is None

    def test_caches_resolved_paths(self, temp_assets_dir):
        """Should cache resolved paths for performance."""
        resolver = SpriteResolver(assets_path=temp_assets_dir)

        # First call
        resolver.get_monster_sprite_path("skeleton", "undead")

        # Second call should use cache
        assert resolver.cache_size > 0

    def test_clear_cache(self, temp_assets_dir):
        """Should be able to clear the cache."""
        resolver = SpriteResolver(assets_path=temp_assets_dir)

        resolver.get_monster_sprite_path("skeleton", "undead")
        resolver.clear_cache()

        assert resolver.cache_size == 0


class TestSpriteResolverCharacters:
    """Tests for character sprite resolution."""

    def test_class_sprite_found(self, temp_assets_dir):
        """Should return class sprite when it exists."""
        resolver = SpriteResolver(assets_path=temp_assets_dir)

        path = resolver.get_character_sprite_path("fighter")

        assert path is not None
        assert path.name == "fighter.png"

    def test_class_race_combination(self, temp_assets_dir):
        """Should try class_race combination first."""
        resolver = SpriteResolver(assets_path=temp_assets_dir)
        # Create a race-specific sprite
        (temp_assets_dir / "sprites" / "characters" / "fighter_dwarf.png").touch()

        path = resolver.get_character_sprite_path("fighter", race="dwarf")

        assert path is not None
        assert path.name == "fighter_dwarf.png"

    def test_falls_back_to_class_only(self, temp_assets_dir):
        """Should fall back to class-only sprite when race combo missing."""
        resolver = SpriteResolver(assets_path=temp_assets_dir)

        # No fighter_elf.png exists, should fall back to fighter.png
        path = resolver.get_character_sprite_path("fighter", race="elf")

        assert path is not None
        assert path.name == "fighter.png"

    def test_falls_back_to_humanoid(self, temp_assets_dir):
        """Should fall back to humanoid when class missing."""
        resolver = SpriteResolver(assets_path=temp_assets_dir)

        # No paladin.png exists
        path = resolver.get_character_sprite_path("paladin")

        assert path is not None
        assert path.name == "_fallback_humanoid.png"


class TestAssetManager:
    """Tests for the AssetManager."""

    def test_get_monster_sprite_path(self, temp_assets_dir):
        """Should delegate to sprite resolver."""
        manager = AssetManager(assets_path=temp_assets_dir)

        path = manager.get_monster_sprite_path("skeleton", "undead")

        assert path is not None
        assert path.name == "skeleton.png"

    def test_tracks_missing_assets(self, temp_assets_dir):
        """Should track assets that weren't found."""
        # Remove generic fallback so wolf can't be found
        (temp_assets_dir / "sprites" / "monsters" / "_fallback_generic.png").unlink()

        manager = AssetManager(assets_path=temp_assets_dir)

        manager.get_monster_sprite_path("wolf", "beast")

        missing = manager.get_missing_assets()
        assert "monster:beast:wolf" in missing

    def test_get_tileset_path(self, temp_assets_dir):
        """Should return tileset path when it exists."""
        manager = AssetManager(assets_path=temp_assets_dir)

        path = manager.get_tileset_path("dungeon_basic")

        assert path is not None
        assert path.name == "dungeon_basic.png"

    def test_get_tileset_tracks_missing(self, temp_assets_dir):
        """Should track missing tilesets."""
        manager = AssetManager(assets_path=temp_assets_dir)

        path = manager.get_tileset_path("nonexistent")

        assert path is None
        assert "tileset:nonexistent" in manager.get_missing_assets()

    def test_get_map_path(self, temp_assets_dir):
        """Should return map path when it exists."""
        manager = AssetManager(assets_path=temp_assets_dir)

        path = manager.get_map_path("crypt", "entrance")

        assert path is not None
        assert path.name == "entrance.tmx"

    def test_validate_assets(self, temp_assets_dir):
        """Should validate required directories exist."""
        manager = AssetManager(assets_path=temp_assets_dir)

        validation = manager.validate_assets()

        assert validation["sprites"] is True
        assert validation["sprites/characters"] is True
        assert validation["sprites/monsters"] is True
        assert validation["tilesets"] is True
        assert validation["maps"] is True

    def test_clear_missing_assets(self, temp_assets_dir):
        """Should be able to clear missing assets tracker."""
        manager = AssetManager(assets_path=temp_assets_dir)
        manager.get_tileset_path("nonexistent")

        manager.clear_missing_assets()

        assert len(manager.get_missing_assets()) == 0

    def test_clear_cache(self, temp_assets_dir):
        """Should be able to clear all caches."""
        manager = AssetManager(assets_path=temp_assets_dir)
        manager.get_monster_sprite_path("skeleton", "undead")

        manager.clear_cache()

        assert manager.sprite_resolver.cache_size == 0


class TestSpriteResolverGeneric:
    """Tests for generic fallback resolution."""

    def test_resolve_with_fallback_primary_exists(self, temp_assets_dir):
        """Should return primary path when it exists."""
        resolver = SpriteResolver(assets_path=temp_assets_dir)

        primary = temp_assets_dir / "sprites" / "monsters" / "undead" / "skeleton.png"
        fallbacks = [
            temp_assets_dir / "sprites" / "monsters" / "undead" / "_fallback.png"
        ]

        path = resolver.resolve_with_fallback(primary, fallbacks)

        assert path == primary

    def test_resolve_with_fallback_uses_first_fallback(self, temp_assets_dir):
        """Should return first existing fallback when primary missing."""
        resolver = SpriteResolver(assets_path=temp_assets_dir)

        primary = temp_assets_dir / "sprites" / "monsters" / "undead" / "ghost.png"
        fallbacks = [
            temp_assets_dir / "sprites" / "monsters" / "undead" / "_fallback.png",
            temp_assets_dir / "sprites" / "monsters" / "_fallback_generic.png",
        ]

        path = resolver.resolve_with_fallback(primary, fallbacks)

        assert path.name == "_fallback.png"

    def test_resolve_with_fallback_returns_none(self, temp_assets_dir):
        """Should return None when nothing exists."""
        resolver = SpriteResolver(assets_path=temp_assets_dir)

        primary = temp_assets_dir / "nonexistent" / "sprite.png"
        fallbacks = [
            temp_assets_dir / "nonexistent" / "fallback1.png",
            temp_assets_dir / "nonexistent" / "fallback2.png",
        ]

        path = resolver.resolve_with_fallback(primary, fallbacks)

        assert path is None
