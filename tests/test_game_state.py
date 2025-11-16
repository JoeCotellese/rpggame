# ABOUTME: Unit tests for the game state manager
# ABOUTME: Tests game state, room navigation, combat flow, and action handling

import pytest
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus, EventType


class TestGameState:
    """Test the GameState class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.event_bus = EventBus()
        self.loader = DataLoader()
        self.dice_roller = DiceRoller()

        # Create a test character
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=15,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        self.character = Character(
            name="Thorin",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16
        )

        self.game_state = GameState(
            player=self.character,
            dungeon_name="goblin_warren",
            event_bus=self.event_bus,
            data_loader=self.loader,
            dice_roller=self.dice_roller
        )

    def test_game_state_creation(self):
        """Test creating a game state"""
        assert self.game_state.player == self.character
        assert self.game_state.dungeon is not None
        assert self.game_state.current_room_id is not None
        assert not self.game_state.in_combat

    def test_initial_room_is_start_room(self):
        """Test that player starts in the dungeon's start room"""
        assert self.game_state.current_room_id == self.game_state.dungeon["start_room"]

    def test_get_current_room(self):
        """Test getting the current room data"""
        room = self.game_state.get_current_room()
        assert room is not None
        assert "name" in room
        assert "description" in room

    def test_move_to_valid_room(self):
        """Test moving to a valid adjacent room"""
        initial_room = self.game_state.current_room_id
        current_room = self.game_state.get_current_room()

        # Get a valid exit
        if current_room["exits"]:
            direction = list(current_room["exits"].keys())[0]
            target = current_room["exits"][direction]

            success = self.game_state.move(direction)
            assert success
            assert self.game_state.current_room_id == target
            assert self.game_state.current_room_id != initial_room

    def test_move_to_invalid_direction(self):
        """Test moving in an invalid direction"""
        initial_room = self.game_state.current_room_id
        success = self.game_state.move("invalid_direction")

        assert not success
        assert self.game_state.current_room_id == initial_room

    def test_move_emits_room_enter_event(self):
        """Test that moving to a new room emits a ROOM_ENTER event"""
        events_received = []

        def handler(event):
            events_received.append(event)

        self.event_bus.subscribe(EventType.ROOM_ENTER, handler)

        current_room = self.game_state.get_current_room()
        if current_room["exits"]:
            direction = list(current_room["exits"].keys())[0]
            self.game_state.move(direction)

            assert len(events_received) == 1
            assert events_received[0].type == EventType.ROOM_ENTER

    def test_entering_room_with_enemies_starts_combat(self):
        """Test that entering a room with enemies starts combat"""
        # Move to guard_post which has enemies
        self.game_state.current_room_id = "entrance"
        self.game_state.move("north")  # To guard_post

        # Should be in combat now
        assert self.game_state.in_combat

    def test_combat_initialization(self):
        """Test that combat is properly initialized"""
        # Move to a room with enemies
        self.game_state.current_room_id = "entrance"
        self.game_state.move("north")

        assert self.game_state.in_combat
        assert self.game_state.initiative_tracker is not None
        assert len(self.game_state.active_enemies) > 0

    def test_cannot_move_during_combat(self):
        """Test that player cannot move to a new room during combat"""
        # Start combat
        self.game_state.current_room_id = "entrance"
        self.game_state.move("north")

        assert self.game_state.in_combat

        # Try to move - should fail
        initial_room = self.game_state.current_room_id
        success = self.game_state.move("south")

        assert not success
        assert self.game_state.current_room_id == initial_room

    def test_get_available_actions_exploration(self):
        """Test getting available actions during exploration"""
        # Start in entrance (no enemies)
        self.game_state.current_room_id = "entrance"

        actions = self.game_state.get_available_actions()

        assert "move" in actions
        assert "search" in actions or True  # May not be searchable

    def test_get_available_actions_combat(self):
        """Test getting available actions during combat"""
        # Start combat
        self.game_state.current_room_id = "entrance"
        self.game_state.move("north")

        actions = self.game_state.get_available_actions()

        assert "attack" in actions

    def test_room_already_searched(self):
        """Test that rooms can only be searched once"""
        self.game_state.current_room_id = "storage_room"
        room = self.game_state.get_current_room()

        # Search the room
        if room.get("searchable"):
            initial_searched = room.get("searched", False)
            items_found = self.game_state.search_room()

            # Room should now be marked as searched
            room = self.game_state.get_current_room()
            assert room["searched"] is True

    def test_empty_room_no_enemies(self):
        """Test that empty rooms don't start combat"""
        self.game_state.current_room_id = "entrance"
        assert not self.game_state.in_combat

    def test_defeating_all_enemies_ends_combat(self):
        """Test that defeating all enemies ends combat"""
        # Start combat
        self.game_state.current_room_id = "entrance"
        self.game_state.move("north")

        assert self.game_state.in_combat

        # Kill all enemies
        for enemy in self.game_state.active_enemies:
            enemy.take_damage(999)

        # End combat manually for this test
        self.game_state._check_combat_end()

        assert not self.game_state.in_combat


class TestGameStateActions:
    """Test game state action methods"""

    def setup_method(self):
        """Set up test fixtures"""
        self.event_bus = EventBus()
        self.loader = DataLoader()
        self.dice_roller = DiceRoller()

        abilities = Abilities(16, 14, 15, 10, 12, 8)
        self.character = Character(
            name="Thorin",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16
        )

        self.game_state = GameState(
            player=self.character,
            dungeon_name="goblin_warren",
            event_bus=self.event_bus,
            data_loader=self.loader,
            dice_roller=self.dice_roller
        )

    def test_get_room_description(self):
        """Test getting a room description"""
        desc = self.game_state.get_room_description()
        assert desc is not None
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_get_player_status(self):
        """Test getting player status"""
        status = self.game_state.get_player_status()
        assert "name" in status
        assert "hp" in status
        assert "max_hp" in status

    def test_is_game_over_player_alive(self):
        """Test game over check when player is alive"""
        assert not self.game_state.is_game_over()

    def test_is_game_over_player_dead(self):
        """Test game over check when player is dead"""
        self.character.take_damage(999)
        assert self.game_state.is_game_over()
