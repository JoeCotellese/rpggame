# ABOUTME: Unit tests for movement controller and movement state
# ABOUTME: Tests movement, collision, door interaction, and combat movement limits

import pytest

from dnd_engine.spatial import (
    Position,
    Direction,
    TileMap,
    TileType,
    Tile,
    MovementController,
    MovementMode,
    MovementState,
    key_to_direction,
    create_map_from_string,
)
from dnd_engine.utils.events import EventBus


class TestMovementState:
    """Tests for MovementState class."""

    def test_default_speed(self):
        """Test default movement speed is 30ft."""
        state = MovementState()
        assert state.speed == 30
        assert state.movement_remaining == 30

    def test_tiles_remaining(self):
        """Test tiles remaining calculation."""
        state = MovementState(speed=30)
        # 30ft / 5ft per tile = 6 tiles
        assert state.tiles_remaining == 6

    def test_can_move(self):
        """Test movement availability check."""
        state = MovementState(speed=30)
        assert state.can_move(1)
        assert state.can_move(6)
        assert not state.can_move(7)  # 7 tiles = 35ft > 30ft

    def test_use_movement(self):
        """Test using movement."""
        state = MovementState(speed=30)

        assert state.use_movement(1)  # 5ft used
        assert state.movement_used == 5
        assert state.movement_remaining == 25

        assert state.use_movement(2)  # 10ft more
        assert state.movement_used == 15
        assert state.movement_remaining == 15

    def test_use_movement_fails_when_insufficient(self):
        """Test that using too much movement fails."""
        state = MovementState(speed=10)  # Only 2 tiles

        assert state.use_movement(2)  # Use all
        assert not state.use_movement(1)  # No more left
        assert state.movement_used == 10  # Didn't increase

    def test_reset(self):
        """Test resetting movement at turn start."""
        state = MovementState(speed=30)
        state.use_movement(4)
        assert state.movement_used == 20

        state.reset()
        assert state.movement_used == 0
        assert state.movement_remaining == 30


