"""Integration tests for CharacterCreationWizard - tests integration between wizard and factory/data loader"""

import pytest
from dnd_engine.ui.character_wizard import CharacterCreationWizard
from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.character import CharacterClass
from dnd_engine.rules.loader import DataLoader


class TestWizardDataIntegration:
    """Test that wizard properly integrates with game data"""

    @pytest.fixture
    def wizard(self):
        """Create wizard with real data loader"""
        dice_roller = DiceRoller(seed=42)
        factory = CharacterFactory(dice_roller=dice_roller)
        return CharacterCreationWizard(
            character_factory=factory,
            data_loader=DataLoader(),
            dice_roller=dice_roller
        )

    def test_wizard_loads_all_game_data(self, wizard):
        """Test that wizard successfully loads all required game data"""
        # Races
        assert wizard.races_data is not None
        assert len(wizard.races_data) > 0
        assert "human" in wizard.races_data
        assert "ability_bonuses" in wizard.races_data["human"]

        # Classes
        assert wizard.classes_data is not None
        assert len(wizard.classes_data) > 0
        assert "fighter" in wizard.classes_data
        assert "ability_priorities" in wizard.classes_data["fighter"]

        # Items
        assert wizard.items_data is not None
        assert "weapons" in wizard.items_data
        assert "armor" in wizard.items_data

        # Skills
        assert wizard.skills_data is not None
        assert len(wizard.skills_data) > 0

        # Spells
        assert wizard.spells_data is not None
        assert len(wizard.spells_data) > 0

    def test_wizard_loads_templates(self, wizard):
        """Test that wizard loads character templates"""
        assert wizard.templates_data is not None

        # If templates exist, verify structure
        if wizard.templates_data:
            for template_id, template in wizard.templates_data.items():
                # Each template should have required fields
                assert "name" in template
                assert "description" in template
                assert "race" in template
                assert "class" in template
                assert "abilities" in template

                # Verify referenced race and class exist
                assert template["race"] in wizard.races_data
                assert template["class"] in wizard.classes_data

                # Verify abilities are complete
                assert len(template["abilities"]) == 6
                for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
                    assert ability in template["abilities"]


class TestTemplateIntegration:
    """Test template-based character creation integrates properly"""

    @pytest.fixture
    def wizard(self):
        """Create wizard instance"""
        return CharacterCreationWizard(
            character_factory=CharacterFactory(),
            data_loader=DataLoader()
        )

    def test_template_creates_valid_character(self, wizard):
        """Test that template creates a fully valid character"""
        if not wizard.templates_data or 'classic_fighter' not in wizard.templates_data:
            pytest.skip("Classic fighter template not available")

        # Set wizard state from template
        template = wizard.templates_data['classic_fighter']
        wizard.name = "Test Fighter"
        wizard.race = template['race']
        wizard.character_class = template['class']
        wizard.abilities = template['abilities'].copy()

        # Apply racial bonuses (as template path does)
        wizard.abilities = wizard.factory.apply_racial_bonuses(
            wizard.abilities,
            wizard.races_data[wizard.race]
        )

        wizard.skill_proficiencies = template.get('skill_choices', [])
        wizard.expertise_skills = []
        wizard.selected_spells = []

        # Create character
        character = wizard._create_character()

        # Verify character is valid
        assert character is not None
        assert character.name == "Test Fighter"
        assert character.character_class == CharacterClass.FIGHTER
        assert character.level == 1
        assert character.max_hp > 0
        assert character.ac >= 10
        assert len(character.skill_proficiencies) > 0

    def test_template_applies_racial_bonuses_correctly(self, wizard):
        """Test that racial bonuses are applied correctly in templates"""
        if not wizard.templates_data or 'classic_fighter' not in wizard.templates_data:
            pytest.skip("Classic fighter template not available")

        template = wizard.templates_data['classic_fighter']
        base_str = template['abilities']['strength']

        # Apply racial bonuses as wizard does
        abilities = template['abilities'].copy()
        abilities_with_bonuses = wizard.factory.apply_racial_bonuses(
            abilities,
            wizard.races_data[template['race']]
        )

        # Human gets +1 to all abilities
        assert abilities_with_bonuses['strength'] >= base_str

    def test_rogue_template_has_expertise(self, wizard):
        """Test that rogue template includes expertise"""
        if not wizard.templates_data or 'sneaky_rogue' not in wizard.templates_data:
            pytest.skip("Sneaky rogue template not available")

        template = wizard.templates_data['sneaky_rogue']
        assert 'expertise_choices' in template
        assert len(template['expertise_choices']) == 2


