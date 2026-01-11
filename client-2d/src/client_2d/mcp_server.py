# ABOUTME: MCP server exposing game client as tools for Claude-driven playtesting.
# ABOUTME: Uses real dnd-engine via EngineAdapter for authentic game mechanics.

"""MCP server for the 2D game client.

This server exposes the game client as MCP tools, allowing Claude to
playtest the game by calling tools directly. Uses the real dnd-engine
for authentic combat, party management, and game mechanics.

Architecture:
    Claude (MCP) --> EngineAdapter --> dnd-engine (real game)
                 |
                 --> LayoutLoader --> room tiles (for ASCII map)

Issue: #326

Usage:
    Add to Claude Code MCP settings:
    {
        "mcpServers": {
            "dnd-game": {
                "command": "uv",
                "args": ["run", "--directory", "/path/to/client-2d", "python", "-m", "client_2d.mcp_server"]
            }
        }
    }

Tools:
    game_new: Start a new game session with real engine
    game_state: Get current game state (ASCII map + JSON)
    game_move: Move party in a direction (room transitions)
    game_attack: Attack an enemy (real combat rolls)
    game_wait: Wait/pass turn in combat
"""

from mcp.server.fastmcp import FastMCP

from client_2d.integration.engine_adapter import EngineAdapter
from client_2d.integration.layout_loader import LayoutLoader, RoomLayout
from client_2d.systems.fog_of_war import FogOfWarSystem
from client_2d.systems.lighting import LightingSystem
from client_2d.testing.state_renderer import Entity, StateRenderer

# Initialize MCP server
mcp = FastMCP("dnd-game")

# Global state (persists across tool calls)
_engine: EngineAdapter | None = None
_layout_loader: LayoutLoader | None = None
_room_layout: RoomLayout | None = None
_fog: FogOfWarSystem | None = None
_lighting: LightingSystem | None = None
_renderer: StateRenderer | None = None
_player_x: int = 0
_player_y: int = 0


def _get_layout_loader() -> LayoutLoader:
    """Get or create the layout loader."""
    global _layout_loader
    if _layout_loader is None:
        _layout_loader = LayoutLoader()
    return _layout_loader


def _load_room_layout() -> None:
    """Load the current room's tile layout for ASCII rendering."""
    global _room_layout, _fog, _lighting, _renderer, _player_x, _player_y

    if _engine is None or _engine.game_state is None:
        return

    loader = _get_layout_loader()
    game_state = _engine.game_state

    room_id = game_state.current_room_id
    dungeon_name = game_state.dungeon_name
    campaign_id = game_state.campaign_id

    # Get room data for exits
    room_data = loader.get_room_data(dungeon_name, room_id, campaign_id)
    exits = {}
    if room_data:
        raw_exits = room_data.get("exits", {})
        for direction, dest in raw_exits.items():
            if isinstance(dest, dict):
                exits[direction] = dest.get("destination", "")
            else:
                exits[direction] = dest

    # Load layout with fallback generation
    _room_layout = loader.load_room_with_fallback(
        dungeon_name=dungeon_name,
        room_id=room_id,
        campaign_id=campaign_id,
        default_width=25,
        default_height=18,
        exits=exits,
    )

    # Initialize fog of war and lighting
    _fog = FogOfWarSystem(
        width=_room_layout.width,
        height=_room_layout.height,
    )
    _lighting = LightingSystem(
        map_width=_room_layout.width,
        map_height=_room_layout.height,
    )

    # Set walls as obstacles for lighting
    for y in range(_room_layout.height):
        for x in range(_room_layout.width):
            if _room_layout.is_blocking(x, y):
                _lighting.add_obstacle(x, y)

    # Set player position from spawn point
    _player_x, _player_y = _room_layout.spawn_points.player

    # Initialize renderer
    _renderer = StateRenderer(
        width=_room_layout.width,
        height=_room_layout.height,
    )

    # Update lighting
    _update_lighting()


def _update_lighting() -> None:
    """Recalculate fog of war and lighting from player position."""
    if _fog is None or _lighting is None:
        return

    _fog.reset_to_dark()
    _lighting.update_party_lights([(_player_x, _player_y)], "torch")
    lit_tiles = _lighting.calculate_lighting()
    _fog.apply_lighting(lit_tiles)


