# ABOUTME: Unit tests for Session turn-advancement branches and failure handling.
# ABOUTME: Uses light stubs to reach states real combat cannot produce on demand.

"""Unit verification for P1-02 (AC-4, AC-7, AC-8).

The integration suite plays real combat, but cannot summon a stabilized
character or an engine fault on demand. These tests drive those branches
directly with stubs standing in for the parts of `GameState` the facade touches.

Only the facade's own branch logic is under test here — the engine behaviour each
branch delegates to is the engine's to verify.
"""

from __future__ import annotations

from typing import Any

import pytest

from dnd_engine.core.entity_ids import pc_entity_id
from dnd_engine.session import ErrorKind, Session, WaitIntent
from dnd_engine.utils.events import EventBus


class StubCharacter:
    """A party member with directly settable turn state."""

    def __init__(
        self,
        name: str = "Thorin",
        *,
        is_alive: bool = True,
        is_dead: bool = False,
        is_unconscious: bool = False,
        stabilized: bool = False,
        can_act: bool = True,
    ) -> None:
        self.name = name
        self.is_alive = is_alive
        self.is_dead = is_dead
        self.is_unconscious = is_unconscious
        self.stabilized = stabilized
        self.current_hp = 10
        self.max_hp = 10
        self.death_save_successes = 0
        self.death_save_failures = 0
        self._can_act = can_act
        self.end_of_turn_calls = 0
        self.active_conditions: dict[str, Any] = {}

    def can_take_actions(self) -> bool:
        return self._can_act

    def process_end_of_turn_conditions(self, event_bus: Any) -> list[dict[str, Any]]:
        self.end_of_turn_calls += 1
        return [{"type": "condition_expired", "condition": "stunned"}]


class StubEntry:
    """One initiative slot."""

    def __init__(self, creature: Any) -> None:
        self.creature = creature
        self.display_name = getattr(creature, "name", "")


class StubTracker:
    """Initiative over a fixed ring, recording how often it advanced."""

    def __init__(self, creatures: list[Any]) -> None:
        self._creatures = creatures
        self.index = 0
        self.advance_count = 0
        self.numbering_calls = 0

    def assign_combat_numbers(self, player_creatures: list[Any]) -> None:
        """Real trackers disambiguate same-named enemies; record that we asked."""
        self.numbering_calls += 1

    def get_all_combatants(self) -> list[StubEntry]:
        return [StubEntry(c) for c in self._creatures]

    def get_current_combatant(self) -> StubEntry | None:
        if not self._creatures:
            return None
        return StubEntry(self._creatures[self.index % len(self._creatures)])

    def next_turn(self) -> None:
        self.advance_count += 1
        self.index += 1


class StubParty:
    def __init__(self, characters: list[Any]) -> None:
        self.characters = characters


class StubGameState:
    """The slice of `GameState` the facade actually calls."""

    def __init__(self, characters: list[Any], *, in_combat: bool = True) -> None:
        self.party = StubParty(characters)
        self.initiative_tracker = StubTracker(list(characters))
        self.in_combat = in_combat
        self.event_bus = EventBus()
        self.active_enemies: list[Any] = []
        self.condition_manager = None
        self.unconscious_turns = 0
        self.combat_end_checks = 0

    def is_game_over(self) -> bool:
        return False

    def _check_combat_end(self) -> None:
        self.combat_end_checks += 1

    def process_unconscious_turn(self) -> Any:
        self.unconscious_turns += 1
        self.initiative_tracker.next_turn()
        return object()

    def process_enemy_turn(self) -> None:
        return None


