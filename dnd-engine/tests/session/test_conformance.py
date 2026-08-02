# ABOUTME: Asserts the session facade never reports something the engine did not do.
# ABOUTME: Same-run comparison — drives one GameState and checks reports against reality.

"""Conformance between what the facade reports and what the engine contains.

The facade now sits between every client and the engine. If it claims "Skeleton
takes 10 damage" while the skeleton lost 7, every client renders that lie
identically and confidently, and nothing else in the suite would notice.

Deliberately a **same-run** comparison. The obvious design — run a scenario
twice, once each way, and diff — cannot work here: enemy AI targeting calls the
global `random` module directly and at least one further source of variance
survives beyond that, so two runs of "the same" scenario are not the same
scenario. Such a test would be flaky by construction and would eventually be
deleted rather than trusted. Instead this drives one `GameState` and checks that
the facade's reports agree with that same object's contents.

Each invariant is a small named function, so a failure names the property that
broke rather than pointing at a line in a long test.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.entity_ids import pc_entity_id
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.session import ActionResult, AttackIntent, Session, WaitIntent
from dnd_engine.utils.events import EventBus, EventType

MAX_ACTIONS = 60


def _build_game() -> GameState:
    """A real crypt fight — the encounter at the graveyard entrance."""
    party = Party(
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
    game = GameState(
        party=party,
        dungeon_name="crypt",
        campaign_id="the_unquiet_dead",
        event_bus=EventBus(),
        data_loader=DataLoader(),
        dice_roller=DiceRoller(seed=20260802),
    )
    game.start()
    return game


def _hp_by_creature(game: GameState) -> dict[int, int]:
    """Current HP for every combatant, keyed by identity.

    Keyed by ``id()`` rather than name: two skeletons share a name, and summing
    them together would make the damage reconciliation report a phantom
    discrepancy.
    """
    creatures = list(game.party.characters) + list(game.active_enemies or [])
    return {id(c): c.current_hp for c in creatures}


def _creatures_by_display_name(session: Session, game: GameState) -> dict[str, Any]:
    """Map the names events use back to the creatures they refer to.

    Events carry the disambiguated display name ("Skeleton 2"); engine creatures
    carry the raw name. Party members appear under their plain name.
    """
    mapping: dict[str, Any] = {}
    for character in game.party.characters:
        mapping[character.name] = character
    for enemy in game.active_enemies or []:
        mapping[session._enemy_display_name(enemy)] = enemy
    return mapping


# ----------------------------------------------------------------------
# Invariants. Each takes the same arguments so the driver can apply them all.
# ----------------------------------------------------------------------


def check_hp_matches(session: Session, game: GameState, result, before, after) -> None:
    """AC-1: every HP the snapshot reports equals the engine's own value."""
    snapshot = session.snapshot()
    by_name = {c.name: c for c in game.party.characters}
    for member in snapshot["party"]:
        engine_character = by_name[member["name"]]
        assert member["hp"] == engine_character.current_hp, (
            f"snapshot reports {member['name']} at {member['hp']} HP, "
            f"engine has {engine_character.current_hp}"
        )

    engine_enemies = {
        session._enemy_display_name(e): e for e in (game.active_enemies or [])
    }
    for enemy in snapshot["enemies"]:
        engine_enemy = engine_enemies.get(enemy["display_name"])
        if engine_enemy is None:
            continue
        assert enemy["hp"] == engine_enemy.current_hp, (
            f"snapshot reports {enemy['display_name']} at {enemy['hp']} HP, "
            f"engine has {engine_enemy.current_hp}"
        )


def check_damage_reconciles(
    session: Session, game: GameState, result: ActionResult, before, after
) -> None:
    """AC-2: reported damage matches the HP actually lost.

    Two legitimate wrinkles, handled rather than papered over:

    - **Overkill.** A killing blow may report more damage than the target had
      left, so a creature that died is checked with ``>=`` rather than ``==``.
    - **Healing.** A negative delta means HP went up; damage reconciliation does
      not apply, so those are skipped.
    """
    lookup = _creatures_by_display_name(session, game)
    reported: dict[int, int] = defaultdict(int)

    for event in result.events:
        if event.type is not EventType.DAMAGE_DEALT:
            continue
        target_name = event.data.get("target")
        amount = event.data.get("amount") or 0
        creature = lookup.get(target_name)
        if creature is None:
            continue
        reported[id(creature)] += amount

    for creature_id, reported_damage in reported.items():
        if creature_id not in before or creature_id not in after:
            continue
        actual = before[creature_id] - after[creature_id]
        if actual < 0:
            continue  # healing happened this action; not a damage question

        creature = next(
            (
                c
                for c in list(game.party.characters) + list(game.active_enemies or [])
                if id(c) == creature_id
            ),
            None,
        )
        died = creature is not None and not creature.is_alive

        if died:
            assert reported_damage >= actual, (
                f"reported {reported_damage} damage to {getattr(creature, 'name', '?')} "
                f"but only {actual} HP was lost before it fell"
            )
        else:
            assert reported_damage == actual, (
                f"reported {reported_damage} damage to {getattr(creature, 'name', '?')} "
                f"but {actual} HP was actually lost"
            )


def check_turn_matches(session: Session, game: GameState, result, before, after) -> None:
    """AC-3: `awaiting_actor_id` agrees with the engine's initiative tracker."""
    awaiting = session.awaiting_actor_id
    if awaiting is None:
        return

    current = game.initiative_tracker.get_current_combatant()
    assert current is not None, "facade awaits an actor while the engine has no current combatant"
    assert awaiting == pc_entity_id(current.creature.name), (
        f"facade awaits {awaiting}, engine's current combatant is "
        f"{current.creature.name}"
    )


