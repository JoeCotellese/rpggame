#!/bin/bash
# ABOUTME: Wrapper script to run the game MCP server.
# ABOUTME: Used by Claude Code MCP configuration.

cd "$(dirname "$0")/.." && uv run python -m client_2d.mcp_server
