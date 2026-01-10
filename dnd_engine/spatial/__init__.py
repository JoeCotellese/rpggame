# ABOUTME: Spatial module for 2D dungeon crawler grid-based positioning
# ABOUTME: Provides tile maps, entity positions, FOV, and pathfinding

from dnd_engine.spatial.position import Position, Direction
from dnd_engine.spatial.tile import Tile, TileType, VisibilityState
from dnd_engine.spatial.grid import TileMap, EntityInfo, MoveResult
from dnd_engine.spatial.map_loader import (
    MapLoader,
    LoadedMap,
    SpawnPoint,
    MapConnection,
    MapRegion,
    create_simple_map,
    create_map_from_string,
)
from dnd_engine.spatial.movement import (
    MovementController,
    MovementMode,
    MovementState,
    key_to_direction,
    KEY_TO_DIRECTION,
)
from dnd_engine.spatial.fov import (
    FieldOfView,
    SimpleFOV,
    FOVConfig,
    compute_los,
    compute_visibility_at_distance,
)
from dnd_engine.spatial.combat_grid import (
    CombatGridManager,
    CombatantInfo,
    RangeCheckResult,
    AttackType,
    FEET_PER_TILE,
)

__all__ = [
    "Position",
    "Direction",
    "Tile",
    "TileType",
    "VisibilityState",
    "TileMap",
    "EntityInfo",
    "MoveResult",
    "MapLoader",
    "LoadedMap",
    "SpawnPoint",
    "MapConnection",
    "MapRegion",
    "create_simple_map",
    "create_map_from_string",
    "MovementController",
    "MovementMode",
    "MovementState",
    "key_to_direction",
    "KEY_TO_DIRECTION",
    "FieldOfView",
    "SimpleFOV",
    "FOVConfig",
    "compute_los",
    "compute_visibility_at_distance",
    "CombatGridManager",
    "CombatantInfo",
    "RangeCheckResult",
    "AttackType",
    "FEET_PER_TILE",
]
