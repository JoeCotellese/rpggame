# ABOUTME: Integration tests for Phase 1 systems working together.
# ABOUTME: Tests fog of war + lighting + input as a cohesive navigation system.

"""Phase 1 integration tests for the 2D client systems."""

import tempfile
from pathlib import Path

import pytest
from client_2d.assets.asset_manager import AssetManager
from client_2d.core.constants import (
    Action,
    GameMode,
    LightingState,
)
from client_2d.input.input_handler import KEY_DOWN, KEY_RIGHT, KEY_UP, InputHandler
from client_2d.systems.fog_of_war import FogOfWarSystem
from client_2d.systems.lighting import LightingSystem, LightSource


class TestNavigationWithFogAndLighting:
    """Tests for navigation updating fog and lighting together."""

    def setup_method(self):
        """Set up test fixtures."""
        self.map_width = 20
        self.map_height = 20
        self.fog = FogOfWarSystem(width=self.map_width, height=self.map_height)
        self.lighting = LightingSystem(
            map_width=self.map_width, map_height=self.map_height
        )
        self.input_handler = InputHandler(current_mode=GameMode.EXPLORATION)

        # Starting position
        self.player_x = 10
        self.player_y = 10

    def _update_lighting_and_fog(self):
        """Simulate the render loop update cycle."""
        # Clear old lighting
        self.fog.reset_to_dark()

        # Update party torch position
        self.lighting.update_party_lights([(self.player_x, self.player_y)])

        # Calculate new lighting
        lit_tiles = self.lighting.calculate_lighting()

        # Apply to fog of war
        self.fog.apply_lighting(lit_tiles)

    def _handle_movement(self, key: int) -> bool:
        """Process a movement key press, returns True if moved."""
        action = self.input_handler.handle_key_press(key)
        if action is None:
            return False

        direction = self.input_handler.get_direction_from_action(action)
        if direction is None:
            return False

        dx, dy = direction.delta
        new_x = self.player_x + dx
        new_y = self.player_y + dy

        # Bounds check
        if 0 <= new_x < self.map_width and 0 <= new_y < self.map_height:
            self.player_x = new_x
            self.player_y = new_y
            self._update_lighting_and_fog()
            return True

        return False

    def test_initial_position_is_lit(self):
        """Player's starting position should be fully lit."""
        self._update_lighting_and_fog()

        assert self.fog.get_visibility(10, 10) == LightingState.BRIGHT

    def test_torch_radius_reveals_tiles(self):
        """Torch should reveal tiles within its radius."""
        self._update_lighting_and_fog()

        # Tiles within bright radius should be bright
        assert self.fog.get_visibility(10, 6) == LightingState.BRIGHT  # 4 north
        assert self.fog.get_visibility(14, 10) == LightingState.BRIGHT  # 4 east

        # Tiles in dim radius should be dim
        assert self.fog.get_visibility(10, 5) == LightingState.DIM  # 5 north

    def test_movement_updates_lighting(self):
        """Moving should update which tiles are lit."""
        self._update_lighting_and_fog()

        # Move north
        self._handle_movement(KEY_UP)

        # New position should be bright
        assert self.fog.get_visibility(10, 9) == LightingState.BRIGHT

        # Old position should still be visible (explored)
        assert self.fog.is_explored(10, 10)

    def test_explored_tiles_remain_visible(self):
        """Tiles that were explored should remain as DARK when not lit."""
        self._update_lighting_and_fog()

        # Move far enough that starting position is out of torch range
        for _ in range(10):  # Move 10 tiles north
            self._handle_movement(KEY_UP)

        # Original position should still be explored (now dark, not unexplored)
        assert self.fog.is_explored(10, 10)
        assert self.fog.get_visibility(10, 10) == LightingState.DARK

    def test_unexplored_tiles_stay_unexplored(self):
        """Tiles that were never lit should remain unexplored."""
        self._update_lighting_and_fog()

        # Far corner should be unexplored
        assert self.fog.get_visibility(0, 0) == LightingState.UNEXPLORED
        assert not self.fog.is_explored(0, 0)

    def test_full_room_exploration(self):
        """Simulate exploring an entire room."""
        # Start at one corner
        self.player_x = 2
        self.player_y = 2
        self._update_lighting_and_fog()

        # Move across the room
        positions_visited = [(self.player_x, self.player_y)]

        # Move right across the room
        for _ in range(15):
            if self._handle_movement(KEY_RIGHT):
                positions_visited.append((self.player_x, self.player_y))

        # Move down
        for _ in range(15):
            if self._handle_movement(KEY_DOWN):
                positions_visited.append((self.player_x, self.player_y))

        # All visited positions should be explored
        for x, y in positions_visited:
            assert self.fog.is_explored(x, y)