class TestAC4TurnStructureRulesLiveInTheFacade:
    """AC-4: skip-dead, death saves, stabilized, incapacitated — all facade-owned."""

    def test_dead_combatant_is_skipped(self):
        """Mirrors cli.py:6119 — a dead character never gets a turn."""
        actor = StubCharacter("Thorin")
        corpse = StubCharacter("Garrick", is_alive=False, is_dead=True)
        alive = StubCharacter("Nyx")
        game = StubGameState([actor, corpse, alive])
        session = Session(game)

        session.perform(WaitIntent(actor_id=pc_entity_id("Thorin")))

        assert session.awaiting_actor_id == pc_entity_id("Nyx"), (
            "turn advancement stopped on a dead character"
        )

    def test_unconscious_unstabilized_character_rolls_a_death_save(self):
        """Mirrors cli.py:6146 — dying characters roll rather than act."""
        actor = StubCharacter("Thorin")
        dying = StubCharacter("Garrick", is_alive=False, is_unconscious=True)
        game = StubGameState([actor, dying])
        session = Session(game)

        session.perform(WaitIntent(actor_id=pc_entity_id("Thorin")))

        assert game.unconscious_turns == 1, "no death save was rolled for a dying character"

    def test_stabilized_character_skips_without_rolling(self):
        """Mirrors cli.py:6140 — stabilized characters do not roll death saves."""
        actor = StubCharacter("Thorin")
        stable = StubCharacter(
            "Garrick", is_alive=False, is_unconscious=True, stabilized=True
        )
        game = StubGameState([actor, stable])
        session = Session(game)

        result = session.perform(WaitIntent(actor_id=pc_entity_id("Thorin")))

        assert game.unconscious_turns == 0, "rolled a death save for a stabilized character"
        assert any("stable" in (e.message or "") for e in result.events)

    def test_incapacitated_character_processes_end_of_turn_conditions(self):
        """Mirrors cli.py:6162 — an incapacitated character still ticks conditions."""
        actor = StubCharacter("Thorin")
        stunned = StubCharacter("Garrick", can_act=False)
        game = StubGameState([actor, stunned])
        session = Session(game)

        session.perform(WaitIntent(actor_id=pc_entity_id("Thorin")))

        assert stunned.end_of_turn_calls == 1, (
            "incapacitated character did not process end-of-turn conditions"
        )

    def test_advancement_cannot_loop_forever(self):
        """A ring of unactionable combatants must terminate, not hang a client."""
        everyone_dead = [
            StubCharacter(f"Corpse{i}", is_alive=False, is_dead=True) for i in range(3)
        ]
        actor = StubCharacter("Thorin")
        game = StubGameState([actor, *everyone_dead])
        session = Session(game)

        session.perform(WaitIntent(actor_id=pc_entity_id("Thorin")))

        assert game.initiative_tracker.advance_count < 500


class TestSkippedTurnsAreRenderable:
    """A skipped turn must say why in its payload, not just that it happened.

    `client-terminal` tells the player *which* conditions stopped a character
    ("Garrick is PARALYZED and cannot act!") and announces a death caused by an
    ongoing effect. Both facts are known while the turn is being skipped and
    unrecoverable afterwards — the conditions may be cleared by the very
    end-of-turn processing that follows. So they travel in the event.
    """

    def test_incapacitated_turn_names_the_conditions(self):
        actor = StubCharacter("Thorin")
        stunned = StubCharacter("Garrick", can_act=False)
        stunned.active_conditions = {"paralyzed": {}, "stunned": {}}
        session = Session(StubGameState([actor, stunned]))

        result = session.perform(WaitIntent(actor_id=pc_entity_id("Thorin")))

        skipped = [
            e
            for e in result.events
            if e.data.get("reason") == "incapacitated" and e.data.get("actor") == "Garrick"
        ]
        assert skipped, "no incapacitated turn-end event for the stunned character"
        assert skipped[0].data.get("conditions") == ["paralyzed", "stunned"], (
            "the event does not say which conditions stopped the character"
        )

    def test_a_turn_start_effect_that_kills_says_so(self):
        class KillingEffect:
            condition_id = "on_fire"
            message = "Thorin takes 4 fire damage!"
            damage = 4
            creature_died = True

        class StubConditionManager:
            def process_turn_start_effects(self, creature: Any) -> list[Any]:
                creature.is_alive = False
                return [KillingEffect()]

        actor = StubCharacter("Thorin")
        burning = StubCharacter("Garrick")
        game = StubGameState([actor, burning])
        game.condition_manager = StubConditionManager()
        session = Session(game)

        result = session.perform(WaitIntent(actor_id=pc_entity_id("Thorin")))

        effects = [e for e in result.events if e.data.get("condition") == "on_fire"]
        assert effects, "no event for the turn-start effect"
        assert effects[0].data.get("creature_died") is True, (
            "a fatal turn-start effect does not report the death"
        )
        assert effects[0].data.get("damage") == 4


class TestStreamingEventsToAListener:
    """A client that also watches the bus needs events as they happen.

    Found in a `client-terminal` playtest. The CLI subscribes to `COMBAT_END`
    directly, so that handler printed the moment the engine emitted — while the
    session's own events were rendered afterwards from the returned result. The
    transcript put "Defeat!" above the enemy turns and death saves that led to
    it. Streaming puts both on one timeline.
    """

    def test_the_listener_sees_every_event_the_result_carries(self):
        seen = []
        actor = StubCharacter("Thorin")
        stunned = StubCharacter("Garrick", can_act=False)
        session = Session(StubGameState([actor, stunned]), event_listener=seen.append)

        result = session.perform(WaitIntent(actor_id=pc_entity_id("Thorin")))

        assert [e.sequence for e in seen] == [e.sequence for e in result.events]

    def test_the_listener_is_called_before_the_call_returns(self):
        """Streaming is only worth having if it beats the return."""
        arrived_during: list[bool] = []
        actor = StubCharacter("Thorin")
        stunned = StubCharacter("Garrick", can_act=False)
        game = StubGameState([actor, stunned])

        original = game.initiative_tracker.next_turn
        streamed: list[object] = []

        def record_when_advancing() -> None:
            arrived_during.append(bool(streamed))
            original()

        game.initiative_tracker.next_turn = record_when_advancing  # type: ignore[method-assign]
        session = Session(game, event_listener=streamed.append)
        session.perform(WaitIntent(actor_id=pc_entity_id("Thorin")))

        assert any(arrived_during), (
            "no event reached the listener until resolution had finished"
        )

    def test_no_listener_leaves_behaviour_unchanged(self):
        actor = StubCharacter("Thorin")
        session = Session(StubGameState([actor]))
        assert session.perform(WaitIntent(actor_id=pc_entity_id("Thorin"))).ok


