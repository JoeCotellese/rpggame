# ABOUTME: Unit tests for CombatGridManager
# ABOUTME: Tests range checking, distance calculations, and combat movement

import pytest

from dnd_engine.spatial import (
    Position,
    Direction,
    TileMap,
    Tile,
    TileType,
    CombatGridManager,
    RangeCheckResult,
    FEET_PER_TILE,
    create_map_from_string,
)


# Simple mock creature for testing
class MockCreature:
    """Simple creature mock for testing."""

    def __init__(self, name: str = "Test Creature"):
        self.name = name


class TestCombatGridManager:
    """Tests for CombatGridManager class."""

    @pytest.fixture
    def arena_map(self):
        """Create a simple arena map for combat testing."""
        result = create_map_from_string("""
###########
#.........#
#.........#
#.........#
#.........#
#.........#
#.........#
#.........#
#.........#
###########
""")
        result.tile_map.reveal_all()
        return result.tile_map

    @pytest.fixture
    def corridor_map(self):
        """Create a corridor map with walls for LOS testing."""
        result = create_map_from_string("""
###########
#....#....#
#....#....#
#....+....#
#....#....#
###########
""")
        # Make the + a door (closed)
        result.tile_map.set_tile(Position(5, 3), Tile(tile_type=TileType.DOOR_CLOSED))
        result.tile_map.reveal_all()
        return result.tile_map

    @pytest.fixture
    def combat_grid(self, arena_map):
        """Create a combat grid manager with the arena map."""
        return CombatGridManager(arena_map)

    def test_add_combatant(self, combat_grid):
        """Test adding a combatant to the grid."""
        player = MockCreature("Hero")

        success = combat_grid.add_combatant(
            creature_id="player",
            creature=player,
            position=Position(5, 5),
            is_player=True,
        )

        assert success
        assert combat_grid.get_position("player") == Position(5, 5)

    def test_add_combatant_at_occupied_position(self, combat_grid):
        """Test that adding combatant at occupied position fails."""
        player = MockCreature("Hero")
        enemy = MockCreature("Goblin")

        combat_grid.add_combatant("player", player, Position(5, 5), is_player=True)
        success = combat_grid.add_combatant("enemy", enemy, Position(5, 5))

        assert not success

    def test_remove_combatant(self, combat_grid):
        """Test removing a combatant from the grid."""
        player = MockCreature("Hero")
        combat_grid.add_combatant("player", player, Position(5, 5))

        success = combat_grid.remove_combatant("player")

        assert success
        assert combat_grid.get_position("player") is None

    def test_get_distance(self, combat_grid):
        """Test distance calculation between combatants."""
        player = MockCreature("Hero")
        enemy = MockCreature("Goblin")

        combat_grid.add_combatant("player", player, Position(5, 5))
        combat_grid.add_combatant("enemy", enemy, Position(8, 5))

        distance = combat_grid.get_distance("player", "enemy")

        assert distance == 3  # 3 tiles

    def test_get_distance_diagonal(self, combat_grid):
        """Test diagonal distance uses Chebyshev (D&D 5E)."""
        player = MockCreature("Hero")
        enemy = MockCreature("Goblin")

        combat_grid.add_combatant("player", player, Position(5, 5))
        combat_grid.add_combatant("enemy", enemy, Position(7, 7))

        distance = combat_grid.get_distance("player", "enemy")

        # Chebyshev distance: max(|7-5|, |7-5|) = 2
        assert distance == 2

    def test_get_distance_feet(self, combat_grid):
        """Test distance in feet calculation."""
        player = MockCreature("Hero")
        enemy = MockCreature("Goblin")

        combat_grid.add_combatant("player", player, Position(5, 5))
        combat_grid.add_combatant("enemy", enemy, Position(8, 5))

        distance_feet = combat_grid.get_distance_feet("player", "enemy")

        assert distance_feet == 15  # 3 tiles * 5ft