class TestLightingWithMultipleSources:
    """Tests for multiple light sources interacting."""

    def test_overlapping_lights_take_brightest(self):
        """When lights overlap, the brightest state wins."""
        fog = FogOfWarSystem(width=30, height=30)
        lighting = LightingSystem(map_width=30, map_height=30)

        # Two torches 6 tiles apart
        lighting.add_light_source(LightSource.torch(x=10, y=15))
        lighting.add_light_source(LightSource.torch(x=16, y=15))

        lit_tiles = lighting.calculate_lighting()
        fog.apply_lighting(lit_tiles)

        # Midpoint at (13, 15) is 3 tiles from each torch
        # Should be BRIGHT (within both torches' bright radius)
        assert fog.get_visibility(13, 15) == LightingState.BRIGHT

    def test_light_sources_can_be_removed(self):
        """Removing light sources should update illumination."""
        fog = FogOfWarSystem(width=20, height=20)
        lighting = LightingSystem(map_width=20, map_height=20)

        torch1 = LightSource.torch(x=10, y=10)
        torch2 = LightSource.torch(x=10, y=5)

        lighting.add_light_source(torch1)
        lighting.add_light_source(torch2)

        # Initial state
        lit_tiles = lighting.calculate_lighting()
        fog.apply_lighting(lit_tiles)
        assert fog.get_visibility(10, 10) == LightingState.BRIGHT

        # Remove first torch and reset
        lighting.remove_light_source(torch1)
        fog.reset_to_dark()
        lit_tiles = lighting.calculate_lighting()
        fog.apply_lighting(lit_tiles)

        # Position 10,10 is now 5 tiles from torch2, so DIM
        assert fog.get_visibility(10, 10) == LightingState.DIM


class TestInputModeTransitions:
    """Tests for input mode affecting gameplay."""

    def test_exploration_to_combat_disables_movement(self):
        """Switching to combat mode should disable movement keys."""
        handler = InputHandler(current_mode=GameMode.EXPLORATION)

        # Movement works in exploration
        assert handler.handle_key_press(KEY_UP) == Action.MOVE_NORTH

        # Switch to combat
        handler.set_mode(GameMode.COMBAT)

        # Movement disabled
        assert handler.handle_key_press(KEY_UP) is None

    def test_combat_to_exploration_enables_movement(self):
        """Switching back to exploration should re-enable movement."""
        handler = InputHandler(current_mode=GameMode.COMBAT)

        # Movement disabled in combat
        assert handler.handle_key_press(KEY_UP) is None

        # Switch to exploration
        handler.set_mode(GameMode.EXPLORATION)

        # Movement works again
        assert handler.handle_key_press(KEY_UP) == Action.MOVE_NORTH


