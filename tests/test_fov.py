# ABOUTME: Unit tests for Field of View (FOV) calculation
# ABOUTME: Tests shadowcasting, line of sight, and visibility

import pytest

from dnd_engine.spatial import (
    Position,
    TileMap,
    TileType,
    Tile,
    FieldOfView,
    SimpleFOV,
    FOVConfig,
    compute_los,
    compute_visibility_at_distance,
    create_map_from_string,
)


class TestFieldOfView:
    """Tests for FieldOfView shadowcasting."""

    @pytest.fixture
    def open_room(self):
        """Create an open room map."""
        result = create_map_from_string("""
#########
#.......#
#.......#
#.......#
#.......#
#.......#
#.......#
#########
""")
        return result.tile_map

    @pytest.fixture
    def room_with_pillar(self):
        """Create a room with a central pillar."""
        result = create_map_from_string("""
#########
#.......#
#.......#
#...#...#
#.......#
#.......#
#.......#
#########
""")
        # Set the center # as a pillar
        result.tile_map.set_tile(Position(4, 3), Tile(tile_type=TileType.PILLAR))
        return result.tile_map

    def test_basic_visibility(self, open_room):
        """Test basic visibility in open room."""
        fov = FieldOfView(open_room, FOVConfig(max_radius=10))

        visible = fov.compute(Position(4, 4))

        # Origin should be visible
        assert Position(4, 4) in visible

        # Adjacent tiles should be visible
        assert Position(4, 3) in visible
        assert Position(4, 5) in visible
        assert Position(3, 4) in visible
        assert Position(5, 4) in visible

    def test_radius_limit(self, open_room):
        """Test visibility respects radius limit."""
        fov = FieldOfView(open_room, FOVConfig(max_radius=2))

        visible = fov.compute(Position(4, 4))

        # 2 tiles away should be visible
        assert Position(4, 2) in visible

        # 3 tiles away should not be visible
        assert Position(4, 1) not in visible

    def test_wall_blocks_sight(self, room_with_pillar):
        """Test that walls/pillars block line of sight."""
        fov = FieldOfView(room_with_pillar, FOVConfig(max_radius=10))

        # Compute from left side of pillar
        visible = fov.compute(Position(2, 3))

        # Should see the pillar
        assert Position(4, 3) in visible

        # Should not see behind the pillar (to the right)
        # The exact tiles blocked depend on the algorithm
        # At minimum, the tile directly behind should be shadowed
        assert Position(6, 3) not in visible

    def test_diagonal_visibility(self, open_room):
        """Test diagonal visibility."""
        fov = FieldOfView(open_room, FOVConfig(max_radius=5))

        visible = fov.compute(Position(4, 4))

        # Diagonal tiles should be visible
        assert Position(3, 3) in visible
        assert Position(5, 5) in visible
        assert Position(3, 5) in visible
        assert Position(5, 3) in visible

    def test_compute_and_apply(self, open_room):
        """Test that compute_and_apply sets tile visibility."""
        fov = FieldOfView(open_room, FOVConfig(max_radius=3))

        visible = fov.compute_and_apply(Position(4, 4))

        # Check tiles are marked visible
        tile = open_room.get_tile(Position(4, 4))
        assert tile.is_visible()

        tile = open_room.get_tile(Position(4, 3))
        assert tile.is_visible()

    def test_reset_visibility(self, open_room):
        """Test that visibility resets properly."""
        fov = FieldOfView(open_room, FOVConfig(max_radius=3))

        # First computation
        fov.compute_and_apply(Position(2, 2))
        assert open_room.get_tile(Position(2, 2)).is_visible()

        # Second computation at different position
        fov.compute_and_apply(Position(6, 6), mark_explored=True)

        # Old position should be explored but not visible
        tile = open_room.get_tile(Position(2, 2))
        assert tile.is_explored()
        assert not tile.is_visible()

    def test_walls_blocking_disabled(self, room_with_pillar):
        """Test disabling wall blocking."""
        fov = FieldOfView(
            room_with_pillar,
            FOVConfig(max_radius=10, walls_block=False)
        )

        visible = fov.compute(Position(2, 3))

        # Should see through the pillar
        assert Position(6, 3) in visible

    def test_get_visible_entities(self, open_room):
        """Test getting visible entities."""
        open_room.add_entity("goblin", Position(5, 4), display_char="G")
        open_room.add_entity("far_goblin", Position(1, 1), display_char="G")

        fov = FieldOfView(open_room, FOVConfig(max_radius=3))
        fov.compute(Position(4, 4))

        visible_entities = fov.get_visible_entities()

        assert "goblin" in visible_entities
        assert "far_goblin" not in visible_entities

    def test_is_visible(self, open_room):
        """Test is_visible method."""
        fov = FieldOfView(open_room, FOVConfig(max_radius=3))
        fov.compute(Position(4, 4))

        assert fov.is_visible(Position(4, 4))
        assert fov.is_visible(Position(4, 3))
        assert not fov.is_visible(Position(1, 1))

    def test_origin_excluded(self, open_room):
        """Test origin can be excluded from visible set."""
        fov = FieldOfView(
            open_room,
            FOVConfig(max_radius=3, include_origin=False)
        )

        visible = fov.compute(Position(4, 4))

        assert Position(4, 4) not in visible
        assert Position(4, 3) in visible


