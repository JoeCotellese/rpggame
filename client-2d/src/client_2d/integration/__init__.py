# ABOUTME: Integration module for bridging dnd-engine events to the 2D client.
# ABOUTME: Subscribes to EventBus and triggers appropriate UI updates.

"""Engine integration for the 2D client."""

from client_2d.integration.engine_bridge import (
    ClientEventCallback,
    CombatState,
    EngineBridge,
    EntityState,
    PlayerState,
)
from client_2d.integration.layout_loader import LayoutLoader, generate_basic_room
from client_2d.integration.layout_schema import (
    EntityPositions,
    LightSource,
    RoomLayout,
    SpawnPoints,
    TileType,
)

__all__ = [
    # Engine bridge
    "EngineBridge",
    "PlayerState",
    "EntityState",
    "CombatState",
    "ClientEventCallback",
    # Layout schema
    "RoomLayout",
    "SpawnPoints",
    "EntityPositions",
    "LightSource",
    "TileType",
    # Layout loader
    "LayoutLoader",
    "generate_basic_room",
]
