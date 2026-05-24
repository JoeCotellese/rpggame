# ABOUTME: Unit tests for the StateRenderer class.
# ABOUTME: Validates ASCII map generation, fog-of-war rendering, and JSON output.

"""Tests for the StateRenderer class."""

import json

import pytest
from client_2d.core.constants import LightingState
from client_2d.systems.fog_of_war import FogOfWarSystem
from client_2d.testing.state_renderer import Entity, StateRenderer


class TestEntity:
    """Tests for Entity dataclass."""

    def test_from_tuple_monster(self):
        """Test creating Entity from monster tuple."""
        data = (5, 3, "monster:goblin", None)
        entity = Entity.from_tuple(data, 0)

        assert entity.x == 5
        assert entity.y == 3
        assert entity.entity_type == "monster"
        assert entity.entity_id == "goblin"

    def test_from_tuple_item(self):
        """Test creating Entity from item tuple."""
        data = (10, 7, "item:potion_of_healing", None)
        entity = Entity.from_tuple(data, 1)

        assert entity.x == 10
        assert entity.y == 7
        assert entity.entity_type == "item"
        assert entity.entity_id == "potion_of_healing"

    def test_from_tuple_unknown_format(self):
        """Test creating Entity from malformed tuple."""
        data = (2, 2, "something", None)
        entity = Entity.from_tuple(data, 5)

        assert entity.entity_type == "something"
        assert entity.entity_id == "entity_5"


