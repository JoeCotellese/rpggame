# ABOUTME: Command-line interface for the D&D 5E terminal game
# ABOUTME: Handles player input, displays game state, and manages the game loop

import sys
from typing import Optional, List, Dict, Any
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.combat import AttackResult
from dnd_engine.core.dice import format_dice_with_modifier
from dnd_engine.utils.events import EventBus, Event, EventType
from dnd_engine.systems.inventory import EquipmentSlot
from dnd_engine.systems.condition_manager import ConditionManager
from dnd_engine.ui.debug_console import DebugConsole
from rich.status import Status
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

    def __init__(self, game_state: GameState, campaign_manager, campaign_name: str, auto_save_enabled: bool = True, llm_enhancer=None):
        """
        Initialize the CLI.

        Args:
            game_state: The game state to interact with
            campaign_manager: CampaignManager for save operations
            campaign_name: Name of the current campaign
            auto_save_enabled: Whether to enable auto-save feature
            llm_enhancer: Optional LLM enhancer for narrative generation
        """
        self.game_state = game_state
        self.campaign_manager = campaign_manager
        self.campaign_name = campaign_name
        self.running = True
        self.auto_save_enabled = auto_save_enabled
        self.llm_enhancer = llm_enhancer

        # Condition manager for handling status effects
        self.condition_manager = ConditionManager(
            dice_roller=game_state.dice_roller,
            event_bus=game_state.event_bus
        )

        # Enemy numbering map: maps Creature instances to their combat numbers
        self.enemy_numbers: Dict[Any, int] = {}

        # Combat display management
        self.combat_status_shown = False

        # Combat history tracking for narrative context
        self.combat_history: List[str] = []

        # Debug console for testing and development
        self.debug_console = DebugConsole(game_state)

        # Subscribe to game events for display and auto-save
        self.game_state.event_bus.subscribe(EventType.COMBAT_START, self._on_combat_start)
        self.game_state.event_bus.subscribe(EventType.COMBAT_END, self._on_combat_end)
        self.game_state.event_bus.subscribe(EventType.COMBAT_FLED, self._on_combat_fled)
        self.game_state.event_bus.subscribe(EventType.ITEM_ACQUIRED, self._on_item_acquired)
        self.game_state.event_bus.subscribe(EventType.GOLD_ACQUIRED, self._on_gold_acquired)
        self.game_state.event_bus.subscribe(EventType.ROOM_ENTER, self._on_room_enter)
        self.game_state.event_bus.subscribe(EventType.LEVEL_UP, self._on_level_up)
        self.game_state.event_bus.subscribe(EventType.FEATURE_GRANTED, self._on_feature_granted)
        self.game_state.event_bus.subscribe(EventType.LONG_REST, self._on_long_rest)
        self.game_state.event_bus.subscribe(EventType.SKILL_CHECK, self._on_skill_check)

    def display_banner(self) -> None:
        """Display the game banner."""
        print_title("D&D 5E Terminal Game", "Welcome to your adventure!")

    def display_room(self) -> None:
        """Display the current room description with LLM enhancement."""
        room = self.game_state.get_current_room()

        # Extract room name and basic description
        room_name = room.get("name", "Unknown Room")
        basic_desc = room.get("description", self.game_state.get_room_description())
        exits = room.get("exits", [])

        # Check for monsters in the room
        enemy_ids = room.get("enemies", [])
        monster_names = []
        if enemy_ids:
            # Load monster data to get display names
            monsters_data = self.game_state.data_loader.load_monsters()
            for enemy_id in enemy_ids:
                if enemy_id in monsters_data:
                    monster_names.append(monsters_data[enemy_id]["name"])

        # Detect if combat is about to start
        # Combat starts if there are enemies and we're not already in combat
        combat_starting = bool(enemy_ids) and not self.game_state.in_combat

        # Try to get enhanced description from LLM
        enhanced_desc = None
        if self.llm_enhancer:
            # Load full monster data for creature-aware prompts
            monsters_data = self.game_state.data_loader.load_monsters()
            party_size = len(self.game_state.party.characters)

            room_data = {
                "id": room.get("id", room_name.lower().replace(" ", "_")),
                "name": room_name,
                "description": basic_desc,
                "monsters": monster_names,  # Include monster info for LLM
                "combat_starting": combat_starting,  # Flag for combat initiation narrative
                "monsters_data": monsters_data,  # Full monster definitions for creature-aware prompts
                "party_size": party_size  # Party size for combat context
            }
            with console.status("", spinner="dots"):
                enhanced_desc = self.llm_enhancer.get_room_description_sync(room_data, timeout=3.0)

        # Use enhanced description if available, otherwise use basic
        room_text = enhanced_desc if enhanced_desc else basic_desc

        print_room_description(room_name, room_text, exits)

    def display_player_status(self) -> None:
        """Display status for all party members."""
        # Convert party data to table format
        party_data = []
        for char in self.game_state.party.characters:
            party_data.append({
                "name": char.name,
                "class": char.character_class.value.capitalize(),
                "level": char.level,
                "hp": char.current_hp,
                "max_hp": char.max_hp,
                "ac": char.ac,
                "xp": char.xp
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

            # Get numbered name for enemies
            display_name = entry.creature.name
            if not is_player:
                enemy_number = self._get_enemy_number(entry.creature)
                if enemy_number is not None:
                    display_name = f"{entry.creature.name} {enemy_number}"

            combatant_data = {
                "name": display_name,
                "initiative": entry.initiative_total,
                "hp": entry.creature.current_hp,
                "max_hp": entry.creature.max_hp,
                "is_player": is_player,
                "current_turn": entry == current_combatant
            }

            # Add death save data for characters
            if hasattr(entry.creature, 'death_save_successes'):
                combatant_data["death_saves"] = {
                    "successes": entry.creature.death_save_successes,
                    "failures": entry.creature.death_save_failures,
                    "stabilized": entry.creature.stabilized
                }

            combatants.append(combatant_data)

        table = create_combat_table(combatants)
        console.print(table)

    def display_turn_status(self, is_player_turn: bool, current_creature) -> None:
        """
        Display compact turn status without full combat table.

        Args:
            is_player_turn: Whether it's a player's turn
            current_creature: The current creature whose turn it is
        """
        from rich.panel import Panel

        if is_player_turn:
            # Show player turn with current HP and enemy status
            char = current_creature
            hp_pct = char.current_hp / char.max_hp if char.max_hp > 0 else 0
            hp_color = "green" if hp_pct > 0.5 else "yellow" if hp_pct > 0.25 else "red"

            # Build enemy summary
            living_enemies = [e for e in self.game_state.active_enemies if e.is_alive]
            enemy_summary = []
            for enemy in living_enemies:
                e_hp_pct = enemy.current_hp / enemy.max_hp if enemy.max_hp > 0 else 0
                if e_hp_pct <= 0.25:
                    e_color = "red"
                elif e_hp_pct <= 0.5:
                    e_color = "yellow"
                else:
                    e_color = "white"
                enemy_summary.append(f"[{e_color}]{enemy.name} ({enemy.current_hp}/{enemy.max_hp})[/{e_color}]")

            enemies_str = ", ".join(enemy_summary) if enemy_summary else "None"

            console.print(Panel(
                f"[bold]{char.name}'s turn![/bold] | HP: [{hp_color}]{char.current_hp}/{char.max_hp}[/{hp_color}] | Enemies: {enemies_str}",
                border_style="yellow",
                padding=(0, 1)
            ))
        # No display for enemy turns - the action will print itself

    def _build_battlefield_state(self) -> Dict[str, Any]:
        """
        Build current battlefield state for LLM context.

        Returns:
            Dict with party_hp and enemy_hp lists
        """
        party_hp = [
            (char.name, char.current_hp, char.max_hp)
            for char in self.game_state.party.characters
        ]

        enemy_hp = []
        for enemy in self.game_state.active_enemies:
            if enemy.is_alive:
                enemy_num = self._get_enemy_number(enemy)
                display_name = f"{enemy.name} {enemy_num}" if enemy_num else enemy.name
                enemy_hp.append((display_name, enemy.current_hp, enemy.max_hp))

        return {
            "party_hp": party_hp,
            "enemy_hp": enemy_hp
        }

    def _record_combat_action(self, result: Any) -> None:
        """
        Record a combat action in history for narrative context.

        Args:
            result: AttackResult from combat engine
        """
        if result.hit:
            if result.critical_hit:
                action = f"{result.attacker_name} CRITICALLY hit {result.defender_name} for {result.damage} damage"
            else:
                action = f"{result.attacker_name} hit {result.defender_name} for {result.damage} damage"
        else:
            action = f"{result.attacker_name} missed {result.defender_name}"

        self.combat_history.append(action)

        # Keep only last 12 actions to prevent prompt bloat
        if len(self.combat_history) > 12:
            self.combat_history = self.combat_history[-12:]

    def display_narrative_panel(self, text: str) -> None:
        """
        Display narrative text in a styled panel.

        Args:
            text: The narrative text to display
        """
        from rich.markdown import Markdown
        from rich.panel import Panel

        console.print()
        console.print(Panel(
            Markdown(text),
            title="✨",
            border_style="gold1",
            padding=(0, 1)
        ))

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
        # Check for debug commands first (start with /)
        if self.debug_console.is_debug_command(command):
            self.debug_console.execute(command)
            return

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
            "west": "west", "w": "west",
            "up": "up", "u": "up",
            "down": "down", "d": "down"
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

        if command == "examine" or command.startswith("examine ") or command in ["x", "ex"] or command.startswith("x ") or command.startswith("ex "):
            parts = command.split()[1:]
            if not parts:
                self.handle_examine_menu()
            else:
                object_id = "_".join(parts)
                self.handle_examine(object_id)
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
                # Progressive disclosure: prompt for item, then target
                item_selection = self._prompt_consumable_selection()
                if not item_selection:
                    return  # User cancelled

                item_id, item_data = item_selection
                item_name = item_data.get("name", item_id)

                # Prompt for target
                target_character = self._prompt_target_selection(item_name)
                if not isinstance(target_character, Character):
                    return  # User cancelled or invalid selection

                # Find which character has this item
                owner = None
                for char in self.game_state.party.characters:
                    if char.is_alive:
                        consumables = char.inventory.get_items_by_category("consumables")
                        for inv_item in consumables:
                            if inv_item.item_id == item_id:
                                owner = char
                                break
                    if owner:
                        break

                if not owner:
                    print_error(f"Could not find {item_name} in any party member's inventory!")
                    return

                # Execute the use on the selected target
                self.handle_use_item_direct(item_id, target_character, owner)
                return

            # Parse with support for "on" keyword (old syntax still works)
            item_id, player_id = self._parse_command_with_target(parts)
            self.handle_use_item(item_id, player_id)
            return

        if command in ["save"]:
            self.handle_save()
            return

        if command in ["qs", "quicksave"]:
            self.handle_quick_save()
            return

        # Note: 'reset' command moved to debug console as '/reset'
        # Use '/reset' in debug mode (DEBUG_MODE=true) for reset functionality

        if command in ["rest"]:
            self.handle_rest()
            return

        if command in ["cast"]:
            self.handle_cast_spell_exploration()
            return

        if command in ["take", "get", "pickup"]:
            # Prompt for item selection with arrow keys
            item_to_take = self._prompt_item_to_take()
            if item_to_take is None or item_to_take == "Cancel":
                return  # User cancelled

            # Determine item name based on type
            if item_to_take["type"] in ["gold", "currency"]:
                item_name = "currency"
            else:
                item_name = item_to_take.get("id", "")

            self.handle_take(item_name)
            return

        if command.startswith("take ") or command.startswith("get ") or command.startswith("pickup "):
            # Extract item name from command
            parts = command.split(maxsplit=1)
            if len(parts) > 1:
                item_name = parts[1]
                self.handle_take(item_name)
            else:
                print_error("Specify an item to take. Example: 'take dagger'")
            return

        print_status_message("Unknown command. Type 'help' for available commands.", "warning")

    def process_combat_command(self, command: str) -> None:
        """
        Process a command during combat.

        Args:
            command: The player's command
        """
        # Check for debug commands first (start with /)
        if self.debug_console.is_debug_command(command):
            self.debug_console.execute(command)
            return

        if command in ["help", "h", "?"]:
            self.display_help_combat()
            return

        if command in ["quit", "exit"]:
            print_status_message("Exiting game...", "info")
            self.running = False
            return

        if command.startswith("attack "):
            target_name = " ".join(command.split()[1:])
            self.handle_attack(target_name)
            return

        if command == "attack":
            # Prompt for enemy selection with arrow keys
            target = self._prompt_enemy_selection()
            if target is None or target == "Cancel":
                return  # User cancelled

            # Find the target name with number
            enemy_num = self._get_enemy_number(target)
            target_name = f"{target.name} {enemy_num}" if enemy_num else target.name

            self.handle_attack(target_name)
            return

        if command.startswith("cast "):
            spell_name = " ".join(command.split()[1:])
            self.handle_cast_spell(spell_name)
            return

        if command == "cast":
            # Prompt for spell selection
            self.handle_cast_spell("")
            return

        if command in ["flee", "run", "escape", "retreat"]:
            self.handle_flee()
            return

        if command in ["status", "stats"]:
            self.display_combat_status()
            return

        if command.startswith("stabilize ") or command == "stabilize":
            parts = command.split()[1:] if " " in command else []
            if not parts:
                # Show list of unconscious allies
                unconscious = [c for c in self.game_state.party.characters if c.is_unconscious]
                if unconscious:
                    names = ", ".join([c.name for c in unconscious])
                    print_error(f"Specify an ally to stabilize. Unconscious: {names}")
                else:
                    print_error("No unconscious allies to stabilize.")
            else:
                target_name = " ".join(parts)
                self.handle_stabilize(target_name)
            return

        if command == "use" or command.startswith("use "):
            parts = command.split()[1:]
            if not parts:
                # Progressive disclosure: prompt for item (combat mode - self only for now)
                # Get current combatant
                if not self.game_state.in_combat or not self.game_state.initiative_tracker:
                    print_error("Not in combat!")
                    return

                current = self.game_state.initiative_tracker.get_current_combatant()
                if not current:
                    print_error("No current combatant!")
                    return

                # Check if current combatant is a party member
                if current.creature not in self.game_state.party.characters:
                    print_error("It's not a party member's turn!")
                    return

                character = current.creature

                # Prompt for item selection (showing action costs)
                item_selection = self._prompt_consumable_selection(character=character, show_action_cost=True)
                if not item_selection:
                    return  # User cancelled

                item_id, item_data = item_selection
                item_name = item_data.get("name", item_id)

                # Check if item can target others
                target_type = item_data.get("target_type", "self")
                if target_type == "any":
                    # Prompt for target selection (allies within range)
                    target = self._prompt_combat_ally_selection(item_name, item_data, character)
                    if not isinstance(target, Character):
                        return  # User cancelled or invalid selection
                    # Execute the use with selected target
                    self.handle_use_item_combat_with_target(item_id, item_data, character, target)
                elif target_type == "enemy":
                    # Prompt for enemy target selection
                    target = self._prompt_enemy_selection()
                    if target is None:
                        return  # User cancelled
                    # Execute attack with item on enemy
                    self.handle_use_item_combat_attack(item_id, item_data, character, target)
                else:
                    # Self-target only
                    target = character
                    # Execute the use with selected target
                    self.handle_use_item_combat_with_target(item_id, item_data, character, target)
                return

            # Use item during combat (old syntax still works)
            item_id = parts[0]
            self.handle_use_item_combat(item_id)
            return

        # Provide helpful suggestions for unknown commands
        print_status_message("Unknown combat command.", "warning")
        living_enemies = []
        for enemy in self.game_state.active_enemies:
            if enemy.is_alive:
                enemy_num = self._get_enemy_number(enemy)
                display_name = f"{enemy.name} {enemy_num}" if enemy_num else enemy.name
                living_enemies.append(display_name)
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

        # Check if exit is locked before attempting move
        if self.game_state.is_exit_locked(direction):
            self.handle_unlock(direction)
            return

        # Move without checking for enemies yet
        success = self.game_state.move(direction, check_for_enemies=False)
        if success:
            print_status_message(f"You move {direction}", "info")
            # Display room description FIRST
            self.display_room()
            # THEN check for enemies and potentially start combat
            self.game_state._check_for_enemies()
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

    def handle_unlock(self, direction: str) -> None:
        """Handle unlocking a locked door."""
        # Get unlock methods
        unlock_methods = self.game_state.get_unlock_methods(direction)

        if not unlock_methods:
            print_error(f"The door to the {direction} is locked, but you cannot find a way to open it.")
            return

        # Check for item-based auto-unlock first
        for idx, method in enumerate(unlock_methods):
            if "requires_item" in method:
                item_id = method["requires_item"]
                # Check if party has the item
                has_item = any(char.inventory.has_item(item_id) for char in self.game_state.party.characters)
                if has_item:
                    print_status_message(f"The door to the {direction} is locked, but you have {item_id}!", "success")
                    # Auto-unlock with item
                    result = self.game_state.attempt_unlock(direction, idx, self.game_state.party.characters[0])
                    if result["success"]:
                        print_status_message(f"You unlock the door with the {item_id}!", "success")
                        # Now move through the unlocked door
                        self.handle_move(direction)
                    return

        # Display locked door message
        print_status_message(f"The door to the {direction} is locked.", "warning")
        console.print()

        # Build unlock methods content
        methods_content = []
        for idx, method in enumerate(unlock_methods):
            desc = method.get("description", "unknown method")
            if "skill" in method:
                skill = method["skill"]
                dc = method["dc"]
                tool_req = ""
                if "tool_proficiency" in method:
                    tool_req = f" + {method['tool_proficiency'].replace('_', ' ').title()}"
                methods_content.append(f"  {idx + 1}. {desc.capitalize()} ({skill}{tool_req} DC {dc})")
            elif "requires_item" in method:
                methods_content.append(f"  {idx + 1}. {desc.capitalize()} (requires {method['requires_item']})")

        # Display unlock methods in box
        print_section("Available unlock methods:", "\n".join(methods_content))
        console.print()

        # Prompt for method selection
        try:
            method_input = input("Choose a method (number) or 'cancel': ").strip().lower()
            if method_input == "cancel":
                return

            method_index = int(method_input) - 1
            if method_index < 0 or method_index >= len(unlock_methods):
                print_error("Invalid method number.")
                return

        except ValueError:
            print_error("Invalid input. Enter a number or 'cancel'.")
            return

        method = unlock_methods[method_index]

        # For skill-based methods, prompt for character selection
        if "skill" in method:
            character = self._prompt_character_for_unlock(method)
            if not character:
                return  # User cancelled

            # Attempt unlock
            result = self.game_state.attempt_unlock(direction, method_index, character)

            # Display result
            if result["success"]:
                check_result = result.get("skill_check_result", {})
                roll = check_result.get("roll", 0)
                modifier = check_result.get("modifier", 0)
                total = check_result.get("total", 0)
                dc = method.get("dc", 0)

                print_mechanics_panel(
                    f"{character.name} attempts to {method['description']}\n"
                    f"d20: {roll} + {modifier} = {total} vs DC {dc}"
                )
                print_status_message(f"Success! {character.name} unlocks the door.", "success")
                console.print()

                # Now move through the unlocked door
                self.handle_move(direction)
            else:
                check_result = result.get("skill_check_result", {})
                if check_result:
                    roll = check_result.get("roll", 0)
                    modifier = check_result.get("modifier", 0)
                    total = check_result.get("total", 0)
                    dc = method.get("dc", 0)

                    print_mechanics_panel(
                        f"{character.name} attempts to {method['description']}\n"
                        f"d20: {roll} + {modifier} = {total} vs DC {dc}"
                    )
                print_error(f"Failed! The door remains locked. You can try again.")

    def _prompt_character_for_unlock(self, method: dict) -> Optional[Character]:
        """
        Prompt player to select which character attempts the unlock.

        Args:
            method: The unlock method being used

        Returns:
            Selected Character or None if cancelled
        """
        skill = method.get("skill", "")
        dc = method.get("dc", 0)
        tool_proficiency = method.get("tool_proficiency")

        # Load skills data
        skills_data = self.game_state.data_loader.load_skills()

        # Build header
        header = f"Choose a character to {method['description']} ({skill}"
        if tool_proficiency:
            header += f" + {tool_proficiency.replace('_', ' ').title()}"
        header += f" DC {dc}):"

        # Build character list content
        living_chars = [c for c in self.game_state.party.characters if c.is_alive]
        char_list_content = []
        for idx, char in enumerate(living_chars, 1):
            # Get skill modifier
            skill_mod = char.get_skill_modifier(skill, skills_data)

            # Check tool proficiency
            tool_prof_str = ""
            if tool_proficiency:
                has_prof = hasattr(char, 'tool_proficiencies') and tool_proficiency in char.tool_proficiencies
                if has_prof:
                    # Tool proficiency adds proficiency bonus
                    tool_bonus = char.proficiency_bonus if hasattr(char, 'proficiency_bonus') else 2
                    tool_prof_str = f", {tool_proficiency.replace('_', ' ').title()} +{tool_bonus}"
                else:
                    tool_prof_str = f" (no {tool_proficiency.replace('_', ' ').title()})"

            char_list_content.append(f"  {idx}. {char.name} - {skill.upper()} +{skill_mod}{tool_prof_str}")

        # Display in box
        console.print()
        print_section(header, "\n".join(char_list_content))
        console.print()

        # Prompt for selection
        try:
            char_input = input("Enter number or 'cancel': ").strip().lower()
            if char_input == "cancel":
                return None

            char_index = int(char_input) - 1
            if char_index < 0 or char_index >= len(living_chars):
                print_error("Invalid character number.")
                return None

            return living_chars[char_index]

        except ValueError:
            print_error("Invalid input. Enter a number or 'cancel'.")
            return None

    def handle_search(self) -> None:
        """Handle search command with optional skill checks."""
        room = self.game_state.get_current_room()

        # Check if room has search_checks
        has_skill_check = bool(room.get("search_checks"))

        if has_skill_check:
            # Skill check required - select character
            character = self._prompt_simple_character_selection("Who will search the room?")
            if not character:
                return

            result = self.game_state.search_room(character)

            if result.get("already_searched"):
                if result["items"]:
                    print_status_message("You already searched this room. Items found:", "info")
                    self._display_items_list(result["items"])
                else:
                    print_status_message("You already searched this room and found nothing.", "info")
                return

            # Success/failure and detailed results are displayed by event handler
            if result["success"]:
                if result["items"]:
                    print_status_message("\nItems found:", "success")
                    self._display_items_list(result["items"])
                else:
                    print_status_message("The search was successful but nothing was found.", "info")
            else:
                # Failure message already shown by event handler
                pass
        else:
            # No skill check - automatic success (backward compatibility)
            result = self.game_state.search_room()

            if result.get("already_searched"):
                if result["items"]:
                    print_status_message("You already searched this room. Items found:", "info")
                    self._display_items_list(result["items"])
                else:
                    print_status_message("You already searched this room and found nothing.", "info")
                return

            if result["success"] and result["items"]:
                print_status_message("You search the room and find:", "success")
                self._display_items_list(result["items"])
            else:
                print_status_message("You find nothing of interest.", "info")

    def _display_items_list(self, items: list) -> None:
        """Helper to display a list of items."""
        for item in items:
            if item["type"] == "gold":
                print_status_message(f"  • {item['amount']} gold pieces", "info")
            elif item["type"] == "currency":
                currency_parts = []
                if item.get("gold", 0) > 0:
                    currency_parts.append(f"{item['gold']} gold")
                if item.get("silver", 0) > 0:
                    currency_parts.append(f"{item['silver']} silver")
                if item.get("copper", 0) > 0:
                    currency_parts.append(f"{item['copper']} copper")
                print_status_message(f"  • {', '.join(currency_parts)}", "info")
            else:
                print_status_message(f"  • {item.get('id', 'an item')}", "info")
        print_status_message("\nUse 'take <item>' to pick up items", "info")

    def handle_examine_menu(self) -> None:
        """Show what can be examined in the current room."""
        objects = self.game_state.get_examinable_objects()
        exits = self.game_state.get_examinable_exits()

        if not objects and not exits:
            print_status_message("There's nothing to examine here.", "info")
            return

        print_status_message("You can examine:", "info")

        if objects:
            print_status_message("\n  Objects:", "header")
            for obj in objects:
                print_status_message(f"    • {obj['name']} - use: examine {obj['id']}", "info")

        if exits:
            print_status_message("\n  Exits:", "header")
            for direction in exits:
                print_status_message(f"    • {direction} door - use: examine {direction}", "info")

    def handle_examine(self, target: str) -> None:
        """
        Examine an object or exit.

        Args:
            target: The object ID or direction to examine
        """
        # Check if it's an examinable exit
        exits = self.game_state.get_examinable_exits()
        if target in exits:
            self._examine_exit(target)
            return

        # Check if it's an examinable object
        objects = self.game_state.get_examinable_objects()
        obj = next((o for o in objects if o["id"] == target), None)

        if obj:
            self._examine_object(target, obj)
            return

        # Not found
        print_error(f"Cannot examine '{target}'. Type 'examine' to see what you can examine.")

    def _examine_object(self, object_id: str, obj_data: dict) -> None:
        """
        Examine an object with skill check.

        Args:
            object_id: ID of the object
            obj_data: Object data dict
        """
        # Select character
        character = self._prompt_simple_character_selection(f"Who will examine the {obj_data['name']}?")
        if not character:
            return

        # Perform examination
        result = self.game_state.examine_object(object_id, character)

        if result.get("already_checked"):
            print_status_message(f"You already examined the {result['object_name']}.", "info")

        # Results are displayed by the event handler

    def _examine_exit(self, direction: str) -> None:
        """
        Examine an exit (listen at door, etc.).

        Args:
            direction: Direction of the exit
        """
        # Select character
        character = self._prompt_simple_character_selection(f"Who will examine the {direction} exit?")
        if not character:
            return

        # Perform examination
        result = self.game_state.examine_exit(direction, character)

        # Handle locked door case (no skill check involved)
        if result.get("is_locked"):
            print_status_message(f"\n🔒 {result.get('description', 'The door is locked.')}", "info")

            unlock_methods = result.get("unlock_methods", [])
            if unlock_methods:
                print_status_message("\n   Available unlock methods:", "info")
                for method in unlock_methods:
                    method_desc = method.get("description", "unknown method")
                    print_status_message(f"      • {method_desc.capitalize()}", "info")
            return

        # Results are displayed by the event handler for skill-based examinations

    def _prompt_simple_character_selection(self, prompt: str = "Select character:") -> Optional[Character]:
        """
        Prompt user to select a character from living party members.

        Args:
            prompt: The prompt message to display

        Returns:
            Selected Character or None if cancelled
        """
        living_members = self.game_state.party.get_living_members()

        if not living_members:
            print_error("No living party members!")
            return None

        if len(living_members) == 1:
            return living_members[0]

        print_status_message(f"\n{prompt}", "info")
        for i, char in enumerate(living_members, 1):
            print_status_message(f"  {i}. {char.name}", "info")

        choice = input("\n> ").strip()

        if choice.lower() in ["cancel", "c"]:
            return None

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(living_members):
                return living_members[idx]
        except ValueError:
            # Try to match by name
            for char in living_members:
                if char.name.lower() == choice.lower():
                    return char

        print_error("Invalid selection.")
        return None

    def handle_take(self, item_name: str) -> None:
        """
        Handle taking an item from the current room.

        Args:
            item_name: Name or ID of the item to take
        """
        # Get available items in the room
        available_items = self.game_state.get_available_items_in_room()

        if not available_items:
            room = self.game_state.get_current_room()
            if room.get("searchable") and not room.get("searched"):
                print_error("You haven't searched this room yet. Use 'search' first.")
            else:
                print_error("There are no items to take here.")
            return

        # Normalize item name for matching
        item_name_lower = item_name.lower().replace("_", " ")

        # Find matching item
        item_to_take = None
        for item in available_items:
            if item["type"] == "gold" and item_name_lower in ["gold", "gold pieces"]:
                item_to_take = item
                break
            elif item["type"] == "currency" and item_name_lower in ["gold", "silver", "copper", "currency", "coins"]:
                item_to_take = item
                break
            elif item["type"] == "item":
                item_id = item.get("id", "")
                # Match by ID or display name
                if item_id.lower() == item_name_lower or item_id.lower().replace("_", " ") == item_name_lower:
                    item_to_take = item
                    break

        if not item_to_take:
            print_error(f"'{item_name}' not found in this room.")
            print_status_message("Available items:", "info")
            for item in available_items:
                if item["type"] == "gold":
                    print_status_message(f"  - gold ({item['amount']} pieces)", "info")
                elif item["type"] == "currency":
                    currency_parts = []
                    if item.get("gold", 0) > 0:
                        currency_parts.append(f"{item['gold']} gold")
                    if item.get("silver", 0) > 0:
                        currency_parts.append(f"{item['silver']} silver")
                    if item.get("copper", 0) > 0:
                        currency_parts.append(f"{item['copper']} copper")
                    print_status_message(f"  - currency ({', '.join(currency_parts)})", "info")
                else:
                    print_status_message(f"  - {item.get('id', 'unknown')}", "info")
            return

        # Handle currency/gold specially - auto-add to party
        if item_to_take["type"] in ["gold", "currency"]:
            # Currency goes to all party members automatically
            success = self.game_state.take_item(item_name, self.game_state.party.characters[0])
            if success:
                if item_to_take["type"] == "gold":
                    amount = item_to_take["amount"]
                    split = amount // len(self.game_state.party.characters)
                    print_status_message(f"You pick up {amount} gold pieces ({split} each).", "success")
                else:
                    currency_parts = []
                    if item_to_take.get("gold", 0) > 0:
                        currency_parts.append(f"{item_to_take['gold']} gold")
                    if item_to_take.get("silver", 0) > 0:
                        currency_parts.append(f"{item_to_take['silver']} silver")
                    if item_to_take.get("copper", 0) > 0:
                        currency_parts.append(f"{item_to_take['copper']} copper")
                    print_status_message(f"You pick up {', '.join(currency_parts)} and split it among the party.", "success")
            else:
                print_error("Failed to pick up the currency.")
            return

        # For regular items, select character if multi-character party
        living_members = self.game_state.party.get_living_members()
        if not living_members:
            print_error("No living party members to take the item!")
            return

        selected_character = None
        if len(living_members) == 1:
            # Single character party - auto-assign
            selected_character = living_members[0]
        else:
            # Multi-character party - prompt for selection
            import questionary

            # Build choices for questionary
            choices = []
            item_id = item_to_take.get("id", item_name)

            for character in living_members:
                choice_text = f"{character.name} ({character.character_class.value.title()})"
                choices.append(questionary.Choice(title=choice_text, value=character))

            # Add cancel option
            choices.append(questionary.Choice(title="Cancel", value=None))

            # Get user selection
            try:
                result = questionary.select(
                    f"Who should receive the {item_id}?",
                    choices=choices,
                    use_arrow_keys=True
                ).ask()

                if result is None or result == "Cancel":
                    print_status_message("Cancelled.", "warning")
                    return
                selected_character = result
            except (EOFError, KeyboardInterrupt):
                print_status_message("Cancelled.", "warning")
                return

        # Take the item
        item_id = item_to_take.get("id", item_name)
        success = self.game_state.take_item(item_id, selected_character)

        if success:
            print_status_message(f"{selected_character.name} picks up the {item_id}.", "success")
        else:
            print_error(f"Failed to pick up {item_id}.")

    def handle_attack(self, target_name: str) -> None:
        """Handle attack command during combat."""
        if not self.game_state.in_combat:
            print_error("You're not in_combat!")
            return

        # Check if it's a party member's turn
        current = self.game_state.initiative_tracker.get_current_combatant()
        attacker = None
        for character in self.game_state.party.characters:
            if current.creature == character and character.is_alive:
                attacker = character
                break

        if not attacker:
            # Show which party member's turn it is or if it's an enemy turn
            enemy_turn = False
            for enemy in self.game_state.active_enemies:
                if current.creature == enemy:
                    enemy_num = self._get_enemy_number(enemy)
                    display_name = f"{enemy.name} {enemy_num}" if enemy_num else enemy.name
                    print_status_message(f"It's {display_name}'s turn, not a party member's!", "warning")
                    enemy_turn = True
                    break
            if not enemy_turn:
                print_status_message(f"It's not a valid combatant's turn!", "warning")
            return

        # Check action economy
        from dnd_engine.systems.action_economy import ActionType
        turn_state = self.game_state.initiative_tracker.get_current_turn_state()
        if not turn_state:
            print_error("Unable to get current turn state!")
            return

        if not turn_state.is_action_available(ActionType.ACTION):
            print_error("You don't have an Action available this turn!")
            print_status_message(f"Available: {turn_state}", "info")
            return

        # Find target using new numbering system
        target = self._find_enemy_by_target(target_name)

        if not target:
            print_error(f"No such enemy: {target_name}")
            # Show numbered enemy list
            living_enemies = []
            for enemy in self.game_state.active_enemies:
                if enemy.is_alive:
                    enemy_num = self._get_enemy_number(enemy)
                    display_name = f"{enemy.name} {enemy_num}" if enemy_num else enemy.name
                    living_enemies.append(display_name)
            if living_enemies:
                print_status_message(f"Available targets: {', '.join(living_enemies)}", "info")
            return

        # Consume the action
        if not turn_state.consume_action(ActionType.ACTION):
            print_error("Failed to consume action!")
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

        # Get equipped weapon and its properties
        equipped_weapon = attacker.inventory.get_equipped_item(EquipmentSlot.WEAPON)

        # Load weapon data
        items_data = self.game_state.data_loader.load_items()

        # Get attack bonus and damage bonus based on weapon
        if equipped_weapon:
            attack_bonus = attacker.get_attack_bonus(equipped_weapon, items_data)
            damage_bonus = attacker.get_damage_bonus(equipped_weapon, items_data)
            # Get weapon damage dice from item data
            weapon_data = items_data.get("weapons", {}).get(equipped_weapon, {})
            damage_dice = weapon_data.get("damage", "1d8")
            damage_dice = format_dice_with_modifier(damage_dice, damage_bonus)
        else:
            # Fallback to melee attack if no weapon equipped
            attack_bonus = attacker.melee_attack_bonus
            damage_bonus = attacker.melee_damage_bonus
            damage_dice = format_dice_with_modifier("1d8", damage_bonus)

        # Perform attack (resolve mechanics)
        result = self.game_state.combat_engine.resolve_attack(
            attacker=attacker,
            defender=target,
            attack_bonus=attack_bonus,
            damage_dice=damage_dice,
            apply_damage=True
        )

        # NEW FLOW: Narrative → Mechanics → Death Narrative → Death Message

        # 1. Get and display attack narrative FIRST (if hit)
        if self.llm_enhancer and result.hit:
            room = self.game_state.get_current_room()
            location = room.get("name", "")

            # Get weapon name and damage type
            weapon_name = "weapon"
            damage_type = ""
            if equipped_weapon and weapon_data:
                weapon_name = weapon_data.get("name", equipped_weapon)
                damage_type = weapon_data.get("damage_type", "")

            # Get attacker race
            races_data = self.game_state.data_loader.load_races()
            attacker_race_data = races_data.get(attacker.race, {})
            attacker_race = attacker_race_data.get("name", "")

            # Get defender armor type (for enemies, check monster data)
            defender_armor = ""
            if isinstance(target, Character):
                # Target is player - get equipped armor
                equipped_armor_id = target.inventory.get_equipped_item(EquipmentSlot.ARMOR)
                if equipped_armor_id:
                    armor_data = items_data.get("armor", {}).get(equipped_armor_id, {})
                    armor_type = armor_data.get("armor_type", "")
                    if armor_type:
                        defender_armor = f"{armor_type} armor"
            else:
                # Target is enemy - try to get from monster data or AC source
                monsters = self.game_state.data_loader.load_monsters()
                for mid, mdata in monsters.items():
                    if mdata["name"] == target.name:
                        ac_source = mdata.get("ac_source", "")
                        if ac_source:
                            defender_armor = ac_source
                        break

            with console.status("", spinner="dots"):
                narrative = self.llm_enhancer.get_combat_narrative_sync(
                    action_data={
                        "attacker": result.attacker_name,
                        "defender": result.defender_name,
                        "damage": result.damage,
                        "critical": result.critical_hit,
                        "hit": result.hit,
                        "location": location,
                        "weapon": weapon_name,
                        "damage_type": damage_type,
                        "attacker_race": attacker_race,
                        "defender_armor": defender_armor,
                        "combat_history": self.combat_history,
                        "battlefield_state": self._build_battlefield_state()
                    },
                    timeout=3.0
                )
            if narrative:
                self.display_narrative_panel(narrative)

        # Record this action in combat history
        self._record_combat_action(result)

        # 2. Display mechanics after narrative
        console.print(f"[cyan]⚔️  {str(result)}[/cyan]")

        # 3. If target died, show death narrative then confirmation
        if not target.is_alive:
            if self.llm_enhancer:
                with console.status("", spinner="dots"):
                    death_narrative = self.llm_enhancer.get_death_narrative_sync(
                        character_data={
                            "name": target.name,
                            "is_player": isinstance(target, Character)
                        },
                        timeout=3.0
                    )
                if death_narrative:
                    self.display_narrative_panel(death_narrative)

            # 4. Display defeated message after death narrative
            print_status_message(f"{target.name} is defeated!", "success")

        # End player turn
        self.game_state.initiative_tracker.next_turn()

        # Check if combat is over
        self.game_state._check_combat_end()

        if self.game_state.in_combat:
            # Process enemy turns
            self.process_enemy_turns()

    def handle_cast_spell(self, spell_name: str) -> None:
        """Handle cast spell command during combat."""
        if not self.game_state.in_combat:
            print_error("You're not in combat!")
            return

        # Check if it's a party member's turn
        current = self.game_state.initiative_tracker.get_current_combatant()
        caster = None
        for character in self.game_state.party.characters:
            if current.creature == character and character.is_alive:
                caster = character
                break

        if not caster:
            # Show whose turn it is
            enemy_turn = False
            for enemy in self.game_state.active_enemies:
                if current.creature == enemy:
                    enemy_num = self._get_enemy_number(enemy)
                    display_name = f"{enemy.name} {enemy_num}" if enemy_num else enemy.name
                    print_status_message(f"It's {display_name}'s turn, not a party member's!", "warning")
                    enemy_turn = True
                    break
            if not enemy_turn:
                print_status_message(f"It's not a valid combatant's turn!", "warning")
            return

        # Check action economy
        from dnd_engine.systems.action_economy import ActionType
        turn_state = self.game_state.initiative_tracker.get_current_turn_state()
        if not turn_state:
            print_error("Unable to get current turn state!")
            return

        if not turn_state.is_action_available(ActionType.ACTION):
            print_error("You don't have an Action available this turn!")
            print_status_message(f"Available: {turn_state}", "info")
            return

        # Get spellcasting ability from class data
        classes_data = self.game_state.data_loader.load_classes()
        class_data = classes_data.get(caster.character_class.value, {})
        spellcasting = class_data.get("spellcasting", {})
        spellcasting_ability = spellcasting.get("ability")

        if not spellcasting_ability:
            print_error(f"{caster.character_class.value.title()} cannot cast spells!")
            return

        # Load spells data
        spells_data = self.game_state.data_loader.load_spells()

        # Get castable spells from game engine (respects prepared/known spells)
        available_spells = caster.get_castable_spells(spells_data)

        if not available_spells:
            print_error(f"{caster.name} doesn't have any combat spells prepared!")
            return

        # If no spell specified, show list and prompt for selection
        spell_data = None
        spell_id = None

        if not spell_name:
            # Display available spells with slot information
            console.print("\n[bold cyan]Available Spells:[/bold cyan]")
            spell_choices = []
            for sid, sdata in available_spells:
                spell_level = sdata.get("level", 0)
                spell_display_name = sdata.get("name", sid)
                damage_info = sdata.get("damage", {})
                damage_dice = damage_info.get("dice", "")
                damage_type = damage_info.get("damage_type", "")

                # Scale cantrip damage for display
                if spell_level == 0:
                    damage_dice = caster.scale_cantrip_damage(damage_dice)
                    slot_info = "[green](cantrip)[/green]"
                else:
                    available_slots = caster.get_available_spell_slots(spell_level)
                    ordinal = caster._level_to_ordinal(spell_level)
                    if available_slots > 0:
                        slot_info = f"[green]({ordinal}, {available_slots} slots)[/green]"
                    else:
                        slot_info = f"[red]({ordinal}, no slots)[/red]"

                spell_choices.append(f"{spell_display_name} - {damage_dice} {damage_type} {slot_info}")

            # Use questionary for selection
            from questionary import select
            selected = select(
                "Choose a spell to cast:",
                choices=spell_choices + ["Cancel"]
            ).ask()

            if not selected or selected == "Cancel":
                return

            # Extract spell name from selection
            selected_spell_name = selected.split(" - ")[0]
            # Find the spell data
            for sid, sdata in available_spells:
                if sdata.get("name", sid) == selected_spell_name:
                    spell_id = sid
                    spell_data = sdata
                    break
        else:
            # Find spell by name
            spell_name_lower = spell_name.lower()
            for sid, sdata in available_spells:
                if sdata.get("name", "").lower() == spell_name_lower or sid == spell_name_lower:
                    spell_id = sid
                    spell_data = sdata
                    break

        if not spell_data:
            print_error(f"Unknown spell: {spell_name}")
            return

        # Check and consume spell slot for leveled spells
        spell_level = spell_data.get("level", 0)
        if spell_level > 0:
            if not caster.use_spell_slot(spell_level):
                ordinal = caster._level_to_ordinal(spell_level)
                print_error(f"No {ordinal}-level spell slots available!")
                return

        # Prompt for target selection
        target = self._prompt_enemy_selection()
        if target is None or target == "Cancel":
            # Refund spell slot if cancelled
            if spell_level > 0:
                pool_name = f"spell_slots_level_{spell_level}"
                pool = caster.get_resource_pool(pool_name)
                if pool:
                    pool.current += 1
            return

        # Consume the action
        if not turn_state.consume_action(ActionType.ACTION):
            print_error("Failed to consume action!")
            # Refund spell slot
            if spell_level > 0:
                pool_name = f"spell_slots_level_{spell_level}"
                pool = caster.get_resource_pool(pool_name)
                if pool:
                    pool.current += 1
            return

        # Log player action
        from dnd_engine.utils.logging_config import get_logging_config
        logging_config = get_logging_config()
        if logging_config:
            logging_config.log_player_action(
                character=caster.name,
                action="cast_spell",
                details=f"spell={spell_data.get('name')}, target={target.name}"
            )

        # Perform spell attack
        result = self.game_state.combat_engine.resolve_spell_attack(
            caster=caster,
            target=target,
            spell=spell_data,
            spellcasting_ability=spellcasting_ability,
            apply_damage=True,
            event_bus=self.game_state.event_bus
        )

        # Display narrative if available
        if self.llm_enhancer and result.hit:
            room = self.game_state.get_current_room()
            location = room.get("name", "")

            damage_info = spell_data.get("damage", {})
            damage_type = damage_info.get("damage_type", "magical")

            # Get caster race
            races_data = self.game_state.data_loader.load_races()
            caster_race_data = races_data.get(caster.race, {})
            caster_race = caster_race_data.get("name", "")

            with console.status("", spinner="dots"):
                narrative = self.llm_enhancer.get_combat_narrative_sync(
                    action_data={
                        "attacker": result.attacker_name,
                        "defender": result.defender_name,
                        "damage": result.damage,
                        "critical": result.critical_hit,
                        "hit": result.hit,
                        "location": location,
                        "weapon": spell_data.get("name", "spell"),
                        "damage_type": damage_type,
                        "attacker_race": caster_race,
                        "defender_armor": "",
                        "combat_history": self.combat_history,
                        "battlefield_state": self._build_battlefield_state(),
                        "is_spell": True
                    },
                    timeout=3.0
                )
            if narrative:
                self.display_narrative_panel(narrative)

        # Record this action in combat history
        self._record_combat_action(result)

        # Display mechanics
        spell_display_name = spell_data.get("name", spell_id)
        console.print(f"[magenta]✨ {caster.name} casts {spell_display_name}![/magenta]")
        console.print(f"[cyan]⚔️  {str(result)}[/cyan]")

        # If target died, show death narrative
        if not target.is_alive:
            if self.llm_enhancer:
                with console.status("", spinner="dots"):
                    death_narrative = self.llm_enhancer.get_death_narrative_sync(
                        character_data={
                            "name": target.name,
                            "is_player": isinstance(target, Character)
                        },
                        timeout=3.0
                    )
                if death_narrative:
                    self.display_narrative_panel(death_narrative)

            print_status_message(f"{target.name} is defeated!", "success")

        # End player turn
        self.game_state.initiative_tracker.next_turn()

        # Check if combat is over
        self.game_state._check_combat_end()

        if self.game_state.in_combat:
            # Process enemy turns
            self.process_enemy_turns()

    def handle_stabilize(self, target_name: str) -> None:
        """Handle stabilize command to help unconscious ally."""
        if not self.game_state.in_combat:
            print_error("You're not in combat!")
            return

        # Check if it's a party member's turn
        current = self.game_state.initiative_tracker.get_current_combatant()
        helper = None
        for character in self.game_state.party.characters:
            if current.creature == character and character.is_alive and not character.is_unconscious:
                helper = character
                break

        if not helper:
            print_status_message("It's not your turn, or your character is unconscious!", "warning")
            return

        # Find target ally
        target = None
        for character in self.game_state.party.characters:
            if character.name.lower() == target_name.lower() and character.is_unconscious:
                target = character
                break

        if not target:
            print_error(f"No unconscious ally named '{target_name}' found.")
            return

        print_section(f"{helper.name} attempts to stabilize {target.name}")

        # Load skills data
        skills_data = self.game_state.data_loader.load_skills()

        # Make Medicine skill check (DC 10)
        check_result = helper.make_skill_check("medicine", 10, skills_data)

        # Display check result
        modifier_str = f"+{check_result['modifier']}" if check_result['modifier'] >= 0 else str(check_result['modifier'])
        print_status_message(
            f"Medicine check: {check_result['roll']}{modifier_str} = {check_result['total']} vs DC {check_result['dc']}",
            "info"
        )

        if check_result['success']:
            # Stabilize the target
            target.stabilize_character()
            print_status_message(f"Success! {target.name} is stabilized.", "success")

            # Emit stabilization event
            from dnd_engine.utils.events import Event, EventType
            self.game_state.event_bus.emit(Event(
                type=EventType.CHARACTER_STABILIZED,
                data={
                    "helper": helper.name,
                    "target": target.name,
                    "check_total": check_result['total']
                }
            ))
        else:
            print_error(f"Failed! {target.name} remains unstabilized.")

        # Advance turn
        self.game_state.initiative_tracker.next_turn()

        # Check if combat is over
        self.game_state._check_combat_end()

        if self.game_state.in_combat:
            # Process enemy turns
            self.process_enemy_turns()

    def handle_flee(self) -> None:
        """Handle flee command during combat."""
        if not self.game_state.in_combat:
            print_error("You're not in combat!")
            return

        print_section("Fleeing Combat")
        print_status_message("The party attempts to flee...", "warning")

        # Execute flee
        result = self.game_state.flee_combat()

        if not result["success"]:
            print_error(f"Failed to flee: {result.get('reason', 'Unknown reason')}")
            return

        # Display opportunity attacks
        if result["opportunity_attacks"]:
            print_message("\nEnemies strike as you flee!")
            for attack_result in result["opportunity_attacks"]:
                console.print(f"[dim red]⚔️  {str(attack_result)}[/dim red]")

        # Display casualties
        if result["casualties"]:
            print_status_message(f"Casualties during retreat: {', '.join(result['casualties'])}", "warning")

        # Check if entire party died during flee
        if self.game_state.party.is_wiped():
            print_status_message("The entire party has fallen during the retreat!", "warning")
        else:
            retreat_dir = result.get("retreat_direction", "unknown")
            retreat_room = result.get("retreat_room", "unknown")
            print_status_message(f"The party flees {retreat_dir} to {retreat_room}!", "success")

            # Display new room
            self.display_room()

    def process_death_save_turn(self, character: Character) -> None:
        """
        Process a death saving throw turn for an unconscious character.

        Args:
            character: The unconscious character making the death save
        """
        print_section(f"{character.name}'s Turn - Death Save")
        print_status_message(f"{character.name} is unconscious and must make a death saving throw!", "warning")

        # Roll death save
        result = character.make_death_save(event_bus=self.game_state.event_bus)

        # Display results
        if result["natural_20"]:
            print_status_message(f"Natural 20! {character.name} regains 1 HP and consciousness!", "success")
        elif result["natural_1"]:
            # Natural 1 counts as 2 failures
            failures_display = min(result['failures'], 3)  # Cap display at 3
            print_status_message(f"Natural 1! Two failures recorded. Failures: {failures_display}/3", "warning")
        elif result["success"]:
            print_status_message(f"Success! (rolled {result['roll']}) Successes: {result['successes']}/3", "info")
        else:
            # Regular failure
            failures_display = min(result['failures'], 3)  # Cap display at 3
            print_status_message(f"Failure (rolled {result['roll']}) Failures: {failures_display}/3", "warning")

        # Check outcomes
        if result["conscious"]:
            print_status_message(f"{character.name} is conscious again with 1 HP!", "success")
        elif result["stabilized"]:
            print_status_message(f"{character.name} is stabilized! They no longer need to make death saves.", "success")
        elif result["dead"]:
            print_error(f"{character.name} has died...")
            # Remove from initiative
            self.game_state.initiative_tracker.remove_combatant(character)

    def _process_turn_start_effects(self, creature) -> None:
        """
        Process effects that trigger at the start of a creature's turn.

        Uses the ConditionManager to handle all condition-based turn-start effects.

        Args:
            creature: The creature whose turn is starting
        """
        # Process all turn-start effects using ConditionManager
        results = self.condition_manager.process_turn_start_effects(creature)

        # Display results
        for result in results:
            print_status_message(result.message, "warning")

            # Check if creature died from the effect
            if not creature.is_alive:
                print_status_message(f"💀 {creature.name} is killed by {result.condition_id.replace('_', ' ')}!", "warning")

    def _prompt_condition_removal(self, creature) -> bool:
        """
        Prompt the player to attempt removing a condition via ability check.

        Args:
            creature: The creature with conditions

        Returns:
            True if an action was consumed attempting to remove a condition
        """
        # Check each condition for removal options
        for condition_id in list(creature.conditions):
            if not self.condition_manager.can_attempt_early_removal(condition_id):
                continue

            # Get removal prompt info
            prompt_info = self.condition_manager.get_removal_prompt_info(condition_id)
            if not prompt_info:
                continue

            # Check if action is required and available
            turn_state = self.game_state.initiative_tracker.get_current_turn_state()
            if not turn_state or not turn_state.action_available:
                continue  # No action available

            # Prompt player
            condition_name = prompt_info["condition_name"]
            ability = prompt_info["ability"].upper()
            dc = prompt_info["dc"]
            description = prompt_info["description"]

            print_status_message(
                f"🔥 {creature.name} has condition: {condition_name}!",
                "warning"
            )
            print_message(f"   {description}")
            print_message(f"   Use your action to attempt a DC {dc} {ability} check to remove it? [Y/N]")

            response = input("   > ").strip().lower()

            if response in ['y', 'yes']:
                # Consume action
                from dnd_engine.systems.action_economy import ActionType
                turn_state.consume_action(ActionType.ACTION)

                # Attempt removal
                result = self.condition_manager.attempt_condition_removal(creature, condition_id)

                if result:
                    if result.success:
                        print_status_message(result.message, "success")
                    else:
                        print_status_message(result.message, "warning")

                return True  # Action was consumed

        return False  # No action consumed

    def _should_enemy_attempt_condition_removal(self, enemy) -> bool:
        """
        Simple AI to determine if an enemy should attempt to remove a condition.

        Logic:
        - If on fire and current_hp <= 4 (one more 1d4 could kill), attempt to extinguish
        - Otherwise, attack normally

        Args:
            enemy: The enemy creature

        Returns:
            True if enemy should attempt to remove condition (consumes turn)
        """
        # Check each condition for removal options
        for condition_id in list(enemy.conditions):
            if not self.condition_manager.can_attempt_early_removal(condition_id):
                continue

            # Simple AI for on_fire: attempt if low HP
            if condition_id == "on_fire":
                # If one more 1d4 damage could kill (HP <= 4), try to extinguish
                if enemy.current_hp <= 4:
                    print_status_message(
                        f"🔥 {enemy.name} is on fire with low HP! Attempting to extinguish...",
                        "info"
                    )

                    # Attempt removal
                    result = self.condition_manager.attempt_condition_removal(enemy, condition_id)

                    if result:
                        if result.success:
                            print_status_message(result.message, "success")
                        else:
                            print_status_message(result.message, "warning")

                    return True  # Turn was used
                else:
                    # Enemy chooses to ignore the flames and attack instead
                    print_status_message(
                        f"🔥 {enemy.name} is on fire ({enemy.current_hp}/{enemy.max_hp} HP) but chooses to press the attack rather than extinguish the flames!",
                        "info"
                    )

        return False  # No condition removal attempted

    def process_enemy_turns(self) -> None:
        """Process all enemy turns until it's a party member's turn again."""
        while self.game_state.in_combat:
            current = self.game_state.initiative_tracker.get_current_combatant()

            # If it's a party member's turn, stop
            is_party_turn = False
            for character in self.game_state.party.characters:
                if current.creature == character:
                    is_party_turn = True
                    break

            if is_party_turn:
                break

            # Enemy turn
            enemy = current.creature
            if not enemy.is_alive:
                self.game_state.initiative_tracker.next_turn()
                continue

            print_status_message(f"{enemy.name}'s turn...", "info")

            # Process turn-start effects (e.g., ongoing fire damage)
            self._process_turn_start_effects(enemy)

            # Check if enemy died from turn-start effects
            if not enemy.is_alive:
                self.game_state.initiative_tracker.next_turn()
                continue

            # Enemy AI: Check if should attempt to remove conditions
            if self._should_enemy_attempt_condition_removal(enemy):
                # Enemy attempts to remove condition instead of attacking
                self.game_state.initiative_tracker.next_turn()
                continue

            # Choose target from living party members (lowest HP)
            living_party = self.game_state.party.get_living_members()
            if not living_party:
                # No conscious targets - check if combat should end (party defeated)
                self.game_state._check_combat_end()
                if not self.game_state.in_combat:
                    break  # Combat ended (party wiped or all stabilized)
                # Combat continues (e.g., stabilized characters), advance turn
                self.game_state.initiative_tracker.next_turn()
                break

            target = min(living_party, key=lambda c: c.current_hp)

            # Get monster data for attack
            monsters = self.game_state.data_loader.load_monsters()
            monster_data = None
            for mid, mdata in monsters.items():
                if mdata["name"] == enemy.name:
                    monster_data = mdata
                    break

            if monster_data and monster_data.get("actions"):
                # Find first weapon attack action (skip Multiattack, etc.)
                action = None
                for act in monster_data["actions"]:
                    if "attack_bonus" in act and "damage" in act:
                        action = act
                        break

                if not action:
                    print_error(f"{enemy.name} has no valid attack actions!")
                    self.game_state.initiative_tracker.next_turn()
                    continue

                result = self.game_state.combat_engine.resolve_attack(
                    attacker=enemy,
                    defender=target,
                    attack_bonus=action["attack_bonus"],
                    damage_dice=action["damage"],
                    apply_damage=True
                )

                # Get and display attack narrative FIRST (if hit)
                if self.llm_enhancer and result.hit:
                    room = self.game_state.get_current_room()
                    location = room.get("name", "")

                    # Get weapon name and damage type from action
                    weapon_name = action.get("name", "weapon")
                    damage_type = action.get("damage_type", "")

                    # Get attacker type/race from monster data
                    attacker_race = monster_data.get("type", "")

                    # Get defender armor (target is always a player character here)
                    defender_armor = ""
                    items_data = self.game_state.data_loader.load_items()
                    equipped_armor_id = target.inventory.get_equipped_item(EquipmentSlot.ARMOR)
                    if equipped_armor_id:
                        armor_data = items_data.get("armor", {}).get(equipped_armor_id, {})
                        armor_type = armor_data.get("armor_type", "")
                        if armor_type:
                            defender_armor = f"{armor_type} armor"

                    with console.status("", spinner="dots"):
                        narrative = self.llm_enhancer.get_combat_narrative_sync(
                            action_data={
                                "attacker": result.attacker_name,
                                "defender": result.defender_name,
                                "damage": result.damage,
                                "critical": result.critical_hit,
                                "hit": result.hit,
                                "location": location,
                                "weapon": weapon_name,
                                "damage_type": damage_type,
                                "attacker_race": attacker_race,
                                "defender_armor": defender_armor,
                                "combat_history": self.combat_history,
                                "battlefield_state": self._build_battlefield_state()
                            },
                            timeout=3.0
                        )
                    if narrative:
                        self.display_narrative_panel(narrative)

                # Record this action in combat history
                self._record_combat_action(result)

                # Display mechanics after narrative
                console.print(f"[cyan]⚔️  {str(result)}[/cyan]")

                # Check if party member died - show death narrative then message
                if not target.is_alive:
                    if self.llm_enhancer:
                        with console.status("", spinner="dots"):
                            death_narrative = self.llm_enhancer.get_death_narrative_sync(
                                character_data={
                                    "name": target.name,
                                    "is_player": isinstance(target, Character)
                                },
                                timeout=3.0
                            )
                        if death_narrative:
                            self.display_narrative_panel(death_narrative)

                    print_status_message(f"{target.name} has fallen!", "warning")

            # Next turn
            self.game_state.initiative_tracker.next_turn()

            # Check if entire party is dead
            if self.game_state.party.is_wiped():
                break

    def _assign_enemy_numbers(self) -> None:
        """
        Assign sequential numbers to enemies when combat starts.

        Numbers are assigned based on order in active_enemies list.
        This creates a mapping like: Goblin -> 1, Goblin -> 2, Wolf -> 3, etc.
        """
        self.enemy_numbers.clear()
        for idx, enemy in enumerate(self.game_state.active_enemies, start=1):
            self.enemy_numbers[enemy] = idx

    def _get_enemy_number(self, enemy: Any) -> Optional[int]:
        """
        Get the combat number for an enemy.

        Args:
            enemy: The enemy creature

        Returns:
            The enemy's number, or None if not found
        """
        return self.enemy_numbers.get(enemy)

    def _find_enemy_by_target(self, target: str) -> Optional[Any]:
        """
        Find an enemy by number or name.

        Supports:
        - Direct number: "1", "2", "3"
        - Name with number: "goblin 1", "wolf 3"
        - Name only: "goblin", "wolf" (if unambiguous)

        Args:
            target: The target string

        Returns:
            The matching enemy, or None if not found
        """
        target = target.strip().lower()

        # Try to parse as pure number first
        try:
            num = int(target)
            for enemy, enemy_num in self.enemy_numbers.items():
                if enemy_num == num and enemy.is_alive:
                    return enemy
            return None
        except ValueError:
            pass

        # Try to match "name number" pattern (e.g., "goblin 1")
        parts = target.split()
        if len(parts) >= 2:
            try:
                num = int(parts[-1])
                name_part = " ".join(parts[:-1])
                # Find enemy with matching name and number
                for enemy, enemy_num in self.enemy_numbers.items():
                    if enemy_num == num and enemy.name.lower() == name_part and enemy.is_alive:
                        return enemy
            except ValueError:
                pass

        # Try to match by name only
        matching_enemies = []
        for enemy in self.game_state.active_enemies:
            if enemy.is_alive and enemy.name.lower() == target:
                matching_enemies.append(enemy)

        # If exactly one match, return it
        if len(matching_enemies) == 1:
            return matching_enemies[0]

        # If multiple matches, return None (ambiguous)
        return None

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

    def _prompt_consumable_selection(self, character: Optional[Character] = None, show_action_cost: bool = False) -> Optional[tuple[str, Dict[str, Any]]]:
        """
        Prompt user to select a consumable item from inventory.

        Args:
            character: Character whose inventory to use. If None, searches all party members.
            show_action_cost: Whether to show action cost (for combat mode)

        Returns:
            Tuple of (item_id, item_data) or None if cancelled
        """
        import questionary

        items_data = self.game_state.data_loader.load_items()
        consumables_list = []

        # Gather consumables from specified character or all party
        if character:
            inventory = character.inventory
            consumables = inventory.get_items_by_category("consumables")
            for inv_item in consumables:
                item_data = items_data["consumables"].get(inv_item.item_id, {})
                consumables_list.append({
                    "item_id": inv_item.item_id,
                    "item_data": item_data,
                    "quantity": inv_item.quantity,
                    "owner": character.name
                })
        else:
            # Aggregate from all party members
            for char in self.game_state.party.characters:
                if not char.is_alive:
                    continue
                inventory = char.inventory
                consumables = inventory.get_items_by_category("consumables")
                for inv_item in consumables:
                    item_data = items_data["consumables"].get(inv_item.item_id, {})
                    consumables_list.append({
                        "item_id": inv_item.item_id,
                        "item_data": item_data,
                        "quantity": inv_item.quantity,
                        "owner": char.name
                    })

        if not consumables_list:
            print_error("No consumable items available!")
            return None

        # Build choices for questionary
        choices = []
        for item in consumables_list:
            item_name = item["item_data"].get("name", item["item_id"])
            quantity = item["quantity"]
            owner = item["owner"]

            display_parts = [item_name]

            if show_action_cost:
                action_cost = item["item_data"].get("action_required", "action")
                display_parts.append(f"({action_cost.replace('_', ' ')})")

            display_parts.append(f"(x{quantity})")

            if not character:
                display_parts.append(f"- {owner}")

            choice_text = " ".join(display_parts)
            choices.append(questionary.Choice(title=choice_text, value=item))

        # Add cancel option
        choices.append(questionary.Choice(title="Cancel", value=None))

        # Get user selection with arrow keys
        try:
            result = questionary.select(
                "Select Item to Use:",
                choices=choices,
                use_arrow_keys=True
            ).ask()

            # Check if user cancelled or selected Cancel option
            # questionary returns "Cancel" string when user selects Cancel option
            if result is None or result == "Cancel" or not isinstance(result, dict):
                return None

            return (result["item_id"], result["item_data"])
        except (EOFError, KeyboardInterrupt):
            return None

    def _prompt_target_selection(self, item_name: str) -> Optional[Character]:
        """
        Prompt user to select a target character for item use.

        Args:
            item_name: Name of the item being used (for display)

        Returns:
            Selected Character or None if cancelled
        """
        import questionary

        # Get targetable members from game engine (includes living + unconscious)
        targetable_members = self.game_state.party.get_targetable_members()

        if not targetable_members:
            print_error("No party members can be targeted!")
            return None

        # Build choices for questionary
        choices = []
        for character in targetable_members:
            hp_pct = character.current_hp / character.max_hp if character.max_hp > 0 else 0

            # Use text-based indicators since questionary doesn't support rich formatting
            if character.is_unconscious:
                hp_indicator = "💀 UNCONSCIOUS"
            elif hp_pct > 0.5:
                hp_indicator = "●●●"
            elif hp_pct > 0.25:
                hp_indicator = "●●○"
            else:
                hp_indicator = "●○○"

            choice_text = f"{character.name} (HP: {character.current_hp}/{character.max_hp} {hp_indicator})"
            choices.append(questionary.Choice(title=choice_text, value=character))

        # Add cancel option
        choices.append(questionary.Choice(title="Cancel", value=None))

        # Get user selection with arrow keys
        try:
            result = questionary.select(
                f"Use {item_name} on:",
                choices=choices,
                use_arrow_keys=True
            ).ask()

            return result
        except (EOFError, KeyboardInterrupt):
            return None

    def _prompt_enemy_selection(self) -> Optional[Any]:
        """
        Prompt user to select an enemy to attack.

        Returns:
            Selected enemy creature or None if cancelled
        """
        import questionary

        living_enemies = [e for e in self.game_state.active_enemies if e.is_alive]
        if not living_enemies:
            print_error("No enemies to attack!")
            return None

        # Build choices for questionary
        choices = []
        for enemy in living_enemies:
            enemy_num = self._get_enemy_number(enemy)
            hp_pct = enemy.current_hp / enemy.max_hp if enemy.max_hp > 0 else 0

            # Use text-based indicators
            if hp_pct > 0.5:
                hp_indicator = "●●●"
            elif hp_pct > 0.25:
                hp_indicator = "●●○"
            else:
                hp_indicator = "●○○"

            display_name = f"{enemy.name} {enemy_num}" if enemy_num else enemy.name
            choice_text = f"{display_name} (HP: {enemy.current_hp}/{enemy.max_hp} {hp_indicator})"
            choices.append(questionary.Choice(title=choice_text, value=enemy))

        # Add cancel option
        choices.append(questionary.Choice(title="Cancel", value=None))

        # Get user selection with arrow keys
        try:
            result = questionary.select(
                "Select target to attack:",
                choices=choices,
                use_arrow_keys=True
            ).ask()

            return result
        except (EOFError, KeyboardInterrupt):
            return None

    def _prompt_combat_ally_selection(self, item_name: str, item_data: Dict[str, Any], user: Character) -> Optional[Character]:
        """
        Prompt user to select an ally to use an item on during combat.
        Validates range and includes unconscious allies.

        Args:
            item_name: Name of the item being used
            item_data: Item data dictionary
            user: Character using the item

        Returns:
            Selected Character or None if cancelled
        """
        import questionary

        # Get item range (default 5 feet for touch items)
        item_range = item_data.get("range", 5)

        # Get all party members (including unconscious ones)
        # In D&D 5E combat, we assume all party members are within 5 feet (touch range)
        # For this implementation, we'll consider all party members as valid targets
        valid_targets = [c for c in self.game_state.party.characters if c.is_alive or c.is_unconscious]

        if not valid_targets:
            print_error("No valid targets available!")
            return None

        # Build choices for questionary
        choices = []
        for character in valid_targets:
            hp_pct = character.current_hp / character.max_hp if character.max_hp > 0 else 0

            # Use text-based indicators
            if character.is_unconscious:
                hp_indicator = "💀 UNCONSCIOUS"
                status = f"(HP: 0/{character.max_hp})"
            elif hp_pct > 0.5:
                hp_indicator = "●●●"
                status = f"(HP: {character.current_hp}/{character.max_hp})"
            elif hp_pct > 0.25:
                hp_indicator = "●●○"
                status = f"(HP: {character.current_hp}/{character.max_hp})"
            else:
                hp_indicator = "●○○"
                status = f"(HP: {character.current_hp}/{character.max_hp})"

            choice_text = f"{character.name} {status} {hp_indicator}"
            choices.append(questionary.Choice(title=choice_text, value=character))

        # Add cancel option
        choices.append(questionary.Choice(title="Cancel", value=None))

        # Get user selection with arrow keys
        try:
            result = questionary.select(
                f"Use {item_name} on:",
                choices=choices,
                use_arrow_keys=True
            ).ask()

            return result
        except (EOFError, KeyboardInterrupt):
            return None

    def _prompt_item_to_take(self) -> Optional[Dict[str, Any]]:
        """
        Prompt user to select an item to take from the current room.

        Returns:
            Selected item dict or None if cancelled
        """
        import questionary

        # Get available items in the room
        available_items = self.game_state.get_available_items_in_room()

        if not available_items:
            room = self.game_state.get_current_room()
            if room.get("searchable") and not room.get("searched"):
                print_error("You haven't searched this room yet. Use 'search' first.")
            else:
                print_error("There are no items to take here.")
            return None

        # Build choices for questionary
        choices = []
        for item in available_items:
            if item["type"] == "gold":
                choice_text = f"Gold ({item['amount']} pieces)"
                choices.append(questionary.Choice(title=choice_text, value=item))
            elif item["type"] == "currency":
                currency_parts = []
                if item.get("gold", 0) > 0:
                    currency_parts.append(f"{item['gold']} gold")
                if item.get("silver", 0) > 0:
                    currency_parts.append(f"{item['silver']} silver")
                if item.get("copper", 0) > 0:
                    currency_parts.append(f"{item['copper']} copper")
                if item.get("platinum", 0) > 0:
                    currency_parts.append(f"{item['platinum']} platinum")
                choice_text = f"Currency ({', '.join(currency_parts)})"
                choices.append(questionary.Choice(title=choice_text, value=item))
            elif item["type"] == "item":
                item_id = item.get("id", "unknown")
                # Format item name nicely
                display_name = item_id.replace("_", " ").title()
                choices.append(questionary.Choice(title=display_name, value=item))

        # Add cancel option
        choices.append(questionary.Choice(title="Cancel", value=None))

        # Get user selection with arrow keys
        try:
            result = questionary.select(
                "Select item to take:",
                choices=choices,
                use_arrow_keys=True
            ).ask()

            return result
        except (EOFError, KeyboardInterrupt):
            return None

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

    def handle_use_item_direct(self, item_id: str, target: Character, owner: Character) -> None:
        """
        Handle using a consumable item with explicit character references.

        Args:
            item_id: The item to use (ID)
            target: Character to apply the effect to
            owner: Character who owns the item
        """
        from dnd_engine.systems.item_effects import apply_item_effect

        inventory = owner.inventory
        items_data = self.game_state.data_loader.load_items()

        # Use the item from owner's inventory (removes it)
        success, item_info = inventory.use_item(item_id, items_data)

        if not success:
            print_error(f"Failed to use {item_id}")
            return

        item_name = item_info.get("name", item_id)

        # Apply the item's effect to the target
        result = apply_item_effect(
            item_info=item_info,
            target=target,
            dice_roller=self.game_state.dice_roller,
            event_bus=self.game_state.event_bus
        )

        # Display the result
        if owner == target:
            print_status_message(f"{owner.name} uses {item_name}", "info")
        else:
            print_status_message(f"{owner.name} uses {item_name} on {target.name}", "info")
        print_message(result.message)

        # Emit item used event
        self.game_state.event_bus.emit(Event(
            type=EventType.ITEM_USED,
            data={
                "character": owner.name,
                "target": target.name,
                "item_id": item_id,
                "item_name": item_name,
                "effect_type": result.effect_type,
                "success": result.success
            }
        ))

    def handle_use_item(self, item_id: str, player_identifier: Optional[str] = None) -> None:
        """
        Handle using a consumable item for a specific party member (legacy method).

        Args:
            item_id: The item to use (ID or name)
            player_identifier: Optional player identifier (1-based index or character name)
        """
        from dnd_engine.systems.item_effects import apply_item_effect

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

        # Use the item from inventory (removes it)
        success, item_info = inventory.use_item(target_item, items_data)

        if not success:
            print_error(f"Failed to use {item_id}")
            return

        item_name = item_info.get("name", target_item)

        # Apply the item's effect
        result = apply_item_effect(
            item_info=item_info,
            target=character,
            dice_roller=self.game_state.dice_roller,
            event_bus=self.game_state.event_bus
        )

        # Display the result
        print_status_message(f"{character.name} uses {item_name}", "info")
        print_message(result.message)

        # Emit item used event
        self.game_state.event_bus.emit(Event(
            type=EventType.ITEM_USED,
            data={
                "character": character.name,
                "item_id": target_item,
                "item_name": item_name,
                "effect_type": result.effect_type,
                "success": result.success
            }
        ))

    def handle_use_item_combat_direct(self, item_id: str, item_data: Dict[str, Any], character: Character) -> None:
        """
        Handle using a consumable item during combat with explicit item data.

        Validates action economy, consumes action, and applies item effect.

        Args:
            item_id: The item ID to use
            item_data: The item data dictionary
            character: The character using the item
        """
        from dnd_engine.systems.item_effects import apply_item_effect
        from dnd_engine.systems.action_economy import ActionType

        inventory = character.inventory
        items_data = self.game_state.data_loader.load_items()

        item_name = item_data.get("name", item_id)
        action_required_str = item_data.get("action_required", "action")

        # Map string to ActionType
        action_type_map = {
            "action": ActionType.ACTION,
            "bonus_action": ActionType.BONUS_ACTION,
            "free_object": ActionType.FREE_OBJECT,
            "no_action": ActionType.NO_ACTION
        }
        action_required = action_type_map.get(action_required_str, ActionType.ACTION)

        # Check if action is available
        turn_state = self.game_state.initiative_tracker.get_current_turn_state()
        if not turn_state:
            print_error("Unable to get current turn state!")
            return

        if not turn_state.is_action_available(action_required):
            action_name = action_required_str.replace("_", " ").title()
            print_error(f"You don't have a {action_name} available this turn!")
            print_status_message(f"Available: {turn_state}", "info")
            return

        # Consume the action
        if not turn_state.consume_action(action_required):
            print_error(f"Failed to consume {action_required_str}!")
            return

        # Use the item from inventory (removes it)
        success, used_item_data = inventory.use_item(item_id, items_data)

        if not success:
            print_error(f"Failed to use {item_name}")
            # Restore the action since item use failed
            turn_state.reset()
            turn_state.consume_action(action_required)  # Put back what we consumed
            return

        # Apply the item's effect
        result = apply_item_effect(
            item_info=used_item_data,
            target=character,
            dice_roller=self.game_state.dice_roller,
            event_bus=self.game_state.event_bus
        )

        # Display the result
        action_cost_msg = f"({action_required_str.replace('_', ' ')})"
        print_status_message(f"{character.name} uses {item_name} {action_cost_msg}", "info")
        print_message(result.message)

        # Show remaining actions
        remaining_actions = str(turn_state)
        print_status_message(f"Remaining this turn: {remaining_actions}", "info")

        # Emit item used event
        self.game_state.event_bus.emit(Event(
            type=EventType.ITEM_USED,
            data={
                "character": character.name,
                "item_id": item_id,
                "item_name": item_name,
                "effect_type": result.effect_type,
                "action_cost": action_required_str,
                "success": result.success
            }
        ))

    def handle_use_item_combat_with_target(self, item_id: str, item_data: Dict[str, Any], user: Character, target: Character) -> None:
        """
        Handle using a consumable item during combat on a specified target.

        Validates action economy, consumes action, and applies item effect to target.

        Args:
            item_id: The item ID to use
            item_data: The item data dictionary
            user: The character using the item
            target: The character receiving the item's effect
        """
        from dnd_engine.systems.item_effects import apply_item_effect
        from dnd_engine.systems.action_economy import ActionType

        inventory = user.inventory
        items_data = self.game_state.data_loader.load_items()

        item_name = item_data.get("name", item_id)
        action_required_str = item_data.get("action_required", "action")

        # Map string to ActionType
        action_type_map = {
            "action": ActionType.ACTION,
            "bonus_action": ActionType.BONUS_ACTION,
            "free_object": ActionType.FREE_OBJECT,
            "no_action": ActionType.NO_ACTION
        }
        action_required = action_type_map.get(action_required_str, ActionType.ACTION)

        # Check if action is available
        turn_state = self.game_state.initiative_tracker.get_current_turn_state()
        if not turn_state:
            print_error("Unable to get current turn state!")
            return

        if not turn_state.is_action_available(action_required):
            action_name = action_required_str.replace("_", " ").title()
            print_error(f"You don't have a {action_name} available this turn!")
            print_status_message(f"Available: {turn_state}", "info")
            return

        # Consume the action
        if not turn_state.consume_action(action_required):
            print_error(f"Failed to consume {action_required_str}!")
            return

        # Show HP before healing (if target is alive or unconscious)
        hp_before = target.current_hp

        # Use the item from inventory (removes it)
        success, used_item_data = inventory.use_item(item_id, items_data)

        if not success:
            print_error(f"Failed to use {item_name}")
            # Restore the action since item use failed
            turn_state.reset()
            turn_state.consume_action(action_required)  # Put back what we consumed
            return

        # Apply the item's effect to the target
        result = apply_item_effect(
            item_info=used_item_data,
            target=target,
            dice_roller=self.game_state.dice_roller,
            event_bus=self.game_state.event_bus
        )

        # Display the result with target information
        action_cost_msg = f"({action_required_str.replace('_', ' ')})"
        if user == target:
            print_status_message(f"{user.name} uses {item_name} {action_cost_msg}", "info")
        else:
            print_status_message(f"{user.name} uses {item_name} on {target.name} {action_cost_msg}", "info")

        print_message(result.message)

        # Show HP change if healing occurred
        if result.effect_type == "healing" and target.current_hp > hp_before:
            hp_gained = target.current_hp - hp_before
            print_status_message(f"{target.name}: {hp_before} → {target.current_hp} HP (+{hp_gained})", "success")

        # Show remaining actions
        remaining_actions = str(turn_state)
        print_status_message(f"Remaining this turn: {remaining_actions}", "info")

        # Emit item used event
        self.game_state.event_bus.emit(Event(
            type=EventType.ITEM_USED,
            data={
                "character": user.name,
                "target": target.name,
                "item_id": item_id,
                "item_name": item_name,
                "effect_type": result.effect_type,
                "action_cost": action_required_str,
                "success": result.success
            }
        ))

        # End player turn
        self.game_state.initiative_tracker.next_turn()

        # Check if combat is over
        self.game_state._check_combat_end()

        if self.game_state.in_combat:
            # Process enemy turns
            self.process_enemy_turns()

    def handle_use_item_combat_attack(self, item_id: str, item_data: Dict[str, Any], user: Character, target) -> None:
        """
        Handle using an attack-type consumable item during combat on an enemy target.

        Makes a ranged attack roll and applies damage/effects on hit.
        Suitable for throwable items like Alchemist's Fire, Acid Vials, etc.

        Args:
            item_id: The item ID to use
            item_data: The item data dictionary
            user: The character using the item
            target: The enemy creature being targeted
        """
        # Use the game state method to handle all game logic
        result = self.game_state.use_combat_attack_item(user, item_id, target)

        # Handle failure cases with DM-friendly messages
        if not result.success:
            # Action economy issues - not errors, just game rules
            if result.error_message and "available" in result.error_message.lower():
                turn_state = self.game_state.initiative_tracker.get_current_turn_state()
                print_status_message(f"You don't have a {result.action_type.value.replace('_', ' ')} available right now.", "warning")
                if turn_state:
                    print_status_message(f"What you can still do: {turn_state}", "info")
            else:
                # Actual errors (item not found, etc.)
                print_error(result.error_message)
            return

        # Display the attack
        action_str = result.action_type.value.replace("_", " ")
        print_status_message(f"{user.name} throws {result.item_name} ({action_str})", "info")

        # Show attack roll result
        if result.attack_result:
            console.print(f"[cyan]⚔️  {str(result.attack_result)}[/cyan]")

            # Show special effects
            if "on_fire" in result.special_effects:
                print_status_message(f"🔥 {target.name} catches fire and will take 1d4 fire damage at the start of each turn!", "warning")
                print_status_message(f"{target.name} can use an action to make a DC 10 DEX check to extinguish the flames", "info")

        # Check if target died
        if not target.is_alive:
            enemy_num = self._get_enemy_number(target)
            display_name = f"{target.name} {enemy_num}" if enemy_num else target.name
            print_status_message(f"💀 {display_name} is defeated!", "success")

        # End player turn
        self.game_state.initiative_tracker.next_turn()

        # Check if combat is over
        self.game_state._check_combat_end()

        if self.game_state.in_combat:
            # Process enemy turns
            self.process_enemy_turns()

    def handle_use_item_combat(self, item_id: str) -> None:
        """
        Handle using a consumable item during combat (legacy method).

        Validates action economy, consumes action, and applies item effect.

        Args:
            item_id: The item to use (ID or name)
        """
        from dnd_engine.systems.item_effects import apply_item_effect
        from dnd_engine.systems.action_economy import ActionType

        # Verify it's the player's turn
        if not self.game_state.in_combat or not self.game_state.initiative_tracker:
            print_error("Not in combat!")
            return

        current = self.game_state.initiative_tracker.get_current_combatant()
        if not current:
            print_error("No current combatant!")
            return

        # Check if current combatant is a party member
        if current.creature not in self.game_state.party.characters:
            print_error("It's not a party member's turn!")
            return

        character = current.creature
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

        # Get item data to check action cost
        item_info = items_data["consumables"][target_item]
        item_name = item_info.get("name", target_item)
        action_required_str = item_info.get("action_required", "action")

        # Map string to ActionType
        action_type_map = {
            "action": ActionType.ACTION,
            "bonus_action": ActionType.BONUS_ACTION,
            "free_object": ActionType.FREE_OBJECT,
            "no_action": ActionType.NO_ACTION
        }
        action_required = action_type_map.get(action_required_str, ActionType.ACTION)

        # Check if action is available
        turn_state = self.game_state.initiative_tracker.get_current_turn_state()
        if not turn_state:
            print_error("Unable to get current turn state!")
            return

        if not turn_state.is_action_available(action_required):
            action_name = action_required_str.replace("_", " ").title()
            print_error(f"You don't have a {action_name} available this turn!")
            print_status_message(f"Available: {turn_state}", "info")
            return

        # Consume the action
        if not turn_state.consume_action(action_required):
            print_error(f"Failed to consume {action_required_str}!")
            return

        # Use the item from inventory (removes it)
        success, item_data = inventory.use_item(target_item, items_data)

        if not success:
            print_error(f"Failed to use {item_id}")
            # Restore the action since item use failed
            turn_state.reset()
            turn_state.consume_action(action_required)  # Put back what we consumed
            return

        # Apply the item's effect
        result = apply_item_effect(
            item_info=item_data,
            target=character,
            dice_roller=self.game_state.dice_roller,
            event_bus=self.game_state.event_bus
        )

        # Display the result
        action_cost_msg = f"({action_required_str.replace('_', ' ')})"
        print_status_message(f"{character.name} uses {item_name} {action_cost_msg}", "info")
        print_message(result.message)

        # Show remaining actions
        remaining_actions = str(turn_state)
        print_status_message(f"Remaining this turn: {remaining_actions}", "info")

        # Emit item used event
        self.game_state.event_bus.emit(Event(
            type=EventType.ITEM_USED,
            data={
                "character": character.name,
                "item_id": target_item,
                "item_name": item_name,
                "effect_type": result.effect_type,
                "action_cost": action_required_str,
                "success": result.success
            }
        ))

    def handle_save(self) -> None:
        """Handle manual named save command."""
        if not self.campaign_manager or not self.campaign_name:
            print_error("Save functionality not available")
            return

        print_section("Save Game", "Enter a name for your save")

        save_name = input("Save name: ").strip()

        if not save_name:
            print_status_message("Save cancelled", "warning")
            return

        try:
            with console.status("[cyan]Saving...[/cyan]", spinner="dots"):
                self.campaign_manager.save_campaign_state(
                    campaign_name=self.campaign_name,
                    game_state=self.game_state,
                    slot_name=save_name,
                    save_type="manual"
                )
            print_status_message(f"✓ Game saved: {save_name}", "success")
        except Exception as e:
            print_error(f"Failed to save game: {e}")

    def handle_quick_save(self) -> None:
        """Handle quick-save command (S key)."""
        if not self.campaign_manager or not self.campaign_name:
            print_error("Save functionality not available")
            return

        try:
            with console.status("[cyan]Saving...[/cyan]", spinner="dots"):
                self.campaign_manager.save_campaign_state(
                    campaign_name=self.campaign_name,
                    game_state=self.game_state,
                    slot_name="quick",
                    save_type="quick"
                )
            print_status_message("✓ Quick-saved", "success")
        except Exception as e:
            print_error(f"Failed to quick-save: {e}")

    def handle_rest(self) -> None:
        """
        Handle rest command to allow party to rest and recover.

        Prompts player to choose between short rest or long rest.
        """
        from dnd_engine.ui.rich_ui import print_section, print_message, print_status_message
        from dnd_engine.utils.events import Event, EventType

        print_section("Rest")
        print_message("The party takes a moment to rest and recover...")
        print_message("")
        print_message("How long would you like to rest?")
        print_message("  1. Short rest (1 hour) - Recover some abilities")
        print_message("  2. Long rest (8 hours) - Recover all HP and abilities")
        print_message("  3. Cancel")
        print_message("")

        choice = input("Choose rest type (1-3): ").strip()

        if choice == "3":
            print_status_message("Rest cancelled", "warning")
            return

        if choice not in ["1", "2"]:
            print_status_message("Invalid choice. Rest cancelled.", "warning")
            return

        # Determine rest type
        if choice == "1":
            rest_type = "short"
            rest_duration = "1 hour"
        else:
            rest_type = "long"
            rest_duration = "8 hours"

        # Perform rest for all party members
        results = []
        hp_recovered_total = {}
        resources_recovered_total = {}

        for character in self.game_state.party.characters:
            if rest_type == "short":
                result = character.take_short_rest()
            else:
                result = character.take_long_rest()
            results.append(result)
            hp_recovered_total[character.name] = result["hp_recovered"]
            resources_recovered_total[character.name] = result["resources_recovered"]

        # Emit rest event
        event_type = EventType.SHORT_REST if rest_type == "short" else EventType.LONG_REST
        event = Event(
            type=event_type,
            data={
                "party": [char.name for char in self.game_state.party.characters],
                "rest_type": rest_type,
                "hp_recovered": hp_recovered_total,
                "resources_recovered": resources_recovered_total
            }
        )
        self.game_state.event_bus.emit(event)

        # Display rest results
        self._display_rest_results(results, rest_type, rest_duration)

        # After long rest, offer spell preparation to prepared casters
        if rest_type == "long":
            for result in results:
                if result.get("can_prepare_spells"):
                    character = self.game_state.party.get_character_by_name(result["character"])
                    if character:
                        self._offer_spell_preparation(character)

    def _display_rest_results(self, results: list, rest_type: str, rest_duration: str) -> None:
        """
        Display the results of a rest to the player.

        Args:
            results: List of rest result dictionaries from each character
            rest_type: "short" or "long"
            rest_duration: Human-readable duration string (e.g., "1 hour", "8 hours")
        """
        from dnd_engine.ui.rich_ui import print_section, print_message, print_status_message

        print_section(f"{'Short' if rest_type == 'short' else 'Long'} Rest Complete")
        print_message(f"The party rests for {rest_duration}...")
        print_message("")

        for result in results:
            char_name = result["character"]
            hp_recovered = result["hp_recovered"]
            resources = result["resources_recovered"]

            print_message(f"{char_name}:")

            if hp_recovered > 0:
                print_message(f"  ❤️  HP recovered: {hp_recovered}")

            if resources:
                # Format resource names nicely
                formatted_resources = [r.replace("_", " ").title() for r in resources]
                print_message(f"  ⚡ Recovered: {', '.join(formatted_resources)}")

            if hp_recovered == 0 and not resources:
                print_message(f"  Already at full health and resources")

            print_message("")

        print_status_message("The party is refreshed and ready to continue!", "success")

    def _offer_spell_preparation(self, character: Character) -> None:
        """
        Offer spell preparation UI for prepared caster classes.

        Allows player to review and change prepared spells after a long rest.
        This is pure UI - displays spells, captures selections, calls GameState.

        Args:
            character: Character who can prepare spells (Wizard or Cleric)
        """
        from dnd_engine.ui.rich_ui import print_section, print_message, print_status_message

        # Ask if player wants to change prepared spells
        print_message("")
        print_message(f"{character.name} can prepare spells.")
        choice = input("Change prepared spells? (y/n): ").strip().lower()

        if choice != 'y':
            print_message("Keeping current spell selection.")
            return

        # Load spell data
        spells_data = self.game_state.data_loader.load_spells()

        # Get available spells
        cantrips, leveled_spells = character.get_preparable_spells(spells_data)

        # Calculate preparation limit
        max_prepared = character.get_max_prepared_spells()

        # Show current prepared spells (excluding cantrips)
        current_prepared = [s for s in character.prepared_spells if s not in cantrips]

        print_section(f"Spell Preparation - {character.name}")
        print_message(f"You can prepare up to {max_prepared} spells (cantrips don't count).")
        print_message("")
        print_message("Cantrips (always prepared):")
        for cantrip_id in cantrips:
            cantrip = spells_data.get(cantrip_id, {})
            print_message(f"  • {cantrip.get('name', cantrip_id)}")
        print_message("")

        if not leveled_spells:
            print_status_message("No leveled spells available to prepare.", "warning")
            return

        print_message("Available Spells:")
        for idx, (spell_id, spell_data) in enumerate(leveled_spells, 1):
            spell_name = spell_data.get("name", spell_id)
            spell_level = spell_data.get("level", "?")
            school = spell_data.get("school", "")
            prepared_mark = "✓" if spell_id in current_prepared else " "
            print_message(f"  [{prepared_mark}] {idx}. {spell_name} (Level {spell_level}, {school})")

        print_message("")
        print_message("Enter spell numbers to prepare (comma-separated, e.g., '1,3,5')")
        print_message(f"You can select up to {max_prepared} spells.")
        print_message("Press Enter without typing to cancel.")
        print_message("")

        selection = input(f"Select spells (max {max_prepared}): ").strip()

        if not selection:
            print_message("Spell preparation cancelled.")
            return

        # Parse selection
        try:
            indices = [int(x.strip()) - 1 for x in selection.split(',')]
        except ValueError:
            print_status_message("Invalid input. Spell preparation cancelled.", "error")
            return

        # Validate indices
        if any(i < 0 or i >= len(leveled_spells) for i in indices):
            print_status_message("Invalid spell number. Spell preparation cancelled.", "error")
            return

        # Check count
        if len(indices) > max_prepared:
            print_status_message(
                f"Too many spells selected ({len(indices)}/{max_prepared}). Preparation cancelled.",
                "error"
            )
            return

        # Get selected spell IDs (excluding duplicates)
        selected_spell_ids = list(dict.fromkeys([leveled_spells[i][0] for i in indices]))

        # Add cantrips to selection (they're always prepared)
        final_spell_ids = cantrips + selected_spell_ids

        # Call GameState to prepare spells (it validates and updates)
        success = self.game_state.prepare_spells(character.name, final_spell_ids)

        if success:
            spell_names = [spells_data[sid].get("name", sid) for sid in selected_spell_ids]
            print_status_message(
                f"✓ Prepared {len(selected_spell_ids)} spell{'s' if len(selected_spell_ids) != 1 else ''}: "
                f"{', '.join(spell_names)}",
                "success"
            )
        else:
            print_status_message("Failed to prepare spells. Please try again.", "error")

    def handle_cast_spell_exploration(self) -> None:
        """
        Handle spell casting during exploration mode.

        Allows party members to cast healing and utility spells outside of combat.
        Prompts for caster selection, spell selection, and target selection.
        """
        from dnd_engine.ui.rich_ui import print_section, print_message, print_status_message, print_error
        import questionary

        # 1. Select caster
        caster = self._prompt_party_member_selection("Who will cast a spell?")
        if not caster:
            return  # User cancelled

        # Check if character can cast spells
        spells_data = self.game_state.data_loader.load_spells()
        available_spells = caster.get_out_of_combat_spells(spells_data)

        if not available_spells:
            print_error(f"{caster.name} doesn't have any spells available for casting outside combat.")
            return

        # 2. Select spell
        print_section(f"{caster.name}'s Available Spells")

        # Build spell choices
        spell_choices = []
        for spell_id, spell_data in available_spells:
            spell_name = spell_data.get("name", spell_id)
            spell_level = spell_data.get("level", 0)

            # Show slot information
            if spell_level == 0:
                slot_info = "[green](cantrip)[/green]"
            else:
                available_slots = caster.get_available_spell_slots(spell_level)
                slot_info = f"[cyan](level {spell_level}, {available_slots} slots)[/cyan]"

            # Show spell type (healing, ritual, utility)
            spell_types = []
            if spell_data.get("healing"):
                healing_dice = spell_data["healing"].get("dice", "")
                spell_types.append(f"healing: {healing_dice}")
            if spell_data.get("ritual"):
                spell_types.append("ritual")
            if not spell_types:
                spell_types.append("utility")

            type_info = ", ".join(spell_types)
            choice_text = f"{spell_name} {slot_info} - {type_info}"
            spell_choices.append(questionary.Choice(title=choice_text, value=(spell_id, spell_data)))

        spell_choices.append(questionary.Choice(title="Cancel", value=None))

        try:
            selected = questionary.select(
                f"Select spell for {caster.name} to cast:",
                choices=spell_choices,
                use_arrow_keys=True
            ).ask()

            if not selected:
                return  # User cancelled

            spell_id, spell_data = selected
        except (EOFError, KeyboardInterrupt):
            return

        # 3. Select target if needed (for healing spells)
        target_name = None
        if spell_data.get("healing"):
            target = self._prompt_party_member_selection(
                f"Who should {caster.name} heal with {spell_data.get('name')}?"
            )
            if not target:
                return  # User cancelled
            target_name = target.name

        # 4. Cast the spell
        result = self.game_state.cast_spell_exploration(
            caster_name=caster.name,
            spell_id=spell_id,
            target_name=target_name
        )

        # 5. Display result
        print_section("Spell Cast")

        if result["success"]:
            spell_name = result.get("spell_name", "spell")

            if "healing_amount" in result:
                # Healing spell
                healing = result["healing_amount"]
                target = result.get("target", "target")
                print_status_message(
                    f"✨ {caster.name} casts {spell_name} on {target}, healing {healing} HP!",
                    "success"
                )
            else:
                # Utility spell
                print_status_message(f"✨ {caster.name} casts {spell_name}!", "success")
                description = result.get("description", "")
                if description:
                    print_message(f"\n{description}")

            # Show spell slot consumption
            spell_level = result.get("spell_level", 0)
            if spell_level > 0:
                remaining_slots = caster.get_available_spell_slots(spell_level)
                print_message(f"\nLevel {spell_level} spell slots remaining: {remaining_slots}")
        else:
            error_msg = result.get("error", "Failed to cast spell")
            print_error(f"❌ {error_msg}")

    def _prompt_party_member_selection(self, prompt_message: str) -> Optional[Character]:
        """
        Prompt user to select a party member.

        Args:
            prompt_message: Message to display in the prompt

        Returns:
            Selected Character or None if cancelled
        """
        import questionary

        # Build choices for party members
        choices = []
        for character in self.game_state.party.characters:
            if character.is_alive:
                hp_pct = character.current_hp / character.max_hp if character.max_hp > 0 else 0

                # HP indicator
                if hp_pct >= 0.9:
                    hp_indicator = "●●●"
                elif hp_pct >= 0.5:
                    hp_indicator = "●●○"
                elif hp_pct > 0:
                    hp_indicator = "●○○"
                else:
                    hp_indicator = "○○○"

                choice_text = f"{character.name} (HP: {character.current_hp}/{character.max_hp} {hp_indicator})"
                choices.append(questionary.Choice(title=choice_text, value=character))

        if not choices:
            from dnd_engine.ui.rich_ui import print_error
            print_error("No party members available!")
            return None

        # Add cancel option
        choices.append(questionary.Choice(title="Cancel", value=None))

        # Get user selection
        try:
            result = questionary.select(
                prompt_message,
                choices=choices,
                use_arrow_keys=True
            ).ask()

            return result
        except (EOFError, KeyboardInterrupt):
            return None

    def handle_reset(self, command: str) -> None:
        """
        Handle reset command to restart the campaign.

        Supports:
        - 'reset': Reset current dungeon with same party
        - 'reset --dungeon <name>': Switch to different dungeon
        """
        # Parse command for options
        parts = command.split()
        dungeon_name = None
        reset_hp = True
        reset_conditions = True

        # Check for --dungeon option
        if len(parts) > 1 and parts[1] == "--dungeon" and len(parts) > 2:
            dungeon_name = parts[2]

        print_section("Reset Campaign")
        print_message("This will restart the campaign with your current party intact")
        print_message("Your characters will retain their level, XP, and equipment")

        # Show current state
        print_section("Current Status")
        print_message(f"Dungeon: {self.game_state.dungeon_name}")
        print_message(f"Party size: {len(self.game_state.party.characters)}")

        if dungeon_name:
            print_message(f"\nWill reset to: {dungeon_name}")

        # Ask for confirmation
        print_message("")
        confirm = input("Confirm reset? (y/n): ").strip().lower()

        if confirm != "y":
            print_status_message("Reset cancelled", "warning")
            return

        try:
            # Reset dungeon (optionally to a new one)
            self.game_state.reset_dungeon(dungeon_name)

            # Reset party HP (to reflect fresh start)
            self.game_state.reset_party_hp()

            # Reset party conditions
            self.game_state.reset_party_conditions()

            # Save the reset game state if save_manager is available
            if hasattr(self.game_state, 'save_manager'):
                try:
                    self.game_state.save_manager.save_game(
                        self.game_state,
                        "reset_autosave",
                        auto_save=True
                    )
                except Exception as e:
                    # Log but don't fail on autosave error
                    print_status_message(f"Note: Autosave failed ({e})", "warning")

            # Display success message
            print_status_message("Campaign reset successfully!", "success")
            print_message(f"Returned to dungeon entrance in {self.game_state.dungeon_name}")

            # Display the new room
            self.display_room()

        except Exception as e:
            print_error(f"Failed to reset campaign: {e}")

    def display_help_exploration(self) -> None:
        """Display help for exploration commands."""
        commands = [
            ("north/n, south/s, east/e, west/w", "Move in a direction (shorthand)"),
            ("move/go <direction>", "Move in a direction (e.g., 'go north')"),
            ("look or l", "Look around the current room"),
            ("examine / x [target]", "Examine objects or listen at doors (e.g., 'examine corpse')"),
            ("search", "Search the room for items"),
            ("take/get/pickup <item>", "Pick up an item (e.g., 'take dagger', 'get gold')"),
            ("inventory / i [filter]", "Show inventory. Filter: summary, player name/number, or item type"),
            ("equip <item> [on <player>]", "Equip weapon/armor (e.g., 'equip sword on 2')"),
            ("unequip <slot> [on <player>]", "Unequip weapon/armor (e.g., 'unequip weapon on gandalf')"),
            ("use <item> [on <player>]", "Use consumable (e.g., 'use potion on 2')"),
            ("status", "Show your character status"),
            ("rest", "Take a short or long rest"),
            ("cast", "Cast healing or utility spells outside combat"),
            ("save", "Create a named save"),
            ("qs / quicksave", "Quick-save"),
            ("help or ?", "Show this help message"),
            ("quit / exit", "Exit the game"),
        ]
        print_help_section("Exploration Commands", commands)

        # Show debug mode hint if enabled
        if self.debug_console.enabled:
            debug_commands = [
                ("/help", "Show debug console commands (character, combat, inventory manipulation)"),
                ("/reset", "Reset campaign with same party"),
            ]
            print_help_section("Debug Commands", debug_commands)

    def display_help_combat(self) -> None:
        """Display help for combat commands."""
        commands = [
            ("attack <enemy>", "Attack an enemy (e.g., 'attack goblin 1' or 'attack 1')"),
            ("cast <spell>", "Cast a spell (e.g., 'cast magic missile')"),
            ("use <item>", "Use a consumable item (e.g., 'use potion') - costs an action"),
            ("stabilize <ally>", "Stabilize an unconscious ally (Medicine DC 10)"),
            ("flee / run / escape", "Flee from combat (enemies get opportunity attacks)"),
            ("status", "Show combat status"),
            ("help or ?", "Show this help message"),
            ("quit / exit", "Exit the game"),
        ]
        print_help_section("Combat Commands", commands)

    def run(self) -> None:
        """Run the main game loop."""
        self.display_banner()
        self.display_room()
        self.display_player_status()

        # Start the game (GameState handles checking starting room for enemies)
        self.game_state.start()

        print_status_message("Type 'help' for available commands", "info")

        while self.running and not self.game_state.is_game_over():
            if self.game_state.in_combat:
                # Only show full combat status at start of combat or when explicitly requested
                if not self.combat_status_shown:
                    self.display_combat_status()
                    self.combat_status_shown = True

                current = self.game_state.initiative_tracker.get_current_combatant()

                # Check if current combatant is dead - skip if truly dead
                # For Characters, check is_dead (3 death save failures)
                # For other creatures, check is_alive
                should_skip = False
                if hasattr(current.creature, 'is_dead'):
                    # Character: skip only if dead (3 failures), not if unconscious
                    should_skip = current.creature.is_dead
                else:
                    # Regular creature: skip if not alive
                    should_skip = not current.creature.is_alive

                if should_skip:
                    self.game_state.initiative_tracker.next_turn()
                    continue

                # Check if it's a party member's turn
                is_party_turn = False
                party_character = None
                for character in self.game_state.party.characters:
                    if current.creature == character:
                        is_party_turn = True
                        party_character = character
                        break

                if is_party_turn:
                    # Check if character is unconscious and needs death save
                    if party_character.is_unconscious:
                        self.process_death_save_turn(party_character)
                        # Advance turn after death save
                        self.game_state.initiative_tracker.next_turn()
                        # Check if combat is over
                        self.game_state._check_combat_end()
                    else:
                        # Normal turn for conscious character
                        # Process turn-start effects (e.g., ongoing fire damage)
                        self._process_turn_start_effects(party_character)

                        # Check if character died from turn-start effects
                        if not party_character.is_alive:
                            print_error(f"{party_character.name} has died from turn-start effects!")
                            self.game_state.initiative_tracker.next_turn()
                            continue

                        # Prompt for condition removal (may consume action)
                        self._prompt_condition_removal(party_character)

                        # Show compact turn status instead of full table
                        self.display_turn_status(is_party_turn, current.creature)
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
        """Handle combat start event.

        Note: Combat start narrative is now integrated into the room description
        when entering a room with enemies. This handler only displays functional
        UI elements (combat warning, enemy list).
        """
        # Clear combat history for new combat
        self.combat_history = []

        # Assign numbers to enemies for this combat
        self._assign_enemy_numbers()

        # Build numbered enemy list for display
        numbered_enemies = []
        for enemy in self.game_state.active_enemies:
            enemy_num = self._get_enemy_number(enemy)
            display_name = f"{enemy.name} {enemy_num}" if enemy_num else enemy.name
            numbered_enemies.append(display_name)

        # Display combat warning (no separate narrative - it's in room description)
        print_status_message(f"Combat begins! Enemies: {', '.join(numbered_enemies)}", "warning")

        # Reset combat status flag for new combat
        self.combat_status_shown = False

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
        # Clear enemy numbers when combat ends
        self.enemy_numbers.clear()

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

        # Reset combat status flag
        self.combat_status_shown = False

        # Auto-save after combat
        self._auto_save("after_combat")

    def _on_combat_fled(self, event: Event) -> None:
        """Handle combat fled event."""
        # Clear enemy numbers when fleeing combat
        self.enemy_numbers.clear()

        # Log flee event
        from dnd_engine.utils.logging_config import get_logging_config
        logging_config = get_logging_config()
        if logging_config:
            num_attacks = event.data.get("opportunity_attacks", 0)
            casualties = event.data.get("casualties", [])
            surviving = event.data.get("surviving_party", [])
            logging_config.log_combat_event(
                f"Party fled combat - Opportunity attacks: {num_attacks}, "
                f"Casualties: {len(casualties)}, Survivors: {len(surviving)}"
            )

        # Reset combat status flag
        self.combat_status_shown = False

        # Auto-save after fleeing
        self._auto_save("after_flee")

    def _on_item_acquired(self, event: Event) -> None:
        """Handle item acquired event."""
        # Events are already displayed during search, so we can pass
        pass

    def _on_gold_acquired(self, event: Event) -> None:
        """Handle gold acquired event."""
        # Events are already displayed during search, so we can pass
        pass

    def _on_level_up(self, event: Event) -> None:
        """Handle level-up event."""
        char_name = event.data["character"]
        new_level = event.data["new_level"]
        hp_increase = event.data["hp_increase"]

        print_section(f"🎉 LEVEL UP!")
        print_status_message(f"{char_name} reached level {new_level}!", "success")
        print_message(f"❤️  HP increased by {hp_increase}")

        # Auto-save after level-up
        self._auto_save("level_up")

    def _on_feature_granted(self, event: Event) -> None:
        """Handle feature granted event."""
        char_name = event.data["character"]
        feature = event.data["feature"]

        print_status_message(f"✨ {char_name} learned: {feature}", "info")

    def _on_room_enter(self, event: Event) -> None:
        """Handle room enter event."""
        # Auto-save when entering a new room
        self._auto_save("room_change")

    def _on_long_rest(self, event: Event) -> None:
        """Handle long rest event."""
        # Auto-save after long rest
        self._auto_save("long_rest")

    def _on_skill_check(self, event: Event) -> None:
        """Handle skill check event for display."""
        data = event.data

        if data.get("passive"):
            # Passive check (e.g., Passive Perception)
            if data["success"]:
                print_status_message(
                    f"🔍 {data['character']} (Passive Perception {data['total']}): {data['success_text']}",
                    "success"
                )
        else:
            # Active check
            result_text = "✓ SUCCESS" if data["success"] else "✗ FAILURE"
            color = "success" if data["success"] else "error"

            print_status_message(
                f"🎲 {data['character']} {data['skill'].title()} check (DC {data['dc']}): "
                f"rolled {data['roll']} + {data['modifier']} = {data['total']} - {result_text}",
                color
            )

            # Display result text
            if data["success"] and data.get("success_text"):
                print_status_message(f"   → {data['success_text']}", "info")
            elif not data["success"] and data.get("failure_text"):
                print_status_message(f"   → {data['failure_text']}", "info")

    def _auto_save(self, trigger: str) -> None:
        """
        Perform an auto-save using CampaignManager.

        Args:
            trigger: What triggered the auto-save (for logging)
        """
        if not self.auto_save_enabled:
            return

        if not self.campaign_manager or not self.campaign_name:
            return

        try:
            # Show saving indicator
            with console.status("[cyan]Saving...[/cyan]", spinner="dots"):
                self.campaign_manager.save_campaign_state(
                    campaign_name=self.campaign_name,
                    game_state=self.game_state,
                    slot_name="auto",
                    save_type="auto"
                )
            # Brief success message
            print_status_message("✓ Saved", "success")
        except Exception:
            # Silently fail auto-save to avoid disrupting gameplay
            pass
