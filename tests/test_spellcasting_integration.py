# ABOUTME: Integration tests for spellcasting system
# ABOUTME: Tests CharacterFactory initialization, save/load, and spell slot management

import pytest
import tempfile
import os
from pathlib import Path
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.save_manager import SaveManager
from dnd_engine.core.creature import Abilities
from dnd_engine.core.spell import Spell, SpellSchool, SpellComponents, DurationType
from dnd_engine.rules.loader import DataLoader


class TestSpellcastingIntegration:
    """Integration tests for spellcasting system"""

    @pytest.fixture
    def data_loader(self):
        """Create a DataLoader instance"""
        return DataLoader()

    @pytest.fixture
    def character_factory(self):
        """Create a CharacterFactory instance"""
        return CharacterFactory()

    @pytest.fixture
    def temp_save_dir(self):
        """Create a temporary directory for save files"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup
        for file in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, file))
        os.rmdir(temp_dir)

    @pytest.fixture
    def wizard_character(self, data_loader):
        """Create a level 1 wizard with spellcasting initialized"""
        abilities = Abilities(
            strength=8,
            dexterity=14,
            constitution=12,
            intelligence=16,
            wisdom=10,
            charisma=8
        )

        character = Character(
            name="Test Wizard",
            character_class=CharacterClass.WIZARD,
            level=1,
            abilities=abilities,
            max_hp=8,
            ac=12
        )

        # Load class data and initialize spellcasting
        classes_data = data_loader.load_classes()
        wizard_class_data = classes_data["wizard"]

        # Initialize resources and spellcasting
        CharacterFactory.initialize_class_resources(character, wizard_class_data, 1)
        spells_data = data_loader.load_spells()
        CharacterFactory.initialize_spellcasting(character, wizard_class_data, spells_data, interactive=False)

        return character

    # Test CharacterFactory spellcasting initialization
    def test_initialize_spellcasting_sets_ability(self, wizard_character):
        """Test that initialize_spellcasting sets spellcasting ability"""
        assert wizard_character.spellcasting_ability == "int"

    def test_initialize_spellcasting_adds_known_spells(self, wizard_character):
        """Test that initialize_spellcasting adds known spells"""
        assert len(wizard_character.known_spells) > 0
        # Should have cantrips and leveled spells
        assert any(spell_id in wizard_character.known_spells for spell_id in ["fire_bolt", "mage_hand", "light"])

    def test_initialize_spellcasting_adds_prepared_spells(self, wizard_character):
        """Test that initialize_spellcasting adds prepared spells"""
        assert len(wizard_character.prepared_spells) > 0

    def test_initialize_spellcasting_creates_spell_slots(self, wizard_character):
        """Test that spell slots are created as resource pools"""
        pool = wizard_character.get_resource_pool("1st level slots")
        assert pool is not None
        assert pool.maximum == 2
        assert pool.recovery_type == "long_rest"

    def test_non_spellcasting_class_has_no_spellcasting(self, data_loader):
        """Test that non-spellcasting classes don't get spellcasting initialized"""
        abilities = Abilities(16, 14, 14, 10, 12, 8)
        fighter = Character(
            name="Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16
        )

        classes_data = data_loader.load_classes()
        fighter_class_data = classes_data["fighter"]

        spells_data = data_loader.load_spells()
        CharacterFactory.initialize_spellcasting(fighter, fighter_class_data, spells_data)

        assert fighter.spellcasting_ability is None
        assert len(fighter.known_spells) == 0
        assert len(fighter.prepared_spells) == 0

    # Test spell casting workflow
    def test_cast_spell_workflow(self, wizard_character):
        """Test complete spell casting workflow"""
        # Create a spell
        spell = Spell(
            id="magic_missile",
            name="Magic Missile",
            level=1,
            school=SpellSchool.EVOCATION,
            casting_time="1 action",
            range_ft=120,
            components=SpellComponents(verbal=True, somatic=True),
            duration=DurationType.INSTANTANEOUS,
            description="Test spell"
        )

        # Add to prepared spells
        wizard_character.prepared_spells.append("magic_missile")

        # Check can cast
        assert wizard_character.can_cast_spell(spell) is True

        # Cast the spell
        initial_slots = wizard_character.get_resource_pool("1st level slots").current
        result = wizard_character.cast_spell(spell)

        assert result is True
        assert wizard_character.get_resource_pool("1st level slots").current == initial_slots - 1

        # Cast again
        result = wizard_character.cast_spell(spell)
        assert result is True
        assert wizard_character.get_resource_pool("1st level slots").current == 0

        # Cannot cast anymore
        assert wizard_character.can_cast_spell(spell) is False
        result = wizard_character.cast_spell(spell)
        assert result is False

    def test_spell_slot_recovery_workflow(self, wizard_character):
        """Test spell slot recovery on long rest"""
        # Create and prepare a spell
        spell = Spell(
            id="magic_missile",
            name="Magic Missile",
            level=1,
            school=SpellSchool.EVOCATION,
            casting_time="1 action",
            range_ft=120,
            components=SpellComponents(verbal=True, somatic=True),
            duration=DurationType.INSTANTANEOUS,
            description="Test spell"
        )
        wizard_character.prepared_spells.append("magic_missile")

        # Cast all spells
        wizard_character.cast_spell(spell)
        wizard_character.cast_spell(spell)
        assert wizard_character.get_resource_pool("1st level slots").current == 0

        # Cannot cast
        assert wizard_character.can_cast_spell(spell) is False

        # Take long rest
        rest_result = wizard_character.take_long_rest()

        # Verify slots recovered
        assert "1st level slots" in rest_result["resources_recovered"]
        assert wizard_character.get_resource_pool("1st level slots").current == 2

        # Can cast again
        assert wizard_character.can_cast_spell(spell) is True

    def test_cantrip_casting_workflow(self, wizard_character):
        """Test that cantrips don't consume slots"""
        cantrip = Spell(
            id="fire_bolt",
            name="Fire Bolt",
            level=0,
            school=SpellSchool.EVOCATION,
            casting_time="1 action",
            range_ft=120,
            components=SpellComponents(verbal=True, somatic=True),
            duration=DurationType.INSTANTANEOUS,
            description="Test cantrip"
        )

        initial_slots = wizard_character.get_resource_pool("1st level slots").current

        # Cast cantrip multiple times
        for _ in range(5):
            assert wizard_character.can_cast_spell(cantrip) is True
            result = wizard_character.cast_spell(cantrip)
            assert result is True

        # Spell slots unchanged
        assert wizard_character.get_resource_pool("1st level slots").current == initial_slots

    def test_spell_attack_and_dc_calculations(self, wizard_character):
        """Test spell attack modifier and save DC calculations"""
        # Level 1 wizard with INT 16 (+3)
        # Proficiency bonus: +2
        # Spell attack: 2 + 3 = +5
        # Spell DC: 8 + 2 + 3 = 13

        assert wizard_character.get_spell_attack_modifier() == 5
        assert wizard_character.get_spell_save_dc() == 13

    # Test multiple spell slot levels
    def test_multiple_spell_slot_levels(self, data_loader):
        """Test character with multiple spell slot levels"""
        abilities = Abilities(8, 14, 12, 16, 10, 8)
        wizard = Character(
            name="Level 3 Wizard",
            character_class=CharacterClass.WIZARD,
            level=3,
            abilities=abilities,
            max_hp=18,
            ac=12
        )

        classes_data = data_loader.load_classes()
        wizard_class_data = classes_data["wizard"]

        # Initialize resources for level 3
        CharacterFactory.initialize_class_resources(wizard, wizard_class_data, 3)

        # Should have 1st and 2nd level slots
        first_level_pool = wizard.get_resource_pool("1st level slots")
        second_level_pool = wizard.get_resource_pool("2nd level slots")

        assert first_level_pool is not None
        assert first_level_pool.maximum == 4

        assert second_level_pool is not None
        assert second_level_pool.maximum == 2

    def test_prepared_spell_limitation(self, wizard_character):
        """Test that only prepared spells can be cast"""
        # Create two spells
        prepared_spell = Spell(
            id="magic_missile",
            name="Magic Missile",
            level=1,
            school=SpellSchool.EVOCATION,
            casting_time="1 action",
            range_ft=120,
            components=SpellComponents(verbal=True, somatic=True),
            duration=DurationType.INSTANTANEOUS,
            description="Prepared spell"
        )

        unprepared_spell = Spell(
            id="shield",
            name="Shield",
            level=1,
            school=SpellSchool.ABJURATION,
            casting_time="1 reaction",
            range_ft=0,
            components=SpellComponents(verbal=True, somatic=True),
            duration=DurationType.TIMED,
            description="Unprepared spell"
        )

        # Add both to known spells
        wizard_character.known_spells.extend(["magic_missile", "shield"])

        # Only prepare magic_missile
        wizard_character.prepared_spells = ["magic_missile"]

        # Can cast prepared spell
        assert wizard_character.can_cast_spell(prepared_spell) is True

        # Cannot cast unprepared spell
        assert wizard_character.can_cast_spell(unprepared_spell) is False

        # Prepare shield
        wizard_character.prepared_spells.append("shield")

        # Now can cast it
        assert wizard_character.can_cast_spell(unprepared_spell) is True