class TestStateRendererAsciiMap:
    """Tests for ASCII map rendering."""

    @pytest.fixture
    def small_room(self) -> list[list[int]]:
        """Create a simple 5x5 room with walls on edges."""
        return [
            [1, 1, 1, 1, 1],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 1, 1, 1, 1],
        ]

    @pytest.fixture
    def fog_all_bright(self) -> FogOfWarSystem:
        """Create fog system with all tiles bright."""
        fog = FogOfWarSystem(width=5, height=5)
        for y in range(5):
            for x in range(5):
                fog.set_visibility(x, y, LightingState.BRIGHT)
        return fog

    @pytest.fixture
    def fog_partial(self) -> FogOfWarSystem:
        """Create fog system with mixed visibility."""
        fog = FogOfWarSystem(width=5, height=5)
        # Center area bright
        for y in range(1, 4):
            for x in range(1, 4):
                fog.set_visibility(x, y, LightingState.BRIGHT)
        # Edges dim
        for x in range(5):
            fog.set_visibility(x, 0, LightingState.DIM)
            fog.set_visibility(x, 4, LightingState.DIM)
        for y in range(5):
            fog.set_visibility(0, y, LightingState.DIM)
            fog.set_visibility(4, y, LightingState.DIM)
        return fog

    def test_render_empty_room_player_center(
        self, small_room: list[list[int]], fog_all_bright: FogOfWarSystem
    ):
        """Test rendering player in center of empty room."""
        renderer = StateRenderer(width=5, height=5)
        ascii_map = renderer.render_ascii_map(
            room=small_room,
            player_x=2,
            player_y=2,
            entities=[],
            fog=fog_all_bright,
        )

        lines = ascii_map.split("\n")
        assert len(lines) == 5

        # Player should be at center
        assert lines[2][2] == "@"

        # Walls around edges
        assert lines[0] == "#####"
        assert lines[4] == "#####"

        # Floor tiles where not player or wall
        assert lines[2][1] == "."
        assert lines[2][3] == "."

    def test_render_with_entity(
        self, small_room: list[list[int]], fog_all_bright: FogOfWarSystem
    ):
        """Test rendering with an entity on the map."""
        renderer = StateRenderer(width=5, height=5)
        entities = [Entity(x=3, y=2, entity_type="monster", entity_id="goblin")]

        ascii_map = renderer.render_ascii_map(
            room=small_room,
            player_x=1,
            player_y=2,
            entities=entities,
            fog=fog_all_bright,
        )

        lines = ascii_map.split("\n")
        # Player at (1,2), goblin at (3,2)
        assert lines[2][1] == "@"
        assert lines[2][3] == "A"  # First entity gets 'A'

    def test_render_multiple_entities(
        self, small_room: list[list[int]], fog_all_bright: FogOfWarSystem
    ):
        """Test rendering multiple entities get sequential symbols."""
        renderer = StateRenderer(width=5, height=5)
        entities = [
            Entity(x=1, y=1, entity_type="monster", entity_id="goblin"),
            Entity(x=3, y=1, entity_type="item", entity_id="sword"),
            Entity(x=3, y=3, entity_type="monster", entity_id="skeleton"),
        ]

        ascii_map = renderer.render_ascii_map(
            room=small_room,
            player_x=2,
            player_y=2,
            entities=entities,
            fog=fog_all_bright,
        )

        lines = ascii_map.split("\n")
        assert lines[1][1] == "A"  # goblin
        assert lines[1][3] == "B"  # sword
        assert lines[3][3] == "C"  # skeleton

    def test_fog_unexplored_shows_space(
        self, small_room: list[list[int]]
    ):
        """Test unexplored tiles render as spaces."""
        fog = FogOfWarSystem(width=5, height=5)
        # Only reveal center tile
        fog.set_visibility(2, 2, LightingState.BRIGHT)

        renderer = StateRenderer(width=5, height=5)
        ascii_map = renderer.render_ascii_map(
            room=small_room,
            player_x=2,
            player_y=2,
            entities=[],
            fog=fog,
        )

        lines = ascii_map.split("\n")
        # Player visible
        assert lines[2][2] == "@"
        # Surrounding tiles unexplored (space)
        assert lines[0][0] == " "
        assert lines[1][1] == " "

    def test_fog_dim_shows_comma(
        self, small_room: list[list[int]]
    ):
        """Test dim light tiles show comma for floor."""
        fog = FogOfWarSystem(width=5, height=5)
        # Set some tiles to dim
        fog.set_visibility(1, 1, LightingState.DIM)
        fog.set_visibility(2, 2, LightingState.BRIGHT)

        renderer = StateRenderer(width=5, height=5)
        ascii_map = renderer.render_ascii_map(
            room=small_room,
            player_x=2,
            player_y=2,
            entities=[],
            fog=fog,
        )

        lines = ascii_map.split("\n")
        assert lines[1][1] == ","  # Dim floor

    def test_fog_dark_shows_colon(
        self, small_room: list[list[int]]
    ):
        """Test dark (remembered) tiles show colon for floor."""
        fog = FogOfWarSystem(width=5, height=5)
        fog.set_visibility(1, 1, LightingState.DARK)
        fog.set_visibility(2, 2, LightingState.BRIGHT)

        renderer = StateRenderer(width=5, height=5)
        ascii_map = renderer.render_ascii_map(
            room=small_room,
            player_x=2,
            player_y=2,
            entities=[],
            fog=fog,
        )

        lines = ascii_map.split("\n")
        assert lines[1][1] == ":"  # Dark (remembered) floor

    def test_entity_hidden_in_unexplored(
        self, small_room: list[list[int]]
    ):
        """Test entities in unexplored areas are not rendered."""
        fog = FogOfWarSystem(width=5, height=5)
        # Only player area visible
        fog.set_visibility(2, 2, LightingState.BRIGHT)

        renderer = StateRenderer(width=5, height=5)
        entities = [Entity(x=1, y=1, entity_type="monster", entity_id="hidden")]

        ascii_map = renderer.render_ascii_map(
            room=small_room,
            player_x=2,
            player_y=2,
            entities=entities,
            fog=fog,
        )

        lines = ascii_map.split("\n")
        # Entity at (1,1) should not be visible
        assert lines[1][1] == " "  # Unexplored, not 'A'


