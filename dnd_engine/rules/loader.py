# ABOUTME: Data loader for reading JSON game content files
# ABOUTME: Loads monsters, items, dungeons, and character classes from JSON

import json
from pathlib import Path
from typing import Dict, Any
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.core.dice import DiceRoller


class DataLoader:
    """
    Loads game content from JSON files.

    Responsible for reading monster stats, items, dungeons, and character classes
    from the data directory and converting them into usable game objects.
    """

    def __init__(self, data_path: Path | None = None):
        """
        Initialize the data loader.

        Args:
            data_path: Path to the data directory (defaults to dnd_engine/data)
        """
        if data_path is None:
            # Default to the data directory in the package
            self.data_path = Path(__file__).parent.parent / "data"
        else:
            self.data_path = Path(data_path)

        self.dice_roller = DiceRoller()

    def load_monsters(self) -> Dict[str, Any]:
        """
        Load all monster definitions from JSON.

        Returns:
            Dictionary mapping monster IDs to monster data
        """
        monsters_file = self.data_path / "srd" / "monsters.json"
        with open(monsters_file, 'r') as f:
            return json.load(f)

    def create_monster(self, monster_id: str) -> Creature:
        """
        Create a Creature instance from a monster definition.

        Args:
            monster_id: ID of the monster to create (e.g., "goblin")

        Returns:
            Creature instance with stats from the monster definition

        Raises:
            KeyError: If monster_id doesn't exist
        """
        monsters = self.load_monsters()

        if monster_id not in monsters:
            raise KeyError(f"Monster '{monster_id}' not found in monster definitions")

        data = monsters[monster_id]

        # Create abilities
        abilities = Abilities(
            strength=data["abilities"]["str"],
            dexterity=data["abilities"]["dex"],
            constitution=data["abilities"]["con"],
            intelligence=data["abilities"]["int"],
            wisdom=data["abilities"]["wis"],
            charisma=data["abilities"]["cha"]
        )

        # Roll HP from dice notation
        hp_roll = self.dice_roller.roll(data["hp"])
        max_hp = max(1, hp_roll.total)  # Minimum 1 HP

        # Create the creature
        creature = Creature(
            name=data["name"],
            max_hp=max_hp,
            ac=data["ac"],
            abilities=abilities
        )

        return creature

    def load_items(self) -> Dict[str, Any]:
        """
        Load all item definitions from JSON.

        Returns:
            Dictionary containing weapons, armor, and consumables
        """
        items_file = self.data_path / "srd" / "items.json"
        with open(items_file, 'r') as f:
            return json.load(f)

    def load_dungeon(self, dungeon_name: str) -> Dict[str, Any]:
        """
        Load a dungeon definition from JSON.

        Args:
            dungeon_name: Name of the dungeon file (without .json extension)

        Returns:
            Dictionary containing dungeon data

        Raises:
            FileNotFoundError: If dungeon file doesn't exist
        """
        dungeon_file = self.data_path / "content" / "dungeons" / f"{dungeon_name}.json"

        if not dungeon_file.exists():
            raise FileNotFoundError(f"Dungeon file not found: {dungeon_file}")

        with open(dungeon_file, 'r') as f:
            return json.load(f)

    def load_classes(self) -> Dict[str, Any]:
        """
        Load all character class definitions from JSON.

        Returns:
            Dictionary mapping class names to class data
        """
        classes_file = self.data_path / "srd" / "classes.json"
        with open(classes_file, 'r') as f:
            return json.load(f)

    def load_races(self) -> Dict[str, Any]:
        """
        Load all race definitions from JSON.

        Returns:
            Dictionary mapping race IDs to race data
        """
        races_file = self.data_path / "srd" / "races.json"
        with open(races_file, 'r') as f:
            return json.load(f)