def _build_entities() -> list[Entity]:
    """Build entity list from engine state for ASCII rendering."""
    entities: list[Entity] = []

    if _engine is None or _room_layout is None:
        return entities

    game_state = _engine.game_state
    if game_state is None:
        return entities

    # Add enemies from engine
    enemy_positions = _room_layout.entity_positions.enemies
    for i, enemy in enumerate(game_state.active_enemies):
        if enemy.is_alive:
            if i < len(enemy_positions):
                ex, ey = enemy_positions[i]
            else:
                ex = _room_layout.width // 2 + i
                ey = _room_layout.height // 2
            entities.append(Entity(
                x=ex,
                y=ey,
                entity_type="monster",
                entity_id=f"{enemy.name.lower().replace(' ', '_')}_{i + 1}",
            ))

    return entities


def _get_current_state() -> dict:
    """Get the current rendered game state."""
    if _renderer is None or _room_layout is None or _fog is None:
        return {"error": "Game not initialized"}

    entities = _build_entities()

    # Get turn info from engine
    turn = 0
    if _engine and _engine.game_state:
        tracker = _engine.game_state.initiative_tracker
        if tracker:
            turn = tracker.round_number

    # Get party HP (sum of all characters)
    player_hp = 30
    player_max_hp = 30
    if _engine:
        party_data = _engine.get_party_data()
        if party_data:
            player_hp = sum(c["hp"] for c in party_data)
            player_max_hp = sum(c["max_hp"] for c in party_data)

    return _renderer.render_state(
        room=_room_layout.tiles,
        player_x=_player_x,
        player_y=_player_y,
        entities=entities,
        fog=_fog,
        turn=turn,
        player_hp=player_hp,
        player_max_hp=player_max_hp,
        light_source="torch",
    )


def _format_state_response(state_dict: dict) -> str:
    """Format state dict as readable response."""
    if "error" in state_dict:
        return f"Error: {state_dict['error']}"

    lines = [
        f"Turn: {state_dict['turn']}",
        f"Party HP: {state_dict['player']['hp']}/{state_dict['player']['max_hp']} "
        f"Light: {state_dict['player']['light_source']}",
        f"Explored: {state_dict['explored_tiles']}/{state_dict['total_tiles']}",
    ]

    # Add combat info if in combat
    if _engine and _engine.in_combat:
        combat_data = _engine.get_combat_data()
        if combat_data:
            lines.append(f"Combat Round: {combat_data['round']}")
            current = _engine.get_current_combatant()
            if current:
                lines.append(f"Current Turn: {current['name']}")

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
                f"at {info['position']} ({info['distance']} tiles {info['direction']})"
            )

    # Add party status
    if _engine:
        party_data = _engine.get_party_data()
        if party_data:
            lines.append("")
            lines.append("Party:")
            for member in party_data:
                conditions = ", ".join(member.get("conditions", [])) or "healthy"
                lines.append(
                    f"  {member['name']} ({member['class']}): "
                    f"{member['hp']}/{member['max_hp']} HP - {conditions}"
                )

    # Add enemies in combat
    if _engine and _engine.in_combat:
        enemies = _engine.get_enemies()
        if enemies:
            lines.append("")
            lines.append("Enemies:")
            for e in enemies:
                lines.append(f"  [{e['index']}] {e['name']}: {e['hp']}/{e['max_hp']} HP")

    lines.append("")
    lines.append("Available Actions:")
    for action in state_dict["available_actions"]:
        lines.append(f"  - {action}")

    # Add combat actions if in combat
    if _engine and _engine.in_combat and _engine.is_player_turn():
        lines.append("")
        lines.append("Combat Actions:")
        lines.append("  - game_attack(target_index) - e.g., game_attack(0)")
        lines.append("  - game_wait() - pass turn")

    return "\n".join(lines)


def _get_available_exits() -> dict[str, str]:
    """Get available exits from current room."""
    if _engine is None or _engine.game_state is None:
        return {}

    room = _engine.game_state.get_current_room()
    exits = {}
    raw_exits = room.get("exits", {})
    for direction, dest in raw_exits.items():
        if isinstance(dest, dict):
            if not dest.get("hidden", False):
                exits[direction] = dest.get("destination", "")
        else:
            exits[direction] = dest
    return exits


