# ABOUTME: Unit tests for RoomDisplayContext and related game state methods
# ABOUTME: Tests room display context generation, monster info, lighting, and item visibility

from unittest.mock import MagicMock

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import (
    GameState,
    PartyMemberLighting,
    RoomDisplayContext,
)
from dnd_engine.core.party import Party
from dnd_engine.systems.time_manager import ActiveEffect, EffectType


def create_test_character(name: str, char_class: str = "fighter", level: int = 1) -> Character:
    """Helper to create a test character with minimal setup."""
    char_class_enum = CharacterClass.FIGHTER if char_class == "fighter" else CharacterClass.WIZARD
    return Character(
        name=name,
        character_class=char_class_enum,
        level=level,
        abilities=Abilities(15, 14, 13, 10, 12, 8),
        max_hp=10,
        ac=15,
        race="human",
    )


class TestRoomDisplayContext:
    """Tests for the RoomDisplayContext dataclass and get_room_display_context()."""

    @pytest.fixture
    def basic_game_state(self):
        """Create a basic game state for testing."""
        char = create_test_character("Frodo", "fighter", 1)
        party = Party([char])
        game_state = GameState(party, "test_dungeon")
        return game_state

    @pytest.fixture
    def game_state_with_party(self):
        """Create game state with multiple party members."""
        char1 = create_test_character("Frodo", "fighter", 1)
        char2 = create_test_character("Gandalf", "wizard", 1)
        # Give Gandalf darkvision
        char2.darkvision_range = 60
        party = Party([char1, char2])
        game_state = GameState(party, "test_dungeon")
        return game_state

    def test_get_room_display_context_basic(self, basic_game_state):
        """Test basic room display context generation."""
        context = basic_game_state.get_room_display_context()

        assert isinstance(context, RoomDisplayContext)
        assert context.room_name is not None
        assert context.description is not None
        assert isinstance(context.exits, dict)
        assert isinstance(context.monster_names, list)
        assert isinstance(context.party_lighting, list)
        assert context.party_size == 1

    def test_room_display_context_has_correct_room_info(self, basic_game_state):
        """Test that context contains correct room information."""
        context = basic_game_state.get_room_display_context()

        # Should have the start room info
        room = basic_game_state.get_current_room()
        assert context.room_name == room.get("name", "Unknown Room")
        assert context.room_id is not None

    def test_party_lighting_calculation(self, game_state_with_party):
        """Test that party lighting is calculated for each member."""
        context = game_state_with_party.get_room_display_context()

        assert len(context.party_lighting) == 2

        # Find each character's lighting info
        frodo_lighting = next(pl for pl in context.party_lighting if pl.character_name == "Frodo")
        gandalf_lighting = next(
            pl for pl in context.party_lighting if pl.character_name == "Gandalf"
        )

        assert isinstance(frodo_lighting, PartyMemberLighting)
        assert frodo_lighting.has_darkvision is False
        assert gandalf_lighting.has_darkvision is True

    def test_combat_starting_detection_no_enemies(self, basic_game_state):
        """Test that combat_starting is False when no enemies."""
        context = basic_game_state.get_room_display_context()

        assert context.combat_starting is False
        assert context.monster_names == []

    def test_combat_starting_detection_with_enemies(self, basic_game_state):
        """Test that combat_starting is True when enemies present."""
        # Add enemies to current room
        room = basic_game_state.get_current_room()
        room["enemies"] = ["goblin"]

        context = basic_game_state.get_room_display_context()

        assert context.combat_starting is True

    def test_combat_starting_false_when_already_in_combat(self, basic_game_state):
        """Test that combat_starting is False when already in combat."""
        room = basic_game_state.get_current_room()
        room["enemies"] = ["goblin"]
        basic_game_state.in_combat = True

        context = basic_game_state.get_room_display_context()

        assert context.combat_starting is False

    def test_visible_items_gold(self, basic_game_state):
        """Test visible gold items are included."""
        room = basic_game_state.get_current_room()
        room["items"] = [{"type": "gold", "amount": 50, "visible": True}]

        context = basic_game_state.get_room_display_context()

        assert len(context.visible_items) == 1
        item = context.visible_items[0]
        assert item.item_type == "gold"
        assert item.amount == 50

    def test_visible_items_currency(self, basic_game_state):
        """Test visible currency items are included."""
        room = basic_game_state.get_current_room()
        room["items"] = [
            {"type": "currency", "gold": 10, "silver": 25, "copper": 50, "visible": True}
        ]

        context = basic_game_state.get_room_display_context()

        assert len(context.visible_items) == 1
        item = context.visible_items[0]
        assert item.item_type == "currency"
        assert item.gold == 10
        assert item.silver == 25
        assert item.copper == 50

    def test_visible_items_regular_item(self, basic_game_state):
        """Test visible regular items are included."""
        room = basic_game_state.get_current_room()
        room["items"] = [{"type": "item", "id": "healing_potion", "visible": True}]

        context = basic_game_state.get_room_display_context()

        assert len(context.visible_items) == 1
        item = context.visible_items[0]
        assert item.item_type == "item"
        assert item.item_id == "healing_potion"
        assert item.item_name == "Healing Potion"

    def test_hidden_items_not_included(self, basic_game_state):
        """Test that hidden items are not included."""
        room = basic_game_state.get_current_room()
        room["items"] = [
            {"type": "gold", "amount": 50, "visible": True},
            {"type": "gold", "amount": 100, "visible": False},
        ]

        context = basic_game_state.get_room_display_context()

        assert len(context.visible_items) == 1
        assert context.visible_items[0].amount == 50

    def test_room_searched_status(self, basic_game_state):
        """Test that room searched status is included."""
        room = basic_game_state.get_current_room()
        room["searched"] = False

        context = basic_game_state.get_room_display_context()
        assert context.room_searched is False

        room["searched"] = True
        context = basic_game_state.get_room_display_context()
        assert context.room_searched is True

    def test_to_llm_dict_format(self, basic_game_state):
        """Test that to_llm_dict() returns proper format for LLM."""
        context = basic_game_state.get_room_display_context()
        llm_dict = context.to_llm_dict()

        # Check required fields for LLM
        assert "id" in llm_dict
        assert "name" in llm_dict
        assert "description" in llm_dict
        assert "monsters" in llm_dict
        assert "combat_starting" in llm_dict
        assert "monsters_data" in llm_dict
        assert "party_size" in llm_dict
        assert "base_lighting" in llm_dict
        assert "party_lighting" in llm_dict
        assert "light_casters" in llm_dict
        assert "previous_room_id" in llm_dict

    def test_to_llm_dict_party_lighting_format(self, game_state_with_party):
        """Test that party lighting is formatted correctly for LLM."""
        context = game_state_with_party.get_room_display_context()
        llm_dict = context.to_llm_dict()

        party_lighting = llm_dict["party_lighting"]
        assert len(party_lighting) == 2

        # Check each entry has required keys
        for entry in party_lighting:
            assert "character" in entry
            assert "lighting" in entry
            assert "has_darkvision" in entry


