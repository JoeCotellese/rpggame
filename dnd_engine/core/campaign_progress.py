# ABOUTME: Campaign progression tracker for multi-dungeon campaigns
# ABOUTME: Loads campaign definitions, tracks dungeon completion, and handles unlock logic

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DungeonDefinition:
    """Definition of a dungeon within a campaign."""

    id: str
    name: str
    order: int
    unlocked_by_default: bool
    boss_defeated_required: bool
    required_quest_items: list[str]
    unlocks: list[str]
    final_dungeon: bool = False


@dataclass
class CampaignDefinition:
    """
    Static campaign definition loaded from JSON.

    Defines the structure of a campaign: which dungeons it contains,
    their order, and unlock requirements.
    """

    id: str
    name: str
    description: str
    level_range: str
    estimated_playtime: str
    starting_room: str
    dungeons: dict[str, DungeonDefinition]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CampaignDefinition":
        """Load campaign definition from dictionary."""
        dungeons = {}
        for dungeon_id, dungeon_data in data.get("dungeons", {}).items():
            # Handle null completion_criteria (None from JSON null)
            completion = dungeon_data.get("completion_criteria") or {}
            dungeons[dungeon_id] = DungeonDefinition(
                id=dungeon_id,
                name=dungeon_data.get("name", dungeon_id),
                order=dungeon_data.get("order", 0),
                unlocked_by_default=dungeon_data.get("unlocked_by_default", False),
                boss_defeated_required=completion.get("boss_defeated", False),
                required_quest_items=completion.get("required_quest_items", []),
                unlocks=dungeon_data.get("unlocks", []),
                final_dungeon=dungeon_data.get("final_dungeon", False),
            )

        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            level_range=data.get("level_range", "1-20"),
            estimated_playtime=data.get("estimated_playtime", "Unknown"),
            starting_room=data.get("starting_room", ""),
            dungeons=dungeons,
        )


