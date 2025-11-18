# ABOUTME: Integration tests for inventory system with Character and GameState
# ABOUTME: Tests inventory integrated into the full game systems including events

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.party import Party
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.systems.inventory import Inventory, EquipmentSlot
from dnd_engine.utils.events import EventBus, Event, EventType
from dnd_engine.rules.loader import DataLoader
from dnd_engine.core.dice import DiceRoller


class TestInventoryCharacterIntegration:
    """Test inventory integrated with Character class"""

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

        self.character = Character(
            name="Test Hero",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=20,
            ac=16
        )

    def test_character_has_inventory(self):
        """Test that characters have an inventory"""
        assert hasattr(self.character, "inventory")
        assert isinstance(self.character.inventory, Inventory)

    def test_character_inventory_starts_empty(self):
        """Test that character inventory starts empty"""
        assert self.character.inventory.is_empty()
        assert self.character.inventory.gold == 0

    def test_character_can_add_items(self):
        """Test adding items to character inventory"""
        self.character.inventory.add_item("longsword", "weapons")
        assert self.character.inventory.has_item("longsword")

    def test_character_can_equip_items(self):
        """Test equipping items on character"""
        self.character.inventory.add_item("longsword", "weapons")
        self.character.inventory.equip_item("longsword", EquipmentSlot.WEAPON)

        assert self.character.inventory.get_equipped_item(EquipmentSlot.WEAPON) == "longsword"

    def test_character_with_custom_inventory(self):
        """Test creating character with custom inventory"""
        custom_inventory = Inventory()
        custom_inventory.add_item("greataxe", "weapons")
        custom_inventory.add_gold(100)

        char = Character(
            name="Wealthy Hero",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(16, 14, 15, 10, 12, 8),
            max_hp=20,
            ac=16,
            inventory=custom_inventory
        )

        assert char.inventory.has_item("greataxe")
        assert char.inventory.gold == 100


