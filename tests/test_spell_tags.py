# ABOUTME: Unit tests for spell tag-based filtering system
# ABOUTME: Tests get_castable_spells and get_out_of_combat_spells tag logic

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities


@pytest.fixture
def wizard():
    """Create a level 1 wizard for testing"""
    return Character(
        name="Test Wizard",
        character_class=CharacterClass.WIZARD,
        level=1,
        abilities=Abilities(
            strength=8, dexterity=14, constitution=12, intelligence=16, wisdom=10, charisma=10
        ),
        max_hp=8,
        ac=12,
        spellcasting_ability="int",
        known_spells=[
            "fire_bolt",  # combat
            "light",  # utility
            "mage_hand",  # utility
            "magic_missile",  # combat
            "mage_armor",  # combat + buff
            "detect_magic",  # utility + ritual
            "sleep",  # combat + control
        ],
        prepared_spells=[
            "fire_bolt",
            "light",
            "mage_hand",
            "magic_missile",
            "mage_armor",
            "detect_magic",
            "sleep",
        ],
    )


@pytest.fixture
def spells_data():
    """Spell data with tags for testing"""
    return {
        "fire_bolt": {
            "id": "fire_bolt",
            "name": "Fire Bolt",
            "level": 0,
            "target_type": "enemy",
            "tags": ["combat", "damage"],
        },
        "light": {
            "id": "light",
            "name": "Light",
            "level": 0,
            "target_type": "any",
            "tags": ["utility"],
        },
        "mage_hand": {
            "id": "mage_hand",
            "name": "Mage Hand",
            "level": 0,
            "target_type": "self",
            "tags": ["utility"],
        },
        "magic_missile": {
            "id": "magic_missile",
            "name": "Magic Missile",
            "level": 1,
            "target_type": "enemy",
            "tags": ["combat", "damage"],
        },
        "mage_armor": {
            "id": "mage_armor",
            "name": "Mage Armor",
            "level": 1,
            "target_type": "ally",
            "tags": ["combat", "buff", "defense"],
        },
        "detect_magic": {
            "id": "detect_magic",
            "name": "Detect Magic",
            "level": 1,
            "target_type": "self",
            "tags": ["utility", "ritual"],
        },
        "sleep": {
            "id": "sleep",
            "name": "Sleep",
            "level": 1,
            "target_type": "area",
            "tags": ["combat", "control", "aoe"],
        },
    }


