# ABOUTME: Registry mapping dungeon IDs to their 2D grid map files
# ABOUTME: Used by CLI to load appropriate grid when entering a dungeon

from pathlib import Path


# Map dungeon IDs to their grid JSON files
DUNGEON_GRID_MAPS: dict[str, str] = {
    "poisoned_laboratory": "laboratory_grid.json",
}


def get_grid_map_path(dungeon_id: str) -> Path | None:
    """
    Get the path to a dungeon's grid map file, if one exists.

    Args:
        dungeon_id: The dungeon identifier (e.g., "poisoned_laboratory")

    Returns:
        Path to the grid map JSON file, or None if no grid map exists
    """
    filename = DUNGEON_GRID_MAPS.get(dungeon_id)
    if filename:
        return Path(__file__).parent.parent / "data" / "content" / "maps" / filename
    return None


def has_grid_map(dungeon_id: str) -> bool:
    """Check if a dungeon has an associated grid map."""
    return dungeon_id in DUNGEON_GRID_MAPS
