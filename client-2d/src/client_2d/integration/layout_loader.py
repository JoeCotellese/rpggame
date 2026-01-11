# ABOUTME: Loads room layouts from dungeon JSON files.
# ABOUTME: Falls back to procedural generation when layout not defined.

"""Layout loader for campaign room layouts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from client_2d.integration.layout_schema import RoomLayout, TileType


class LayoutLoader:
    """Loads room layouts from campaign dungeon files.

    Layouts are optional - if a room doesn't have a layout field,
    a basic procedural layout is generated.

    Usage:
        loader = LayoutLoader(content_path)
        layout = loader.load_room_layout("laboratory", "laboratory.entrance")
    """

    def __init__(self, content_path: Path | None = None) -> None:
        """Initialize the layout loader.

        Args:
            content_path: Path to content directory containing campaigns.
                         If None, uses default dnd-engine content path.
        """
        if content_path is None:
            # Default to dnd-engine content path
            # Path: integration/ -> client_2d/ -> src/ -> client-2d/ -> rpggame/
            content_path = (
                Path(__file__).parent.parent.parent.parent.parent
                / "dnd-engine"
                / "dnd_engine"
                / "data"
                / "content"
            )
        self.content_path = content_path
        self._cache: dict[str, RoomLayout] = {}

    def load_room_layout(
        self,
        dungeon_name: str,
        room_id: str,
        campaign_id: str = "poisoned_laboratory",
    ) -> RoomLayout | None:
        """Load a room layout from a dungeon file.

        Args:
            dungeon_name: Name of the dungeon file (without .json)
            room_id: Room ID within the dungeon
            campaign_id: Campaign containing the dungeon

        Returns:
            RoomLayout if layout exists, None if not found
        """
        cache_key = f"{campaign_id}/{dungeon_name}/{room_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        dungeon_path = (
            self.content_path
            / "campaigns"
            / campaign_id
            / "dungeons"
            / f"{dungeon_name}.json"
        )

        if not dungeon_path.exists():
            return None

        try:
            with open(dungeon_path) as f:
                dungeon_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

        rooms = dungeon_data.get("rooms", {})
        room_data = rooms.get(room_id)

        if not room_data:
            return None

        layout_data = room_data.get("layout")
        if not layout_data:
            return None

        try:
            layout = RoomLayout.model_validate(layout_data)
            self._cache[cache_key] = layout
            return layout
        except ValidationError:
            return None

    def load_room_with_fallback(
        self,
        dungeon_name: str,
        room_id: str,
        campaign_id: str = "poisoned_laboratory",
        default_width: int = 20,
        default_height: int = 15,
        exits: dict[str, str] | None = None,
    ) -> RoomLayout:
        """Load a room layout, generating a fallback if none exists.

        Args:
            dungeon_name: Name of the dungeon file
            room_id: Room ID within the dungeon
            campaign_id: Campaign containing the dungeon
            default_width: Width for generated fallback
            default_height: Height for generated fallback
            exits: Exit directions for doorway placement

        Returns:
            RoomLayout (from file or generated)
        """
        layout = self.load_room_layout(dungeon_name, room_id, campaign_id)
        if layout:
            return layout

        return generate_basic_room(default_width, default_height, exits or {})

    def get_room_data(
        self,
        dungeon_name: str,
        room_id: str,
        campaign_id: str = "poisoned_laboratory",
    ) -> dict[str, Any] | None:
        """Get raw room data from dungeon file.

        Args:
            dungeon_name: Name of the dungeon file
            room_id: Room ID within the dungeon
            campaign_id: Campaign containing the dungeon

        Returns:
            Room data dict or None
        """
        dungeon_path = (
            self.content_path
            / "campaigns"
            / campaign_id
            / "dungeons"
            / f"{dungeon_name}.json"
        )

        if not dungeon_path.exists():
            return None

        try:
            with open(dungeon_path) as f:
                dungeon_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

        return dungeon_data.get("rooms", {}).get(room_id)

    def clear_cache(self) -> None:
        """Clear the layout cache."""
        self._cache.clear()


def generate_basic_room(
    width: int,
    height: int,
    exits: dict[str, str],
) -> RoomLayout:
    """Generate a basic procedural room layout.

    Creates a simple rectangular room with walls around the border
    and doorways for each exit direction.

    Args:
        width: Room width in tiles
        height: Room height in tiles
        exits: Map of exit direction to destination room

    Returns:
        Generated RoomLayout
    """
    # Create tile array - floor with wall border
    tiles = []
    for y in range(height):
        row = []
        for x in range(width):
            if x == 0 or x == width - 1 or y == 0 or y == height - 1:
                row.append(TileType.WALL.value)
            else:
                row.append(TileType.FLOOR.value)
        tiles.append(row)

    # Calculate exit positions and create doorways
    exit_positions: dict[str, tuple[int, int]] = {}
    center_x = width // 2
    center_y = height // 2

    for direction in exits:
        if direction == "north":
            ex, ey = center_x, 0
            tiles[0][center_x] = TileType.DOOR.value
        elif direction == "south":
            ex, ey = center_x, height - 1
            tiles[height - 1][center_x] = TileType.DOOR.value
        elif direction == "east":
            ex, ey = width - 1, center_y
            tiles[center_y][width - 1] = TileType.DOOR.value
        elif direction == "west":
            ex, ey = 0, center_y
            tiles[center_y][0] = TileType.DOOR.value
        else:
            continue
        exit_positions[direction] = (ex, ey)

    # Player spawn in center
    player_spawn = (center_x, center_y)

    return RoomLayout(
        width=width,
        height=height,
        tiles=tiles,
        spawn_points={
            "player": player_spawn,
            "exits": exit_positions,
        },
    )