class TestSpellTagFiltering:
    """Tests for tag-based spell filtering"""

    def test_get_castable_spells_returns_only_combat_spells(self, wizard, spells_data):
        """Combat spells should include all spells with 'combat' tag"""
        castable = wizard.get_castable_spells(spells_data)
        spell_names = [s[1]["name"] for s in castable]

        # Should include all combat-tagged spells
        assert "Fire Bolt" in spell_names
        assert "Magic Missile" in spell_names
        assert "Mage Armor" in spell_names
        assert "Sleep" in spell_names

        # Should NOT include utility-only spells
        assert "Light" not in spell_names
        assert "Mage Hand" not in spell_names
        assert "Detect Magic" not in spell_names

    def test_get_castable_spells_count(self, wizard, spells_data):
        """Should return exactly 4 combat spells"""
        castable = wizard.get_castable_spells(spells_data)
        assert len(castable) == 4

    def test_get_castable_spells_sorted_by_level(self, wizard, spells_data):
        """Combat spells should be sorted by level (cantrips first)"""
        castable = wizard.get_castable_spells(spells_data)
        levels = [s[1]["level"] for s in castable]

        # Cantrips (level 0) should come before level 1 spells
        assert levels == sorted(levels)
        assert levels[0] == 0  # First spell is cantrip

    def test_get_out_of_combat_spells_includes_utility(self, wizard, spells_data):
        """Out-of-combat should include utility, healing, ritual, and buff spells"""
        out_of_combat = wizard.get_out_of_combat_spells(spells_data)
        spell_names = [s[1]["name"] for s in out_of_combat]

        # Should include utility spells
        assert "Light" in spell_names
        assert "Mage Hand" in spell_names
        assert "Detect Magic" in spell_names

        # Should include buffs (useful before combat)
        assert "Mage Armor" in spell_names

        # Should NOT include pure combat spells
        assert "Fire Bolt" not in spell_names
        assert "Magic Missile" not in spell_names
        assert "Sleep" not in spell_names

    def test_spell_without_tags_not_included(self, wizard):
        """Spells without tags should not be included in any list"""
        spells_without_tags = {
            "test_spell": {
                "id": "test_spell",
                "name": "Test Spell",
                "level": 1,
                # No tags field
            }
        }

        wizard.prepared_spells = ["test_spell"]

        castable = wizard.get_castable_spells(spells_without_tags)
        out_of_combat = wizard.get_out_of_combat_spells(spells_without_tags)

        assert len(castable) == 0
        assert len(out_of_combat) == 0

    def test_spell_with_empty_tags_not_included(self, wizard):
        """Spells with empty tags list should not be included"""
        spells_empty_tags = {
            "test_spell": {"id": "test_spell", "name": "Test Spell", "level": 1, "tags": []}
        }

        wizard.prepared_spells = ["test_spell"]

        castable = wizard.get_castable_spells(spells_empty_tags)
        out_of_combat = wizard.get_out_of_combat_spells(spells_empty_tags)

        assert len(castable) == 0
        assert len(out_of_combat) == 0

    def test_multiple_tags_work_correctly(self, wizard, spells_data):
        """Spells with multiple tags should appear in appropriate lists"""
        # Mage Armor has tags: ["combat", "buff", "defense"]
        # Should appear in combat list (has "combat" tag)
        castable = wizard.get_castable_spells(spells_data)
        castable_names = [s[1]["name"] for s in castable]
        assert "Mage Armor" in castable_names

        # Should also appear in out-of-combat list (has "buff" tag)
        out_of_combat = wizard.get_out_of_combat_spells(spells_data)
        out_of_combat_names = [s[1]["name"] for s in out_of_combat]
        assert "Mage Armor" in out_of_combat_names

    def test_ritual_tag_includes_in_out_of_combat(self, wizard, spells_data):
        """Spells with 'ritual' tag should appear in out-of-combat list"""
        out_of_combat = wizard.get_out_of_combat_spells(spells_data)
        spell_names = [s[1]["name"] for s in out_of_combat]

        assert "Detect Magic" in spell_names

    def test_control_spell_only_in_combat(self, wizard, spells_data):
        """Control spells with 'combat' tag should only appear in combat list"""
        # Sleep has tags: ["combat", "control", "aoe"]
        castable = wizard.get_castable_spells(spells_data)
        castable_names = [s[1]["name"] for s in castable]
        assert "Sleep" in castable_names

        # Should NOT appear in out-of-combat (no utility/healing/ritual/buff tags)
        out_of_combat = wizard.get_out_of_combat_spells(spells_data)
        out_of_combat_names = [s[1]["name"] for s in out_of_combat]
        assert "Sleep" not in out_of_combat_names

    def test_empty_prepared_spells_returns_empty_lists(self, wizard, spells_data):
        """With no prepared spells, both methods should return empty lists"""
        wizard.prepared_spells = []

        castable = wizard.get_castable_spells(spells_data)
        out_of_combat = wizard.get_out_of_combat_spells(spells_data)

        assert len(castable) == 0
        assert len(out_of_combat) == 0

    def test_spell_not_in_data_ignored(self, wizard, spells_data):
        """Spells in prepared_spells but not in spells_data should be ignored"""
        wizard.prepared_spells = ["fire_bolt", "nonexistent_spell", "magic_missile"]

        castable = wizard.get_castable_spells(spells_data)
        spell_names = [s[1]["name"] for s in castable]

        # Should only include the 2 valid spells
        assert len(castable) == 2
        assert "Fire Bolt" in spell_names
        assert "Magic Missile" in spell_names
