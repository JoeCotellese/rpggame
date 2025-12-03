# ABOUTME: Questionary-based shop UI for buying and selling items with NPCs
# ABOUTME: Provides character selection, categorized browsing, and proficiency checking

from dataclasses import dataclass
from typing import Any

import questionary

from dnd_engine.core.character import Character
from dnd_engine.core.npc import NPC, NPCShop, ShopItem
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.currency import Currency
from dnd_engine.systems.inventory import EquipmentSlot


@dataclass
class ShopTransaction:
    """Result of a shop transaction."""

    success: bool
    message: str
    item_id: str | None = None
    quantity: int = 0
    total_price: int = 0


class ShopUI:
    """
    Interactive shop interface using questionary menus.

    Provides a structured UI for browsing and purchasing items from NPC shops,
    with support for character selection, item categorization, and proficiency
    checking.
    """

    # Map item types to display categories
    CATEGORY_MAP = {
        "weapon": "Weapons",
        "armor": "Armor",
        "ammunition": "Ammunition",
        "consumable": "Consumables",
        "equipment": "Equipment",
        "tool": "Tools",
        "wondrous_item": "Magical Items",
    }

    # Reverse map for looking up items by category
    CATEGORY_TO_JSON_KEY = {
        "Weapons": "weapons",
        "Armor": "armor",
        "Ammunition": "ammunition",
        "Consumables": "consumables",
        "Equipment": "equipment",
        "Tools": "tools",
        "Magical Items": "magical_items",
    }

    def __init__(self, npc: NPC, party: list[Character]):
        """
        Initialize shop UI.

        Args:
            npc: NPC with an enabled shop
            party: List of party member characters
        """
        self.npc = npc
        self.party = party
        self.shop: NPCShop = npc.shop  # type: ignore
        self.loader = DataLoader()
        self.items_data = self.loader.load_items()
        self.active_character: Character | None = None

    def run(self) -> None:
        """Run the shop interface until the user exits."""
        if not self.shop or not self.shop.enabled:
            print("This NPC doesn't have a shop.")
            return

        if not self.party:
            print("No party members available to shop.")
            return

        print(f"\n{'=' * 50}")
        print(f"  Welcome to {self.npc.display_name}'s Shop")
        print(f"{'=' * 50}\n")

        while True:
            # Select character if not selected
            if not self.active_character:
                self.active_character = self._select_character()
                if not self.active_character:
                    break

            # Show main menu
            action = self._show_main_menu()
            if action == "browse":
                self._browse_wares()
            elif action == "sell":
                self._sell_items()
            elif action == "switch":
                self.active_character = None
            elif action == "exit":
                break

        print(f"\n{self.npc.dialogue.get('farewell', 'Goodbye!')}\n")

    def _select_character(self) -> Character | None:
        """Show character selection menu."""
        choices = []
        for char in self.party:
            gold = char.inventory.currency.gold
            total_cp = char.inventory.currency.to_copper()
            # Show gold equivalent for display
            gold_display = total_cp // 100
            remainder_sp = (total_cp % 100) // 10
            if remainder_sp > 0:
                gold_str = f"{gold_display} GP {remainder_sp} SP"
            else:
                gold_str = f"{gold_display} GP"

            display = f"{char.name} ({char.character_class.value.title()}) - {gold_str}"
            choices.append(questionary.Choice(title=display, value=char))

        choices.append(questionary.Choice(title="← Leave Shop", value="__EXIT__"))

        try:
            result = questionary.select(
                "Who's shopping today?",
                choices=choices,
            ).ask()
            if result == "__EXIT__":
                return None
            return result
        except KeyboardInterrupt:
            return None

    def _show_main_menu(self) -> str:
        """Show main shop menu for selected character."""
        char = self.active_character
        if not char:
            return "exit"

        gold_cp = char.inventory.currency.to_copper()
        gold_display = gold_cp // 100

        choices = [
            questionary.Choice(title="Browse Wares", value="browse"),
            questionary.Choice(title="Sell Items", value="sell"),
            questionary.Choice(title="Switch Character", value="switch"),
            questionary.Choice(title="← Leave Shop", value="exit"),
        ]

        try:
            result = questionary.select(
                f"{char.name} is shopping (Gold: {gold_display} GP)",
                choices=choices,
            ).ask()
            return result or "exit"
        except KeyboardInterrupt:
            return "exit"

    def _browse_wares(self) -> None:
        """Browse shop inventory by category."""
        while True:
            # Group items by category
            categories = self._get_categories()

            if not categories:
                print("No items available for sale.")
                return

            # Build category choices
            choices = []
            for cat_name, items in categories.items():
                choices.append(
                    questionary.Choice(
                        title=f"{cat_name} ({len(items)})",
                        value=cat_name,
                    )
                )
            choices.append(questionary.Choice(title="← Back", value="__BACK__"))

            try:
                category = questionary.select(
                    "Browse by category:",
                    choices=choices,
                ).ask()
            except KeyboardInterrupt:
                return

            if category is None or category == "__BACK__":
                return

            # Show items in selected category
            self._show_category_items(category, categories[category])

    def _get_categories(self) -> dict[str, list[tuple[ShopItem, dict[str, Any]]]]:
        """Group shop items by category with their full item data."""
        categories: dict[str, list[tuple[ShopItem, dict[str, Any]]]] = {}

        for shop_item in self.shop.inventory:
            item_data = self._get_item_data(shop_item.item_id)
            if not item_data:
                continue

            # Skip out of stock items (stock 0)
            if shop_item.stock == 0:
                continue

            item_type = item_data.get("type", "equipment")
            category_name = self.CATEGORY_MAP.get(item_type, "Equipment")

            if category_name not in categories:
                categories[category_name] = []
            categories[category_name].append((shop_item, item_data))

        return categories

    def _get_item_data(self, item_id: str) -> dict[str, Any] | None:
        """Look up full item data from items.json."""
        # Search through all item categories
        for category_key in self.items_data:
            if item_id in self.items_data[category_key]:
                return self.items_data[category_key][item_id]
        return None

    def _get_item_category_key(self, item_id: str) -> str | None:
        """Get the JSON category key for an item."""
        for category_key in self.items_data:
            if item_id in self.items_data[category_key]:
                return category_key
        return None

    def _show_category_items(
        self,
        category_name: str,
        items: list[tuple[ShopItem, dict[str, Any]]],
    ) -> None:
        """Show items in a category with purchase options."""
        char = self.active_character
        if not char:
            return

        while True:
            choices = []
            for shop_item, item_data in items:
                # Skip out of stock
                if shop_item.stock == 0:
                    continue

                name = item_data.get("name", shop_item.item_id)
                price = shop_item.price

                # Stock display
                if shop_item.stock < 0:
                    stock_str = "∞"
                else:
                    stock_str = str(shop_item.stock)

                # Affordability check
                gold_cp = char.inventory.currency.to_copper()
                price_cp = price * 100
                can_afford = gold_cp >= price_cp

                # Build status string based on affordability and proficiency
                status_str = self._get_item_status_display(char, item_data, can_afford)

                display = f"{name:<20} {price:>3} GP  [{stock_str:>2}]  {status_str}"
                choices.append(
                    questionary.Choice(
                        title=display,
                        value=(shop_item, item_data),
                        disabled=None if can_afford else "insufficient gold",
                    )
                )

            choices.append(questionary.Choice(title="← Back", value="__BACK__"))

            try:
                result = questionary.select(
                    f"{category_name} - {char.name}'s Gold: {char.inventory.currency.to_copper() // 100} GP",
                    choices=choices,
                ).ask()
            except KeyboardInterrupt:
                return

            if result is None or result == "__BACK__":
                return

            shop_item, item_data = result
            self._purchase_item(shop_item, item_data)

    def _get_item_status_display(
        self, char: Character, item_data: dict[str, Any], can_afford: bool
    ) -> str:
        """
        Get combined affordability and proficiency status for display.

        Returns a single status string that clearly indicates:
        - Can't afford: "✗ insufficient gold"
        - Can afford + proficient (weapons/armor): "✓ proficient"
        - Can afford + not proficient (weapons/armor): "not proficient"
        - Can afford + compatible (ammunition): "✓ compatible"
        - Can afford (consumables/equipment): "" (no status needed)
        """
        if not can_afford:
            return "✗ insufficient gold"

        item_type = item_data.get("type", "")

        if item_type == "weapon":
            weapon_type = item_data.get("weapon_type", "")
            # Check if proficient
            if weapon_type in char.weapon_proficiencies:
                return "✓ proficient"
            # Check for specific weapon proficiency (e.g., rogue with rapier)
            item_id = item_data.get("name", "").lower().replace(" ", "_")
            if item_id in char.weapon_proficiencies:
                return "✓ proficient"
            return "not proficient"

        elif item_type == "armor":
            armor_type = item_data.get("armor_type", "")
            if armor_type in char.armor_proficiencies:
                return "✓ proficient"
            return "not proficient"

        elif item_type == "ammunition":
            # Check if character has a compatible weapon
            compatible = item_data.get("compatible_weapons", [])
            # Check equipped weapon
            equipped_weapon_id = char.inventory.equipped.get(EquipmentSlot.WEAPON)
            if equipped_weapon_id and equipped_weapon_id in compatible:
                return "✓ compatible"
            # Check if any compatible weapon in inventory
            for weapon_id in compatible:
                if weapon_id in char.inventory.items:
                    return "✓ has weapon"
            return ""

        # Consumables and equipment are usable by all - no status needed
        return ""

    def _purchase_item(self, shop_item: ShopItem, item_data: dict[str, Any]) -> None:
        """Handle item purchase with quantity selection."""
        char = self.active_character
        if not char:
            return

        name = item_data.get("name", shop_item.item_id)
        price = shop_item.price
        gold_cp = char.inventory.currency.to_copper()
        price_cp = price * 100

        # Calculate max affordable
        max_afford = gold_cp // price_cp

        # Calculate max by stock
        if shop_item.stock < 0:
            max_stock = max_afford  # Unlimited stock
        else:
            max_stock = min(shop_item.stock, max_afford)

        if max_stock <= 0:
            print(f"Cannot afford {name}.")
            return

        # Build quantity choices
        choices = []
        for qty in range(1, min(max_stock + 1, 11)):  # Max 10 at a time
            total = price * qty
            choices.append(
                questionary.Choice(
                    title=f"Buy {qty} ({total} GP)",
                    value=qty,
                )
            )
        choices.append(questionary.Choice(title="← Cancel", value="__CANCEL__"))

        try:
            quantity = questionary.select(
                f"How many {name}?",
                choices=choices,
            ).ask()
        except KeyboardInterrupt:
            return

        if quantity is None or quantity == "__CANCEL__":
            return

        # Process purchase
        total_price = price * quantity
        total_cp = total_price * 100

        # Deduct gold
        cost = Currency()
        cost._from_copper(total_cp)
        if not char.inventory.currency.subtract(cost):
            print("Transaction failed - insufficient funds.")
            return

        # Add item to inventory
        category_key = self._get_item_category_key(shop_item.item_id)
        if category_key:
            char.inventory.add_item(shop_item.item_id, category_key, quantity)

        # Update stock
        if shop_item.stock > 0:
            shop_item.stock -= quantity

        # Show confirmation
        remaining_gold = char.inventory.currency.to_copper() // 100
        print(f"\n✓ Purchased {quantity}x {name} for {total_price} GP")
        print(f"  {char.name}'s gold: {remaining_gold} GP\n")

    def _sell_items(self) -> None:
        """Show sell interface for character's inventory."""
        char = self.active_character
        if not char:
            return

        while True:
            # Get sellable items from character's inventory
            sellable = self._get_sellable_items(char)

            if not sellable:
                print(f"\n{char.name} has nothing to sell.\n")
                return

            choices = []
            for item_id, inv_item, item_data, sell_price in sellable:
                name = item_data.get("name", item_id) if item_data else item_id
                qty_str = f" x{inv_item.quantity}" if inv_item.quantity > 1 else ""
                display = f"{name}{qty_str} - {sell_price} GP each"
                choices.append(
                    questionary.Choice(
                        title=display,
                        value=(item_id, inv_item, item_data, sell_price),
                    )
                )

            choices.append(questionary.Choice(title="← Back", value="__BACK__"))

            try:
                result = questionary.select(
                    f"Sell items ({char.name})",
                    choices=choices,
                ).ask()
            except KeyboardInterrupt:
                return

            if result is None or result == "__BACK__":
                return

            item_id, inv_item, item_data, sell_price = result
            self._sell_item(char, item_id, inv_item, item_data, sell_price)

    def _get_sellable_items(
        self, char: Character
    ) -> list[tuple[str, Any, dict[str, Any] | None, int]]:
        """Get list of items character can sell with prices."""
        sellable = []
        buy_rate = self.shop.buy_rate

        for item_id, inv_item in char.inventory.items.items():
            # Skip equipped items
            if item_id == char.inventory.equipped.get(EquipmentSlot.WEAPON):
                continue
            if item_id == char.inventory.equipped.get(EquipmentSlot.ARMOR):
                continue

            item_data = self._get_item_data(item_id)
            if item_data:
                base_value = item_data.get("value", 0)
                sell_price = int(base_value * buy_rate)
            else:
                sell_price = 1  # Default for unknown items

            if sell_price > 0:
                sellable.append((item_id, inv_item, item_data, sell_price))

        return sellable

    def _sell_item(
        self,
        char: Character,
        item_id: str,
        inv_item: Any,
        item_data: dict[str, Any] | None,
        sell_price: int,
    ) -> None:
        """Process selling an item."""
        name = item_data.get("name", item_id) if item_data else item_id

        # Quantity selection if more than 1
        if inv_item.quantity > 1:
            choices = []
            for qty in range(1, min(inv_item.quantity + 1, 11)):
                total = sell_price * qty
                choices.append(
                    questionary.Choice(
                        title=f"Sell {qty} ({total} GP)",
                        value=qty,
                    )
                )
            choices.append(questionary.Choice(title="← Cancel", value="__CANCEL__"))

            try:
                quantity = questionary.select(
                    f"How many {name} to sell?",
                    choices=choices,
                ).ask()
            except KeyboardInterrupt:
                return

            if quantity is None or quantity == "__CANCEL__":
                return
        else:
            # Confirm single item sale
            try:
                confirm = questionary.confirm(
                    f"Sell {name} for {sell_price} GP?",
                    default=True,
                ).ask()
            except KeyboardInterrupt:
                return

            if not confirm:
                return
            quantity = 1

        # Process sale
        total_gold = sell_price * quantity

        # Remove from inventory
        char.inventory.remove_item(item_id, quantity)

        # Add gold
        gold_currency = Currency(gold=total_gold)
        char.inventory.currency.add(gold_currency)

        # Show confirmation
        remaining_gold = char.inventory.currency.to_copper() // 100
        print(f"\n✓ Sold {quantity}x {name} for {total_gold} GP")
        print(f"  {char.name}'s gold: {remaining_gold} GP\n")