@mcp.tool()
def game_new(
    dungeon_name: str = "cellar",
    campaign_id: str = "poisoned_laboratory",
    start_room: str = "cellar.stairs",
) -> str:
    """Start a new game session with real dnd-engine.

    Args:
        dungeon_name: Dungeon file name without .json (default: cellar)
        campaign_id: Campaign containing the dungeon (default: poisoned_laboratory)
        start_room: Room ID to start in (default: cellar.stairs)

    Returns:
        Initial game state with ASCII map, party info, and available actions.

    Examples:
        game_new()  # Start in cellar stairs (safe room)
        game_new(start_room="cellar.storage")  # Start in storage (has rats!)
    """
    global _engine

    try:
        # Initialize real engine
        _engine = EngineAdapter()

        # Load party from vault
        party_info = _engine.load_party_from_vault()
        party_names = [p["name"] for p in party_info]

        # Initialize game
        game_info = _engine.initialize_game(
            dungeon_name=dungeon_name,
            campaign_id=campaign_id,
            start_room=start_room,
        )

        # Start game (checks for enemies)
        start_info = _engine.start_game()

        # Load room layout for ASCII rendering
        _load_room_layout()

        # Build response
        lines = [
            "New game started! (Real Engine)",
            f"Dungeon: {game_info['dungeon']} / {game_info['campaign']}",
            f"Room: {game_info['room_name']} ({game_info['room_id']})",
            f"Party: {', '.join(party_names)}",
        ]

        if start_info["in_combat"]:
            lines.append(f"COMBAT! Enemies: {', '.join(start_info['enemies'])}")
        else:
            lines.append("No enemies in starting room. Explore with game_move()!")

        lines.append("")

        state = _get_current_state()
        return "\n".join(lines) + _format_state_response(state)

    except Exception as e:
        return f"Failed to start game: {e}"


@mcp.tool()
def game_state() -> str:
    """Get the current game state.

    Returns:
        ASCII map showing visible area with fog of war,
        party status, combat info if in combat,
        and available actions.
    """
    if _engine is None:
        return "No game in progress. Use game_new() to start."

    state = _get_current_state()
    return _format_state_response(state)


@mcp.tool()
def game_move(direction: str) -> str:
    """Move the party in a direction. May trigger room transitions or combat.

    Args:
        direction: One of 'north', 'south', 'east', 'west'

    Returns:
        Updated game state after movement, or error if blocked.
    """
    global _player_x, _player_y

    if _engine is None or _engine.game_state is None:
        return "No game in progress. Use game_new() to start."

    if _engine.in_combat:
        return "Cannot move during combat! Use game_attack() or game_wait()."

    dir_lower = direction.lower()
    if dir_lower not in ("north", "south", "east", "west"):
        return f"Invalid direction: {direction}. Use north, south, east, or west."

    # Check for room exit
    exits = _get_available_exits()
    if dir_lower in exits:
        # Room transition via engine
        try:
            result = _engine.game_state.move(dir_lower)
            if result:
                _load_room_layout()

                room = _engine.game_state.get_current_room()
                room_name = room.get("name", "Unknown")

                lines = [f"Moved {dir_lower}. Entered: {room_name}"]

                # Check for combat
                if _engine.in_combat:
                    enemies = [e.name for e in _engine.game_state.active_enemies]
                    lines.append(f"COMBAT! Enemies: {', '.join(enemies)}")

                lines.append("")
                state = _get_current_state()
                return "\n".join(lines) + _format_state_response(state)
            else:
                return f"Cannot move {dir_lower}: path blocked."
        except Exception as e:
            return f"Move failed: {e}"

    # Intra-room movement
    dx, dy = {
        "north": (0, -1),
        "south": (0, 1),
        "east": (1, 0),
        "west": (-1, 0),
    }[dir_lower]

    new_x = _player_x + dx
    new_y = _player_y + dy

    # Check bounds and walls
    if _room_layout and 0 <= new_x < _room_layout.width and 0 <= new_y < _room_layout.height:
        if not _room_layout.is_blocking(new_x, new_y):
            _player_x = new_x
            _player_y = new_y
            _update_lighting()

            state = _get_current_state()
            return f"Moved {dir_lower}.\n\n" + _format_state_response(state)

    return f"Cannot move {dir_lower}: blocked by wall."


