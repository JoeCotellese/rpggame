# ABOUTME: Command-line interface for the D&D 5E terminal game
# ABOUTME: Handles player input, displays game state, and manages the game loop

import sys
from typing import Optional, List, Dict, Any
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.combat import AttackResult
from dnd_engine.utils.events import EventBus, Event, EventType
from dnd_engine.ui.rich_ui import (
    console,
    create_party_status_table,
    create_inventory_table,
    create_combat_table,
    print_status_message,
    print_error,
    print_room_description,
    print_help_section,
    print_title,
    print_message,
    print_section,
    print_list,
    print_mechanics_panel,
    print_narrative_loading,
    print_narrative_panel
)


class CLI:
    """
    Command-line interface for the game.

    Handles:
    - Displaying game state
    - Processing player input
    - Combat turns
    - Game loop
    """

    def __init__(self, game_state: GameState, auto_save_enabled: bool = True):
        """
        Initialize the CLI.

        Args:
            game_state: The game state to interact with
            auto_save_enabled: Whether to enable auto-save feature
        """
        self.game_state = game_state
        self.running = True
        self.narrative_pending = False
        self.auto_save_enabled = auto_save_enabled

        # Subscribe to game events for display
        self.game_state.event_bus.subscribe(EventType.COMBAT_START, self._on_combat_start)
        self.game_state.event_bus.subscribe(EventType.COMBAT_END, self._on_combat_end)
        self.game_state.event_bus.subscribe(EventType.DAMAGE_DEALT, self._on_damage_dealt)
        self.game_state.event_bus.subscribe(EventType.ITEM_ACQUIRED, self._on_item_acquired)
        self.game_state.event_bus.subscribe(EventType.GOLD_ACQUIRED, self._on_gold_acquired)
        self.game_state.event_bus.subscribe(EventType.ENHANCEMENT_STARTED, self._on_enhancement_started)
        self.game_state.event_bus.subscribe(EventType.DESCRIPTION_ENHANCED, self._on_description_enhanced)
        self.game_state.event_bus.subscribe(EventType.ROOM_ENTER, self._on_room_enter)

    def display_banner(self) -> None:
        """Display the game banner."""
        print_title("D&D 5E Terminal Game", "Welcome to your adventure!")

    def display_room(self) -> None:
        """Display the current room description."""
        desc = self.game_state.get_room_description()
        room = self.game_state.get_current_room()

        # Extract room name and description
        room_name = room.get("name", "Unknown Room")
        room_text = room.get("description", desc)
        exits = room.get("exits", [])

        print_room_description(room_name, room_text, exits)

    def display_player_status(self) -> None:
        """Display status for all party members."""
        party_status = self.game_state.get_player_status()

        # Convert party status to table format
        party_data = []
        for status in party_status:
            party_data.append({
                "name": status['name'],
                "class": "Fighter",  # TODO: Get actual class from character
                "level": status['level'],
                "hp": status['hp'],
                "max_hp": status['max_hp'],
                "ac": status['ac'],
                "xp": status['xp']
            })

        table = create_party_status_table(party_data)
        console.print(table)

    def display_combat_status(self) -> None:
        """Display combat status and initiative order."""
        if not self.game_state.in_combat or not self.game_state.initiative_tracker:
            return

        # Prepare combat data
        combatants = []
        current_combatant = self.game_state.initiative_tracker.get_current_combatant()

        for entry in self.game_state.initiative_tracker.get_all_combatants():
            is_player = any(char == entry.creature for char in self.game_state.party.characters)
            combatants.append({
                "name": entry.creature.name,
                "initiative": entry.initiative_total,
                "hp": entry.creature.current_hp,
                "max_hp": entry.creature.max_hp,
                "is_player": is_player,
                "current_turn": entry == current_combatant
            })

        table = create_combat_table(combatants)
        console.print(table)

    def get_player_command(self) -> str:
        """
        Get a command from the player with history support.

        Returns:
            Player's command as a string
        """
        try:
            from prompt_toolkit import prompt
            from prompt_toolkit.history import FileHistory
            from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
            from pathlib import Path

            # Store history in user's home directory
            history_file = Path.home() / ".dnd_game_history"

            return prompt(
                "\n> ",
                history=FileHistory(str(history_file)),
                auto_suggest=AutoSuggestFromHistory(),
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "quit"
        except ImportError:
            # Fallback to basic input if prompt_toolkit is not available
            return input("\n> ").strip().lower()

    def process_exploration_command(self, command: str) -> None:
        """
        Process a command during exploration mode.

        Args:
            command: The player's command
        """
        if command in ["quit", "exit", "q"]:
            self.running = False
            print_status_message("Thanks for playing!", "success")
            return

        if command in ["help", "h", "?"]:
            self.display_help_exploration()
            return

        # Support multiple movement command styles
        # 1. "move north" or "go north"
        # 2. Bare directions: "north", "n", "south", "s", etc.
        direction_aliases = {
            "north": "north", "n": "north",
            "south": "south", "s": "south",
            "east": "east", "e": "east",
            "west": "west", "w": "west"
        }

        if command.startswith("move ") or command.startswith("go ") or command.startswith("m ") or command.startswith("g "):
            direction = command.split()[1] if len(command.split()) > 1 else ""
            self.handle_move(direction)
            return

        # Check if command is a bare direction
        if command in direction_aliases:
            self.handle_move(direction_aliases[command])
            return

        if command in ["look", "l"]:
            self.display_room()
            return

        if command in ["status", "stats"]:
            self.display_player_status()
            return

        if command in ["search"]:
            self.handle_search()
            return

        if command in ["inventory", "i", "inv"] or command.startswith("inventory ") or command.startswith("inv "):
            # Parse inventory subcommand
            parts = command.split()
            if len(parts) > 1:
                filter_arg = " ".join(parts[1:])
                self.display_inventory(filter_arg)
            else:
                self.display_inventory()
            return

        if command == "equip" or command.startswith("equip "):
            parts = command.split()[1:]
            if not parts:
                print_error("Specify an item to equip. Example: 'equip longsword' or 'equip longsword on 2'")
                return
            # Parse with support for "on" keyword
            item_id, player_id = self._parse_command_with_target(parts)
            self.handle_equip(item_id, player_id)
            return

        if command == "unequip" or command.startswith("unequip "):
            parts = command.split()[1:]
            if not parts:
                print_error("Specify a slot to unequip. Example: 'unequip weapon' or 'unequip weapon on gandalf'")
                return
            # Parse with support for "on" keyword
            slot_name, player_id = self._parse_command_with_target(parts)
            self.handle_unequip(slot_name, player_id)
            return

        if command == "use" or command.startswith("use "):
            parts = command.split()[1:]
            if not parts:
                print_error("Specify an item to use. Example: 'use potion' or 'use potion on 2'")
                return
            # Parse with support for "on" keyword
            item_id, player_id = self._parse_command_with_target(parts)
            self.handle_use_item(item_id, player_id)
            return

        if command in ["save"]:
            self.handle_save()
            return

        print_status_message("Unknown command. Type 'help' for available commands.", "warning")

    def process_combat_command(self, command: str) -> None:
        """
        Process a command during combat.

        Args:
            command: The player's command
        """
        if command in ["help", "h", "?"]:
            self.display_help_combat()
            return

        if command.startswith("attack "):
            target_name = " ".join(command.split()[1:])
            self.handle_attack(target_name)
            return

        if command == "attack":
            # Show available targets
            living_enemies = [e.name for e in self.game_state.active_enemies if e.is_alive]
            if living_enemies:
                print_error(f"Specify a target. Available enemies: {', '.join(living_enemies)}")
            else:
                print_error("No enemies to attack!")
            return

        if command in ["status", "stats"]:
            self.display_combat_status()
            return

        # Provide helpful suggestions for unknown commands
        print_status_message("Unknown combat command.", "warning")
        living_enemies = [e.name for e in self.game_state.active_enemies if e.is_alive]
        if living_enemies:
            print_status_message(f"Try: 'attack {living_enemies[0].lower()}' or 'help' for more commands", "info")

    def handle_move(self, direction: str) -> None:
        """Handle movement command."""
        if not direction:
            # Show available exits
            room = self.game_state.get_current_room()
            exits = room.get("exits", [])
            if exits:
                print_status_message(f"Specify a direction. Available exits: {', '.join(exits)}", "warning")
            else:
                print_status_message("No exits available from this room.", "warning")
            return

        success = self.game_state.move(direction)
        if success:
            print_status_message(f"You move {direction}", "info")
            self.display_room()
        else:
            if self.game_state.in_combat:
                print_error("You cannot move during combat!")
            else:
                # Show available exits when movement fails
                room = self.game_state.get_current_room()
                exits = room.get("exits", [])
                if exits:
                    print_error(f"You cannot go {direction} from here. Available exits: {', '.join(exits)}")
                else:
                    print_error("No exits available from this room.")

    def handle_search(self) -> None:
        """Handle search command."""
        items = self.game_state.search_room()
        if items:
            print_status_message("You search the room and find:", "success")
            for item in items:
                if item["type"] == "gold":
                    print_status_message(f"{item['amount']} gold pieces", "info")
                else:
                    print_status_message(f"{item.get('id', 'an item')}", "info")
        else:
            room = self.game_state.get_current_room()
            if room.get("searched"):
                print_status_message("You've already searched this room", "warning")
            else:
                print_status_message("You find nothing of interest", "info")

    def handle_attack(self, target_name: str) -> None:
        """Handle attack command during combat."""
        if not self.game_state.in_combat:
            print_error("You're not in combat!")
            return

        # Check if it's a party member's turn
        current = self.game_state.initiative_tracker.get_current_combatant()
        attacker = None
        for character in self.game_state.party.characters:
            if current.creature == character:
                attacker = character
                break

        if not attacker:
            # Show which party member's turn it is or if it's an enemy turn
            enemy_turn = False
            for enemy in self.game_state.active_enemies:
                if current.creature == enemy:
                    print_status_message(f"It's {current.creature.name}'s turn, not a party member's!", "warning")
                    enemy_turn = True
                    break
            if not enemy_turn:
                print_status_message(f"It's not a valid combatant's turn!", "warning")
            return

        # Find target
        target = None
        for enemy in self.game_state.active_enemies:
            if enemy.is_alive and enemy.name.lower() == target_name.lower():
                target = enemy
                break

        if not target:
            print_error(f"No such enemy: {target_name}")
            living_enemies = [e.name for e in self.game_state.active_enemies if e.is_alive]
            if living_enemies:
                print_status_message(f"Available targets: {', '.join(living_enemies)}", "info")
            return

        # Log player action
        from dnd_engine.utils.logging_config import get_logging_config
        logging_config = get_logging_config()
        if logging_config:
            logging_config.log_player_action(
                character=attacker.name,
                action="attack",
                details=f"target={target.name}"
            )

        # Perform attack
        result = self.game_state.combat_engine.resolve_attack(
            attacker=attacker,
            defender=target,
            attack_bonus=attacker.melee_attack_bonus,
            damage_dice=f"1d8+{attacker.melee_damage_bonus}",
            apply_damage=True
        )

        # Display mechanics (simplified, without panel)
        console.print(f"[dim blue]⚔️  {str(result)}[/dim blue]")

        # Emit damage event
        if result.hit:
            self.game_state.event_bus.emit(Event(
                type=EventType.DAMAGE_DEALT,
                data={
                    "attacker": result.attacker_name,
                    "defender": result.defender_name,
                    "damage": result.damage,
                    "critical": result.critical_hit
                }
            ))

        # Check if target died
        if not target.is_alive:
            print_status_message(f"{target.name} is defeated!", "success")
            self.game_state.event_bus.emit(Event(
                type=EventType.CHARACTER_DEATH,
                data={"name": target.name}
            ))

        # End player turn
        self.game_state.initiative_tracker.next_turn()

        # Check if combat is over
        self.game_state._check_combat_end()

        if self.game_state.in_combat:
            # Process enemy turns
            self.process_enemy_turns()

    def process_enemy_turns(self) -> None:
        """Process all enemy turns until it's a party member's turn again."""
        while self.game_state.in_combat:
            current = self.game_state.initiative_tracker.get_current_combatant()

            # If it's a party member's turn, stop
            is_party_turn = False
            for character in self.game_state.party.characters:
                if current.creature == character:
                    is_party_turn = True
                    print_section(f"{character.name}'s Turn")
                    break

            if is_party_turn:
                break

            # Enemy turn
            enemy = current.creature
            if not enemy.is_alive:
                self.game_state.initiative_tracker.next_turn()
                continue

            print_status_message(f"{enemy.name}'s turn...", "info")

            # Choose target from living party members (lowest HP)
            living_party = self.game_state.party.get_living_members()
            if not living_party:
                break  # No one to attack

            target = min(living_party, key=lambda c: c.current_hp)

            # Get monster data for attack
            monsters = self.game_state.data_loader.load_monsters()
            monster_data = None
            for mid, mdata in monsters.items():
                if mdata["name"] == enemy.name:
                    monster_data = mdata
                    break

            if monster_data and monster_data.get("actions"):
                action = monster_data["actions"][0]
                result = self.game_state.combat_engine.resolve_attack(
                    attacker=enemy,
                    defender=target,
                    attack_bonus=action["attack_bonus"],
                    damage_dice=action["damage"],
                    apply_damage=True
                )

                console.print(f"[dim blue]⚔️  {str(result)}[/dim blue]")

                if result.hit:
                    self.game_state.event_bus.emit(Event(
                        type=EventType.DAMAGE_DEALT,
                        data={
                            "attacker": enemy.name,
                            "defender": target.name,
                            "damage": result.damage
                        }
                    ))

                # Check if party member died
                if not target.is_alive:
                    print_status_message(f"{target.name} has fallen!", "warning")
                    self.game_state.event_bus.emit(Event(
                        type=EventType.CHARACTER_DEATH,
                        data={"name": target.name}
                    ))

            # Next turn
            self.game_state.initiative_tracker.next_turn()

            # Check if entire party is dead
            if self.game_state.party.is_wiped():
                break

    def _parse_command_with_target(self, parts: List[str]) -> tuple[str, Optional[str]]:
        """
        Parse item/slot name and optional player identifier from command parts.
        Supports both syntaxes:
        - Old: "potion 2" or "potion gandalf"
        - New: "potion on 2" or "potion on gandalf"

        Args:
            parts: Command parts (e.g., ["longsword", "2"] or ["potion", "on", "gandalf"])

        Returns:
            Tuple of (item_name, player_identifier)
        """
        if not parts:
            return "", None

        # Check for "on" keyword (new explicit syntax)
        if "on" in parts:
            on_index = parts.index("on")
            if on_index == len(parts) - 1:
                # "on" is the last word, no target specified
                item_name = " ".join(parts[:on_index])
                return item_name, None
            else:
                # Everything before "on" is the item, everything after is the target
                item_name = " ".join(parts[:on_index])
                player_id = " ".join(parts[on_index + 1:])
                return item_name, player_id

        # Fall back to old syntax (last word might be player identifier)
        return self._parse_item_and_player(parts)

    def _parse_item_and_player(self, parts: List[str]) -> tuple[str, Optional[str]]:
        """
        Parse item/slot name and optional player identifier from command parts.

        Args:
            parts: Command parts (e.g., ["longsword", "2"] or ["potion", "of", "healing", "gandalf"])

        Returns:
            Tuple of (item_name, player_identifier)
        """
        if not parts:
            return "", None

        # Try the last part as a player identifier
        # Check if it's a number or matches a character name
        last_part = parts[-1]

        # Check if it's a number
        try:
            player_num = int(last_part)
            if 1 <= player_num <= len(self.game_state.party.characters):
                # Valid player number
                item_name = " ".join(parts[:-1]) if len(parts) > 1 else ""
                return item_name, last_part
        except ValueError:
            pass

        # Check if it matches a character name
        for character in self.game_state.party.characters:
            if character.name.lower() == last_part.lower():
                # Valid player name
                item_name = " ".join(parts[:-1]) if len(parts) > 1 else ""
                return item_name, last_part

        # Last part is not a player identifier, treat entire string as item name
        return " ".join(parts), None

    def _get_target_player(self, player_identifier: Optional[str]) -> Optional[Character]:
        """
        Get a target player from an identifier (number or name).

        Args:
            player_identifier: Optional player identifier (1-based index or character name)

        Returns:
            The matching character, or None if not found or if identifier is invalid
        """
        living_members = self.game_state.party.get_living_members()
        if not living_members:
            return None

        # If no identifier, return first living member (backward compatibility)
        if not player_identifier:
            return living_members[0]

        # Try to parse as a number (1-based index)
        try:
            index = int(player_identifier) - 1  # Convert to 0-based index
            if 0 <= index < len(self.game_state.party.characters):
                character = self.game_state.party.characters[index]
                if character.is_alive:
                    return character
                else:
                    print_error(f"Player {player_identifier} is not alive!")
                    return None
            else:
                print_error(f"Invalid player number: {player_identifier}. Valid range: 1-{len(self.game_state.party.characters)}")
                return None
        except ValueError:
            # Not a number, try to match by name
            pass

        # Try to match by name (case-insensitive)
        for character in living_members:
            if character.name.lower() == player_identifier.lower():
                return character

        # No match found
        print_error(f"No living player found with identifier: {player_identifier}")
        return None

    def display_inventory(self, filter_arg: Optional[str] = None) -> None:
        """
        Display party members' inventories with optional filtering.

        Args:
            filter_arg: Optional filter - can be:
                - "summary": Show cross-party consumables summary
                - Player number (e.g., "2"): Show specific player's inventory
                - Player name (e.g., "gandalf"): Show specific player's inventory
                - Category (e.g., "potions", "weapons", "armor"): Filter by item type
        """
        items_data = self.game_state.data_loader.load_items()
        from dnd_engine.systems.inventory import EquipmentSlot

        # Handle summary view
        if filter_arg == "summary":
            self._display_inventory_summary()
            return

        # Handle player-specific filter
        player_filter = None
        if filter_arg:
            # Try to parse as player number
            try:
                player_num = int(filter_arg)
                if 1 <= player_num <= len(self.game_state.party.characters):
                    player_filter = player_num - 1  # Convert to 0-based index
            except ValueError:
                # Try to match by name
                for idx, character in enumerate(self.game_state.party.characters):
                    if character.name.lower() == filter_arg.lower():
                        player_filter = idx
                        break

        # Handle category filter
        category_filter = None
        category_map = {
            "weapon": "weapons", "weapons": "weapons",
            "armor": "armor", "armour": "armor",
            "consumable": "consumables", "consumables": "consumables",
            "potion": "consumables", "potions": "consumables"
        }
        if filter_arg and filter_arg.lower() in category_map:
            category_filter = category_map[filter_arg.lower()]

        # Display inventory
        characters_to_show = []
        if player_filter is not None:
            characters_to_show = [(player_filter + 1, self.game_state.party.characters[player_filter])]
        else:
            characters_to_show = list(enumerate(self.game_state.party.characters, 1))

        for idx, character in characters_to_show:
            inventory = character.inventory

            # Build inventory data for rich table
            inventory_items = {}

            # Add equipped items
            weapon_id = inventory.get_equipped_item(EquipmentSlot.WEAPON)
            armor_id = inventory.get_equipped_item(EquipmentSlot.ARMOR)

            # Add items by category
            categories_to_show = [category_filter] if category_filter else ["weapons", "armor", "consumables"]
            for category in categories_to_show:
                category_items = inventory.get_items_by_category(category)
                if category_items:
                    if category not in inventory_items:
                        inventory_items[category] = []

                    for inv_item in category_items:
                        item_data = items_data[category].get(inv_item.item_id, {})
                        item_name = item_data.get("name", inv_item.item_id)
                        is_equipped = (inv_item.item_id == weapon_id or inv_item.item_id == armor_id)

                        inventory_items[category].append({
                            "name": item_name,
                            "quantity": inv_item.quantity,
                            "equipped": is_equipped
                        })

            # Display character title with player number
            alive_marker = "✓" if character.is_alive else "💀"
            print_title(f"[{idx}] {alive_marker} {character.name} - Gold: {inventory.gold} gp")

            # Create and display inventory table
            if inventory_items:
                table = create_inventory_table(inventory_items)
                console.print(table)
            else:
                if category_filter:
                    print_status_message(f"No {category_filter} in inventory", "info")
                else:
                    print_status_message("No items in inventory", "info")

    def _display_inventory_summary(self) -> None:
        """Display a summary of consumables across all party members."""
        items_data = self.game_state.data_loader.load_items()

        # Aggregate consumables across party
        consumable_totals = {}

        for character in self.game_state.party.characters:
            inventory = character.inventory
            consumables = inventory.get_items_by_category("consumables")

            for inv_item in consumables:
                if inv_item.item_id not in consumable_totals:
                    consumable_totals[inv_item.item_id] = 0
                consumable_totals[inv_item.item_id] += inv_item.quantity

        if consumable_totals:
            print_title("Party Consumables Summary")

            from rich.table import Table
            table = Table(title="CROSS-PARTY CONSUMABLES", style="green", show_header=True, header_style="bold magenta")
            table.add_column("Item", style="bold")
            table.add_column("Total Qty", justify="center")

            for item_id, total_qty in consumable_totals.items():
                item_data = items_data["consumables"].get(item_id, {})
                item_name = item_data.get("name", item_id)
                table.add_row(item_name, str(total_qty))

            console.print(table)
        else:
            print_status_message("No consumables in party inventory", "info")

    def handle_equip(self, item_id: str, player_identifier: Optional[str] = None) -> None:
        """
        Handle equipping an item for a specific party member.

        Args:
            item_id: The item to equip (ID or name)
            player_identifier: Optional player identifier (1-based index or character name)
        """
        character = self._get_target_player(player_identifier)
        if not character:
            if not self.game_state.party.get_living_members():
                print_error("No living party members to equip items!")
            return

        inventory = character.inventory
        items_data = self.game_state.data_loader.load_items()

        # Find the item in inventory (by ID or name)
        target_item = None
        target_category = None

        for category in ["weapons", "armor"]:
            category_items = inventory.get_items_by_category(category)
            for inv_item in category_items:
                item_data = items_data[category].get(inv_item.item_id, {})
                if inv_item.item_id == item_id or item_data.get("name", "").lower() == item_id.lower():
                    target_item = inv_item.item_id
                    target_category = category
                    break
            if target_item:
                break

        if not target_item:
            print_error(f"{character.name} doesn't have '{item_id}' in inventory.")
            return

        # Equip the item
        from dnd_engine.systems.inventory import EquipmentSlot

        if target_category == "weapons":
            slot = EquipmentSlot.WEAPON
        elif target_category == "armor":
            slot = EquipmentSlot.ARMOR
        else:
            print_error(f"Cannot equip {item_id}")
            return

        inventory.equip_item(target_item, slot)

        item_data = items_data[target_category][target_item]
        item_name = item_data.get("name", target_item)
        print_status_message(f"{character.name} equipped {item_name}", "success")

        # Emit event
        self.game_state.event_bus.emit(Event(
            type=EventType.ITEM_EQUIPPED,
            data={"item_id": target_item, "slot": slot.value}
        ))

    def handle_unequip(self, slot_name: str, player_identifier: Optional[str] = None) -> None:
        """
        Handle unequipping an item for a specific party member.

        Args:
            slot_name: The equipment slot to unequip (weapon or armor)
            player_identifier: Optional player identifier (1-based index or character name)
        """
        character = self._get_target_player(player_identifier)
        if not character:
            if not self.game_state.party.get_living_members():
                print_error("No living party members to unequip items!")
            return

        from dnd_engine.systems.inventory import EquipmentSlot

        slot = None
        if slot_name.lower() in ["weapon", "w"]:
            slot = EquipmentSlot.WEAPON
        elif slot_name.lower() in ["armor", "a"]:
            slot = EquipmentSlot.ARMOR
        else:
            print_error(f"Unknown equipment slot: {slot_name}. Use 'weapon' or 'armor'.")
            return

        inventory = character.inventory
        item_id = inventory.unequip_item(slot)

        if item_id:
            items_data = self.game_state.data_loader.load_items()
            category = "weapons" if slot == EquipmentSlot.WEAPON else "armor"
            item_data = items_data[category].get(item_id, {})
            item_name = item_data.get("name", item_id)
            print_status_message(f"{character.name} unequipped {item_name}", "success")

            # Emit event
            self.game_state.event_bus.emit(Event(
                type=EventType.ITEM_UNEQUIPPED,
                data={"item_id": item_id, "slot": slot.value}
            ))
        else:
            print_status_message(f"{character.name} has nothing equipped in {slot_name} slot.", "warning")

    def handle_use_item(self, item_id: str, player_identifier: Optional[str] = None) -> None:
        """
        Handle using a consumable item for a specific party member.

        Args:
            item_id: The item to use (ID or name)
            player_identifier: Optional player identifier (1-based index or character name)
        """
        character = self._get_target_player(player_identifier)
        if not character:
            if not self.game_state.party.get_living_members():
                print_error("No living party members to use items!")
            return

        inventory = character.inventory
        items_data = self.game_state.data_loader.load_items()

        # Find the item in consumables
        target_item = None
        consumables = inventory.get_items_by_category("consumables")

        for inv_item in consumables:
            item_data = items_data["consumables"].get(inv_item.item_id, {})
            if inv_item.item_id == item_id or item_data.get("name", "").lower() == item_id.lower():
                target_item = inv_item.item_id
                break

        if not target_item:
            print_error(f"{character.name} doesn't have a consumable '{item_id}' in inventory.")
            return

        # Get item data
        item_data = items_data["consumables"][target_item]
        item_name = item_data.get("name", target_item)

        # Process the effect
        effect = item_data.get("effect")
        if effect == "heal":
            amount_dice = item_data.get("amount", "1d4")
            roll = self.game_state.dice_roller.roll(amount_dice)
            healing = roll.total

            old_hp = character.current_hp
            character.heal(healing)
            actual_healing = character.current_hp - old_hp

            print_status_message(f"{character.name} uses {item_name}", "info")
            print_message(f"Healing: {roll} = {healing} HP")
            print_status_message(f"{character.name} recovers {actual_healing} HP (now at {character.current_hp}/{character.max_hp})", "success")
        else:
            print_status_message(f"{character.name} uses {item_name}", "info")

        # Remove the item from inventory
        inventory.remove_item(target_item, 1)

        # Emit event
        self.game_state.event_bus.emit(Event(
            type=EventType.ITEM_USED,
            data={"item_id": target_item, "effect": effect}
        ))

    def handle_save(self) -> None:
        """Handle manual save command."""
        # Check if save_manager is available
        if not hasattr(self.game_state, 'save_manager'):
            print_error("Save functionality not available")
            return

        print_section("Save Game", "Enter a name for your save")

        save_name = input("Save name: ").strip()

        if not save_name:
            print_status_message("Save cancelled", "warning")
            return

        try:
            save_path = self.game_state.save_manager.save_game(
                self.game_state,
                save_name,
                auto_save=False
            )
            print_status_message(f"Game saved successfully: {save_path.stem}", "success")
        except Exception as e:
            print_error(f"Failed to save game: {e}")

    def display_help_exploration(self) -> None:
        """Display help for exploration commands."""
        commands = [
            ("north/n, south/s, east/e, west/w", "Move in a direction (shorthand)"),
            ("move/go <direction>", "Move in a direction (e.g., 'go north')"),
            ("look or l", "Look around the current room"),
            ("search", "Search the room for items"),
            ("inventory / i [filter]", "Show inventory. Filter: summary, player name/number, or item type"),
            ("equip <item> [on <player>]", "Equip weapon/armor (e.g., 'equip sword on 2')"),
            ("unequip <slot> [on <player>]", "Unequip weapon/armor (e.g., 'unequip weapon on gandalf')"),
            ("use <item> [on <player>]", "Use consumable (e.g., 'use potion on 2')"),
            ("status", "Show your character status"),
            ("save", "Save your game"),
            ("help or ?", "Show this help message"),
            ("quit / exit", "Exit the game"),
        ]
        print_help_section("Exploration Commands", commands)

    def display_help_combat(self) -> None:
        """Display help for combat commands."""
        commands = [
            ("attack <enemy>", "Attack an enemy (e.g., 'attack goblin')"),
            ("status", "Show combat status"),
            ("help or ?", "Show this help message"),
        ]
        print_help_section("Combat Commands", commands)

    def run(self) -> None:
        """Run the main game loop."""
        self.display_banner()
        self.display_room()
        self.display_player_status()

        print_status_message("Type 'help' for available commands", "info")

        while self.running and not self.game_state.is_game_over():
            if self.game_state.in_combat:
                self.display_combat_status()
                current = self.game_state.initiative_tracker.get_current_combatant()

                # Check if it's a party member's turn
                is_party_turn = False
                for character in self.game_state.party.characters:
                    if current.creature == character:
                        is_party_turn = True
                        break

                if is_party_turn:
                    command = self.get_player_command()
                    self.process_combat_command(command)
                else:
                    self.process_enemy_turns()
            else:
                command = self.get_player_command()
                self.process_exploration_command(command)

        # Game over
        if self.game_state.is_game_over():
            print_title("GAME OVER", "Your party has been wiped out!")

    def _on_combat_start(self, event: Event) -> None:
        """Handle combat start event."""
        enemies = event.data.get("enemies", [])
        print_status_message(f"Combat begins! Enemies: {', '.join(enemies)}", "warning")

        # Log combat start with initiative order
        from dnd_engine.utils.logging_config import get_logging_config
        logging_config = get_logging_config()
        if logging_config and self.game_state.initiative_tracker:
            # Build initiative order string
            combatants = self.game_state.initiative_tracker.get_all_combatants()
            init_order = ", ".join(
                f"{entry.creature.name}({entry.initiative_total})"
                for entry in combatants
            )
            logging_config.log_combat_event(f"Combat started - Initiative order: {init_order}")

    def _on_combat_end(self, event: Event) -> None:
        """Handle combat end event."""
        total_xp = event.data.get("xp_gained", 0)
        xp_per_char = event.data.get("xp_per_character", 0)
        print_status_message(
            f"Victory! Party gained {total_xp} XP ({xp_per_char} XP per character)",
            "success"
        )

        # Log combat end
        from dnd_engine.utils.logging_config import get_logging_config
        logging_config = get_logging_config()
        if logging_config:
            logging_config.log_combat_event(
                f"Combat ended - Total XP: {total_xp}, XP per character: {xp_per_char}"
            )

        # Auto-save after combat
        self._auto_save("after_combat")

    def _on_damage_dealt(self, event: Event) -> None:
        """Handle damage dealt event (currently just passes through)."""
        pass

    def _on_item_acquired(self, event: Event) -> None:
        """Handle item acquired event."""
        # Events are already displayed during search, so we can pass
        pass

    def _on_gold_acquired(self, event: Event) -> None:
        """Handle gold acquired event."""
        # Events are already displayed during search, so we can pass
        pass

    def _on_enhancement_started(self, event: Event) -> None:
        """Handle LLM enhancement started event."""
        description_type = event.data.get("type", "unknown")

        # Track that narrative is pending but don't show loading state
        # (per UX guidelines, avoid loading indicators for quick responses)
        if description_type == "combat":
            self.narrative_pending = True

    def _on_description_enhanced(self, event: Event) -> None:
        """Handle LLM-enhanced description event."""
        description_type = event.data.get("type", "unknown")
        text = event.data.get("text", "")

        if text:
            # Display enhanced descriptions sequentially (no panels)
            from rich.markdown import Markdown

            if description_type == "combat" or description_type == "death" or description_type == "victory":
                # Display combat narrative sequentially after mechanics
                self.narrative_pending = False
                console.print(Markdown(text), style="gold1")
            elif description_type == "room":
                # Room descriptions
                console.print(Markdown(text), style="cyan")
            else:
                console.print(text)

    def _on_room_enter(self, event: Event) -> None:
        """Handle room enter event."""
        # Auto-save when entering a new room
        self._auto_save("room_change")

    def _auto_save(self, trigger: str) -> None:
        """
        Perform an auto-save.

        Args:
            trigger: What triggered the auto-save (for logging)
        """
        if not self.auto_save_enabled:
            return

        if not hasattr(self.game_state, 'save_manager'):
            return

        try:
            # Use "autosave" as the save name
            self.game_state.save_manager.save_game(
                self.game_state,
                "autosave",
                auto_save=True
            )
        except Exception:
            # Silently fail auto-save to avoid disrupting gameplay
            pass
