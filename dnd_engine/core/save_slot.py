# ABOUTME: Save slot data model for the new 10-slot save system
# ABOUTME: Provides slot management, auto-naming, metadata tracking, and serialization

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path


@dataclass
class SaveSlot:
    """
    Represents a single save slot in the new 10-slot save system.

    Replaces the old Campaign > Save > Adventure hierarchy with a flat structure.
    Each slot contains complete game state with auto-generated descriptive names.
    """

    slot_number: int
    """Slot number (1-10)"""

    created_at: datetime
    """When this save slot was first created"""

    last_played: datetime
    """When this save slot was last loaded"""

    playtime_seconds: int = 0
    """Total playtime for this save (in seconds)"""

    adventure_name: Optional[str] = None
    """Current adventure/dungeon name (e.g., 'Tomb of Horrors')"""

    adventure_progress: Optional[str] = None
    """Current progress description (e.g., 'Room 12')"""

    party_composition: List[str] = field(default_factory=list)
    """List of character names in the party"""

    party_levels: List[int] = field(default_factory=list)
    """List of character levels (parallel to party_composition)"""

    custom_name: Optional[str] = None
    """User-provided custom name (overrides auto-generated name)"""

    save_version: str = "2.0.0"
    """Save file version for compatibility checking"""

    def get_display_name(self) -> str:
        """
        Get the display name for this save slot.

        Uses custom name if set, otherwise generates from slot data.
        Format: "{Adventure} - {Party} - {Progress} - {Playtime}"

        Returns:
            Display name for the save slot
        """
        if self.custom_name:
            return self.custom_name

        return self.generate_auto_name()

    def generate_auto_name(self) -> str:
        """
        Generate auto-name from slot data.

        Format: "{Adventure} - {Party} - {Progress} - {Playtime}"
        Examples:
            - "Tomb of Horrors - Aria, Zephyr - Room 12 - 2h 30m"
            - "Lost Mine - Solo Ranger - Level 3 - 45m"
            - "Empty Slot 1"

        Returns:
            Auto-generated descriptive name
        """
        # Empty slot
        if not self.adventure_name:
            return f"Empty Slot {self.slot_number}"

        # Adventure part
        adventure_part = self.adventure_name

        # Party part
        if self.party_composition:
            if len(self.party_composition) == 1:
                party_part = self.party_composition[0]
            elif len(self.party_composition) <= 3:
                party_part = ", ".join(self.party_composition)
            else:
                # Show first 2 names + count
                first_two = ", ".join(self.party_composition[:2])
                remaining = len(self.party_composition) - 2
                party_part = f"{first_two} +{remaining}"
        else:
            party_part = "No Party"

        # Progress part
        if self.adventure_progress:
            progress_part = self.adventure_progress
        elif self.party_levels:
            avg_level = sum(self.party_levels) // len(self.party_levels)
            progress_part = f"Level {avg_level}"
        else:
            progress_part = "Just Started"

        # Playtime part
        playtime_part = self._format_playtime()

        return f"{adventure_part} - {party_part} - {progress_part} - {playtime_part}"

    def _format_playtime(self) -> str:
        """
        Format playtime as human-readable string.

        Returns:
            Formatted playtime (e.g., "2h 30m", "45m", "1d 3h")
        """
        if self.playtime_seconds == 0:
            return "0m"

        seconds = self.playtime_seconds

        if seconds < 60:
            return f"{seconds}s"

        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m"

        hours = minutes // 60
        remaining_minutes = minutes % 60

        if hours < 24:
            if remaining_minutes > 0:
                return f"{hours}h {remaining_minutes}m"
            return f"{hours}h"

        days = hours // 24
        remaining_hours = hours % 24

        if remaining_hours > 0:
            return f"{days}d {remaining_hours}h"
        return f"{days}d"

    def get_last_played_display(self) -> str:
        """
        Get human-readable "last played" string (relative time).

        Returns:
            Formatted relative time (e.g., "2 hours ago", "3 days ago")
        """
        now = datetime.now()
        delta = now - self.last_played

        seconds = int(delta.total_seconds())

        if seconds < 60:
            return "just now"

        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"

        hours = minutes // 60
        if hours < 24:
            return f"{hours} hour{'s' if hours > 1 else ''} ago"

        days = hours // 24
        if days < 30:
            return f"{days} day{'s' if days > 1 else ''} ago"

        months = days // 30
        if months < 12:
            return f"{months} month{'s' if months > 1 else ''} ago"

        years = days // 365
        return f"{years} year{'s' if years > 1 else ''} ago"

    def is_empty(self) -> bool:
        """
        Check if this save slot is empty (unused).

        Returns:
            True if slot has never been used
        """
        return self.adventure_name is None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert save slot to dictionary for JSON serialization.

        Returns:
            Dictionary representation of save slot metadata
        """
        return {
            "slot_number": self.slot_number,
            "created_at": self.created_at.isoformat(),
            "last_played": self.last_played.isoformat(),
            "playtime_seconds": self.playtime_seconds,
            "adventure_name": self.adventure_name,
            "adventure_progress": self.adventure_progress,
            "party_composition": self.party_composition,
            "party_levels": self.party_levels,
            "custom_name": self.custom_name,
            "save_version": self.save_version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SaveSlot":
        """
        Create save slot from dictionary (loaded from JSON).

        Args:
            data: Dictionary representation of save slot

        Returns:
            SaveSlot instance
        """
        return cls(
            slot_number=data["slot_number"],
            created_at=datetime.fromisoformat(data["created_at"]),
            last_played=datetime.fromisoformat(data["last_played"]),
            playtime_seconds=data.get("playtime_seconds", 0),
            adventure_name=data.get("adventure_name"),
            adventure_progress=data.get("adventure_progress"),
            party_composition=data.get("party_composition", []),
            party_levels=data.get("party_levels", []),
            custom_name=data.get("custom_name"),
            save_version=data.get("save_version", "2.0.0")
        )

    @classmethod
    def create_empty(cls, slot_number: int) -> "SaveSlot":
        """
        Create an empty save slot.

        Args:
            slot_number: Slot number (1-10)

        Returns:
            Empty SaveSlot instance
        """
        now = datetime.now()
        return cls(
            slot_number=slot_number,
            created_at=now,
            last_played=now,
            playtime_seconds=0,
            adventure_name=None,
            adventure_progress=None,
            party_composition=[],
            party_levels=[],
            custom_name=None,
            save_version="2.0.0"
        )
