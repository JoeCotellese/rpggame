# ABOUTME: Unit tests for the fog of war system.
# ABOUTME: Tests visibility states, exploration tracking, and lighting integration.

"""Tests for the FogOfWarSystem."""

import pytest

from client_2d.core.constants import LightingState
from client_2d.systems.fog_of_war import FogOfWarSystem


class TestFogOfWarSystemInitialization:
    """Tests for FogOfWarSystem initialization."""

    def test_creates_with_correct_dimensions(self):
        """FogOfWarSystem should create a grid of the specified size."""
        fog = FogOfWarSystem(width=10, height=8)

        assert fog.width == 10
        assert fog.height == 8
        assert fog.total_tiles == 80

    def test_all_tiles_start_unexplored(self):
        """All tiles should start in UNEXPLORED state."""
        fog = FogOfWarSystem(width=5, height=5)

        for x in range(5):
            for y in range(5):
                assert fog.get_visibility(x, y) == LightingState.UNEXPLORED

    def test_explored_count_starts_at_zero(self):
        """No tiles should be explored initially."""
        fog = FogOfWarSystem(width=10, height=10)

        assert fog.explored_count == 0


class TestFogOfWarVisibility:
    """Tests for visibility state management."""

    def test_set_visibility_changes_state(self):
        """Setting visibility should change the tile state."""
        fog = FogOfWarSystem(width=10, height=10)

        fog.set_visibility(5, 5, LightingState.BRIGHT)

        assert fog.get_visibility(5, 5) == LightingState.BRIGHT

    def test_set_visibility_out_of_bounds_is_safe(self):
        """Setting visibility for out-of-bounds coords should be ignored."""
        fog = FogOfWarSystem(width=10, height=10)

        # Should not raise
        fog.set_visibility(-1, 5, LightingState.BRIGHT)
        fog.set_visibility(5, -1, LightingState.BRIGHT)
        fog.set_visibility(10, 5, LightingState.BRIGHT)
        fog.set_visibility(5, 10, LightingState.BRIGHT)

    def test_get_visibility_out_of_bounds_returns_unexplored(self):
        """Getting visibility for out-of-bounds coords returns UNEXPLORED."""
        fog = FogOfWarSystem(width=10, height=10)

        assert fog.get_visibility(-1, 5) == LightingState.UNEXPLORED
        assert fog.get_visibility(10, 5) == LightingState.UNEXPLORED
        assert fog.get_visibility(5, -1) == LightingState.UNEXPLORED
        assert fog.get_visibility(5, 10) == LightingState.UNEXPLORED

    def test_reveal_tile_sets_minimum_dark(self):
        """Revealing a tile should set it to at least DARK."""
        fog = FogOfWarSystem(width=10, height=10)

        fog.reveal_tile(5, 5)

        assert fog.get_visibility(5, 5) == LightingState.DARK
        assert fog.is_explored(5, 5)

    def test_reveal_tile_tracks_exploration(self):
        """Revealing tiles should increment explored count."""
        fog = FogOfWarSystem(width=10, height=10)

        fog.reveal_tile(5, 5)
        fog.reveal_tile(6, 5)
        fog.reveal_tile(5, 6)

        assert fog.explored_count == 3


class TestFogOfWarExploration:
    """Tests for exploration tracking."""

    def test_is_explored_returns_false_for_new_tiles(self):
        """Unexplored tiles should return False for is_explored."""
        fog = FogOfWarSystem(width=10, height=10)

        assert fog.is_explored(5, 5) is False

    def test_is_explored_returns_true_after_reveal(self):
        """Revealed tiles should return True for is_explored."""
        fog = FogOfWarSystem(width=10, height=10)

        fog.reveal_tile(5, 5)

        assert fog.is_explored(5, 5) is True

    def test_set_visibility_marks_as_explored(self):
        """Setting any non-UNEXPLORED state marks tile as explored."""
        fog = FogOfWarSystem(width=10, height=10)

        fog.set_visibility(5, 5, LightingState.DIM)

        assert fog.is_explored(5, 5) is True

    def test_explored_tiles_persist_after_reset_to_dark(self):
        """Explored tiles should remain explored after reset."""
        fog = FogOfWarSystem(width=10, height=10)

        fog.set_visibility(5, 5, LightingState.BRIGHT)
        fog.reset_to_dark()

        assert fog.is_explored(5, 5) is True
        assert fog.get_visibility(5, 5) == LightingState.DARK