class TestStateRendererLegend:
    """Tests for legend building."""

    def test_legend_includes_player(self):
        """Test legend always includes player."""
        renderer = StateRenderer(width=5, height=5)
        fog = FogOfWarSystem(width=5, height=5)
        for y in range(5):
            for x in range(5):
                fog.set_visibility(x, y, LightingState.BRIGHT)

        room = [[0] * 5 for _ in range(5)]

        # Render to assign symbols
        renderer.render_ascii_map(room, 2, 2, [], fog)
        legend = renderer.build_legend([])

        assert "@" in legend
        assert legend["@"] == "player"

    def test_legend_includes_rendered_entities(self):
        """Test legend includes entities that were rendered."""
        renderer = StateRenderer(width=5, height=5)
        fog = FogOfWarSystem(width=5, height=5)
        for y in range(5):
            for x in range(5):
                fog.set_visibility(x, y, LightingState.BRIGHT)

        room = [[0] * 5 for _ in range(5)]
        entities = [
            Entity(x=1, y=1, entity_type="monster", entity_id="goblin"),
            Entity(x=3, y=3, entity_type="item", entity_id="sword"),
        ]

        renderer.render_ascii_map(room, 2, 2, entities, fog)
        legend = renderer.build_legend(entities)

        assert "A" in legend
        assert legend["A"] == "monster:goblin"
        assert "B" in legend
        assert legend["B"] == "item:sword"


class TestStateRendererJsonOutput:
    """Tests for JSON state output."""

    @pytest.fixture
    def simple_game_state(self):
        """Create a simple game state for testing."""
        room = [
            [1, 1, 1, 1, 1],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 1, 1, 1, 1],
        ]
        fog = FogOfWarSystem(width=5, height=5)
        for y in range(5):
            for x in range(5):
                fog.set_visibility(x, y, LightingState.BRIGHT)

        entities = [
            Entity(x=3, y=2, entity_type="monster", entity_id="goblin"),
        ]
        return room, fog, entities

    def test_render_state_includes_required_fields(self, simple_game_state):
        """Test render_state output has all required fields."""
        room, fog, entities = simple_game_state
        renderer = StateRenderer(width=5, height=5)

        state = renderer.render_state(
            room=room,
            player_x=1,
            player_y=2,
            entities=entities,
            fog=fog,
            turn=5,
        )

        assert "turn" in state
        assert "map" in state
        assert "legend" in state
        assert "player" in state
        assert "visible_entities" in state
        assert "available_actions" in state

    def test_render_state_player_info(self, simple_game_state):
        """Test player info in state output."""
        room, fog, entities = simple_game_state
        renderer = StateRenderer(width=5, height=5)

        state = renderer.render_state(
            room=room,
            player_x=1,
            player_y=2,
            entities=entities,
            fog=fog,
            player_hp=25,
            player_max_hp=30,
            light_source="lantern",
        )

        assert state["player"]["position"] == [1, 2]
        assert state["player"]["hp"] == 25
        assert state["player"]["max_hp"] == 30
        assert state["player"]["light_source"] == "lantern"

    def test_render_state_visible_entities(self, simple_game_state):
        """Test visible entities in state output."""
        room, fog, entities = simple_game_state
        renderer = StateRenderer(width=5, height=5)

        state = renderer.render_state(
            room=room,
            player_x=1,
            player_y=2,
            entities=entities,
            fog=fog,
        )

        assert "goblin" in state["visible_entities"]
        goblin = state["visible_entities"]["goblin"]
        assert goblin["type"] == "monster"
        assert goblin["position"] == [3, 2]
        assert goblin["distance"] == 2  # Manhattan distance
        assert goblin["direction"] == "east"

    def test_render_state_available_actions(self, simple_game_state):
        """Test available actions are computed correctly."""
        room, fog, entities = simple_game_state
        renderer = StateRenderer(width=5, height=5)

        # Player at (1,2) can move north, south, east but not west (wall)
        state = renderer.render_state(
            room=room,
            player_x=1,
            player_y=2,
            entities=entities,
            fog=fog,
        )

        actions = state["available_actions"]
        assert "move_north" in actions
        assert "move_south" in actions
        assert "move_east" in actions
        assert "move_west" not in actions  # Wall at x=0
        assert "wait" in actions

    def test_render_state_attack_adjacent_monster(self, simple_game_state):
        """Test attack action available for adjacent monster."""
        room, fog, _ = simple_game_state
        renderer = StateRenderer(width=5, height=5)

        # Place monster adjacent to player
        entities = [
            Entity(x=2, y=2, entity_type="monster", entity_id="goblin"),
        ]

        state = renderer.render_state(
            room=room,
            player_x=1,
            player_y=2,
            entities=entities,
            fog=fog,
        )

        assert "attack_goblin" in state["available_actions"]

    def test_to_json_produces_valid_json(self, simple_game_state):
        """Test to_json produces valid JSON string."""
        room, fog, entities = simple_game_state
        renderer = StateRenderer(width=5, height=5)

        json_str = renderer.to_json(
            room=room,
            player_x=1,
            player_y=2,
            entities=entities,
            fog=fog,
        )

        # Should parse without error
        parsed = json.loads(json_str)
        assert "map" in parsed
        assert "player" in parsed


