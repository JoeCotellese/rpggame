# ABOUTME: Room registry that maps room GUIDs to dungeon files for cross-dungeon navigation.
# ABOUTME: Scans dungeon files on init and provides room lookup by GUID.

import json
from pathlib import Path
from typing import Any


class RoomRegistry:
    """
    Registry that maps room GUIDs to their dungeon files.

    Room GUIDs follow the format: prefix.room_name (e.g., crypt.entrance, arden.town_square)
    The prefix identifies which dungeon the room belongs to.
    """

    def __init__(self, dungeons_path: Path):
        """
        Initialize the room registry by scanning all dungeon files.

        Args:
            dungeons_path: Path to the dungeons directory
        """
        self.dungeons_path = dungeons_path
        # Maps room GUID prefix to dungeon filename (without .json)
        self._prefix_to_dungeon: dict[str, str] = {}
        # Maps dungeon filename to loaded dungeon data (lazy loaded)
        self._loaded_dungeons: dict[str, dict[str, Any]] = {}

        self._scan_dungeons()

    def _scan_dungeons(self) -> None:
        """Scan all dungeon files and build the prefix-to-dungeon mapping."""
        for dungeon_file in self.dungeons_path.glob("*.json"):
            # Skip generated dungeons
            if dungeon_file.stem.startswith("generated_"):
                continue

            try:
                with open(dungeon_file) as f:
                    dungeon_data = json.load(f)

                # Get room prefixes from the rooms dict
                rooms = dungeon_data.get("rooms", {})
                for room_id in rooms.keys():
                    prefix = self._get_prefix(room_id)
                    if prefix:
                        self._prefix_to_dungeon[prefix] = dungeon_file.stem

            except (json.JSONDecodeError, OSError):
                # Skip files that can't be parsed
                continue

    def _get_prefix(self, room_id: str) -> str | None:
        """
        Extract the prefix from a room GUID.

        Args:
            room_id: Room GUID (e.g., "crypt.entrance")

        Returns:
            The prefix (e.g., "crypt") or None if no prefix
        """
        if "." in room_id:
            return room_id.split(".")[0]
        return None

    def get_dungeon_for_room(self, room_id: str) -> str | None:
        """
        Get the dungeon filename for a room GUID.

        Args:
            room_id: Room GUID (e.g., "crypt.entrance")

        Returns:
            Dungeon filename (without .json) or None if not found
        """
        prefix = self._get_prefix(room_id)
        if prefix:
            return self._prefix_to_dungeon.get(prefix)
        return None

    def load_dungeon(self, dungeon_name: str) -> dict[str, Any] | None:
        """
        Load a dungeon by name (with caching).

        Args:
            dungeon_name: Dungeon filename without .json

        Returns:
            Dungeon data dict or None if not found
        """
        if dungeon_name in self._loaded_dungeons:
            return self._loaded_dungeons[dungeon_name]

        dungeon_file = self.dungeons_path / f"{dungeon_name}.json"
        if not dungeon_file.exists():
            return None

        try:
            with open(dungeon_file) as f:
                dungeon_data = json.load(f)
            self._loaded_dungeons[dungeon_name] = dungeon_data
            return dungeon_data
        except (json.JSONDecodeError, OSError):
            return None

    def get_room(self, room_id: str) -> dict[str, Any] | None:
        """
        Get room data by GUID, loading the dungeon if needed.

        Args:
            room_id: Room GUID (e.g., "crypt.entrance")

        Returns:
            Room data dict or None if not found
        """
        dungeon_name = self.get_dungeon_for_room(room_id)
        if not dungeon_name:
            return None

        dungeon = self.load_dungeon(dungeon_name)
        if not dungeon:
            return None

        return dungeon.get("rooms", {}).get(room_id)

    def room_exists(self, room_id: str) -> bool:
        """
        Check if a room GUID exists in any registered dungeon.

        Args:
            room_id: Room GUID to check

        Returns:
            True if room exists, False otherwise
        """
        return self.get_room(room_id) is not None

    def get_all_prefixes(self) -> list[str]:
        """Get all registered room prefixes."""
        return list(self._prefix_to_dungeon.keys())

    def get_dungeon_data_for_room(self, room_id: str) -> dict[str, Any] | None:
        """
        Get the full dungeon data that contains a room.

        Args:
            room_id: Room GUID

        Returns:
            Full dungeon data dict or None if not found
        """
        dungeon_name = self.get_dungeon_for_room(room_id)
        if not dungeon_name:
            return None
        return self.load_dungeon(dungeon_name)
