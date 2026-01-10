# ABOUTME: Unit tests for the lighting system.
# ABOUTME: Tests light sources, illumination calculation, and D&D-compliant radii.

"""Tests for the LightingSystem and related classes."""

import pytest

from client_2d.core.constants import (
    LANTERN_BRIGHT_RADIUS,
    LANTERN_DIM_RADIUS,
    TORCH_BRIGHT_RADIUS,
    TORCH_DIM_RADIUS,
    LightingState,
)
from client_2d.systems.lighting import (
    LightingSystem,
    LightSource,
    SimpleLighting,
)


class TestLightSource:
    """Tests for LightSource dataclass."""

    def test_create_torch_light_source(self):
        """Torch should have correct D&D 5E radii."""
        torch = LightSource.torch(x=5, y=5)

        assert torch.x == 5
        assert torch.y == 5
        assert torch.bright_radius == TORCH_BRIGHT_RADIUS
        assert torch.dim_radius == TORCH_DIM_RADIUS
        assert torch.source_type == "torch"

    def test_create_lantern_light_source(self):
        """Lantern should have correct D&D 5E radii."""
        lantern = LightSource.lantern(x=10, y=10)

        assert lantern.bright_radius == LANTERN_BRIGHT_RADIUS
        assert lantern.dim_radius == LANTERN_DIM_RADIUS
        assert lantern.source_type == "lantern"

    def test_create_light_spell(self):
        """Light cantrip should have correct radii."""
        light = LightSource.light_spell(x=3, y=3)

        assert light.source_type == "light_spell"
        # Light cantrip has same range as torch
        assert light.bright_radius == 4
        assert light.dim_radius == 4

    def test_total_radius_calculation(self):
        """Total radius should be bright + dim."""
        torch = LightSource.torch(x=5, y=5)

        assert torch.total_radius == torch.bright_radius + torch.dim_radius
        assert torch.total_radius == 8  # 4 + 4 for torch


class TestSimpleLighting:
    """Tests for SimpleLighting algorithm."""

    def test_center_tile_is_bright(self):
        """The light source tile itself should be bright."""
        algorithm = SimpleLighting()
        source = LightSource.torch(x=10, y=10)

        lit_tiles = algorithm.calculate_lit_tiles(
            source, obstacles=set(), map_width=20, map_height=20
        )

        assert lit_tiles[(10, 10)] == LightingState.BRIGHT

    def test_tiles_within_bright_radius_are_bright(self):
        """Tiles within bright radius should be BRIGHT."""
        algorithm = SimpleLighting()
        source = LightSource.torch(x=10, y=10)  # bright_radius = 4

        lit_tiles = algorithm.calculate_lit_tiles(
            source, obstacles=set(), map_width=20, map_height=20
        )

        # Check cardinal directions within bright radius
        assert lit_tiles[(10, 6)] == LightingState.BRIGHT  # 4 tiles north
        assert lit_tiles[(14, 10)] == LightingState.BRIGHT  # 4 tiles east
        assert lit_tiles[(10, 14)] == LightingState.BRIGHT  # 4 tiles south
        assert lit_tiles[(6, 10)] == LightingState.BRIGHT  # 4 tiles west

    def test_tiles_in_dim_radius_are_dim(self):
        """Tiles in dim radius (beyond bright) should be DIM."""
        algorithm = SimpleLighting()
        source = LightSource.torch(x=10, y=10)  # dim starts at 5 tiles

        lit_tiles = algorithm.calculate_lit_tiles(
            source, obstacles=set(), map_width=20, map_height=20
        )

        # 5 tiles away is dim (beyond 4 tile bright radius)
        assert lit_tiles[(10, 5)] == LightingState.DIM
        assert lit_tiles[(15, 10)] == LightingState.DIM

    def test_tiles_beyond_total_radius_not_lit(self):
        """Tiles beyond total radius should not be in result."""
        algorithm = SimpleLighting()
        source = LightSource.torch(x=10, y=10)  # total_radius = 8

        lit_tiles = algorithm.calculate_lit_tiles(
            source, obstacles=set(), map_width=20, map_height=20
        )

        # 9 tiles away is beyond total radius
        assert (10, 1) not in lit_tiles
        assert (19, 10) not in lit_tiles

    def test_respects_map_bounds(self):
        """Light should not extend beyond map boundaries."""
        algorithm = SimpleLighting()
        source = LightSource.torch(x=2, y=2)

        lit_tiles = algorithm.calculate_lit_tiles(
            source, obstacles=set(), map_width=10, map_height=10
        )

        # No negative coordinates
        assert all(x >= 0 and y >= 0 for x, y in lit_tiles.keys())
        # No coordinates beyond map
        assert all(x < 10 and y < 10 for x, y in lit_tiles.keys())


