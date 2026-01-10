# ABOUTME: Fog of war system managing tile visibility based on exploration.
# ABOUTME: Tracks which tiles have been explored and their current visibility state.

"""Fog of War system for tracking tile visibility and exploration."""

from dataclasses import dataclass, field

import numpy as np

from client_2d.core.constants import LightingState


@dataclass
class FogOfWarSystem:
    """Manages tile visibility states based on exploration and lighting.

    The fog of war system tracks:
    - Which tiles have been explored (ever seen by the party)
    - Current visibility based on lighting sources
    - Memory of previously seen tiles (rendered as dim/grayscale)

    Visibility States:
    - UNEXPLORED: Never seen, rendered as solid black
    - DARK: Previously seen but not currently lit, rendered dim
    - DIM: Currently in dim light, rendered with partial dimming
    - BRIGHT: Currently in bright light, rendered at full brightness
    """

    width: int
    height: int
    # Visibility grid using LightingState enum values
    _visibility: np.ndarray = field(init=False)
    # Set of tiles that have ever been explored
    _explored: set[tuple[int, int]] = field(default_factory=set)

    def __post_init__(self):
        """Initialize the visibility grid to all unexplored."""
        self._visibility = np.full(
            (self.width, self.height),
            LightingState.UNEXPLORED.value,
            dtype=np.uint8,
        )

    def get_visibility(self, x: int, y: int) -> LightingState:
        """Get the current visibility state for a tile.

        Args:
            x: Tile X coordinate
            y: Tile Y coordinate

        Returns:
            Current LightingState for the tile
        """
        if not self._in_bounds(x, y):
            return LightingState.UNEXPLORED
        return LightingState(self._visibility[x, y])

    def set_visibility(self, x: int, y: int, state: LightingState) -> None:
        """Set the visibility state for a tile.

        Args:
            x: Tile X coordinate
            y: Tile Y coordinate
            state: New LightingState for the tile
        """
        if not self._in_bounds(x, y):
            return

        self._visibility[x, y] = state.value

        # Any state other than UNEXPLORED means the tile has been explored
        if state != LightingState.UNEXPLORED:
            self._explored.add((x, y))

    def reveal_tile(self, x: int, y: int) -> None:
        """Mark a tile as explored, setting minimum state to DARK.

        This is called when a tile enters the player's field of view.
        Once explored, a tile will never return to UNEXPLORED.

        Args:
            x: Tile X coordinate
            y: Tile Y coordinate
        """
        if not self._in_bounds(x, y):
            return

        # Mark as explored
        self._explored.add((x, y))

        # Set to DARK if currently unexplored (will be upgraded by lighting)
        if self._visibility[x, y] == LightingState.UNEXPLORED.value:
            self._visibility[x, y] = LightingState.DARK.value

    def is_explored(self, x: int, y: int) -> bool:
        """Check if a tile has ever been explored.

        Args:
            x: Tile X coordinate
            y: Tile Y coordinate

        Returns:
            True if the tile has been explored
        """
        return (x, y) in self._explored

    def reset_to_dark(self) -> None:
        """Reset all explored tiles to DARK state.

        Called before recalculating lighting. Unexplored tiles stay unexplored.
        """
        for x, y in self._explored:
            self._visibility[x, y] = LightingState.DARK.value

    def apply_lighting(
        self, lit_tiles: dict[tuple[int, int], LightingState]
    ) -> None:
        """Apply lighting states from a lighting calculation.

        This should be called after reset_to_dark() to apply current lighting.

        Args:
            lit_tiles: Dict mapping (x, y) to LightingState for lit tiles
        """
        for (x, y), state in lit_tiles.items():
            if self._in_bounds(x, y):
                # Only reveal tiles that are being lit
                self._explored.add((x, y))
                # Take the brighter of current state and new state
                current = self._visibility[x, y]
                if state.value > current:
                    self._visibility[x, y] = state.value

    def get_all_visible_tiles(self) -> list[tuple[int, int, LightingState]]:
        """Get all tiles that are visible (not unexplored).

        Returns:
            List of (x, y, state) tuples for visible tiles
        """
        visible = []
        for x, y in self._explored:
            state = LightingState(self._visibility[x, y])
            visible.append((x, y, state))
        return visible

    def get_tiles_in_state(
        self, state: LightingState
    ) -> list[tuple[int, int]]:
        """Get all tiles currently in a specific visibility state.

        Args:
            state: The LightingState to filter by

        Returns:
            List of (x, y) tuples for tiles in that state
        """
        matches = np.argwhere(self._visibility == state.value)
        return [(int(x), int(y)) for x, y in matches]

    def _in_bounds(self, x: int, y: int) -> bool:
        """Check if coordinates are within the fog grid bounds."""
        return 0 <= x < self.width and 0 <= y < self.height

    @property
    def explored_count(self) -> int:
        """Number of tiles that have been explored."""
        return len(self._explored)

    @property
    def total_tiles(self) -> int:
        """Total number of tiles in the map."""
        return self.width * self.height
