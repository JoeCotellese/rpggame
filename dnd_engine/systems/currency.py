# ABOUTME: D&D 5E currency system with automatic conversions and change-making
# ABOUTME: Tracks copper, silver, electrum, gold, and platinum pieces with automatic consolidation

from dataclasses import dataclass


@dataclass
class Currency:
    """
    Represents D&D 5E currency with five denominations.

    Conversion rates (D&D 5E Standard):
    - 1 cp (copper piece) = 1 cp
    - 1 sp (silver piece) = 10 cp
    - 1 ep (electrum piece) = 50 cp
    - 1 gp (gold piece) = 100 cp
    - 1 pp (platinum piece) = 1000 cp

    Provides automatic change-making when paying and optional
    consolidation when receiving currency.
    """

    copper: int = 0
    silver: int = 0
    electrum: int = 0
    gold: int = 0
    platinum: int = 0

    # Conversion rates to copper pieces
    CP_PER_SP = 10
    CP_PER_EP = 50
    CP_PER_GP = 100
    CP_PER_PP = 1000

    def __post_init__(self) -> None:
        """Validate currency values are non-negative"""
        if any(value < 0 for value in [self.copper, self.silver, self.electrum, self.gold, self.platinum]):
            raise ValueError("Currency values cannot be negative")

    def to_copper(self) -> int:
        """
        Convert all currency to total copper pieces.

        Returns:
            Total wealth in copper pieces
        """
        return (
            self.copper +
            (self.silver * self.CP_PER_SP) +
            (self.electrum * self.CP_PER_EP) +
            (self.gold * self.CP_PER_GP) +
            (self.platinum * self.CP_PER_PP)
        )

    def _from_copper(self, amount_cp: int) -> None:
        """
        Convert from copper pieces to all denominations (consolidated form).

        Resets all denominations and converts the given copper amount
        back into the minimum set of denominations.

        Args:
            amount_cp: Total amount in copper pieces
        """
        if amount_cp < 0:
            raise ValueError("Amount cannot be negative")

        self.platinum = amount_cp // self.CP_PER_PP
        remaining = amount_cp % self.CP_PER_PP

        self.gold = remaining // self.CP_PER_GP
        remaining = remaining % self.CP_PER_GP

        self.electrum = remaining // self.CP_PER_EP
        remaining = remaining % self.CP_PER_EP

        self.silver = remaining // self.CP_PER_SP
        self.copper = remaining % self.CP_PER_SP

    def add(self, other: 'Currency') -> None:
        """
        Add currency from another Currency object.

        Args:
            other: Currency object to add

        Raises:
            ValueError: If other is not a Currency instance
        """
        if not isinstance(other, Currency):
            raise ValueError("Can only add Currency objects")

        self.copper += other.copper
        self.silver += other.silver
        self.electrum += other.electrum
        self.gold += other.gold
        self.platinum += other.platinum

    def subtract(self, other: 'Currency') -> bool:
        """
        Subtract currency from this object with automatic change-making.

        If we don't have exact denominations but have enough total value,
        automatically breaks down larger denominations to make change.
        The result is returned in consolidated form (largest denominations first).

        Args:
            other: Currency object to subtract

        Returns:
            True if subtraction was successful, False if insufficient funds

        Raises:
            ValueError: If other is not a Currency instance
        """
        if not isinstance(other, Currency):
            raise ValueError("Can only subtract Currency objects")

        # Check if we have enough total currency in copper pieces
        required_cp = other.to_copper()
        available_cp = self.to_copper()

        if available_cp < required_cp:
            return False

        # Convert all currency to copper, subtract, and convert back to consolidated form
        total_cp = self.to_copper()
        remaining_cp = total_cp - required_cp

        # Convert remaining amount back to denominations (consolidated)
        self._from_copper(remaining_cp)

        return True

    def can_afford(self, other: 'Currency') -> bool:
        """
        Check if this currency can afford the given amount.

        Args:
            other: Currency object to check affordability for

        Returns:
            True if we have enough currency value

        Raises:
            ValueError: If other is not a Currency instance
        """
        if not isinstance(other, Currency):
            raise ValueError("Can only compare with Currency objects")

        return self.to_copper() >= other.to_copper()

    def consolidate(self) -> None:
        """
        Consolidate currency to larger denominations.

        Converts smaller denominations to larger ones:
        - 10 copper → 1 silver
        - 50 copper → 1 electrum (or 5 silver)
        - 100 copper → 1 gold (or 2 electrum, or 10 silver)
        - 1000 copper → 1 platinum

        This provides a "realistic" consolidation where merchants
        would naturally convert change to convenient denominations.
        """
        # Convert copper to silver (10:1)
        if self.copper >= self.CP_PER_SP:
            new_silver = self.copper // self.CP_PER_SP
            self.copper = self.copper % self.CP_PER_SP
            self.silver += new_silver

        # Convert silver to electrum (5:1)
        if self.silver >= 5:
            new_electrum = self.silver // 5
            self.silver = self.silver % 5
            self.electrum += new_electrum

        # Convert electrum to gold (2:1)
        if self.electrum >= 2:
            new_gold = self.electrum // 2
            self.electrum = self.electrum % 2
            self.gold += new_gold

        # Convert gold to platinum (10:1)
        if self.gold >= 10:
            new_platinum = self.gold // 10
            self.gold = self.gold % 10
            self.platinum += new_platinum

    def is_zero(self) -> bool:
        """
        Check if currency is zero (no money at all).

        Returns:
            True if all denominations are zero
        """
        return all(value == 0 for value in [self.copper, self.silver, self.electrum, self.gold, self.platinum])

    def __str__(self) -> str:
        """
        String representation in human-readable format.

        Shows only non-zero denominations.
        Example: "5 gp, 7 sp, 3 cp"

        Returns:
            Formatted currency string
        """
        parts = []

        if self.platinum > 0:
            parts.append(f"{self.platinum} pp")
        if self.gold > 0:
            parts.append(f"{self.gold} gp")
        if self.electrum > 0:
            parts.append(f"{self.electrum} ep")
        if self.silver > 0:
            parts.append(f"{self.silver} sp")
        if self.copper > 0:
            parts.append(f"{self.copper} cp")

        if not parts:
            return "0 cp"

        return ", ".join(parts)

    def __eq__(self, other: object) -> bool:
        """
        Check equality with another Currency object by total value.

        Currency objects are equal if they represent the same total value
        in copper pieces, regardless of denomination breakdown.

        Args:
            other: Object to compare with

        Returns:
            True if total values are equal
        """
        if not isinstance(other, Currency):
            return NotImplemented

        return self.to_copper() == other.to_copper()

    def __lt__(self, other: 'Currency') -> bool:
        """
        Compare currency by total value in copper pieces.

        Args:
            other: Currency object to compare with

        Returns:
            True if this currency has less value
        """
        if not isinstance(other, Currency):
            return NotImplemented

        return self.to_copper() < other.to_copper()

    def __le__(self, other: 'Currency') -> bool:
        """
        Compare currency by total value in copper pieces.

        Args:
            other: Currency object to compare with

        Returns:
            True if this currency has equal or less value
        """
        if not isinstance(other, Currency):
            return NotImplemented

        return self.to_copper() <= other.to_copper()

    def __gt__(self, other: 'Currency') -> bool:
        """
        Compare currency by total value in copper pieces.

        Args:
            other: Currency object to compare with

        Returns:
            True if this currency has greater value
        """
        if not isinstance(other, Currency):
            return NotImplemented

        return self.to_copper() > other.to_copper()

    def __ge__(self, other: 'Currency') -> bool:
        """
        Compare currency by total value in copper pieces.

        Args:
            other: Currency object to compare with

        Returns:
            True if this currency has equal or greater value
        """
        if not isinstance(other, Currency):
            return NotImplemented

        return self.to_copper() >= other.to_copper()