@mcp.tool()
def game_attack(target_index: int) -> str:
    """Attack an enemy in combat using real D&D 5E combat rules.

    Args:
        target_index: Index of the enemy to attack (from enemies list)

    Returns:
        Combat result with attack roll, damage, and updated state.
    """
    if _engine is None:
        return "No game in progress. Use game_new() to start."

    if not _engine.in_combat:
        return "Not in combat. Move to find enemies!"

    if not _engine.is_player_turn():
        return "Not your turn! Wait for enemies to act."

    try:
        # Execute attack through engine
        result = _engine.execute_attack(target_index=target_index)

        if not result["success"]:
            return f"Attack failed: {result.get('error', 'Unknown error')}"

        # Build response
        lines = []
        if result["hit"]:
            crit = " CRITICAL!" if result.get("critical") else ""
            lines.append(
                f"{result['attacker_name']} hits {result['target_name']} "
                f"for {result['damage']} damage!{crit}"
            )
            if result.get("target_killed"):
                lines.append(f"{result['target_name']} is defeated!")
        else:
            lines.append(
                f"{result['attacker_name']} misses {result['target_name']}! "
                f"(rolled {result['attack_roll']} vs AC {result['target_ac']})"
            )

        # Advance turn
        turn_result = _engine.advance_turn()

        if turn_result.get("combat_ended"):
            check = _engine.end_combat_check()
            if check.get("victory"):
                lines.append("Victory! All enemies defeated!")
            elif check.get("party_wiped"):
                lines.append("Defeat! Your party has fallen...")
        else:
            # Process enemy turns automatically
            while not _engine.is_player_turn() and _engine.in_combat:
                enemy_result = _engine.process_enemy_turn()
                if enemy_result["success"]:
                    if enemy_result.get("hit") is not None:
                        if enemy_result["hit"]:
                            lines.append(
                                f"{enemy_result['enemy_name']} hits "
                                f"{enemy_result['target_name']} "
                                f"for {enemy_result['damage']} damage!"
                            )
                        else:
                            lines.append(
                                f"{enemy_result['enemy_name']} misses "
                                f"{enemy_result['target_name']}!"
                            )

                adv = _engine.advance_turn()
                if adv.get("combat_ended"):
                    check = _engine.end_combat_check()
                    if check.get("victory"):
                        lines.append("Victory! All enemies defeated!")
                    break

        lines.append("")
        state = _get_current_state()
        return "\n".join(lines) + _format_state_response(state)

    except Exception as e:
        return f"Attack error: {e}"


@mcp.tool()
def game_wait() -> str:
    """Wait/pass your turn in combat, or let enemies act if it's their turn.

    If it's a player's turn, passes that turn.
    Then processes all enemy turns until it's a player's turn again.

    Returns:
        Updated game state after waiting.
    """
    if _engine is None:
        return "No game in progress. Use game_new() to start."

    if not _engine.in_combat:
        return "Not in combat. Use game_move() to explore."

    try:
        lines = []

        # If it's player's turn, pass it first
        if _engine.is_player_turn():
            current = _engine.get_current_combatant()
            if current:
                lines.append(f"{current['name']} waits...")
            turn_result = _engine.advance_turn()
            if turn_result.get("combat_ended"):
                check = _engine.end_combat_check()
                if check.get("victory"):
                    lines.append("Victory! All enemies defeated!")
                elif check.get("party_wiped"):
                    lines.append("Defeat! Your party has fallen...")
                lines.append("")
                state = _get_current_state()
                return "\n".join(lines) + _format_state_response(state)

        # Process enemy turns until it's a player's turn again
        max_enemy_turns = 20  # Safety limit
        enemy_turns = 0

        while not _engine.is_player_turn() and _engine.in_combat and enemy_turns < max_enemy_turns:
            enemy_result = _engine.process_enemy_turn()
            enemy_turns += 1

            if enemy_result["success"]:
                if enemy_result.get("hit") is not None:
                    if enemy_result["hit"]:
                        lines.append(
                            f"{enemy_result['enemy_name']} hits "
                            f"{enemy_result['target_name']} "
                            f"for {enemy_result['damage']} damage!"
                        )
                    else:
                        lines.append(
                            f"{enemy_result['enemy_name']} misses "
                            f"{enemy_result['target_name']}!"
                        )

            adv = _engine.advance_turn()
            if adv.get("combat_ended"):
                check = _engine.end_combat_check()
                if check.get("victory"):
                    lines.append("Victory! All enemies defeated!")
                elif check.get("party_wiped"):
                    lines.append("Defeat! Your party has fallen...")
                break

        lines.append("")
        state = _get_current_state()
        return "\n".join(lines) + _format_state_response(state)

    except Exception as e:
        return f"Wait error: {e}"


if __name__ == "__main__":
    mcp.run()
