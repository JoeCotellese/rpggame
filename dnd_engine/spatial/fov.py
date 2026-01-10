# ABOUTME: Field of View (FOV) calculation using shadowcasting algorithm
# ABOUTME: Determines which tiles are visible from a given position considering walls

from __future__ import annotations

from dataclasses import dataclass

from dnd_engine.spatial.grid import TileMap
from dnd_engine.spatial.position import Position


@dataclass
class FOVConfig:
    """Configuration for FOV calculation."""

    # Maximum sight radius in tiles
    max_radius: int = 10

    # Whether walls block sight
    walls_block: bool = True

    # Whether to include the origin in visible tiles
    include_origin: bool = True

    # Light level affects radius (for torch/darkvision)
    light_radius: int | None = None


class FieldOfView:
    """
    Field of View calculator using recursive shadowcasting.

    Shadowcasting is an efficient algorithm for determining visibility
    that works by casting shadows from obstacles in each octant of the
    circle around the viewer.
    """

    # Octant definitions: each tuple is (row_dir_x, row_dir_y, col_dir_x, col_dir_y)
    # row_dir: direction we move as row increases (depth)
    # col_dir: direction we move as col increases (lateral)
    OCTANTS = [
        (0, -1, 1, 0),   # N, scan E
        (1, 0, 0, -1),   # E, scan N
        (1, 0, 0, 1),    # E, scan S
        (0, 1, 1, 0),    # S, scan E
        (0, 1, -1, 0),   # S, scan W
        (-1, 0, 0, 1),   # W, scan S
        (-1, 0, 0, -1),  # W, scan N
        (0, -1, -1, 0),  # N, scan W
    ]

    def __init__(self, tile_map: TileMap, config: FOVConfig | None = None):
        """
        Initialize FOV calculator.

        Args:
            tile_map: The map to calculate FOV on
            config: FOV configuration options
        """
        self.tile_map = tile_map
        self.config = config or FOVConfig()
        self._visible: set[Position] = set()

    def compute(self, origin: Position, radius: int | None = None) -> set[Position]:
        """
        Compute visible tiles from origin position.

        Args:
            origin: Position to compute FOV from
            radius: Optional override for max sight radius

        Returns:
            Set of visible positions
        """
        effective_radius = radius or self.config.light_radius or self.config.max_radius

        self._visible = set()

        if self.config.include_origin:
            self._visible.add(origin)

        # Cast light in all 8 octants
        for row_dx, row_dy, col_dx, col_dy in self.OCTANTS:
            self._cast_light_octant(
                origin.x, origin.y,
                1,  # start at row 1
                1.0, 0.0,  # full visible range: slope 1 to 0
                effective_radius,
                row_dx, row_dy, col_dx, col_dy
            )

        return self._visible

    def compute_and_apply(
        self,
        origin: Position,
        radius: int | None = None,
        mark_explored: bool = True,
    ) -> set[Position]:
        """
        Compute FOV and apply visibility to tile map.

        Args:
            origin: Position to compute FOV from
            radius: Optional override for max sight radius
            mark_explored: If True, reset previous visible to explored

        Returns:
            Set of newly visible positions
        """
        if mark_explored:
            self.tile_map.reset_visibility()

        visible = self.compute(origin, radius)

        for pos in visible:
            self.tile_map.set_visible(pos)

        return visible

    def _blocks_light(self, x: int, y: int) -> bool:
        """Check if a tile blocks light."""
        pos = Position(x, y)
        if not self.tile_map.in_bounds(pos):
            return True  # Out of bounds blocks light

        if not self.config.walls_block:
            return False

        tile = self.tile_map.get_tile(pos)
        return tile is not None and tile.does_block_sight

    def _set_visible(self, x: int, y: int) -> None:
        """Mark a tile as visible."""
        pos = Position(x, y)
        if self.tile_map.in_bounds(pos):
            self._visible.add(pos)

    def _cast_light_octant(
        self,
        cx: int,
        cy: int,
        row: int,
        start_slope: float,
        end_slope: float,
        radius: int,
        row_dx: int,
        row_dy: int,
        col_dx: int,
        col_dy: int,
    ) -> None:
        """
        Recursive shadowcasting for one octant.

        Args:
            cx, cy: Center position (origin)
            row: Current row being scanned (distance from origin)
            start_slope: Starting slope of visible arc (1.0 = full)
            end_slope: Ending slope of visible arc (0.0 = center line)
            radius: Maximum visible radius
            row_dx, row_dy: Direction vector for rows (depth)
            col_dx, col_dy: Direction vector for columns (lateral)

        Slope is defined as column/row. At slope 1, column == row (45 degrees).
        At slope 0, column == 0 (directly along row axis).
        """
        if start_slope < end_slope:
            return

        radius_sq = radius * radius
        next_start_slope = start_slope

        for depth in range(row, radius + 1):
            blocked = False

            # Scan columns from slope=start_slope down to slope=end_slope
            # At each depth, max column is depth (when slope=1)
            for col in range(depth, -1, -1):
                # Calculate actual map position
                map_x = cx + depth * row_dx + col * col_dx
                map_y = cy + depth * row_dy + col * col_dy

                # Calculate slopes for tile edges
                # left_slope: slope to the "left" edge (higher slope)
                # right_slope: slope to the "right" edge (lower slope)
                left_slope = (col + 0.5) / (depth - 0.5) if depth > 0 else 1.0
                right_slope = (col - 0.5) / (depth + 0.5)

                # If we haven't reached the start of visible area, skip
                if left_slope < end_slope:
                    continue

                # If we've passed the visible area, stop
                if right_slope > start_slope:
                    continue

                # Check if within radius
                if depth * depth + col * col <= radius_sq:
                    self._set_visible(map_x, map_y)

                # Handle blocking tiles
                if blocked:
                    if self._blocks_light(map_x, map_y):
                        next_start_slope = right_slope
                    else:
                        blocked = False
                        start_slope = next_start_slope
                elif self._blocks_light(map_x, map_y):
                    blocked = True
                    # Recurse for the unblocked portion
                    self._cast_light_octant(
                        cx, cy, depth + 1, start_slope, left_slope, radius,
                        row_dx, row_dy, col_dx, col_dy
                    )
                    next_start_slope = right_slope

            if blocked:
                break

    def is_visible(self, pos: Position) -> bool:
        """Check if a position is currently in the visible set."""
        return pos in self._visible

    def get_visible_entities(self) -> list[str]:
        """Get IDs of entities in visible tiles."""
        visible_entities = []
        for pos in self._visible:
            entity = self.tile_map.get_entity_at(pos)
            if entity:
                visible_entities.append(entity.entity_id)
        return visible_entities


