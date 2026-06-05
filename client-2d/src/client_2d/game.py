# ABOUTME: Main entry point for the 2D graphical client.
# ABOUTME: Launches the game window with real engine integration.

"""2D graphical client for the D&D game.

This module provides the entry point for the 2D client, which can be
launched via `dnd-game --mode 2d`.
"""

import math
from datetime import datetime
from pathlib import Path

import arcade
from arcade.types import Color

from client_2d.assets.asset_manager import AssetManager
from client_2d.core.constants import (
    FONT_SIZE_BODY,
    FONT_SIZE_SMALL,
    FONT_SIZE_TITLE,
    NARRATIVE_HEIGHT_PCT,
    PULSE_CYCLE_DURATION,
    TILE_SIZE,
    UI_BORDER_WIDTH,
    UI_PADDING,
    VIEWPORT_WIDTH_PCT,
    GameMode,
    LightingState,
    TargetingColors,
    UIColors,
)
from client_2d.entities import Entity, EntityType
from client_2d.session import GameSession

# Window settings
WINDOW_TITLE = "D&D 5E - 2D Client"
WINDOW_SIZES = {
    "small": (800, 600),
    "medium": (1280, 900),
    "large": (1600, 1000),
}

# Combat timing
ENEMY_TURN_DELAY = 1.5  # Seconds before enemy acts

# Assets directory
ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"

# Screenshots directory
SCREENSHOTS_DIR = Path.home() / ".dnd_game" / "screenshots"
SCREENSHOT_FEEDBACK_DURATION = 2.0  # Seconds to show "Screenshot saved!"

# Lighting tint colors (RGB multipliers as 0-255)
LIGHTING_TINTS = {
    LightingState.UNEXPLORED: None,  # Don't render
    LightingState.DARK: (60, 60, 80),  # Dark blue-gray (memory)
    LightingState.DIM: (160, 160, 180),  # Dimmed
    LightingState.BRIGHT: (255, 255, 255),  # Full brightness
}


# ========== Range Utilities for Ranged Attacks ==========


def parse_weapon_range(range_str: str | None) -> tuple[int, int]:
    """Parse weapon range string like "150/600" into (normal_feet, max_feet).

    Args:
        range_str: Range string in format "normal/max" (feet), or None for melee.

    Returns:
        Tuple of (normal_range_feet, max_range_feet). Returns (5, 5) for melee.
    """
    if not range_str:
        return (5, 5)  # Melee: adjacent only (5 ft)
    parts = range_str.split("/")
    if len(parts) == 2:
        return (int(parts[0]), int(parts[1]))
    # Single value means same normal and max
    return (int(parts[0]), int(parts[0]))


def get_attack_range(weapon_data: dict | None) -> tuple[int, int]:
    """Get (normal_range, max_range) in feet for a weapon.

    Handles melee, ranged, and thrown weapons per D&D 5E rules:
    - Melee weapons (no range property): 5 ft only
    - Ranged weapons: use range property
    - Thrown weapons (melee with "thrown" property + range): can use at range

    Args:
        weapon_data: Weapon dict from items.json, or None for unarmed.

    Returns:
        Tuple of (normal_range_feet, max_range_feet).
    """
    if not weapon_data:
        return (5, 5)  # Unarmed: melee only

    range_str = weapon_data.get("range")
    properties = weapon_data.get("properties", [])
    category = weapon_data.get("category", "melee")

    # Ranged weapons always use their range
    if category == "ranged":
        return parse_weapon_range(range_str)

    # Thrown melee weapons can be used at range
    if "thrown" in properties and range_str:
        return parse_weapon_range(range_str)

    # Regular melee weapons: adjacent only
    return (5, 5)


