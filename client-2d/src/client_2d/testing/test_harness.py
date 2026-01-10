# ABOUTME: Test harness for headless game testing via stdin/stdout protocol.
# ABOUTME: Enables Claude-driven playtesting without graphical rendering.

"""Test harness for headless game testing."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any, TextIO

from client_2d.core.constants import Direction
from client_2d.systems.fog_of_war import FogOfWarSystem
from client_2d.systems.lighting import LightingSystem
from client_2d.testing.command_processor import CommandProcessor, CommandType
from client_2d.testing.state_renderer import Entity, StateRenderer


@dataclass
class GameState:
    """Encapsulates the game state for the test harness."""

    room: list[list[int]]
    player_x: int
    player_y: int
    entities: list[Entity]
    fog: FogOfWarSystem
    lighting: LightingSystem
    turn: int = 0
    player_hp: int = 30
    player_max_hp: int = 30
    light_source: str = "torch"
    running: bool = True


@dataclass
class TestHarness:
    """Headless test harness for Claude-driven playtesting.

    The harness runs a game loop that:
    1. Outputs game state as JSON to stdout
    2. Reads commands from stdin
    3. Processes commands and updates state
    4. Repeats until quit command

    Protocol:
        Output: JSON state after each action
        Input: JSON commands like {"action": "move_north"}

    Example session:
        > {"action": "get_state"}
        < {"turn": 0, "map": "...", "player": {...}, ...}
        > {"action": "move_east"}
        < {"turn": 1, "map": "...", "player": {...}, ...}
        > {"action": "quit"}
        < {"message": "Goodbye!"}
    """

    state: GameState
    renderer: StateRenderer = field(init=False)
    processor: CommandProcessor = field(init=False)
    input_stream: TextIO = field(default_factory=lambda: sys.stdin)
    output_stream: TextIO = field(default_factory=lambda: sys.stdout)

    def __post_init__(self):
        """Initialize renderer and processor."""
        width = len(self.state.room[0]) if self.state.room else 0
        height = len(self.state.room) if self.state.room else 0
        self.renderer = StateRenderer(width=width, height=height)
        self.processor = CommandProcessor()

    def run(self) -> None:
        """Run the main game loop.

        Reads commands from input_stream, processes them, and
        writes state to output_stream.
        """
        # Output initial state
        self._output_state()

        while self.state.running:
            try:
                line = self.input_stream.readline()
                if not line:
                    # EOF reached
                    break

                self._process_line(line.strip())

            except KeyboardInterrupt:
                self._output_message("Interrupted")
                break

    def _process_line(self, line: str) -> None:
        """Process a single input line."""
        if not line:
            return

        # Get current available actions
        current_state = self._render_current_state()
        available_actions = current_state["available_actions"]

        # Parse and validate command
        command, result = self.processor.process_input(line, available_actions)

        if not result.success:
            self._output_error(result.message)
            return

        # Handle meta commands
        if command.command_type == CommandType.QUIT:
            self.state.running = False
            self._output_message("Goodbye!")
            return

        if command.command_type == CommandType.GET_STATE:
            self._output_state()
            return

        # Handle game commands
        if command.command_type == CommandType.MOVE:
            self._handle_move(command.direction)
        elif command.command_type == CommandType.WAIT:
            self._handle_wait()
        elif command.command_type == CommandType.ATTACK:
            self._handle_attack(command.target_id)
        elif command.command_type == CommandType.INTERACT:
            self._handle_interact(command.target_id)

        # Output updated state
        self._output_state()

    def _handle_move(self, direction: Direction | None) -> None:
        """Handle movement command."""
        if direction is None:
            return

        dx, dy = direction.delta
        new_x = self.state.player_x + dx
        new_y = self.state.player_y + dy

        # Validate move (should already be validated, but double-check)
        if self._can_move_to(new_x, new_y):
            self.state.player_x = new_x
            self.state.player_y = new_y
            self._update_lighting()
            self.state.turn += 1

    def _handle_wait(self) -> None:
        """Handle wait command."""
        self.state.turn += 1

    def _handle_attack(self, target_id: str | None) -> None:
        """Handle attack command."""
        if target_id is None:
            return

        # Find the target entity
        for entity in self.state.entities:
            if entity.entity_id == target_id and entity.entity_type == "monster":
                # Simple combat: remove the monster (placeholder for real combat)
                self.state.entities.remove(entity)
                self.state.turn += 1
                return

    def _handle_interact(self, target_id: str | None) -> None:
        """Handle interact command."""
        if target_id is None:
            return

        # Find the target entity
        for entity in self.state.entities:
            if entity.entity_id == target_id:
                # Simple interaction: remove items (placeholder for real interaction)
                if entity.entity_type in ("item", "deco"):
                    self.state.entities.remove(entity)
                self.state.turn += 1
                return

    def _can_move_to(self, x: int, y: int) -> bool:
        """Check if player can move to position."""
        if x < 0 or y < 0:
            return False
        if y >= len(self.state.room) or x >= len(self.state.room[0]):
            return False
        return self.state.room[y][x] == 0

    def _update_lighting(self) -> None:
        """Update lighting based on player position."""
        self.state.fog.reset_to_dark()
        self.state.lighting.update_party_lights(
            [(self.state.player_x, self.state.player_y)],
            self.state.light_source,
        )
        lit_tiles = self.state.lighting.calculate_lighting()
        self.state.fog.apply_lighting(lit_tiles)

    def _render_current_state(self) -> dict[str, Any]:
        """Render current game state as dict."""
        return self.renderer.render_state(
            room=self.state.room,
            player_x=self.state.player_x,
            player_y=self.state.player_y,
            entities=self.state.entities,
            fog=self.state.fog,
            turn=self.state.turn,
            player_hp=self.state.player_hp,
            player_max_hp=self.state.player_max_hp,
            light_source=self.state.light_source,
        )

    def _output_state(self) -> None:
        """Output current state as JSON."""
        state = self._render_current_state()
        self._write_json(state)

    def _output_error(self, message: str) -> None:
        """Output error message as JSON."""
        self._write_json({"error": True, "message": message})

    def _output_message(self, message: str) -> None:
        """Output simple message as JSON."""
        self._write_json({"message": message})

    def _write_json(self, data: dict[str, Any]) -> None:
        """Write JSON to output stream."""
        json.dump(data, self.output_stream)
        self.output_stream.write("\n")
        self.output_stream.flush()


def create_demo_game_state() -> GameState:
    """Create a demo game state matching visual_test.py.

    Returns:
        GameState configured like the visual demo
    """
    # Map dimensions
    map_width = 40
    map_height = 28

    # Create room layout (simplified version of visual_test.py)
    room = [[0 for _ in range(map_width)] for _ in range(map_height)]

    # Border walls
    for x in range(map_width):
        room[0][x] = 1
        room[map_height - 1][x] = 1
    for y in range(map_height):
        room[y][0] = 1
        room[y][map_width - 1] = 1

    # Vertical wall dividing left and right (with gaps)
    for y in range(1, map_height - 1):
        if y not in [7, 8, 18, 19]:
            room[y][20] = 1

    # Horizontal wall in left area (with gap)
    for x in range(1, 20):
        if x not in [8, 9]:
            room[12][x] = 1

    # Initialize systems
    fog = FogOfWarSystem(width=map_width, height=map_height)
    lighting = LightingSystem(map_width=map_width, map_height=map_height)

    # Set walls as obstacles
    for y in range(map_height):
        for x in range(map_width):
            if room[y][x] == 1:
                lighting.add_obstacle(x, y)

    # Create entities
    entities = [
        Entity(x=6, y=6, entity_type="monster", entity_id="skeleton_1"),
        Entity(x=15, y=3, entity_type="monster", entity_id="goblin_1"),
        Entity(x=25, y=5, entity_type="monster", entity_id="wolf_1"),
        Entity(x=12, y=16, entity_type="monster", entity_id="rat_1"),
        Entity(x=4, y=2, entity_type="item", entity_id="longsword"),
        Entity(x=18, y=10, entity_type="item", entity_id="potion_1"),
        Entity(x=3, y=8, entity_type="deco", entity_id="chest_1"),
    ]

    # Player starting position
    player_x = map_width // 2
    player_y = map_height // 2

    state = GameState(
        room=room,
        player_x=player_x,
        player_y=player_y,
        entities=entities,
        fog=fog,
        lighting=lighting,
    )

    # Initial lighting update
    fog.reset_to_dark()
    lighting.update_party_lights([(player_x, player_y)], "torch")
    lit_tiles = lighting.calculate_lighting()
    fog.apply_lighting(lit_tiles)

    return state
