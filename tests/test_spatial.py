# ABOUTME: Unit tests for 2D dungeon crawler spatial module
# ABOUTME: Tests Position, Direction, Tile, TileType, and TileMap classes

import pytest

from dnd_engine.spatial.position import Direction, Position
from dnd_engine.spatial.tile import Tile, TileType, VisibilityState
from dnd_engine.spatial.grid import TileMap, EntityInfo, MoveResult


class TestPosition:
    """Tests for Position dataclass."""

    def test_position_creation(self):
        """Test basic position creation."""
        pos = Position(5, 10)
        assert pos.x == 5
        assert pos.y == 10

    def test_position_immutable(self):
        """Test that position is immutable (frozen dataclass)."""
        pos = Position(5, 10)
        with pytest.raises(AttributeError):
            pos.x = 6

    def test_position_addition_with_position(self):
        """Test adding two positions."""
        pos1 = Position(3, 4)
        pos2 = Position(1, 2)
        result = pos1 + pos2
        assert result == Position(4, 6)

    def test_position_addition_with_tuple(self):
        """Test adding a tuple to position."""
        pos = Position(3, 4)
        result = pos + (1, -1)
        assert result == Position(4, 3)

    def test_position_addition_with_direction(self):
        """Test adding a direction to position."""
        pos = Position(5, 5)
        result = pos + Direction.NORTH
        assert result == Position(5, 4)

    def test_position_subtraction(self):
        """Test subtracting positions."""
        pos1 = Position(10, 10)
        pos2 = Position(3, 4)
        result = pos1 - pos2
        assert result == Position(7, 6)

    def test_position_unpacking(self):
        """Test unpacking position as tuple."""
        pos = Position(3, 7)
        x, y = pos
        assert x == 3
        assert y == 7

    def test_euclidean_distance(self):
        """Test Euclidean distance calculation."""
        pos1 = Position(0, 0)
        pos2 = Position(3, 4)
        assert pos1.distance_to(pos2) == 5.0

    def test_manhattan_distance(self):
        """Test Manhattan distance calculation."""
        pos1 = Position(0, 0)
        pos2 = Position(3, 4)
        assert pos1.manhattan_distance(pos2) == 7

    def test_chebyshev_distance(self):
        """Test Chebyshev distance (D&D style)."""
        pos1 = Position(0, 0)
        pos2 = Position(3, 4)
        # Max of |3-0| and |4-0| = 4
        assert pos1.chebyshev_distance(pos2) == 4

    def test_chebyshev_distance_diagonal(self):
        """Test that diagonal movement costs 1 in Chebyshev."""
        pos1 = Position(0, 0)
        pos2 = Position(5, 5)
        # Diagonal = same as cardinal in Chebyshev
        assert pos1.chebyshev_distance(pos2) == 5

    def test_grid_distance_feet(self):
        """Test D&D 5E feet distance calculation."""
        pos1 = Position(0, 0)
        pos2 = Position(6, 0)
        # 6 tiles * 5 feet = 30 feet
        assert pos1.grid_distance_feet(pos2) == 30

    def test_is_adjacent_cardinal(self):
        """Test adjacency for cardinal directions."""
        pos = Position(5, 5)
        assert pos.is_adjacent(Position(5, 4))  # North
        assert pos.is_adjacent(Position(5, 6))  # South
        assert pos.is_adjacent(Position(4, 5))  # West
        assert pos.is_adjacent(Position(6, 5))  # East

    def test_is_adjacent_diagonal(self):
        """Test adjacency for diagonal directions."""
        pos = Position(5, 5)
        assert pos.is_adjacent(Position(4, 4))  # NW
        assert pos.is_adjacent(Position(6, 4))  # NE
        assert pos.is_adjacent(Position(4, 6))  # SW
        assert pos.is_adjacent(Position(6, 6))  # SE

    def test_is_adjacent_no_diagonal(self):
        """Test adjacency excluding diagonals."""
        pos = Position(5, 5)
        assert pos.is_adjacent(Position(5, 4), include_diagonal=False)
        assert not pos.is_adjacent(Position(4, 4), include_diagonal=False)

    def test_not_adjacent(self):
        """Test non-adjacent positions."""
        pos = Position(5, 5)
        assert not pos.is_adjacent(Position(5, 7))  # 2 tiles away
        assert not pos.is_adjacent(Position(5, 5))  # Same position

    def test_direction_to(self):
        """Test getting direction to another position."""
        pos = Position(5, 5)
        assert pos.direction_to(Position(5, 4)) == Direction.NORTH
        assert pos.direction_to(Position(6, 6)) == Direction.SOUTHEAST
        assert pos.direction_to(Position(5, 5)) is None  # Same position

    def test_neighbors(self):
        """Test getting neighbor positions."""
        pos = Position(5, 5)
        neighbors = pos.neighbors()
        assert len(neighbors) == 8  # All 8 directions

    def test_neighbors_cardinal_only(self):
        """Test getting only cardinal neighbors."""
        pos = Position(5, 5)
        neighbors = pos.neighbors(include_diagonal=False)
        assert len(neighbors) == 4

    def test_in_bounds(self):
        """Test bounds checking."""
        pos = Position(5, 5)
        assert pos.in_bounds(10, 10)
        assert not pos.in_bounds(5, 5)  # Edge case: 5 not < 5
        assert not Position(-1, 5).in_bounds(10, 10)
        assert not Position(5, -1).in_bounds(10, 10)

    def test_move(self):
        """Test moving in a direction."""
        pos = Position(5, 5)
        new_pos = pos.move(Direction.EAST)
        assert new_pos == Position(6, 5)


