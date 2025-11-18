# ABOUTME: Unit tests for item usage mechanics
# ABOUTME: Tests inventory.use_item() and item effect application

import pytest
from dnd_engine.systems.inventory import Inventory
from dnd_engine.systems.item_effects import apply_item_effect, ItemEffectResult
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.core.dice import DiceRoller


class TestInventoryUseItem:
    """Test the Inventory.use_item() method"""

    def test_use_item_success(self):
        """Test successfully using an item from inventory"""
        inventory = Inventory()
        inventory.add_item("potion_of_healing", "consumables", quantity=2)

        items_data = {
            "consumables": {
                "potion_of_healing": {
                    "name": "Potion of Healing",
                    "effect_type": "healing",
                    "healing": "2d4+2"
                }
            }
        }

        success, item_info = inventory.use_item("potion_of_healing", items_data)

        assert success is True
        assert item_info is not None
        assert item_info["name"] == "Potion of Healing"
        assert item_info["effect_type"] == "healing"
        assert item_info["healing"] == "2d4+2"
        # Should have 1 potion left
        assert inventory.get_item_quantity("potion_of_healing") == 1

    def test_use_item_removes_when_quantity_reaches_zero(self):
        """Test that item is removed from inventory when last one is used"""
        inventory = Inventory()
        inventory.add_item("potion_of_healing", "consumables", quantity=1)

        items_data = {
            "consumables": {
                "potion_of_healing": {
                    "name": "Potion of Healing",
                    "effect_type": "healing",
                    "healing": "2d4+2"
                }
            }
        }

        success, item_info = inventory.use_item("potion_of_healing", items_data)

        assert success is True
        # Item should be completely removed
        assert not inventory.has_item("potion_of_healing")
        assert inventory.get_item_quantity("potion_of_healing") == 0

    def test_use_item_not_in_inventory(self):
        """Test using an item that's not in inventory returns False"""
        inventory = Inventory()
        items_data = {
            "consumables": {
                "potion_of_healing": {
                    "name": "Potion of Healing",
                    "effect_type": "healing",
                    "healing": "2d4+2"
                }
            }
        }

        success, item_info = inventory.use_item("potion_of_healing", items_data)

        assert success is False
        assert item_info is None

    def test_use_item_not_in_data(self):
        """Test using an item that's in inventory but not in data returns False"""
        inventory = Inventory()
        inventory.add_item("mysterious_potion", "consumables", quantity=1)

        items_data = {
            "consumables": {}  # Empty - item doesn't exist in data
        }

        success, item_info = inventory.use_item("mysterious_potion", items_data)

        assert success is False
        assert item_info is None
        # Item should not be removed from inventory if data lookup failed
        assert inventory.has_item("mysterious_potion")