class TestMovementController:
    """Tests for MovementController class."""

    @pytest.fixture
    def simple_map(self):
        """Create a simple test map."""
        result = create_map_from_string("""
#######
#.....#
#.....#
#.....#
#######
""")
        result.tile_map.reveal_all()
        return result.tile_map

    @pytest.fixture
    def map_with_door(self):
        """Create a map with a door."""
        result = create_map_from_string("""
#######
#..+..#
#.....#
#######
""")
        result.tile_map.reveal_all()
        return result.tile_map

    def test_basic_movement(self, simple_map):
        """Test basic movement in a direction."""
        simple_map.add_entity("player", Position(3, 2), display_char="@")
        controller = MovementController(tile_map=simple_map)

        result = controller.move("player", Direction.NORTH)

        assert result.success
        assert result.new_position == Position(3, 1)
        assert simple_map.get_entity_position("player") == Position(3, 1)

    def test_movement_blocked_by_wall(self, simple_map):
        """Test movement blocked by wall."""
        simple_map.add_entity("player", Position(1, 1), display_char="@")
        controller = MovementController(tile_map=simple_map)

        result = controller.move("player", Direction.NORTH)

        assert not result.success
        assert result.blocked_by == "wall"
        assert simple_map.get_entity_position("player") == Position(1, 1)

    def test_movement_blocked_by_entity(self, simple_map):
        """Test movement blocked by another entity."""
        simple_map.add_entity("player", Position(3, 2), display_char="@")
        simple_map.add_entity("goblin", Position(3, 1), display_char="G")
        controller = MovementController(tile_map=simple_map)

        result = controller.move("player", Direction.NORTH)

        assert not result.success
        assert result.blocked_by == "entity"

    def test_diagonal_movement(self, simple_map):
        """Test diagonal movement."""
        simple_map.add_entity("player", Position(3, 2), display_char="@")
        controller = MovementController(tile_map=simple_map)

        result = controller.move("player", Direction.NORTHEAST)

        assert result.success
        assert result.new_position == Position(4, 1)

    def test_diagonal_movement_disabled(self, simple_map):
        """Test diagonal movement can be disabled."""
        simple_map.add_entity("player", Position(3, 2), display_char="@")
        controller = MovementController(tile_map=simple_map)

        result = controller.move("player", Direction.NORTHEAST, allow_diagonal=False)

        assert not result.success
        assert result.blocked_by == "diagonal"

    def test_get_valid_moves(self, simple_map):
        """Test getting valid movement directions."""
        simple_map.add_entity("player", Position(3, 2), display_char="@")
        controller = MovementController(tile_map=simple_map)

        valid = controller.get_valid_moves("player")

        # In middle of room, all directions should be valid
        assert Direction.NORTH in valid
        assert Direction.SOUTH in valid
        assert Direction.EAST in valid
        assert Direction.WEST in valid

    def test_get_valid_moves_near_wall(self):
        """Test valid moves near a wall."""
        result = create_map_from_string("""
####
#..#
####
""")
        result.tile_map.reveal_all()
        result.tile_map.add_entity("player", Position(1, 1), display_char="@")

        controller = MovementController(tile_map=result.tile_map)
        valid = controller.get_valid_moves("player")

        assert Direction.EAST in valid
        assert Direction.WEST not in valid  # Wall
        assert Direction.NORTH not in valid  # Wall
        assert Direction.SOUTH not in valid  # Wall

    def test_combat_movement_limit(self, simple_map):
        """Test movement is limited in combat mode."""
        simple_map.add_entity("player", Position(3, 2), display_char="@")
        controller = MovementController(
            tile_map=simple_map,
            mode=MovementMode.COMBAT,
        )
        controller.set_speed("player", 15)  # 3 tiles

        # Move 3 times (15ft)
        assert controller.move("player", Direction.EAST).success
        assert controller.move("player", Direction.EAST).success
        assert controller.move("player", Direction.SOUTH).success

        # 4th move should fail
        result = controller.move("player", Direction.SOUTH)
        assert not result.success
        assert result.blocked_by == "speed"

    def test_combat_movement_reset(self, simple_map):
        """Test movement resets at turn start."""
        simple_map.add_entity("player", Position(3, 2), display_char="@")
        controller = MovementController(
            tile_map=simple_map,
            mode=MovementMode.COMBAT,
        )
        controller.set_speed("player", 10)  # 2 tiles

        # Use all movement
        controller.move("player", Direction.EAST)
        controller.move("player", Direction.EAST)

        # Should fail
        assert not controller.move("player", Direction.EAST).success

        # Reset
        controller.reset_movement("player")

        # Should work again
        assert controller.move("player", Direction.SOUTH).success

    def test_exploration_mode_unlimited(self, simple_map):
        """Test exploration mode has unlimited movement."""
        simple_map.add_entity("player", Position(1, 1), display_char="@")
        controller = MovementController(
            tile_map=simple_map,
            mode=MovementMode.EXPLORATION,
        )

        # Move many times - should all succeed (not blocked by speed)
        for _ in range(10):
            # Move back and forth
            controller.move("player", Direction.EAST)
            controller.move("player", Direction.WEST)

    def test_door_interaction_open(self, map_with_door):
        """Test opening a closed door."""
        map_with_door.add_entity("player", Position(2, 1), display_char="@")
        controller = MovementController(tile_map=map_with_door)

        door_pos = Position(3, 1)
        success = controller.interact_with_door("player", door_pos)

        assert success
        assert map_with_door.get_tile(door_pos).tile_type == TileType.DOOR_OPEN

    def test_door_interaction_close(self, map_with_door):
        """Test closing an open door."""
        map_with_door.add_entity("player", Position(2, 1), display_char="@")
        controller = MovementController(tile_map=map_with_door)

        door_pos = Position(3, 1)

        # Open first
        controller.interact_with_door("player", door_pos)
        assert map_with_door.get_tile(door_pos).tile_type == TileType.DOOR_OPEN

        # Close
        controller.interact_with_door("player", door_pos)
        assert map_with_door.get_tile(door_pos).tile_type == TileType.DOOR_CLOSED

    def test_door_interaction_not_adjacent(self, map_with_door):
        """Test can't interact with non-adjacent door."""
        map_with_door.add_entity("player", Position(1, 2), display_char="@")
        controller = MovementController(tile_map=map_with_door)

        door_pos = Position(3, 1)  # Not adjacent
        success = controller.interact_with_door("player", door_pos)

        assert not success

    def test_open_adjacent_door(self, map_with_door):
        """Test opening nearest adjacent door."""
        map_with_door.add_entity("player", Position(2, 1), display_char="@")
        controller = MovementController(tile_map=map_with_door)

        opened_pos = controller.open_adjacent_door("player")

        assert opened_pos == Position(3, 1)
        assert map_with_door.get_tile(opened_pos).tile_type == TileType.DOOR_OPEN

    def test_event_emission(self, simple_map):
        """Test that movement emits events."""
        event_bus = EventBus()
        events_received = []

        def on_event(event):
            events_received.append(event)

        from dnd_engine.utils.events import EventType
        event_bus.subscribe(EventType.ENTITY_MOVED, on_event)

        simple_map.add_entity("player", Position(3, 2), display_char="@")
        controller = MovementController(tile_map=simple_map, event_bus=event_bus)

        controller.move("player", Direction.NORTH)

        assert len(events_received) == 1
        assert events_received[0].data["entity_id"] == "player"
        assert events_received[0].data["old_position"] == {"x": 3, "y": 2}
        assert events_received[0].data["new_position"] == {"x": 3, "y": 1}

    def test_move_callback(self, simple_map):
        """Test move callback is called."""
        simple_map.add_entity("player", Position(3, 2), display_char="@")

        callback_data = []

        def on_move(entity_id, old_pos, new_pos):
            callback_data.append((entity_id, old_pos, new_pos))

        controller = MovementController(tile_map=simple_map, on_move=on_move)
        controller.move("player", Direction.NORTH)

        assert len(callback_data) == 1
        assert callback_data[0][0] == "player"
        assert callback_data[0][1] == Position(3, 2)
        assert callback_data[0][2] == Position(3, 1)

    def test_blocked_callback(self, simple_map):
        """Test blocked callback is called."""
        simple_map.add_entity("player", Position(1, 1), display_char="@")

        callback_data = []

        def on_blocked(entity_id, target_pos, reason):
            callback_data.append((entity_id, target_pos, reason))

        controller = MovementController(tile_map=simple_map, on_blocked=on_blocked)
        controller.move("player", Direction.NORTH)  # Into wall

        assert len(callback_data) == 1
        assert callback_data[0][0] == "player"
        assert callback_data[0][2] == "wall"

    def test_move_to_adjacent(self, simple_map):
        """Test moving to specific adjacent position."""
        simple_map.add_entity("player", Position(3, 2), display_char="@")
        controller = MovementController(tile_map=simple_map)

        result = controller.move_to("player", Position(3, 1))

        assert result.success
        assert simple_map.get_entity_position("player") == Position(3, 1)

    def test_move_to_non_adjacent_fails(self, simple_map):
        """Test moving to non-adjacent position fails."""
        simple_map.add_entity("player", Position(3, 2), display_char="@")
        controller = MovementController(tile_map=simple_map)

        result = controller.move_to("player", Position(5, 2))

        assert not result.success
        assert result.blocked_by == "distance"


