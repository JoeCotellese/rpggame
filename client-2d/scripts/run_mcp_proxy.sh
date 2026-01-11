#!/bin/bash
# ABOUTME: Launch the always-running MCP proxy server.
# ABOUTME: This replaces the game's direct MCP for Claude Code integration.

# Change to client-2d directory
cd "$(dirname "$0")/.." || exit 1

# Run proxy via uv (stays running, manages game lifecycle)
exec uv run python -m client_2d.mcp_proxy
