# ABOUTME: Migration system for converting old campaign format to new save slot system
# ABOUTME: Handles detection, backup, conversion, and verification of legacy save data

import json
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from dnd_engine.core.save_slot import SaveSlot
from dnd_engine.core.save_slot_manager import SaveSlotManager
from dnd_engine.core.character_vault_v2 import CharacterVaultV2
from dnd_engine.core.campaign import Campaign


class MigrationManager:
    """
    Manages migration from old campaign system to new save slot system.

    Migrates from:
        ~/.dnd_terminal/campaigns/{campaign}/saves/
    To:
        ~/.dnd_game/saves/slot_XX.json
        ~/.dnd_game/character_vault.json
    """

    def __init__(
        self,
        old_campaigns_dir: Optional[Path] = None,
        new_save_dir: Optional[Path] = None,
        new_vault_path: Optional[Path] = None
    ):
        """
        Initialize migration manager.

        Args:
            old_campaigns_dir: Old campaigns directory (defaults to ~/.dnd_terminal/campaigns)
            new_save_dir: New saves directory (defaults to ~/.dnd_game/saves)
            new_vault_path: New vault file path (defaults to ~/.dnd_game/character_vault.json)
        """
        if old_campaigns_dir is None:
            old_campaigns_dir = Path.home() / ".dnd_terminal" / "campaigns"

        if new_save_dir is None:
            new_save_dir = Path.home() / ".dnd_game" / "saves"

        if new_vault_path is None:
            new_vault_path = Path.home() / ".dnd_game" / "character_vault.json"

        self.old_campaigns_dir = Path(old_campaigns_dir)
        self.new_save_dir = Path(new_save_dir)
        self.new_vault_path = Path(new_vault_path)

        self.backup_dir = Path.home() / ".dnd_terminal" / "backup_pre_migration"

    def should_migrate(self) -> bool:
        """
        Check if migration is needed.

        Returns:
            True if old campaigns exist and new system is not initialized
        """
        # Old system exists
        has_old_campaigns = self.old_campaigns_dir.exists() and any(self.old_campaigns_dir.iterdir())

        # New system not initialized (or has empty slots only)
        has_new_saves = False
        if self.new_save_dir.exists():
            slot_manager = SaveSlotManager(saves_dir=self.new_save_dir)
            slots = slot_manager.list_slots()
            has_new_saves = any(not slot.is_empty() for slot in slots)

        return has_old_campaigns and not has_new_saves

    def get_migration_info(self) -> Dict[str, Any]:
        """
        Get information about what will be migrated.

        Returns:
            Dictionary with migration statistics
        """
        if not self.old_campaigns_dir.exists():
            return {
                "total_campaigns": 0,
                "migratable_campaigns": 0,
                "total_characters": 0,
                "campaigns_to_migrate": []
            }

        campaigns_to_migrate = []
        all_characters = {}

        for campaign_dir in self.old_campaigns_dir.iterdir():
            if not campaign_dir.is_dir():
                continue

            # Load campaign metadata
            metadata_path = campaign_dir / "campaign.json"
            if not metadata_path.exists():
                continue

            try:
                with open(metadata_path, 'r') as f:
                    campaign_data = json.load(f)

                campaign = Campaign.from_dict(campaign_data)

                # Find save files
                saves_dir = campaign_dir / "saves"
                save_files = list(saves_dir.glob("*.json")) if saves_dir.exists() else []

                # Collect character info
                for save_file in save_files:
                    try:
                        with open(save_file, 'r') as f:
                            save_data = json.load(f)

                        for char_data in save_data.get("party", []):
                            char_name = char_data.get("name")
                            char_level = char_data.get("level", 1)

                            if char_name:
                                if char_name not in all_characters or char_level > all_characters[char_name]["level"]:
                                    all_characters[char_name] = {
                                        "name": char_name,
                                        "level": char_level,
                                        "class": char_data.get("character_class", "Unknown")
                                    }
                    except (json.JSONDecodeError, KeyError):
                        continue

                campaigns_to_migrate.append({
                    "name": campaign.name,
                    "last_played": campaign.last_played.isoformat(),
                    "playtime": campaign.get_playtime_display(),
                    "save_count": len(save_files)
                })

            except (json.JSONDecodeError, KeyError, ValueError):
                continue

        # Sort by last_played (most recent first)
        campaigns_to_migrate.sort(key=lambda c: c["last_played"], reverse=True)

        return {
            "total_campaigns": len(campaigns_to_migrate),
            "migratable_campaigns": min(len(campaigns_to_migrate), 10),
            "total_characters": len(all_characters),
            "campaigns_to_migrate": campaigns_to_migrate[:10],  # Only show first 10
            "unique_characters": list(all_characters.values())
        }

    def migrate(self, dry_run: bool = False) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Perform migration from old to new system.

        Args:
            dry_run: If True, validate but don't actually migrate

        Returns:
            Tuple of (success, message, stats_dict)
        """
        if not self.should_migrate():
            return (False, "No migration needed or new system already has data", {})

        stats = {
            "campaigns_migrated": 0,
            "characters_migrated": 0,
            "slots_used": 0,
            "errors": []
        }

        try:
            # Step 1: Create backup
            if not dry_run:
                self._create_backup()

            # Step 2: Collect campaigns (up to 10 most recent)
            campaigns = self._collect_campaigns()[:10]

            if not campaigns:
                return (False, "No valid campaigns found to migrate", stats)

            # Step 3: Collect all unique characters (highest level version)
            character_map = self._collect_unique_characters(campaigns)

            # Step 4: Migrate characters to vault
            if not dry_run:
                vault = CharacterVaultV2(vault_path=self.new_vault_path)
                char_id_map = {}  # Maps character name to new vault ID

                for char_name, char_data in character_map.items():
                    try:
                        character = self._deserialize_character(char_data)
                        char_id = vault.add_character(character)
                        char_id_map[char_name] = char_id
                        stats["characters_migrated"] += 1
                    except Exception as e:
                        stats["errors"].append(f"Failed to migrate character {char_name}: {e}")

            # Step 5: Migrate campaigns to save slots
            if not dry_run:
                slot_manager = SaveSlotManager(saves_dir=self.new_save_dir)

                for slot_num, (campaign, save_path) in enumerate(campaigns, start=1):
                    try:
                        self._migrate_campaign_to_slot(
                            slot_manager,
                            slot_num,
                            campaign,
                            save_path
                        )
                        stats["campaigns_migrated"] += 1
                        stats["slots_used"] += 1
                    except Exception as e:
                        stats["errors"].append(f"Failed to migrate campaign {campaign.name}: {e}")

            # Step 6: Verify migration
            if not dry_run:
                verify_success, verify_msg = self._verify_migration(stats)
                if not verify_success:
                    return (False, f"Migration verification failed: {verify_msg}", stats)

            success_msg = f"Migration completed successfully! Migrated {stats['campaigns_migrated']} campaigns and {stats['characters_migrated']} characters."
            if dry_run:
                success_msg = f"[DRY RUN] Would migrate {len(campaigns)} campaigns and {len(character_map)} characters."

            return (True, success_msg, stats)

        except Exception as e:
            return (False, f"Migration failed: {e}", stats)

    def _create_backup(self) -> None:
        """Create backup of old campaigns directory."""
        if self.old_campaigns_dir.exists():
            # Remove old backup if exists
            if self.backup_dir.exists():
                shutil.rmtree(self.backup_dir)

            # Create new backup
            shutil.copytree(self.old_campaigns_dir, self.backup_dir)

    def _collect_campaigns(self) -> List[Tuple[Campaign, Path]]:
        """
        Collect all campaigns with their most recent save file.

        Returns:
            List of tuples (Campaign, save_file_path) sorted by last_played
        """
        campaigns = []

        for campaign_dir in self.old_campaigns_dir.iterdir():
            if not campaign_dir.is_dir():
                continue

            metadata_path = campaign_dir / "campaign.json"
            if not metadata_path.exists():
                continue

            try:
                with open(metadata_path, 'r') as f:
                    campaign_data = json.load(f)

                campaign = Campaign.from_dict(campaign_data)

                # Find most recent save file
                saves_dir = campaign_dir / "saves"
                if not saves_dir.exists():
                    continue

                save_files = list(saves_dir.glob("*.json"))
                if not save_files:
                    continue

                # Prefer auto-save, then quick-save, then most recent manual save
                auto_save = saves_dir / "save_auto.json"
                if auto_save.exists():
                    most_recent_save = auto_save
                else:
                    # Get most recently modified save
                    save_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    most_recent_save = save_files[0]

                campaigns.append((campaign, most_recent_save))

            except (json.JSONDecodeError, KeyError, ValueError):
                continue

        # Sort by last_played (most recent first)
        campaigns.sort(key=lambda c: c[0].last_played, reverse=True)

        return campaigns

    def _collect_unique_characters(
        self,
        campaigns: List[Tuple[Campaign, Path]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Collect unique characters across all campaigns (highest level version).

        Args:
            campaigns: List of (Campaign, save_path) tuples

        Returns:
            Dictionary mapping character name to character data
        """
        character_map = {}

        for campaign, save_path in campaigns:
            try:
                with open(save_path, 'r') as f:
                    save_data = json.load(f)

                for char_data in save_data.get("party", []):
                    char_name = char_data.get("name")
                    char_level = char_data.get("level", 1)

                    if char_name:
                        # Keep highest level version
                        if char_name not in character_map or char_level > character_map[char_name].get("level", 0):
                            character_map[char_name] = char_data

            except (json.JSONDecodeError, KeyError):
                continue

        return character_map

    def _migrate_campaign_to_slot(
        self,
        slot_manager: SaveSlotManager,
        slot_number: int,
        campaign: Campaign,
        save_path: Path
    ) -> None:
        """
        Migrate a single campaign to a save slot.

        Args:
            slot_manager: SaveSlotManager instance
            slot_number: Slot number (1-10)
            campaign: Campaign metadata
            save_path: Path to the save file to migrate
        """
        # Load save file
        with open(save_path, 'r') as f:
            save_data = json.load(f)

        # Create new slot file with migrated data
        now = datetime.now()

        # Build slot metadata from campaign
        slot = SaveSlot(
            slot_number=slot_number,
            created_at=campaign.created_at,
            last_played=campaign.last_played,
            playtime_seconds=campaign.playtime_seconds,
            adventure_name=campaign.current_dungeon,
            adventure_progress=f"Room {campaign.current_room}" if campaign.current_room else "Unknown",
            party_composition=[c.get("name") for c in save_data.get("party", [])],
            party_levels=[c.get("level", 1) for c in save_data.get("party", [])],
            custom_name=None,  # No custom name on migration
            save_version="2.0.0"
        )

        # Write slot file
        slot_path = slot_manager._get_slot_path(slot_number)

        migrated_data = {
            "version": "2.0.0",
            "metadata": slot.to_dict(),
            "party": save_data.get("party", []),
            "game_state": save_data.get("game_state", {})
        }

        with open(slot_path, 'w', encoding='utf-8') as f:
            json.dump(migrated_data, f, indent=2, ensure_ascii=False)

    def _deserialize_character(self, char_data: Dict[str, Any]):
        """
        Deserialize character from old save format.

        Args:
            char_data: Character data from old save file

        Returns:
            Character instance
        """
        from dnd_engine.core.character import Character, CharacterClass
        from dnd_engine.core.creature import Abilities
        from dnd_engine.systems.inventory import Inventory, EquipmentSlot
        from dnd_engine.systems.currency import Currency
        from dnd_engine.systems.resources import ResourcePool

        abilities = Abilities(**char_data["abilities"])

        # Deserialize inventory
        inventory = Inventory()
        inv_data = char_data.get("inventory", {})

        for item_data in inv_data.get("items", []):
            inventory.add_item(
                item_id=item_data["item_id"],
                category=item_data["category"],
                quantity=item_data["quantity"]
            )

        equipped_data = inv_data.get("equipped", {})
        if equipped_data.get("weapon"):
            inventory.equip_item(equipped_data["weapon"], EquipmentSlot.WEAPON)
        if equipped_data.get("armor"):
            inventory.equip_item(equipped_data["armor"], EquipmentSlot.ARMOR)

        currency_data = inv_data.get("currency", {})
        inventory.currency = Currency(**currency_data)

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

    def _verify_migration(self, stats: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Verify migration completed successfully.

        Args:
            stats: Migration statistics

        Returns:
            Tuple of (success, message)
        """
        # Check that slots were created
        if stats["slots_used"] == 0:
            return (False, "No save slots were created")

        # Check that vault has characters
        if stats["characters_migrated"] == 0:
            return (False, "No characters were migrated to vault")

        # Check that files exist
        if not self.new_save_dir.exists():
            return (False, "New saves directory was not created")

        if not self.new_vault_path.exists():
            return (False, "New vault file was not created")

        # Check backup exists
        if not self.backup_dir.exists():
            return (False, "Backup was not created")

        return (True, "Verification passed")