class GameView(arcade.View):
    """Gameplay view: renders the dungeon and routes player input.

    Hosted by :class:`GameWindow` via ``window.show_view``. Owns the
    rendering + input surface and a :class:`GameSession` (the non-graphical
    authority). Keeping gameplay in a View lets the host window swap between
    this view and the launch-screen menu views (#626-#630).
    """

    def __init__(
        self,
        enable_mcp: bool = False,
        mcp_port: int = 8765,
        dev_mode: bool = False,
    ):
        """Initialize the gameplay view.

        Args:
            enable_mcp: Whether to start embedded MCP server.
            mcp_port: Port for MCP HTTP server.
            dev_mode: Whether to register --dev spawn/setup MCP tools.
        """
        super().__init__()

        # Session owns the non-graphical state: engine adapter, entity
        # manager, MCP plumbing, room layout, combat state machine.
        # GameView accesses these via property delegators below.
        self.session = GameSession(
            enable_mcp=enable_mcp,
            mcp_port=mcp_port,
            dev_mode=dev_mode,
        )

        # Asset manager and textures (rendering-only state).
        self.assets = AssetManager(assets_path=ASSETS_DIR)
        self._load_textures()

        # Hand off the loaded textures so the session's spawn / load
        # paths can apply sprites when registering entities.
        self.session.monster_textures = self.monster_textures
        self.session.character_textures = self.character_textures
        self.session.item_textures = self.item_textures

        # Screenshot feedback state (UI-only).
        self.screenshot_message: str = ""
        self.screenshot_message_timer: float = 0.0

        # Mouse targeting state (for #355 unified targeting) - input/UI only.
        self.mouse_x: int = 0
        self.mouse_y: int = 0
        self.hovered_entity: Entity | None = None
        self.selected_target: Entity | None = None
        self.pulse_timer: float = 0.0

        # Boot the session: load party, room, optionally start MCP server.
        self.session.initialize()
        if enable_mcp:
            # Pass the host window so the bridge can resolve back to it for
            # code paths that still consult its window reference.
            self.session.initialize_mcp_server(window=self.window)

    # ========== Window geometry ==========
    # A View has no surface of its own; the host Window owns width/height.
    # Expose them so the rendering / input code keeps using self.width and
    # self.height unchanged.

    @property
    def width(self) -> int:
        return self.window.width

    @property
    def height(self) -> int:
        return self.window.height

    # ========== Property delegators to GameSession ==========
    # GameView holds a GameSession; these proxies let the existing
    # drawing / input code read session-owned state through the
    # familiar self.X names without per-call updates.

    @property
    def engine(self):
        return self.session.engine

    @property
    def entity_manager(self):
        return self.session.entity_manager

    @property
    def layout_loader(self):
        return self.session.layout_loader

    @property
    def room_layout(self):
        return self.session.room_layout

    @property
    def room_tiles(self):
        return self.session.room_tiles

    @property
    def player_x(self) -> int:
        return self.session.player_x

    @player_x.setter
    def player_x(self, value: int) -> None:
        self.session.player_x = value

    @property
    def player_y(self) -> int:
        return self.session.player_y

    @player_y.setter
    def player_y(self, value: int) -> None:
        self.session.player_y = value

    @property
    def party_spread(self) -> bool:
        return self.session.party_spread

    @property
    def party_positions(self) -> list[tuple[int, int]]:
        return self.session.party_positions

    @property
    def fog(self):
        return self.session.fog

    @property
    def lighting(self):
        return self.session.lighting

    @property
    def current_mode(self):
        return self.session.current_mode

    @current_mode.setter
    def current_mode(self, value) -> None:
        self.session.current_mode = value

    @property
    def selected_enemy(self) -> int:
        return self.session.selected_enemy

    @selected_enemy.setter
    def selected_enemy(self, value: int) -> None:
        self.session.selected_enemy = value

    @property
    def combat_log(self) -> list[str]:
        return self.session.combat_log

    @property
    def processing_enemy_turn(self) -> bool:
        return self.session.processing_enemy_turn

    @property
    def enemy_turn_timer(self) -> float:
        return self.session.enemy_turn_timer

    # ========== Method delegators to GameSession ==========
    # Thin wrappers for the methods that GameView's input handlers,
    # drawing code, and mouse handlers still call directly. The real
    # logic lives in GameSession; these keep the call sites unchanged.

    def _add_combat_log(self, message: str) -> None:
        self.session._add_combat_log(message)

    def _update_lighting(self) -> None:
        self.session._update_lighting()

    def _spread_party_for_combat(self) -> None:
        self.session._spread_party_for_combat()

    def _collapse_party_after_combat(self) -> None:
        self.session._collapse_party_after_combat()

    def _load_room_layout(self) -> None:
        self.session._load_room_layout()

    def _get_available_exits(self) -> dict[str, str]:
        return self.session._get_available_exits()

    def _move_player(self, direction: str) -> None:
        self.session._move_player(direction)

    def _transition_room(self, direction: str) -> None:
        self.session._transition_room(direction)

    def _process_enemy_turn(self) -> None:
        self.session._process_enemy_turn()

    def _process_unconscious_turn(self) -> None:
        self.session._process_unconscious_turn()

    def _handle_combat_end(self) -> None:
        self.session._handle_combat_end()

    def _execute_attack(self, *, disadvantage: bool = False) -> None:
        self.session.execute_attack(disadvantage=disadvantage)

    def _pass_turn(self) -> None:
        self.session.pass_turn()

    def _hide(self) -> None:
        """Take the Hide action for the current PC.

        Delegates to GameSession.hide, which routes into
        GameState.attempt_hide and logs the outcome (including the
        environment-gate refusal when there's no concealment) to the
        combat log. Hide spends the action but leaves the turn with the
        player, so no enemy turns are drained here.
        """
        self.session.hide()

    def _mcp_combat_move(self, direction: str) -> str:
        return self.session.combat_move(direction)

    # ========== End delegators ==========

    def save_screenshot(self) -> Path | None:
        """Save a screenshot of the current game window.

        Returns:
            Path to the saved screenshot, or None if save failed.
        """
        # Ensure screenshots directory exists
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

        # Generate timestamped filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        filepath = SCREENSHOTS_DIR / filename

        try:
            # Capture the framebuffer
            image = arcade.get_image(0, 0, *self.window.get_size())
            image.save(str(filepath))

            # Show feedback
            self.screenshot_message = f"Screenshot saved: {filename}"
            self.screenshot_message_timer = SCREENSHOT_FEEDBACK_DURATION

            print(f"Screenshot saved: {filepath}")
            return filepath
        except Exception as e:
            print(f"Failed to save screenshot: {e}")
            self.screenshot_message = "Screenshot failed!"
            self.screenshot_message_timer = SCREENSHOT_FEEDBACK_DURATION
            return None

    def _load_textures(self) -> None:
        """Load tile textures from Stone Soup assets."""
        # Floor and wall textures
        floor_path = self.assets.get_terrain_sprite_path("floor_stone")
        wall_path = self.assets.get_terrain_sprite_path("wall_brick")
        door_closed_path = self.assets.get_terrain_sprite_path("door_closed")
        player_path = self.assets.get_character_sprite_path("fighter")

        # Load terrain textures
        self.floor_texture = self._try_load_texture(floor_path, "floor")
        self.wall_texture = self._try_load_texture(wall_path, "wall")
        self.door_texture = self._try_load_texture(door_closed_path, "door")
        self.player_texture = self._try_load_texture(player_path, "player")

        # Load per-class character textures for party rendering
        self.character_textures: dict[str, arcade.Texture | None] = {}
        classes_to_load = ["fighter", "rogue", "wizard", "cleric", "paladin", "barbarian"]
        for char_class in classes_to_load:
            path = self.assets.get_character_sprite_path(char_class)
            texture = self._try_load_texture(path, f"character:{char_class}")
            if texture:
                self.character_textures[char_class] = texture

        # Load monster textures
        self.monster_textures: dict[str, arcade.Texture | None] = {}
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

        # Load item textures
        self.item_textures: dict[str, arcade.Texture | None] = {}
        items_to_load = [
            ("longsword", "weapons"),
            ("potion_of_healing", "potions"),
            ("torch", "misc"),
            ("chain_mail", "armor"),
            ("alchemists_fire", "misc"),
            ("acid_vial", "misc"),
        ]
        for item_id, item_category in items_to_load:
            path = self.assets.get_item_sprite_path(item_id, item_category)
            texture = self._try_load_texture(path, f"item:{item_id}")
            if texture:
                self.item_textures[item_id] = texture

        # Load decoration textures
        self.decoration_textures: dict[str, arcade.Texture | None] = {}
        for deco_id in ["chest_closed", "bones"]:
            path = self.assets.get_decoration_sprite_path(deco_id)
            texture = self._try_load_texture(path, f"decoration:{deco_id}")
            if texture:
                self.decoration_textures[deco_id] = texture

    def _try_load_texture(self, path: Path | None, name: str) -> arcade.Texture | None:
        """Try to load a texture, logging success or fallback."""
        if path and path.exists():
            print(f"Loaded {name}: {path.name}")
            return arcade.load_texture(str(path))
        else:
            print(f"Using fallback for {name}")
            return None

    def _draw_texture(
        self,
        texture: arcade.Texture,
        x: float,
        y: float,
        tint: tuple[int, int, int] | None = None,
    ) -> None:
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

    def _multiply_tints(
        self, tint1: tuple[int, int, int], tint2: tuple[int, int, int]
    ) -> tuple[int, int, int]:
        """Combine two RGB tints via multiplication (for fog + targeting)."""
        return (
            tint1[0] * tint2[0] // 255,
            tint1[1] * tint2[1] // 255,
            tint1[2] * tint2[2] // 255,
        )

    def on_draw(self) -> None:
        """Render the game."""
        self.clear()

        # Calculate layout zones
        viewport_w = int(self.width * VIEWPORT_WIDTH_PCT)
        context_w = self.width - viewport_w
        narrative_h = int(self.height * NARRATIVE_HEIGHT_PCT)
        main_h = self.height - narrative_h

        # Draw UI panels
        self._draw_game_viewport(0, narrative_h, viewport_w, main_h)
        self._draw_context_panel(viewport_w, narrative_h, context_w, main_h)
        self._draw_narrative_panel(0, 0, self.width, narrative_h)

        # Draw screenshot feedback overlay
        if self.screenshot_message:
            self._draw_screenshot_feedback()

        # Draw entity tooltip (must be last to appear on top)
        if self.hovered_entity and self.current_mode == GameMode.COMBAT:
            self._draw_entity_tooltip()

    def _draw_entity_tooltip(self) -> None:
        """Draw tooltip for hovered entity near the cursor."""
        entity = self.hovered_entity
        if entity is None:
            return

        from dnd_engine.core.distance import distance_in_feet
        from dnd_engine.systems.inventory import EquipmentSlot

        # Get combatant position for distance calculation
        combatant_pos = self.entity_manager.get_current_turn_position(self.engine)
        if combatant_pos is None:
            combatant_x, combatant_y = self.player_x, self.player_y
        else:
            combatant_x, combatant_y = combatant_pos

        distance_ft = distance_in_feet(combatant_x, combatant_y, entity.grid_x, entity.grid_y)

        # Get attacker's equipped weapon range
        current = self.engine.get_current_combatant()
        weapon_data = None
        if current and current["is_player"]:
            creature = current["creature"]
            if hasattr(creature, "inventory"):
                weapon_id = creature.inventory.get_equipped_item(EquipmentSlot.WEAPON)
                if weapon_id:
                    items_data = self.engine.game_state.data_loader.load_items(
                        self.engine.game_state.campaign_id
                    )
                    weapon_data = items_data.get("weapons", {}).get(weapon_id, {})

        normal_range, max_range = get_attack_range(weapon_data)

        # Build tooltip text
        name = entity.sub_type.replace("_", " ").title() if entity.sub_type else entity.entity_id
        hp_text = f"{entity.hp}/{entity.max_hp} HP"
        distance_text = f"{distance_ft} ft"

        if distance_ft <= normal_range:
            range_text = "(in range)"
        elif distance_ft <= max_range:
            range_text = "(long range)"
        else:
            range_text = "(out of range)"

        text = f"{name} - {hp_text} - {distance_text} {range_text}"

        # Calculate tooltip position (16px above-right of cursor, clamped to screen)
        tooltip_width = len(text) * 8 + 20
        tooltip_height = 28
        tip_x = min(self.mouse_x + 16, self.width - tooltip_width - 10)
        tip_y = min(self.mouse_y + 16, self.height - tooltip_height - 10)

        # Ensure tooltip doesn't go below screen
        tip_y = max(tip_y, 10)
        tip_x = max(tip_x, 10)

        # Draw background
        bg_rect = arcade.LBWH(tip_x, tip_y, tooltip_width, tooltip_height)
        arcade.draw_rect_filled(bg_rect, (0, 0, 0, 220))
        arcade.draw_rect_outline(bg_rect, UIColors.BORDER, 1)

        # Draw text
        arcade.draw_text(
            text,
            tip_x + 10,
            tip_y + 6,
            arcade.color.WHITE,
            FONT_SIZE_BODY,
        )

    def _draw_game_viewport(self, x: float, y: float, w: float, h: float) -> None:
        """Draw the main game viewport with dungeon tiles."""
        # Background
        rect = arcade.LBWH(x, y, w, h)
        arcade.draw_rect_filled(rect, UIColors.PANEL_BG_DARK)
        arcade.draw_rect_outline(rect, UIColors.BORDER, UI_BORDER_WIDTH)

        # Room name
        room_name = "Unknown"
        if self.engine.game_state:
            room = self.engine.game_state.get_current_room()
            room_name = room.get("name", "Unknown")

        arcade.draw_text(
            room_name,
            x + UI_PADDING,
            y + h - UI_PADDING - FONT_SIZE_TITLE,
            UIColors.TEXT_HIGHLIGHT,
            FONT_SIZE_TITLE,
            bold=True,
        )

        # Draw the dungeon tiles
        if self.room_layout:
            self._draw_dungeon_tiles(x, y, w, h)

        # Combat overlay
        if self.engine.in_combat:
            self._draw_combat_overlay(x, y, w, h)
        else:
            # Exploration controls hint
            arcade.draw_text(
                "WASD: Move  |  Go NORTH to find the rats!",
                x + w // 2,
                y + UI_PADDING,
                UIColors.TEXT_DIM,
                FONT_SIZE_SMALL,
                anchor_x="center",
            )

    def _draw_dungeon_tiles(self, vp_x: float, vp_y: float, vp_w: float, vp_h: float) -> None:
        """Draw the dungeon tile grid with textures and lighting."""
        if not self.room_layout:
            return

        # Calculate tile size to fit the viewport
        margin = 50  # Space for title and controls
        available_h = vp_h - margin * 2
        available_w = vp_w - UI_PADDING * 2

        tile_size = min(
            available_w // self.room_layout.width,
            available_h // self.room_layout.height,
            TILE_SIZE,  # Cap at max tile size
        )

        # Center the map in the viewport
        map_w = self.room_layout.width * tile_size
        map_h = self.room_layout.height * tile_size
        offset_x = vp_x + (vp_w - map_w) // 2
        offset_y = vp_y + margin + (available_h - map_h) // 2

        # Draw tiles with lighting
        for ty in range(self.room_layout.height):
            for tx in range(self.room_layout.width):
                screen_x = offset_x + tx * tile_size
                # Flip Y for screen coords (0,0 at bottom-left in arcade)
                screen_y = offset_y + (self.room_layout.height - 1 - ty) * tile_size

                # Get lighting state for this tile
                if self.fog:
                    state = self.fog.get_visibility(tx, ty)
                    tint = LIGHTING_TINTS.get(state)
                else:
                    tint = (255, 255, 255)  # Full bright if no fog system

                # Skip unexplored tiles (render black)
                if tint is None:
                    tile_rect = arcade.LBWH(screen_x, screen_y, tile_size, tile_size)
                    arcade.draw_rect_filled(tile_rect, arcade.color.BLACK)
                    continue

                tile_val = self.room_tiles[ty][tx]
                is_wall = tile_val == 1
                is_door = tile_val == 2

                # Draw tile with texture or fallback
                if is_wall:
                    if self.wall_texture:
                        self._draw_texture(self.wall_texture, screen_x, screen_y, tint)
                    else:
                        tile_rect = arcade.LBWH(screen_x, screen_y, tile_size - 1, tile_size - 1)
                        arcade.draw_rect_filled(tile_rect, (60, 50, 40))
                elif is_door:
                    if self.door_texture:
                        self._draw_texture(self.door_texture, screen_x, screen_y, tint)
                    else:
                        tile_rect = arcade.LBWH(screen_x, screen_y, tile_size - 1, tile_size - 1)
                        arcade.draw_rect_filled(tile_rect, (100, 80, 60))
                        arcade.draw_rect_outline(tile_rect, UIColors.TEXT_HIGHLIGHT, 2)
                else:  # Floor
                    if self.floor_texture:
                        self._draw_texture(self.floor_texture, screen_x, screen_y, tint)
                    else:
                        tile_rect = arcade.LBWH(screen_x, screen_y, tile_size - 1, tile_size - 1)
                        arcade.draw_rect_filled(tile_rect, (40, 35, 30))

        # Draw entities (monsters, items) from EntityManager with lighting
        for entity in self.entity_manager.get_all():
            # Skip party members - they're drawn separately in combat
            if entity.entity_type == EntityType.PARTY_MEMBER:
                continue

            # Skip dead entities
            if not entity.is_alive:
                continue

            if self.fog:
                state = self.fog.get_visibility(entity.grid_x, entity.grid_y)
                fog_tint = LIGHTING_TINTS.get(state)
            else:
                fog_tint = (255, 255, 255)

            # Only draw visible entities
            if fog_tint is None:
                continue

            screen_x = offset_x + entity.grid_x * tile_size
            screen_y = offset_y + (self.room_layout.height - 1 - entity.grid_y) * tile_size

            # Calculate final tint (fog + targeting)
            final_tint = fog_tint
            in_range = False

            # Apply targeting tint for monsters during combat
            if (
                self.current_mode == GameMode.COMBAT
                and entity.entity_type == EntityType.MONSTER
                and entity.is_alive
            ):
                from dnd_engine.core.distance import distance_in_feet
                from dnd_engine.systems.inventory import EquipmentSlot

                # Get current combatant position for range check
                combatant_pos = self.entity_manager.get_current_turn_position(self.engine)
                if combatant_pos is None:
                    combatant_x, combatant_y = self.player_x, self.player_y
                else:
                    combatant_x, combatant_y = combatant_pos

                distance_ft = distance_in_feet(
                    combatant_x, combatant_y, entity.grid_x, entity.grid_y
                )

                # Get attacker's equipped weapon range
                current = self.engine.get_current_combatant()
                weapon_data = None
                if current and current["is_player"]:
                    creature = current["creature"]
                    if hasattr(creature, "inventory"):
                        weapon_id = creature.inventory.get_equipped_item(EquipmentSlot.WEAPON)
                        if weapon_id and self.engine.game_state:
                            items_data = self.engine.game_state.data_loader.load_items(
                                self.engine.game_state.campaign_id
                            )
                            weapon_data = items_data.get("weapons", {}).get(weapon_id, {})

                _normal_range, max_range = get_attack_range(weapon_data)
                in_range = distance_ft <= max_range

                # Apply targeting tint (green = in range, red = out of range)
                if in_range:
                    targeting_tint = TargetingColors.IN_RANGE_TINT
                else:
                    targeting_tint = TargetingColors.OUT_OF_RANGE_TINT
                final_tint = self._multiply_tints(fog_tint, targeting_tint)

            if entity.texture:
                self._draw_texture(entity.texture, screen_x, screen_y, final_tint)
            else:
                # Fallback: colored squares based on entity type
                if entity.entity_type == EntityType.MONSTER:
                    fallback_color = (180, 50, 50)  # Red for monsters
                elif entity.entity_type == EntityType.ITEM:
                    fallback_color = (50, 180, 50)  # Green for items
                else:
                    fallback_color = (180, 140, 50)  # Gold for decorations
                tile_rect = arcade.LBWH(screen_x + 4, screen_y + 4, tile_size - 8, tile_size - 8)
                arcade.draw_rect_filled(tile_rect, fallback_color)

            # Draw targeting overlays for monsters during combat
            if (
                self.current_mode == GameMode.COMBAT
                and entity.entity_type == EntityType.MONSTER
                and entity.is_alive
            ):
                center_x = screen_x + tile_size // 2
                center_y = screen_y + tile_size // 2

                # Draw pulsing selection ring for selected target
                if entity == self.selected_target:
                    # Calculate pulse value (0.0 to 1.0)
                    pulse = (
                        math.sin(self.pulse_timer * 2 * math.pi / PULSE_CYCLE_DURATION) + 1
                    ) / 2

                    # Pulsing glow
                    glow_radius = tile_size // 2 + 2 + int(pulse * 6)
                    glow_alpha = int(60 + pulse * 60)
                    arcade.draw_circle_filled(
                        center_x,
                        center_y,
                        glow_radius,
                        (*TargetingColors.SELECTED_RING, glow_alpha),
                    )

                    # Pulsing ring thickness
                    ring_thickness = 2 + int(pulse * 2)
                    arcade.draw_circle_outline(
                        center_x,
                        center_y,
                        tile_size // 2 + 4,
                        TargetingColors.SELECTED_RING,
                        ring_thickness,
                    )

                # Draw hover highlight
                elif entity == self.hovered_entity:
                    arcade.draw_circle_outline(
                        center_x, center_y, tile_size // 2 + 2, arcade.color.WHITE, 2
                    )

        # Draw party/player
        if self.party_spread and self.party_positions:
            # Combat formation - draw each party member from EntityManager
            for party_entity in self.entity_manager.get_party_members():
                char_screen_x = offset_x + party_entity.grid_x * tile_size
                char_screen_y = (
                    offset_y + (self.room_layout.height - 1 - party_entity.grid_y) * tile_size
                )

                char_class = party_entity.character_class
                is_current_turn = party_entity.is_current_turn
                texture = party_entity.texture or self.player_texture

                # Draw current turn highlight (selection ring)
                if is_current_turn:
                    center_x = char_screen_x + tile_size // 2
                    center_y = char_screen_y + tile_size // 2
                    arcade.draw_circle_outline(
                        center_x, center_y, tile_size // 2 + 2, UIColors.TEXT_HIGHLIGHT, 3
                    )

                # Draw character texture or fallback
                if texture:
                    self._draw_texture(texture, char_screen_x, char_screen_y)
                else:
                    center_x = char_screen_x + tile_size // 2
                    center_y = char_screen_y + tile_size // 2
                    color = UIColors.TEXT_HIGHLIGHT if is_current_turn else UIColors.HP_FULL
                    arcade.draw_circle_filled(center_x, center_y, tile_size // 3, color)
                    # Show first letter of class
                    arcade.draw_text(
                        char_class[0].upper(),
                        center_x,
                        center_y - 5,
                        (255, 255, 255),
                        14,
                        anchor_x="center",
                    )

                # Draw torch glow on current turn character
                if is_current_turn:
                    center_x = char_screen_x + tile_size // 2
                    center_y = char_screen_y + tile_size // 2
                    arcade.draw_circle_filled(center_x, center_y, 6, arcade.color.ORANGE)
        else:
            # Exploration mode - single unit
            player_screen_x = offset_x + self.player_x * tile_size
            player_screen_y = offset_y + (self.room_layout.height - 1 - self.player_y) * tile_size

            if self.player_texture:
                self._draw_texture(self.player_texture, player_screen_x, player_screen_y)
            else:
                # Fallback colored circle with @ symbol
                center_x = player_screen_x + tile_size // 2
                center_y = player_screen_y + tile_size // 2
                arcade.draw_circle_filled(center_x, center_y, tile_size // 3, UIColors.HP_FULL)
                arcade.draw_text(
                    "@", center_x, center_y - 5, (255, 255, 255), 14, anchor_x="center"
                )

            # Draw light indicator on player (torch glow)
            center_x = player_screen_x + tile_size // 2
            center_y = player_screen_y + tile_size // 2
            arcade.draw_circle_filled(center_x, center_y, 6, arcade.color.ORANGE)

        # Draw exit indicators
        exits = self._get_available_exits()
        for direction in exits:
            if self.room_layout:
                exit_pos = self.room_layout.spawn_points.exits.get(direction)
                if exit_pos:
                    exit_x, exit_y = exit_pos
                    exit_screen_x = offset_x + exit_x * tile_size + tile_size // 2
                    exit_screen_y = (
                        offset_y
                        + (self.room_layout.height - 1 - exit_y) * tile_size
                        + tile_size // 2
                    )
                    arcade.draw_text(
                        direction[0].upper(),  # N, S, E, W
                        exit_screen_x,
                        exit_screen_y - 5,
                        UIColors.TEXT_HIGHLIGHT,
                        12,
                        anchor_x="center",
                        bold=True,
                    )

    def _draw_combat_overlay(self, x: float, y: float, w: float, h: float) -> None:
        """Draw combat mode overlay on the viewport."""
        # Semi-transparent overlay
        overlay_rect = arcade.LBWH(x + 2, y + 2, w - 4, 80)
        arcade.draw_rect_filled(overlay_rect, (0, 0, 0, 180))

        status = "COMBAT!"
        if self.processing_enemy_turn:
            status += " - Enemy turn..."
        elif self.engine.is_player_turn():
            current = self.engine.get_current_combatant()
            if current:
                status += f" - {current['name']}'s turn"
                # Add movement remaining for player turns
                turn_state = self.engine.get_current_turn_state()
                if turn_state:
                    status += f" ({turn_state.movement_remaining} ft)"

        arcade.draw_text(
            status,
            x + w // 2,
            y + 60,
            UIColors.HP_LOW,
            FONT_SIZE_TITLE,
            anchor_x="center",
            bold=True,
        )

        # Enemy list with selection
        enemies = self.engine.get_enemies()
        enemy_text = "  ".join(
            f"{'>' if i == self.selected_enemy else ' '}{i + 1}.{e['name']}({e['hp']}hp)"
            for i, e in enumerate(enemies)
        )
        arcade.draw_text(
            enemy_text,
            x + w // 2,
            y + 30,
            UIColors.TEXT,
            FONT_SIZE_BODY,
            anchor_x="center",
        )

        # Controls hint. Hide is offered only when the engine's #496 gate
        # passes for the current combatant (heavy obscurement or cover),
        # matching GameState.get_available_actions().
        controls = "1-9: Select  |  A: Attack  |  WASD/Arrows: Move  |  Space: Wait"
        game_state = self.engine.game_state
        if game_state is not None and "hide" in game_state.get_available_actions():
            controls += "  |  H: Hide"
        arcade.draw_text(
            controls,
            x + w // 2,
            y + UI_PADDING,
            UIColors.TEXT_DIM,
            FONT_SIZE_SMALL,
            anchor_x="center",
        )

    def _draw_context_panel(self, x: float, y: float, w: float, h: float) -> None:
        """Draw the context panel (party status / combat initiative)."""
        # Background
        rect = arcade.LBWH(x, y, w, h)
        arcade.draw_rect_filled(rect, UIColors.PANEL_BG)
        arcade.draw_rect_outline(rect, UIColors.BORDER, UI_BORDER_WIDTH)

        if self.engine.in_combat:
            self._draw_combat_panel(x, y, w, h)
        else:
            self._draw_party_panel(x, y, w, h)

    def _draw_party_panel(self, x: float, y: float, w: float, h: float) -> None:
        """Draw party status panel."""
        arcade.draw_text(
            "PARTY",
            x + UI_PADDING,
            y + h - UI_PADDING - FONT_SIZE_TITLE,
            UIColors.TEXT_HIGHLIGHT,
            FONT_SIZE_TITLE,
            bold=True,
        )

        party_data = self.engine.get_party_data()
        row_h = 50
        start_y = y + h - 60

        for i, member in enumerate(party_data):
            row_y = start_y - (i * row_h)

            # Name and class
            arcade.draw_text(
                f"{member['name']}",
                x + UI_PADDING,
                row_y,
                UIColors.TEXT_HIGHLIGHT,
                FONT_SIZE_BODY,
                bold=True,
            )
            arcade.draw_text(
                f"{member['class']}",
                x + UI_PADDING,
                row_y - 18,
                UIColors.TEXT_DIM,
                FONT_SIZE_SMALL,
            )

            # HP bar
            hp_pct = member["hp"] / member["max_hp"] if member["max_hp"] > 0 else 0
            bar_w = w - UI_PADDING * 4 - 60
            bar_x = x + UI_PADDING
            bar_y = row_y - 35

            # Background
            bg_rect = arcade.LBWH(bar_x, bar_y, bar_w, 8)
            arcade.draw_rect_filled(bg_rect, UIColors.HP_BG)

            # Fill
            if hp_pct > 0:
                if hp_pct > 0.5:
                    color = UIColors.HP_FULL
                elif hp_pct > 0.25:
                    color = UIColors.HP_MEDIUM
                else:
                    color = UIColors.HP_LOW
                fill_rect = arcade.LBWH(bar_x, bar_y, bar_w * hp_pct, 8)
                arcade.draw_rect_filled(fill_rect, color)

            # HP text
            arcade.draw_text(
                f"{member['hp']}/{member['max_hp']}",
                bar_x + bar_w + 5,
                bar_y - 2,
                UIColors.TEXT,
                FONT_SIZE_SMALL,
            )

    def _draw_combat_panel(self, x: float, y: float, w: float, h: float) -> None:
        """Draw combat initiative panel."""
        combat_data = self.engine.get_combat_data()
        if not combat_data:
            return

        arcade.draw_text(
            f"COMBAT - Round {combat_data['round']}",
            x + UI_PADDING,
            y + h - UI_PADDING - FONT_SIZE_TITLE,
            UIColors.HP_LOW,
            FONT_SIZE_TITLE,
            bold=True,
        )

        row_h = 35
        start_y = y + h - 60

        for i, combatant in enumerate(combat_data["initiative"]):
            row_y = start_y - (i * row_h)
            is_current = i == combat_data["current_turn"]

            # Highlight current turn
            if is_current:
                highlight_rect = arcade.LBWH(x + 2, row_y - 10, w - 4, row_h - 2)
                arcade.draw_rect_filled(highlight_rect, UIColors.SELECTION)

            # Initiative number
            arcade.draw_text(
                f"{combatant['init']:2d}",
                x + UI_PADDING,
                row_y,
                UIColors.TEXT_DIM,
                FONT_SIZE_BODY,
            )

            # Name
            name_color = UIColors.TEXT_HIGHLIGHT if combatant["is_player"] else UIColors.HP_LOW
            arcade.draw_text(
                combatant["name"],
                x + UI_PADDING + 35,
                row_y,
                name_color,
                FONT_SIZE_BODY,
                bold=is_current,
            )

            # HP
            hp_pct = combatant["hp"] / combatant["max_hp"] if combatant["max_hp"] > 0 else 0
            if hp_pct > 0.5:
                hp_color = UIColors.HP_FULL
            elif hp_pct > 0.25:
                hp_color = UIColors.HP_MEDIUM
            else:
                hp_color = UIColors.HP_LOW

            arcade.draw_text(
                f"{combatant['hp']}/{combatant['max_hp']}",
                x + w - UI_PADDING - 60,
                row_y,
                hp_color,
                FONT_SIZE_BODY,
            )

    def _draw_narrative_panel(self, x: float, y: float, w: float, h: float) -> None:
        """Draw the narrative/combat log panel."""
        # Background
        rect = arcade.LBWH(x, y, w, h)
        arcade.draw_rect_filled(rect, UIColors.PANEL_BG)
        arcade.draw_rect_outline(rect, UIColors.BORDER, UI_BORDER_WIDTH)

        arcade.draw_text(
            "COMBAT LOG",
            x + UI_PADDING,
            y + h - UI_PADDING - FONT_SIZE_TITLE,
            UIColors.TEXT_HIGHLIGHT,
            FONT_SIZE_TITLE,
            bold=True,
        )

        # Display combat log
        log_y = y + h - 50
        for i, msg in enumerate(reversed(self.combat_log[-5:])):
            arcade.draw_text(
                msg,
                x + UI_PADDING,
                log_y - (i * 20),
                UIColors.TEXT,
                FONT_SIZE_BODY,
            )

    def _draw_screenshot_feedback(self) -> None:
        """Draw screenshot saved feedback overlay."""
        # Semi-transparent background box at top center
        msg_width = len(self.screenshot_message) * 10 + 40
        msg_height = 40
        msg_x = (self.width - msg_width) // 2
        msg_y = self.height - msg_height - 10

        # Draw background
        bg_rect = arcade.LBWH(msg_x, msg_y, msg_width, msg_height)
        arcade.draw_rect_filled(bg_rect, (0, 0, 0, 200))
        arcade.draw_rect_outline(bg_rect, UIColors.TEXT_HIGHLIGHT, 2)

        # Draw text
        arcade.draw_text(
            self.screenshot_message,
            self.width // 2,
            msg_y + msg_height // 2 - 8,
            UIColors.TEXT_HIGHLIGHT,
            FONT_SIZE_BODY,
            anchor_x="center",
            bold=True,
        )

    # ========== Targeting Helpers ==========

    def _get_map_render_params(self) -> tuple[float, float, float] | None:
        """Calculate map rendering parameters (offset_x, offset_y, tile_size).

        Returns None if room layout is not available.
        """
        if not self.room_layout:
            return None

        # Must match the calculation in _draw_dungeon_tiles exactly
        viewport_w = int(self.width * VIEWPORT_WIDTH_PCT)
        narrative_h = int(self.height * NARRATIVE_HEIGHT_PCT)
        main_h = self.height - narrative_h

        margin = 50
        available_h = main_h - margin * 2
        available_w = viewport_w - UI_PADDING * 2

        tile_size = min(
            available_w // self.room_layout.width,
            available_h // self.room_layout.height,
            TILE_SIZE,
        )

        map_w = self.room_layout.width * tile_size
        map_h = self.room_layout.height * tile_size
        offset_x = (viewport_w - map_w) // 2
        offset_y = narrative_h + margin + (available_h - map_h) // 2

        return (offset_x, offset_y, tile_size)

    def _screen_to_grid(self, screen_x: int, screen_y: int) -> tuple[int, int] | None:
        """Convert screen coordinates to grid position.

        Returns None if position is outside the map bounds.
        """
        params = self._get_map_render_params()
        if params is None or self.room_layout is None:
            return None

        offset_x, offset_y, tile_size = params

        # Convert screen coords to grid (accounting for Y-flip)
        grid_x = int((screen_x - offset_x) // tile_size)
        grid_y = self.room_layout.height - 1 - int((screen_y - offset_y) // tile_size)

        # Bounds check
        if 0 <= grid_x < self.room_layout.width and 0 <= grid_y < self.room_layout.height:
            return (grid_x, grid_y)
        return None

    # ========== Update Loop ==========

    def on_update(self, delta_time: float) -> None:
        """Update game state."""
        # Advance non-rendering state (MCP commands + combat state machine).
        self.session.tick(delta_time)

        # Update screenshot feedback timer (rendering-only).
        if self.screenshot_message_timer > 0:
            self.screenshot_message_timer -= delta_time
            if self.screenshot_message_timer <= 0:
                self.screenshot_message = ""

        # Update pulse timer for targeting animation (rendering-only).
        if self.current_mode == GameMode.COMBAT:
            self.pulse_timer += delta_time

    def on_key_press(self, key: int, modifiers: int) -> None:
        """Handle key presses."""
        # ESC behavior depends on context
        if key == arcade.key.ESCAPE:
            # In combat with selected target: deselect first
            if self.current_mode == GameMode.COMBAT and self.selected_target:
                self.selected_target = None
                self._add_combat_log("Target deselected")
                return
            # Otherwise: close window
            self.window.close()
            return

        # Ctrl-P to take screenshot
        if key == arcade.key.P and (modifiers & arcade.key.MOD_CTRL):
            self.save_screenshot()
            return

        if self.engine.in_combat and not self.processing_enemy_turn:
            self._handle_combat_input(key, modifiers)
        else:
            self._handle_exploration_input(key)

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> None:
        """Track mouse position and update hovered entity."""
        self.mouse_x = x
        self.mouse_y = y

        # Only track hovered entities during combat
        if self.current_mode != GameMode.COMBAT:
            self.hovered_entity = None
            return

        # Convert screen position to grid and find entity
        grid_pos = self._screen_to_grid(x, y)
        if grid_pos:
            self.hovered_entity = self.entity_manager.get_at_position(*grid_pos)
        else:
            self.hovered_entity = None

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        """Handle mouse clicks for targeting."""
        # Only handle targeting during combat and on player's turn
        if self.current_mode != GameMode.COMBAT:
            return
        if self.processing_enemy_turn:
            return
        if not self.engine.is_player_turn():
            current = self.engine.get_current_combatant()
            if current:
                self._add_combat_log(f"Wait - it's {current['name']}'s turn!")
            return

        # Get entity at click position
        grid_pos = self._screen_to_grid(x, y)
        if not grid_pos:
            return

        entity = self.entity_manager.get_at_position(*grid_pos)

        # Left-click: select target
        if button == arcade.MOUSE_BUTTON_LEFT:
            if entity and entity.entity_type == EntityType.MONSTER and entity.is_alive:
                self.selected_target = entity
                self.pulse_timer = 0.0  # Reset pulse animation
                # Also update selected_enemy for compatibility with existing attack system
                self.selected_enemy = entity.enemy_index
                self._add_combat_log(f"Selected: {entity.sub_type or entity.entity_id}")

        # Right-click: direct attack (no confirmation)
        elif button == arcade.MOUSE_BUTTON_RIGHT:
            if entity and entity.entity_type == EntityType.MONSTER and entity.is_alive:
                self._attack_entity(entity)

    def _attack_entity(self, target: Entity) -> None:
        """Execute attack on a specific entity."""
        from dnd_engine.core.distance import distance_in_feet
        from dnd_engine.systems.inventory import EquipmentSlot

        # Get current combatant position for range check
        combatant_pos = self.entity_manager.get_current_turn_position(self.engine)
        if combatant_pos is None:
            combatant_x, combatant_y = self.player_x, self.player_y
        else:
            combatant_x, combatant_y = combatant_pos

        # Calculate distance in feet (each square = 5 ft)
        distance_ft = distance_in_feet(combatant_x, combatant_y, target.grid_x, target.grid_y)

        # Get attacker's equipped weapon and its range
        current = self.engine.get_current_combatant()
        weapon_data = None
        weapon_name = "Unarmed"
        if current and current["is_player"]:
            creature = current["creature"]
            if hasattr(creature, "inventory"):
                weapon_id = creature.inventory.get_equipped_item(EquipmentSlot.WEAPON)
                if weapon_id:
                    items_data = self.engine.game_state.data_loader.load_items(
                        self.engine.game_state.campaign_id
                    )
                    weapon_data = items_data.get("weapons", {}).get(weapon_id, {})
                    weapon_name = weapon_data.get("name", weapon_id.replace("_", " ").title())

        normal_range, max_range = get_attack_range(weapon_data)

        # Check if target is in range
        if distance_ft > max_range:
            self._add_combat_log(
                f"Out of range! ({distance_ft} ft away, {weapon_name} max: {max_range} ft)"
            )
            return

        # Long-range attacks roll with disadvantage per D&D 5E.
        in_long_range = distance_ft > normal_range
        if in_long_range:
            self._add_combat_log(f"{weapon_name} at {distance_ft} ft (long range - disadvantage)")

        # Set selected enemy and execute attack
        self.selected_enemy = target.enemy_index
        self.selected_target = target
        self._execute_attack(disadvantage=in_long_range)

    def _cycle_target(self, reverse: bool = False) -> None:
        """Cycle through targets sorted by distance (nearest first)."""
        from dnd_engine.core.distance import chebyshev_distance

        monsters = self.entity_manager.get_monsters()
        if not monsters:
            self._add_combat_log("No targets available")
            return

        # Get combatant position
        combatant_pos = self.entity_manager.get_current_turn_position(self.engine)
        if combatant_pos is None:
            combatant_x, combatant_y = self.player_x, self.player_y
        else:
            combatant_x, combatant_y = combatant_pos

        # Sort by distance (nearest first)
        sorted_monsters = sorted(
            monsters,
            key=lambda m: chebyshev_distance(combatant_x, combatant_y, m.grid_x, m.grid_y),
        )

        # Find current index in sorted list
        current_idx = -1
        if self.selected_target in sorted_monsters:
            current_idx = sorted_monsters.index(self.selected_target)

        # Calculate next index
        if reverse:
            next_idx = (current_idx - 1) % len(sorted_monsters)
        else:
            next_idx = (current_idx + 1) % len(sorted_monsters)

        # Update selection
        self.selected_target = sorted_monsters[next_idx]
        self.selected_enemy = self.selected_target.enemy_index
        self.pulse_timer = 0.0  # Reset pulse animation

        name = self.selected_target.sub_type or self.selected_target.entity_id
        self._add_combat_log(f"Target: {name}")

    def _handle_combat_input(self, key: int, modifiers: int = 0) -> None:
        """Handle combat-mode input."""
        if not self.engine.is_player_turn():
            # Provide feedback instead of silently ignoring
            current = self.engine.get_current_combatant()
            if current:
                self._add_combat_log(f"Wait - it's {current['name']}'s turn!")
            return

        # Tab to cycle targets (Shift+Tab for reverse)
        if key == arcade.key.TAB:
            self._cycle_target(reverse=bool(modifiers & arcade.key.MOD_SHIFT))
            return

        # Escape to deselect target
        if key == arcade.key.ESCAPE:
            if self.selected_target:
                self.selected_target = None
                self._add_combat_log("Target deselected")
            return

        # Number keys to select enemy
        if arcade.key.KEY_1 <= key <= arcade.key.KEY_9:
            display_index = key - arcade.key.KEY_1
            monsters = self.entity_manager.get_monsters()
            if display_index < len(monsters):
                self.selected_target = monsters[display_index]
                self.selected_enemy = self.selected_target.enemy_index
                name = self.selected_target.sub_type or self.selected_target.entity_id
                self._add_combat_log(f"Selected: {name}")

        # A or Enter to attack selected target
        elif key in (arcade.key.A, arcade.key.ENTER):
            if self.selected_target:
                self._attack_entity(self.selected_target)
            else:
                self._add_combat_log("No target selected! Press Tab or 1-9 to select.")

        # Space to wait/pass
        elif key == arcade.key.SPACE:
            self._pass_turn()

        # H to take the Hide action (gated on concealment/cover; the
        # session logs the refusal when the #496 environment gate fails)
        elif key == arcade.key.H:
            self._hide()

        # WASD/Arrow movement during combat (uses action economy)
        elif key in (arcade.key.W, arcade.key.UP):
            self._handle_combat_movement("north")
        elif key in (arcade.key.S, arcade.key.DOWN):
            self._handle_combat_movement("south")
        elif key in (arcade.key.D, arcade.key.RIGHT):
            self._handle_combat_movement("east")
        elif key == arcade.key.LEFT:  # A is attack, so only LEFT arrow for west
            self._handle_combat_movement("west")

    def _handle_exploration_input(self, key: int) -> None:
        """Handle exploration-mode input."""
        # WASD / Arrow movement
        if key == arcade.key.W or key == arcade.key.UP:
            self._move_player("north")
        elif key == arcade.key.S or key == arcade.key.DOWN:
            self._move_player("south")
        elif key == arcade.key.A or key == arcade.key.LEFT:
            self._move_player("west")
        elif key == arcade.key.D or key == arcade.key.RIGHT:
            self._move_player("east")

    def _handle_combat_movement(self, direction: str) -> None:
        """Handle keyboard-triggered combat movement with feedback."""
        result = self._mcp_combat_move(direction)

        # Extract first line for combat log (MCP returns full state after newline)
        feedback = result.split("\n")[0]

        # Always show feedback in combat log
        self._add_combat_log(feedback)


class GameWindow(arcade.Window):
    """Thin host window that shows gameplay / menu views.

    Owns the OS window + GL context only; gameplay lives in
    :class:`GameView`. Constructing the window immediately shows a GameView
    so the windowed entry point behaves exactly as before, while leaving
    room to swap in the launch-screen views (#626-#630) via show_view.
    """

    def __init__(
        self,
        width: int = 1280,
        height: int = 900,
        fullscreen: bool = False,
        enable_mcp: bool = False,
        mcp_port: int = 8765,
        dev_mode: bool = False,
    ):
        """Create the host window and show the gameplay view.

        Args:
            width: Window width in pixels.
            height: Window height in pixels.
            fullscreen: Whether to run in fullscreen mode.
            enable_mcp: Whether to start embedded MCP server.
            mcp_port: Port for MCP HTTP server.
            dev_mode: Whether to register --dev spawn/setup MCP tools.
        """
        super().__init__(width, height, WINDOW_TITLE, fullscreen=fullscreen)
        arcade.set_background_color(UIColors.PANEL_BG_DARK)

        self.show_view(
            GameView(
                enable_mcp=enable_mcp,
                mcp_port=mcp_port,
                dev_mode=dev_mode,
            )
        )


def run_2d_client(
    size: str = "medium",
    fullscreen: bool = False,
    enable_mcp: bool = False,
    mcp_port: int = 8765,
    dev_mode: bool = False,
) -> None:
    """Entry point for the 2D client.

    Args:
        size: Window size preset (small, medium, large).
        fullscreen: Whether to run in fullscreen mode.
        enable_mcp: Whether to start embedded MCP HTTP server.
        mcp_port: Port for MCP server (default 8765).
        dev_mode: Whether to register --dev spawn/setup MCP tools.
    """
    width, height = WINDOW_SIZES.get(size, WINDOW_SIZES["medium"])

    # For fullscreen, use large dimensions as starting point
    if fullscreen:
        width, height = WINDOW_SIZES["large"]

    print("=" * 50)
    print("D&D 5E - 2D Graphical Client")
    print("=" * 50)
    if fullscreen:
        print("Mode: Fullscreen")
    else:
        print(f"Window: {width}x{height} ({size})")
    if enable_mcp:
        print(f"MCP Server: http://127.0.0.1:{mcp_port}/sse")
    if dev_mode:
        print("Dev mode: ENABLED (spawn_monster/spawn_character/... available)")
    print()

    GameWindow(
        width=width,
        height=height,
        fullscreen=fullscreen,
        enable_mcp=enable_mcp,
        mcp_port=mcp_port,
        dev_mode=dev_mode,
    )
    arcade.run()


if __name__ == "__main__":
    run_2d_client()
