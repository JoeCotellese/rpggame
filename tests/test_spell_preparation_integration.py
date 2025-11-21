# ABOUTME: Integration tests for spell preparation system
# ABOUTME: Tests integration between Character, GameState, and EventBus during spell preparation workflow

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.utils.events import EventBus, EventType
from dnd_engine.rules.loader import DataLoader
from dnd_engine.core.dice import DiceRoller


@pytest.fixture
def wizard_abilities():
    """Create abilities for a wizard with 16 INT (+3 modifier)"""
    return Abilities(
        strength=8,
        dexterity=14,
        constitution=12,
        intelligence=16,  # +3 modifier
        wisdom=10,
        charisma=8
    )


@pytest.fixture
def level_1_wizard(wizard_abilities):
    """Create a level 1 wizard with known spells"""
    return Character(
        name="Test Wizard",
        character_class=CharacterClass.WIZARD,
        level=1,
        abilities=wizard_abilities,
        max_hp=8,
        ac=12,
        spellcasting_ability="int",
        known_spells=[
            "fire_bolt",      # cantrip
            "mage_hand",      # cantrip
            "light",          # cantrip
            "magic_missile",  # level 1
            "shield",         # level 1
            "mage_armor",     # level 1
            "detect_magic",   # level 1
            "burning_hands"   # level 1
        ],
        prepared_spells=[]
    )


@pytest.fixture
def event_bus():
    """Create an event bus for testing"""
    return EventBus()


@pytest.fixture
def data_loader():
    """Create a data loader for loading game data"""
    return DataLoader()


@pytest.fixture
def game_state_with_wizard(level_1_wizard, event_bus, data_loader):
    """Create a game state with a wizard in the party"""
    party = Party([level_1_wizard])
    dice_roller = DiceRoller(seed=42)

    game_state = GameState(
        party=party,
        dungeon_name="test_dungeon",
        event_bus=event_bus,
        data_loader=data_loader,
        dice_roller=dice_roller
    )

    return game_state


class TestSpellPreparationWorkflow:
    """Test complete spell preparation workflow through GameState"""

    def test_prepare_spells_success(self, game_state_with_wizard, event_bus):
        """Test successful spell preparation updates character and emits event"""
        wizard = game_state_with_wizard.party.characters[0]

        # Track events
        events_received = []
        def event_handler(event):
            events_received.append(event)
        event_bus.subscribe(EventType.SPELLS_PREPARED, event_handler)

        # Prepare spells (cantrips + 4 leveled spells, max is INT mod 3 + level 1 = 4 leveled)
        spell_ids = [
            "fire_bolt",      # cantrip (doesn't count)
            "mage_hand",      # cantrip (doesn't count)
            "light",          # cantrip (doesn't count)
            "magic_missile",  # level 1 (1)
            "shield",         # level 1 (2)
            "mage_armor",     # level 1 (3)
            "detect_magic"    # level 1 (4)
        ]

        result = game_state_with_wizard.prepare_spells("Test Wizard", spell_ids)

        # Verify success
        assert result is True

        # Verify character state updated
        assert wizard.prepared_spells == spell_ids

        # Verify event was emitted
        assert len(events_received) == 1
        event = events_received[0]
        assert event.type == EventType.SPELLS_PREPARED
        assert event.data["character"] == "Test Wizard"
        assert event.data["spell_count"] == len(spell_ids)

    def test_prepare_spells_unknown_spell_fails(self, game_state_with_wizard, event_bus):
        """Test preparing unknown spell fails and doesn't emit event"""
        wizard = game_state_with_wizard.party.characters[0]

        # Track events
        events_received = []
        def event_handler(event):
            events_received.append(event)
        event_bus.subscribe(EventType.SPELLS_PREPARED, event_handler)

        # Try to prepare a spell the wizard doesn't know
        spell_ids = ["magic_missile", "fireball"]  # fireball is not in known_spells

        result = game_state_with_wizard.prepare_spells("Test Wizard", spell_ids)

        # Verify failure
        assert result is False

        # Verify character state unchanged
        assert wizard.prepared_spells == []

        # Verify no event was emitted
        assert len(events_received) == 0

    def test_prepare_spells_nonexistent_character_fails(self, game_state_with_wizard, event_bus):
        """Test preparing spells for nonexistent character fails"""
        # Track events
        events_received = []
        def event_handler(event):
            events_received.append(event)
        event_bus.subscribe(EventType.SPELLS_PREPARED, event_handler)

        result = game_state_with_wizard.prepare_spells("Nonexistent Wizard", ["magic_missile"])

        # Verify failure
        assert result is False

        # Verify no event was emitted
        assert len(events_received) == 0

    def test_prepare_spells_empty_list(self, game_state_with_wizard, event_bus):
        """Test preparing empty spell list succeeds (unprepare all)"""
        wizard = game_state_with_wizard.party.characters[0]

        # First prepare some spells
        wizard.prepared_spells = ["magic_missile", "shield"]

        # Track events
        events_received = []
        def event_handler(event):
            events_received.append(event)
        event_bus.subscribe(EventType.SPELLS_PREPARED, event_handler)

        # Prepare empty list
        result = game_state_with_wizard.prepare_spells("Test Wizard", [])

        # Verify success
        assert result is True

        # Verify character state updated
        assert wizard.prepared_spells == []

        # Verify event was emitted
        assert len(events_received) == 1


