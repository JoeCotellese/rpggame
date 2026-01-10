# ABOUTME: MCP server exposing game client as tools for Claude-driven playtesting.
# ABOUTME: Provides game_new, game_state, game_move, game_attack, game_interact, game_wait.

"""MCP server for the 2D game client.

This server exposes the game client as MCP tools, allowing Claude to
playtest the game by calling tools directly instead of using stdin/stdout.

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
    game_new: Start a new game session
    game_state: Get current game state (ASCII map + JSON)
    game_move: Move player in a direction
    game_attack: Attack an adjacent enemy
    game_interact: Interact with an adjacent object
    game_wait: Wait one turn
"""

from mcp.server.fastmcp import FastMCP

from client_2d.core.constants import Direction
from client_2d.testing.command_processor import CommandProcessor
from client_2d.testing.state_renderer import StateRenderer
from client_2d.testing.test_harness import GameState, create_demo_game_state

# Initialize MCP server
mcp = FastMCP("dnd-game")

# Global game state (persists across tool calls)
_game_state: GameState | None = None
_renderer: StateRenderer | None = None
_processor: CommandProcessor | None = None


def _ensure_game() -> tuple[GameState, StateRenderer, CommandProcessor]:
    """Ensure game is initialized, create if needed."""
    global _game_state, _renderer, _processor

    if _game_state is None:
        _game_state = create_demo_game_state()
        width = len(_game_state.room[0])
        height = len(_game_state.room)
        _renderer = StateRenderer(width=width, height=height)
        _processor = CommandProcessor()

    return _game_state, _renderer, _processor


def _get_current_state() -> dict:
    """Get the current rendered game state."""
    state, renderer, _ = _ensure_game()
    return renderer.render_state(
        room=state.room,
        player_x=state.player_x,
        player_y=state.player_y,
        entities=state.entities,
        fog=state.fog,
        turn=state.turn,
        player_hp=state.player_hp,
        player_max_hp=state.player_max_hp,
        light_source=state.light_source,
    )


def _format_state_response(state_dict: dict) -> str:
    """Format state dict as readable response."""
    lines = [
        f"Turn: {state_dict['turn']}",
        f"Player: {state_dict['player']['position']} "
        f"HP: {state_dict['player']['hp']}/{state_dict['player']['max_hp']} "
        f"Light: {state_dict['player']['light_source']}",
        f"Explored: {state_dict['explored_tiles']}/{state_dict['total_tiles']}",
        "",
        "Map:",
        state_dict["map"],
        "",
        "Legend:",
    ]

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

    lines.append("")
    lines.append("Available Actions:")
    for action in state_dict["available_actions"]:
        lines.append(f"  - {action}")

    return "\n".join(lines)


@mcp.tool()
def game_new() -> str:
    """Start a new game session.

    Resets the game to initial state with player in the center of the dungeon.
    Returns the initial game state.
    """
    global _game_state, _renderer, _processor

    _game_state = create_demo_game_state()
    width = len(_game_state.room[0])
    height = len(_game_state.room)
    _renderer = StateRenderer(width=width, height=height)
    _processor = CommandProcessor()

    state = _get_current_state()
    return "New game started!\n\n" + _format_state_response(state)


@mcp.tool()
def game_state() -> str:
    """Get the current game state.

    Returns:
        ASCII map showing visible area with fog of war,
        player position and stats, visible entities,
        and available actions.
    """
    state = _get_current_state()
    return _format_state_response(state)


@mcp.tool()
def game_move(direction: str) -> str:
    """Move the player in a direction.

    Args:
        direction: One of 'north', 'south', 'east', 'west'

    Returns:
        Updated game state after movement, or error if blocked.
    """
    state, renderer, processor = _ensure_game()

    direction_map = {
        "north": Direction.NORTH,
        "south": Direction.SOUTH,
        "east": Direction.EAST,
        "west": Direction.WEST,
    }

    dir_lower = direction.lower()
    if dir_lower not in direction_map:
        return f"Invalid direction: {direction}. Use north, south, east, or west."

    # Check if move is valid
    current_state = _get_current_state()
    action_name = f"move_{dir_lower}"

    if action_name not in current_state["available_actions"]:
        return f"Cannot move {dir_lower}: blocked by wall or obstacle."

    # Execute move
    dir_obj = direction_map[dir_lower]
    dx, dy = dir_obj.delta
    state.player_x += dx
    state.player_y += dy
    state.turn += 1

    # Update lighting
    state.fog.reset_to_dark()
    state.lighting.update_party_lights(
        [(state.player_x, state.player_y)], state.light_source
    )
    lit_tiles = state.lighting.calculate_lighting()
    state.fog.apply_lighting(lit_tiles)

    new_state = _get_current_state()
    return f"Moved {dir_lower}.\n\n" + _format_state_response(new_state)


@mcp.tool()
def game_attack(target: str) -> str:
    """Attack an adjacent enemy.

    Args:
        target: The entity ID to attack (e.g., 'goblin_1', 'skeleton_1')

    Returns:
        Result of the attack and updated game state.
    """
    state, _, _ = _ensure_game()

    # Check if attack is valid
    current_state = _get_current_state()
    action_name = f"attack_{target}"

    if action_name not in current_state["available_actions"]:
        return f"Cannot attack {target}: not adjacent or not visible."

    # Find and remove the target (simple combat for now)
    for entity in state.entities:
        if entity.entity_id == target and entity.entity_type == "monster":
            state.entities.remove(entity)
            state.turn += 1
            new_state = _get_current_state()
            return f"Attacked {target}! Enemy defeated.\n\n" + _format_state_response(
                new_state
            )

    return f"Could not find target: {target}"


@mcp.tool()
def game_interact(target: str) -> str:
    """Interact with an adjacent object (item, chest, door, etc.).

    Args:
        target: The entity ID to interact with (e.g., 'chest_1', 'potion_1')

    Returns:
        Result of the interaction and updated game state.
    """
    state, _, _ = _ensure_game()

    # Check if interact is valid
    current_state = _get_current_state()
    action_name = f"interact_{target}"

    if action_name not in current_state["available_actions"]:
        return f"Cannot interact with {target}: not adjacent or not visible."

    # Find and handle the target
    for entity in state.entities:
        if entity.entity_id == target:
            if entity.entity_type == "item":
                state.entities.remove(entity)
                state.turn += 1
                new_state = _get_current_state()
                return f"Picked up {target}!\n\n" + _format_state_response(new_state)
            elif entity.entity_type == "deco":
                state.entities.remove(entity)
                state.turn += 1
                new_state = _get_current_state()
                return f"Opened {target}!\n\n" + _format_state_response(new_state)
            else:
                state.turn += 1
                new_state = _get_current_state()
                return f"Interacted with {target}.\n\n" + _format_state_response(
                    new_state
                )

    return f"Could not find target: {target}"


@mcp.tool()
def game_wait() -> str:
    """Wait one turn without taking action.

    Returns:
        Updated game state after waiting.
    """
    state, _, _ = _ensure_game()
    state.turn += 1
    new_state = _get_current_state()
    return "Waited one turn.\n\n" + _format_state_response(new_state)


if __name__ == "__main__":
    mcp.run()
