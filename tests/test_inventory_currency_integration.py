# ABOUTME: Integration tests for Inventory and Currency systems
# ABOUTME: Tests real-world game scenarios involving item and currency management

import pytest
from dnd_engine.systems.inventory import Inventory, EquipmentSlot
from dnd_engine.systems.currency import Currency


class TestInventoryCurrencyIntegration:
    """Integration tests for Inventory with Currency system"""

    def test_inventory_with_currency(self):
        """Test basic inventory with currency"""
        inv = Inventory()

        # Add items
        inv.add_item("longsword", "weapons")
        inv.add_item("leather_armor", "armor")

        # Add currency
        inv.add_gold(100)

        assert inv.item_count() == 2
        assert inv.has_gold(100)
        assert inv.gold == 100

    def test_currency_display_in_inventory(self):
        """Test that currency displays correctly in inventory output"""
        inv = Inventory()

        inv.add_item("potion_of_healing", "consumables", 2)
        inv.add_gold(50)

        inv_str = str(inv)
        assert "50 gp" in inv_str  # Should show gold in string format
        assert "Currency:" in inv_str

    def test_treasure_looting_scenario(self):
        """Test looting treasure from defeated enemies"""
        player_inv = Inventory()

        # Defeat goblin, loot treasure
        goblin_loot = Currency(gold=5, silver=15, copper=25)
        player_inv.currency.add(goblin_loot)

        assert player_inv.currency.to_copper() == 5 * 100 + 15 * 10 + 25
        assert player_inv.currency.gold == 5
        assert player_inv.currency.silver == 15
        assert player_inv.currency.copper == 25

    def test_shop_purchase_scenario(self):
        """Test purchasing items from a shop"""
        player_inv = Inventory()

        # Start with some gold
        player_inv.add_gold(50)

        # Shop items and prices
        shop_item = "health_potion"
        price = Currency(silver=5)  # 50 cp

        # Check if player can afford
        assert player_inv.currency.can_afford(price)

        # Purchase item
        player_inv.currency.subtract(price)
        player_inv.add_item(shop_item, "consumables")

        # Verify state
        assert player_inv.has_item(shop_item)
        assert player_inv.currency.to_copper() == 4950  # 5000 - 50

    def test_complex_transaction_scenario(self):
        """Test complex transaction with mixed currencies"""
        player_inv = Inventory()
        merchant_inv = Inventory()

        # Player has 2 gp + 3 sp + 5 cp = 235 cp
        player_inv.add_gold(2)
        player_inv.currency.add(Currency(silver=3, copper=5))

        # Merchant has items and wants 1 gp + 8 sp for some item = 180 cp
        price = Currency(gold=1, silver=8)

        # Check affordability
        assert player_inv.currency.can_afford(price)

        # Purchase
        player_inv.currency.subtract(price)
        merchant_inv.currency.add(price)

        # Verify both inventories
        # 235 - 180 = 55 cp remaining (consolidated form = 1 ep + 5 cp)
        assert player_inv.currency.to_copper() == 55
        assert merchant_inv.currency.to_copper() == 180

    def test_party_treasure_splitting(self):
        """Test splitting treasure among party members"""
        party_treasury = Inventory()
        member1 = Inventory()
        member2 = Inventory()
        member3 = Inventory()
        member4 = Inventory()

        # Treasury collects loot
        party_treasury.add_gold(100)
        party_treasury.currency.add(Currency(silver=50))

        total_value = party_treasury.currency.to_copper()  # 11000 cp
        share_value = total_value // 4  # 2750 cp each

        # Distribute to members
        for member in [member1, member2, member3, member4]:
            share = Currency()
            share._from_copper(share_value)
            member.currency.add(share)

        # Verify each got 2750 cp (27 gp 5 sp)
        for member in [member1, member2, member3, member4]:
            assert member.currency.to_copper() == share_value

    def test_inventory_with_equipped_items_and_currency(self):
        """Test inventory display with equipped items and currency"""
        inv = Inventory()

        # Add and equip items
        inv.add_item("longsword", "weapons")
        inv.equip_item("longsword", EquipmentSlot.WEAPON)

        inv.add_item("plate_armor", "armor")
        inv.equip_item("plate_armor", EquipmentSlot.ARMOR)

        # Add currency
        inv.add_gold(75)
        inv.currency.add(Currency(silver=12, copper=8))

        inv_str = str(inv)
        assert "Equipped" in inv_str
        assert "longsword" in inv_str
        assert "plate_armor" in inv_str
        assert "Currency:" in inv_str

    def test_gold_property_backward_compatibility(self):
        """Test that gold property maintains backward compatibility"""
        inv = Inventory()

        # Using backward compat property
        inv.gold = 50
        assert inv.gold == 50
        assert inv.currency.gold == 50

        # Adding gold
        inv.add_gold(25)
        assert inv.gold == 75

        # Removing gold
        inv.remove_gold(30)
        assert inv.gold == 45

        # Checking gold
        assert inv.has_gold(45)
        assert not inv.has_gold(50)

    def test_currency_consolidation_in_loot(self):
        """Test that looted currency consolidates appropriately"""
        player_inv = Inventory()

        # Loot mixed denominations
        loot = Currency(copper=50, silver=5, electrum=1, gold=2)
        player_inv.currency.add(loot)

        # Total: 50 + 50 + 50 + 200 = 350 cp
        assert player_inv.currency.to_copper() == 350

        # Individual denominations unchanged (not auto-consolidated on add)
        assert player_inv.currency.copper == 50
        assert player_inv.currency.silver == 5
        assert player_inv.currency.electrum == 1
        assert player_inv.currency.gold == 2

        # Manual consolidation
        player_inv.currency.consolidate()
        assert player_inv.currency.to_copper() == 350  # Value unchanged
        # 350 cp = 3 gp (300) + 1 ep (50) + 0 sp + 0 cp
        assert player_inv.currency.gold == 3
        assert player_inv.currency.electrum == 1
        assert player_inv.currency.silver == 0
        assert player_inv.currency.copper == 0

    def test_item_value_calculation_with_currency(self):
        """Test calculating total wealth including item value and currency"""
        inv = Inventory()

        # Items with values
        items_data = {
            "weapons": {
                "longsword": {"name": "Longsword", "value": 15},
                "dagger": {"name": "Dagger", "value": 2}
            }
        }

        inv.add_item("longsword", "weapons", 1)  # 15 gp value
        inv.add_item("dagger", "weapons", 2)  # 2 gp value each

        # Currency
        inv.add_gold(50)

        # Total wealth
        item_value = inv.total_value(items_data)
        currency_value = inv.currency.to_copper()

        total_cp = currency_value + item_value * 100
        assert total_cp == (50 * 100 + 15 * 100 + 2 * 100 + 2 * 100)  # 6900 cp

    def test_insufficient_funds_for_purchase(self):
        """Test attempting to purchase without sufficient funds"""
        player_inv = Inventory()

        player_inv.add_gold(5)  # 5 gp = 500 cp
        expensive_item_price = Currency(gold=10)  # 1000 cp

        assert not player_inv.currency.can_afford(expensive_item_price)
        assert not player_inv.remove_gold(10)

        # Inventory unchanged
        assert player_inv.gold == 5

    def test_currency_string_representation_in_context(self):
        """Test currency string representation in various contexts"""
        inv = Inventory()

        # Empty inventory
        inv_str = str(inv)
        assert "(empty)" in inv_str.lower()

        # Add items
        inv.add_item("rope", "equipment")
        inv.add_gold(3)
        inv.currency.add(Currency(silver=7, copper=11))

        inv_str = str(inv)
        assert "rope" in inv_str
        assert "3 gp, 7 sp, 11 cp" in inv_str

    def test_multiple_purchases_depleting_funds(self):
        """Test making multiple purchases that deplete funds"""
        player_inv = Inventory()
        player_inv.add_gold(50)  # Start with 50 gp

        purchases = [
            (Currency(gold=5), "item1"),
            (Currency(gold=10), "item2"),
            (Currency(gold=20), "item3"),
            (Currency(gold=15), "item4"),
        ]

        for price, item_name in purchases:
            if player_inv.currency.can_afford(price):
                player_inv.currency.subtract(price)
                player_inv.add_item(item_name, "items")
            else:
                break

        # Should have made 4 purchases (5 + 10 + 20 + 15 = 50)
        assert player_inv.item_count() == 4
        assert player_inv.currency.is_zero()

    def test_cannot_purchase_beyond_budget(self):
        """Test that purchasing stops when funds are insufficient"""
        player_inv = Inventory()
        player_inv.add_gold(15)  # 15 gp

        expensive = Currency(gold=20)
        cheap = Currency(gold=3)

        # Can't afford expensive
        assert not player_inv.currency.can_afford(expensive)

        # Can afford cheap
        assert player_inv.currency.can_afford(cheap)
        player_inv.currency.subtract(cheap)
        player_inv.add_item("cheap_item", "items")

        assert player_inv.currency.to_copper() == 1200  # 12 gp
        assert player_inv.item_count() == 1
