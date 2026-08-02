# ABOUTME: Seeds the V2 character vault with a deterministic four-person party.
# ABOUTME: Required to make the headless client and playtest harness runnable in a fresh environment.

"""Seed a deterministic party into the V2 character vault.

The headless 2D client refuses to start when the vault is empty, which makes
automated playtesting impossible in a fresh checkout or container. This script
creates a fixed party so playtest runs are reproducible.

The party deliberately uses only classes and races present in
``dnd_engine/data/srd/`` (classes: fighter, rogue, wizard; races: human,
mountain_dwarf, high_elf, halfling).

Usage:
    uv run python scripts/seed_test_vault.py
    uv run python scripts/seed_test_vault.py --force
"""

import argparse
import sys

from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.character_vault_v2 import CharacterVaultV2
from dnd_engine.rules.loader import DataLoader

# Fixed roster so playtest scenarios reference stable names.
PARTY: list[tuple[str, str, str]] = [
    ("Thorin", "fighter", "mountain_dwarf"),
    ("Elara", "wizard", "high_elf"),
    ("Nyx", "rogue", "halfling"),
    ("Garrick", "fighter", "human"),
]


def seed(force: bool = False) -> int:
    """Create the standard playtest party in the V2 vault.

    Args:
        force: Add the party even when the vault already holds characters.

    Returns:
        Process exit code (0 on success).
    """
    vault = CharacterVaultV2()
    existing = vault.list_characters()

    if existing and not force:
        print(f"Vault already holds {len(existing)} character(s) at {vault.vault_path}.")
        print("Nothing to do. Re-run with --force to add the standard party anyway.")
        return 0

    loader = DataLoader()
    factory = CharacterFactory()

    for name, class_name, race_name in PARTY:
        character = factory.create_character(
            class_name=class_name,
            race_name=race_name,
            data_loader=loader,
            name=name,
        )
        character_id = vault.add_character(character)
        print(f"  created {name:10s} {class_name:8s} {race_name:15s} {character_id}")

    print(f"Vault now holds {len(vault.list_characters())} character(s) at {vault.vault_path}.")
    return 0


def main() -> int:
    """Parse arguments and seed the vault."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Seed even when the vault already contains characters.",
    )
    args = parser.parse_args()
    return seed(force=args.force)


if __name__ == "__main__":
    sys.exit(main())
