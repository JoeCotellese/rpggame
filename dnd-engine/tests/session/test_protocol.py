# ABOUTME: Unit tests for the session protocol types (issue P1-01).
# ABOUTME: Covers construction, JSON round-tripping, outcome states, and decision validation.

"""Tests for `dnd_engine.session.protocol`.

Each test class maps to one acceptance criterion in
`plans/autonomous/issues/P1-01.md`.
"""

import ast
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from dnd_engine.session.protocol import (
    ActionResult,
    AttackIntent,
    DecisionKind,
    DecisionOption,
    FreeformIntent,
    GameEvent,
    Intent,
    IntentKind,
    MoveIntent,
    PendingDecision,
    WaitIntent,
)
from dnd_engine.utils.events import EventType


def _sample_intents() -> list[Intent]:
    """Representative instance of every intent subclass."""
    return [
        MoveIntent(actor_id="pc_thorin", direction="east"),
        AttackIntent(actor_id="pc_thorin", target_ref="goblin_1"),
        WaitIntent(actor_id="pc_elara"),
        FreeformIntent(actor_id="pc_nyx", text="I shove the brazier into the webs"),
    ]


class TestAC1IntentsUsePrimitivesOnly:
    """AC-1: intents express player wants without engine types."""

    def test_every_intent_constructs_from_primitives(self):
        for intent in _sample_intents():
            assert isinstance(intent.actor_id, str)
            assert isinstance(intent.kind, IntentKind)

    def test_move_intent_carries_direction(self):
        assert MoveIntent(actor_id="pc_thorin", direction="east").direction == "east"

    def test_attack_intent_carries_target_ref(self):
        assert AttackIntent(actor_id="pc_thorin", target_ref="goblin_1").target_ref == "goblin_1"

    def test_freeform_intent_carries_raw_text(self):
        text = "I shove the brazier into the webs"
        assert FreeformIntent(actor_id="pc_nyx", text=text).text == text

    def test_intents_are_immutable(self):
        intent = MoveIntent(actor_id="pc_thorin", direction="east")
        with pytest.raises(FrozenInstanceError):
            intent.direction = "west"  # type: ignore[misc]

    def test_protocol_module_does_not_import_engine_internals(self):
        """The protocol must stay free of core engine types.

        `EventType` from `utils.events` is the one deliberate exception —
        reusing it is AC-5. Any import from `dnd_engine.core` would couple
        clients to engine internals, which is the coupling this issue exists
        to remove.
        """
        source = Path(__file__).parents[2] / "dnd_engine" / "session" / "protocol.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))

        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
            elif isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)

        offenders = [m for m in imported if m.startswith("dnd_engine.core")]
        assert offenders == [], f"protocol.py must not import engine internals: {offenders}"

        dnd_imports = {m for m in imported if m.startswith("dnd_engine")}
        assert dnd_imports <= {"dnd_engine.utils.events"}, (
            f"unexpected dnd_engine imports in protocol.py: {dnd_imports}"
        )


class TestAC2JsonRoundTrip:
    """AC-2: every protocol type round-trips through JSON unchanged."""

    @pytest.mark.parametrize("intent", _sample_intents(), ids=lambda i: i.kind.value)
    def test_intent_round_trips(self, intent):
        restored = Intent.from_dict(json.loads(json.dumps(intent.to_dict())))
        assert restored == intent

    def test_game_event_round_trips(self):
        event = GameEvent(
            type=EventType.DAMAGE_DEALT,
            data={"attacker": "pc_thorin", "target": "goblin_1", "amount": 7},
            sequence=0,
            message="Thorin hits Goblin for 7 damage.",
        )
        assert GameEvent.from_dict(json.loads(json.dumps(event.to_dict()))) == event

    def test_game_event_round_trips_with_empty_data_and_no_message(self):
        event = GameEvent(type=EventType.TURN_END, data={}, sequence=3)
        restored = GameEvent.from_dict(json.loads(json.dumps(event.to_dict())))
        assert restored == event
        assert restored.message is None

    def test_pending_decision_round_trips(self):
        decision = PendingDecision(
            decision_id="d1",
            kind=DecisionKind.REACTION,
            actor_id="pc_thorin",
            prompt="Goblin is leaving your reach. Use your reaction?",
            options=(
                DecisionOption("attack", "Opportunity attack", "Melee attack as a reaction"),
                DecisionOption("decline", "Decline"),
            ),
            default_option_id="decline",
            context={"provoker": "goblin_1"},
        )
        assert PendingDecision.from_dict(json.loads(json.dumps(decision.to_dict()))) == decision

    def test_action_result_round_trips_with_no_events(self):
        result = ActionResult(ok=False, error="not your turn")
        restored = ActionResult.from_dict(json.loads(json.dumps(result.to_dict())))
        assert restored == result
        assert restored.events == ()
        assert restored.pending is None

    def test_action_result_round_trips_with_events_and_pending(self):
        result = ActionResult(
            ok=True,
            events=(
                GameEvent(type=EventType.CREATURE_MOVED, data={"to": [3, 4]}, sequence=0),
                GameEvent(type=EventType.TURN_END, data={}, sequence=1, message="Turn ends."),
            ),
            pending=PendingDecision(
                decision_id="d2",
                kind=DecisionKind.CONFIRM,
                actor_id="pc_nyx",
                prompt="Really step into the pit?",
                options=(DecisionOption("yes", "Yes"), DecisionOption("no", "No")),
                default_option_id="no",
            ),
        )
        restored = ActionResult.from_dict(json.loads(json.dumps(result.to_dict())))
        assert restored == result
        assert isinstance(restored.events, tuple)

    def test_to_dict_output_is_json_serialisable_for_all_types(self):
        payloads = [i.to_dict() for i in _sample_intents()]
        payloads.append(GameEvent(type=EventType.COMBAT_START, data={}, sequence=0).to_dict())
        payloads.append(ActionResult(ok=True).to_dict())
        for payload in payloads:
            json.dumps(payload)


