# ABOUTME: TileMap class for 2D dungeon grid management
# ABOUTME: Handles entity positioning, movement, collision detection, and grid operations

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterator

from dnd_engine.spatial.position import Direction, Position
from dnd_engine.spatial.tile import Tile, TileType, VisibilityState

if TYPE_CHECKING:
    from dnd_engine.core.creature import Creature

logger = logging.getLogger(__name__)


@dataclass
class EntityInfo:
    """Information about an entity on the map."""

    entity_id: str
    position: Position
    display_char: str = "@"
    display_name: str = ""
    is_player: bool = False
    blocks_movement: bool = True


@dataclass
class MoveResult:
    """Result of a movement attempt."""

    success: bool
    new_position: Position | None = None
    blocked_by: str | None = None  # "wall", "entity", "bounds", "door"
    message: str = ""


@dataclass
class TileMap:
    """
    2D tile-based dungeon map with entity tracking.

    Manages the grid of tiles, entity positions, and provides methods
    for movement, collision detection, and spatial queries.
    """

    width: int
    height: int
    name: str = "Unknown"
    tiles: list[list[Tile]] = field(default_factory=list)
    entities: dict[str, EntityInfo] = field(default_factory=dict)

    # Map connections to other maps
    connections: dict[str, dict] = field(default_factory=dict)

    # Metadata
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        """Initialize tiles if not provided."""
        if not self.tiles:
            self.tiles = [
                [Tile() for _ in range(self.width)] for _ in range(self.height)
            ]

    # === Tile Access ===

    def get_tile(self, pos: Position) -> Tile | None:
        """Get tile at position, or None if out of bounds."""
        if not self.in_bounds(pos):
            return None
        return self.tiles[pos.y][pos.x]

    def set_tile(self, pos: Position, tile: Tile) -> bool:
        """Set tile at position. Returns False if out of bounds."""
        if not self.in_bounds(pos):
            return False
        self.tiles[pos.y][pos.x] = tile
        return True

    def in_bounds(self, pos: Position) -> bool:
        """Check if position is within map bounds."""
        return pos.in_bounds(self.width, self.height)

    def get_tile_type(self, pos: Position) -> TileType | None:
        """Get tile type at position."""
        tile = self.get_tile(pos)
        return tile.tile_type if tile else None

    # === Entity Management ===

    def add_entity(
        self,
        entity_id: str,
        position: Position,
        display_char: str = "?",
        display_name: str = "",
        is_player: bool = False,
        blocks_movement: bool = True,
    ) -> bool:
        """
        Add an entity to the map at the specified position.

        Returns False if position is invalid or occupied.
        """
        if not self.in_bounds(position):
            logger.warning(f"Cannot add entity {entity_id}: position {position} out of bounds")
            return False

        tile = self.get_tile(position)
        if tile and tile.is_occupied:
            logger.warning(f"Cannot add entity {entity_id}: position {position} occupied")
            return False

        # Create entity info
        self.entities[entity_id] = EntityInfo(
            entity_id=entity_id,
            position=position,
            display_char=display_char,
            display_name=display_name or entity_id,
            is_player=is_player,
            blocks_movement=blocks_movement,
        )

        # Mark tile as occupied
        if tile:
            tile.entity_id = entity_id

        return True

    def remove_entity(self, entity_id: str) -> bool:
        """Remove an entity from the map."""
        if entity_id not in self.entities:
            return False

        entity = self.entities[entity_id]
        tile = self.get_tile(entity.position)
        if tile and tile.entity_id == entity_id:
            tile.entity_id = None

        del self.entities[entity_id]
        return True

    def get_entity(self, entity_id: str) -> EntityInfo | None:
        """Get entity info by ID."""
        return self.entities.get(entity_id)

    def get_entity_position(self, entity_id: str) -> Position | None:
        """Get position of an entity."""
        entity = self.entities.get(entity_id)
        return entity.position if entity else None

    def get_entity_at(self, pos: Position) -> EntityInfo | None:
        """Get entity at a specific position."""
        tile = self.get_tile(pos)
        if tile and tile.entity_id:
            return self.entities.get(tile.entity_id)
        return None

    # === Movement ===

    def can_move_to(self, pos: Position, ignore_entities: bool = False) -> bool:
        """Check if a position can be moved to."""
        if not self.in_bounds(pos):
            return False

        tile = self.get_tile(pos)
        if not tile:
            return False

        if not tile.is_walkable:
            return False

        if not ignore_entities and tile.is_occupied:
            return False

        return True

    def move_entity(self, entity_id: str, direction: Direction) -> MoveResult:
        """
        Attempt to move an entity in a direction.

        Returns MoveResult with success status and details.
        """
        entity = self.entities.get(entity_id)
        if not entity:
            return MoveResult(
                success=False,
                blocked_by="invalid",
                message=f"Entity {entity_id} not found",
            )

        new_pos = entity.position + direction
        return self.move_entity_to(entity_id, new_pos)

    def move_entity_to(self, entity_id: str, new_pos: Position) -> MoveResult:
        """
        Attempt to move an entity to a specific position.

        Returns MoveResult with success status and details.
        """
        entity = self.entities.get(entity_id)
        if not entity:
            return MoveResult(
                success=False,
                blocked_by="invalid",
                message=f"Entity {entity_id} not found",
            )

        old_pos = entity.position

        # Check bounds
        if not self.in_bounds(new_pos):
            return MoveResult(
                success=False,
                blocked_by="bounds",
                message="Cannot move outside map bounds",
            )

        new_tile = self.get_tile(new_pos)
        if not new_tile:
            return MoveResult(
                success=False,
                blocked_by="bounds",
                message="Invalid position",
            )

        # Check walkability
        if not new_tile.is_walkable:
            blocked_type = "wall"
            if new_tile.tile_type in (TileType.DOOR_CLOSED,):
                blocked_type = "door"
            elif new_tile.tile_type in (TileType.WATER_DEEP, TileType.PIT):
                blocked_type = new_tile.tile_type.value
            return MoveResult(
                success=False,
                blocked_by=blocked_type,
                message=f"Blocked by {blocked_type}",
            )

        # Check entity collision
        if new_tile.is_occupied:
            other_entity = self.get_entity_at(new_pos)
            other_name = other_entity.display_name if other_entity else "something"
            return MoveResult(
                success=False,
                blocked_by="entity",
                message=f"Blocked by {other_name}",
            )

        # Perform move
        old_tile = self.get_tile(old_pos)
        if old_tile:
            old_tile.entity_id = None

        new_tile.entity_id = entity_id
        entity.position = new_pos

        return MoveResult(
            success=True,
            new_position=new_pos,
            message="",
        )

    def teleport_entity(self, entity_id: str, new_pos: Position) -> bool:
        """
        Teleport entity to position, ignoring collision.

        Still respects map bounds. Used for spawning and special effects.
        """
        entity = self.entities.get(entity_id)
        if not entity:
            return False

        if not self.in_bounds(new_pos):
            return False

        # Clear old tile
        old_tile = self.get_tile(entity.position)
        if old_tile and old_tile.entity_id == entity_id:
            old_tile.entity_id = None

        # Set new position (may share tile temporarily)
        new_tile = self.get_tile(new_pos)
        if new_tile:
            new_tile.entity_id = entity_id

        entity.position = new_pos
        return True

    # === Spatial Queries ===

    def get_entities_in_radius(
        self, center: Position, radius: int, include_center: bool = False
    ) -> list[EntityInfo]:
        """Get all entities within a certain radius of a position."""
        entities = []
        for entity in self.entities.values():
            dist = center.chebyshev_distance(entity.position)
            if include_center and dist == 0:
                entities.append(entity)
            elif dist > 0 and dist <= radius:
                entities.append(entity)
        return entities

    def get_adjacent_entities(
        self, pos: Position, include_diagonal: bool = True
    ) -> list[EntityInfo]:
        """Get all entities adjacent to a position."""
        return self.get_entities_in_radius(pos, 1, include_center=False)

    def distance_between_entities(
        self, entity_id1: str, entity_id2: str
    ) -> int | None:
        """Get distance in tiles between two entities."""
        pos1 = self.get_entity_position(entity_id1)
        pos2 = self.get_entity_position(entity_id2)
        if pos1 is None or pos2 is None:
            return None
        return pos1.chebyshev_distance(pos2)

    def distance_feet(self, entity_id1: str, entity_id2: str) -> int | None:
        """Get distance in feet between two entities (5ft per tile)."""
        dist = self.distance_between_entities(entity_id1, entity_id2)
        return dist * 5 if dist is not None else None

    def get_player_entities(self) -> list[EntityInfo]:
        """Get all player-controlled entities."""
        return [e for e in self.entities.values() if e.is_player]

    def get_enemy_entities(self) -> list[EntityInfo]:
        """Get all non-player entities."""
        return [e for e in self.entities.values() if not e.is_player]

    # === Door Interaction ===

    def open_door(self, pos: Position) -> bool:
        """Open a door at the specified position."""
        tile = self.get_tile(pos)
        if tile:
            return tile.open_door()
        return False

    def close_door(self, pos: Position) -> bool:
        """Close a door at the specified position."""
        tile = self.get_tile(pos)
        if tile:
            return tile.close_door()
        return False

    def get_adjacent_doors(self, pos: Position) -> list[Position]:
        """Get positions of all adjacent doors (open or closed)."""
        doors = []
        for neighbor_pos in pos.neighbors():
            tile = self.get_tile(neighbor_pos)
            if tile and tile.tile_type in (TileType.DOOR_CLOSED, TileType.DOOR_OPEN):
                doors.append(neighbor_pos)
        return doors

    # === Visibility ===

    def reset_visibility(self) -> None:
        """Mark all visible tiles as explored (for FOV recalculation)."""
        for row in self.tiles:
            for tile in row:
                tile.set_explored()

    def set_visible(self, pos: Position) -> None:
        """Mark a tile as visible."""
        tile = self.get_tile(pos)
        if tile:
            tile.set_visible()

    def reveal_all(self) -> None:
        """Reveal entire map (for debugging or after dungeon completion)."""
        for row in self.tiles:
            for tile in row:
                tile.set_visible()

    # === Iteration ===

    def iter_tiles(self) -> Iterator[tuple[Position, Tile]]:
        """Iterate over all tiles with their positions."""
        for y, row in enumerate(self.tiles):
            for x, tile in enumerate(row):
                yield Position(x, y), tile

    def iter_visible_tiles(self) -> Iterator[tuple[Position, Tile]]:
        """Iterate over only visible tiles."""
        for pos, tile in self.iter_tiles():
            if tile.is_visible():
                yield pos, tile

    def iter_explored_tiles(self) -> Iterator[tuple[Position, Tile]]:
        """Iterate over all explored tiles (visible or previously seen)."""
        for pos, tile in self.iter_tiles():
            if tile.is_explored():
                yield pos, tile

    # === Serialization ===

    def to_dict(self) -> dict:
        """Serialize map to dictionary for saving."""
        return {
            "width": self.width,
            "height": self.height,
            "name": self.name,
            "tiles": [
                [
                    {
                        "type": tile.tile_type.value,
                        "visibility": tile.visibility.value,
                        "entity_id": tile.entity_id,
                        "item_ids": tile.item_ids,
                        "metadata": tile.metadata,
                    }
                    for tile in row
                ]
                for row in self.tiles
            ],
            "entities": {
                eid: {
                    "position": {"x": e.position.x, "y": e.position.y},
                    "display_char": e.display_char,
                    "display_name": e.display_name,
                    "is_player": e.is_player,
                    "blocks_movement": e.blocks_movement,
                }
                for eid, e in self.entities.items()
            },
            "connections": self.connections,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TileMap:
        """Deserialize map from dictionary."""
        width = data["width"]
        height = data["height"]

        tiles = []
        for row_data in data.get("tiles", []):
            row = []
            for tile_data in row_data:
                tile = Tile(
                    tile_type=TileType(tile_data["type"]),
                    visibility=VisibilityState(tile_data.get("visibility", "unexplored")),
                    entity_id=tile_data.get("entity_id"),
                    item_ids=tile_data.get("item_ids", []),
                    metadata=tile_data.get("metadata", {}),
                )
                row.append(tile)
            tiles.append(row)

        tile_map = cls(
            width=width,
            height=height,
            name=data.get("name", "Unknown"),
            tiles=tiles,
            connections=data.get("connections", {}),
            metadata=data.get("metadata", {}),
        )

        # Restore entities
        for eid, edata in data.get("entities", {}).items():
            pos = Position(edata["position"]["x"], edata["position"]["y"])
            tile_map.entities[eid] = EntityInfo(
                entity_id=eid,
                position=pos,
                display_char=edata.get("display_char", "?"),
                display_name=edata.get("display_name", eid),
                is_player=edata.get("is_player", False),
                blocks_movement=edata.get("blocks_movement", True),
            )

        return tile_map

    def __str__(self) -> str:
        """Simple string representation of the map."""
        return f"TileMap({self.name}, {self.width}x{self.height}, {len(self.entities)} entities)"