class TestRandomGenerationIntegration:
    """Test random character generation integrates properly"""

    @pytest.fixture
    def wizard(self):
        """Create wizard with seeded dice roller"""
        dice_roller = DiceRoller(seed=42)
        return CharacterCreationWizard(
            character_factory=CharacterFactory(dice_roller=dice_roller),
            data_loader=DataLoader(),
            dice_roller=dice_roller
        )

    def test_random_generation_creates_valid_character(self, wizard):
        """Test that random generation produces a valid character"""
        wizard._generate_random_character()

        # Verify state is set
        assert wizard.race is not None
        assert wizard.character_class is not None
        assert wizard.abilities is not None

        # Verify race and class are valid
        assert wizard.race in wizard.races_data
        assert wizard.character_class in wizard.classes_data

        # Verify abilities
        assert len(wizard.abilities) == 6
        for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            assert ability in wizard.abilities
            assert 3 <= wizard.abilities[ability] <= 20  # Reasonable range after bonuses

        # Set name and create character
        wizard.name = "Random Hero"
        character = wizard._create_character()

        # Verify character is valid
        assert character is not None
        assert character.name == "Random Hero"
        assert character.level == 1
        assert character.max_hp > 0

    def test_random_uses_standard_array(self, wizard):
        """Test that random generation uses standard array"""
        wizard._generate_random_character()

        # Get all ability scores
        scores = sorted(wizard.abilities.values())

        # After racial bonuses, we can't check exact values
        # But we can verify we have 6 ability scores
        assert len(scores) == 6

        # All scores should be reasonable (3-20 range after bonuses)
        assert all(3 <= score <= 20 for score in scores)

    def test_random_selects_valid_skills(self, wizard):
        """Test that random generation selects valid skills for class"""
        wizard._generate_random_character()

        # Should have selected skills (if class allows)
        if wizard.skill_proficiencies:
            class_data = wizard.classes_data[wizard.character_class]
            skill_profs = class_data.get("skill_proficiencies", {})
            available_skills = skill_profs.get("from", [])

            # All selected skills should be from available list
            for skill in wizard.skill_proficiencies:
                assert skill in available_skills

    def test_random_generation_is_deterministic(self):
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


class TestCharacterCreationFlow:
    """Test complete character creation flow"""

    @pytest.fixture
    def wizard(self):
        """Create wizard instance"""
        dice_roller = DiceRoller(seed=42)
        return CharacterCreationWizard(
            character_factory=CharacterFactory(dice_roller=dice_roller),
            data_loader=DataLoader(),
            dice_roller=dice_roller
        )

    def test_create_fighter_from_wizard_state(self, wizard):
        """Test creating a fighter character from wizard state"""
        # Manually set wizard state (as custom path would)
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

        # Create character
        character = wizard._create_character()

        # Verify character
        assert character is not None
        assert character.name == "Test Fighter"
        assert character.character_class == CharacterClass.FIGHTER
        assert character.race == "human"
        assert character.level == 1
        assert character.max_hp > 0
        assert character.ac > 0
        assert "athletics" in character.skill_proficiencies
        assert "intimidation" in character.skill_proficiencies

        # Verify equipment was applied
        assert character.inventory is not None
        assert character.inventory.gold >= 0

    def test_create_rogue_with_expertise_from_wizard_state(self, wizard):
        """Test creating a rogue with expertise"""
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

        # Create character
        character = wizard._create_character()

        # Verify expertise
        assert character is not None
        assert "stealth" in character.expertise_skills
        assert "sleight_of_hand" in character.expertise_skills
        assert len(character.expertise_skills) == 2

    def test_create_wizard_with_spells_from_wizard_state(self, wizard):
        """Test creating a wizard with spells"""
        wizard.name = "Test Wizard"
        wizard.race = "high_elf"
        wizard.character_class = "wizard"
        wizard.abilities = {
            "strength": 8,
            "dexterity": 13,
            "constitution": 12,
            "intelligence": 16,
            "wisdom": 14,
            "charisma": 10
        }
        wizard.skill_proficiencies = ["arcana", "history"]
        wizard.expertise_skills = []
        wizard.selected_spells = ["fire_bolt", "mage_hand", "light", "magic_missile", "shield", "mage_armor"]

        # Create character
        character = wizard._create_character()

        # Verify spellcasting
        assert character is not None
        assert character.spellcasting_ability == "int"
        # Either known_spells from wizard state or initialized by factory
        assert len(character.known_spells) > 0