class TestSpellPreparationAfterLongRest:
    """Test spell preparation after long rest"""

    def test_long_rest_sets_can_prepare_flag_for_wizard(self, level_1_wizard):
        """Test that long rest sets can_prepare_spells flag for wizard"""
        result = level_1_wizard.take_long_rest()

        assert result["can_prepare_spells"] is True

    def test_long_rest_sets_can_prepare_flag_for_cleric(self):
        """Test that long rest sets can_prepare_spells flag for cleric"""
        cleric = Character(
            name="Test Cleric",
            character_class=CharacterClass.CLERIC,
            level=1,
            abilities=Abilities(
                strength=14,
                dexterity=10,
                constitution=14,
                intelligence=8,
                wisdom=16,  # +3 modifier
                charisma=12
            ),
            max_hp=10,
            ac=16,
            spellcasting_ability="wis",
            known_spells=["sacred_flame", "cure_wounds", "bless", "shield_of_faith"]
        )

        result = cleric.take_long_rest()

        assert result["can_prepare_spells"] is True

    def test_long_rest_does_not_set_can_prepare_for_fighter(self):
        """Test that long rest doesn't set can_prepare_spells flag for non-prepared casters"""
        fighter = Character(
            name="Test Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(
                strength=16,
                dexterity=14,
                constitution=15,
                intelligence=10,
                wisdom=12,
                charisma=8
            ),
            max_hp=12,
            ac=16
        )

        result = fighter.take_long_rest()

        assert result["can_prepare_spells"] is False


