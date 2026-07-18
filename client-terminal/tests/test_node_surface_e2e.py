# ABOUTME: True end-to-end tests for the settlement node surface (issue #684 slice 5).
# ABOUTME: Drives the real CLI through a pty with pexpect — numbers AND typed prose.

import sys
from pathlib import Path

import pytest

pexpect = pytest.importorskip("pexpect")

DRIVER = Path(__file__).parent / "drivers" / "lab_settlement_driver.py"
TIMEOUT = 20


@pytest.fixture
def game():
    child = pexpect.spawn(
        sys.executable,
        [str(DRIVER)],
        cwd=str(Path(__file__).parent.parent),
        env={
            "PATH": "/usr/bin:/bin",
            "TERM": "dumb",
            "NO_COLOR": "1",
            "HOME": str(Path.home()),
        },
        encoding="utf-8",
        timeout=TIMEOUT,
    )
    yield child
    child.close(force=True)


def _await_prompt(child):
    """Wait for the node action menu to be on screen."""
    child.expect("What do you do?")


class TestLabSettlementE2E:
    # pexpect.spawn uses os.forkpty(), which CPython 3.13 deprecates in
    # multi-threaded processes (pytest is one); harmless for a test child.
    @pytest.mark.filterwarnings(
        "ignore:This process.*forkpty:DeprecationWarning"
    )
    def test_full_playthrough_numbers_and_prose(self, game):
        # Arrival: start node renders with its three zones
        game.expect("Lab Settlement")
        game.expect("Lab Square")
        _await_prompt(game)

        # --- Numbered input: lab_square authors gather_rumors then read_job_board
        game.sendline("2")
        game.expect("The job board is bare")

        game.sendline("1")
        game.expect("no one with news")

        # --- Prose input: destination by name
        game.sendline("go to the tankard")
        game.expect("The Testing Tankard")
        _await_prompt(game)

        # --- Prose with typo still resolves
        game.sendline("visit the old gaet")
        game.expect("The Old Gate")
        _await_prompt(game)

        # --- Examine through the authored skill gate (either branch is a beat)
        game.sendline("examine the symbol")
        game.expect("Choose a character")
        game.sendline("")  # accept the top character
        game.expect(["ward against the restless dead", "meaning escapes you"])

        # --- Depart across the seam; retry the Athletics gate until it opens
        for _ in range(12):
            game.sendline("depart")
            game.expect("Choose a character")
            game.sendline("")
            index = game.expect(["stale air", "will not budge"])
            if index == 0:
                break
        else:
            pytest.fail("Athletics DC 10 never succeeded in 12 attempts")

        # Grid side of the seam
        game.expect("Lab Dungeon Entry")

        # --- Reverse seam: walk the grid exit back up into the settlement
        game.sendline("go up")
        game.expect("The Old Gate")
        _await_prompt(game)

        # --- Node help is the settlement help
        game.sendline("help")
        game.expect("Settlement Commands")

        game.sendline("quit")
        game.expect("Thanks for playing")
        game.expect(pexpect.EOF)
