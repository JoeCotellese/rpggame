# ABOUTME: ASCII grid renderer for 2D dungeon crawler using Rich library
# ABOUTME: Renders tile maps with entities, fog of war, and status panel

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rich.console import Console, Group
from rich.panel import Panel
from rich.style import Style
from rich.table import Table
from rich.text import Text

from dnd_engine.spatial.grid import TileMap, EntityInfo
from dnd_engine.spatial.position import Position
from dnd_engine.spatial.tile import Tile, TileType, VisibilityState

if TYPE_CHECKING:
    from dnd_engine.core.character import Character


@dataclass
class RenderConfig:
    """Configuration for grid rendering."""

    # Viewport settings
    viewport_width: int = 40  # Tiles visible horizontally
    viewport_height: int = 20  # Tiles visible vertically
    center_on_player: bool = True

    # Display options
    show_fog_of_war: bool = True
    show_explored: bool = True  # Show previously explored but not visible tiles
    show_grid_coords: bool = False

    # Color scheme
    wall_color: str = "bright_black"
    floor_color: str = "white"
    door_color: str = "yellow"
    water_color: str = "blue"
    player_color: str = "bright_green"
    enemy_color: str = "bright_red"
    npc_color: str = "bright_cyan"
    item_color: str = "bright_yellow"
    unexplored_color: str = "black"
    explored_color: str = "dim white"


@dataclass
class TileStyle:
    """Style definition for a tile type."""

    char: str
    fg_color: str
    bg_color: str | None = None
    bold: bool = False


