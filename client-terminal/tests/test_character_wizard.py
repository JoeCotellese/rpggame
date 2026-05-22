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
        with patch("terminal_client.ui.character_wizard.print_message"):
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
        with patch("terminal_client.ui.character_wizard.print_message"):
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

        with patch("terminal_client.ui.character_wizard.questionary.select", return_value=mock_select):
            with patch("terminal_client.ui.character_wizard.print_status_message"):
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

        with patch("terminal_client.ui.character_wizard.questionary.select", return_value=mock_select):
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

        with patch("terminal_client.ui.character_wizard.questionary.text", return_value=mock_text):
            with patch("terminal_client.ui.character_wizard.console.print"):
                with patch("terminal_client.ui.character_wizard.print_status_message"):
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
        with patch("terminal_client.ui.character_wizard.console.print"):
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
        with patch("terminal_client.ui.character_wizard.console.status"):
            with patch("terminal_client.ui.character_wizard.print_status_message"):
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
        with patch("terminal_client.ui.character_wizard.console.status"):
            with patch("terminal_client.ui.character_wizard.print_status_message"):
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
        with patch("terminal_client.ui.character_wizard.console.print"):
            with patch("terminal_client.ui.character_wizard.console.input"):
                with patch("terminal_client.ui.character_wizard.print_section"):
                    wizard._show_progress_summary()

    def test_step_choose_path_custom(self, wizard):
        """Test choosing custom creation path with questionary"""
        mock_select = MagicMock()
        mock_select.ask.return_value = CreationPath.CUSTOM

        with patch("terminal_client.ui.character_wizard.questionary.select", return_value=mock_select):
            with patch("terminal_client.ui.character_wizard.print_section"):
                with patch("terminal_client.ui.character_wizard.console.print"):
                    result = wizard._step_choose_path()

        assert result is True
        assert wizard.creation_path == CreationPath.CUSTOM

    def test_step_choose_path_cancel(self, wizard):
        """Test cancelling path selection"""
        mock_select = MagicMock()
        mock_select.ask.return_value = None

        with patch("terminal_client.ui.character_wizard.questionary.select", return_value=mock_select):
            with patch("terminal_client.ui.character_wizard.print_section"):
                with patch("terminal_client.ui.character_wizard.console.print"):
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
            "terminal_client.ui.character_wizard.questionary.select",
            side_effect=[mock_select, mock_nav],
        ):
            with patch("terminal_client.ui.character_wizard.print_status_message"):
                with patch("terminal_client.ui.character_wizard.console.print"):
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
            "terminal_client.ui.character_wizard.questionary.select",
            side_effect=[mock_select, mock_nav],
        ):
            with patch("terminal_client.ui.character_wizard.print_status_message"):
                with patch("terminal_client.ui.character_wizard.console.print"):
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

        with patch("terminal_client.ui.character_wizard.questionary.text", return_value=mock_text):
            with patch(
                "terminal_client.ui.character_wizard.questionary.select",
                return_value=mock_nav,
            ):
                with patch("terminal_client.ui.character_wizard.print_status_message"):
                    with patch("terminal_client.ui.character_wizard.console.print"):
                        result = wizard._custom_step_name()

        assert wizard.name == "Test Hero"
        assert result == "next"

    def test_select_skills_questionary(self, wizard):
        """Test skill selection with questionary checkbox"""
        class_data = wizard.classes_data["fighter"]

        mock_checkbox = MagicMock()
        mock_checkbox.ask.return_value = ["athletics", "intimidation"]

        with patch(
            "terminal_client.ui.character_wizard.questionary.checkbox",
            return_value=mock_checkbox,
        ):
            with patch("terminal_client.ui.character_wizard.print_status_message"):
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
        with patch("terminal_client.ui.character_wizard.console.print"):
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

        with patch("terminal_client.ui.character_wizard.questionary.select", return_value=mock_select):
            with patch("terminal_client.ui.character_wizard.console.print"):
                with patch("terminal_client.ui.character_wizard.console.status"):
                    with patch("terminal_client.ui.character_wizard.print_section"):
                        with patch("terminal_client.ui.character_wizard.print_status_message"):
                            character = wizard._finalize_character()

        assert character is not None
        assert character.name == "Test Character"


