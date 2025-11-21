# ABOUTME: Unit tests for Wizard-specific character functionality
# ABOUTME: Tests spell preparation, Arcane Recovery, and wizard-specific mechanics

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.systems.resources import ResourcePool


class TestWizardSpellPreparation:
    """Test wizard spell preparation mechanics"""

    @pytest.fixture
    def wizard_abilities(self):
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
    def level_1_wizard(self, wizard_abilities):
        """Create a level 1 wizard character"""
        character = Character(
            name="Test Wizard",
            character_class=CharacterClass.WIZARD,
            level=1,
            abilities=wizard_abilities,
            max_hp=8,
            ac=12,
            spellcasting_ability="int",
            known_spells=["fire_bolt", "mage_hand", "light", "magic_missile", "shield", "mage_armor", "detect_magic"],
            prepared_spells=["magic_missile", "shield", "mage_armor"]
        )
        return character

    def test_get_max_prepared_spells_level_1(self, level_1_wizard):
        """Test max prepared spells for level 1 wizard with INT 16"""
        # Level 1 + INT mod 3 = 4
        assert level_1_wizard.get_max_prepared_spells() == 4

    def test_can_prepare_spell_success(self, level_1_wizard):
        """Test can prepare a known spell"""
        # Wizard has 3 prepared, can prepare 4 total
        assert level_1_wizard.can_prepare_spell("detect_magic") is True

    def test_can_prepare_spell_already_prepared(self, level_1_wizard):
        """Test cannot prepare an already prepared spell"""
        assert level_1_wizard.can_prepare_spell("magic_missile") is False

    def test_can_prepare_spell_unknown(self, level_1_wizard):
        """Test cannot prepare an unknown spell"""
        assert level_1_wizard.can_prepare_spell("fireball") is False

    def test_can_prepare_spell_at_maximum(self, level_1_wizard):
        """Test cannot prepare when at maximum"""
        # Prepare one more spell to reach maximum
        level_1_wizard.prepare_spell("detect_magic")
        # Now at max (4), cannot prepare more
        assert level_1_wizard.can_prepare_spell("shield") is False

    def test_prepare_spell_success(self, level_1_wizard):
        """Test prepare spell successfully"""
        initial_count = len(level_1_wizard.prepared_spells)
        result = level_1_wizard.prepare_spell("detect_magic")

        assert result is True
        assert "detect_magic" in level_1_wizard.prepared_spells
        assert len(level_1_wizard.prepared_spells) == initial_count + 1

    def test_prepare_spell_failure(self, level_1_wizard):
        """Test prepare spell failure when unknown"""
        initial_count = len(level_1_wizard.prepared_spells)
        result = level_1_wizard.prepare_spell("fireball")

        assert result is False
        assert len(level_1_wizard.prepared_spells) == initial_count

    def test_unprepare_spell_success(self, level_1_wizard):
        """Test unprepare spell successfully"""
        initial_count = len(level_1_wizard.prepared_spells)
        result = level_1_wizard.unprepare_spell("magic_missile")

        assert result is True
        assert "magic_missile" not in level_1_wizard.prepared_spells
        assert len(level_1_wizard.prepared_spells) == initial_count - 1

    def test_unprepare_spell_not_prepared(self, level_1_wizard):
        """Test unprepare spell that isn't prepared"""
        initial_count = len(level_1_wizard.prepared_spells)
        result = level_1_wizard.unprepare_spell("detect_magic")

        assert result is False
        assert len(level_1_wizard.prepared_spells) == initial_count

    def test_set_prepared_spells_success(self, level_1_wizard):
        """Test set prepared spells to a new list"""
        new_spells = ["magic_missile", "detect_magic"]
        result = level_1_wizard.set_prepared_spells(new_spells)

        assert result is True
        assert level_1_wizard.prepared_spells == new_spells

    def test_set_prepared_spells_with_cantrips(self, level_1_wizard):
        """Test set prepared spells with cantrips included (cantrips don't count toward limit)"""
        # Max leveled spells is 4 (INT mod 3 + level 1)
        # Set 4 leveled spells + 1 cantrip = should succeed
        spells_with_cantrip = ["magic_missile", "shield", "mage_armor", "detect_magic", "mage_hand"]
        result = level_1_wizard.set_prepared_spells(spells_with_cantrip)

        # Should succeed - cantrips don't count toward limit
        # (set_prepared_spells doesn't validate count, caller must enforce limit for leveled spells)
        assert result is True
        assert len(level_1_wizard.prepared_spells) == 5
        assert "mage_hand" in level_1_wizard.prepared_spells  # cantrip included

    def test_set_prepared_spells_with_unknown(self, level_1_wizard):
        """Test set prepared spells with unknown spell"""
        spells_with_unknown = ["magic_missile", "fireball"]  # fireball is not known
        result = level_1_wizard.set_prepared_spells(spells_with_unknown)

        assert result is False

    def test_prepare_and_unprepare_workflow(self, level_1_wizard):
        """Test complete prepare/unprepare workflow"""
        # Start with 3 prepared
        assert len(level_1_wizard.prepared_spells) == 3

        # Unprepare one
        level_1_wizard.unprepare_spell("shield")
        assert len(level_1_wizard.prepared_spells) == 2

        # Prepare two more
        level_1_wizard.prepare_spell("detect_magic")
        assert len(level_1_wizard.prepared_spells) == 3

        level_1_wizard.prepare_spell("shield")
        assert len(level_1_wizard.prepared_spells) == 4

        # Now at max, cannot prepare more
        assert level_1_wizard.can_prepare_spell("mage_hand") is False

    def test_get_preparable_spells_separates_cantrips(self, level_1_wizard):
        """Test get_preparable_spells separates cantrips from leveled spells"""
        # Mock spells data
        spells_data = {
            "fire_bolt": {"id": "fire_bolt", "name": "Fire Bolt", "level": 0, "school": "evocation"},
            "mage_hand": {"id": "mage_hand", "name": "Mage Hand", "level": 0, "school": "conjuration"},
            "light": {"id": "light", "name": "Light", "level": 0, "school": "evocation"},
            "magic_missile": {"id": "magic_missile", "name": "Magic Missile", "level": 1, "school": "evocation"},
            "shield": {"id": "shield", "name": "Shield", "level": 1, "school": "abjuration"},
            "mage_armor": {"id": "mage_armor", "name": "Mage Armor", "level": 1, "school": "abjuration"},
            "detect_magic": {"id": "detect_magic", "name": "Detect Magic", "level": 1, "school": "divination"}
        }

        cantrips, leveled_spells = level_1_wizard.get_preparable_spells(spells_data)

        # Should have 3 cantrips
        assert len(cantrips) == 3
        assert set(cantrips) == {"fire_bolt", "mage_hand", "light"}

        # Should have 4 leveled spells
        assert len(leveled_spells) == 4
        leveled_ids = [spell_id for spell_id, _ in leveled_spells]
        assert set(leveled_ids) == {"magic_missile", "shield", "mage_armor", "detect_magic"}

    def test_get_preparable_spells_sorted_by_level(self, level_1_wizard):
        """Test get_preparable_spells sorts leveled spells by level then name"""
        # Mock spells data with mixed levels
        spells_data = {
            "fire_bolt": {"id": "fire_bolt", "name": "Fire Bolt", "level": 0, "school": "evocation"},
            "fireball": {"id": "fireball", "name": "Fireball", "level": 3, "school": "evocation"},
            "shield": {"id": "shield", "name": "Shield", "level": 1, "school": "abjuration"},
            "magic_missile": {"id": "magic_missile", "name": "Magic Missile", "level": 1, "school": "evocation"},
            "fly": {"id": "fly", "name": "Fly", "level": 3, "school": "transmutation"}
        }

        # Update wizard's known spells for this test
        level_1_wizard.known_spells = ["fire_bolt", "fireball", "shield", "magic_missile", "fly"]

        cantrips, leveled_spells = level_1_wizard.get_preparable_spells(spells_data)

        # Check sorting: level 1 spells first (sorted by name), then level 3 (sorted by name)
        expected_order = [
            ("magic_missile", 1),  # Level 1, M comes before S
            ("shield", 1),
            ("fireball", 3),  # Level 3, F comes before F
            ("fly", 3)
        ]

        for idx, (spell_id, level) in enumerate(expected_order):
            assert leveled_spells[idx][0] == spell_id
            assert leveled_spells[idx][1]["level"] == level

    def test_get_preparable_spells_empty_known_spells(self):
        """Test get_preparable_spells with no known spells"""
        wizard = Character(
            name="Empty Wizard",
            character_class=CharacterClass.WIZARD,
            level=1,
            abilities=Abilities(10, 10, 10, 14, 10, 10),
            max_hp=8,
            ac=12,
            spellcasting_ability="int",
            known_spells=[],
            prepared_spells=[]
        )

        spells_data = {}
        cantrips, leveled_spells = wizard.get_preparable_spells(spells_data)

        assert cantrips == []
        assert leveled_spells == []

    def test_take_long_rest_returns_can_prepare_spells(self, level_1_wizard):
        """Test take_long_rest returns can_prepare_spells flag for Wizard"""
        result = level_1_wizard.take_long_rest()

        assert "can_prepare_spells" in result
        assert result["can_prepare_spells"] is True
        assert result["character"] == "Test Wizard"
        assert result["rest_type"] == "long"

    def test_take_long_rest_non_caster_cannot_prepare(self):
        """Test take_long_rest returns False for non-prepared-caster classes"""
        fighter = Character(
            name="Test Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(16, 14, 14, 10, 10, 10),
            max_hp=12,
            ac=16
        )

        result = fighter.take_long_rest()

        assert "can_prepare_spells" in result
        assert result["can_prepare_spells"] is False


