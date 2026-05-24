# ABOUTME: Tests for GameSession (#362) - the non-graphical session object
# ABOUTME: extracted from GameWindow so headless mode + tests can use it directly.

"""Tests for the GameSession class.

These tests exercise the session API the same way the headless entry
point will: instantiate GameSession directly (no Arcade window), poke
the engine through it, and assert on engine + entity-manager state.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Path to the starter scenarios shipped with the engine. The session
# accepts any filesystem path; we use the ranged-attack basic scenario
# as a deterministic fixture.
SCENARIO_DIR = Path(__file__).parent.parent.parent / "dnd-engine" / "tests" / "scenarios" / "yaml"


@pytest.fixture
def session():
    """A GameSession constructed without MCP or party-vault dependency.

    The session loads a scenario YAML immediately so we have a known
    party + enemy layout to exercise spawn/attack/state APIs without
    going through the cellar vault flow.
    """
    from client_2d.session import GameSession

    s = GameSession(enable_mcp=False, dev_mode=True)
    # load_scenario reuses the scenario-driven path so the session
    # has a deterministic, vault-free starting state.
    s.load_scenario(SCENARIO_DIR / "ranged_attack_basic.yaml")
    return s


class TestGameSessionInstantiation:
    def test_can_instantiate_without_arcade_window(self) -> None:
        """GameSession must not require arcade.Window to construct."""
        from client_2d.session import GameSession

        s = GameSession(enable_mcp=False, dev_mode=False)
        # Core collaborators should be wired up.
        assert s.engine is not None
        assert s.entity_manager is not None
        # No MCP server when disabled.
        assert s._mcp_server is None
        assert s._mcp_bridge is None

    def test_dev_mode_flag_persists(self) -> None:
        from client_2d.session import GameSession

        s = GameSession(enable_mcp=False, dev_mode=True)
        assert s._dev_mode is True


class TestSessionLoadScenario:
    def test_load_scenario_populates_engine_state(self, session) -> None:
        """After loading the ranged_attack_basic scenario the engine is
        in combat with the goblin and the party has Archy."""
        assert session.engine.in_combat is True
        assert session.engine.party is not None
        assert session.engine.party.characters[0].name == "Archy"
        assert len(session.engine.game_state.active_enemies) == 1
        assert session.engine.game_state.active_enemies[0].name.lower().startswith("goblin")

    def test_load_scenario_populates_entity_manager(self, session) -> None:
        """The entity manager mirrors the scenario's party and enemies."""
        monsters = session.entity_manager.get_monsters()
        party = session.entity_manager.get_party_members()
        assert len(monsters) == 1
        assert len(party) == 1
        # Positions come straight from the YAML.
        assert (monsters[0].grid_x, monsters[0].grid_y) == (10, 5)
        assert (party[0].grid_x, party[0].grid_y) == (3, 5)

    def test_load_scenario_enemies_appear_in_state_output(self, session) -> None:
        """Regression for #372: scenario enemies must render in
        ``game_state`` after ``load_scenario``. Before the fix the fog
        was lit around the room spawn point, not the scenario party
        positions, so the renderer's BRIGHT/DIM filter hid every
        scenario enemy.

        Goblin at [10, 5] is 7 tiles from Archy at [3, 5] — inside the
        torch dim range (bright=4 + dim=4 = 8) so natural lighting is
        sufficient once the lighting is anchored on the party.
        """
        state = session.get_state()
        assert "goblin_0" in state