class TestFogOfWarLightingIntegration:
    """Tests for lighting system integration."""

    def test_reset_to_dark_sets_explored_tiles_to_dark(self):
        """Reset should set all explored tiles to DARK."""
        fog = FogOfWarSystem(width=10, height=10)

        # Explore and light some tiles
        fog.set_visibility(5, 5, LightingState.BRIGHT)
        fog.set_visibility(6, 5, LightingState.DIM)
        fog.set_visibility(7, 5, LightingState.BRIGHT)

        fog.reset_to_dark()

        assert fog.get_visibility(5, 5) == LightingState.DARK
        assert fog.get_visibility(6, 5) == LightingState.DARK
        assert fog.get_visibility(7, 5) == LightingState.DARK

    def test_reset_to_dark_leaves_unexplored_unchanged(self):
        """Reset should not change unexplored tiles."""
        fog = FogOfWarSystem(width=10, height=10)

        fog.set_visibility(5, 5, LightingState.BRIGHT)
        fog.reset_to_dark()

        # Unexplored tile should still be unexplored
        assert fog.get_visibility(0, 0) == LightingState.UNEXPLORED

    def test_apply_lighting_updates_tile_states(self):
        """Applying lighting should update tile states."""
        fog = FogOfWarSystem(width=10, height=10)

        lighting = {
            (5, 5): LightingState.BRIGHT,
            (5, 6): LightingState.DIM,
            (5, 7): LightingState.DIM,
        }
        fog.apply_lighting(lighting)

        assert fog.get_visibility(5, 5) == LightingState.BRIGHT
        assert fog.get_visibility(5, 6) == LightingState.DIM
        assert fog.get_visibility(5, 7) == LightingState.DIM

    def test_apply_lighting_takes_brightest_state(self):
        """Applying lighting should take the brightest state."""
        fog = FogOfWarSystem(width=10, height=10)

        # Set initial dim state
        fog.set_visibility(5, 5, LightingState.DIM)

        # Apply brighter lighting
        fog.apply_lighting({(5, 5): LightingState.BRIGHT})

        assert fog.get_visibility(5, 5) == LightingState.BRIGHT

    def test_apply_lighting_does_not_downgrade(self):
        """Applying dimmer lighting should not downgrade state."""
        fog = FogOfWarSystem(width=10, height=10)

        # Set initial bright state
        fog.set_visibility(5, 5, LightingState.BRIGHT)

        # Apply dimmer lighting (should be ignored)
        fog.apply_lighting({(5, 5): LightingState.DIM})

        assert fog.get_visibility(5, 5) == LightingState.BRIGHT

    def test_apply_lighting_marks_tiles_explored(self):
        """Applying lighting should mark tiles as explored."""
        fog = FogOfWarSystem(width=10, height=10)

        fog.apply_lighting({(5, 5): LightingState.DIM})

        assert fog.is_explored(5, 5) is True


class TestFogOfWarQueries:
    """Tests for querying fog state."""

    def test_get_all_visible_tiles_returns_explored(self):
        """get_all_visible_tiles should return all explored tiles."""
        fog = FogOfWarSystem(width=10, height=10)

        fog.set_visibility(5, 5, LightingState.BRIGHT)
        fog.set_visibility(6, 5, LightingState.DIM)
        fog.set_visibility(7, 5, LightingState.DARK)

        visible = fog.get_all_visible_tiles()

        # Check all three tiles are returned
        positions = {(x, y) for x, y, _ in visible}
        assert (5, 5) in positions
        assert (6, 5) in positions
        assert (7, 5) in positions

    def test_get_tiles_in_state_filters_correctly(self):
        """get_tiles_in_state should return only matching tiles."""
        fog = FogOfWarSystem(width=10, height=10)

        fog.set_visibility(5, 5, LightingState.BRIGHT)
        fog.set_visibility(6, 5, LightingState.BRIGHT)
        fog.set_visibility(7, 5, LightingState.DIM)

        bright_tiles = fog.get_tiles_in_state(LightingState.BRIGHT)

        assert len(bright_tiles) == 2
        assert (5, 5) in bright_tiles
        assert (6, 5) in bright_tiles
        assert (7, 5) not in bright_tiles
