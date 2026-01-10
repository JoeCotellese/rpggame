# ABOUTME: Downloads and organizes Dungeon Crawl Stone Soup tiles for the 2D client.
# ABOUTME: Handles download, extraction, reorganization, and mapping validation.

"""Setup script for Stone Soup tileset integration.

Downloads the Dungeon Crawl Stone Soup 32x32 tiles from OpenGameArt,
extracts them, and organizes them into our asset directory structure.
Also validates that all tile mappings resolve to existing files.
"""

import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

# URLs for Stone Soup tilesets on OpenGameArt
STONESOUP_URLS = {
    "full": "https://opengameart.org/sites/default/files/Dungeon%20Crawl%20Stone%20Soup%20Full.zip",
    "tiles": "https://opengameart.org/sites/default/files/crawl-tiles%20Oct-5-2010.zip",
}

# Base paths
SCRIPT_DIR = Path(__file__).parent
CLIENT_2D_DIR = SCRIPT_DIR.parent
ASSETS_DIR = CLIENT_2D_DIR / "assets"
STONESOUP_DIR = ASSETS_DIR / "stonesoup"
MAPPINGS_FILE = ASSETS_DIR / "tile_mappings.json"
TEMP_DIR = CLIENT_2D_DIR / ".tmp_stonesoup"


def download_tileset(url: str, dest: Path) -> Path:
    """Download a tileset ZIP file.

    Args:
        url: URL to download from
        dest: Directory to save the ZIP file

    Returns:
        Path to the downloaded ZIP file
    """
    dest.mkdir(parents=True, exist_ok=True)
    filename = url.split("/")[-1].replace("%20", "_")
    zip_path = dest / filename

    if zip_path.exists():
        print(f"  Already downloaded: {zip_path.name}")
        return zip_path

    print(f"  Downloading: {url}")
    urllib.request.urlretrieve(url, zip_path)
    print(f"  Saved to: {zip_path}")
    return zip_path


def extract_tileset(zip_path: Path, dest: Path) -> Path:
    """Extract a tileset ZIP file.

    Args:
        zip_path: Path to the ZIP file
        dest: Directory to extract to

    Returns:
        Path to the extracted directory
    """
    extract_dir = dest / zip_path.stem
    if extract_dir.exists():
        print(f"  Already extracted: {extract_dir.name}")
        return extract_dir

    print(f"  Extracting: {zip_path.name}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)
    print(f"  Extracted to: {extract_dir}")
    return extract_dir


def find_tile_in_extraction(
    extract_dir: Path, tile_name: str, search_dirs: list[str]
) -> Path | None:
    """Find a tile file in the extracted directory.

    Searches through common Stone Soup directory structures.

    Args:
        extract_dir: Root of extracted files
        tile_name: Name of the tile file to find
        search_dirs: List of subdirectories to search

    Returns:
        Path to the tile file, or None if not found
    """
    # Try direct match first
    for search_dir in search_dirs:
        candidate = extract_dir / search_dir / tile_name
        if candidate.exists():
            return candidate

    # Try recursive search
    for found in extract_dir.rglob(tile_name):
        return found

    # Try without extension
    base_name = Path(tile_name).stem
    for found in extract_dir.rglob(f"{base_name}.*"):
        if found.suffix.lower() in (".png", ".gif", ".bmp"):
            return found

    return None


def organize_tiles(extract_dir: Path, mappings: dict) -> dict[str, list[str]]:
    """Organize tiles from extraction into our directory structure.

    Args:
        extract_dir: Root of extracted files
        mappings: Tile mappings from tile_mappings.json

    Returns:
        Dict with 'found' and 'missing' lists
    """
    results = {"found": [], "missing": []}

    # Common search directories in Stone Soup extraction
    search_dirs = [
        "",
        "dc-mon",
        "dc-player",
        "dc-item",
        "dc-dngn",
        "player",
        "mon",
        "item",
        "dungeon",
        "gui",
        "effect",
    ]

    for category, items in mappings.items():
        # Skip metadata section
        if category == "_meta":
            continue
        for entity_id, tile_path in items.items():
            # The tile_path is our target structure (e.g., "monster/undead/skeleton_small.png")
            dest_path = STONESOUP_DIR / tile_path

            if dest_path.exists():
                results["found"].append(f"{category}/{entity_id}")
                continue

            # Extract just the filename to search for
            tile_name = Path(tile_path).name

            # Try to find the tile in the extraction
            source = find_tile_in_extraction(extract_dir, tile_name, search_dirs)

            if source:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest_path)
                results["found"].append(f"{category}/{entity_id}")
                print(f"  Copied: {tile_name} -> {tile_path}")
            else:
                results["missing"].append(f"{category}/{entity_id}: {tile_name}")

    return results


