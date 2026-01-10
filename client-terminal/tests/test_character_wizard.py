"""Unit tests for CharacterCreationWizard"""

from unittest.mock import MagicMock, patch

import pytest

from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.dice import DiceRoller
from dnd_engine.rules.loader import DataLoader
from terminal_client.ui.character_wizard import CharacterCreationWizard, CreationPath


class TestCharacterCreationWizard:
    """Unit tests for CharacterCreationWizard class"""

    @pytest.fixture
    def wizard(self):
        """Create wizard instance with seeded dice roller"""
        dice_roller = DiceRoller(seed=42)
        factory = CharacterFactory(dice_roller=dice_roller)
        return CharacterCreationWizard(
            character_factory=factory, data_loader=DataLoader(), dice_roller=dice_roller
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
            for _template_id, template in wizard.templates_data.items():
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
            "charisma": 8,
        }

        # Should not raise exception
        with patch("dnd_engine.ui.character_wizard.print_message"):
            wizard._display_abilities(abilities)

    def test_display_abilities_with_bonuses(self, wizard):
        """Test ability display with before/after comparison"""
        before = {
            "strength": 14,
            "dexterity": 12,
            "constitution": 13,
            "intelligence": 10,
            "wisdom": 12,
            "charisma": 8,
        }

        after = {
            "strength": 16,  # +2 from racial bonus
            "dexterity": 12,
            "constitution": 15,  # +2 from racial bonus
            "intelligence": 10,
            "wisdom": 12,
            "charisma": 8,
        }

        # Should not raise exception
        with patch("dnd_engine.ui.character_wizard.print_message"):
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
        for ability in [
            "strength",
            "dexterity",
            "constitution",
            "intelligence",
            "wisdom",
            "charisma",
        ]:
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
        """Test ability swapping functionality with questionary select"""
        wizard.abilities = {
            "strength": 16,
            "dexterity": 14,
            "constitution": 15,
            "intelligence": 10,
            "wisdom": 12,
            "charisma": 8,
        }

        original_str = wizard.abilities["strength"]
        original_dex = wizard.abilities["dexterity"]

        # Mock questionary.select for swap
        mock_select = MagicMock()
        mock_select.ask.side_effect = ["strength", "dexterity"]

        with patch("dnd_engine.ui.character_wizard.questionary.select", return_value=mock_select):
            with patch("dnd_engine.ui.character_wizard.print_status_message"):
                result = wizard._swap_abilities_interactive()

        # Should swap successfully
        assert result is True
        assert wizard.abilities["strength"] == original_dex
        assert wizard.abilities["dexterity"] == original_str

    def test_swap_abilities_cancelled(self, wizard):
        """Test ability swap cancellation"""
        wizard.abilities = {
            "strength": 16,
            "dexterity": 14,
            "constitution": 15,
            "intelligence": 10,
            "wisdom": 12,
            "charisma": 8,
        }

        # Mock questionary.select returning None (cancelled)
        mock_select = MagicMock()
        mock_select.ask.return_value = None

        with patch("dnd_engine.ui.character_wizard.questionary.select", return_value=mock_select):
            result = wizard._swap_abilities_interactive()

        # Should fail (cancelled)
        assert result is False

    def test_create_from_template_sets_state(self, wizard):
        """Test that creating from template sets wizard state correctly"""
        # Skip if no templates available
        if not wizard.templates_data:
            pytest.skip("No templates available")

        template_id = list(wizard.templates_data.keys())[0]
        template = wizard.templates_data[template_id]

        # Mock questionary.text for name input
        mock_text = MagicMock()
        mock_text.ask.return_value = "Test Character"

        with patch("dnd_engine.ui.character_wizard.questionary.text", return_value=mock_text):
            with patch("dnd_engine.ui.character_wizard.console.print"):
                with patch("dnd_engine.ui.character_wizard.print_status_message"):
                    # Mock finalize to return None (we just want to test state setting)
                    with patch.object(wizard, "_finalize_character", return_value=None):
                        wizard._create_from_template(template_id)

        # Check state was set from template
        assert wizard.race == template["race"]
        assert wizard.character_class == template["class"]
        assert wizard.name == "Test Character"
        assert wizard.abilities is not None

        # Abilities should include racial bonuses
        for ability, base_score in template["abilities"].items():
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
            "charisma": 8,
        }
        wizard.skill_proficiencies = ["athletics", "intimidation"]
        wizard.level = 1

        # Should not raise exception
        with patch("dnd_engine.ui.character_wizard.console.print"):
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
            "charisma": 8,
        }
        wizard.skill_proficiencies = ["athletics", "intimidation"]
        wizard.expertise_skills = []
        wizard.selected_spells = []
        wizard.level = 1

        # Create character
        with patch("dnd_engine.ui.character_wizard.console.status"):
            with patch("dnd_engine.ui.character_wizard.print_status_message"):
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
            "charisma": 14,
        }
        wizard.skill_proficiencies = ["stealth", "sleight_of_hand", "deception", "perception"]
        wizard.expertise_skills = ["stealth", "sleight_of_hand"]
        wizard.selected_spells = []
        wizard.level = 1

        # Create character
        with patch("dnd_engine.ui.character_wizard.console.status"):
            with patch("dnd_engine.ui.character_wizard.print_status_message"):
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
            wizard1.race != wizard2.race
            or wizard1.character_class != wizard2.character_class
            or wizard1.abilities != wizard2.abilities
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
            "charisma": 8,
        }

        # Should display without error
        with patch("dnd_engine.ui.character_wizard.console.print"):
            with patch("dnd_engine.ui.character_wizard.console.input"):
                with patch("dnd_engine.ui.character_wizard.print_section"):
                    wizard._show_progress_summary()

    def test_step_choose_path_custom(self, wizard):
        """Test choosing custom creation path with questionary"""
        mock_select = MagicMock()
        mock_select.ask.return_value = CreationPath.CUSTOM

        with patch("dnd_engine.ui.character_wizard.questionary.select", return_value=mock_select):
            with patch("dnd_engine.ui.character_wizard.print_section"):
                with patch("dnd_engine.ui.character_wizard.console.print"):
                    result = wizard._step_choose_path()

        assert result is True
        assert wizard.creation_path == CreationPath.CUSTOM

    def test_step_choose_path_cancel(self, wizard):
        """Test cancelling path selection"""
        mock_select = MagicMock()
        mock_select.ask.return_value = None

        with patch("dnd_engine.ui.character_wizard.questionary.select", return_value=mock_select):
            with patch("dnd_engine.ui.character_wizard.print_section"):
                with patch("dnd_engine.ui.character_wizard.console.print"):
                    result = wizard._step_choose_path()

        assert result is False
        assert wizard.creation_path is None

    def test_custom_step_race(self, wizard):
        """Test race selection step with questionary"""
        mock_select = MagicMock()
        mock_select.ask.return_value = "human"

        mock_nav = MagicMock()
        mock_nav.ask.return_value = "next"

        with patch(
            "dnd_engine.ui.character_wizard.questionary.select",
            side_effect=[mock_select, mock_nav],
        ):
            with patch("dnd_engine.ui.character_wizard.print_status_message"):
                with patch("dnd_engine.ui.character_wizard.console.print"):
                    result = wizard._custom_step_race()

        assert wizard.race == "human"
        assert result == "next"

    def test_custom_step_class(self, wizard):
        """Test class selection step with questionary"""
        mock_select = MagicMock()
        mock_select.ask.return_value = "fighter"

        mock_nav = MagicMock()
        mock_nav.ask.return_value = "next"

        with patch(
            "dnd_engine.ui.character_wizard.questionary.select",
            side_effect=[mock_select, mock_nav],
        ):
            with patch("dnd_engine.ui.character_wizard.print_status_message"):
                with patch("dnd_engine.ui.character_wizard.console.print"):
                    result = wizard._custom_step_class()

        assert wizard.character_class == "fighter"
        assert result == "next"

    def test_custom_step_name(self, wizard):
        """Test name input step (now last step) with questionary"""
        wizard.race = "human"
        wizard.character_class = "fighter"

        mock_text = MagicMock()
        mock_text.ask.return_value = "Test Hero"

        mock_nav = MagicMock()
        mock_nav.ask.return_value = "next"

        with patch("dnd_engine.ui.character_wizard.questionary.text", return_value=mock_text):
            with patch(
                "dnd_engine.ui.character_wizard.questionary.select",
                return_value=mock_nav,
            ):
                with patch("dnd_engine.ui.character_wizard.print_status_message"):
                    with patch("dnd_engine.ui.character_wizard.console.print"):
                        result = wizard._custom_step_name()

        assert wizard.name == "Test Hero"
        assert result == "next"

    def test_select_skills_questionary(self, wizard):
        """Test skill selection with questionary checkbox"""
        class_data = wizard.classes_data["fighter"]

        mock_checkbox = MagicMock()
        mock_checkbox.ask.return_value = ["athletics", "intimidation"]

        with patch(
            "dnd_engine.ui.character_wizard.questionary.checkbox",
            return_value=mock_checkbox,
        ):
            with patch("dnd_engine.ui.character_wizard.print_status_message"):
                result = wizard._select_skills_questionary(class_data, wizard.skills_data)

        assert result == ["athletics", "intimidation"]
        assert len(result) == 2

    def test_display_progress_bar(self, wizard):
        """Test progress bar display during wizard steps"""
        steps = [
            ("Race", None),
            ("Class", None),
            ("Abilities", None),
            ("Skills", None),
            ("Name", None),
        ]

        # Should not raise exception for any step
        with patch("dnd_engine.ui.character_wizard.console.print"):
            for i in range(len(steps)):
                wizard._display_progress_bar(i, len(steps), steps)

    def test_finalize_character_confirm(self, wizard):
        """Test confirming character creation with questionary"""
        wizard.name = "Test Character"
        wizard.race = "human"
        wizard.character_class = "fighter"
        wizard.abilities = {
            "strength": 16,
            "dexterity": 14,
            "constitution": 15,
            "intelligence": 10,
            "wisdom": 12,
            "charisma": 8,
        }
        wizard.skill_proficiencies = ["athletics", "intimidation"]
        wizard.expertise_skills = []
        wizard.selected_spells = []
        wizard.level = 1

        mock_select = MagicMock()
        mock_select.ask.return_value = "confirm"

        with patch("dnd_engine.ui.character_wizard.questionary.select", return_value=mock_select):
            with patch("dnd_engine.ui.character_wizard.console.print"):
                with patch("dnd_engine.ui.character_wizard.console.status"):
                    with patch("dnd_engine.ui.character_wizard.print_section"):
                        with patch("dnd_engine.ui.character_wizard.print_status_message"):
                            character = wizard._finalize_character()

        assert character is not None
        assert character.name == "Test Character"
