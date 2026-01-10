# ABOUTME: Sprite resolution system with hierarchical fallback for missing assets.
# ABOUTME: Supports tile mappings (Stone Soup) and category-based fallbacks.

"""Sprite resolver with hierarchical fallback system."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SpriteResolver:
    """Resolves sprite paths with tile mappings and hierarchical fallback.

    The sprite resolver finds the best available sprite for an entity using:
    1. Tile mappings (from tile_mappings.json) pointing to Stone Soup assets
    2. Fallback hierarchy when specific sprites are unavailable

    Resolution order for monsters:
    1. Tile mapping: stonesoup/{mapped_path}
    2. Exact match: sprites/monsters/{type}/{creature_id}.png
    3. Category fallback: sprites/monsters/{type}/_fallback.png
    4. Generic fallback: sprites/monsters/_fallback_generic.png

    Resolution order for characters:
    1. Tile mapping: stonesoup/{mapped_path}
    2. Class + race: sprites/characters/{class}_{race}.png
    3. Class only: sprites/characters/{class}.png
    4. Fallback: sprites/characters/_fallback_humanoid.png

    Attributes:
        assets_path: Base path to the assets directory
    """

    assets_path: Path
    _cache: dict[str, Path | None] = field(default_factory=dict)
    _mappings: dict[str, dict[str, str]] = field(default_factory=dict)
    _mappings_loaded: bool = field(default=False)

    def __post_init__(self) -> None:
        """Load tile mappings on initialization."""
        self.load_mappings()

    def load_mappings(self, mappings_file: Path | None = None) -> bool:
        """Load tile mappings from JSON file.

        Args:
            mappings_file: Path to mappings JSON, defaults to assets/tile_mappings.json

        Returns:
            True if mappings loaded successfully, False otherwise
        """
        if mappings_file is None:
            mappings_file = self.assets_path / "tile_mappings.json"

        if not mappings_file.exists():
            self._mappings = {}
            self._mappings_loaded = False
            return False

        try:
            with open(mappings_file) as f:
                data: dict[str, Any] = json.load(f)

            # Extract mappings, ignoring _meta key
            self._mappings = {
                k: v for k, v in data.items() if not k.startswith("_")
            }
            self._mappings_loaded = True
            return True
        except (json.JSONDecodeError, OSError):
            self._mappings = {}
            self._mappings_loaded = False
            return False

    def _get_mapped_path(self, category: str, entity_id: str) -> Path | None:
        """Look up a mapped sprite path from tile_mappings.json.

        Args:
            category: Mapping category (monsters, characters, items, etc.)
            entity_id: Entity identifier

        Returns:
            Path to mapped sprite if exists, None otherwise
        """
        if not self._mappings_loaded:
            return None

        category_mappings = self._mappings.get(category, {})
        mapped_path = category_mappings.get(entity_id)

        if mapped_path:
            full_path = self.assets_path / "stonesoup" / mapped_path
            if full_path.exists():
                return full_path

        return None

    def get_monster_sprite_path(
        self, creature_id: str, creature_type: str
    ) -> Path | None:
        """Resolve sprite path for a monster with fallback.

        Resolution order:
        1. Tile mapping (Stone Soup)
        2. Exact match in sprites/monsters
        3. Category fallback
        4. Generic fallback

        Args:
            creature_id: The creature identifier (e.g., "skeleton", "goblin")
            creature_type: The creature category (e.g., "undead", "beast")

        Returns:
            Path to the sprite file, or None if no sprite found
        """
        cache_key = f"monster:{creature_type}:{creature_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try tile mapping first (Stone Soup)
        mapped_path = self._get_mapped_path("monsters", creature_id)
        if mapped_path:
            self._cache[cache_key] = mapped_path
            return mapped_path

        sprites_path = self.assets_path / "sprites" / "monsters"

        # Try exact match
        exact_path = sprites_path / creature_type / f"{creature_id}.png"
        if exact_path.exists():
            self._cache[cache_key] = exact_path
            return exact_path

        # Try category fallback
        category_fallback = sprites_path / creature_type / "_fallback.png"
        if category_fallback.exists():
            self._cache[cache_key] = category_fallback
            return category_fallback

        # Try generic fallback
        generic_fallback = sprites_path / "_fallback_generic.png"
        if generic_fallback.exists():
            self._cache[cache_key] = generic_fallback
            return generic_fallback

        # No sprite found
        self._cache[cache_key] = None
        return None

    def get_character_sprite_path(
        self, class_name: str, race: str | None = None
    ) -> Path | None:
        """Resolve sprite path for a character with fallback.

        Resolution order:
        1. Tile mapping (Stone Soup)
        2. Class + race combination
        3. Class only
        4. Humanoid fallback

        Args:
            class_name: The character class (e.g., "fighter", "wizard")
            race: Optional race for race-specific sprites

        Returns:
            Path to the sprite file, or None if no sprite found
        """
        cache_key = f"character:{class_name}:{race or 'none'}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try tile mapping first (Stone Soup)
        mapped_path = self._get_mapped_path("characters", class_name)
        if mapped_path:
            self._cache[cache_key] = mapped_path
            return mapped_path

        sprites_path = self.assets_path / "sprites" / "characters"

        # Try class + race combination
        if race:
            race_path = sprites_path / f"{class_name}_{race}.png"
            if race_path.exists():
                self._cache[cache_key] = race_path
                return race_path

        # Try class only
        class_path = sprites_path / f"{class_name}.png"
        if class_path.exists():
            self._cache[cache_key] = class_path
            return class_path

        # Try humanoid fallback
        fallback_path = sprites_path / "_fallback_humanoid.png"
        if fallback_path.exists():
            self._cache[cache_key] = fallback_path
            return fallback_path

        # No sprite found
        self._cache[cache_key] = None
        return None

    def get_item_sprite_path(
        self, item_id: str, item_category: str
    ) -> Path | None:
        """Resolve sprite path for an item with fallback.

        Resolution order:
        1. Tile mapping (Stone Soup)
        2. Exact match in sprites/items
        3. Category fallback
        4. Generic fallback

        Args:
            item_id: The item identifier (e.g., "longsword", "health_potion")
            item_category: The item category (e.g., "weapons", "consumables")

        Returns:
            Path to the sprite file, or None if no sprite found
        """
        cache_key = f"item:{item_category}:{item_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try tile mapping first (Stone Soup)
        mapped_path = self._get_mapped_path("items", item_id)
        if mapped_path:
            self._cache[cache_key] = mapped_path
            return mapped_path

        sprites_path = self.assets_path / "sprites" / "items"

        # Try exact match
        exact_path = sprites_path / item_category / f"{item_id}.png"
        if exact_path.exists():
            self._cache[cache_key] = exact_path
            return exact_path

        # Try category fallback
        category_fallback = sprites_path / item_category / "_fallback.png"
        if category_fallback.exists():
            self._cache[cache_key] = category_fallback
            return category_fallback

        # Try generic fallback
        generic_fallback = sprites_path / "items" / "_fallback.png"
        if generic_fallback.exists():
            self._cache[cache_key] = generic_fallback
            return generic_fallback

        self._cache[cache_key] = None
        return None

    def get_effect_sprite_path(
        self, effect_id: str, effect_type: str
    ) -> Path | None:
        """Resolve sprite path for a visual effect.

        Resolution order:
        1. Tile mapping (Stone Soup)
        2. Exact match in sprites/effects
        3. Category fallback

        Args:
            effect_id: The effect identifier (e.g., "slash", "fire")
            effect_type: The effect category (e.g., "damage", "healing")

        Returns:
            Path to the sprite file, or None if no sprite found
        """
        cache_key = f"effect:{effect_type}:{effect_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try tile mapping first (Stone Soup)
        mapped_path = self._get_mapped_path("effects", effect_id)
        if mapped_path:
            self._cache[cache_key] = mapped_path
            return mapped_path

        sprites_path = self.assets_path / "sprites" / "effects"

        # Try exact match
        exact_path = sprites_path / effect_type / f"{effect_id}.png"
        if exact_path.exists():
            self._cache[cache_key] = exact_path
            return exact_path

        # Try category fallback
        category_fallback = sprites_path / effect_type / "_fallback.png"
        if category_fallback.exists():
            self._cache[cache_key] = category_fallback
            return category_fallback

        self._cache[cache_key] = None
        return None

    def get_terrain_sprite_path(self, terrain_id: str) -> Path | None:
        """Resolve sprite path for terrain tiles.

        Resolution order:
        1. Tile mapping (Stone Soup)
        2. Returns None (no fallback for terrain)

        Args:
            terrain_id: The terrain identifier (e.g., "floor_stone", "wall_brick")

        Returns:
            Path to the sprite file, or None if no sprite found
        """
        cache_key = f"terrain:{terrain_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try tile mapping (Stone Soup)
        mapped_path = self._get_mapped_path("terrain", terrain_id)
        if mapped_path:
            self._cache[cache_key] = mapped_path
            return mapped_path

        self._cache[cache_key] = None
        return None

    def get_decoration_sprite_path(self, decoration_id: str) -> Path | None:
        """Resolve sprite path for decorative elements.

        Resolution order:
        1. Tile mapping (Stone Soup)
        2. Returns None (no fallback for decorations)

        Args:
            decoration_id: The decoration identifier (e.g., "chest", "altar")

        Returns:
            Path to the sprite file, or None if no sprite found
        """
        cache_key = f"decoration:{decoration_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try tile mapping (Stone Soup)
        mapped_path = self._get_mapped_path("decorations", decoration_id)
        if mapped_path:
            self._cache[cache_key] = mapped_path
            return mapped_path

        self._cache[cache_key] = None
        return None

    def get_ui_sprite_path(self, ui_element_id: str) -> Path | None:
        """Resolve sprite path for UI elements.

        Resolution order:
        1. Tile mapping (Stone Soup)
        2. Local ui directory
        3. Returns None

        Args:
            ui_element_id: The UI element identifier (e.g., "cursor_select")

        Returns:
            Path to the sprite file, or None if no sprite found
        """
        cache_key = f"ui:{ui_element_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try tile mapping first (Stone Soup)
        mapped_path = self._get_mapped_path("ui", ui_element_id)
        if mapped_path:
            self._cache[cache_key] = mapped_path
            return mapped_path

        # Try local ui directory
        ui_path = self.assets_path / "ui" / f"{ui_element_id}.png"
        if ui_path.exists():
            self._cache[cache_key] = ui_path
            return ui_path

        self._cache[cache_key] = None
        return None

    def resolve_with_fallback(
        self,
        primary_path: Path,
        fallback_paths: list[Path],
    ) -> Path | None:
        """Generic fallback resolution for any sprite type.

        Args:
            primary_path: The preferred sprite path
            fallback_paths: List of fallback paths in priority order

        Returns:
            First existing path, or None if none exist
        """
        if primary_path.exists():
            return primary_path

        for fallback in fallback_paths:
            if fallback.exists():
                return fallback

        return None

    def clear_cache(self) -> None:
        """Clear the sprite path cache."""
        self._cache.clear()

    @property
    def cache_size(self) -> int:
        """Number of cached sprite paths."""
        return len(self._cache)

    @property
    def has_mappings(self) -> bool:
        """Whether tile mappings are loaded."""
        return self._mappings_loaded

    @property
    def mapping_categories(self) -> list[str]:
        """List of categories with mappings loaded."""
        return list(self._mappings.keys())
