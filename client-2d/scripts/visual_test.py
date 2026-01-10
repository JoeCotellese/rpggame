#!/usr/bin/env python3
# ABOUTME: Simple visual demo of the 2D client fog of war and lighting systems.
# ABOUTME: Run with: python scripts/visual_test.py

"""Visual test demo for Phase 1 systems.

Usage:
    cd client-2d
    uv pip install -e ".[graphics]"
    python scripts/visual_test.py

Controls:
    WASD / Arrow keys: Move player
    L: Toggle lantern (brighter light)
    ESC: Quit
"""

import sys
from pathlib import Path

import arcade

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from client_2d.core.constants import TILE_SIZE, GameMode, LightingState
from client_2d.input.input_handler import InputHandler
from client_2d.systems.fog_of_war import FogOfWarSystem
from client_2d.systems.lighting import LightingSystem

# Window settings
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
WINDOW_TITLE = "D&D 2D Client - Phase 1 Demo"

# Map settings (in tiles)
MAP_WIDTH = 20
MAP_HEIGHT = 15

# Colors for rendering
COLORS = {
    LightingState.UNEXPLORED: arcade.color.BLACK,
    LightingState.DARK: (30, 30, 40, 200),  # Dark blue-gray, semi-transparent
    LightingState.DIM: (60, 60, 80, 150),   # Lighter, more transparent
    LightingState.BRIGHT: None,              # No overlay
}

FLOOR_COLOR = (64, 64, 64)
WALL_COLOR = (32, 32, 32)
PLAYER_COLOR = (70, 130, 180)  # Steel blue


