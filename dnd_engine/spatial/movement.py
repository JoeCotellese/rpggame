# ABOUTME: Movement controller for 2D dungeon crawler
# ABOUTME: Handles entity movement, collision, door interaction, and movement costs

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Callable

from dnd_engine.spatial.grid import TileMap, MoveResult
from dnd_engine.spatial.position import Direction, Position
from dnd_engine.spatial.tile import TileType
from dnd_engine.utils.events import Event, EventBus, EventType

if TYPE_CHECKING:
    from dnd_engine.core.character import Character

logger = logging.getLogger(__name__)


class MovementMode(Enum):
    """Movement mode affects how movement is processed."""

    EXPLORATION = "exploration"  # Free movement, no action cost
    COMBAT = "combat"  # Movement costs from speed pool


@dataclass
class MovementState:
    """
    Tracks movement state for an entity during combat.

    In combat, movement is limited by speed (typically 30ft = 6 tiles).
    This tracks how much movement has been used.
    """

    speed: int = 30  # Total speed in feet
    movement_used: int = 0  # Feet of movement used this turn
    feet_per_tile: int = 5

    @property
    def movement_remaining(self) -> int:
        """Get remaining movement in feet."""
        return max(0, self.speed - self.movement_used)

    @property
    def tiles_remaining(self) -> int:
        """Get remaining movement in tiles."""
        return self.movement_remaining // self.feet_per_tile

    def can_move(self, tiles: int = 1) -> bool:
        """Check if entity can move the specified number of tiles."""
        feet_needed = tiles * self.feet_per_tile
        return feet_needed <= self.movement_remaining

    def use_movement(self, tiles: int = 1) -> bool:
        """
        Use movement for the specified number of tiles.

        Returns True if movement was available and used.
        """
        feet_needed = tiles * self.feet_per_tile
        if feet_needed > self.movement_remaining:
            return False
        self.movement_used += feet_needed
        return True

    def reset(self) -> None:
        """Reset movement at start of turn."""
        self.movement_used = 0


