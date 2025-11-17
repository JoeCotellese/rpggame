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

    def __init__(self, game_state: GameState):
        """
        Initialize the CLI.

        Args:
            game_state: The game state to interact with
        """
        self.game_state = game_state
        self.running = True
        self.narrative_pending = False

        # Subscribe to game events for display
        self.game_state.event_bus.subscribe(EventType.COMBAT_START, self._on_combat_start)
        self.game_state.event_bus.subscribe(EventType.COMBAT_END, self._on_combat_end)
        self.game_state.event_bus.subscribe(EventType.DAMAGE_DEALT, self._on_damage_dealt)
        self.game_state.event_bus.subscribe(EventType.ITEM_ACQUIRED, self._on_item_acquired)
        self.game_state.event_bus.subscribe(EventType.GOLD_ACQUIRED, self._on_gold_acquired)
        self.game_state.event_bus.subscribe(EventType.ENHANCEMENT_STARTED, self._on_enhancement_started)
        self.game_state.event_bus.subscribe(EventType.DESCRIPTION_ENHANCED, self._on_description_enhanced)

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
        Get a command from the player.

        Returns:
            Player's command as a string
        """
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

        if command.startswith("move ") or command.startswith("go "):
            direction = command.split()[1] if len(command.split()) > 1 else ""
            self.handle_move(direction)
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

        if command in ["inventory", "i", "inv"]:
            self.display_inventory()
            return

        if command.startswith("equip "):
            item_id = " ".join(command.split()[1:])
            self.handle_equip(item_id)
            return

        if command.startswith("unequip "):
            slot_name = " ".join(command.split()[1:])
            self.handle_unequip(slot_name)
            return

        if command.startswith("use "):
            item_id = " ".join(command.split()[1:])
            self.handle_use_item(item_id)
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

        if command in ["status", "stats"]:
            self.display_combat_status()
            return

        print_status_message("Unknown combat command. Type 'help' for available commands.", "warning")

    def handle_move(self, direction: str) -> None:
        """Handle movement command."""
        if not direction:
            print_status_message("Specify a direction (e.g., 'move north')", "warning")
            return

        success = self.game_state.move(direction)
        if success:
            print_status_message(f"You move {direction}", "info")
            self.display_room()
        else:
            if self.game_state.in_combat:
                print_error("You cannot move during combat!")
            else:
                print_error(f"You cannot go {direction} from here")

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

        # Perform attack
        result = self.game_state.combat_engine.resolve_attack(
            attacker=attacker,
            defender=target,
            attack_bonus=attacker.melee_attack_bonus,
            damage_dice=f"1d8+{attacker.melee_damage_bonus}",
            apply_damage=True
        )

        # Display mechanics in panel
        print_mechanics_panel(str(result))

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

                print_mechanics_panel(str(result))

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

    def display_inventory(self) -> None:
        """Display all party members' inventories with item details."""
        items_data = self.game_state.data_loader.load_items()
        from dnd_engine.systems.inventory import EquipmentSlot

        for character in self.game_state.party.characters:
            inventory = character.inventory

            # Build inventory data for rich table
            inventory_items = {}

            # Add equipped items
            weapon_id = inventory.get_equipped_item(EquipmentSlot.WEAPON)
            armor_id = inventory.get_equipped_item(EquipmentSlot.ARMOR)

            # Add items by category
            for category in ["weapons", "armor", "consumables"]:
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

            # Display character title
            alive_marker = "✓" if character.is_alive else "💀"
            print_title(f"{alive_marker} {character.name} - Gold: {inventory.gold} gp")

            # Create and display inventory table
            if inventory_items:
                table = create_inventory_table(inventory_items)
                console.print(table)
            else:
                print_status_message("No items in inventory", "info")

    def handle_equip(self, item_id: str) -> None:
        """Handle equipping an item for the first living party member."""
        living_members = self.game_state.party.get_living_members()
        if not living_members:
            print_error("No living party members to equip items!")
            return

        character = living_members[0]
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
            print_error(f"You don't have '{item_id}' in your inventory.")
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

    def handle_unequip(self, slot_name: str) -> None:
        """Handle unequipping an item for the first living party member."""
        living_members = self.game_state.party.get_living_members()
        if not living_members:
            print_error("No living party members to unequip items!")
            return

        character = living_members[0]
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
            print_status_message(f"Nothing equipped in {slot_name} slot.", "warning")

    def handle_use_item(self, item_id: str) -> None:
        """Handle using a consumable item for the first living party member."""
        living_members = self.game_state.party.get_living_members()
        if not living_members:
            print_error("No living party members to use items!")
            return

        character = living_members[0]
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

    def display_help_exploration(self) -> None:
        """Display help for exploration commands."""
        commands = [
            ("move <direction>", "Move in a direction (north, south, east, west)"),
            ("look or l", "Look around the current room"),
            ("search", "Search the room for items"),
            ("inventory / i", "Show your inventory"),
            ("equip <item>", "Equip a weapon or armor"),
            ("unequip <slot>", "Unequip weapon or armor"),
            ("use <item>", "Use a consumable item"),
            ("status", "Show your character status"),
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

    def _on_combat_end(self, event: Event) -> None:
        """Handle combat end event."""
        total_xp = event.data.get("xp_gained", 0)
        xp_per_char = event.data.get("xp_per_character", 0)
        print_status_message(
            f"Victory! Party gained {total_xp} XP ({xp_per_char} XP per character)",
            "success"
        )

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

        # Only show loading for combat actions (not room descriptions)
        if description_type == "combat":
            self.narrative_pending = True
            print_narrative_loading()

    def _on_description_enhanced(self, event: Event) -> None:
        """Handle LLM-enhanced description event."""
        description_type = event.data.get("type", "unknown")
        text = event.data.get("text", "")

        if text:
            # Display enhanced descriptions in appropriate panels
            if description_type == "combat" or description_type == "death" or description_type == "victory":
                # Use narrative panel for combat-related narratives
                self.narrative_pending = False
                print_narrative_panel(text)
            elif description_type == "room":
                # Room descriptions use the old style for now
                from rich.markdown import Markdown
                console.print(Markdown(text), style="cyan")
            else:
                console.print(text)