class DemoGame(arcade.Window):
    """Simple demo window for testing fog of war and lighting."""

    def __init__(self):
        super().__init__(WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE)
        arcade.set_background_color(arcade.color.BLACK)

        # Player position (in tiles)
        self.player_x = MAP_WIDTH // 2
        self.player_y = MAP_HEIGHT // 2

        # Light type toggle
        self.use_lantern = False

        # Initialize systems
        self.fog = FogOfWarSystem(width=MAP_WIDTH, height=MAP_HEIGHT)
        self.lighting = LightingSystem(map_width=MAP_WIDTH, map_height=MAP_HEIGHT)
        self.input_handler = InputHandler(current_mode=GameMode.EXPLORATION)

        # Simple room layout (1 = wall, 0 = floor)
        self.room = self._create_room()

        # Set walls as obstacles for lighting
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                if self.room[y][x] == 1:
                    self.lighting.add_obstacle(x, y)

        # Initial lighting update
        self._update_lighting()

    def _create_room(self) -> list[list[int]]:
        """Create a simple room with walls around the border and some interior walls."""
        room = [[0 for _ in range(MAP_WIDTH)] for _ in range(MAP_HEIGHT)]

        # Border walls
        for x in range(MAP_WIDTH):
            room[0][x] = 1
            room[MAP_HEIGHT - 1][x] = 1
        for y in range(MAP_HEIGHT):
            room[y][0] = 1
            room[y][MAP_WIDTH - 1] = 1

        # Some interior walls for interest
        for y in range(3, 8):
            room[y][5] = 1
        for x in range(10, 15):
            room[7][x] = 1
        for y in range(10, 13):
            room[y][12] = 1

        return room

    def _update_lighting(self):
        """Recalculate lighting based on player position."""
        # Reset fog to dark for explored tiles
        self.fog.reset_to_dark()

        # Update party light at player position
        light_type = "lantern" if self.use_lantern else "torch"
        self.lighting.update_party_lights([(self.player_x, self.player_y)], light_type)

        # Calculate lighting
        lit_tiles = self.lighting.calculate_lighting()

        # Apply to fog of war
        self.fog.apply_lighting(lit_tiles)

    def _draw_rect(self, x: float, y: float, width: float, height: float, color):
        """Draw a filled rectangle (Arcade 3.x compatible)."""
        rect = arcade.LBWH(x, y, width, height)
        arcade.draw_rect_filled(rect, color)

    def _draw_rect_centered(self, cx: float, cy: float, width: float, height: float, color):
        """Draw a filled rectangle centered at cx, cy."""
        rect = arcade.XYWH(cx, cy, width, height)
        arcade.draw_rect_filled(rect, color)

    def on_draw(self):
        """Render the game."""
        self.clear()

        # Calculate offset to center the map
        offset_x = (WINDOW_WIDTH - MAP_WIDTH * TILE_SIZE) // 2
        offset_y = (WINDOW_HEIGHT - MAP_HEIGHT * TILE_SIZE) // 2

        # Draw floor and walls
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                screen_x = offset_x + x * TILE_SIZE
                screen_y = offset_y + (MAP_HEIGHT - 1 - y) * TILE_SIZE  # Flip Y

                color = WALL_COLOR if self.room[y][x] == 1 else FLOOR_COLOR
                self._draw_rect(screen_x, screen_y, TILE_SIZE - 1, TILE_SIZE - 1, color)

        # Draw player
        player_screen_x = offset_x + self.player_x * TILE_SIZE + TILE_SIZE // 2
        player_screen_y = offset_y + (MAP_HEIGHT - 1 - self.player_y) * TILE_SIZE + TILE_SIZE // 2
        self._draw_rect_centered(
            player_screen_x,
            player_screen_y,
            TILE_SIZE - 4,
            TILE_SIZE - 4,
            PLAYER_COLOR,
        )

        # Draw light indicator on player
        light_color = arcade.color.YELLOW if self.use_lantern else arcade.color.ORANGE
        arcade.draw_circle_filled(
            player_screen_x,
            player_screen_y,
            6,
            light_color,
        )

        # Draw fog of war overlay
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                state = self.fog.get_visibility(x, y)
                color = COLORS.get(state)

                if color is not None:
                    screen_x = offset_x + x * TILE_SIZE
                    screen_y = offset_y + (MAP_HEIGHT - 1 - y) * TILE_SIZE

                    self._draw_rect(screen_x, screen_y, TILE_SIZE, TILE_SIZE, color)

        # Draw UI text
        light_name = "Lantern (30ft)" if self.use_lantern else "Torch (20ft)"
        arcade.draw_text(
            f"Light: {light_name}  |  Press L to toggle  |  WASD/Arrows to move  |  ESC to quit",
            10,
            WINDOW_HEIGHT - 25,
            arcade.color.WHITE,
            14,
        )

        explored_pct = (self.fog.explored_count / self.fog.total_tiles) * 100
        arcade.draw_text(
            f"Explored: {self.fog.explored_count}/{self.fog.total_tiles} tiles ({explored_pct:.1f}%)",
            10,
            WINDOW_HEIGHT - 45,
            arcade.color.LIGHT_GRAY,
            12,
        )

    def on_key_press(self, key: int, modifiers: int):
        """Handle key press."""
        # Check for quit
        if key == arcade.key.ESCAPE:
            arcade.close_window()
            return

        # Check for light toggle
        if key == arcade.key.L:
            self.use_lantern = not self.use_lantern
            self._update_lighting()
            return

        # Handle movement
        action = self.input_handler.handle_key_press(key, modifiers)
        if action is None:
            return

        direction = self.input_handler.get_direction_from_action(action)
        if direction is None:
            return

        # Calculate new position
        dx, dy = direction.delta
        new_x = self.player_x + dx
        new_y = self.player_y + dy

        # Check bounds and walls
        if 0 <= new_x < MAP_WIDTH and 0 <= new_y < MAP_HEIGHT:
            if self.room[new_y][new_x] == 0:  # Not a wall
                self.player_x = new_x
                self.player_y = new_y
                self._update_lighting()


def main():
    """Run the demo."""
    print("Starting D&D 2D Client - Phase 1 Demo")
    print("Controls:")
    print("  WASD / Arrow keys: Move player")
    print("  L: Toggle between torch and lantern")
    print("  ESC: Quit")
    print()

    _game = DemoGame()  # Window registered with arcade
    arcade.run()


if __name__ == "__main__":
    main()
