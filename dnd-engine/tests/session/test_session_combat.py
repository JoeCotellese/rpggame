# ABOUTME: Integration tests driving real crypt combat entirely through the Session facade.
# ABOUTME: Proves a client can play a full fight without touching engine internals.

"""Integration verification for P1-02.

The point of the facade is that a caller never implements D&D's turn structure.
These tests therefore play real combat using only `Session.perform()` and the
session's public properties — no `initiative_tracker`, no `_check_combat_end`,
no `process_enemy_turn`.
"""

from __future__ import annotations

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.entity_ids import pc_entity_id
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.session import AttackIntent, Session, WaitIntent
from dnd_engine.utils.events import EventBus, EventType

MAX_ROUNDS = 60


def _party() -> Party:
    """Two level-3 fighters, durable enough to finish a fight."""
    return Party(
        [
            Character(
                name=name,
                character_class=CharacterClass.FIGHTER,
                level=3,
                abilities=Abilities(
                    strength=16,
                    dexterity=12,
                    constitution=14,
                    intelligence=10,
                    wisdom=11,
                    charisma=8,
                ),
                max_hp=30,
                ac=16,
            )
            for name in ("Thorin", "Garrick")
        ]
    )


@pytest.fixture
def session() -> Session:
    """A session in the crypt, already in combat at the graveyard entrance."""
    game = GameState(
        party=_party(),
        dungeon_name="crypt",
        campaign_id="the_unquiet_dead",
        event_bus=EventBus(),
        data_loader=DataLoader(),
        dice_roller=DiceRoller(seed=20260802),
    )
    game.start()
    return Session(game)


def _fight_to_the_end(session: Session) -> list:
    """Play until combat ends, using only the facade. Returns all events."""
    collected = []
    for _ in range(MAX_ROUNDS):
        if session.is_over or not session.in_combat:
            break
        actor = session.awaiting_actor_id
        if actor is None:
            break
        enemies = [e for e in session.snapshot()["enemies"] if e["is_alive"]]
        intent = (
            AttackIntent(actor_id=actor, target_ref=enemies[0]["name"])
            if enemies
            else WaitIntent(actor_id=actor)
        )
        result = session.perform(intent)
        assert result.ok, f"facade rejected a legal action: {result.error}"
        collected.extend(result.events)
    return collected


class TestAC1PlayableThroughPerformAlone:
    """AC-1: a full combat is playable through perform() alone."""

    def test_combat_reaches_a_terminal_state(self, session):
        assert session.in_combat, "expected the crypt entrance to start a fight"
        _fight_to_the_end(session)
        assert not session.in_combat or session.is_over

    def test_the_caller_never_needed_engine_internals(self):
        """This module must not *access* private GameState members.

        Checked over the AST rather than the raw text, so mentioning a name in
        prose (as this docstring does) is not mistaken for using it.
        """
        import ast
        from pathlib import Path

        forbidden = {"_check_combat_end", "initiative_tracker", "process_enemy_turn"}
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))

        accessed = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }

        assert not (accessed & forbidden), (
            f"integration test reaches into engine internals: {sorted(accessed & forbidden)}"
        )


class TestAC2EngineAdvancesTheTurn:
    """AC-2: the engine advances the turn, not the caller."""

    def test_control_returns_only_on_a_conscious_party_member(self, session):
        for _ in range(12):
            if not session.in_combat or session.is_over:
                break
            actor = session.awaiting_actor_id
            if actor is None:
                break

            party = {p["entity_id"]: p for p in session.snapshot()["party"]}
            assert actor in party, f"awaiting an actor who is not in the party: {actor}"
            assert party[actor]["is_alive"], "handed control to a dead character"
            assert not party[actor]["is_unconscious"], "handed control to an unconscious character"

            session.perform(WaitIntent(actor_id=actor))

    def test_waiting_advances_past_the_actor(self, session):
        first = session.awaiting_actor_id
        assert first is not None
        session.perform(WaitIntent(actor_id=first))
        assert session.awaiting_actor_id != first or not session.in_combat


class TestAC3EnemyTurnsDrained:
    """AC-3: enemy turns are drained automatically."""

    def test_one_perform_surfaces_events_from_enemies(self, session):
        """A player who merely waits should still see what the enemies did.

        This is the observable consequence of draining: the caller made one
        call, took no action itself, and the result nonetheless describes enemy
        activity.
        """
        party_names = {p["name"] for p in session.snapshot()["party"]}
        enemy_actor_seen = False

        for _ in range(MAX_ROUNDS):
            if not session.in_combat or session.is_over:
                break
            actor = session.awaiting_actor_id
            if actor is None:
                session.advance()
                continue

            result = session.perform(WaitIntent(actor_id=actor))
            for event in result.events:
                name = event.data.get("attacker") or event.data.get("actor")
                if name and name not in party_names:
                    enemy_actor_seen = True
            if enemy_actor_seen:
                break

        assert enemy_actor_seen, (
            "a waiting player saw no enemy activity — enemy turns were not drained"
        )


