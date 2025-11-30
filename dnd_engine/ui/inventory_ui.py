# ABOUTME: Questionary-based inventory management UI for character equipment and items
# ABOUTME: Provides character selection, equipment management, item viewing, and proficiency display

from typing import Any

import questionary
from rich.panel import Panel

from dnd_engine.core.character import Character
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.inventory import EquipmentSlot

from .rich_ui import console, print_section, print_status_message


class InventoryUI:
    """
    Interactive inventory management interface using questionary menus.

    Provides a structured UI for viewing inventory, managing equipment,
    and displaying proficiency information for party members.
    """

    def __init__(self, party: list[Character], data_loader: DataLoader | None = None):
        """
        Initialize inventory UI.

        Args:
            party: List of party member characters
            data_loader: Optional data loader (creates one if not provided)
        """
        self.party = party
        self.loader = data_loader or DataLoader()
        self.items_data = self.loader.load_items()
        self.active_character: Character | None = None

    def run(self) -> None:
        """Run the inventory management interface until the user exits."""
        if not self.party:
            print_status_message("No party members available.", "warning")
            return

        # Filter to living members only
        living_members = [c for c in self.party if c.is_alive]
        if not living_members:
            print_status_message("No living party members.", "warning")
            return

        while True:
            console.print()
            print_section("INVENTORY MANAGEMENT")

            # Select character if not selected
            if not self.active_character:
                self.active_character = self._select_character(living_members)
                if not self.active_character:
                    break

            # Show main menu for selected character
            action = self._show_main_menu()

            if action == "view":
                self._view_inventory()
            elif action == "equipment":
                self._manage_equipment()
            elif action == "back":
                self.active_character = None
            elif action == "exit":
                break

    def _select_character(self, characters: list[Character]) -> Character | None:
        """
        Show character selection menu.

        Args:
            characters: List of characters to choose from

        Returns:
            Selected character or None if cancelled
        """
        choices = []
        for char in characters:
            gold = char.inventory.gold
            item_count = char.inventory.item_count()
            display = (
                f"{char.name} ({char.character_class.value.title()} {char.level}) "
                f"- {gold} GP - {item_count} items"
            )
            choices.append(questionary.Choice(title=display, value=char))

        choices.append(questionary.Choice(title="← Back", value=None))

        try:
            result = questionary.select(
                "Select a character:",
                choices=choices,
                use_arrow_keys=True
            ).ask()
            return result
        except (EOFError, KeyboardInterrupt):
            return None

    def _show_main_menu(self) -> str:
        """
        Show main inventory menu for selected character.

        Returns:
            Selected action string
        """
        char = self.active_character
        if not char:
            return "exit"

        gold = char.inventory.gold
        hp_str = f"{char.current_hp}/{char.max_hp} HP"

        choices = [
            questionary.Choice(title="View All Items", value="view"),
            questionary.Choice(title="Manage Equipment", value="equipment"),
            questionary.Choice(title="← Back to Characters", value="back"),
        ]

        try:
            result = questionary.select(
                f"{char.name}'s Inventory ({gold} GP, {hp_str}):",
                choices=choices,
                use_arrow_keys=True
            ).ask()
            return result or "exit"
        except (EOFError, KeyboardInterrupt):
            return "exit"

    def _view_inventory(self) -> None:
        """Display character's full inventory in a formatted view."""
        char = self.active_character
        if not char:
            return

        inventory = char.inventory
        console.print()

        # Build inventory display
        equipped_weapon = inventory.get_equipped_item(EquipmentSlot.WEAPON)
        equipped_armor = inventory.get_equipped_item(EquipmentSlot.ARMOR)

        # Create panel content
        lines = []

        # Equipped section
        lines.append("[bold cyan]EQUIPPED:[/bold cyan]")
        if equipped_weapon:
            weapon_data = self._get_item_data(equipped_weapon, "weapons")
            weapon_name = weapon_data.get("name", equipped_weapon) if weapon_data else equipped_weapon
            weapon_info = self._get_weapon_info(weapon_data) if weapon_data else ""
            lines.append(f"  Weapon: {weapon_name} {weapon_info}")
        else:
            lines.append("  Weapon: [dim]None[/dim]")

        if equipped_armor:
            armor_data = self._get_item_data(equipped_armor, "armor")
            armor_name = armor_data.get("name", equipped_armor) if armor_data else equipped_armor
            armor_info = self._get_armor_info(armor_data) if armor_data else ""
            lines.append(f"  Armor:  {armor_name} {armor_info}")
        else:
            lines.append("  Armor:  [dim]None[/dim]")

        lines.append("")

        # Weapons section
        weapons = inventory.get_items_by_category("weapons")
        if weapons:
            lines.append("[bold cyan]WEAPONS:[/bold cyan]")
            for inv_item in weapons:
                item_data = self._get_item_data(inv_item.item_id, "weapons")
                name = item_data.get("name", inv_item.item_id) if item_data else inv_item.item_id
                equipped_marker = " [green][equipped][/green]" if inv_item.item_id == equipped_weapon else ""
                prof_marker = self._get_proficiency_marker(char, item_data, "weapon")
                qty_str = f" (x{inv_item.quantity})" if inv_item.quantity > 1 else ""
                lines.append(f"  {name}{qty_str}{equipped_marker}{prof_marker}")
            lines.append("")

        # Armor section
        armor_items = inventory.get_items_by_category("armor")
        if armor_items:
            lines.append("[bold cyan]ARMOR:[/bold cyan]")
            for inv_item in armor_items:
                item_data = self._get_item_data(inv_item.item_id, "armor")
                name = item_data.get("name", inv_item.item_id) if item_data else inv_item.item_id
                equipped_marker = " [green][equipped][/green]" if inv_item.item_id == equipped_armor else ""
                prof_marker = self._get_proficiency_marker(char, item_data, "armor")
                lines.append(f"  {name}{equipped_marker}{prof_marker}")
            lines.append("")

        # Consumables section
        consumables = inventory.get_items_by_category("consumables")
        if consumables:
            lines.append("[bold cyan]CONSUMABLES:[/bold cyan]")
            for inv_item in consumables:
                item_data = self._get_item_data(inv_item.item_id, "consumables")
                name = item_data.get("name", inv_item.item_id) if item_data else inv_item.item_id
                qty_str = f" (x{inv_item.quantity})" if inv_item.quantity > 1 else ""
                quest_marker = " [yellow]⚿[/yellow]" if inv_item.quest_item else ""
                lines.append(f"  {name}{qty_str}{quest_marker}")
            lines.append("")

        # Quest items note
        if any(inv.quest_item for inv in inventory.get_all_items()):
            lines.append("[dim]⚿ = Quest item (cannot be dropped or sold)[/dim]")

        if not (weapons or armor_items or consumables):
            lines.append("[dim]No items in inventory[/dim]")

        panel = Panel(
            "\n".join(lines),
            title=f"[bold white]{char.name}'s Items[/bold white]",
            subtitle=f"[dim]Gold: {inventory.gold} GP[/dim]",
            border_style="cyan",
            padding=(1, 2)
        )
        console.print(panel)

        # Wait for user to continue
        console.print("\n[dim]Press Enter to continue...[/dim]")
        console.input()

    def _manage_equipment(self) -> None:
        """Equipment management submenu."""
        char = self.active_character
        if not char:
            return

        while True:
            inventory = char.inventory
            equipped_weapon = inventory.get_equipped_item(EquipmentSlot.WEAPON)
            equipped_armor = inventory.get_equipped_item(EquipmentSlot.ARMOR)

            # Get display names
            weapon_name = "None"
            if equipped_weapon:
                weapon_data = self._get_item_data(equipped_weapon, "weapons")
                weapon_name = weapon_data.get("name", equipped_weapon) if weapon_data else equipped_weapon

            armor_name = "None"
            if equipped_armor:
                armor_data = self._get_item_data(equipped_armor, "armor")
                armor_name = armor_data.get("name", equipped_armor) if armor_data else equipped_armor

            choices = [
                questionary.Choice(
                    title=f"Change Weapon (current: {weapon_name})",
                    value="weapon"
                ),
                questionary.Choice(
                    title=f"Change Armor (current: {armor_name})",
                    value="armor"
                ),
                questionary.Choice(title="← Back", value="__BACK__"),
            ]

            try:
                action = questionary.select(
                    f"Manage Equipment - {char.name}:",
                    choices=choices,
                    use_arrow_keys=True
                ).ask()
            except (EOFError, KeyboardInterrupt):
                return

            if action is None or action == "__BACK__":
                return
            elif action == "weapon":
                self._change_equipment(EquipmentSlot.WEAPON)
            elif action == "armor":
                self._change_equipment(EquipmentSlot.ARMOR)

    def _change_equipment(self, slot: EquipmentSlot) -> None:
        """
        Change equipment in a specific slot.

        Args:
            slot: The equipment slot to change
        """
        char = self.active_character
        if not char:
            return

        inventory = char.inventory
        category = "weapons" if slot == EquipmentSlot.WEAPON else "armor"
        slot_name = "weapon" if slot == EquipmentSlot.WEAPON else "armor"

        # Get available items
        available_items = inventory.get_items_by_category(category)
        currently_equipped = inventory.get_equipped_item(slot)

        choices = []
        for inv_item in available_items:
            item_data = self._get_item_data(inv_item.item_id, category)
            name = item_data.get("name", inv_item.item_id) if item_data else inv_item.item_id

            # Build display with proficiency status
            prof_marker = self._get_proficiency_marker(char, item_data, slot_name)
            equipped_marker = " [green][equipped][/green]" if inv_item.item_id == currently_equipped else ""

            display = f"{name}{equipped_marker}{prof_marker}"
            choices.append(questionary.Choice(title=display, value=inv_item.item_id))

        # Add unequip option if something is equipped
        if currently_equipped:
            choices.append(questionary.Choice(
                title=f"Unequip {slot_name}",
                value="__UNEQUIP__"
            ))

        choices.append(questionary.Choice(title="← Cancel", value="__CANCEL__"))

        if len(choices) == 1:  # Only cancel option
            print_status_message(f"No {category} available to equip.", "info")
            return

        try:
            selected = questionary.select(
                f"Select {slot_name} for {char.name}:",
                choices=choices,
                use_arrow_keys=True
            ).ask()
        except (EOFError, KeyboardInterrupt):
            return

        if selected is None or selected == "__CANCEL__":
            return

        if selected == "__UNEQUIP__":
            unequipped_id = inventory.unequip_item(slot)
            if unequipped_id:
                item_data = self._get_item_data(unequipped_id, category)
                name = item_data.get("name", unequipped_id) if item_data else unequipped_id
                print_status_message(f"{char.name} unequipped {name}", "info")
        else:
            # Equip the selected item
            inventory.equip_item(selected, slot)
            item_data = self._get_item_data(selected, category)
            name = item_data.get("name", selected) if item_data else selected
            print_status_message(f"{char.name} equipped {name}", "success")

    def _get_item_data(self, item_id: str, category: str) -> dict[str, Any] | None:
        """
        Look up item data from items.json.

        Args:
            item_id: The item ID to look up
            category: The category to search in (weapons, armor, consumables)

        Returns:
            Item data dictionary or None if not found
        """
        if category in self.items_data and item_id in self.items_data[category]:
            return self.items_data[category][item_id]
        return None

    def _get_weapon_info(self, item_data: dict[str, Any] | None) -> str:
        """Get compact weapon info string."""
        if not item_data:
            return ""

        parts = []
        damage = item_data.get("damage")
        if damage:
            parts.append(damage)

        damage_type = item_data.get("damage_type")
        if damage_type:
            parts.append(damage_type)

        return f"[dim]({', '.join(parts)})[/dim]" if parts else ""

    def _get_armor_info(self, item_data: dict[str, Any] | None) -> str:
        """Get compact armor info string."""
        if not item_data:
            return ""

        ac = item_data.get("ac_base")
        if ac:
            return f"[dim](AC {ac})[/dim]"
        return ""

    def _get_proficiency_marker(
        self,
        char: Character,
        item_data: dict[str, Any] | None,
        item_type: str
    ) -> str:
        """
        Get proficiency marker for an item.

        Args:
            char: Character to check proficiency for
            item_data: Item data dictionary
            item_type: "weapon" or "armor"

        Returns:
            Formatted proficiency marker string
        """
        if not item_data:
            return ""

        if item_type == "weapon":
            weapon_type = item_data.get("weapon_type", "")
            # Check weapon type proficiency
            if weapon_type in char.weapon_proficiencies:
                return " [green]✓[/green]"
            # Check specific weapon proficiency
            item_id = item_data.get("name", "").lower().replace(" ", "_")
            if item_id in char.weapon_proficiencies:
                return " [green]✓[/green]"
            return " [red]✗ not proficient[/red]"

        elif item_type == "armor":
            armor_type = item_data.get("armor_type", "")
            if armor_type in char.armor_proficiencies:
                return " [green]✓[/green]"
            return " [red]✗ not proficient[/red]"

        return ""
