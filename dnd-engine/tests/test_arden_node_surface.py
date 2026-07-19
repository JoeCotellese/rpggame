# ABOUTME: Validates the Town of Arden as a node-surface settlement in The Unquiet Dead.
# ABOUTME: Covers schema load, NPC placement onto nodes, the Town Gate transition, and both reverse seams.

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.rules.node_schema import validate_location_surface
from dnd_engine.utils.events import EventBus

EXPECTED_NODES = {
    "arden.town_square",
    "arden.crooked_tankard",
    "arden.gareths_goods",
    "arden.chapel_of_the_light",
    "arden.davos_manor",
    "arden.warrens_alley",
    "arden.town_road",
    "arden.watch_house",
}


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
def arden():
    return DataLoader().load_dungeon("town_of_arden", campaign_id="the_unquiet_dead")


class TestArdenSchema:
    def test_loads_as_node_surface(self, arden):
        assert arden["surface"] == "node"
        assert arden["start_node"] == "arden.town_square"

    def test_passes_node_schema_validation(self, arden):
        validate_location_surface(arden, source="town_of_arden")  # must not raise

    def test_has_expected_nodes(self, arden):
        assert set(arden["nodes"]) == EXPECTED_NODES

    def test_no_grid_rooms_remain(self, arden):
        assert "rooms" not in arden

    def test_chapel_carries_the_crypt_quest_hook(self, arden):
        # Father Aldric (chapel) is the giver of investigate_crypt.
        assert arden["nodes"]["arden.chapel_of_the_light"]["quest_hook"] == "investigate_crypt"


class TestArdenStartAndNpcPlacement:
    def test_game_starts_on_node_surface(self, party):
        gs = GameState(
            party=party,
            dungeon_name="town_of_arden",
            campaign_id="the_unquiet_dead",
            event_bus=EventBus(),
            data_loader=DataLoader(),
        )
        assert gs.is_node_surface()
        assert gs.current_node_id == "arden.town_square"

    def test_static_npcs_placed_on_their_nodes(self, party):
        gs = GameState(
            party=party,
            dungeon_name="town_of_arden",
            campaign_id="the_unquiet_dead",
            event_bus=EventBus(),
            data_loader=DataLoader(),
        )
        nm = gs.npc_manager

        def names_at(node_id):
            return {n.name for n in nm.get_npcs_in_room(node_id)}

        assert "Marta" in names_at("arden.crooked_tankard")
        assert "Gareth" in names_at("arden.gareths_goods")
        assert "Lord Davos" in names_at("arden.davos_manor")
        assert "Father Aldric" in names_at("arden.chapel_of_the_light")

    def test_roderick_has_a_home_on_a_real_node(self, party):
        """Roderick was previously placed at a phantom room; he must now resolve to a real Arden node."""
        gs = GameState(
            party=party,
            dungeon_name="town_of_arden",
            campaign_id="the_unquiet_dead",
            event_bus=EventBus(),
            data_loader=DataLoader(),
        )
        nm = gs.npc_manager
        located = {
            node_id
            for node_id in EXPECTED_NODES
            if any(n.name == "Captain Roderick" for n in nm.get_npcs_in_room(node_id))
        }
        assert located, "Captain Roderick is not placed on any Arden node"
        assert located <= EXPECTED_NODES


class TestArdenSeams:
    def _hero(self, party):
        return party.get_living_members()[0]

    def test_town_gate_transitions_to_crypt(self, party):
        gs = GameState(
            party=party,
            dungeon_name="town_of_arden",
            campaign_id="the_unquiet_dead",
            event_bus=EventBus(),
            data_loader=DataLoader(),
        )
        gs.enter_node("arden.town_road")
        result = gs.node_actions.transition(self._hero(party))
        assert result["success"] is True
        assert gs.dungeon_name == "crypt"
        assert gs.current_room_id == "crypt.graveyard_entrance"

    def test_crypt_north_reenters_arden_node(self, party):
        gs = GameState(
            party=party,
            dungeon_name="crypt",
            campaign_id="the_unquiet_dead",
            event_bus=EventBus(),
            data_loader=DataLoader(),
        )
        assert gs.move("north", check_for_enemies=False) is True
        assert gs.is_node_surface()
        assert gs.current_node_id == "arden.town_road"
        assert gs.dungeon_name == "town_of_arden"

    def test_cult_hideout_up_reenters_arden_node(self, party):
        gs = GameState(
            party=party,
            dungeon_name="cult_hideout",
            campaign_id="the_unquiet_dead",
            event_bus=EventBus(),
            data_loader=DataLoader(),
        )
        assert gs.move("up", check_for_enemies=False) is True
        assert gs.is_node_surface()
        assert gs.current_node_id == "arden.warrens_alley"
        assert gs.dungeon_name == "town_of_arden"