class TestAC5WeaponAttacksAppearInEvents:
    """AC-5: weapon attacks appear in the event stream.

    The engine publishes nothing to the bus for weapon attacks, so if these
    events are present the facade's synthesis is working.
    """

    def test_attacking_produces_an_attack_roll_event(self, session):
        actor = session.awaiting_actor_id
        assert actor is not None
        enemies = [e for e in session.snapshot()["enemies"] if e["is_alive"]]
        assert enemies, "expected living enemies at the crypt entrance"

        result = session.perform(
            AttackIntent(actor_id=actor, target_ref=enemies[0]["name"])
        )

        assert result.ok, result.error
        assert any(e.type is EventType.ATTACK_ROLL for e in result.events), (
            "no ATTACK_ROLL event — facade is not synthesizing weapon attacks"
        )

    def test_a_landed_hit_produces_a_damage_event(self, session):
        for _ in range(MAX_ROUNDS):
            if not session.in_combat:
                break
            actor = session.awaiting_actor_id
            if actor is None:
                break
            enemies = [e for e in session.snapshot()["enemies"] if e["is_alive"]]
            if not enemies:
                break
            result = session.perform(
                AttackIntent(actor_id=actor, target_ref=enemies[0]["name"])
            )
            hits = [
                e
                for e in result.events
                if e.type is EventType.ATTACK_ROLL and e.data.get("hit")
            ]
            if hits:
                assert any(e.type is EventType.DAMAGE_DEALT for e in result.events), (
                    "an attack hit but produced no DAMAGE_DEALT event"
                )
                return
        pytest.skip("no attack landed within the round budget")


class TestAC6EventOrdering:
    """AC-6: events preserve real chronological order."""

    def test_sequence_numbers_are_contiguous_from_zero(self, session):
        actor = session.awaiting_actor_id
        assert actor is not None
        result = session.perform(WaitIntent(actor_id=actor))
        assert [e.sequence for e in result.events] == list(range(len(result.events)))

    def test_ordering_holds_across_a_whole_fight(self, session):
        for _ in range(10):
            if not session.in_combat or session.is_over:
                break
            actor = session.awaiting_actor_id
            if actor is None:
                break
            result = session.perform(WaitIntent(actor_id=actor))
            assert [e.sequence for e in result.events] == list(range(len(result.events)))


class TestAC7RejectionsAreTyped:
    """AC-7: rejections are distinguishable from internal failures."""

    def test_acting_out_of_turn_is_a_rule_rejection(self, session):
        from dnd_engine.session import ErrorKind

        actor = session.awaiting_actor_id
        assert actor is not None
        other = next(
            p["entity_id"] for p in session.snapshot()["party"] if p["entity_id"] != actor
        )

        result = session.perform(WaitIntent(actor_id=other))

        assert not result.ok
        assert result.error_kind is ErrorKind.RULE
        assert "turn" in result.error

    def test_attacking_a_nonexistent_target_is_a_rule_rejection(self, session):
        from dnd_engine.session import ErrorKind

        actor = session.awaiting_actor_id
        assert actor is not None
        result = session.perform(
            AttackIntent(actor_id=actor, target_ref="a dragon that is not here")
        )
        assert not result.ok
        assert result.error_kind is ErrorKind.RULE

    def test_a_rejected_action_does_not_consume_the_turn(self, session):
        actor = session.awaiting_actor_id
        session.perform(AttackIntent(actor_id=actor, target_ref="nonexistent"))
        assert session.awaiting_actor_id == actor, "a rejection consumed the actor's turn"


class TestSnapshotIsRenderable:
    """A client must be able to render from the snapshot without engine types."""

    def test_snapshot_is_json_native(self, session):
        import json

        json.dumps(session.snapshot())

    def test_snapshot_names_the_awaiting_actor(self, session):
        snap = session.snapshot()
        if snap["awaiting_actor_id"] is not None:
            ids = {p["entity_id"] for p in snap["party"]}
            assert snap["awaiting_actor_id"] in ids

    def test_entity_ids_match_the_engine_convention(self, session):
        for member in session.snapshot()["party"]:
            assert member["entity_id"] == pc_entity_id(member["name"])