class TestMeleeRange:
    """Tests for melee range checking."""

    @pytest.fixture
    def combat_grid(self):
        """Create combat grid for melee tests."""
        result = create_map_from_string("""
#######
#.....#
#.....#
#.....#
#######
""")
        result.tile_map.reveal_all()
        return CombatGridManager(result.tile_map)

    def test_melee_range_adjacent(self, combat_grid):
        """Test melee range when target is adjacent."""
        player = MockCreature("Hero")
        enemy = MockCreature("Goblin")

        combat_grid.add_combatant("player", player, Position(3, 2))
        combat_grid.add_combatant("enemy", enemy, Position(4, 2))

        result = combat_grid.check_melee_range("player", "enemy")

        assert result.in_range
        assert result.distance_tiles == 1
        assert result.distance_feet == 5

    def test_melee_range_diagonal_adjacent(self, combat_grid):
        """Test melee range when target is diagonally adjacent."""
        player = MockCreature("Hero")
        enemy = MockCreature("Goblin")

        combat_grid.add_combatant("player", player, Position(3, 2))
        combat_grid.add_combatant("enemy", enemy, Position(4, 3))

        result = combat_grid.check_melee_range("player", "enemy")

        assert result.in_range
        assert result.distance_tiles == 1

    def test_melee_range_too_far(self, combat_grid):
        """Test melee range when target is too far."""
        player = MockCreature("Hero")
        enemy = MockCreature("Goblin")

        combat_grid.add_combatant("player", player, Position(1, 2))
        combat_grid.add_combatant("enemy", enemy, Position(5, 2))

        result = combat_grid.check_melee_range("player", "enemy")

        assert not result.in_range
        assert result.distance_tiles == 4
        assert result.distance_feet == 20
        assert result.requires_movement == 3  # Need to move 3 tiles closer

    def test_melee_reach_10ft(self, combat_grid):
        """Test melee range with reach weapon (10ft)."""
        player = MockCreature("Hero")
        enemy = MockCreature("Goblin")

        combat_grid.add_combatant("player", player, Position(2, 2))
        combat_grid.add_combatant("enemy", enemy, Position(4, 2))

        result = combat_grid.check_melee_range("player", "enemy", reach=True)

        assert result.in_range  # 2 tiles = 10ft, within reach
        assert result.distance_tiles == 2


class TestRangedRange:
    """Tests for ranged attack range checking."""

    @pytest.fixture
    def combat_grid(self):
        """Create combat grid for ranged tests."""
        result = create_map_from_string("""
#################
#...............#
#...............#
#...............#
#...............#
#...............#
#################
""")
        result.tile_map.reveal_all()
        return CombatGridManager(result.tile_map)

    def test_ranged_normal_range(self, combat_grid):
        """Test ranged attack within normal range."""
        player = MockCreature("Hero")
        enemy = MockCreature("Goblin")

        combat_grid.add_combatant("player", player, Position(1, 3))
        combat_grid.add_combatant("enemy", enemy, Position(7, 3))

        # Shortbow: 80ft normal, 320ft long
        result = combat_grid.check_ranged_range("player", "enemy", 80, 320)

        assert result.in_range
        assert result.distance_feet == 30
        assert "normal range" in result.message

    def test_ranged_long_range(self, combat_grid):
        """Test ranged attack at long range (disadvantage)."""
        player = MockCreature("Hero")
        enemy = MockCreature("Goblin")

        combat_grid.add_combatant("player", player, Position(1, 3))
        combat_grid.add_combatant("enemy", enemy, Position(11, 3))

        # Shortbow: 80ft normal, 320ft long
        result = combat_grid.check_ranged_range("player", "enemy", 80, 320)

        assert result.in_range
        assert result.distance_feet == 50
        # 50ft is within 80ft normal range
        assert "normal range" in result.message

    def test_ranged_out_of_range(self, combat_grid):
        """Test ranged attack out of maximum range."""
        player = MockCreature("Hero")
        enemy = MockCreature("Goblin")

        combat_grid.add_combatant("player", player, Position(1, 3))
        combat_grid.add_combatant("enemy", enemy, Position(11, 3))

        # Dagger thrown: 20ft normal, 40ft long (50ft distance is out of range)
        result = combat_grid.check_ranged_range("player", "enemy", 20, 40)

        assert not result.in_range
        assert "out of range" in result.message.lower()


class TestRangedLineOfSight:
    """Tests for ranged attacks requiring line of sight."""

    @pytest.fixture
    def combat_grid(self):
        """Create combat grid with obstacles."""
        result = create_map_from_string("""
#############
#.....#.....#
#.....#.....#
#.....#.....#
#.....#.....#
#############
""")
        result.tile_map.reveal_all()
        return CombatGridManager(result.tile_map)

    def test_ranged_blocked_by_wall(self, combat_grid):
        """Test ranged attack blocked by wall."""
        player = MockCreature("Hero")
        enemy = MockCreature("Goblin")

        combat_grid.add_combatant("player", player, Position(3, 3))
        combat_grid.add_combatant("enemy", enemy, Position(9, 3))

        # Wall at x=6 blocks line of sight
        result = combat_grid.check_ranged_range("player", "enemy", 80, 320)

        assert not result.in_range
        assert "line of sight" in result.message.lower()


