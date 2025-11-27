# ABOUTME: Main menu system with new save slot system and migration support
# ABOUTME: Handles menu display, save slot selection, character vault integration, and migration

import questionary
from rich.panel import Panel

from dnd_engine.core.campaign_progress import CampaignProgressTracker
from dnd_engine.core.character import Character
from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.character_vault_v2 import CharacterVaultV2
from dnd_engine.core.game_state import GameState
from dnd_engine.core.migration import MigrationManager
from dnd_engine.core.party import Party
from dnd_engine.core.room_registry import RoomRegistry
from dnd_engine.core.save_slot_manager import SaveSlotManager
from dnd_engine.rules.loader import DataLoader
from dnd_engine.ui.rich_ui import (
    console,
    print_banner,
    print_choice_menu,
    print_error,
    print_section,
    print_status_message,
)


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
        self.campaign_tracker = CampaignProgressTracker()

        # Track current slot for save operations
        self.current_slot_number: int | None = None

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

    def show(self) -> str | None:
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

    def handle_load_game(self) -> tuple[GameState, int] | None:
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

            # Load game state - returns tuple of (game_state, campaign_progress)
            game_state, campaign_progress = self.slot_manager.load_game(slot_num)

            # Store campaign progress on game_state if available
            if campaign_progress:
                game_state.campaign_progress = campaign_progress

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

    def handle_new_game(self) -> tuple[GameState, int] | None:
        """
        Handle new game flow with character vault and slot selection.

        Returns:
            Tuple of (GameState, slot_number) if successful, None otherwise
        """
        # Step 1: Select campaign
        campaign_info = self._select_adventure()

        if not campaign_info:
            console.print("\n[yellow]No campaign selected. Returning to menu.[/yellow]")
            return None

        # Step 2: Select party from vault or create new
        console.print()
        level_range = campaign_info.get("level_range", "Any")
        print_section(
            "SELECT PARTY",
            f"Campaign: {campaign_info['name']} (Level {level_range})\n"
            "Build your party by selecting 1-6 characters from your vault.\n"
            "Press [bold]C[/bold] to create new characters on the fly."
        )

        party_characters = self._select_party_from_vault()

        if not party_characters:
            console.print("\n[yellow]No party selected. Returning to menu.[/yellow]")
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

            # Step 4: Create game state with campaign progress
            party = Party(party_characters)
            campaign_progress = campaign_info.get("campaign_progress")

            # Use room registry to find the dungeon containing the starting room
            starting_room = campaign_info["starting_room"]
            dungeons_path = self.data_loader.data_path / "content" / "dungeons"
            room_registry = RoomRegistry(dungeons_path)
            starting_dungeon = room_registry.get_dungeon_for_room(starting_room)

            if not starting_dungeon:
                print_error(f"Could not find dungeon for room: {starting_room}")
                return None

            game_state = GameState(
                party=party,
                dungeon_name=starting_dungeon,
                campaign_id=campaign_info["campaign_id"],
                data_loader=self.data_loader,
                campaign_progress=campaign_progress
            )

            # Override to start at the campaign's specific starting room
            game_state.current_room_id = starting_room

            # Step 5: Save to slot with campaign progress
            self.slot_manager.save_game(
                slot_number=slot_num,
                game_state=game_state,
                playtime_delta=0,
                campaign_progress=campaign_progress
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

    def _select_party_from_vault(self) -> list[Character]:
        """
        Select party members from character vault or create new.

        Returns:
            List of selected characters (1-6)
        """
        selected_characters: list[Character] = []
        char_list = self.vault.list_characters()

        # Step 1: Select from existing vault characters (if any)
        if char_list:
            console.print()

            # Build choices for questionary
            choices = []
            for char_info in char_list:
                display = (
                    f"{char_info['name']} - "
                    f"Level {char_info['level']} {char_info['class']}"
                )
                choices.append(questionary.Choice(title=display, value=char_info['id']))

            def validate_selection(selected: list) -> bool | str:
                if len(selected) > 6:
                    return "Maximum 6 characters in a party"
                return True

            try:
                selected_ids = questionary.checkbox(
                    "Select characters for your party (1-6):",
                    choices=choices,
                    validate=validate_selection,
                    instruction="(Space to toggle, Enter to confirm)"
                ).ask()

                if selected_ids:
                    for char_id in selected_ids:
                        character = self.vault.get_character(char_id)
                        selected_characters.append(character)

            except (EOFError, KeyboardInterrupt):
                return []

        # Step 2: Offer to create new characters if party isn't full
        while len(selected_characters) < 6:
            if len(selected_characters) == 0:
                prompt = "No characters selected. Create a new character?"
            else:
                party_names = ", ".join(c.name for c in selected_characters)
                prompt = f"Party: {party_names}\nCreate another character?"

            try:
                create_more = questionary.confirm(
                    prompt,
                    default=len(selected_characters) == 0  # Default yes if no characters
                ).ask()
            except (EOFError, KeyboardInterrupt):
                if len(selected_characters) > 0:
                    break
                return []

            if not create_more:
                break

            # Create new character
            new_char = self._create_character_interactive()
            if new_char:
                self.vault.add_character(new_char)
                selected_characters.append(new_char)
                print_status_message(f"Added {new_char.name} to party", "success")

        return selected_characters

    def _create_character_interactive(self) -> Character | None:
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

    def _select_adventure(self) -> dict | None:
        """
        Select a campaign to play.

        Shows campaigns with dungeon progression info:
        - ✓ = completed, 🔓 = unlocked/available, 🔒 = locked

        Returns:
            Dict with campaign_id, starting_dungeon, and campaign_progress, or None if cancelled
        """
        console.print()
        print_section("SELECT CAMPAIGN")

        # List available campaigns
        campaigns = self.campaign_tracker.list_available_campaigns()

        if not campaigns:
            print_error("No campaigns found!")
            return None

        # Build choices for questionary with rich display
        choices = []
        for campaign in campaigns:
            level_range = campaign.level_range
            playtime = campaign.estimated_playtime
            display = f"{campaign.name} (Level {level_range}, ~{playtime})"
            choices.append(questionary.Choice(title=display, value=campaign.id))

        choices.append(questionary.Choice(title="← Back", value=None))

        try:
            selected_id = questionary.select(
                "Choose a campaign:",
                choices=choices,
                use_arrow_keys=True
            ).ask()
        except (EOFError, KeyboardInterrupt):
            return None

        if not selected_id:
            return None

        # Find the selected campaign definition
        definition = self.campaign_tracker.load_campaign_definition(selected_id)
        if not definition:
            return None

        # Create initial progress for new game
        progress = self.campaign_tracker.create_initial_progress(selected_id)
        if not progress:
            return None

        # Display dungeon progression info
        console.print()
        print_section(f"{definition.name} - Dungeon Progression")
        console.print()
        console.print(f"[dim]{definition.description}[/dim]")
        console.print()

        # Show dungeons with lock states
        ordered_dungeons = self.campaign_tracker.get_ordered_dungeons(selected_id)
        for dungeon_id, dungeon_def in ordered_dungeons:
            state = self.campaign_tracker.get_dungeon_state(progress, dungeon_id)

            # State icons
            if state == "completed":
                icon = "[green]✓[/green]"
            elif state == "unlocked":
                icon = "[cyan]🔓[/cyan]"
            else:
                icon = "[dim]🔒[/dim]"

            # Dungeon display
            if state == "locked":
                console.print(f"  {icon} [dim]{dungeon_def.name}[/dim]")
            else:
                console.print(f"  {icon} {dungeon_def.name}")

        console.print()

        # Use campaign's starting_room to determine where to begin
        starting_room = definition.starting_room
        if not starting_room:
            print_error("Campaign has no starting room defined!")
            return None

        return {
            "campaign_id": definition.id,
            "name": definition.name,
            "level_range": definition.level_range,
            "starting_room": starting_room,
            "campaign_progress": progress
        }

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

            console.print("\n[bold]Actions:[/bold]")
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

            console.print("\n[bold]Actions:[/bold]")
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

    def run(self) -> tuple[GameState, int] | None:
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
