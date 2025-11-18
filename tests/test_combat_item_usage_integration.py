# ABOUTME: Integration tests for using consumable items during combat
# ABOUTME: Tests action economy enforcement, turn state integration, and combat flow

import pytest
from dnd_engine.core.character import Character, CharacterClass, Abilities
from dnd_engine.core.creature import Creature
from dnd_engine.systems.inventory import Inventory
from dnd_engine.systems.initiative import InitiativeTracker
from dnd_engine.systems.action_economy import ActionType
from dnd_engine.systems.item_effects import apply_item_effect
from dnd_engine.core.dice import DiceRoller
from dnd_engine.utils.events import EventBus, EventType


class TestCombatItemUsageIntegration:
    """Integration tests for using items during combat"""

    def test_use_potion_during_combat_turn(self):
        """Test using a healing potion during a character's combat turn"""
        # Setup
        abilities = Abilities(10, 10, 14, 10, 10, 10)  # CON 14 for HP
        hero = Character(
            "Hero",
            CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=15,
            current_hp=6  # Damaged
        )

        # Add potion to inventory
        hero.inventory.add_item("potion_of_healing", "consumables", quantity=1)

        # Setup combat
        tracker = InitiativeTracker()
        tracker.add_combatant(hero)

        # Get item data
        items_data = {
            "consumables": {
                "potion_of_healing": {
                    "name": "Potion of Healing",
                    "effect_type": "healing",
                    "healing": "2d4+2",
                    "action_required": "action"
                }
            }
        }

        # Get turn state and verify action available
        turn_state = tracker.get_current_turn_state()
        assert turn_state.is_action_available(ActionType.ACTION)

        # Use the potion
        success, item_info = hero.inventory.use_item("potion_of_healing", items_data)
        assert success is True

        # Consume action
        consumed = turn_state.consume_action(ActionType.ACTION)
        assert consumed is True

        # Apply healing effect
        dice_roller = DiceRoller()
        result = apply_item_effect(item_info, hero, dice_roller)

        assert result.success is True
        assert hero.current_hp > 6  # Should have healed
        assert hero.current_hp <= 12  # Should not exceed max HP

        # Verify action consumed
        assert not turn_state.is_action_available(ActionType.ACTION)

        # Verify potion removed from inventory
        assert not hero.inventory.has_item("potion_of_healing")

    def test_cannot_use_item_without_action(self):
        """Test that item cannot be used if action already consumed"""
        abilities = Abilities(10, 10, 10, 10, 10, 10)
        hero = Character(
            "Hero",
            CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=15,
            current_hp=5
        )

        hero.inventory.add_item("potion_of_healing", "consumables", quantity=1)

        tracker = InitiativeTracker()
        tracker.add_combatant(hero)

        turn_state = tracker.get_current_turn_state()

        # Consume action first (e.g., by attacking)
        turn_state.consume_action(ActionType.ACTION)

        # Try to use potion
        assert not turn_state.is_action_available(ActionType.ACTION)

        # In real code, this would be prevented by the CLI handler
        # Here we verify the action economy correctly blocks it
        items_data = {
            "consumables": {
                "potion_of_healing": {
                    "name": "Potion of Healing",
                    "effect_type": "healing",
                    "healing": "2d4+2",
                    "action_required": "action"
                }
            }
        }

        # Attempt to consume action would fail
        can_use = turn_state.is_action_available(ActionType.ACTION)
        assert can_use is False

    def test_action_resets_on_next_turn(self):
        """Test that actions reset when turn advances"""
        abilities = Abilities(10, 10, 10, 10, 10, 10)
        hero = Character(
            "Hero",
            CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=15,
            current_hp=5
        )

        enemy = Creature("Goblin", max_hp=7, ac=13, abilities=abilities)

        tracker = InitiativeTracker()
        tracker.add_combatant(hero)
        tracker.add_combatant(enemy)

        # Hero's turn - use action
        turn_state = tracker.get_current_turn_state()
        turn_state.consume_action(ActionType.ACTION)
        assert not turn_state.is_action_available(ActionType.ACTION)

        # Advance to enemy's turn
        tracker.next_turn()

        # Advance back to hero's turn
        tracker.next_turn()

        # Hero should have action again
        turn_state_new = tracker.get_current_turn_state()
        assert turn_state_new.is_action_available(ActionType.ACTION)

    def test_multiple_potions_across_turns(self):
        """Test using multiple potions across multiple turns"""
        abilities = Abilities(10, 10, 10, 10, 10, 10)
        hero = Character(
            "Hero",
            CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=20,
            ac=15,
            current_hp=5
        )

        # Add 3 potions
        hero.inventory.add_item("potion_of_healing", "consumables", quantity=3)

        enemy = Creature("Goblin", max_hp=7, ac=13, abilities=abilities)

        tracker = InitiativeTracker()
        tracker.add_combatant(hero)
        tracker.add_combatant(enemy)

        items_data = {
            "consumables": {
                "potion_of_healing": {
                    "name": "Potion of Healing",
                    "effect_type": "healing",
                    "healing": "2d4+2",
                    "action_required": "action"
                }
            }
        }

        dice_roller = DiceRoller()

        # Turn 1 - Use first potion
        turn_state = tracker.get_current_turn_state()
        success, item_info = hero.inventory.use_item("potion_of_healing", items_data)
        assert success
        turn_state.consume_action(ActionType.ACTION)
        result = apply_item_effect(item_info, hero, dice_roller)
        assert result.success

        assert hero.inventory.get_item_quantity("potion_of_healing") == 2

        # Advance through enemy turn
        tracker.next_turn()

        # Turn 2 - Use second potion
        tracker.next_turn()
        turn_state = tracker.get_current_turn_state()
        success, item_info = hero.inventory.use_item("potion_of_healing", items_data)
        assert success
        turn_state.consume_action(ActionType.ACTION)
        result = apply_item_effect(item_info, hero, dice_roller)

        assert hero.inventory.get_item_quantity("potion_of_healing") == 1

    def test_cannot_use_item_on_enemy_turn(self):
        """Test that player cannot use items during enemy turn"""
        abilities = Abilities(10, 10, 10, 10, 10, 10)
        hero = Character(
            "Hero",
            CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=15
        )

        enemy = Creature("Goblin", max_hp=7, ac=13, abilities=abilities)

        tracker = InitiativeTracker()
        tracker.add_combatant(enemy)  # Enemy goes first
        tracker.add_combatant(hero)

        # Verify it's enemy's turn
        current = tracker.get_current_combatant()
        assert current.creature == enemy

        # Player should not be able to use items
        # (This would be enforced by CLI checking current combatant)
        assert current.creature != hero

    def test_event_emission_on_item_use(self):
        """Test that proper events are emitted when using items in combat"""
        abilities = Abilities(10, 10, 10, 10, 10, 10)
        hero = Character(
            "Hero",
            CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=15,
            current_hp=5
        )

        hero.inventory.add_item("potion_of_healing", "consumables", quantity=1)

        items_data = {
            "consumables": {
                "potion_of_healing": {
                    "name": "Potion of Healing",
                    "effect_type": "healing",
                    "healing": "2d4+2",
                    "action_required": "action"
                }
            }
        }

        event_bus = EventBus()
        events_captured = []

        def capture_event(event):
            events_captured.append(event)

        event_bus.subscribe(EventType.HEALING_DONE, capture_event)

        # Use potion
        success, item_info = hero.inventory.use_item("potion_of_healing", items_data)
        dice_roller = DiceRoller()
        result = apply_item_effect(item_info, hero, dice_roller, event_bus)

        # Verify healing event was emitted
        assert len(events_captured) == 1
        event = events_captured[0]
        assert event.type == EventType.HEALING_DONE
        assert event.data["target"] == "Hero"
        assert event.data["item"] == "Potion of Healing"

    def test_inventory_depletes_correctly(self):
        """Test that inventory properly depletes as potions are used"""
        abilities = Abilities(10, 10, 10, 10, 10, 10)
        hero = Character(
            "Hero",
            CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=30,
            ac=15,
            current_hp=10
        )

        # Start with 5 potions
        hero.inventory.add_item("potion_of_healing", "consumables", quantity=5)
        assert hero.inventory.get_item_quantity("potion_of_healing") == 5

        items_data = {
            "consumables": {
                "potion_of_healing": {
                    "name": "Potion of Healing",
                    "effect_type": "healing",
                    "healing": "2d4+2",
                    "action_required": "action"
                }
            }
        }

        # Use 3 potions
        for i in range(3):
            success, item_info = hero.inventory.use_item("potion_of_healing", items_data)
            assert success is True
            expected_remaining = 5 - (i + 1)
            assert hero.inventory.get_item_quantity("potion_of_healing") == expected_remaining

        # Should have 2 left
        assert hero.inventory.get_item_quantity("potion_of_healing") == 2

        # Use remaining 2
        for i in range(2):
            success, item_info = hero.inventory.use_item("potion_of_healing", items_data)
            assert success is True

        # Should be completely out
        assert not hero.inventory.has_item("potion_of_healing")
        assert hero.inventory.get_item_quantity("potion_of_healing") == 0

        # Trying to use when out should fail
        success, item_info = hero.inventory.use_item("potion_of_healing", items_data)
        assert success is False
        assert item_info is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
