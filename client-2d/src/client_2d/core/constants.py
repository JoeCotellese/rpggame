# ABOUTME: Core constants and enumerations for the 2D client.
# ABOUTME: Defines tile sizes, window dimensions, lighting states, and game modes.

"""Constants and configuration for the 2D graphical client."""

from enum import Enum, auto

# Display settings
TILE_SIZE = 32  # Pixels per tile
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720

# UI Layout (percentage-based for flexibility)
VIEWPORT_WIDTH_PCT = 0.70      # Game viewport takes 70% of window width
CONTEXT_PANEL_WIDTH_PCT = 0.30  # Context panel takes 30% of window width
NARRATIVE_HEIGHT_PCT = 0.25     # Narrative area takes 25% of window height
GAME_AREA_HEIGHT_PCT = 0.75     # Game viewport + context panel take 75% of height

# Font sizes (in points)
FONT_SIZE_TITLE = 18      # Panel headers, modal titles
FONT_SIZE_BODY = 14       # Narrative text, item names, descriptions
FONT_SIZE_SMALL = 12      # Stats, labels, secondary info
FONT_SIZE_TINY = 10       # Tooltips, fine print

# UI spacing (in pixels)
UI_PADDING = 8            # Inside panels
UI_MARGIN = 4             # Between elements
UI_BORDER_WIDTH = 2       # Panel border thickness

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


# =============================================================================
# UI Color Palette (Earthy Theme)
# =============================================================================
# All colors defined as (R, G, B) tuples for use with Arcade.
# Single source of truth - change colors here to update entire UI.

class UIColors:
    """Centralized color palette for the 2D client UI.

    Earthy theme inspired by worn leather, parchment, and dungeon stone.
    """

    # Background colors
    BACKGROUND = (28, 26, 23)        # #1c1a17 - Deep earth
    PANEL_BG = (46, 42, 36)          # #2e2a24 - Worn leather
    PANEL_BG_DARK = (35, 32, 28)     # #23201c - Darker panel variant

    # Border and frame colors
    BORDER = (92, 77, 60)            # #5c4d3c - Wood grain
    BORDER_HIGHLIGHT = (120, 100, 78)  # #78644e - Lighter wood

    # Text colors
    TEXT = (212, 200, 176)           # #d4c8b0 - Parchment
    TEXT_DIM = (150, 142, 125)       # #968e7d - Faded parchment
    TEXT_HIGHLIGHT = (255, 240, 200)  # #fff0c8 - Bright parchment
    TEXT_DISABLED = (100, 95, 85)    # #645f55 - Aged/disabled

    # Accent colors
    HIGHLIGHT = (201, 162, 39)       # #c9a227 - Torchlight gold
    SELECTION = (80, 70, 55)         # #504637 - Selected item bg

    # HP bar colors
    HP_FULL = (85, 170, 119)         # #5aa77 - Forest green
    HP_MEDIUM = (170, 170, 85)       # #aaaa55 - Caution yellow-green
    HP_LOW = (187, 136, 85)          # #bb8855 - Autumn orange
    HP_CRITICAL = (153, 51, 51)      # #993333 - Dark crimson
    HP_BG = (40, 35, 30)             # #28231e - HP bar background

    # Combat/status colors
    DAMAGE = (200, 80, 80)           # #c85050 - Damage numbers
    HEALING = (80, 200, 120)         # #50c878 - Healing numbers
    BUFF = (100, 150, 220)           # #6496dc - Buff effects
    DEBUFF = (180, 100, 180)         # #b464b4 - Debuff effects

    # Lighting overlay tints (for fog of war)
    FOG_UNEXPLORED = (0, 0, 0)       # Pure black
    FOG_DARK = (60, 55, 50)          # Dark memory tint
    FOG_DIM = (140, 135, 125)        # Dim light tint
