# ABOUTME: Unit tests for the inventory system
# ABOUTME: Tests item management, equipment, gold tracking, and edge cases

import pytest
from dnd_engine.systems.inventory import Inventory, InventoryItem, EquipmentSlot


class TestInventoryItem:
    """Test the InventoryItem dataclass"""

    def test_create_inventory_item(self):
        """Test creating an inventory item"""
        item = InventoryItem(item_id="longsword", category="weapons", quantity=1)
        assert item.item_id == "longsword"
        assert item.category == "weapons"
        assert item.quantity == 1

    def test_inventory_item_default_quantity(self):
        """Test that default quantity is 1"""
        item = InventoryItem(item_id="dagger", category="weapons")
        assert item.quantity == 1

    def test_inventory_item_string_representation(self):
        """Test string representation of inventory items"""
        item1 = InventoryItem(item_id="potion_of_healing", category="consumables", quantity=1)
        assert "potion_of_healing" in str(item1)
        assert "x" not in str(item1)  # No quantity indicator for single items

        item2 = InventoryItem(item_id="potion_of_healing", category="consumables", quantity=3)
        assert "potion_of_healing" in str(item2)
        assert "x3" in str(item2)


class TestInventory:
    """Test the Inventory class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.inventory = Inventory()

    def test_create_inventory(self):
        """Test creating an empty inventory"""
        assert self.inventory.gold == 0
        assert self.inventory.is_empty()
        assert self.inventory.item_count() == 0

    def test_add_single_item(self):
        """Test adding a single item"""
        result = self.inventory.add_item("longsword", "weapons", 1)
        assert result is True
        assert self.inventory.has_item("longsword")
        assert self.inventory.get_item_quantity("longsword") == 1
        assert not self.inventory.is_empty()

    def test_add_multiple_same_item(self):
        """Test adding multiple of the same item stacks them"""
        self.inventory.add_item("potion_of_healing", "consumables", 2)
        self.inventory.add_item("potion_of_healing", "consumables", 3)
        assert self.inventory.get_item_quantity("potion_of_healing") == 5
        assert self.inventory.item_count() == 1  # Still just one unique item

    def test_add_different_items(self):
        """Test adding different items"""
        self.inventory.add_item("longsword", "weapons", 1)
        self.inventory.add_item("leather_armor", "armor", 1)
        self.inventory.add_item("potion_of_healing", "consumables", 2)

        assert self.inventory.item_count() == 3
        assert self.inventory.has_item("longsword")
        assert self.inventory.has_item("leather_armor")
        assert self.inventory.has_item("potion_of_healing")

    def test_add_item_with_zero_quantity_raises_error(self):
        """Test that adding zero quantity raises ValueError"""
        with pytest.raises(ValueError):
            self.inventory.add_item("sword", "weapons", 0)

    def test_add_item_with_negative_quantity_raises_error(self):
        """Test that adding negative quantity raises ValueError"""
        with pytest.raises(ValueError):
            self.inventory.add_item("sword", "weapons", -1)

    def test_add_item_respects_max_items(self):
        """Test that inventory respects max_items limit"""
        limited_inventory = Inventory(max_items=2)

        # Add two items successfully
        assert limited_inventory.add_item("longsword", "weapons") is True
        assert limited_inventory.add_item("dagger", "weapons") is True

        # Third item should fail
        assert limited_inventory.add_item("leather_armor", "armor") is False
        assert limited_inventory.item_count() == 2

        # But adding more of existing item should work
        assert limited_inventory.add_item("longsword", "weapons", 5) is True
        assert limited_inventory.get_item_quantity("longsword") == 6

    def test_remove_item(self):
        """Test removing an item"""
        self.inventory.add_item("potion_of_healing", "consumables", 5)

        result = self.inventory.remove_item("potion_of_healing", 2)
        assert result is True
        assert self.inventory.get_item_quantity("potion_of_healing") == 3

    def test_remove_all_of_item(self):
        """Test removing all quantity of an item removes it completely"""
        self.inventory.add_item("potion_of_healing", "consumables", 3)

        result = self.inventory.remove_item("potion_of_healing", 3)
        assert result is True
        assert not self.inventory.has_item("potion_of_healing")
        assert self.inventory.is_empty()

    def test_remove_nonexistent_item(self):
        """Test removing an item that doesn't exist"""
        result = self.inventory.remove_item("nonexistent", 1)
        assert result is False

    def test_remove_more_than_available(self):
        """Test removing more than available quantity fails"""
        self.inventory.add_item("potion_of_healing", "consumables", 2)

        result = self.inventory.remove_item("potion_of_healing", 5)
        assert result is False
        assert self.inventory.get_item_quantity("potion_of_healing") == 2  # Unchanged

    def test_remove_with_zero_quantity_raises_error(self):
        """Test that removing zero quantity raises ValueError"""
        self.inventory.add_item("sword", "weapons")
        with pytest.raises(ValueError):
            self.inventory.remove_item("sword", 0)

    def test_remove_with_negative_quantity_raises_error(self):
        """Test that removing negative quantity raises ValueError"""
        self.inventory.add_item("sword", "weapons")
        with pytest.raises(ValueError):
            self.inventory.remove_item("sword", -1)

    def test_has_item_with_quantity(self):
        """Test checking for items with specific quantities"""
        self.inventory.add_item("potion_of_healing", "consumables", 3)

        assert self.inventory.has_item("potion_of_healing", 1)
        assert self.inventory.has_item("potion_of_healing", 3)
        assert not self.inventory.has_item("potion_of_healing", 5)

    def test_get_item_quantity_nonexistent(self):
        """Test getting quantity of nonexistent item returns 0"""
        assert self.inventory.get_item_quantity("nonexistent") == 0

    def test_equip_weapon(self):
        """Test equipping a weapon"""
        self.inventory.add_item("longsword", "weapons")

        result = self.inventory.equip_item("longsword", EquipmentSlot.WEAPON)
        assert result is True
        assert self.inventory.get_equipped_item(EquipmentSlot.WEAPON) == "longsword"

    def test_equip_armor(self):
        """Test equipping armor"""
        self.inventory.add_item("chain_mail", "armor")

        result = self.inventory.equip_item("chain_mail", EquipmentSlot.ARMOR)
        assert result is True
        assert self.inventory.get_equipped_item(EquipmentSlot.ARMOR) == "chain_mail"

    def test_equip_nonexistent_item(self):
        """Test equipping an item not in inventory fails"""
        result = self.inventory.equip_item("nonexistent", EquipmentSlot.WEAPON)
        assert result is False
        assert self.inventory.get_equipped_item(EquipmentSlot.WEAPON) is None

    def test_equip_replaces_previous_item(self):
        """Test equipping a new item replaces the old one"""
        self.inventory.add_item("longsword", "weapons")
        self.inventory.add_item("greataxe", "weapons")

        self.inventory.equip_item("longsword", EquipmentSlot.WEAPON)
        assert self.inventory.get_equipped_item(EquipmentSlot.WEAPON) == "longsword"

        self.inventory.equip_item("greataxe", EquipmentSlot.WEAPON)
        assert self.inventory.get_equipped_item(EquipmentSlot.WEAPON) == "greataxe"

    def test_unequip_item(self):
        """Test unequipping an item"""
        self.inventory.add_item("longsword", "weapons")
        self.inventory.equip_item("longsword", EquipmentSlot.WEAPON)

        unequipped = self.inventory.unequip_item(EquipmentSlot.WEAPON)
        assert unequipped == "longsword"
        assert self.inventory.get_equipped_item(EquipmentSlot.WEAPON) is None

    def test_unequip_empty_slot(self):
        """Test unequipping an empty slot returns None"""
        unequipped = self.inventory.unequip_item(EquipmentSlot.WEAPON)
        assert unequipped is None

    def test_remove_equipped_item_unequips_it(self):
        """Test that removing an equipped item automatically unequips it"""
        self.inventory.add_item("longsword", "weapons")
        self.inventory.equip_item("longsword", EquipmentSlot.WEAPON)

        self.inventory.remove_item("longsword")
        assert self.inventory.get_equipped_item(EquipmentSlot.WEAPON) is None

    def test_add_gold(self):
        """Test adding gold"""
        self.inventory.add_gold(50)
        assert self.inventory.gold == 50

        self.inventory.add_gold(25)
        assert self.inventory.gold == 75

    def test_add_zero_gold(self):
        """Test adding zero gold is allowed"""
        self.inventory.add_gold(0)
        assert self.inventory.gold == 0

    def test_add_negative_gold_raises_error(self):
        """Test that adding negative gold raises ValueError"""
        with pytest.raises(ValueError):
            self.inventory.add_gold(-10)

    def test_remove_gold(self):
        """Test removing gold"""
        self.inventory.add_gold(100)

        result = self.inventory.remove_gold(30)
        assert result is True
        assert self.inventory.gold == 70

    def test_remove_more_gold_than_available(self):
        """Test removing more gold than available fails"""
        self.inventory.add_gold(50)

        result = self.inventory.remove_gold(100)
        assert result is False
        assert self.inventory.gold == 50  # Unchanged

    def test_remove_negative_gold_raises_error(self):
        """Test that removing negative gold raises ValueError"""
        self.inventory.add_gold(50)
        with pytest.raises(ValueError):
            self.inventory.remove_gold(-10)

    def test_has_gold(self):
        """Test checking for gold"""
        self.inventory.add_gold(100)

        assert self.inventory.has_gold(50)
        assert self.inventory.has_gold(100)
        assert not self.inventory.has_gold(101)

    def test_get_all_items(self):
        """Test getting all items"""
        self.inventory.add_item("longsword", "weapons")
        self.inventory.add_item("leather_armor", "armor")
        self.inventory.add_item("potion_of_healing", "consumables", 2)

        all_items = self.inventory.get_all_items()
        assert len(all_items) == 3

        item_ids = {item.item_id for item in all_items}
        assert item_ids == {"longsword", "leather_armor", "potion_of_healing"}

    def test_get_items_by_category(self):
        """Test filtering items by category"""
        self.inventory.add_item("longsword", "weapons")
        self.inventory.add_item("dagger", "weapons")
        self.inventory.add_item("leather_armor", "armor")
        self.inventory.add_item("potion_of_healing", "consumables")

        weapons = self.inventory.get_items_by_category("weapons")
        assert len(weapons) == 2
        weapon_ids = {item.item_id for item in weapons}
        assert weapon_ids == {"longsword", "dagger"}

        armor = self.inventory.get_items_by_category("armor")
        assert len(armor) == 1
        assert armor[0].item_id == "leather_armor"

        consumables = self.inventory.get_items_by_category("consumables")
        assert len(consumables) == 1

    def test_get_items_by_category_empty(self):
        """Test getting items from empty category"""
        self.inventory.add_item("longsword", "weapons")

        armor = self.inventory.get_items_by_category("armor")
        assert len(armor) == 0

    def test_total_value(self):
        """Test calculating total inventory value"""
        # Mock items data
        items_data = {
            "weapons": {
                "longsword": {"name": "Longsword", "value": 15},
                "dagger": {"name": "Dagger", "value": 2}
            },
            "armor": {
                "leather_armor": {"name": "Leather Armor", "value": 10}
            },
            "consumables": {
                "potion_of_healing": {"name": "Potion of Healing", "value": 50}
            }
        }

        self.inventory.add_item("longsword", "weapons", 1)
        self.inventory.add_item("dagger", "weapons", 3)
        self.inventory.add_item("potion_of_healing", "consumables", 2)

        total = self.inventory.total_value(items_data)
        # 15 (longsword) + 6 (3 daggers) + 100 (2 potions) = 121
        assert total == 121

    def test_string_representation_empty(self):
        """Test string representation of empty inventory"""
        assert "(empty)" in str(self.inventory).lower()

    def test_string_representation_with_items(self):
        """Test string representation with items"""
        self.inventory.add_item("longsword", "weapons")
        self.inventory.add_item("potion_of_healing", "consumables", 3)
        self.inventory.add_gold(50)

        inv_str = str(self.inventory)
        assert "Inventory" in inv_str
        assert "50 gp" in inv_str
        assert "longsword" in inv_str
        assert "potion_of_healing" in inv_str

    def test_string_representation_with_equipped(self):
        """Test string representation shows equipped items"""
        self.inventory.add_item("longsword", "weapons")
        self.inventory.equip_item("longsword", EquipmentSlot.WEAPON)

        inv_str = str(self.inventory)
        assert "Equipped" in inv_str
        assert "longsword" in inv_str
        assert "[equipped]" in inv_str