class TestLightingSystem:
    """Tests for the LightingSystem manager."""

    def test_create_empty_system(self):
        """System should start with no light sources."""
        system = LightingSystem(map_width=20, map_height=20)

        assert system.light_source_count == 0

    def test_add_light_source(self):
        """Adding a light source should increase count."""
        system = LightingSystem(map_width=20, map_height=20)

        system.add_light_source(LightSource.torch(x=10, y=10))

        assert system.light_source_count == 1

    def test_remove_light_source(self):
        """Removing a light source should decrease count."""
        system = LightingSystem(map_width=20, map_height=20)
        torch = LightSource.torch(x=10, y=10)

        system.add_light_source(torch)
        system.remove_light_source(torch)

        assert system.light_source_count == 0

    def test_clear_light_sources(self):
        """Clearing should remove all light sources."""
        system = LightingSystem(map_width=20, map_height=20)
        system.add_light_source(LightSource.torch(x=5, y=5))
        system.add_light_source(LightSource.torch(x=15, y=15))

        system.clear_light_sources()

        assert system.light_source_count == 0

    def test_calculate_lighting_with_single_source(self):
        """Single source should produce expected lighting."""
        system = LightingSystem(map_width=20, map_height=20)
        system.add_light_source(LightSource.torch(x=10, y=10))

        lighting = system.calculate_lighting()

        assert lighting[(10, 10)] == LightingState.BRIGHT
        assert (10, 15) in lighting  # Within dim radius

    def test_calculate_lighting_combines_multiple_sources(self):
        """Multiple sources should be combined (brightest wins)."""
        system = LightingSystem(map_width=20, map_height=20)
        system.add_light_source(LightSource.torch(x=5, y=10))
        system.add_light_source(LightSource.torch(x=15, y=10))

        lighting = system.calculate_lighting()

        # Overlapping area should be bright or dim from either source
        assert (10, 10) in lighting

    def test_get_light_at_returns_correct_state(self):
        """get_light_at should return the lighting state for a tile."""
        system = LightingSystem(map_width=20, map_height=20)
        system.add_light_source(LightSource.torch(x=10, y=10))

        assert system.get_light_at(10, 10) == LightingState.BRIGHT
        assert system.get_light_at(0, 0) == LightingState.DARK

    def test_update_party_lights_replaces_party_sources(self):
        """update_party_lights should replace existing party lights."""
        system = LightingSystem(map_width=20, map_height=20)
        system.add_light_source(LightSource.torch(x=5, y=5))

        system.update_party_lights([(10, 10), (12, 12)])

        # Should now have 2 torches at new positions
        assert system.light_source_count == 2
        positions = {(s.x, s.y) for s in system.light_sources}
        assert (10, 10) in positions
        assert (12, 12) in positions
        assert (5, 5) not in positions

    def test_update_party_lights_with_lantern(self):
        """update_party_lights should create lanterns when specified."""
        system = LightingSystem(map_width=20, map_height=20)

        system.update_party_lights([(10, 10)], light_type="lantern")

        assert system.light_sources[0].source_type == "lantern"
        assert system.light_sources[0].bright_radius == LANTERN_BRIGHT_RADIUS


class TestLightingSystemObstacles:
    """Tests for obstacle handling in lighting system."""

    def test_add_obstacle(self):
        """Adding obstacles should be tracked."""
        system = LightingSystem(map_width=20, map_height=20)

        system.add_obstacle(5, 5)
        system.add_obstacle(6, 5)

        # Obstacles don't affect SimpleLighting but are tracked
        # for future RaycastLighting
        assert (5, 5) in system._obstacles
        assert (6, 5) in system._obstacles

    def test_remove_obstacle(self):
        """Removing obstacles should work."""
        system = LightingSystem(map_width=20, map_height=20)
        system.add_obstacle(5, 5)

        system.remove_obstacle(5, 5)

        assert (5, 5) not in system._obstacles

    def test_set_obstacles(self):
        """Setting obstacles should replace existing ones."""
        system = LightingSystem(map_width=20, map_height=20)
        system.add_obstacle(5, 5)

        system.set_obstacles({(10, 10), (11, 10)})

        assert (5, 5) not in system._obstacles
        assert (10, 10) in system._obstacles


class TestLightingIntegration:
    """Integration tests for lighting with fog of war."""

    def test_torch_illumination_pattern(self):
        """Verify torch creates correct D&D 5E illumination pattern."""
        system = LightingSystem(map_width=30, map_height=30)
        # Place torch at center
        system.add_light_source(LightSource.torch(x=15, y=15))

        lighting = system.calculate_lighting()

        # Bright light: 20ft = 4 tiles in each direction
        # At distance 4 (Chebyshev), should be bright
        assert lighting[(15, 11)] == LightingState.BRIGHT  # 4 tiles north
        assert lighting[(19, 15)] == LightingState.BRIGHT  # 4 tiles east

        # Dim light: +20ft = additional 4 tiles
        # At distance 5-8 (Chebyshev), should be dim
        assert lighting[(15, 10)] == LightingState.DIM  # 5 tiles north
        assert lighting[(15, 7)] == LightingState.DIM  # 8 tiles north

        # Beyond 8 tiles: not lit
        assert (15, 6) not in lighting  # 9 tiles north

    def test_multiple_torches_overlap(self):
        """Overlapping torch light should take brightest."""
        system = LightingSystem(map_width=30, map_height=30)
        # Two torches 6 tiles apart
        system.add_light_source(LightSource.torch(x=10, y=15))
        system.add_light_source(LightSource.torch(x=16, y=15))

        lighting = system.calculate_lighting()

        # Midpoint at (13, 15) is 3 tiles from each torch
        # Should be BRIGHT (within 4 tile bright radius of both)
        assert lighting[(13, 15)] == LightingState.BRIGHT
