# ABOUTME: Data loader for reading JSON game content files
# ABOUTME: Loads monsters, items, dungeons, and character classes from JSON

import json
from pathlib import Path
from typing import Any

from dnd_engine.core.creature import Abilities, Creature
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

    def load_monsters(self) -> dict[str, Any]:
        """
        Load all monster definitions from JSON.

        Returns:
            Dictionary mapping monster IDs to monster data
        """
        monsters_file = self.data_path / "srd" / "monsters.json"
        with open(monsters_file) as f:
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

    def load_items(self, campaign_id: str | None = None) -> dict[str, Any]:
        """
        Load all item definitions from JSON.

        Loads base SRD items and optionally merges in campaign-specific items
        from the quest file's "items" section.

        Args:
            campaign_id: Optional campaign ID to load campaign-specific items

        Returns:
            Dictionary containing weapons, armor, consumables, and campaign items
        """
        items_file = self.data_path / "srd" / "items.json"
        with open(items_file) as f:
            items = json.load(f)

        # Load campaign-specific items if campaign_id provided
        if campaign_id:
            # Try new path structure first: campaigns/{campaign_id}/quests.json
            quest_file = (
                self.data_path / "content" / "campaigns" / campaign_id / "quests.json"
            )
            # Fall back to legacy path: quests/{campaign_id}.json
            if not quest_file.exists():
                quest_file = (
                    self.data_path / "content" / "quests" / f"{campaign_id}.json"
                )
            if quest_file.exists():
                with open(quest_file, encoding="utf-8") as f:
                    quest_data = json.load(f)
                    campaign_items = quest_data.get("items", {})
                    if campaign_items:
                        # Add campaign items to consumables category
                        if "consumables" not in items:
                            items["consumables"] = {}
                        items["consumables"].update(campaign_items)

        return items

    def load_dungeon(
        self, dungeon_name: str, campaign_id: str | None = None
    ) -> dict[str, Any]:
        """
        Load a dungeon definition from JSON.

        Args:
            dungeon_name: Name of the dungeon file (without .json extension)
            campaign_id: Campaign containing the dungeon. If provided, looks in
                        campaigns/{campaign_id}/dungeons/. If None, looks in
                        content/dungeons/ for standalone test dungeons.

        Returns:
            Dictionary containing dungeon data

        Raises:
            FileNotFoundError: If dungeon file doesn't exist
        """
        if campaign_id:
            dungeon_file = (
                self.data_path
                / "content"
                / "campaigns"
                / campaign_id
                / "dungeons"
                / f"{dungeon_name}.json"
            )
        else:
            # Fallback for standalone/test dungeons
            dungeon_file = (
                self.data_path / "content" / "dungeons" / f"{dungeon_name}.json"
            )

        if not dungeon_file.exists():
            raise FileNotFoundError(f"Dungeon file not found: {dungeon_file}")

        with open(dungeon_file) as f:
            return json.load(f)

    def load_classes(self) -> dict[str, Any]:
        """
        Load all character class definitions from JSON.

        Returns:
            Dictionary mapping class names to class data
        """
        classes_file = self.data_path / "srd" / "classes.json"
        with open(classes_file) as f:
            return json.load(f)

    def load_races(self) -> dict[str, Any]:
        """
        Load all race definitions from JSON.

        Returns:
            Dictionary mapping race IDs to race data
        """
        races_file = self.data_path / "srd" / "races.json"
        with open(races_file) as f:
            return json.load(f)

    def load_skills(self) -> dict[str, Any]:
        """
        Load all skill definitions from JSON.

        Returns:
            Dictionary mapping skill IDs to skill data (name and ability)
        """
        skills_file = self.data_path / "srd" / "skills.json"
        with open(skills_file) as f:
            return json.load(f)

    def load_progression(self) -> dict[str, Any]:
        """
        Load character progression data (XP thresholds and proficiency bonuses).

        Returns:
            Dictionary containing xp_by_level and proficiency_by_level
        """
        progression_file = self.data_path / "srd" / "progression.json"
        with open(progression_file) as f:
            return json.load(f)

    def load_spells(self) -> dict[str, Any]:
        """
        Load all spell definitions from JSON.

        Validates that all spells have a valid target_type field.

        Returns:
            Dictionary mapping spell IDs to spell data

        Raises:
            ValueError: If any spell is missing target_type or has invalid target_type
        """
        spells_file = self.data_path / "srd" / "spells.json"
        with open(spells_file) as f:
            spells = json.load(f)

        # Validate target_type for all spells
        valid_target_types = {"self", "ally", "enemy", "area", "any"}
        errors = []

        for spell_id, spell_data in spells.items():
            target_type = spell_data.get("target_type")
            if not target_type:
                errors.append(f"Spell '{spell_id}' missing required 'target_type' field")
            elif target_type not in valid_target_types:
                errors.append(
                    f"Spell '{spell_id}' has invalid target_type '{target_type}'. "
                    f"Must be one of: {', '.join(sorted(valid_target_types))}"
                )

        if errors:
            error_msg = "Spell validation errors:\n" + "\n".join(errors)
            raise ValueError(error_msg)

        return spells

    def get_spell(self, spell_id: str) -> dict[str, Any]:
        """
        Get a specific spell by its ID.

        Args:
            spell_id: ID of the spell to retrieve (e.g., "fireball")

        Returns:
            Dictionary containing spell data

        Raises:
            KeyError: If spell_id doesn't exist
        """
        spells = self.load_spells()

        if spell_id not in spells:
            raise KeyError(f"Spell '{spell_id}' not found in spell definitions")

        return spells[spell_id]

    def load_quests(self, campaign_id: str) -> dict[str, Any]:
        """
        Load quest definitions for a campaign from JSON.

        Args:
            campaign_id: ID of the campaign (e.g., "the_unquiet_dead")

        Returns:
            Dictionary containing quest data with 'quests' list

        Raises:
            FileNotFoundError: If quest file doesn't exist
        """
        quest_file = (
            self.data_path
            / "content"
            / "campaigns"
            / campaign_id
            / "quests.json"
        )

        if not quest_file.exists():
            raise FileNotFoundError(f"Quest file not found: {quest_file}")

        with open(quest_file, encoding="utf-8") as f:
            return json.load(f)

    def load_npcs(self, campaign_id: str) -> dict[str, Any]:
        """
        Load NPC definitions for a campaign from JSON.

        Args:
            campaign_id: ID of the campaign (e.g., "the_unquiet_dead")

        Returns:
            Dictionary containing NPC data with 'npcs' dict

        Raises:
            FileNotFoundError: If NPC file doesn't exist
        """
        npc_file = (
            self.data_path
            / "content"
            / "campaigns"
            / campaign_id
            / "npcs.json"
        )

        if not npc_file.exists():
            raise FileNotFoundError(f"NPC file not found: {npc_file}")

        with open(npc_file, encoding="utf-8") as f:
            return json.load(f)
