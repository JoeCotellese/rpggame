# ABOUTME: Unit tests for GridRenderer and CompactGridRenderer
# ABOUTME: Tests rendering, viewport, fog of war, and entity display

import pytest

from dnd_engine.spatial import (
    Position,
    TileMap,
    TileType,
    Tile,
    create_map_from_string,
)
from dnd_engine.ui.grid_renderer import (
    GridRenderer,
    CompactGridRenderer,
    RenderConfig,
)


class TestGridRenderer:
    """Tests for GridRenderer class."""

    def test_render_simple_map(self):
        """Test rendering a simple map to string."""
        result = create_map_from_string("""
#####
#...#
#.@.#
#...#
#####
""")
        # Reveal all tiles for rendering
        result.tile_map.reveal_all()

        renderer = GridRenderer(config=RenderConfig(
            viewport_width=5,
            viewport_height=5,
            show_fog_of_war=False,
        ))

        output = renderer.render_to_string(result.tile_map)
        lines = output.strip().split("\n")

        assert len(lines) == 5
        assert lines[0] == "#####"
        assert lines[2] == "#...#"  # No entities spawned yet

    def test_render_with_entity(self):
        """Test rendering with a player entity."""
        result = create_map_from_string("""
#####
#...#
#...#
#####
""")
        result.tile_map.reveal_all()
        result.tile_map.add_entity("player", Position(2, 1), display_char="@", is_player=True)

        renderer = GridRenderer(config=RenderConfig(
            viewport_width=5,
            viewport_height=4,
            show_fog_of_war=False,
        ))

        output = renderer.render_to_string(result.tile_map)
        assert "@" in output

    def test_viewport_centering(self):
        """Test viewport centers on player."""
        # Create a larger map
        result = create_map_from_string("""
####################
#..................#
#..................#
#..................#
#..................#
#..................#
#..................#
#..................#
#..................#
####################
""")
        result.tile_map.reveal_all()
        # Place player in middle
        result.tile_map.add_entity("player", Position(10, 5), display_char="@", is_player=True)

        renderer = GridRenderer(config=RenderConfig(
            viewport_width=10,
            viewport_height=5,
            center_on_player=True,
            show_fog_of_war=False,
        ))

        output = renderer.render_to_string(result.tile_map, player_id="player")

        # Player should be visible (roughly centered)
        assert "@" in output

    def test_fog_of_war_unexplored(self):
        """Test that unexplored tiles render as space."""
        result = create_map_from_string("""
#####
#...#
#####
""")
        # Don't reveal - all unexplored

        renderer = GridRenderer(config=RenderConfig(
            viewport_width=5,
            viewport_height=3,
            show_fog_of_war=True,
        ))

        output = renderer.render_to_string(result.tile_map)

        # Should be all spaces (unexplored)
        assert output.strip() == ""  # All spaces get stripped

    def test_fog_of_war_visible(self):
        """Test that visible tiles render normally."""
        result = create_map_from_string("""
#####
#...#
#####
""")
        # Reveal some tiles
        result.tile_map.set_visible(Position(1, 1))
        result.tile_map.set_visible(Position(2, 1))
        result.tile_map.set_visible(Position(3, 1))

        renderer = GridRenderer(config=RenderConfig(
            viewport_width=5,
            viewport_height=3,
            show_fog_of_war=True,
        ))

        output = renderer.render_to_string(result.tile_map)

        # Visible tiles should show
        assert "." in output

    def test_render_config_defaults(self):
        """Test RenderConfig has sensible defaults."""
        config = RenderConfig()

        assert config.viewport_width > 0
        assert config.viewport_height > 0
        assert config.show_fog_of_war is True
        assert config.center_on_player is True

    def test_entity_colors_different(self):
        """Test that player and enemy colors are configured differently."""
        config = RenderConfig()

        assert config.player_color != config.enemy_color

    def test_set_viewport_manually(self):
        """Test manually setting viewport position."""
        result = create_map_from_string("""
##########
#........#
#........#
##########
""")
        result.tile_map.reveal_all()

        renderer = GridRenderer(config=RenderConfig(
            viewport_width=5,
            viewport_height=4,
            show_fog_of_war=False,
        ))

        # Set viewport to offset position
        renderer.set_viewport(3, 0)

        output = renderer.render_to_string(result.tile_map)
        lines = output.split("\n")

        # Should start from x=3
        assert lines[0] == "#####"  # Still shows walls

    def test_items_render_as_dollar(self):
        """Test that tiles with items show $ symbol."""
        result = create_map_from_string("""
#####
#...#
#####
""")
        result.tile_map.reveal_all()

        # Add item to a tile
        tile = result.tile_map.get_tile(Position(2, 1))
        tile.item_ids.append("sword_1")

        renderer = GridRenderer(config=RenderConfig(
            viewport_width=5,
            viewport_height=3,
            show_fog_of_war=False,
        ))

        output = renderer.render_to_string(result.tile_map)
        assert "$" in output


