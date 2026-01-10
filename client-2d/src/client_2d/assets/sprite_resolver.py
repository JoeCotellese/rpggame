# ABOUTME: Sprite resolution system with hierarchical fallback for missing assets.
# ABOUTME: Supports category-based fallbacks (undead, beast, humanoid) for monsters.

"""Sprite resolver with hierarchical fallback system."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SpriteResolver:
    """Resolves sprite paths with hierarchical fallback.

    The sprite resolver finds the best available sprite for an entity,
    using a fallback hierarchy when specific sprites are unavailable:

    For monsters:
    1. Exact match: monsters/{type}/{creature_id}.png
    2. Category fallback: monsters/{type}/_fallback.png
    3. Generic fallback: monsters/_fallback_generic.png

    For characters:
    1. Class + race: characters/{class}_{race}.png
    2. Class only: characters/{class}.png
    3. Fallback: characters/_fallback_humanoid.png

    Attributes:
        assets_path: Base path to the assets directory
    """

    assets_path: Path
    _cache: dict[str, Optional[Path]] = field(default_factory=dict)

    def get_monster_sprite_path(
        self, creature_id: str, creature_type: str
    ) -> Optional[Path]:
        """Resolve sprite path for a monster with fallback.

        Args:
            creature_id: The creature identifier (e.g., "skeleton", "goblin")
            creature_type: The creature category (e.g., "undead", "beast")

        Returns:
            Path to the sprite file, or None if no sprite found
        """
        cache_key = f"monster:{creature_type}:{creature_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        sprites_path = self.assets_path / "sprites" / "monsters"

        # Try exact match first
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
        self, class_name: str, race: Optional[str] = None
    ) -> Optional[Path]:
        """Resolve sprite path for a character with fallback.

        Args:
            class_name: The character class (e.g., "fighter", "wizard")
            race: Optional race for race-specific sprites

        Returns:
            Path to the sprite file, or None if no sprite found
        """
        cache_key = f"character:{class_name}:{race or 'none'}"
        if cache_key in self._cache:
            return self._cache[cache_key]

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
    ) -> Optional[Path]:
        """Resolve sprite path for an item with fallback.

        Args:
            item_id: The item identifier (e.g., "longsword", "health_potion")
            item_category: The item category (e.g., "weapons", "consumables")

        Returns:
            Path to the sprite file, or None if no sprite found
        """
        cache_key = f"item:{item_category}:{item_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

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
    ) -> Optional[Path]:
        """Resolve sprite path for a visual effect.

        Args:
            effect_id: The effect identifier (e.g., "slash", "fire")
            effect_type: The effect category (e.g., "damage", "healing")

        Returns:
            Path to the sprite file, or None if no sprite found
        """
        cache_key = f"effect:{effect_type}:{effect_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

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

    def resolve_with_fallback(
        self,
        primary_path: Path,
        fallback_paths: list[Path],
    ) -> Optional[Path]:
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