class TestCustomStepEquipment:
    """Unit tests for the custom-path Equipment step (issue #382)."""

    @pytest.fixture
    def wizard(self):
        dice_roller = DiceRoller(seed=42)
        factory = CharacterFactory(dice_roller=dice_roller)
        return CharacterCreationWizard(
            character_factory=factory, data_loader=DataLoader(), dice_roller=dice_roller
        )

    def test_wizard_initializes_equipment_option_index_to_zero(self, wizard):
        """Default equipment_option_index should be 0 (Standard Loadout)."""
        assert wizard.equipment_option_index == 0

    def test_custom_step_equipment_records_selection(self, wizard):
        """Selecting option 1 stores its index on the wizard and continues."""
        wizard.character_class = "fighter"

        mock_select = MagicMock()
        mock_select.ask.return_value = 1

        mock_nav = MagicMock()
        mock_nav.ask.return_value = "next"

        with patch(
            "terminal_client.ui.character_wizard.questionary.select",
            side_effect=[mock_select, mock_nav],
        ):
            with patch("terminal_client.ui.character_wizard.print_status_message"):
                with patch("terminal_client.ui.character_wizard.console.print"):
                    result = wizard._custom_step_equipment()

        assert wizard.equipment_option_index == 1
        assert result == "next"

    def test_custom_step_equipment_back_navigation(self, wizard):
        """Back sentinel returns 'back' without setting an option."""
        wizard.character_class = "fighter"
        wizard.equipment_option_index = 0

        mock_select = MagicMock()
        mock_select.ask.return_value = "back"

        with patch(
            "terminal_client.ui.character_wizard.questionary.select", return_value=mock_select
        ):
            with patch("terminal_client.ui.character_wizard.console.print"):
                result = wizard._custom_step_equipment()

        assert result == "back"
        assert wizard.equipment_option_index == 0

    def test_custom_step_equipment_cancel(self, wizard):
        """questionary returning None (Ctrl-C) cancels the step."""
        wizard.character_class = "fighter"

        mock_select = MagicMock()
        mock_select.ask.return_value = None

        with patch(
            "terminal_client.ui.character_wizard.questionary.select", return_value=mock_select
        ):
            with patch("terminal_client.ui.character_wizard.console.print"):
                result = wizard._custom_step_equipment()

        assert result == "cancel"

    def test_custom_step_equipment_no_options_skipped(self, wizard):
        """Classes without starting_equipment_options skip the step silently."""
        # Mutate the in-memory class data to simulate the legacy fallback
        wizard.character_class = "fighter"
        wizard.classes_data["fighter"] = {
            k: v
            for k, v in wizard.classes_data["fighter"].items()
            if k != "starting_equipment_options"
        }

        with patch(
            "terminal_client.ui.character_wizard.questionary.select"
        ) as mock_select_module:
            result = wizard._custom_step_equipment()

        assert result == "next"
        assert wizard.equipment_option_index == 0
        mock_select_module.assert_not_called()


class TestRandomPathEquipment:
    """Random path should pick an equipment option via the seeded RNG."""

    def test_random_picks_equipment_option_in_range(self):
        dice_roller = DiceRoller(seed=42)
        wizard = CharacterCreationWizard(
            character_factory=CharacterFactory(dice_roller=dice_roller),
            data_loader=DataLoader(),
            dice_roller=dice_roller,
        )

        wizard._generate_random_character()

        class_data = wizard.classes_data[wizard.character_class]
        options = class_data.get("starting_equipment_options", [])
        if options:
            assert 0 <= wizard.equipment_option_index < len(options)
        else:
            assert wizard.equipment_option_index == 0

    def test_random_equipment_choice_varies_across_seeds(self):
        """Across many seeds, random picks should hit more than just index 0.

        Locks in that we are actually rolling for the option rather than
        leaving it at the default of 0.
        """
        seen_indices: set[int] = set()
        for seed in range(50):
            dice_roller = DiceRoller(seed=seed)
            wizard = CharacterCreationWizard(
                character_factory=CharacterFactory(dice_roller=dice_roller),
                data_loader=DataLoader(),
                dice_roller=dice_roller,
            )
            wizard._generate_random_character()
            class_data = wizard.classes_data[wizard.character_class]
            if class_data.get("starting_equipment_options"):
                seen_indices.add(wizard.equipment_option_index)
        # All current SRD classes have exactly 3 options
        assert len(seen_indices) > 1, (
            f"Expected random rolls to hit multiple option indices, got {seen_indices}"
        )

    def test_random_equipment_choice_is_deterministic_with_seed(self):
        d1 = DiceRoller(seed=100)
        w1 = CharacterCreationWizard(
            character_factory=CharacterFactory(dice_roller=d1),
            data_loader=DataLoader(),
            dice_roller=d1,
        )
        d2 = DiceRoller(seed=100)
        w2 = CharacterCreationWizard(
            character_factory=CharacterFactory(dice_roller=d2),
            data_loader=DataLoader(),
            dice_roller=d2,
        )

        w1._generate_random_character()
        w2._generate_random_character()

        assert w1.character_class == w2.character_class
        assert w1.equipment_option_index == w2.equipment_option_index


