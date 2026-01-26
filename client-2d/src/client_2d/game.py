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
from client_2d.entities import Entity, EntityManager, EntityType
from client_2d.integration.engine_adapter import EngineAdapter
from client_2d.integration.layout_loader import LayoutLoader
from client_2d.systems.fog_of_war import FogOfWarSystem
from client_2d.systems.lighting import LightingSystem
from client_2d.testing.state_renderer import Entity as StateEntity
from client_2d.testing.state_renderer import StateRenderer

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


class GameWindow(arcade.Window):
    """Main game window with real engine integration."""

    def __init__(
        self,
        width: int = 1280,
        height: int = 900,
        fullscreen: bool = False,
        enable_mcp: bool = False,
        mcp_port: int = 8765,
    ):
        """Initialize the game window.

        Args:
            width: Window width in pixels.
            height: Window height in pixels.
            fullscreen: Whether to run in fullscreen mode.
            enable_mcp: Whether to start embedded MCP server.
            mcp_port: Port for MCP HTTP server.
        """
        super().__init__(width, height, WINDOW_TITLE, fullscreen=fullscreen)
        arcade.set_background_color(UIColors.PANEL_BG_DARK)

        # MCP server integration (initialized later if enabled)
        self._mcp_bridge = None
        self._mcp_server = None
        self._state_renderer: StateRenderer | None = None
        self._enable_mcp = enable_mcp
        self._mcp_port = mcp_port

        # Engine adapter
        self.engine = EngineAdapter()
        self.layout_loader = LayoutLoader()

        # Asset manager and textures
        self.assets = AssetManager(assets_path=ASSETS_DIR)
        self._load_textures()

        # Room/map state
        self.room_layout = None
        self.room_tiles: list[list[int]] = []
        self.player_x = 0
        self.player_y = 0

        # Party position tracking for combat (spread formation)
        self.party_spread = False
        self.party_positions: list[tuple[int, int]] = []

        # Fog of war and lighting systems (initialized per-room)
        self.fog: FogOfWarSystem | None = None
        self.lighting: LightingSystem | None = None

        # Entity manager for live-synced entities with engine references
        self.entity_manager = EntityManager()

        # Game state
        self.running = True
        self.current_mode = GameMode.EXPLORATION
        self.selected_enemy = 0
        self.enemy_turn_timer = 0.0
        self.processing_enemy_turn = False
        self.combat_log: list[str] = []

        # Screenshot feedback state
        self.screenshot_message: str = ""
        self.screenshot_message_timer: float = 0.0

        # Mouse targeting state (for #355 unified targeting)
        self.mouse_x: int = 0
        self.mouse_y: int = 0
        self.hovered_entity: Entity | None = None
        self.selected_target: Entity | None = None
        self.pulse_timer: float = 0.0

        # Initialize the game
        self._initialize_game()

        # Initialize MCP server if enabled
        if self._enable_mcp:
            self._initialize_mcp_server()

    def _initialize_game(self) -> None:
        """Initialize game with party and dungeon."""
        print("Loading party from vault...")
        party_info = self.engine.load_party_from_vault()
        for char in party_info:
            print(f"  - {char['name']} ({char['class']} L{char['level']})")

        print("\nInitializing game in cellar dungeon...")
        game_info = self.engine.initialize_game(
            dungeon_name="cellar",
            campaign_id="poisoned_laboratory",
            start_room="cellar.stairs",  # Start in safe room, rats are north
        )
        print(f"  Starting room: {game_info['room_name']}")
        print("  Hint: Go NORTH to find the rats!")

        # Load room layout for rendering
        self._load_room_layout()

        print("\nStarting game...")
        start_info = self.engine.start_game()
        if start_info["in_combat"]:
            print(f"  Combat started! Enemies: {', '.join(start_info['enemies'])}")
            self.current_mode = GameMode.COMBAT
            self._spread_party_for_combat()
            self._add_combat_log(f"Combat begins! {len(start_info['enemies'])} enemies!")
            # Show whose turn it is
            current = self.engine.get_current_combatant()
            if current:
                self._add_combat_log(f"{current['name']}'s turn first!")
            # If enemy goes first or player is unconscious, start auto-turn processing
            if not self.engine.is_player_turn():
                self.processing_enemy_turn = True
                self.enemy_turn_timer = ENEMY_TURN_DELAY
            elif self.engine.is_current_combatant_unconscious():
                # Unconscious player goes first - process their death save
                self.processing_enemy_turn = True
                self.enemy_turn_timer = ENEMY_TURN_DELAY
        else:
            print("  No enemies in starting room. Explore with WASD!")
            self._add_combat_log("Use WASD to move. Go NORTH to find the rats!")

    def _add_combat_log(self, message: str) -> None:
        """Add a message to the combat log."""
        self.combat_log.append(message)
        # Keep only last 10 messages
        if len(self.combat_log) > 10:
            self.combat_log = self.combat_log[-10:]

    # ========== MCP Server Integration ==========

    def _initialize_mcp_server(self) -> None:
        """Initialize embedded MCP server with HTTP transport."""
        from client_2d.embedded_mcp_server import EmbeddedMCPServer
        from client_2d.mcp_bridge import MCPBridge

        self._mcp_bridge = MCPBridge()
        self._mcp_bridge.set_game_window(self)

        # Create StateRenderer for ASCII map generation
        width = self.room_layout.width if self.room_layout else 25
        height = self.room_layout.height if self.room_layout else 18
        self._state_renderer = StateRenderer(width=width, height=height)

        self._mcp_server = EmbeddedMCPServer(
            bridge=self._mcp_bridge,
            port=self._mcp_port,
        )
        self._mcp_server.start()

    def _process_mcp_commands(self) -> None:
        """Process pending MCP commands from the HTTP server thread.

        Called from on_update() to process commands in the main thread.
        Only processes one command per frame to avoid blocking rendering.
        """
        if self._mcp_bridge is None:
            return

        # Skip if enemy turn is being processed (avoid inconsistent state)
        if self.processing_enemy_turn:
            return

        request = self._mcp_bridge.poll_commands()
        if request is None:
            return

        from client_2d.mcp_bridge import CommandType

        try:
            if request.command_type == CommandType.GET_STATE:
                result = self._mcp_get_state()
            elif request.command_type == CommandType.MOVE:
                result = self._mcp_move(request.args.get("direction", ""))
            elif request.command_type == CommandType.ATTACK:
                # Support both int index and str entity_id
                target = request.args.get("target", request.args.get("target_index", 0))
                result = self._mcp_attack(target)
            elif request.command_type == CommandType.WAIT:
                result = self._mcp_wait()
            else:
                result = f"Unknown command: {request.command_type}"
            request.response_future.set_result(result)
        except Exception as e:
            request.response_future.set_exception(e)

    def _mcp_get_state(self) -> str:
        """Generate state response using StateRenderer."""
        if self._state_renderer is None or self.room_layout is None or self.fog is None:
            return "Game not initialized"

        entities = self._build_state_entities()

        # Get turn info
        turn = 0
        if self.engine.game_state:
            tracker = self.engine.game_state.initiative_tracker
            if tracker:
                turn = tracker.round_number

        # Get party HP
        player_hp = 30
        player_max_hp = 30
        party_data = self.engine.get_party_data()
        if party_data:
            player_hp = sum(c["hp"] for c in party_data)
            player_max_hp = sum(c["max_hp"] for c in party_data)

        state = self._state_renderer.render_state(
            room=self.room_tiles,
            player_x=self.player_x,
            player_y=self.player_y,
            entities=entities,
            fog=self.fog,
            turn=turn,
            player_hp=player_hp,
            player_max_hp=player_max_hp,
            light_source="torch",
        )

        return self._format_mcp_state_response(state)

    def _build_state_entities(self) -> list[StateEntity]:
        """Build entity list for StateRenderer from EntityManager."""
        entities: list[StateEntity] = []

        # Sync from engine and remove dead entities before rendering
        self.entity_manager.sync_from_engine(self.engine)
        self.entity_manager.remove_dead_entities()

        for entity in self.entity_manager.get_all():
            if not entity.is_alive:
                continue

            # Map EntityType to string type for StateRenderer
            if entity.entity_type == EntityType.MONSTER:
                type_str = "monster"
            elif entity.entity_type == EntityType.ITEM:
                type_str = "item"
            elif entity.entity_type == EntityType.PARTY_MEMBER:
                type_str = "party"
            else:
                type_str = "decoration"

            # Use unique entity_id to ensure each entity has its own symbol
            # Include sub_type in the ID for readable display (e.g., "giant_rat" not "monster_0")
            display_id = entity.sub_type or entity.entity_id
            unique_suffix = entity.entity_id.split("_")[-1]  # Extract index like "0", "1"
            unique_id = f"{display_id}_{unique_suffix}" if entity.sub_type else entity.entity_id

            entities.append(
                StateEntity(
                    x=entity.grid_x,
                    y=entity.grid_y,
                    entity_type=type_str,
                    entity_id=unique_id,
                )
            )

        return entities

    def _format_mcp_state_response(self, state_dict: dict) -> str:
        """Format state dict as readable MCP response."""
        if "error" in state_dict:
            return f"Error: {state_dict['error']}"

        lines = [
            f"Turn: {state_dict['turn']}",
            f"Party HP: {state_dict['player']['hp']}/{state_dict['player']['max_hp']} "
            f"Light: {state_dict['player']['light_source']}",
            f"Explored: {state_dict['explored_tiles']}/{state_dict['total_tiles']}",
        ]

        # Add combat info if in combat
        if self.engine.in_combat:
            combat_data = self.engine.get_combat_data()
            if combat_data:
                lines.append(f"Combat Round: {combat_data['round']}")
                current = self.engine.get_current_combatant()
                if current:
                    lines.append(f"Current Turn: {current['name']}")
                    # Show equipped weapon and range for player characters
                    if current["is_player"]:
                        from dnd_engine.systems.inventory import EquipmentSlot

                        creature = current["creature"]
                        weapon_name = "Unarmed"
                        range_text = "5 ft (melee)"
                        if hasattr(creature, "inventory"):
                            weapon_id = creature.inventory.get_equipped_item(
                                EquipmentSlot.WEAPON
                            )
                            if weapon_id and self.engine.game_state:
                                items_data = self.engine.game_state.data_loader.load_items(
                                    self.engine.game_state.campaign_id
                                )
                                weapon_data = items_data.get("weapons", {}).get(weapon_id, {})
                                weapon_name = weapon_data.get(
                                    "name", weapon_id.replace("_", " ").title()
                                )
                                normal_range, max_range = get_attack_range(weapon_data)
                                if max_range > 5:
                                    range_text = f"{normal_range}/{max_range} ft"
                                else:
                                    range_text = "5 ft (melee)"
                        lines.append(f"Equipped: {weapon_name} (range: {range_text})")

        lines.extend([
            "",
            "Map:",
            state_dict["map"],
            "",
            "Legend:",
        ])

        for symbol, entity in state_dict["legend"].items():
            lines.append(f"  {symbol} = {entity}")

        if state_dict["visible_entities"]:
            lines.append("")
            lines.append("Visible Entities:")
            for entity_id, info in state_dict["visible_entities"].items():
                lines.append(
                    f"  {info['symbol']} {info['type']}:{entity_id} "
                    f"at {info['position']} ({info['distance']} squares {info['direction']})"
                )

        # Add party status
        party_data = self.engine.get_party_data()
        if party_data:
            lines.append("")
            lines.append("Party:")
            for member in party_data:
                conditions = ", ".join(member.get("conditions", [])) or "healthy"
                lines.append(
                    f"  {member['name']} ({member['class']}): "
                    f"{member['hp']}/{member['max_hp']} HP - {conditions}"
                )

        # Add available actions
        lines.append("")
        lines.append("Available Actions:")
        if self.engine.in_combat:
            # Show movement remaining during combat
            turn_state = self.engine.get_current_turn_state()
            if turn_state:
                lines.append(f"  Movement: {turn_state.movement_remaining} ft remaining")
            lines.append("  - game_move(direction) - Move north/south/east/west")
            lines.append("  - game_attack(target) - Attack enemy in weapon range")
            lines.append("  - game_wait() - Pass turn")
        else:
            lines.append("  - game_move(direction) - Move north/south/east/west")

        return "\n".join(lines)

    def _mcp_move(self, direction: str) -> str:
        """Handle MCP move command - works in exploration AND combat."""
        direction = direction.lower()
        if direction not in ("north", "south", "east", "west"):
            return f"Invalid direction: {direction}. Use north/south/east/west."

        if self.engine.in_combat:
            return self._mcp_combat_move(direction)
        else:
            self._move_player(direction)
            return self._mcp_get_state()

    def _mcp_combat_move(self, direction: str) -> str:
        """Handle movement during combat with action economy."""
        # Check if it's player's turn
        if not self.engine.is_player_turn():
            return "Not your turn! Wait for enemies to act."

        # Get turn state for movement tracking
        turn_state = self.engine.get_current_turn_state()
        if turn_state is None:
            return "Error: Could not get turn state."

        # Check movement remaining (5 ft per grid square)
        if turn_state.movement_remaining < 5:
            current = self.engine.get_current_combatant()
            speed = current["creature"].speed if current else 30
            return f"No movement remaining (0/{speed} ft). Use game_attack() or game_wait()."

        # Calculate new position
        dx, dy = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}[direction]
        new_x = self.player_x + dx
        new_y = self.player_y + dy

        # Check bounds
        if not self.room_layout or not (
            0 <= new_x < self.room_layout.width and 0 <= new_y < self.room_layout.height
        ):
            return "Path blocked! Cannot move outside room."

        # Check wall
        if self.room_layout.is_blocking(new_x, new_y):
            return "Path blocked! Wall in the way."

        # Check entity collision (can't move through monsters)
        entity_at_dest = self.entity_manager.get_at_position(new_x, new_y)
        if entity_at_dest is not None and entity_at_dest in self.entity_manager.get_monsters():
            # Get display name from creature reference or format sub_type
            if entity_at_dest._creature_ref:
                name = entity_at_dest._creature_ref.name
            else:
                name = entity_at_dest.sub_type.replace("_", " ").title()
            return f"Path blocked! {name} is in the way."

        # Execute movement
        self.player_x = new_x
        self.player_y = new_y
        turn_state.consume_movement(5)
        self._update_lighting()

        # Sync visual position of current turn character
        self.entity_manager.update_current_turn_position(self.engine, new_x, new_y)

        # Return state with movement info
        remaining = turn_state.movement_remaining
        return f"Moved {direction}. Movement remaining: {remaining} ft.\n" + self._mcp_get_state()

    def _mcp_attack(self, target: int | str) -> str:
        """Handle MCP attack command.

        Args:
            target: Either a display index (int, 0-based) or an entity ID string
                   (e.g., "goblin_0", "giant_rat_1").
        """
        if not self.engine.in_combat:
            return "Not in combat! Use game_move() to explore."

        if not self.engine.is_player_turn():
            return "Not your turn! Wait for enemies to act."

        monsters = self.entity_manager.get_monsters()

        # Resolve target to entity
        if isinstance(target, int):
            # Validate target index
            if target < 0 or target >= len(monsters):
                return f"Invalid target index {target}. Valid: 0-{len(monsters)-1}"
            target_entity = monsters[target]
        else:
            # Find by entity_id string
            target_entity = next(
                (m for m in monsters if (
                    m.entity_id == target or
                    f"{m.sub_type}_{m.entity_id.split('_')[-1]}" == target
                )),
                None,
            )
            if target_entity is None:
                valid_ids = [
                    f"{m.sub_type}_{m.entity_id.split('_')[-1]}" if m.sub_type else m.entity_id
                    for m in monsters
                ]
                return f"Unknown target: {target}. Valid targets: {', '.join(valid_ids)}"

        # Check attack range based on equipped weapon
        target = target_entity
        from dnd_engine.core.distance import distance_in_feet
        from dnd_engine.systems.inventory import EquipmentSlot

        # Get current combatant's position (not player token position)
        combatant_pos = self.entity_manager.get_current_turn_position(self.engine)
        if combatant_pos is None:
            # Fallback to player position if combatant not found
            combatant_x, combatant_y = self.player_x, self.player_y
        else:
            combatant_x, combatant_y = combatant_pos

        # Calculate distance in feet (each square = 5 ft)
        distance_ft = distance_in_feet(
            combatant_x, combatant_y, target.grid_x, target.grid_y
        )

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
            turn_state = self.engine.get_current_turn_state()
            movement_info = (
                f" Movement remaining: {turn_state.movement_remaining} ft."
                if turn_state
                else ""
            )
            return (
                f"Out of range! ({distance_ft} ft away, {weapon_name} max range: {max_range} ft). "
                f"Move closer first.{movement_info}"
            )

        # Log range info (long range = disadvantage in future)
        in_long_range = distance_ft > normal_range
        if in_long_range:
            # Track for future disadvantage implementation
            self._add_combat_log(
                f"{weapon_name} attack at {distance_ft} ft (long range - disadvantage)"
            )

        # Track current combatant before attack to detect if turn advanced
        pre_attack_combatant = current["name"] if current else None

        # Set selected enemy and execute attack
        # Use target.enemy_index (engine index) not target_index (display index)
        self.selected_enemy = target.enemy_index
        self._execute_attack()

        # Check if attack succeeded by comparing combatant before/after
        # Turn advances on success, so different combatant = attack worked
        post_attack_combatant = self.engine.get_current_combatant()
        post_name = post_attack_combatant["name"] if post_attack_combatant else None

        # If same combatant and not processing enemies, attack didn't execute
        if pre_attack_combatant == post_name and not self.processing_enemy_turn:
            return (
                f"Attack failed! {pre_attack_combatant} cannot reach the target. "
                f"Use game_wait() to pass."
            )

        # Process enemy turns synchronously for MCP
        while self.processing_enemy_turn:
            self._process_enemy_turn()

        return self._mcp_get_state()

    def _mcp_wait(self) -> str:
        """Handle MCP wait command."""
        if not self.engine.in_combat:
            return "Not in combat! Use game_move() to explore."

        self._pass_turn()

        # Process enemy turns synchronously for MCP
        while self.processing_enemy_turn:
            self._process_enemy_turn()

        return self._mcp_get_state()

    # ========== End MCP Server Integration ==========

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
            image = arcade.get_image(0, 0, *self.get_size())
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

    def _update_lighting(self) -> None:
        """Recalculate lighting based on player/party positions."""
        if self.fog is None or self.lighting is None:
            return

        # Reset fog to dark for explored tiles
        self.fog.reset_to_dark()

        # Use party positions if spread, otherwise single player position
        if self.party_spread and self.party_positions:
            light_positions = self.party_positions
        else:
            light_positions = [(self.player_x, self.player_y)]

        self.lighting.update_party_lights(light_positions, "torch")
        lit_tiles = self.lighting.calculate_lighting()
        self.fog.apply_lighting(lit_tiles)

    def _spread_party_for_combat(self) -> None:
        """Spread party into formation around current position for combat.

        Formation (assuming enemies to the north):
            Back row:  [2] [3]  (wizard, rogue)
            Front row: [0] [1]  (fighters)
        """
        if not self.room_layout:
            return

        cx, cy = self.player_x, self.player_y

        # Use EntityManager to create party member entities in formation
        self.party_positions = self.entity_manager.spread_party_for_combat(
            engine=self.engine,
            center_x=cx,
            center_y=cy,
            layout=self.room_layout,
            character_textures=self.character_textures,
        )

        self.party_spread = True
        self._update_lighting()

    def _collapse_party_after_combat(self) -> None:
        """Collapse party back to single unit after combat ends."""
        # Set player position to center of formation
        if self.party_positions:
            avg_x = sum(p[0] for p in self.party_positions) // len(self.party_positions)
            avg_y = sum(p[1] for p in self.party_positions) // len(self.party_positions)
            self.player_x = avg_x
            self.player_y = avg_y

        # Remove party member entities
        self.entity_manager.collapse_party()

        self.party_spread = False
        self.party_positions = []
        self._update_lighting()

    def _load_room_layout(self) -> None:
        """Load the current room's layout for rendering."""
        game_state = self.engine.game_state
        if game_state is None:
            return

        room_id = game_state.current_room_id
        dungeon_name = game_state.dungeon_name
        campaign_id = game_state.campaign_id

        # Get room data for exits and entities
        room_data = self.layout_loader.get_room_data(dungeon_name, room_id, campaign_id)
        exits = {}
        if room_data:
            raw_exits = room_data.get("exits", {})
            for direction, dest in raw_exits.items():
                if isinstance(dest, dict):
                    exits[direction] = dest.get("destination", "")
                else:
                    exits[direction] = dest

        # Load layout with fallback generation
        self.room_layout = self.layout_loader.load_room_with_fallback(
            dungeon_name=dungeon_name,
            room_id=room_id,
            campaign_id=campaign_id,
            default_width=20,
            default_height=15,
            exits=exits,
        )

        self.room_tiles = self.room_layout.tiles
        self.player_x, self.player_y = self.room_layout.spawn_points.player

        # Initialize fog of war and lighting systems
        self.fog = FogOfWarSystem(
            width=self.room_layout.width,
            height=self.room_layout.height,
        )
        self.lighting = LightingSystem(
            map_width=self.room_layout.width,
            map_height=self.room_layout.height,
        )

        # Set walls as obstacles for lighting
        for y in range(self.room_layout.height):
            for x in range(self.room_layout.width):
                if self.room_layout.is_blocking(x, y):
                    self.lighting.add_obstacle(x, y)

        # Load entities from engine state using EntityManager
        self.entity_manager.load_from_room(
            engine=self.engine,
            layout=self.room_layout,
            room_data=room_data,
            monster_textures=self.monster_textures,
            item_textures=self.item_textures,
        )

        # Initial lighting update
        self._update_lighting()

    def _get_available_exits(self) -> dict[str, str]:
        """Get available exits from current room."""
        game_state = self.engine.game_state
        if game_state is None:
            return {}

        room = game_state.get_current_room()
        exits = {}
        raw_exits = room.get("exits", {})
        for direction, dest in raw_exits.items():
            if isinstance(dest, dict):
                if not dest.get("hidden", False):  # Skip hidden exits
                    exits[direction] = dest.get("destination", "")
            else:
                exits[direction] = dest
        return exits

    def _move_player(self, direction: str) -> None:
        """Attempt to move the player in a direction."""
        if self.engine.in_combat:
            self._add_combat_log("Can't move during combat!")
            return

        # Check if this direction leads to an exit
        exits = self._get_available_exits()
        if direction in exits:
            # Room transition!
            self._add_combat_log(f"Moving {direction}...")
            self._transition_room(direction)
            return

        # Otherwise, try to move within the room
        dx, dy = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}.get(
            direction, (0, 0)
        )
        new_x = self.player_x + dx
        new_y = self.player_y + dy

        # Check bounds and walls
        if self.room_layout and 0 <= new_x < self.room_layout.width and 0 <= new_y < self.room_layout.height:
            if not self.room_layout.is_blocking(new_x, new_y):
                self.player_x = new_x
                self.player_y = new_y
                self._update_lighting()

    def _transition_room(self, direction: str) -> None:
        """Transition to a new room via an exit."""
        game_state = self.engine.game_state
        if game_state is None:
            return

        # Use engine's move to transition rooms
        result = game_state.move(direction)

        if result:
            # Reload room layout
            self._load_room_layout()

            room = game_state.get_current_room()
            room_name = room.get("name", "Unknown")
            self._add_combat_log(f"Entered: {room_name}")

            # Check for combat
            if game_state.in_combat:
                enemies = [e.name for e in game_state.active_enemies]
                self.current_mode = GameMode.COMBAT
                self._spread_party_for_combat()
                self._add_combat_log(f"Combat! {len(enemies)} enemies: {', '.join(enemies)}")
                # Show whose turn it is
                current = self.engine.get_current_combatant()
                if current:
                    if current["is_player"]:
                        self._add_combat_log(f"{current['name']}'s turn - press 1-9 then A to attack!")
                    else:
                        self._add_combat_log(f"{current['name']} attacks first...")
                # If enemy goes first, start enemy turn processing
                if not self.engine.is_player_turn():
                    self.processing_enemy_turn = True
                    self.enemy_turn_timer = ENEMY_TURN_DELAY

    # ========== Drawing Methods ==========

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
                tile_rect = arcade.LBWH(
                    screen_x + 4, screen_y + 4, tile_size - 8, tile_size - 8
                )
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
                        math.sin(self.pulse_timer * 2 * math.pi / PULSE_CYCLE_DURATION)
                        + 1
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
                        center_x, center_y, tile_size // 2 + 2,
                        arcade.color.WHITE, 2
                    )

        # Draw party/player
        if self.party_spread and self.party_positions:
            # Combat formation - draw each party member from EntityManager
            for party_entity in self.entity_manager.get_party_members():
                char_screen_x = offset_x + party_entity.grid_x * tile_size
                char_screen_y = offset_y + (self.room_layout.height - 1 - party_entity.grid_y) * tile_size

                char_class = party_entity.character_class
                is_current_turn = party_entity.is_current_turn
                texture = party_entity.texture or self.player_texture

                # Draw current turn highlight (selection ring)
                if is_current_turn:
                    center_x = char_screen_x + tile_size // 2
                    center_y = char_screen_y + tile_size // 2
                    arcade.draw_circle_outline(
                        center_x, center_y, tile_size // 2 + 2,
                        UIColors.TEXT_HIGHLIGHT, 3
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
                        char_class[0].upper(), center_x, center_y - 5,
                        (255, 255, 255), 14, anchor_x="center"
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
                arcade.draw_text("@", center_x, center_y - 5, (255, 255, 255), 14, anchor_x="center")

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
                    exit_screen_y = offset_y + (self.room_layout.height - 1 - exit_y) * tile_size + tile_size // 2
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

        # Controls hint
        arcade.draw_text(
            "1-9: Select  |  A: Attack  |  WASD/Arrows: Move  |  Space: Wait",
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
        # Process any pending MCP commands (thread-safe)
        self._process_mcp_commands()

        # Update screenshot feedback timer
        if self.screenshot_message_timer > 0:
            self.screenshot_message_timer -= delta_time
            if self.screenshot_message_timer <= 0:
                self.screenshot_message = ""

        # Update pulse timer for targeting animation
        if self.current_mode == GameMode.COMBAT:
            self.pulse_timer += delta_time

        if not self.engine.in_combat:
            return

        # Handle auto-turn processing (enemy turns and unconscious player turns)
        if self.processing_enemy_turn:
            self.enemy_turn_timer -= delta_time
            if self.enemy_turn_timer <= 0:
                # Check what kind of turn to process
                if self.engine.is_current_combatant_unconscious():
                    self._process_unconscious_turn()
                elif not self.engine.is_player_turn():
                    self._process_enemy_turn()
                else:
                    # Conscious player's turn - stop auto-processing
                    self.processing_enemy_turn = False

    def _process_enemy_turn(self) -> None:
        """Process the current enemy's turn."""
        result = self.engine.process_enemy_turn()

        if result["success"]:
            if result.get("hit") is not None:
                if result["hit"]:
                    self._add_combat_log(
                        f"{result['enemy_name']} hits {result['target_name']} for {result['damage']} damage!"
                    )
                    if result.get("target_killed"):
                        self._add_combat_log(f"{result['target_name']} is down!")
                else:
                    self._add_combat_log(f"{result['enemy_name']} misses {result['target_name']}!")
            else:
                self._add_combat_log(f"{result['enemy_name']} takes no action.")

        # Sync entity state from engine after enemy action
        self.entity_manager.sync_from_engine(self.engine)
        self.entity_manager.update_party_turn_status(self.engine)

        # Advance turn
        turn_result = self.engine.advance_turn()

        if turn_result.get("combat_ended"):
            self._handle_combat_end()
        elif not turn_result.get("is_player_turn"):
            # Another enemy's turn - continue timer
            self.enemy_turn_timer = ENEMY_TURN_DELAY
        else:
            # Player's turn - check if unconscious
            if self.engine.is_current_combatant_unconscious():
                self._process_unconscious_turn()
            else:
                self.processing_enemy_turn = False

    def _process_unconscious_turn(self) -> None:
        """Process an unconscious character's death saving throw turn."""
        result = self.engine.process_unconscious_turn()

        if result is None:
            # Not an unconscious turn - shouldn't happen but handle gracefully
            self.processing_enemy_turn = False
            return

        # Log the death save result
        if result.already_stabilized:
            self._add_combat_log(
                f"{result.character_name} is stabilized (no death save needed)"
            )
        elif result.natural_20:
            self._add_combat_log(
                f"{result.character_name} rolls NAT 20! Regains consciousness with 1 HP!"
            )
        elif result.natural_1:
            self._add_combat_log(
                f"{result.character_name} rolls NAT 1! Two failures! ({result.failures}/3)"
            )
        elif result.success:
            self._add_combat_log(
                f"{result.character_name} death save: {result.roll} - Success! ({result.successes}/3)"
            )
        else:
            self._add_combat_log(
                f"{result.character_name} death save: {result.roll} - Failure! ({result.failures}/3)"
            )

        # Check outcomes
        if result.conscious:
            self._add_combat_log(f"{result.character_name} is back on their feet!")
        elif result.stabilized and not result.already_stabilized:
            self._add_combat_log(f"{result.character_name} is stabilized!")
        elif result.dead:
            self._add_combat_log(f"{result.character_name} has died...")

        # Sync entity state
        self.entity_manager.sync_from_engine(self.engine)

        # Check if combat ended (party wiped)
        if not self.engine.in_combat:
            self._handle_combat_end()
            return

        # Continue to next turn (still in auto-processing mode)
        self.enemy_turn_timer = ENEMY_TURN_DELAY

    def _handle_combat_end(self) -> None:
        """Handle end of combat."""
        self.processing_enemy_turn = False
        self.current_mode = GameMode.EXPLORATION
        self._collapse_party_after_combat()

        check = self.engine.end_combat_check()
        if check.get("victory"):
            self._add_combat_log("Victory! All enemies defeated!")
        elif check.get("party_wiped"):
            self._add_combat_log("Defeat! Your party has fallen...")

    # ========== Input Handling ==========

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
            self.close()
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
        distance_ft = distance_in_feet(
            combatant_x, combatant_y, target.grid_x, target.grid_y
        )

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

        # Log long range (disadvantage in future)
        in_long_range = distance_ft > normal_range
        if in_long_range:
            self._add_combat_log(
                f"{weapon_name} at {distance_ft} ft (long range - disadvantage)"
            )

        # Set selected enemy and execute attack
        self.selected_enemy = target.enemy_index
        self.selected_target = target
        self._execute_attack()

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
            key=lambda m: chebyshev_distance(
                combatant_x, combatant_y, m.grid_x, m.grid_y
            ),
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

    def _execute_attack(self) -> None:
        """Execute attack on selected enemy."""
        result = self.engine.execute_attack(target_index=self.selected_enemy)

        if result["success"]:
            if result["hit"]:
                crit = " CRITICAL!" if result.get("critical") else ""
                self._add_combat_log(
                    f"{result['attacker_name']} hits {result['target_name']} "
                    f"for {result['damage']} damage!{crit}"
                )
                if result.get("target_killed"):
                    self._add_combat_log(f"{result['target_name']} is defeated!")
            else:
                self._add_combat_log(
                    f"{result['attacker_name']} misses {result['target_name']}! "
                    f"(rolled {result['attack_roll']} vs AC {result['target_ac']})"
                )

            # Sync entity state from engine and remove dead enemies
            self.entity_manager.sync_from_engine(self.engine)
            self.entity_manager.remove_dead_entities()
            self.entity_manager.update_party_turn_status(self.engine)

            # Advance turn
            turn_result = self.engine.advance_turn()

            if turn_result.get("combat_ended"):
                self._handle_combat_end()
            elif not turn_result.get("is_player_turn"):
                # Start enemy turn timer
                self.processing_enemy_turn = True
                self.enemy_turn_timer = ENEMY_TURN_DELAY
        else:
            self._add_combat_log(f"Attack failed: {result.get('error', 'Unknown error')}")

    def _pass_turn(self) -> None:
        """Pass the current turn."""
        current = self.engine.get_current_combatant()
        if current:
            self._add_combat_log(f"{current['name']} waits...")

        # Update turn status after passing
        self.entity_manager.update_party_turn_status(self.engine)

        turn_result = self.engine.advance_turn()

        if turn_result.get("combat_ended"):
            self._handle_combat_end()
        elif not turn_result.get("is_player_turn"):
            self.processing_enemy_turn = True
            self.enemy_turn_timer = ENEMY_TURN_DELAY

    def _handle_combat_movement(self, direction: str) -> None:
        """Handle keyboard-triggered combat movement with feedback."""
        result = self._mcp_combat_move(direction)

        # Extract first line for combat log (MCP returns full state after newline)
        feedback = result.split("\n")[0]

        # Always show feedback in combat log
        self._add_combat_log(feedback)


def run_2d_client(
    size: str = "medium",
    fullscreen: bool = False,
    enable_mcp: bool = False,
    mcp_port: int = 8765,
) -> None:
    """Entry point for the 2D client.

    Args:
        size: Window size preset (small, medium, large).
        fullscreen: Whether to run in fullscreen mode.
        enable_mcp: Whether to start embedded MCP HTTP server.
        mcp_port: Port for MCP server (default 8765).
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
    print()

    GameWindow(
        width=width,
        height=height,
        fullscreen=fullscreen,
        enable_mcp=enable_mcp,
        mcp_port=mcp_port,
    )
    arcade.run()


if __name__ == "__main__":
    run_2d_client()