class TestSessionSpawn:
    def test_spawn_monster_adds_to_engine_and_entity_manager(self, session) -> None:
        """spawn_monster wires the new creature into both layers."""
        before = len(session.engine.game_state.active_enemies)
        result = session.spawn_monster("giant_rat", 8, 6)
        after = len(session.engine.game_state.active_enemies)

        assert after == before + 1
        assert "giant_rat" in result
        ent = session.entity_manager.get_by_id(f"giant_rat_{after - 1}")
        assert ent is not None
        assert (ent.grid_x, ent.grid_y) == (8, 6)

    def test_spawn_character_adds_party_member(self, session) -> None:
        """spawn_character extends the party via the engine adapter."""
        before = len(session.engine.party.characters)
        session.spawn_character("fighter", "human", ["longsword"], 4, 5, name="Probe")
        after = len(session.engine.party.characters)
        assert after == before + 1
        assert session.engine.party.characters[-1].name == "Probe"

    def test_spawn_monster_from_exploration_keeps_party_positions(self, session) -> None:
        """Re-entering combat via spawn_monster must not stomp PartyMemberEntity positions.

        Regression for #371: when current_mode was EXPLORATION, spawn_monster
        used to call _spread_party_for_combat which clears _party_members and
        rebuilds them at fixed offsets around the player tile — clobbering
        positions the dev had placed via load_scenario / spawn_character.
        """
        # Drop back to EXPLORATION while leaving the party in entity_manager.
        session.clear_enemies()
        assert session.engine.in_combat is False
        before = {
            e.entity_id: (e.grid_x, e.grid_y) for e in session.entity_manager.get_party_members()
        }
        assert before, "fixture should have at least one party member"

        session.spawn_monster("goblin", 12, 5)

        # Same ids, same positions — no spread.
        after = {
            e.entity_id: (e.grid_x, e.grid_y) for e in session.entity_manager.get_party_members()
        }
        assert after == before

        # And the spawned monster is the only one, at the requested tile.
        monsters = session.entity_manager.get_monsters()
        assert len(monsters) == 1
        assert monsters[0].entity_id == "goblin_0"
        assert (monsters[0].grid_x, monsters[0].grid_y) == (12, 5)

    def test_spawn_monster_in_torch_light_shows_in_state(self, session) -> None:
        """When a monster is spawned inside the @'s natural torch radius,
        get_state() lists it as a monster (legend + visible entities).

        Pre-#371, the user's repro placed the goblin at the @'s exact tile,
        so the @ glyph shadowed it in the rendered map and the renderer
        also misattributed the spawn under the (clobbered) party formation.
        With the spread guard in place, a goblin spawned within the @'s
        bright torch radius (4 tiles) renders correctly with no fog
        bypass — this exercises the normal lighting flow set up by
        _load_room_layout -> _update_lighting.
        """
        session.clear_enemies()
        # Two tiles east of the @ is well within TORCH_BRIGHT_RADIUS (4).
        gx, gy = session.player_x + 2, session.player_y
        session.spawn_monster("goblin", gx, gy)

        state = session.get_state()

        # Legend entry from build_legend.
        assert "monster:goblin_0" in state
        # Visible-entities entry from render_state.
        assert f"goblin_0 at [{gx}, {gy}]" in state

    def test_spawn_monster_in_combat_preserves_party_positions(self, session) -> None:
        """Spawning a second enemy while already in combat must not respread.

        Pins the existing in-combat path: party positions stay put, second
        monster gets entity_id <monster_id>_1 at the requested tile.
        """
        before = {
            e.entity_id: (e.grid_x, e.grid_y) for e in session.entity_manager.get_party_members()
        }
        assert session.engine.in_combat is True

        session.spawn_monster("goblin", 8, 6)

        after = {
            e.entity_id: (e.grid_x, e.grid_y) for e in session.entity_manager.get_party_members()
        }
        assert after == before

        monsters = {
            e.entity_id: (e.grid_x, e.grid_y) for e in session.entity_manager.get_monsters()
        }
        # Scenario fixture starts with goblin_0; second spawn is goblin_1.
        assert "goblin_1" in monsters
        assert monsters["goblin_1"] == (8, 6)