class TestTemplateEquipmentChoice:
    """Template path should honor the per-template equipment_choice field."""

    @pytest.fixture
    def wizard(self):
        dice_roller = DiceRoller(seed=42)
        return CharacterCreationWizard(
            character_factory=CharacterFactory(dice_roller=dice_roller),
            data_loader=DataLoader(),
            dice_roller=dice_roller,
        )

    def _drive_template(self, wizard, template_id):
        mock_text = MagicMock()
        mock_text.ask.return_value = "Test"

        with patch("terminal_client.ui.character_wizard.questionary.text", return_value=mock_text):
            with patch("terminal_client.ui.character_wizard.console.print"):
                with patch("terminal_client.ui.character_wizard.print_status_message"):
                    with patch.object(wizard, "_finalize_character", return_value=None):
                        wizard._create_from_template(template_id)

    def test_template_honors_equipment_choice(self, wizard):
        """A template declaring equipment_choice: 2 should set the index."""
        wizard.templates_data["custom_fighter"] = {
            "name": "Custom Fighter",
            "description": "Test fighter with chosen loadout",
            "race": "human",
            "class": "fighter",
            "abilities": {
                "strength": 15,
                "dexterity": 12,
                "constitution": 14,
                "intelligence": 8,
                "wisdom": 13,
                "charisma": 10,
            },
            "skill_choices": ["athletics", "intimidation"],
            "equipment_choice": 2,
        }
        self._drive_template(wizard, "custom_fighter")
        assert wizard.equipment_option_index == 2

    def test_template_defaults_equipment_choice_zero(self, wizard):
        """A template without equipment_choice keeps the default of 0."""
        wizard.templates_data["legacy_fighter"] = {
            "name": "Legacy Fighter",
            "description": "Pre-#382 template (no equipment_choice)",
            "race": "human",
            "class": "fighter",
            "abilities": {
                "strength": 15,
                "dexterity": 12,
                "constitution": 14,
                "intelligence": 8,
                "wisdom": 13,
                "charisma": 10,
            },
            "skill_choices": ["athletics", "intimidation"],
        }
        wizard.equipment_option_index = 99  # poison value to prove a write happened
        self._drive_template(wizard, "legacy_fighter")
        assert wizard.equipment_option_index == 0


class TestSummaryDisplaysChosenEquipment:
    """The summary screen should reflect the chosen equipment option."""

    @pytest.fixture
    def wizard(self):
        return CharacterCreationWizard(
            character_factory=CharacterFactory(),
            data_loader=DataLoader(),
            dice_roller=DiceRoller(seed=42),
        )

    def _capture_summary(self, wizard) -> str:
        """Run _show_character_summary and return the joined console output."""
        captured: list[str] = []

        def fake_print(*args, **kwargs):
            captured.append(" ".join(str(a) for a in args))

        with patch(
            "terminal_client.ui.character_wizard.console.print", side_effect=fake_print
        ):
            wizard._show_character_summary()

        return "\n".join(captured)

    def _set_state(self, wizard, character_class, option_index):
        wizard.name = "Tester"
        wizard.race = "human"
        wizard.character_class = character_class
        wizard.abilities = {
            "strength": 15,
            "dexterity": 12,
            "constitution": 14,
            "intelligence": 8,
            "wisdom": 13,
            "charisma": 10,
        }
        wizard.skill_proficiencies = []
        wizard.expertise_skills = []
        wizard.equipment_option_index = option_index

    def test_summary_shows_fighter_skirmisher_loadout(self, wizard):
        """Fighter option 1 (Skirmisher): longbow + studded leather + 11 gp."""
        self._set_state(wizard, "fighter", 1)
        output = self._capture_summary(wizard)
        assert "Skirmisher" in output
        assert "Longbow" in output
        assert "Studded Leather" in output
        assert "11" in output  # gold

    def test_summary_shows_standard_loadout(self, wizard):
        """Fighter option 0 (Standard Loadout): chain mail + longsword."""
        self._set_state(wizard, "fighter", 0)
        output = self._capture_summary(wizard)
        assert "Standard Loadout" in output
        assert "Chain Mail" in output
        assert "Longsword" in output
        assert "10" in output  # gold

    def test_summary_shows_gold_only_loadout(self, wizard):
        """Fighter option 2 (Mercenary): 155 gp, no items."""
        self._set_state(wizard, "fighter", 2)
        output = self._capture_summary(wizard)
        assert "Mercenary" in output
        assert "155" in output
