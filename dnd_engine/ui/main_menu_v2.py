# ABOUTME: Main menu system with new save slot system and migration support
# ABOUTME: Handles menu display, save slot selection, character vault integration, and migration

from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

from dnd_engine.core.save_slot_manager import SaveSlotManager
from dnd_engine.core.save_slot import SaveSlot
from dnd_engine.core.character_vault_v2 import CharacterVaultV2
from dnd_engine.core.migration import MigrationManager
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.core.character import Character
from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.rules.loader import DataLoader
from dnd_engine.ui.rich_ui import (
    console,
    print_banner,
    print_choice_menu,
    print_section,
    print_status_message,
    print_input_prompt,
    print_error,
    print_message
)
from rich.table import Table
from rich.panel import Panel
from rich import box


class MainMenuV2:
    """
    Main menu system for D&D Terminal Game with new save slot system.

    Features:
    - 10-slot save system
    - Character vault integration
    - Automatic migration from old campaign system
    - Streamlined UI flows
    """

    def __init__(self):
        """Initialize the main menu with new save system."""
        # Check for and handle migration first
        self.migration_manager = MigrationManager()
        self._handle_migration_if_needed()

        # Initialize new systems
        self.slot_manager = SaveSlotManager()
        self.vault = CharacterVaultV2()
        self.data_loader = DataLoader()

        # Track current slot for save operations
        self.current_slot_number: Optional[int] = None

    def _handle_migration_if_needed(self) -> None:
        """Check for old campaigns and handle migration."""
        if not self.migration_manager.should_migrate():
            return

        # Show migration UI
        console.print()
        print_section("MIGRATION DETECTED")

        info = self.migration_manager.get_migration_info()

        console.print(f"\n[yellow]Found {info['total_campaigns']} old campaign(s)[/yellow]")
        console.print(f"[cyan]Will migrate:[/cyan] {info['migratable_campaigns']} most recent")
        console.print(f"[cyan]Will extract:[/cyan] {info['total_characters']} unique character(s)")

        if info['campaigns_to_migrate']:
            console.print("\n[bold]Campaigns to migrate:[/bold]")
            for i, camp in enumerate(info['campaigns_to_migrate'][:5], 1):
                console.print(f"  {i}. {camp['name']} ({camp['playtime']})")
            if len(info['campaigns_to_migrate']) > 5:
                console.print(f"  ... and {len(info['campaigns_to_migrate']) - 5} more")

        console.print("\n[dim]Backup will be created at: ~/.dnd_terminal/backup_pre_migration/[/dim]")
        console.print()

        confirm = console.input("[bold cyan]Proceed with migration? (yes/no):[/bold cyan] ").strip().lower()

        if confirm == 'yes':
            console.print("\n[yellow]Migrating...[/yellow]")

            success, message, stats = self.migration_manager.migrate()

            if success:
                print_status_message(message, "success")

                if stats.get('errors'):
                    console.print("\n[yellow]Warnings:[/yellow]")
                    for error in stats['errors'][:5]:
                        console.print(f"  [dim]• {error}[/dim]")

                console.print(f"\n[green]✓ Migrated {stats['campaigns_migrated']} campaign(s)[/green]")
                console.print(f"[green]✓ Extracted {stats['characters_migrated']} character(s)[/green]")

                console.print("\n[dim]Press Enter to continue...[/dim]")
                console.input()
            else:
                print_error(f"Migration failed: {message}")
                console.print("\n[yellow]You can try again later or start fresh.[/yellow]")
                console.print("[dim]Press Enter to continue...[/dim]")
                console.input()
        else:
            console.print("\n[yellow]Migration cancelled.[/yellow]")
            console.print("[dim]Note: Delete ~/.dnd_game/ to migrate later[/dim]")
            console.print("\n[dim]Press Enter to continue...[/dim]")
            console.input()

        console.clear()

    def show(self) -> Optional[str]:
        """
        Display the main menu and handle user choice.

        Returns:
            Menu choice: "new", "load", "vault", "manage", "exit"
        """
        print_banner("D&D 5E Terminal Adventure", version="0.2.0 (Save Slot System)", color="cyan")
        console.print()

        options = [
            {"number": "1", "text": "New Game"},
            {"number": "2", "text": "Load Game"},
            {"number": "3", "text": "Character Vault"},
            {"number": "4", "text": "Manage Save Slots"},
            {"number": "5", "text": "Exit"}
        ]

        print_choice_menu("Main Menu", options)
        console.print()

        choice = console.input("[bold cyan]Choose an option [1-5]:[/bold cyan] ").strip()

        choice_map = {
            "1": "new",
            "2": "load",
            "3": "vault",
            "4": "manage",
            "5": "exit"
        }

        return choice_map.get(choice)

    def show_save_slot_list(self, filter_empty: bool = False) -> None:
        """
        Display all save slots with their current state.

        Args:
            filter_empty: If True, only show non-empty slots
        """
        slots = self.slot_manager.list_slots()

        if filter_empty:
            slots = [slot for slot in slots if not slot.is_empty()]

        if not slots:
            print_status_message("No saved games found.", "warning")
            return

        console.print()
        print_section("SAVE SLOTS")
        console.print()

        for slot in slots:
            if slot.is_empty():
                status = "[dim]EMPTY[/dim]"
                panel_content = ["[dim]No game saved in this slot[/dim]"]
                border_style = "dim"
            else:
                status = slot.get_display_name()
                panel_content = [
                    f"[cyan]Last played:[/cyan] {slot.get_last_played_display()}",
                    f"[cyan]Playtime:[/cyan] {slot._format_playtime()}"
                ]

                if slot.party_composition:
                    party_str = ", ".join(slot.party_composition)
                    panel_content.append(f"[cyan]Party:[/cyan] {party_str}")

                if slot.adventure_progress:
                    panel_content.append(f"[cyan]Progress:[/cyan] {slot.adventure_progress}")

                border_style = "cyan"

            panel = Panel(
                "\n".join(panel_content),
                title=f"[bold cyan][Slot {slot.slot_number}][/bold cyan] {status}",
                border_style=border_style,
                padding=(0, 2)
            )
            console.print(panel)

    def handle_load_game(self) -> Optional[Tuple[GameState, int]]:
        """
        Handle load game flow.

        Returns:
            Tuple of (GameState, slot_number) if successful, None otherwise
        """
        self.show_save_slot_list(filter_empty=True)

        slots = self.slot_manager.list_slots()
        used_slots = [s for s in slots if not s.is_empty()]

        if not used_slots:
            console.print("\n[yellow]No saved games found.[/yellow]")
            return None

        console.print()
        choice = console.input("[bold cyan]Select slot number (1-10) or [B]ack:[/bold cyan] ").strip()

        if choice.lower() in ['b', 'back']:
            return None

        try:
            slot_num = int(choice)

            if not 1 <= slot_num <= 10:
                print_error("Invalid slot number. Must be between 1 and 10.")
                return None

            slot = self.slot_manager.get_slot(slot_num)

            if slot.is_empty():
                print_error(f"Slot {slot_num} is empty.")
                return None

            # Load game state
            game_state = self.slot_manager.load_game(slot_num)

            print_status_message(f"Loaded: {slot.get_display_name()}", "success")

            # Store current slot number for auto-save
            self.current_slot_number = slot_num

            return (game_state, slot_num)

        except ValueError:
            print_error("Invalid input. Please enter a number.")
            return None
        except Exception as e:
            print_error(f"Failed to load game: {e}")
            return None

    def handle_new_game(self) -> Optional[Tuple[GameState, int]]:
        """
        Handle new game flow with character vault and slot selection.

        Returns:
            Tuple of (GameState, slot_number) if successful, None otherwise
        """
        # Step 1: Select party from vault or create new
        console.print()
        print_section(
            "NEW GAME - SELECT PARTY",
            "Build your party by selecting 1-6 characters from your vault.\n"
            "Press [bold]C[/bold] to create new characters on the fly."
        )

        party_characters = self._select_party_from_vault()

        if not party_characters:
            console.print("\n[yellow]No party selected. Returning to menu.[/yellow]")
            return None

        # Step 2: Select adventure
        adventure_name = self._select_adventure()

        if not adventure_name:
            console.print("\n[yellow]No adventure selected. Returning to menu.[/yellow]")
            return None

        # Step 3: Select save slot
        console.print()
        print_section("SELECT SAVE SLOT")
        self.show_save_slot_list(filter_empty=False)
        console.print()

        choice = console.input("[bold cyan]Select slot number (1-10):[/bold cyan] ").strip()

        try:
            slot_num = int(choice)

            if not 1 <= slot_num <= 10:
                print_error("Invalid slot number. Must be between 1 and 10.")
                return None

            slot = self.slot_manager.get_slot(slot_num)

            # Confirm overwrite if not empty
            if not slot.is_empty():
                console.print(f"\n[yellow]⚠  Slot {slot_num} contains:[/yellow] {slot.get_display_name()}")
                confirm = console.input("[bold red]Overwrite this slot? (yes/no):[/bold red] ").strip().lower()

                if confirm != 'yes':
                    console.print("\n[yellow]Cancelled.[/yellow]")
                    return None

            # Step 4: Create game state
            party = Party(party_characters)
            game_state = GameState(
                party=party,
                dungeon_name=adventure_name,
                data_loader=self.data_loader
            )

            # Step 5: Save to slot
            self.slot_manager.save_game(
                slot_number=slot_num,
                game_state=game_state,
                playtime_delta=0
            )

            # Step 6: Record character usage in vault
            for character in party_characters:
                # Find character ID in vault by name (not ideal, but works for now)
                char_list = self.vault.list_characters()
                for char_info in char_list:
                    if char_info['name'] == character.name:
                        self.vault.record_usage(char_info['id'], slot_num)
                        break

            print_status_message(f"Game saved to Slot {slot_num}", "success")

            # Store current slot number
            self.current_slot_number = slot_num

            return (game_state, slot_num)

        except ValueError:
            print_error("Invalid input. Please enter a number.")
            return None
        except Exception as e:
            print_error(f"Failed to create game: {e}")
            return None

    def _select_party_from_vault(self) -> List[Character]:
        """
        Select party members from character vault or create new.

        Returns:
            List of selected characters (1-6)
        """
        selected_characters = []

        while len(selected_characters) < 6:
            console.print()
            print_section(f"SELECT CHARACTER #{len(selected_characters) + 1}")

            # Show vault characters
            char_list = self.vault.list_characters()

            if char_list:
                console.print("\n[bold]Characters in Vault:[/bold]")
                for i, char_info in enumerate(char_list, 1):
                    usage_str = f"Used {char_info['times_used']} times" if char_info['times_used'] > 0 else "Never used"
                    console.print(
                        f"  [{i}] {char_info['name']} - "
                        f"Level {char_info['level']} {char_info['class']} "
                        f"[dim]({usage_str})[/dim]"
                    )
            else:
                console.print("\n[dim]No characters in vault yet.[/dim]")

            console.print(f"\n  [C] Create new character")
            console.print(f"  [F] Finish party selection (current: {len(selected_characters)})")

            if len(selected_characters) == 0:
                console.print("\n[dim]Note: You need at least 1 character[/dim]")

            console.print()
            choice = console.input(f"[bold cyan]Select option:[/bold cyan] ").strip()

            if choice.upper() == 'F':
                if len(selected_characters) > 0:
                    break
                else:
                    console.print("\n[yellow]You need at least 1 character.[/yellow]")
                    continue

            elif choice.upper() == 'C':
                # Create new character
                new_char = self._create_character_interactive()
                if new_char:
                    # Add to vault
                    char_id = self.vault.add_character(new_char)
                    selected_characters.append(new_char)
                    print_status_message(f"Added {new_char.name} to party", "success")

            elif choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(char_list):
                    char_info = char_list[idx - 1]
                    character = self.vault.get_character(char_info['id'])
                    selected_characters.append(character)
                    print_status_message(f"Added {character.name} to party", "success")
                else:
                    print_error("Invalid character number.")
            else:
                print_error("Invalid input.")

        return selected_characters

    def _create_character_interactive(self) -> Optional[Character]:
        """
        Create a new character interactively.

        Returns:
            Created Character or None if cancelled
        """
        console.print()
        print_section("CREATE CHARACTER")

        factory = CharacterFactory()

        try:
            character = factory.create_character_interactive(
                ui=None,
                data_loader=self.data_loader
            )
            return character
        except KeyboardInterrupt:
            console.print("\n[yellow]Character creation cancelled.[/yellow]")
            return None
        except Exception as e:
            print_error(f"Character creation failed: {e}")
            return None

    def _select_adventure(self) -> Optional[str]:
        """
        Select an adventure/dungeon to play.

        Returns:
            Dungeon filename or None if cancelled
        """
        console.print()
        print_section("SELECT ADVENTURE")

        # List available dungeons
        dungeons_dir = Path(__file__).parent.parent / "data" / "content" / "dungeons"
        dungeon_files = list(dungeons_dir.glob("*.json"))

        # Filter out test dungeons
        dungeon_files = [f for f in dungeon_files if not f.stem.startswith("test_") and not f.stem.startswith("multi_char_")]

        if not dungeon_files:
            print_error("No adventures found!")
            return None

        console.print("\n[bold]Available Adventures:[/bold]")
        for i, dungeon_file in enumerate(dungeon_files, 1):
            # Convert filename to display name
            display_name = dungeon_file.stem.replace('_', ' ').title()
            console.print(f"  [{i}] {display_name}")

        console.print()
        choice = console.input(f"[bold cyan]Select adventure [1-{len(dungeon_files)}]:[/bold cyan] ").strip()

        try:
            idx = int(choice)
            if 1 <= idx <= len(dungeon_files):
                selected_file = dungeon_files[idx - 1]
                return selected_file.stem  # Return filename without extension
            else:
                print_error("Invalid adventure number.")
                return None
        except ValueError:
            print_error("Invalid input.")
            return None

    def handle_character_vault(self) -> None:
        """Handle character vault management menu."""
        while True:
            console.print()
            print_section("CHARACTER VAULT")

            char_list = self.vault.list_characters()

            if not char_list:
                console.print("\n[yellow]No characters in vault.[/yellow]")
            else:
                console.print()
                for char_info in char_list:
                    panel_content = [
                        f"[cyan]Class:[/cyan] {char_info['class']}",
                        f"[cyan]Level:[/cyan] {char_info['level']}",
                        f"[cyan]Race:[/cyan] {char_info['race']}",
                    ]

                    if char_info['times_used'] > 0:
                        panel_content.append(f"[cyan]Times used:[/cyan] {char_info['times_used']}")
                        panel_content.append(f"[cyan]Slots:[/cyan] {', '.join(map(str, char_info['save_slots_used']))}")

                    panel = Panel(
                        "\n".join(panel_content),
                        title=f"[bold white]{char_info['name']}[/bold white]",
                        border_style="cyan",
                        padding=(0, 2)
                    )
                    console.print(panel)

            console.print(f"\n[bold]Actions:[/bold]")
            console.print("  [C] Create new character")
            if char_list:
                console.print("  [D] Delete character")
            console.print("  [B] Back to main menu")

            console.print()
            choice = console.input("[bold cyan]Select action:[/bold cyan] ").strip().upper()

            if choice == 'B':
                break
            elif choice == 'C':
                new_char = self._create_character_interactive()
                if new_char:
                    self.vault.add_character(new_char)
                    print_status_message(f"Added {new_char.name} to vault", "success")
            elif choice == 'D' and char_list:
                console.print()
                for i, char_info in enumerate(char_list, 1):
                    console.print(f"  [{i}] {char_info['name']}")

                del_choice = console.input("\n[bold cyan]Delete character number:[/bold cyan] ").strip()

                try:
                    idx = int(del_choice)
                    if 1 <= idx <= len(char_list):
                        char_info = char_list[idx - 1]
                        confirm = console.input(f"[bold red]Delete {char_info['name']}? (yes/no):[/bold red] ").strip().lower()

                        if confirm == 'yes':
                            self.vault.delete_character(char_info['id'])
                            print_status_message(f"Deleted {char_info['name']}", "success")
                except ValueError:
                    print_error("Invalid input.")
            else:
                print_error("Invalid action.")

            console.print("\n[dim]Press Enter to continue...[/dim]")
            console.input()

    def handle_manage_slots(self) -> None:
        """Handle save slot management menu."""
        while True:
            console.print()
            self.show_save_slot_list(filter_empty=False)

            console.print(f"\n[bold]Actions:[/bold]")
            console.print("  [R] Rename slot")
            console.print("  [C] Clear slot")
            console.print("  [B] Back to main menu")

            console.print()
            choice = console.input("[bold cyan]Select action:[/bold cyan] ").strip().upper()

            if choice == 'B':
                break
            elif choice == 'R':
                slot_num = console.input("\n[bold cyan]Slot number to rename:[/bold cyan] ").strip()
                try:
                    num = int(slot_num)
                    if 1 <= num <= 10:
                        new_name = console.input("[bold cyan]Enter custom name (empty for auto-name):[/bold cyan] ").strip()
                        self.slot_manager.rename_slot(num, new_name)
                        print_status_message(f"Renamed Slot {num}", "success")
                except ValueError:
                    print_error("Invalid slot number.")
            elif choice == 'C':
                slot_num = console.input("\n[bold cyan]Slot number to clear:[/bold cyan] ").strip()
                try:
                    num = int(slot_num)
                    if 1 <= num <= 10:
                        slot = self.slot_manager.get_slot(num)
                        if slot.is_empty():
                            print_status_message("Slot is already empty.", "info")
                        else:
                            confirm = console.input(f"[bold red]Clear slot {num}? This cannot be undone! (yes/no):[/bold red] ").strip().lower()
                            if confirm == 'yes':
                                self.slot_manager.clear_slot(num)
                                print_status_message(f"Cleared Slot {num}", "success")
                except ValueError:
                    print_error("Invalid slot number.")
            else:
                print_error("Invalid action.")

            console.print("\n[dim]Press Enter to continue...[/dim]")
            console.input()

    def run(self) -> Optional[Tuple[GameState, int]]:
        """
        Run the main menu loop until user makes a valid selection.

        Returns:
            Tuple of (GameState, slot_number) if a game is loaded/created, None if user exits
        """
        while True:
            choice = self.show()

            if choice == "exit":
                print_status_message("Thanks for playing!", "info")
                return None

            elif choice == "load":
                result = self.handle_load_game()
                if result:
                    return result

            elif choice == "new":
                result = self.handle_new_game()
                if result:
                    return result

            elif choice == "vault":
                self.handle_character_vault()

            elif choice == "manage":
                self.handle_manage_slots()

            else:
                print_error("Invalid choice. Please select a valid option.")

            console.print()
            console.print("[dim]Press Enter to continue...[/dim]")
            console.input()
            console.clear()
