# ABOUTME: Core dice rolling system for D&D 5E mechanics
# ABOUTME: Handles dice notation parsing, rolling with modifiers, and advantage/disadvantage

import re
import random
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DiceRoll:
    """
    Represents the result of a dice roll.

    Attributes:
        rolls: Individual die results
        modifier: Numeric modifier added to the roll
        notation: Original dice notation string (e.g., "2d6+3")
        advantage: Whether the roll was made with advantage
        disadvantage: Whether the roll was made with disadvantage
    """
    rolls: List[int]
    modifier: int
    notation: str
    advantage: bool = False
    disadvantage: bool = False

    @property
    def total(self) -> int:
        """
        Calculate the total result of the dice roll.

        For advantage/disadvantage, takes max/min of rolls before adding modifier.
        For normal rolls, sums all dice and adds modifier.

        Returns:
            Total result of the roll
        """
        if self.advantage:
            base = max(self.rolls)
        elif self.disadvantage:
            base = min(self.rolls)
        else:
            base = sum(self.rolls)

        return base + self.modifier

    def __str__(self) -> str:
        """String representation of the dice roll"""
        adv_status = ""
        if self.advantage:
            adv_status = " (advantage)"
        elif self.disadvantage:
            adv_status = " (disadvantage)"

        return f"{self.notation}{adv_status}: {self.rolls} + {self.modifier} = {self.total}"


class DiceRoller:
    """
    Handles dice rolling with D&D 5E notation.

    Supports:
    - Standard notation: 1d20, 2d6, 3d8, etc.
    - Modifiers: 1d20+5, 2d6-2
    - Implicit single die: d20 (treated as 1d20)
    - Advantage/disadvantage: Roll 2d20 and take best/worst
    """

    # Regex pattern for parsing dice notation: NdS+M or NdS-M
    DICE_PATTERN = re.compile(r'^(\d*)d(\d+)(([+-])(\d+))?$', re.IGNORECASE)

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize the dice roller.

        Args:
            seed: Optional random seed for reproducible results (mainly for testing)
        """
        if seed is not None:
            self.random = random.Random(seed)
        else:
            self.random = random.Random()

    def roll(
        self,
        notation: str,
        advantage: bool = False,
        disadvantage: bool = False
    ) -> DiceRoll:
        """
        Roll dice according to standard D&D notation.

        Args:
            notation: Dice notation string (e.g., "1d20", "2d6+3", "d20-1")
            advantage: Roll 2d20 and take the higher result
            disadvantage: Roll 2d20 and take the lower result

        Returns:
            DiceRoll object containing rolls, modifier, and total

        Raises:
            ValueError: If notation is invalid or advantage/disadvantage used incorrectly
        """
        if advantage and disadvantage:
            raise ValueError("Cannot have both advantage and disadvantage")

        # Parse the dice notation
        count, sides, modifier = self._parse_notation(notation)

        # Advantage/disadvantage only works with single die rolls
        if (advantage or disadvantage) and count != 1:
            raise ValueError("Advantage/disadvantage only works with single die rolls (e.g., 1d20)")

        # Roll the dice
        if advantage or disadvantage:
            # Roll 2 dice for advantage/disadvantage
            rolls = [self._roll_die(sides), self._roll_die(sides)]
        else:
            # Roll the specified number of dice
            rolls = [self._roll_die(sides) for _ in range(count)]

        result = DiceRoll(
            rolls=rolls,
            modifier=modifier,
            notation=notation,
            advantage=advantage,
            disadvantage=disadvantage
        )

        # Log the roll if debug mode is enabled
        from dnd_engine.utils.logging_config import get_logging_config
        logging_config = get_logging_config()
        if logging_config:
            logging_config.log_dice_roll(
                notation=notation,
                rolls=rolls,
                modifier=modifier,
                total=result.total,
                advantage=advantage,
                disadvantage=disadvantage
            )

        return result

    def _parse_notation(self, notation: str) -> tuple[int, int, int]:
        """
        Parse dice notation string into components.

        Args:
            notation: Dice notation string (e.g., "2d6+3")

        Returns:
            Tuple of (count, sides, modifier)

        Raises:
            ValueError: If notation is invalid
        """
        if not notation:
            raise ValueError("Dice notation cannot be empty")

        match = self.DICE_PATTERN.match(notation.strip())
        if not match:
            raise ValueError(f"Invalid dice notation: {notation}")

        # Extract count (default to 1 if not specified, e.g., "d20")
        count_str = match.group(1)
        count = int(count_str) if count_str else 1

        # Extract die size
        sides = int(match.group(2))

        # Extract modifier (default to 0)
        modifier = 0
        if match.group(3):  # Has modifier
            sign = match.group(4)
            value = int(match.group(5))
            modifier = value if sign == '+' else -value

        return count, sides, modifier

    def _roll_die(self, sides: int) -> int:
        """
        Roll a single die with the specified number of sides.

        Args:
            sides: Number of sides on the die

        Returns:
            Random integer between 1 and sides (inclusive)
        """
        return self.random.randint(1, sides)


def format_dice_with_modifier(base_dice: str, modifier: int) -> str:
    """
    Format dice notation with modifier, handling negative values correctly.

    This function prevents generating invalid dice notation like "1d8+-1"
    when the modifier is negative.

    Args:
        base_dice: Base dice notation (e.g., "1d8", "2d6")
        modifier: Modifier to add (can be positive, negative, or zero)

    Returns:
        Properly formatted dice notation

    Examples:
        >>> format_dice_with_modifier("1d8", 3)
        "1d8+3"
        >>> format_dice_with_modifier("1d8", -1)
        "1d8-1"
        >>> format_dice_with_modifier("1d8", 0)
        "1d8"
    """
    if modifier > 0:
        return f"{base_dice}+{modifier}"
    elif modifier < 0:
        return f"{base_dice}{modifier}"  # negative sign already included
    else:
        return base_dice
