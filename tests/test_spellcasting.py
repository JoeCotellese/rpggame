# ABOUTME: Unit tests for Character spellcasting functionality
# ABOUTME: Tests spell slot tracking, casting, and spellcasting modifiers

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.spell import Spell, SpellSchool, SpellComponents, DurationType
from dnd_engine.systems.resources import ResourcePool


class TestCharacterSpellcasting:
    """Test Character class spellcasting functionality"""

    @pytest.fixture
    def wizard_abilities(self):
        """Create abilities for a wizard"""
        return Abilities(
            strength=8,
            dexterity=14,
            constitution=12,
            intelligence=16,  # +3 modifier
            wisdom=10,
            charisma=8
        )

    @pytest.fixture
    def wizard_character(self, wizard_abilities):
        """Create a level 1 wizard character"""
        character = Character(
            name="Test Wizard",
            character_class=CharacterClass.WIZARD,
            level=1,
            abilities=wizard_abilities,
            max_hp=8,
            ac=12,
            spellcasting_ability="int",
            known_spells=["fire_bolt", "mage_hand", "magic_missile"],
            prepared_spells=["magic_missile"]
        )

        # Add 1st level spell slots
        spell_slots = ResourcePool(
            name="1st level slots",
            current=2,
            maximum=2,
            recovery_type="long_rest"
        )
        character.add_resource_pool(spell_slots)

        return character

    @pytest.fixture
    def cantrip(self):
        """Create a sample cantrip (Fire Bolt)"""
        return Spell(
            id="fire_bolt",
            name="Fire Bolt",
            level=0,
            school=SpellSchool.EVOCATION,
            casting_time="1 action",
            range_ft=120,
            components=SpellComponents(verbal=True, somatic=True),
            duration=DurationType.INSTANTANEOUS,
            description="You hurl a mote of fire at a creature or object within range."
        )

    @pytest.fixture
    def first_level_spell(self):
        """Create a sample 1st level spell (Magic Missile)"""
        return Spell(
            id="magic_missile",
            name="Magic Missile",
            level=1,
            school=SpellSchool.EVOCATION,
            casting_time="1 action",
            range_ft=120,
            components=SpellComponents(verbal=True, somatic=True),
            duration=DurationType.INSTANTANEOUS,
            description="You create three darts of magical force."
        )

    @pytest.fixture
    def unprepared_spell(self):
        """Create a spell the wizard knows but hasn't prepared"""
        return Spell(
            id="shield",
            name="Shield",
            level=1,
            school=SpellSchool.ABJURATION,
            casting_time="1 reaction",
            range_ft=0,
            components=SpellComponents(verbal=True, somatic=True),
            duration=DurationType.TIMED,
            description="An invisible barrier of magical force appears and protects you."
        )

    # Test spellcasting ability and initialization
    def test_wizard_has_spellcasting_ability(self, wizard_character):
        """Test that wizard has spellcasting ability set"""
        assert wizard_character.spellcasting_ability == "int"

    def test_wizard_has_known_spells(self, wizard_character):
        """Test that wizard has known spells"""
        assert len(wizard_character.known_spells) == 3
        assert "fire_bolt" in wizard_character.known_spells
        assert "magic_missile" in wizard_character.known_spells

    def test_wizard_has_prepared_spells(self, wizard_character):
        """Test that wizard has prepared spells"""
        assert len(wizard_character.prepared_spells) == 1
        assert "magic_missile" in wizard_character.prepared_spells

    def test_wizard_has_spell_slots(self, wizard_character):
        """Test that wizard has spell slots as resource pool"""
        pool = wizard_character.get_resource_pool("1st level slots")
        assert pool is not None
        assert pool.maximum == 2
        assert pool.current == 2

    # Test get_spell_attack_modifier
    def test_spell_attack_modifier_calculation(self, wizard_character):
        """Test spell attack modifier calculation (proficiency + ability mod)"""
        # Level 1 wizard: proficiency +2, int +3 = +5
        assert wizard_character.get_spell_attack_modifier() == 5

    def test_spell_attack_modifier_without_spellcasting_ability(self):
        """Test that spell attack modifier raises error without spellcasting ability"""
        fighter = Character(
            name="Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(16, 14, 14, 10, 12, 8),
            max_hp=12,
            ac=16
        )

        with pytest.raises(ValueError, match="has no spellcasting ability"):
            fighter.get_spell_attack_modifier()

    # Test get_spell_save_dc
    def test_spell_save_dc_calculation(self, wizard_character):
        """Test spell save DC calculation (8 + proficiency + ability mod)"""
        # 8 + 2 (proficiency) + 3 (int) = 13
        assert wizard_character.get_spell_save_dc() == 13

    def test_spell_save_dc_without_spellcasting_ability(self):
        """Test that spell save DC raises error without spellcasting ability"""
        fighter = Character(
            name="Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(16, 14, 14, 10, 12, 8),
            max_hp=12,
            ac=16
        )

        with pytest.raises(ValueError, match="has no spellcasting ability"):
            fighter.get_spell_save_dc()

    # Test can_cast_spell
    def test_can_cast_cantrip(self, wizard_character, cantrip):
        """Test that cantrips can always be cast"""
        assert wizard_character.can_cast_spell(cantrip) is True

    def test_can_cast_prepared_spell_with_slots(self, wizard_character, first_level_spell):
        """Test that prepared spell with available slots can be cast"""
        assert wizard_character.can_cast_spell(first_level_spell) is True

    def test_cannot_cast_unprepared_spell(self, wizard_character, unprepared_spell):
        """Test that unprepared spell cannot be cast"""
        wizard_character.known_spells.append("shield")  # Add to known spells
        assert wizard_character.can_cast_spell(unprepared_spell) is False

    def test_cannot_cast_spell_without_slots(self, wizard_character, first_level_spell):
        """Test that spell cannot be cast without available slots"""
        # Use up all spell slots
        wizard_character.use_resource("1st level slots", 2)
        assert wizard_character.can_cast_spell(first_level_spell) is False

    def test_cannot_cast_spell_without_slot_pool(self, first_level_spell):
        """Test that spell cannot be cast if spell slot pool doesn't exist"""
        wizard = Character(
            name="Wizard No Slots",
            character_class=CharacterClass.WIZARD,
            level=1,
            abilities=Abilities(8, 14, 12, 16, 10, 8),
            max_hp=8,
            ac=12,
            spellcasting_ability="int",
            known_spells=["magic_missile"],
            prepared_spells=["magic_missile"]
        )
        # No spell slot pool added
        assert wizard.can_cast_spell(first_level_spell) is False

    # Test cast_spell
    def test_cast_cantrip_does_not_consume_slots(self, wizard_character, cantrip):
        """Test that casting cantrip doesn't consume spell slots"""
        initial_slots = wizard_character.get_resource_pool("1st level slots").current

        result = wizard_character.cast_spell(cantrip)

        assert result is True
        assert wizard_character.get_resource_pool("1st level slots").current == initial_slots

    def test_cast_prepared_spell_consumes_slot(self, wizard_character, first_level_spell):
        """Test that casting prepared spell consumes a spell slot"""
        initial_slots = wizard_character.get_resource_pool("1st level slots").current

        result = wizard_character.cast_spell(first_level_spell)

        assert result is True
        assert wizard_character.get_resource_pool("1st level slots").current == initial_slots - 1

    def test_cast_unprepared_spell_fails(self, wizard_character, unprepared_spell):
        """Test that casting unprepared spell fails"""
        wizard_character.known_spells.append("shield")  # Add to known but not prepared
        initial_slots = wizard_character.get_resource_pool("1st level slots").current

        result = wizard_character.cast_spell(unprepared_spell)

        assert result is False
        assert wizard_character.get_resource_pool("1st level slots").current == initial_slots

    def test_cast_spell_without_slots_fails(self, wizard_character, first_level_spell):
        """Test that casting spell without available slots fails"""
        # Use up all slots
        wizard_character.use_resource("1st level slots", 2)

        result = wizard_character.cast_spell(first_level_spell)

        assert result is False

    def test_cast_multiple_spells(self, wizard_character, first_level_spell):
        """Test casting multiple spells consumes multiple slots"""
        assert wizard_character.cast_spell(first_level_spell) is True
        assert wizard_character.get_resource_pool("1st level slots").current == 1

        assert wizard_character.cast_spell(first_level_spell) is True
        assert wizard_character.get_resource_pool("1st level slots").current == 0

        # Third cast should fail (no slots)
        assert wizard_character.cast_spell(first_level_spell) is False

    # Test spell slot recovery on long rest
    def test_spell_slots_recover_on_long_rest(self, wizard_character, first_level_spell):
        """Test that spell slots recover on long rest"""
        # Cast spells to use slots
        wizard_character.cast_spell(first_level_spell)
        wizard_character.cast_spell(first_level_spell)
        assert wizard_character.get_resource_pool("1st level slots").current == 0

        # Take long rest
        wizard_character.take_long_rest()

        # Slots should be restored
        assert wizard_character.get_resource_pool("1st level slots").current == 2

    # Test with different spellcasting abilities
    def test_wisdom_spellcaster(self):
        """Test spellcasting with wisdom (e.g., Cleric)"""
        cleric = Character(
            name="Cleric",
            character_class=CharacterClass.FIGHTER,  # Using fighter as placeholder
            level=1,
            abilities=Abilities(14, 10, 12, 8, 16, 14),  # WIS +3
            max_hp=10,
            ac=14,
            spellcasting_ability="wis"
        )

        # Spell attack: 2 (prof) + 3 (wis) = 5
        assert cleric.get_spell_attack_modifier() == 5
        # Spell DC: 8 + 2 (prof) + 3 (wis) = 13
        assert cleric.get_spell_save_dc() == 13

    def test_charisma_spellcaster(self):
        """Test spellcasting with charisma (e.g., Sorcerer)"""
        sorcerer = Character(
            name="Sorcerer",
            character_class=CharacterClass.FIGHTER,  # Using fighter as placeholder
            level=1,
            abilities=Abilities(8, 14, 12, 10, 10, 16),  # CHA +3
            max_hp=8,
            ac=12,
            spellcasting_ability="cha"
        )

        # Spell attack: 2 (prof) + 3 (cha) = 5
        assert sorcerer.get_spell_attack_modifier() == 5
        # Spell DC: 8 + 2 (prof) + 3 (cha) = 13
        assert sorcerer.get_spell_save_dc() == 13

    # Test spell level name helper
    def test_get_spell_level_name_1st(self, wizard_character):
        """Test spell level name for 1st level"""
        assert wizard_character._get_spell_level_name(1) == "1st"

    def test_get_spell_level_name_2nd(self, wizard_character):
        """Test spell level name for 2nd level"""
        assert wizard_character._get_spell_level_name(2) == "2nd"

    def test_get_spell_level_name_3rd(self, wizard_character):
        """Test spell level name for 3rd level"""
        assert wizard_character._get_spell_level_name(3) == "3rd"

    def test_get_spell_level_name_4th_and_higher(self, wizard_character):
        """Test spell level name for 4th level and higher"""
        assert wizard_character._get_spell_level_name(4) == "4th"
        assert wizard_character._get_spell_level_name(5) == "5th"
        assert wizard_character._get_spell_level_name(9) == "9th"

    # Test ability modifier helper
    def test_get_ability_modifier(self, wizard_character):
        """Test getting ability modifiers by name"""
        assert wizard_character._get_ability_modifier("int") == 3
        assert wizard_character._get_ability_modifier("dex") == 2
        assert wizard_character._get_ability_modifier("str") == -1

    def test_get_ability_modifier_invalid_ability(self, wizard_character):
        """Test that invalid ability name raises error"""
        with pytest.raises(ValueError, match="Invalid ability name"):
            wizard_character._get_ability_modifier("invalid")

    # Test higher level character
    def test_higher_level_wizard_spell_modifiers(self):
        """Test spell modifiers scale with level"""
        wizard = Character(
            name="Level 5 Wizard",
            character_class=CharacterClass.WIZARD,
            level=5,
            abilities=Abilities(8, 14, 12, 18, 10, 8),  # INT +4
            max_hp=24,
            ac=12,
            spellcasting_ability="int"
        )

        # Level 5: proficiency +3
        # Spell attack: 3 (prof) + 4 (int) = 7
        assert wizard.get_spell_attack_modifier() == 7
        # Spell DC: 8 + 3 (prof) + 4 (int) = 15
        assert wizard.get_spell_save_dc() == 15
