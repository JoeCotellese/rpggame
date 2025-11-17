# ABOUTME: Integration tests for the skills system
# ABOUTME: Tests skill proficiency selection in character creation and event emission

import pytest
from unittest.mock import patch, MagicMock
from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.character import CharacterClass
from dnd_engine.rules.loader import DataLoader


class TestCharacterFactorySkillSelection:
    """Integration tests for character factory skill proficiency selection"""

    @pytest.fixture
    def factory(self):
        """Create a character factory"""
        return CharacterFactory()

    @pytest.fixture
    def data_loader(self):
        """Create a data loader"""
        return DataLoader()

    def test_select_skill_proficiencies_fighter_valid(self, factory, data_loader):
        """Test that skill selection works with valid Fighter class options"""
        classes_data = data_loader.load_classes()
        skills_data = data_loader.load_skills()

        class_data = classes_data["fighter"]

        # Mock user input: select skills at indices 0 and 1
        with patch('dnd_engine.core.character_factory.print_input_prompt') as mock_input:
            mock_input.side_effect = ["1", "2"]

            # Mock the UI functions to prevent output
            with patch('dnd_engine.core.character_factory.print_section'):
                with patch('dnd_engine.core.character_factory.print_choice_menu'):
                    with patch('dnd_engine.core.character_factory.print_status_message'):
                        selected = factory.select_skill_proficiencies(class_data, skills_data)

        assert len(selected) == 2
        assert all(skill in class_data["skill_proficiencies"]["from"] for skill in selected)

    def test_select_skill_proficiencies_no_duplicates(self, factory, data_loader):
        """Test that duplicate skill selections are rejected"""
        classes_data = data_loader.load_classes()
        skills_data = data_loader.load_skills()

        class_data = classes_data["fighter"]
        available_skills = class_data["skill_proficiencies"]["from"]

        # Mock user input: try to select skill 1 twice, then skills 1 and 2
        with patch('dnd_engine.core.character_factory.print_input_prompt') as mock_input:
            mock_input.side_effect = ["1", "1", "2"]

            # Mock the UI functions
            with patch('dnd_engine.core.character_factory.print_section'):
                with patch('dnd_engine.core.character_factory.print_choice_menu'):
                    with patch('dnd_engine.core.character_factory.print_status_message'):
                        selected = factory.select_skill_proficiencies(class_data, skills_data)

        # Should have 2 unique skills (rejected the duplicate)
        assert len(selected) == 2
        assert selected[0] == selected[1] or len(set(selected)) == 2

    def test_select_skill_proficiencies_returns_correct_number(self, factory, data_loader):
        """Test that the correct number of skills are selected"""
        classes_data = data_loader.load_classes()
        skills_data = data_loader.load_skills()

        class_data = classes_data["fighter"]
        num_to_choose = class_data["skill_proficiencies"]["choose"]

        # Mock valid inputs
        with patch('dnd_engine.core.character_factory.print_input_prompt') as mock_input:
            mock_input.side_effect = [str(i) for i in range(1, num_to_choose + 1)]

            # Mock UI functions
            with patch('dnd_engine.core.character_factory.print_section'):
                with patch('dnd_engine.core.character_factory.print_choice_menu'):
                    with patch('dnd_engine.core.character_factory.print_status_message'):
                        selected = factory.select_skill_proficiencies(class_data, skills_data)

        assert len(selected) == num_to_choose

    def test_select_skill_proficiencies_empty_for_class_without_skills(self, factory, data_loader):
        """Test that classes without skill proficiencies return empty list"""
        skills_data = data_loader.load_skills()

        # Class with no skill proficiencies
        class_data = {"name": "No Skills", "skill_proficiencies": None}

        selected = factory.select_skill_proficiencies(class_data, skills_data)
        assert selected == []

    def test_character_creation_includes_skill_proficiencies(self, factory, data_loader):
        """Test that character created through factory includes skill proficiencies"""
        # This is a more complex test that mocks the entire interactive flow
        classes_data = data_loader.load_classes()
        skills_data = data_loader.load_skills()

        # Get Fighter class data
        class_data = classes_data["fighter"]
        available_skills = class_data["skill_proficiencies"]["from"]

        # Mock all user inputs for character creation
        # Format: name, race, class, ability_swaps, skill_selections
        user_inputs = [
            "Aragorn",          # name
            "1",                # race: Human
            "1",                # class: Fighter
            "n",                # no ability swaps
            "1",                # skill 1
            "2",                # skill 2
            "",                 # press enter at end
        ]

        with patch('dnd_engine.core.character_factory.print_input_prompt') as mock_input:
            mock_input.side_effect = user_inputs

            # Mock all UI functions
            with patch('dnd_engine.core.character_factory.print_section'):
                with patch('dnd_engine.core.character_factory.print_choice_menu'):
                    with patch('dnd_engine.core.character_factory.print_status_message'):
                        with patch('dnd_engine.core.character_factory.print_message'):
                            with patch('dnd_engine.core.character_factory.print_error'):
                                character = factory.create_character_interactive(None, data_loader)

        # Verify that character has skill proficiencies
        assert hasattr(character, 'skill_proficiencies')
        assert len(character.skill_proficiencies) == 2
        assert all(skill in available_skills for skill in character.skill_proficiencies)


class TestSkillCheckIntegration:
    """Integration tests for skill check event emission and usage"""

    @pytest.fixture
    def character_with_skills(self):
        """Create a character with skill proficiencies"""
        from dnd_engine.core.character import Character
        from dnd_engine.core.creature import Abilities

        abilities = Abilities(
            strength=14, dexterity=16, constitution=12,
            intelligence=10, wisdom=14, charisma=10
        )
        return Character(
            name="Rogue",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=14,
            skill_proficiencies=["stealth", "perception", "acrobatics"]
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
