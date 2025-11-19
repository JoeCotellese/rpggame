# ABOUTME: Campaign management system for creating, loading, and organizing campaigns
# ABOUTME: Handles campaign directories, save slots, and game state serialization

import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from dataclasses import asdict

from dnd_engine.core.campaign import Campaign, SaveSlotMetadata
from dnd_engine.core.game_state import GameState
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.party import Party
from dnd_engine.systems.inventory import Inventory, EquipmentSlot
from dnd_engine.systems.currency import Currency
from dnd_engine.systems.resources import ResourcePool
from dnd_engine.utils.events import EventBus
from dnd_engine.rules.loader import DataLoader
from dnd_engine.core.dice import DiceRoller


# Current save file version
SAVE_VERSION = "1.0.0"


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

        # Serialize game state
        auto_save = (save_type == "auto")
        save_data = self._serialize_game_state(game_state, auto_save)

        # Write to file
        saves_dir = campaign_dir / "saves"
        saves_dir.mkdir(exist_ok=True)
        save_path = saves_dir / f"{save_file_name}.json"
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)

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

        # Determine save file name based on slot
        if slot_name == "auto":
            save_file_name = "save_auto"
        elif slot_name == "quick":
            save_file_name = "save_quick"
        else:
            # For custom saves, we need to find the matching file
            # This is a simplified approach - in practice, you'd want a better lookup
            save_file_name = slot_name

        # Load save file
        saves_dir = campaign_dir / "saves"
        save_path = saves_dir / f"{save_file_name}.json"

        if not save_path.exists():
            raise FileNotFoundError(f"Save file not found: {save_file_name}")

        # Read and deserialize save file
        try:
            with open(save_path, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Corrupted save file: {e}")

        # Validate save file
        self._validate_save_data(save_data)

        # Check version compatibility
        save_version = save_data.get("version", "0.0.0")
        if not self._is_compatible_version(save_version):
            raise ValueError(
                f"Incompatible save version: {save_version} "
                f"(current version: {SAVE_VERSION})"
            )

        # Deserialize game state
        game_state = self._deserialize_game_state(
            save_data,
            event_bus,
            data_loader,
            dice_roller
        )

        # Update campaign last_played timestamp
        campaign = self.load_campaign(campaign_name)
        campaign.last_played = datetime.now()
        self._save_campaign_metadata(safe_name, campaign)

        # Update last_played in save file as well
        save_data["metadata"]["last_played"] = datetime.now().isoformat()
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)

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

    def _serialize_game_state(
        self,
        game_state: GameState,
        auto_save: bool
    ) -> Dict[str, Any]:
        """
        Serialize game state to a dictionary.

        Args:
            game_state: Game state to serialize
            auto_save: Whether this is an auto-save

        Returns:
            Dictionary representation of game state
        """
        now = datetime.now().isoformat()

        return {
            "version": SAVE_VERSION,
            "metadata": {
                "created": now,
                "last_played": now,
                "auto_save": auto_save
            },
            "party": [self._serialize_character(char) for char in game_state.party.characters],
            "game_state": {
                "dungeon_name": game_state.dungeon_name,
                "current_room_id": game_state.current_room_id,
                "dungeon_state": self._serialize_dungeon_state(game_state.dungeon),
                "in_combat": game_state.in_combat,
                "action_history": game_state.action_history,
                "last_entry_direction": game_state.last_entry_direction
            }
        }

    def _serialize_character(self, character: Character) -> Dict[str, Any]:
        """
        Serialize a character to a dictionary.

        Args:
            character: Character to serialize

        Returns:
            Dictionary representation of character
        """
        return {
            "name": character.name,
            "character_class": character.character_class.value,
            "level": character.level,
            "race": character.race,
            "subclass": character.subclass,
            "xp": character.xp,
            "max_hp": character.max_hp,
            "current_hp": character.current_hp,
            "ac": character.ac,
            "abilities": asdict(character.abilities),
            "inventory": self._serialize_inventory(character.inventory),
            "conditions": list(character.conditions),
            "resource_pools": self._serialize_resource_pools(character),
            "spellcasting_ability": character.spellcasting_ability,
            "known_spells": character.known_spells,
            "prepared_spells": character.prepared_spells
        }

    def _serialize_inventory(self, inventory: Inventory) -> Dict[str, Any]:
        """
        Serialize inventory to a dictionary.

        Args:
            inventory: Inventory to serialize

        Returns:
            Dictionary representation of inventory
        """
        return {
            "items": [
                {
                    "item_id": item.item_id,
                    "category": item.category,
                    "quantity": item.quantity
                }
                for item in inventory.items.values()
            ],
            "equipped": {
                "weapon": inventory.equipped[EquipmentSlot.WEAPON],
                "armor": inventory.equipped[EquipmentSlot.ARMOR]
            },
            "currency": asdict(inventory.currency)
        }

    def _serialize_resource_pools(self, character: Character) -> List[Dict[str, Any]]:
        """
        Serialize character resource pools to a list of dictionaries.

        Args:
            character: Character to serialize resource pools from

        Returns:
            List of dictionaries representing each resource pool
        """
        return [
            {
                "name": pool.name,
                "current": pool.current,
                "maximum": pool.maximum,
                "recovery_type": pool.recovery_type
            }
            for pool in character.resource_pools.values()
        ]

    def _serialize_dungeon_state(self, dungeon: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize dungeon state (room modifications).

        Args:
            dungeon: Dungeon data

        Returns:
            Dictionary with room states
        """
        room_states = {}

        for room_id, room_data in dungeon.get("rooms", {}).items():
            room_states[room_id] = {
                "searched": room_data.get("searched", False),
                "enemies": room_data.get("enemies", [])
            }

        return room_states

    def _deserialize_game_state(
        self,
        save_data: Dict[str, Any],
        event_bus: Optional[EventBus],
        data_loader: Optional[DataLoader],
        dice_roller: Optional[DiceRoller]
    ) -> GameState:
        """
        Deserialize game state from save data.

        Args:
            save_data: Save data dictionary
            event_bus: Event bus for the game
            data_loader: Data loader for content
            dice_roller: Dice roller

        Returns:
            Reconstructed GameState
        """
        # Create party from saved characters
        characters = [
            self._deserialize_character(char_data)
            for char_data in save_data["party"]
        ]
        party = Party(characters)

        # Get game state data
        gs_data = save_data["game_state"]

        # Create game state (this loads fresh dungeon)
        game_state = GameState(
            party=party,
            dungeon_name=gs_data["dungeon_name"],
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller
        )

        # Restore room-specific state
        room_states = gs_data.get("dungeon_state", {})
        for room_id, room_state in room_states.items():
            if room_id in game_state.dungeon["rooms"]:
                game_state.dungeon["rooms"][room_id]["searched"] = room_state.get("searched", False)
                game_state.dungeon["rooms"][room_id]["enemies"] = room_state.get("enemies", [])

        # Restore current position
        game_state.current_room_id = gs_data["current_room_id"]

        # Restore action history
        game_state.action_history = gs_data.get("action_history", [])

        # Restore navigation tracking
        game_state.last_entry_direction = gs_data.get("last_entry_direction")

        return game_state

    def _deserialize_character(self, char_data: Dict[str, Any]) -> Character:
        """
        Deserialize character from save data.

        Args:
            char_data: Character data dictionary

        Returns:
            Reconstructed Character
        """
        abilities = Abilities(**char_data["abilities"])
        inventory = self._deserialize_inventory(char_data["inventory"])

        character = Character(
            name=char_data["name"],
            character_class=CharacterClass(char_data["character_class"]),
            level=char_data["level"],
            abilities=abilities,
            max_hp=char_data["max_hp"],
            ac=char_data["ac"],
            current_hp=char_data["current_hp"],
            xp=char_data["xp"],
            inventory=inventory,
            race=char_data["race"],
            subclass=char_data.get("subclass"),
            spellcasting_ability=char_data.get("spellcasting_ability"),
            known_spells=char_data.get("known_spells"),
            prepared_spells=char_data.get("prepared_spells")
        )

        # Restore conditions
        for condition in char_data.get("conditions", []):
            character.add_condition(condition)

        # Restore resource pools
        for pool_data in char_data.get("resource_pools", []):
            pool = ResourcePool(**pool_data)
            character.add_resource_pool(pool)

        return character

    def _deserialize_inventory(self, inv_data: Dict[str, Any]) -> Inventory:
        """
        Deserialize inventory from save data.

        Args:
            inv_data: Inventory data dictionary

        Returns:
            Reconstructed Inventory
        """
        inventory = Inventory()

        # Restore items
        for item_data in inv_data.get("items", []):
            inventory.add_item(
                item_id=item_data["item_id"],
                category=item_data["category"],
                quantity=item_data["quantity"]
            )

        # Restore equipped items
        equipped_data = inv_data.get("equipped", {})
        if equipped_data.get("weapon"):
            inventory.equip_item(equipped_data["weapon"], EquipmentSlot.WEAPON)
        if equipped_data.get("armor"):
            inventory.equip_item(equipped_data["armor"], EquipmentSlot.ARMOR)

        # Restore currency
        currency_data = inv_data.get("currency", {})
        inventory.currency = Currency(**currency_data)

        return inventory

    def _validate_save_data(self, save_data: Dict[str, Any]) -> None:
        """
        Validate save file structure.

        Args:
            save_data: Save data to validate

        Raises:
            ValueError: If save data is invalid
        """
        required_keys = ["version", "metadata", "party", "game_state"]

        for key in required_keys:
            if key not in save_data:
                raise ValueError(f"Invalid save file: missing '{key}'")

        if not isinstance(save_data["party"], list):
            raise ValueError("Invalid save file: 'party' must be a list")

        if len(save_data["party"]) == 0:
            raise ValueError("Invalid save file: party cannot be empty")

    def _is_compatible_version(self, save_version: str) -> bool:
        """
        Check if save version is compatible with current version.

        Args:
            save_version: Version string from save file

        Returns:
            True if compatible
        """
        # For now, we only support exact version match
        # In the future, this could support migration between versions
        return save_version == SAVE_VERSION
