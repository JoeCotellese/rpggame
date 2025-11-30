# ABOUTME: Command-line interface for the D&D 5E terminal game
# ABOUTME: Handles player input, displays game state, and manages the game loop

from typing import Any, Optional

from rich.panel import Panel

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.dice import format_dice_with_modifier
from dnd_engine.core.game_state import (
    CombatEvent,
    CombatSpellResult,
    EnemyTurnAction,
    EnemyTurnResult,
    GameState,
    PlayerAttackResult,
    StabilizeResult,
)
from dnd_engine.llm.npc_chat import NPCChatManager
from dnd_engine.systems.action_economy import ActionType
from dnd_engine.systems.ai import EnemyAI
from dnd_engine.systems.combat_context import CombatContextBuilder
from dnd_engine.systems.combat_middleware import (
    ActionResult,
    CombatActionContext,
    CombatActionExecutor,
)
from dnd_engine.systems.condition_manager import ConditionManager
from dnd_engine.systems.inventory import EquipmentSlot
from dnd_engine.systems.item_assignment import ItemAssignmentService
from dnd_engine.systems.targeting import (
    ValidTargets,
    get_item_targeting_requirements,
    get_spell_targeting_requirements,
)
from dnd_engine.ui.shop_ui import ShopUI
from dnd_engine.ui.debug_console import DebugConsole
from dnd_engine.ui.rich_ui import (
    console,
    create_combat_table,
    create_inventory_table,
    create_party_status_table,
    print_error,
    print_help_section,
    print_mechanics_panel,
    print_message,
    print_room_description,
    print_section,
    print_status_message,
    print_title,
)
from dnd_engine.utils.events import Event, EventType


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

        # NPC chat manager for LLM-powered conversations
        self.npc_chat_manager: NPCChatManager | None = None
        if llm_enhancer and llm_enhancer.provider:
            self.npc_chat_manager = NPCChatManager(
                provider=llm_enhancer.provider,
                game_state=game_state
            )

        # Condition manager for handling status effects
        self.condition_manager = ConditionManager(
            dice_roller=game_state.dice_roller,
            event_bus=game_state.event_bus
        )

        # Enemy AI for combat decisions
        self.enemy_ai = EnemyAI()

        # Item assignment service for intelligent item distribution
        self.item_assignment = ItemAssignmentService()

        # Combat context builder for assembling narrative context
        self.context_builder = CombatContextBuilder(game_state.data_loader, game_state)

        # Combat action executor for middleware-based action handling
        self.action_executor = CombatActionExecutor(game_state)

        # Combat display management
        self.combat_status_shown = False

        # Debug console for testing and development
        self.debug_console = DebugConsole(game_state, cli=self)

        # Subscribe to game events for display and auto-save
        self.game_state.event_bus.subscribe(EventType.COMBAT_START, self._on_combat_start)
        self.game_state.event_bus.subscribe(EventType.COMBAT_END, self._on_combat_end)
        self.game_state.event_bus.subscribe(EventType.COMBAT_FLED, self._on_combat_fled)
        self.game_state.event_bus.subscribe(EventType.BOSS_DEFEATED, self._on_boss_defeated)
        self.game_state.event_bus.subscribe(EventType.DUNGEON_COMPLETED, self._on_dungeon_completed)
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
        # Get all room context from game engine
        context = self.game_state.get_room_display_context()

        # Try to get enhanced description from LLM
        enhanced_desc = None
        if self.llm_enhancer:
            with console.status("", spinner="dots"):
                enhanced_desc = self.llm_enhancer.get_room_description_sync(
                    context.to_llm_dict(), timeout=20.0
                )

        # Use enhanced description if available, otherwise use basic
        room_text = enhanced_desc if enhanced_desc else context.description

        # Display room description
        print_room_description(context.room_name, room_text, context.exits)

        # Show visible items in the room
        if context.visible_items and not context.room_searched:
            print_status_message("\nYou notice:", "info")
            for item in context.visible_items:
                if item.item_type == "gold":
                    print_status_message(f"  • {item.amount} gold pieces", "info")
                elif item.item_type == "currency":
                    currency_parts = []
                    if item.gold > 0:
                        currency_parts.append(f"{item.gold} gold")
                    if item.silver > 0:
                        currency_parts.append(f"{item.silver} silver")
                    if item.copper > 0:
                        currency_parts.append(f"{item.copper} copper")
                    if item.platinum > 0:
                        currency_parts.append(f"{item.platinum} platinum")
                    print_status_message(f"  • {', '.join(currency_parts)}", "info")
                else:
                    print_status_message(f"  • {item.item_name}", "info")
            print_status_message("Use 'take <item>' or 'take all' to pick up items.", "info")

        # Show NPCs in the room
        if context.npc_display_names:
            print_status_message("\nYou see:", "info")
            for npc_name in context.npc_display_names:
                print_status_message(f"  • {npc_name}", "info")
            print_status_message("Use 'talk <name>' to start a conversation.", "info")

        # Mark room as displayed so subsequent "look" commands show "already in room" narrative
        self.game_state.mark_room_displayed()

    def display_player_status(self) -> None:
        """Display status for all party members."""
        # Convert party data to table format
        party_data = []
        for char in self.game_state.party.characters:
            # Get active effects for this character
            active_effects = self.game_state.time_manager.get_effects_for_character(char.name)

            # Get effective AC (includes modifiers from spells/effects)
            effective_ac = self.game_state.get_effective_ac(char)

            party_data.append({
                "name": char.name,
                "class": char.character_class.value.capitalize(),
                "level": char.level,
                "hp": char.current_hp,
                "max_hp": char.max_hp,
                "ac": effective_ac,
                "xp": char.xp,
                "active_effects": active_effects,
                "spell_slots": char.get_spell_slots_display() if char.has_spell_slots() else None,
                "is_dead": char.is_dead,
                "conditions": char.active_conditions
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

            # Use display_name from InitiativeEntry (already has enemy numbers)
            display_name = entry.display_name if entry.display_name else entry.creature.name

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

            # Add conditions if present
            if hasattr(entry.creature, 'active_conditions'):
                combatant_data["conditions"] = list(entry.creature.active_conditions.keys())

            # Add concentration information for players
            if is_player:
                concentration_spell = self.game_state.get_concentration_spell(entry.creature.name)
                if concentration_spell:
                    combatant_data["concentration"] = concentration_spell

            # Add active effects for all combatants
            active_effects = self.game_state.time_manager.get_effects_for_character(entry.creature.name)
            if active_effects:
                combatant_data["active_effects"] = active_effects

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

            # Build status line
            status_parts = [
                f"[bold]{char.name}'s turn![/bold]",
                f"HP: [{hp_color}]{char.current_hp}/{char.max_hp}[/{hp_color}]"
            ]

            # Add spell slots for spellcasters
            if char.has_spell_slots():
                spell_slots_display = char.get_spell_slots_display()
                if spell_slots_display:
                    status_parts.append(f"Slots: [cyan]{spell_slots_display}[/cyan]")

            status_parts.append(f"Enemies: {enemies_str}")

            console.print(Panel(
                " | ".join(status_parts),
                border_style="yellow",
                padding=(0, 1)
            ))
        # No display for enemy turns - the action will print itself

    def _build_battlefield_state(self) -> dict[str, Any]:
        """
        Build current battlefield state for LLM context.

        Returns:
            Dict with party_hp and enemy_hp lists
        """
        # Use new GameState API for battlefield state
        battlefield = self.game_state.get_battlefield_state()

        party_hp = [
            (combatant.name, combatant.current_hp, combatant.max_hp)
            for combatant in battlefield.party_combatants
        ]

        enemy_hp = [
            (combatant.display_name, combatant.current_hp, combatant.max_hp)
            for combatant in battlefield.enemy_combatants
            if combatant.is_alive
        ]

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
        import time

        # Determine event type and description
        if result.hit:
            event_type = "attack"
            if result.critical_hit:
                description = f"{result.attacker_name} CRITICALLY hit {result.defender_name} for {result.damage} damage"
            else:
                description = f"{result.attacker_name} hit {result.defender_name} for {result.damage} damage"
        else:
            event_type = "miss"
            description = f"{result.attacker_name} missed {result.defender_name}"

        # Use new GameState API for recording combat events
        event = CombatEvent(
            timestamp=time.time(),
            event_type=event_type,
            attacker=result.attacker_name,
            defender=result.defender_name,
            damage=result.damage if result.hit else 0,
            critical=result.critical_hit if result.hit else False,
            description=description
        )
        self.game_state.record_combat_event(event)

    def _get_combat_history_for_llm(self) -> list[str]:
        """
        Get combat history formatted for LLM context.

        Returns:
            List of combat action descriptions
        """
        events = self.game_state.get_recent_combat_history(count=12)
        return [event.description for event in events]

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

    def _get_status_bar(self):
        """Build the status bar content for the bottom toolbar."""
        from prompt_toolkit.formatted_text import HTML

        # Get current location
        room = self.game_state.get_current_room()
        room_name = room.get("name", "Unknown")
        dungeon = self.game_state.dungeon
        location_name = dungeon.get("name", "Unknown") if dungeon else "Unknown"

        # Get effective lighting (best among party members)
        best_lighting = "dark"
        for char in self.game_state.party.characters:
            lighting = self.game_state.get_effective_lighting(char)
            if lighting == "bright":
                best_lighting = "bright"
                break
            elif lighting == "dim":
                best_lighting = "dim"

        # Format lighting with icon and color
        lighting_display = {
            "bright": ("☀️", "yellow", "Bright"),
            "dim": ("🌙", "orange", "Dim"),
            "dark": ("⚫", "red", "Dark")
        }
        icon, color, label = lighting_display.get(best_lighting, ("?", "white", "Unknown"))

        return HTML(
            f'<style fg="cyan">{location_name}</style>'
            f' <style fg="white">│</style> '
            f'<style fg="white">{room_name}</style>'
            f' <style fg="white">│</style> '
            f'<style fg="{color}">{icon} {label}</style>'
        )

    def get_player_command(self) -> str:
        """
        Get a command from the player with history support.

        Returns:
            Player's command as a string
        """
        try:
            from pathlib import Path

            from prompt_toolkit import prompt
            from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
            from prompt_toolkit.history import FileHistory

            # Store history in user's home directory
            history_file = Path.home() / ".dnd_game_history"

            return prompt(
                "\n> ",
                history=FileHistory(str(history_file)),
                auto_suggest=AutoSuggestFromHistory(),
                bottom_toolbar=self._get_status_bar,
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
            "northeast": "northeast", "ne": "northeast",
            "northwest": "northwest", "nw": "northwest",
            "southeast": "southeast", "se": "southeast",
            "southwest": "southwest", "sw": "southwest",
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

        if command in ["spells"]:
            self.handle_spells()
            return

        if command in ["prepare"]:
            self.handle_prepare_spells()
            return

        if command in ["time"]:
            self.handle_time()
            return

        if command in ["effects"]:
            self.handle_effects()
            return

        if command in ["take", "get", "pickup"]:
            # Prompt for multi-item selection with checkboxes
            items_to_take = self._prompt_multi_items_to_take()
            if not items_to_take:
                return  # User cancelled or no items selected

            # Take each selected item
            for item_to_take in items_to_take:
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
                # Handle "take all" command
                if item_name.lower() in ["all", "everything"]:
                    self.handle_take_all()
                else:
                    self.handle_take(item_name)
            else:
                print_error("Specify an item to take. Example: 'take dagger'")
            return

        if command == "talk" or command.startswith("talk "):
            parts = command.split()[1:]
            if not parts:
                self.handle_talk_menu()
            else:
                npc_name = " ".join(parts)
                self.handle_talk(npc_name)
            return

        if command == "shop" or command.startswith("shop "):
            parts = command.split()[1:]
            if not parts:
                self.handle_shop_menu()
            else:
                npc_name = " ".join(parts)
                self.handle_shop(npc_name)
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
            target_name = self._get_enemy_display_name(target)

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

        if command in ["spells"]:
            self.handle_spells()
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

                # Get targeting requirements from game engine (not interpreting data directly)
                targeting = get_item_targeting_requirements(item_data)

                if targeting.valid_targets == ValidTargets.ANY:
                    # Prompt for target selection (allies within range)
                    target = self._prompt_combat_ally_selection(item_name, item_data, character)
                    if not isinstance(target, Character):
                        return  # User cancelled or invalid selection
                    self.handle_use_item_combat_with_target(item_id, item_data, character, target)
                elif targeting.valid_targets == ValidTargets.ENEMY:
                    # Prompt for enemy target selection
                    target = self._prompt_enemy_selection()
                    if target is None or target == "Cancel":
                        return  # User cancelled
                    self.handle_use_item_combat_attack(item_id, item_data, character, target)
                else:
                    # Self-target only (SELF or default)
                    target = character
                    self.handle_use_item_combat_with_target(item_id, item_data, character, target)
                return

            # Parse item and optional target from command
            # Supports: "use potion", "use potion Tim", "use potion on Tim"
            item_id, player_id = self._parse_command_with_target(parts)

            if not item_id:
                print_error("Specify an item to use.")
                return

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
            items_data = self.game_state.data_loader.load_items()

            # Search for the item in the character's inventory
            consumables = character.inventory.get_items_by_category("consumables")
            found_item = None
            found_item_data = None

            for inv_item in consumables:
                item_data = items_data["consumables"].get(inv_item.item_id, {})
                if inv_item.item_id == item_id or item_data.get("name", "").lower() == item_id.lower():
                    found_item = inv_item.item_id
                    found_item_data = item_data
                    break

            if not found_item or not found_item_data:
                print_error(f"{character.name} doesn't have a consumable '{item_id}' in inventory.")
                return

            # Get targeting requirements from game engine (not interpreting data directly)
            targeting = get_item_targeting_requirements(found_item_data)

            if player_id:
                # Player specified a target - validate it
                if targeting.valid_targets == ValidTargets.ENEMY:
                    print_error(f"{found_item_data.get('name', found_item)} must target an enemy. Use the enemy name or number.")
                    return

                # Parse the target (allow unconscious for healing items)
                target = self._get_target_player(player_id, allow_unconscious=True)
                if not target:
                    return

                # Use item on specified target
                self.handle_use_item_combat_with_target(found_item, found_item_data, character, target)
            elif targeting.valid_targets == ValidTargets.ENEMY:
                # Item requires enemy target but none specified
                print_error(f"{found_item_data.get('name', found_item)} requires an enemy target. Specify the target (e.g., 'use {item_id} skeleton 1')")
                return
            elif targeting.valid_targets == ValidTargets.ANY:
                # Item can target anyone but no target specified - default to self
                self.handle_use_item_combat_with_target(found_item, found_item_data, character, character)
            else:
                # Self-target only
                self.handle_use_item_combat_with_target(found_item, found_item_data, character, character)
            return

        if command in ["end turn", "end", "done", "pass", "skip"]:
            self.handle_end_turn()
            return

        # Provide helpful suggestions for unknown commands
        print_status_message("Unknown combat command.", "warning")
        living_enemies = []
        for enemy in self.game_state.active_enemies:
            if enemy.is_alive:
                display_name = self._get_enemy_display_name(enemy)
                living_enemies.append(display_name)
        if living_enemies:
            print_status_message(f"Try: 'attack {living_enemies[0].lower()}' or 'help' for more commands", "info")

    def handle_move(self, direction: str) -> None:
        """Handle movement command."""
        if not direction:
            # Show available exits (filtered by requirements)
            exits = self.game_state.get_available_exits()
            if exits:
                print_status_message(
                    f"Specify a direction. Available exits: {', '.join(exits)}",
                    "warning"
                )
            else:
                print_status_message("No exits available from this room.", "warning")
            return

        # Check if exit is locked before attempting move
        if self.game_state.is_exit_locked(direction):
            self.handle_unlock(direction)
            return

        # Check if exit requirements are met (quest items, etc.)
        req_check = self.game_state.check_exit_requirements(direction)
        if not req_check["met"]:
            for reason in req_check["missing"]:
                print_error(reason)
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
                exits = self.game_state.get_available_exits()
                if exits:
                    print_error(
                        f"You cannot go {direction} from here. "
                        f"Available exits: {', '.join(exits)}"
                    )
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

        # Build choices for questionary
        import questionary

        choices = []
        for idx, method in enumerate(unlock_methods):
            desc = method.get("description", "unknown method")
            if "skill" in method:
                skill = method["skill"]
                dc = method["dc"]
                tool_req = ""
                if "tool_proficiency" in method:
                    tool_req = f" + {method['tool_proficiency'].replace('_', ' ').title()}"
                choice_text = f"{desc.capitalize()} ({skill}{tool_req} DC {dc})"
            elif "requires_item" in method:
                choice_text = f"{desc.capitalize()} (requires {method['requires_item']})"
            else:
                choice_text = desc.capitalize()

            choices.append(questionary.Choice(title=choice_text, value=idx))

        # Add cancel option
        choices.append(questionary.Choice(title="Cancel", value=None))

        # Prompt for method selection
        try:
            method_index = questionary.select(
                "Choose an unlock method:",
                choices=choices,
                use_arrow_keys=True
            ).ask()

            # questionary may return "Cancel" string or None when user cancels
            if method_index is None or method_index == "Cancel":
                print_status_message("Cancelled.", "warning")
                return

        except (EOFError, KeyboardInterrupt):
            print_status_message("Cancelled.", "warning")
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
                print_error("Failed! The door remains locked. You can try again.")

    def _prompt_character_for_unlock(self, method: dict) -> Character | None:
        """
        Prompt player to select which character attempts the unlock.

        Args:
            method: The unlock method being used

        Returns:
            Selected Character or None if cancelled
        """
        import questionary

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

        # Build character list with metadata for sorting
        living_chars = [c for c in self.game_state.party.characters if c.is_alive]
        char_data = []
        for char in living_chars:
            # Get skill modifier
            skill_mod = char.get_skill_modifier(skill, skills_data)

            # Check tool proficiency
            has_tool_prof = False
            tool_prof_str = ""
            if tool_proficiency:
                has_tool_prof = hasattr(char, 'tool_proficiencies') and tool_proficiency in char.tool_proficiencies
                if has_tool_prof:
                    # Tool proficiency adds proficiency bonus
                    tool_bonus = char.proficiency_bonus if hasattr(char, 'proficiency_bonus') else 2
                    tool_prof_str = f", {tool_proficiency.replace('_', ' ').title()} +{tool_bonus}"
                else:
                    tool_prof_str = f" (no {tool_proficiency.replace('_', ' ').title()})"

            char_data.append({
                'character': char,
                'skill_mod': skill_mod,
                'has_tool_prof': has_tool_prof,
                'display': f"{char.name} - {skill.upper()} +{skill_mod}{tool_prof_str}"
            })

        # Sort by tool proficiency (desc) then skill modifier (desc)
        char_data.sort(key=lambda x: (not x['has_tool_prof'], -x['skill_mod']))

        # Build choices for questionary
        choices = []
        for data in char_data:
            choices.append(questionary.Choice(title=data['display'], value=data['character']))

        # Add cancel option
        choices.append(questionary.Choice(title="Cancel", value=None))

        # Prompt for selection
        try:
            result = questionary.select(
                header,
                choices=choices,
                use_arrow_keys=True
            ).ask()

            # questionary may return "Cancel" string or None when user cancels
            if result is None or result == "Cancel":
                print_status_message("Cancelled.", "warning")
                return None

            return result

        except (EOFError, KeyboardInterrupt):
            print_status_message("Cancelled.", "warning")
            return None

    def _prompt_character_for_skill_check(
        self,
        action_desc: str,
        skill: str,
        dc: int
    ) -> Character | None:
        """
        Prompt player to select a character for a skill check, sorted by modifier.

        Characters are sorted by their skill modifier (highest first) to help
        players make informed decisions.

        Args:
            action_desc: Description of the action (e.g., "examine the murals")
            skill: The skill being used (e.g., "religion", "investigation")
            dc: The difficulty class for the check

        Returns:
            Selected Character or None if cancelled
        """
        import questionary

        # Load skills data
        skills_data = self.game_state.data_loader.load_skills()

        # Build header
        header = f"Choose a character to {action_desc} ({skill.upper()} DC {dc}):"

        # Build character list with skill modifiers
        living_chars = [c for c in self.game_state.party.characters if c.is_alive]
        char_data = []

        for char in living_chars:
            # Get skill modifier
            skill_mod = char.get_skill_modifier(skill, skills_data)

            # Check for proficiency/expertise
            prof_str = ""
            if hasattr(char, 'skill_proficiencies') and skill.lower() in char.skill_proficiencies:
                if hasattr(char, 'skill_expertise') and skill.lower() in char.skill_expertise:
                    prof_str = " (Expertise)"
                else:
                    prof_str = " (Proficient)"

            # Format modifier with sign
            mod_sign = "+" if skill_mod >= 0 else ""
            display = f"{char.name} - {skill.upper()} {mod_sign}{skill_mod}{prof_str}"

            char_data.append({
                'character': char,
                'skill_mod': skill_mod,
                'display': display
            })

        # Sort by skill modifier (highest first)
        char_data.sort(key=lambda x: -x['skill_mod'])

        # Build choices for questionary
        choices = []
        for data in char_data:
            choices.append(questionary.Choice(title=data['display'], value=data['character']))

        # Add cancel option
        choices.append(questionary.Choice(title="← Cancel", value=None))

        try:
            result = questionary.select(
                header,
                choices=choices,
                use_arrow_keys=True
            ).ask()

            if result is None:
                print_status_message("Cancelled.", "warning")
                return None

            return result

        except (EOFError, KeyboardInterrupt):
            print_status_message("Cancelled.", "warning")
            return None

    def handle_search(self) -> None:
        """Handle search command with optional skill checks."""
        room = self.game_state.get_current_room()

        # Check for visible items first
        visible_items = [item for item in room.get("items", []) if item.get("visible", False)]

        # Show visible items without requiring search
        if visible_items and not room.get("searched", False):
            print_status_message("You can see the following items:", "info")
            self._display_items_list(visible_items)

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
                hidden_items = result.get("hidden_items", [])
                if hidden_items:
                    print_status_message("\nYou discover hidden items:", "success")
                    self._prompt_and_take_items()
                elif result["items"]:
                    print_status_message("\nItems available:", "success")
                    self._prompt_and_take_items()
                else:
                    print_status_message("The search was successful but nothing new was found.", "info")
            else:
                # Failure message already shown by event handler
                if visible_items:
                    print_status_message("You didn't find anything hidden, but visible items remain.", "info")
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

            hidden_items = result.get("hidden_items", [])
            if result["success"]:
                if hidden_items:
                    print_status_message("You search the room and discover hidden items:", "success")
                    self._prompt_and_take_items()
                elif result["items"]:
                    print_status_message("You search the room. Items available:", "success")
                    self._prompt_and_take_items()
                else:
                    print_status_message("You find nothing of interest.", "info")
            else:
                print_status_message("You find nothing of interest.", "info")

    def _display_items_list(self, items: list, show_take_hint: bool = True) -> None:
        """Helper to display a list of items.

        Args:
            items: List of items to display
            show_take_hint: Whether to show the "Use 'take <item>'" hint
        """
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
        if show_take_hint:
            print_status_message("\nUse 'take <item>' to pick up items", "info")

    def _prompt_and_take_items(self) -> None:
        """Prompt user to select items to take using multi-select interface."""
        try:
            # Show multi-select menu directly
            items_to_take = self._prompt_multi_items_to_take()
            if not items_to_take:
                return  # User cancelled or no items selected

            # Take each selected item
            for item_to_take in items_to_take:
                # Determine item name based on type
                if item_to_take["type"] in ["gold", "currency"]:
                    item_name = "currency"
                else:
                    item_name = item_to_take.get("id", "")
                self.handle_take(item_name)

        except (EOFError, KeyboardInterrupt):
            print_status_message("\nCancelled.", "warning")

    def handle_examine_menu(self) -> None:
        """
        Show interactive questionary menu for examining objects/exits.

        Uses progressive disclosure:
        1. Select what to examine (with skill/DC info)
        2. Select who examines it (sorted by skill modifier)
        """
        import questionary

        objects = self.game_state.get_examinable_objects()
        exits = self.game_state.get_examinable_exits()

        if not objects and not exits:
            print_status_message("There's nothing to examine here.", "info")
            return

        # Build choices for questionary
        choices = []

        # Add objects with skill/DC info
        for obj in objects:
            examine_checks = obj.get("examine_checks", [])
            if examine_checks:
                # Show first check's skill and DC
                check = examine_checks[0]
                skill = check.get("skill", "").upper()
                dc = check.get("dc", 10)
                display = f"{obj['name']} ({skill} DC {dc})"
            else:
                display = obj['name']

            choices.append(questionary.Choice(
                title=display,
                value=("object", obj)
            ))

        # Add exits
        room = self.game_state.get_current_room()
        exits_data = room.get("exits", {})
        for direction in exits:
            exit_data = exits_data.get(direction, {})
            if isinstance(exit_data, dict):
                examine_checks = exit_data.get("examine_checks", [])
                if examine_checks:
                    check = examine_checks[0]
                    skill = check.get("skill", "").upper()
                    dc = check.get("dc", 10)
                    display = f"{direction.capitalize()} door ({skill} DC {dc})"
                elif exit_data.get("locked"):
                    display = f"{direction.capitalize()} door (locked)"
                else:
                    display = f"{direction.capitalize()} door"
            else:
                display = f"{direction.capitalize()} door"

            choices.append(questionary.Choice(
                title=display,
                value=("exit", direction)
            ))

        # Add cancel option
        choices.append(questionary.Choice(title="← Cancel", value=None))

        try:
            result = questionary.select(
                "What would you like to examine?",
                choices=choices,
                use_arrow_keys=True
            ).ask()

            if result is None:
                return

            item_type, item_data = result
            if item_type == "object":
                self._examine_object(item_data["id"], item_data)
            else:
                self._examine_exit(item_data)

        except (EOFError, KeyboardInterrupt):
            print_status_message("Cancelled.", "warning")

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

        Uses skill-sorted character selection when a skill check is required.

        Args:
            object_id: ID of the object
            obj_data: Object data dict
        """
        examine_checks = obj_data.get("examine_checks", [])

        if examine_checks:
            # Get skill and DC from first check
            check = examine_checks[0]
            skill = check.get("skill", "investigation")
            dc = check.get("dc", 10)

            # Use skill-sorted character selection
            character = self._prompt_character_for_skill_check(
                action_desc=f"examine the {obj_data['name']}",
                skill=skill,
                dc=dc
            )
        else:
            # No skill check - simple selection
            character = self._prompt_simple_character_selection(
                f"Who will examine the {obj_data['name']}?"
            )

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

        Uses skill-sorted character selection when a skill check is required.

        Args:
            direction: Direction of the exit
        """
        # Get exit data to check for skill requirements
        room = self.game_state.get_current_room()
        exits_data = room.get("exits", {})
        exit_data = exits_data.get(direction, {})

        examine_checks = []
        if isinstance(exit_data, dict):
            examine_checks = exit_data.get("examine_checks", [])

        if examine_checks:
            # Get skill and DC from first check
            check = examine_checks[0]
            skill = check.get("skill", "perception")
            dc = check.get("dc", 10)

            # Use skill-sorted character selection
            character = self._prompt_character_for_skill_check(
                action_desc=f"examine the {direction} door",
                skill=skill,
                dc=dc
            )
        else:
            # No skill check - simple selection
            character = self._prompt_simple_character_selection(
                f"Who will examine the {direction} exit?"
            )

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

    def _prompt_simple_character_selection(self, prompt: str = "Select character:") -> Character | None:
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

        # Find matching item with fuzzy matching support
        item_to_take = None
        from difflib import SequenceMatcher

        # First try exact match
        for item in available_items:
            if item["type"] == "gold" and item_name_lower in ["gold", "gold pieces", "gp"]:
                item_to_take = item
                break
            elif item["type"] == "currency" and item_name_lower in ["gold", "silver", "copper", "currency", "coins", "money"]:
                item_to_take = item
                break
            elif item["type"] == "item":
                item_id = item.get("id", "")
                # Match by ID or display name (exact match or contains)
                if (item_id.lower() == item_name_lower or
                    item_id.lower().replace("_", " ") == item_name_lower or
                    item_name_lower in item_id.lower().replace("_", " ")):
                    item_to_take = item
                    break

        # If no exact match, try fuzzy matching
        if not item_to_take:
            best_match = None
            best_ratio = 0.6  # Minimum similarity threshold

            for item in available_items:
                if item["type"] == "item":
                    item_id = item.get("id", "").lower().replace("_", " ")
                    ratio = SequenceMatcher(None, item_name_lower, item_id).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_match = item

            if best_match:
                item_to_take = best_match

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

    def handle_take_all(self) -> None:
        """
        Handle taking all items from the current room with intelligent distribution.
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

        living_members = self.game_state.party.get_living_members()
        if not living_members:
            print_error("No living party members to take items!")
            return

        # Separate currency from regular items
        currency_items = [item for item in available_items if item["type"] in ["gold", "currency"]]
        regular_items = [item for item in available_items if item["type"] == "item"]

        # Take all currency items (auto-distributed)
        for item in currency_items:
            self.game_state.take_item("currency", living_members[0])

        if currency_items:
            print_status_message("Collected all currency and split among the party.", "success")

        # For regular items, use intelligent assignment
        if regular_items:
            for item in regular_items:
                item_id = item.get("id", "unknown")

                # Auto-assign to best character or prompt if ambiguous
                assigned_character = self._auto_assign_item(item, living_members)

                if assigned_character:
                    success = self.game_state.take_item(item_id, assigned_character)
                    if success:
                        print_status_message(f"{assigned_character.name} picks up the {item_id}.", "success")
                    else:
                        print_error(f"Failed to pick up {item_id}.")

    def _auto_assign_item(self, item: dict[str, Any], living_members: list) -> Optional:
        """
        Intelligently assign an item to a character based on class and item type.

        Uses ItemAssignmentService for recommendation logic, then handles user
        interaction if needed.

        Args:
            item: The item to assign
            living_members: List of living party members

        Returns:
            The character to assign the item to, or None if cancelled
        """
        item_id = item.get("id", "")

        # Get recommendations from the item assignment service
        recommendations = self.item_assignment.get_recommended_recipients(
            item_id, living_members
        )

        # Check if we can auto-assign
        auto_recipient = self.item_assignment.should_auto_assign(recommendations)
        if auto_recipient:
            return auto_recipient

        # Multiple good matches or no clear match: prompt user
        import questionary

        choices = []
        for rec in recommendations:
            character = rec.character
            choice_text = f"{character.name} ({character.character_class.value.title()})"
            choices.append(questionary.Choice(title=choice_text, value=character))

        choices.append(questionary.Choice(title="Skip this item", value=None))

        try:
            result = questionary.select(
                f"Who should receive the {item_id}?",
                choices=choices,
                use_arrow_keys=True
            ).ask()

            return result
        except (EOFError, KeyboardInterrupt):
            return None

    def handle_talk_menu(self) -> None:
        """Show a menu of NPCs in the current room to talk to."""
        import questionary

        # Check if NPC manager is available
        if not self.game_state.npc_manager:
            print_error("No NPCs available in this campaign.")
            return

        # Get NPCs in current room
        current_room = self.game_state.get_current_room()
        room_id = current_room.get("id", "")
        npcs = self.game_state.npc_manager.get_npcs_in_room(room_id)

        if not npcs:
            print_status_message("There's no one here to talk to.", "info")
            return

        # Build choices
        choices = []
        for npc in npcs:
            choices.append(questionary.Choice(title=npc.display_name, value=npc))
        choices.append(questionary.Choice(title="Cancel", value=None))

        try:
            result = questionary.select(
                "Who do you want to talk to?",
                choices=choices,
                use_arrow_keys=True
            ).ask()

            if result is None:
                print_status_message("Cancelled.", "warning")
                return

            self._run_chat_loop(result)
        except (EOFError, KeyboardInterrupt):
            print_status_message("Cancelled.", "warning")

    def handle_talk(self, npc_name: str) -> None:
        """
        Start a conversation with a specific NPC.

        Args:
            npc_name: Name of the NPC to talk to
        """
        # Check if NPC manager is available
        if not self.game_state.npc_manager:
            print_error("No NPCs available in this campaign.")
            return

        # Get NPCs in current room
        current_room = self.game_state.get_current_room()
        room_id = current_room.get("id", "")
        npcs = self.game_state.npc_manager.get_npcs_in_room(room_id)

        if not npcs:
            print_status_message("There's no one here to talk to.", "info")
            return

        # Find matching NPC by name (fuzzy match)
        npc_name_lower = npc_name.lower()
        matched_npc = None

        # Try exact match first
        for npc in npcs:
            if npc.name.lower() == npc_name_lower or npc.display_name.lower() == npc_name_lower:
                matched_npc = npc
                break

        # Try partial match
        if not matched_npc:
            for npc in npcs:
                if npc_name_lower in npc.name.lower() or npc_name_lower in npc.display_name.lower():
                    matched_npc = npc
                    break

        if not matched_npc:
            print_error(f"'{npc_name}' is not here.")
            print_status_message("People here:", "info")
            for npc in npcs:
                print_status_message(f"  - {npc.display_name}", "info")
            return

        self._run_chat_loop(matched_npc)

    def _run_chat_loop(self, npc) -> None:
        """
        Run the interactive chat loop with an NPC.

        Args:
            npc: The NPC to converse with
        """
        from rich.console import Console
        from rich.panel import Panel

        console = Console()

        # Start conversation
        if self.npc_chat_manager:
            greeting = self.npc_chat_manager.start_conversation_sync(npc)
        else:
            greeting = npc.get_greeting()

        # Display greeting
        console.print()
        console.print(Panel(
            greeting or "...",
            title=f"[bold cyan]{npc.display_name}[/bold cyan]",
            border_style="cyan"
        ))

        # Chat loop
        while True:
            try:
                # Get player input
                player_input = console.input("\n[bold green]You:[/bold green] ").strip()

                if not player_input:
                    continue

                # Check for exit commands
                if player_input.lower() in ["bye", "goodbye", "leave", "farewell", "exit", "quit", "q"]:
                    if self.npc_chat_manager:
                        response, _ = self.npc_chat_manager.send_message_sync(player_input)
                        if response:
                            console.print()
                            console.print(Panel(
                                response,
                                title=f"[bold cyan]{npc.display_name}[/bold cyan]",
                                border_style="cyan"
                            ))
                        self.npc_chat_manager.end_conversation()
                    else:
                        farewell = npc.get_farewell()
                        console.print()
                        console.print(Panel(
                            farewell,
                            title=f"[bold cyan]{npc.display_name}[/bold cyan]",
                            border_style="cyan"
                        ))
                    console.print()
                    print_status_message("You end the conversation.", "info")
                    break

                # Get NPC response
                if self.npc_chat_manager:
                    response, ended = self.npc_chat_manager.send_message_sync(player_input)

                    # Check if shop UI was requested
                    if self.npc_chat_manager.shop_requested:
                        self.npc_chat_manager.shop_requested = False  # Reset flag
                        if response:
                            console.print()
                            console.print(Panel(
                                response,
                                title=f"[bold cyan]{npc.display_name}[/bold cyan]",
                                border_style="cyan"
                            ))
                        # Open shop UI
                        self._open_shop(npc)
                        continue  # Return to conversation after shopping
                else:
                    response = "Hmm, I'm not sure what to say to that."
                    ended = False

                if response:
                    console.print()
                    console.print(Panel(
                        response,
                        title=f"[bold cyan]{npc.display_name}[/bold cyan]",
                        border_style="cyan"
                    ))

                if ended:
                    if self.npc_chat_manager:
                        self.npc_chat_manager.end_conversation()
                    console.print()
                    print_status_message("The conversation ends.", "info")
                    break

            except (EOFError, KeyboardInterrupt):
                if self.npc_chat_manager:
                    self.npc_chat_manager.end_conversation()
                console.print()
                print_status_message("You walk away.", "info")
                break

    def handle_shop_menu(self) -> None:
        """Show a menu of NPCs with shops in the current room."""
        import questionary

        # Check if NPC manager is available
        if not self.game_state.npc_manager:
            print_error("No NPCs available in this campaign.")
            return

        # Get NPCs in current room
        current_room = self.game_state.get_current_room()
        room_id = current_room.get("id", "")
        npcs = self.game_state.npc_manager.get_npcs_in_room(room_id)

        # Filter to shopkeepers
        shopkeeper_npcs = []
        for npc in npcs:
            if npc.shop and npc.shop.enabled:
                shopkeeper_npcs.append(npc)

        if not shopkeeper_npcs:
            print_status_message("There are no shops here.", "warning")
            return

        if len(shopkeeper_npcs) == 1:
            # Only one shopkeeper, open directly
            self._open_shop(shopkeeper_npcs[0])
            return

        # Multiple shopkeepers - let user choose
        choices = []
        for npc in shopkeeper_npcs:
            choices.append(questionary.Choice(title=npc.display_name, value=npc))
        choices.append(questionary.Choice(title="Cancel", value=None))

        try:
            result = questionary.select(
                "Which shop would you like to visit?",
                choices=choices,
            ).ask()
            if result:
                self._open_shop(result)
        except (EOFError, KeyboardInterrupt):
            print_status_message("Cancelled.", "warning")

    def handle_shop(self, npc_name: str) -> None:
        """Open shop for a specific NPC by name."""
        # Check if NPC manager is available
        if not self.game_state.npc_manager:
            print_error("No NPCs available in this campaign.")
            return

        # Get NPCs in current room
        current_room = self.game_state.get_current_room()
        room_id = current_room.get("id", "")
        npcs = self.game_state.npc_manager.get_npcs_in_room(room_id)

        # Find NPC by name (case-insensitive partial match)
        target_npc = None
        npc_name_lower = npc_name.lower()

        for npc in npcs:
            if (
                npc_name_lower in npc.name.lower()
                or npc_name_lower in npc.display_name.lower()
            ):
                target_npc = npc
                break

        if not target_npc:
            print_error(f"No one named '{npc_name}' is here.")
            return

        if not target_npc.shop or not target_npc.shop.enabled:
            print_status_message(f"{target_npc.display_name} doesn't run a shop.", "warning")
            return

        self._open_shop(target_npc)

    def _open_shop(self, npc: Any) -> None:
        """Open the shop UI for an NPC."""
        party = self.game_state.party.characters
        if not party:
            print_error("No party members available.")
            return

        shop_ui = ShopUI(npc, party)
        shop_ui.run()

    def handle_attack(self, target_name: str) -> None:
        """Handle attack command during combat."""
        # Get current actor (must be a party member)
        current = self.game_state.initiative_tracker.get_current_combatant()
        attacker = None
        for character in self.game_state.party.characters:
            if current.creature == character and character.is_alive:
                attacker = character
                break

        if not attacker:
            # Not a player turn - middleware will show error
            return

        # Find target before executing through middleware
        target = self._find_enemy_by_target(target_name)

        if not target:
            print_error(f"No such enemy: {target_name}")
            # Show numbered enemy list
            living_enemies = []
            for enemy in self.game_state.active_enemies:
                if enemy.is_alive:
                    display_name = self._get_enemy_display_name(enemy)
                    living_enemies.append(display_name)
            if living_enemies:
                print_status_message(f"Available targets: {', '.join(living_enemies)}", "info")
            return

        # Execute attack through middleware chain
        context = self.action_executor.execute(
            actor=attacker,
            action_type=ActionType.ACTION,
            action_name="attack",
            action_handler=lambda ctx: self._execute_attack(target),
            target=target.name
        )

        # Handle execution result
        if context.result == ActionResult.FAILED:
            print_error(context.error_message)
            return
        elif context.result == ActionResult.CANCELLED:
            print_status_message("Attack cancelled", "warning")
            return

        # Middleware handled validation/logging - now complete turn
        # End player turn
        self.game_state.initiative_tracker.next_turn()

        # Check if combat is over
        self.game_state._check_combat_end()

        if self.game_state.in_combat:
            # Process enemy turns
            self.process_enemy_turns()

    def _execute_attack(self, target) -> bool:
        """
        Execute the actual attack logic without boilerplate.

        This is called by the middleware after all validation passes.
        Returns True if action completed successfully.
        """
        # Get attacker from current turn (middleware already validated this)
        current = self.game_state.initiative_tracker.get_current_combatant()
        attacker = current.creature

        # Execute attack through game engine
        result = self.game_state.execute_player_attack(attacker, target)

        # Display the attack result
        self._display_player_attack_result(result, attacker, target)

        return True

    def _display_player_attack_result(
        self,
        result: PlayerAttackResult,
        attacker: Character,
        target
    ) -> None:
        """Display the results of a player attack."""
        attack_result = result.attack_result

        # Display concentration break if applicable
        if result.concentration_broken:
            spell_name = result.concentration_broken["spell_name"]
            save_result = result.concentration_broken["save_result"]
            dc = result.concentration_broken["dc"]
            console.print(
                f"[yellow]💫 {target.name}'s concentration on {spell_name} is broken! "
                f"(CON save: {save_result['total']} vs DC {dc})[/yellow]"
            )

        # FLOW: Narrative → Mechanics → Death Narrative → Death Message

        # 1. Get and display attack narrative FIRST (if hit)
        if self.llm_enhancer and attack_result.hit:
            attack_context = self.context_builder.build_attack_context(
                attacker, target, attack_result
            )

            with console.status("", spinner="dots"):
                narrative = self.llm_enhancer.get_combat_narrative_sync(
                    action_data=attack_context,
                    timeout=20.0
                )
            if narrative:
                self.display_narrative_panel(narrative)

        # Record this action in combat history
        self._record_combat_action(attack_result)

        # 2. Display mechanics after narrative
        console.print(f"[cyan]⚔️  {str(attack_result)}[/cyan]")

        # 3. If target died, show death narrative then confirmation
        if result.target_killed:
            if self.llm_enhancer:
                with console.status("", spinner="dots"):
                    death_narrative = self.llm_enhancer.get_death_narrative_sync(
                        character_data={
                            "name": target.name,
                            "is_player": isinstance(target, Character)
                        },
                        timeout=20.0
                    )
                if death_narrative:
                    self.display_narrative_panel(death_narrative)

            # 4. Display defeated message after death narrative
            print_status_message(f"{target.name} is defeated!", "success")

    def handle_cast_spell(self, spell_name: str) -> None:
        """Handle cast spell command during combat."""
        # Get current actor (must be a party member)
        current = self.game_state.initiative_tracker.get_current_combatant()
        caster = None
        for character in self.game_state.party.characters:
            if current.creature == character and character.is_alive:
                caster = character
                break

        if not caster:
            # Not a player turn
            return

        # Check if character can cast spells
        if not caster.spellcasting_ability:
            print_error(f"{caster.character_class.value.title()} cannot cast spells!")
            return

        spellcasting_ability = caster.spellcasting_ability

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
                    slot_info = "(cantrip)"
                else:
                    available_slots = caster.get_available_spell_slots(spell_level)
                    ordinal = caster._level_to_ordinal(spell_level)
                    if available_slots > 0:
                        slot_info = f"({ordinal}, {available_slots} slots)"
                    else:
                        slot_info = f"({ordinal}, no slots)"

                # Build spell description based on available information
                if damage_dice and damage_type:
                    # Damage spell: show damage
                    description = f"{damage_dice} {damage_type}"
                else:
                    # Non-damage spell: show tags or school
                    tags = sdata.get("tags", [])
                    if tags:
                        # Show primary tag (skip "combat" as it's implied)
                        non_combat_tags = [t for t in tags if t != "combat"]
                        description = non_combat_tags[0] if non_combat_tags else "combat"
                    else:
                        # Fallback to school
                        description = sdata.get("school", "spell")

                spell_choices.append(f"{spell_display_name} - {description} {slot_info}")

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

        # Get targeting requirements from game engine (not interpreting data directly)
        targeting = get_spell_targeting_requirements(spell_data)
        spell_display_name = spell_data.get("name", spell_id)

        # Warn if spell data is missing target_type
        if targeting.missing_target_type:
            print_error(f"Warning: Spell '{spell_display_name}' missing target_type, defaulting to enemy targeting")

        # Route targeting based on requirements from game engine
        if targeting.is_area_effect:
            # Area effect spells - target all living enemies
            target = None  # Special marker for area effects
            print_status_message(f"{caster.name} casts {spell_display_name}!", "info")
        elif targeting.valid_targets == ValidTargets.SELF:
            # Self-only spells
            target = caster
            print_status_message(f"{caster.name} targets themselves with {spell_display_name}", "info")
        elif targeting.valid_targets == ValidTargets.ALLY:
            # Allied target (including self)
            target = self._prompt_combat_ally_selection(spell_display_name, spell_data, caster)
        elif targeting.valid_targets == ValidTargets.ENEMY:
            # Single enemy target
            target = self._prompt_enemy_selection()
        elif targeting.valid_targets == ValidTargets.ANY:
            # Any creature (rare - Light, Identify, etc.)
            # For now, prompt ally selection (can be expanded later)
            target = self._prompt_combat_ally_selection(spell_display_name, spell_data, caster)
        else:
            # Fallback should not happen, but handle gracefully
            target = self._prompt_enemy_selection()

        # Handle target cancellation - nothing consumed yet so just return
        # Note: target=None is valid for area effects, so check for explicit "Cancel"
        if target == "Cancel" or (target is None and not targeting.is_area_effect):
            return

        # Execute spell through middleware chain
        # Spell slot validation/consumption handled by game engine, resources tracked for auto-refund
        context = self.action_executor.execute(
            actor=caster,
            action_type=ActionType.ACTION,
            action_name="cast_spell",
            action_handler=lambda ctx: self._execute_spell(
                ctx, spell_data, spell_id, target, spellcasting_ability
            ),
            spell=spell_data.get('name'),
            target=target.name if target else "area"  # "area" for area effect spells
        )

        # Handle execution result
        if context.result == ActionResult.FAILED:
            print_error(context.error_message)
            return
        elif context.result == ActionResult.CANCELLED:
            print_status_message("Spell cancelled", "warning")
            return

        # Middleware handled validation/logging - now complete turn
        # End player turn
        self.game_state.initiative_tracker.next_turn()

        # Check if combat is over
        self.game_state._check_combat_end()

        if self.game_state.in_combat:
            # Process enemy turns
            self.process_enemy_turns()

    def _execute_spell(
        self,
        context: CombatActionContext,
        spell_data: dict[str, Any],
        spell_id: str,
        target,
        spellcasting_ability: str
    ) -> bool:
        """
        Execute spell by delegating to game engine and displaying results.

        This is called by the middleware after all validation passes.
        Returns True if action completed successfully.

        Args:
            context: Middleware context for resource tracking
            spell_data: Spell definition dictionary
            spell_id: Spell identifier
            target: Target creature or None for area spells
            spellcasting_ability: Ability used for spellcasting
        """
        # Get caster from current turn (middleware already validated this)
        current = self.game_state.initiative_tracker.get_current_combatant()
        caster = current.creature

        # Delegate to game engine for all game logic (including spell slot handling)
        result = self.game_state.cast_spell_combat(
            caster=caster,
            spell_data=spell_data,
            target=target,
            spellcasting_ability=spellcasting_ability
        )

        # Propagate consumed resources to middleware for auto-refund on failure
        context.resources_consumed = result.resources_consumed

        if not result.success:
            context.result = ActionResult.FAILED
            context.error_message = result.error or "Spell failed"
            print_error(context.error_message)
            return False

        # Display results (UI responsibility only)
        self._display_spell_result(result, spell_data, caster)

        return True

    def _display_spell_result(
        self,
        result: CombatSpellResult,
        spell_data: dict[str, Any],
        caster
    ) -> None:
        """Display spell casting results - pure presentation logic."""
        # Display concentration break for caster if applicable
        if result.broke_concentration:
            console.print(
                f"[yellow]💫 {result.caster_name} stops concentrating on "
                f"{result.broke_concentration}[/yellow]"
            )

        # Handle area effect display (multi-target save spells)
        if result.is_area_effect and result.spell_type == "save":
            console.print(f"[bold cyan]✨ {result.caster_name} casts {result.spell_name}![/bold cyan]")
            for target_result in result.save_results:
                target_name = target_result["name"]
                save_success = target_result.get("success", False)
                damage = target_result.get("damage", 0)
                save_total = target_result.get("total", 0)

                save_status = "saved" if save_success else "failed"
                save_ability = result.save_ability.upper() if result.save_ability else "DEX"
                console.print(
                    f"  [yellow]{target_name}[/yellow]: "
                    f"{save_ability} save {save_total} vs DC {result.save_dc} - "
                    f"{save_status.upper()} - {damage} damage"
                )

            # Display target concentration breaks for area spells
            for conc_break in result.target_concentration_breaks:
                console.print(
                    f"    [yellow]💫 {conc_break['target']}'s concentration on "
                    f"{conc_break['spell']} is broken![/yellow]"
                )

            # Display new concentration
            if result.now_concentrating:
                console.print(
                    f"[cyan]🎯 {result.caster_name} begins concentrating on "
                    f"{result.spell_name}[/cyan]"
                )
            return  # Early return for area effects

        # Handle HP pool spells (Sleep, Color Spray)
        if result.spell_type == "hp_pool":
            console.print(f"[bold cyan]✨ {result.caster_name} casts {result.spell_name}![/bold cyan]")
            console.print(f"[cyan]🎲 HP Pool: {result.hp_pool_rolled}[/cyan]")

            # Show affected targets
            if result.affected_targets:
                for target_info in result.affected_targets:
                    condition = target_info.get("condition", "affected")
                    console.print(
                        f"  [green]💤 {target_info['name']} ({target_info['hp']} HP) "
                        f"falls {condition}![/green]"
                    )

            # Show unaffected targets
            if result.unaffected_targets:
                for target_info in result.unaffected_targets:
                    reason = target_info.get("reason", "unaffected")
                    console.print(
                        f"  [yellow]{target_info['name']} ({target_info['hp']} HP) - {reason}[/yellow]"
                    )

            # Display remaining HP pool
            if result.hp_pool_remaining and result.hp_pool_remaining > 0:
                console.print(f"[dim]HP Pool remaining: {result.hp_pool_remaining}[/dim]")

            # Display new concentration
            if result.now_concentrating:
                console.print(
                    f"[cyan]🎯 {result.caster_name} begins concentrating on "
                    f"{result.spell_name}[/cyan]"
                )
            return  # Early return for HP pool spells

        # Display target concentration breaks for single-target spells
        for conc_break in result.target_concentration_breaks:
            save_result = conc_break.get("save_result", {})
            console.print(
                f"[yellow]💫 {conc_break['target']}'s concentration on "
                f"{conc_break['spell']} is broken! "
                f"(CON save: {save_result.get('total', 0)} vs DC {conc_break.get('dc', 10)})[/yellow]"
            )

        # Display new concentration
        if result.now_concentrating:
            console.print(
                f"[cyan]🎯 {result.caster_name} begins concentrating on "
                f"{result.spell_name}[/cyan]"
            )

        # Display LLM narrative for attack spells that hit
        if self.llm_enhancer and result.attack_result and result.attack_result.hit:
            # Find actual target creature by name (not active_enemies[0] which could be dead)
            target_name = result.targets[0] if result.targets else None
            target_creature = None
            if target_name:
                for enemy in self.game_state.active_enemies:
                    if enemy.name == target_name:
                        target_creature = enemy
                        break
            if target_creature:
                spell_action_data = {
                    "name": spell_data.get("name", "spell"),
                    "damage_type": spell_data.get("damage", {}).get("damage_type", "magical")
                }
                attack_context = self.context_builder.build_attack_context(
                    caster, target_creature, result.attack_result,
                    action_data=spell_action_data, is_spell=True
                )

                with console.status("", spinner="dots"):
                    narrative = self.llm_enhancer.get_combat_narrative_sync(
                        action_data=attack_context,
                        timeout=20.0
                    )
                if narrative:
                    self.display_narrative_panel(narrative)

        # Record combat action for attack spells
        if result.attack_result:
            self._record_combat_action(result.attack_result)

        # Display mechanics
        console.print(f"[magenta]✨ {result.caster_name} casts {result.spell_name}![/magenta]")

        # Show attack/save mechanics based on spell type
        if result.spell_type == "attack" and result.attack_result:
            console.print(f"[cyan]⚔️  {str(result.attack_result)}[/cyan]")
        elif result.spell_type == "save" and result.total_damage > 0:
            # Single-target save with damage
            target_result = result.save_results[0] if result.save_results else {}
            save_text = "SUCCESS" if target_result.get("success") else "FAILURE"
            save_ability = result.save_ability.upper() if result.save_ability else ""
            console.print(
                f"[cyan]🎲 {result.targets[0]} {save_ability} save: {save_text} - "
                f"{result.total_damage} damage[/cyan]"
            )
        elif result.spell_type == "save":
            # Save spell with no damage (debuff)
            target_result = result.save_results[0] if result.save_results else {}
            save_text = "SUCCESS" if target_result.get("success") else "FAILURE"
            save_ability = result.save_ability.upper() if result.save_ability else ""
            console.print(f"[cyan]🎲 {result.targets[0]} {save_ability} save: {save_text}[/cyan]")
        # For buff spells, no mechanics display needed - just the cast message

        # Display death for killed targets
        for killed in result.killed_targets:
            if self.llm_enhancer:
                with console.status("", spinner="dots"):
                    death_narrative = self.llm_enhancer.get_death_narrative_sync(
                        character_data={
                            "name": killed,
                            "is_player": killed in [c.name for c in self.game_state.party.characters]
                        },
                        timeout=20.0
                    )
                if death_narrative:
                    self.display_narrative_panel(death_narrative)

            print_status_message(f"{killed} is defeated!", "success")

    def handle_stabilize(self, target_name: str) -> None:
        """Handle stabilize command to help unconscious ally."""
        # Get current actor (must be a party member)
        current = self.game_state.initiative_tracker.get_current_combatant()
        helper = None
        for character in self.game_state.party.characters:
            if current.creature == character and character.is_alive and not character.is_unconscious:
                helper = character
                break

        if not helper:
            # Not a valid player turn
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

        # Execute stabilize through middleware chain
        context = self.action_executor.execute(
            actor=helper,
            action_type=ActionType.ACTION,
            action_name="stabilize",
            action_handler=lambda ctx: self._execute_stabilize(target),
            target=target.name
        )

        # Handle execution result
        if context.result == ActionResult.FAILED:
            print_error(context.error_message)
            return
        elif context.result == ActionResult.CANCELLED:
            print_status_message("Stabilize cancelled", "warning")
            return

        # Middleware handled validation/logging - now complete turn
        # End player turn
        self.game_state.initiative_tracker.next_turn()

        # Check if combat is over
        self.game_state._check_combat_end()

        if self.game_state.in_combat:
            # Process enemy turns
            self.process_enemy_turns()

    def _execute_stabilize(self, target: Character) -> bool:
        """
        Execute the actual stabilize logic without boilerplate.

        This is called by the middleware after all validation passes.
        Returns True if action completed successfully.
        """
        # Get helper from current turn (middleware already validated this)
        current = self.game_state.initiative_tracker.get_current_combatant()
        helper = current.creature

        print_section(f"{helper.name} attempts to stabilize {target.name}")

        # Execute stabilize through game engine
        result = self.game_state.execute_stabilize(helper, target)

        # Display check result
        modifier_str = f"+{result.modifier}" if result.modifier >= 0 else str(result.modifier)
        print_status_message(
            f"Medicine check: {result.roll}{modifier_str} = {result.total} vs DC {result.dc}",
            "info"
        )

        if result.success:
            print_status_message(f"Success! {target.name} is stabilized.", "success")
        else:
            print_error(f"Failed! {target.name} remains unstabilized.")

        return True

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

    def handle_end_turn(self) -> None:
        """Handle end turn command during combat."""
        if not self.game_state.in_combat:
            print_error("You're not in combat!")
            return

        # Verify it's a player character's turn
        if not self.game_state.initiative_tracker:
            print_error("No initiative tracker!")
            return

        current = self.game_state.initiative_tracker.get_current_combatant()
        if not current:
            print_error("No current combatant!")
            return

        # Check if current combatant is a party member
        if current.creature not in self.game_state.party.characters:
            print_error("It's not a party member's turn!")
            return

        # End the turn
        print_status_message(f"{current.creature.name} ends their turn.", "info")
        self.game_state.initiative_tracker.next_turn()

        # Check if combat is over
        self.game_state._check_combat_end()

        if self.game_state.in_combat:
            # Process enemy turns
            self.process_enemy_turns()

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

        Delegates game logic to game_state and handles display/prompting.

        Args:
            creature: The creature with conditions

        Returns:
            True if an action was consumed attempting to remove a condition
        """
        # Get removable conditions from game engine
        options = self.game_state.get_removable_conditions(creature)

        for option in options:
            # Display condition and prompt
            print_status_message(
                f"🔥 {creature.name} has condition: {option.condition_name}!",
                "warning"
            )
            print_message(f"   {option.description}")
            print_message(
                f"   Use your action to attempt a DC {option.dc} "
                f"{option.ability.upper()} check to remove it? [Y/N]"
            )

            response = input("   > ").strip().lower()

            if response in ['y', 'yes']:
                # Attempt removal via game engine
                result = self.game_state.attempt_player_condition_removal(
                    creature, option.condition_id
                )

                if result.attempted:
                    if result.success:
                        print_status_message(result.message, "success")
                    else:
                        print_status_message(result.message, "warning")
                    return True  # Action was consumed
                else:
                    # Shouldn't happen if get_removable_conditions filtered properly
                    print_error(result.message)

        return False  # No action consumed

    def process_enemy_turns(self) -> None:
        """Process all enemy turns until it's a party member's turn again."""
        while self.game_state.in_combat:
            # Process one enemy turn via game engine
            result = self.game_state.process_enemy_turn()

            # None means it's a party member's turn
            if result is None:
                break

            # Display the enemy turn result
            self._display_enemy_turn_result(result)

            # Check if combat ended
            if result.combat_ended:
                break

            # Check if entire party is dead
            if self.game_state.party.is_wiped():
                break

    def _display_enemy_turn_result(self, result: EnemyTurnResult) -> None:
        """
        Display the result of an enemy turn to the player.

        Handles all UI output based on the action taken and results.

        Args:
            result: The EnemyTurnResult from game_state.process_enemy_turn()
        """
        enemy_name = result.enemy_display_name

        # Display turn-start effects
        for effect in result.turn_start_effects:
            print_status_message(effect.message, "warning")
            if effect.creature_died:
                print_status_message(
                    f"💀 {enemy_name} is killed by {effect.condition_id.replace('_', ' ')}!",
                    "warning"
                )

        # Handle different action types
        if result.action_taken == EnemyTurnAction.DIED_START_OF_TURN:
            # Already displayed death message above if from effects
            return

        if result.action_taken == EnemyTurnAction.INCAPACITATED:
            condition_text = ", ".join(result.incapacitating_conditions)
            print_status_message(
                f"⚠️  {enemy_name} is {condition_text} and cannot act this turn!",
                "warning"
            )
            self._display_turn_end_effects(result)
            return

        if result.action_taken == EnemyTurnAction.CONDITION_REMOVAL:
            if result.condition_removal:
                # Display condition removal attempt
                if result.condition_removal.condition_id == "on_fire":
                    print_status_message(
                        f"🔥 {enemy_name} is on fire with low HP! Attempting to extinguish...",
                        "info"
                    )
                if result.condition_removal.success:
                    print_status_message(result.condition_removal.message, "success")
                else:
                    print_status_message(result.condition_removal.message, "warning")
            return

        if result.action_taken == EnemyTurnAction.NO_TARGETS:
            # No display needed - combat will end
            return

        if result.action_taken == EnemyTurnAction.NO_VALID_ATTACK:
            if result.error:
                print_error(f"{enemy_name} has no valid attack actions!")
            return

        # ATTACK action
        if result.action_taken == EnemyTurnAction.ATTACK:
            print_status_message(f"{enemy_name}'s turn...", "info")

            # Display concentration break if applicable
            if result.concentration_broken:
                conc = result.concentration_broken
                console.print(
                    f"[yellow]💫 {result.target_name}'s concentration on "
                    f"{conc['spell_name']} is broken! "
                    f"(CON save: {conc['save_result']['total']} vs DC {conc['dc']})[/yellow]"
                )

            # Display saving throw results
            if result.saving_throw_triggered and result.save_ability and result.save_dc:
                if result.save_succeeded is False and result.conditions_applied:
                    # Failed save - get duration from target if available
                    for condition in result.conditions_applied:
                        # Get the target to check duration metadata
                        target = self._find_party_member_by_name(result.target_name)
                        duration = 0
                        if target and hasattr(target, 'active_conditions'):
                            metadata = target.active_conditions.get(condition, {})
                            duration = metadata.get('duration_remaining', 0)
                        print_status_message(
                            f"💀 {result.target_name} fails {result.save_ability} save "
                            f"(DC {result.save_dc}) - {condition.upper()} for {duration} rounds!",
                            "error"
                        )
                elif result.save_succeeded is True:
                    print_status_message(
                        f"✓ {result.target_name} succeeds on {result.save_ability} save "
                        f"(DC {result.save_dc})!",
                        "success"
                    )

            # Get attack narrative (if LLM enabled and hit)
            if self.llm_enhancer and result.attack_result and result.attack_result.hit:
                # Get the enemy and target creatures for context building
                enemy = self._find_enemy_by_name(result.enemy_name)
                target = self._find_party_member_by_name(result.target_name)

                if enemy and target:
                    attack_context = self.context_builder.build_attack_context(
                        enemy, target, result.attack_result, action_data=result.action_data
                    )

                    with console.status("", spinner="dots"):
                        narrative = self.llm_enhancer.get_combat_narrative_sync(
                            action_data=attack_context,
                            timeout=20.0
                        )
                    if narrative:
                        self.display_narrative_panel(narrative)

            # Record combat action in history
            if result.attack_result:
                self._record_combat_action(result.attack_result)

            # Display attack mechanics
            if result.attack_result:
                console.print(f"[cyan]⚔️  {str(result.attack_result)}[/cyan]")

            # Display death if target killed
            if result.target_killed:
                target = self._find_party_member_by_name(result.target_name)
                if self.llm_enhancer and target:
                    with console.status("", spinner="dots"):
                        death_narrative = self.llm_enhancer.get_death_narrative_sync(
                            character_data={
                                "name": result.target_name,
                                "is_player": isinstance(target, Character)
                            },
                            timeout=20.0
                        )
                    if death_narrative:
                        self.display_narrative_panel(death_narrative)

                print_status_message(f"{result.target_name} has fallen!", "warning")

            # Display turn-end effects
            self._display_turn_end_effects(result)

    def _display_turn_end_effects(self, result: EnemyTurnResult) -> None:
        """Display turn-end condition effects."""
        for effect in result.turn_end_effects:
            if effect.effect_type == "condition_expired":
                # Don't announce surprised expiry
                if effect.condition_id != "surprised":
                    print_status_message(
                        f"⏱ {effect.condition_id.upper()} on {result.enemy_name} has expired!",
                        "info"
                    )

    def _find_party_member_by_name(self, name: str | None) -> Character | None:
        """Find a party member by name."""
        if not name:
            return None
        for char in self.game_state.party.characters:
            if char.name == name:
                return char
        return None

    def _find_enemy_by_name(self, name: str) -> Any | None:
        """Find an enemy creature by name."""
        for enemy in self.game_state.active_enemies:
            if enemy.name == name:
                return enemy
        return None

    def _get_enemy_display_name(self, enemy: Any) -> str:
        """
        Get the display name for an enemy (with combat number if applicable).

        Args:
            enemy: The enemy creature

        Returns:
            Display name (e.g., "Goblin 2" or just "Goblin")
        """
        if self.game_state.initiative_tracker:
            for entry in self.game_state.initiative_tracker.get_all_combatants():
                if entry.creature == enemy:
                    return entry.display_name if entry.display_name else enemy.name
        return enemy.name

    def _find_enemy_by_target(self, target: str) -> Any | None:
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
        # Use new InitiativeTracker API for target lookup
        if self.game_state.initiative_tracker:
            player_creatures = [char for char in self.game_state.party.characters]
            entry = self.game_state.initiative_tracker.find_combatant_by_reference(
                target,
                player_creatures=player_creatures
            )
            if entry and entry.creature not in player_creatures:
                return entry.creature

        return None

    def _parse_command_with_target(self, parts: list[str]) -> tuple[str, str | None]:
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

    def _prompt_consumable_selection(self, character: Character | None = None, show_action_cost: bool = False) -> tuple[str, dict[str, Any]] | None:
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

    def _prompt_target_selection(self, item_name: str) -> Character | None:
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

    def _prompt_enemy_selection(self) -> Any | None:
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
            hp_pct = enemy.current_hp / enemy.max_hp if enemy.max_hp > 0 else 0

            # Use text-based indicators
            if hp_pct > 0.5:
                hp_indicator = "●●●"
            elif hp_pct > 0.25:
                hp_indicator = "●●○"
            else:
                hp_indicator = "●○○"

            display_name = self._get_enemy_display_name(enemy)
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

    def _prompt_combat_ally_selection(self, item_name: str, item_data: dict[str, Any], user: Character) -> Character | None:
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

    def _prompt_item_to_take(self) -> dict[str, Any] | None:
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

    def _prompt_multi_items_to_take(self) -> list[dict[str, Any]]:
        """
        Prompt user to select multiple items to take from the current room.

        Returns:
            List of selected item dicts, or empty list if cancelled
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
            return []

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

        # Get user selection with arrow keys and space to select
        # Note: Use Ctrl+C to cancel without taking items
        try:
            results = questionary.checkbox(
                "Select items to take:",
                choices=choices,
                use_arrow_keys=True,
                instruction="(space=select, enter=confirm, ctrl+c=cancel)"
            ).ask()

            return results if results else []
        except (EOFError, KeyboardInterrupt):
            return []

    def _parse_item_and_player(self, parts: list[str]) -> tuple[str, str | None]:
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

    def _get_target_player(self, player_identifier: str | None, allow_unconscious: bool = False) -> Character | None:
        """
        Get a target player from an identifier (number or name).

        Args:
            player_identifier: Optional player identifier (1-based index or character name)
            allow_unconscious: If True, allow unconscious (but not dead) characters as valid targets

        Returns:
            The matching character, or None if not found or if identifier is invalid
        """
        # Choose the appropriate member list based on whether unconscious targets are allowed
        if allow_unconscious:
            members = self.game_state.party.get_targetable_members()
        else:
            members = self.game_state.party.get_living_members()

        if not members:
            return None

        # If no identifier, return first member (backward compatibility)
        if not player_identifier:
            return members[0]

        # Try to parse as a number (1-based index)
        try:
            index = int(player_identifier) - 1  # Convert to 0-based index
            if 0 <= index < len(self.game_state.party.characters):
                character = self.game_state.party.characters[index]
                # Check if character is valid based on allow_unconscious flag
                if allow_unconscious:
                    if not character.is_dead:
                        return character
                    else:
                        print_error(f"Player {player_identifier} is dead and cannot be targeted!")
                        return None
                else:
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
        for character in members:
            if character.name.lower() == player_identifier.lower():
                return character

        # No match found
        if allow_unconscious:
            print_error(f"No targetable player found with identifier: {player_identifier}")
        else:
            print_error(f"No living player found with identifier: {player_identifier}")
        return None

    def display_inventory(self, filter_arg: str | None = None) -> None:
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
                        is_quest_item = item_data.get("quest_item", False)

                        inventory_items[category].append({
                            "name": item_name,
                            "quantity": inv_item.quantity,
                            "equipped": is_equipped,
                            "quest_item": is_quest_item
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

    def handle_equip(self, item_id: str, player_identifier: str | None = None) -> None:
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

    def handle_unequip(self, slot_name: str, player_identifier: str | None = None) -> None:
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
            event_bus=self.game_state.event_bus,
            time_manager=self.game_state.time_manager
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

    def handle_use_item(self, item_id: str, player_identifier: str | None = None) -> None:
        """
        Handle using a consumable item on a target character.

        This method supports using items on any targetable party member (including unconscious allies).
        It searches all living party members' inventories for the item and uses it on the target.

        Args:
            item_id: The item to use (ID or name)
            player_identifier: Optional player identifier for target (1-based index or character name)
        """
        items_data = self.game_state.data_loader.load_items()

        # Get target character (allow unconscious but not dead)
        target = self._get_target_player(player_identifier, allow_unconscious=True)
        if not target:
            if not self.game_state.party.get_targetable_members():
                print_error("No party members can be targeted!")
            return

        # Search all living party members' inventories for the item
        owner = None
        target_item_id = None

        for char in self.game_state.party.get_living_members():
            consumables = char.inventory.get_items_by_category("consumables")
            for inv_item in consumables:
                item_data = items_data["consumables"].get(inv_item.item_id, {})
                if inv_item.item_id == item_id or item_data.get("name", "").lower() == item_id.lower():
                    owner = char
                    target_item_id = inv_item.item_id
                    break
            if owner:
                break

        if not owner or not target_item_id:
            print_error(f"No party member has a consumable '{item_id}' in inventory.")
            return

        # Use the item via the direct handler
        self.handle_use_item_direct(target_item_id, target, owner)

    def handle_use_item_combat_with_target(self, item_id: str, item_data: dict[str, Any], user: Character, target: Character) -> None:
        """
        Handle using a consumable item during combat on a specified target.

        Delegates game logic to game_state.use_item_combat() and handles display.

        Args:
            item_id: The item ID to use
            item_data: The item data dictionary (unused, kept for API compatibility)
            user: The character using the item
            target: The character receiving the item's effect
        """
        # Use the game state method to handle all game logic
        result = self.game_state.use_item_combat(user, item_id, target)

        # Handle failure cases
        if not result.success:
            # Action economy issues - show available actions
            if result.error_message and "available" in result.error_message.lower():
                turn_state = self.game_state.initiative_tracker.get_current_turn_state()
                print_error(f"You don't have a {result.action_type.value.replace('_', ' ')} available this turn!")
                if turn_state:
                    print_status_message(f"Available: {turn_state}", "info")
            else:
                print_error(result.error_message or "Failed to use item")
            return

        # Display the result with target information
        action_cost_msg = f"({result.action_type.value.replace('_', ' ')})"
        if result.user_name == result.target_name:
            print_status_message(f"{result.user_name} uses {result.item_name} {action_cost_msg}", "info")
        else:
            print_status_message(f"{result.user_name} uses {result.item_name} on {result.target_name} {action_cost_msg}", "info")

        if result.effect_message:
            print_message(result.effect_message)

        # Show HP change if healing occurred
        if result.effect_type == "healing" and result.hp_after is not None and result.hp_before is not None:
            if result.hp_after > result.hp_before:
                hp_gained = result.hp_after - result.hp_before
                print_status_message(f"{result.target_name}: {result.hp_before} → {result.hp_after} HP (+{hp_gained})", "success")

        # Show remaining actions
        turn_state = self.game_state.initiative_tracker.get_current_turn_state()
        if turn_state:
            print_status_message(f"Remaining this turn: {turn_state}", "info")
            if turn_state.has_any_action():
                print_status_message("Type 'done' or 'pass' to end your turn", "info")

        # End player turn
        self.game_state.initiative_tracker.next_turn()

        # Check if combat is over
        self.game_state._check_combat_end()

        if self.game_state.in_combat:
            # Process enemy turns
            self.process_enemy_turns()

    def handle_use_item_combat_attack(self, item_id: str, item_data: dict[str, Any], user: Character, target) -> None:
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
            display_name = self._get_enemy_display_name(target)
            print_status_message(f"💀 {display_name} is defeated!", "success")

        # End player turn
        self.game_state.initiative_tracker.next_turn()

        # Check if combat is over
        self.game_state._check_combat_end()

        if self.game_state.in_combat:
            # Process enemy turns
            self.process_enemy_turns()

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
        Game logic is handled by GameState.party_rest().
        """
        from dnd_engine.ui.rich_ui import print_message, print_section, print_status_message

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
        rest_type = "short" if choice == "1" else "long"

        # Delegate all game logic to GameState
        result = self.game_state.party_rest(rest_type)

        # Display rest results
        self._display_rest_results(result)

        # After long rest, offer spell preparation to prepared casters
        if rest_type == "long":
            for char_result in result.character_results:
                if char_result.can_prepare_spells:
                    character = self.game_state.party.get_character_by_name(
                        char_result.character_name
                    )
                    if character:
                        self._offer_spell_preparation(character)

    def _display_rest_results(self, result: "PartyRestResult") -> None:
        """
        Display the results of a rest to the player.

        Args:
            result: PartyRestResult from GameState.party_rest()
        """
        from dnd_engine.core.game_state import PartyRestResult
        from dnd_engine.ui.rich_ui import print_message, print_section, print_status_message

        rest_type_display = "Short" if result.rest_type == "short" else "Long"
        print_section(f"{rest_type_display} Rest Complete")
        print_message(f"The party rests for {result.rest_duration_display}...")
        print_message("")

        for char_result in result.character_results:
            print_message(f"{char_result.character_name}:")

            if char_result.hp_recovered > 0:
                print_message(f"  ❤️  HP recovered: {char_result.hp_recovered}")

            if char_result.resources_recovered:
                # Format resource names nicely
                formatted_resources = [
                    r.replace("_", " ").title()
                    for r in char_result.resources_recovered
                ]
                print_message(f"  ⚡ Recovered: {', '.join(formatted_resources)}")

            if char_result.hp_recovered == 0 and not char_result.resources_recovered:
                # Check if character is at 0 HP (unconscious)
                if char_result.hp_after == 0:
                    print_message("  ⚠️  Still unconscious (0 HP)")
                else:
                    # Check if character has depleted spell slots (not recovered on short rest)
                    character = self.game_state.party.get_character_by_name(
                        char_result.character_name
                    )
                    has_depleted_slots = False
                    if character and character.has_spell_slots():
                        slots = character.spell_slots
                        has_depleted_slots = any(
                            slots.get(level, 0) < character.get_max_spell_slots(level)
                            for level in range(1, 10)
                            if character.get_max_spell_slots(level) > 0
                        )

                    if has_depleted_slots and result.rest_type == "short":
                        print_message("  ✓ HP at full (spell slots require long rest)")
                    else:
                        print_message("  Already at full health and resources")

            print_message("")

        print_status_message("The party is refreshed and ready to continue!", "success")

    def _offer_spell_preparation(self, character: Character) -> None:
        """
        Spell preparation UI for prepared caster classes.

        Shows all spells from spellbook with checkboxes, pre-selecting currently
        prepared spells. Allows selecting up to max_prepared spells total.
        Automatically shown after long rest (no confirmation prompt).

        Args:
            character: Character who can prepare spells (Wizard or Cleric)
        """
        import questionary
        from questionary import Choice

        from dnd_engine.ui.rich_ui import print_message, print_section, print_status_message

        # Load spell data
        spells_data = self.game_state.data_loader.load_spells()

        # Get available spells from spellbook
        cantrips, leveled_spells = character.get_preparable_spells(spells_data)

        # Calculate preparation limit
        max_prepared = character.get_max_prepared_spells()

        # Get currently prepared spells (excluding cantrips)
        current_prepared = {s for s in character.prepared_spells if s not in cantrips}

        # Filter to only spells of levels for which character has spell slots
        available_leveled_spells = []
        for spell_id, spell_data in leveled_spells:
            spell_level = spell_data.get("level", 1)
            # Check if character has slots for this level
            pool_name = f"spell_slots_level_{spell_level}"
            pool = character.resource_pools.get(pool_name)
            if pool and pool.maximum > 0:
                available_leveled_spells.append((spell_id, spell_data))

        print_section(f"Spell Preparation - {character.name}")
        print_message(f"Select up to [cyan]{max_prepared}[/cyan] spells to prepare.")
        print_message("")

        # Show cantrips (always prepared, not selectable)
        if cantrips:
            print_message("[green]Cantrips (always prepared):[/green]")
            for cantrip_id in cantrips:
                cantrip = spells_data.get(cantrip_id, {})
                print_message(f"  • {cantrip.get('name', cantrip_id)}")
            print_message("")

        if not available_leveled_spells:
            print_status_message("No leveled spells available to prepare.", "warning")
            return

        # Build checkbox choices organized by spell level
        choices = []
        current_level = 0

        for spell_id, spell_data in available_leveled_spells:
            spell_level = spell_data.get("level", 1)
            spell_name = spell_data.get("name", spell_id)
            school = spell_data.get("school", "")

            # Add level separator
            if spell_level != current_level:
                current_level = spell_level
                level_ordinal = character._level_to_ordinal(spell_level)
                pool = character.resource_pools.get(f"spell_slots_level_{spell_level}")
                max_slots = pool.maximum if pool else 0
                choices.append(questionary.Separator(f"── {level_ordinal.capitalize()} Level ({max_slots} slots) ──"))

            # Build choice with spell info
            # Get effect description
            if spell_data.get("damage"):
                effect = f"{spell_data['damage'].get('dice', '')} {spell_data['damage'].get('type', '')}"
            elif spell_data.get("healing"):
                effect = f"healing {spell_data['healing'].get('dice', '')}"
            else:
                desc = spell_data.get("description", "utility")
                effect = desc[:30] + "..." if len(desc) > 30 else desc

            choice_title = f"{spell_name} ({school}) - {effect}"
            is_checked = spell_id in current_prepared

            choices.append(Choice(
                title=choice_title,
                value=spell_id,
                checked=is_checked
            ))

        # Custom validator to enforce max selection
        def validate_selection(selected):
            if len(selected) > max_prepared:
                return f"Too many spells! Select at most {max_prepared} (you selected {len(selected)})"
            return True

        try:
            selected_spell_ids = questionary.checkbox(
                f"Select spells to prepare (max {max_prepared}):",
                choices=choices,
                validate=validate_selection,
                instruction="(Space to toggle, Enter to confirm)"
            ).ask()

            # Handle cancellation
            if selected_spell_ids is None:
                print_message("Spell preparation cancelled. Keeping current selection.")
                return

        except (EOFError, KeyboardInterrupt):
            print_message("Spell preparation cancelled. Keeping current selection.")
            return

        # Add cantrips to selection (they're always prepared)
        final_spell_ids = cantrips + selected_spell_ids

        # Call GameState to prepare spells
        success = self.game_state.prepare_spells(character.name, final_spell_ids)

        if success:
            if selected_spell_ids:
                spell_names = [spells_data[sid].get("name", sid) for sid in selected_spell_ids]
                print_status_message(
                    f"Prepared {len(selected_spell_ids)} spell{'s' if len(selected_spell_ids) != 1 else ''}: "
                    f"{', '.join(spell_names)}",
                    "success"
                )
            else:
                print_status_message("No leveled spells prepared.", "warning")
        else:
            print_status_message("Failed to prepare spells. Please try again.", "error")

    def handle_spells(self) -> None:
        """
        Display spellbook, prepared spells, and spell slot availability.

        Works for both exploration and combat modes. Shows all spellcasters
        in the party with their prepared spells organized by level.
        """
        from dnd_engine.ui.rich_ui import print_message, print_section, print_status_message

        spells_data = self.game_state.data_loader.load_spells()
        found_caster = False

        for character in self.game_state.party.characters:
            # Check if character has any spells
            if not character.known_spells and not character.prepared_spells:
                continue

            found_caster = True
            print_section(f"{character.name}'s Spells ({character.character_class.value.capitalize()})")

            # Show spell slots
            if character.has_spell_slots():
                slots_display = character.get_spell_slots_display()
                print_message(f"[cyan]Spell Slots: {slots_display}[/cyan]")
                print_message("")

            # Determine which spell list to use
            prepared_caster_classes = {CharacterClass.WIZARD, CharacterClass.CLERIC}
            if character.character_class in prepared_caster_classes:
                spell_list = character.prepared_spells
                list_type = "Prepared"
            else:
                spell_list = character.known_spells
                list_type = "Known"

            if not spell_list:
                print_message(f"[yellow]No spells {list_type.lower()}.[/yellow]")
                print_message("")
                continue

            # Organize spells by level
            spells_by_level: dict[int, list[tuple[str, dict]]] = {}
            for spell_id in spell_list:
                spell_data = spells_data.get(spell_id)
                if not spell_data:
                    continue
                level = spell_data.get("level", 0)
                if level not in spells_by_level:
                    spells_by_level[level] = []
                spells_by_level[level].append((spell_id, spell_data))

            # Display cantrips first
            if 0 in spells_by_level:
                print_message("[green]Cantrips:[/green]")
                for spell_id, spell_data in sorted(spells_by_level[0], key=lambda x: x[1].get("name", "")):
                    name = spell_data.get("name", spell_id)
                    school = spell_data.get("school", "")
                    # Get damage or effect info
                    if spell_data.get("damage"):
                        effect = f"{spell_data['damage'].get('dice', '')} {spell_data['damage'].get('type', '')}"
                    elif spell_data.get("healing"):
                        effect = f"healing {spell_data['healing'].get('dice', '')}"
                    else:
                        effect = "utility"
                    print_message(f"  • {name} ({school}) - {effect}")
                print_message("")

            # Display leveled spells
            for level in sorted(k for k in spells_by_level.keys() if k > 0):
                available_slots = character.get_available_spell_slots(level)
                level_ordinal = character._level_to_ordinal(level)
                print_message(f"[cyan]{level_ordinal.capitalize()} Level[/cyan] [{available_slots} slots]:")
                for spell_id, spell_data in sorted(spells_by_level[level], key=lambda x: x[1].get("name", "")):
                    name = spell_data.get("name", spell_id)
                    school = spell_data.get("school", "")
                    # Get damage or effect info
                    if spell_data.get("damage"):
                        effect = f"{spell_data['damage'].get('dice', '')} {spell_data['damage'].get('type', '')}"
                    elif spell_data.get("healing"):
                        effect = f"healing {spell_data['healing'].get('dice', '')}"
                    else:
                        effect = spell_data.get("description", "")[:40] + "..." if len(spell_data.get("description", "")) > 40 else spell_data.get("description", "utility")
                    print_message(f"  • {name} ({school}) - {effect}")
                print_message("")

            # Show spellbook info for wizards
            if character.character_class == CharacterClass.WIZARD:
                known_count = len(character.known_spells)
                prepared_count = len([s for s in character.prepared_spells if spells_data.get(s, {}).get("level", 0) > 0])
                max_prepared = character.get_max_prepared_spells()
                print_message(f"[dim]Spellbook: {known_count} spells known | Prepared: {prepared_count}/{max_prepared}[/dim]")
                print_message("")

        if not found_caster:
            print_status_message("No spellcasters in the party.", "warning")

    def handle_prepare_spells(self) -> None:
        """
        Handle the prepare command to manage prepared spells.

        Only available for prepared caster classes (Wizard, Cleric).
        Allows changing prepared spells outside of combat.
        """
        import questionary

        from dnd_engine.ui.rich_ui import print_error, print_status_message

        if self.game_state.in_combat:
            print_error("You cannot change prepared spells during combat.")
            return

        # Find prepared casters in the party
        prepared_caster_classes = {CharacterClass.WIZARD, CharacterClass.CLERIC}
        casters = [c for c in self.game_state.party.characters
                   if c.character_class in prepared_caster_classes and c.known_spells]

        if not casters:
            print_status_message("No prepared casters in the party (Wizards or Clerics with spellbooks).", "warning")
            return

        # If only one caster, use them directly
        if len(casters) == 1:
            character = casters[0]
        else:
            # Prompt for caster selection
            choices = [questionary.Choice(title=f"{c.name} ({c.character_class.value.capitalize()})", value=c)
                       for c in casters]
            choices.append(questionary.Choice(title="Cancel", value=None))

            try:
                character = questionary.select(
                    "Which character will prepare spells?",
                    choices=choices,
                    use_arrow_keys=True
                ).ask()

                if not character:
                    return
            except (EOFError, KeyboardInterrupt):
                return

        # Use existing spell preparation logic
        self._offer_spell_preparation(character)

    def handle_cast_spell_exploration(self) -> None:
        """
        Handle spell casting during exploration mode.

        Allows party members to cast healing and utility spells outside of combat.
        Prompts for caster selection, spell selection, and target selection.
        """
        import questionary

        from dnd_engine.ui.rich_ui import (
            print_error,
            print_message,
            print_section,
            print_status_message,
        )

        # 1. Select caster
        caster = self._prompt_party_member_selection("Who will cast a spell?")
        # Handle both None and "Cancel" string (questionary may return either)
        if not caster or isinstance(caster, str):
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

            if not selected or selected == "Cancel":
                return  # User cancelled

            spell_id, spell_data = selected
        except (EOFError, KeyboardInterrupt):
            return

        # 3. Select target if needed (using targeting requirements from game engine)
        target_name = None
        targeting = get_spell_targeting_requirements(spell_data)

        if targeting.valid_targets == ValidTargets.ALLY:
            # Ally-targeting spells need a target selection
            target = self._prompt_party_member_selection(
                f"Who should {caster.name} target with {spell_data.get('name')}?"
            )
            # Handle both None and "Cancel" string (questionary may return either)
            if not target or isinstance(target, str):
                return  # User cancelled
            target_name = target.name
        elif targeting.valid_targets == ValidTargets.ANY:
            # "Any" target type - for now, treat like ally (can expand later for objects/items)
            target = self._prompt_party_member_selection(
                f"Who should {caster.name} target with {spell_data.get('name')}?"
            )
            if not target or isinstance(target, str):
                return  # User cancelled
            target_name = target.name
        # Self and utility spells don't need target selection

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

    def _prompt_party_member_selection(self, prompt_message: str) -> Character | None:
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

    def handle_time(self) -> None:
        """Display the current game time."""
        elapsed_time = self.game_state.time_manager.get_elapsed_time_display()
        print_section("Game Time")
        print_message(f"Time elapsed: {elapsed_time}")

    def handle_effects(self) -> None:
        """Display all active effects on party members."""
        effects = self.game_state.time_manager.get_all_effects()

        if not effects:
            print_message("No active effects")
            return

        print_section("Active Effects")

        # Group effects by target
        effects_by_target = {}
        for effect in effects:
            if effect.target_name not in effects_by_target:
                effects_by_target[effect.target_name] = []
            effects_by_target[effect.target_name].append(effect)

        # Display effects for each target
        for target_name, target_effects in effects_by_target.items():
            print_message(f"\n{target_name}:")
            for effect in target_effects:
                time_remaining = effect.get_time_remaining_display()
                concentration_marker = " (Concentration)" if effect.concentration else ""
                caster_info = f" from {effect.caster_name}" if effect.caster_name else ""
                print_message(f"  • {effect.source}: {time_remaining}{concentration_marker}{caster_info}")

    def display_help_exploration(self) -> None:
        """Display help for exploration commands."""
        commands = [
            ("n/s/e/w/ne/nw/se/sw", "Move in a direction (cardinal or diagonal)"),
            ("move/go <direction>", "Move in a direction (e.g., 'go north', 'go northeast')"),
            ("look or l", "Look around the current room"),
            ("examine / x [target]", "Examine objects or listen at doors (e.g., 'examine corpse')"),
            ("talk [npc]", "Talk to an NPC (e.g., 'talk marta' or just 'talk' for menu)"),
            ("shop [npc]", "Open shop UI (e.g., 'shop gareth' or just 'shop' for menu)"),
            ("search", "Search the room for items"),
            ("take/get/pickup <item>", "Pick up an item (e.g., 'take dagger', 'get gold')"),
            ("inventory / i [filter]", "Show inventory. Filter: summary, player name/number, or item type"),
            ("equip <item> [on <player>]", "Equip weapon/armor (e.g., 'equip sword on 2')"),
            ("unequip <slot> [on <player>]", "Unequip weapon/armor (e.g., 'unequip weapon on gandalf')"),
            ("use <item> [on <player>]", "Use consumable (e.g., 'use potion on 2')"),
            ("status", "Show your character status"),
            ("rest", "Take a short or long rest"),
            ("cast [spell]", "Cast a spell (e.g., 'cast light' or just 'cast' for menu)"),
            ("spells", "View prepared spells and available spell slots"),
            ("prepare", "Manage prepared spells (wizards/clerics)"),
            ("time", "Show elapsed game time"),
            ("effects", "Show active spell effects and their durations"),
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
            ("cast [spell]", "Cast a spell (e.g., 'cast magic missile' or just 'cast')"),
            ("spells", "View prepared spells and available spell slots"),
            ("use <item>", "Use a consumable item (e.g., 'use potion') - costs an action"),
            ("stabilize <ally>", "Stabilize an unconscious ally (Medicine DC 10)"),
            ("end turn / done / pass", "End your turn and skip remaining actions"),
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
                        # Stabilized characters skip their turn (no death saves needed)
                        if party_character.stabilized:
                            print_status_message(
                                f"{party_character.name} is unconscious but stabilized (no action needed).",
                                "info"
                            )
                        else:
                            # Unstabilized unconscious character makes death save
                            self.process_death_save_turn(party_character)
                        # Advance turn after death save or stabilized skip
                        self.game_state.initiative_tracker.next_turn()
                        # Check if combat is over
                        self.game_state._check_combat_end()
                    elif not party_character.can_take_actions():
                        # Character is incapacitated (paralyzed, stunned, etc.)
                        # Show their condition and process end-of-turn effects
                        conditions = list(party_character.active_conditions.keys())
                        condition_names = ", ".join([c.upper() for c in conditions])
                        print_status_message(
                            f"{party_character.name} is {condition_names} and cannot act!",
                            "warning"
                        )

                        # Process end-of-turn effects (repeat saves, duration countdown)
                        results = party_character.process_end_of_turn_conditions(self.game_state.event_bus)
                        for result in results:
                            if result["type"] == "repeat_save_success":
                                save_result = result["save_result"]
                                print_status_message(
                                    f"✓ {party_character.name} succeeds on {save_result['ability'].upper()} save - {result['condition'].upper()} removed!",
                                    "success"
                                )
                            elif result["type"] == "duration_expired":
                                print_status_message(
                                    f"⏱ {result['condition'].upper()} on {party_character.name} has expired!",
                                    "info"
                                )

                        # Advance turn
                        self.game_state.initiative_tracker.next_turn()
                    else:
                        # Normal turn for conscious character
                        # Process turn-start effects (e.g., ongoing fire damage)
                        self._process_turn_start_effects(party_character)

                        # Check if character died from turn-start effects
                        if not party_character.is_alive:
                            print_error(f"{party_character.name} has died from turn-start effects!")
                            self.game_state.initiative_tracker.next_turn()
                            continue

                        # Check if character can act (not incapacitated or surprised)
                        if not party_character.can_take_actions():
                            conditions = [c.upper() for c in party_character.conditions]
                            condition_text = ", ".join(conditions)
                            print_status_message(f"⚠️  {party_character.name} is {condition_text} and cannot act this turn!", "warning")
                            # Process end-of-turn conditions (will remove surprised, etc.)
                            results = party_character.process_end_of_turn_conditions(self.game_state.event_bus)
                            for result in results:
                                if result["type"] == "condition_expired":
                                    if result["condition"] != "surprised":  # Don't announce surprised expiry
                                        print_status_message(
                                            f"⏱ {result['condition'].upper()} on {party_character.name} has expired!",
                                            "info"
                                        )
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
        # Use new InitiativeTracker API for assigning enemy numbers
        if self.game_state.initiative_tracker:
            player_creatures = [char for char in self.game_state.party.characters]
            self.game_state.initiative_tracker.assign_combat_numbers(player_creatures)

        # Build numbered enemy list for display using new display_name
        numbered_enemies = []
        if self.game_state.initiative_tracker:
            for entry in self.game_state.initiative_tracker.get_all_combatants():
                is_player = any(char == entry.creature for char in self.game_state.party.characters)
                if not is_player:
                    display_name = entry.display_name if entry.display_name else entry.creature.name
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
        victory = event.data.get("victory", True)
        total_xp = event.data.get("xp_gained", 0)
        xp_per_char = event.data.get("xp_per_character", 0)

        if victory:
            print_status_message(
                f"Victory! Party gained {total_xp} XP ({xp_per_char} XP per character)",
                "success"
            )
        else:
            print_error("Defeat! All party members have fallen unconscious.")
            print_status_message(
                "The enemies remain in the room. Consider healing and regrouping before attempting combat again.",
                "warning"
            )

        # Log combat end
        from dnd_engine.utils.logging_config import get_logging_config
        logging_config = get_logging_config()
        if logging_config:
            result = "Victory" if victory else "Defeat"
            logging_config.log_combat_event(
                f"Combat ended - {result} - Total XP: {total_xp}, XP per character: {xp_per_char}"
            )

        # Reset combat status flag
        self.combat_status_shown = False

        # Auto-save after combat
        self._auto_save("after_combat")

    def _on_boss_defeated(self, event: Event) -> None:
        """Handle boss defeated event."""
        dungeon_name = event.data.get("dungeon_name", "Unknown")
        console.print()
        console.print(
            Panel(
                f"[bold yellow]⚔️ BOSS DEFEATED![/bold yellow]\n\n"
                f"You have defeated the boss of {dungeon_name}!",
                border_style="yellow"
            )
        )

    def _on_dungeon_completed(self, event: Event) -> None:
        """Handle dungeon completed event."""
        dungeon_name = event.data.get("dungeon_name", "Unknown")
        unlocked_names = event.data.get("unlocked_names", [])
        campaign_complete = event.data.get("campaign_complete", False)

        console.print()

        if campaign_complete:
            console.print(
                Panel(
                    "[bold green]🎉 CAMPAIGN COMPLETE! 🎉[/bold green]\n\n"
                    f"You have completed {dungeon_name} and finished the entire campaign!\n\n"
                    "[dim]Congratulations, brave adventurers![/dim]",
                    border_style="green"
                )
            )
        else:
            unlocked_text = "\n".join(f"  🔓 {name}" for name in unlocked_names)
            console.print(
                Panel(
                    f"[bold cyan]✨ DUNGEON COMPLETE![/bold cyan]\n\n"
                    f"You have completed {dungeon_name}!\n\n"
                    f"[bold]New areas unlocked:[/bold]\n{unlocked_text}",
                    border_style="cyan"
                )
            )

    def _on_combat_fled(self, event: Event) -> None:
        """Handle combat fled event."""
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

        print_section("🎉 LEVEL UP!")
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
