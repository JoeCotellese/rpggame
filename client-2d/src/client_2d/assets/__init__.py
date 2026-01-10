# ABOUTME: Asset management module for loading and caching game assets.
# ABOUTME: Provides sprite resolution with hierarchical fallback system.

"""Asset management for sprites, tilesets, and maps."""

from client_2d.assets.asset_manager import AssetManager
from client_2d.assets.sprite_resolver import SpriteResolver

__all__ = ["AssetManager", "SpriteResolver"]
