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

    def display_help_exploration(self) -> None:
        """Display help for exploration commands."""
        print("\nExploration Commands:")
        print("  move <direction>  - Move in a direction (north, south, east, west)")
        print("  look              - Look around the current room")
        print("  search            - Search the room for items")
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