class TestSynthesisDoesNotDuplicateTheBus:
    """Synthesis must cover only what the engine does not publish.

    P1-02 PLAYTEST found every death save reported twice: once from the bus and
    once synthesized. Measured across five seeded fights, `ATTACK_ROLL`,
    `DAMAGE_DEALT` and `CHARACTER_DEATH` came only from synthesis (the bus is
    silent for weapon attacks), while `DEATH_SAVE` came from both. This guard
    stops a future synthesized type from silently double-reporting.
    """

    def test_no_event_type_arrives_from_both_sources(self, session):
        from collections import Counter

        from dnd_engine.session import session as session_module

        bus_types: Counter = Counter()
        synth_types: Counter = Counter()

        original_record = session_module._EventRecorder.record
        original_bus = session_module._EventRecorder.record_bus_event

        def traced_bus(self, event):
            bus_types[event.type.name] += 1
            self._from_bus = True
            try:
                original_bus(self, event)
            finally:
                self._from_bus = False

        def traced_record(self, event_type, data, message=None):
            if not getattr(self, "_from_bus", False):
                synth_types[event_type.name] += 1
            original_record(self, event_type, data, message)

        session_module._EventRecorder.record = traced_record
        session_module._EventRecorder.record_bus_event = traced_bus
        try:
            session.advance()
            _fight_to_the_end(session)
        finally:
            session_module._EventRecorder.record = original_record
            session_module._EventRecorder.record_bus_event = original_bus

        both = sorted(set(bus_types) & set(synth_types))
        assert both == [], (
            f"event types reported twice — once from the bus and once synthesized: {both}"
        )


class TestCombatStartWithEnemyInitiative:
    """Regression: an enemy holding the first initiative slot must not deadlock.

    Found during P1-02 PLAYTEST. Enemy turns drain only inside a session call, so
    when combat opened with an enemy up, `awaiting_actor_id` was None and a client
    following the documented contract had no legal move at all.
    """

    def test_advance_yields_an_actor_or_ends_combat(self, session):
        session.advance()
        assert (
            session.awaiting_actor_id is not None
            or not session.in_combat
            or session.is_over
        ), "advance() left the session with nobody to act as"

    def test_advance_is_safe_when_a_player_is_already_up(self, session):
        session.advance()
        before = session.awaiting_actor_id
        result = session.advance()
        assert result.ok
        assert session.awaiting_actor_id == before, "advance() skipped a waiting player's turn"

    def test_advance_out_of_combat_is_a_noop(self, session):
        session.advance()
        _fight_to_the_end(session)
        if not session.in_combat:
            result = session.advance()
            assert result.ok
            assert result.events == ()


class TestEnemiesAreDistinguishable:
    """Regression: a caller must be able to target one of two identical enemies.

    Found during P1-02 REVIEW. `InitiativeTracker.assign_combat_numbers` exists to
    turn two skeletons into "Skeleton 1" and "Skeleton 2", but nothing in the
    engine called it — only `client-terminal` did (`cli.py:6243`). Every other
    client saw two identical names, and `_resolve_target` silently attacked
    whichever the engine listed first. The facade now assigns the numbers itself,
    so all clients inherit the disambiguation.
    """

    def test_same_named_enemies_get_distinct_display_names(self, session):
        session.advance()
        enemies = [e for e in session.snapshot()["enemies"] if e["is_alive"]]
        if len({e["name"] for e in enemies}) == len(enemies):
            pytest.skip("this encounter has no duplicate enemy names")

        display_names = [e["display_name"] for e in enemies]
        assert len(set(display_names)) == len(display_names), (
            f"enemies are not distinguishable: {display_names}"
        )

    def test_attacks_land_on_the_named_target_only(self, session):
        session.advance()
        enemies = [e for e in session.snapshot()["enemies"] if e["is_alive"]]
        if len(enemies) < 2:
            pytest.skip("need at least two living enemies to test precise targeting")

        target_name = enemies[1]["display_name"]
        untouched_name = enemies[0]["display_name"]
        untouched_hp_before = enemies[0]["hp"]

        for _ in range(MAX_ROUNDS):
            if not session.in_combat or session.is_over:
                break
            actor = session.awaiting_actor_id
            if actor is None:
                session.advance()
                continue
            current = {
                e["display_name"]: e
                for e in session.snapshot()["enemies"]
                if e["is_alive"]
            }
            if target_name not in current:
                break
            session.perform(AttackIntent(actor_id=actor, target_ref=target_name))

        after = {e["display_name"]: e for e in session.snapshot()["enemies"]}
        if untouched_name in after:
            assert after[untouched_name]["hp"] == untouched_hp_before, (
                f"attacks aimed at {target_name} damaged {untouched_name}"
            )

    def test_combat_log_uses_the_disambiguated_name(self, session):
        session.advance()
        enemies = [e for e in session.snapshot()["enemies"] if e["is_alive"]]
        if len(enemies) < 2 or len({e["name"] for e in enemies}) == len(enemies):
            pytest.skip("this encounter has no duplicate enemy names")

        actor = session.awaiting_actor_id
        if actor is None:
            pytest.skip("no player actor available")
        target_name = enemies[1]["display_name"]
        result = session.perform(AttackIntent(actor_id=actor, target_ref=target_name))

        targets = {
            e.data.get("target") for e in result.events if e.data.get("target")
        }
        assert targets == {target_name}, (
            f"combat log names the target ambiguously: {targets} (wanted {target_name})"
        )


