# ABOUTME: Map loader for 2D dungeon grid maps from JSON format
# ABOUTME: Converts ASCII-art style maps with legend into TileMap objects

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dnd_engine.spatial.grid import TileMap, EntityInfo
from dnd_engine.spatial.position import Position
from dnd_engine.spatial.tile import Tile, TileType

logger = logging.getLogger(__name__)


@dataclass
class SpawnPoint:
    """A spawn point for entities on the map."""

    position: Position
    entity_type: str  # "player", "monster", "npc"
    entity_id: str | None = None  # Specific monster/NPC ID
    display_char: str = "?"
    display_name: str = ""


@dataclass
class MapConnection:
    """Connection to another map (stairs, portal, etc.)."""

    position: Position
    target_map: str
    target_position: Position | None = None
    connection_type: str = "stairs"  # stairs_up, stairs_down, portal, door


@dataclass
class MapRegion:
    """Named region of the map for room-based events."""

    name: str
    x1: int
    y1: int
    x2: int
    y2: int
    description: str = ""
    metadata: dict = field(default_factory=dict)

    def contains(self, pos: Position) -> bool:
        """Check if position is within this region."""
        return self.x1 <= pos.x <= self.x2 and self.y1 <= pos.y <= self.y2


@dataclass
class LoadedMap:
    """Result of loading a map, includes all parsed data."""

    tile_map: TileMap
    spawn_points: list[SpawnPoint] = field(default_factory=list)
    connections: list[MapConnection] = field(default_factory=list)
    regions: list[MapRegion] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class MapLoader:
    """
    Loads 2D grid maps from JSON format.

    Map JSON format:
    {
        "id": "dungeon_level_1",
        "name": "The Dark Dungeon - Level 1",
        "width": 40,
        "height": 20,
        "tiles": [
            "########################################",
            "#......................................#",
            "#..@...G...............................#",
            ...
        ],
        "legend": {
            "#": {"type": "wall"},
            ".": {"type": "floor"},
            "+": {"type": "door_closed"},
            "@": {"type": "floor", "spawn": "player"},
            "G": {"type": "floor", "spawn": {"type": "monster", "id": "goblin"}}
        },
        "regions": [
            {"name": "entrance", "x1": 0, "y1": 0, "x2": 10, "y2": 10}
        ],
        "connections": [
            {"x": 38, "y": 18, "target_map": "level_2", "type": "stairs_down"}
        ]
    }
    """

    # Default legend for common characters
    DEFAULT_LEGEND: dict[str, dict[str, Any]] = {
        "#": {"type": "wall"},
        ".": {"type": "floor"},
        " ": {"type": "floor"},  # Space = floor
        "+": {"type": "door_closed"},
        "/": {"type": "door_open"},
        "<": {"type": "stairs_up"},
        ">": {"type": "stairs_down"},
        "~": {"type": "water_shallow"},
        "=": {"type": "water_deep"},
        "^": {"type": "trap"},
        "$": {"type": "chest"},
        "_": {"type": "altar"},
        "O": {"type": "pillar"},
        "@": {"type": "floor", "spawn": "player"},
        "G": {"type": "floor", "spawn": {"type": "monster", "id": "goblin"}},
        "S": {"type": "floor", "spawn": {"type": "monster", "id": "skeleton"}},
        "W": {"type": "floor", "spawn": {"type": "monster", "id": "wolf"}},
        "B": {"type": "floor", "spawn": {"type": "monster", "id": "goblin_boss"}},
    }

    def __init__(self, base_path: Path | None = None):
        """
        Initialize map loader.

        Args:
            base_path: Base path for relative map file references
        """
        self.base_path = base_path or Path(".")

    def load_from_file(self, file_path: Path | str) -> LoadedMap:
        """Load map from a JSON file."""
        path = Path(file_path)
        if not path.is_absolute():
            path = self.base_path / path

        with open(path, "r") as f:
            data = json.load(f)

        return self.load_from_dict(data)

    def load_from_dict(self, data: dict) -> LoadedMap:
        """Load map from a dictionary (parsed JSON)."""
        # Get dimensions
        tiles_data = data.get("tiles", [])
        if not tiles_data:
            raise ValueError("Map must have 'tiles' array")

        height = len(tiles_data)
        width = max(len(row) for row in tiles_data) if tiles_data else 0

        # Override dimensions if specified
        width = data.get("width", width)
        height = data.get("height", height)

        # Merge default legend with custom legend
        legend = dict(self.DEFAULT_LEGEND)
        legend.update(data.get("legend", {}))

        # Create tile map
        tile_map = TileMap(
            width=width,
            height=height,
            name=data.get("name", "Unknown Map"),
            metadata=data.get("metadata", {}),
        )

        # Parse tiles and collect spawn points
        spawn_points: list[SpawnPoint] = []

        for y, row in enumerate(tiles_data):
            for x, char in enumerate(row):
                if x >= width or y >= height:
                    continue

                pos = Position(x, y)
                tile_def = legend.get(char, {"type": "floor"})

                # Create tile
                tile = self._create_tile(tile_def)
                tile_map.set_tile(pos, tile)

                # Check for spawn point
                spawn = self._parse_spawn(tile_def, pos, char)
                if spawn:
                    spawn_points.append(spawn)

        # Parse regions
        regions = self._parse_regions(data.get("regions", []))

        # Parse connections
        connections = self._parse_connections(data.get("connections", []))

        return LoadedMap(
            tile_map=tile_map,
            spawn_points=spawn_points,
            connections=connections,
            regions=regions,
            metadata=data.get("metadata", {}),
        )

    def _create_tile(self, tile_def: dict) -> Tile:
        """Create a Tile from a legend definition."""
        tile_type_str = tile_def.get("type", "floor")

        # Map string to TileType enum
        type_map = {
            "floor": TileType.FLOOR,
            "wall": TileType.WALL,
            "door_closed": TileType.DOOR_CLOSED,
            "door_open": TileType.DOOR_OPEN,
            "stairs_up": TileType.STAIRS_UP,
            "stairs_down": TileType.STAIRS_DOWN,
            "water_shallow": TileType.WATER_SHALLOW,
            "water_deep": TileType.WATER_DEEP,
            "pit": TileType.PIT,
            "trap": TileType.TRAP,
            "chest": TileType.CHEST,
            "altar": TileType.ALTAR,
            "pillar": TileType.PILLAR,
        }

        tile_type = type_map.get(tile_type_str, TileType.FLOOR)

        # Create tile with optional overrides
        tile = Tile(
            tile_type=tile_type,
            walkable=tile_def.get("walkable"),
            blocks_sight=tile_def.get("blocks_sight"),
            metadata=tile_def.get("metadata", {}),
        )

        return tile

    def _parse_spawn(
        self, tile_def: dict, pos: Position, char: str
    ) -> SpawnPoint | None:
        """Parse spawn point from tile definition."""
        spawn_data = tile_def.get("spawn")
        if not spawn_data:
            return None

        if isinstance(spawn_data, str):
            # Simple spawn: "player" or monster name
            if spawn_data == "player":
                return SpawnPoint(
                    position=pos,
                    entity_type="player",
                    display_char="@",
                    display_name="Player",
                )
            else:
                # Assume it's a monster ID
                return SpawnPoint(
                    position=pos,
                    entity_type="monster",
                    entity_id=spawn_data,
                    display_char=char,
                    display_name=spawn_data.replace("_", " ").title(),
                )
        elif isinstance(spawn_data, dict):
            # Complex spawn with full details
            entity_type = spawn_data.get("type", "monster")
            return SpawnPoint(
                position=pos,
                entity_type=entity_type,
                entity_id=spawn_data.get("id"),
                display_char=spawn_data.get("char", char),
                display_name=spawn_data.get("name", spawn_data.get("id", "Unknown")),
            )

        return None

    def _parse_regions(self, regions_data: list | dict) -> list[MapRegion]:
        """Parse region definitions."""
        regions = []

        # Handle both list and dict formats
        if isinstance(regions_data, dict):
            for name, region in regions_data.items():
                regions.append(
                    MapRegion(
                        name=name,
                        x1=region.get("x1", 0),
                        y1=region.get("y1", 0),
                        x2=region.get("x2", 0),
                        y2=region.get("y2", 0),
                        description=region.get("description", ""),
                        metadata=region.get("metadata", {}),
                    )
                )
        else:
            for region in regions_data:
                regions.append(
                    MapRegion(
                        name=region.get("name", "unnamed"),
                        x1=region.get("x1", 0),
                        y1=region.get("y1", 0),
                        x2=region.get("x2", 0),
                        y2=region.get("y2", 0),
                        description=region.get("description", ""),
                        metadata=region.get("metadata", {}),
                    )
                )

        return regions

    def _parse_connections(self, connections_data: list) -> list[MapConnection]:
        """Parse map connection definitions."""
        connections = []

        for conn in connections_data:
            target_pos = None
            if "target_x" in conn and "target_y" in conn:
                target_pos = Position(conn["target_x"], conn["target_y"])

            connections.append(
                MapConnection(
                    position=Position(conn["x"], conn["y"]),
                    target_map=conn.get("target_map", ""),
                    target_position=target_pos,
                    connection_type=conn.get("type", "stairs"),
                )
            )

        return connections

    def spawn_entities(
        self, loaded_map: LoadedMap, spawn_players: bool = True
    ) -> list[str]:
        """
        Spawn entities from spawn points onto the tile map.

        Args:
            loaded_map: The loaded map with spawn points
            spawn_players: Whether to spawn player spawn points

        Returns:
            List of spawned entity IDs
        """
        spawned = []
        tile_map = loaded_map.tile_map

        for i, spawn in enumerate(loaded_map.spawn_points):
            if spawn.entity_type == "player" and not spawn_players:
                continue

            # Generate unique entity ID
            if spawn.entity_id:
                entity_id = f"{spawn.entity_id}_{i}"
            else:
                entity_id = f"{spawn.entity_type}_{i}"

            # Add entity to map
            success = tile_map.add_entity(
                entity_id=entity_id,
                position=spawn.position,
                display_char=spawn.display_char,
                display_name=spawn.display_name,
                is_player=(spawn.entity_type == "player"),
            )

            if success:
                spawned.append(entity_id)
            else:
                logger.warning(
                    f"Failed to spawn {entity_id} at {spawn.position}"
                )

        return spawned


