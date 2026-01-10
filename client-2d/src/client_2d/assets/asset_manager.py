# ABOUTME: Central asset manager for loading and caching all game assets.
# ABOUTME: Integrates sprite resolver and provides texture loading interface.

"""Asset manager for loading and caching game assets."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from client_2d.assets.sprite_resolver import SpriteResolver


@dataclass
class AssetManager:
    """Central manager for all game assets.

    The asset manager:
    1. Provides a unified interface for loading sprites, tilesets, maps
    2. Uses SpriteResolver for fallback-based sprite resolution
    3. Caches loaded textures to avoid redundant disk reads
    4. Reports missing assets for debugging

    For Phase 1, this operates without the Arcade library dependency
    by tracking paths and metadata. The actual texture loading is
    deferred to when Arcade is initialized.

    Attributes:
        assets_path: Base path to the assets directory
    """

    assets_path: Path
    _sprite_resolver: SpriteResolver = field(init=False)
    _texture_cache: dict[str, Any] = field(default_factory=dict)
    _missing_assets: set[str] = field(default_factory=set)

    def __post_init__(self):
        """Initialize the sprite resolver."""
        self._sprite_resolver = SpriteResolver(self.assets_path)

    def get_monster_sprite_path(
        self, creature_id: str, creature_type: str
    ) -> Path | None:
        """Get the sprite path for a monster.

        Args:
            creature_id: The creature identifier
            creature_type: The creature category

        Returns:
            Path to sprite file, or None if not found
        """
        path = self._sprite_resolver.get_monster_sprite_path(
            creature_id, creature_type
        )
        if path is None:
            self._missing_assets.add(f"monster:{creature_type}:{creature_id}")
        return path

    def get_character_sprite_path(
        self, class_name: str, race: str | None = None
    ) -> Path | None:
        """Get the sprite path for a character.

        Args:
            class_name: The character class
            race: Optional race for race-specific sprites

        Returns:
            Path to sprite file, or None if not found
        """
        path = self._sprite_resolver.get_character_sprite_path(
            class_name, race
        )
        if path is None:
            self._missing_assets.add(
                f"character:{class_name}:{race or 'none'}"
            )
        return path

    def get_tileset_path(self, tileset_name: str) -> Path | None:
        """Get the path for a tileset.

        Args:
            tileset_name: The tileset identifier

        Returns:
            Path to tileset file, or None if not found
        """
        tileset_path = self.assets_path / "tilesets" / f"{tileset_name}.png"
        if tileset_path.exists():
            return tileset_path
        self._missing_assets.add(f"tileset:{tileset_name}")
        return None

    def get_map_path(self, dungeon_id: str, room_id: str) -> Path | None:
        """Get the path for a room's tilemap.

        Args:
            dungeon_id: The dungeon identifier
            room_id: The room identifier

        Returns:
            Path to .tmx file, or None if not found
        """
        map_path = self.assets_path / "maps" / dungeon_id / f"{room_id}.tmx"
        if map_path.exists():
            return map_path

        # Try without dungeon prefix (flat structure)
        flat_path = self.assets_path / "maps" / f"{room_id}.tmx"
        if flat_path.exists():
            return flat_path

        self._missing_assets.add(f"map:{dungeon_id}:{room_id}")
        return None

    def get_ui_sprite_path(self, ui_element: str) -> Path | None:
        """Get the path for a UI sprite element.

        Args:
            ui_element: The UI element identifier

        Returns:
            Path to sprite file, or None if not found
        """
        path = self._sprite_resolver.get_ui_sprite_path(ui_element)
        if path is None:
            self._missing_assets.add(f"ui:{ui_element}")
        return path

    def get_item_sprite_path(
        self, item_id: str, item_category: str
    ) -> Path | None:
        """Get the sprite path for an item.

        Args:
            item_id: The item identifier (e.g., "longsword")
            item_category: The item category (e.g., "weapons")

        Returns:
            Path to sprite file, or None if not found
        """
        path = self._sprite_resolver.get_item_sprite_path(item_id, item_category)
        if path is None:
            self._missing_assets.add(f"item:{item_category}:{item_id}")
        return path

    def get_effect_sprite_path(
        self, effect_id: str, effect_type: str
    ) -> Path | None:
        """Get the sprite path for a visual effect.

        Args:
            effect_id: The effect identifier (e.g., "slash")
            effect_type: The effect category (e.g., "damage")

        Returns:
            Path to sprite file, or None if not found
        """
        path = self._sprite_resolver.get_effect_sprite_path(effect_id, effect_type)
        if path is None:
            self._missing_assets.add(f"effect:{effect_type}:{effect_id}")
        return path

    def get_terrain_sprite_path(self, terrain_id: str) -> Path | None:
        """Get the sprite path for a terrain tile.

        Args:
            terrain_id: The terrain identifier (e.g., "floor_stone", "wall_brick")

        Returns:
            Path to sprite file, or None if not found
        """
        path = self._sprite_resolver.get_terrain_sprite_path(terrain_id)
        if path is None:
            self._missing_assets.add(f"terrain:{terrain_id}")
        return path

    def get_decoration_sprite_path(self, decoration_id: str) -> Path | None:
        """Get the sprite path for a decorative element.

        Args:
            decoration_id: The decoration identifier (e.g., "chest", "altar")

        Returns:
            Path to sprite file, or None if not found
        """
        path = self._sprite_resolver.get_decoration_sprite_path(decoration_id)
        if path is None:
            self._missing_assets.add(f"decoration:{decoration_id}")
        return path

    def get_missing_assets(self) -> set[str]:
        """Get the set of assets that were requested but not found.

        Returns:
            Set of missing asset identifiers
        """
        return self._missing_assets.copy()

    def clear_missing_assets(self) -> None:
        """Clear the missing assets tracker."""
        self._missing_assets.clear()

    def clear_cache(self) -> None:
        """Clear all cached assets."""
        self._texture_cache.clear()
        self._sprite_resolver.clear_cache()

    @property
    def sprite_resolver(self) -> SpriteResolver:
        """Access the underlying sprite resolver."""
        return self._sprite_resolver

    def validate_assets(self) -> dict[str, bool]:
        """Validate that required asset directories exist.

        Returns:
            Dict mapping asset types to their existence status
        """
        required_dirs = {
            "sprites": self.assets_path / "sprites",
            "sprites/characters": self.assets_path / "sprites" / "characters",
            "sprites/monsters": self.assets_path / "sprites" / "monsters",
            "tilesets": self.assets_path / "tilesets",
            "maps": self.assets_path / "maps",
            "ui": self.assets_path / "ui",
            "stonesoup": self.assets_path / "stonesoup",
            "tile_mappings": self.assets_path / "tile_mappings.json",
        }

        return {name: path.exists() for name, path in required_dirs.items()}

    @property
    def has_stonesoup_tiles(self) -> bool:
        """Check if Stone Soup tiles are available."""
        return self._sprite_resolver.has_mappings
