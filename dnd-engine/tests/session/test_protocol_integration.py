# ABOUTME: Integration test proving the session protocol can carry real engine event payloads.
# ABOUTME: Drives actual crypt combat rather than synthetic fixtures, then round-trips what it captured.

"""Forward verification for the session protocol (issue P1-01).

Unit tests prove the protocol types round-trip *instances the test authored*.
That is not the same as proving they can carry what the engine actually emits.
This module drives real gameplay — walk the crypt, fight what is there — and
asserts every captured event survives the protocol unchanged.

Assertions are on invariants (serialisability, round-trip fidelity) rather than
on specific rolls, so the test stays meaningful regardless of what the
playthrough happens to roll.
"""

from __future__ import annotations

import json

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.session import ActionResult, GameEvent
from dnd_engine.utils.events import Event, EventBus, EventType

MAX_STEPS = 40

# Fixed so the playthrough exercises the same ground every run.
PLAYTHROUGH_SEED = 20260802


def _build_party() -> Party:
    """Two level-3 fighters — durable enough to survive the crypt's skeletons."""
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


def _play_the_crypt(seed: int = PLAYTHROUGH_SEED) -> list[Event]:
    """Walk the crypt and fight, returning every event the bus saw.

    Deliberately uses the real dungeon and real combat rather than a fixture so
    the payloads under test are the ones a client would actually receive.

    The dice roller is seeded, but be aware that **this does not make the run
    reproducible** — the engine has no complete determinism seam today. Enemy AI
    target selection calls the global ``random`` module directly
    (``systems/ai/targeting.py``, ``core/game_state.py:5969``), and some
    remaining variance survives even with ``random.seed()`` and
    ``PYTHONHASHSEED`` both pinned. Measured across runs: dice seed alone gives
    a stable 9 events but 5-6 distinct types; adding ``random.seed()`` made it
    worse (9 to 46 events). See ``QUESTIONS.md`` Q-002.

    That is why every assertion below is an invariant over whatever was
    captured, guarded by an explicit non-vacuity check, rather than an
    assertion about specific events.
    """
    party = _build_party()
    bus = EventBus()
    captured: list[Event] = []
    for event_type in EventType:
        bus.subscribe(event_type, captured.append)

    game = GameState(
        party=party,
        dungeon_name="crypt",
        campaign_id="the_unquiet_dead",
        event_bus=bus,
        data_loader=DataLoader(),
        dice_roller=DiceRoller(seed=seed),
    )
    game.start()

    for step in range(MAX_STEPS):
        if game.is_game_over():
            break

        if game.in_combat:
            current = game.initiative_tracker.get_current_combatant()
            if current is None:
                break
            if current.creature in party.characters:
                living = [e for e in game.active_enemies if e.is_alive]
                if not living:
                    game._check_combat_end()
                    continue
                game.execute_player_attack(current.creature, living[0])
                game.initiative_tracker.next_turn()
            else:
                game.process_enemy_turn()
            game._check_combat_end()
            continue

        exits = list(game.get_available_exits().keys())
        if not exits:
            break
        game.move(exits[step % len(exits)])

    return captured


@pytest.fixture(scope="module")
def played_events() -> list[Event]:
    """Events from one real crypt run, shared across the assertions below."""
    return _play_the_crypt()


class TestProtocolCarriesRealEngineEvents:
    """The protocol must survive contact with real engine payloads."""

    def test_the_run_actually_produced_events(self, played_events):
        """Guard against the whole suite passing vacuously on an empty run."""
        assert len(played_events) > 0, "playthrough emitted no events — the test proves nothing"
        assert {e.type for e in played_events} >= {EventType.ROOM_ENTER}, (
            "expected at least a room entry from walking the crypt"
        )

    def test_every_real_payload_is_json_serialisable(self, played_events):
        """A payload the protocol cannot serialise is a payload no client can receive."""
        unserialisable: dict[str, str] = {}
        for index, event in enumerate(played_events):
            game_event = GameEvent(type=event.type, data=event.data, sequence=index)
            try:
                json.dumps(game_event.to_dict())
            except TypeError as exc:
                unserialisable[event.type.name] = str(exc)

        assert unserialisable == {}, (
            f"engine payloads that cannot cross the protocol: {unserialisable}"
        )

    def test_every_real_event_round_trips_unchanged(self, played_events):
        """to_dict/from_dict must be lossless for real payloads, not just authored ones."""
        for index, event in enumerate(played_events):
            original = GameEvent(type=event.type, data=event.data, sequence=index)
            restored = GameEvent.from_dict(json.loads(json.dumps(original.to_dict())))
            assert restored == original, f"event {index} ({event.type.name}) did not round-trip"

    def test_a_whole_run_fits_in_one_action_result(self, played_events):
        """A client must be able to receive a turn's worth of events as one value."""
        result = ActionResult(
            ok=True,
            events=tuple(
                GameEvent(type=e.type, data=e.data, sequence=i)
                for i, e in enumerate(played_events)
            ),
        )
        restored = ActionResult.from_dict(json.loads(result.to_json()))

        assert restored == result
        assert len(restored.events) == len(played_events)
        assert [e.sequence for e in restored.events] == list(range(len(played_events)))

    def test_sequence_numbers_survive_serialisation_in_order(self, played_events):
        """Ordering must not depend on list order surviving the wire."""
        events = tuple(
            GameEvent(type=e.type, data=e.data, sequence=i) for i, e in enumerate(played_events)
        )
        shuffled = ActionResult(ok=True, events=tuple(reversed(events)))
        restored = ActionResult.from_dict(json.loads(shuffled.to_json()))
        assert [e.sequence for e in restored.events] == list(
            range(len(played_events) - 1, -1, -1)
        )