class TestKeyToDirection:
    """Tests for key_to_direction function."""

    def test_wasd_keys(self):
        """Test WASD keys map to directions."""
        assert key_to_direction("w") == Direction.NORTH
        assert key_to_direction("a") == Direction.WEST
        assert key_to_direction("s") == Direction.SOUTH
        assert key_to_direction("d") == Direction.EAST

    def test_wasd_uppercase(self):
        """Test uppercase WASD works."""
        assert key_to_direction("W") == Direction.NORTH
        assert key_to_direction("A") == Direction.WEST

    def test_arrow_keys(self):
        """Test arrow key names."""
        assert key_to_direction("up") == Direction.NORTH
        assert key_to_direction("down") == Direction.SOUTH
        assert key_to_direction("left") == Direction.WEST
        assert key_to_direction("right") == Direction.EAST

    def test_vi_keys(self):
        """Test vi-style keys."""
        assert key_to_direction("h") == Direction.WEST
        assert key_to_direction("j") == Direction.SOUTH
        assert key_to_direction("k") == Direction.NORTH
        assert key_to_direction("l") == Direction.EAST

    def test_vi_diagonal(self):
        """Test vi-style diagonal keys."""
        assert key_to_direction("y") == Direction.NORTHWEST
        assert key_to_direction("u") == Direction.NORTHEAST
        assert key_to_direction("b") == Direction.SOUTHWEST
        assert key_to_direction("n") == Direction.SOUTHEAST

    def test_numpad_keys(self):
        """Test numpad keys."""
        assert key_to_direction("8") == Direction.NORTH
        assert key_to_direction("2") == Direction.SOUTH
        assert key_to_direction("4") == Direction.WEST
        assert key_to_direction("6") == Direction.EAST

    def test_unknown_key(self):
        """Test unknown key returns None."""
        assert key_to_direction("x") is None
        assert key_to_direction("z") is None
        assert key_to_direction("") is None


class TestMovementIntegration:
    """Integration tests for movement workflow."""

    def test_movement_through_room(self):
        """Test moving through a room with obstacles."""
        loaded = create_map_from_string("""
#########
#.......#
#.###...#
#.#.#...#
#.#.....#
#.......#
#########
""")
        loaded.tile_map.reveal_all()
        loaded.tile_map.add_entity("player", Position(1, 1), display_char="@")

        controller = MovementController(tile_map=loaded.tile_map)

        # Move around obstacle
        moves = [
            Direction.SOUTH,  # (1, 2)
            Direction.SOUTH,  # (1, 3)
            Direction.SOUTH,  # (1, 4)
            Direction.SOUTH,  # (1, 5)
            Direction.EAST,   # (2, 5)
            Direction.EAST,   # (3, 5)
            Direction.EAST,   # (4, 5)
            Direction.NORTH,  # (4, 4)
        ]

        for direction in moves:
            result = controller.move("player", direction)
            assert result.success, f"Failed to move {direction}"

        assert loaded.tile_map.get_entity_position("player") == Position(4, 4)

    def test_door_then_move_through(self):
        """Test opening door then moving through."""
        result = create_map_from_string("""
#####
#...#
##+##
#...#
#####
""")
        result.tile_map.reveal_all()
        result.tile_map.add_entity("player", Position(2, 1), display_char="@")

        controller = MovementController(tile_map=result.tile_map)

        # Can't move through closed door
        move_result = controller.move("player", Direction.SOUTH)
        assert not move_result.success

        # Open the door
        controller.open_adjacent_door("player")

        # Now can move through
        move_result = controller.move("player", Direction.SOUTH)
        assert move_result.success
        assert result.tile_map.get_entity_position("player") == Position(2, 2)

        # And continue
        move_result = controller.move("player", Direction.SOUTH)
        assert move_result.success
        assert result.tile_map.get_entity_position("player") == Position(2, 3)
