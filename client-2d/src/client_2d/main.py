# ABOUTME: CLI entry point for the 2D graphical client.
# ABOUTME: Parses command-line arguments and launches the game window.

"""CLI entry point for the D&D 5E 2D client.

Usage:
    dnd-2d                    # Default medium window
    dnd-2d --size large       # Large window
    dnd-2d --fullscreen       # Fullscreen mode
    dnd-2d --mcp              # Enable embedded MCP server
    dnd-2d --mcp-port 9000    # Custom MCP port
"""

import argparse

from client_2d.game import run_2d_client


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="D&D 5E 2D Graphical Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  dnd-2d                     Launch with medium window
  dnd-2d --size large        Launch with large window
  dnd-2d --fullscreen        Launch in fullscreen mode
  dnd-2d --mcp               Enable MCP server for Claude playtesting
  dnd-2d --mcp --mcp-port 9000   Use custom MCP port
        """,
    )

    parser.add_argument(
        "--size",
        choices=["small", "medium", "large"],
        default="medium",
        help="Window size preset (default: medium)",
    )

    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="Run in fullscreen mode",
    )

    parser.add_argument(
        "--mcp",
        action="store_true",
        help="Enable embedded MCP HTTP server for Claude playtesting",
    )

    parser.add_argument(
        "--mcp-port",
        type=int,
        default=8765,
        help="Port for MCP server (default: 8765)",
    )

    args = parser.parse_args()

    run_2d_client(
        size=args.size,
        fullscreen=args.fullscreen,
        enable_mcp=args.mcp,
        mcp_port=args.mcp_port,
    )


if __name__ == "__main__":
    main()
