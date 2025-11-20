# ABOUTME: Debug console for QA testing and development workflows
# ABOUTME: Provides slash commands to rapidly manipulate game state for testing

import os
from typing import Optional, List, Dict, Any, Tuple
from dnd_engine.core.game_state import GameState
from dnd_engine.core.character import Character
from dnd_engine.core.creature import Creature, Abilities
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

        # Clear unconscious/dead status
        character.is_unconscious = False

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
        if str(level) in progression_data["levels"]:
            character.xp = progression_data["levels"][str(level)]["xp_required"]

        # Reapply class features for new level
        character.apply_class_features()

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

        # Validate ability
        valid_abilities = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
        if ability not in valid_abilities:
            print_error(f"Invalid ability. Must be one of: {', '.join(valid_abilities)}")
            return

        character = self._find_character(char_name)
        if not character:
            return

        # Set the ability score
        old_value = getattr(character.abilities, ability.lower())
        setattr(character.abilities, ability.lower(), value)

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
            monster_data = None
            for key, data in monsters.items():
                if key.lower() == monster_name.lower():
                    monster_data = data
                    break

            if not monster_data:
                print_error(f"Monster not found: {monster_name}")
                print_message("Use /listmonsters to see available monsters")
                return

            # Create creatures
            spawned = []
            for i in range(count):
                creature = Creature.from_monster_data(monster_data, self.game_state.dice_roller)
                spawned.append(creature)

            # If not in combat, start combat
            if not self.game_state.in_combat:
                self.game_state.active_enemies = spawned
                self.game_state.start_combat()
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

        old_gold = self.game_state.party.currency.to_copper() // 100

        if amount > 0:
            self.game_state.party.currency.add_gold(amount)
            print_status_message(f"Added {amount} gold to party", "success")
        else:
            # Remove gold
            try:
                self.game_state.party.currency.spend_gold(abs(amount))
                print_status_message(f"Removed {abs(amount)} gold from party", "success")
            except ValueError as e:
                print_error(str(e))
                return

        new_gold = self.game_state.party.currency.to_copper() // 100
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
        table.add_column("Category", style="cyan")
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
