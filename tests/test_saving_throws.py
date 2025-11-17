# ABOUTME: Unit tests for saving throw mechanics
# ABOUTME: Tests saving throw modifier calculation, rolls, and proficiency bonuses

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller


class TestGetSavingThrowModifier:
    """Test calculating saving throw modifiers"""

    def setup_method(self):
        """Set up test fixtures"""
        # Create a Fighter with STR 16, CON 15, DEX 12, others 10
        self.fighter_abilities = Abilities(
            strength=16,      # +3
            dexterity=12,     # +1
            constitution=15,  # +2
            intelligence=10,  # +0
            wisdom=10,        # +0
            charisma=8        # -1
        )

        # Fighter is proficient in STR and CON saves
        self.fighter = Character(
            name="Aragorn",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=self.fighter_abilities,
            max_hp=12,
            ac=16,
            saving_throw_proficiencies=["str", "con"]
        )

    def test_proficient_save_includes_proficiency_bonus(self):
        """Test that proficient saves add proficiency bonus"""
        # Fighter level 1 has +2 proficiency bonus
        # STR modifier is +3
        # Total should be +5 (+3 from STR, +2 from proficiency)
        modifier = self.fighter.get_saving_throw_modifier("str")
        assert modifier == 5

    def test_proficient_save_con(self):
        """Test CON save proficiency"""
        # CON modifier is +2, proficiency is +2
        # Total should be +4
        modifier = self.fighter.get_saving_throw_modifier("con")
        assert modifier == 4

    def test_non_proficient_save_no_bonus(self):
        """Test that non-proficient saves don't add proficiency bonus"""
        # DEX modifier is +1, no proficiency
        # Total should be +1 (just the ability modifier)
        modifier = self.fighter.get_saving_throw_modifier("dex")
        assert modifier == 1

    def test_non_proficient_save_negative_modifier(self):
        """Test non-proficient save with negative modifier"""
        # CHA modifier is -1, no proficiency
        # Total should be -1
        modifier = self.fighter.get_saving_throw_modifier("cha")
        assert modifier == -1

    def test_short_ability_names(self):
        """Test that short ability names work correctly"""
        # STR short form
        str_mod = self.fighter.get_saving_throw_modifier("str")
        assert str_mod == 5

        # DEX short form
        dex_mod = self.fighter.get_saving_throw_modifier("dex")
        assert dex_mod == 1

    def test_full_ability_names(self):
        """Test that full ability names work correctly"""
        # Strength full form
        str_mod = self.fighter.get_saving_throw_modifier("strength")
        assert str_mod == 5

        # Dexterity full form
        dex_mod = self.fighter.get_saving_throw_modifier("dexterity")
        assert dex_mod == 1

    def test_case_insensitive(self):
        """Test that ability names are case insensitive"""
        # Mixed case should work
        assert self.fighter.get_saving_throw_modifier("STR") == 5
        assert self.fighter.get_saving_throw_modifier("Dex") == 1
        assert self.fighter.get_saving_throw_modifier("CONSTITUTION") == 4

    def test_invalid_ability_raises_error(self):
        """Test that invalid ability names raise ValueError"""
        with pytest.raises(ValueError):
            self.fighter.get_saving_throw_modifier("invalid")

    def test_level_3_fighter_increased_proficiency(self):
        """Test that proficiency bonus increases with level"""
        # Create a level 3 fighter (proficiency +2)
        fighter_level_3 = Character(
            name="Aragorn",
            character_class=CharacterClass.FIGHTER,
            level=3,
            abilities=self.fighter_abilities,
            max_hp=20,
            ac=16,
            saving_throw_proficiencies=["str", "con"]
        )

        # Level 3: proficiency bonus is still +2 (levels 1-4)
        # So STR save should still be +5
        modifier = fighter_level_3.get_saving_throw_modifier("str")
        assert modifier == 5

    def test_no_proficiencies(self):
        """Test character with no saving throw proficiencies"""
        wizard_abilities = Abilities(
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=16,
            wisdom=12,
            charisma=10
        )

        # Wizard with no proficiencies
        wizard = Character(
            name="Gandalf",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=wizard_abilities,
            max_hp=6,
            ac=12,
            saving_throw_proficiencies=[]
        )

        # Even for low ability, no proficiency bonus
        str_mod = wizard.get_saving_throw_modifier("str")
        assert str_mod == -1  # Just the ability modifier

    def test_multiple_proficiencies(self):
        """Test character with multiple proficiencies"""
        fighter = Character(
            name="Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=self.fighter_abilities,
            max_hp=12,
            ac=16,
            saving_throw_proficiencies=["str", "con", "dex", "wis"]
        )

        # All proficient saves should include bonus
        assert fighter.get_saving_throw_modifier("str") == 5   # +3 ability, +2 prof
        assert fighter.get_saving_throw_modifier("con") == 4   # +2 ability, +2 prof
        assert fighter.get_saving_throw_modifier("dex") == 3   # +1 ability, +2 prof
        assert fighter.get_saving_throw_modifier("wis") == 2   # +0 ability, +2 prof

        # Non-proficient saves don't have bonus
        assert fighter.get_saving_throw_modifier("int") == 0   # +0 ability, no prof
        assert fighter.get_saving_throw_modifier("cha") == -1  # -1 ability, no prof