class TestAC3ActionResultOutcomeStates:
    """AC-3: ActionResult distinguishes the outcomes a caller must handle.

    Three states, not four — see the AC-3 amendment note in the issue file.
    """

    def test_succeeded_and_continue(self):
        result = ActionResult(ok=True, events=(GameEvent(EventType.TURN_END, {}, 0),))
        assert result.ok
        assert not result.is_awaiting_decision
        assert result.error is None

    def test_succeeded_but_awaiting_decision(self):
        result = ActionResult(
            ok=True,
            pending=PendingDecision(
                decision_id="d1",
                kind=DecisionKind.REACTION,
                actor_id="pc_thorin",
                prompt="React?",
                options=(DecisionOption("yes", "Yes"),),
            ),
        )
        assert result.ok
        assert result.is_awaiting_decision
        assert result.error is None

    def test_rejected_with_reason(self):
        result = ActionResult(ok=False, error="occupied by goblin_1")
        assert not result.ok
        assert not result.is_awaiting_decision
        assert result.error == "occupied by goblin_1"

    def test_failure_always_carries_an_error(self):
        with pytest.raises(ValueError, match="error"):
            ActionResult(ok=False)

    def test_caller_can_branch_without_inspecting_events(self):
        """The four states must be distinguishable from ok/pending/error alone."""
        states = {
            (r.ok, r.is_awaiting_decision, r.error is not None)
            for r in (
                ActionResult(ok=True),
                ActionResult(
                    ok=True,
                    pending=PendingDecision(
                        decision_id="d",
                        kind=DecisionKind.CONFIRM,
                        actor_id="a",
                        prompt="?",
                        options=(DecisionOption("y", "Yes"),),
                    ),
                ),
                ActionResult(ok=False, error="rejected"),
            )
        }
        assert len(states) == 3


class TestAC4PendingDecisionRendering:
    """AC-4: PendingDecision carries enough to render a prompt and to auto-answer."""

    def _decision(self, **overrides):
        kwargs = {
            "decision_id": "d1",
            "kind": DecisionKind.REACTION,
            "actor_id": "pc_thorin",
            "prompt": "Goblin is leaving your reach. Use your reaction?",
            "options": (
                DecisionOption("attack", "Opportunity attack"),
                DecisionOption("decline", "Decline"),
            ),
            "default_option_id": "decline",
        }
        kwargs.update(overrides)
        return PendingDecision(**kwargs)

    def test_renderable_fields_are_populated(self):
        decision = self._decision()
        assert decision.prompt
        assert decision.actor_id
        assert all(option.label for option in decision.options)

    def test_default_option_id_names_a_real_option(self):
        decision = self._decision()
        assert decision.default_option_id in {o.option_id for o in decision.options}

    def test_unknown_default_option_id_is_rejected(self):
        with pytest.raises(ValueError, match="default_option_id"):
            self._decision(default_option_id="nonexistent")

    def test_default_option_id_is_optional(self):
        assert self._decision(default_option_id=None).default_option_id is None

    def test_empty_options_is_rejected(self):
        with pytest.raises(ValueError, match="options"):
            self._decision(options=(), default_option_id=None)

    def test_duplicate_option_ids_are_rejected(self):
        with pytest.raises(ValueError, match="duplicate"):
            self._decision(
                options=(DecisionOption("a", "A"), DecisionOption("a", "A again")),
                default_option_id=None,
            )

    def test_default_option_enables_auto_answering(self):
        """A headless caller resolves by picking the default without prompting."""
        decision = self._decision()
        chosen = next(o for o in decision.options if o.option_id == decision.default_option_id)
        assert chosen.label == "Decline"