class TestSimpleFOV:
    """Tests for SimpleFOV circular visibility."""

    @pytest.fixture
    def open_room(self):
        """Create an open room map."""
        result = create_map_from_string("""
#########
#.......#
#.......#
#.......#
#.......#
#########
""")
        return result.tile_map

    def test_circular_visibility(self, open_room):
        """Test circular visibility calculation."""
        fov = SimpleFOV(open_room)

        visible = fov.compute(Position(4, 3), radius=2)

        # Origin
        assert Position(4, 3) in visible

        # Adjacent
        assert Position(4, 2) in visible
        assert Position(4, 4) in visible

        # Diagonal within radius
        assert Position(3, 2) in visible
        assert Position(5, 4) in visible

    def test_radius_boundary(self, open_room):
        """Test radius boundary."""
        fov = SimpleFOV(open_room)

        visible = fov.compute(Position(4, 3), radius=1)

        # 1 tile away
        assert Position(4, 2) in visible

        # 2 tiles away - outside radius
        assert Position(4, 1) not in visible

    def test_ignores_walls(self, open_room):
        """Test SimpleFOV ignores walls (doesn't do shadowcasting)."""
        # Add a wall
        open_room.set_tile(Position(4, 2), Tile(tile_type=TileType.WALL))

        fov = SimpleFOV(open_room)
        visible = fov.compute(Position(4, 3), radius=2)

        # Can "see" through wall (simple distance check)
        assert Position(4, 1) in visible

    def test_compute_and_apply(self, open_room):
        """Test SimpleFOV compute_and_apply."""
        fov = SimpleFOV(open_room)

        visible = fov.compute_and_apply(Position(4, 3), radius=2)

        # Check tiles are marked
        assert open_room.get_tile(Position(4, 3)).is_visible()
        assert open_room.get_tile(Position(4, 2)).is_visible()


class TestLineOfSight:
    """Tests for line of sight calculation."""

    @pytest.fixture
    def corridor(self):
        """Create a corridor map."""
        result = create_map_from_string("""
#########
#.......#
#########
""")
        return result.tile_map

    @pytest.fixture
    def blocked_corridor(self):
        """Create a corridor with a pillar."""
        result = create_map_from_string("""
#########
#...#...#
#########
""")
        result.tile_map.set_tile(Position(4, 1), Tile(tile_type=TileType.PILLAR))
        return result.tile_map

    def test_clear_los(self, corridor):
        """Test clear line of sight."""
        has_los = compute_los(corridor, Position(1, 1), Position(7, 1))
        assert has_los

    def test_blocked_los(self, blocked_corridor):
        """Test blocked line of sight."""
        has_los = compute_los(blocked_corridor, Position(1, 1), Position(7, 1))
        assert not has_los

    def test_diagonal_los(self):
        """Test diagonal line of sight."""
        result = create_map_from_string("""
#####
#...#
#...#
#...#
#####
""")
        has_los = compute_los(result.tile_map, Position(1, 1), Position(3, 3))
        assert has_los

    def test_same_position_los(self, corridor):
        """Test LOS to same position."""
        has_los = compute_los(corridor, Position(1, 1), Position(1, 1))
        assert has_los

    def test_adjacent_los(self, corridor):
        """Test LOS to adjacent position."""
        has_los = compute_los(corridor, Position(1, 1), Position(2, 1))
        assert has_los


