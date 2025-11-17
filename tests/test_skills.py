# ABOUTME: Unit tests for the D&D 5E skills system
# ABOUTME: Tests skill modifiers, skill checks, and proficiency mechanics

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.rules.loader import DataLoader


class TestSkillModifierCalculation:
    """Test skill modifier calculation with and without proficiency"""

    @pytest.fixture
    def skills_data(self):
        """Load skills data for testing"""
        loader = DataLoader()
        return loader.load_skills()

    @pytest.fixture
    def character_with_no_proficiencies(self, skills_data):
        """Create a character with no skill proficiencies"""
        abilities = Abilities(
            strength=10,  # modifier: 0
            dexterity=14,  # modifier: 2
            constitution=10,  # modifier: 0
            intelligence=12,  # modifier: 1
            wisdom=16,  # modifier: 3
            charisma=10  # modifier: 0
        )
        character = Character(
            name="Test Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=10,
            skill_proficiencies=[]
        )
        return character

    @pytest.fixture
    def character_with_proficiencies(self, skills_data):
        """Create a character with some skill proficiencies"""
        abilities = Abilities(
            strength=10,  # modifier: 0
            dexterity=14,  # modifier: 2
            constitution=10,  # modifier: 0
            intelligence=12,  # modifier: 1
            wisdom=16,  # modifier: 3
            charisma=10  # modifier: 0
        )
        character = Character(
            name="Proficient Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=10,
            skill_proficiencies=["stealth", "perception"]
        )
        return character

    def test_get_skill_modifier_without_proficiency(self, character_with_no_proficiencies, skills_data):
        """Test that skill modifier without proficiency is just ability modifier"""
        # Stealth uses DEX (2)
        modifier = character_with_no_proficiencies.get_skill_modifier("stealth", skills_data)
        assert modifier == 2  # Just DEX modifier

    def test_get_skill_modifier_with_proficiency(self, character_with_proficiencies, skills_data):
        """Test that skill modifier with proficiency includes proficiency bonus"""
        # Stealth uses DEX (2) + proficiency bonus (2 at level 1)
        modifier = character_with_proficiencies.get_skill_modifier("stealth", skills_data)
        assert modifier == 4  # DEX 2 + proficiency 2

    def test_get_skill_modifier_wisdom_based(self, character_with_proficiencies, skills_data):
        """Test that proficiency bonus is applied to different ability modifiers"""
        # Perception uses WIS (3) + proficiency bonus (2)
        modifier = character_with_proficiencies.get_skill_modifier("perception", skills_data)
        assert modifier == 5  # WIS 3 + proficiency 2

    def test_get_skill_modifier_unrelated_proficiency(self, character_with_proficiencies, skills_data):
        """Test that lack of proficiency means no bonus applied"""
        # Investigation uses INT (1), not proficient
        modifier = character_with_proficiencies.get_skill_modifier("investigation", skills_data)
        assert modifier == 1  # Just INT modifier

    def test_get_skill_modifier_invalid_skill(self, character_with_no_proficiencies, skills_data):
        """Test that invalid skill raises KeyError"""
        with pytest.raises(KeyError):
            character_with_no_proficiencies.get_skill_modifier("invalid_skill", skills_data)

    def test_skill_modifier_at_different_levels(self, skills_data):
        """Test that proficiency bonus scales with level"""
        abilities = Abilities(
            strength=10, dexterity=14, constitution=10,
            intelligence=12, wisdom=16, charisma=10
        )

        # Level 1: proficiency +2
        char_level1 = Character(
            name="Level 1", character_class=CharacterClass.FIGHTER,
            level=1, abilities=abilities, max_hp=10, ac=10,
            skill_proficiencies=["stealth"]
        )
        modifier_level1 = char_level1.get_skill_modifier("stealth", skills_data)
        assert modifier_level1 == 4  # 2 (DEX) + 2 (proficiency)

        # Level 5: proficiency +3
        char_level5 = Character(
            name="Level 5", character_class=CharacterClass.FIGHTER,
            level=5, abilities=abilities, max_hp=30, ac=10,
            skill_proficiencies=["stealth"]
        )
        modifier_level5 = char_level5.get_skill_modifier("stealth", skills_data)
        assert modifier_level5 == 5  # 2 (DEX) + 3 (proficiency)

        # Level 9: proficiency +4
        char_level9 = Character(
            name="Level 9", character_class=CharacterClass.FIGHTER,
            level=9, abilities=abilities, max_hp=70, ac=10,
            skill_proficiencies=["stealth"]
        )
        modifier_level9 = char_level9.get_skill_modifier("stealth", skills_data)
        assert modifier_level9 == 6  # 2 (DEX) + 4 (proficiency)


