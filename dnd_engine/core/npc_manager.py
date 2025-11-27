# ABOUTME: NPC manager for loading, accessing, and tracking NPC state
# ABOUTME: Provides room-based NPC lookup and state persistence

import logging
from typing import TYPE_CHECKING, Any

from dnd_engine.core.npc import NPC

if TYPE_CHECKING:
    from dnd_engine.rules.loader import DataLoader

logger = logging.getLogger(__name__)


class NPCManager:
    """
    Manages NPCs for a campaign.

    Responsibilities:
    - Load NPC definitions from campaign JSON
    - Provide room-based NPC lookup
    - Track runtime NPC state (location, reputation, shop stock)
    - Serialize/deserialize NPC state for saving
    """

    def __init__(self, campaign_id: str, data_loader: "DataLoader"):
        """
        Initialize NPC manager for a campaign.

        Args:
            campaign_id: Campaign identifier (e.g., "the_unquiet_dead")
            data_loader: Data loader for content access
        """
        self.campaign_id = campaign_id
        self.data_loader = data_loader
        self.npcs: dict[str, NPC] = {}

        self._load_npcs()

    def _load_npcs(self) -> None:
        """Load NPC definitions from campaign JSON."""
        try:
            npc_data = self.data_loader.load_npcs(self.campaign_id)
            for npc_id, npc_dict in npc_data.get("npcs", {}).items():
                self.npcs[npc_id] = NPC.from_dict(npc_dict)
            logger.info(
                f"Loaded {len(self.npcs)} NPCs for campaign '{self.campaign_id}'"
            )
        except FileNotFoundError:
            logger.warning(f"No NPC file found for campaign '{self.campaign_id}'")

    def get_npc(self, npc_id: str) -> NPC | None:
        """Get NPC by ID."""
        return self.npcs.get(npc_id)

    def get_npc_by_name(self, name: str) -> NPC | None:
        """
        Get NPC by name (case-insensitive partial match).

        Args:
            name: Full or partial NPC name

        Returns:
            Matching NPC or None
        """
        name_lower = name.lower()
        for npc in self.npcs.values():
            if name_lower in npc.name.lower():
                return npc
        return None

    def get_npcs_in_room(self, room_guid: str) -> list[NPC]:
        """Get all NPCs currently in a specific room."""
        return [npc for npc in self.npcs.values() if npc.current_location == room_guid]

    def get_all_npcs(self) -> list[NPC]:
        """Get all NPCs in the campaign."""
        return list(self.npcs.values())

    def update_npc_locations(self, time_of_day: str) -> list[tuple[NPC, str, str]]:
        """
        Update NPC locations based on schedules.

        Args:
            time_of_day: Current time period (morning, afternoon, evening, night)

        Returns:
            List of (npc, old_location, new_location) for NPCs that moved
        """
        movements = []
        for npc in self.npcs.values():
            if npc.schedule and time_of_day in npc.schedule:
                new_location = npc.schedule[time_of_day]
                if new_location != npc.current_location:
                    old_location = npc.current_location
                    npc.move_to(new_location)
                    movements.append((npc, old_location, new_location))
        return movements

    def serialize_state(self) -> dict[str, Any]:
        """Serialize NPC runtime state for saving."""
        return {npc_id: npc.to_dict() for npc_id, npc in self.npcs.items()}

    def deserialize_state(self, saved_state: dict[str, Any]) -> None:
        """Restore NPC runtime state from saved data."""
        for npc_id, state in saved_state.items():
            if npc_id in self.npcs:
                npc = self.npcs[npc_id]
                npc.current_location = state.get("current_location", npc.home_location)
                npc.player_reputation = state.get("player_reputation", 0)

                # Restore shop stock
                if npc.shop and "shop_stock" in state:
                    for item in npc.shop.inventory:
                        if item.item_id in state["shop_stock"]:
                            item.stock = state["shop_stock"][item.item_id]
