#!/usr/bin/env python3
# ABOUTME: Visual demo of the 2D client with Stone Soup sprites.
# ABOUTME: Run with: python scripts/visual_test.py

"""Visual test demo with Stone Soup tile rendering.

Usage:
    cd client-2d
    uv pip install -e ".[graphics]"
    python scripts/visual_test.py

Controls:
    WASD / Arrow keys: Move player
    L: Cycle light mode (torch -> lantern -> light spell -> darkvision -> full bright)
    ESC: Quit
"""

import sys
from pathlib import Path

import arcade
from arcade.types import Color

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from client_2d.assets.asset_manager import AssetManager
from client_2d.core.constants import TILE_SIZE, GameMode, LightingState
from client_2d.input.input_handler import InputHandler
from client_2d.systems.fog_of_war import FogOfWarSystem
from client_2d.systems.lighting import LightingSystem

# Window settings
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 900
WINDOW_TITLE = "D&D 2D Client - Stone Soup Tiles Demo"

# Map settings (in tiles)
MAP_WIDTH = 40
MAP_HEIGHT = 28

# Light modes for cycling (name, light_type, description)
LIGHT_MODES = [
    ("torch", "torch", "Torch (20ft bright, 20ft dim)"),
    ("lantern", "lantern", "Lantern (30ft bright, 30ft dim)"),
    ("light_spell", "light_spell", "Light Spell (20ft bright, 20ft dim)"),
    ("darkvision", "darkvision", "Darkvision (60ft dim only)"),
    ("full_bright", "full_bright", "Full Bright (debug mode)"),
]

# Lighting tint colors (RGB multipliers as 0-255)
LIGHTING_TINTS = {
    LightingState.UNEXPLORED: None,  # Don't render
    LightingState.DARK: (60, 60, 80),  # Dark blue-gray (memory)
    LightingState.DIM: (160, 160, 180),  # Dimmed
    LightingState.BRIGHT: (255, 255, 255),  # Full brightness
}

# Assets directory
ASSETS_DIR = Path(__file__).parent.parent / "assets"


