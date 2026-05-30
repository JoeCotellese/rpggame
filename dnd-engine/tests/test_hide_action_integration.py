# ABOUTME: Integration tests for GameState.attempt_hide (the Hide action, #443).
# ABOUTME: Exercises the env gate, the Stealth-vs-passive-Perception roll, and slot use.

"""Integration coverage for the player-initiated Hide action.

`GameState.attempt_hide` ties together the #496 environmental gate
(`can_attempt_hide`), the combat-turn action economy, and a Dexterity
(Stealth) check contested against the most perceptive enemy. These tests
drive the orchestration end-to-end against the shipped crypt campaign.
"""

from __future__ import annotations

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.game_state import GameState, HideAttemptResult
from dnd_engine.core.party import Party
from dnd_engine.systems.action_economy import ActionType
from dnd_engine.systems.initiative import InitiativeTracker


def _stealthy_rogue(*, dex: int = 16, expertise: bool = False) -> Character:
    char = Character(
        name="Sneak",
        character_class=CharacterClass.ROGUE,
        level=1,
        abilities=Abilities(10, dex, 10, 10, 10, 10),
        max_hp=8,
        ac=14,
        race="halfling",
        skill_proficiencies=["stealth"],
    )
    if expertise:
        char.expertise_skills = ["stealth"]
    return char


def _game_state_with_turn(char: Character) -> GameState:
    """Build a crypt-room GameState with ``char`` as the current combatant."""
    party = Party([char])
    gs = GameState(party, "crypt", campaign_id="the_unquiet_dead")
    gs.current_room_id = "crypt.hall_of_the_dead"
    gs.in_combat = True
    gs.initiative_tracker = InitiativeTracker(gs.dice_roller, gs.time_manager)
    gs.initiative_tracker.add_combatant(char)
    return gs


def _make_room_concealing(gs: GameState) -> None:
    room = gs.get_current_room()
    room["lighting"] = "bright"
    room["obscurement_sources"] = ["heavy_fog"]  # Heavily Obscured
    room["cover"] = "none"


def _make_room_open(gs: GameState) -> None:
    room = gs.get_current_room()
    room["lighting"] = "bright"
    room["obscurement_sources"] = []
    room["cover"] = "none"


class TestAttemptHide:
    def test_open_lit_room_blocks_hide_and_keeps_the_action(self):
        char = _stealthy_rogue()
        gs = _game_state_with_turn(char)
        _make_room_open(gs)

        result = gs.attempt_hide(char)

        assert isinstance(result, HideAttemptResult)
        assert result.attempted is False
        assert result.success is False
        assert char.has_condition("hidden") is False
        # Gate refusal happens before any slot is spent.
        assert gs.initiative_tracker.get_current_turn_state().action_available is True

    def test_successful_hide_sets_hidden_and_spends_the_action(self):
        # DEX 20 (+5) + Stealth expertise (prof 2 doubled = +4) → +9; with no
        # enemies the DC is the baseline 10, so even a natural 1 clears it.
        char = _stealthy_rogue(dex=20, expertise=True)
        gs = _game_state_with_turn(char)
        _make_room_concealing(gs)

        result = gs.attempt_hide(char)

        assert result.attempted is True
        assert result.success is True
        assert result.dc == 10
        assert result.action_consumed == ActionType.ACTION
        assert char.has_condition("hidden") is True
        assert gs.initiative_tracker.get_current_turn_state().action_available is False

    def test_failed_hide_stays_visible_but_still_spends_the_action(self):
        char = _stealthy_rogue()
        gs = _game_state_with_turn(char)
        _make_room_concealing(gs)
        # An impossibly perceptive watcher forces the Stealth check to fail.
        watcher = Creature(
            name="All-Seeing Eye", max_hp=1, ac=10, abilities=Abilities(10, 10, 10, 10, 10, 10)
        )
        watcher.passive_perception = 100
        gs.active_enemies = [watcher]

        result = gs.attempt_hide(char)

        assert result.attempted is True
        assert result.success is False
        assert result.dc == 100
        assert char.has_condition("hidden") is False
        assert gs.initiative_tracker.get_current_turn_state().action_available is False

    def test_hide_requires_an_active_turn(self):
        char = _stealthy_rogue()
        gs = _game_state_with_turn(char)
        _make_room_concealing(gs)
        gs.initiative_tracker = None  # no combat turn in progress

        result = gs.attempt_hide(char)

        assert result.attempted is False
        assert char.has_condition("hidden") is False