class TestDirection:
    """Tests for Direction enum."""

    def test_direction_values(self):
        """Test direction vector values."""
        assert Direction.NORTH.value == (0, -1)
        assert Direction.SOUTH.value == (0, 1)
        assert Direction.EAST.value == (1, 0)
        assert Direction.WEST.value == (-1, 0)

    def test_direction_dx_dy(self):
        """Test dx and dy properties."""
        assert Direction.NORTHEAST.dx == 1
        assert Direction.NORTHEAST.dy == -1

    def test_is_diagonal(self):
        """Test diagonal detection."""
        assert not Direction.NORTH.is_diagonal
        assert Direction.NORTHEAST.is_diagonal

    def test_cardinal_directions(self):
        """Test getting cardinal directions."""
        cardinals = Direction.cardinal()
        assert len(cardinals) == 4
        assert Direction.NORTH in cardinals
        assert Direction.NORTHEAST not in cardinals

    def test_all_directions(self):
        """Test getting all directions."""
        all_dirs = Direction.all_directions()
        assert len(all_dirs) == 8

    def test_from_delta(self):
        """Test creating direction from delta."""
        assert Direction.from_delta(0, -1) == Direction.NORTH
        assert Direction.from_delta(5, 0) == Direction.EAST  # Normalized
        assert Direction.from_delta(0, 0) is None


class TestTileType:
    """Tests for TileType enum."""

    def test_default_walkable(self):
        """Test default walkability."""
        assert TileType.FLOOR.default_walkable
        assert not TileType.WALL.default_walkable
        assert not TileType.DOOR_CLOSED.default_walkable
        assert TileType.DOOR_OPEN.default_walkable

    def test_default_blocks_sight(self):
        """Test default sight blocking."""
        assert not TileType.FLOOR.default_blocks_sight
        assert TileType.WALL.default_blocks_sight
        assert TileType.DOOR_CLOSED.default_blocks_sight
        assert not TileType.DOOR_OPEN.default_blocks_sight

    def test_default_char(self):
        """Test default ASCII characters."""
        assert TileType.FLOOR.default_char == "."
        assert TileType.WALL.default_char == "#"
        assert TileType.DOOR_CLOSED.default_char == "+"

    def test_is_interactive(self):
        """Test interactive tile detection."""
        assert TileType.DOOR_CLOSED.is_interactive
        assert TileType.CHEST.is_interactive
        assert not TileType.FLOOR.is_interactive
        assert not TileType.WALL.is_interactive