@dataclass
class MovementController:
    """
    Manages entity movement on a tile map.

    Handles:
    - Movement in cardinal and diagonal directions
    - Collision detection (walls, entities)
    - Door interaction
    - Movement costs (combat mode)
    - Event emission for movement
    """

    tile_map: TileMap
    event_bus: EventBus | None = None
    mode: MovementMode = MovementMode.EXPLORATION

    # Track movement state per entity (for combat)
    movement_states: dict[str, MovementState] = field(default_factory=dict)

    # Callbacks for special events
    on_move: Callable[[str, Position, Position], None] | None = None
    on_blocked: Callable[[str, Position, str], None] | None = None
    on_door_interact: Callable[[str, Position, bool], None] | None = None

    def move(
        self,
        entity_id: str,
        direction: Direction,
        allow_diagonal: bool = True,
    ) -> MoveResult:
        """
        Move an entity in a direction.

        Args:
            entity_id: ID of entity to move
            direction: Direction to move
            allow_diagonal: Whether diagonal movement is allowed

        Returns:
            MoveResult with success status and details
        """
        if not allow_diagonal and direction.is_diagonal:
            return MoveResult(
                success=False,
                blocked_by="diagonal",
                message="Diagonal movement not allowed",
            )

        # Check combat movement limits
        if self.mode == MovementMode.COMBAT:
            state = self._get_movement_state(entity_id)
            if not state.can_move(1):
                return MoveResult(
                    success=False,
                    blocked_by="speed",
                    message=f"No movement remaining (used {state.movement_used}/{state.speed} ft)",
                )

        # Get current position
        entity = self.tile_map.get_entity(entity_id)
        if not entity:
            return MoveResult(
                success=False,
                blocked_by="invalid",
                message=f"Entity {entity_id} not found",
            )

        old_pos = entity.position

        # Attempt move
        result = self.tile_map.move_entity(entity_id, direction)

        if result.success:
            # Use combat movement
            if self.mode == MovementMode.COMBAT:
                state = self._get_movement_state(entity_id)
                state.use_movement(1)

            # Emit event
            self._emit_move_event(entity_id, old_pos, result.new_position)

            # Callback
            if self.on_move and result.new_position:
                self.on_move(entity_id, old_pos, result.new_position)
        else:
            # Callback for blocked
            if self.on_blocked:
                target_pos = old_pos + direction
                self.on_blocked(entity_id, target_pos, result.blocked_by or "unknown")

        return result

    def move_to(self, entity_id: str, target: Position) -> MoveResult:
        """
        Move entity to a specific adjacent position.

        Only allows movement to adjacent tiles (1 tile away).
        """
        entity = self.tile_map.get_entity(entity_id)
        if not entity:
            return MoveResult(
                success=False,
                blocked_by="invalid",
                message=f"Entity {entity_id} not found",
            )

        old_pos = entity.position

        # Check if target is adjacent
        if not old_pos.is_adjacent(target):
            return MoveResult(
                success=False,
                blocked_by="distance",
                message="Target position is not adjacent",
            )

        # Get direction
        direction = old_pos.direction_to(target)
        if not direction:
            return MoveResult(
                success=False,
                blocked_by="invalid",
                message="Cannot determine direction",
            )

        return self.move(entity_id, direction)

    def interact_with_door(self, entity_id: str, door_pos: Position) -> bool:
        """
        Interact with a door (toggle open/closed).

        Entity must be adjacent to the door.

        Returns True if interaction succeeded.
        """
        entity = self.tile_map.get_entity(entity_id)
        if not entity:
            logger.warning(f"Entity {entity_id} not found for door interaction")
            return False

        # Check adjacency
        if not entity.position.is_adjacent(door_pos):
            logger.info(f"Door at {door_pos} not adjacent to {entity_id}")
            return False

        tile = self.tile_map.get_tile(door_pos)
        if not tile:
            return False

        # Toggle door state
        if tile.tile_type == TileType.DOOR_CLOSED:
            success = tile.open_door()
            if success:
                self._emit_door_event(door_pos, opened=True)
                if self.on_door_interact:
                    self.on_door_interact(entity_id, door_pos, True)
            return success
        elif tile.tile_type == TileType.DOOR_OPEN:
            success = tile.close_door()
            if success:
                self._emit_door_event(door_pos, opened=False)
                if self.on_door_interact:
                    self.on_door_interact(entity_id, door_pos, False)
            return success

        return False

    def open_adjacent_door(self, entity_id: str) -> Position | None:
        """
        Open the nearest adjacent closed door.

        Returns the position of the opened door, or None if no door found.
        """
        entity = self.tile_map.get_entity(entity_id)
        if not entity:
            return None

        doors = self.tile_map.get_adjacent_doors(entity.position)

        for door_pos in doors:
            tile = self.tile_map.get_tile(door_pos)
            if tile and tile.tile_type == TileType.DOOR_CLOSED:
                if self.interact_with_door(entity_id, door_pos):
                    return door_pos

        return None

    def get_valid_moves(
        self,
        entity_id: str,
        allow_diagonal: bool = True,
    ) -> list[Direction]:
        """
        Get list of valid movement directions for an entity.

        Considers walls, entities, and optionally diagonal restrictions.
        """
        entity = self.tile_map.get_entity(entity_id)
        if not entity:
            return []

        # Check combat movement limits
        if self.mode == MovementMode.COMBAT:
            state = self._get_movement_state(entity_id)
            if not state.can_move(1):
                return []

        valid = []
        directions = Direction.all_directions() if allow_diagonal else Direction.cardinal()

        for direction in directions:
            new_pos = entity.position + direction
            if self.tile_map.can_move_to(new_pos):
                valid.append(direction)

        return valid

    def get_movement_state(self, entity_id: str) -> MovementState:
        """Get movement state for an entity (creates if needed)."""
        return self._get_movement_state(entity_id)

    def set_speed(self, entity_id: str, speed: int) -> None:
        """Set the movement speed for an entity."""
        state = self._get_movement_state(entity_id)
        state.speed = speed

    def reset_movement(self, entity_id: str) -> None:
        """Reset movement for an entity (start of turn)."""
        if entity_id in self.movement_states:
            self.movement_states[entity_id].reset()

    def reset_all_movement(self) -> None:
        """Reset movement for all entities."""
        for state in self.movement_states.values():
            state.reset()

    def set_mode(self, mode: MovementMode) -> None:
        """Set the movement mode."""
        self.mode = mode
        if mode == MovementMode.EXPLORATION:
            # In exploration, movement is unlimited
            self.reset_all_movement()

    def _get_movement_state(self, entity_id: str) -> MovementState:
        """Get or create movement state for entity."""
        if entity_id not in self.movement_states:
            self.movement_states[entity_id] = MovementState()
        return self.movement_states[entity_id]

    def _emit_move_event(
        self,
        entity_id: str,
        old_pos: Position,
        new_pos: Position | None,
    ) -> None:
        """Emit ENTITY_MOVED event."""
        if self.event_bus and new_pos:
            self.event_bus.emit(Event(
                type=EventType.ENTITY_MOVED,
                data={
                    "entity_id": entity_id,
                    "old_position": {"x": old_pos.x, "y": old_pos.y},
                    "new_position": {"x": new_pos.x, "y": new_pos.y},
                    "mode": self.mode.value,
                },
            ))

    def _emit_door_event(self, door_pos: Position, opened: bool) -> None:
        """Emit door opened/closed event."""
        if self.event_bus:
            event_type = EventType.DOOR_OPENED if opened else EventType.DOOR_CLOSED
            self.event_bus.emit(Event(
                type=event_type,
                data={
                    "position": {"x": door_pos.x, "y": door_pos.y},
                },
            ))


# Input mapping for common key schemes
KEY_TO_DIRECTION: dict[str, Direction] = {
    # WASD
    "w": Direction.NORTH,
    "a": Direction.WEST,
    "s": Direction.SOUTH,
    "d": Direction.EAST,
    # Arrow keys (as strings)
    "up": Direction.NORTH,
    "down": Direction.SOUTH,
    "left": Direction.WEST,
    "right": Direction.EAST,
    # Numpad (roguelike)
    "8": Direction.NORTH,
    "2": Direction.SOUTH,
    "4": Direction.WEST,
    "6": Direction.EAST,
    "7": Direction.NORTHWEST,
    "9": Direction.NORTHEAST,
    "1": Direction.SOUTHWEST,
    "3": Direction.SOUTHEAST,
    # Vi keys
    "k": Direction.NORTH,
    "j": Direction.SOUTH,
    "h": Direction.WEST,
    "l": Direction.EAST,
    "y": Direction.NORTHWEST,
    "u": Direction.NORTHEAST,
    "b": Direction.SOUTHWEST,
    "n": Direction.SOUTHEAST,
}


def key_to_direction(key: str) -> Direction | None:
    """Convert a key press to a direction."""
    return KEY_TO_DIRECTION.get(key.lower())
