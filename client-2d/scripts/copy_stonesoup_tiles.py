#!/usr/bin/env python3
# ABOUTME: Copies Stone Soup tiles from extraction to organized asset directory.
# ABOUTME: Run after extracting the DCSS Full zip file.

"""Copy Stone Soup tiles from extraction to organized directory structure."""

import json
import shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CLIENT_2D_DIR = SCRIPT_DIR.parent
ASSETS_DIR = CLIENT_2D_DIR / "assets"
STONESOUP_DIR = ASSETS_DIR / "stonesoup"
MAPPINGS_FILE = ASSETS_DIR / "tile_mappings.json"

# Source directory from extraction
SOURCE_DIR = (
    CLIENT_2D_DIR
    / ".tmp_stonesoup"
    / "Dungeon_Crawl_Stone_Soup_Full"
    / "Dungeon Crawl Stone Soup Full"
)


def copy_tiles():
    """Copy tiles based on mappings."""
    if not SOURCE_DIR.exists():
        print(f"Source directory not found: {SOURCE_DIR}")
        print("Run setup_stonesoup.py first to download and extract tiles.")
        return

    with open(MAPPINGS_FILE) as f:
        mappings = json.load(f)

    copied = 0
    missing = []

    for category, items in mappings.items():
        if category.startswith("_"):
            continue

        for entity_id, rel_path in items.items():
            source_path = SOURCE_DIR / rel_path
            dest_path = STONESOUP_DIR / rel_path

            # Try alternate paths for some files
            alt_paths = [
                source_path,
                SOURCE_DIR / rel_path.replace("skeleton_small", "skeletons/skeleton_small"),
                SOURCE_DIR / rel_path.replace("wight", "wight_new"),
            ]

            found = False
            for try_path in alt_paths:
                if try_path.exists():
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(try_path, dest_path)
                    copied += 1
                    found = True
                    print(f"  Copied: {rel_path}")
                    break

            if not found:
                missing.append(f"{category}/{entity_id}: {rel_path}")

    print(f"\nCopied {copied} tiles")
    if missing:
        print(f"\nMissing {len(missing)} tiles:")
        for m in missing:
            print(f"  - {m}")


def find_and_copy_extras():
    """Copy some extra commonly needed tiles."""
    extras = {
        # Skeletons are in a subdirectory
        "monster/undead/skeleton_small.png": "monster/undead/skeletons/skeleton_small.png",
        # Additional undead
        "monster/undead/wight.png": "monster/undead/wight_new.png",
        "monster/undead/zombie.png": "monster/undead/zombies/zombie_small.png",
        # Doors
        "dungeon/doors/open_door.png": "dungeon/doors/open_door.png",
        # Effects
        "effect/slash.png": "effect/slash_new.png",
    }

    for dest_rel, source_rel in extras.items():
        source = SOURCE_DIR / source_rel
        dest = STONESOUP_DIR / dest_rel

        if source.exists() and not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            print(f"  Extra: {dest_rel}")


def main():
    """Main entry point."""
    print("Copying Stone Soup tiles...")
    print(f"Source: {SOURCE_DIR}")
    print(f"Destination: {STONESOUP_DIR}")
    print()

    copy_tiles()
    print("\nCopying extra tiles...")
    find_and_copy_extras()

    print("\nDone!")


if __name__ == "__main__":
    main()
