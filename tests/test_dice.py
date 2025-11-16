# ABOUTME: Unit tests for the dice rolling system
# ABOUTME: Tests dice notation parsing, rolling mechanics, and advantage/disadvantage

import pytest
from dnd_engine.core.dice import DiceRoller, DiceRoll


class TestDiceRoller:
    """Test the DiceRoller class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.roller = DiceRoller()

    def test_roll_single_die(self):
        """Test rolling a single die"""
        # Roll d20 100 times to test range
        for _ in range(100):
            result = self.roller.roll("1d20")
            assert 1 <= result.total <= 20
            assert len(result.rolls) == 1
            assert 1 <= result.rolls[0] <= 20

    def test_roll_multiple_dice(self):
        """Test rolling multiple dice"""
        result = self.roller.roll("3d6")
        assert 3 <= result.total <= 18
        assert len(result.rolls) == 3
        for roll in result.rolls:
            assert 1 <= roll <= 6

    def test_roll_with_positive_modifier(self):
        """Test rolling with positive modifier"""
        result = self.roller.roll("1d20+5")
        assert 6 <= result.total <= 25
        assert result.modifier == 5
        assert len(result.rolls) == 1

    def test_roll_with_negative_modifier(self):
        """Test rolling with negative modifier"""
        result = self.roller.roll("1d20-3")
        assert -2 <= result.total <= 17
        assert result.modifier == -3

    def test_roll_multiple_dice_with_modifier(self):
        """Test rolling multiple dice with modifier"""
        result = self.roller.roll("2d6+3")
        assert 5 <= result.total <= 15
        assert result.modifier == 3
        assert len(result.rolls) == 2

    def test_roll_advantage(self):
        """Test rolling with advantage (take higher of 2d20)"""
        # Run multiple times to ensure both dice are rolled
        for _ in range(50):
            result = self.roller.roll("1d20", advantage=True)
            assert 1 <= result.total <= 20
            assert len(result.rolls) == 2
            assert result.total == max(result.rolls)
            assert result.advantage is True

    def test_roll_disadvantage(self):
        """Test rolling with disadvantage (take lower of 2d20)"""
        for _ in range(50):
            result = self.roller.roll("1d20", disadvantage=True)
            assert 1 <= result.total <= 20
            assert len(result.rolls) == 2
            assert result.total == min(result.rolls)
            assert result.disadvantage is True

    def test_roll_advantage_with_modifier(self):
        """Test advantage with modifier"""
        result = self.roller.roll("1d20+5", advantage=True)
        assert 6 <= result.total <= 25
        assert len(result.rolls) == 2
        assert result.modifier == 5
        # Total should be max of two rolls plus modifier
        assert result.total == max(result.rolls) + 5

    def test_roll_different_die_sizes(self):
        """Test different die sizes"""
        die_sizes = [4, 6, 8, 10, 12, 20, 100]
        for size in die_sizes:
            result = self.roller.roll(f"1d{size}")
            assert 1 <= result.total <= size

    def test_roll_zero_modifier(self):
        """Test that zero modifier works correctly"""
        result = self.roller.roll("1d20+0")
        assert result.modifier == 0
        assert result.total == result.rolls[0]

    def test_parse_dice_notation(self):
        """Test parsing various dice notation formats"""
        test_cases = [
            ("1d20", 1, 20, 0),
            ("2d6", 2, 6, 0),
            ("3d8+5", 3, 8, 5),
            ("1d12-2", 1, 12, -2),
            ("4d6+10", 4, 6, 10),
            ("d20", 1, 20, 0),  # Implicit 1
        ]

        for notation, expected_count, expected_sides, expected_mod in test_cases:
            result = self.roller.roll(notation)
            assert len(result.rolls) == expected_count
            assert result.modifier == expected_mod
            for roll in result.rolls:
                assert 1 <= roll <= expected_sides

    def test_invalid_dice_notation(self):
        """Test that invalid notation raises appropriate errors"""
        invalid_notations = [
            "invalid",
            "d",
            "2d",
            "d+5",
            "abc",
            "",
        ]

        for notation in invalid_notations:
            with pytest.raises(ValueError):
                self.roller.roll(notation)

    def test_roll_result_attributes(self):
        """Test that DiceRoll result has correct attributes"""
        result = self.roller.roll("2d6+3")
        assert hasattr(result, 'rolls')
        assert hasattr(result, 'modifier')
        assert hasattr(result, 'total')
        assert hasattr(result, 'notation')
        assert hasattr(result, 'advantage')
        assert hasattr(result, 'disadvantage')
        assert result.notation == "2d6+3"

    def test_advantage_and_disadvantage_mutually_exclusive(self):
        """Test that advantage and disadvantage cannot both be True"""
        with pytest.raises(ValueError):
            self.roller.roll("1d20", advantage=True, disadvantage=True)

    def test_advantage_only_on_single_die(self):
        """Test that advantage/disadvantage only work with single die rolls"""
        # Advantage on multiple dice should raise an error
        with pytest.raises(ValueError):
            self.roller.roll("2d20", advantage=True)

        with pytest.raises(ValueError):
            self.roller.roll("2d20", disadvantage=True)

    def test_roll_consistency(self):
        """Test that roll results are consistent with their parts"""
        for _ in range(20):
            result = self.roller.roll("3d6+2")
            expected_total = sum(result.rolls) + result.modifier
            assert result.total == expected_total

    def test_seeded_randomness(self):
        """Test that seeded roller produces reproducible results"""
        roller1 = DiceRoller(seed=42)
        roller2 = DiceRoller(seed=42)

        results1 = [roller1.roll("1d20").total for _ in range(10)]
        results2 = [roller2.roll("1d20").total for _ in range(10)]

        assert results1 == results2


class TestDiceRoll:
    """Test the DiceRoll result class"""

    def test_dice_roll_creation(self):
        """Test creating a DiceRoll result"""
        roll = DiceRoll(
            rolls=[15],
            modifier=3,
            notation="1d20+3",
            advantage=False,
            disadvantage=False
        )
        assert roll.total == 18
        assert roll.rolls == [15]
        assert roll.modifier == 3

    def test_dice_roll_string_representation(self):
        """Test string representation of DiceRoll"""
        roll = DiceRoll(
            rolls=[4, 6],
            modifier=2,
            notation="2d6+2",
            advantage=False,
            disadvantage=False
        )
        str_rep = str(roll)
        assert "2d6+2" in str_rep
        assert "12" in str_rep  # total

    def test_dice_roll_advantage_total(self):
        """Test that advantage correctly calculates total"""
        roll = DiceRoll(
            rolls=[12, 8],
            modifier=3,
            notation="1d20+3",
            advantage=True,
            disadvantage=False
        )
        # Should take max (12) and add modifier
        assert roll.total == 15

    def test_dice_roll_disadvantage_total(self):
        """Test that disadvantage correctly calculates total"""
        roll = DiceRoll(
            rolls=[12, 8],
            modifier=3,
            notation="1d20+3",
            advantage=False,
            disadvantage=True
        )
        # Should take min (8) and add modifier
        assert roll.total == 11