class TestVisibilityAtDistance:
    """Tests for distance-based visibility."""

    def test_bright_light_full_radius(self):
        """Test bright light allows full radius."""
        assert compute_visibility_at_distance(
            Position(0, 0),
            Position(5, 0),
            base_radius=10,
            light_level="bright"
        )

    def test_bright_light_beyond_radius(self):
        """Test bright light respects max radius."""
        assert not compute_visibility_at_distance(
            Position(0, 0),
            Position(15, 0),
            base_radius=10,
            light_level="bright"
        )

    def test_dim_light_half_radius(self):
        """Test dim light has half radius."""
        # Within half radius (5)
        assert compute_visibility_at_distance(
            Position(0, 0),
            Position(4, 0),
            base_radius=10,
            light_level="dim"
        )

        # Beyond half radius
        assert not compute_visibility_at_distance(
            Position(0, 0),
            Position(7, 0),
            base_radius=10,
            light_level="dim"
        )

    def test_darkness_no_visibility(self):
        """Test darkness prevents visibility."""
        assert not compute_visibility_at_distance(
            Position(0, 0),
            Position(1, 0),
            base_radius=10,
            light_level="dark"
        )


class TestFOVIntegration:
    """Integration tests for FOV with movement."""

    def test_movement_updates_fov(self):
        """Test FOV updates when player moves."""
        result = create_map_from_string("""
###########
#.........#
#.........#
#.........#
###########
""")
        tm = result.tile_map

        fov = FieldOfView(tm, FOVConfig(max_radius=3))

        # Initial position
        fov.compute_and_apply(Position(1, 2))
        assert tm.get_tile(Position(1, 2)).is_visible()
        assert not tm.get_tile(Position(9, 2)).is_visible()

        # Move to new position
        fov.compute_and_apply(Position(5, 2))
        assert tm.get_tile(Position(5, 2)).is_visible()

        # Old position should be explored but not visible
        tile = tm.get_tile(Position(1, 2))
        assert tile.is_explored()
        # May or may not be visible depending on radius

    def test_fov_with_entities(self):
        """Test FOV shows/hides entities."""
        result = create_map_from_string("""
#############
#...........#
#...........#
#...........#
#############
""")
        tm = result.tile_map

        # Add entities
        tm.add_entity("near_goblin", Position(3, 2), display_char="G")
        tm.add_entity("far_goblin", Position(10, 2), display_char="G")

        fov = FieldOfView(tm, FOVConfig(max_radius=3))
        fov.compute(Position(1, 2))

        visible_entities = fov.get_visible_entities()

        assert "near_goblin" in visible_entities
        assert "far_goblin" not in visible_entities

    def test_corridor_exploration(self):
        """Test exploring a corridor reveals tiles progressively."""
        result = create_map_from_string("""
#######################
#.....................#
#######################
""")
        tm = result.tile_map

        fov = FieldOfView(tm, FOVConfig(max_radius=3))

        # Start at left end
        fov.compute_and_apply(Position(1, 1))

        # Middle should not be visible yet
        assert not tm.get_tile(Position(10, 1)).is_visible()

        # Move through corridor
        for x in range(2, 11):
            fov.compute_and_apply(Position(x, 1))

        # Now middle should be visible/explored
        assert tm.get_tile(Position(10, 1)).is_visible() or \
               tm.get_tile(Position(10, 1)).is_explored()
