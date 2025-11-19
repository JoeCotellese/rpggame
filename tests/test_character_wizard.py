"""Unit tests for CharacterCreationWizard"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from dnd_engine.ui.character_wizard import CharacterCreationWizard, CreationPath
from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.dice import DiceRoller
from dnd_engine.rules.loader import DataLoader


class TestCharacterCreationWizard:
    """Unit tests for CharacterCreationWizard class"""

    @pytest.fixture
    def wizard(self):
        """Create wizard instance with seeded dice roller"""
        dice_roller = DiceRoller(seed=42)
        factory = CharacterFactory(dice_roller=dice_roller)
        return CharacterCreationWizard(
            character_factory=factory,
            data_loader=DataLoader(),
            dice_roller=dice_roller
        )

    def test_wizard_initialization(self, wizard):
        """Test wizard initializes with correct state"""
        assert wizard.creation_path is None
        assert wizard.name is None
        assert wizard.race is None
        assert wizard.character_class is None
        assert wizard.abilities is None
        assert wizard.level == 1
        assert wizard.skill_proficiencies == []
        assert wizard.expertise_skills == []

    def test_load_templates(self, wizard):
        """Test template loading"""
        # Should load templates from JSON
        assert isinstance(wizard.templates_data, dict)

        # Should have some templates (if file exists)
        if wizard.templates_data:
            # Check template structure
            for template_id, template in wizard.templates_data.items():
                assert "name" in template
                assert "description" in template
                assert "race" in template
                assert "class" in template
                assert "abilities" in template
                assert isinstance(template["abilities"], dict)

    def test_display_abilities(self, wizard):
        """Test ability score display formatting"""
        abilities = {
            "strength": 16,
            "dexterity": 14,
            "constitution": 15,
            "intelligence": 10,
            "wisdom": 12,
            "charisma": 8
        }

        # Should not raise exception
        with patch('dnd_engine.ui.character_wizard.print_message'):
            wizard._display_abilities(abilities)

    def test_display_abilities_with_bonuses(self, wizard):
        """Test ability display with before/after comparison"""
        before = {
            "strength": 14,
            "dexterity": 12,
            "constitution": 13,
            "intelligence": 10,
            "wisdom": 12,
            "charisma": 8
        }

        after = {
            "strength": 16,  # +2 from racial bonus
            "dexterity": 12,
            "constitution": 15,  # +2 from racial bonus
            "intelligence": 10,
            "wisdom": 12,
            "charisma": 8
        }

        # Should not raise exception
        with patch('dnd_engine.ui.character_wizard.print_message'):
            wizard._display_abilities(after, before=before)

    def test_generate_random_character(self, wizard):
        """Test random character generation"""
        wizard._generate_random_character()

        # Should have selected race and class
        assert wizard.race is not None
        assert wizard.character_class is not None
        assert wizard.abilities is not None

        # Should have valid abilities
        assert len(wizard.abilities) == 6
        for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            assert ability in wizard.abilities
            assert isinstance(wizard.abilities[ability], int)
            assert wizard.abilities[ability] > 0

        # Should have selected skills (if class allows)
        assert isinstance(wizard.skill_proficiencies, list)

    def test_generate_random_name(self, wizard):
        """Test random name generation"""
        name = wizard._generate_random_name()

        assert isinstance(name, str)
        assert len(name) > 0
        assert " " in name  # Should have first and last name

    def test_swap_abilities(self, wizard):
        """Test ability swapping functionality"""
        wizard.abilities = {
            "strength": 16,
            "dexterity": 14,
            "constitution": 15,
            "intelligence": 10,
            "wisdom": 12,
            "charisma": 8
        }

        original_str = wizard.abilities["strength"]
        original_dex = wizard.abilities["dexterity"]

        # Mock console input for swap
        with patch('dnd_engine.ui.character_wizard.console.input') as mock_input:
            mock_input.side_effect = ["str", "dex"]

            result = wizard._swap_abilities_interactive()

        # Should swap successfully
        assert result is True
        assert wizard.abilities["strength"] == original_dex
        assert wizard.abilities["dexterity"] == original_str

    def test_swap_abilities_invalid(self, wizard):
        """Test ability swap with invalid ability name"""
        wizard.abilities = {
            "strength": 16,
            "dexterity": 14,
            "constitution": 15,
            "intelligence": 10,
            "wisdom": 12,
            "charisma": 8
        }

        # Mock console input with invalid ability
        with patch('dnd_engine.ui.character_wizard.console.input') as mock_input:
            with patch('dnd_engine.ui.character_wizard.print_error'):
                mock_input.side_effect = ["invalid", "dex"]

                result = wizard._swap_abilities_interactive()

        # Should fail
        assert result is False

    def test_create_from_template_sets_state(self, wizard):
        """Test that creating from template sets wizard state correctly"""
        # Skip if no templates available
        if not wizard.templates_data:
            pytest.skip("No templates available")

        template_id = list(wizard.templates_data.keys())[0]
        template = wizard.templates_data[template_id]

        # Mock console input for name
        with patch('dnd_engine.ui.character_wizard.console.input', return_value="Test Character"):
            with patch('dnd_engine.ui.character_wizard.console.print'):
                with patch('dnd_engine.ui.character_wizard.print_status_message'):
                    # Mock finalize to return None (we just want to test state setting)
                    with patch.object(wizard, '_finalize_character', return_value=None):
                        wizard._create_from_template(template_id)

        # Check state was set from template
        assert wizard.race == template['race']
        assert wizard.character_class == template['class']
        assert wizard.name == "Test Character"
        assert wizard.abilities is not None

        # Abilities should include racial bonuses
        for ability, base_score in template['abilities'].items():
            # May have racial bonus applied
            assert wizard.abilities[ability] >= base_score

    def test_show_character_summary(self, wizard):
        """Test character summary display"""
        # Set up complete wizard state
        wizard.name = "Test Character"
        wizard.race = "human"
        wizard.character_class = "fighter"
        wizard.abilities = {
            "strength": 16,
            "dexterity": 14,
            "constitution": 15,
            "intelligence": 10,
            "wisdom": 12,
            "charisma": 8
        }
        wizard.skill_proficiencies = ["athletics", "intimidation"]
        wizard.level = 1

        # Should not raise exception
        with patch('dnd_engine.ui.character_wizard.console.print'):
            wizard._show_character_summary()

    def test_create_character_from_wizard_state(self, wizard):
        """Test creating final Character object from wizard state"""
        # Set up complete wizard state
        wizard.name = "Test Fighter"
        wizard.race = "human"
        wizard.character_class = "fighter"
        wizard.abilities = {
            "strength": 16,
            "dexterity": 14,
            "constitution": 15,
            "intelligence": 10,
            "wisdom": 12,
            "charisma": 8
        }
        wizard.skill_proficiencies = ["athletics", "intimidation"]
        wizard.expertise_skills = []
        wizard.selected_spells = []
        wizard.level = 1

        # Create character
        with patch('dnd_engine.ui.character_wizard.console.status'):
            with patch('dnd_engine.ui.character_wizard.print_status_message'):
                character = wizard._create_character()

        # Verify character properties
        assert character is not None
        assert character.name == "Test Fighter"
        assert character.level == 1
        assert character.race == "human"
        assert character.abilities.strength == 16
        assert character.abilities.dexterity == 14
        assert character.max_hp > 0
        assert character.ac > 0
        assert "athletics" in character.skill_proficiencies
        assert "intimidation" in character.skill_proficiencies

    def test_create_rogue_with_expertise(self, wizard):
        """Test creating a Rogue character with expertise"""
        wizard.name = "Test Rogue"
        wizard.race = "halfling"
        wizard.character_class = "rogue"
        wizard.abilities = {
            "strength": 8,
            "dexterity": 16,
            "constitution": 12,
            "intelligence": 13,
            "wisdom": 10,
            "charisma": 14
        }
        wizard.skill_proficiencies = ["stealth", "sleight_of_hand", "deception", "perception"]
        wizard.expertise_skills = ["stealth", "sleight_of_hand"]
        wizard.selected_spells = []
        wizard.level = 1

        # Create character
        with patch('dnd_engine.ui.character_wizard.console.status'):
            with patch('dnd_engine.ui.character_wizard.print_status_message'):
                character = wizard._create_character()

        # Verify expertise
        assert character is not None
        assert "stealth" in character.expertise_skills
        assert "sleight_of_hand" in character.expertise_skills
        assert len(character.expertise_skills) == 2

    def test_random_generation_deterministic_with_seed(self):
        """Test that random generation is deterministic with same seed"""
        # Create two wizards with same seed
        dice_roller1 = DiceRoller(seed=100)
        wizard1 = CharacterCreationWizard(dice_roller=dice_roller1)

        dice_roller2 = DiceRoller(seed=100)
        wizard2 = CharacterCreationWizard(dice_roller=dice_roller2)

        # Generate random characters
        wizard1._generate_random_character()
        wizard2._generate_random_character()

        # Should generate identical characters
        assert wizard1.race == wizard2.race
        assert wizard1.character_class == wizard2.character_class
        assert wizard1.abilities == wizard2.abilities

    def test_random_generation_different_with_different_seed(self):
        """Test that random generation differs with different seeds"""
        # Create two wizards with different seeds
        dice_roller1 = DiceRoller(seed=100)
        wizard1 = CharacterCreationWizard(dice_roller=dice_roller1)

        dice_roller2 = DiceRoller(seed=200)
        wizard2 = CharacterCreationWizard(dice_roller=dice_roller2)

        # Generate random characters
        wizard1._generate_random_character()
        wizard2._generate_random_character()

        # Should generate different characters (highly likely)
        # Note: There's a tiny chance they could be identical, but extremely unlikely
        different = (
            wizard1.race != wizard2.race or
            wizard1.character_class != wizard2.character_class or
            wizard1.abilities != wizard2.abilities
        )
        assert different

    def test_creation_path_enum(self):
        """Test CreationPath enum values"""
        assert CreationPath.CUSTOM.value == "custom"
        assert CreationPath.TEMPLATE.value == "template"
        assert CreationPath.RANDOM.value == "random"

    def test_show_progress_summary(self, wizard):
        """Test progress summary display during custom creation"""
        wizard.name = "In Progress Character"
        wizard.race = "mountain_dwarf"
        wizard.character_class = "fighter"
        wizard.abilities = {
            "strength": 16,
            "dexterity": 12,
            "constitution": 15,
            "intelligence": 10,
            "wisdom": 12,
            "charisma": 8
        }

        # Should display without error
        with patch('dnd_engine.ui.character_wizard.console.print'):
            with patch('dnd_engine.ui.character_wizard.console.input'):
                with patch('dnd_engine.ui.character_wizard.print_section'):
                    wizard._show_progress_summary()