class SimpleFOV:
    """
    Simple circular FOV without shadowcasting.

    Uses basic distance check - faster but doesn't account for walls.
    Useful for things like area effects or when walls don't matter.
    """

    def __init__(self, tile_map: TileMap):
        self.tile_map = tile_map

    def compute(self, origin: Position, radius: int) -> set[Position]:
        """
        Compute visible tiles in a circular area.

        Args:
            origin: Center position
            radius: Radius in tiles

        Returns:
            Set of positions within radius
        """
        visible = set()

        for y in range(origin.y - radius, origin.y + radius + 1):
            for x in range(origin.x - radius, origin.x + radius + 1):
                pos = Position(x, y)

                if not self.tile_map.in_bounds(pos):
                    continue

                # Check circular distance
                dx = x - origin.x
                dy = y - origin.y
                if dx * dx + dy * dy <= radius * radius:
                    visible.add(pos)

        return visible

    def compute_and_apply(
        self,
        origin: Position,
        radius: int,
        mark_explored: bool = True,
    ) -> set[Position]:
        """Compute FOV and apply to tile map."""
        if mark_explored:
            self.tile_map.reset_visibility()

        visible = self.compute(origin, radius)

        for pos in visible:
            self.tile_map.set_visible(pos)

        return visible


def compute_los(
    tile_map: TileMap,
    start: Position,
    end: Position,
) -> bool:
    """
    Check line of sight between two positions.

    Uses Bresenham's line algorithm to trace from start to end,
    checking for blocking tiles.

    Args:
        tile_map: The map to check
        start: Starting position
        end: Target position

    Returns:
        True if there is clear line of sight
    """
    x0, y0 = start.x, start.y
    x1, y1 = end.x, end.y

    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    while True:
        pos = Position(x0, y0)

        # Skip start position
        if pos != start:
            tile = tile_map.get_tile(pos)

            # Check if we've reached the end
            if pos == end:
                return True

            # Check if blocked
            if tile is None or tile.does_block_sight:
                return False

        if x0 == x1 and y0 == y1:
            return True

        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy


def compute_visibility_at_distance(
    origin: Position,
    target: Position,
    base_radius: int,
    light_level: str = "bright",
) -> bool:
    """
    Check if target is visible based on distance and light level.

    D&D 5E visibility rules:
    - Bright light: See normally
    - Dim light: Disadvantage on Perception, can still see
    - Darkness: Can't see without darkvision

    Args:
        origin: Observer position
        target: Target position
        base_radius: Base sight radius in tiles
        light_level: "bright", "dim", or "dark"

    Returns:
        True if target is visible based on distance
    """
    distance = origin.chebyshev_distance(target)

    if light_level == "bright":
        return distance <= base_radius
    elif light_level == "dim":
        # Half radius in dim light
        return distance <= base_radius // 2
    else:  # dark
        return False