class TestInventoryIntegration:
    """Integration tests for inventory edge cases and complex scenarios"""

    def test_multiple_equipment_changes(self):
        """Test changing equipment multiple times"""
        inventory = Inventory()
        inventory.add_item("longsword", "weapons")
        inventory.add_item("shortsword", "weapons")
        inventory.add_item("greataxe", "weapons")

        # Equip and change multiple times
        inventory.equip_item("longsword", EquipmentSlot.WEAPON)
        assert inventory.get_equipped_item(EquipmentSlot.WEAPON) == "longsword"

        inventory.equip_item("shortsword", EquipmentSlot.WEAPON)
        assert inventory.get_equipped_item(EquipmentSlot.WEAPON) == "shortsword"

        inventory.equip_item("greataxe", EquipmentSlot.WEAPON)
        assert inventory.get_equipped_item(EquipmentSlot.WEAPON) == "greataxe"

        # All items still in inventory
        assert inventory.has_item("longsword")
        assert inventory.has_item("shortsword")
        assert inventory.has_item("greataxe")

    def test_complex_item_management(self):
        """Test complex sequence of adding, removing, and equipping items"""
        inventory = Inventory()

        # Add items
        inventory.add_item("longsword", "weapons")
        inventory.add_item("potion_of_healing", "consumables", 5)

        # Equip weapon
        inventory.equip_item("longsword", EquipmentSlot.WEAPON)

        # Use some potions
        inventory.remove_item("potion_of_healing", 2)
        assert inventory.get_item_quantity("potion_of_healing") == 3

        # Add more potions
        inventory.add_item("potion_of_healing", "consumables", 1)
        assert inventory.get_item_quantity("potion_of_healing") == 4

        # Add and equip new weapon
        inventory.add_item("greataxe", "weapons")
        inventory.equip_item("greataxe", EquipmentSlot.WEAPON)

        # Old weapon still in inventory but not equipped
        assert inventory.has_item("longsword")
        assert inventory.get_equipped_item(EquipmentSlot.WEAPON) == "greataxe"

    def test_inventory_with_max_capacity(self):
        """Test inventory behavior at maximum capacity"""
        inventory = Inventory(max_items=3)

        # Fill to capacity
        inventory.add_item("longsword", "weapons")
        inventory.add_item("leather_armor", "armor")
        inventory.add_item("potion_of_healing", "consumables")

        assert inventory.item_count() == 3

        # Can't add new item
        assert inventory.add_item("dagger", "weapons") is False

        # Can add more of existing item
        assert inventory.add_item("potion_of_healing", "consumables", 3) is True
        assert inventory.get_item_quantity("potion_of_healing") == 4

        # Remove an item, then can add new one
        inventory.remove_item("longsword")
        assert inventory.add_item("dagger", "weapons") is True
