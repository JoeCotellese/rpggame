# ABOUTME: Tests for out-of-combat spellcasting functionality
# ABOUTME: Tests Character.get_out_of_combat_spells() filtering logic

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.rules.loader import DataLoader


class TestGetOutOfCombatSpells:
    """Test Character.get_out_of_combat_spells() method"""

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
    def wizard_with_mixed_spells(self, wizard_abilities):
        """Create a wizard with both combat and utility spells"""
        return Character(
            name="Test Wizard",
            character_class=CharacterClass.WIZARD,
            level=3,
            abilities=wizard_abilities,
            max_hp=15,
            ac=12,
            spellcasting_ability="int",
            known_spells=[
                # Combat spells
                "fire_bolt",        # cantrip: attack + damage
                "ray_of_frost",     # cantrip: attack + damage
                "magic_missile",    # level 1: damage only
                "burning_hands",    # level 1: damage + save
                "scorching_ray",    # level 2: attack + damage
                # Utility/healing spells
                "light",            # cantrip: utility (no attack/damage)
                "mage_hand",        # cantrip: utility
                "cure_wounds",      # level 1: healing
                "detect_magic",     # level 1: ritual
                "shield",           # level 1: reaction utility
                "mage_armor",       # level 1: buff utility
                "identify"          # level 1: ritual
            ],
            prepared_spells=[
                "fire_bolt", "light", "mage_hand",  # cantrips
                "magic_missile", "cure_wounds", "detect_magic",
                "shield", "mage_armor"
            ]
        )

    @pytest.fixture
    def data_loader(self):
        """Load real spell data"""
        return DataLoader()

    def test_returns_healing_spells(self, wizard_with_mixed_spells, data_loader):
        """Test that healing spells are included"""
        spells_data = data_loader.load_spells()
        out_of_combat = wizard_with_mixed_spells.get_out_of_combat_spells(spells_data)

        spell_ids = [spell_id for spell_id, _ in out_of_combat]
        assert "cure_wounds" in spell_ids

    def test_returns_ritual_spells(self, wizard_with_mixed_spells, data_loader):
        """Test that ritual spells are included"""
        spells_data = data_loader.load_spells()
        out_of_combat = wizard_with_mixed_spells.get_out_of_combat_spells(spells_data)

        spell_ids = [spell_id for spell_id, _ in out_of_combat]
        assert "detect_magic" in spell_ids

    def test_returns_utility_spells(self, wizard_with_mixed_spells, data_loader):
        """Test that utility spells (no attack/damage) are included"""
        spells_data = data_loader.load_spells()
        out_of_combat = wizard_with_mixed_spells.get_out_of_combat_spells(spells_data)

        spell_ids = [spell_id for spell_id, _ in out_of_combat]
        assert "light" in spell_ids
        assert "mage_hand" in spell_ids
        assert "shield" in spell_ids
        assert "mage_armor" in spell_ids

    def test_excludes_pure_combat_spells(self, wizard_with_mixed_spells, data_loader):
        """Test that pure attack/damage spells are excluded"""
        spells_data = data_loader.load_spells()
        out_of_combat = wizard_with_mixed_spells.get_out_of_combat_spells(spells_data)

        spell_ids = [spell_id for spell_id, _ in out_of_combat]
        # These should NOT be in out-of-combat list
        assert "fire_bolt" not in spell_ids  # attack + damage
        assert "magic_missile" not in spell_ids  # damage only (no utility)

    def test_sorted_by_level(self, wizard_with_mixed_spells, data_loader):
        """Test that spells are sorted by level (cantrips first)"""
        spells_data = data_loader.load_spells()
        out_of_combat = wizard_with_mixed_spells.get_out_of_combat_spells(spells_data)

        # Extract levels
        levels = [spell_data.get("level", 0) for _, spell_data in out_of_combat]

        # Should be sorted: cantrips (0) first, then ascending
        assert levels == sorted(levels)
        # First items should be level 0 (cantrips)
        if out_of_combat:
            assert out_of_combat[0][1].get("level", 0) == 0

    def test_uses_prepared_spells_for_wizard(self, wizard_with_mixed_spells, data_loader):
        """Test that wizards use prepared_spells, not all known_spells"""
        spells_data = data_loader.load_spells()

        # The wizard knows identify but hasn't prepared it
        assert "identify" in wizard_with_mixed_spells.known_spells
        assert "identify" not in wizard_with_mixed_spells.prepared_spells

        out_of_combat = wizard_with_mixed_spells.get_out_of_combat_spells(spells_data)
        spell_ids = [spell_id for spell_id, _ in out_of_combat]

        # Should NOT include unprepared spell
        assert "identify" not in spell_ids

    def test_empty_spell_list(self, wizard_abilities, data_loader):
        """Test character with no spells"""
        wizard = Character(
            name="Newbie Wizard",
            character_class=CharacterClass.WIZARD,
            level=1,
            abilities=wizard_abilities,
            max_hp=8,
            ac=12,
            spellcasting_ability="int",
            known_spells=[],
            prepared_spells=[]
        )

        spells_data = data_loader.load_spells()
        out_of_combat = wizard.get_out_of_combat_spells(spells_data)

        assert out_of_combat == []

    def test_non_caster_returns_empty(self, data_loader):
        """Test that non-casters return empty list"""
        fighter = Character(
            name="Test Fighter",
            character_class=CharacterClass.FIGHTER,
            level=5,
            abilities=Abilities(
                strength=16,
                dexterity=14,
                constitution=15,
                intelligence=10,
                wisdom=12,
                charisma=8
            ),
            max_hp=40,
            ac=18
        )

        spells_data = data_loader.load_spells()
        out_of_combat = fighter.get_out_of_combat_spells(spells_data)

        assert out_of_combat == []

    def test_returns_spell_data_tuples(self, wizard_with_mixed_spells, data_loader):
        """Test that method returns (spell_id, spell_data) tuples"""
        spells_data = data_loader.load_spells()
        out_of_combat = wizard_with_mixed_spells.get_out_of_combat_spells(spells_data)

        # Should return list of tuples
        assert isinstance(out_of_combat, list)

        if out_of_combat:
            # Each item should be a tuple of (str, dict)
            spell_id, spell_data = out_of_combat[0]
            assert isinstance(spell_id, str)
            assert isinstance(spell_data, dict)
            assert "name" in spell_data
            assert "level" in spell_data

    def test_handles_missing_spell_data_gracefully(self, wizard_abilities):
        """Test that method handles spells not in spells_data"""
        wizard = Character(
            name="Test Wizard",
            character_class=CharacterClass.WIZARD,
            level=1,
            abilities=wizard_abilities,
            max_hp=8,
            ac=12,
            spellcasting_ability="int",
            known_spells=["nonexistent_spell", "light"],
            prepared_spells=["nonexistent_spell", "light"]
        )

        # Spell data that doesn't include the nonexistent spell
        spells_data = {
            "light": {
                "name": "Light",
                "level": 0,
                "school": "evocation"
            }
        }

        out_of_combat = wizard.get_out_of_combat_spells(spells_data)

        # Should only include "light", skip the nonexistent one
        spell_ids = [spell_id for spell_id, _ in out_of_combat]
        assert spell_ids == ["light"]
        assert "nonexistent_spell" not in spell_ids

    def test_shield_included_as_utility(self, wizard_with_mixed_spells, data_loader):
        """Test that Shield (reaction, no damage) is included as utility"""
        spells_data = data_loader.load_spells()
        out_of_combat = wizard_with_mixed_spells.get_out_of_combat_spells(spells_data)

        spell_ids = [spell_id for spell_id, _ in out_of_combat]
        # Shield has no attack and no damage, so it's utility
        assert "shield" in spell_ids