class TestEnemyTurnPayload:
    """An enemy turn must be renderable in full from its event alone.

    The synthesized attack events carry the roll and the damage, which is enough
    for a log line but not enough for a client that shows what `client-terminal`
    shows today: turn-start and turn-end condition effects, incapacitation,
    condition-removal attempts, saving throws and the conditions they applied,
    concentration breaks, and how far the monster moved. Those live on
    `EnemyTurnResult`, which the facade otherwise discards. `ENEMY_TURN` carries
    the whole thing so no client has to call `process_enemy_turn` to get it.
    """

    def _first_enemy_turn_event(self, session):
        """Play until an enemy takes a turn, and return that event."""
        for _ in range(MAX_ROUNDS):
            if not session.in_combat or session.is_over:
                return None
            actor = session.awaiting_actor_id
            if actor is None:
                result = session.advance()
            else:
                result = session.perform(WaitIntent(actor_id=actor))
            for event in result.events:
                if event.type is EventType.ENEMY_TURN:
                    return event
        return None

    def test_an_enemy_turn_emits_an_enemy_turn_event(self, session):
        assert self._first_enemy_turn_event(session) is not None, (
            "no ENEMY_TURN event — a client cannot render what the monster did"
        )

    def test_the_payload_carries_every_display_field(self, session):
        event = self._first_enemy_turn_event(session)
        assert event is not None

        for field in (
            "enemy_name",
            "enemy_display_name",
            "action_taken",
            "target_name",
            "target_killed",
            "action_data",
            "saving_throw_triggered",
            "save_ability",
            "save_dc",
            "save_succeeded",
            "conditions_applied",
            "condition_removal",
            "concentration_broken",
            "turn_start_effects",
            "turn_end_effects",
            "incapacitating_conditions",
            "moved_squares",
        ):
            assert field in event.data, f"ENEMY_TURN payload is missing {field!r}"

    def test_the_payload_is_json_native(self, session):
        import json

        event = self._first_enemy_turn_event(session)
        assert event is not None
        json.dumps(event.data)

    def test_an_attacking_enemy_carries_a_rendered_attack_line(self, session):
        """`AttackResult.__str__` is the mechanics line players read today.

        Serialising the dataclass loses it, so the facade carries the rendered
        text alongside the fields.
        """
        for _ in range(MAX_ROUNDS):
            if not session.in_combat or session.is_over:
                break
            actor = session.awaiting_actor_id
            if actor is None:
                result = session.advance()
            else:
                result = session.perform(WaitIntent(actor_id=actor))
            for event in result.events:
                if event.type is not EventType.ENEMY_TURN:
                    continue
                if event.data.get("attack_result") is None:
                    continue
                assert event.data.get("attack_text"), (
                    "an attacking enemy turn carries no rendered attack line"
                )
                return
        pytest.skip("no enemy landed an attack within the round budget")


class TestEnemyIdentityIsStable:
    """Regression: enemy ids must be unique and survive the whole session.

    Two defects found in P1-04. Display names collapsed back to the raw name
    once the engine dropped the initiative tracker at combat end, and
    `entity_id` collided before combat numbering had run — so a client reading
    the opening state of a fight saw two enemies sharing one id.
    """

    def test_entity_ids_are_unique_before_any_action(self, session):
        enemies = session.snapshot()["enemies"]
        ids = [e["entity_id"] for e in enemies]
        assert len(set(ids)) == len(ids), (
            f"enemies share an entity_id before the first action: {ids}"
        )

    def test_entity_ids_are_unique_after_the_fight(self, session):
        session.advance()
        _fight_to_the_end(session)
        ids = [e["entity_id"] for e in session.snapshot()["enemies"]]
        assert len(set(ids)) == len(ids), (
            f"enemies share an entity_id after combat ended: {ids}"
        )

    def test_display_names_survive_combat_end(self, session):
        session.advance()
        before = {e["entity_id"]: e["display_name"] for e in session.snapshot()["enemies"]}
        _fight_to_the_end(session)
        after = {e["entity_id"]: e["display_name"] for e in session.snapshot()["enemies"]}
        for entity_id, name in before.items():
            if entity_id in after:
                assert after[entity_id] == name, (
                    f"{entity_id} was '{name}' during combat and "
                    f"'{after[entity_id]}' afterwards"
                )
