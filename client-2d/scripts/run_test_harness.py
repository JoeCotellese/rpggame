#!/usr/bin/env python3
# ABOUTME: Entry point script for running the headless test harness.
# ABOUTME: Run with: uv run python scripts/run_test_harness.py

"""Run the headless test harness for Claude-driven playtesting.

Usage:
    cd client-2d
    uv run python scripts/run_test_harness.py

Protocol:
    The harness reads JSON commands from stdin and writes JSON state to stdout.

    Commands:
        {"action": "get_state"}     - Get current game state
        {"action": "move_north"}    - Move player north
        {"action": "move_south"}    - Move player south
        {"action": "move_east"}     - Move player east
        {"action": "move_west"}     - Move player west
        {"action": "attack_<id>"}   - Attack adjacent monster
        {"action": "interact_<id>"} - Interact with adjacent entity
        {"action": "wait"}          - Wait one turn
        {"action": "quit"}          - Exit the harness

    State Output:
        {
            "turn": 0,
            "map": "ASCII map string",
            "legend": {"@": "player", "A": "monster:goblin", ...},
            "player": {"position": [x, y], "hp": 30, "max_hp": 30, ...},
            "visible_entities": {...},
            "available_actions": ["move_north", "attack_goblin", ...]
        }

Example session:
    $ echo '{"action": "get_state"}' | uv run python scripts/run_test_harness.py
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from client_2d.testing import TestHarness, create_demo_game_state


def main() -> None:
    """Run the test harness."""
    # Create demo game state
    state = create_demo_game_state()

    # Create and run harness
    harness = TestHarness(state=state)
    harness.run()


if __name__ == "__main__":
    main()
