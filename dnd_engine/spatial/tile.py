# ABOUTME: Tile types and tile data for 2D dungeon grid
# ABOUTME: Defines walkability, visibility blocking, and interactive properties

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TileType(Enum):
    """
    Standard tile types for dungeon maps.

    Each type has default properties for walkability and sight blocking.
    """

    FLOOR = "floor"
    WALL = "wall"
    DOOR_CLOSED = "door_closed"
    DOOR_OPEN = "door_open"
    STAIRS_UP = "stairs_up"
    STAIRS_DOWN = "stairs_down"
    WATER_SHALLOW = "water_shallow"
    WATER_DEEP = "water_deep"
    PIT = "pit"
    TRAP = "trap"
    CHEST = "chest"
    ALTAR = "altar"
    PILLAR = "pillar"

    @property
    def default_walkable(self) -> bool:
        """Default walkability for this tile type."""
        non_walkable = {
            TileType.WALL,
            TileType.DOOR_CLOSED,
            TileType.WATER_DEEP,
            TileType.PIT,
            TileType.PILLAR,
        }
        return self not in non_walkable

    @property
    def default_blocks_sight(self) -> bool:
        """Default sight-blocking for this tile type."""
        blocks_sight = {
            TileType.WALL,
            TileType.DOOR_CLOSED,
            TileType.PILLAR,
        }
        return self in blocks_sight

    @property
    def default_char(self) -> str:
        """Default ASCII character for rendering."""
        char_map = {
            TileType.FLOOR: ".",
            TileType.WALL: "#",
            TileType.DOOR_CLOSED: "+",
            TileType.DOOR_OPEN: "/",
            TileType.STAIRS_UP: "<",
            TileType.STAIRS_DOWN: ">",
            TileType.WATER_SHALLOW: "~",
            TileType.WATER_DEEP: "~",
            TileType.PIT: "^",
            TileType.TRAP: "^",
            TileType.CHEST: "$",
            TileType.ALTAR: "_",
            TileType.PILLAR: "O",
        }
        return char_map.get(self, "?")

    @property
    def is_interactive(self) -> bool:
        """Check if this tile type can be interacted with."""
        interactive = {
            TileType.DOOR_CLOSED,
            TileType.DOOR_OPEN,
            TileType.STAIRS_UP,
            TileType.STAIRS_DOWN,
            TileType.CHEST,
            TileType.ALTAR,
            TileType.TRAP,
        }
        return self in interactive


class VisibilityState(Enum):
    """Visibility state for fog of war."""

    UNEXPLORED = "unexplored"  # Never seen
    EXPLORED = "explored"  # Seen before but not currently visible
    VISIBLE = "visible"  # Currently in line of sight


@dataclass
class Tile:
    """
    A single tile in the dungeon grid.

    Tiles have a type that determines default properties, but these
    can be overridden for special cases (e.g., a magically locked door
    that blocks movement but not sight).
    """

    tile_type: TileType = TileType.FLOOR
    walkable: bool | None = None  # None = use default from type
    blocks_sight: bool | None = None  # None = use default from type
    visibility: VisibilityState = VisibilityState.UNEXPLORED

    # Entity/item tracking
    entity_id: str | None = None  # ID of creature/character on this tile
    item_ids: list[str] = field(default_factory=list)  # Items on this tile

    # Interactive properties
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_walkable(self) -> bool:
        """Check if this tile can be walked on."""
        if self.walkable is not None:
            return self.walkable
        return self.tile_type.default_walkable

    @property
    def does_block_sight(self) -> bool:
        """Check if this tile blocks line of sight."""
        if self.blocks_sight is not None:
            return self.blocks_sight
        return self.tile_type.default_blocks_sight

    @property
    def is_occupied(self) -> bool:
        """Check if an entity is on this tile."""
        return self.entity_id is not None

    @property
    def has_items(self) -> bool:
        """Check if there are items on this tile."""
        return len(self.item_ids) > 0

    @property
    def char(self) -> str:
        """Get the ASCII character for rendering this tile."""
        return self.tile_type.default_char

    @property
    def is_interactive(self) -> bool:
        """Check if this tile can be interacted with."""
        return self.tile_type.is_interactive

    def set_visible(self) -> None:
        """Mark tile as currently visible (also marks as explored)."""
        self.visibility = VisibilityState.VISIBLE

    def set_explored(self) -> None:
        """Mark tile as explored but not currently visible."""
        if self.visibility == VisibilityState.VISIBLE:
            self.visibility = VisibilityState.EXPLORED

    def is_visible(self) -> bool:
        """Check if tile is currently visible."""
        return self.visibility == VisibilityState.VISIBLE

    def is_explored(self) -> bool:
        """Check if tile has been explored (seen at least once)."""
        return self.visibility in (VisibilityState.VISIBLE, VisibilityState.EXPLORED)

    def open_door(self) -> bool:
        """Attempt to open a closed door. Returns True if successful."""
        if self.tile_type == TileType.DOOR_CLOSED:
            self.tile_type = TileType.DOOR_OPEN
            return True
        return False

    def close_door(self) -> bool:
        """Attempt to close an open door. Returns True if successful."""
        if self.tile_type == TileType.DOOR_OPEN:
            self.tile_type = TileType.DOOR_CLOSED
            return True
        return False

    def copy(self) -> Tile:
        """Create a copy of this tile."""
        return Tile(
            tile_type=self.tile_type,
            walkable=self.walkable,
            blocks_sight=self.blocks_sight,
            visibility=self.visibility,
            entity_id=self.entity_id,
            item_ids=list(self.item_ids),
            metadata=dict(self.metadata),
        )