class TestAC8InternalFailuresAreContained:
    """AC-8: an engine exception never corrupts the session."""

    def test_engine_exception_becomes_an_internal_error(self):
        actor = StubCharacter("Thorin")
        game = StubGameState([actor])

        def explode() -> None:
            raise RuntimeError("engine exploded")

        game.initiative_tracker.next_turn = explode  # type: ignore[method-assign]
        session = Session(game)

        result = session.perform(WaitIntent(actor_id=pc_entity_id("Thorin")))

        assert not result.ok
        assert result.error_kind is ErrorKind.INTERNAL
        assert "RuntimeError" in result.error

    def test_session_remains_usable_after_an_internal_error(self):
        actor = StubCharacter("Thorin")
        game = StubGameState([actor])
        original = game.initiative_tracker.next_turn
        calls = {"n": 0}

        def explode_once() -> None:
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("transient")
            original()

        game.initiative_tracker.next_turn = explode_once  # type: ignore[method-assign]
        session = Session(game)

        first = session.perform(WaitIntent(actor_id=pc_entity_id("Thorin")))
        second = session.perform(WaitIntent(actor_id=pc_entity_id("Thorin")))

        assert not first.ok and first.error_kind is ErrorKind.INTERNAL
        assert second.ok, f"session unusable after an internal error: {second.error}"

    def test_bus_subscriptions_do_not_leak_after_a_failure(self):
        """A raised action must still unsubscribe, or events double up later."""
        actor = StubCharacter("Thorin")
        game = StubGameState([actor])

        def explode() -> None:
            raise RuntimeError("boom")

        game.initiative_tracker.next_turn = explode  # type: ignore[method-assign]
        session = Session(game)
        session.perform(WaitIntent(actor_id=pc_entity_id("Thorin")))

        from dnd_engine.utils.events import EventType

        assert game.event_bus.subscriber_count(EventType.TURN_END) == 0, (
            "bus subscription leaked after an exception"
        )


class TestAC7RuleRejections:
    """AC-7: rules refusals are typed RULE and cost nothing."""

    def test_out_of_turn_intent_is_rejected_as_a_rule(self):
        first = StubCharacter("Thorin")
        second = StubCharacter("Garrick")
        session = Session(StubGameState([first, second]))

        result = session.perform(WaitIntent(actor_id=pc_entity_id("Garrick")))

        assert not result.ok
        assert result.error_kind is ErrorKind.RULE

    def test_rejection_leaves_the_turn_with_the_original_actor(self):
        first = StubCharacter("Thorin")
        second = StubCharacter("Garrick")
        game = StubGameState([first, second])
        session = Session(game)

        session.perform(WaitIntent(actor_id=pc_entity_id("Garrick")))

        assert game.initiative_tracker.advance_count == 0
        assert session.awaiting_actor_id == pc_entity_id("Thorin")

    def test_unsupported_freeform_intent_is_rejected_cleanly(self):
        from dnd_engine.session import FreeformIntent

        session = Session(StubGameState([StubCharacter("Thorin")]))
        result = session.perform(
            FreeformIntent(actor_id=pc_entity_id("Thorin"), text="I shove the brazier")
        )

        assert not result.ok
        assert result.error_kind is ErrorKind.RULE
        assert "freeform" in result.error


class TestOutOfCombatBehaviour:
    """Exploration has no initiative to respect."""

    def test_any_actor_may_act_out_of_combat(self):
        game = StubGameState([StubCharacter("Thorin")], in_combat=False)
        session = Session(game)

        assert session.awaiting_actor_id is None
        result = session.perform(WaitIntent(actor_id=pc_entity_id("Thorin")))
        assert result.ok

    def test_no_turn_advancement_happens_out_of_combat(self):
        game = StubGameState([StubCharacter("Thorin")], in_combat=False)
        Session(game).perform(WaitIntent(actor_id=pc_entity_id("Thorin")))
        assert game.initiative_tracker.advance_count == 0


@pytest.mark.parametrize("direction", ["north", "south", "east", "west"])
def test_all_compass_directions_are_understood(direction):
    """A client must not have to guess which direction strings work."""
    from dnd_engine.session.session import _DIRECTION_DELTAS

    assert direction in _DIRECTION_DELTAS
