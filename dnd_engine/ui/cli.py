# ABOUTME: Command-line interface for the D&D 5E terminal game
# ABOUTME: Handles player input, displays game state, and manages the game loop

import sys
from typing import Optional
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.combat import AttackResult
from dnd_engine.utils.events import EventBus, Event, EventType


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

        # Subscribe to game events for display
        self.game_state.event_bus.subscribe(EventType.COMBAT_START, self._on_combat_start)
        self.game_state.event_bus.subscribe(EventType.COMBAT_END, self._on_combat_end)
        self.game_state.event_bus.subscribe(EventType.DAMAGE_DEALT, self._on_damage_dealt)
        self.game_state.event_bus.subscribe(EventType.ITEM_ACQUIRED, self._on_item_acquired)
        self.game_state.event_bus.subscribe(EventType.GOLD_ACQUIRED, self._on_gold_acquired)

    def display_banner(self) -> None:
        """Display the game banner."""
        print("\n" + "=" * 60)
        print("D&D 5E TERMINAL GAME")
        print("=" * 60 + "\n")

    def display_room(self) -> None:
        """Display the current room description."""
        desc = self.game_state.get_room_description()
        print("\n" + "-" * 60)
        print(desc)
        print("-" * 60)

    def display_player_status(self) -> None:
        """Display player character status."""
        status = self.game_state.get_player_status()
        print(f"\n{status['name']} (Level {status['level']} Fighter)")
        print(f"HP: {status['hp']}/{status['max_hp']} | AC: {status['ac']} | XP: {status['xp']}")

    def display_combat_status(self) -> None:
        """Display combat status and initiative order."""
        if not self.game_state.in_combat or not self.game_state.initiative_tracker:
            return

        print("\n" + "~" * 60)
        print("COMBAT!")
        print("~" * 60)

        # Show initiative order
        for entry in self.game_state.initiative_tracker.get_all_combatants():
            current = "→" if entry == self.game_state.initiative_tracker.get_current_combatant() else " "
            status = "DEAD" if not entry.creature.is_alive else f"HP: {entry.creature.current_hp}/{entry.creature.max_hp}"
            print(f"{current} {entry.creature.name} (Init: {entry.initiative_total}) - {status}")

        print("~" * 60)

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
            print("\nThanks for playing!")
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

        print("Unknown command. Type 'help' for available commands.")

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

        print("Unknown combat command. Type 'help' for available commands.")

    def handle_move(self, direction: str) -> None:
        """Handle movement command."""
        if not direction:
            print("Specify a direction (e.g., 'move north').")
            return

        success = self.game_state.move(direction)
        if success:
            print(f"\nYou move {direction}.")
            self.display_room()
        else:
            if self.game_state.in_combat:
                print("You cannot move during combat!")
            else:
                print(f"You cannot go {direction} from here.")

    def handle_search(self) -> None:
        """Handle search command."""
        items = self.game_state.search_room()
        if items:
            print(f"\nYou search the room and find:")
            for item in items:
                if item["type"] == "gold":
                    print(f"  - {item['amount']} gold pieces")
                else:
                    print(f"  - {item.get('id', 'an item')}")
        else:
            room = self.game_state.get_current_room()
            if room.get("searched"):
                print("\nYou've already searched this room.")
            else:
                print("\nYou find nothing of interest.")

    def handle_attack(self, target_name: str) -> None:
        """Handle attack command during combat."""
        if not self.game_state.in_combat:
            print("You're not in combat!")
            return

        # Check if it's the player's turn
        current = self.game_state.initiative_tracker.get_current_combatant()
        if current.creature != self.game_state.player:
            print(f"It's {current.creature.name}'s turn, not yours!")
            return

        # Find target
        target = None
        for enemy in self.game_state.active_enemies:
            if enemy.is_alive and enemy.name.lower() == target_name.lower():
                target = enemy
                break

        if not target:
            print(f"No such enemy: {target_name}")
            living_enemies = [e.name for e in self.game_state.active_enemies if e.is_alive]
            if living_enemies:
                print(f"Available targets: {', '.join(living_enemies)}")
            return

        # Perform attack
        result = self.game_state.combat_engine.resolve_attack(
            attacker=self.game_state.player,
            defender=target,
            attack_bonus=self.game_state.player.melee_attack_bonus,
            damage_dice=f"1d8+{self.game_state.player.melee_damage_bonus}",
            apply_damage=True
        )

        # Display result
        print(f"\n{result}")

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
            print(f"\n{target.name} is defeated!")
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
        """Process all enemy turns until it's the player's turn again."""
        while self.game_state.in_combat:
            current = self.game_state.initiative_tracker.get_current_combatant()

            # If it's the player's turn, stop
            if current.creature == self.game_state.player:
                print(f"\n--- Your turn ---")
                break

            # Enemy turn
            enemy = current.creature
            if not enemy.is_alive:
                self.game_state.initiative_tracker.next_turn()
                continue

            print(f"\n{enemy.name}'s turn...")

            # Simple AI: attack the player
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
                    defender=self.game_state.player,
                    attack_bonus=action["attack_bonus"],
                    damage_dice=action["damage"],
                    apply_damage=True
                )

                print(result)

                if result.hit:
                    self.game_state.event_bus.emit(Event(
                        type=EventType.DAMAGE_DEALT,
                        data={
                            "attacker": enemy.name,
                            "defender": self.game_state.player.name,
                            "damage": result.damage
                        }
                    ))

            # Next turn
            self.game_state.initiative_tracker.next_turn()

            # Check if player died
            if not self.game_state.player.is_alive:
                break

    def display_inventory(self) -> None:
        """Display the player's inventory with item details."""
        inventory = self.game_state.player.inventory
        items_data = self.game_state.data_loader.load_items()

        print("\n" + "=" * 60)
        print("INVENTORY")
        print("=" * 60)

        # Display gold
        print(f"\nGold: {inventory.gold} gp")

        # Display equipped items
        print("\nEquipped:")
        from dnd_engine.systems.inventory import EquipmentSlot

        weapon_id = inventory.get_equipped_item(EquipmentSlot.WEAPON)
        armor_id = inventory.get_equipped_item(EquipmentSlot.ARMOR)

        if weapon_id:
            weapon_data = items_data["weapons"].get(weapon_id, {})
            weapon_name = weapon_data.get("name", weapon_id)
            print(f"  Weapon: {weapon_name}")
        else:
            print(f"  Weapon: (none)")

        if armor_id:
            armor_data = items_data["armor"].get(armor_id, {})
            armor_name = armor_data.get("name", armor_id)
            print(f"  Armor: {armor_name}")
        else:
            print(f"  Armor: (none)")

        # Display items by category
        if inventory.is_empty():
            print("\nItems: (none)")
        else:
            print("\nItems:")
            for category in ["weapons", "armor", "consumables"]:
                category_items = inventory.get_items_by_category(category)
                if category_items:
                    print(f"\n  {category.title()}:")
                    for inv_item in category_items:
                        item_data = items_data[category].get(inv_item.item_id, {})
                        item_name = item_data.get("name", inv_item.item_id)
                        qty_str = f" x{inv_item.quantity}" if inv_item.quantity > 1 else ""
                        equipped = ""
                        if inv_item.item_id == weapon_id or inv_item.item_id == armor_id:
                            equipped = " [equipped]"
                        print(f"    - {item_name}{qty_str}{equipped}")

        print("=" * 60)

    def handle_equip(self, item_id: str) -> None:
        """Handle equipping an item."""
        inventory = self.game_state.player.inventory
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
            print(f"You don't have '{item_id}' in your inventory.")
            return

        # Equip the item
        from dnd_engine.systems.inventory import EquipmentSlot

        if target_category == "weapons":
            slot = EquipmentSlot.WEAPON
        elif target_category == "armor":
            slot = EquipmentSlot.ARMOR
        else:
            print(f"Cannot equip {item_id}")
            return

        inventory.equip_item(target_item, slot)

        item_data = items_data[target_category][target_item]
        item_name = item_data.get("name", target_item)
        print(f"\nEquipped {item_name}")

        # Emit event
        self.game_state.event_bus.emit(Event(
            type=EventType.ITEM_EQUIPPED,
            data={"item_id": target_item, "slot": slot.value}
        ))

    def handle_unequip(self, slot_name: str) -> None:
        """Handle unequipping an item."""
        from dnd_engine.systems.inventory import EquipmentSlot

        slot = None
        if slot_name.lower() in ["weapon", "w"]:
            slot = EquipmentSlot.WEAPON
        elif slot_name.lower() in ["armor", "a"]:
            slot = EquipmentSlot.ARMOR
        else:
            print(f"Unknown equipment slot: {slot_name}. Use 'weapon' or 'armor'.")
            return

        inventory = self.game_state.player.inventory
        item_id = inventory.unequip_item(slot)

        if item_id:
            items_data = self.game_state.data_loader.load_items()
            category = "weapons" if slot == EquipmentSlot.WEAPON else "armor"
            item_data = items_data[category].get(item_id, {})
            item_name = item_data.get("name", item_id)
            print(f"\nUnequipped {item_name}")

            # Emit event
            self.game_state.event_bus.emit(Event(
                type=EventType.ITEM_UNEQUIPPED,
                data={"item_id": item_id, "slot": slot.value}
            ))
        else:
            print(f"\nNothing equipped in {slot_name} slot.")

    def handle_use_item(self, item_id: str) -> None:
        """Handle using a consumable item."""
        inventory = self.game_state.player.inventory
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
            print(f"You don't have a consumable '{item_id}' in your inventory.")
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

            old_hp = self.game_state.player.current_hp
            self.game_state.player.heal(healing)
            actual_healing = self.game_state.player.current_hp - old_hp

            print(f"\nYou use {item_name}")
            print(f"Healing: {roll} = {healing} HP")
            print(f"You recover {actual_healing} HP (now at {self.game_state.player.current_hp}/{self.game_state.player.max_hp})")
        else:
            print(f"\nYou use {item_name}")

        # Remove the item from inventory
        inventory.remove_item(target_item, 1)

        # Emit event
        self.game_state.event_bus.emit(Event(
            type=EventType.ITEM_USED,
            data={"item_id": target_item, "effect": effect}
        ))

    def display_help_exploration(self) -> None:
        """Display help for exploration commands."""
        print("\nExploration Commands:")
        print("  move <direction>  - Move in a direction (north, south, east, west)")
        print("  look              - Look around the current room")
        print("  search            - Search the room for items")
        print("  inventory         - Show your inventory (shortcut: i)")
        print("  equip <item>      - Equip a weapon or armor")
        print("  unequip <slot>    - Unequip weapon or armor")
        print("  use <item>        - Use a consumable item")
        print("  status            - Show your character status")
        print("  help              - Show this help message")
        print("  quit              - Exit the game")

    def display_help_combat(self) -> None:
        """Display help for combat commands."""
        print("\nCombat Commands:")
        print("  attack <enemy>    - Attack an enemy (e.g., 'attack goblin')")
        print("  status            - Show combat status")
        print("  help              - Show this help message")

    def run(self) -> None:
        """Run the main game loop."""
        self.display_banner()
        self.display_room()
        self.display_player_status()

        print("\nType 'help' for available commands.")

        while self.running and not self.game_state.is_game_over():
            if self.game_state.in_combat:
                self.display_combat_status()
                current = self.game_state.initiative_tracker.get_current_combatant()

                if current.creature == self.game_state.player:
                    command = self.get_player_command()
                    self.process_combat_command(command)
                else:
                    self.process_enemy_turns()
            else:
                command = self.get_player_command()
                self.process_exploration_command(command)

        # Game over
        if self.game_state.is_game_over():
            print("\n" + "=" * 60)
            print("GAME OVER")
            print("You have been defeated!")
            print("=" * 60)

    def _on_combat_start(self, event: Event) -> None:
        """Handle combat start event."""
        enemies = event.data.get("enemies", [])
        print(f"\n⚔️  Combat begins! Enemies: {', '.join(enemies)}")

    def _on_combat_end(self, event: Event) -> None:
        """Handle combat end event."""
        xp = event.data.get("xp_gained", 0)
        print(f"\n✓ Victory! You gained {xp} XP.")

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