class TestCompactGridRenderer:
    """Tests for CompactGridRenderer class."""

    def test_compact_render_basic(self):
        """Test basic compact rendering."""
        result = create_map_from_string("""
#####
#...#
#.@.#
#...#
#####
""")
        result.tile_map.reveal_all()

        renderer = CompactGridRenderer(width=5, height=5, show_fog=False)
        output = renderer.render_to_string(result.tile_map)

        lines = output.split("\n")
        assert len(lines) == 5
        assert "#" in lines[0]

    def test_compact_center_on_position(self):
        """Test centering on a specific position."""
        # Larger map
        tm = TileMap(width=20, height=20, name="Test")
        tm.reveal_all()
        tm.add_entity("player", Position(15, 15), display_char="@")

        renderer = CompactGridRenderer(width=10, height=10, show_fog=False)
        output = renderer.render_to_string(tm, center_pos=Position(15, 15))

        # Player should be visible
        assert "@" in output

    def test_compact_fog_of_war(self):
        """Test compact renderer respects fog of war."""
        result = create_map_from_string("""
#####
#...#
#####
""")
        # Don't reveal

        renderer = CompactGridRenderer(width=5, height=3, show_fog=True)
        output = renderer.render_to_string(result.tile_map)

        # All unexplored = spaces
        assert "#" not in output
        assert "." not in output

    def test_compact_render_to_text(self):
        """Test rendering to Rich Text object."""
        result = create_map_from_string("""
#####
#...#
#####
""")
        result.tile_map.reveal_all()

        renderer = CompactGridRenderer(width=5, height=3, show_fog=False)
        text = renderer.render_to_text(result.tile_map)

        # Should be a Text object with content
        assert len(text) > 0

    def test_compact_entities_displayed(self):
        """Test entities are displayed in compact view."""
        result = create_map_from_string("""
#####
#...#
#####
""")
        result.tile_map.reveal_all()
        result.tile_map.add_entity("goblin", Position(2, 1), display_char="G")

        renderer = CompactGridRenderer(width=5, height=3, show_fog=False)
        output = renderer.render_to_string(result.tile_map)

        assert "G" in output

    def test_compact_out_of_bounds(self):
        """Test compact renderer handles out of bounds gracefully."""
        tm = TileMap(width=3, height=3, name="Small")
        tm.reveal_all()

        renderer = CompactGridRenderer(width=10, height=10, show_fog=False)
        output = renderer.render_to_string(tm)

        # Should render without error, with spaces for out of bounds
        assert len(output) > 0


class TestRenderIntegration:
    """Integration tests for rendering workflow."""

    def test_load_and_render_map(self):
        """Test loading a map and rendering it."""
        map_str = """
##########
#........#
#..@..G..#
#........#
#...+....#
#........#
##########
"""
        result = create_map_from_string(map_str, "Test Dungeon")
        result.tile_map.reveal_all()

        # Spawn entities
        from dnd_engine.spatial import MapLoader
        loader = MapLoader()
        loader.spawn_entities(result)

        # Render
        renderer = CompactGridRenderer(width=10, height=7, show_fog=False)
        output = renderer.render_to_string(result.tile_map)

        # Should show map elements
        assert "#" in output
        assert "." in output
        assert "+" in output
        # Entities should be spawned
        assert "@" in output or "G" in output

    def test_render_with_multiple_entity_types(self):
        """Test rendering different entity types."""
        tm = TileMap(width=10, height=5, name="Test")
        tm.reveal_all()

        tm.add_entity("player", Position(2, 2), display_char="@", is_player=True)
        tm.add_entity("goblin", Position(4, 2), display_char="G", is_player=False)
        tm.add_entity("skeleton", Position(6, 2), display_char="S", is_player=False)

        renderer = CompactGridRenderer(width=10, height=5, show_fog=False)
        output = renderer.render_to_string(tm)

        assert "@" in output
        assert "G" in output
        assert "S" in output