class TestLightCasters:
    """Tests for light caster tracking."""

    @pytest.fixture
    def game_state_with_light(self):
        """Create game state with Light spell active."""
        char = create_test_character("Gandalf", "wizard", 1)
        party = Party([char])
        game_state = GameState(party, "test_dungeon")

        # Add Light spell effect
        light_effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Light",
            duration_type="minutes",
            duration_value=60,
            remaining_value=60,
            target_name="Gandalf",
            caster_name="Gandalf",
        )
        game_state.time_manager.active_effects.append(light_effect)

        return game_state

    def test_light_casters_detected(self, game_state_with_light):
        """Test that Light spell casters are detected."""
        context = game_state_with_light.get_room_display_context()

        assert "Gandalf" in context.light_casters

    def test_light_casters_empty_without_spell(self):
        """Test that light_casters is empty without Light spell."""
        char = create_test_character("Frodo", "fighter", 1)
        party = Party([char])
        game_state = GameState(party, "test_dungeon")

        context = game_state.get_room_display_context()

        assert context.light_casters == []

    def test_multiple_light_casters(self):
        """Test multiple Light spell casters."""
        char1 = create_test_character("Gandalf", "wizard", 1)
        char2 = create_test_character("Radagast", "wizard", 1)
        party = Party([char1, char2])
        game_state = GameState(party, "test_dungeon")

        # Add Light spells from both
        game_state.time_manager.active_effects.append(
            ActiveEffect(
                effect_type=EffectType.SPELL,
                source="Light",
                duration_type="minutes",
                duration_value=60,
                remaining_value=60,
                target_name="Gandalf",
                caster_name="Gandalf",
            )
        )
        game_state.time_manager.active_effects.append(
            ActiveEffect(
                effect_type=EffectType.SPELL,
                source="Light",
                duration_type="minutes",
                duration_value=60,
                remaining_value=60,
                target_name="Radagast",
                caster_name="Radagast",
            )
        )

        context = game_state.get_room_display_context()

        assert len(context.light_casters) == 2
        assert "Gandalf" in context.light_casters
        assert "Radagast" in context.light_casters

    def test_duplicate_light_caster_not_repeated(self):
        """Test that same caster with multiple Light spells isn't repeated."""
        char = create_test_character("Gandalf", "wizard", 1)
        party = Party([char])
        game_state = GameState(party, "test_dungeon")

        # Add two Light spells from same caster
        game_state.time_manager.active_effects.append(
            ActiveEffect(
                effect_type=EffectType.SPELL,
                source="Light",
                duration_type="minutes",
                duration_value=60,
                remaining_value=60,
                target_name="Gandalf",
                caster_name="Gandalf",
            )
        )
        game_state.time_manager.active_effects.append(
            ActiveEffect(
                effect_type=EffectType.SPELL,
                source="Light",
                duration_type="minutes",
                duration_value=60,
                remaining_value=60,
                target_name="Gandalf",
                caster_name="Gandalf",
            )
        )

        context = game_state.get_room_display_context()

        assert context.light_casters == ["Gandalf"]


