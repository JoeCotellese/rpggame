# ABOUTME: E2E driver that boots the real CLI on the lab settlement (no LLM, no menus).
# ABOUTME: Run under pexpect by test_node_surface_e2e.py; only game setup is scripted.

import sys
from pathlib import Path

from terminal_client.ui.cli import CLI

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests.support import make_lab_game_state  # noqa: E402


class NoopCampaignManager:
    """Save-less campaign manager so the e2e run never touches real save slots."""

    def save_game(self, *args: object, **kwargs: object) -> None:
        """Discard the save request."""
        return None


def main() -> None:
    """Boot the CLI on the lab settlement with a standard one-fighter party."""
    game_state = make_lab_game_state()
    cli = CLI(
        game_state,
        NoopCampaignManager(),
        "lab",
        auto_save_enabled=False,
        llm_enhancer=None,
    )
    cli.run()


if __name__ == "__main__":
    main()
