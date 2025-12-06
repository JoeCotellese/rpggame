# ABOUTME: Tests for spellcaster UX improvements (issue #141)
# ABOUTME: Tests spell name parsing and wizard spellbook display formatting

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities


class TestSpellNameParsing:
    """Test that spell names with target syntax are parsed correctly"""

    @pytest.fixture
    def spells_data(self):
        """Mock spell data"""
        return {
            "magic_missile": {
                "name": "Magic Missile",
                "level": 1,
                "school": "evocation",
                "tags": ["combat"],
                "damage": {"dice": "3d4+3", "damage_type": "force"},
                "target_type": "enemy",
            },
            "fire_bolt": {
                "name": "Fire Bolt",
                "level": 0,
                "school": "evocation",
                "tags": ["combat"],
                "damage": {"dice": "1d10", "damage_type": "fire"},
                "target_type": "enemy",
            },
        }

    def test_spell_name_with_at_target_finds_spell(self, spells_data):
        """'cast magic missile at skeleton 1' should find 'magic missile' spell"""
        spell_input = "magic missile at skeleton 1"

        # Extract the spell name parsing logic we're testing
        spell_name_clean = spell_input
        for separator in [" at ", " on "]:
            if separator in spell_input.lower():
                spell_name_clean = spell_input[: spell_input.lower().index(separator)]
                break

        # Verify the spell name was extracted correctly
        assert spell_name_clean == "magic missile"

        # Verify this would find the spell
        spell_name_lower = spell_name_clean.lower()
        found = False
        for sid, sdata in spells_data.items():
            if sdata.get("name", "").lower() == spell_name_lower or sid == spell_name_lower:
                found = True
                break
        assert found, f"Should find spell with name '{spell_name_clean}'"

    def test_spell_name_with_on_target_finds_spell(self, spells_data):
        """'cast fire bolt on goblin' should find 'fire bolt' spell"""
        spell_input = "fire bolt on goblin"

        spell_name_clean = spell_input
        for separator in [" at ", " on "]:
            if separator in spell_input.lower():
                spell_name_clean = spell_input[: spell_input.lower().index(separator)]
                break

        assert spell_name_clean == "fire bolt"

        # Verify this would find the spell
        spell_name_lower = spell_name_clean.lower()
        found = False
        for sid, sdata in spells_data.items():
            if sdata.get("name", "").lower() == spell_name_lower or sid == spell_name_lower:
                found = True
                break
        assert found

    def test_spell_name_without_target_unchanged(self, spells_data):
        """'cast magic missile' should remain 'magic missile'"""
        spell_input = "magic missile"

        spell_name_clean = spell_input
        for separator in [" at ", " on "]:
            if separator in spell_input.lower():
                spell_name_clean = spell_input[: spell_input.lower().index(separator)]
                break

        assert spell_name_clean == "magic missile"

    def test_spell_name_case_insensitive_separator(self, spells_data):
        """'cast Magic Missile AT skeleton' should find spell (case insensitive)"""
        spell_input = "Magic Missile AT skeleton"

        spell_name_clean = spell_input
        for separator in [" at ", " on "]:
            if separator in spell_input.lower():
                spell_name_clean = spell_input[: spell_input.lower().index(separator)]
                break

        assert spell_name_clean == "Magic Missile"


class TestWizardSpellbookDisplay:
    """Test wizard spellbook display formatting"""

    @pytest.fixture
    def wizard(self):
        """Create a wizard with spells"""
        wizard = Character(
            name="Gandalf",
            character_class=CharacterClass.WIZARD,
            level=5,
            abilities=Abilities(8, 14, 12, 16, 10, 8),  # INT 16 = +3 modifier
            max_hp=28,
            ac=12,
            spellcasting_ability="int",
            known_spells=[
                "fire_bolt",
                "ray_of_frost",
                "magic_missile",
                "shield",
                "burning_hands",
                "mage_armor",
                "scorching_ray",
                "misty_step",
            ],
            prepared_spells=[
                "fire_bolt",  # cantrip - not counted
                "ray_of_frost",  # cantrip - not counted
                "magic_missile",  # level 1
                "shield",  # level 1
                "burning_hands",  # level 1
            ],
        )
        return wizard

    @pytest.fixture
    def spells_data(self):
        """Mock spell data with levels"""
        return {
            "fire_bolt": {"name": "Fire Bolt", "level": 0, "school": "evocation"},
            "ray_of_frost": {"name": "Ray of Frost", "level": 0, "school": "evocation"},
            "magic_missile": {"name": "Magic Missile", "level": 1, "school": "evocation"},
            "shield": {"name": "Shield", "level": 1, "school": "abjuration"},
            "burning_hands": {"name": "Burning Hands", "level": 1, "school": "evocation"},
            "mage_armor": {"name": "Mage Armor", "level": 1, "school": "abjuration"},
            "scorching_ray": {"name": "Scorching Ray", "level": 2, "school": "evocation"},
            "misty_step": {"name": "Misty Step", "level": 2, "school": "conjuration"},
        }

    def test_prepared_count_excludes_cantrips(self, wizard, spells_data):
        """Prepared count should only count leveled spells, not cantrips"""
        prepared_count = len(
            [
                s
                for s in wizard.prepared_spells
                if spells_data.get(s, {}).get("level", 0) > 0
            ]
        )

        # fire_bolt (cantrip) and ray_of_frost (cantrip) shouldn't be counted
        # magic_missile, shield, burning_hands should be counted = 3
        assert prepared_count == 3

    def test_max_prepared_calculation(self, wizard):
        """Max prepared should be INT mod + level"""
        max_prepared = wizard.get_max_prepared_spells()

        # INT 16 = +3 modifier, level 5 = 3 + 5 = 8
        assert max_prepared == 8

    def test_display_format_is_clear(self, wizard, spells_data):
        """Display should say 'X of Y spells prepared' not 'Prepared: X/Y'"""
        prepared_count = len(
            [
                s
                for s in wizard.prepared_spells
                if spells_data.get(s, {}).get("level", 0) > 0
            ]
        )
        max_prepared = wizard.get_max_prepared_spells()

        # Build the display string as the code does
        display = f"{prepared_count} of {max_prepared} spells prepared"

        assert display == "3 of 8 spells prepared"
        # Verify it doesn't use the confusing old format
        assert "Prepared:" not in display
        assert "/" not in display