class TestMonsterInfo:
    """Tests for monster information in room context."""

    def test_monster_names_from_data_loader(self):
        """Test that monster names are loaded from data."""
        char = create_test_character("Frodo", "fighter", 1)
        party = Party([char])
        game_state = GameState(party, "test_dungeon")

        # Add enemies to room
        room = game_state.get_current_room()
        room["enemies"] = ["goblin", "skeleton"]

        context = game_state.get_room_display_context()

        # Should have loaded monster names (actual names depend on data files)
        assert isinstance(context.monster_names, list)
        assert isinstance(context.monsters_data, dict)

    def test_empty_monster_info_without_enemies(self):
        """Test that monster info is empty without enemies."""
        char = create_test_character("Frodo", "fighter", 1)
        party = Party([char])
        game_state = GameState(party, "test_dungeon")

        context = game_state.get_room_display_context()

        assert context.monster_names == []
        assert context.monsters_data == {}


class TestNPCDisplay:
    """Tests for NPC display in room context."""

    def test_npc_names_empty_without_npc_manager(self):
        """Test that NPC names are empty without NPC manager."""
        char = create_test_character("Frodo", "fighter", 1)
        party = Party([char])
        game_state = GameState(party, "test_dungeon")
        game_state.npc_manager = None

        context = game_state.get_room_display_context()

        assert context.npc_display_names == []

    def test_npc_names_with_mocked_manager(self):
        """Test NPC names are included when NPCs are present."""
        char = create_test_character("Frodo", "fighter", 1)
        party = Party([char])
        game_state = GameState(party, "test_dungeon")

        # Mock NPC manager
        mock_npc = MagicMock()
        mock_npc.display_name = "Bob the Merchant"
        mock_npc_manager = MagicMock()
        mock_npc_manager.get_npcs_in_room.return_value = [mock_npc]
        game_state.npc_manager = mock_npc_manager

        context = game_state.get_room_display_context()

        assert "Bob the Merchant" in context.npc_display_names


class TestPreviousRoomTracking:
    """Tests for previous room ID tracking."""

    def test_previous_room_id_initially_none(self):
        """Test that previous_room_id starts as None."""
        char = create_test_character("Frodo", "fighter", 1)
        party = Party([char])
        game_state = GameState(party, "test_dungeon")

        context = game_state.get_room_display_context()

        assert context.previous_room_id is None

    def test_previous_room_id_after_transition(self):
        """Test previous_room_id after room transition."""
        char = create_test_character("Frodo", "fighter", 1)
        party = Party([char])
        game_state = GameState(party, "test_dungeon")

        # Mark room as displayed (simulates viewing room)
        game_state.mark_room_displayed()
        start_room_id = game_state.current_room_id

        # Move to a new room if possible
        exits = game_state.get_available_exits()
        if exits:
            direction = list(exits.keys())[0]
            game_state.move(direction)

            context = game_state.get_room_display_context()
            assert context.previous_room_id == start_room_id