class TestMakeSavingThrow:
    """Test making saving throws"""

    def setup_method(self):
        """Set up test fixtures"""
        self.abilities = Abilities(
            strength=16,      # +3
            dexterity=12,     # +1
            constitution=15,  # +2
            intelligence=10,  # +0
            wisdom=10,        # +0
            charisma=8        # -1
        )

        self.fighter = Character(
            name="Aragorn",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=self.abilities,
            max_hp=12,
            ac=16,
            saving_throw_proficiencies=["str", "con"]
        )

    def test_saving_throw_returns_dict(self):
        """Test that saving throw returns a dictionary"""
        result = self.fighter.make_saving_throw("str", dc=10)

        assert isinstance(result, dict)
        assert "success" in result
        assert "roll" in result
        assert "modifier" in result
        assert "total" in result
        assert "dc" in result
        assert "ability" in result

    def test_saving_throw_success(self):
        """Test successful saving throw"""
        # With a seeded roller, we can predict the result
        fighter_with_seed = Character(
            name="Aragorn",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=self.abilities,
            max_hp=12,
            ac=16,
            saving_throw_proficiencies=["str", "con"]
        )

        # Make multiple throws to test success/failure statistics
        successes = 0
        failures = 0

        for _ in range(100):
            result = fighter_with_seed.make_saving_throw("str", dc=15)
            if result["success"]:
                successes += 1
            else:
                failures += 1

        # With DC 15 and STR mod +5, we should have some successes
        # (need to roll 10+ on d20, which is 11/20 chance = 55%)
        assert successes > 0
        assert failures > 0

    def test_saving_throw_vs_low_dc(self):
        """Test saving throw against a low DC"""
        result = self.fighter.make_saving_throw("str", dc=5)

        # With STR mod +5 (5+proficiency), we should beat DC 5
        # Need to roll 0+ on d20 (always succeeds)
        assert result["success"] == True
        assert result["total"] >= 5

    def test_saving_throw_vs_high_dc(self):
        """Test saving throw against a high DC"""
        result = self.fighter.make_saving_throw("str", dc=25)

        # With STR mod +5, need to roll 20 on d20
        # Very unlikely to succeed
        # This test just checks the return structure
        assert isinstance(result["success"], bool)
        assert result["total"] < 25  # Unlikely to beat DC 25

    def test_saving_throw_total_calculation(self):
        """Test that total is calculated correctly"""
        result = self.fighter.make_saving_throw("str", dc=10)

        # Total should be roll + modifier
        expected_total = result["roll"] + result["modifier"]
        assert result["total"] == expected_total

    def test_saving_throw_modifier_included(self):
        """Test that the correct modifier is included"""
        result = self.fighter.make_saving_throw("str", dc=10)

        # STR save modifier should be 5 (3 + 2)
        assert result["modifier"] == 5

    def test_advantage_mechanics(self):
        """Test saving throw with advantage"""
        # With advantage, we roll 2d20 and take the higher
        # This should increase success rate
        fighter = Character(
            name="Aragorn",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=self.abilities,
            max_hp=12,
            ac=16,
            saving_throw_proficiencies=["str", "con"]
        )

        result = fighter.make_saving_throw("str", dc=15, advantage=True)

        assert isinstance(result["roll"], int)
        assert 1 <= result["roll"] <= 20
        assert result["success"] in [True, False]

    def test_disadvantage_mechanics(self):
        """Test saving throw with disadvantage"""
        # With disadvantage, we roll 2d20 and take the lower
        # This should decrease success rate
        fighter = Character(
            name="Aragorn",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=self.abilities,
            max_hp=12,
            ac=16,
            saving_throw_proficiencies=["str", "con"]
        )

        result = fighter.make_saving_throw("str", dc=15, disadvantage=True)

        assert isinstance(result["roll"], int)
        assert 1 <= result["roll"] <= 20
        assert result["success"] in [True, False]

    def test_invalid_ability_in_saving_throw(self):
        """Test that invalid ability raises error"""
        with pytest.raises(ValueError):
            self.fighter.make_saving_throw("invalid", dc=10)

    def test_saving_throw_ability_normalization(self):
        """Test that ability names are normalized correctly"""
        result1 = self.fighter.make_saving_throw("str", dc=10)
        result2 = self.fighter.make_saving_throw("STR", dc=10)
        result3 = self.fighter.make_saving_throw("strength", dc=10)

        # All should have the same ability in result
        assert result1["ability"] == "str"
        assert result2["ability"] == "str"
        assert result3["ability"] == "str"