class TestSpellRange:
    """Tests for spell range checking."""

    @pytest.fixture
    def combat_grid(self):
        """Create combat grid for spell tests."""
        result = create_map_from_string("""
#############
#...........#
#...........#
#...........#
#...........#
#############
""")
        result.tile_map.reveal_all()
        return CombatGridManager(result.tile_map)

    def test_spell_self_target(self, combat_grid):
        """Test self-targeting spell."""
        player = MockCreature("Hero")

        combat_grid.add_combatant("player", player, Position(5, 3))

        # Shield spell (range: Self = 0)
        result = combat_grid.check_spell_range("player", "player", 0)

        assert result.in_range

    def test_spell_self_cannot_target_others(self, combat_grid):
        """Test self-targeting spell cannot target others."""
        player = MockCreature("Hero")
        ally = MockCreature("Ally")

        combat_grid.add_combatant("player", player, Position(5, 3))
        combat_grid.add_combatant("ally", ally, Position(6, 3))

        result = combat_grid.check_spell_range("player", "ally", 0)

        assert not result.in_range

    def test_spell_touch_adjacent(self, combat_grid):
        """Test touch spell on adjacent target."""
        player = MockCreature("Hero")
        ally = MockCreature("Ally")

        combat_grid.add_combatant("player", player, Position(5, 3))
        combat_grid.add_combatant("ally", ally, Position(6, 3))

        # Touch spell (range: Touch = -1)
        result = combat_grid.check_spell_range("player", "ally", -1)

        assert result.in_range

    def test_spell_ranged_in_range(self, combat_grid):
        """Test ranged spell in range."""
        player = MockCreature("Hero")
        enemy = MockCreature("Goblin")

        combat_grid.add_combatant("player", player, Position(1, 3))
        combat_grid.add_combatant("enemy", enemy, Position(7, 3))

        # Fire Bolt (range: 120ft)
        result = combat_grid.check_spell_range("player", "enemy", 120)

        assert result.in_range
        assert result.distance_feet == 30

    def test_spell_ranged_out_of_range(self, combat_grid):
        """Test ranged spell out of range."""
        player = MockCreature("Hero")
        enemy = MockCreature("Goblin")

        combat_grid.add_combatant("player", player, Position(1, 3))
        combat_grid.add_combatant("enemy", enemy, Position(11, 3))

        # Shocking Grasp (range: Touch = -1, but testing with 15ft)
        result = combat_grid.check_spell_range("player", "enemy", 15)

        assert not result.in_range


class TestCombatMovement:
    """Tests for combat movement."""

    @pytest.fixture
    def combat_grid(self):
        """Create combat grid for movement tests."""
        result = create_map_from_string("""
############
#..........#
#..........#
#..........#
############
""")
        result.tile_map.reveal_all()
        return CombatGridManager(result.tile_map)

    def test_move_combatant(self, combat_grid):
        """Test basic combat movement."""
        player = MockCreature("Hero")

        combat_grid.add_combatant("player", player, Position(3, 2), speed=30)

        success = combat_grid.move_combatant("player", Direction.EAST)

        assert success
        assert combat_grid.get_position("player") == Position(4, 2)

    def test_movement_consumes_speed(self, combat_grid):
        """Test movement consumes from speed pool."""
        player = MockCreature("Hero")

        combat_grid.add_combatant("player", player, Position(3, 2), speed=30)

        # Move 3 times = 15ft
        combat_grid.move_combatant("player", Direction.EAST)
        combat_grid.move_combatant("player", Direction.EAST)
        combat_grid.move_combatant("player", Direction.EAST)

        remaining = combat_grid.get_movement_remaining("player")
        assert remaining == 15  # 30 - 15 = 15

    def test_movement_limited_by_speed(self, combat_grid):
        """Test movement is limited by speed."""
        player = MockCreature("Hero")

        # Only 10ft speed = 2 tiles
        combat_grid.add_combatant("player", player, Position(2, 2), speed=10)

        combat_grid.move_combatant("player", Direction.EAST)
        combat_grid.move_combatant("player", Direction.EAST)

        # Third move should fail
        assert not combat_grid.can_move("player")

    def test_reset_turn_restores_movement(self, combat_grid):
        """Test resetting turn restores movement."""
        player = MockCreature("Hero")

        combat_grid.add_combatant("player", player, Position(3, 2), speed=30)

        # Use all movement
        for _ in range(6):
            combat_grid.move_combatant("player", Direction.EAST)

        assert combat_grid.get_movement_remaining("player") == 0

        # Reset turn
        combat_grid.reset_turn("player")

        assert combat_grid.get_movement_remaining("player") == 30


