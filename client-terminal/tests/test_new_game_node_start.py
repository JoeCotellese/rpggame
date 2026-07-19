# ABOUTME: Integration test for starting a campaign whose starting_room is a settlement node.
# ABOUTME: Guards the Unquiet Dead new-game path where Arden is now a node surface, not a grid room.

import json

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.core.room_registry import RoomRegistry
from dnd_engine.rules.loader import DataLoader
from terminal_client.ui.main_menu_v2 import MainMenuV2

CAMPAIGN_ID = "the_unquiet_dead"
STARTING_NODE = "arden.town_square"
STARTING_DUNGEON = "town_of_arden"


@pytest.fixture
def party():
    abilities = Abilities(
        strength=12, dexterity=14, constitution=14, intelligence=10, wisdom=12, charisma=10
    )
    hero = Character(
        name="Test Hero",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=12,
        ac=16,
    )
    return Party([hero])


@pytest.fixture
def data_loader():
    return DataLoader()


@pytest.fixture
def content_path(data_loader):
    return data_loader.data_path / "content"


@pytest.fixture
def campaign_starting_room(content_path):
    campaign_file = content_path / "campaigns" / CAMPAIGN_ID / "campaign.json"
    return json.loads(campaign_file.read_text())["starting_room"]


def test_campaign_starts_at_a_node(campaign_starting_room):
    # The Unquiet Dead now opens on the Town of Arden node surface.
    assert campaign_starting_room == STARTING_NODE


def test_room_only_resolution_misses_the_node(content_path):
    # The trap the fallback exists to cover: a node id has no grid-room
    # prefix entry, so the room lookup alone returns None.
    registry = RoomRegistry(campaign_id=CAMPAIGN_ID, content_path=content_path)
    assert registry.get_dungeon_for_room(STARTING_NODE) is None
    assert registry.get_dungeon_for_node(STARTING_NODE) == STARTING_DUNGEON


def test_resolve_starting_dungeon_finds_the_node_settlement(campaign_starting_room):
    menu = MainMenuV2()
    resolved = menu._resolve_starting_dungeon(CAMPAIGN_ID, campaign_starting_room)
    assert resolved == STARTING_DUNGEON


def test_new_game_lands_on_arden_node_surface(campaign_starting_room, data_loader, party):
    # Reproduces main_menu_v2._create_new_game's construction: resolve the
    # dungeon, build the GameState, and never override current_room_id for a
    # node surface. This is the path that raised
    # "Could not find dungeon for room: arden.town_square".
    menu = MainMenuV2()
    starting_dungeon = menu._resolve_starting_dungeon(CAMPAIGN_ID, campaign_starting_room)
    assert starting_dungeon is not None, "starting dungeon must resolve"

    game_state = GameState(
        party=party,
        dungeon_name=starting_dungeon,
        campaign_id=CAMPAIGN_ID,
        data_loader=data_loader,
    )
    if not game_state.is_node_surface():
        game_state.current_room_id = campaign_starting_room

    assert game_state.is_node_surface()
    assert game_state.current_node_id == STARTING_NODE
    assert game_state.current_room_id is None