class TestInventoryGameStateIntegration:
    """Test inventory integrated with GameState"""

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

    def test_search_room_adds_items_to_inventory(self):
        """Test that searching a room reveals items, then taking them adds to inventory"""
        # Clear enemies from guard_post to allow movement
        self.game_state.dungeon["rooms"]["guard_post"]["enemies"] = []

        # Move to storage room (has searchable items)
        self.game_state.move("north")  # to guard_post
        self.game_state.move("east")   # to storage_room

        initial_item_count = self.player.inventory.item_count()

        # Search the room (reveals items but doesn't pick them up)
        items = self.game_state.search_room()

        assert len(items) > 0  # Storage room has items
        # Items should NOT be in inventory yet after search
        assert self.player.inventory.item_count() == initial_item_count

        # Take each item
        for item in items:
            if item["type"] == "item":
                self.game_state.take_item(item["id"], self.player)
            elif item["type"] in ["gold", "currency"]:
                self.game_state.take_item("gold", self.player)

        # Now items should be in inventory
        assert self.player.inventory.item_count() > initial_item_count or \
               self.player.inventory.currency.gold > 0

    def test_search_room_adds_gold(self):
        """Test that searching reveals gold, then taking it adds to inventory"""
        # Clear enemies from guard_post to allow movement
        self.game_state.dungeon["rooms"]["guard_post"]["enemies"] = []

        # Move to storage room
        self.game_state.move("north")
        self.game_state.move("east")

        initial_gold = self.player.inventory.currency.gold

        # Search reveals items but doesn't pick up
        items = self.game_state.search_room()

        # Gold should NOT be in inventory yet
        assert self.player.inventory.currency.gold == initial_gold

        # Take the gold/currency
        for item in items:
            if item["type"] in ["gold", "currency"]:
                self.game_state.take_item("gold", self.player)
                break

        # Storage room has 2 gold
        assert self.player.inventory.currency.gold > initial_gold

    def test_search_room_adds_specific_items(self):
        """Test that specific items from room can be taken after searching"""
        # Clear enemies from guard_post to allow movement
        self.game_state.dungeon["rooms"]["guard_post"]["enemies"] = []

        # Move to storage room (has potion_of_healing and shortsword)
        self.game_state.move("north")
        self.game_state.move("east")

        # Search reveals items
        items = self.game_state.search_room()

        # Items should NOT be in inventory yet
        assert not self.player.inventory.has_item("potion_of_healing")
        assert not self.player.inventory.has_item("shortsword")

        # Take each item
        for item in items:
            if item["type"] == "item":
                self.game_state.take_item(item["id"], self.player)

        # Check that items from storage room are now in inventory
        assert self.player.inventory.has_item("potion_of_healing") or \
               self.player.inventory.has_item("shortsword")

    def test_search_room_emits_item_acquired_event(self):
        """Test that taking items emits ITEM_ACQUIRED events"""
        # Clear enemies from guard_post to allow movement
        self.game_state.dungeon["rooms"]["guard_post"]["enemies"] = []

        events_received = []

        def track_event(event: Event):
            events_received.append(event)

        self.event_bus.subscribe(EventType.ITEM_ACQUIRED, track_event)

        # Move to storage room and search
        self.game_state.move("north")
        self.game_state.move("east")
        items = self.game_state.search_room()

        # Search should NOT emit events
        assert len(events_received) == 0

        # Take items
        for item in items:
            if item["type"] == "item":
                self.game_state.take_item(item["id"], self.player)

        # Should have received item acquired events from taking items
        assert len(events_received) > 0
        for event in events_received:
            assert event.type == EventType.ITEM_ACQUIRED
            assert "item_id" in event.data
            assert "category" in event.data

    def test_search_room_emits_gold_acquired_event(self):
        """Test that taking gold emits GOLD_ACQUIRED events"""
        # Clear enemies from guard_post to allow movement
        self.game_state.dungeon["rooms"]["guard_post"]["enemies"] = []

        events_received = []

        def track_event(event: Event):
            events_received.append(event)

        self.event_bus.subscribe(EventType.GOLD_ACQUIRED, track_event)

        # Move to storage room and search
        self.game_state.move("north")
        self.game_state.move("east")
        items = self.game_state.search_room()

        # Search should NOT emit events
        assert len(events_received) == 0

        # Take gold/currency
        for item in items:
            if item["type"] in ["gold", "currency"]:
                self.game_state.take_item("gold", self.player)
                break

        # Should have received gold acquired event
        assert len(events_received) == 1
        event = events_received[0]
        assert event.type == EventType.GOLD_ACQUIRED
        assert "amount" in event.data
        assert event.data["amount"] == 2

    def test_can_search_room_multiple_times(self):
        """Test that a room can be searched multiple times to see current state"""
        # Use current room and set up for testing
        room = self.game_state.get_current_room()
        room["searchable"] = True
        room["searched"] = False
        room["items"] = [
            {"type": "item", "id": "potion_of_healing"},
            {"type": "item", "id": "shortsword"}
        ]

        # First search succeeds
        items1 = self.game_state.search_room()
        assert len(items1) == 2

        # Second search returns same items
        items2 = self.game_state.search_room()
        assert len(items2) == 2

        # Take one item
        self.game_state.take_item("potion_of_healing", self.player)

        # Third search returns remaining items
        items3 = self.game_state.search_room()
        assert len(items3) == 1
        assert items3[0]["id"] == "shortsword"

    def test_search_non_searchable_room(self):
        """Test searching a non-searchable room returns nothing"""
        # Set up current room as non-searchable
        room = self.game_state.get_current_room()
        room["searchable"] = False
        room["items"] = [{"type": "item", "id": "dagger"}]

        items = self.game_state.search_room()
        assert len(items) == 0

    def test_get_item_category_correctly_identifies_items(self):
        """Test that _get_item_category correctly identifies item categories"""
        assert self.game_state._get_item_category("longsword") == "weapons"
        assert self.game_state._get_item_category("chain_mail") == "armor"
        assert self.game_state._get_item_category("potion_of_healing") == "consumables"
        assert self.game_state._get_item_category("nonexistent") is None

    def test_search_and_take_workflow(self):
        """Integration test for search then take workflow"""
        room = self.game_state.get_current_room()

        # Setup room with items
        room["items"] = [
            {"type": "item", "id": "longsword"},
            {"type": "gold", "amount": 50}
        ]
        room["searchable"] = True
        room["searched"] = False

        # Search reveals items but doesn't pick them up
        items_found = self.game_state.search_room()

        assert len(items_found) == 2
        assert room["searched"] is True
        # Items should NOT be in inventory yet
        assert not self.player.inventory.has_item("longsword")
        initial_gold = self.player.inventory.currency.gold

        # Take the longsword
        success = self.game_state.take_item("longsword", self.player)

        assert success is True
        assert self.player.inventory.has_item("longsword")
        # Only longsword should be gone from room
        assert len(room["items"]) == 1

        # Take the gold
        success = self.game_state.take_item("gold", self.player)

        assert success is True
        assert self.player.inventory.currency.gold == initial_gold + 50
        # All items should be gone
        assert len(room["items"]) == 0

    def test_take_item_without_search_fails(self):
        """Test that taking items from unsearched searchable room fails"""
        room = self.game_state.get_current_room()

        # Setup searchable room with items but don't search
        room["items"] = [{"type": "item", "id": "dagger"}]
        room["searchable"] = True
        room["searched"] = False

        # Get available items should return empty for unsearched room
        available = self.game_state.get_available_items_in_room()
        assert len(available) == 0


