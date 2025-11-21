# ABOUTME: Tests for GameState.cast_spell_exploration() method
# ABOUTME: Tests out-of-combat spellcasting game logic including healing and utility spells

import pytest
from dnd_engine.core.game_state import GameState
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.party import Party
from dnd_engine.core.dice import DiceRoller
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus, EventType


class TestCastSpellExploration:
    """Test GameState.cast_spell_exploration() method"""

    @pytest.fixture
    def event_bus(self):
        """Create event bus for testing"""
        return EventBus()

    @pytest.fixture
    def data_loader(self):
        """Create data loader"""
        return DataLoader()

    @pytest.fixture
    def dice_roller(self):
        """Create seeded dice roller for predictable results"""
        return DiceRoller(seed=42)

    @pytest.fixture
    def cleric_abilities(self):
        """Create abilities for a cleric"""
        return Abilities(
            strength=14,
            dexterity=10,
            constitution=14,
            intelligence=8,
            wisdom=16,  # +3 modifier
            charisma=12
        )

    @pytest.fixture
    def cleric_with_spells(self, cleric_abilities):
        """Create a cleric with healing and utility spells"""
        from dnd_engine.systems.resources import ResourcePool

        cleric = Character(
            name="Brother Marcus",
            character_class=CharacterClass.CLERIC,
            level=3,
            abilities=cleric_abilities,
            max_hp=20,
            ac=16,
            spellcasting_ability="wis",
            known_spells=["sacred_flame", "light", "cure_wounds", "detect_magic"],
            prepared_spells=["sacred_flame", "light", "cure_wounds", "detect_magic"]
        )
        # Set up spell slots using ResourcePools
        cleric.add_resource_pool(ResourcePool(
            name="spell_slots_level_1",
            current=4,
            maximum=4,
            recovery_type="long_rest"
        ))
        cleric.add_resource_pool(ResourcePool(
            name="spell_slots_level_2",
            current=2,
            maximum=2,
            recovery_type="long_rest"
        ))
        return cleric

    @pytest.fixture
    def injured_fighter(self):
        """Create an injured fighter for healing"""
        fighter = Character(
            name="Bruenor",
            character_class=CharacterClass.FIGHTER,
            level=3,
            abilities=Abilities(16, 14, 15, 10, 12, 8),
            max_hp=25,
            ac=18
        )
        fighter.current_hp = 10  # Injured
        return fighter

    @pytest.fixture
    def game_state_with_party(self, cleric_with_spells, injured_fighter, event_bus, data_loader, dice_roller):
        """Create game state with a party"""
        party = Party([cleric_with_spells, injured_fighter])
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller
        )
        return game_state

    def test_cast_healing_spell_success(self, game_state_with_party, event_bus):
        """Test successfully casting a healing spell"""
        # Track events
        events_received = []
        def event_handler(event):
            events_received.append(event)
        event_bus.subscribe(EventType.SPELL_CAST, event_handler)

        # Cast cure wounds on injured fighter
        result = game_state_with_party.cast_spell_exploration(
            caster_name="Brother Marcus",
            spell_id="cure_wounds",
            target_name="Bruenor"
        )

        # Verify success
        assert result["success"] is True
        assert "healing_amount" in result
        assert result["healing_amount"] > 0
        assert result["spell_name"] == "Cure Wounds"
        assert result["target"] == "Bruenor"

        # Verify event was emitted
        assert len(events_received) == 1
        event = events_received[0]
        assert event.type == EventType.SPELL_CAST
        assert event.data["caster"] == "Brother Marcus"
        assert event.data["spell"] == "Cure Wounds"
        assert event.data["target"] == "Bruenor"
        assert event.data["healing"] > 0

    def test_healing_spell_increases_hp(self, game_state_with_party):
        """Test that healing spell actually increases target HP"""
        fighter = game_state_with_party.party.get_character_by_name("Bruenor")
        initial_hp = fighter.current_hp

        result = game_state_with_party.cast_spell_exploration(
            caster_name="Brother Marcus",
            spell_id="cure_wounds",
            target_name="Bruenor"
        )

        assert result["success"] is True
        assert fighter.current_hp > initial_hp
        assert fighter.current_hp <= fighter.max_hp  # Can't exceed max

    def test_healing_spell_consumes_spell_slot(self, game_state_with_party):
        """Test that casting a healing spell consumes a spell slot"""
        cleric = game_state_with_party.party.get_character_by_name("Brother Marcus")
        initial_slots = cleric.get_available_spell_slots(1)

        result = game_state_with_party.cast_spell_exploration(
            caster_name="Brother Marcus",
            spell_id="cure_wounds",
            target_name="Bruenor"
        )

        assert result["success"] is True
        assert cleric.get_available_spell_slots(1) == initial_slots - 1

    def test_cantrip_doesnt_consume_spell_slot(self, game_state_with_party):
        """Test that casting a cantrip doesn't consume spell slots"""
        cleric = game_state_with_party.party.get_character_by_name("Brother Marcus")
        initial_slots_level1 = cleric.get_available_spell_slots(1)
        initial_slots_level2 = cleric.get_available_spell_slots(2)

        result = game_state_with_party.cast_spell_exploration(
            caster_name="Brother Marcus",
            spell_id="light"
        )

        assert result["success"] is True
        assert cleric.get_available_spell_slots(1) == initial_slots_level1  # Unchanged
        assert cleric.get_available_spell_slots(2) == initial_slots_level2  # Unchanged

    def test_utility_spell_returns_description(self, game_state_with_party):
        """Test that utility spells return flavor text"""
        result = game_state_with_party.cast_spell_exploration(
            caster_name="Brother Marcus",
            spell_id="light"
        )

        assert result["success"] is True
        assert "description" in result
        assert result["spell_name"] == "Light"
        assert len(result["description"]) > 0

    def test_healing_without_target_fails(self, game_state_with_party):
        """Test that healing spells require a target"""
        result = game_state_with_party.cast_spell_exploration(
            caster_name="Brother Marcus",
            spell_id="cure_wounds"
            # No target_name provided
        )

        assert result["success"] is False
        assert "error" in result
        assert "target" in result["error"].lower()

    def test_nonexistent_caster_fails(self, game_state_with_party):
        """Test that casting with invalid caster name fails"""
        result = game_state_with_party.cast_spell_exploration(
            caster_name="Nonexistent Wizard",
            spell_id="cure_wounds",
            target_name="Bruenor"
        )

        assert result["success"] is False
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_nonexistent_target_fails(self, game_state_with_party):
        """Test that healing nonexistent target fails"""
        result = game_state_with_party.cast_spell_exploration(
            caster_name="Brother Marcus",
            spell_id="cure_wounds",
            target_name="Nonexistent Fighter"
        )

        assert result["success"] is False
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_unknown_spell_fails(self, game_state_with_party):
        """Test that casting unknown spell fails"""
        result = game_state_with_party.cast_spell_exploration(
            caster_name="Brother Marcus",
            spell_id="fireball",  # Cleric doesn't know this
            target_name="Bruenor"
        )

        assert result["success"] is False
        assert "error" in result
        assert "know" in result["error"].lower()

    def test_no_spell_slots_fails(self, game_state_with_party):
        """Test that casting without spell slots fails"""
        cleric = game_state_with_party.party.get_character_by_name("Brother Marcus")
        # Deplete level 1 slots
        pool = cleric.get_resource_pool("spell_slots_level_1")
        pool.current = 0

        result = game_state_with_party.cast_spell_exploration(
            caster_name="Brother Marcus",
            spell_id="cure_wounds",
            target_name="Bruenor"
        )

        assert result["success"] is False
        assert "error" in result
        assert "spell slot" in result["error"].lower()

    def test_healing_cant_exceed_max_hp(self, game_state_with_party):
        """Test that healing can't exceed max HP"""
        fighter = game_state_with_party.party.get_character_by_name("Bruenor")
        fighter.current_hp = fighter.max_hp - 2  # Almost full

        result = game_state_with_party.cast_spell_exploration(
            caster_name="Brother Marcus",
            spell_id="cure_wounds",
            target_name="Bruenor"
        )

        assert result["success"] is True
        assert fighter.current_hp == fighter.max_hp  # Capped at max
        assert result["healing_amount"] <= 2  # Only healed up to max

    def test_healing_includes_spellcasting_modifier(self, game_state_with_party):
        """Test that healing includes caster's spellcasting modifier"""
        cleric = game_state_with_party.party.get_character_by_name("Brother Marcus")
        wisdom_modifier = cleric.abilities.wis_mod

        result = game_state_with_party.cast_spell_exploration(
            caster_name="Brother Marcus",
            spell_id="cure_wounds",
            target_name="Bruenor"
        )

        assert result["success"] is True
        # Healing should be at least the modifier (1d8 min is 1, plus modifier)
        assert result["healing_amount"] >= wisdom_modifier + 1

    def test_nonexistent_spell_data_fails(self, game_state_with_party):
        """Test that spell ID not in spells.json fails"""
        result = game_state_with_party.cast_spell_exploration(
            caster_name="Brother Marcus",
            spell_id="totally_fake_spell"
        )

        assert result["success"] is False
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_ritual_spell_consumes_slot_outside_ritual(self, game_state_with_party):
        """Test that ritual spells still consume slots when not cast as ritual"""
        cleric = game_state_with_party.party.get_character_by_name("Brother Marcus")
        initial_slots = cleric.get_available_spell_slots(1)

        # Detect Magic is a ritual but we're not implementing ritual casting yet
        result = game_state_with_party.cast_spell_exploration(
            caster_name="Brother Marcus",
            spell_id="detect_magic"
        )

        assert result["success"] is True
        assert cleric.get_available_spell_slots(1) == initial_slots - 1

    def test_self_healing(self, game_state_with_party):
        """Test that a character can heal themselves"""
        cleric = game_state_with_party.party.get_character_by_name("Brother Marcus")
        cleric.current_hp = 10  # Injure the cleric
        initial_hp = cleric.current_hp

        result = game_state_with_party.cast_spell_exploration(
            caster_name="Brother Marcus",
            spell_id="cure_wounds",
            target_name="Brother Marcus"  # Self-target
        )

        assert result["success"] is True
        assert cleric.current_hp > initial_hp

    def test_event_data_for_utility_spell(self, game_state_with_party, event_bus):
        """Test that utility spells emit proper event data"""
        events_received = []
        def event_handler(event):
            events_received.append(event)
        event_bus.subscribe(EventType.SPELL_CAST, event_handler)

        result = game_state_with_party.cast_spell_exploration(
            caster_name="Brother Marcus",
            spell_id="light"
        )

        assert result["success"] is True
        assert len(events_received) == 1
        event = events_received[0]
        assert event.type == EventType.SPELL_CAST
        assert event.data["caster"] == "Brother Marcus"
        assert event.data["spell"] == "Light"
        assert event.data["spell_level"] == 0
        assert "target" not in event.data  # Utility spells don't have targets