class GridRenderer:
    """
    Renders a TileMap to the terminal using Rich.

    Features:
    - Viewport that follows the player
    - Fog of war rendering
    - Entity display with colors
    - Status panel with HP/location info
    """

    # Default tile appearance
    TILE_STYLES: dict[TileType, TileStyle] = {
        TileType.FLOOR: TileStyle(".", "white"),
        TileType.WALL: TileStyle("#", "bright_black", bold=True),
        TileType.DOOR_CLOSED: TileStyle("+", "yellow", bold=True),
        TileType.DOOR_OPEN: TileStyle("/", "yellow"),
        TileType.STAIRS_UP: TileStyle("<", "bright_cyan", bold=True),
        TileType.STAIRS_DOWN: TileStyle(">", "bright_cyan", bold=True),
        TileType.WATER_SHALLOW: TileStyle("~", "blue"),
        TileType.WATER_DEEP: TileStyle("~", "bright_blue", bold=True),
        TileType.PIT: TileStyle("^", "red"),
        TileType.TRAP: TileStyle("^", "bright_red"),
        TileType.CHEST: TileStyle("$", "bright_yellow", bold=True),
        TileType.ALTAR: TileStyle("_", "magenta"),
        TileType.PILLAR: TileStyle("O", "bright_black"),
    }

    def __init__(
        self,
        console: Console | None = None,
        config: RenderConfig | None = None,
    ):
        """
        Initialize the grid renderer.

        Args:
            console: Rich Console instance (creates new if not provided)
            config: Rendering configuration
        """
        self.console = console or Console()
        self.config = config or RenderConfig()

        # Track viewport position
        self._viewport_x = 0
        self._viewport_y = 0

    def render(
        self,
        tile_map: TileMap,
        player_id: str | None = None,
        status_info: dict | None = None,
    ) -> None:
        """
        Render the tile map to the console.

        Args:
            tile_map: The map to render
            player_id: ID of player entity to center viewport on
            status_info: Optional status information to display
        """
        # Update viewport position
        if player_id and self.config.center_on_player:
            player_pos = tile_map.get_entity_position(player_id)
            if player_pos:
                self._center_viewport_on(player_pos, tile_map)

        # Build the render
        grid_text = self._render_grid(tile_map)
        status_panel = self._render_status(tile_map, player_id, status_info)
        legend = self._render_legend()

        # Create layout
        content = Group(
            Panel(
                grid_text,
                title=f"[bold]{tile_map.name}[/bold]",
                border_style="blue",
            ),
            status_panel,
            legend,
        )

        # Clear and render
        self.console.clear()
        self.console.print(content)

    def render_to_string(
        self,
        tile_map: TileMap,
        player_id: str | None = None,
    ) -> str:
        """
        Render the tile map to a string (for testing).

        Args:
            tile_map: The map to render
            player_id: ID of player entity to center viewport on

        Returns:
            String representation of the rendered map
        """
        if player_id and self.config.center_on_player:
            player_pos = tile_map.get_entity_position(player_id)
            if player_pos:
                self._center_viewport_on(player_pos, tile_map)

        lines = []
        for y in range(self._viewport_y, self._viewport_y + self.config.viewport_height):
            line = ""
            for x in range(self._viewport_x, self._viewport_x + self.config.viewport_width):
                pos = Position(x, y)
                char = self._get_tile_char(tile_map, pos)
                line += char
            lines.append(line)

        return "\n".join(lines)

    def _center_viewport_on(self, pos: Position, tile_map: TileMap) -> None:
        """Center the viewport on a position."""
        # Calculate viewport position to center on target
        self._viewport_x = pos.x - self.config.viewport_width // 2
        self._viewport_y = pos.y - self.config.viewport_height // 2

        # Clamp to map bounds
        self._viewport_x = max(0, min(self._viewport_x, tile_map.width - self.config.viewport_width))
        self._viewport_y = max(0, min(self._viewport_y, tile_map.height - self.config.viewport_height))

    def _render_grid(self, tile_map: TileMap) -> Text:
        """Render the grid portion of the map."""
        text = Text()

        for y in range(self._viewport_y, self._viewport_y + self.config.viewport_height):
            if y >= tile_map.height:
                # Pad with spaces if viewport extends beyond map
                text.append(" " * self.config.viewport_width + "\n")
                continue

            for x in range(self._viewport_x, self._viewport_x + self.config.viewport_width):
                pos = Position(x, y)

                if x >= tile_map.width:
                    text.append(" ")
                    continue

                tile = tile_map.get_tile(pos)
                if not tile:
                    text.append(" ")
                    continue

                char, style = self._get_tile_render(tile_map, pos, tile)
                text.append(char, style=style)

            text.append("\n")

        return text

    def _get_tile_render(
        self, tile_map: TileMap, pos: Position, tile: Tile
    ) -> tuple[str, Style]:
        """Get the character and style to render for a tile."""
        # Handle fog of war
        if self.config.show_fog_of_war:
            if tile.visibility == VisibilityState.UNEXPLORED:
                return " ", Style(color=self.config.unexplored_color)
            elif tile.visibility == VisibilityState.EXPLORED and self.config.show_explored:
                # Dim rendering for explored but not visible
                char, style = self._get_visible_tile_render(tile_map, pos, tile)
                return char, Style(color=self.config.explored_color, dim=True)

        return self._get_visible_tile_render(tile_map, pos, tile)

    def _get_visible_tile_render(
        self, tile_map: TileMap, pos: Position, tile: Tile
    ) -> tuple[str, Style]:
        """Get render for a visible tile."""
        # Check for entity first (entities on top)
        entity = tile_map.get_entity_at(pos)
        if entity:
            return self._get_entity_render(entity)

        # Check for items
        if tile.has_items:
            return "$", Style(color=self.config.item_color, bold=True)

        # Render the tile itself
        tile_style = self.TILE_STYLES.get(tile.tile_type)
        if tile_style:
            style = Style(
                color=tile_style.fg_color,
                bgcolor=tile_style.bg_color,
                bold=tile_style.bold,
            )
            return tile_style.char, style

        # Fallback
        return tile.char, Style(color="white")

    def _get_entity_render(self, entity: EntityInfo) -> tuple[str, Style]:
        """Get render for an entity."""
        if entity.is_player:
            return entity.display_char, Style(color=self.config.player_color, bold=True)
        else:
            return entity.display_char, Style(color=self.config.enemy_color, bold=True)

    def _get_tile_char(self, tile_map: TileMap, pos: Position) -> str:
        """Get just the character for a tile (no styling)."""
        if not tile_map.in_bounds(pos):
            return " "

        tile = tile_map.get_tile(pos)
        if not tile:
            return " "

        # Handle fog of war
        if self.config.show_fog_of_war:
            if tile.visibility == VisibilityState.UNEXPLORED:
                return " "

        # Check for entity
        entity = tile_map.get_entity_at(pos)
        if entity:
            return entity.display_char

        # Check for items
        if tile.has_items:
            return "$"

        return tile.char

    def _render_status(
        self,
        tile_map: TileMap,
        player_id: str | None,
        status_info: dict | None,
    ) -> Panel:
        """Render the status panel."""
        status_text = Text()

        # Player info
        if player_id:
            player = tile_map.get_entity(player_id)
            if player:
                status_text.append(f"Location: ", style="bold")
                status_text.append(f"{player.position}\n")

        # Custom status info
        if status_info:
            if "hp" in status_info and "max_hp" in status_info:
                hp = status_info["hp"]
                max_hp = status_info["max_hp"]
                hp_color = "green" if hp > max_hp // 2 else ("yellow" if hp > max_hp // 4 else "red")
                status_text.append("HP: ", style="bold")
                status_text.append(f"{hp}/{max_hp}", style=hp_color)
                status_text.append("\n")

            if "region" in status_info:
                status_text.append("Area: ", style="bold")
                status_text.append(f"{status_info['region']}\n")

            if "message" in status_info:
                status_text.append("\n")
                status_text.append(status_info["message"], style="italic")

        # Entity count
        enemies = tile_map.get_enemy_entities()
        if enemies:
            status_text.append(f"\nEnemies nearby: ", style="bold red")
            status_text.append(f"{len(enemies)}")

        return Panel(
            status_text,
            title="[bold]Status[/bold]",
            border_style="green",
        )

    def _render_legend(self) -> Text:
        """Render the control legend."""
        legend = Text()
        legend.append("  ", style="bold")
        legend.append("@", style=f"bold {self.config.player_color}")
        legend.append("=You  ")
        legend.append("G", style=f"bold {self.config.enemy_color}")
        legend.append("=Enemy  ")
        legend.append("#", style=f"bold {self.config.wall_color}")
        legend.append("=Wall  ")
        legend.append("+", style=f"bold {self.config.door_color}")
        legend.append("=Door  ")
        legend.append("$", style=f"bold {self.config.item_color}")
        legend.append("=Item")
        return legend

    def set_viewport(self, x: int, y: int) -> None:
        """Manually set the viewport position."""
        self._viewport_x = x
        self._viewport_y = y


