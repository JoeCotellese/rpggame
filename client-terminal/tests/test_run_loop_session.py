# ABOUTME: Tests that the CLI's main loop takes its turn structure from the Session.
# ABOUTME: Covers enemy-first initiative, player prompting, stalls and game over.

"""Verification for the migrated run loop (#697).

`run()` used to carry the turn structure itself: skipping dead combatants,
routing unconscious characters to death saves, noticing incapacitation, running
turn-start effects and advancing initiative from five separate branches. All of
that belongs to `Session` now, so what is left to test here is the handover —
who gets asked, when the engine is told to run forward, and that a malformed
initiative order surfaces instead of hanging the client.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from dnd_engine.core.entity_ids import pc_entity_id
from dnd_engine.session import ActionResult, GameEvent
from dnd_engine.utils.events import EventType
from terminal_client.ui.cli import CLI


class FakeSession:
    """A session whose answers the test dictates turn by turn."""

    def __init__(self, awaiting: list[str | None], advance_events: bool = True) -> None:
        self._awaiting = list(awaiting)
        self.advance_calls = 0
        self.perform_calls: list[object] = []
        self.pending_decision = None
        self.is_over = False
        self.in_combat = True
        self._advance_events = advance_events

    @property
    def awaiting_actor_id(self) -> str | None:
        return self._awaiting[0] if self._awaiting else None

    def advance(self) -> ActionResult:
        self.advance_calls += 1
        if self._awaiting:
            self._awaiting.pop(0)
        if not self._awaiting:
            # Nothing left to hand out: the fight is over, so the loop exits
            # the same way a real session would end it.
            self.in_combat = False
            self.is_over = True
        events = (
            (GameEvent(type=EventType.TURN_END, data={"actor": "Skeleton"}, sequence=0),)
            if self._advance_events
            else ()
        )
        return ActionResult(ok=True, events=events)

    def perform(self, intent) -> ActionResult:
        self.perform_calls.append(intent)
        return ActionResult(ok=True)

    def snapshot(self) -> dict:
        return {"party": [], "enemies": []}


class StallingSession(FakeSession):
    """A session stuck in combat with nobody able to act.

    Stands in for a malformed initiative order: every advance succeeds, nothing
    happens, and no player ever comes up.
    """

    def __init__(self) -> None:
        super().__init__(awaiting=[], advance_events=False)

    def advance(self) -> ActionResult:
        self.advance_calls += 1
        return ActionResult(ok=True)


@pytest.fixture
def cli():
    """A CLI whose display and engine calls are inert, so only the loop runs."""
    game_state = Mock()
    game_state.in_combat = True
    game_state.is_game_over.return_value = False
    game_state.party.characters = []
    game_state.active_enemies = []

    instance = CLI(
        game_state=game_state,
        campaign_manager=Mock(),
        campaign_name="test_campaign",
    )
    instance.display_banner = Mock()
    instance.display_location = Mock()
    instance.display_player_status = Mock()
    instance.display_combat_status = Mock()
    instance.display_turn_status = Mock()
    instance._prompt_condition_removal = Mock(return_value=False)
    instance.session_render = Mock()
    return instance


def _character(name: str = "Thorin"):
    character = Mock()
    character.name = name
    return character


class TestEnemyInitiative:
    """An enemy may hold the first slot; the client must let the engine run."""

    def test_the_engine_is_asked_to_run_forward_when_nobody_is_up(self, cli):
        character = _character()
        cli.game_state.party.characters = [character]
        cli.session = FakeSession(awaiting=[None, None])

        def stop_after_prompt() -> str:
            cli.running = False
            return "done"

        cli.get_player_command = Mock(side_effect=stop_after_prompt)
        cli.process_combat_command = Mock()

        cli.run()

        assert cli.session.advance_calls == 2, (
            "the client did not hand control to the engine while an enemy was up"
        )

    def test_a_stalled_initiative_order_reports_instead_of_hanging(self, cli):
        """A malformed order must surface as an error, not spin forever."""
        cli.game_state.party.characters = []
        cli.session = StallingSession()

        with patch("terminal_client.ui.cli.print_error") as mock_error:
            cli.run()

        assert mock_error.called, "a stalled combat produced no error"
        assert "advance" in str(mock_error.call_args)


class TestPlayerTurns:
    """When a player is up, the client prompts them."""

    def test_the_awaited_character_is_prompted(self, cli):
        character = _character("Thorin")
        cli.game_state.party.characters = [character]
        cli.session = FakeSession(awaiting=[pc_entity_id("Thorin")])

        def stop_after_prompt() -> str:
            cli.running = False
            return "done"

        cli.get_player_command = Mock(side_effect=stop_after_prompt)
        cli.process_combat_command = Mock()

        cli.run()

        cli.process_combat_command.assert_called_once_with("done")
        cli._prompt_condition_removal.assert_called_once_with(character)

    def test_the_turn_status_names_the_awaited_character(self, cli):
        character = _character("Thorin")
        cli.game_state.party.characters = [character]
        cli.session = FakeSession(awaiting=[pc_entity_id("Thorin")])

        def stop_after_prompt() -> str:
            cli.running = False
            return "done"

        cli.get_player_command = Mock(side_effect=stop_after_prompt)
        cli.process_combat_command = Mock()

        cli.run()

        cli.display_turn_status.assert_called_once_with(True, character)


class TestGameOver:
    """The loop ends when the party is wiped."""

    def test_the_loop_exits_and_announces_game_over(self, cli):
        cli.game_state.is_game_over.return_value = True
        cli.session = FakeSession(awaiting=[])
        cli.session.is_over = True

        with patch("terminal_client.ui.cli.print_title") as mock_title:
            cli.run()

        assert any("GAME OVER" in str(call) for call in mock_title.call_args_list)
