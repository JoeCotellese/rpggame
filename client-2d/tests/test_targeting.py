# ABOUTME: Unit tests for the unified targeting system (issue #355).
# ABOUTME: Tests screen-to-grid conversion, target cycling, and MCP entity ID targeting.

"""Unit tests for the targeting system."""

from unittest.mock import MagicMock, PropertyMock


class MockRoomLayout:
    """Mock room layout for testing coordinate conversion."""

    def __init__(self, width: int = 20, height: int = 15):
        self.width = width
        self.height = height


def create_mock_game_window():
    """Create a properly mocked GameWindow instance for testing."""
    # Mock arcade.Window to avoid GUI initialization
    mock_window = MagicMock()
    mock_window.room_layout = None
    # Use internal attribute names to avoid property conflicts
    mock_window._width = 1280
    mock_window._height = 900

    # Add the width/height as simple attributes
    type(mock_window).width = PropertyMock(return_value=1280)
    type(mock_window).height = PropertyMock(return_value=900)

    return mock_window


class TestScreenToGridConversion:
    """Tests for _screen_to_grid and _get_map_render_params."""

    def test_get_map_render_params_returns_none_without_layout(self):
        """Should return None when room_layout is not set."""
        from client_2d.game import GameWindow

        mock_window = create_mock_game_window()
        mock_window.room_layout = None

        # Bind the method to our mock
        result = GameWindow._get_map_render_params(mock_window)
        assert result is None

    def test_get_map_render_params_calculates_offsets(self):
        """Should calculate proper offsets for centering map."""
        from client_2d.game import GameWindow

        mock_window = create_mock_game_window()
        mock_window.room_layout = MockRoomLayout(width=20, height=15)

        result = GameWindow._get_map_render_params(mock_window)
        assert result is not None
        offset_x, offset_y, tile_size = result

        # Verify we got reasonable values
        assert offset_x > 0  # Map should be centered
        assert offset_y > 0
        assert tile_size > 0
        assert tile_size <= 32  # Should not exceed TILE_SIZE

    def test_screen_to_grid_returns_none_outside_bounds(self):
        """Should return None for coordinates outside the map."""
        from client_2d.game import GameWindow

        mock_window = create_mock_game_window()
        mock_window.room_layout = MockRoomLayout(width=20, height=15)

        # Bind real method to mock for _get_map_render_params
        mock_window._get_map_render_params = lambda: GameWindow._get_map_render_params(mock_window)

        # Test far outside bounds
        result = GameWindow._screen_to_grid(mock_window, -100, -100)
        assert result is None

        result = GameWindow._screen_to_grid(mock_window, 2000, 2000)
        assert result is None

    def test_screen_to_grid_returns_valid_coords(self):
        """Should return valid grid coordinates for points on the map."""
        from client_2d.game import GameWindow

        mock_window = create_mock_game_window()
        mock_window.room_layout = MockRoomLayout(width=20, height=15)

        # Get render params to understand the coordinate space
        params = GameWindow._get_map_render_params(mock_window)
        assert params is not None
        offset_x, offset_y, tile_size = params

        # Bind real method to mock
        mock_window._get_map_render_params = lambda: GameWindow._get_map_render_params(mock_window)

        # Test center of map
        center_screen_x = int(offset_x + 10 * tile_size + tile_size // 2)
        center_screen_y = int(offset_y + (15 - 1 - 7) * tile_size + tile_size // 2)

        result = GameWindow._screen_to_grid(mock_window, center_screen_x, center_screen_y)
        assert result is not None
        grid_x, grid_y = result

        # Should be within bounds
        assert 0 <= grid_x < 20
        assert 0 <= grid_y < 15


class TestTargetCycling:
    """Tests for _cycle_target method."""

    def test_cycle_target_sorts_by_distance(self):
        """Should cycle through targets nearest first."""
        from client_2d.game import GameWindow

        mock_window = create_mock_game_window()
        mock_window.player_x = 5
        mock_window.player_y = 5
        mock_window.selected_target = None
        mock_window.selected_enemy = 0
        mock_window.combat_log = []

        # Monster at distance 1
        monster_close = MagicMock()
        monster_close.grid_x = 5
        monster_close.grid_y = 4  # 1 tile away
        monster_close.enemy_index = 0
        monster_close.sub_type = "goblin"
        monster_close.entity_id = "monster_0"

        # Monster at distance 3
        monster_far = MagicMock()
        monster_far.grid_x = 8
        monster_far.grid_y = 5  # 3 tiles away
        monster_far.enemy_index = 1
        monster_far.sub_type = "orc"
        monster_far.entity_id = "monster_1"

        # Monster at distance 2
        monster_mid = MagicMock()
        monster_mid.grid_x = 7
        monster_mid.grid_y = 5  # 2 tiles away
        monster_mid.enemy_index = 2
        monster_mid.sub_type = "skeleton"
        monster_mid.entity_id = "monster_2"

        mock_window.entity_manager = MagicMock()
        mock_window.entity_manager.get_monsters.return_value = [
            monster_close,
            monster_far,
            monster_mid,
        ]
        mock_window.entity_manager.get_current_turn_position.return_value = (5, 5)

        # First cycle should select closest
        GameWindow._cycle_target(mock_window)
        assert mock_window.selected_target == monster_close
        assert mock_window.selected_enemy == 0

        # Second cycle should select next closest (mid)
        GameWindow._cycle_target(mock_window)
        assert mock_window.selected_target == monster_mid
        assert mock_window.selected_enemy == 2

        # Third cycle should select farthest
        GameWindow._cycle_target(mock_window)
        assert mock_window.selected_target == monster_far
        assert mock_window.selected_enemy == 1

        # Fourth cycle should wrap back to closest
        GameWindow._cycle_target(mock_window)
        assert mock_window.selected_target == monster_close

    def test_cycle_target_reverse(self):
        """Should cycle in reverse order with reverse=True."""
        from client_2d.game import GameWindow

        mock_window = create_mock_game_window()
        mock_window.player_x = 5
        mock_window.player_y = 5
        mock_window.selected_target = None
        mock_window.selected_enemy = 0
        mock_window.combat_log = []

        monster1 = MagicMock()
        monster1.grid_x = 5
        monster1.grid_y = 4
        monster1.enemy_index = 0
        monster1.sub_type = "goblin"

        monster2 = MagicMock()
        monster2.grid_x = 7
        monster2.grid_y = 5
        monster2.enemy_index = 1
        monster2.sub_type = "orc"

        mock_window.entity_manager = MagicMock()
        mock_window.entity_manager.get_monsters.return_value = [monster1, monster2]
        mock_window.entity_manager.get_current_turn_position.return_value = (5, 5)

        # Forward: should select monster1 (closest)
        GameWindow._cycle_target(mock_window, reverse=False)
        assert mock_window.selected_target == monster1

        # Reverse: should go to last (monster2)
        GameWindow._cycle_target(mock_window, reverse=True)
        assert mock_window.selected_target == monster2

    def test_cycle_target_no_monsters(self):
        """Should log message when no targets available."""
        from client_2d.game import GameWindow

        mock_window = create_mock_game_window()
        mock_window.combat_log = []

        mock_window.entity_manager = MagicMock()
        mock_window.entity_manager.get_monsters.return_value = []

        # Bind _add_combat_log to actually append
        mock_window._add_combat_log = lambda msg: mock_window.combat_log.append(msg)

        GameWindow._cycle_target(mock_window)

        assert "No targets available" in mock_window.combat_log


class TestMCPAttackEntityID:
    """Tests for MCP attack with entity ID strings."""

    def test_mcp_attack_by_index(self):
        """Should accept integer index."""
        from client_2d.game import GameWindow

        mock_window = create_mock_game_window()
        mock_window.player_x = 5
        mock_window.player_y = 5
        mock_window.selected_enemy = 0

        # Mock engine
        mock_window.engine = MagicMock()
        mock_window.engine.in_combat = True
        mock_window.engine.is_player_turn.return_value = True
        mock_window.engine.execute_attack.return_value = {
            "success": True,
            "hit": True,
            "damage": 5,
        }
        mock_window.engine.advance_turn.return_value = {"combat_ended": True}
        mock_window.engine.game_state = MagicMock()
        mock_window.engine.get_party_data.return_value = []

        # Mock entity manager
        monster = MagicMock()
        monster.grid_x = 5
        monster.grid_y = 4
        monster.enemy_index = 0
        mock_window.entity_manager = MagicMock()
        mock_window.entity_manager.get_monsters.return_value = [monster]
        mock_window.entity_manager.get_current_turn_position.return_value = (5, 5)

        # Mock other required attributes
        mock_window.processing_enemy_turn = False
        mock_window.combat_log = []
        mock_window.current_mode = MagicMock()
        mock_window.party_spread = False
        mock_window.party_positions = []
        mock_window._state_renderer = None

        result = GameWindow._mcp_attack(mock_window, 0)
        # Should not return an error message
        assert "Invalid" not in result
        assert "Unknown" not in result

    def test_mcp_attack_by_entity_id(self):
        """Should accept entity ID string."""
        from client_2d.game import GameWindow

        mock_window = create_mock_game_window()
        mock_window.player_x = 5
        mock_window.player_y = 5
        mock_window.selected_enemy = 0

        mock_window.engine = MagicMock()
        mock_window.engine.in_combat = True
        mock_window.engine.is_player_turn.return_value = True
        mock_window.engine.execute_attack.return_value = {
            "success": True,
            "hit": True,
            "damage": 5,
        }
        mock_window.engine.advance_turn.return_value = {"combat_ended": True}
        mock_window.engine.game_state = MagicMock()
        mock_window.engine.get_party_data.return_value = []

        monster = MagicMock()
        monster.grid_x = 5
        monster.grid_y = 4
        monster.enemy_index = 0
        monster.entity_id = "monster_0"
        monster.sub_type = "goblin"
        mock_window.entity_manager = MagicMock()
        mock_window.entity_manager.get_monsters.return_value = [monster]
        mock_window.entity_manager.get_current_turn_position.return_value = (5, 5)

        mock_window.processing_enemy_turn = False
        mock_window.combat_log = []
        mock_window.current_mode = MagicMock()
        mock_window.party_spread = False
        mock_window.party_positions = []
        mock_window._state_renderer = None

        # Test with full entity ID format
        result = GameWindow._mcp_attack(mock_window, "goblin_0")
        assert "Unknown target" not in result

    def test_mcp_attack_invalid_entity_id(self):
        """Should return error for invalid entity ID."""
        from client_2d.game import GameWindow

        mock_window = create_mock_game_window()

        mock_window.engine = MagicMock()
        mock_window.engine.in_combat = True
        mock_window.engine.is_player_turn.return_value = True

        monster = MagicMock()
        monster.entity_id = "monster_0"
        monster.sub_type = "goblin"
        mock_window.entity_manager = MagicMock()
        mock_window.entity_manager.get_monsters.return_value = [monster]

        result = GameWindow._mcp_attack(mock_window, "nonexistent_enemy")
        assert "Unknown target" in result
        assert "Valid targets" in result

    def test_mcp_attack_out_of_range(self):
        """Should return error when target is out of melee range."""
        from client_2d.game import GameWindow

        mock_window = create_mock_game_window()
        mock_window.player_x = 5
        mock_window.player_y = 5

        mock_window.engine = MagicMock()
        mock_window.engine.in_combat = True
        mock_window.engine.is_player_turn.return_value = True
        mock_window.engine.get_current_turn_state.return_value = MagicMock(
            movement_remaining=30
        )

        monster = MagicMock()
        monster.grid_x = 10  # 5 tiles away
        monster.grid_y = 5
        monster.enemy_index = 0
        mock_window.entity_manager = MagicMock()
        mock_window.entity_manager.get_monsters.return_value = [monster]
        mock_window.entity_manager.get_current_turn_position.return_value = (5, 5)

        result = GameWindow._mcp_attack(mock_window, 0)
        assert "not in melee range" in result


class TestInRangeDetection:
    """Tests for melee range detection in visual feedback."""

    def test_adjacent_is_in_range(self):
        """Adjacent tiles (distance 1) should be in range."""
        from dnd_engine.core.distance import chebyshev_distance

        # All 8 adjacent directions
        test_cases = [
            (5, 4),  # North
            (5, 6),  # South
            (4, 5),  # West
            (6, 5),  # East
            (4, 4),  # NW
            (6, 4),  # NE
            (4, 6),  # SW
            (6, 6),  # SE
        ]

        combatant_x, combatant_y = 5, 5

        for target_x, target_y in test_cases:
            distance = chebyshev_distance(combatant_x, combatant_y, target_x, target_y)
            assert distance <= 1, f"({target_x}, {target_y}) should be adjacent"

    def test_distance_2_is_out_of_range(self):
        """Distance 2+ should be out of melee range."""
        from dnd_engine.core.distance import chebyshev_distance

        combatant_x, combatant_y = 5, 5
        target_x, target_y = 7, 5  # 2 tiles east

        distance = chebyshev_distance(combatant_x, combatant_y, target_x, target_y)
        assert distance > 1
