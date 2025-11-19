# ABOUTME: Campaign data model representing a named campaign with party and save state
# ABOUTME: Provides campaign metadata, save slot management, and playtime tracking

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from pathlib import Path


@dataclass
class Campaign:
    """
    Represents a D&D campaign with metadata and save state.

    A campaign bundles together:
    - A unique name
    - A party of characters
    - A dungeon/adventure
    - Save slots (auto-save, manual saves, named saves)
    - Play session metadata (playtime, timestamps)
    """

    name: str
    """Campaign name (used as directory name)"""

    created_at: datetime
    """When the campaign was created"""

    last_played: datetime
    """When the campaign was last loaded"""

    playtime_seconds: int = 0
    """Total time spent playing this campaign (in seconds)"""

    current_dungeon: Optional[str] = None
    """Current dungeon filename (e.g., 'tomb_of_horrors')"""

    current_room: Optional[str] = None
    """Current room ID in the dungeon"""

    party_character_ids: List[str] = field(default_factory=list)
    """List of character IDs/names in the party"""

    save_version: str = "1.0.0"
    """Save file version for compatibility checking"""

    def to_dict(self) -> dict:
        """
        Convert campaign to dictionary for JSON serialization.

        Returns:
            Dictionary representation of campaign
        """
        return {
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "last_played": self.last_played.isoformat(),
            "playtime_seconds": self.playtime_seconds,
            "current_dungeon": self.current_dungeon,
            "current_room": self.current_room,
            "party_character_ids": self.party_character_ids,
            "save_version": self.save_version
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Campaign":
        """
        Create campaign from dictionary (loaded from JSON).

        Args:
            data: Dictionary representation of campaign

        Returns:
            Campaign instance
        """
        return cls(
            name=data["name"],
            created_at=datetime.fromisoformat(data["created_at"]),
            last_played=datetime.fromisoformat(data["last_played"]),
            playtime_seconds=data.get("playtime_seconds", 0),
            current_dungeon=data.get("current_dungeon"),
            current_room=data.get("current_room"),
            party_character_ids=data.get("party_character_ids", []),
            save_version=data.get("save_version", "1.0.0")
        )

    def get_playtime_display(self) -> str:
        """
        Get human-readable playtime string.

        Returns:
            Formatted playtime (e.g., "6h 23m", "45m", "2d 3h")
        """
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


@dataclass
class SaveSlotMetadata:
    """
    Metadata for a save slot within a campaign.

    Used to display save slot information without loading the full save file.
    """

    slot_name: str
    """Save slot name (e.g., 'auto', 'quick', 'custom_123456')"""

    created_at: datetime
    """When this save was created"""

    location: Optional[str] = None
    """Current location description (e.g., 'Room 12 - The Crypt')"""

    party_hp_summary: Optional[str] = None
    """Party HP summary (e.g., 'Aria 23/30, Zephyr 18/18')"""

    save_type: str = "manual"
    """Type of save: 'auto', 'quick', or 'manual'"""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "slot_name": self.slot_name,
            "created_at": self.created_at.isoformat(),
            "location": self.location,
            "party_hp_summary": self.party_hp_summary,
            "save_type": self.save_type
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SaveSlotMetadata":
        """Create from dictionary (loaded from JSON)."""
        return cls(
            slot_name=data["slot_name"],
            created_at=datetime.fromisoformat(data["created_at"]),
            location=data.get("location"),
            party_hp_summary=data.get("party_hp_summary"),
            save_type=data.get("save_type", "manual")
        )

    def get_time_display(self) -> str:
        """
        Get human-readable timestamp for this save.

        Returns:
            Formatted relative time (e.g., "2 minutes ago", "yesterday")
        """
        now = datetime.now()
        delta = now - self.created_at

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

        if days == 1:
            return "yesterday"
        elif days < 7:
            return f"{days} days ago"
        elif days < 30:
            weeks = days // 7
            return f"{weeks} week{'s' if weeks > 1 else ''} ago"
        else:
            # For older saves, show actual date
            return self.created_at.strftime("%b %d, %Y at %I:%M %p")
