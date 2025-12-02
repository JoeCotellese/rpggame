# ABOUTME: Unit tests for _get_item_category method in GameState
# ABOUTME: Ensures all item types from items.json can be properly categorized

import pytest

from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities


@pytest.fixture
def game_state():
    """Create a minimal game state for testing item categories."""
    abilities = Abilities(10, 10, 10, 10, 10, 10)
    char = Character(
        name="Test",
        race="human",
        character_class=CharacterClass.FIGHTER,
        abilities=abilities,
        level=1,
        max_hp=10,
        ac=10,
    )
    party = Party([char])
    return GameState(party=party, dungeon_name="crypt", campaign_id="the_unquiet_dead")


class TestGetItemCategory:
    """Tests for GameState._get_item_category method."""

    def test_weapons_category(self, game_state):
        """Weapons should return 'weapons' category."""
        assert game_state._get_item_category("longsword") == "weapons"
        assert game_state._get_item_category("shortbow") == "weapons"

    def test_armor_category(self, game_state):
        """Armor should return 'armor' category."""
        assert game_state._get_item_category("chain_mail") == "armor"
        assert game_state._get_item_category("hide") == "armor"

    def test_consumables_category(self, game_state):
        """Consumables should return 'consumables' category."""
        assert game_state._get_item_category("potion_of_healing") == "consumables"

    def test_magical_items_category(self, game_state):
        """Magical items should return 'magical_items' category."""
        assert game_state._get_item_category("immovable_rod") == "magical_items"

    def test_tools_category(self, game_state):
        """Tools should return 'tools' category."""
        assert game_state._get_item_category("thieves_tools") == "tools"

    def test_equipment_category(self, game_state):
        """Equipment should return 'equipment' category."""
        assert game_state._get_item_category("backpack") == "equipment"

    def test_ammunition_maps_to_consumables(self, game_state):
        """Ammunition should map to 'consumables' category (consumed on use)."""
        assert game_state._get_item_category("arrows") == "consumables"
        assert game_state._get_item_category("bolts") == "consumables"

    def test_unknown_item_returns_none(self, game_state):
        """Unknown items should return None."""
        assert game_state._get_item_category("nonexistent_item_xyz") is None
