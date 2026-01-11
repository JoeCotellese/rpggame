# ABOUTME: Renders game state as ASCII maps and JSON for headless testing.
# ABOUTME: Enables Claude-driven playtesting by providing structured state output.

"""State renderer for converting game state to ASCII + JSON format."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from client_2d.core.constants import LightingState
from client_2d.systems.fog_of_war import FogOfWarSystem


@dataclass
class Entity:
    """Represents an entity on the map for rendering."""

    x: int
    y: int
    entity_type: str
    entity_id: str
    symbol: str = ""

    @classmethod
    def from_tuple(
        cls, data: tuple[int, int, str, Any], entity_num: int
    ) -> Entity:
        """Create Entity from visual_test.py format (x, y, type_string, texture)."""
        x, y, type_string, _ = data
        # type_string is like "monster:goblin" or "item:potion_of_healing"
        parts = type_string.split(":", 1)
        entity_type = parts[0] if parts else "unknown"
        entity_id = parts[1] if len(parts) > 1 else f"entity_{entity_num}"
        return cls(x=x, y=y, entity_type=entity_type, entity_id=entity_id)


@dataclass
class StateRenderer:
    """Renders game state as ASCII maps and structured JSON.

    The renderer converts game state into a format suitable for
    Claude-driven playtesting:
    - ASCII map showing spatial relationships
    - JSON metadata with entity details and available actions

    ASCII Map Symbols:
        @ = Player
        A-Z = Entities (mapped in legend)
        # = Wall
        . = Floor (bright light)
        , = Floor (dim light)
        : = Floor (dark/remembered)
        ? = Unexplored
        ~ = Water/difficult terrain
        + = Closed door
        ' = Open door
    """

    width: int
    height: int
    _entity_symbols: dict[str, str] = field(default_factory=dict)
    _symbol_counter: int = field(default=0)

    # Symbol mappings for terrain and lighting
    WALL_CHAR = "#"
    FLOOR_BRIGHT = "."
    FLOOR_DIM = ","
    FLOOR_DARK = ":"
    UNEXPLORED = " "
    PLAYER_CHAR = "@"

    # Entity type prefixes for symbol assignment
    ENTITY_SYMBOLS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def render_ascii_map(
        self,
        room: list[list[int]],
        player_x: int,
        player_y: int,
        entities: list[Entity],
        fog: FogOfWarSystem,
    ) -> str:
        """Render the game state as an ASCII map.

        Args:
            room: 2D grid where 1=wall, 0=floor
            player_x: Player X coordinate
            player_y: Player Y coordinate
            entities: List of Entity objects on the map
            fog: FogOfWarSystem for visibility states

        Returns:
            ASCII string representation of the visible map
        """
        # Reset symbol assignments for fresh render
        self._entity_symbols = {}
        self._symbol_counter = 0

        # Build entity position lookup
        entity_at: dict[tuple[int, int], Entity] = {}
        for entity in entities:
            entity_at[(entity.x, entity.y)] = entity

        lines = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                char = self._get_tile_char(
                    x, y, room, player_x, player_y, entity_at, fog
                )
                row.append(char)
            lines.append("".join(row))

        return "\n".join(lines)

    def _get_tile_char(
        self,
        x: int,
        y: int,
        room: list[list[int]],
        player_x: int,
        player_y: int,
        entity_at: dict[tuple[int, int], Entity],
        fog: FogOfWarSystem,
    ) -> str:
        """Get the character to display at a given tile position."""
        # Player always visible at their position
        if x == player_x and y == player_y:
            return self.PLAYER_CHAR

        # Check visibility
        visibility = fog.get_visibility(x, y)
        if visibility == LightingState.UNEXPLORED:
            return self.UNEXPLORED

        # Check for entity at this position (only show in bright/dim light)
        if visibility in (LightingState.BRIGHT, LightingState.DIM):
            entity = entity_at.get((x, y))
            if entity:
                return self._get_entity_symbol(entity)

        # Terrain tile with lighting state
        is_wall = room[y][x] == 1 if y < len(room) and x < len(room[0]) else False

        if is_wall:
            return self.WALL_CHAR

        # Floor with lighting-based character
        if visibility == LightingState.BRIGHT:
            return self.FLOOR_BRIGHT
        elif visibility == LightingState.DIM:
            return self.FLOOR_DIM
        else:  # DARK
            return self.FLOOR_DARK

    def _get_entity_symbol(self, entity: Entity) -> str:
        """Get or assign a symbol for an entity."""
        key = f"{entity.entity_type}:{entity.entity_id}"
        if key not in self._entity_symbols:
            if self._symbol_counter < len(self.ENTITY_SYMBOLS):
                symbol = self.ENTITY_SYMBOLS[self._symbol_counter]
                self._symbol_counter += 1
            else:
                # Fallback if we run out of letters
                symbol = "?"
            self._entity_symbols[key] = symbol
            entity.symbol = symbol
        return self._entity_symbols[key]

    def build_legend(self, entities: list[Entity]) -> dict[str, str]:
        """Build a legend mapping symbols to entity descriptions.

        Args:
            entities: List of entities that were rendered

        Returns:
            Dict mapping symbols to entity type:id strings
        """
        legend = {"@": "player"}
        for entity in entities:
            key = f"{entity.entity_type}:{entity.entity_id}"
            if key in self._entity_symbols:
                symbol = self._entity_symbols[key]
                legend[symbol] = key
        return legend

    def render_state(
        self,
        room: list[list[int]],
        player_x: int,
        player_y: int,
        entities: list[Entity],
        fog: FogOfWarSystem,
        turn: int = 0,
        light_source: str = "torch",
        player_hp: int = 30,
        player_max_hp: int = 30,
    ) -> dict[str, Any]:
        """Render complete game state as a JSON-serializable dict.

        Args:
            room: 2D grid where 1=wall, 0=floor
            player_x: Player X coordinate
            player_y: Player Y coordinate
            entities: List of Entity objects on the map
            fog: FogOfWarSystem for visibility states
            turn: Current turn number
            light_source: Current light source type
            player_hp: Player current HP
            player_max_hp: Player maximum HP

        Returns:
            Dict with map, legend, player info, visible entities, and actions
        """
        # Render ASCII map
        ascii_map = self.render_ascii_map(room, player_x, player_y, entities, fog)

        # Build legend
        legend = self.build_legend(entities)

        # Find visible entities with details
        visible_entities = {}
        for entity in entities:
            visibility = fog.get_visibility(entity.x, entity.y)
            if visibility in (LightingState.BRIGHT, LightingState.DIM):
                key = f"{entity.entity_type}:{entity.entity_id}"
                if key in self._entity_symbols:
                    # Calculate distance and direction from player
                    # Use Chebyshev distance (D&D 5E: diagonal = 1 square)
                    dx = entity.x - player_x
                    dy = entity.y - player_y
                    distance = max(abs(dx), abs(dy))  # Chebyshev distance
                    direction = self._get_direction(dx, dy)

                    visible_entities[entity.entity_id] = {
                        "type": entity.entity_type,
                        "id": entity.entity_id,
                        "symbol": self._entity_symbols[key],
                        "position": [entity.x, entity.y],
                        "distance": distance,
                        "direction": direction,
                    }

        # Determine available actions based on state
        available_actions = self._compute_available_actions(
            room, player_x, player_y, entities, fog
        )

        return {
            "turn": turn,
            "map": ascii_map,
            "legend": legend,
            "player": {
                "position": [player_x, player_y],
                "hp": player_hp,
                "max_hp": player_max_hp,
                "light_source": light_source,
            },
            "visible_entities": visible_entities,
            "available_actions": available_actions,
            "explored_tiles": fog.explored_count,
            "total_tiles": fog.total_tiles,
        }

    def _get_direction(self, dx: int, dy: int) -> str:
        """Get cardinal direction from delta."""
        if dx == 0 and dy == 0:
            return "here"

        directions = []
        if dy < 0:
            directions.append("north")
        elif dy > 0:
            directions.append("south")
        if dx > 0:
            directions.append("east")
        elif dx < 0:
            directions.append("west")

        return "-".join(directions) if directions else "here"

    def _compute_available_actions(
        self,
        room: list[list[int]],
        player_x: int,
        player_y: int,
        entities: list[Entity],
        fog: FogOfWarSystem,
    ) -> list[str]:
        """Compute available actions based on current state."""
        actions = []

        # Check movement in each direction
        directions = [
            ("move_north", 0, -1),
            ("move_south", 0, 1),
            ("move_east", 1, 0),
            ("move_west", -1, 0),
        ]

        for action_name, dx, dy in directions:
            new_x = player_x + dx
            new_y = player_y + dy
            if self._can_move_to(room, new_x, new_y):
                actions.append(action_name)

        # Check for adjacent entities (interact/attack)
        for entity in entities:
            dx = abs(entity.x - player_x)
            dy = abs(entity.y - player_y)
            if dx + dy == 1:  # Adjacent
                visibility = fog.get_visibility(entity.x, entity.y)
                if visibility in (LightingState.BRIGHT, LightingState.DIM):
                    if entity.entity_type == "monster":
                        actions.append(f"attack_{entity.entity_id}")
                    else:
                        actions.append(f"interact_{entity.entity_id}")

        # Always can wait
        actions.append("wait")

        return actions

    def _can_move_to(self, room: list[list[int]], x: int, y: int) -> bool:
        """Check if player can move to a position."""
        if x < 0 or y < 0:
            return False
        if y >= len(room) or x >= len(room[0]):
            return False
        return room[y][x] == 0  # 0 = floor, 1 = wall

    def to_json(
        self,
        room: list[list[int]],
        player_x: int,
        player_y: int,
        entities: list[Entity],
        fog: FogOfWarSystem,
        **kwargs: Any,
    ) -> str:
        """Render state and return as JSON string.

        Args:
            room: 2D grid where 1=wall, 0=floor
            player_x: Player X coordinate
            player_y: Player Y coordinate
            entities: List of Entity objects
            fog: FogOfWarSystem
            **kwargs: Additional args passed to render_state

        Returns:
            JSON string of the rendered state
        """
        state = self.render_state(
            room, player_x, player_y, entities, fog, **kwargs
        )
        return json.dumps(state, indent=2)