class TestTile:
    """Tests for Tile dataclass."""

    def test_tile_default(self):
        """Test default tile properties."""
        tile = Tile()
        assert tile.tile_type == TileType.FLOOR
        assert tile.is_walkable
        assert not tile.does_block_sight

    def test_tile_wall(self):
        """Test wall tile properties."""
        tile = Tile(tile_type=TileType.WALL)
        assert not tile.is_walkable
        assert tile.does_block_sight

    def test_tile_override_walkable(self):
        """Test overriding walkability."""
        # Normally wall is not walkable
        tile = Tile(tile_type=TileType.WALL, walkable=True)
        assert tile.is_walkable  # Override takes precedence

    def test_tile_visibility(self):
        """Test tile visibility states."""
        tile = Tile()
        assert tile.visibility == VisibilityState.UNEXPLORED
        assert not tile.is_visible()
        assert not tile.is_explored()

        tile.set_visible()
        assert tile.is_visible()
        assert tile.is_explored()

        tile.set_explored()
        assert not tile.is_visible()
        assert tile.is_explored()

    def test_tile_entity(self):
        """Test entity tracking on tile."""
        tile = Tile()
        assert not tile.is_occupied
        assert tile.entity_id is None

        tile.entity_id = "goblin_1"
        assert tile.is_occupied

    def test_tile_items(self):
        """Test item tracking on tile."""
        tile = Tile()
        assert not tile.has_items

        tile.item_ids.append("sword_1")
        assert tile.has_items

    def test_door_operations(self):
        """Test opening and closing doors."""
        tile = Tile(tile_type=TileType.DOOR_CLOSED)
        assert not tile.is_walkable

        assert tile.open_door()
        assert tile.tile_type == TileType.DOOR_OPEN
        assert tile.is_walkable

        assert tile.close_door()
        assert tile.tile_type == TileType.DOOR_CLOSED

    def test_door_invalid_operations(self):
        """Test invalid door operations."""
        tile = Tile(tile_type=TileType.FLOOR)
        assert not tile.open_door()  # Can't open floor
        assert not tile.close_door()  # Can't close floor

    def test_tile_copy(self):
        """Test tile copying."""
        tile = Tile(tile_type=TileType.CHEST, entity_id="goblin")
        tile.item_ids.append("gold")
        tile.metadata["trapped"] = True

        copy = tile.copy()
        assert copy.tile_type == tile.tile_type
        assert copy.entity_id == tile.entity_id
        assert copy.item_ids == tile.item_ids
        assert copy.item_ids is not tile.item_ids  # Different list object


