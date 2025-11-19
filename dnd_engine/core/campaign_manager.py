# ABOUTME: Campaign management system for creating, loading, and organizing campaigns
# ABOUTME: Handles campaign directories, save slots, and integration with existing SaveManager

import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from dnd_engine.core.campaign import Campaign, SaveSlotMetadata
from dnd_engine.core.save_manager import SaveManager
from dnd_engine.core.game_state import GameState
from dnd_engine.utils.events import EventBus
from dnd_engine.rules.loader import DataLoader
from dnd_engine.core.dice import DiceRoller


class CampaignManager:
    """
    Manages D&D campaigns with save slots and metadata.

    Responsibilities:
    - Create new campaigns
    - Load existing campaigns
    - List all campaigns with metadata
    - Manage save slots within campaigns (auto, quick, manual)
    - Track playtime and timestamps
    - Organize campaigns in directory structure
    """

    def __init__(self, campaigns_dir: Optional[Path] = None):
        """
        Initialize campaign manager.

        Args:
            campaigns_dir: Root directory for campaigns (defaults to ~/.dnd_terminal/campaigns)
        """
        if campaigns_dir is None:
            campaigns_dir = Path.home() / ".dnd_terminal" / "campaigns"

        self.campaigns_dir = Path(campaigns_dir)
        self.campaigns_dir.mkdir(parents=True, exist_ok=True)

    def create_campaign(
        self,
        name: str,
        dungeon_name: Optional[str] = None,
        party_character_ids: Optional[List[str]] = None
    ) -> Campaign:
        """
        Create a new campaign.

        Args:
            name: Campaign name (must be unique)
            dungeon_name: Optional dungeon filename to start with
            party_character_ids: Optional list of character IDs in party

        Returns:
            Created Campaign instance

        Raises:
            ValueError: If campaign name already exists or is invalid
        """
        # Validate name
        if not name or not name.strip():
            raise ValueError("Campaign name cannot be empty")

        # Sanitize name for use as directory name
        safe_name = self._sanitize_campaign_name(name)

        # Check if campaign already exists
        campaign_dir = self.campaigns_dir / safe_name
        if campaign_dir.exists():
            raise ValueError(f"Campaign '{name}' already exists")

        # Create campaign directory structure
        campaign_dir.mkdir(parents=True, exist_ok=True)
        (campaign_dir / "saves").mkdir(exist_ok=True)
        (campaign_dir / "party").mkdir(exist_ok=True)

        # Create campaign metadata
        now = datetime.now()
        campaign = Campaign(
            name=name,
            created_at=now,
            last_played=now,
            playtime_seconds=0,
            current_dungeon=dungeon_name,
            current_room=None,
            party_character_ids=party_character_ids or [],
            save_version="1.0.0"
        )

        # Save campaign metadata
        self._save_campaign_metadata(safe_name, campaign)

        return campaign

    def load_campaign(self, campaign_name: str) -> Campaign:
        """
        Load campaign metadata.

        Args:
            campaign_name: Name of the campaign to load

        Returns:
            Campaign instance with metadata

        Raises:
            FileNotFoundError: If campaign doesn't exist
        """
        safe_name = self._sanitize_campaign_name(campaign_name)
        campaign_dir = self.campaigns_dir / safe_name

        if not campaign_dir.exists():
            raise FileNotFoundError(f"Campaign '{campaign_name}' not found")

        metadata_path = campaign_dir / "campaign.json"
        if not metadata_path.exists():
            raise FileNotFoundError(f"Campaign metadata not found for '{campaign_name}'")

        with open(metadata_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return Campaign.from_dict(data)

    def save_campaign_state(
        self,
        campaign_name: str,
        game_state: GameState,
        slot_name: str = "auto",
        save_type: str = "auto"
    ) -> Path:
        """
        Save game state to a campaign save slot.

        Args:
            campaign_name: Name of the campaign
            game_state: Current game state to save
            slot_name: Save slot name ('auto', 'quick', or custom name)
            save_type: Type of save ('auto', 'quick', or 'manual')

        Returns:
            Path to the saved file

        Raises:
            FileNotFoundError: If campaign doesn't exist
        """
        safe_name = self._sanitize_campaign_name(campaign_name)
        campaign_dir = self.campaigns_dir / safe_name

        if not campaign_dir.exists():
            raise FileNotFoundError(f"Campaign '{campaign_name}' not found")

        # Create SaveManager for this campaign's saves directory
        saves_dir = campaign_dir / "saves"
        save_manager = SaveManager(saves_dir=saves_dir)

        # Determine save file name based on slot
        if slot_name == "auto":
            save_file_name = "save_auto"
        elif slot_name == "quick":
            save_file_name = "save_quick"
        else:
            # Custom save: use timestamp to make unique
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_slot_name = self._sanitize_filename(slot_name)
            save_file_name = f"save_{safe_slot_name}_{timestamp}"

        # Save the game state
        auto_save = (save_type == "auto")
        save_path = save_manager.save_game(
            game_state=game_state,
            save_name=save_file_name,
            auto_save=auto_save
        )

        # Update campaign metadata
        campaign = self.load_campaign(campaign_name)
        campaign.last_played = datetime.now()
        campaign.current_dungeon = game_state.dungeon_name
        campaign.current_room = game_state.current_room_id

        # Update party character IDs
        campaign.party_character_ids = [char.name for char in game_state.party.characters]

        self._save_campaign_metadata(safe_name, campaign)

        return save_path

    def load_campaign_state(
        self,
        campaign_name: str,
        slot_name: str = "auto",
        event_bus: Optional[EventBus] = None,
        data_loader: Optional[DataLoader] = None,
        dice_roller: Optional[DiceRoller] = None
    ) -> GameState:
        """
        Load game state from a campaign save slot.

        Args:
            campaign_name: Name of the campaign
            slot_name: Save slot name ('auto', 'quick', or custom save name)
            event_bus: Event bus for the game (creates new if not provided)
            data_loader: Data loader for content (creates new if not provided)
            dice_roller: Dice roller (creates new if not provided)

        Returns:
            Loaded GameState

        Raises:
            FileNotFoundError: If campaign or save slot doesn't exist
        """
        safe_name = self._sanitize_campaign_name(campaign_name)
        campaign_dir = self.campaigns_dir / safe_name

        if not campaign_dir.exists():
            raise FileNotFoundError(f"Campaign '{campaign_name}' not found")

        # Create SaveManager for this campaign's saves directory
        saves_dir = campaign_dir / "saves"
        save_manager = SaveManager(saves_dir=saves_dir)

        # Determine save file name based on slot
        if slot_name == "auto":
            save_file_name = "save_auto"
        elif slot_name == "quick":
            save_file_name = "save_quick"
        else:
            # For custom saves, we need to find the matching file
            # This is a simplified approach - in practice, you'd want a better lookup
            save_file_name = slot_name

        # Load the game state
        game_state = save_manager.load_game(
            save_name=save_file_name,
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller
        )

        # Update campaign last_played timestamp
        campaign = self.load_campaign(campaign_name)
        campaign.last_played = datetime.now()
        self._save_campaign_metadata(safe_name, campaign)

        return game_state

    def list_campaigns(self) -> List[Campaign]:
        """
        List all available campaigns with metadata.

        Returns:
            List of Campaign instances, sorted by last_played (most recent first)
        """
        campaigns = []

        for campaign_dir in self.campaigns_dir.iterdir():
            if not campaign_dir.is_dir():
                continue

            metadata_path = campaign_dir / "campaign.json"
            if not metadata_path.exists():
                continue

            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                campaign = Campaign.from_dict(data)
                campaigns.append(campaign)
            except (json.JSONDecodeError, KeyError, ValueError):
                # Skip corrupted campaign metadata
                continue

        # Sort by last_played (most recent first)
        campaigns.sort(key=lambda c: c.last_played, reverse=True)

        return campaigns

    def list_save_slots(self, campaign_name: str) -> List[SaveSlotMetadata]:
        """
        List all save slots for a campaign.

        Args:
            campaign_name: Name of the campaign

        Returns:
            List of SaveSlotMetadata instances

        Raises:
            FileNotFoundError: If campaign doesn't exist
        """
        safe_name = self._sanitize_campaign_name(campaign_name)
        campaign_dir = self.campaigns_dir / safe_name

        if not campaign_dir.exists():
            raise FileNotFoundError(f"Campaign '{campaign_name}' not found")

        saves_dir = campaign_dir / "saves"
        save_slots = []

        for save_file in saves_dir.glob("*.json"):
            try:
                with open(save_file, 'r', encoding='utf-8') as f:
                    save_data = json.load(f)

                metadata = save_data.get("metadata", {})
                game_state_data = save_data.get("game_state", {})
                party_data = save_data.get("party", [])

                # Determine save type from filename and metadata
                if save_file.stem == "save_auto":
                    save_type = "auto"
                elif save_file.stem == "save_quick":
                    save_type = "quick"
                else:
                    save_type = "manual"

                # Build party HP summary
                party_hp_parts = []
                for char_data in party_data:
                    name = char_data.get("name", "Unknown")
                    current_hp = char_data.get("current_hp", 0)
                    max_hp = char_data.get("max_hp", 1)
                    party_hp_parts.append(f"{name} {current_hp}/{max_hp}")
                party_hp_summary = ", ".join(party_hp_parts)

                # Get location description
                current_room = game_state_data.get("current_room_id", "Unknown")
                dungeon_name = game_state_data.get("dungeon_name", "Unknown")
                location = f"{dungeon_name} - Room {current_room}"

                save_slot = SaveSlotMetadata(
                    slot_name=save_file.stem,
                    created_at=datetime.fromisoformat(metadata.get("created", metadata.get("last_played", datetime.now().isoformat()))),
                    location=location,
                    party_hp_summary=party_hp_summary,
                    save_type=save_type
                )
                save_slots.append(save_slot)

            except (json.JSONDecodeError, KeyError, ValueError):
                # Skip corrupted save files
                continue

        # Sort: auto first, quick second, then manual (each by newest first)
        def sort_key(slot: SaveSlotMetadata):
            # Use negative timestamp to get newest first within each type
            timestamp = -slot.created_at.timestamp()
            if slot.save_type == "auto":
                return (0, timestamp)
            elif slot.save_type == "quick":
                return (1, timestamp)
            else:
                return (2, timestamp)

        save_slots.sort(key=sort_key)

        return save_slots

    def delete_campaign(self, campaign_name: str) -> bool:
        """
        Delete a campaign and all its save files.

        Args:
            campaign_name: Name of the campaign to delete

        Returns:
            True if campaign was deleted, False if it didn't exist
        """
        safe_name = self._sanitize_campaign_name(campaign_name)
        campaign_dir = self.campaigns_dir / safe_name

        if not campaign_dir.exists():
            return False

        # Delete the entire campaign directory
        import shutil
        shutil.rmtree(campaign_dir)

        return True

    def get_most_recent_campaign(self) -> Optional[Campaign]:
        """
        Get the most recently played campaign.

        Returns:
            Campaign instance or None if no campaigns exist
        """
        campaigns = self.list_campaigns()
        return campaigns[0] if campaigns else None

    def _save_campaign_metadata(self, safe_campaign_name: str, campaign: Campaign) -> None:
        """
        Save campaign metadata to disk.

        Args:
            safe_campaign_name: Sanitized campaign name (directory name)
            campaign: Campaign instance to save
        """
        campaign_dir = self.campaigns_dir / safe_campaign_name
        metadata_path = campaign_dir / "campaign.json"

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(campaign.to_dict(), f, indent=2, ensure_ascii=False)

    def _sanitize_campaign_name(self, name: str) -> str:
        """
        Sanitize campaign name for use as directory name.

        Args:
            name: Campaign name

        Returns:
            Safe directory name
        """
        # Convert to lowercase and replace spaces with underscores
        safe_name = name.lower().strip()
        safe_name = safe_name.replace(" ", "_")

        # Remove invalid characters (replace with underscore, then dedupe)
        invalid_chars = '<>:"/\\|?*!@#$%^&()+=[]{};\',.'
        for char in invalid_chars:
            safe_name = safe_name.replace(char, '_')

        # Remove consecutive underscores
        while '__' in safe_name:
            safe_name = safe_name.replace('__', '_')

        # Remove leading/trailing underscores
        safe_name = safe_name.strip('_')

        # Ensure it's not empty
        if not safe_name:
            safe_name = "campaign"

        return safe_name

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to remove invalid characters.

        Args:
            filename: Proposed filename

        Returns:
            Sanitized filename
        """
        # Remove invalid filename characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')

        # Replace spaces with underscores
        filename = filename.replace(" ", "_")

        # Remove leading/trailing spaces and dots
        filename = filename.strip('. ')

        # Ensure it's not empty after sanitization
        if not filename:
            filename = "save"

        return filename
