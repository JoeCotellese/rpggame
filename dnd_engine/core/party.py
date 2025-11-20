# ABOUTME: Party class managing a group of player characters
# ABOUTME: Handles party membership, living members check, and character lookup

from typing import List, Optional
from dnd_engine.core.character import Character


class Party:
    """
    Manages a group of player characters.

    The party acts as a container for multiple characters and provides
    methods to query party status (alive/dead), manage membership,
    and find specific characters.
    """

    def __init__(self, characters: Optional[List[Character]] = None):
        """
        Initialize a party with characters.

        Args:
            characters: List of Character objects (empty list if not provided)
        """
        self.characters: List[Character] = characters if characters is not None else []

    def get_living_members(self) -> List[Character]:
        """
        Get all living party members.

        Returns:
            List of characters with HP > 0
        """
        return [char for char in self.characters if char.is_alive]

    def get_targetable_members(self) -> List[Character]:
        """
        Get all party members that can be targeted with items/abilities.

        This includes:
        - Living members (HP > 0)
        - Unconscious members (0 HP but < 3 death save failures)

        Excludes:
        - Dead members (3 death save failures)

        Returns:
            List of characters that can be targeted for healing/buffs/etc.
        """
        targetable = []
        for char in self.characters:
            # Use is_dead if available (supports death saves)
            if hasattr(char, 'is_dead'):
                if not char.is_dead:
                    targetable.append(char)
            else:
                # Fallback to is_alive for creatures without death saves
                if char.is_alive:
                    targetable.append(char)
        return targetable

    def is_wiped(self) -> bool:
        """
        Check if the entire party is dead (game over condition).

        With death saves:
        - Unconscious characters (0 HP, < 3 failures) are still "alive"
        - Only characters with 3 death save failures are truly dead
        - Party is wiped only when ALL characters are truly dead

        Returns:
            True if all party members are dead, False otherwise
        """
        for char in self.characters:
            # If character has is_dead property (supports death saves)
            if hasattr(char, 'is_dead'):
                if not char.is_dead:
                    return False  # At least one character is not dead
            else:
                # Fallback to is_alive for characters without death saves
                if char.is_alive:
                    return False

        # All characters are dead
        return True

    def add_character(self, character: Character) -> None:
        """
        Add a character to the party.

        Args:
            character: Character to add
        """
        if character not in self.characters:
            self.characters.append(character)

    def remove_character(self, character: Character) -> None:
        """
        Remove a character from the party.

        Used when a character leaves the party (not the same as death).

        Args:
            character: Character to remove
        """
        if character in self.characters:
            self.characters.remove(character)

    def get_character_by_name(self, name: str) -> Optional[Character]:
        """
        Find a character in the party by name.

        Args:
            name: Name of the character to find (case-insensitive)

        Returns:
            Character object if found, None otherwise
        """
        for char in self.characters:
            if char.name.lower() == name.lower():
                return char
        return None

    def __len__(self) -> int:
        """Return the number of characters in the party."""
        return len(self.characters)

    def __str__(self) -> str:
        """String representation of the party."""
        if not self.characters:
            return "Party: (empty)"

        char_list = ", ".join(f"{char.name} ({char.current_hp}/{char.max_hp} HP)" for char in self.characters)
        return f"Party ({len(self.characters)} members): {char_list}"
