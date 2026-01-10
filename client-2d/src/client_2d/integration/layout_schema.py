# ABOUTME: Pydantic models for room layout JSON schema validation.
# ABOUTME: Defines tile-based layout structure for 2D client rendering.

"""Layout schema definitions for campaign room layouts."""

from __future__ import annotations

from enum import IntEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class TileType(IntEnum):
    """Tile types for room layouts."""

    FLOOR = 0  # Walkable floor
    WALL = 1  # Solid wall, blocks movement and light
    DOOR = 2  # Doorway, walkable
    WATER = 3  # Water, difficult terrain
    PIT = 4  # Pit, blocks movement unless flying


class SpawnPoints(BaseModel):
    """Spawn point definitions for a room."""

    player: tuple[int, int] = Field(description="Player spawn position [x, y]")
    exits: dict[str, tuple[int, int]] = Field(
        default_factory=dict,
        description="Exit positions keyed by direction (north, south, etc.)",
    )

    @field_validator("player", "exits", mode="before")
    @classmethod
    def convert_lists_to_tuples(cls, v: Any) -> Any:
        """Convert JSON lists to tuples."""
        if isinstance(v, list) and len(v) == 2:
            return tuple(v)
        if isinstance(v, dict):
            return {k: tuple(pos) if isinstance(pos, list) else pos for k, pos in v.items()}
        return v


class EntityPositions(BaseModel):
    """Entity position definitions for a room."""

    enemies: list[tuple[int, int]] = Field(
        default_factory=list, description="Enemy spawn positions"
    )
    items: list[tuple[int, int]] = Field(
        default_factory=list, description="Item positions"
    )

    @field_validator("enemies", "items", mode="before")
    @classmethod
    def convert_lists_to_tuples(cls, v: Any) -> Any:
        """Convert JSON lists to tuples."""
        if isinstance(v, list):
            return [tuple(pos) if isinstance(pos, list) else pos for pos in v]
        return v


class LightSource(BaseModel):
    """Static light source in a room."""

    x: int
    y: int
    type: str = "torch"  # torch, lantern, magical, etc.
    radius: int = 20  # Light radius in tiles


class RoomLayout(BaseModel):
    """Tile-based layout for a dungeon room."""

    width: int = Field(gt=0, description="Room width in tiles")
    height: int = Field(gt=0, description="Room height in tiles")
    tiles: list[list[int]] = Field(description="2D array of tile values")
    spawn_points: SpawnPoints
    entity_positions: EntityPositions = Field(default_factory=EntityPositions)
    light_sources: list[LightSource] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dimensions(self) -> RoomLayout:
        """Validate tile array matches declared dimensions."""
        if len(self.tiles) != self.height:
            raise ValueError(
                f"Tile array height {len(self.tiles)} doesn't match declared height {self.height}"
            )
        for y, row in enumerate(self.tiles):
            if len(row) != self.width:
                raise ValueError(
                    f"Row {y} width {len(row)} doesn't match declared width {self.width}"
                )
        return self

    @model_validator(mode="after")
    def validate_spawn_in_bounds(self) -> RoomLayout:
        """Validate spawn points are within room bounds."""
        px, py = self.spawn_points.player
        if not (0 <= px < self.width and 0 <= py < self.height):
            raise ValueError(f"Player spawn {self.spawn_points.player} out of bounds")

        for direction, (ex, ey) in self.spawn_points.exits.items():
            if not (0 <= ex < self.width and 0 <= ey < self.height):
                raise ValueError(f"Exit '{direction}' spawn ({ex}, {ey}) out of bounds")

        return self

    def get_tile(self, x: int, y: int) -> TileType:
        """Get tile type at position."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return TileType(self.tiles[y][x])
        return TileType.WALL  # Out of bounds treated as wall

    def is_walkable(self, x: int, y: int) -> bool:
        """Check if a tile is walkable."""
        tile = self.get_tile(x, y)
        return tile in (TileType.FLOOR, TileType.DOOR, TileType.WATER)

    def is_blocking(self, x: int, y: int) -> bool:
        """Check if a tile blocks movement and light."""
        tile = self.get_tile(x, y)
        return tile in (TileType.WALL, TileType.PIT)