class TestWizardArcaneRecovery:
    """Test wizard Arcane Recovery feature"""

    @pytest.fixture
    def wizard_abilities(self):
        """Create abilities for a wizard"""
        return Abilities(
            strength=8,
            dexterity=14,
            constitution=12,
            intelligence=16,
            wisdom=10,
            charisma=8
        )

    @pytest.fixture
    def level_1_wizard(self, wizard_abilities):
        """Create a level 1 wizard with spell slots and Arcane Recovery"""
        character = Character(
            name="Test Wizard",
            character_class=CharacterClass.WIZARD,
            level=1,
            abilities=wizard_abilities,
            max_hp=8,
            ac=12,
            spellcasting_ability="int"
        )

        # Add spell slots
        spell_slots = ResourcePool(
            name="1st level slots",
            current=0,  # All used
            maximum=2,
            recovery_type="long_rest"
        )
        character.add_resource_pool(spell_slots)

        # Add Arcane Recovery resource
        arcane_recovery = ResourcePool(
            name="arcane_recovery",
            current=1,
            maximum=1,
            recovery_type="long_rest"
        )
        character.add_resource_pool(arcane_recovery)

        return character

    @pytest.fixture
    def level_3_wizard(self, wizard_abilities):
        """Create a level 3 wizard with 1st and 2nd level spell slots"""
        character = Character(
            name="Level 3 Wizard",
            character_class=CharacterClass.WIZARD,
            level=3,
            abilities=wizard_abilities,
            max_hp=18,
            ac=12,
            spellcasting_ability="int"
        )

        # Add 1st level spell slots
        slots_1st = ResourcePool(
            name="1st level slots",
            current=1,  # 3 used
            maximum=4,
            recovery_type="long_rest"
        )
        character.add_resource_pool(slots_1st)

        # Add 2nd level spell slots
        slots_2nd = ResourcePool(
            name="2nd level slots",
            current=0,  # 2 used
            maximum=2,
            recovery_type="long_rest"
        )
        character.add_resource_pool(slots_2nd)

        # Add Arcane Recovery
        arcane_recovery = ResourcePool(
            name="arcane_recovery",
            current=1,
            maximum=1,
            recovery_type="long_rest"
        )
        character.add_resource_pool(arcane_recovery)

        return character

    def test_arcane_recovery_level_1_max_slots(self, level_1_wizard):
        """Test level 1 wizard can recover 1 spell slot level"""
        # Level 1: (1 + 1) // 2 = 1 slot level
        result = level_1_wizard.use_arcane_recovery({1: 1})

        assert result is True
        pool = level_1_wizard.get_resource_pool("1st level slots")
        assert pool.current == 1

    def test_arcane_recovery_level_3_max_slots(self, level_3_wizard):
        """Test level 3 wizard can recover 2 spell slot levels"""
        # Level 3: (3 + 1) // 2 = 2 slot levels
        # Recover two 1st level slots
        result = level_3_wizard.use_arcane_recovery({1: 2})

        assert result is True
        pool = level_3_wizard.get_resource_pool("1st level slots")
        assert pool.current == 3

    def test_arcane_recovery_mixed_levels(self, level_3_wizard):
        """Test recovering mixed spell slot levels"""
        # Recover 1 first-level (1) + 1 second-level (2) = 3 total
        # But max is 2 for level 3, so this should fail
        with pytest.raises(ValueError, match="Cannot recover 3 spell slot levels"):
            level_3_wizard.use_arcane_recovery({1: 1, 2: 1})

    def test_arcane_recovery_one_second_level_slot(self, level_3_wizard):
        """Test recovering one 2nd level slot"""
        # Recover 1 second-level slot (2 slot levels)
        result = level_3_wizard.use_arcane_recovery({2: 1})

        assert result is True
        pool = level_3_wizard.get_resource_pool("2nd level slots")
        assert pool.current == 1

    def test_arcane_recovery_exceeds_maximum(self, level_1_wizard):
        """Test cannot recover more slot levels than allowed"""
        # Level 1 max is 1 slot level, trying to recover 2
        with pytest.raises(ValueError, match="Cannot recover 2 spell slot levels"):
            level_1_wizard.use_arcane_recovery({1: 2})

    def test_arcane_recovery_consumes_resource(self, level_1_wizard):
        """Test Arcane Recovery consumes the resource"""
        arcane_pool = level_1_wizard.get_resource_pool("arcane_recovery")
        assert arcane_pool.current == 1

        level_1_wizard.use_arcane_recovery({1: 1})

        assert arcane_pool.current == 0

    def test_arcane_recovery_only_once(self, level_1_wizard):
        """Test Arcane Recovery can only be used once per long rest"""
        # Use it once
        level_1_wizard.use_arcane_recovery({1: 1})

        # Try to use again
        result = level_1_wizard.use_arcane_recovery({1: 1})
        assert result is False

    def test_arcane_recovery_no_6th_level_slots(self, level_3_wizard):
        """Test Arcane Recovery cannot recover 6th+ level slots"""
        with pytest.raises(ValueError, match="6th level or higher"):
            level_3_wizard.use_arcane_recovery({6: 1})

    def test_arcane_recovery_invalid_spell_level(self, level_3_wizard):
        """Test Arcane Recovery with invalid spell level"""
        # Try to recover 3rd level slots when character only has 2nd
        with pytest.raises(ValueError, match="No spell slot pool found"):
            level_3_wizard.use_arcane_recovery({3: 1})

    def test_arcane_recovery_doesnt_exceed_max_slots(self, level_1_wizard):
        """Test recovered slots don't exceed maximum"""
        # Set current to 1
        pool = level_1_wizard.get_resource_pool("1st level slots")
        pool.current = 1

        # Recover 1 more (should go to 2, not exceed)
        level_1_wizard.use_arcane_recovery({1: 1})

        assert pool.current == 2
        assert pool.current == pool.maximum

    def test_arcane_recovery_zero_slots(self, level_1_wizard):
        """Test Arcane Recovery with zero slots to recover"""
        result = level_1_wizard.use_arcane_recovery({1: 0})

        # Should succeed but not recover anything
        assert result is True
        pool = level_1_wizard.get_resource_pool("1st level slots")
        assert pool.current == 0
