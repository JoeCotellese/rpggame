#!/usr/bin/env python3
# ABOUTME: Visual demo of the 2D client with Stone Soup sprites.
# ABOUTME: Run with: python scripts/visual_test.py [room_id]

"""Visual test demo with Stone Soup tile rendering.

Usage:
    cd client-2d
    uv pip install -e ".[graphics]"
    python scripts/visual_test.py                           # Demo mode (medium window)
    python scripts/visual_test.py laboratory.entrance       # Load real room
    python scripts/visual_test.py --fullscreen              # Full screen mode
    python scripts/visual_test.py --size small              # Small window (800x600)
    python scripts/visual_test.py --size large              # Large window (1600x1000)

Controls:
    WASD / Arrow keys: Move player
    L: Cycle light mode (torch -> lantern -> light spell -> darkvision -> full bright)
    Tab: Cycle UI mode (exploration -> combat -> character)
    ESC: Quit
"""

import argparse
import sys
from pathlib import Path

import arcade
from arcade.types import Color

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from client_2d.assets.asset_manager import AssetManager
from client_2d.core.constants import (
    FONT_SIZE_BODY,
    FONT_SIZE_SMALL,
    FONT_SIZE_TITLE,
    NARRATIVE_HEIGHT_PCT,
    TILE_SIZE,
    UI_BORDER_WIDTH,
    UI_PADDING,
    VIEWPORT_WIDTH_PCT,
    GameMode,
    LightingState,
    UIColors,
)
from client_2d.input.input_handler import InputHandler
from client_2d.integration.layout_loader import LayoutLoader
from client_2d.systems.fog_of_war import FogOfWarSystem
from client_2d.systems.lighting import LightingSystem

# Mock party data for UI demo
MOCK_PARTY = [
    {"name": "Aldric", "class": "Fighter", "hp": 28, "max_hp": 32, "conditions": []},
    {"name": "Mira", "class": "Wizard", "hp": 14, "max_hp": 18, "conditions": ["Concentrating"]},
    {"name": "Thorne", "class": "Rogue", "hp": 22, "max_hp": 24, "conditions": []},
    {"name": "Elena", "class": "Cleric", "hp": 8, "max_hp": 20, "conditions": ["Blessed"]},
]

# Mock narrative text
MOCK_NARRATIVE = (
    "You descend into the crumbling entrance hall of the poisoned laboratory. "
    "The air is thick with dust and the faint scent of old alchemical reagents. "
    "Faded symbols on the walls hint at experiments long abandoned. "
    "Somewhere deeper within, you hear the scrape of bone against stone..."
)

# Mock combat data (initiative order with combatants)
MOCK_COMBAT = {
    "round": 2,
    "current_turn": 1,  # Index into initiative order
    "initiative": [
        {"name": "Thorne", "init": 18, "is_player": True, "hp": 22, "max_hp": 24},
        {"name": "Skeleton", "init": 15, "is_player": False, "hp": 8, "max_hp": 13},
        {"name": "Aldric", "init": 12, "is_player": True, "hp": 28, "max_hp": 32},
        {"name": "Skeleton", "init": 10, "is_player": False, "hp": 13, "max_hp": 13},
        {"name": "Mira", "init": 8, "is_player": True, "hp": 14, "max_hp": 18},
        {"name": "Elena", "init": 5, "is_player": True, "hp": 8, "max_hp": 20},
    ],
}

# Mock character data (selected character details)
MOCK_CHARACTER = {
    "name": "Aldric",
    "class": "Fighter",
    "level": 3,
    "hp": 28,
    "max_hp": 32,
    "ac": 18,
    "stats": {
        "STR": 16,
        "DEX": 12,
        "CON": 14,
        "INT": 10,
        "WIS": 11,
        "CHA": 13,
    },
    "equipment": {
        "weapon": "Longsword",
        "armor": "Chain Mail",
        "shield": "Shield",
    },
}

