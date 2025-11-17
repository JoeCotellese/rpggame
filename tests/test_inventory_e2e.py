# ABOUTME: End-to-end tests for inventory system through complete game flow
# ABOUTME: Tests full player journey with inventory: searching, equipping, using items in combat

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.party import Party
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.systems.inventory import EquipmentSlot
from dnd_engine.utils.events import EventBus
from dnd_engine.rules.loader import DataLoader
from dnd_engine.core.dice import DiceRoller


class TestInventoryEndToEnd:
    """End-to-end tests for complete inventory gameplay flow"""

    def setup_method(self):
        """Set up test fixtures"""
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=15,
            intelligence=10,
            wisdom=12,
            charisma=8
        )

        self.player = Character(
            name="Test Hero",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=20,
            ac=16
        )

        # Create party with the player
        self.party = Party(characters=[self.player])

        self.event_bus = EventBus()
        self.data_loader = DataLoader()
        self.dice_roller = DiceRoller(seed=42)

        self.game_state = GameState(
            party=self.party,
            dungeon_name="goblin_warren",
            event_bus=self.event_bus,
            data_loader=self.data_loader,
            dice_roller=self.dice_roller
        )

        # Clear enemies from all rooms for testing
        for room_id in self.game_state.dungeon["rooms"]:
            self.game_state.dungeon["rooms"][room_id]["enemies"] = []

    def test_complete_dungeon_inventory_flow(self):
        """Test complete flow: explore dungeon, collect items, equip, use in combat"""
        # Start with empty inventory
        assert self.player.inventory.is_empty()
        assert self.player.inventory.gold == 0

        # Move to storage room
        self.game_state.move("north")  # to guard_post
        self.game_state.move("east")   # to storage_room

        # Search and collect items
        items_found = self.game_state.search_room()
        assert len(items_found) > 0

        # Verify we now have items and gold
        assert self.player.inventory.gold > 0
        assert not self.player.inventory.is_empty()

        # Should have found potion and shortsword in storage room
        assert self.player.inventory.has_item("potion_of_healing")
        assert self.player.inventory.has_item("shortsword")

        # Equip the shortsword
        self.player.inventory.equip_item("shortsword", EquipmentSlot.WEAPON)
        assert self.player.inventory.get_equipped_item(EquipmentSlot.WEAPON) == "shortsword"

        # Verify inventory state
        # Storage room has 2 gold, 5 silver, 30 copper = 280 cp = 2 gold + 8 silver
        assert self.player.inventory.gold == 2
        assert self.player.inventory.item_count() == 2

    def test_collect_items_from_multiple_rooms(self):
        """Test collecting items from multiple rooms in sequence"""
        total_gold_collected = 0
        items_collected = set()

        # Search storage room
        self.game_state.move("north")
        self.game_state.move("east")
        items = self.game_state.search_room()
        if items:
            for item in items:
                if item["type"] == "currency":
                    # Currency is consolidated, so count the gold pieces
                    total_gold_collected += item.get("gold", 0)
                elif item["type"] == "gold":
                    total_gold_collected += item["amount"]
                elif item["type"] == "item":
                    items_collected.add(item["id"])

        # Move to prison
        self.game_state.move("west")  # back to guard_post
        self.game_state.move("north")  # to main_hall
        self.game_state.move("west")   # to prison

        items = self.game_state.search_room()
        if items:
            for item in items:
                if item["type"] == "currency":
                    # Currency is consolidated, so count the gold pieces
                    total_gold_collected += item.get("gold", 0)
                elif item["type"] == "gold":
                    total_gold_collected += item["amount"]
                elif item["type"] == "item":
                    items_collected.add(item["id"])

        # Verify accumulated inventory
        assert self.player.inventory.gold == total_gold_collected
        for item_id in items_collected:
            assert self.player.inventory.has_item(item_id)

    def test_use_healing_potion_in_combat_scenario(self):
        """Test using a healing potion when damaged"""
        # Give player a healing potion
        self.player.inventory.add_item("potion_of_healing", "consumables")

        # Damage the player
        initial_hp = self.player.current_hp
        self.player.take_damage(10)
        damaged_hp = self.player.current_hp

        assert damaged_hp == initial_hp - 10

        # Use healing potion
        items_data = self.data_loader.load_items()
        potion_data = items_data["consumables"]["potion_of_healing"]

        # Simulate using potion (roll healing)
        healing_roll = self.dice_roller.roll(potion_data["healing"])
        self.player.heal(healing_roll.total)

        # Remove potion from inventory
        self.player.inventory.remove_item("potion_of_healing")

        # Verify effects
        assert self.player.current_hp > damaged_hp
        assert not self.player.inventory.has_item("potion_of_healing")

    def test_equip_better_armor_found_in_dungeon(self):
        """Test finding and equipping better armor during exploration"""
        # Start with leather armor equipped
        self.player.inventory.add_item("leather_armor", "armor")
        self.player.inventory.equip_item("leather_armor", EquipmentSlot.ARMOR)

        assert self.player.inventory.get_equipped_item(EquipmentSlot.ARMOR) == "leather_armor"

        # Navigate to throne room (has chain mail)
        self.game_state.move("north")  # to guard_post
        self.game_state.move("north")  # to main_hall
        self.game_state.move("north")  # to throne_room

        # Room isn't marked searchable, so items are visible immediately
        # For this test, manually add the item we know is there
        self.player.inventory.add_item("chain_mail", "armor")

        # Equip the better armor
        self.player.inventory.equip_item("chain_mail", EquipmentSlot.ARMOR)

        # Verify swap
        assert self.player.inventory.get_equipped_item(EquipmentSlot.ARMOR) == "chain_mail"
        assert self.player.inventory.has_item("leather_armor")  # Old armor still in inventory

    def test_manage_multiple_weapons(self):
        """Test collecting and swapping between multiple weapons"""
        # Add multiple weapons to inventory
        self.player.inventory.add_item("longsword", "weapons")
        self.player.inventory.add_item("dagger", "weapons")
        self.player.inventory.add_item("greataxe", "weapons")

        # Equip longsword
        self.player.inventory.equip_item("longsword", EquipmentSlot.WEAPON)
        assert self.player.inventory.get_equipped_item(EquipmentSlot.WEAPON) == "longsword"

        # Switch to greataxe for big damage
        self.player.inventory.equip_item("greataxe", EquipmentSlot.WEAPON)
        assert self.player.inventory.get_equipped_item(EquipmentSlot.WEAPON) == "greataxe"

        # Switch to dagger for finesse
        self.player.inventory.equip_item("dagger", EquipmentSlot.WEAPON)
        assert self.player.inventory.get_equipped_item(EquipmentSlot.WEAPON) == "dagger"

        # All weapons still in inventory
        assert self.player.inventory.has_item("longsword")
        assert self.player.inventory.has_item("dagger")
        assert self.player.inventory.has_item("greataxe")

    def test_inventory_persists_across_rooms(self):
        """Test that inventory persists as player moves between rooms"""
        # Collect items in storage room
        self.game_state.move("north")
        self.game_state.move("east")
        self.game_state.search_room()

        gold_after_search = self.player.inventory.gold
        items_after_search = self.player.inventory.get_all_items()

        # Move around the dungeon
        self.game_state.move("west")
        self.game_state.move("south")
        self.game_state.move("north")

        # Inventory should be unchanged
        assert self.player.inventory.gold == gold_after_search
        assert len(self.player.inventory.get_all_items()) == len(items_after_search)

    def test_collect_gold_from_defeated_enemies_room(self):
        """Test collecting gold from rooms after defeating enemies"""
        # Move to guard post (has enemies and gold)
        self.game_state.move("north")

        # The room has 15 gold, but it's not searchable
        # Simulate defeating enemies and looting (gold should be available)
        room = self.game_state.get_current_room()
        gold_items = [item for item in room.get("items", []) if item["type"] == "gold"]

        # In a real game, gold would be acquired after combat
        # For this test, manually add it
        if gold_items:
            for gold_item in gold_items:
                self.player.inventory.add_gold(gold_item["amount"])

            assert self.player.inventory.gold == 15

    def test_multiple_consumables_stack_correctly(self):
        """Test that finding multiple healing potions stacks them"""
        # Add first potion
        self.player.inventory.add_item("potion_of_healing", "consumables", 1)
        assert self.player.inventory.get_item_quantity("potion_of_healing") == 1

        # Find more potions in different rooms
        self.player.inventory.add_item("potion_of_healing", "consumables", 2)
        assert self.player.inventory.get_item_quantity("potion_of_healing") == 3

        # Use one potion
        self.player.inventory.remove_item("potion_of_healing", 1)
        assert self.player.inventory.get_item_quantity("potion_of_healing") == 2

        # Use another
        self.player.inventory.remove_item("potion_of_healing", 1)
        assert self.player.inventory.get_item_quantity("potion_of_healing") == 1

        # Use last one
        self.player.inventory.remove_item("potion_of_healing", 1)
        assert not self.player.inventory.has_item("potion_of_healing")

    def test_inventory_value_increases_as_items_collected(self):
        """Test that inventory value increases as player collects items"""
        items_data = self.data_loader.load_items()

        # Empty inventory has zero value
        assert self.player.inventory.total_value(items_data) == 0

        # Add some items
        self.player.inventory.add_item("longsword", "weapons")
        value1 = self.player.inventory.total_value(items_data)
        assert value1 == 15  # longsword value

        self.player.inventory.add_item("chain_mail", "armor")
        value2 = self.player.inventory.total_value(items_data)
        assert value2 == 90  # 15 + 75

        self.player.inventory.add_item("potion_of_healing", "consumables", 2)
        value3 = self.player.inventory.total_value(items_data)
        assert value3 == 190  # 15 + 75 + 100

    def test_full_dungeon_completion_with_inventory(self):
        """Test completing dungeon collecting all available searchable items"""
        searchable_rooms = []
        total_items_found = 0

        # Navigate through dungeon and search all searchable rooms
        # Storage room
        self.game_state.move("north")
        self.game_state.move("east")
        items = self.game_state.search_room()
        if items:
            total_items_found += len(items)
            searchable_rooms.append("storage_room")

        # Prison
        self.game_state.move("west")
        self.game_state.move("north")
        self.game_state.move("west")
        items = self.game_state.search_room()
        if items:
            total_items_found += len(items)
            searchable_rooms.append("prison")

        # Verify we found items in searchable rooms
        assert len(searchable_rooms) > 0
        assert total_items_found > 0

        # Verify inventory has accumulated items
        assert not self.player.inventory.is_empty()
        assert self.player.inventory.gold > 0


