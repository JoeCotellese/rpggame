# ABOUTME: True end-to-end test for the Town of Arden node surface in The Unquiet Dead.
# ABOUTME: Drives the real CLI through a pty with pexpect — arrival, node nav, and the crypt seam.

import sys
from pathlib import Path

import pytest

pexpect = pytest.importorskip("pexpect")

DRIVER = Path(__file__).parent / "drivers" / "arden_settlement_driver.py"
TIMEOUT = 25


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


class TestArdenNodeSurfaceE2E:
    # pexpect.spawn uses os.forkpty(), which CPython 3.13 deprecates in
    # multi-threaded processes (pytest is one); harmless for a test child.
    @pytest.mark.filterwarnings("ignore:This process.*forkpty:DeprecationWarning")
    def test_arden_arrival_navigation_and_seam(self, game):
        # Arrival on the settlement node surface — the path that previously
        # crashed with "Could not find dungeon for room: arden.town_square".
        game.expect("Town of Arden")
        game.expect("Town Square")
        _await_prompt(game)

        # Prose navigation resolves to a named node with its authored NPC.
        game.sendline("go to the tankard")
        game.expect("The Crooked Tankard")
        game.expect("Marta")
        _await_prompt(game)

        # Walk to the Town Gate; it exposes the seam into the crypt. The
        # action prompt renders before its menu, so await it, then assert
        # the seam option is offered.
        game.sendline("go to the town gate")
        game.expect("Town Gate")
        _await_prompt(game)
        game.expect("Depart for Crypt")

        game.sendline("quit")
        game.expect("Thanks for playing")
        game.expect(pexpect.EOF)