class TestItemEffectApplication:
    """Test applying item effects to creatures"""

    def test_apply_healing_effect(self):
        """Test applying a healing effect to a damaged creature"""
        # Create a damaged creature
        abilities = Abilities(10, 10, 10, 10, 10, 10)
        creature = Creature("Test Hero", max_hp=20, ac=15, abilities=abilities, current_hp=10)

        item_info = {
            "name": "Potion of Healing",
            "effect_type": "healing",
            "healing": "2d4+2"  # Min 4, max 10
        }

        dice_roller = DiceRoller()
        result = apply_item_effect(item_info, creature, dice_roller)

        assert result.success is True
        assert result.effect_type == "healing"
        assert result.amount > 0
        assert result.dice_notation == "2d4+2"
        assert creature.current_hp > 10  # Should have healed
        assert creature.current_hp <= 20  # Should not exceed max HP

    def test_apply_healing_at_full_hp(self):
        """Test applying healing when creature is already at full HP"""
        abilities = Abilities(10, 10, 10, 10, 10, 10)
        creature = Creature("Test Hero", max_hp=20, ac=15, abilities=abilities, current_hp=20)

        item_info = {
            "name": "Potion of Healing",
            "effect_type": "healing",
            "healing": "2d4+2"
        }

        dice_roller = DiceRoller()
        result = apply_item_effect(item_info, creature, dice_roller)

        assert result.success is False  # No healing actually applied
        assert result.amount == 0  # No HP gained
        assert creature.current_hp == 20  # Still at max
        assert "full health" in result.message.lower()

    def test_apply_healing_caps_at_max_hp(self):
        """Test that healing cannot exceed max HP"""
        abilities = Abilities(10, 10, 10, 10, 10, 10)
        creature = Creature("Test Hero", max_hp=20, ac=15, abilities=abilities, current_hp=19)

        item_info = {
            "name": "Potion of Greater Healing",
            "effect_type": "healing",
            "healing": "4d4+4"  # Will definitely heal more than 1 HP
        }

        dice_roller = DiceRoller()
        result = apply_item_effect(item_info, creature, dice_roller)

        # Should heal, but only 1 HP
        assert result.success is True
        assert result.amount == 1  # Can only heal 1 HP to reach max
        assert creature.current_hp == 20  # At max HP

    def test_apply_healing_to_dead_creature(self):
        """Test that healing doesn't work on dead creatures"""
        abilities = Abilities(10, 10, 10, 10, 10, 10)
        creature = Creature("Dead Hero", max_hp=20, ac=15, abilities=abilities, current_hp=0)

        assert not creature.is_alive

        item_info = {
            "name": "Potion of Healing",
            "effect_type": "healing",
            "healing": "2d4+2"
        }

        dice_roller = DiceRoller()
        result = apply_item_effect(item_info, creature, dice_roller)

        assert result.success is False
        assert result.amount == 0
        assert creature.current_hp == 0  # Still dead
        assert "dead" in result.message.lower()

    def test_apply_unknown_effect(self):
        """Test applying an unknown/unimplemented effect type"""
        abilities = Abilities(10, 10, 10, 10, 10, 10)
        creature = Creature("Test Hero", max_hp=20, ac=15, abilities=abilities)

        item_info = {
            "name": "Mysterious Potion",
            "effect_type": "levitation",  # Not implemented
        }

        dice_roller = DiceRoller()
        result = apply_item_effect(item_info, creature, dice_roller)

        assert result.success is False
        assert "no implemented effect" in result.message.lower()

    def test_healing_dice_variation(self):
        """Test that healing values vary appropriately based on dice"""
        abilities = Abilities(10, 10, 10, 10, 10, 10)

        # Test different healing potions
        test_cases = [
            ("2d4+2", 4, 10),   # Potion of Healing: min 4, max 10
            ("4d4+4", 8, 20),   # Greater: min 8, max 20
            ("8d4+8", 16, 40),  # Superior: min 16, max 40
            ("10d4+20", 30, 60) # Supreme: min 30, max 60
        ]

        for dice_notation, min_val, max_val in test_cases:
            creature = Creature("Test", max_hp=100, ac=15, abilities=abilities, current_hp=10)
            item_info = {
                "name": "Test Potion",
                "effect_type": "healing",
                "healing": dice_notation
            }

            dice_roller = DiceRoller()
            result = apply_item_effect(item_info, creature, dice_roller)

            assert result.success is True
            assert result.amount >= min_val, f"{dice_notation} healed less than minimum"
            assert result.amount <= max_val, f"{dice_notation} healed more than maximum"


class TestItemEffectEvents:
    """Test that item effects emit appropriate events"""

    def test_healing_emits_event(self):
        """Test that healing emits a HEALING_DONE event"""
        from dnd_engine.utils.events import EventBus, EventType

        abilities = Abilities(10, 10, 10, 10, 10, 10)
        creature = Creature("Test Hero", max_hp=20, ac=15, abilities=abilities, current_hp=10)

        item_info = {
            "name": "Potion of Healing",
            "effect_type": "healing",
            "healing": "2d4+2"
        }

        event_bus = EventBus()
        events_received = []

        def capture_event(event):
            events_received.append(event)

        event_bus.subscribe(EventType.HEALING_DONE, capture_event)

        dice_roller = DiceRoller()
        result = apply_item_effect(item_info, creature, dice_roller, event_bus)

        # Should have emitted one event
        assert len(events_received) == 1

        event = events_received[0]
        assert event.type == EventType.HEALING_DONE
        assert event.data["target"] == "Test Hero"
        assert event.data["item"] == "Potion of Healing"
        assert event.data["healing_dice"] == "2d4+2"
        assert event.data["healing_rolled"] > 0
        assert event.data["healing_actual"] > 0

    def test_no_healing_still_emits_event(self):
        """Test that event is emitted even when no healing occurs (full HP)"""
        from dnd_engine.utils.events import EventBus, EventType

        abilities = Abilities(10, 10, 10, 10, 10, 10)
        creature = Creature("Test Hero", max_hp=20, ac=15, abilities=abilities, current_hp=20)

        item_info = {
            "name": "Potion of Healing",
            "effect_type": "healing",
            "healing": "2d4+2"
        }

        event_bus = EventBus()
        events_received = []

        def capture_event(event):
            events_received.append(event)

        event_bus.subscribe(EventType.HEALING_DONE, capture_event)

        dice_roller = DiceRoller()
        result = apply_item_effect(item_info, creature, dice_roller, event_bus)

        # Should still emit event even though no healing occurred
        assert len(events_received) == 1
        event = events_received[0]
        assert event.data["healing_actual"] == 0  # No actual healing


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
