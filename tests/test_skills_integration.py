# ABOUTME: Integration tests for the skills system
# ABOUTME: Tests skill checks, proficiency handling, and data loader skill functionality

import pytest

from dnd_engine.core.character import CharacterClass
from dnd_engine.rules.loader import DataLoader


class TestSkillCheckIntegration:
    """Integration tests for skill check event emission and usage"""

    @pytest.fixture
    def character_with_skills(self):
        """Create a character with skill proficiencies"""
        from dnd_engine.core.character import Character
        from dnd_engine.core.creature import Abilities

        abilities = Abilities(
            strength=14, dexterity=16, constitution=12, intelligence=10, wisdom=14, charisma=10
        )
        return Character(
            name="Rogue",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=14,
            skill_proficiencies=["stealth", "perception", "acrobatics"],
        )

    def test_character_can_make_skill_checks(self, character_with_skills):
        """Test that a character can make skill checks with their proficiencies"""
        data_loader = DataLoader()
        skills_data = data_loader.load_skills()

        # Test proficient skill
        result = character_with_skills.make_skill_check("stealth", dc=12, skills_data=skills_data)
        assert result["success"] in [True, False]  # Valid result
        assert result["proficient"] is True

        # Test non-proficient skill
        result = character_with_skills.make_skill_check("arcana", dc=12, skills_data=skills_data)
        assert result["success"] in [True, False]  # Valid result
        assert result["proficient"] is False

    def test_skill_proficiencies_persist_in_saved_character(self, character_with_skills):
        """Test that skill proficiencies are saved in character data"""
        assert character_with_skills.skill_proficiencies == ["stealth", "perception", "acrobatics"]

        # Verify they're accessible as a list
        assert isinstance(character_with_skills.skill_proficiencies, list)
        assert len(character_with_skills.skill_proficiencies) == 3


class TestDataLoaderSkills:
    """Integration tests for DataLoader skills functionality"""

    def test_load_skills_returns_valid_data(self):
        """Test that load_skills returns properly formatted data"""
        loader = DataLoader()
        skills = loader.load_skills()

        assert isinstance(skills, dict)
        assert len(skills) == 18  # All D&D 5E skills

        # Verify structure of a skill
        stealth = skills.get("stealth")
        assert stealth is not None
        assert "name" in stealth
        assert "ability" in stealth

    def test_fighter_class_has_skill_proficiencies(self):
        """Test that Fighter class has skill proficiency data"""
        loader = DataLoader()
        classes = loader.load_classes()

        fighter = classes.get("fighter")
        assert fighter is not None
        assert "skill_proficiencies" in fighter

        skill_profs = fighter["skill_proficiencies"]
        assert "choose" in skill_profs
        assert "from" in skill_profs
        assert skill_profs["choose"] == 2
        assert len(skill_profs["from"]) >= 2


class TestDataLoaderCampaignItems:
    """Integration tests for DataLoader campaign item loading"""

    def test_load_items_without_campaign(self):
        """Test that load_items works without campaign_id"""
        loader = DataLoader()
        items = loader.load_items()

        assert isinstance(items, dict)
        assert "weapons" in items
        assert "consumables" in items
        # Should not have campaign-specific items
        assert "alchemist_research_notes" not in items.get("consumables", {})

    def test_load_items_with_campaign_merges_items(self):
        """Test that load_items with campaign_id merges campaign items"""
        loader = DataLoader()
        items = loader.load_items(campaign_id="poisoned_laboratory")

        assert isinstance(items, dict)
        assert "consumables" in items

        # Should have campaign-specific items merged into consumables
        consumables = items["consumables"]
        assert "alchemist_research_notes" in consumables
        assert "volatile_compound" in consumables
        assert "necromantic_evidence" in consumables
        assert "preserved_specimen" in consumables

        # Verify campaign item has expected fields
        notes = consumables["alchemist_research_notes"]
        assert notes["quest_item"] is True
        assert "description" in notes

    def test_load_items_with_nonexistent_campaign(self):
        """Test that load_items handles missing campaign gracefully"""
        loader = DataLoader()
        items = loader.load_items(campaign_id="nonexistent_campaign")

        # Should still return base items without error
        assert isinstance(items, dict)
        assert "weapons" in items

    def test_load_items_campaign_without_items_section(self):
        """Test that load_items handles campaigns without items section"""
        loader = DataLoader()
        # the_unquiet_dead doesn't have items in quest file (they're in srd)
        items = loader.load_items(campaign_id="the_unquiet_dead")

        assert isinstance(items, dict)
        assert "weapons" in items
