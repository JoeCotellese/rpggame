# ABOUTME: Unit tests for distance calculation utilities
# ABOUTME: Tests Chebyshev distance and adjacency checks for tactical combat

import pytest

from dnd_engine.core.distance import chebyshev_distance, distance_in_feet, is_adjacent


class TestChebyshevDistance:
    """Test Chebyshev distance calculations"""

    def test_same_position(self):
        """Distance to self is 0"""
        assert chebyshev_distance(5, 5, 5, 5) == 0

    def test_horizontal_distance(self):
        """Test horizontal movement"""
        assert chebyshev_distance(0, 0, 3, 0) == 3
        assert chebyshev_distance(5, 5, 2, 5) == 3

    def test_vertical_distance(self):
        """Test vertical movement"""
        assert chebyshev_distance(0, 0, 0, 4) == 4
        assert chebyshev_distance(5, 5, 5, 1) == 4

    def test_diagonal_distance(self):
        """Diagonal movement costs 1 per square in Chebyshev"""
        assert chebyshev_distance(0, 0, 3, 3) == 3
        assert chebyshev_distance(5, 5, 2, 2) == 3

    def test_mixed_distance(self):
        """Test non-straight movement (uses max of x and y difference)"""
        assert chebyshev_distance(0, 0, 3, 4) == 4  # max(3, 4) = 4
        assert chebyshev_distance(0, 0, 5, 2) == 5  # max(5, 2) = 5

    def test_negative_coordinates(self):
        """Test with negative coordinates"""
        assert chebyshev_distance(-3, -3, 0, 0) == 3
        assert chebyshev_distance(-2, 3, 2, -3) == 6  # max(4, 6) = 6


class TestIsAdjacent:
    """Test adjacency checks for melee range"""

    def test_same_position_is_adjacent(self):
        """Same position is considered adjacent"""
        assert is_adjacent(5, 5, 5, 5) is True

    def test_orthogonal_adjacent(self):
        """Test adjacent in cardinal directions"""
        assert is_adjacent(5, 5, 6, 5) is True  # East
        assert is_adjacent(5, 5, 4, 5) is True  # West
        assert is_adjacent(5, 5, 5, 6) is True  # North
        assert is_adjacent(5, 5, 5, 4) is True  # South

    def test_diagonal_adjacent(self):
        """Diagonal squares are adjacent in Chebyshev"""
        assert is_adjacent(5, 5, 6, 6) is True  # NE
        assert is_adjacent(5, 5, 4, 4) is True  # SW
        assert is_adjacent(5, 5, 6, 4) is True  # SE
        assert is_adjacent(5, 5, 4, 6) is True  # NW

    def test_not_adjacent_2_squares(self):
        """2 squares away is not adjacent"""
        assert is_adjacent(5, 5, 7, 5) is False
        assert is_adjacent(5, 5, 5, 7) is False
        assert is_adjacent(5, 5, 7, 7) is False

    def test_not_adjacent_far(self):
        """Far positions are not adjacent"""
        assert is_adjacent(0, 0, 10, 10) is False
        assert is_adjacent(0, 0, 5, 0) is False


class TestDistanceInFeet:
    """Test distance conversion to feet"""

    def test_same_position_zero_feet(self):
        """Same position is 0 feet"""
        assert distance_in_feet(5, 5, 5, 5) == 0

    def test_one_square_is_five_feet(self):
        """One square is 5 feet"""
        assert distance_in_feet(0, 0, 1, 0) == 5
        assert distance_in_feet(0, 0, 1, 1) == 5  # Diagonal

    def test_multiple_squares(self):
        """Multiple squares multiply by 5"""
        assert distance_in_feet(0, 0, 6, 0) == 30
        assert distance_in_feet(0, 0, 3, 4) == 20  # max(3,4) * 5 = 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
