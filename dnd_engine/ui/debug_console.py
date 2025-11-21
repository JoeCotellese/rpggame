# ABOUTME: Debug console for QA testing and development workflows
# ABOUTME: Provides slash commands to rapidly manipulate game state for testing

import os
from typing import Optional, List, Dict, Any, Tuple
import random
from dnd_engine.core.game_state import GameState
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.ui.rich_ui import (
    print_error,
    print_status_message,
    print_message,
    print_section,
    print_mechanics_panel,
    console
)
from rich.table import Table


class DebugConsole:
    """
    Debug console for testing and development.

    Provides slash commands (e.g., /revive, /kill, /teleport) that allow
    rapid manipulation of game state for QA testing, bug reproduction,
    and feature demonstrations.

    Commands are organized by priority:
    - CRITICAL: Character manipulation, combat testing, inventory
    - HIGH: Conditions, resources, navigation, spells
    - MEDIUM: Party management, save tools, dungeon manipulation
    - LOW: Proficiencies, dice testing, UI toggles
    """

    def __init__(self, game_state: GameState, enabled: bool = None):
        """
        Initialize the debug console.

        Args:
            game_state: The game state to manipulate
            enabled: Whether debug mode is enabled (defaults to DEBUG_MODE env var)
        """
        self.game_state = game_state

        # Check if debug mode is enabled via environment variable
        if enabled is None:
            enabled = os.getenv("DEBUG_MODE", "false").lower() in ["true", "1", "yes"]

        self.enabled = enabled

        # Command registry: maps command names to handler methods
        self.commands: Dict[str, Any] = {
            # CRITICAL - Character State Manipulation
            "revive": self.cmd_revive,
            "kill": self.cmd_kill,
            "sethp": self.cmd_set_hp,
            "damage": self.cmd_damage,
            "heal": self.cmd_heal,
            "godmode": self.cmd_godmode,
            "setlevel": self.cmd_set_level,
            "addxp": self.cmd_add_xp,
            "setstat": self.cmd_set_stat,

            # CRITICAL - Combat Testing
            "spawn": self.cmd_spawn,
            "despawn": self.cmd_despawn,
            "nextturn": self.cmd_next_turn,
            "endcombat": self.cmd_end_combat,

            # CRITICAL - Inventory & Currency
            "give": self.cmd_give,
            "remove": self.cmd_remove,
            "gold": self.cmd_gold,
            "clearinventory": self.cmd_clear_inventory,

            # HIGH - Condition Testing
            "addcondition": self.cmd_add_condition,
            "removecondition": self.cmd_remove_condition,
            "clearconditions": self.cmd_clear_conditions,
            "listconditions": self.cmd_list_conditions,

            # HIGH - Resource Management
            "setslots": self.cmd_set_slots,
            "restoreslots": self.cmd_restore_slots,
            "setresource": self.cmd_set_resource,
            "shortrest": self.cmd_short_rest,
            "longrest": self.cmd_long_rest,

            # HIGH - Navigation & Exploration
            "teleport": self.cmd_teleport,
            "listrooms": self.cmd_list_rooms,
            "unlock": self.cmd_unlock,
            "reveal": self.cmd_reveal,

            # HIGH - Spellcasting
            "learnspell": self.cmd_learn_spell,
            "forgetspell": self.cmd_forget_spell,
            "listspells": self.cmd_list_spells,

            # MEDIUM - Party Management
            "addcharacter": self.cmd_add_character,
            "removecharacter": self.cmd_remove_character,

            # System
            "help": self.cmd_help,
            "reset": self.cmd_reset,
        }

        # God mode tracking (character name -> invulnerable)
        self.god_mode_characters: set = set()

    def is_debug_command(self, command: str) -> bool:
        """Check if a command is a debug command (starts with /)."""
        return command.startswith("/")

    def parse_command(self, command: str) -> Tuple[str, List[str]]:
        """
        Parse a slash command into command name and arguments.

        Args:
            command: Raw command string (e.g., "/revive Gandalf")

        Returns:
            Tuple of (command_name, arguments_list)
        """
        # Remove leading slash
        command = command.lstrip("/")

        # Split into parts
        parts = command.split()

        if not parts:
            return "", []

        cmd_name = parts[0].lower()
        args = parts[1:]

        return cmd_name, args

    def execute(self, command: str) -> bool:
        """
        Execute a debug command.

        Args:
            command: The full command string (e.g., "/revive Gandalf")

        Returns:
            True if command was handled, False otherwise
        """
        if not self.enabled:
            print_error("Debug console is disabled. Set DEBUG_MODE=true to enable.")
            return False

        if not self.is_debug_command(command):
            return False

        cmd_name, args = self.parse_command(command)

        if not cmd_name:
            print_error("Invalid debug command")
            return False

        # Check if command exists
        if cmd_name not in self.commands:
            print_error(f"Unknown debug command: /{cmd_name}")
            print_message(f"Type '/help' for available debug commands")
            return False

        # Execute the command
        try:
            handler = self.commands[cmd_name]
            handler(args)
            return True
        except Exception as e:
            print_error(f"Debug command failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    # =====================================================================
    # CRITICAL PRIORITY - Character State Manipulation
    # =====================================================================

    def cmd_revive(self, args: List[str]) -> None:
        """Revive a dead or unconscious character."""
        if not args:
            print_error("Usage: /revive <character_name>")
            return

        char_name = " ".join(args)
        character = self._find_character(char_name)

        if not character:
            return

        # Set HP to max
        character.current_hp = character.max_hp

        # Reset death saves
        character.death_save_successes = 0
        character.death_save_failures = 0

        print_status_message(f"{character.name} has been revived to full HP!", "success")

    def cmd_kill(self, args: List[str]) -> None:
        """Kill a character or monster."""
        if not args:
            print_error("Usage: /kill <target_name>")
            return

        target_name = " ".join(args)

        # Try to find as character first
        character = self._find_character(target_name, silent=True)
        if character:
            character.current_hp = 0
            character.death_save_failures = 3
            print_status_message(f"{character.name} has been killed.", "warning")
            return

        # Try to find as enemy
        enemy = self._find_enemy(target_name)
        if enemy:
            enemy.current_hp = 0
            print_status_message(f"{enemy.name} has been killed.", "success")

            # Check if combat should end
            if self.game_state.in_combat:
                self.game_state._check_combat_end()
            return

    def cmd_set_hp(self, args: List[str]) -> None:
        """Set exact HP value for a character."""
        if len(args) < 2:
            print_error("Usage: /sethp <character_name> <hp_value>")
            return

        try:
            hp_value = int(args[-1])
            char_name = " ".join(args[:-1])
        except ValueError:
            print_error("HP value must be a number")
            return

        character = self._find_character(char_name)
        if not character:
            return

        # Clamp to valid range
        hp_value = max(0, min(hp_value, character.max_hp))
        character.current_hp = hp_value

        print_status_message(
            f"{character.name} HP set to {hp_value}/{character.max_hp}",
            "success"
        )

    def cmd_damage(self, args: List[str]) -> None:
        """Deal damage to a character for testing."""
        if len(args) < 2:
            print_error("Usage: /damage <character_name> <damage_amount>")
            return

        try:
            damage = int(args[-1])
            char_name = " ".join(args[:-1])
        except ValueError:
            print_error("Damage must be a number")
            return

        character = self._find_character(char_name)
        if not character:
            return

        # Apply damage
        character.take_damage(damage)

        print_status_message(
            f"{character.name} took {damage} damage. HP: {character.current_hp}/{character.max_hp}",
            "warning"
        )

        if character.current_hp == 0:
            print_message(f"{character.name} is unconscious!")

    def cmd_heal(self, args: List[str]) -> None:
        """Heal a character directly."""
        if len(args) < 2:
            print_error("Usage: /heal <character_name> <heal_amount>")
            return

        try:
            heal_amount = int(args[-1])
            char_name = " ".join(args[:-1])
        except ValueError:
            print_error("Heal amount must be a number")
            return

        character = self._find_character(char_name)
        if not character:
            return

        # Apply healing
        character.heal(heal_amount)

        print_status_message(
            f"{character.name} healed {heal_amount} HP. HP: {character.current_hp}/{character.max_hp}",
            "success"
        )

    def cmd_godmode(self, args: List[str]) -> None:
        """Toggle invulnerability for a character."""
        if not args:
            print_error("Usage: /godmode <character_name>")
            return

        char_name = " ".join(args)
        character = self._find_character(char_name)

        if not character:
            return

        # Toggle god mode
        if character.name in self.god_mode_characters:
            self.god_mode_characters.remove(character.name)
            print_status_message(f"God mode DISABLED for {character.name}", "info")
        else:
            self.god_mode_characters.add(character.name)
            # Set to full HP when enabling
            character.current_hp = character.max_hp
            print_status_message(f"God mode ENABLED for {character.name}", "success")

    def cmd_set_level(self, args: List[str]) -> None:
        """Set character to a specific level."""
        if len(args) < 2:
            print_error("Usage: /setlevel <character_name> <level>")
            return

        try:
            level = int(args[-1])
            char_name = " ".join(args[:-1])
        except ValueError:
            print_error("Level must be a number")
            return

        if level < 1 or level > 20:
            print_error("Level must be between 1 and 20")
            return

        character = self._find_character(char_name)
        if not character:
            return

        old_level = character.level

        # Set level and XP to match
        character.level = level

        # Set XP to the minimum for this level
        progression_data = self.game_state.data_loader.load_progression()
        if str(level) in progression_data.get("xp_by_level", {}):
            character.xp = progression_data["xp_by_level"][str(level)]

        # Reapply class features for new level
        if hasattr(character, 'apply_class_features'):
            character.apply_class_features()
        elif hasattr(character, '_grant_class_features'):
            character._grant_class_features(self.game_state.data_loader)

        print_status_message(
            f"{character.name} level changed from {old_level} to {level}",
            "success"
        )

    def cmd_add_xp(self, args: List[str]) -> None:
        """Grant XP to a character."""
        if len(args) < 2:
            print_error("Usage: /addxp <character_name> <xp_amount>")
            return

        try:
            xp_amount = int(args[-1])
            char_name = " ".join(args[:-1])
        except ValueError:
            print_error("XP amount must be a number")
            return

        character = self._find_character(char_name)
        if not character:
            return

        old_xp = character.xp
        character.gain_xp(xp_amount)

        print_status_message(
            f"{character.name} gained {xp_amount} XP ({old_xp} → {character.xp})",
            "success"
        )

    def cmd_set_stat(self, args: List[str]) -> None:
        """Set ability score for a character."""
        if len(args) < 3:
            print_error("Usage: /setstat <character_name> <ability> <value>")
            print_message("Abilities: STR, DEX, CON, INT, WIS, CHA")
            return

        try:
            value = int(args[-1])
            ability = args[-2].upper()
            char_name = " ".join(args[:-2])
        except ValueError:
            print_error("Ability value must be a number")
            return

        # Validate ability and map to full name
        ability_mapping = {
            "STR": "strength",
            "DEX": "dexterity",
            "CON": "constitution",
            "INT": "intelligence",
            "WIS": "wisdom",
            "CHA": "charisma"
        }

        if ability not in ability_mapping:
            print_error(f"Invalid ability. Must be one of: {', '.join(ability_mapping.keys())}")
            return

        character = self._find_character(char_name)
        if not character:
            return

        # Set the ability score
        ability_name = ability_mapping[ability]
        old_value = getattr(character.abilities, ability_name)
        setattr(character.abilities, ability_name, value)

        print_status_message(
            f"{character.name} {ability} changed from {old_value} to {value}",
            "success"
        )

    # =====================================================================
    # CRITICAL PRIORITY - Combat Testing
    # =====================================================================

    def cmd_spawn(self, args: List[str]) -> None:
        """Spawn enemies in the current room."""
        if not args:
            print_error("Usage: /spawn <monster_name> [count]")
            return

        # Parse count if provided
        count = 1
        if len(args) > 1 and args[-1].isdigit():
            count = int(args[-1])
            monster_name = " ".join(args[:-1])
        else:
            monster_name = " ".join(args)

        # Load monster data
        try:
            monsters = self.game_state.data_loader.load_monsters()

            # Find monster (case-insensitive)
            monster_id = None
            for key, data in monsters.items():
                if key.lower() == monster_name.lower():
                    monster_id = key
                    break

            if not monster_id:
                print_error(f"Monster not found: {monster_name}")
                print_message("Use /listmonsters to see available monsters")
                return

            # Create creatures
            spawned = []
            for i in range(count):
                creature = self.game_state.data_loader.create_monster(monster_id)
                spawned.append(creature)

            # If not in combat, start combat
            if not self.game_state.in_combat:
                self.game_state.active_enemies = spawned
                self.game_state._start_combat()
                print_status_message(f"Spawned {count}x {monster_name} and started combat!", "success")
            else:
                # Add to existing combat
                self.game_state.active_enemies.extend(spawned)
                # Add to initiative
                for creature in spawned:
                    self.game_state.initiative_tracker.add_combatant(creature)
                print_status_message(f"Spawned {count}x {monster_name} into combat!", "success")

        except Exception as e:
            print_error(f"Failed to spawn monster: {e}")

    def cmd_despawn(self, args: List[str]) -> None:
        """Remove a monster from combat."""
        if not args:
            print_error("Usage: /despawn <monster_name>")
            return

        if not self.game_state.in_combat:
            print_error("Not in combat")
            return

        target_name = " ".join(args)
        enemy = self._find_enemy(target_name)

        if not enemy:
            return

        # Remove from active enemies
        self.game_state.active_enemies.remove(enemy)

        # Remove from initiative
        if self.game_state.initiative_tracker:
            # Find and remove from combatants
            for combatant in self.game_state.initiative_tracker.combatants:
                if combatant.creature == enemy:
                    self.game_state.initiative_tracker.combatants.remove(combatant)
                    break

        print_status_message(f"{enemy.name} removed from combat", "success")

        # Check if combat should end
        self.game_state._check_combat_end()

    def cmd_next_turn(self, args: List[str]) -> None:
        """Skip to next turn in initiative."""
        if not self.game_state.in_combat:
            print_error("Not in combat")
            return

        if not self.game_state.initiative_tracker:
            print_error("No initiative tracker active")
            return

        current = self.game_state.initiative_tracker.get_current_combatant()
        self.game_state.initiative_tracker.next_turn()
        next_combatant = self.game_state.initiative_tracker.get_current_combatant()

        print_status_message(
            f"Skipped turn. Next: {next_combatant.creature.name}",
            "info"
        )

    def cmd_end_combat(self, args: List[str]) -> None:
        """Force end combat encounter."""
        if not self.game_state.in_combat:
            print_error("Not in combat")
            return

        self.game_state.end_combat()
        print_status_message("Combat ended", "success")

    # =====================================================================
    # CRITICAL PRIORITY - Inventory & Currency
    # =====================================================================

    def cmd_give(self, args: List[str]) -> None:
        """Give an item to a character."""
        if len(args) < 2:
            print_error("Usage: /give <item_name> <quantity> [character_name]")
            print_message("If character not specified, gives to first party member")
            return

        # Try to parse quantity
        try:
            # Check if last arg is a number
            if args[-1].isdigit():
                quantity = int(args[-1])
                remaining_args = args[:-1]
            else:
                quantity = 1
                remaining_args = args

            # Try to find character name at the end
            # For now, just give to first party member
            character = self.game_state.party.characters[0]
            item_name = " ".join(remaining_args)

        except (ValueError, IndexError):
            print_error("Invalid arguments")
            return

        # Load item data
        items = self.game_state.data_loader.load_items()

        # Find item (case-insensitive)
        item_id = None
        for key in items.keys():
            if key.lower().replace("_", " ") == item_name.lower():
                item_id = key
                break

        if not item_id:
            print_error(f"Item not found: {item_name}")
            return

        # Add to inventory
        character.inventory.add_item(item_id, quantity)

        print_status_message(
            f"Gave {quantity}x {item_name} to {character.name}",
            "success"
        )

    def cmd_remove(self, args: List[str]) -> None:
        """Remove an item from inventory."""
        if len(args) < 2:
            print_error("Usage: /remove <item_name> <quantity>")
            return

        try:
            quantity = int(args[-1])
            item_name = " ".join(args[:-1])
        except ValueError:
            print_error("Quantity must be a number")
            return

        # Remove from first party member for now
        character = self.game_state.party.characters[0]

        # Find item in inventory
        item_id = None
        for iid, qty in character.inventory.items.items():
            if iid.lower().replace("_", " ") == item_name.lower():
                item_id = iid
                break

        if not item_id:
            print_error(f"Item not found in inventory: {item_name}")
            return

        # Remove from inventory
        character.inventory.remove_item(item_id, quantity)

        print_status_message(
            f"Removed {quantity}x {item_name} from {character.name}",
            "success"
        )

    def cmd_gold(self, args: List[str]) -> None:
        """Add or remove gold from party."""
        if not args:
            print_error("Usage: /gold <amount>")
            print_message("Use negative values to remove gold")
            return

        try:
            amount = int(args[0])
        except ValueError:
            print_error("Amount must be a number")
            return

        old_gold = self.game_state.party.currency.gold

        if amount > 0:
            # Add gold directly
            self.game_state.party.currency.gold += amount
            print_status_message(f"Added {amount} gold to party", "success")
        else:
            # Remove gold
            gold_to_remove = abs(amount)
            if self.game_state.party.currency.gold >= gold_to_remove:
                self.game_state.party.currency.gold -= gold_to_remove
                print_status_message(f"Removed {gold_to_remove} gold from party", "success")
            else:
                print_error(f"Not enough gold. Party has {self.game_state.party.currency.gold} gold.")
                return

        new_gold = self.game_state.party.currency.gold
        print_message(f"Party gold: {old_gold} → {new_gold}")

    def cmd_clear_inventory(self, args: List[str]) -> None:
        """Clear a character's inventory."""
        if not args:
            print_error("Usage: /clearinventory <character_name>")
            return

        char_name = " ".join(args)
        character = self._find_character(char_name)

        if not character:
            return

        # Confirm destructive action
        print_message(f"This will remove all items from {character.name}'s inventory.")
        confirm = input("Confirm? (y/n): ").strip().lower()

        if confirm != "y":
            print_status_message("Cancelled", "warning")
            return

        # Clear inventory
        character.inventory.items.clear()

        print_status_message(f"Cleared inventory for {character.name}", "success")

    # =====================================================================
    # HIGH PRIORITY - Condition Testing
    # =====================================================================

    def cmd_add_condition(self, args: List[str]) -> None:
        """Add a condition to a character."""
        if len(args) < 2:
            print_error("Usage: /addcondition <character_name> <condition>")
            print_message("Use /listconditions to see available conditions")
            return

        condition = args[-1].lower()
        char_name = " ".join(args[:-1])

        character = self._find_character(char_name)
        if not character:
            return

        # Add condition
        character.add_condition(condition)

        print_status_message(
            f"Added condition '{condition}' to {character.name}",
            "success"
        )

    def cmd_remove_condition(self, args: List[str]) -> None:
        """Remove a condition from a character."""
        if len(args) < 2:
            print_error("Usage: /removecondition <character_name> <condition>")
            return

        condition = args[-1].lower()
        char_name = " ".join(args[:-1])

        character = self._find_character(char_name)
        if not character:
            return

        if not character.has_condition(condition):
            print_error(f"{character.name} does not have condition '{condition}'")
            return

        # Remove condition
        character.remove_condition(condition)

        print_status_message(
            f"Removed condition '{condition}' from {character.name}",
            "success"
        )

    def cmd_clear_conditions(self, args: List[str]) -> None:
        """Clear all conditions from a character."""
        if not args:
            print_error("Usage: /clearconditions <character_name>")
            return

        char_name = " ".join(args)
        character = self._find_character(char_name)

        if not character:
            return

        # Clear all conditions
        condition_count = len(character.conditions)
        character.conditions.clear()

        print_status_message(
            f"Cleared {condition_count} condition(s) from {character.name}",
            "success"
        )

    def cmd_list_conditions(self, args: List[str]) -> None:
        """List all available conditions."""
        from dnd_engine.systems.condition_manager import ConditionManager

        condition_mgr = ConditionManager(
            dice_roller=self.game_state.dice_roller,
            event_bus=self.game_state.event_bus
        )

        print_section("Available Conditions")

        for condition_id, data in condition_mgr.conditions_data.items():
            name = data.get("name", condition_id)
            desc = data.get("description", "No description")
            print_message(f"• {condition_id}: {name}")
            print_message(f"  {desc}")

    # =====================================================================
    # HIGH PRIORITY - Resource Management
    # =====================================================================

    def cmd_set_slots(self, args: List[str]) -> None:
        """Set spell slot count for a character."""
        if len(args) < 3:
            print_error("Usage: /setslots <character_name> <level> <count>")
            print_message("Example: /setslots Gandalf 3 5")
            return

        try:
            count = int(args[-1])
            level = int(args[-2])
            char_name = " ".join(args[:-2])
        except ValueError:
            print_error("Level and count must be numbers")
            return

        if level < 1 or level > 9:
            print_error("Spell level must be between 1 and 9")
            return

        character = self._find_character(char_name)
        if not character:
            return

        # Set spell slot
        slot_key = f"level_{level}"
        if slot_key not in character.spell_slots:
            print_error(f"{character.name} doesn't have {level}th level spell slots")
            return

        character.spell_slots[slot_key]["current"] = count
        character.spell_slots[slot_key]["max"] = max(count, character.spell_slots[slot_key]["max"])

        print_status_message(
            f"Set {character.name}'s level {level} spell slots to {count}",
            "success"
        )

    def cmd_restore_slots(self, args: List[str]) -> None:
        """Restore all spell slots for a character."""
        if not args:
            print_error("Usage: /restoreslots <character_name>")
            return

        char_name = " ".join(args)
        character = self._find_character(char_name)

        if not character:
            return

        # Restore all spell slots
        for slot_key in character.spell_slots:
            character.spell_slots[slot_key]["current"] = character.spell_slots[slot_key]["max"]

        print_status_message(
            f"Restored all spell slots for {character.name}",
            "success"
        )

    def cmd_set_resource(self, args: List[str]) -> None:
        """Set a resource pool value."""
        if len(args) < 3:
            print_error("Usage: /setresource <character_name> <resource_name> <amount>")
            print_message("Example: /setresource Fighter 'Action Surge' 2")
            return

        try:
            amount = int(args[-1])
            resource_name = args[-2]
            char_name = " ".join(args[:-2])
        except ValueError:
            print_error("Amount must be a number")
            return

        character = self._find_character(char_name)
        if not character:
            return

        # Find resource pool (case-insensitive)
        pool = None
        for pool_name, pool_obj in character.resource_pools.items():
            if pool_name.lower() == resource_name.lower():
                pool = pool_obj
                resource_name = pool_name  # Use actual name
                break

        if not pool:
            print_error(f"Resource pool '{resource_name}' not found on {character.name}")
            print_message(f"Available: {', '.join(character.resource_pools.keys())}")
            return

        # Set resource
        pool.current = min(amount, pool.maximum)

        print_status_message(
            f"Set {character.name}'s {resource_name} to {pool.current}/{pool.maximum}",
            "success"
        )

    def cmd_short_rest(self, args: List[str]) -> None:
        """Instantly take a short rest (all party members)."""
        print_section("Short Rest")

        for character in self.game_state.party.characters:
            character.take_short_rest()

        print_status_message("Party took a short rest", "success")

    def cmd_long_rest(self, args: List[str]) -> None:
        """Instantly take a long rest (all party members)."""
        print_section("Long Rest")

        for character in self.game_state.party.characters:
            character.take_long_rest()

        print_status_message("Party took a long rest and is fully restored!", "success")

    # =====================================================================
    # HIGH PRIORITY - Navigation & Exploration
    # =====================================================================

    def cmd_teleport(self, args: List[str]) -> None:
        """Teleport to a specific room."""
        if not args:
            print_error("Usage: /teleport <room_id>")
            print_message("Use /listrooms to see available room IDs")
            return

        room_id = "_".join(args)

        # Check if room exists
        if room_id not in self.game_state.dungeon["rooms"]:
            print_error(f"Room not found: {room_id}")
            print_message("Use /listrooms to see available rooms")
            return

        # Teleport
        old_room = self.game_state.current_room_id
        self.game_state.current_room_id = room_id

        # End combat if in combat
        if self.game_state.in_combat:
            self.game_state.end_combat()

        print_status_message(
            f"Teleported from {old_room} to {room_id}",
            "success"
        )

    def cmd_list_rooms(self, args: List[str]) -> None:
        """List all rooms in the current dungeon."""
        print_section(f"Rooms in {self.game_state.dungeon_name}")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Room ID", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Type", style="yellow")

        for room_id, room_data in self.game_state.dungeon["rooms"].items():
            room_name = room_data.get("name", "Unknown")
            room_type = room_data.get("type", "unknown")

            # Mark current room
            if room_id == self.game_state.current_room_id:
                room_id = f"→ {room_id}"

            table.add_row(room_id, room_name, room_type)

        console.print(table)

    def cmd_unlock(self, args: List[str]) -> None:
        """Unlock a door in the current room."""
        if not args:
            print_error("Usage: /unlock <direction>")
            print_message("Example: /unlock north")
            return

        direction = args[0].lower()
        current_room = self.game_state.get_current_room()
        exits = current_room.get("exits", {})

        if direction not in exits:
            print_error(f"No exit to the {direction}")
            return

        exit_data = exits[direction]

        # Check if door is locked
        if not exit_data.get("locked", False):
            print_message(f"The {direction} exit is already unlocked")
            return

        # Unlock it
        exit_data["locked"] = False

        print_status_message(f"Unlocked the {direction} exit", "success")

    def cmd_reveal(self, args: List[str]) -> None:
        """Reveal all hidden features in the current room."""
        current_room = self.game_state.get_current_room()

        # Mark room as searched
        current_room["searched"] = True

        # Show hidden features
        hidden_features = current_room.get("hidden_features", [])

        if not hidden_features:
            print_message("No hidden features in this room")
            return

        print_section("Revealed Hidden Features")

        for feature in hidden_features:
            desc = feature.get("description", "Unknown feature")
            print_message(f"• {desc}")

        print_status_message("Revealed all hidden features", "success")

    # =====================================================================
    # HIGH PRIORITY - Spellcasting
    # =====================================================================

    def cmd_learn_spell(self, args: List[str]) -> None:
        """Add a spell to a character's known spells."""
        if len(args) < 2:
            print_error("Usage: /learnspell <character_name> <spell_name>")
            return

        # Find character and spell
        spell_name = args[-1]
        char_name = " ".join(args[:-1])

        character = self._find_character(char_name)
        if not character:
            return

        # Load spells
        spells = self.game_state.data_loader.load_spells()

        # Find spell (case-insensitive, handle underscores)
        spell_id = None
        for key in spells.keys():
            if key.lower().replace("_", " ") == spell_name.lower().replace("_", " "):
                spell_id = key
                break

        if not spell_id:
            print_error(f"Spell not found: {spell_name}")
            return

        # Add to known spells if not already known
        if spell_id in character.known_spells:
            print_message(f"{character.name} already knows {spell_id}")
            return

        character.known_spells.append(spell_id)

        # Also add to prepared spells if character prepares spells
        if spell_id not in character.prepared_spells:
            character.prepared_spells.append(spell_id)

        print_status_message(
            f"{character.name} learned {spell_id}",
            "success"
        )

    def cmd_forget_spell(self, args: List[str]) -> None:
        """Remove a spell from a character's known spells."""
        if len(args) < 2:
            print_error("Usage: /forgetspell <character_name> <spell_name>")
            return

        spell_name = args[-1]
        char_name = " ".join(args[:-1])

        character = self._find_character(char_name)
        if not character:
            return

        # Find spell in known spells (case-insensitive)
        spell_id = None
        for known_spell in character.known_spells:
            if known_spell.lower().replace("_", " ") == spell_name.lower().replace("_", " "):
                spell_id = known_spell
                break

        if not spell_id:
            print_error(f"{character.name} doesn't know {spell_name}")
            return

        # Remove from known and prepared
        character.known_spells.remove(spell_id)
        if spell_id in character.prepared_spells:
            character.prepared_spells.remove(spell_id)

        print_status_message(
            f"{character.name} forgot {spell_id}",
            "success"
        )

    def cmd_list_spells(self, args: List[str]) -> None:
        """List available spells, optionally filtered by class and level."""
        spells = self.game_state.data_loader.load_spells()

        # Parse filters
        class_filter = None
        level_filter = None

        if len(args) >= 1:
            class_filter = args[0].lower()
        if len(args) >= 2:
            try:
                level_filter = int(args[1])
            except ValueError:
                print_error("Level must be a number (0-9)")
                return

        print_section("Available Spells")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Spell", style="cyan", no_wrap=True)
        table.add_column("Level", style="white", justify="center")
        table.add_column("School", style="yellow")
        table.add_column("Classes", style="green")

        count = 0
        for spell_id, spell_data in sorted(spells.items()):
            level = spell_data.get("level", 0)
            school = spell_data.get("school", "unknown")
            classes = spell_data.get("classes", [])

            # Apply filters
            if class_filter and class_filter not in [c.lower() for c in classes]:
                continue
            if level_filter is not None and level != level_filter:
                continue

            # Format level
            level_str = "Cantrip" if level == 0 else str(level)

            # Format classes
            classes_str = ", ".join(classes[:3])  # Show first 3 classes
            if len(classes) > 3:
                classes_str += "..."

            table.add_row(spell_id, level_str, school, classes_str)
            count += 1

            # Limit output
            if count >= 50:
                print_message(f"\n... and {len(spells) - 50} more spells")
                break

        console.print(table)

        if class_filter or level_filter is not None:
            filters = []
            if class_filter:
                filters.append(f"class={class_filter}")
            if level_filter is not None:
                filters.append(f"level={level_filter}")
            print_message(f"\nFiltered by: {', '.join(filters)}")

    # =====================================================================
    # MEDIUM PRIORITY - Party Management
    # =====================================================================

    def cmd_add_character(self, args: List[str]) -> None:
        """Add a new character to the party with specified class, optional race and level."""
        # Load data once at the start
        races_data = self.game_state.data_loader.load_races()
        classes_data = self.game_state.data_loader.load_classes()
        items_data = self.game_state.data_loader.load_items()
        spells_data = self.game_state.data_loader.load_spells()

        if len(args) < 1:
            print_error("Usage: /addcharacter <class> [race] [level]")
            print_message("Examples:")
            print_message("  /addcharacter wizard            # random race, level 1")
            print_message("  /addcharacter wizard high_elf   # specified race, level 1")
            print_message("  /addcharacter wizard high_elf 3 # fully specified")
            print_message(f"Available classes: {', '.join(sorted(classes_data.keys()))}")
            print_message(f"Available races: {', '.join(sorted(races_data.keys()))}")
            return

        class_name = args[0].lower()
        race_name = None
        level = 1

        # Parse optional race argument
        if len(args) >= 2:
            # Check if second arg is a number (level) or race name
            if args[1].isdigit():
                # It's a level, pick random race
                level = int(args[1])
                if level < 1 or level > 20:
                    print_error("Level must be between 1 and 20")
                    return
            else:
                # It's a race name
                race_name = args[1].lower()

        # Parse optional level argument
        if len(args) >= 3:
            try:
                level = int(args[2])
                if level < 1 or level > 20:
                    print_error("Level must be between 1 and 20")
                    return
            except ValueError:
                print_error("Level must be a number")
                return

        # Validate class
        if class_name not in classes_data:
            print_error(f"Invalid class: {class_name}")
            print_message(f"Available: {', '.join(classes_data.keys())}")
            return

        # Handle race - pick random if not specified
        if race_name is None:
            race_name = random.choice(list(races_data.keys()))
            print_message(f"Randomly selected race: {race_name}")
        elif race_name not in races_data:
            print_error(f"Invalid race: {race_name}")
            print_message(f"Available: {', '.join(races_data.keys())}")
            return

        # Get class and race data
        class_data = classes_data[class_name]
        race_data = races_data[race_name]

        # Generate random name
        name_prefixes = ["Brave", "Bold", "Mighty", "Swift", "Wise", "Dark", "Noble", "Silent"]
        name_suffixes = ["blade", "heart", "shield", "storm", "wind", "fire", "shadow", "light"]
        name = f"{random.choice(name_prefixes)}{random.choice(name_suffixes)}"

        # Create character factory
        factory = CharacterFactory(self.game_state.dice_roller)

        # Roll ability scores
        all_rolls = factory.roll_all_abilities(self.game_state.dice_roller)
        scores = [score for score, _ in all_rolls]

        # Auto-assign abilities based on class priorities
        abilities = factory.auto_assign_abilities(scores, class_data)

        # Apply racial bonuses
        abilities = factory.apply_racial_bonuses(abilities, race_data)

        # Create abilities object
        abilities_obj = Abilities(
            strength=abilities["strength"],
            dexterity=abilities["dexterity"],
            constitution=abilities["constitution"],
            intelligence=abilities["intelligence"],
            wisdom=abilities["wisdom"],
            charisma=abilities["charisma"]
        )

        # Calculate HP for level 1 using factory method
        con_modifier = factory.calculate_ability_modifier(abilities["constitution"])
        hp = factory.calculate_hp(class_data, con_modifier, level=1)

        # Calculate AC
        starting_equipment = class_data.get("starting_equipment", [])
        armor_id = None
        for item_id in starting_equipment:
            if item_id in items_data.get("armor", {}):
                armor_id = item_id
                break

        armor_data = items_data["armor"].get(armor_id) if armor_id else None
        ac = factory.calculate_ac(armor_data, abilities_obj.dex_mod)

        # Auto-select skill proficiencies (take first N available)
        skill_profs = class_data.get("skill_proficiencies", {})
        num_skills = skill_profs.get("choose", 0)
        available_skills = skill_profs.get("from", [])
        skill_proficiencies = available_skills[:num_skills]

        # Get expertise for rogues (first 2 skills)
        expertise_skills = []
        if class_name == "rogue" and skill_proficiencies:
            expertise_skills = skill_proficiencies[:2]

        # Get weapon and armor proficiencies
        weapon_proficiencies = class_data.get("weapon_proficiencies", [])
        armor_proficiencies = class_data.get("armor_proficiencies", [])

        # Create character
        try:
            character_class_enum = CharacterClass[class_name.upper()]
        except KeyError:
            print_error(f"Class not found in CharacterClass enum: {class_name}")
            return

        character = Character(
            name=name,
            character_class=character_class_enum,
            level=1,  # Start at level 1, will level up below
            abilities=abilities_obj,
            max_hp=hp,
            ac=ac,
            xp=0,
            skill_proficiencies=skill_proficiencies,
            expertise_skills=expertise_skills,
            weapon_proficiencies=weapon_proficiencies,
            armor_proficiencies=armor_proficiencies
        )

        # Store race and saving throws
        character.race = race_name
        character.saving_throw_proficiencies = class_data.get("saving_throw_proficiencies", [])

        # Level up character to target level (uses actual dice roller)
        for _ in range(1, level):
            character.level += 1
            character._increase_hp(self.game_state.data_loader)

        # Initialize class resources and spellcasting for final level
        factory.initialize_class_resources(character, class_data, level)
        factory.initialize_spellcasting(character, class_data, spells_data, interactive=False)

        # Apply starting equipment
        factory.apply_starting_equipment(character, class_data, items_data)

        # Add to party
        self.game_state.party.add_character(character)

        print_status_message(
            f"Added {name} (Level {level} {race_data['name']} {class_data['name']}) to party",
            "success"
        )
        print_message(f"HP: {character.current_hp}/{character.max_hp}, AC: {character.ac}")

    def cmd_remove_character(self, args: List[str]) -> None:
        """Remove a character from the party."""
        if not args:
            print_error("Usage: /removecharacter <character_name>")
            return

        char_name = " ".join(args)
        character = self._find_character(char_name)

        if not character:
            return

        # Confirm removal
        print_message(f"This will remove {character.name} from the party.")
        confirm = input("Confirm? (y/n): ").strip().lower()

        if confirm != "y":
            print_status_message("Cancelled", "warning")
            return

        # Remove from party
        self.game_state.party.remove_character(character)

        print_status_message(f"Removed {character.name} from party", "success")

    # =====================================================================
    # System Commands
    # =====================================================================

    def cmd_reset(self, args: List[str]) -> None:
        """Reset the game (converted from regular reset command)."""
        print_message("Reset functionality moved to /reset")
        print_message("This will reset the dungeon while keeping your party intact")

        # Confirm
        confirm = input("Confirm reset? (y/n): ").strip().lower()

        if confirm != "y":
            print_status_message("Reset cancelled", "warning")
            return

        # Reset dungeon
        self.game_state.reset_dungeon()
        self.game_state.reset_party_hp()
        self.game_state.reset_party_conditions()

        print_status_message("Game reset successfully!", "success")

    def cmd_help(self, args: List[str]) -> None:
        """Show debug console help."""
        if args:
            # Show help for specific command
            cmd_name = args[0].lower()
            if cmd_name in self.commands:
                handler = self.commands[cmd_name]
                print_section(f"Help: /{cmd_name}")
                print_message(handler.__doc__ or "No help available")
            else:
                print_error(f"Unknown command: /{cmd_name}")
            return

        # Show all commands organized by category
        print_section("Debug Console Commands")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Category", style="cyan", no_wrap=True)
        table.add_column("Commands", style="white")

        # CRITICAL - Character
        table.add_row(
            "Character",
            "/revive, /kill, /sethp, /damage, /heal\n/godmode, /setlevel, /addxp, /setstat"
        )

        # CRITICAL - Combat
        table.add_row(
            "Combat",
            "/spawn, /despawn, /nextturn, /endcombat"
        )

        # CRITICAL - Inventory
        table.add_row(
            "Inventory",
            "/give, /remove, /gold, /clearinventory"
        )

        # HIGH - Conditions
        table.add_row(
            "Conditions",
            "/addcondition, /removecondition\n/clearconditions, /listconditions"
        )

        # HIGH - Resources
        table.add_row(
            "Resources",
            "/setslots, /restoreslots, /setresource\n/shortrest, /longrest"
        )

        # HIGH - Navigation
        table.add_row(
            "Navigation",
            "/teleport, /listrooms, /unlock, /reveal"
        )

        # HIGH - Spells
        table.add_row(
            "Spells",
            "/learnspell, /forgetspell, /listspells"
        )

        # MEDIUM - Party Management
        table.add_row(
            "Party",
            "/addcharacter, /removecharacter"
        )

        # System
        table.add_row(
            "System",
            "/help, /reset"
        )

        console.print(table)
        print_message("\nUse '/help <command>' for detailed help on a specific command")

    # =====================================================================
    # Helper Methods
    # =====================================================================

    def _find_character(self, name: str, silent: bool = False) -> Optional[Character]:
        """Find a character by name (case-insensitive)."""
        for character in self.game_state.party.characters:
            if character.name.lower() == name.lower():
                return character

        if not silent:
            print_error(f"Character not found: {name}")
        return None

    def _find_enemy(self, name: str) -> Optional[Creature]:
        """Find an enemy by name or number."""
        if not self.game_state.in_combat:
            print_error("Not in combat")
            return None

        # Try to match by name
        for enemy in self.game_state.active_enemies:
            if enemy.name.lower() in name.lower() or name.lower() in enemy.name.lower():
                return enemy

        print_error(f"Enemy not found: {name}")
        return None

    def is_god_mode(self, character: Character) -> bool:
        """Check if a character has god mode enabled."""
        return character.name in self.god_mode_characters