class TestSessionMCPState:
    def test_get_state_returns_renderable_string(self, session) -> None:
        """get_state surfaces the same ASCII-state payload as the MCP tool."""
        state = session.get_state()
        assert isinstance(state, str)
        assert "Map:" in state
        # Combat info must surface; the goblin sits beyond torch range so
        # may not appear on the visible-entity list, but "Combat Round"
        # proves the engine wired into the formatter.
        assert "Combat Round" in state
        assert "Archy" in state


class TestSessionTick:
    def test_tick_is_noop_outside_combat(self) -> None:
        """A scenario-less session has no engine in combat; tick must
        return immediately without raising."""
        from client_2d.session import GameSession

        s = GameSession(enable_mcp=False, dev_mode=True)
        # No initialize() call -> engine has no GameState yet. tick
        # should tolerate that gracefully.
        s.tick(0.016)  # nothing to assert, just no crash

    def test_tick_does_not_crash_with_loaded_scenario(self, session) -> None:
        """With a scenario loaded and the player's turn first, tick is a
        no-op (no enemy-turn timer to advance)."""
        # ranged_attack_basic puts the elf first, so processing_enemy_turn
        # starts False. tick should do nothing dangerous.
        assert session.processing_enemy_turn in (False, True)
        session.tick(0.016)


class TestMCPServerWiring:
    def test_enable_mcp_creates_bridge_and_server(self) -> None:
        """When enable_mcp=True, initialize() must build the bridge + server."""
        from client_2d.session import GameSession

        s = GameSession(enable_mcp=True, mcp_port=0, dev_mode=True)
        s.load_scenario(SCENARIO_DIR / "ranged_attack_basic.yaml")
        # Initialize MCP plumbing without starting the HTTP thread:
        # initialize_mcp_server is the public seam the headless entry uses.
        s.initialize_mcp_server(start_http=False)
        assert s._mcp_bridge is not None
        assert s._mcp_server is not None


class TestSessionResetGame:
    """Tests for the session-layer reset_game primitive (#373).

    reset_game must wipe both the engine layer (party + active_enemies +
    combat) AND the visual entity manager (party members + monsters), so
    a subsequent load_scenario or spawn_character composes against a
    clean slate. The room layout / fog / lighting stay intact - callers
    swap maps via load_scenario when they need a different room.
    """

    def test_reset_game_clears_engine_party_and_enemies(self, session) -> None:
        """Engine state must be empty of party + enemies after reset."""
        # Fixture loaded a scenario with at least one PC and one goblin.
        assert len(session.engine.party.characters) >= 1
        assert len(session.engine.game_state.active_enemies) >= 1

        session.reset_game()

        assert session.engine.party.characters == []
        assert session.engine.game_state.active_enemies == []

    def test_reset_game_clears_entity_manager_party_and_monsters(self, session) -> None:
        """Visual entities for party + monsters must be dropped."""
        assert session.entity_manager.get_party_members(), "fixture should populate party members"
        assert session.entity_manager.get_monsters(), "fixture should populate monsters"

        session.reset_game()

        assert session.entity_manager.get_party_members() == []
        assert session.entity_manager.get_monsters() == []

    def test_reset_game_exits_combat_mode(self, session) -> None:
        """Combat flag + mode flip out of combat after reset."""
        from client_2d.core.constants import GameMode

        assert session.engine.in_combat is True
        session.current_mode = GameMode.COMBAT
        session.processing_enemy_turn = True

        session.reset_game()

        assert session.engine.in_combat is False
        assert session.current_mode == GameMode.EXPLORATION
        assert session.processing_enemy_turn is False

    def test_reset_game_preserves_room_layout(self, session) -> None:
        """Room layout / tiles stay intact - reset wipes entities, not the map."""
        room_layout_before = session.room_layout
        room_tiles_before = session.room_tiles

        session.reset_game()

        assert session.room_layout is room_layout_before
        assert session.room_tiles is room_tiles_before

    def test_reset_game_returns_status_string(self, session) -> None:
        """Returns a string suitable for surfacing through MCP."""
        result = session.reset_game()
        assert isinstance(result, str)
        # Mentions both counts so the caller can verify what was cleared.
        assert "party" in result.lower()
        assert "enemies" in result.lower()

    def test_reset_game_idempotent(self, session) -> None:
        """Calling reset twice in a row must not raise."""
        session.reset_game()
        # Second call against the already-empty state should be a no-op.
        session.reset_game()
        assert session.engine.party.characters == []
        assert session.engine.game_state.active_enemies == []

    def test_reset_game_then_load_scenario_composes(self, session) -> None:
        """After reset, load_scenario rebuilds party + enemies cleanly."""
        session.reset_game()
        session.load_scenario(SCENARIO_DIR / "ranged_attack_basic.yaml")

        # Scenario has 1 party member + 1 goblin; no leftover duplicates.
        assert len(session.engine.party.characters) == 1
        assert len(session.engine.game_state.active_enemies) == 1
        assert len(session.entity_manager.get_party_members()) == 1
        assert len(session.entity_manager.get_monsters()) == 1