class TestTileMap:
    """Tests for TileMap class."""

    def test_tilemap_creation(self):
        """Test basic tilemap creation."""
        tm = TileMap(width=10, height=8, name="Test Map")
        assert tm.width == 10
        assert tm.height == 8
        assert tm.name == "Test Map"
        assert len(tm.tiles) == 8
        assert len(tm.tiles[0]) == 10

    def test_tilemap_default_tiles(self):
        """Test that tiles are initialized as floor by default."""
        tm = TileMap(width=5, height=5)
        tile = tm.get_tile(Position(2, 2))
        assert tile is not None
        assert tile.tile_type == TileType.FLOOR

    def test_get_tile_out_of_bounds(self):
        """Test getting tile outside bounds."""
        tm = TileMap(width=5, height=5)
        assert tm.get_tile(Position(-1, 0)) is None
        assert tm.get_tile(Position(0, -1)) is None
        assert tm.get_tile(Position(5, 0)) is None
        assert tm.get_tile(Position(0, 5)) is None

    def test_set_tile(self):
        """Test setting a tile."""
        tm = TileMap(width=5, height=5)
        wall = Tile(tile_type=TileType.WALL)
        assert tm.set_tile(Position(2, 2), wall)
        assert tm.get_tile(Position(2, 2)).tile_type == TileType.WALL

    def test_set_tile_out_of_bounds(self):
        """Test setting tile outside bounds."""
        tm = TileMap(width=5, height=5)
        wall = Tile(tile_type=TileType.WALL)
        assert not tm.set_tile(Position(10, 10), wall)

    def test_add_entity(self):
        """Test adding an entity to the map."""
        tm = TileMap(width=10, height=10)
        pos = Position(5, 5)

        assert tm.add_entity(
            entity_id="player_1",
            position=pos,
            display_char="@",
            display_name="Hero",
            is_player=True,
        )

        entity = tm.get_entity("player_1")
        assert entity is not None
        assert entity.position == pos
        assert entity.display_char == "@"
        assert entity.is_player

        # Tile should be marked as occupied
        tile = tm.get_tile(pos)
        assert tile.is_occupied
        assert tile.entity_id == "player_1"

    def test_add_entity_occupied(self):
        """Test adding entity to occupied position fails."""
        tm = TileMap(width=10, height=10)
        pos = Position(5, 5)

        tm.add_entity("entity_1", pos)
        assert not tm.add_entity("entity_2", pos)

    def test_add_entity_out_of_bounds(self):
        """Test adding entity outside bounds fails."""
        tm = TileMap(width=10, height=10)
        assert not tm.add_entity("entity_1", Position(100, 100))

    def test_remove_entity(self):
        """Test removing an entity."""
        tm = TileMap(width=10, height=10)
        pos = Position(5, 5)
        tm.add_entity("entity_1", pos)

        assert tm.remove_entity("entity_1")
        assert tm.get_entity("entity_1") is None
        assert not tm.get_tile(pos).is_occupied

    def test_remove_nonexistent_entity(self):
        """Test removing entity that doesn't exist."""
        tm = TileMap(width=10, height=10)
        assert not tm.remove_entity("nonexistent")

    def test_get_entity_position(self):
        """Test getting entity position."""
        tm = TileMap(width=10, height=10)
        pos = Position(3, 7)
        tm.add_entity("entity_1", pos)
        assert tm.get_entity_position("entity_1") == pos
        assert tm.get_entity_position("nonexistent") is None

    def test_get_entity_at(self):
        """Test getting entity at position."""
        tm = TileMap(width=10, height=10)
        pos = Position(5, 5)
        tm.add_entity("goblin", pos, display_char="G")

        entity = tm.get_entity_at(pos)
        assert entity is not None
        assert entity.entity_id == "goblin"

        assert tm.get_entity_at(Position(0, 0)) is None

    def test_can_move_to_floor(self):
        """Test movement to floor tile."""
        tm = TileMap(width=10, height=10)
        assert tm.can_move_to(Position(5, 5))

    def test_can_move_to_wall(self):
        """Test movement to wall tile blocked."""
        tm = TileMap(width=10, height=10)
        tm.set_tile(Position(5, 5), Tile(tile_type=TileType.WALL))
        assert not tm.can_move_to(Position(5, 5))

    def test_can_move_to_occupied(self):
        """Test movement to occupied tile blocked."""
        tm = TileMap(width=10, height=10)
        pos = Position(5, 5)
        tm.add_entity("blocker", pos)
        assert not tm.can_move_to(pos)
        assert tm.can_move_to(pos, ignore_entities=True)

    def test_move_entity_success(self):
        """Test successful entity movement."""
        tm = TileMap(width=10, height=10)
        start = Position(5, 5)
        tm.add_entity("player", start)

        result = tm.move_entity("player", Direction.NORTH)

        assert result.success
        assert result.new_position == Position(5, 4)
        assert tm.get_entity_position("player") == Position(5, 4)
        assert not tm.get_tile(start).is_occupied
        assert tm.get_tile(Position(5, 4)).is_occupied

    def test_move_entity_blocked_by_wall(self):
        """Test movement blocked by wall."""
        tm = TileMap(width=10, height=10)
        start = Position(5, 5)
        tm.add_entity("player", start)
        tm.set_tile(Position(5, 4), Tile(tile_type=TileType.WALL))

        result = tm.move_entity("player", Direction.NORTH)

        assert not result.success
        assert result.blocked_by == "wall"
        assert tm.get_entity_position("player") == start

    def test_move_entity_blocked_by_door(self):
        """Test movement blocked by closed door."""
        tm = TileMap(width=10, height=10)
        start = Position(5, 5)
        tm.add_entity("player", start)
        tm.set_tile(Position(5, 4), Tile(tile_type=TileType.DOOR_CLOSED))

        result = tm.move_entity("player", Direction.NORTH)

        assert not result.success
        assert result.blocked_by == "door"

    def test_move_entity_blocked_by_entity(self):
        """Test movement blocked by another entity."""
        tm = TileMap(width=10, height=10)
        tm.add_entity("player", Position(5, 5))
        tm.add_entity("goblin", Position(5, 4), display_name="Goblin")

        result = tm.move_entity("player", Direction.NORTH)

        assert not result.success
        assert result.blocked_by == "entity"
        assert "Goblin" in result.message

    def test_move_entity_blocked_by_bounds(self):
        """Test movement blocked by map edge."""
        tm = TileMap(width=10, height=10)
        tm.add_entity("player", Position(0, 0))

        result = tm.move_entity("player", Direction.NORTH)

        assert not result.success
        assert result.blocked_by == "bounds"

    def test_move_entity_to_position(self):
        """Test moving entity to specific position."""
        tm = TileMap(width=10, height=10)
        tm.add_entity("player", Position(0, 0))

        result = tm.move_entity_to("player", Position(5, 5))

        assert result.success
        assert tm.get_entity_position("player") == Position(5, 5)

    def test_teleport_entity(self):
        """Test teleporting entity (ignores collision)."""
        tm = TileMap(width=10, height=10)
        tm.add_entity("player", Position(0, 0))

        # Teleport should work even if destination has entity
        tm.add_entity("npc", Position(5, 5))
        assert tm.teleport_entity("player", Position(5, 5))
        assert tm.get_entity_position("player") == Position(5, 5)

    def test_get_entities_in_radius(self):
        """Test getting entities within radius."""
        tm = TileMap(width=20, height=20)
        center = Position(10, 10)
        tm.add_entity("center", center)
        tm.add_entity("near", Position(11, 10))  # 1 away
        tm.add_entity("medium", Position(12, 10))  # 2 away
        tm.add_entity("far", Position(15, 10))  # 5 away

        entities = tm.get_entities_in_radius(center, 2)
        entity_ids = [e.entity_id for e in entities]

        assert "near" in entity_ids
        assert "medium" in entity_ids
        assert "far" not in entity_ids
        assert "center" not in entity_ids  # Exclude center by default

    def test_distance_between_entities(self):
        """Test distance calculation between entities."""
        tm = TileMap(width=20, height=20)
        tm.add_entity("a", Position(0, 0))
        tm.add_entity("b", Position(6, 0))

        assert tm.distance_between_entities("a", "b") == 6
        assert tm.distance_feet("a", "b") == 30  # 6 * 5ft

    def test_player_and_enemy_entities(self):
        """Test filtering player vs enemy entities."""
        tm = TileMap(width=20, height=20)
        tm.add_entity("hero", Position(0, 0), is_player=True)
        tm.add_entity("sidekick", Position(1, 0), is_player=True)
        tm.add_entity("goblin", Position(5, 5), is_player=False)

        players = tm.get_player_entities()
        enemies = tm.get_enemy_entities()

        assert len(players) == 2
        assert len(enemies) == 1

    def test_door_operations(self):
        """Test door opening/closing through tilemap."""
        tm = TileMap(width=10, height=10)
        door_pos = Position(5, 5)
        tm.set_tile(door_pos, Tile(tile_type=TileType.DOOR_CLOSED))

        assert tm.open_door(door_pos)
        assert tm.get_tile(door_pos).tile_type == TileType.DOOR_OPEN

        assert tm.close_door(door_pos)
        assert tm.get_tile(door_pos).tile_type == TileType.DOOR_CLOSED

    def test_get_adjacent_doors(self):
        """Test finding adjacent doors."""
        tm = TileMap(width=10, height=10)
        pos = Position(5, 5)
        tm.set_tile(Position(5, 4), Tile(tile_type=TileType.DOOR_CLOSED))
        tm.set_tile(Position(6, 5), Tile(tile_type=TileType.DOOR_OPEN))

        doors = tm.get_adjacent_doors(pos)
        assert len(doors) == 2

    def test_visibility_operations(self):
        """Test visibility management."""
        tm = TileMap(width=10, height=10)
        pos = Position(5, 5)

        tm.set_visible(pos)
        assert tm.get_tile(pos).is_visible()

        tm.reset_visibility()
        assert not tm.get_tile(pos).is_visible()
        assert tm.get_tile(pos).is_explored()

    def test_reveal_all(self):
        """Test revealing entire map."""
        tm = TileMap(width=5, height=5)
        tm.reveal_all()

        for pos, tile in tm.iter_tiles():
            assert tile.is_visible()

    def test_iter_tiles(self):
        """Test iterating all tiles."""
        tm = TileMap(width=3, height=3)
        tiles = list(tm.iter_tiles())
        assert len(tiles) == 9

    def test_iter_visible_tiles(self):
        """Test iterating only visible tiles."""
        tm = TileMap(width=5, height=5)
        tm.set_visible(Position(2, 2))
        tm.set_visible(Position(3, 3))

        visible = list(tm.iter_visible_tiles())
        assert len(visible) == 2

    def test_serialization_roundtrip(self):
        """Test map can be serialized and deserialized."""
        tm = TileMap(width=10, height=10, name="Test")
        tm.set_tile(Position(5, 5), Tile(tile_type=TileType.WALL))
        tm.add_entity("player", Position(3, 3), display_char="@", is_player=True)
        tm.set_visible(Position(3, 3))

        # Serialize
        data = tm.to_dict()

        # Deserialize
        tm2 = TileMap.from_dict(data)

        assert tm2.width == tm.width
        assert tm2.height == tm.height
        assert tm2.name == tm.name
        assert tm2.get_tile(Position(5, 5)).tile_type == TileType.WALL
        assert tm2.get_entity_position("player") == Position(3, 3)
        assert tm2.get_tile(Position(3, 3)).is_visible()

    def test_str_representation(self):
        """Test string representation."""
        tm = TileMap(width=10, height=8, name="Dungeon")
        tm.add_entity("player", Position(0, 0))
        tm.add_entity("goblin", Position(5, 5))

        s = str(tm)
        assert "Dungeon" in s
        assert "10x8" in s
        assert "2 entities" in s
