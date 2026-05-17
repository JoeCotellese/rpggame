# ABOUTME: Tests that the --dev MCP tools register on EmbeddedMCPServer iff dev_mode=True.
# ABOUTME: Verifies the five spawn/setup tools never leak into normal play sessions.

"""Tests for dev-mode gating on EmbeddedMCPServer.

The five --dev tools (spawn_monster, spawn_character, set_position,
clear_enemies, set_seed) must only register when EmbeddedMCPServer is
constructed with dev_mode=True. The default (dev_mode=False) keeps them
invisible to normal play sessions.
"""

from __future__ import annotations

from client_2d.embedded_mcp_server import EmbeddedMCPServer
from client_2d.mcp_bridge import MCPBridge

DEV_TOOL_NAMES = {
    "spawn_monster",
    "spawn_character",
    "set_position",
    "clear_enemies",
    "set_seed",
}

PLAY_TOOL_NAMES = {"game_state", "game_move", "game_attack", "game_wait"}


def _registered_tool_names(server: EmbeddedMCPServer) -> set[str]:
    """Return the set of tool names registered on the embedded FastMCP."""
    return {tool.name for tool in server._mcp._tool_manager.list_tools()}


def test_play_tools_always_present() -> None:
    """The four play-mode tools register regardless of dev_mode."""
    server = EmbeddedMCPServer(bridge=MCPBridge())
    assert PLAY_TOOL_NAMES.issubset(_registered_tool_names(server))


def test_spawn_tools_absent_when_dev_mode_false() -> None:
    """Default construction (dev_mode=False) keeps spawn tools off the wire."""
    server = EmbeddedMCPServer(bridge=MCPBridge())
    names = _registered_tool_names(server)
    assert names.isdisjoint(DEV_TOOL_NAMES)


def test_spawn_tools_absent_when_dev_mode_explicitly_false() -> None:
    """Explicit dev_mode=False matches the default."""
    server = EmbeddedMCPServer(bridge=MCPBridge(), dev_mode=False)
    names = _registered_tool_names(server)
    assert names.isdisjoint(DEV_TOOL_NAMES)


def test_spawn_tools_present_when_dev_mode_true() -> None:
    """dev_mode=True registers all five spawn/setup tools."""
    server = EmbeddedMCPServer(bridge=MCPBridge(), dev_mode=True)
    names = _registered_tool_names(server)
    assert DEV_TOOL_NAMES.issubset(names)


def test_play_tools_still_present_in_dev_mode() -> None:
    """Dev mode adds tools; it does not replace the play-mode set."""
    server = EmbeddedMCPServer(bridge=MCPBridge(), dev_mode=True)
    names = _registered_tool_names(server)
    assert PLAY_TOOL_NAMES.issubset(names)
