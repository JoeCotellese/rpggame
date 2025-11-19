# ABOUTME: Campaign creation wizard for new campaign setup
# ABOUTME: Handles multi-step campaign creation with party building and dungeon selection

from typing import Optional, List, Dict, Any
from pathlib import Path

from dnd_engine.core.campaign_manager import CampaignManager
from dnd_engine.core.character_vault import CharacterVault, CharacterState
from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.character import Character
from dnd_engine.rules.loader import DataLoader
from dnd_engine.ui.character_wizard import CharacterCreationWizard
from dnd_engine.ui.rich_ui import (
    console,
    print_banner,
    print_section,
    print_status_message,
    print_error,
    print_message,
    print_choice_menu
)
from rich.table import Table
from rich.panel import Panel
from rich import box


class CampaignCreationWizard:
    """
    Multi-step wizard for creating new campaigns.

    Steps:
    1. Campaign name
    2. Starting level
    3. Party composition (create/import characters)
    4. Adventure selection
    5. Confirmation and creation
    """

    def __init__(
        self,
        campaign_manager: Optional[CampaignManager] = None,
        character_vault: Optional[CharacterVault] = None,
        character_factory: Optional[CharacterFactory] = None,
        data_loader: Optional[DataLoader] = None
    ):
        """
        Initialize the campaign creation wizard.

        Args:
            campaign_manager: CampaignManager instance
            character_vault: CharacterVault instance
            character_factory: CharacterFactory instance
            data_loader: DataLoader instance
        """
        self.campaign_manager = campaign_manager or CampaignManager()
        self.character_vault = character_vault or CharacterVault()
        self.character_factory = character_factory or CharacterFactory()
        self.data_loader = data_loader or DataLoader()

        # Wizard state
        self.campaign_name: Optional[str] = None
        self.starting_level: int = 1
        self.party_character_ids: List[str] = []
        self.dungeon_name: Optional[str] = None

    def run(self) -> Optional[str]:
        """
        Run the campaign creation wizard.

        Returns:
            Campaign name if created, None if cancelled
        """
        console.clear()
        print_banner("Create New Campaign", color="cyan")
        console.print()

        # Step 1: Campaign name
        if not self._step_campaign_name():
            return None

        # Step 2: Starting level
        if not self._step_starting_level():
            return None

        # Step 3: Build party
        if not self._step_build_party():
            return None

        # Step 4: Select adventure
        if not self._step_select_adventure():
            return None

        # Step 5: Confirm and create
        if not self._step_confirm():
            return None

        # Create the campaign
        return self._create_campaign()

    def _step_campaign_name(self) -> bool:
        """
        Step 1: Get campaign name.

        Returns:
            True to continue, False to cancel
        """
        print_section("Step 1: Campaign Name")
        console.print()

        while True:
            campaign_name = console.input("[bold cyan]Campaign Name:[/bold cyan] ").strip()

            if not campaign_name:
                print_error("Campaign name cannot be empty")
                continue

            # Check for name conflicts
            existing_campaigns = self.campaign_manager.list_campaigns()
            if any(c.name == campaign_name for c in existing_campaigns):
                print_error(f"Campaign '{campaign_name}' already exists")
                console.print()
                retry = console.input("[bold]Choose a different name? [Y/n]:[/bold] ").strip().lower()
                if retry in ["n", "no"]:
                    return False
                continue

            self.campaign_name = campaign_name
            return True

    def _step_starting_level(self) -> bool:
        """
        Step 2: Get starting level.

        Returns:
            True to continue, False to cancel
        """
        console.print()
        print_section("Step 2: Starting Level")
        console.print()

        while True:
            level_input = console.input(
                "[bold cyan]Starting Level [1-20][/bold cyan] (default: 1): "
            ).strip()

            if not level_input:
                self.starting_level = 1
                return True

            try:
                level = int(level_input)
                if 1 <= level <= 20:
                    self.starting_level = level
                    return True
                else:
                    print_error("Level must be between 1 and 20")
            except ValueError:
                print_error("Please enter a valid number")

    def _step_build_party(self) -> bool:
        """
        Step 3: Build party (create/import characters).

        Returns:
            True to continue, False to cancel
        """
        console.print()
        print_section("Step 3: Build Your Party")
        console.print()

        while True:
            self._display_current_party()
            console.print()

            options = [
                {"number": "1", "text": "Create New Character"},
                {"number": "2", "text": "Import from Character Vault"},
            ]

            if len(self.party_character_ids) >= 1:
                options.append({"number": "3", "text": "Continue to next step"})

            options.append({"number": "B", "text": "Back/Cancel"})

            print_choice_menu("Party Builder", options)
            console.print()

            choice = console.input("[bold cyan]Choose:[/bold cyan] ").strip().lower()

            if choice == "1":
                self._create_new_character()
            elif choice == "2":
                self._import_character()
            elif choice == "3" and len(self.party_character_ids) >= 1:
                return True
            elif choice == "b":
                confirm = console.input(
                    "[bold]Cancel campaign creation? [y/N]:[/bold] "
                ).strip().lower()
                if confirm in ["y", "yes"]:
                    return False
            else:
                print_error("Invalid choice")

    def _display_current_party(self) -> None:
        """Display current party composition."""
        if not self.party_character_ids:
            console.print("[dim]Current Party: (empty)[/dim]")
            console.print("[yellow]⚠ You need at least 1 character to continue[/yellow]")
        else:
            console.print(f"[bold]Current Party ({len(self.party_character_ids)}/6):[/bold]")
            for char_id in self.party_character_ids:
                try:
                    char = self.character_vault.load_character(char_id)
                    console.print(f"  • {char.name} ({char.character_class.value.title()} {char.level})")
                except Exception:
                    console.print(f"  • {char_id} [dim](error loading)[/dim]")

    def _create_new_character(self) -> None:
        """Create a new character and add to party."""
        console.print()
        print_status_message("Creating new character at level {}...".format(self.starting_level), "info")

        # Launch new character creation wizard
        wizard = CharacterCreationWizard(
            character_factory=self.character_factory,
            data_loader=self.data_loader
        )
        character = wizard.run()

        if character is None:
            print_status_message("Character creation cancelled", "warning")
            return

        # Set level if different from 1
        if self.starting_level != 1:
            character.level = self.starting_level
            # Recalculate HP for higher levels
            # TODO: Implement proper leveling system

        # Save to vault
        char_id = self.character_vault.save_character(
            character,
            state=CharacterState.AVAILABLE,
            campaign_name=None
        )

        # Add to party
        self.party_character_ids.append(char_id)
        print_status_message(f"✓ {character.name} added to party", "success")

    def _import_character(self) -> None:
        """Import character from vault."""
        console.print()

        # List available characters
        all_characters = self.character_vault.list_characters()

        if not all_characters:
            print_status_message("No characters in vault. Create a new one instead!", "warning")
            return

        # Display characters
        print_section("Character Vault")
        console.print()

        for i, char_info in enumerate(all_characters, 1):
            state = char_info.get("state", "available")
            state_icon = {
                "available": "✓",
                "active": "⚠",
                "retired": "✗"
            }.get(state, "?")

            state_color = {
                "available": "green",
                "active": "yellow",
                "retired": "dim"
            }.get(state, "white")

            char_name = char_info.get("name", "Unknown")
            char_class = char_info.get("class", "Unknown")
            char_level = char_info.get("level", "?")
            campaign = char_info.get("campaign_name", "")

            status = f"[{state_color}]{state_icon} {state.title()}[/{state_color}]"
            if campaign:
                status += f" [dim]in '{campaign}'[/dim]"

            console.print(f"[{i}] {char_name} ({char_class} {char_level}) - {status}")

        console.print()
        choice = console.input(f"[bold cyan]Select character [1-{len(all_characters)}] or [B]ack:[/bold cyan] ").strip()

        if choice.lower() == "b":
            return

        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(all_characters):
                char_info = all_characters[choice_num - 1]
                char_id = char_info["id"]

                # Check if character is already in party
                if char_id in self.party_character_ids:
                    print_error("This character is already in the party")
                    return

                # Warn if character is active in another campaign
                if char_info.get("state") == "active":
                    console.print()
                    print_status_message(
                        f"⚠ Warning: {char_info['name']} is active in '{char_info.get('campaign_name')}'",
                        "warning"
                    )
                    confirm = console.input(
                        "[bold]Import anyway? (This will remove them from that campaign) [y/N]:[/bold] "
                    ).strip().lower()
                    if confirm not in ["y", "yes"]:
                        return

                # Add to party
                self.party_character_ids.append(char_id)
                print_status_message(f"✓ {char_info['name']} added to party", "success")
            else:
                print_error("Invalid selection")
        except ValueError:
            print_error("Please enter a number")

    def _step_select_adventure(self) -> bool:
        """
        Step 4: Select adventure/dungeon.

        Returns:
            True to continue, False to cancel
        """
        console.print()
        print_section("Step 4: Select Adventure")
        console.print()

        # List available dungeons
        dungeons_dir = self.data_loader.data_path / "content" / "dungeons"
        dungeon_files = sorted(dungeons_dir.glob("*.json"))

        # Filter out generated dungeons (they have timestamps in name)
        dungeon_files = [f for f in dungeon_files if not f.stem.startswith("generated_")]

        if not dungeon_files:
            print_error("No adventures found in dungeon directory")
            return False

        # Display dungeons
        for i, dungeon_file in enumerate(dungeon_files, 1):
            dungeon_name = dungeon_file.stem.replace("_", " ").title()
            console.print(f"[{i}] {dungeon_name}")

        console.print()
        choice = console.input(
            f"[bold cyan]Select adventure [1-{len(dungeon_files)}] or [B]ack:[/bold cyan] "
        ).strip()

        if choice.lower() == "b":
            return False

        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(dungeon_files):
                self.dungeon_name = dungeon_files[choice_num - 1].stem
                return True
            else:
                print_error("Invalid selection")
                return self._step_select_adventure()
        except ValueError:
            print_error("Please enter a number")
            return self._step_select_adventure()

    def _step_confirm(self) -> bool:
        """
        Step 5: Show confirmation and get final approval.

        Returns:
            True to create, False to cancel
        """
        console.print()
        print_section("Campaign Summary")
        console.print()

        # Build summary table
        table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Name", f"[bold]{self.campaign_name}[/bold]")
        table.add_row("Starting Level", str(self.starting_level))
        table.add_row("Party Size", f"{len(self.party_character_ids)} character(s)")

        # List party members
        party_names = []
        for char_id in self.party_character_ids:
            try:
                char = self.character_vault.load_character(char_id)
                party_names.append(f"{char.name} ({char.character_class.value.title()} {char.level})")
            except Exception:
                party_names.append(f"{char_id} (error)")

        table.add_row("Party", "\n".join(party_names))

        dungeon_display = self.dungeon_name.replace("_", " ").title() if self.dungeon_name else "None"
        table.add_row("Adventure", dungeon_display)

        console.print(table)
        console.print()

        confirm = console.input("[bold cyan]Create campaign? [Y/n]:[/bold cyan] ").strip().lower()

        return confirm in ["", "y", "yes"]

    def _create_campaign(self) -> str:
        """
        Create the campaign with configured settings.

        Returns:
            Campaign name
        """
        console.print()
        with console.status("[cyan]Creating campaign...[/cyan]", spinner="dots"):
            # Create campaign
            self.campaign_manager.create_campaign(
                name=self.campaign_name,
                dungeon_name=self.dungeon_name,
                party_character_ids=self.party_character_ids
            )

            # Update character states to ACTIVE
            for char_id in self.party_character_ids:
                self.character_vault.update_character_state(
                    character_id=char_id,
                    state=CharacterState.ACTIVE,
                    campaign_name=self.campaign_name
                )

        print_status_message(f"✓ Campaign '{self.campaign_name}' created successfully!", "success")

        return self.campaign_name