def check_flags_match(session: Session, game: GameState, result, before, after) -> None:
    """AC-4: combat and game-over flags equal the engine's."""
    assert session.in_combat == bool(game.in_combat), (
        f"facade in_combat={session.in_combat}, engine={game.in_combat}"
    )
    assert session.is_over == bool(game.is_game_over()), (
        f"facade is_over={session.is_over}, engine={game.is_game_over()}"
    )


def check_deaths_are_real(
    session: Session, game: GameState, result: ActionResult, before, after
) -> None:
    """AC-5: nothing is reported dead that is still standing.

    This class of bug has already occurred twice — death saves reported twice in
    P1-02, and a death re-announced for an already-dead creature in P1-03 — so
    it gets a standing guard.
    """
    lookup = _creatures_by_display_name(session, game)
    for event in result.events:
        if event.type is not EventType.CHARACTER_DEATH:
            continue
        name = event.data.get("name") or event.data.get("target")
        creature = lookup.get(name)
        if creature is None:
            continue
        assert not creature.is_alive, (
            f"a death was reported for {name}, but it is still alive with "
            f"{creature.current_hp} HP"
        )


ALL_CHECKS = (
    check_hp_matches,
    check_damage_reconciles,
    check_turn_matches,
    check_flags_match,
    check_deaths_are_real,
)


def _drive_and_check(session: Session, game: GameState, checks=ALL_CHECKS) -> int:
    """Play a fight through the facade, asserting every invariant after each action."""
    actions = 0
    session.advance()

    for _ in range(MAX_ACTIONS):
        if session.is_over or not session.in_combat:
            break

        before = _hp_by_creature(game)
        actor = session.awaiting_actor_id

        if actor is None:
            result = session.advance()
        else:
            living = [e for e in session.snapshot()["enemies"] if e["is_alive"]]
            result = session.perform(
                AttackIntent(actor_id=actor, target_ref=living[0]["display_name"])
                if living
                else WaitIntent(actor_id=actor)
            )

        assert result.ok, f"facade rejected a legal action: {result.error}"
        actions += 1
        after = _hp_by_creature(game)

        for check in checks:
            check(session, game, result, before, after)

    return actions


@pytest.fixture
def game() -> GameState:
    return _build_game()


class TestFacadeReportsMatchEngineReality:
    """AC-1 through AC-5, all asserted after every action of a real fight."""

    def test_a_whole_fight_stays_conformant(self, game):
        session = Session(game)
        actions = _drive_and_check(session, game)
        assert actions > 0, "the fight produced no actions — nothing was verified"

    def test_the_driver_actually_exercises_damage(self, game):
        """Guard against the suite passing because nothing ever happened."""
        session = Session(game)
        session.advance()
        seen_damage = False
        for _ in range(MAX_ACTIONS):
            if session.is_over or not session.in_combat:
                break
            actor = session.awaiting_actor_id
            if actor is None:
                result = session.advance()
            else:
                living = [e for e in session.snapshot()["enemies"] if e["is_alive"]]
                result = session.perform(
                    AttackIntent(actor_id=actor, target_ref=living[0]["display_name"])
                    if living
                    else WaitIntent(actor_id=actor)
                )
            if any(e.type is EventType.DAMAGE_DEALT for e in result.events):
                seen_damage = True
                break
        assert seen_damage, "no damage occurred, so the reconciliation proved nothing"


class TestLegacyPathStillWorksAfterTheFacade:
    """AC-6: the strangler's real guarantee.

    Migration is incremental, so both paths will drive the same `GameState` for a
    while. If the facade leaves state the legacy path cannot continue from,
    incremental migration is impossible — and nobody finds out until they try.
    """

    def test_legacy_calls_continue_a_facade_driven_fight(self, game):
        session = Session(game)
        session.advance()

        # A few turns through the facade.
        for _ in range(3):
            if not session.in_combat or session.is_over:
                break
            actor = session.awaiting_actor_id
            if actor is None:
                session.advance()
                continue
            session.perform(WaitIntent(actor_id=actor))

        if not game.in_combat:
            pytest.skip("combat ended before the handover could be tested")

        # Now drive the old way, exactly as cli.py does.
        for _ in range(MAX_ACTIONS):
            if not game.in_combat or game.is_game_over():
                break
            current = game.initiative_tracker.get_current_combatant()
            if current is None:
                break
            if current.creature in game.party.characters:
                living = [e for e in game.active_enemies if e.is_alive]
                if living:
                    game.execute_player_attack(current.creature, living[0])
                game.initiative_tracker.next_turn()
            else:
                game.process_enemy_turn()
            game._check_combat_end()

        assert not game.in_combat or game.is_game_over(), (
            "the legacy path could not drive a facade-touched GameState to a "
            "terminal state — incremental migration would be impossible"
        )

    def test_engine_state_is_coherent_after_facade_use(self, game):
        """Initiative, party, and combat flags must all still make sense."""
        session = Session(game)
        session.advance()
        for _ in range(3):
            if not session.in_combat or session.is_over:
                break
            actor = session.awaiting_actor_id
            if actor is None:
                session.advance()
                continue
            session.perform(WaitIntent(actor_id=actor))

        tracker = game.initiative_tracker
        assert tracker is not None
        combatants = tracker.get_all_combatants()
        assert combatants, "facade use emptied the initiative order"
        if game.in_combat:
            assert tracker.get_current_combatant() is not None, (
                "in combat but no current combatant after facade use"
            )
        for character in game.party.characters:
            assert character.current_hp <= character.max_hp, (
                f"{character.name} has more HP than its maximum after facade use"
            )