class TestEnemyQueries:
    """Tests for querying enemies."""

    @pytest.fixture
    def combat_grid(self):
        """Create combat grid with multiple combatants."""
        result = create_map_from_string("""
#########
#.......#
#.......#
#.......#
#.......#
#########
""")
        result.tile_map.reveal_all()
        grid = CombatGridManager(result.tile_map)

        # Add player in center
        grid.add_combatant(
            "player", MockCreature("Hero"), Position(4, 3), is_player=True
        )

        # Add enemies around
        grid.add_combatant("goblin1", MockCreature("Goblin"), Position(5, 3))  # Adjacent
        grid.add_combatant("goblin2", MockCreature("Goblin"), Position(7, 3))  # 3 tiles away
        grid.add_combatant("goblin3", MockCreature("Goblin"), Position(4, 1))  # 2 tiles away

        return grid

    def test_get_adjacent_enemies(self, combat_grid):
        """Test getting adjacent enemies."""
        adjacent = combat_grid.get_adjacent_enemies("player")

        assert "goblin1" in adjacent
        assert "goblin2" not in adjacent
        assert "goblin3" not in adjacent

    def test_get_enemies_in_range(self, combat_grid):
        """Test getting enemies within a range."""
        # Within 15ft (3 tiles) - all 3 goblins are within this range
        # goblin1 at (5,3) = 5ft, goblin3 at (4,1) = 10ft, goblin2 at (7,3) = 15ft
        enemies = combat_grid.get_enemies_in_range("player", 15)

        assert len(enemies) == 3
        # Should be sorted by distance
        assert enemies[0][0] == "goblin1"  # 5ft
        assert enemies[1][0] == "goblin3"  # 10ft
        assert enemies[2][0] == "goblin2"  # 15ft

    def test_get_closest_enemy(self, combat_grid):
        """Test getting closest enemy."""
        closest = combat_grid.get_closest_enemy("player")

        assert closest is not None
        assert closest[0] == "goblin1"
        assert closest[1] == 5  # 5ft away

    def test_get_player_combatants(self, combat_grid):
        """Test getting all player combatants."""
        players = combat_grid.get_player_combatants()

        assert "player" in players
        assert len(players) == 1

    def test_get_enemy_combatants(self, combat_grid):
        """Test getting all enemy combatants."""
        enemies = combat_grid.get_enemy_combatants()

        assert "goblin1" in enemies
        assert "goblin2" in enemies
        assert "goblin3" in enemies
        assert len(enemies) == 3


class TestCombatGridIntegration:
    """Integration tests for combat grid."""

    def test_full_combat_scenario(self):
        """Test a full combat scenario with movement and attacks."""
        # Create arena
        result = create_map_from_string("""
#############
#...........#
#...........#
#...........#
#...........#
#############
""")
        result.tile_map.reveal_all()
        grid = CombatGridManager(result.tile_map)

        # Setup combatants
        player = MockCreature("Hero")
        goblin = MockCreature("Goblin")

        grid.add_combatant("player", player, Position(2, 3), is_player=True, speed=30)
        grid.add_combatant("goblin", goblin, Position(8, 3))

        # Check initial range - out of melee
        melee = grid.check_melee_range("player", "goblin")
        assert not melee.in_range
        assert melee.distance_feet == 30

        # But within bow range
        ranged = grid.check_ranged_range("player", "goblin", 80, 320)
        assert ranged.in_range

        # Player moves closer (5 tiles = 25ft)
        for _ in range(5):
            grid.move_combatant("player", Direction.EAST)

        # Now should be adjacent
        melee = grid.check_melee_range("player", "goblin")
        assert melee.in_range
        assert melee.distance_feet == 5

        # Goblin is defeated
        grid.remove_combatant("goblin")

        # No more enemies
        assert grid.get_closest_enemy("player") is None