class DemoGame(arcade.Window):
    """Demo window with Stone Soup sprite rendering."""

    def __init__(self):
        super().__init__(WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE)
        arcade.set_background_color(arcade.color.BLACK)

        # Player position (in tiles)
        self.player_x = MAP_WIDTH // 2
        self.player_y = MAP_HEIGHT // 2

        # Light mode cycling
        self.light_mode_index = 0

        # Initialize asset manager
        self.assets = AssetManager(assets_path=ASSETS_DIR)

        # Load textures
        self._load_textures()

        # Entity positions (placed after room creation)
        self.entities: list[tuple[int, int, str, arcade.Texture | None]] = []

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

        # Place entities on the map
        self._place_entities()

        # Initial lighting update
        self._update_lighting()

    def _load_textures(self):
        """Load tile textures from Stone Soup assets."""
        # Floor and wall textures
        floor_path = self.assets.get_terrain_sprite_path("floor_stone")
        floor_crypt_path = self.assets.get_terrain_sprite_path("floor_crypt")
        wall_path = self.assets.get_terrain_sprite_path("wall_brick")
        door_closed_path = self.assets.get_terrain_sprite_path("door_closed")
        player_path = self.assets.get_character_sprite_path("fighter")

        # Load terrain textures
        self.floor_texture = self._try_load_texture(floor_path, "floor")
        self.floor_crypt_texture = self._try_load_texture(floor_crypt_path, "floor_crypt")
        self.wall_texture = self._try_load_texture(wall_path, "wall")
        self.door_texture = self._try_load_texture(door_closed_path, "door")
        self.player_texture = self._try_load_texture(player_path, "player")

        # Load monster textures (creature_id, creature_type pairs)
        self.monster_textures = {}
        monsters_to_load = [
            ("skeleton", "undead"),
            ("ghoul", "undead"),
            ("goblin", "humanoid"),
            ("wolf", "beast"),
            ("giant_rat", "beast"),
            ("cultist", "humanoid"),
        ]
        for monster_id, creature_type in monsters_to_load:
            path = self.assets.get_monster_sprite_path(monster_id, creature_type)
            texture = self._try_load_texture(path, f"monster:{monster_id}")
            if texture:
                self.monster_textures[monster_id] = texture

        # Load item textures (item_id, item_category pairs)
        self.item_textures = {}
        items_to_load = [
            ("longsword", "weapons"),
            ("potion_of_healing", "potions"),
            ("torch", "misc"),
            ("chain_mail", "armor"),
        ]
        for item_id, item_category in items_to_load:
            path = self.assets.get_item_sprite_path(item_id, item_category)
            texture = self._try_load_texture(path, f"item:{item_id}")
            if texture:
                self.item_textures[item_id] = texture

        # Load decoration textures
        self.decoration_textures = {}
        for deco_id in ["chest_closed", "bones"]:
            path = self.assets.get_decoration_sprite_path(deco_id)
            texture = self._try_load_texture(path, f"decoration:{deco_id}")
            if texture:
                self.decoration_textures[deco_id] = texture

    def _try_load_texture(
        self, path: Path | None, name: str
    ) -> arcade.Texture | None:
        """Try to load a texture, logging success or fallback."""
        if path and path.exists():
            print(f"Loaded {name}: {path.name}")
            return arcade.load_texture(str(path))
        else:
            print(f"Using fallback for {name}")
            return None

    def _create_room(self) -> list[list[int]]:
        """Create a multi-room dungeon layout."""
        room = [[0 for _ in range(MAP_WIDTH)] for _ in range(MAP_HEIGHT)]

        # Border walls
        for x in range(MAP_WIDTH):
            room[0][x] = 1
            room[MAP_HEIGHT - 1][x] = 1
        for y in range(MAP_HEIGHT):
            room[y][0] = 1
            room[y][MAP_WIDTH - 1] = 1

        # Vertical wall dividing left and right (with gaps)
        for y in range(1, MAP_HEIGHT - 1):
            if y not in [7, 8, 18, 19]:  # Leave doorways
                room[y][20] = 1

        # Horizontal wall in left area (with gap)
        for x in range(1, 20):
            if x not in [8, 9]:
                room[12][x] = 1

        # Create rooms in right area
        for y in range(1, 12):
            if y not in [5, 6]:
                room[y][30] = 1
        for x in range(21, 30):
            if x not in [25, 26]:
                room[12][x] = 1

        # Small chamber in bottom right
        for y in range(18, 24):
            room[y][30] = 1
        for x in range(30, 38):
            room[18][x] = 1

        # Pillars in the large left room
        for px, py in [(5, 4), (14, 4), (5, 9), (14, 9)]:
            room[py][px] = 1

        # L-shaped corridor walls
        for y in range(14, 20):
            room[y][10] = 1
        for x in range(10, 18):
            room[20][x] = 1

        return room

    def _place_entities(self):
        """Place monsters, items, and decorations on the map."""
        # Monsters in various locations
        monster_positions = [
            (6, 6, "skeleton"),
            (15, 3, "goblin"),
            (25, 5, "wolf"),
            (35, 22, "ghoul"),
            (12, 16, "giant_rat"),
            (32, 8, "cultist"),
            (8, 22, "skeleton"),
            (28, 18, "goblin"),
        ]
        for x, y, monster_id in monster_positions:
            texture = self.monster_textures.get(monster_id)
            self.entities.append((x, y, f"monster:{monster_id}", texture))

        # Items scattered around
        item_positions = [
            (4, 2, "longsword"),
            (18, 10, "potion_of_healing"),
            (33, 4, "torch"),
            (12, 24, "chain_mail"),
            (26, 20, "potion_of_healing"),
        ]
        for x, y, item_id in item_positions:
            texture = self.item_textures.get(item_id)
            self.entities.append((x, y, f"item:{item_id}", texture))

        # Decorations
        deco_positions = [
            (3, 8, "chest_closed"),
            (36, 2, "chest_closed"),
            (7, 17, "bones"),
            (24, 10, "bones"),
            (30, 25, "chest_closed"),
        ]
        for x, y, deco_id in deco_positions:
            texture = self.decoration_textures.get(deco_id)
            self.entities.append((x, y, f"deco:{deco_id}", texture))

    def _update_lighting(self):
        """Recalculate lighting based on player position and current light mode."""
        mode_name, light_type, _ = LIGHT_MODES[self.light_mode_index]

        # Reset fog to dark for explored tiles
        self.fog.reset_to_dark()

        if mode_name == "full_bright":
            # Full bright mode: everything visible at full brightness
            for y in range(MAP_HEIGHT):
                for x in range(MAP_WIDTH):
                    self.fog.set_visibility(x, y, LightingState.BRIGHT)
        elif mode_name == "darkvision":
            # Darkvision: 60ft (12 tiles) dim light, no bright
            from client_2d.systems.lighting import LightSource

            # Clear existing lights and add custom darkvision source
            self.lighting.clear_light_sources()
            dv_source = LightSource(
                x=self.player_x,
                y=self.player_y,
                bright_radius=0,
                dim_radius=12,
                source_type="darkvision",
            )
            self.lighting.add_light_source(dv_source)
            lit_tiles = self.lighting.calculate_lighting()
            self.fog.apply_lighting(lit_tiles)
        else:
            # Standard light types (torch, lantern, light_spell)
            self.lighting.update_party_lights(
                [(self.player_x, self.player_y)], light_type
            )
            lit_tiles = self.lighting.calculate_lighting()
            self.fog.apply_lighting(lit_tiles)

    def _draw_texture(
        self,
        texture: arcade.Texture,
        x: float,
        y: float,
        tint: tuple[int, int, int] | None = None,
    ):
        """Draw a texture at position with optional tint."""
        if tint:
            color = Color(*tint, 255)
        else:
            color = arcade.color.WHITE

        arcade.draw_texture_rect(
            texture,
            arcade.XYWH(x + TILE_SIZE / 2, y + TILE_SIZE / 2, TILE_SIZE, TILE_SIZE),
            color=color,
        )

    def _draw_rect(self, x: float, y: float, width: float, height: float, color):
        """Draw a filled rectangle (fallback)."""
        rect = arcade.LBWH(x, y, width, height)
        arcade.draw_rect_filled(rect, color)

    def on_draw(self):
        """Render the game."""
        self.clear()

        # Calculate offset to center the map
        offset_x = (WINDOW_WIDTH - MAP_WIDTH * TILE_SIZE) // 2
        offset_y = (WINDOW_HEIGHT - MAP_HEIGHT * TILE_SIZE) // 2

        # Draw floor and walls with lighting
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                screen_x = offset_x + x * TILE_SIZE
                screen_y = offset_y + (MAP_HEIGHT - 1 - y) * TILE_SIZE  # Flip Y

                # Get lighting state for tinting
                state = self.fog.get_visibility(x, y)
                tint = LIGHTING_TINTS.get(state)

                # Skip unexplored tiles (render black)
                if tint is None:
                    self._draw_rect(screen_x, screen_y, TILE_SIZE, TILE_SIZE, arcade.color.BLACK)
                    continue

                is_wall = self.room[y][x] == 1

                # Draw tile with texture or fallback
                if is_wall:
                    if self.wall_texture:
                        self._draw_texture(self.wall_texture, screen_x, screen_y, tint)
                    else:
                        self._draw_rect(screen_x, screen_y, TILE_SIZE - 1, TILE_SIZE - 1, (32, 32, 32))
                else:
                    if self.floor_texture:
                        self._draw_texture(self.floor_texture, screen_x, screen_y, tint)
                    else:
                        self._draw_rect(screen_x, screen_y, TILE_SIZE - 1, TILE_SIZE - 1, (64, 64, 64))

        # Draw entities (monsters, items, decorations) with lighting
        for ex, ey, entity_type, texture in self.entities:
            state = self.fog.get_visibility(ex, ey)
            tint = LIGHTING_TINTS.get(state)

            # Only draw visible entities
            if tint is None:
                continue

            screen_x = offset_x + ex * TILE_SIZE
            screen_y = offset_y + (MAP_HEIGHT - 1 - ey) * TILE_SIZE

            if texture:
                self._draw_texture(texture, screen_x, screen_y, tint)
            else:
                # Fallback: colored squares based on entity type
                if entity_type.startswith("monster:"):
                    fallback_color = (180, 50, 50)  # Red for monsters
                elif entity_type.startswith("item:"):
                    fallback_color = (50, 180, 50)  # Green for items
                else:
                    fallback_color = (180, 140, 50)  # Gold for decorations
                self._draw_rect(
                    screen_x + 4, screen_y + 4, TILE_SIZE - 8, TILE_SIZE - 8,
                    fallback_color
                )

        # Draw player
        player_screen_x = offset_x + self.player_x * TILE_SIZE
        player_screen_y = offset_y + (MAP_HEIGHT - 1 - self.player_y) * TILE_SIZE

        if self.player_texture:
            self._draw_texture(self.player_texture, player_screen_x, player_screen_y)
        else:
            # Fallback colored rectangle
            self._draw_rect(
                player_screen_x + 2,
                player_screen_y + 2,
                TILE_SIZE - 4,
                TILE_SIZE - 4,
                (70, 130, 180),
            )

        # Draw light indicator on player (color varies by mode)
        mode_name, _, _ = LIGHT_MODES[self.light_mode_index]
        light_colors = {
            "torch": arcade.color.ORANGE,
            "lantern": arcade.color.YELLOW,
            "light_spell": arcade.color.WHITE,
            "darkvision": arcade.color.PURPLE,
            "full_bright": arcade.color.CYAN,
        }
        light_color = light_colors.get(mode_name, arcade.color.ORANGE)
        arcade.draw_circle_filled(
            player_screen_x + TILE_SIZE // 2,
            player_screen_y + TILE_SIZE // 2,
            6,
            light_color,
        )

        # Draw UI text
        _, _, light_desc = LIGHT_MODES[self.light_mode_index]
        tiles_info = "Stone Soup" if self.assets.has_stonesoup_tiles else "Placeholders"
        arcade.draw_text(
            f"Light: {light_desc}  |  Tiles: {tiles_info}",
            10,
            WINDOW_HEIGHT - 25,
            arcade.color.WHITE,
            14,
        )

        explored_pct = (self.fog.explored_count / self.fog.total_tiles) * 100
        arcade.draw_text(
            f"Explored: {self.fog.explored_count}/{self.fog.total_tiles} ({explored_pct:.0f}%)  |  "
            f"Entities: {len(self.entities)}  |  L: cycle light  |  WASD: move  |  ESC: quit",
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

        # Check for light mode cycling
        if key == arcade.key.L:
            self.light_mode_index = (self.light_mode_index + 1) % len(LIGHT_MODES)
            mode_name, _, desc = LIGHT_MODES[self.light_mode_index]
            print(f"Light mode: {desc}")
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
    print("Starting D&D 2D Client - Stone Soup Tiles Demo")
    print("Controls:")
    print("  WASD / Arrow keys: Move player")
    print("  L: Cycle light mode (torch -> lantern -> light spell -> darkvision -> full bright)")
    print("  ESC: Quit")
    print()

    _game = DemoGame()  # Window registered with arcade
    arcade.run()


if __name__ == "__main__":
    main()
