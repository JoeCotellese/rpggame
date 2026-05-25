# ABOUTME: SRD conformance audit for "Playing the Game > Reactions".
# ABOUTME: Cross-references docs/srd/playing-the-game/reactions.md against engine code.

"""SRD conformance: Reactions.

Maps every rule in `docs/srd/playing-the-game/reactions.md` to a test.
Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dnd_engine.systems.action_economy import TurnState

pytestmark = pytest.mark.srd(
    "playing-the-game/reactions.md",
    lines="1438-1451",
)


SPELLS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "spells.json"
)


class TestReaction_Definition:
    """SRD § Playing the Game › Reactions › Definition.

    > Certain special abilities, spells, and situations allow you to
    > take a special action called a Reaction.
    """

    def test_reaction_casting_time_is_a_recognized_spell_timing(self) -> None:
        """At least one SRD spell declares `casting_time: "1 reaction"`.

        Data-parity check: the SRD's "spells [...] allow you to take a
        special action called a Reaction" clause shows up as a real
        casting-time string on at least one spell in `spells.json`
        (e.g., Shield). Confirms the catalog encodes the trigger
        surface, even though the engine's turn loop does not yet
        consume it (see TestReaction_OncePerRound below).
        """
        spells = json.loads(SPELLS_JSON.read_text())
        reaction_spells = [
            (sid, sdata.get("name"))
            for sid, sdata in spells.items()
            if sdata.get("casting_time") == "1 reaction"
        ]
        assert reaction_spells, (
            "Expected at least one spell with `casting_time: '1 reaction'` "
            "in spells.json (e.g., shield)."
        )

    def test_reaction_action_type_is_modeled_in_action_economy(self) -> None:
        """ActionType enumerates REACTION; TurnState tracks reaction_available.

        SRD requires the "special action called a Reaction" to be a
        first-class member of the action economy. Closes the original
        gap captured under issue #412.
        """
        from dnd_engine.systems.action_economy import ActionType

        assert ActionType.REACTION.value == "reaction"
        turn = TurnState()
        assert hasattr(turn, "reaction_available")
        assert turn.reaction_available is True


class TestReaction_TriggerResponse:
    """SRD § Playing the Game › Reactions › Trigger Response.

    > A Reaction is an instant response to a trigger of some kind,
    > which can occur on your turn or on someone else's.
    """

    def test_reaction_can_fire_outside_the_reactors_turn(self) -> None:
        pytest.skip(
            "GAP: The engine has no general 'trigger -> reaction' "
            "dispatch. The only Reaction-shaped fan-out today is "
            "`GameState.flee_combat()` "
            "(dnd_engine/core/game_state.py:4194), which fires for "
            "every living enemy when the *party* attempts to retreat. "
            "There is no event-bus subscription model that lets a "
            "creature register a reaction to fire on an arbitrary "
            "trigger during another creature's turn (e.g., Shield in "
            "response to being hit, Counterspell in response to a "
            "cast). Tracked by issue #429 (depends on #412 reaction "
            "economy); see also #413 for per-creature OAs on tactical "
            "movement."
        )

    def test_reaction_can_fire_during_the_reactors_own_turn(self) -> None:
        pytest.skip(
            "GAP: same root cause as above — no trigger -> reaction "
            "dispatch exists. The SRD explicitly carves out that a "
            "Reaction may occur on the reactor's own turn (e.g., "
            "Opportunity Attack provoked by another creature's "
            "movement that happens to fall in your turn's window), "
            "but with no reaction model at all this exception is "
            "moot. Tracked by issue #429."
        )


class TestReaction_OpportunityAttackIsMostCommon:
    """SRD § Playing the Game › Reactions › OA is the most common type.

    > The Opportunity Attack, described later in "Playing the Game,"
    > is the most common type of Reaction.
    """

    def test_opportunity_attack_path_exists_in_engine(self) -> None:
        """`GameState.flee_combat` is the engine's OA-equivalent path.

        The SRD's "OA is the most common Reaction" framing is honored
        in spirit: there *is* an OA fan-out path on the engine side.
        Behavioral gaps (no Reaction consumption, no per-creature
        triggering, no visibility check) are audited in the
        melee-attacks conformance file. This test guards that the
        callable still exists so the citation in those skips stays
        accurate.
        """
        import inspect

        from dnd_engine.core.game_state import GameState

        assert callable(getattr(GameState, "flee_combat", None))
        src = inspect.getsource(GameState.flee_combat)
        assert "opportunity_attacks" in src, (
            "flee_combat must continue to surface an "
            "`opportunity_attacks` field — the conformance audit for "
            "melee-attacks anchors its OA citations here."
        )


class TestReaction_OncePerRound:
    """SRD § Playing the Game › Reactions › Once-per-round limit.

    > When you take a Reaction, you can't take another one until the
    > start of your next turn.
    """

    def test_turn_state_tracks_reaction_slot(self) -> None:
        """`TurnState` exposes a `reaction_available` field.

        SRD requires per-creature state that records "did this
        creature already use its Reaction this round?". `TurnState`
        now carries `reaction_available` alongside the existing
        action / bonus_action / free-object / movement slots.

        Closes the original gap captured under issue #412.
        """
        turn = TurnState()
        assert hasattr(turn, "reaction_available")
        assert turn.reaction_available is True

    def test_reaction_consumed_blocks_a_second_reaction_same_round(self) -> None:
        """Consuming the Reaction slot blocks a second Reaction this round.

        SRD: "When you take a Reaction, you can't take another one
        until the start of your next turn." A second
        ``consume_action(REACTION)`` in the same turn must return
        ``False``.
        """
        from dnd_engine.systems.action_economy import ActionType

        turn = TurnState()
        assert turn.consume_action(ActionType.REACTION) is True
        assert turn.reaction_available is False
        assert turn.consume_action(ActionType.REACTION) is False
        assert turn.is_action_available(ActionType.REACTION) is False

    def test_reaction_resets_at_start_of_next_turn(self) -> None:
        """`TurnState.reset()` restores the Reaction slot.

        SRD's "until the start of your next turn" phrasing requires a
        reaction flag that is cleared by the same path that resets
        the rest of the action economy. ``InitiativeTracker.next_turn``
        invokes ``.reset()`` on the incoming combatant, so resetting
        the reaction flag there enforces the once-per-round rule.
        """
        from dnd_engine.systems.action_economy import ActionType

        turn = TurnState()
        turn.consume_action(ActionType.REACTION)
        assert turn.reaction_available is False

        turn.reset()
        assert turn.reaction_available is True
        assert turn.is_action_available(ActionType.REACTION) is True


class TestReaction_InterruptedTurnContinuation:
    """SRD § Playing the Game › Reactions › Interrupted-turn continuation.

    > If the reaction interrupts another creature's turn, that
    > creature can continue its turn right after the Reaction.
    """

    def test_interrupted_turn_resumes_after_reaction_resolves(self) -> None:
        pytest.skip(
            "GAP: There is no interruption model in the turn loop. "
            "`InitiativeTracker.next_turn` "
            "(dnd_engine/systems/initiative.py:173) advances the "
            "turn index monotonically; nothing pauses the active "
            "turn to resolve a Reaction triggered mid-action and "
            "then resume the original turn. Because no Reactions "
            "fire mid-turn today (see TestReaction_TriggerResponse), "
            "this rule has nothing to enforce, but the SRD's "
            "continuation guarantee will need a mid-turn pause/"
            "resume mechanism once Reactions are wired up. Tracked "
            "by issue #430 (depends on #412 reaction economy and "
            "#429 trigger->reaction dispatcher)."
        )


class TestReaction_TimingDefault:
    """SRD § Playing the Game › Reactions › Default timing.

    > In terms of timing, a Reaction takes place immediately after
    > its trigger unless the Reaction's description says otherwise.
    """

    def test_reaction_resolves_immediately_after_trigger_by_default(self) -> None:
        pytest.skip(
            "GAP: No trigger-bound Reaction dispatcher exists. The "
            "engine has no concept of 'this Reaction is bound to "
            "trigger X and fires immediately after X resolves'. "
            "`flee_combat()` resolves its attack fan-out inline in "
            "the same call (game_state.py:4238-4304), which is "
            "incidentally 'immediately after' but is not gated on a "
            "named trigger — every flee fires every enemy's "
            "pseudo-OA regardless of any reaction state. A real "
            "implementation needs (a) named triggers (movement-out-"
            "of-reach, attacked, spell-cast-nearby, etc.) and (b) a "
            "default resolve-immediately policy unless the Reaction "
            "carves out 'before' / 'after' timing. Tracked by issue "
            "#429 (depends on #412 reaction economy)."
        )

    def test_reaction_description_can_override_default_timing(self) -> None:
        pytest.skip(
            "GAP: depends on the trigger/dispatch model in the test "
            "above. The SRD's 'unless the Reaction's description says "
            "otherwise' clause requires per-reaction timing metadata "
            "(e.g., Shield resolves *before* the triggering hit is "
            "applied so its AC bonus counts against that very "
            "attack). spells.json carries `casting_time: '1 reaction'` "
            "but no engine field encoding *which* trigger or *when* "
            "relative to the trigger. Tracked under issue #429 as a "
            "sub-clause of the dispatcher acceptance criteria."
        )
