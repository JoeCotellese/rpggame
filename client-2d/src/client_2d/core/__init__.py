# ABOUTME: Core module containing game constants, configuration, and main game classes.
# ABOUTME: Provides the central coordination for the 2D client systems.

"""Core game components for the 2D client."""

from client_2d.core.constants import (
    TILE_SIZE,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    LightingState,
    Direction,
    GameMode,
)

__all__ = [
    "TILE_SIZE",
    "WINDOW_WIDTH",
    "WINDOW_HEIGHT",
    "LightingState",
    "Direction",
    "GameMode",
]