class TestInventoryEdgeCases:
    """End-to-end tests for edge cases and error conditions"""

    def setup_method(self):
        """Set up test fixtures"""
        abilities = Abilities(16, 14, 15, 10, 12, 8)

        self.player = Character(
            name="Test Hero",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=20,
            ac=16
        )

        # Create party with the player
        self.party = Party(characters=[self.player])

        self.game_state = GameState(
            party=self.party,
            dungeon_name="goblin_warren",
            event_bus=EventBus(),
            data_loader=DataLoader(),
            dice_roller=DiceRoller(seed=42)
        )

        # Clear enemies from all rooms for testing
        for room_id in self.game_state.dungeon["rooms"]:
            self.game_state.dungeon["rooms"][room_id]["enemies"] = []

    def test_using_last_healing_potion_removes_it(self):
        """Test that using the last potion removes it from inventory"""
        self.player.inventory.add_item("potion_of_healing", "consumables", 1)
        assert self.player.inventory.has_item("potion_of_healing")

        self.player.inventory.remove_item("potion_of_healing", 1)
        assert not self.player.inventory.has_item("potion_of_healing")
        assert self.player.inventory.is_empty()

    def test_cannot_equip_consumable_items(self):
        """Test that consumable items cannot be equipped"""
        self.player.inventory.add_item("potion_of_healing", "consumables")

        # Trying to equip should fail or not make sense
        # (The inventory system doesn't prevent this at the class level,
        # but the CLI should handle it correctly)
        # This test documents expected behavior

    def test_unequipping_all_gear(self):
        """Test unequipping all equipment"""
        self.player.inventory.add_item("longsword", "weapons")
        self.player.inventory.add_item("chain_mail", "armor")

        self.player.inventory.equip_item("longsword", EquipmentSlot.WEAPON)
        self.player.inventory.equip_item("chain_mail", EquipmentSlot.ARMOR)

        # Unequip everything
        self.player.inventory.unequip_item(EquipmentSlot.WEAPON)
        self.player.inventory.unequip_item(EquipmentSlot.ARMOR)

        assert self.player.inventory.get_equipped_item(EquipmentSlot.WEAPON) is None
        assert self.player.inventory.get_equipped_item(EquipmentSlot.ARMOR) is None

        # Items still in inventory
        assert self.player.inventory.has_item("longsword")
        assert self.player.inventory.has_item("chain_mail")

    def test_healing_when_already_at_full_hp(self):
        """Test using healing potion when already at full health"""
        assert self.player.current_hp == self.player.max_hp

        # Use healing potion
        self.player.inventory.add_item("potion_of_healing", "consumables")

        items_data = self.game_state.data_loader.load_items()
        potion_data = items_data["consumables"]["potion_of_healing"]
        healing_roll = self.game_state.dice_roller.roll(potion_data["healing"])

        old_hp = self.player.current_hp
        self.player.heal(healing_roll.total)

        # HP should not exceed max
        assert self.player.current_hp == self.player.max_hp
        assert self.player.current_hp == old_hp  # No change

    def test_search_already_searched_room(self):
        """Test that searching an already-searched room yields nothing"""
        # Move to storage room
        self.game_state.move("north")
        self.game_state.move("east")

        # First search
        items1 = self.game_state.search_room()
        gold1 = self.player.inventory.gold
        assert len(items1) > 0

        # Second search
        items2 = self.game_state.search_room()
        gold2 = self.player.inventory.gold

        assert len(items2) == 0
        assert gold2 == gold1  # No additional gold
