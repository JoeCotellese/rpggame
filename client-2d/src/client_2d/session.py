# ABOUTME: GameSession owns the non-graphical pieces of the 2D client.
# ABOUTME: GameWindow composes one for rendering; headless mode runs it standalone.

"""GameSession - non-graphical core of the 2D client.

GameSession owns the engine adapter, entity manager, fog/lighting state,
combat state machine, and MCP plumbing. It contains no Arcade imports so
it can be exercised directly from tests and from the --headless entry
point without spawning a window.

Architecture:
    GameWindow (arcade.Window)  ─── composes ──>  GameSession
                                                    │
                       run_headless()    ──── owns ─┘
                                                    │
                                                    ├── EngineAdapter
                                                    ├── EntityManager
                                                    ├── MCPBridge
                                                    ├── EmbeddedMCPServer
                                                    ├── FogOfWarSystem / LightingSystem
                                                    └── room_layout, combat state

GameWindow reads state from the session for rendering and delegates input
actions back into session methods.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from client_2d.core.constants import GameMode
from client_2d.entities import EntityManager, EntityType
from client_2d.entities.entity import MonsterEntity, PartyMemberEntity
from client_2d.integration.engine_adapter import EngineAdapter
from client_2d.integration.layout_loader import LayoutLoader
from client_2d.systems.fog_of_war import FogOfWarSystem
from client_2d.systems.lighting import LightingSystem
from client_2d.testing.state_renderer import Entity as StateEntity
from client_2d.testing.state_renderer import StateRenderer

if TYPE_CHECKING:
    from client_2d.embedded_mcp_server import EmbeddedMCPServer
    from client_2d.mcp_bridge import MCPBridge

# Combat timing - mirrors GameWindow's ENEMY_TURN_DELAY (1.5s between
# auto-advanced enemy turns) so windowed and headless modes pace
# identically.
ENEMY_TURN_DELAY = 1.5


def parse_weapon_range(range_str: str | None) -> tuple[int, int]:
    """Parse weapon range string like "150/600" into (normal_feet, max_feet)."""
    if not range_str:
        return (5, 5)
    parts = range_str.split("/")
    if len(parts) == 2:
        return (int(parts[0]), int(parts[1]))
    return (int(parts[0]), int(parts[0]))


def get_attack_range(weapon_data: dict | None) -> tuple[int, int]:
    """Get (normal_range, max_range) in feet for a weapon.

    Mirrors GameWindow's range helper. Pure function; kept here so the
    session is self-contained for headless callers.
    """
    if not weapon_data:
        return (5, 5)

    range_str = weapon_data.get("range")
    properties = weapon_data.get("properties", [])
    category = weapon_data.get("category", "melee")

    if category == "ranged":
        return parse_weapon_range(range_str)

    if "thrown" in properties and range_str:
        return parse_weapon_range(range_str)

    return (5, 5)


class GameSession:
    """Non-graphical session: engine + entity manager + MCP + combat FSM.

    The session is the single source of truth for the game's runtime
    state. ``GameWindow`` holds one and renders from it; ``run_headless``
    drives one without any arcade dependencies.

    Texture dicts are optional. In windowed mode ``GameWindow`` populates
    them after loading sprites; in headless mode they stay empty and
    ``EntityManager`` happily creates entities with ``texture=None``.
    """

    def __init__(
        self,
        enable_mcp: bool = False,
        mcp_port: int = 8765,
        dev_mode: bool = False,
    ) -> None:
        """Construct an uninitialized session.

        Args:
            enable_mcp: When True, ``initialize_mcp_server()`` will build
                the bridge + HTTP server. The HTTP server is not started
                until ``initialize_mcp_server(start_http=True)``.
            mcp_port: Port for the embedded MCP HTTP server.
            dev_mode: When True, the MCP server exposes the --dev spawn
                / setup tools.
        """
        self.engine = EngineAdapter()
        self.layout_loader = LayoutLoader()
        self.entity_manager = EntityManager()

        # Texture dicts - GameWindow populates these before initialize().
        # Empty dicts work fine for headless mode (entity_manager handles
        # missing entries via dict.get() -> None).
        self.monster_textures: dict[str, Any] = {}
        self.character_textures: dict[str, Any] = {}
        self.item_textures: dict[str, Any] = {}

        # Room / map state - populated by _load_room_layout.
        self.room_layout = None
        self.room_tiles: list[list[int]] = []
        self.player_x = 0
        self.player_y = 0

        # Party combat formation tracking.
        self.party_spread = False
        self.party_positions: list[tuple[int, int]] = []

        # Per-room visibility and lighting.
        self.fog: FogOfWarSystem | None = None
        self.lighting: LightingSystem | None = None

        # Combat state machine.
        self.running = True
        self.current_mode = GameMode.EXPLORATION
        self.selected_enemy = 0
        self.enemy_turn_timer = 0.0
        self.processing_enemy_turn = False
        self.combat_log: list[str] = []
        # Per-MCP-call accumulator: every line the windowed-mode combat
        # log gains during a synchronous enemy-turn drain is mirrored
        # here so the MCP response can surface what happened between
        # the player's actions (#570). Distinct from ``combat_log``
        # because that buffer is bounded (10 lines) for the windowed
        # HUD; this one is per-call and reset by ``_consume_pending_events``.
        self._pending_combat_events: list[str] = []
        # Raised by ``_drain_enemy_turns`` while it owns the FSM. When
        # set, ``_add_combat_log`` mirrors each appended line directly
        # into ``_pending_combat_events``. Replaces the prior
        # ``combat_log[log_before:]`` slice mirror, which silently lost
        # lines whenever the 10-line cap truncated the windowed HUD
        # buffer mid-turn (#570 follow-up).
        self._capturing_drain_events: bool = False

        # MCP plumbing.
        self._mcp_bridge: MCPBridge | None = None
        self._mcp_server: EmbeddedMCPServer | None = None
        self._state_renderer: StateRenderer | None = None
        self._enable_mcp = enable_mcp
        self._mcp_port = mcp_port
        self._dev_mode = dev_mode

    # ========== Initialization ==========

    def initialize(
        self,
        dungeon_name: str = "cellar",
        campaign_id: str = "poisoned_laboratory",
        start_room: str = "cellar.stairs",
    ) -> None:
        """Load the party from the vault and start the game.

        Mirrors the original ``GameWindow._initialize_game``. The vault
        path is the user's character vault - this can raise
        ``PartyLoadError`` if the vault is missing or empty.
        """
        print("Loading party from vault...")
        party_info = self.engine.load_party_from_vault()
        for char in party_info:
            print(f"  - {char['name']} ({char['class']} L{char['level']})")

        print(f"\nInitializing game in {dungeon_name} dungeon...")
        game_info = self.engine.initialize_game(
            dungeon_name=dungeon_name,
            campaign_id=campaign_id,
            start_room=start_room,
        )
        print(f"  Starting room: {game_info['room_name']}")

        self._load_room_layout()

        print("\nStarting game...")
        start_info = self.engine.start_game()
        if start_info["in_combat"]:
            print(f"  Combat started! Enemies: {', '.join(start_info['enemies'])}")
            self.current_mode = GameMode.COMBAT
            self._spread_party_for_combat()
            self._add_combat_log(f"Combat begins! {len(start_info['enemies'])} enemies!")
            current = self.engine.get_current_combatant()
            if current:
                self._add_combat_log(f"{current['name']}'s turn first!")
            if not self.engine.is_player_turn():
                self.processing_enemy_turn = True
                self.enemy_turn_timer = ENEMY_TURN_DELAY
            elif self.engine.is_current_combatant_unconscious():
                self.processing_enemy_turn = True
                self.enemy_turn_timer = ENEMY_TURN_DELAY
        else:
            self._add_combat_log("Use WASD to move.")

    def initialize_mcp_server(
        self,
        start_http: bool = True,
        window: Any | None = None,
    ) -> None:
        """Create the MCP bridge + embedded server.

        Args:
            start_http: When True (default), start the HTTP server in a
                background thread. Tests can pass False to inspect the
                wiring without binding a port.
            window: Optional ``GameWindow`` to register on the bridge for
                code paths that still consult the bridge's window
                reference (windowed mode only).
        """
        # Local imports to keep the heavy MCP / uvicorn stack out of the
        # session's module-load path until it's actually requested.
        from client_2d.embedded_mcp_server import EmbeddedMCPServer
        from client_2d.mcp_bridge import MCPBridge

        self._mcp_bridge = MCPBridge()
        self._mcp_bridge.set_session(self)
        if window is not None:
            self._mcp_bridge.set_game_window(window)

        width = self.room_layout.width if self.room_layout else 25
        height = self.room_layout.height if self.room_layout else 18
        self._state_renderer = StateRenderer(width=width, height=height)

        self._mcp_server = EmbeddedMCPServer(
            bridge=self._mcp_bridge,
            port=self._mcp_port,
            dev_mode=self._dev_mode,
        )
        if start_http:
            self._mcp_server.start()

    def shutdown(self) -> None:
        """Tear down session-owned resources.

        Currently stops the embedded MCP server if one is running. Safe
        to call multiple times and safe to call when no MCP server was
        ever started.
        """
        if self._mcp_server is not None:
            self._mcp_server.stop()
            self._mcp_server = None

    # ========== Tick (called from GameWindow.on_update or headless loop) ==========

    def tick(self, delta_time: float) -> None:
        """Advance the non-rendering portion of the game state.

        Processes one pending MCP command (if any) and advances the
        auto-turn timer for enemy / unconscious-player turns. Called from
        ``GameWindow.on_update`` at Arcade's framerate, and from the
        headless tick loop at ~30 Hz.
        """
        self._process_mcp_commands()

        if not self.engine.in_combat:
            return

        if self.processing_enemy_turn:
            # When MCP is driving, wait()/attack()/spawn_monster() drain
            # enemy turns synchronously via _drain_enemy_turns(). Letting
            # the tick loop also auto-drain races against user commands:
            # after ENEMY_TURN_DELAY seconds of think-time the ticker
            # silently advances one enemy turn and lands on the next PC,
            # so the user's next wait() burns that PC's turn instead of
            # resolving the enemy's (#577). Hand pacing to the bridge.
            if self._mcp_bridge is not None:
                return
            self.enemy_turn_timer -= delta_time
            if self.enemy_turn_timer <= 0:
                if self.engine.is_current_combatant_unconscious():
                    self._process_unconscious_turn()
                elif not self.engine.is_player_turn():
                    self._process_enemy_turn()
                else:
                    self.processing_enemy_turn = False

    # ========== Combat log helper ==========

    def _add_combat_log(self, message: str) -> None:
        """Add a message to the combat log (capped at 10).

        While ``_drain_enemy_turns`` owns the FSM, each appended message
        is also mirrored into ``_pending_combat_events`` for the MCP
        response. Mirroring at the append site (rather than via a
        post-iteration ``combat_log[log_before:]`` slice) means the
        bounded 10-line HUD buffer can truncate freely without dropping
        events the MCP caller hasn't seen yet (#570 follow-up).
        """
        self.combat_log.append(message)
        if len(self.combat_log) > 10:
            self.combat_log = self.combat_log[-10:]
        if self._capturing_drain_events:
            self._pending_combat_events.append(message)

    def _drain_enemy_turns(self) -> None:
        """Run the FSM forward through every non-player turn.

        Wraps the synchronous drain loop used by ``attack`` / ``wait``
        so the MCP path can see what happened during the drain. Each
        ``_add_combat_log`` call inside the loop mirrors directly into
        ``_pending_combat_events`` via ``_capturing_drain_events`` —
        the windowed HUD's 10-line cap can truncate freely without the
        MCP response losing lines (#570).

        Mirrors ``tick``'s branching so an unconscious PC's death-save
        turn processes inside the same drain rather than being deferred
        until the next tick.
        """
        self._capturing_drain_events = True
        try:
            while self.processing_enemy_turn:
                if self.engine.is_current_combatant_unconscious():
                    self._process_unconscious_turn()
                elif not self.engine.is_player_turn():
                    self._process_enemy_turn()
                else:
                    # FSM contract: when the current combatant is a
                    # conscious PC, ``processing_enemy_turn`` should
                    # already be False. Guard against drift so a
                    # misconfigured state can't spin this loop forever.
                    self.processing_enemy_turn = False
                    break
        finally:
            self._capturing_drain_events = False

    def _consume_pending_events(self) -> list[str]:
        """Return and clear the per-call combat event buffer."""
        events = self._pending_combat_events
        self._pending_combat_events = []
        return events

    @staticmethod
    def _format_between_turns_block(events: list[str]) -> str:
        """Render a list of drained-turn lines under a stable header.

        Returns the empty string when ``events`` is empty so callers can
        unconditionally embed the block in a response without producing
        an orphan header (#570).
        """
        if not events:
            return ""
        body = "\n".join(f"  {line}" for line in events)
        return f"Between turns:\n{body}"

    # ========== Lighting / party spread ==========

    def _update_lighting(self) -> None:
        """Recalculate lighting based on player/party positions."""
        if self.fog is None or self.lighting is None:
            return

        self.fog.reset_to_dark()

        if self.party_spread and self.party_positions:
            light_positions = self.party_positions
        else:
            light_positions = [(self.player_x, self.player_y)]

        self.lighting.update_party_lights(light_positions, "torch")
        lit_tiles = self.lighting.calculate_lighting()
        self.fog.apply_lighting(lit_tiles)

    def _spread_party_for_combat(self) -> None:
        """Spread party into formation around current position."""
        if not self.room_layout:
            return

        cx, cy = self.player_x, self.player_y

        self.party_positions = self.entity_manager.spread_party_for_combat(
            engine=self.engine,
            center_x=cx,
            center_y=cy,
            layout=self.room_layout,
            character_textures=self.character_textures,
        )

        self.party_spread = True
        self._update_lighting()

    def _collapse_party_after_combat(self) -> None:
        """Collapse party back to single unit after combat ends."""
        if self.party_positions:
            avg_x = sum(p[0] for p in self.party_positions) // len(self.party_positions)
            avg_y = sum(p[1] for p in self.party_positions) // len(self.party_positions)
            self.player_x = avg_x
            self.player_y = avg_y

        self.entity_manager.collapse_party()

        self.party_spread = False
        self.party_positions = []
        self._update_lighting()

    # ========== Room / layout management ==========

    def _load_room_layout(self) -> None:
        """Load the current room's layout for rendering."""
        game_state = self.engine.game_state
        if game_state is None:
            return

        room_id = game_state.current_room_id
        dungeon_name = game_state.dungeon_name
        campaign_id = game_state.campaign_id

        room_data = self.layout_loader.get_room_data(dungeon_name, room_id, campaign_id)
        exits = {}
        if room_data:
            raw_exits = room_data.get("exits", {})
            for direction, dest in raw_exits.items():
                if isinstance(dest, dict):
                    exits[direction] = dest.get("destination", "")
                else:
                    exits[direction] = dest

        self.room_layout = self.layout_loader.load_room_with_fallback(
            dungeon_name=dungeon_name,
            room_id=room_id,
            campaign_id=campaign_id,
            default_width=20,
            default_height=15,
            exits=exits,
        )

        self.room_tiles = self.room_layout.tiles
        self.player_x, self.player_y = self.room_layout.spawn_points.player

        self.fog = FogOfWarSystem(
            width=self.room_layout.width,
            height=self.room_layout.height,
        )
        self.lighting = LightingSystem(
            map_width=self.room_layout.width,
            map_height=self.room_layout.height,
        )

        for y in range(self.room_layout.height):
            for x in range(self.room_layout.width):
                if self.room_layout.is_blocking(x, y):
                    self.lighting.add_obstacle(x, y)

        self.entity_manager.load_from_room(
            engine=self.engine,
            layout=self.room_layout,
            room_data=room_data,
            monster_textures=self.monster_textures,
            item_textures=self.item_textures,
        )

        self._update_lighting()

    def _get_available_exits(self) -> dict[str, str]:
        """Get available exits from current room (excluding hidden)."""
        game_state = self.engine.game_state
        if game_state is None:
            return {}

        room = game_state.get_current_room()
        exits = {}
        raw_exits = room.get("exits", {})
        for direction, dest in raw_exits.items():
            if isinstance(dest, dict):
                if not dest.get("hidden", False):
                    exits[direction] = dest.get("destination", "")
            else:
                exits[direction] = dest
        return exits

    # ========== Exploration movement ==========

    def _move_player(self, direction: str) -> None:
        """Attempt to move the player in a direction during exploration."""
        if self.engine.in_combat:
            self._add_combat_log("Can't move during combat!")
            return

        exits = self._get_available_exits()
        if direction in exits:
            self._add_combat_log(f"Moving {direction}...")
            self._transition_room(direction)
            return

        dx, dy = {
            "north": (0, -1),
            "south": (0, 1),
            "east": (1, 0),
            "west": (-1, 0),
        }.get(direction, (0, 0))
        new_x = self.player_x + dx
        new_y = self.player_y + dy

        if self.room_layout and (
            0 <= new_x < self.room_layout.width and 0 <= new_y < self.room_layout.height
        ):
            if not self.room_layout.is_blocking(new_x, new_y):
                self.player_x = new_x
                self.player_y = new_y
                self._update_lighting()

    def _transition_room(self, direction: str) -> None:
        """Transition to a new room via an exit."""
        game_state = self.engine.game_state
        if game_state is None:
            return

        result = game_state.move(direction)

        if result:
            self._load_room_layout()

            room = game_state.get_current_room()
            room_name = room.get("name", "Unknown")
            self._add_combat_log(f"Entered: {room_name}")

            if game_state.in_combat:
                enemies = [e.name for e in game_state.active_enemies]
                self.current_mode = GameMode.COMBAT
                self._spread_party_for_combat()
                self._add_combat_log(f"Combat! {len(enemies)} enemies: {', '.join(enemies)}")
                current = self.engine.get_current_combatant()
                if current:
                    if current["is_player"]:
                        self._add_combat_log(
                            f"{current['name']}'s turn - press 1-9 then A to attack!"
                        )
                    else:
                        self._add_combat_log(f"{current['name']} attacks first...")
                if not self.engine.is_player_turn():
                    self.processing_enemy_turn = True
                    self.enemy_turn_timer = ENEMY_TURN_DELAY

    # ========== Combat state machine ==========

    def _process_enemy_turn(self) -> None:
        """Process the current enemy's turn."""
        result = self.engine.process_enemy_turn()

        if result["success"]:
            self._emit_enemy_turn_log(result)

        self.entity_manager.sync_from_engine(self.engine)
        self.entity_manager.update_party_turn_status(self.engine)

        # The engine's process_enemy_turn already advances the initiative
        # tracker on every non-party-wipe return path, so we must NOT call
        # engine.advance_turn() again here — that double-advance silently
        # skipped the next combatant and left their TurnState unrendered
        # in MCP output (#569).
        if not self.engine.in_combat:
            self._handle_combat_end()
        elif not self.engine.is_player_turn():
            self.enemy_turn_timer = ENEMY_TURN_DELAY
        else:
            if self.engine.is_current_combatant_unconscious():
                self._process_unconscious_turn()
            else:
                self.processing_enemy_turn = False

    def _emit_enemy_turn_log(self, result: dict[str, Any]) -> None:
        """Render a per-turn combat-log block for one enemy turn.

        Layout, in narrative order:
          1. turn_start_effects (poison tick, etc.)
          2. action line(s) — branched on the ``action`` enum name
          3. turn_end_effects (condition expired, etc.)

        Branches on the engine adapter's ``action`` enum name so each
        action type emits a distinguishing line — players seeing an
        enemy do nothing should learn WHY (died at start of turn,
        stunned, no targets, no usable attack, shaking off a condition)
        rather than the generic "<enemy> takes no action" the
        pre-#570-fix code emitted for all five paths.
        """
        for message in result.get("turn_start_effects") or []:
            self._add_combat_log(message)

        self._emit_enemy_turn_action_line(result)

        for message in result.get("turn_end_effects") or []:
            self._add_combat_log(message)

    def _emit_enemy_turn_action_line(self, result: dict[str, Any]) -> None:
        """Emit the action-specific line (ATTACK / INCAPACITATED / ...)."""
        action = result.get("action")
        enemy = result.get("enemy_name", "Enemy")

        if action == "ATTACK":
            self._emit_enemy_attack_log(result)
            return

        if action == "DIED_START_OF_TURN":
            self._add_combat_log(f"{enemy} died before its turn.")
            return

        if action == "INCAPACITATED":
            conditions = result.get("incapacitating_conditions") or []
            label = ", ".join(c.upper() for c in conditions) if conditions else "incapacitated"
            self._add_combat_log(f"{enemy} cannot act ({label}).")
            return

        if action == "NO_TARGETS":
            self._add_combat_log(f"{enemy} has no valid targets.")
            return

        if action == "NO_VALID_ATTACK":
            self._add_combat_log(f"{enemy} has no usable attack.")
            return

        if action == "CONDITION_REMOVAL":
            message = result.get("condition_removal_message")
            if message:
                self._add_combat_log(message)
            else:
                self._add_combat_log(f"{enemy} attempts to remove a condition.")
            return

        # Unknown action — fall back to the legacy generic line rather
        # than swallow the turn silently. Reaching this branch indicates
        # a new EnemyTurnAction enum value the session doesn't yet
        # render explicitly.
        self._add_combat_log(f"{enemy} takes no action.")

    def _emit_enemy_attack_log(self, result: dict[str, Any]) -> None:
        """Render the line(s) for an ATTACK action.

        Mirrors the PC attack report format
        (``<attacker> attacks <target> with <weapon>: roll X+Y=Z vs AC W
        -> HIT/MISS/CRITICAL HIT for N damage``) so MCP consumers can
        audit the math the same way they can for player attacks (#570).
        """
        if result.get("hit") is None:
            self._add_combat_log(f"{result['enemy_name']} takes no action.")
            return

        attacker = result["enemy_name"]
        target = result["target_name"]
        action_name = result.get("action_name") or "attack"
        attack_roll = result.get("attack_roll", 0)
        attack_bonus = result.get("attack_bonus", 0)
        target_ac = result.get("target_ac", 0)
        total = attack_roll + attack_bonus
        bonus_text = f"+{attack_bonus}" if attack_bonus >= 0 else str(attack_bonus)

        if result.get("critical"):
            outcome = "CRITICAL HIT"
        elif result["hit"]:
            outcome = "HIT"
        else:
            outcome = "MISS"

        line = (
            f"{attacker} attacks {target} with {action_name}: "
            f"roll {attack_roll}{bonus_text}={total} vs AC {target_ac} -> "
            f"{outcome}"
        )
        if result["hit"]:
            line += f" for {result.get('damage', 0)} damage"

        self._add_combat_log(line)

        if result.get("saving_throw_triggered"):
            save_line = self._format_save_line(target, result)
            if save_line is not None:
                self._add_combat_log(save_line)

        concentration = result.get("concentration_broken")
        if concentration:
            spell_name = concentration.get("spell_name") or "their spell"
            self._add_combat_log(
                f"{target}'s concentration on {spell_name} is broken!"
            )

        if result.get("target_killed"):
            self._add_combat_log(f"{target} is down!")

    @staticmethod
    def _format_save_line(target: str, result: dict[str, Any]) -> str | None:
        """Format the saving-throw outcome line that accompanies an
        enemy attack with a save rider (e.g. goblin bite + poison).

        Returns ``None`` when the outcome is undetermined
        (``save_succeeded is None``) so the caller can skip the line
        rather than fabricate a SUCCEEDED/FAILED verdict. A missing
        ``save_dc`` renders as ``"DC ?"`` rather than the literal
        ``"None"`` string an unguarded f-string would produce.
        """
        succeeded = result.get("save_succeeded")
        if succeeded is None:
            return None

        ability = result.get("save_ability") or "Unknown"
        dc = result.get("save_dc")
        dc_text = str(dc) if dc is not None else "?"
        outcome = "SUCCEEDED" if succeeded else "FAILED"
        line = f"{target} DC {dc_text} {ability} save: {outcome}"
        conditions = result.get("conditions_applied") or []
        if conditions and not succeeded:
            applied = ", ".join(c.upper() for c in conditions)
            line += f" — {applied} applied"
        return line

    def _process_unconscious_turn(self) -> None:
        """Process an unconscious character's death saving throw turn."""
        result = self.engine.process_unconscious_turn()

        if result is None:
            self.processing_enemy_turn = False
            return

        if result.already_stabilized:
            self._add_combat_log(f"{result.character_name} is stabilized (no death save needed)")
        elif result.natural_20:
            self._add_combat_log(
                f"{result.character_name} rolls NAT 20! Regains consciousness with 1 HP!"
            )
        elif result.natural_1:
            self._add_combat_log(
                f"{result.character_name} rolls NAT 1! Two failures! ({result.failures}/3)"
            )
        elif result.success:
            self._add_combat_log(
                f"{result.character_name} death save: {result.roll} - Success! "
                f"({result.successes}/3)"
            )
        else:
            self._add_combat_log(
                f"{result.character_name} death save: {result.roll} - Failure! "
                f"({result.failures}/3)"
            )

        if result.conscious:
            self._add_combat_log(f"{result.character_name} is back on their feet!")
        elif result.stabilized and not result.already_stabilized:
            self._add_combat_log(f"{result.character_name} is stabilized!")
        elif result.dead:
            self._add_combat_log(f"{result.character_name} has died...")

        self.entity_manager.sync_from_engine(self.engine)

        if not self.engine.in_combat:
            self._handle_combat_end()
            return

        self.enemy_turn_timer = ENEMY_TURN_DELAY

    def _handle_combat_end(self) -> None:
        """Handle end of combat."""
        self.processing_enemy_turn = False
        self.current_mode = GameMode.EXPLORATION
        self._collapse_party_after_combat()

        check = self.engine.end_combat_check()
        if check.get("victory"):
            self._add_combat_log("Victory! All enemies defeated!")
        elif check.get("party_wiped"):
            self._add_combat_log("Defeat! Your party has fallen...")

    def execute_attack(self, *, disadvantage: bool = False) -> dict[str, Any] | None:
        """Execute an attack on the currently-selected enemy.

        Reads ``self.selected_enemy`` (the engine's enemy index) and
        delegates to the engine adapter. Called by both GameWindow's
        input handler and the MCP attack path.

        Args:
            disadvantage: Roll with disadvantage (e.g. ranged attack at long
                range). Forwarded to the engine adapter.

        Returns the engine adapter's attack-result dict on success so callers
        (notably the MCP attack handler) can render hit/miss/damage details.
        Returns ``None`` if the engine rejected the attack outright.
        """
        result = self.engine.execute_attack(
            target_index=self.selected_enemy, disadvantage=disadvantage
        )

        if result["success"]:
            if result["hit"]:
                crit = " CRITICAL!" if result.get("critical") else ""
                self._add_combat_log(
                    f"{result['attacker_name']} hits {result['target_name']} "
                    f"for {result['damage']} damage!{crit}"
                )
                if result.get("target_killed"):
                    self._add_combat_log(f"{result['target_name']} is defeated!")
            else:
                self._add_combat_log(
                    f"{result['attacker_name']} misses {result['target_name']}! "
                    f"(rolled {result['attack_roll']} vs AC {result['target_ac']})"
                )

            self.entity_manager.sync_from_engine(self.engine)
            self.entity_manager.remove_dead_entities()
            self.entity_manager.update_party_turn_status(self.engine)

            turn_result = self.engine.advance_turn()

            if turn_result.get("combat_ended"):
                self._handle_combat_end()
            elif not turn_result.get("is_player_turn"):
                self.processing_enemy_turn = True
                self.enemy_turn_timer = ENEMY_TURN_DELAY

            return result

        self._add_combat_log(f"Attack failed: {result.get('error', 'Unknown error')}")
        return None

    def pass_turn(self) -> None:
        """Pass the current turn."""
        current = self.engine.get_current_combatant()
        if current:
            self._add_combat_log(f"{current['name']} waits...")

        self.entity_manager.update_party_turn_status(self.engine)

        turn_result = self.engine.advance_turn()

        if turn_result.get("combat_ended"):
            self._handle_combat_end()
        elif not turn_result.get("is_player_turn"):
            self.processing_enemy_turn = True
            self.enemy_turn_timer = ENEMY_TURN_DELAY

    # ========== MCP command processing ==========

    def _process_mcp_commands(self) -> None:
        """Drain one pending command from the MCP bridge, if any.

        Once ``tick`` hands enemy-turn pacing to the bridge (#577), the
        ``processing_enemy_turn`` flag stays raised between MCP calls
        until ``wait()``/``attack()`` drains it. Polling commands while
        that flag is set is therefore the normal MCP-driven flow, not a
        race — those handlers drain synchronously, leaving the flag in
        a consistent state before they return.
        """
        if self._mcp_bridge is None:
            return

        request = self._mcp_bridge.poll_commands()
        if request is None:
            return

        from client_2d.mcp_bridge import CommandType

        try:
            if request.command_type == CommandType.GET_STATE:
                result = self.get_state()
            elif request.command_type == CommandType.MOVE:
                result = self.move(request.args.get("direction", ""))
            elif request.command_type == CommandType.ATTACK:
                target = request.args.get("target", request.args.get("target_index", 0))
                result = self.attack(target)
            elif request.command_type == CommandType.WAIT:
                result = self.wait()
            elif request.command_type == CommandType.SPAWN_MONSTER:
                result = self.spawn_monster(
                    request.args.get("monster_id", ""),
                    request.args.get("x", 0),
                    request.args.get("y", 0),
                )
            elif request.command_type == CommandType.SPAWN_CHARACTER:
                result = self.spawn_character(
                    request.args.get("class_name", ""),
                    request.args.get("race", ""),
                    request.args.get("weapons", []),
                    request.args.get("x", 0),
                    request.args.get("y", 0),
                    name=request.args.get("name"),
                    level=request.args.get("level", 1),
                )
            elif request.command_type == CommandType.SET_POSITION:
                result = self.set_position(
                    request.args.get("entity_id", ""),
                    request.args.get("x", 0),
                    request.args.get("y", 0),
                )
            elif request.command_type == CommandType.CLEAR_ENEMIES:
                result = self.clear_enemies()
            elif request.command_type == CommandType.SET_SEED:
                result = self.set_seed(request.args.get("seed", 0))
            elif request.command_type == CommandType.LOAD_SCENARIO:
                result = self.load_scenario(request.args.get("path", ""))
            elif request.command_type == CommandType.RESET_GAME:
                result = self.reset_game()
            else:
                result = f"Unknown command: {request.command_type}"
            request.response_future.set_result(result)
        except Exception as exc:
            request.response_future.set_exception(exc)

    # ========== Public play API (used by MCP + GameWindow input) ==========

    def get_state(self) -> str:
        """Generate the ASCII state string used by MCP and headless reporting."""
        if self._state_renderer is None or self.room_layout is None or self.fog is None:
            # Lazy-init the state renderer so headless mode and tests can
            # call get_state() before initialize_mcp_server() is invoked.
            if self.room_layout is not None and self._state_renderer is None:
                self._state_renderer = StateRenderer(
                    width=self.room_layout.width,
                    height=self.room_layout.height,
                )
            if self._state_renderer is None or self.room_layout is None or self.fog is None:
                return "Game not initialized"

        entities = self._build_state_entities()

        turn = 0
        if self.engine.game_state:
            tracker = self.engine.game_state.initiative_tracker
            if tracker:
                turn = tracker.round_number

        player_hp = 30
        player_max_hp = 30
        party_data = self.engine.get_party_data()
        if party_data:
            player_hp = sum(c["hp"] for c in party_data)
            player_max_hp = sum(c["max_hp"] for c in party_data)

        state = self._state_renderer.render_state(
            room=self.room_tiles,
            player_x=self.player_x,
            player_y=self.player_y,
            entities=entities,
            fog=self.fog,
            turn=turn,
            player_hp=player_hp,
            player_max_hp=player_max_hp,
            light_source="torch",
        )

        return self._format_state_response(state)

    def _build_state_entities(self) -> list[StateEntity]:
        """Build entity list for StateRenderer from EntityManager."""
        entities: list[StateEntity] = []

        self.entity_manager.sync_from_engine(self.engine)
        self.entity_manager.remove_dead_entities()

        for entity in self.entity_manager.get_all():
            if not entity.is_alive:
                continue

            if entity.entity_type == EntityType.MONSTER:
                type_str = "monster"
            elif entity.entity_type == EntityType.ITEM:
                type_str = "item"
            elif entity.entity_type == EntityType.PARTY_MEMBER:
                type_str = "party"
            else:
                type_str = "decoration"

            display_id = entity.sub_type or entity.entity_id
            unique_suffix = entity.entity_id.split("_")[-1]
            unique_id = f"{display_id}_{unique_suffix}" if entity.sub_type else entity.entity_id

            entities.append(
                StateEntity(
                    x=entity.grid_x,
                    y=entity.grid_y,
                    entity_type=type_str,
                    entity_id=unique_id,
                )
            )

        return entities

    def _format_state_response(self, state_dict: dict) -> str:
        """Format state dict as readable MCP response."""
        if "error" in state_dict:
            return f"Error: {state_dict['error']}"

        lines = [
            f"Turn: {state_dict['turn']}",
            f"Party HP: {state_dict['player']['hp']}/{state_dict['player']['max_hp']} "
            f"Light: {state_dict['player']['light_source']}",
            f"Explored: {state_dict['explored_tiles']}/{state_dict['total_tiles']}",
        ]

        if self.engine.in_combat:
            combat_data = self.engine.get_combat_data()
            if combat_data:
                lines.append(f"Combat Round: {combat_data['round']}")
                current = self.engine.get_current_combatant()
                if current:
                    lines.append(f"Current Turn: {current['name']}")
                    if current["is_player"]:
                        from dnd_engine.systems.inventory import EquipmentSlot

                        creature = current["creature"]
                        weapon_name = "Unarmed"
                        range_text = "5 ft (melee)"
                        if hasattr(creature, "inventory"):
                            weapon_id = creature.inventory.get_equipped_item(EquipmentSlot.WEAPON)
                            if weapon_id and self.engine.game_state:
                                items_data = self.engine.game_state.data_loader.load_items(
                                    self.engine.game_state.campaign_id
                                )
                                weapon_data = items_data.get("weapons", {}).get(weapon_id, {})
                                weapon_name = weapon_data.get(
                                    "name", weapon_id.replace("_", " ").title()
                                )
                                normal_range, max_range = get_attack_range(weapon_data)
                                if max_range > 5:
                                    range_text = f"{normal_range}/{max_range} ft"
                                else:
                                    range_text = "5 ft (melee)"
                        lines.append(f"Equipped: {weapon_name} (range: {range_text})")

        lines.extend(
            [
                "",
                "Map:",
                state_dict["map"],
                "",
                "Legend:",
            ]
        )

        for symbol, entity in state_dict["legend"].items():
            lines.append(f"  {symbol} = {entity}")

        if state_dict["visible_entities"]:
            lines.append("")
            lines.append("Visible Entities:")
            for entity_id, info in state_dict["visible_entities"].items():
                lines.append(
                    f"  {info['symbol']} {info['type']}:{entity_id} "
                    f"at {info['position']} ({info['distance']} squares "
                    f"{info['direction']})"
                )

        party_data = self.engine.get_party_data()
        if party_data:
            lines.append("")
            lines.append("Party:")
            for member in party_data:
                conditions = ", ".join(member.get("conditions", [])) or "healthy"
                lines.append(
                    f"  {member['name']} ({member['class']}): "
                    f"{member['hp']}/{member['max_hp']} HP - {conditions}"
                )

        lines.append("")
        lines.append("Available Actions:")
        if self.engine.in_combat:
            turn_state = self.engine.get_current_turn_state()
            if turn_state:
                lines.append(f"  Movement: {turn_state.movement_remaining} ft remaining")
            lines.append("  - game_move(direction) - Move north/south/east/west")
            lines.append("  - game_attack(target) - Attack enemy in weapon range")
            lines.append("  - game_wait() - Pass turn")
        else:
            lines.append("  - game_move(direction) - Move north/south/east/west")

        return "\n".join(lines)

    def move(self, direction: str) -> str:
        """Move in a direction; routes to combat or exploration movement."""
        direction = direction.lower()
        if direction not in ("north", "south", "east", "west"):
            return f"Invalid direction: {direction}. Use north/south/east/west."

        if self.engine.in_combat:
            return self.combat_move(direction)
        else:
            self._move_player(direction)
            return self.get_state()

    def combat_move(self, direction: str) -> str:
        """Handle movement during combat with action economy."""
        if not self.engine.is_player_turn():
            return "Not your turn! Wait for enemies to act."

        turn_state = self.engine.get_current_turn_state()
        if turn_state is None:
            return "Error: Could not get turn state."

        if turn_state.movement_remaining < 5:
            current = self.engine.get_current_combatant()
            speed = current["creature"].speed if current else 30
            return f"No movement remaining (0/{speed} ft). Use game_attack() or game_wait()."

        # Anchor the `@` cursor to the active combatant's TRUE tile
        # before computing the move. ``spread_party_for_combat`` puts
        # each PC on its own tile around `@`, but `self.player_x/y` is
        # never re-synced when turns advance — so a non-leader PC's
        # ``combat_move`` would otherwise compute ``new_x = player_x +
        # dx`` from the stale leader tile and then ``update_current_turn
        # _position(new_x, new_y)`` would slam the PC's entity grid to
        # that wrong destination (either a silent no-op when it lands
        # on the PC's existing tile, or a teleport). See #578.
        combatant_pos = self.entity_manager.get_current_turn_position(self.engine)
        if combatant_pos is not None:
            self.player_x, self.player_y = combatant_pos

        dx, dy = {
            "north": (0, -1),
            "south": (0, 1),
            "east": (1, 0),
            "west": (-1, 0),
        }[direction]

        # Engine-owned validation path (plan-03 P5). Only engaged when a
        # SpatialIndex has been bootstrapped on GameState; otherwise the
        # legacy RoomLayout-driven path below still runs unchanged.
        game_state = self.engine.game_state
        if game_state is not None and game_state.spatial is not None:
            engine_result = self._combat_move_via_engine(direction, dx, dy)
            if engine_result is not None:
                return engine_result

        new_x = self.player_x + dx
        new_y = self.player_y + dy

        if not self.room_layout or not (
            0 <= new_x < self.room_layout.width and 0 <= new_y < self.room_layout.height
        ):
            return "Path blocked! Cannot move outside room."

        if self.room_layout.is_blocking(new_x, new_y):
            return "Path blocked! Wall in the way."

        entity_at_dest = self.entity_manager.get_at_position(new_x, new_y)
        if entity_at_dest is not None and entity_at_dest in self.entity_manager.get_monsters():
            if entity_at_dest._creature_ref:
                name = entity_at_dest._creature_ref.name
            else:
                name = entity_at_dest.sub_type.replace("_", " ").title()
            return f"Path blocked! {name} is in the way."

        self.player_x = new_x
        self.player_y = new_y
        turn_state.consume_movement(5)
        self._update_lighting()

        self.entity_manager.update_current_turn_position(self.engine, new_x, new_y)

        remaining = turn_state.movement_remaining
        return f"Moved {direction}. Movement remaining: {remaining} ft.\n" + self.get_state()

    def _combat_move_via_engine(
        self, direction: str, dx: int, dy: int
    ) -> str | None:
        """Engine-validated combat step. Returns the same wire format the
        legacy ``combat_move`` path produces so MCP ``game_move`` is
        byte-for-byte stable.

        Returns ``None`` when the engine path can't determine an
        entity_id for the current combatant — caller falls back to the
        legacy ``RoomLayout`` path. ``None`` is NOT a failure indicator;
        explicit rejection messages always come back as strings.

        Note on the difficult-terrain cost delta: the engine reads the
        destination terrain from ``Map.terrain_at`` so a water tile
        (``TerrainType.DIFFICULT``) charges 10 ft per 5-ft step per
        SRD #436. The legacy ``RoomLayout`` path always charged a flat
        5 ft regardless of tile. The engine cost is the SRD-correct
        one; scenarios that depended on the legacy flat cost across
        water need to flatten their terrain.
        """
        current = self.engine.get_current_combatant()
        if current is None:
            return None
        creature = current["creature"]
        # The plan-03 spatial convention for PC entity ids mirrors
        # GameState._find_creature_by_id and EngineAdapter.spawn_character.
        entity_id = f"pc_{creature.name.lower().replace(' ', '_')}"
        game_state = self.engine.game_state
        if game_state.spatial.position_of(entity_id) is None:
            # Spatial is bootstrapped but the PC is not yet placed — seed
            # from the session's current coords and proceed via the
            # engine path. Avoids the silent desync where the legacy
            # fallback would advance player_x/player_y without ever
            # writing to spatial, leaving the bootstrap undone forever.
            try:
                game_state.set_position(entity_id, self.player_x, self.player_y)
            except ValueError:
                # Session coords are blocking / occupied per spatial —
                # fall back to legacy and let the user see the legacy
                # diagnostic.
                return None

        # Pre-check entity_manager for the destination tile. Spatial may
        # not yet know about every entity (transition period until the
        # bootstrap-wiring slice makes the two sources canonical), so we
        # consult both and treat any entity_manager-only occupant as
        # blocking. Doing this BEFORE attempt_combat_step avoids having
        # to undo a committed move on the engine side.
        dest_x = self.player_x + dx
        dest_y = self.player_y + dy
        ent_at_dest = self.entity_manager.get_at_position(dest_x, dest_y)
        if ent_at_dest is not None and getattr(ent_at_dest, "entity_id", None) != entity_id:
            blocker_id = getattr(ent_at_dest, "entity_id", "") or ""
            name = self._resolve_blocker_name(blocker_id)
            return f"Path blocked! {name} is in the way."

        result = game_state.attempt_combat_step(entity_id, dx, dy)
        if not result.ok:
            if result.reason == "out of bounds":
                # Distinct legacy wire string for OOB vs in-bounds walls.
                return "Path blocked! Cannot move outside room."
            if result.reason == "blocking":
                return "Path blocked! Wall in the way."
            if result.reason and result.reason.startswith("occupied"):
                # Match the legacy phrasing so MCP consumers see the same
                # "Path blocked! <Name> is in the way." string they rely on.
                blocker_entity_id = result.reason[len("occupied by ") :]
                name = self._resolve_blocker_name(blocker_entity_id)
                return f"Path blocked! {name} is in the way."
            if result.reason == "no movement remaining":
                speed = creature.speed
                return (
                    f"No movement remaining (0/{speed} ft). "
                    "Use game_attack() or game_wait()."
                )
            # All known reasons handled above. For any unrecognized
            # reason, surface a generic message instead of falling back
            # to legacy — falling back would let legacy execute a move
            # the engine just rejected. The "not placed" path is
            # already handled by the auto-place above so should never
            # reach this branch.
            return f"Cannot move: {result.reason}"

        # Engine accepted the move; mirror the destination into the
        # session/entity-manager state so the rest of the system
        # (lighting, fog, renderer) sees the new position.
        self.player_x = result.position.x
        self.player_y = result.position.y
        self._update_lighting()
        self.entity_manager.update_current_turn_position(
            self.engine, self.player_x, self.player_y
        )

        return (
            f"Moved {direction}. Movement remaining: "
            f"{result.movement_remaining} ft.\n"
            + self.get_state()
        )

    def _resolve_blocker_name(self, blocker_entity_id: str) -> str:
        """Match the legacy combat_move name-resolution order for a
        blocking entity at the destination tile.

        Prefers the engine creature's name when available; falls back
        to the entity's ``sub_type`` titled and space-separated.
        """
        ent = self.entity_manager.get_by_id(blocker_entity_id)
        if ent is not None:
            if getattr(ent, "_creature_ref", None):
                return ent._creature_ref.name
            sub_type = getattr(ent, "sub_type", "") or ""
            if sub_type:
                return sub_type.replace("_", " ").title()
        return blocker_entity_id

    def attack(self, target: int | str) -> str:
        """Attack a target enemy by index or entity ID."""
        if not self.engine.in_combat:
            return "Not in combat! Use game_move() to explore."

        if not self.engine.is_player_turn():
            return "Not your turn! Wait for enemies to act."

        monsters = self.entity_manager.get_monsters()

        if isinstance(target, int):
            if target < 0 or target >= len(monsters):
                return f"Invalid target index {target}. Valid: 0-{len(monsters) - 1}"
            target_entity = monsters[target]
        else:
            target_entity = next(
                (
                    m
                    for m in monsters
                    if (
                        m.entity_id == target
                        or f"{m.sub_type}_{m.entity_id.split('_')[-1]}" == target
                    )
                ),
                None,
            )
            if target_entity is None:
                valid_ids = [
                    f"{m.sub_type}_{m.entity_id.split('_')[-1]}" if m.sub_type else m.entity_id
                    for m in monsters
                ]
                return f"Unknown target: {target}. Valid targets: {', '.join(valid_ids)}"

        from dnd_engine.core.distance import distance_in_feet
        from dnd_engine.systems.inventory import EquipmentSlot
        from dnd_engine.systems.ranged_attacks import is_close_combat_ranged_disadvantage

        combatant_pos = self.entity_manager.get_current_turn_position(self.engine)
        if combatant_pos is None:
            combatant_x, combatant_y = self.player_x, self.player_y
        else:
            combatant_x, combatant_y = combatant_pos

        distance_ft = distance_in_feet(
            combatant_x, combatant_y, target_entity.grid_x, target_entity.grid_y
        )

        current = self.engine.get_current_combatant()
        weapon_data = None
        weapon_name = "Unarmed"
        if current and current["is_player"]:
            creature = current["creature"]
            if hasattr(creature, "inventory"):
                weapon_id = creature.inventory.get_equipped_item(EquipmentSlot.WEAPON)
                if weapon_id:
                    items_data = self.engine.game_state.data_loader.load_items(
                        self.engine.game_state.campaign_id
                    )
                    weapon_data = items_data.get("weapons", {}).get(weapon_id, {})
                    weapon_name = weapon_data.get("name", weapon_id.replace("_", " ").title())

        normal_range, max_range = get_attack_range(weapon_data)

        if distance_ft > max_range:
            turn_state = self.engine.get_current_turn_state()
            movement_info = (
                f" Movement remaining: {turn_state.movement_remaining} ft." if turn_state else ""
            )
            return (
                f"Out of range! ({distance_ft} ft away, "
                f"{weapon_name} max range: {max_range} ft). "
                f"Move closer first.{movement_info}"
            )

        in_long_range = distance_ft > normal_range
        if in_long_range:
            self._add_combat_log(
                f"{weapon_name} attack at {distance_ft} ft (long range - disadvantage)"
            )

        # SRD § Ranged Attacks in Close Combat (#400): adjacent hostile
        # imposes disadvantage on a ranged attack. Thrown melee weapons
        # count as ranged attacks too, matching get_attack_range above.
        is_ranged_attack = weapon_data is not None and (
            weapon_data.get("category") == "ranged"
            or "thrown" in (weapon_data.get("properties") or [])
        )
        in_close_combat = is_ranged_attack and is_close_combat_ranged_disadvantage(
            attacker_pos=(combatant_x, combatant_y),
            enemies=(
                ((m.grid_x, m.grid_y), m.creature)
                for m in monsters
                if m.creature is not None
            ),
        )
        if in_close_combat:
            self._add_combat_log(
                f"{weapon_name} attack in close combat (adjacent enemy - disadvantage)"
            )

        disadvantage = in_long_range or in_close_combat

        pre_attack_combatant = current["name"] if current else None

        self.selected_enemy = target_entity.enemy_index
        attack_result = self.execute_attack(disadvantage=disadvantage)

        post_attack_combatant = self.engine.get_current_combatant()
        post_name = post_attack_combatant["name"] if post_attack_combatant else None

        if pre_attack_combatant == post_name and not self.processing_enemy_turn:
            return (
                f"Attack failed! {pre_attack_combatant} cannot reach the target. "
                f"Use game_wait() to pass."
            )

        report = self._format_attack_report(
            attack_result,
            target_entity,
            weapon_name=weapon_name,
            in_long_range=in_long_range,
        )

        # Drain enemy turns synchronously so the MCP caller sees the
        # post-enemy-action state. The helper also captures each
        # processed turn into ``_pending_combat_events`` (#570).
        self._drain_enemy_turns()

        between = self._format_between_turns_block(self._consume_pending_events())
        state = self.get_state()
        if report and between:
            return f"{report}\n\n{between}\n\n{state}"
        if between:
            return f"{between}\n\n{state}"
        return f"{report}\n\n{state}" if report else state

    def _format_attack_report(
        self,
        result: dict[str, Any] | None,
        target_entity: Any,
        *,
        weapon_name: str,
        in_long_range: bool,
    ) -> str:
        """Format a hit/miss/damage block for a player's attack.

        Returns an empty string if no result is available — preserves the
        existing state-only response in that case.
        """
        if not result:
            return ""

        attacker = result.get("attacker_name", "Attacker")
        target_name = result.get("target_name", "target")
        attack_roll = result.get("attack_roll", 0)
        attack_bonus = result.get("attack_bonus", 0)
        target_ac = result.get("target_ac", 0)
        total = attack_roll + attack_bonus
        bonus_text = f"+{attack_bonus}" if attack_bonus >= 0 else str(attack_bonus)

        if result.get("critical"):
            outcome = "CRITICAL HIT"
        elif result.get("hit"):
            outcome = "HIT"
        else:
            outcome = "MISS"

        suffix = ""
        if in_long_range:
            suffix = " (long range - disadvantage)"

        lines = [
            f"{attacker} attacks {target_name} with {weapon_name}: "
            f"roll {attack_roll}{bonus_text} = {total} vs AC {target_ac} -> "
            f"{outcome}{suffix}"
        ]

        if result.get("hit"):
            lines[0] += f" for {result.get('damage', 0)} damage"

        if result.get("target_killed"):
            lines.append(f"{target_name} is defeated!")
        else:
            # Cached hp/max_hp on the entity is updated by sync_from_engine
            # inside execute_attack, so this reflects post-attack HP.
            hp = getattr(target_entity, "hp", None)
            max_hp = getattr(target_entity, "max_hp", None)
            if hp is not None and max_hp:
                lines.append(f"{target_name}: {hp}/{max_hp} HP")

        return "\n".join(lines)

    def wait(self) -> str:
        """Pass the current turn."""
        if not self.engine.in_combat:
            return "Not in combat! Use game_move() to explore."

        if self.engine.is_player_turn():
            # Standard semantic: the PC chooses to pass. advance off them
            # so the drain can run subsequent enemies.
            self.pass_turn()
        else:
            # Non-PC turn (e.g. just after spawn_monster() left an enemy
            # first in initiative, #572). Don't burn the enemy's slot via
            # pass_turn(); raise the drain gate so _drain_enemy_turns()
            # runs the enemy AI instead of silently advancing past it.
            self.processing_enemy_turn = True

        self._drain_enemy_turns()

        between = self._format_between_turns_block(self._consume_pending_events())
        state = self.get_state()
        if between:
            return f"{between}\n\n{state}"
        return state

    # ========== Public dev/MCP API (gated upstream by dev_mode) ==========

    def _reject_spawn_if_occupied(self, x: int, y: int) -> str | None:
        """Return a rejection message if ``(x, y)`` is unsuitable for a
        new creature spawn, else ``None``.

        Consults four sources because each owns part of the truth during
        the plan-03 transition:
          * Room walls via ``room_layout.is_blocking`` — engine spatial
            may not be bootstrapped yet for legacy room flows.
          * ``entity_manager`` — owns the visible party + monster grid
            positions before they're written into ``SpatialIndex``.
          * Session ``player_x`` / ``player_y`` — the ``@`` marker is
            tracked separately from party-member entities in some
            scenarios (issue #568 repro).
          * ``GameState.spatial.occupant_at`` — authoritative once
            placements have been mirrored into it.
        """
        if self.room_layout is not None:
            if not (0 <= x < self.room_layout.width and 0 <= y < self.room_layout.height):
                return f"Cannot spawn at ({x},{y}): out of bounds."
            if self.room_layout.is_blocking(x, y):
                return f"Cannot spawn at ({x},{y}): tile is blocking (wall)."

        if (x, y) == (self.player_x, self.player_y):
            return f"Cannot spawn at ({x},{y}): tile is occupied by the player."

        existing = self.entity_manager.get_at_position(x, y)
        if existing is not None:
            blocker_id = getattr(existing, "entity_id", "") or ""
            name = self._resolve_blocker_name(blocker_id) if blocker_id else "an entity"
            return f"Cannot spawn at ({x},{y}): tile is occupied by {name}."

        game_state = self.engine.game_state
        if game_state is not None and game_state.spatial is not None:
            from dnd_engine.core.position import Position

            occupant = game_state.spatial.occupant_at(Position(x, y))
            if occupant is not None:
                name = self._resolve_blocker_name(occupant) if occupant else "an entity"
                return f"Cannot spawn at ({x},{y}): tile is occupied by {name}."
        return None

    def spawn_monster(self, monster_id: str, x: int, y: int) -> str:
        """Spawn a monster via engine + visual entity manager."""
        # Occupancy gate (#568): reject placements on the player marker,
        # any entity-manager occupant, a wall, or a spatial-index
        # occupant before the engine adds the creature to active_enemies
        # / initiative. Without this gate the engine adapter writes to
        # SpatialIndex (which would also reject) only AFTER appending to
        # active_enemies, leaving a ghost monster with no spatial
        # coordinate — visible in combat but invisible on the map.
        rejection = self._reject_spawn_if_occupied(x, y)
        if rejection is not None:
            return rejection
        result = self.engine.spawn_monster(monster_id, x, y)
        enemy_index = len(self.engine.game_state.active_enemies) - 1
        creature_ref = self.engine.game_state.active_enemies[enemy_index]

        entity = MonsterEntity(
            entity_id=result["entity_id"],
            grid_x=x,
            grid_y=y,
            entity_type=EntityType.MONSTER,
            sub_type=monster_id,
            enemy_index=enemy_index,
            texture=self.monster_textures.get(monster_id),
        )
        entity.creature = creature_ref
        self.entity_manager._add_entity(entity)

        if self.current_mode != GameMode.COMBAT:
            self.current_mode = GameMode.COMBAT
            # Spreading rebuilds party_members at formation offsets around
            # the @ tile, which is correct for the room-entry combat-start
            # flow but wrong for dev spawns where the dev has already
            # placed PCs via spawn_character / load_scenario.
            if not self.entity_manager.get_party_members():
                self._spread_party_for_combat()

        # Mirror initialize()'s drain-gate pattern: if the spawn left a
        # non-PC (or unconscious PC) as the current combatant, raise
        # processing_enemy_turn so the next wait() / attack() drains the
        # owed turn instead of silently advancing past it (#572).
        if self.engine.in_combat:
            if not self.engine.is_player_turn():
                self.processing_enemy_turn = True
                self.enemy_turn_timer = ENEMY_TURN_DELAY
            elif self.engine.is_current_combatant_unconscious():
                self.processing_enemy_turn = True
                self.enemy_turn_timer = ENEMY_TURN_DELAY

        return (
            f"Spawned {result['name']} at ({x},{y}) as {result['entity_id']}. " + self.get_state()
        )

    def spawn_character(
        self,
        class_name: str,
        race: str,
        weapons: list[str],
        x: int,
        y: int,
        name: str | None = None,
        level: int = 1,
    ) -> str:
        """Spawn a PC via the engine and add a party-member entity."""
        result = self.engine.spawn_character(
            class_name, race, weapons, x, y, name=name, level=level
        )
        party_index = len(self.engine.party.characters) - 1
        creature_ref = self.engine.party.characters[party_index]

        entity = PartyMemberEntity(
            entity_id=result["entity_id"],
            grid_x=x,
            grid_y=y,
            entity_type=EntityType.PARTY_MEMBER,
            sub_type=class_name.lower(),
            party_index=party_index,
            character_class=class_name.lower(),
            texture=self.character_textures.get(class_name.lower()),
        )
        entity.creature = creature_ref
        self.entity_manager._add_entity(entity)

        return (
            f"Spawned {result['name']} ({class_name}/{race}) at ({x},{y}) "
            f"as {result['entity_id']}. " + self.get_state()
        )

    def set_position(self, entity_id: str, x: int, y: int) -> str:
        """Move an existing entity to a new tile."""
        result = self.engine.set_position(entity_id, x, y)
        target = self.entity_manager.get_by_id(entity_id)
        if target is None:
            return f"Entity '{entity_id}' not found on the map."
        target.grid_x = x
        target.grid_y = y
        return f"Moved {entity_id} to {tuple(result['position'])}. " + self.get_state()

    def clear_enemies(self) -> str:
        """Wipe enemies from engine and visual layer."""
        result = self.engine.clear_enemies()
        for entity in list(self.entity_manager.get_all()):
            if entity.entity_type == EntityType.MONSTER:
                entity.is_alive = False
        self.entity_manager.remove_dead_entities()
        if self.current_mode == GameMode.COMBAT:
            self.current_mode = GameMode.EXPLORATION
        return f"Cleared {result['cleared']} enemies. " + self.get_state()

    def reset_game(self) -> str:
        """Wipe party + enemies + combat state for clean scenario reuse.

        Test-harness teardown primitive (#373). Goes one step beyond
        ``clear_enemies`` by also dropping party-member entities so the
        next ``load_scenario`` or ``spawn_character`` composes against a
        known zero state. The room layout / fog / lighting stay intact.
        """
        result = self.engine.reset_game()

        # Drop monsters via the existing dead-removal path.
        for monster in self.entity_manager.get_monsters():
            monster.is_alive = False
        self.entity_manager.remove_dead_entities()

        # remove_dead_entities intentionally preserves party members for
        # resurrection flows; collapse_party drops them unconditionally.
        self.entity_manager.collapse_party()

        if self.current_mode == GameMode.COMBAT:
            self.current_mode = GameMode.EXPLORATION
        self.processing_enemy_turn = False
        self.enemy_turn_timer = 0.0
        self.party_spread = False
        self.party_positions = []

        return (
            f"Reset game ({result['cleared_party']} party, "
            f"{result['cleared_enemies']} enemies cleared). " + self.get_state()
        )

    def set_seed(self, seed: int) -> str:
        """Reseed the engine dice roller."""
        result = self.engine.set_seed(seed)
        return f"Dice roller reseeded with {result['seed']}."

    def load_scenario(self, path: str) -> str:
        """Load a YAML scenario: swap engine state and rebuild visuals."""
        result = self.engine.load_scenario(path)

        # The new engine state has a new dungeon / room; reload the
        # layout (also resets fog + lighting).
        self._load_room_layout()

        # Wipe whatever entities the room layout pre-populated; the
        # scenario is the source of truth for who is present and where.
        self.entity_manager.clear()

        game_state = self.engine.game_state
        for entity_id, (x, y) in result["party_positions"].items():
            expected = entity_id.removeprefix("pc_")
            character = next(
                (
                    c
                    for c in game_state.party.characters
                    if c.name.lower().replace(" ", "_") == expected
                ),
                None,
            )
            if character is None:
                continue
            entity = PartyMemberEntity(
                entity_id=entity_id,
                grid_x=x,
                grid_y=y,
                entity_type=EntityType.PARTY_MEMBER,
                sub_type=character.character_class.value.lower(),
                party_index=game_state.party.characters.index(character),
                character_class=character.character_class.value.lower(),
                texture=self.character_textures.get(character.character_class.value.lower()),
            )
            entity.creature = character
            self.entity_manager._add_entity(entity)

        for entity_id, (x, y) in result["enemy_positions"].items():
            monster_id, _, index_str = entity_id.rpartition("_")
            try:
                enemy_index = int(index_str)
            except ValueError:
                continue
            if enemy_index >= len(game_state.active_enemies):
                continue
            creature = game_state.active_enemies[enemy_index]
            entity = MonsterEntity(
                entity_id=entity_id,
                grid_x=x,
                grid_y=y,
                entity_type=EntityType.MONSTER,
                sub_type=monster_id,
                enemy_index=enemy_index,
                texture=self.monster_textures.get(monster_id),
            )
            entity.creature = creature
            self.entity_manager._add_entity(entity)

        # Re-anchor fog/lighting on the scenario party positions. Without
        # this the renderer filters every scenario entity out of bright/
        # dim view because _load_room_layout lit the fog around the room
        # spawn point, not the scenario's PC positions. #372.
        scenario_party_positions = [
            (e.grid_x, e.grid_y) for e in self.entity_manager.get_party_members()
        ]
        if scenario_party_positions:
            self.player_x, self.player_y = scenario_party_positions[0]
            self.party_positions = scenario_party_positions
            self.party_spread = True
            self._update_lighting()

        if game_state.in_combat:
            self.current_mode = GameMode.COMBAT
        else:
            self.current_mode = GameMode.EXPLORATION

        return f"Loaded scenario '{result['name']}' (seed={result['seed']}). " + self.get_state()