def _force_player_turn(session) -> None:
    """Point the engine's initiative tracker at the first PC.

    The ranged_attack_basic scenario rolls a surprise round on load, and
    spawning extra enemies can shuffle initiative further. ``combat_move``
    short-circuits with "Not your turn!" unless the current combatant is
    a player, so tests targeting the move-collision path force the index
    onto the party member directly.
    """
    party = session.engine.party.characters
    assert party, "scenario fixture must populate the party"
    pc = party[0]
    tracker = session.engine._game_state.initiative_tracker
    for idx, entry in enumerate(tracker.combatants):
        if entry.creature is pc:
            tracker.current_turn_index = idx
            # Reset turn state so movement_remaining starts at full speed.
            tracker.turn_states[pc].reset(speed=pc.speed)
            return
    raise AssertionError("party member missing from initiative tracker")


class TestSessionCombatMoveBlockedByMonster:
    """Regression tests for #339.

    Combat movement into a tile occupied by a monster used to crash
    with ``AttributeError: 'MonsterEntity' object has no attribute
    'display_name'``. MonsterEntity exposes ``sub_type`` plus an
    optional ``_creature_ref`` to the engine creature; the block-path
    message must use one of those - never a non-existent ``display_name``.
    """

    def test_combat_move_into_monster_returns_blocked_message_without_crash(self, session) -> None:
        """Moving into a monster-occupied tile must return the blocked
        message instead of raising AttributeError."""
        # Place a fresh goblin one tile east of the player so combat_move
        # east immediately collides with it.
        target_x = session.player_x + 1
        target_y = session.player_y
        session.spawn_monster("goblin", target_x, target_y)
        _force_player_turn(session)

        # Must not raise. Pre-fix this crashed on ``entity_at_dest.display_name``.
        result = session.combat_move("east")

        assert "Path blocked!" in result
        assert "is in the way" in result
        # Player must not have moved.
        assert (session.player_x, session.player_y) != (target_x, target_y)

    def test_combat_move_into_monster_uses_creature_ref_name(self, session) -> None:
        """When the monster has a creature reference, its name surfaces
        in the blocked message."""
        target_x = session.player_x + 1
        target_y = session.player_y
        session.spawn_monster("goblin", target_x, target_y)
        _force_player_turn(session)

        blocker = session.entity_manager.get_at_position(target_x, target_y)
        assert blocker is not None
        assert blocker._creature_ref is not None
        expected_name = blocker._creature_ref.name

        result = session.combat_move("east")

        assert expected_name in result

    def test_combat_move_into_monster_falls_back_to_sub_type(self, session) -> None:
        """If the monster has no creature reference, the message falls
        back to a titled, space-separated ``sub_type``. Pins both fix
        branches from #339 so a refactor cannot regress the AttributeError."""
        target_x = session.player_x + 1
        target_y = session.player_y
        session.spawn_monster("giant_rat", target_x, target_y)
        _force_player_turn(session)

        blocker = session.entity_manager.get_at_position(target_x, target_y)
        assert blocker is not None
        # Drop the creature ref to exercise the sub_type fallback path.
        blocker._creature_ref = None

        result = session.combat_move("east")

        assert "Giant Rat" in result


