# ABOUTME: Inventory management system for player characters
# ABOUTME: Handles item storage, equipping, usage, and currency tracking

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dnd_engine.systems.currency import Currency


class EquipmentSlot(Enum):
    """Equipment slots for weapons and armor"""
    WEAPON = "weapon"
    ARMOR = "armor"


@dataclass
class InventoryItem:
    """
    Represents an item in inventory with quantity.

    Items are stored by ID referencing the items.json data.
    The item category determines where to look up full item data.
    """
    item_id: str
    category: str  # "weapons", "armor", "consumables"
    quantity: int = 1

    def __str__(self) -> str:
        """String representation of the inventory item"""
        qty_str = f" x{self.quantity}" if self.quantity > 1 else ""
        return f"{self.item_id}{qty_str}"


class Inventory:
    """
    Manages character inventory including items, equipment, and gold.

    Handles:
    - Adding/removing items with quantity tracking
    - Equipping/unequipping weapons and armor
    - Using consumables
    - Gold tracking
    - Capacity management (optional)

    Items are stored by ID and category, with full item data
    looked up from the data loader when needed.
    """

    def __init__(self, max_items: Optional[int] = None):
        """
        Initialize inventory with optional capacity limit.

        Args:
            max_items: Maximum number of unique item types (None for unlimited)
        """
        self.max_items = max_items
        self.items: Dict[str, InventoryItem] = {}  # item_id -> InventoryItem
        self.equipped: Dict[EquipmentSlot, Optional[str]] = {
            EquipmentSlot.WEAPON: None,
            EquipmentSlot.ARMOR: None
        }
        self.currency: Currency = Currency()

    def add_item(
        self,
        item_id: str,
        category: str,
        quantity: int = 1
    ) -> bool:
        """
        Add an item to the inventory.

        If the item already exists, increases quantity.
        If inventory is full (max_items reached), returns False.

        Args:
            item_id: ID of the item from items.json
            category: Item category ("weapons", "armor", "consumables")
            quantity: Number to add (default 1)

        Returns:
            True if item was added, False if inventory full

        Raises:
            ValueError: If quantity is negative or zero
        """
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        # Check if item already exists
        if item_id in self.items:
            self.items[item_id].quantity += quantity
            return True

        # Check capacity limit
        if self.max_items is not None and len(self.items) >= self.max_items:
            return False

        # Add new item
        self.items[item_id] = InventoryItem(
            item_id=item_id,
            category=category,
            quantity=quantity
        )
        return True

    def remove_item(self, item_id: str, quantity: int = 1) -> bool:
        """
        Remove an item from inventory.

        Decreases quantity by the specified amount. If quantity reaches zero,
        removes the item entirely.

        Args:
            item_id: ID of the item to remove
            quantity: Number to remove (default 1)

        Returns:
            True if item was removed, False if not enough quantity

        Raises:
            ValueError: If quantity is negative or zero
        """
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        if item_id not in self.items:
            return False

        item = self.items[item_id]

        if item.quantity < quantity:
            return False

        item.quantity -= quantity

        # Remove item if quantity reaches zero
        if item.quantity == 0:
            del self.items[item_id]
            # Unequip if it was equipped
            for slot, equipped_id in self.equipped.items():
                if equipped_id == item_id:
                    self.equipped[slot] = None

        return True

    def has_item(self, item_id: str, quantity: int = 1) -> bool:
        """
        Check if inventory contains an item with sufficient quantity.

        Args:
            item_id: ID of the item to check
            quantity: Minimum quantity required (default 1)

        Returns:
            True if item exists with at least the specified quantity
        """
        if item_id not in self.items:
            return False

        return self.items[item_id].quantity >= quantity

    def get_item_quantity(self, item_id: str) -> int:
        """
        Get the quantity of an item in inventory.

        Args:
            item_id: ID of the item

        Returns:
            Quantity of the item (0 if not in inventory)
        """
        if item_id not in self.items:
            return 0

        return self.items[item_id].quantity

    def equip_item(self, item_id: str, slot: EquipmentSlot) -> bool:
        """
        Equip an item to a slot.

        Args:
            item_id: ID of the item to equip
            slot: Equipment slot (WEAPON or ARMOR)

        Returns:
            True if item was equipped, False if item not in inventory
        """
        if item_id not in self.items:
            return False

        self.equipped[slot] = item_id
        return True

    def unequip_item(self, slot: EquipmentSlot) -> Optional[str]:
        """
        Unequip an item from a slot.

        Args:
            slot: Equipment slot to unequip

        Returns:
            ID of the unequipped item, or None if slot was empty
        """
        item_id = self.equipped[slot]
        self.equipped[slot] = None
        return item_id

    def get_equipped_item(self, slot: EquipmentSlot) -> Optional[str]:
        """
        Get the item equipped in a slot.

        Args:
            slot: Equipment slot to check

        Returns:
            ID of equipped item, or None if slot is empty
        """
        return self.equipped[slot]

    @property
    def gold(self) -> int:
        """
        Backward compatibility property for gold pieces.

        Returns:
            Current gold piece amount
        """
        return self.currency.gold

    @gold.setter
    def gold(self, amount: int) -> None:
        """
        Backward compatibility property setter for gold pieces.

        Args:
            amount: Amount of gold to set
        """
        self.currency.gold = amount

    def add_gold(self, amount: int) -> None:
        """
        Add gold to the inventory.

        Args:
            amount: Amount of gold to add

        Raises:
            ValueError: If amount is negative
        """
        if amount < 0:
            raise ValueError("Cannot add negative gold")

        self.currency.add(Currency(gold=amount))

    def remove_gold(self, amount: int) -> bool:
        """
        Remove gold from the inventory.

        For backward compatibility, this preserves the gold denomination
        when possible instead of fully consolidating.

        Args:
            amount: Amount of gold to remove

        Returns:
            True if gold was removed, False if insufficient gold

        Raises:
            ValueError: If amount is negative
        """
        if amount < 0:
            raise ValueError("Cannot remove negative gold")

        if self.currency.gold >= amount:
            # Can remove directly from gold without consolidating
            self.currency.gold -= amount
            return True

        # Need to make change - convert other denominations to gold value
        if self.currency.to_copper() >= amount * Currency.CP_PER_GP:
            # Have enough total value, do full subtraction and preserve gold if possible
            total_cp = self.currency.to_copper()
            remaining_cp = total_cp - (amount * Currency.CP_PER_GP)

            # Try to keep result in gold denomination if possible
            if remaining_cp % Currency.CP_PER_GP == 0:
                # Can express entirely in gold
                self.currency.gold = remaining_cp // Currency.CP_PER_GP
                self.currency.silver = 0
                self.currency.copper = 0
                self.currency.electrum = 0
                self.currency.platinum = 0
                return True
            else:
                # Use normal subtraction which consolidates
                return self.currency.subtract(Currency(gold=amount))

        return False

    def has_gold(self, amount: int) -> bool:
        """
        Check if inventory contains sufficient gold.

        Args:
            amount: Amount of gold to check for

        Returns:
            True if inventory has at least the specified amount
        """
        return self.currency.can_afford(Currency(gold=amount))

    def get_all_items(self) -> List[InventoryItem]:
        """
        Get all items in inventory.

        Returns:
            List of all InventoryItem objects
        """
        return list(self.items.values())

    def get_items_by_category(self, category: str) -> List[InventoryItem]:
        """
        Get all items of a specific category.

        Args:
            category: Item category to filter by

        Returns:
            List of InventoryItem objects in that category
        """
        return [item for item in self.items.values() if item.category == category]

    def is_empty(self) -> bool:
        """
        Check if inventory has no items (gold doesn't count).

        Returns:
            True if inventory has no items
        """
        return len(self.items) == 0

    def item_count(self) -> int:
        """
        Get number of unique item types in inventory.

        Returns:
            Number of different items (not total quantity)
        """
        return len(self.items)

    def total_value(self, item_data: Dict[str, Dict[str, Any]]) -> int:
        """
        Calculate total value of all items in inventory.

        Args:
            item_data: Full items data loaded from items.json

        Returns:
            Total value in gold pieces (excluding gold itself)
        """
        total = 0
        for item in self.items.values():
            category_data = item_data.get(item.category, {})
            item_info = category_data.get(item.item_id, {})
            value = item_info.get("value", 0)
            total += value * item.quantity

        return total

    def use_item(self, item_id: str, item_data: Dict[str, Dict[str, Any]]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Use a consumable item from inventory.

        Returns item data for the caller to execute the effect, then removes
        the item from inventory. This method handles inventory management only;
        the caller is responsible for applying effects (healing, buffs, etc.).

        Args:
            item_id: ID of the item to use
            item_data: Full items data loaded from items.json

        Returns:
            Tuple of (success: bool, item_info: Optional[Dict])
            - success: True if item was found and removed from inventory
            - item_info: Item data dict if successful, None if item not found

        Example:
            >>> success, item_info = inventory.use_item("potion_of_healing", items_data)
            >>> if success:
            ...     healing_dice = item_info.get("healing")
            ...     # Caller rolls dice and applies healing
        """
        # Check if item exists in inventory
        if not self.has_item(item_id):
            return False, None

        # Get the item from inventory to determine category
        inv_item = self.items[item_id]
        category = inv_item.category

        # Look up full item data
        category_data = item_data.get(category, {})
        item_info = category_data.get(item_id)

        if item_info is None:
            # Item exists in inventory but not in data file (data integrity issue)
            return False, None

        # Remove one from inventory
        self.remove_item(item_id, quantity=1)

        return True, item_info

    def __str__(self) -> str:
        """String representation of the inventory"""
        if self.is_empty() and self.currency.is_zero():
            return "Inventory: (empty)"

        lines = ["Inventory:"]

        # Show equipped items
        weapon = self.equipped[EquipmentSlot.WEAPON]
        armor = self.equipped[EquipmentSlot.ARMOR]
        if weapon or armor:
            lines.append("  Equipped:")
            if weapon:
                lines.append(f"    Weapon: {weapon}")
            if armor:
                lines.append(f"    Armor: {armor}")

        # Show all items by category
        if self.items:
            lines.append("  Items:")
            for item in sorted(self.items.values(), key=lambda i: (i.category, i.item_id)):
                equipped_marker = ""
                if item.item_id in [weapon, armor]:
                    equipped_marker = " [equipped]"
                lines.append(f"    {item}{equipped_marker}")

        # Show currency
        if not self.currency.is_zero():
            lines.append(f"  Currency: {self.currency}")

        return "\n".join(lines)