def create_simple_map(
    width: int,
    height: int,
    name: str = "Simple Map",
    wall_border: bool = True,
) -> TileMap:
    """
    Create a simple rectangular map filled with floor tiles.

    Args:
        width: Map width in tiles
        height: Map height in tiles
        name: Name of the map
        wall_border: If True, surround the map with walls

    Returns:
        A new TileMap instance
    """
    tile_map = TileMap(width=width, height=height, name=name)

    if wall_border:
        # Add wall border
        for x in range(width):
            tile_map.set_tile(Position(x, 0), Tile(tile_type=TileType.WALL))
            tile_map.set_tile(Position(x, height - 1), Tile(tile_type=TileType.WALL))

        for y in range(height):
            tile_map.set_tile(Position(0, y), Tile(tile_type=TileType.WALL))
            tile_map.set_tile(Position(width - 1, y), Tile(tile_type=TileType.WALL))

    return tile_map


def create_map_from_string(
    map_string: str,
    name: str = "String Map",
    legend: dict[str, dict] | None = None,
) -> LoadedMap:
    """
    Create a map from an ASCII string representation.

    This is useful for quick map creation in tests or simple dungeons.

    Args:
        map_string: Multi-line string representing the map
        name: Name of the map
        legend: Optional custom legend (merged with defaults)

    Returns:
        LoadedMap with the parsed tile map
    """
    lines = map_string.strip().split("\n")

    data = {
        "name": name,
        "tiles": lines,
    }

    if legend:
        data["legend"] = legend

    loader = MapLoader()
    return loader.load_from_dict(data)