@dataclass
class CampaignProgress:
    """
    Player's progress through a campaign.

    Stored in save files, tracks which dungeons have been completed
    and which are currently unlocked.
    """

    campaign_id: str
    completed_dungeons: list[str] = field(default_factory=list)
    unlocked_dungeons: list[str] = field(default_factory=list)
    boss_defeats: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize progress to dictionary for save files."""
        return {
            "campaign_id": self.campaign_id,
            "completed_dungeons": self.completed_dungeons,
            "unlocked_dungeons": self.unlocked_dungeons,
            "boss_defeats": self.boss_defeats,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CampaignProgress":
        """Load progress from save file dictionary."""
        return cls(
            campaign_id=data.get("campaign_id", ""),
            completed_dungeons=data.get("completed_dungeons", []),
            unlocked_dungeons=data.get("unlocked_dungeons", []),
            boss_defeats=data.get("boss_defeats", {}),
        )


class CampaignProgressTracker:
    """
    Manages campaign progression for multi-dungeon campaigns.

    Responsibilities:
    - Load campaign definitions from JSON files
    - Track which dungeons are completed/unlocked
    - Detect dungeon completion (boss defeated + quest items)
    - Handle unlock logic when dungeons are completed
    """

    def __init__(self, campaigns_dir: Path | None = None):
        """
        Initialize campaign progress tracker.

        Args:
            campaigns_dir: Directory containing campaign JSON files.
                          Defaults to dnd_engine/data/content/campaigns/
        """
        if campaigns_dir is None:
            campaigns_dir = (
                Path(__file__).parent.parent / "data" / "content" / "campaigns"
            )
        self.campaigns_dir = Path(campaigns_dir)
        self._definitions: dict[str, CampaignDefinition] = {}

    def load_campaign_definition(self, campaign_id: str) -> CampaignDefinition | None:
        """
        Load a campaign definition by ID.

        Args:
            campaign_id: Campaign identifier (e.g., "the_unquiet_dead")

        Returns:
            CampaignDefinition or None if not found
        """
        if campaign_id in self._definitions:
            return self._definitions[campaign_id]

        campaign_file = self.campaigns_dir / campaign_id / "campaign.json"
        if not campaign_file.exists():
            logger.warning(f"Campaign definition not found: {campaign_file}")
            return None

        try:
            with open(campaign_file, encoding="utf-8") as f:
                data = json.load(f)
            definition = CampaignDefinition.from_dict(data)
            self._definitions[campaign_id] = definition
            return definition
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error loading campaign {campaign_id}: {e}")
            return None

    def list_available_campaigns(self) -> list[CampaignDefinition]:
        """
        List all available campaign definitions.

        Returns:
            List of CampaignDefinition objects
        """
        campaigns = []
        if not self.campaigns_dir.exists():
            return campaigns

        for campaign_dir in self.campaigns_dir.iterdir():
            if campaign_dir.is_dir() and (campaign_dir / "campaign.json").exists():
                campaign_id = campaign_dir.name
                definition = self.load_campaign_definition(campaign_id)
                if definition:
                    campaigns.append(definition)

        return sorted(campaigns, key=lambda c: c.name)

    def create_initial_progress(self, campaign_id: str) -> CampaignProgress | None:
        """
        Create initial progress for a new campaign playthrough.

        Args:
            campaign_id: Campaign to start

        Returns:
            CampaignProgress with default-unlocked dungeons, or None if invalid
        """
        definition = self.load_campaign_definition(campaign_id)
        if not definition:
            return None

        unlocked = [
            dungeon_id
            for dungeon_id, dungeon in definition.dungeons.items()
            if dungeon.unlocked_by_default
        ]

        return CampaignProgress(
            campaign_id=campaign_id,
            completed_dungeons=[],
            unlocked_dungeons=unlocked,
            boss_defeats={},
        )

    def is_dungeon_unlocked(
        self, progress: CampaignProgress, dungeon_id: str
    ) -> bool:
        """
        Check if a dungeon is unlocked for play.

        Args:
            progress: Current campaign progress
            dungeon_id: Dungeon to check

        Returns:
            True if dungeon is unlocked
        """
        return dungeon_id in progress.unlocked_dungeons

    def is_dungeon_completed(
        self, progress: CampaignProgress, dungeon_id: str
    ) -> bool:
        """
        Check if a dungeon has been completed.

        Args:
            progress: Current campaign progress
            dungeon_id: Dungeon to check

        Returns:
            True if dungeon is completed
        """
        return dungeon_id in progress.completed_dungeons

    def get_dungeon_state(
        self, progress: CampaignProgress, dungeon_id: str
    ) -> str:
        """
        Get the state of a dungeon for UI display.

        Args:
            progress: Current campaign progress
            dungeon_id: Dungeon to check

        Returns:
            "completed", "unlocked", or "locked"
        """
        if self.is_dungeon_completed(progress, dungeon_id):
            return "completed"
        elif self.is_dungeon_unlocked(progress, dungeon_id):
            return "unlocked"
        else:
            return "locked"

    def check_dungeon_completion(
        self,
        progress: CampaignProgress,
        dungeon_id: str,
        boss_defeated: bool,
        inventory_item_ids: list[str],
    ) -> bool:
        """
        Check if a dungeon's completion criteria are met.

        Args:
            progress: Current campaign progress
            dungeon_id: Dungeon to check
            boss_defeated: Whether the boss has been defeated
            inventory_item_ids: List of item IDs in party inventory

        Returns:
            True if all completion criteria are met
        """
        definition = self.load_campaign_definition(progress.campaign_id)
        if not definition or dungeon_id not in definition.dungeons:
            return False

        dungeon = definition.dungeons[dungeon_id]

        # Check boss defeat requirement
        if dungeon.boss_defeated_required and not boss_defeated:
            return False

        # Check quest item requirements
        for item_id in dungeon.required_quest_items:
            if item_id not in inventory_item_ids:
                return False

        return True

    def record_boss_defeat(
        self, progress: CampaignProgress, dungeon_id: str
    ) -> None:
        """
        Record that a boss has been defeated in a dungeon.

        Args:
            progress: Campaign progress to update
            dungeon_id: Dungeon where boss was defeated
        """
        progress.boss_defeats[dungeon_id] = True

    def complete_dungeon(
        self,
        progress: CampaignProgress,
        dungeon_id: str,
        inventory_item_ids: list[str],
    ) -> list[str]:
        """
        Mark a dungeon as completed and unlock subsequent dungeons.

        Args:
            progress: Campaign progress to update
            dungeon_id: Dungeon that was completed
            inventory_item_ids: Items in party inventory (for criteria check)

        Returns:
            List of newly unlocked dungeon IDs
        """
        definition = self.load_campaign_definition(progress.campaign_id)
        if not definition or dungeon_id not in definition.dungeons:
            return []

        # Check if already completed
        if dungeon_id in progress.completed_dungeons:
            return []

        # Verify completion criteria
        boss_defeated = progress.boss_defeats.get(dungeon_id, False)
        if not self.check_dungeon_completion(
            progress, dungeon_id, boss_defeated, inventory_item_ids
        ):
            return []

        # Mark as completed
        progress.completed_dungeons.append(dungeon_id)

        # Unlock subsequent dungeons
        dungeon = definition.dungeons[dungeon_id]
        newly_unlocked = []

        for unlock_id in dungeon.unlocks:
            if unlock_id not in progress.unlocked_dungeons:
                progress.unlocked_dungeons.append(unlock_id)
                newly_unlocked.append(unlock_id)
                logger.info(f"Unlocked dungeon: {unlock_id}")

        return newly_unlocked

    def is_campaign_complete(self, progress: CampaignProgress) -> bool:
        """
        Check if the entire campaign has been completed.

        Args:
            progress: Campaign progress to check

        Returns:
            True if the final dungeon has been completed
        """
        definition = self.load_campaign_definition(progress.campaign_id)
        if not definition:
            return False

        for dungeon_id, dungeon in definition.dungeons.items():
            if dungeon.final_dungeon:
                return dungeon_id in progress.completed_dungeons

        # No final dungeon defined - check if all dungeons completed
        return all(
            d_id in progress.completed_dungeons for d_id in definition.dungeons
        )

    def get_ordered_dungeons(
        self, campaign_id: str
    ) -> list[tuple[str, DungeonDefinition]]:
        """
        Get dungeons in order for UI display.

        Args:
            campaign_id: Campaign to get dungeons for

        Returns:
            List of (dungeon_id, DungeonDefinition) tuples sorted by order
        """
        definition = self.load_campaign_definition(campaign_id)
        if not definition:
            return []

        return sorted(
            definition.dungeons.items(), key=lambda x: x[1].order
        )