class TestSessionResetGameMCPDispatch:
    """Tests for the MCP bridge dispatch path of reset_game (#373).

    Exercises the same path the HTTP MCP server uses: queue a
    CommandRequest with CommandType.RESET_GAME and let _process_mcp_commands
    drain it. The session must invoke its reset_game() and resolve the
    response future with the returned status string.
    """

    def test_process_mcp_command_routes_reset_game(self, session) -> None:
        """Submitting RESET_GAME via the bridge wipes engine + entity state."""
        from client_2d.mcp_bridge import CommandRequest, CommandType, MCPBridge

        bridge = MCPBridge()
        bridge.set_session(session)
        session._mcp_bridge = bridge

        request = CommandRequest(command_type=CommandType.RESET_GAME)
        bridge._command_queue.put(request)

        session._process_mcp_commands()

        # Future resolved with the session's status string.
        result = request.response_future.result(timeout=0.1)
        assert isinstance(result, str)
        assert "party" in result.lower()
        assert "enemies" in result.lower()

        # And the state was actually wiped.
        assert session.engine.party.characters == []
        assert session.engine.game_state.active_enemies == []
        assert session.entity_manager.get_party_members() == []
        assert session.entity_manager.get_monsters() == []


class TestSessionCombatMoveSpatialDelegation:
    """Plan-03 P5: when ``GameState.spatial`` is bootstrapped, combat_move
    routes through ``GameState.attempt_combat_step``. The MCP-visible
    wire string template for a successful move MUST be preserved
    byte-for-byte against the legacy ``RoomLayout``-driven path."""

    def _bootstrap_spatial_around_pc(self, session) -> str:
        """Wire a Map + SpatialIndex matching the session's room layout
        and place the current PC at the session's player tile. Returns
        the PC entity_id used."""
        from dnd_engine.core.map import Map

        # Use the session's existing RoomLayout to seed the engine Map.
        game_state = session.engine.game_state
        engine_map = Map.from_room_layout(session.room_layout)
        game_state.bootstrap_spatial(engine_map)

        # Place the current PC at the session's player tile.
        current = session.engine.get_current_combatant()
        creature = current["creature"]
        entity_id = f"pc_{creature.name.lower().replace(' ', '_')}"
        game_state.set_position(entity_id, session.player_x, session.player_y)
        return entity_id

    def test_successful_move_returns_same_wire_template(self, session) -> None:
        """``combat_move("north")`` via the engine path must produce a
        first-line equal to ``Moved <dir>. Movement remaining: <n> ft.``
        — exactly what the legacy path returned."""
        _force_player_turn(session)

        # Move the PC to a tile with empty space all around so the chosen
        # direction is guaranteed walkable on the room layout.
        target_x, target_y = 5, 5
        session.player_x = target_x
        session.player_y = target_y
        # Sync the entity manager so update_current_turn_position has
        # something to advance from.
        for ent in session.entity_manager.get_party_members():
            ent.grid_x = target_x
            ent.grid_y = target_y

        self._bootstrap_spatial_around_pc(session)
        starting_movement = session.engine.get_current_turn_state().movement_remaining

        result = session.combat_move("north")

        # First line must match the legacy wire format exactly. Movement
        # is 5 ft on normal terrain so remaining = starting - 5.
        expected_first_line = (
            f"Moved north. Movement remaining: {starting_movement - 5} ft."
        )
        assert result.startswith(expected_first_line + "\n"), (
            f"wire format drift: expected first line {expected_first_line!r}, "
            f"got {result.splitlines()[0]!r}"
        )

        # And the session's player position must reflect the engine move.
        assert (session.player_x, session.player_y) == (target_x, target_y - 1)