class TestSpellPreparationWithRealData:
    """Test spell preparation with real spell data from DataLoader"""

    def test_get_preparable_spells_separates_cantrips(self, level_1_wizard, data_loader):
        """Test that get_preparable_spells correctly separates cantrips from leveled spells"""
        spells_data = data_loader.load_spells()

        cantrips, leveled_spells = level_1_wizard.get_preparable_spells(spells_data)

        # Verify cantrips are separated
        assert "fire_bolt" in cantrips
        assert "mage_hand" in cantrips
        assert "light" in cantrips

        # Verify leveled spells are in the second list
        leveled_spell_ids = [spell_id for spell_id, _ in leveled_spells]
        assert "magic_missile" in leveled_spell_ids
        assert "shield" in leveled_spell_ids
        assert "mage_armor" in leveled_spell_ids
        assert "detect_magic" in leveled_spell_ids
        assert "burning_hands" in leveled_spell_ids

        # Verify cantrips are NOT in leveled spells
        assert "fire_bolt" not in leveled_spell_ids
        assert "mage_hand" not in leveled_spell_ids
        assert "light" not in leveled_spell_ids

    def test_get_preparable_spells_sorting(self, level_1_wizard, data_loader):
        """Test that leveled spells are sorted by level then name"""
        spells_data = data_loader.load_spells()

        _, leveled_spells = level_1_wizard.get_preparable_spells(spells_data)

        # Verify sorting (all level 1 spells, so should be alphabetical by name)
        spell_names = [spell_data["name"] for _, spell_data in leveled_spells]

        # Should be sorted alphabetically (all are level 1)
        assert spell_names == sorted(spell_names)

    def test_prepare_cantrips_only(self, game_state_with_wizard, event_bus):
        """Test preparing only cantrips (doesn't count toward limit)"""
        wizard = game_state_with_wizard.party.characters[0]

        # Track events
        events_received = []
        def event_handler(event):
            events_received.append(event)
        event_bus.subscribe(EventType.SPELLS_PREPARED, event_handler)

        # Prepare only cantrips
        spell_ids = ["fire_bolt", "mage_hand", "light"]

        result = game_state_with_wizard.prepare_spells("Test Wizard", spell_ids)

        # Verify success
        assert result is True
        assert wizard.prepared_spells == spell_ids

        # Verify event was emitted
        assert len(events_received) == 1

    def test_max_prepared_spells_calculation(self, level_1_wizard):
        """Test max prepared spells calculation (level + ability modifier)"""
        # Level 1 wizard with INT 16 (+3 modifier)
        # Max prepared = 1 + 3 = 4
        assert level_1_wizard.get_max_prepared_spells() == 4

        # Test with higher level
        level_1_wizard.level = 5
        # Max prepared = 5 + 3 = 8
        assert level_1_wizard.get_max_prepared_spells() == 8


class TestSpellPreparationEdgeCases:
    """Test edge cases in spell preparation"""

    def test_prepare_spells_with_no_known_spells(self, event_bus, data_loader):
        """Test preparing spells when character has no known spells"""
        wizard = Character(
            name="Newbie Wizard",
            character_class=CharacterClass.WIZARD,
            level=1,
            abilities=Abilities(
                strength=8,
                dexterity=14,
                constitution=12,
                intelligence=16,
                wisdom=10,
                charisma=8
            ),
            max_hp=8,
            ac=12,
            spellcasting_ability="int",
            known_spells=[],  # No known spells
            prepared_spells=[]
        )

        party = Party([wizard])
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=DiceRoller()
        )

        # Can successfully prepare empty list
        result = game_state.prepare_spells("Newbie Wizard", [])
        assert result is True

        # Cannot prepare any spells
        result = game_state.prepare_spells("Newbie Wizard", ["magic_missile"])
        assert result is False

    def test_get_preparable_spells_with_no_known_spells(self, data_loader):
        """Test get_preparable_spells when character has no known spells"""
        wizard = Character(
            name="Newbie Wizard",
            character_class=CharacterClass.WIZARD,
            level=1,
            abilities=Abilities(
                strength=8,
                dexterity=14,
                constitution=12,
                intelligence=16,
                wisdom=10,
                charisma=8
            ),
            max_hp=8,
            ac=12,
            spellcasting_ability="int",
            known_spells=[],
            prepared_spells=[]
        )

        spells_data = data_loader.load_spells()
        cantrips, leveled_spells = wizard.get_preparable_spells(spells_data)

        assert cantrips == []
        assert leveled_spells == []

    def test_prepare_spells_updates_existing_preparation(self, game_state_with_wizard, event_bus):
        """Test that preparing spells replaces previous preparation"""
        wizard = game_state_with_wizard.party.characters[0]

        # First preparation
        spell_ids_1 = ["magic_missile", "shield"]
        result = game_state_with_wizard.prepare_spells("Test Wizard", spell_ids_1)
        assert result is True
        assert wizard.prepared_spells == spell_ids_1

        # Second preparation (replaces first)
        spell_ids_2 = ["mage_armor", "detect_magic", "burning_hands"]
        result = game_state_with_wizard.prepare_spells("Test Wizard", spell_ids_2)
        assert result is True
        assert wizard.prepared_spells == spell_ids_2
        assert wizard.prepared_spells != spell_ids_1