class TestAC5ReusesExistingEventTaxonomy:
    """AC-5: GameEvent reuses the existing EventType enum."""

    def test_game_event_type_is_an_event_type_member(self):
        event = GameEvent(type=EventType.DAMAGE_DEALT, data={}, sequence=0)
        assert isinstance(event.type, EventType)

    def test_round_trip_preserves_event_type_identity(self):
        event = GameEvent(type=EventType.ATTACK_ROLL, data={}, sequence=0)
        assert GameEvent.from_dict(event.to_dict()).type is event.type

    def test_protocol_declares_no_parallel_event_enum(self):
        """No enum here may duplicate the engine's event taxonomy.

        The allowed set is a whitelist, widened deliberately as the protocol
        grows. `ErrorKind` was added in P1-02 to separate a rules rejection from
        an internal failure; it classifies *failures*, not events, so it does not
        violate what this test exists to prevent — a second `EventType`.
        """
        source = Path(__file__).parents[2] / "dnd_engine" / "session" / "protocol.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        enum_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
            and any(getattr(base, "id", "") == "Enum" or
                    getattr(base, "attr", "") == "Enum" or
                    getattr(base, "id", "") == "str"
                    for base in node.bases)
        }
        assert enum_names == {"IntentKind", "DecisionKind", "ErrorKind"}, (
            f"unexpected enums declared in protocol.py: {enum_names}"
        )


class TestPayloadNormalisation:
    """Regression guard for the P1-01 review finding.

    `CREATURE_MOVED` — emitted on every grid movement — carries `Position`
    objects, which are not JSON-serialisable at all. Before normalisation
    `ActionResult.to_json()` raised `TypeError` on any movement event, and
    tuples silently returned as lists so payloads no longer compared equal.
    """

    def test_dataclass_payload_values_become_dicts(self):
        from dnd_engine.core.position import Position

        event = GameEvent(
            type=EventType.CREATURE_MOVED,
            data={"entity_id": "pc_1", "origin": Position(1, 2), "to": Position(3, 4)},
            sequence=0,
        )
        assert event.data["origin"] == {"x": 1, "y": 2}
        assert event.data["to"] == {"x": 3, "y": 4}

    def test_movement_event_serialises_and_round_trips(self):
        from dnd_engine.core.position import Position

        event = GameEvent(
            type=EventType.CREATURE_MOVED,
            data={"entity_id": "pc_1", "origin": Position(1, 2), "to": Position(3, 4)},
            sequence=0,
        )
        assert GameEvent.from_dict(json.loads(json.dumps(event.to_dict()))) == event

    def test_tuples_round_trip_by_normalising_to_lists(self):
        event = GameEvent(type=EventType.CREATURE_MOVED, data={"to": (3, 4)}, sequence=0)
        assert event.data["to"] == [3, 4]
        assert GameEvent.from_dict(json.loads(json.dumps(event.to_dict()))) == event

    def test_enum_payload_values_become_their_value(self):
        event = GameEvent(
            type=EventType.TURN_START, data={"phase": DecisionKind.REACTION}, sequence=0
        )
        assert event.data["phase"] == "reaction"

    def test_nested_structures_are_normalised_recursively(self):
        event = GameEvent(
            type=EventType.COMBAT_START,
            data={"sides": [{"members": ({"id": "a"}, {"id": "b"})}]},
            sequence=0,
        )
        assert event.data == {"sides": [{"members": [{"id": "a"}, {"id": "b"}]}]}
        assert GameEvent.from_dict(json.loads(json.dumps(event.to_dict()))) == event

    def test_unknown_object_degrades_to_string_rather_than_breaking_the_turn(self):
        class Opaque:
            def __repr__(self) -> str:
                return "<opaque>"

        event = GameEvent(type=EventType.TURN_END, data={"thing": Opaque()}, sequence=0)
        assert event.data["thing"] == "<opaque>"
        json.dumps(event.to_dict())

    def test_pending_decision_context_is_normalised_too(self):
        from dnd_engine.core.position import Position

        decision = PendingDecision(
            decision_id="d1",
            kind=DecisionKind.REACTION,
            actor_id="pc_thorin",
            prompt="React?",
            options=(DecisionOption("yes", "Yes"),),
            context={"provoker_at": Position(5, 6)},
        )
        assert decision.context["provoker_at"] == {"x": 5, "y": 6}
        assert PendingDecision.from_dict(json.loads(json.dumps(decision.to_dict()))) == decision

    def test_action_result_with_movement_events_serialises(self):
        from dnd_engine.core.position import Position

        result = ActionResult(
            ok=True,
            events=(
                GameEvent(
                    type=EventType.CREATURE_MOVED,
                    data={"to": Position(3, 4)},
                    sequence=0,
                ),
            ),
        )
        assert ActionResult.from_dict(json.loads(result.to_json())) == result