class CompactGridRenderer:
    """
    A simpler, more compact grid renderer for smaller displays.

    Renders just the map without panels, useful for embedding
    in other UI layouts.
    """

    def __init__(
        self,
        width: int = 30,
        height: int = 15,
        show_fog: bool = True,
    ):
        self.width = width
        self.height = height
        self.show_fog = show_fog

    def render_to_text(
        self,
        tile_map: TileMap,
        center_pos: Position | None = None,
    ) -> Text:
        """Render map to a Rich Text object."""
        text = Text()

        # Calculate viewport
        if center_pos:
            vp_x = max(0, center_pos.x - self.width // 2)
            vp_y = max(0, center_pos.y - self.height // 2)
        else:
            vp_x, vp_y = 0, 0

        for y in range(vp_y, vp_y + self.height):
            for x in range(vp_x, vp_x + self.width):
                pos = Position(x, y)

                if not tile_map.in_bounds(pos):
                    text.append(" ")
                    continue

                tile = tile_map.get_tile(pos)
                if not tile:
                    text.append(" ")
                    continue

                # Fog of war
                if self.show_fog and tile.visibility == VisibilityState.UNEXPLORED:
                    text.append(" ")
                    continue

                # Entity check
                entity = tile_map.get_entity_at(pos)
                if entity:
                    color = "green" if entity.is_player else "red"
                    text.append(entity.display_char, style=f"bold {color}")
                    continue

                # Tile
                text.append(tile.char)

            text.append("\n")

        return text

    def render_to_string(
        self,
        tile_map: TileMap,
        center_pos: Position | None = None,
    ) -> str:
        """Render map to plain string (for testing)."""
        lines = []

        if center_pos:
            vp_x = max(0, center_pos.x - self.width // 2)
            vp_y = max(0, center_pos.y - self.height // 2)
        else:
            vp_x, vp_y = 0, 0

        for y in range(vp_y, vp_y + self.height):
            line = ""
            for x in range(vp_x, vp_x + self.width):
                pos = Position(x, y)

                if not tile_map.in_bounds(pos):
                    line += " "
                    continue

                tile = tile_map.get_tile(pos)
                if not tile:
                    line += " "
                    continue

                if self.show_fog and tile.visibility == VisibilityState.UNEXPLORED:
                    line += " "
                    continue

                entity = tile_map.get_entity_at(pos)
                if entity:
                    line += entity.display_char
                    continue

                line += tile.char

            lines.append(line)

        return "\n".join(lines)
