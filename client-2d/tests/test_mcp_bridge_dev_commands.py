# ABOUTME: Tests for the --dev MCP CommandType variants (spawn/setup tooling).
# ABOUTME: Verifies the five dev-only command kinds exist and are distinct enum members.

"""Tests for the dev-mode CommandType variants in mcp_bridge.

These five variants exist to carry spawn/setup commands from the MCP server
thread into the GameWindow main thread when --dev (or DND_DEBUG=1) is set.
"""

from __future__ import annotations

from client_2d.mcp_bridge import CommandType

DEV_COMMAND_NAMES = (
    "SPAWN_MONSTER",
    "SPAWN_CHARACTER",
    "SET_POSITION",
    "CLEAR_ENEMIES",
    "SET_SEED",
    "LOAD_SCENARIO",
    "RESET_GAME",
)


def test_dev_command_types_exist() -> None:
    """All five dev-mode CommandType variants are defined on the enum."""
    for name in DEV_COMMAND_NAMES:
        assert hasattr(CommandType, name), f"CommandType.{name} missing"


def test_dev_command_types_unique() -> None:
    """Each dev-mode variant has a unique value (no auto() collisions)."""
    members = [getattr(CommandType, name) for name in DEV_COMMAND_NAMES]
    assert len(members) == len(set(members))


def test_dev_command_types_distinct_from_existing() -> None:
    """Dev-mode variants don't collide with the four play-mode variants."""
    existing = {
        CommandType.GET_STATE,
        CommandType.MOVE,
        CommandType.ATTACK,
        CommandType.WAIT,
    }
    dev = {getattr(CommandType, name) for name in DEV_COMMAND_NAMES}
    assert existing.isdisjoint(dev)