class TestStateRendererDirections:
    """Tests for direction calculation."""

    def test_direction_north(self):
        """Test entity north of player."""
        renderer = StateRenderer(width=5, height=5)
        # _get_direction is called with dx, dy from player to entity
        # Entity north means dy < 0
        direction = renderer._get_direction(0, -2)
        assert direction == "north"

    def test_direction_south_east(self):
        """Test entity south-east of player."""
        renderer = StateRenderer(width=5, height=5)
        direction = renderer._get_direction(2, 3)
        assert direction == "south-east"

    def test_direction_here(self):
        """Test entity at same position."""
        renderer = StateRenderer(width=5, height=5)
        direction = renderer._get_direction(0, 0)
        assert direction == "here"


class TestStateRendererPlayerTileOverlay:
    """Regression tests for issue #579.

    When the @ cursor occupies the same tile as another entity, the entity
    must still appear in the legend and Visible Entities, even though @
    overlays the entity glyph on the ASCII map.
    """

    @pytest.fixture
    def bright_room(self) -> tuple[list[list[int]], FogOfWarSystem]:
        """Create a 5x5 open room with all tiles bright."""
        room = [[0] * 5 for _ in range(5)]
        fog = FogOfWarSystem(width=5, height=5)
        for y in range(5):
            for x in range(5):
                fog.set_visibility(x, y, LightingState.BRIGHT)
        return room, fog

    def test_ascii_map_shows_player_when_entity_on_same_tile(
        self, bright_room: tuple[list[list[int]], FogOfWarSystem]
    ):
        """@ overlay is preserved when an entity shares the player's tile."""
        room, fog = bright_room
        renderer = StateRenderer(width=5, height=5)
        entities = [Entity(x=2, y=2, entity_type="party", entity_id="wizard_1")]

        ascii_map = renderer.render_ascii_map(
            room=room, player_x=2, player_y=2, entities=entities, fog=fog
        )

        lines = ascii_map.split("\n")
        assert lines[2][2] == "@"

    def test_legend_includes_entity_on_player_tile(
        self, bright_room: tuple[list[list[int]], FogOfWarSystem]
    ):
        """Legend lists entities co-located with the player."""
        room, fog = bright_room
        renderer = StateRenderer(width=5, height=5)
        entities = [Entity(x=2, y=2, entity_type="party", entity_id="wizard_1")]

        state = renderer.render_state(
            room=room, player_x=2, player_y=2, entities=entities, fog=fog
        )

        assert "party:wizard_1" in state["legend"].values()

    def test_visible_entities_includes_entity_on_player_tile(
        self, bright_room: tuple[list[list[int]], FogOfWarSystem]
    ):
        """Visible Entities reports co-located entities with distance 0/'here'."""
        room, fog = bright_room
        renderer = StateRenderer(width=5, height=5)
        entities = [Entity(x=2, y=2, entity_type="party", entity_id="wizard_1")]

        state = renderer.render_state(
            room=room, player_x=2, player_y=2, entities=entities, fog=fog
        )

        assert "wizard_1" in state["visible_entities"]
        wizard = state["visible_entities"]["wizard_1"]
        assert wizard["distance"] == 0
        assert wizard["direction"] == "here"
        assert wizard["position"] == [2, 2]
        assert wizard["type"] == "party"