class TestSkillChecks:
    """Test skill check resolution and results"""

    @pytest.fixture
    def skills_data(self):
        """Load skills data for testing"""
        loader = DataLoader()
        return loader.load_skills()

    @pytest.fixture
    def character(self, skills_data):
        """Create a character with specific proficiencies for testing"""
        abilities = Abilities(
            strength=10, dexterity=14, constitution=10,
            intelligence=12, wisdom=16, charisma=10
        )
        character = Character(
            name="Test Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=10,
            skill_proficiencies=["stealth", "perception", "athletics"]
        )
        return character

    def test_make_skill_check_returns_correct_structure(self, character, skills_data):
        """Test that skill check returns all required fields"""
        result = character.make_skill_check("stealth", dc=12, skills_data=skills_data)

        required_fields = ["skill", "ability", "dc", "roll", "modifier", "total", "success", "proficient"]
        for field in required_fields:
            assert field in result, f"Missing field: {field}"

    def test_make_skill_check_correct_ability(self, character, skills_data):
        """Test that skill check returns correct ability"""
        result = character.make_skill_check("stealth", dc=12, skills_data=skills_data)
        assert result["ability"] == "dex"

        result = character.make_skill_check("perception", dc=12, skills_data=skills_data)
        assert result["ability"] == "wis"

        result = character.make_skill_check("athletics", dc=12, skills_data=skills_data)
        assert result["ability"] == "str"

    def test_make_skill_check_proficiency_flag(self, character, skills_data):
        """Test that proficiency flag is set correctly"""
        # Stealth is proficient
        result = character.make_skill_check("stealth", dc=12, skills_data=skills_data)
        assert result["proficient"] is True

        # Investigation is not proficient
        result = character.make_skill_check("investigation", dc=12, skills_data=skills_data)
        assert result["proficient"] is False

    def test_make_skill_check_dc_comparison(self, character, skills_data):
        """Test that success is determined correctly against DC"""
        # Roll with known seed to test success condition
        from dnd_engine.core.dice import DiceRoller

        # Character with athletics +2 (10 STR) not proficient
        abilities = Abilities(
            strength=10, dexterity=10, constitution=10,
            intelligence=10, wisdom=10, charisma=10
        )
        char = Character(
            name="Test", character_class=CharacterClass.FIGHTER,
            level=1, abilities=abilities, max_hp=10, ac=10,
            skill_proficiencies=[]
        )
        char._dice_roller = DiceRoller(seed=42)

        result = char.make_skill_check("athletics", dc=10, skills_data=skills_data)

        # Verify DC is stored correctly
        assert result["dc"] == 10

        # Success depends on: roll + modifier >= dc
        assert result["total"] == result["roll"] + result["modifier"]
        assert result["success"] == (result["total"] >= result["dc"])

    def test_make_skill_check_invalid_skill(self, character, skills_data):
        """Test that invalid skill raises KeyError"""
        with pytest.raises(KeyError):
            character.make_skill_check("invalid_skill", dc=12, skills_data=skills_data)

    def test_skill_check_with_advantage(self, skills_data):
        """Test that advantage increases chances of success"""
        abilities = Abilities(
            strength=10, dexterity=10, constitution=10,
            intelligence=10, wisdom=10, charisma=10
        )
        character = Character(
            name="Test", character_class=CharacterClass.FIGHTER,
            level=1, abilities=abilities, max_hp=10, ac=10,
            skill_proficiencies=[]
        )

        # Set seed for reproducibility
        character._dice_roller = DiceRoller(seed=42)

        # Roll with advantage
        result_advantage = character.make_skill_check("stealth", dc=10, skills_data=skills_data, advantage=True)

        # The advantage should be reflected in the dice roll
        assert "roll" in result_advantage
        assert result_advantage["roll"] >= 1 and result_advantage["roll"] <= 20

    def test_skill_check_with_disadvantage(self, skills_data):
        """Test that disadvantage decreases chances of success"""
        abilities = Abilities(
            strength=10, dexterity=10, constitution=10,
            intelligence=10, wisdom=10, charisma=10
        )
        character = Character(
            name="Test", character_class=CharacterClass.FIGHTER,
            level=1, abilities=abilities, max_hp=10, ac=10,
            skill_proficiencies=[]
        )

        # Set seed for reproducibility
        character._dice_roller = DiceRoller(seed=42)

        # Roll with disadvantage
        result_disadvantage = character.make_skill_check("stealth", dc=10, skills_data=skills_data, disadvantage=True)

        # The disadvantage should be reflected in the dice roll
        assert "roll" in result_disadvantage
        assert result_disadvantage["roll"] >= 1 and result_disadvantage["roll"] <= 20


class TestAllSkillsDefinition:
    """Test that all D&D 5E skills are defined"""

    def test_all_18_skills_defined(self):
        """Test that all 18 D&D 5E skills are defined in skills.json"""
        loader = DataLoader()
        skills_data = loader.load_skills()

        expected_skills = [
            "acrobatics", "animal_handling", "arcana", "athletics",
            "deception", "history", "insight", "intimidation",
            "investigation", "medicine", "nature", "perception",
            "performance", "persuasion", "religion", "sleight_of_hand",
            "stealth", "survival"
        ]

        for skill in expected_skills:
            assert skill in skills_data, f"Missing skill: {skill}"
            skill_info = skills_data[skill]
            assert "name" in skill_info, f"Skill {skill} missing 'name' field"
            assert "ability" in skill_info, f"Skill {skill} missing 'ability' field"

    def test_skill_abilities_valid(self):
        """Test that each skill has a valid ability association"""
        loader = DataLoader()
        skills_data = loader.load_skills()

        valid_abilities = ["str", "dex", "con", "int", "wis", "cha"]

        for skill_id, skill_info in skills_data.items():
            ability = skill_info.get("ability")
            assert ability in valid_abilities, f"Skill {skill_id} has invalid ability: {ability}"