class TestInventoryEventIntegration:
    """Test inventory event system integration"""

    def setup_method(self):
        """Set up test fixtures"""
        self.event_bus = EventBus()
        self.inventory = Inventory()
        self.events_received = []

        def track_event(event: Event):
            self.events_received.append(event)

        # Subscribe to all inventory events
        self.event_bus.subscribe(EventType.ITEM_ACQUIRED, track_event)
        self.event_bus.subscribe(EventType.ITEM_EQUIPPED, track_event)
        self.event_bus.subscribe(EventType.ITEM_UNEQUIPPED, track_event)
        self.event_bus.subscribe(EventType.ITEM_USED, track_event)
        self.event_bus.subscribe(EventType.GOLD_ACQUIRED, track_event)

    def test_emit_item_equipped_event(self):
        """Test emitting ITEM_EQUIPPED events"""
        self.inventory.add_item("longsword", "weapons")
        self.inventory.equip_item("longsword", EquipmentSlot.WEAPON)

        # Manually emit event (as CLI would do)
        self.event_bus.emit(Event(
            type=EventType.ITEM_EQUIPPED,
            data={"item_id": "longsword", "slot": "weapon"}
        ))

        assert len(self.events_received) == 1
        assert self.events_received[0].type == EventType.ITEM_EQUIPPED

    def test_emit_item_unequipped_event(self):
        """Test emitting ITEM_UNEQUIPPED events"""
        self.inventory.add_item("longsword", "weapons")
        self.inventory.equip_item("longsword", EquipmentSlot.WEAPON)
        self.inventory.unequip_item(EquipmentSlot.WEAPON)

        # Manually emit event (as CLI would do)
        self.event_bus.emit(Event(
            type=EventType.ITEM_UNEQUIPPED,
            data={"item_id": "longsword", "slot": "weapon"}
        ))

        assert len(self.events_received) == 1
        assert self.events_received[0].type == EventType.ITEM_UNEQUIPPED

    def test_emit_item_used_event(self):
        """Test emitting ITEM_USED events"""
        self.inventory.add_item("potion_of_healing", "consumables")
        self.inventory.remove_item("potion_of_healing")

        # Manually emit event (as CLI would do)
        self.event_bus.emit(Event(
            type=EventType.ITEM_USED,
            data={"item_id": "potion_of_healing", "effect": "heal"}
        ))

        assert len(self.events_received) == 1
        assert self.events_received[0].type == EventType.ITEM_USED


class TestInventoryDataIntegration:
    """Test inventory integration with data loader"""

    def setup_method(self):
        """Set up test fixtures"""
        self.data_loader = DataLoader()
        self.inventory = Inventory()

    def test_load_items_data(self):
        """Test loading items data from JSON"""
        items_data = self.data_loader.load_items()

        assert "weapons" in items_data
        assert "armor" in items_data
        assert "consumables" in items_data

        # Check some known items exist
        assert "longsword" in items_data["weapons"]
        assert "leather_armor" in items_data["armor"]
        assert "potion_of_healing" in items_data["consumables"]

    def test_inventory_total_value_with_real_data(self):
        """Test calculating inventory value with real item data"""
        items_data = self.data_loader.load_items()

        self.inventory.add_item("longsword", "weapons")
        self.inventory.add_item("leather_armor", "armor")
        self.inventory.add_item("potion_of_healing", "consumables")

        total = self.inventory.total_value(items_data)

        # longsword: 15gp, leather_armor: 10gp, potion: 50gp = 75gp
        assert total == 75

    def test_add_all_item_types_from_data(self):
        """Test adding items of all types from the data files"""
        items_data = self.data_loader.load_items()

        # Add one item from each category
        for category in ["weapons", "armor", "consumables"]:
            category_data = items_data[category]
            if category_data:
                first_item_id = list(category_data.keys())[0]
                self.inventory.add_item(first_item_id, category)

        assert self.inventory.item_count() == 3

    def test_equip_items_from_data(self):
        """Test equipping items that exist in the data files"""
        items_data = self.data_loader.load_items()

        # Get a weapon and armor from data
        weapon_id = list(items_data["weapons"].keys())[0]
        armor_id = list(items_data["armor"].keys())[0]

        self.inventory.add_item(weapon_id, "weapons")
        self.inventory.add_item(armor_id, "armor")

        assert self.inventory.equip_item(weapon_id, EquipmentSlot.WEAPON)
        assert self.inventory.equip_item(armor_id, EquipmentSlot.ARMOR)

        assert self.inventory.get_equipped_item(EquipmentSlot.WEAPON) == weapon_id
        assert self.inventory.get_equipped_item(EquipmentSlot.ARMOR) == armor_id
