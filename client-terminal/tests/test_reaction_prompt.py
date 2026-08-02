# ABOUTME: Tests that the CLI asks the player about opportunity attacks.
# ABOUTME: Covers choosing, declining, cancelling, and not looping on a bad answer.

"""Verification for the reaction prompt (#697).

Before this, the engine resolved a party member's opportunity attack
automatically — the player never chose. The session now pauses and asks, and
this is where the terminal client turns that question into a menu.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from dnd_engine.session import ActionResult, DecisionKind, DecisionOption, PendingDecision
from dnd_engine.session.reactions import ATTACK_OPTION_ID, DECLINE_OPTION_ID
from terminal_client.ui.cli import CLI


def _decision(default: str | None = ATTACK_OPTION_ID) -> PendingDecision:
    return PendingDecision(
        decision_id="oa-1",
        kind=DecisionKind.REACTION,
        actor_id="pc_thorin",
        prompt="Skeleton 2 is leaving Thorin's reach - take an opportunity attack?",
        options=(
            DecisionOption(ATTACK_OPTION_ID, "Take the opportunity attack", "Strike as they withdraw"),
            DecisionOption(DECLINE_OPTION_ID, "Decline", "Keep your reaction"),
        ),
        default_option_id=default,
    )


@pytest.fixture
def cli():
    game_state = Mock()
    game_state.party.characters = []
    instance = CLI(
        game_state=game_state,
        campaign_manager=Mock(),
        campaign_name="test_campaign",
    )
    instance.session = Mock()
    instance.session_render = Mock()
    instance.session.resolve.return_value = ActionResult(ok=True)
    return instance


class TestPromptingForAReaction:
    """The player, not the engine, decides whether to spend a reaction."""

    def test_the_chosen_option_is_sent_back_to_the_session(self, cli):
        cli.session.pending_decision = _decision()
        answered = {"n": 0}

        def stop_after_one(*args, **kwargs):
            answered["n"] += 1
            cli.session.pending_decision = None
            return Mock(ask=Mock(return_value=ATTACK_OPTION_ID))

        with patch("terminal_client.ui.cli.questionary.select", side_effect=stop_after_one):
            cli._render_session_result(ActionResult(ok=True))

        cli.session.resolve.assert_called_once_with("oa-1", ATTACK_OPTION_ID)

    def test_declining_is_sent_back_as_a_decline(self, cli):
        cli.session.pending_decision = _decision()

        def stop_after_one(*args, **kwargs):
            cli.session.pending_decision = None
            return Mock(ask=Mock(return_value=DECLINE_OPTION_ID))

        with patch("terminal_client.ui.cli.questionary.select", side_effect=stop_after_one):
            cli._render_session_result(ActionResult(ok=True))

        cli.session.resolve.assert_called_once_with("oa-1", DECLINE_OPTION_ID)

    def test_an_abandoned_prompt_falls_back_to_the_default(self, cli):
        """Ctrl-C at the menu must not stall the fight.

        The default is the automatic attack the engine always used to make, so
        walking away from the question gets the old behaviour rather than a
        hang.
        """
        cli.session.pending_decision = _decision()

        def stop_after_one(*args, **kwargs):
            cli.session.pending_decision = None
            return Mock(ask=Mock(return_value=None))

        with patch("terminal_client.ui.cli.questionary.select", side_effect=stop_after_one):
            cli._render_session_result(ActionResult(ok=True))

        cli.session.resolve.assert_called_once_with("oa-1", ATTACK_OPTION_ID)

    def test_a_rejected_answer_does_not_loop(self, cli):
        """A refused resolution leaves the decision pending; asking forever would hang."""
        cli.session.pending_decision = _decision()
        cli.session.resolve.return_value = ActionResult(
            ok=False, error="unknown option 'nonsense'"
        )

        with patch(
            "terminal_client.ui.cli.questionary.select",
            return_value=Mock(ask=Mock(return_value=ATTACK_OPTION_ID)),
        ):
            cli._render_session_result(ActionResult(ok=True))

        assert cli.session.resolve.call_count == 1

    def test_a_refused_action_still_drains_the_question(self, cli):
        """The refusal is usually *because* a decision is outstanding.

        Leaving it unanswered would soft-lock the fight: the session refuses
        every further intent while a decision is pending, so the player would
        be asked for commands that could never be accepted.
        """
        cli.session.pending_decision = _decision()

        def stop_after_one(*args, **kwargs):
            cli.session.pending_decision = None
            return Mock(ask=Mock(return_value=DECLINE_OPTION_ID))

        with patch("terminal_client.ui.cli.questionary.select", side_effect=stop_after_one):
            cli._render_session_result(
                ActionResult(ok=False, error="a decision is outstanding (oa-1)")
            )

        cli.session.resolve.assert_called_once_with("oa-1", DECLINE_OPTION_ID)

    def test_nothing_is_asked_when_no_decision_is_pending(self, cli):
        cli.session.pending_decision = None

        with patch("terminal_client.ui.cli.questionary.select") as mock_select:
            cli._render_session_result(ActionResult(ok=True))

        mock_select.assert_not_called()
        cli.session.resolve.assert_not_called()
