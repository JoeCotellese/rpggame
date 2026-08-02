# ABOUTME: Integration test driving the real CLI run loop through a real laboratory fight.
# ABOUTME: Proves the migrated loop plays combat end to end without engine reach-through.

"""End-to-end verification for #697.

The unit tests stub the session; this one does not. A real `GameState` in the
poisoned laboratory, a real `Session`, and the real `CLI.run()` loop play an
actual fight against two goblins — which is also the encounter that proves
same-named enemies stay distinguishable.

Narrative enhancement is off, so nothing here reaches the network.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.session.reactions import DECLINE_OPTION_ID
from dnd_engine.utils.events import EventBus
from terminal_client.ui.cli import CLI

MAX_COMMANDS = 80


def _party(max_hp: int = 30, ac: int = 16) -> Party:
    """Two level-3 fighters. Lower the HP and AC to script a party wipe."""
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
                max_hp=max_hp,
                ac=ac,
            )
            for name in ("Thorin", "Garrick")
        ]
    )


def _cli_for(party: Party) -> CLI:
    """A CLI over a real laboratory game state, with narrative disabled."""
    game_state = GameState(
        party=party,
        dungeon_name="laboratory",
        campaign_id="poisoned_laboratory",
        event_bus=EventBus(),
        data_loader=DataLoader(),
        dice_roller=DiceRoller(seed=20260802),
    )
    return CLI(
        game_state=game_state,
        campaign_manager=Mock(),
        campaign_name="integration_test",
        auto_save_enabled=False,
    )


@pytest.fixture
def cli() -> CLI:
    return _cli_for(_party())


@pytest.fixture
def doomed_cli() -> CLI:
    """A party that cannot survive the goblins, for the wipe path."""
    return _cli_for(_party(max_hp=1, ac=1))


def _play(cli: CLI) -> str:
    """Walk to the goblins, fight until it ends, and return everything printed."""
    issued = {"n": 0}

    def next_command() -> str:
        issued["n"] += 1
        if issued["n"] > MAX_COMMANDS:
            cli.running = False
            return "quit"

        if cli.game_state.in_combat:
            living = [e for e in cli.game_state.active_enemies if e.is_alive]
            if living:
                return f"attack {cli._get_enemy_display_name(living[0])}"
            return "done"

        # Out of combat: entrance -> storage -> laboratory, where the goblins are.
        if not cli.game_state.active_enemies:
            return "north" if issued["n"] == 1 else "east"

        cli.running = False
        return "quit"

    cli.get_player_command = next_command  # type: ignore[method-assign]

    from io import StringIO

    from rich.console import Console

    transcript = StringIO()
    with (
        patch("terminal_client.ui.rich_ui.console", Console(file=transcript, width=200)),
        patch("terminal_client.ui.cli.console", Console(file=transcript, width=200)),
        patch(
            "terminal_client.ui.session_render.console",
            Console(file=transcript, width=200),
        ),
        # A goblin withdrawing may hand a party member an opportunity attack.
        # Declining keeps the fight moving without a real prompt.
        patch(
            "terminal_client.ui.cli.questionary.select",
            return_value=Mock(ask=Mock(return_value=DECLINE_OPTION_ID)),
        ),
    ):
        cli.run()

    return transcript.getvalue()


class TestAFullFightThroughTheMigratedLoop:
    """AC-1: a dungeon run is playable with the turn loop in the engine."""

    def test_combat_starts_reaches_an_end_and_the_loop_terminates(self, cli):
        _play(cli)

        assert not cli.game_state.in_combat or cli.game_state.is_game_over(), (
            "the fight never reached a terminal state"
        )

    def test_the_same_named_goblins_are_distinguishable(self, cli):
        """AC-5: numbering now comes from the facade, not from cli.py."""
        output = _play(cli)

        assert "Goblin 1" in output and "Goblin 2" in output, (
            "two identical goblins were not disambiguated — targeting is ambiguous"
        )

    def test_enemy_turns_are_reported_to_the_player(self, cli):
        """AC-3: enemy turns render from the session's events."""
        output = _play(cli)

        assert "'s turn..." in output, "the player never saw an enemy take its turn"

    def test_the_fight_produces_attack_mechanics(self, cli):
        output = _play(cli)

        assert "HIT" in output or "MISS" in output, "no attack mechanics were shown"


class TestEventsPrintInTheOrderTheyHappened:
    """Found in playtest: the defeat was announced before the blows that caused it.

    The CLI subscribes to the bus directly for combat end, and that handler
    prints the instant the engine emits — mid-resolution. Rendering the
    session's own events afterwards, in a batch, therefore put every enemy turn
    and death save *below* the "Defeat!" line they led up to.
    """

    def test_combat_end_is_announced_after_the_turns_that_ended_it(self, doomed_cli):
        output = _play(doomed_cli)

        assert "Defeat!" in output, "the doomed party did not get wiped"
        assert "'s turn..." in output, "no enemy turn was rendered"

        assert output.index("'s turn...") < output.index("Defeat!"), (
            "the defeat was announced before the enemy turns that caused it - "
            "session events are being rendered after the fact instead of as they happen"
        )