# UI modes for cycling (for testing purposes)
UI_MODES = [GameMode.EXPLORATION, GameMode.COMBAT, GameMode.CHARACTER]

# Window settings
WINDOW_TITLE = "D&D 2D Client - Stone Soup Tiles Demo"

# Window size presets
WINDOW_SIZES = {
    "small": (800, 600),
    "medium": (1280, 900),
    "large": (1600, 1000),
}

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

    def __init__(
        self,
        room_id: str = "",
        width: int = 1280,
        height: int = 900,
        fullscreen: bool = False,
    ):
        super().__init__(width, height, WINDOW_TITLE, fullscreen=fullscreen)
        arcade.set_background_color(arcade.color.BLACK)

        # Store room info
        self.room_id = room_id
        self.map_width = MAP_WIDTH
        self.map_height = MAP_HEIGHT

        # Light mode cycling
        self.light_mode_index = 0

        # UI mode for context panel (Tab to cycle for testing)
        self.ui_mode_index = 0
        self.current_ui_mode = UI_MODES[0]

        # Initialize asset manager
        self.assets = AssetManager(assets_path=ASSETS_DIR)

        # Load textures
        self._load_textures()

        # Entity positions (placed after room creation)
        self.entities: list[tuple[int, int, str, arcade.Texture | None]] = []

        # Load from campaign or create demo room
        if room_id:
            self._load_from_campaign(room_id)
        else:
            # Player position (in tiles)
            self.player_x = MAP_WIDTH // 2
            self.player_y = MAP_HEIGHT // 2

            # Initialize systems
            self.fog = FogOfWarSystem(width=MAP_WIDTH, height=MAP_HEIGHT)
            self.lighting = LightingSystem(map_width=MAP_WIDTH, map_height=MAP_HEIGHT)

            # Simple room layout (1 = wall, 0 = floor)
            self.room = self._create_room()

            # Set walls as obstacles for lighting
            for y in range(MAP_HEIGHT):
                for x in range(MAP_WIDTH):
                    if self.room[y][x] == 1:
                        self.lighting.add_obstacle(x, y)

            # Place entities on the map
            self._place_entities()

        self.input_handler = InputHandler(current_mode=GameMode.EXPLORATION)

        # Initial lighting update
        self._update_lighting()

    def _load_from_campaign(self, room_id: str) -> None:
        """Load room layout and entities from campaign data."""
        loader = LayoutLoader()

        # Parse room_id to get dungeon name (e.g., "laboratory.entrance" -> "laboratory")
        dungeon_name = room_id.split(".")[0] if "." in room_id else "laboratory"

        # Get room data
        room_data = loader.get_room_data(dungeon_name, room_id, "poisoned_laboratory")
        if not room_data:
            print(f"Failed to load room: {room_id}")
            sys.exit(1)

        # Get exits for fallback generation
        exits = room_data.get("exits", {})
        exit_map = {}
        for direction, dest in exits.items():
            if isinstance(dest, dict):
                exit_map[direction] = dest.get("destination", "")
            else:
                exit_map[direction] = dest

        # Load layout
        layout = loader.load_room_with_fallback(
            dungeon_name, room_id, "poisoned_laboratory",
            default_width=25, default_height=18, exits=exit_map
        )

        # Set dimensions
        self.map_width = layout.width
        self.map_height = layout.height

        # Convert layout to room format
        self.room = layout.tiles

        # Player spawn position
        self.player_x, self.player_y = layout.spawn_points.player

        # Initialize systems with room dimensions
        self.fog = FogOfWarSystem(width=self.map_width, height=self.map_height)
        self.lighting = LightingSystem(map_width=self.map_width, map_height=self.map_height)

        # Set walls as obstacles
        for y in range(self.map_height):
            for x in range(self.map_width):
                if layout.is_blocking(x, y):
                    self.lighting.add_obstacle(x, y)

        # Place entities from room data
        # Enemies
        room_enemies = room_data.get("enemies", [])
        enemy_positions = layout.entity_positions.enemies
        for i, enemy_type in enumerate(room_enemies):
            if i < len(enemy_positions):
                ex, ey = enemy_positions[i]
            else:
                ex = self.map_width // 2 + i
                ey = self.map_height // 2
            texture = self.monster_textures.get(enemy_type)
            self.entities.append((ex, ey, f"monster:{enemy_type}", texture))

        # Items
        room_items = room_data.get("items", [])
        item_positions = layout.entity_positions.items
        visible_item_idx = 0
        for item_data in room_items:
            if not item_data.get("visible", True):
                continue
            item_id = item_data.get("id", f"item_{visible_item_idx}")
            if visible_item_idx < len(item_positions):
                ix, iy = item_positions[visible_item_idx]
            else:
                ix = 3 + (visible_item_idx * 2) % (self.map_width - 6)
                iy = 3 + (visible_item_idx * 3) % (self.map_height - 6)
            texture = self.item_textures.get(item_id)
            self.entities.append((ix, iy, f"item:{item_id}", texture))
            visible_item_idx += 1

        print(f"Loaded room: {room_data.get('name', room_id)}")
        print(f"  Size: {self.map_width}x{self.map_height}")
        print(f"  Player spawn: ({self.player_x}, {self.player_y})")
        print(f"  Entities: {len(self.entities)}")

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

    def _calculate_layout(self) -> dict:
        """Calculate pixel positions for UI zones based on window size."""
        narrative_h = int(self.height * NARRATIVE_HEIGHT_PCT)
        game_area_h = self.height - narrative_h
        viewport_w = int(self.width * VIEWPORT_WIDTH_PCT)
        context_w = self.width - viewport_w

        return {
            "viewport": {"x": 0, "y": narrative_h, "w": viewport_w, "h": game_area_h},
            "context": {"x": viewport_w, "y": narrative_h, "w": context_w, "h": game_area_h},
            "narrative": {"x": 0, "y": 0, "w": self.width, "h": narrative_h},
        }

    def _draw_panel(
        self, x: float, y: float, w: float, h: float, title: str = ""
    ) -> None:
        """Draw a UI panel with background and border."""
        # Background
        self._draw_rect(x, y, w, h, UIColors.PANEL_BG)

        # Border
        border_rect = arcade.LBWH(x, y, w, h)
        arcade.draw_rect_outline(border_rect, UIColors.BORDER, UI_BORDER_WIDTH)

        # Title if provided
        if title:
            arcade.draw_text(
                title,
                x + UI_PADDING,
                y + h - UI_PADDING - FONT_SIZE_TITLE,
                UIColors.TEXT_HIGHLIGHT,
                FONT_SIZE_TITLE,
                bold=True,
            )

    def _draw_hp_bar(
        self, x: float, y: float, width: float, hp: int, max_hp: int
    ) -> None:
        """Draw an HP bar with color based on health percentage."""
        bar_height = 8
        hp_pct = hp / max_hp if max_hp > 0 else 0

        # Background
        self._draw_rect(x, y, width, bar_height, UIColors.HP_BG)

        # Determine color based on HP percentage
        if hp_pct > 0.6:
            color = UIColors.HP_FULL
        elif hp_pct > 0.3:
            color = UIColors.HP_LOW
        else:
            color = UIColors.HP_CRITICAL

        # HP fill
        fill_width = int(width * hp_pct)
        if fill_width > 0:
            self._draw_rect(x, y, fill_width, bar_height, color)

        # Border
        bar_rect = arcade.LBWH(x, y, width, bar_height)
        arcade.draw_rect_outline(bar_rect, UIColors.BORDER, 1)

    def _draw_context_panel(self, layout: dict) -> None:
        """Draw the appropriate context panel based on current UI mode."""
        if self.current_ui_mode == GameMode.COMBAT:
            self._draw_combat_panel(layout)
        elif self.current_ui_mode == GameMode.CHARACTER:
            self._draw_character_panel(layout)
        else:
            self._draw_party_panel(layout)

    def _draw_party_panel(self, layout: dict) -> None:
        """Draw the context panel with party status (exploration mode)."""
        ctx = layout["context"]
        self._draw_panel(ctx["x"], ctx["y"], ctx["w"], ctx["h"], "Party")

        # Draw each party member
        start_y = ctx["y"] + ctx["h"] - UI_PADDING - FONT_SIZE_TITLE - 30
        hp_text_width = 60  # Reserve space for "30/30" style text
        bar_width = ctx["w"] - (UI_PADDING * 3) - hp_text_width

        for i, member in enumerate(MOCK_PARTY):
            member_y = start_y - (i * 50)

            # Name and class
            arcade.draw_text(
                f"{member['name']} ({member['class']})",
                ctx["x"] + UI_PADDING,
                member_y,
                UIColors.TEXT,
                FONT_SIZE_BODY,
            )

            # HP bar
            self._draw_hp_bar(
                ctx["x"] + UI_PADDING,
                member_y - 18,
                bar_width,
                member["hp"],
                member["max_hp"],
            )

            # HP text (to the right of the bar with padding)
            arcade.draw_text(
                f"{member['hp']}/{member['max_hp']}",
                ctx["x"] + UI_PADDING + bar_width + 8,
                member_y - 16,
                UIColors.TEXT_DIM,
                FONT_SIZE_SMALL,
            )

            # Conditions
            if member["conditions"]:
                cond_text = ", ".join(member["conditions"])
                arcade.draw_text(
                    cond_text,
                    ctx["x"] + UI_PADDING,
                    member_y - 32,
                    UIColors.BUFF,
                    FONT_SIZE_SMALL,
                )

    def _draw_combat_panel(self, layout: dict) -> None:
        """Draw the combat panel with initiative order."""
        ctx = layout["context"]
        self._draw_panel(
            ctx["x"], ctx["y"], ctx["w"], ctx["h"],
            f"Combat - Round {MOCK_COMBAT['round']}"
        )

        # Draw initiative order
        start_y = ctx["y"] + ctx["h"] - UI_PADDING - FONT_SIZE_TITLE - 30
        hp_text_width = 50
        bar_width = ctx["w"] - (UI_PADDING * 3) - hp_text_width
        current_turn = MOCK_COMBAT["current_turn"]

        for i, combatant in enumerate(MOCK_COMBAT["initiative"]):
            entry_y = start_y - (i * 40)
            is_current = i == current_turn

            # Highlight current turn
            if is_current:
                highlight_rect = arcade.LBWH(
                    ctx["x"] + 2,
                    entry_y - 25,
                    ctx["w"] - 4,
                    38
                )
                arcade.draw_rect_filled(highlight_rect, UIColors.SELECTION)

            # Initiative number
            init_color = UIColors.HIGHLIGHT if is_current else UIColors.TEXT_DIM
            arcade.draw_text(
                f"{combatant['init']:2d}",
                ctx["x"] + UI_PADDING,
                entry_y,
                init_color,
                FONT_SIZE_BODY,
                bold=is_current,
            )

            # Name with player/enemy indicator
            name_color = UIColors.TEXT if combatant["is_player"] else UIColors.DAMAGE
            arcade.draw_text(
                combatant["name"],
                ctx["x"] + UI_PADDING + 30,
                entry_y,
                name_color,
                FONT_SIZE_BODY,
                bold=is_current,
            )

            # HP bar
            self._draw_hp_bar(
                ctx["x"] + UI_PADDING,
                entry_y - 18,
                bar_width,
                combatant["hp"],
                combatant["max_hp"],
            )

            # HP text
            arcade.draw_text(
                f"{combatant['hp']}/{combatant['max_hp']}",
                ctx["x"] + UI_PADDING + bar_width + 8,
                entry_y - 16,
                UIColors.TEXT_DIM,
                FONT_SIZE_SMALL,
            )

    def _draw_character_panel(self, layout: dict) -> None:
        """Draw the character details panel."""
        ctx = layout["context"]
        char = MOCK_CHARACTER
        self._draw_panel(ctx["x"], ctx["y"], ctx["w"], ctx["h"], char["name"])

        start_y = ctx["y"] + ctx["h"] - UI_PADDING - FONT_SIZE_TITLE - 30
        hp_text_width = 60
        bar_width = ctx["w"] - (UI_PADDING * 3) - hp_text_width

        # Class and level
        arcade.draw_text(
            f"Level {char['level']} {char['class']}",
            ctx["x"] + UI_PADDING,
            start_y,
            UIColors.TEXT,
            FONT_SIZE_BODY,
        )

        # HP bar
        self._draw_hp_bar(
            ctx["x"] + UI_PADDING,
            start_y - 25,
            bar_width,
            char["hp"],
            char["max_hp"],
        )
        arcade.draw_text(
            f"{char['hp']}/{char['max_hp']}",
            ctx["x"] + UI_PADDING + bar_width + 8,
            start_y - 23,
            UIColors.TEXT_DIM,
            FONT_SIZE_SMALL,
        )

        # AC
        arcade.draw_text(
            f"AC: {char['ac']}",
            ctx["x"] + UI_PADDING,
            start_y - 50,
            UIColors.TEXT_HIGHLIGHT,
            FONT_SIZE_BODY,
        )

        # Stats section
        stats_y = start_y - 85
        arcade.draw_text(
            "Abilities",
            ctx["x"] + UI_PADDING,
            stats_y,
            UIColors.TEXT_HIGHLIGHT,
            FONT_SIZE_BODY,
            bold=True,
        )

        # Draw stats in two columns
        stats_start_y = stats_y - 25
        stat_names = list(char["stats"].keys())
        for i, stat_name in enumerate(stat_names):
            stat_val = char["stats"][stat_name]
            modifier = (stat_val - 10) // 2
            mod_str = f"+{modifier}" if modifier >= 0 else str(modifier)

            col = i % 2
            row = i // 2
            stat_x = ctx["x"] + UI_PADDING + (col * 90)
            stat_y = stats_start_y - (row * 22)

            arcade.draw_text(
                f"{stat_name}: {stat_val} ({mod_str})",
                stat_x,
                stat_y,
                UIColors.TEXT,
                FONT_SIZE_SMALL,
            )

        # Equipment section
        equip_y = stats_start_y - 85
        arcade.draw_text(
            "Equipment",
            ctx["x"] + UI_PADDING,
            equip_y,
            UIColors.TEXT_HIGHLIGHT,
            FONT_SIZE_BODY,
            bold=True,
        )

        equip_start_y = equip_y - 25
        for i, (slot, item) in enumerate(char["equipment"].items()):
            arcade.draw_text(
                f"{slot.title()}: {item}",
                ctx["x"] + UI_PADDING,
                equip_start_y - (i * 20),
                UIColors.TEXT,
                FONT_SIZE_SMALL,
            )

    def _draw_narrative_panel(self, layout: dict) -> None:
        """Draw the narrative exposition panel."""
        narr = layout["narrative"]
        self._draw_panel(narr["x"], narr["y"], narr["w"], narr["h"])

        # Draw narrative text with word wrap
        arcade.draw_text(
            MOCK_NARRATIVE,
            narr["x"] + UI_PADDING,
            narr["y"] + narr["h"] - UI_PADDING - FONT_SIZE_BODY,
            UIColors.TEXT,
            FONT_SIZE_BODY,
            width=int(narr["w"] - UI_PADDING * 2),
            multiline=True,
        )

    def on_draw(self):
        """Render the game."""
        self.clear()

        # Set background color
        arcade.set_background_color(UIColors.BACKGROUND)

        # Calculate layout zones
        layout = self._calculate_layout()
        vp = layout["viewport"]

        # Calculate offset to center the map within the viewport
        offset_x = vp["x"] + (vp["w"] - self.map_width * TILE_SIZE) // 2
        offset_y = vp["y"] + (vp["h"] - self.map_height * TILE_SIZE) // 2

        # Draw floor and walls with lighting
        for y in range(self.map_height):
            for x in range(self.map_width):
                screen_x = offset_x + x * TILE_SIZE
                screen_y = offset_y + (self.map_height - 1 - y) * TILE_SIZE  # Flip Y

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
            screen_y = offset_y + (self.map_height - 1 - ey) * TILE_SIZE

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
        player_screen_y = offset_y + (self.map_height - 1 - self.player_y) * TILE_SIZE

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

        # Draw UI panels
        self._draw_context_panel(layout)
        self._draw_narrative_panel(layout)

        # Draw status bar in viewport (light mode, UI mode, controls)
        _, _, light_desc = LIGHT_MODES[self.light_mode_index]
        explored_pct = (self.fog.explored_count / self.fog.total_tiles) * 100
        mode_short = {
            GameMode.EXPLORATION: "Party",
            GameMode.COMBAT: "Combat",
            GameMode.CHARACTER: "Character",
        }
        status_text = (
            f"[{mode_short.get(self.current_ui_mode, '?')}]  |  "
            f"Light: {light_desc}  |  "
            f"Explored: {explored_pct:.0f}%  |  "
            f"Tab: mode  |  L: light  |  ESC: quit"
        )
        arcade.draw_text(
            status_text,
            vp["x"] + UI_PADDING,
            vp["y"] + UI_PADDING,
            UIColors.TEXT_DIM,
            FONT_SIZE_SMALL,
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

        # Check for UI mode cycling (Tab for testing)
        if key == arcade.key.TAB:
            self.ui_mode_index = (self.ui_mode_index + 1) % len(UI_MODES)
            self.current_ui_mode = UI_MODES[self.ui_mode_index]
            mode_names = {
                GameMode.EXPLORATION: "Exploration (Party)",
                GameMode.COMBAT: "Combat (Initiative)",
                GameMode.CHARACTER: "Character (Details)",
            }
            print(f"UI mode: {mode_names.get(self.current_ui_mode, 'Unknown')}")
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
        if 0 <= new_x < self.map_width and 0 <= new_y < self.map_height:
            if self.room[new_y][new_x] == 0:  # Not a wall
                self.player_x = new_x
                self.player_y = new_y
                self._update_lighting()


def main():
    """Run the demo."""
    parser = argparse.ArgumentParser(
        description="D&D 2D Client - Stone Soup Tiles Demo"
    )
    parser.add_argument(
        "room_id",
        nargs="?",
        default="",
        help="Room ID to load (e.g., laboratory.entrance)",
    )
    parser.add_argument(
        "-f", "--fullscreen",
        action="store_true",
        help="Run in fullscreen mode",
    )
    parser.add_argument(
        "-s", "--size",
        choices=["small", "medium", "large"],
        default="medium",
        help="Window size preset: small (800x600), medium (1280x900), large (1600x1000)",
    )

    args = parser.parse_args()

    # Get window dimensions
    width, height = WINDOW_SIZES[args.size]
    if args.fullscreen:
        # For fullscreen, start with large dimensions (arcade will handle actual size)
        width, height = WINDOW_SIZES["large"]

    print("Starting D&D 2D Client - Stone Soup Tiles Demo")
    if args.room_id:
        print(f"Loading room: {args.room_id}")
    else:
        print("Demo mode (no room specified)")
    if args.fullscreen:
        print("Mode: Fullscreen")
    else:
        print(f"Window: {width}x{height} ({args.size})")
    print()
    print("Controls:")
    print("  WASD / Arrow keys: Move player")
    print("  L: Cycle light mode (torch -> lantern -> light spell -> darkvision -> full bright)")
    print("  Tab: Cycle UI mode (exploration -> combat -> character)")
    print("  ESC: Quit")
    print()

    _game = DemoGame(
        room_id=args.room_id,
        width=width,
        height=height,
        fullscreen=args.fullscreen,
    )
    arcade.run()


if __name__ == "__main__":
    main()
