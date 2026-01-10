# ABOUTME: Core constants and enumerations for the 2D client.
# ABOUTME: Defines tile sizes, window dimensions, lighting states, and game modes.

"""Constants and configuration for the 2D graphical client."""

from enum import Enum, auto


# Display settings
TILE_SIZE = 32  # Pixels per tile
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720

# Map settings
MAP_WIDTH_TILES = 40  # Default map width in tiles
MAP_HEIGHT_TILES = 22  # Default map height in tiles

# D&D 5E standard light source radii (in tiles, assuming 5ft per tile)
# Torch: 20ft bright + 20ft dim = 4 tiles bright + 4 tiles dim
TORCH_BRIGHT_RADIUS = 4
TORCH_DIM_RADIUS = 4  # Additional radius beyond bright

# Lantern: 30ft bright + 30ft dim = 6 tiles bright + 6 tiles dim
LANTERN_BRIGHT_RADIUS = 6
LANTERN_DIM_RADIUS = 6

# Light cantrip: 20ft bright + 20ft dim
LIGHT_SPELL_BRIGHT_RADIUS = 4
LIGHT_SPELL_DIM_RADIUS = 4

# Darkvision range (typically 60ft = 12 tiles)
DARKVISION_RANGE = 12

# Animation settings
MOVEMENT_TWEEN_DURATION = 0.2  # Seconds for movement animation
DAMAGE_NUMBER_DURATION = 1.0  # Seconds for floating damage numbers


class LightingState(Enum):
    """Visibility states for fog of war tiles.

    These correspond to D&D 5E lighting rules:
    - UNEXPLORED: Never seen, completely black
    - DARK: Previously seen but not currently lit, dim memory
    - DIM: Partially illuminated (10-20ft from torch)
    - BRIGHT: Fully illuminated (0-10ft from torch)
    """

    UNEXPLORED = 0
    DARK = 1
    DIM = 2
    BRIGHT = 3


class Direction(Enum):
    """Cardinal directions for movement."""

    NORTH = auto()
    SOUTH = auto()
    EAST = auto()
    WEST = auto()

    @property
    def delta(self) -> tuple[int, int]:
        """Get the (dx, dy) movement delta for this direction."""
        deltas = {
            Direction.NORTH: (0, -1),
            Direction.SOUTH: (0, 1),
            Direction.EAST: (1, 0),
            Direction.WEST: (-1, 0),
        }
        return deltas[self]

    @property
    def opposite(self) -> "Direction":
        """Get the opposite direction."""
        opposites = {
            Direction.NORTH: Direction.SOUTH,
            Direction.SOUTH: Direction.NORTH,
            Direction.EAST: Direction.WEST,
            Direction.WEST: Direction.EAST,
        }
        return opposites[self]


class GameMode(Enum):
    """Current game mode affecting input handling and UI display."""

    EXPLORATION = auto()
    COMBAT = auto()
    DIALOGUE = auto()
    INVENTORY = auto()
    MENU = auto()


class Action(Enum):
    """Player actions mapped from keyboard input."""

    MOVE_NORTH = auto()
    MOVE_SOUTH = auto()
    MOVE_EAST = auto()
    MOVE_WEST = auto()
    INTERACT = auto()
    CONFIRM = auto()
    CANCEL = auto()
    INVENTORY = auto()
    CHARACTER = auto()
    NEXT_TARGET = auto()
    PREV_TARGET = auto()
    ATTACK = auto()
    SPELL = auto()
    ITEM = auto()
    WAIT = auto()
