# ABOUTME: Lighting system managing light sources and illumination calculation.
# ABOUTME: Implements D&D 5E-compliant lighting with bright and dim light radii.

"""Lighting system for calculating tile illumination from light sources."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from client_2d.core.constants import (
    LANTERN_BRIGHT_RADIUS,
    LANTERN_DIM_RADIUS,
    LIGHT_SPELL_BRIGHT_RADIUS,
    LIGHT_SPELL_DIM_RADIUS,
    TORCH_BRIGHT_RADIUS,
    TORCH_DIM_RADIUS,
    LightingState,
)


@dataclass
class LightSource:
    """A light source with D&D-compliant bright and dim light radii.

    D&D 5E light sources:
    - Torch: 20ft bright, +20ft dim (4 tiles each at 5ft/tile)
    - Lantern: 30ft bright, +30ft dim (6 tiles each)
    - Light cantrip: 20ft bright, +20ft dim (4 tiles each)

    Attributes:
        x: Tile X coordinate of the light source
        y: Tile Y coordinate of the light source
        bright_radius: Tiles of bright light from center
        dim_radius: Additional tiles of dim light beyond bright
        source_type: Type identifier (torch, lantern, spell, etc.)
    """

    x: int
    y: int
    bright_radius: int
    dim_radius: int
    source_type: str = "torch"

    @classmethod
    def torch(cls, x: int, y: int) -> "LightSource":
        """Create a torch light source at the given position."""
        return cls(
            x=x,
            y=y,
            bright_radius=TORCH_BRIGHT_RADIUS,
            dim_radius=TORCH_DIM_RADIUS,
            source_type="torch",
        )

    @classmethod
    def lantern(cls, x: int, y: int) -> "LightSource":
        """Create a lantern light source at the given position."""
        return cls(
            x=x,
            y=y,
            bright_radius=LANTERN_BRIGHT_RADIUS,
            dim_radius=LANTERN_DIM_RADIUS,
            source_type="lantern",
        )

    @classmethod
    def light_spell(cls, x: int, y: int) -> "LightSource":
        """Create a Light cantrip light source at the given position."""
        return cls(
            x=x,
            y=y,
            bright_radius=LIGHT_SPELL_BRIGHT_RADIUS,
            dim_radius=LIGHT_SPELL_DIM_RADIUS,
            source_type="light_spell",
        )

    @property
    def total_radius(self) -> int:
        """Total radius including both bright and dim light."""
        return self.bright_radius + self.dim_radius


class LightingAlgorithm(ABC):
    """Abstract base for lighting calculation algorithms.

    This allows for swapping between simple radius-based lighting (Phase 1)
    and more sophisticated raycast shadow-casting (Phase 5).
    """

    @abstractmethod
    def calculate_lit_tiles(
        self,
        source: LightSource,
        obstacles: set[tuple[int, int]],
        map_width: int,
        map_height: int,
    ) -> dict[tuple[int, int], LightingState]:
        """Calculate which tiles are lit by a light source.

        Args:
            source: The light source to calculate for
            obstacles: Set of (x, y) positions that block light
            map_width: Width of the map in tiles
            map_height: Height of the map in tiles

        Returns:
            Dict mapping (x, y) to LightingState for all lit tiles
        """
        pass


class SimpleLighting(LightingAlgorithm):
    """Simple radius-based lighting without shadow casting.

    This is the Phase 1 implementation that uses circular radii
    without considering obstacles. Good for initial development
    and testing.
    """

    def calculate_lit_tiles(
        self,
        source: LightSource,
        obstacles: set[tuple[int, int]],
        map_width: int,
        map_height: int,
    ) -> dict[tuple[int, int], LightingState]:
        """Calculate lit tiles using simple circular radius.

        Ignores obstacles - all tiles within radius are lit.
        """
        lit_tiles: dict[tuple[int, int], LightingState] = {}

        total_radius = source.total_radius

        # Check all tiles within the maximum radius
        for dx in range(-total_radius, total_radius + 1):
            for dy in range(-total_radius, total_radius + 1):
                x = source.x + dx
                y = source.y + dy

                # Skip out of bounds
                if x < 0 or x >= map_width or y < 0 or y >= map_height:
                    continue

                # Calculate distance (using Chebyshev distance for grid)
                distance = max(abs(dx), abs(dy))

                # Determine lighting state based on distance
                if distance <= source.bright_radius:
                    lit_tiles[(x, y)] = LightingState.BRIGHT
                elif distance <= total_radius:
                    lit_tiles[(x, y)] = LightingState.DIM

        return lit_tiles


class RaycastLighting(LightingAlgorithm):
    """Shadow-casting lighting using recursive shadowcasting algorithm.

    This is planned for Phase 5 to provide more realistic lighting
    that respects walls and obstacles.
    """

    def calculate_lit_tiles(
        self,
        source: LightSource,
        obstacles: set[tuple[int, int]],
        map_width: int,
        map_height: int,
    ) -> dict[tuple[int, int], LightingState]:
        """Calculate lit tiles using recursive shadowcasting.

        This algorithm casts rays from the light source and stops at obstacles.
        """
        # For Phase 5 - implement recursive shadowcasting
        # For now, fall back to simple lighting
        simple = SimpleLighting()
        return simple.calculate_lit_tiles(
            source, obstacles, map_width, map_height
        )


@dataclass
class LightingSystem:
    """Manages all light sources and calculates combined illumination.

    The lighting system:
    1. Tracks all active light sources
    2. Calculates illumination from each source
    3. Combines multiple sources (taking brightest)
    4. Provides the final lighting map for fog of war

    Attributes:
        map_width: Width of the map in tiles
        map_height: Height of the map in tiles
        algorithm: The lighting calculation algorithm to use
    """

    map_width: int
    map_height: int
    algorithm: LightingAlgorithm = None
    _light_sources: list[LightSource] = None
    _obstacles: set[tuple[int, int]] = None

    def __post_init__(self):
        """Initialize with default simple lighting algorithm."""
        if self.algorithm is None:
            self.algorithm = SimpleLighting()
        if self._light_sources is None:
            self._light_sources = []
        if self._obstacles is None:
            self._obstacles = set()

    def add_light_source(self, source: LightSource) -> None:
        """Add a light source to the system.

        Args:
            source: The light source to add
        """
        self._light_sources.append(source)

    def remove_light_source(self, source: LightSource) -> None:
        """Remove a light source from the system.

        Args:
            source: The light source to remove
        """
        if source in self._light_sources:
            self._light_sources.remove(source)

    def clear_light_sources(self) -> None:
        """Remove all light sources."""
        self._light_sources.clear()

    def set_obstacles(self, obstacles: set[tuple[int, int]]) -> None:
        """Set the obstacle positions that block light.

        Args:
            obstacles: Set of (x, y) positions that block light
        """
        self._obstacles = obstacles

    def add_obstacle(self, x: int, y: int) -> None:
        """Add a single obstacle position."""
        self._obstacles.add((x, y))

    def remove_obstacle(self, x: int, y: int) -> None:
        """Remove a single obstacle position."""
        self._obstacles.discard((x, y))

    def calculate_lighting(self) -> dict[tuple[int, int], LightingState]:
        """Calculate combined illumination from all light sources.

        Returns:
            Dict mapping (x, y) to LightingState for all lit tiles.
            Tiles not in the dict are considered dark/unlit.
        """
        combined: dict[tuple[int, int], LightingState] = {}

        for source in self._light_sources:
            source_lighting = self.algorithm.calculate_lit_tiles(
                source, self._obstacles, self.map_width, self.map_height
            )

            # Combine with existing lighting (take brightest)
            for pos, state in source_lighting.items():
                if pos not in combined or state.value > combined[pos].value:
                    combined[pos] = state

        return combined

    def get_light_at(self, x: int, y: int) -> LightingState:
        """Get the lighting state at a specific tile.

        Args:
            x: Tile X coordinate
            y: Tile Y coordinate

        Returns:
            LightingState for the tile (DARK if not lit by any source)
        """
        lighting = self.calculate_lighting()
        return lighting.get((x, y), LightingState.DARK)

    def update_party_lights(
        self,
        party_positions: list[tuple[int, int]],
        light_type: str = "torch",
    ) -> None:
        """Update light sources for party members.

        Clears existing party lights and creates new ones at party positions.

        Args:
            party_positions: List of (x, y) positions for party members
            light_type: Type of light source ("torch", "lantern", "light_spell")
        """
        # Remove existing torch/lantern sources (keep environmental lights)
        self._light_sources = [
            s
            for s in self._light_sources
            if s.source_type not in ("torch", "lantern", "light_spell")
        ]

        # Add new lights at party positions
        for x, y in party_positions:
            if light_type == "torch":
                self.add_light_source(LightSource.torch(x, y))
            elif light_type == "lantern":
                self.add_light_source(LightSource.lantern(x, y))
            elif light_type == "light_spell":
                self.add_light_source(LightSource.light_spell(x, y))

    @property
    def light_source_count(self) -> int:
        """Number of active light sources."""
        return len(self._light_sources)

    @property
    def light_sources(self) -> list[LightSource]:
        """List of active light sources."""
        return list(self._light_sources)
