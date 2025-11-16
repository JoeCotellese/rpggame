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
        """Test that searching a room adds items to player inventory"""
        # Clear enemies from guard_post to allow movement
        self.game_state.dungeon["rooms"]["guard_post"]["enemies"] = []

        # Move to storage room (has searchable items)
        self.game_state.move("north")  # to guard_post
        self.game_state.move("east")   # to storage_room

        initial_item_count = self.player.inventory.item_count()
        initial_gold = self.player.inventory.gold

        # Search the room
        items = self.game_state.search_room()

        assert len(items) > 0  # Storage room has items
        assert self.player.inventory.item_count() > initial_item_count or \
               self.player.inventory.gold > initial_gold

    def test_search_room_adds_gold(self):
        """Test that searching adds gold to inventory"""
        # Clear enemies from guard_post to allow movement
        self.game_state.dungeon["rooms"]["guard_post"]["enemies"] = []

        # Move to storage room
        self.game_state.move("north")
        self.game_state.move("east")

        assert self.player.inventory.gold == 0

        self.game_state.search_room()

        # Storage room has 25 gold
        assert self.player.inventory.gold == 25

    def test_search_room_adds_specific_items(self):
        """Test that specific items from room are added to inventory"""
        # Clear enemies from guard_post to allow movement
        self.game_state.dungeon["rooms"]["guard_post"]["enemies"] = []

        # Move to storage room (has potion_of_healing and shortsword)
        self.game_state.move("north")
        self.game_state.move("east")

        self.game_state.search_room()

        # Check that items from storage room are in inventory
        assert self.player.inventory.has_item("potion_of_healing") or \
               self.player.inventory.has_item("shortsword")

    def test_search_room_emits_item_acquired_event(self):
        """Test that searching emits ITEM_ACQUIRED events"""
        # Clear enemies from guard_post to allow movement
        self.game_state.dungeon["rooms"]["guard_post"]["enemies"] = []

        events_received = []

        def track_event(event: Event):
            events_received.append(event)

        self.event_bus.subscribe(EventType.ITEM_ACQUIRED, track_event)

        # Move to storage room and search
        self.game_state.move("north")
        self.game_state.move("east")
        self.game_state.search_room()

        # Should have received item acquired events
        assert len(events_received) > 0
        for event in events_received:
            assert event.type == EventType.ITEM_ACQUIRED
            assert "item_id" in event.data
            assert "category" in event.data

    def test_search_room_emits_gold_acquired_event(self):
        """Test that searching emits GOLD_ACQUIRED events"""
        # Clear enemies from guard_post to allow movement
        self.game_state.dungeon["rooms"]["guard_post"]["enemies"] = []

        events_received = []

        def track_event(event: Event):
            events_received.append(event)

        self.event_bus.subscribe(EventType.GOLD_ACQUIRED, track_event)

        # Move to storage room and search
        self.game_state.move("north")
        self.game_state.move("east")
        self.game_state.search_room()

        # Should have received gold acquired event
        assert len(events_received) == 1
        event = events_received[0]
        assert event.type == EventType.GOLD_ACQUIRED
        assert "amount" in event.data
        assert event.data["amount"] == 25

    def test_cannot_search_room_twice(self):
        """Test that a room can only be searched once"""
        # Clear enemies from guard_post to allow movement
        self.game_state.dungeon["rooms"]["guard_post"]["enemies"] = []

        # Move to storage room
        self.game_state.move("north")
        self.game_state.move("east")

        # First search succeeds
        items1 = self.game_state.search_room()
        assert len(items1) > 0

        # Second search returns nothing
        items2 = self.game_state.search_room()
        assert len(items2) == 0

    def test_search_non_searchable_room(self):
        """Test searching a non-searchable room returns nothing"""
        # Entrance room is not marked as searchable
        items = self.game_state.search_room()
        assert len(items) == 0

    def test_get_item_category_correctly_identifies_items(self):
        """Test that _get_item_category correctly identifies item categories"""
        assert self.game_state._get_item_category("longsword") == "weapons"
        assert self.game_state._get_item_category("chain_mail") == "armor"
        assert self.game_state._get_item_category("potion_of_healing") == "consumables"
        assert self.game_state._get_item_category("nonexistent") is None


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
