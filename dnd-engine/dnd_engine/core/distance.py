# ABOUTME: Distance calculation utilities for grid-based tactical combat
# ABOUTME: Implements Chebyshev distance (diagonal movement costs 1 square)


def chebyshev_distance(x1: int, y1: int, x2: int, y2: int) -> int:
    """
    Calculate Chebyshev distance between two grid positions.

    Chebyshev distance treats diagonal movement as costing 1 square,
    like a King moving in chess. This is simpler than D&D 5E's alternating
    diagonal rule (5-10-5-10) and commonly used in tactical games.

    Args:
        x1: X coordinate of first position
        y1: Y coordinate of first position
        x2: X coordinate of second position
        y2: Y coordinate of second position

    Returns:
        Distance in grid squares

    Example:
        >>> chebyshev_distance(0, 0, 3, 4)  # Move 3 right, 4 up
        4  # Max of horizontal and vertical distance
        >>> chebyshev_distance(0, 0, 3, 3)  # Diagonal
        3  # Diagonal counts as 1 per square
    """
    return max(abs(x2 - x1), abs(y2 - y1))


def is_adjacent(x1: int, y1: int, x2: int, y2: int) -> bool:
    """
    Check if two grid positions are adjacent (within melee range).

    Adjacent means Chebyshev distance of 1 or less, including diagonals.
    This is standard D&D melee range (5 ft = 1 square).

    Args:
        x1: X coordinate of first position
        y1: Y coordinate of first position
        x2: X coordinate of second position
        y2: Y coordinate of second position

    Returns:
        True if positions are adjacent (distance <= 1)

    Example:
        >>> is_adjacent(5, 5, 6, 5)  # 1 square right
        True
        >>> is_adjacent(5, 5, 6, 6)  # Diagonal
        True
        >>> is_adjacent(5, 5, 7, 5)  # 2 squares away
        False
    """
    return chebyshev_distance(x1, y1, x2, y2) <= 1


def distance_in_feet(x1: int, y1: int, x2: int, y2: int) -> int:
    """
    Calculate distance between grid positions in feet.

    Each grid square is 5 feet. Uses Chebyshev distance.

    Args:
        x1: X coordinate of first position
        y1: Y coordinate of first position
        x2: X coordinate of second position
        y2: Y coordinate of second position

    Returns:
        Distance in feet (multiples of 5)

    Example:
        >>> distance_in_feet(0, 0, 2, 3)
        15  # 3 squares * 5 ft
    """
    return chebyshev_distance(x1, y1, x2, y2) * 5
