# ABOUTME: Unit tests for the reset system
# ABOUTME: Tests dungeon reset, party preservation, and campaign restart functionality

import pytest
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.party import Party
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus, EventType


class TestResetSystem:
    """Test the reset system functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.event_bus = EventBus()
        self.loader = DataLoader()
        self.dice_roller = DiceRoller()

        # Create test characters
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=15,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        self.character1 = Character(
            name="Thorin",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16
        )

        abilities2 = Abilities(
            strength=10,
            dexterity=16,
            constitution=12,
            intelligence=14,
            wisdom=13,
            charisma=12
        )
        self.character2 = Character(
            name="Gandalf",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities2,
            max_hp=10,
            ac=12
        )

        # Create party
        self.party = Party(characters=[self.character1, self.character2])

        self.game_state = GameState(
            party=self.party,
            dungeon_name="test_dungeon",
            event_bus=self.event_bus,
            data_loader=self.loader,
            dice_roller=self.dice_roller
        )

    def test_reset_dungeon_restores_initial_state(self):
        """Test that reset_dungeon restores dungeon to initial state"""
        # Move around and make changes
        initial_room = self.game_state.current_room_id
        initial_start_room = self.game_state.dungeon["start_room"]

        current_room = self.game_state.get_current_room()
        if current_room["exits"]:
            direction = list(current_room["exits"].keys())[0]
            self.game_state.move(direction)

        # Mark a room as searched
        self.game_state.get_current_room()["searched"] = True
        self.game_state.action_history.append("test action")

        # Reset dungeon
        self.game_state.reset_dungeon()

        # Verify reset state
        assert self.game_state.current_room_id == initial_start_room
        assert self.game_state.current_room_id == initial_room
        assert not self.game_state.in_combat
        assert self.game_state.active_enemies == []
        assert self.game_state.action_history == []

    def test_reset_clears_action_history(self):
        """Test that reset clears all action history"""
        self.game_state.action_history = ["action 1", "action 2", "action 3"]
        assert len(self.game_state.action_history) == 3

        self.game_state.reset_dungeon()

        assert self.game_state.action_history == []
        assert len(self.game_state.action_history) == 0

    def test_reset_clears_combat_state(self):
        """Test that reset clears combat state"""
        # Simulate combat state
        self.game_state.in_combat = True
        self.game_state.initiative_tracker = object()  # Mock tracker
        self.game_state.active_enemies = [object(), object()]

        self.game_state.reset_dungeon()

        assert not self.game_state.in_combat
        assert self.game_state.initiative_tracker is None
        assert self.game_state.active_enemies == []

    def test_reset_preserves_party_data(self):
        """Test that reset preserves party data"""
        # Modify party data
        original_xp = 100
        self.character1.xp = original_xp
        self.character1.level = 3

        original_gold = self.character1.inventory.currency.gold
        self.character1.inventory.add_gold(50)

        # Reset
        self.game_state.reset_dungeon()

        # Verify party data is preserved
        assert len(self.game_state.party.characters) == 2
        assert self.character1.xp == original_xp
        assert self.character1.level == 3
        assert self.character1.inventory.currency.gold == original_gold + 50

    def test_reset_preserves_character_equipment(self):
        """Test that reset preserves equipped items"""
        # Add items to inventory and equip them
        self.character1.inventory.add_item("longsword", "weapons")
        from dnd_engine.systems.inventory import EquipmentSlot
        self.character1.inventory.equip_item("longsword", EquipmentSlot.WEAPON)

        # Reset
        self.game_state.reset_dungeon()

        # Verify equipment is preserved
        equipped = self.character1.inventory.get_equipped_item(EquipmentSlot.WEAPON)
        assert equipped == "longsword"

    def test_reset_party_hp_heals_all_characters(self):
        """Test that reset_party_hp heals all characters to max HP"""
        # Damage characters
        self.character1.current_hp = 5
        self.character2.current_hp = 3

        self.game_state.reset_party_hp()

        assert self.character1.current_hp == self.character1.max_hp
        assert self.character2.current_hp == self.character2.max_hp

    def test_reset_party_conditions_clears_conditions(self):
        """Test that reset_party_conditions clears all conditions"""
        # Add conditions
        self.character1.add_condition("poisoned")
        self.character1.add_condition("stunned")
        self.character2.add_condition("paralyzed")

        assert len(self.character1.conditions) == 2
        assert len(self.character2.conditions) == 1

        self.game_state.reset_party_conditions()

        assert len(self.character1.conditions) == 0
        assert len(self.character2.conditions) == 0

    def test_reset_emits_reset_started_event(self):
        """Test that reset emits RESET_STARTED event"""
        events_received = []

        def handler(event):
            events_received.append(event)

        self.event_bus.subscribe(EventType.RESET_STARTED, handler)
        self.game_state.reset_dungeon()

        assert len(events_received) == 1
        assert events_received[0].type == EventType.RESET_STARTED
        assert events_received[0].data["old_dungeon"] == "test_dungeon"

    def test_reset_emits_reset_complete_event(self):
        """Test that reset emits RESET_COMPLETE event"""
        events_received = []

        def handler(event):
            events_received.append(event)

        self.event_bus.subscribe(EventType.RESET_COMPLETE, handler)
        self.game_state.reset_dungeon()

        assert len(events_received) == 1
        assert events_received[0].type == EventType.RESET_COMPLETE
        assert events_received[0].data["dungeon"] == "test_dungeon"
        assert "current_room" in events_received[0].data

    def test_reset_to_different_dungeon(self):
        """Test resetting to a different dungeon (with mocking)"""
        from unittest.mock import patch, MagicMock

        original_dungeon = self.game_state.dungeon_name

        # Mock the data loader to return a different dungeon
        mock_dungeon = {
            "name": "Dragon Lair",
            "start_room": "dragon_throne",
            "rooms": {
                "dragon_throne": {
                    "name": "Dragon Throne",
                    "description": "A grand throne room",
                    "enemies": [],
                    "items": [],
                    "exits": {},
                    "searchable": False,
                    "searched": False
                }
            }
        }

        with patch.object(self.loader, 'load_dungeon', return_value=mock_dungeon):
            self.game_state.reset_dungeon("dragon_lair")

        # Verify dungeon changed
        assert self.game_state.dungeon_name == "dragon_lair"
        # Current room should be the start room of the new dungeon
        assert self.game_state.current_room_id == "dragon_throne"

    def test_reset_to_different_dungeon_preserves_party(self):
        """Test that switching dungeons preserves party data"""
        from unittest.mock import patch, MagicMock

        self.character1.level = 5
        self.character1.xp = 500

        # Mock the data loader to return a different dungeon
        mock_dungeon = {
            "name": "Dragon Lair",
            "start_room": "dragon_throne",
            "rooms": {
                "dragon_throne": {
                    "name": "Dragon Throne",
                    "description": "A grand throne room",
                    "enemies": [],
                    "items": [],
                    "exits": {},
                    "searchable": False,
                    "searched": False
                }
            }
        }

        with patch.object(self.loader, 'load_dungeon', return_value=mock_dungeon):
            self.game_state.reset_dungeon("dragon_lair")

        # Verify party data preserved
        assert self.character1.level == 5
        assert self.character1.xp == 500
        assert len(self.game_state.party.characters) == 2

    def test_reset_dungeon_preserves_character_names(self):
        """Test that reset preserves character names"""
        original_names = [c.name for c in self.game_state.party.characters]

        self.game_state.reset_dungeon()

        new_names = [c.name for c in self.game_state.party.characters]
        assert original_names == new_names

    def test_reset_multiple_times_is_idempotent(self):
        """Test that multiple resets work correctly"""
        # First reset
        self.game_state.reset_dungeon()
        first_room = self.game_state.current_room_id

        # Move around
        current = self.game_state.get_current_room()
        if current["exits"]:
            direction = list(current["exits"].keys())[0]
            self.game_state.move(direction)

        # Second reset
        self.game_state.reset_dungeon()
        second_room = self.game_state.current_room_id

        # Should be at start room again
        assert first_room == second_room
        assert self.game_state.current_room_id == self.game_state.dungeon["start_room"]

    def test_reset_with_dungeon_switching_events(self):
        """Test events when switching dungeons during reset"""
        from unittest.mock import patch

        events_received = []

        def handler(event):
            events_received.append(event)

        self.event_bus.subscribe(EventType.RESET_STARTED, handler)
        self.event_bus.subscribe(EventType.RESET_COMPLETE, handler)

        # Mock the data loader to return a different dungeon
        mock_dungeon = {
            "name": "Dragon Lair",
            "start_room": "dragon_throne",
            "rooms": {
                "dragon_throne": {
                    "name": "Dragon Throne",
                    "description": "A grand throne room",
                    "enemies": [],
                    "items": [],
                    "exits": {},
                    "searchable": False,
                    "searched": False
                }
            }
        }

        with patch.object(self.loader, 'load_dungeon', return_value=mock_dungeon):
            self.game_state.reset_dungeon("dragon_lair")

        assert len(events_received) == 2
        assert events_received[0].type == EventType.RESET_STARTED
        assert events_received[0].data["new_dungeon"] == "dragon_lair"
        assert events_received[1].type == EventType.RESET_COMPLETE

    def test_reset_preserves_all_party_members(self):
        """Test that all party members are preserved after reset"""
        original_count = len(self.game_state.party.characters)

        self.game_state.reset_dungeon()

        assert len(self.game_state.party.characters) == original_count
        assert self.character1 in self.game_state.party.characters
        assert self.character2 in self.game_state.party.characters
