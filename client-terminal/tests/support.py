# ABOUTME: Shared builders for node-surface tests and the pexpect e2e driver.
# ABOUTME: One canonical test party and lab GameState used across suites.

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus


def make_test_party() -> Party:
    """One level-1 fighter, the standard party for node-surface testing."""
    character = Character(
        name="Test Hero",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=Abilities(
            strength=14,
            dexterity=12,
            constitution=13,
            intelligence=10,
            wisdom=11,
            charisma=8,
        ),
        max_hp=12,
        ac=16,
    )
    return Party([character])


def make_lab_game_state(dungeon_name: str = "lab_settlement") -> GameState:
    """A GameState on the given lab fixture with the standard test party."""
    return GameState(
        party=make_test_party(),
        dungeon_name=dungeon_name,
        event_bus=EventBus(),
        data_loader=DataLoader(),
    )