class TestAssetResolutionIntegration:
    """Tests for asset resolution in gameplay scenarios."""

    @pytest.fixture
    def game_assets(self):
        """Create a temporary assets directory with game assets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assets_path = Path(tmpdir)

            # Create creature sprites with fallbacks
            (assets_path / "sprites" / "monsters" / "undead").mkdir(parents=True)
            (assets_path / "sprites" / "monsters" / "humanoid").mkdir(parents=True)
            (assets_path / "sprites" / "characters").mkdir(parents=True)
            (assets_path / "tilesets").mkdir(parents=True)
            (assets_path / "maps").mkdir(parents=True)
            (assets_path / "ui").mkdir(parents=True)

            # Specific sprites
            (assets_path / "sprites" / "monsters" / "undead" / "skeleton.png").touch()
            (assets_path / "sprites" / "monsters" / "humanoid" / "goblin.png").touch()
            (assets_path / "sprites" / "characters" / "fighter.png").touch()

            # Fallbacks
            (assets_path / "sprites" / "monsters" / "undead" / "_fallback.png").touch()
            (assets_path / "sprites" / "monsters" / "_fallback_generic.png").touch()
            (assets_path / "sprites" / "characters" / "_fallback_humanoid.png").touch()

            yield assets_path

    def test_resolve_known_monster(self, game_assets):
        """Should find exact sprite for known monster."""
        manager = AssetManager(assets_path=game_assets)

        path = manager.get_monster_sprite_path("skeleton", "undead")

        assert path is not None
        assert path.name == "skeleton.png"

    def test_resolve_unknown_monster_with_type_fallback(self, game_assets):
        """Should use type fallback for unknown monster with known type."""
        manager = AssetManager(assets_path=game_assets)

        path = manager.get_monster_sprite_path("zombie", "undead")

        assert path is not None
        assert path.name == "_fallback.png"

    def test_resolve_completely_unknown_monster(self, game_assets):
        """Should use generic fallback for completely unknown monster."""
        manager = AssetManager(assets_path=game_assets)

        path = manager.get_monster_sprite_path("dragon", "dragon")

        assert path is not None
        assert path.name == "_fallback_generic.png"

    def test_track_all_missing_assets(self, game_assets):
        """Should track all assets that couldn't be resolved."""
        # Remove generic fallback
        (game_assets / "sprites" / "monsters" / "_fallback_generic.png").unlink()

        manager = AssetManager(assets_path=game_assets)

        # Try to resolve several missing assets
        manager.get_monster_sprite_path("dragon", "dragon")
        manager.get_tileset_path("cave")
        manager.get_map_path("forest", "clearing")

        missing = manager.get_missing_assets()

        assert "monster:dragon:dragon" in missing
        assert "tileset:cave" in missing
        assert "map:forest:clearing" in missing


class TestDDLightingCompliance:
    """Tests verifying D&D 5E lighting rules are followed."""

    def test_torch_20ft_bright_light(self):
        """Torch should produce 20ft (4 tiles) of bright light."""
        lighting = LightingSystem(map_width=30, map_height=30)
        lighting.add_light_source(LightSource.torch(x=15, y=15))

        lit = lighting.calculate_lighting()

        # 4 tiles in each direction should be bright
        assert lit[(15, 11)] == LightingState.BRIGHT  # 4 north
        assert lit[(19, 15)] == LightingState.BRIGHT  # 4 east
        assert lit[(15, 19)] == LightingState.BRIGHT  # 4 south
        assert lit[(11, 15)] == LightingState.BRIGHT  # 4 west

    def test_torch_40ft_total_dim_light(self):
        """Torch should produce dim light from 20-40ft (4-8 tiles)."""
        lighting = LightingSystem(map_width=30, map_height=30)
        lighting.add_light_source(LightSource.torch(x=15, y=15))

        lit = lighting.calculate_lighting()

        # 5-8 tiles should be dim
        assert lit[(15, 10)] == LightingState.DIM  # 5 north
        assert lit[(15, 7)] == LightingState.DIM  # 8 north

        # Beyond 8 tiles should not be lit
        assert (15, 6) not in lit  # 9 north

    def test_lantern_30ft_bright_light(self):
        """Lantern should produce 30ft (6 tiles) of bright light."""
        lighting = LightingSystem(map_width=30, map_height=30)
        lighting.add_light_source(LightSource.lantern(x=15, y=15))

        lit = lighting.calculate_lighting()

        # 6 tiles should be bright
        assert lit[(15, 9)] == LightingState.BRIGHT  # 6 north
        assert lit[(21, 15)] == LightingState.BRIGHT  # 6 east

    def test_lantern_60ft_total_dim_light(self):
        """Lantern should produce dim light from 30-60ft (6-12 tiles)."""
        lighting = LightingSystem(map_width=30, map_height=30)
        lighting.add_light_source(LightSource.lantern(x=15, y=15))

        lit = lighting.calculate_lighting()

        # 7-12 tiles should be dim
        assert lit[(15, 8)] == LightingState.DIM  # 7 north
        assert lit[(15, 3)] == LightingState.DIM  # 12 north

        # Beyond 12 tiles should not be lit
        assert (15, 2) not in lit  # 13 north
