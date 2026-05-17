# ABOUTME: Adapter wrapping dnd-engine for the 2D graphical client.
# ABOUTME: Loads characters from vault, creates GameState, provides UI-friendly data access.

"""Engine adapter for connecting client-2d to dnd-engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dnd_engine.core.character import Character

# Default party size cap. When no explicit character_ids are passed to
# load_party_from_vault(), the first MAX_PARTY_SIZE characters from the vault
# are loaded in insertion order.
MAX_PARTY_SIZE = 4


@dataclass
class PartyLoadError(Exception):
    """Raised when load_party_from_vault cannot find one or more characters.

    Carries enough context for the CLI (or any caller) to print an actionable
    message: which vault was inspected, which IDs were missing, and which
    characters are actually available so the user can pick alternatives.
    """

    vault_path: Path
    missing_ids: list[str]
    vault_character_count: int
    available_characters: list[tuple[str, str]] = field(default_factory=list)

    def __str__(self) -> str:
        lines = [f"Could not load party from vault at {self.vault_path}."]
        if self.missing_ids:
            lines.append(
                f"Vault contains {self.vault_character_count} character(s); "
                f"{len(self.missing_ids)} requested character(s) missing:"
            )
            lines.extend(f"  - {char_id}" for char_id in self.missing_ids)
        else:
            lines.append(
                f"Vault contains {self.vault_character_count} character(s); "
                "none available to load."
            )
        if self.available_characters:
            lines.append("Available in vault:")
            lines.extend(
                f"  - {name} ({char_id})" for char_id, name in self.available_characters
            )
        else:
            lines.append("Vault has no characters yet.")
        return "\n".join(lines)


@dataclass
class CombatantInfo:
    """Information about a combatant for UI display."""

    name: str
    initiative: int
    is_player: bool
    hp: int
    max_hp: int
    is_current_turn: bool = False


class EngineAdapter:
    """Adapter wrapping dnd-engine GameState for the 2D client.

    Provides a clean interface for:
    - Loading characters from the vault
    - Initializing game state with a dungeon
    - Querying game state in UI-friendly formats
    - Executing player actions (move, attack, etc.)

    Usage:
        adapter = EngineAdapter()
        adapter.load_party_from_vault()
        adapter.initialize_game("cellar", "poisoned_laboratory")

        # Get UI data
        party_data = adapter.get_party_data()
        combat_data = adapter.get_combat_data()

        # Execute actions
        result = adapter.execute_attack(target_index=0)
    """

    def __init__(self) -> None:
        """Initialize the engine adapter."""
        self._game_state = None
        self._party = None
        self._event_bus = None
        self._vault = None
        self._initialized = False

    def load_party_from_vault(
        self, character_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Load characters from the vault into a party.

        Args:
            character_ids: List of character UUIDs to load. If not provided,
                          loads the first MAX_PARTY_SIZE characters present in
                          the vault, in insertion order.

        Returns:
            List of character info dicts for UI display.

        Raises:
            PartyLoadError: If the vault is empty (when relying on the default),
                            or one or more requested IDs are missing.
        """
        from dnd_engine.core.character_vault_v2 import CharacterVaultV2
        from dnd_engine.core.party import Party

        self._vault = CharacterVaultV2()
        vault_data = self._vault._load_vault()
        present = vault_data.get("characters", {})
        available = [
            (cid, entry.get("character", {}).get("name", "?"))
            for cid, entry in present.items()
        ]

        if character_ids is None:
            character_ids = list(present.keys())[:MAX_PARTY_SIZE]

        if not character_ids:
            raise PartyLoadError(
                vault_path=self._vault.vault_path,
                missing_ids=[],
                vault_character_count=0,
                available_characters=[],
            )

        characters: list[Character] = []
        missing_ids: list[str] = []

        for char_id in character_ids:
            try:
                character = self._vault.get_character(char_id)
            except FileNotFoundError:
                missing_ids.append(char_id)
                continue
            characters.append(character)

        if missing_ids:
            raise PartyLoadError(
                vault_path=self._vault.vault_path,
                missing_ids=missing_ids,
                vault_character_count=len(present),
                available_characters=available,
            )

        self._party = Party(characters)

        # Return summary for UI
        return [
            {
                "id": char_id,
                "name": char.name,
                "class": char.character_class.value.title(),
                "level": char.level,
                "hp": char.current_hp,
                "max_hp": char.max_hp,
            }
            for char_id, char in zip(character_ids, characters, strict=True)
        ]

    def initialize_game(
        self,
        dungeon_name: str = "cellar",
        campaign_id: str = "poisoned_laboratory",
        start_room: str | None = None,
    ) -> dict[str, Any]:
        """Initialize game state with a dungeon.

        Args:
            dungeon_name: Name of the dungeon file (without .json).
            campaign_id: Campaign containing the dungeon.
            start_room: Optional room ID to start in (uses dungeon default if not provided).

        Returns:
            Dict with initial game info (room_id, room_name, etc.)

        Raises:
            ValueError: If party not loaded yet.
        """
        if self._party is None:
            raise ValueError("Must call load_party_from_vault() first")

        from dnd_engine.core.game_state import GameState
        from dnd_engine.rules.loader import DataLoader
        from dnd_engine.utils.events import EventBus

        self._event_bus = EventBus()
        data_loader = DataLoader()

        self._game_state = GameState(
            party=self._party,
            dungeon_name=dungeon_name,
            event_bus=self._event_bus,
            data_loader=data_loader,
            campaign_id=campaign_id,
        )

        # Override start room if specified
        if start_room:
            self._game_state.current_room_id = start_room

        self._initialized = True

        return {
            "room_id": self._game_state.current_room_id,
            "room_name": self._game_state.get_current_room().get("name", "Unknown"),
            "dungeon": dungeon_name,
            "campaign": campaign_id,
        }

    def start_game(self) -> dict[str, Any]:
        """Start the game (triggers enemy check in starting room).

        Returns:
            Dict with combat status and any enemies found.
        """
        if not self._initialized:
            raise ValueError("Must call initialize_game() first")

        # This triggers _check_for_enemies() in the starting room
        self._game_state.start()

        return {
            "in_combat": self._game_state.in_combat,
            "enemies": [e.name for e in self._game_state.active_enemies],
        }

    @property
    def game_state(self):
        """Access the underlying GameState (for advanced use)."""
        return self._game_state

    @property
    def party(self):
        """Access the Party object."""
        return self._party

    @property
    def event_bus(self):
        """Access the EventBus for subscribing to events."""
        return self._event_bus

    @property
    def in_combat(self) -> bool:
        """Check if currently in combat."""
        if self._game_state is None:
            return False
        return self._game_state.in_combat

    # ========== UI Data Methods ==========

    def get_party_data(self) -> list[dict[str, Any]]:
        """Get party data in MOCK_PARTY format for UI.

        Returns:
            List of dicts with: name, class, hp, max_hp, conditions
        """
        if self._party is None:
            return []

        result = []
        for char in self._party.characters:
            conditions = []
            # Get active conditions from character
            if hasattr(char, "active_conditions"):
                conditions = list(char.active_conditions.keys())

            result.append({
                "name": char.name,
                "class": char.character_class.value.title(),
                "hp": char.current_hp,
                "max_hp": char.max_hp,
                "conditions": conditions,
            })

        return result

    def get_party_for_rendering(self) -> list[dict[str, Any]]:
        """Get party data ordered for combat formation rendering.

        Returns party members in formation order:
        - Index 0: Front-left (typically first fighter)
        - Index 1: Front-right (typically second fighter)
        - Index 2: Back-left (typically wizard/caster)
        - Index 3: Back-right (typically rogue/ranged)

        Returns:
            List of dicts with: name, class, hp, max_hp, is_current_turn
        """
        if self._party is None:
            return []

        # Separate by role (fighters front, others back)
        front_row = []
        back_row = []

        for char in self._party.characters:
            char_class = char.character_class.value.lower()
            if char_class in ("fighter", "paladin", "barbarian"):
                front_row.append(char)
            else:
                back_row.append(char)

        # Build formation order: front row first, then back row
        formation = front_row[:2] + back_row[:2]

        # Pad with remaining characters if needed
        remaining = [c for c in self._party.characters if c not in formation]
        formation.extend(remaining)
        formation = formation[:4]  # Max 4 characters displayed

        # Determine current turn character
        current_creature = None
        if self._game_state and self._game_state.in_combat:
            tracker = self._game_state.initiative_tracker
            if tracker:
                current_entry = tracker.get_current_combatant()
                if current_entry:
                    current_creature = current_entry.creature

        result = []
        for char in formation:
            result.append({
                "name": char.name,
                "class": char.character_class.value.title(),
                "hp": char.current_hp,
                "max_hp": char.max_hp,
                "is_current_turn": char is current_creature,
            })

        return result

    def get_combat_data(self) -> dict[str, Any] | None:
        """Get combat data in MOCK_COMBAT format for UI.

        Returns:
            Dict with round, current_turn, initiative list, or None if not in combat.
        """
        if self._game_state is None or not self._game_state.in_combat:
            return None

        tracker = self._game_state.initiative_tracker
        if tracker is None:
            return None

        current_index = tracker.current_turn_index

        initiative = []
        for entry in tracker.get_all_combatants():
            creature = entry.creature
            is_player = creature in self._party.characters

            initiative.append({
                "name": entry.display_name or creature.name,
                "init": entry.initiative_total,
                "is_player": is_player,
                "hp": creature.current_hp,
                "max_hp": creature.max_hp,
            })

        return {
            "round": tracker.round_number,
            "current_turn": current_index,
            "initiative": initiative,
        }

    def get_character_data(self, name: str | None = None) -> dict[str, Any] | None:
        """Get detailed character data in MOCK_CHARACTER format.

        Args:
            name: Character name. Uses first living character if not provided.

        Returns:
            Dict with full character details, or None if not found.
        """
        if self._party is None:
            return None

        # Find character
        char = None
        if name:
            for c in self._party.characters:
                if c.name == name:
                    char = c
                    break
        else:
            # Use first living character
            living = self._party.get_living_members()
            if living:
                char = living[0]

        if char is None:
            return None

        # Build stats dict
        stats = {}
        if hasattr(char, "abilities"):
            stats = {
                "STR": char.abilities.strength,
                "DEX": char.abilities.dexterity,
                "CON": char.abilities.constitution,
                "INT": char.abilities.intelligence,
                "WIS": char.abilities.wisdom,
                "CHA": char.abilities.charisma,
            }

        # Build equipment dict
        equipment = {}
        if hasattr(char, "inventory"):
            from dnd_engine.systems.inventory import EquipmentSlot

            weapon = char.inventory.get_equipped_item(EquipmentSlot.WEAPON)
            armor = char.inventory.get_equipped_item(EquipmentSlot.ARMOR)
            shield = char.inventory.get_equipped_item(EquipmentSlot.SHIELD)

            equipment = {
                "weapon": weapon or "Unarmed",
                "armor": armor or "None",
                "shield": shield or "None",
            }

        return {
            "name": char.name,
            "class": char.character_class.value.title(),
            "level": char.level,
            "hp": char.current_hp,
            "max_hp": char.max_hp,
            "ac": char.armor_class,
            "stats": stats,
            "equipment": equipment,
        }

    def get_inventory_data(self, name: str) -> dict[str, Any] | None:
        """Get inventory data for a character.

        Args:
            name: Character name.

        Returns:
            Dict with equipped, backpack, currency, or None if not found.
        """
        if self._party is None:
            return None

        # Find character
        char = None
        for c in self._party.characters:
            if c.name == name:
                char = c
                break

        if char is None or not hasattr(char, "inventory"):
            return None

        from dnd_engine.systems.inventory import EquipmentSlot

        inv = char.inventory

        # Equipped items
        equipped = {
            "weapon": None,
            "armor": None,
            "shield": None,
        }

        weapon_id = inv.get_equipped_item(EquipmentSlot.WEAPON)
        if weapon_id:
            equipped["weapon"] = {"item_id": weapon_id, "name": weapon_id.replace("_", " ").title()}

        armor_id = inv.get_equipped_item(EquipmentSlot.ARMOR)
        if armor_id:
            equipped["armor"] = {"item_id": armor_id, "name": armor_id.replace("_", " ").title()}

        shield_id = inv.get_equipped_item(EquipmentSlot.SHIELD)
        if shield_id:
            equipped["shield"] = {"item_id": shield_id, "name": shield_id.replace("_", " ").title()}

        # Backpack items
        backpack = []
        for item in inv.get_all_items():
            backpack.append({
                "item_id": item.item_id,
                "name": item.item_id.replace("_", " ").title(),
                "category": item.category,
                "quantity": item.quantity,
            })

        # Currency
        currency = {
            "gold": inv.gold,
            "silver": 0,
            "copper": 0,
        }

        return {
            "equipped": equipped,
            "backpack": backpack,
            "currency": currency,
        }

    def get_all_inventories(self) -> dict[str, dict[str, Any]]:
        """Get inventory data for all party members.

        Returns:
            Dict mapping character name to inventory data.
        """
        if self._party is None:
            return {}

        result = {}
        for char in self._party.characters:
            inv_data = self.get_inventory_data(char.name)
            if inv_data:
                result[char.name] = inv_data

        return result

    # ========== Combat Action Methods ==========

    def get_enemies(self) -> list[dict[str, Any]]:
        """Get list of active enemies for targeting.

        Returns:
            List of dicts with index, name, hp, max_hp for each enemy.
        """
        if self._game_state is None or not self._game_state.in_combat:
            return []

        result = []
        for i, enemy in enumerate(self._game_state.active_enemies):
            if enemy.is_alive:
                result.append({
                    "index": i,
                    "name": enemy.name,
                    "hp": enemy.current_hp,
                    "max_hp": enemy.max_hp,
                })

        return result

    def get_current_combatant(self) -> dict[str, Any] | None:
        """Get info about whose turn it is.

        Returns:
            Dict with name, is_player, or None if not in combat.
        """
        if self._game_state is None or not self._game_state.in_combat:
            return None

        tracker = self._game_state.initiative_tracker
        if tracker is None:
            return None

        current = tracker.get_current_combatant()
        if current is None:
            return None

        creature = current.creature
        is_player = creature in self._party.characters

        return {
            "name": creature.name,
            "is_player": is_player,
            "creature": creature,
        }

    def is_player_turn(self) -> bool:
        """Check if it's currently a player's turn."""
        current = self.get_current_combatant()
        if current is None:
            return False
        return current["is_player"]

    def is_current_combatant_unconscious(self) -> bool:
        """Check if the current combatant is an unconscious party member.

        Returns:
            True if it's a player's turn and they are unconscious (0 HP).
        """
        current = self.get_current_combatant()
        if current is None or not current["is_player"]:
            return False
        creature = current["creature"]
        return hasattr(creature, "is_unconscious") and creature.is_unconscious

    def process_unconscious_turn(self):
        """Process an unconscious character's death saving throw turn.

        Delegates to GameState.process_unconscious_turn() which handles the
        D&D 5E death save mechanics.

        Returns:
            DeathSaveTurnResult with the outcome, or None if not applicable.
        """
        if self._game_state is None:
            return None
        return self._game_state.process_unconscious_turn()

    def get_current_turn_state(self):
        """Get the TurnState for the current combatant.

        Returns:
            TurnState object with action/movement availability, or None if not in combat.
        """
        if (
            self._game_state is None
            or not self._game_state.in_combat
            or self._game_state.initiative_tracker is None
        ):
            return None
        return self._game_state.initiative_tracker.get_current_turn_state()

    def execute_attack(
        self,
        target_index: int,
        attacker: Character | None = None,
    ) -> dict[str, Any]:
        """Execute a melee attack against an enemy.

        Args:
            target_index: Index into active_enemies list.
            attacker: Character making the attack. Uses current turn character if not provided.

        Returns:
            Dict with attack result info (hit, damage, target_killed, etc.)
        """
        if self._game_state is None or not self._game_state.in_combat:
            return {"success": False, "error": "Not in combat"}

        # Get attacker
        if attacker is None:
            current = self.get_current_combatant()
            if current is None or not current["is_player"]:
                return {"success": False, "error": "Not player's turn"}
            attacker = current["creature"]

        # Get target
        enemies = self._game_state.active_enemies
        if target_index < 0 or target_index >= len(enemies):
            return {"success": False, "error": "Invalid target"}

        target = enemies[target_index]
        if not target.is_alive:
            return {"success": False, "error": "Target is dead"}

        # Execute attack through game state
        try:
            result = self._game_state.execute_player_attack(attacker, target)

            return {
                "success": True,
                "hit": result.attack_result.hit if result.attack_result else False,
                "damage": result.attack_result.damage if result.attack_result else 0,
                "critical": result.attack_result.critical_hit if result.attack_result else False,
                "target_name": target.name,
                "target_killed": not target.is_alive,
                "attacker_name": attacker.name,
                "attack_roll": result.attack_result.attack_roll if result.attack_result else 0,
                "target_ac": result.attack_result.target_ac if result.attack_result else 0,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def process_enemy_turn(self) -> dict[str, Any]:
        """Process the current enemy's turn.

        Returns:
            Dict with enemy action result.
        """
        if self._game_state is None or not self._game_state.in_combat:
            return {"success": False, "error": "Not in combat"}

        current = self.get_current_combatant()
        if current is None:
            return {"success": False, "error": "No current combatant"}

        if current["is_player"]:
            return {"success": False, "error": "It's a player's turn"}

        try:
            result = self._game_state.process_enemy_turn()

            if result is None:
                return {"success": True, "action": "skipped", "reason": "No valid action"}

            return {
                "success": True,
                "action": result.action_taken.name if hasattr(result, "action_taken") else "attack",
                "enemy_name": result.enemy_display_name if hasattr(result, "enemy_display_name") else current["name"],
                "target_name": getattr(result, "target_name", None),
                "hit": result.attack_result.hit if hasattr(result, "attack_result") and result.attack_result else None,
                "damage": result.attack_result.damage if hasattr(result, "attack_result") and result.attack_result else 0,
                "target_killed": getattr(result, "target_killed", False),
                "combat_ended": getattr(result, "combat_ended", False),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def advance_turn(self) -> dict[str, Any]:
        """Advance to the next turn in combat.

        Returns:
            Dict with new turn info.
        """
        if self._game_state is None or not self._game_state.in_combat:
            return {"success": False, "error": "Not in combat"}

        tracker = self._game_state.initiative_tracker
        if tracker is None:
            return {"success": False, "error": "No initiative tracker"}

        tracker.next_turn()

        # Check if combat ended
        self._game_state._check_combat_end()

        current = self.get_current_combatant()

        return {
            "success": True,
            "round": tracker.round_number,
            "current_turn": current["name"] if current else None,
            "is_player_turn": current["is_player"] if current else False,
            "combat_ended": not self._game_state.in_combat,
        }

    def end_combat_check(self) -> dict[str, Any]:
        """Check if combat should end and handle cleanup.

        Returns:
            Dict with combat_ended flag and victory status.
        """
        if self._game_state is None:
            return {"combat_ended": True, "victory": False}

        self._game_state._check_combat_end()

        return {
            "combat_ended": not self._game_state.in_combat,
            "victory": len([e for e in self._game_state.active_enemies if e.is_alive]) == 0,
            "party_wiped": self._party.is_wiped() if self._party else True,
        }