class TestSavingThrowWithEventBus:
    """Test saving throw event emission"""

    def setup_method(self):
        """Set up test fixtures"""
        self.abilities = Abilities(
            strength=16,      # +3
            dexterity=12,     # +1
            constitution=15,  # +2
            intelligence=10,  # +0
            wisdom=10,        # +0
            charisma=8        # -1
        )

        self.fighter = Character(
            name="Aragorn",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=self.abilities,
            max_hp=12,
            ac=16,
            saving_throw_proficiencies=["str", "con"]
        )

        # Track emitted events
        self.events = []

    def event_handler(self, event):
        """Handler to capture events"""
        self.events.append(event)

    def test_saving_throw_emits_event(self):
        """Test that saving throw emits an event when event_bus provided"""
        from dnd_engine.utils.events import EventBus, EventType

        event_bus = EventBus()
        event_bus.subscribe(EventType.SAVING_THROW, self.event_handler)

        self.fighter.make_saving_throw("str", dc=10, event_bus=event_bus)

        assert len(self.events) == 1
        assert self.events[0].type == EventType.SAVING_THROW

    def test_event_contains_correct_data(self):
        """Test that emitted event contains all required data"""
        from dnd_engine.utils.events import EventBus, EventType

        event_bus = EventBus()
        event_bus.subscribe(EventType.SAVING_THROW, self.event_handler)

        result = self.fighter.make_saving_throw("str", dc=15, event_bus=event_bus)

        event = self.events[0]
        assert event.data["character"] == "Aragorn"
        assert event.data["ability"] == "str"
        assert event.data["dc"] == 15
        assert event.data["roll"] == result["roll"]
        assert event.data["modifier"] == 5
        assert event.data["total"] == result["total"]
        assert event.data["success"] == result["success"]

    def test_no_event_without_event_bus(self):
        """Test that no event is emitted if event_bus is None"""
        from dnd_engine.utils.events import EventBus, EventType

        event_bus = EventBus()
        event_bus.subscribe(EventType.SAVING_THROW, self.event_handler)

        # Make saving throw without passing event_bus
        self.fighter.make_saving_throw("str", dc=10)

        # No events should have been captured
        assert len(self.events) == 0