def create_directory_structure() -> None:
    """Create the stonesoup directory structure."""
    directories = [
        "monster/undead",
        "monster/beast",
        "monster/goblin",
        "monster/demon",
        "monster/nonliving",
        "player/base",
        "item/weapon",
        "item/armour",
        "item/potion",
        "item/scroll",
        "item/misc",
        "dungeon/floor",
        "dungeon/wall",
        "dungeon/door",
        "dungeon/stair",
        "dungeon/chest",
        "dungeon/altar",
        "effect",
    ]

    for dir_path in directories:
        (STONESOUP_DIR / dir_path).mkdir(parents=True, exist_ok=True)

    print(f"Created directory structure in {STONESOUP_DIR}")


def create_credits_file() -> None:
    """Create the CREDITS.txt attribution file."""
    credits_content = """\
Dungeon Crawl Stone Soup Tiles
==============================

License: CC0 (Public Domain)
Source: https://opengameart.org/content/dungeon-crawl-32x32-tiles

Original artists: Chris Hamons and the DCSS development team

This tileset is released under CC0, meaning it can be used for any purpose
without attribution required. However, we include this credit file as a
courtesy to the original creators.

The tileset includes over 3000 32x32 pixel tiles covering:
- Monsters and creatures
- Player characters and equipment overlays
- Dungeon terrain (floors, walls, doors, stairs)
- Items (weapons, armor, potions, scrolls)
- Visual effects and UI elements
"""
    credits_path = STONESOUP_DIR / "CREDITS.txt"
    credits_path.write_text(credits_content)
    print(f"Created: {credits_path}")


def validate_mappings() -> dict[str, list[str]]:
    """Validate that all mappings resolve to existing files.

    Returns:
        Dict with 'valid' and 'invalid' lists
    """
    if not MAPPINGS_FILE.exists():
        print(f"Warning: Mappings file not found: {MAPPINGS_FILE}")
        return {"valid": [], "invalid": ["No mappings file"]}

    with open(MAPPINGS_FILE) as f:
        mappings = json.load(f)

    results = {"valid": [], "invalid": []}

    for category, items in mappings.items():
        # Skip metadata section
        if category == "_meta":
            continue
        for entity_id, tile_path in items.items():
            full_path = STONESOUP_DIR / tile_path
            key = f"{category}/{entity_id}"
            if full_path.exists():
                results["valid"].append(key)
            else:
                results["invalid"].append(f"{key}: {tile_path}")

    return results


def print_report(results: dict[str, list[str]], title: str) -> None:
    """Print a validation report."""
    print(f"\n{title}")
    print("=" * len(title))

    if results.get("found"):
        print(f"\nFound: {len(results['found'])} tiles")

    if results.get("valid"):
        print(f"\nValid mappings: {len(results['valid'])}")

    if results.get("missing"):
        print(f"\nMissing tiles ({len(results['missing'])}):")
        for item in results["missing"]:
            print(f"  - {item}")

    if results.get("invalid"):
        print(f"\nInvalid mappings ({len(results['invalid'])}):")
        for item in results["invalid"]:
            print(f"  - {item}")


def main() -> None:
    """Main setup routine."""
    print("Stone Soup Tileset Setup")
    print("========================\n")

    # Step 1: Create directory structure
    print("Step 1: Creating directory structure...")
    create_directory_structure()

    # Step 2: Create credits file
    print("\nStep 2: Creating credits file...")
    create_credits_file()

    # Step 3: Download tileset
    print("\nStep 3: Downloading tileset...")
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    try:
        zip_path = download_tileset(STONESOUP_URLS["full"], TEMP_DIR)
    except Exception as e:
        print(f"  Download failed: {e}")
        print("  You may need to download manually from:")
        print(f"  {STONESOUP_URLS['full']}")
        print(f"  And extract to: {TEMP_DIR}")
        return

    # Step 4: Extract tileset
    print("\nStep 4: Extracting tileset...")
    extract_dir = extract_tileset(zip_path, TEMP_DIR)

    # Step 5: Organize tiles based on mappings
    print("\nStep 5: Organizing tiles...")
    if MAPPINGS_FILE.exists():
        with open(MAPPINGS_FILE) as f:
            mappings = json.load(f)
        results = organize_tiles(extract_dir, mappings)
        print_report(results, "Tile Organization Report")
    else:
        print(f"  Skipping - no mappings file at {MAPPINGS_FILE}")
        print("  Run this script again after creating tile_mappings.json")

    # Step 6: Validate mappings
    print("\nStep 6: Validating mappings...")
    validation = validate_mappings()
    print_report(validation, "Mapping Validation Report")

    # Summary
    print("\n" + "=" * 40)
    print("Setup complete!")
    print(f"Stone Soup tiles directory: {STONESOUP_DIR}")
    if validation.get("invalid"):
        print(f"\nWarning: {len(validation['invalid'])} mappings need attention")
        print("You may need to manually find and copy these tiles.")


if __name__ == "__main__":
    main()
