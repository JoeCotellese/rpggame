# ABOUTME: Main menu system for game startup and campaign management
# ABOUTME: Handles menu display, input, and navigation between campaigns and character vault

from typing import Optional, List, Dict, Any, Callable
from pathlib import Path

from dnd_engine.core.campaign_manager import CampaignManager
from dnd_engine.core.character_vault import CharacterVault
from dnd_engine.core.game_state import GameState
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


class MainMenu:
    """
    Main menu system for D&D Terminal Game.

    Handles:
    - Game startup flow
    - Campaign selection and management
    - Character Vault access
    - Quick Start for new players
    - Continue Last Campaign
    """

    def __init__(
        self,
        campaign_manager: Optional[CampaignManager] = None,
        character_vault: Optional[CharacterVault] = None
    ):
        """
        Initialize the main menu.

        Args:
            campaign_manager: CampaignManager instance (creates default if not provided)
            character_vault: CharacterVault instance (creates default if not provided)
        """
        self.campaign_manager = campaign_manager or CampaignManager()
        self.character_vault = character_vault or CharacterVault()

    def show(self) -> Optional[str]:
        """
        Display the main menu and handle user choice.

        Returns:
            Menu choice selected by user ("quick_start", "continue", "new", "load", "vault", "exit")
            or None if invalid
        """
        print_banner("D&D 5E Terminal Adventure", version="0.2.0", color="cyan")
        console.print()

        options = [
            {"number": "1", "text": "Quick Start (Jump right in!)"},
            {"number": "2", "text": "Continue Last Campaign"},
            {"number": "3", "text": "New Campaign"},
            {"number": "4", "text": "Load Campaign"},
            {"number": "5", "text": "Character Vault"},
            {"number": "6", "text": "Exit"}
        ]

        print_choice_menu("Main Menu", options)
        console.print()

        choice = console.input("[bold cyan]Choose an option [1-6]:[/bold cyan] ").strip()

        choice_map = {
            "1": "quick_start",
            "2": "continue",
            "3": "new",
            "4": "load",
            "5": "vault",
            "6": "exit"
        }

        return choice_map.get(choice)

    def show_continue_preview(self) -> Optional[str]:
        """
        Show a preview of the most recent campaign for quick continue.

        Returns:
            Campaign name if user confirms, None if cancelled
        """
        campaign = self.campaign_manager.get_most_recent_campaign()

        if campaign is None:
            print_status_message(
                "No campaigns found. Please create a new campaign first.",
                "warning"
            )
            return None

        # Display campaign preview
        console.print()
        print_section("Continue Campaign")

        table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Campaign", f"[bold]{campaign.name}[/bold]")
        table.add_row("Dungeon", campaign.current_dungeon or "Unknown")
        table.add_row("Party", ", ".join(campaign.party_character_ids) if campaign.party_character_ids else "None")
        table.add_row("Playtime", campaign.get_playtime_display())
        table.add_row("Last played", campaign.get_last_played_display())

        console.print(table)
        console.print()

        # Confirm
        confirm = console.input("[bold cyan]Continue this campaign? [Y/n]:[/bold cyan] ").strip().lower()

        if confirm in ["", "y", "yes"]:
            return campaign.name

        return None

    def show_campaign_list(self) -> Optional[str]:
        """
        Display list of all campaigns and let user select one.

        Returns:
            Selected campaign name, or None if cancelled/no campaigns
        """
        campaigns = self.campaign_manager.list_campaigns()

        if not campaigns:
            print_status_message(
                "No campaigns found. Please create a new campaign first.",
                "warning"
            )
            return None

        console.print()
        print_section("Available Campaigns")
        console.print()

        # Display each campaign with details
        for i, campaign in enumerate(campaigns, 1):
            panel_content = []

            # Party info
            if campaign.party_character_ids:
                party_str = ", ".join(campaign.party_character_ids)
                panel_content.append(f"[cyan]Party:[/cyan] {party_str}")
            else:
                panel_content.append("[dim]No party members[/dim]")

            # Location
            if campaign.current_dungeon:
                panel_content.append(f"[cyan]Dungeon:[/cyan] {campaign.current_dungeon}")

            # Playtime and last played
            panel_content.append(f"[cyan]Playtime:[/cyan] {campaign.get_playtime_display()}")
            panel_content.append(f"[cyan]Last played:[/cyan] {campaign.get_last_played_display()}")

            panel = Panel(
                "\n".join(panel_content),
                title=f"[bold cyan][{i}][/bold cyan] [bold white]{campaign.name}[/bold white]",
                border_style="cyan",
                padding=(0, 2)
            )
            console.print(panel)
            console.print()

        # Get user choice
        choice_text = f"Select campaign [1-{len(campaigns)}] or [B]ack"
        user_input = console.input(f"[bold cyan]{choice_text}:[/bold cyan] ").strip()

        if user_input.lower() in ["b", "back"]:
            return None

        try:
            choice_num = int(user_input)
            if 1 <= choice_num <= len(campaigns):
                selected_campaign = campaigns[choice_num - 1]
                return selected_campaign.name
            else:
                print_error("Invalid choice. Please select a valid campaign number.")
                return None
        except ValueError:
            print_error("Invalid input. Please enter a number or 'B' for back.")
            return None

    def show_campaign_save_slots(self, campaign_name: str) -> Optional[str]:
        """
        Show available save slots for a campaign and let user select one.

        Args:
            campaign_name: Name of the campaign

        Returns:
            Selected slot name, or None if cancelled/no saves
        """
        try:
            save_slots = self.campaign_manager.list_save_slots(campaign_name)
        except FileNotFoundError:
            print_error(f"Campaign '{campaign_name}' not found.")
            return None

        if not save_slots:
            print_status_message(
                f"No save files found for campaign '{campaign_name}'.",
                "warning"
            )
            return None

        console.print()
        print_section(f"Save Slots for '{campaign_name}'")
        console.print()

        # Display save slots
        for i, slot in enumerate(save_slots, 1):
            save_type_icon = {
                "auto": "🔄",
                "quick": "⚡",
                "manual": "💾"
            }.get(slot.save_type, "💾")

            panel_content = [
                f"[cyan]Type:[/cyan] {save_type_icon} {slot.save_type.title()} Save",
                f"[cyan]Saved:[/cyan] {slot.get_time_display()}"
            ]

            if slot.location:
                panel_content.append(f"[cyan]Location:[/cyan] {slot.location}")

            panel = Panel(
                "\n".join(panel_content),
                title=f"[bold cyan][{i}][/bold cyan] [bold white]{slot.slot_name}[/bold white]",
                border_style="yellow" if slot.save_type == "auto" else "cyan",
                padding=(0, 2)
            )
            console.print(panel)
            console.print()

        # Get user choice
        choice_text = f"Select save slot [1-{len(save_slots)}] or [B]ack"
        user_input = console.input(f"[bold cyan]{choice_text}:[/bold cyan] ").strip()

        if user_input.lower() in ["b", "back"]:
            return None

        try:
            choice_num = int(user_input)
            if 1 <= choice_num <= len(save_slots):
                selected_slot = save_slots[choice_num - 1]
                return selected_slot.slot_name
            else:
                print_error("Invalid choice. Please select a valid save slot number.")
                return None
        except ValueError:
            print_error("Invalid input. Please enter a number or 'B' for back.")
            return None

    def handle_continue_last_campaign(self) -> Optional[GameState]:
        """
        Handle the "Continue Last Campaign" flow.

        Returns:
            Loaded GameState if successful, None otherwise
        """
        campaign_name = self.show_continue_preview()

        if campaign_name is None:
            return None

        try:
            # Try to load auto-save first, fall back to most recent save
            try:
                game_state = self.campaign_manager.load_campaign_state(
                    campaign_name,
                    slot_name="auto"
                )
                print_status_message(
                    f"Loaded auto-save for '{campaign_name}'",
                    "success"
                )
                return game_state
            except FileNotFoundError:
                # No auto-save, show save slot selection
                print_status_message(
                    "No auto-save found. Please select a save slot:",
                    "info"
                )
                slot_name = self.show_campaign_save_slots(campaign_name)

                if slot_name is None:
                    return None

                game_state = self.campaign_manager.load_campaign_state(
                    campaign_name,
                    slot_name=slot_name
                )
                print_status_message(
                    f"Loaded save '{slot_name}' for '{campaign_name}'",
                    "success"
                )
                return game_state

        except FileNotFoundError as e:
            print_error(f"Campaign not found: {campaign_name}", e)
            return None
        except Exception as e:
            print_error(f"Failed to load campaign: {str(e)}", e)
            return None

    def handle_load_campaign(self) -> Optional[GameState]:
        """
        Handle the "Load Campaign" flow with campaign and save slot selection.

        Returns:
            Loaded GameState if successful, None otherwise
        """
        # Step 1: Select campaign
        campaign_name = self.show_campaign_list()

        if campaign_name is None:
            return None

        # Step 2: Select save slot
        slot_name = self.show_campaign_save_slots(campaign_name)

        if slot_name is None:
            return None

        # Step 3: Load the game
        try:
            game_state = self.campaign_manager.load_campaign_state(
                campaign_name,
                slot_name=slot_name
            )
            print_status_message(
                f"Loaded '{campaign_name}' - {slot_name}",
                "success"
            )
            return game_state
        except FileNotFoundError as e:
            print_error(f"Save file not found", e)
            return None
        except Exception as e:
            print_error(f"Failed to load campaign: {str(e)}", e)
            return None

    def handle_quick_start(self) -> Optional[GameState]:
        """
        Handle the "Quick Start" flow - generate character and jump into game.

        NOTE: This will be implemented in a future iteration. For now, returns None.

        Returns:
            GameState if successful, None otherwise
        """
        print_status_message(
            "Quick Start feature coming soon! Please use 'New Campaign' instead.",
            "info"
        )
        return None

    def handle_character_vault(self) -> None:
        """
        Handle navigation to Character Vault menu.

        NOTE: Character Vault UI will be implemented in a future iteration.
        """
        print_status_message(
            "Character Vault UI coming soon!",
            "info"
        )
        # TODO: Implement Character Vault UI in future iteration
        # This will show the vault menu from Issue #81

    def run(self) -> Optional[GameState]:
        """
        Run the main menu loop until user makes a valid selection.

        Returns:
            GameState if a campaign is loaded, None if user exits
        """
        while True:
            choice = self.show()

            if choice == "exit":
                print_status_message("Thanks for playing!", "info")
                return None

            elif choice == "continue":
                game_state = self.handle_continue_last_campaign()
                if game_state:
                    return game_state

            elif choice == "load":
                game_state = self.handle_load_campaign()
                if game_state:
                    return game_state

            elif choice == "quick_start":
                game_state = self.handle_quick_start()
                if game_state:
                    return game_state

            elif choice == "new":
                print_status_message(
                    "New Campaign creation coming soon! (Issue #84)",
                    "info"
                )
                # TODO: Implement in Issue #84

            elif choice == "vault":
                self.handle_character_vault()

            else:
                print_error("Invalid choice. Please select a valid option.")

            console.print()
            console.print("[dim]Press Enter to continue...[/dim]")
            console.input()
            console.clear()
