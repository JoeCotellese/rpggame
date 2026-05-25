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

    def test_tick_polls_mcp_commands_while_enemy_turn_pending(self) -> None:
        """Regression for #577 follow-on: with the ticker no longer
        auto-draining, ``_process_mcp_commands`` must still poll user
        commands while ``processing_enemy_turn`` is True. Otherwise the
        user's ``game_wait()`` deadlocks waiting for a tick that never
        services the queue, because spawn_monster leaves the flag
        raised until the next user-initiated drain.
        """
        from client_2d.mcp_bridge import CommandRequest, CommandType, MCPBridge
        from client_2d.session import GameSession

        s = GameSession(enable_mcp=False, dev_mode=True)
        bridge = MCPBridge()
        s._mcp_bridge = bridge

        # Simulate the post-spawn state: an enemy is queued up and the
        # drain gate is raised, exactly as spawn_monster leaves things.
        s.processing_enemy_turn = True

        # Enqueue a no-op GET_STATE command and verify tick drains it.
        request = CommandRequest(command_type=CommandType.GET_STATE)
        bridge._command_queue.put(request)

        s.tick(0.016)

        assert request.response_future.done(), (
            "MCP command starved while processing_enemy_turn was True; "
            "wait()/attack() would deadlock waiting for tick to service it"
        )

    def test_tick_does_not_auto_drain_enemy_turns_when_mcp_active(self) -> None:
        """Regression for #577: with MCP driving the session, tick must NOT
        auto-process an enemy turn after ENEMY_TURN_DELAY elapses.

        The MCP code path drains enemy turns synchronously inside
        ``wait()``/``attack()``/``spawn_monster()`` via
        ``_drain_enemy_turns``. If ``tick`` also auto-drains in the
        background it races against the user's commands and silently
        consumes a PC's turn: tick advances Goblin -> Abe between
        spawn_monster and the user's first wait(); the user's wait then
        operates on Abe, advancing Abe -> Bob and burning Abe's turn.
        """
        import random

        from client_2d.mcp_bridge import MCPBridge
        from client_2d.session import GameSession

        s = GameSession(enable_mcp=False, dev_mode=True)
        # Match the live MCP wiring without starting the HTTP thread:
        # an attached _mcp_bridge is what signals "MCP is driving."
        s.initialize()
        s._mcp_bridge = MCPBridge()
        # Deterministic seed used in the #577 repro.
        s.engine.game_state.dice_roller.random = random.Random(42)

        s.spawn_monster("goblin", 9, 7)
        tracker = s.engine.game_state.initiative_tracker
        assert tracker is not None

        # After spawn the goblin should be the current combatant and the
        # drain gate should be raised so the user's next wait() resolves it.
        current_before = tracker.get_current_combatant()
        assert current_before is not None
        assert current_before.creature.name == "Goblin"
        assert s.processing_enemy_turn is True
        idx_before = tracker.current_turn_index

        # Simulate the user thinking about their move for several seconds.
        # Each tick is one frame; together they exceed ENEMY_TURN_DELAY (1.5s).
        for _ in range(120):
            s.tick(0.05)

        # The ticker must NOT have advanced past the goblin while MCP
        # is the driver. The goblin's turn is the user's to resolve.
        current_after = tracker.get_current_combatant()
        assert current_after is not None, "tick must not corrupt initiative state"
        assert tracker.current_turn_index == idx_before, (
            f"tick silently advanced initiative under MCP: idx "
            f"{idx_before} -> {tracker.current_turn_index}, "
            f"current now {current_after.creature.name}"
        )
        assert current_after.creature.name == "Goblin"


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


class TestSessionCombatMoveAnchorsToActiveCombatant:
    """Regression tests for #578.

    The ``@`` cursor (``session.player_x/y``) is set during the
    room-entry party-spread to the party-leader tile and is never
    re-anchored to the active PC when their turn begins. Before this
    fix, ``combat_move`` computed the destination as
    ``self.player_x + dx`` — so a non-leader PC's move went from the
    cursor's tile rather than the PC's true tile. The downstream
    ``update_current_turn_position(new_x, new_y)`` call then slammed
    the PC's entity grid to that wrong destination, either silently
    no-op-ing (when the destination equalled the PC's existing tile)
    or teleporting the PC. Both flavors consumed 5 ft of budget per
    press without doing what the player asked.
    """

    def test_move_anchors_north_when_cursor_lags_south(self, session) -> None:
        """When ``@`` is one tile south of the active PC, pressing
        north must move the PC one tile north of its TRUE tile — not
        leave the PC in place after the cursor's would-be destination
        collides with the PC's current tile."""
        _force_player_turn(session)

        # Scenario seeds Archy at (3, 5) and `@` follows. Decouple
        # them: leave `@` at (3, 5) but lift the PC's entity grid one
        # tile north to (3, 4). This mimics the issue #578 repro where
        # spread_party_for_combat puts non-leader PCs on tiles other
        # than `@`.
        party = session.entity_manager.get_party_members()
        assert len(party) == 1
        pc_entity = party[0]
        pc_entity.grid_x = 3
        pc_entity.grid_y = 4
        assert (session.player_x, session.player_y) == (3, 5)

        starting_movement = session.engine.get_current_turn_state().movement_remaining

        session.combat_move("north")

        # The PC must move from its TRUE tile (3, 4) → (3, 3). Under
        # the bug, ``new_y = self.player_y + dy = 5 - 1 = 4`` and
        # ``update_current_turn_position(3, 4)`` re-set the PC's grid
        # back to (3, 4) — a silent no-op despite the budget spend.
        assert (pc_entity.grid_x, pc_entity.grid_y) == (3, 3)
        # Cursor coupled to the PC after the move.
        assert (session.player_x, session.player_y) == (3, 3)
        # Exactly one 5-ft step on normal terrain.
        assert (
            session.engine.get_current_turn_state().movement_remaining
            == starting_movement - 5
        )

    def test_repeated_moves_anchor_each_time(self, session) -> None:
        """Two consecutive presses from a desynced cursor must each
        advance the PC by one tile. The pre-fix behaviour was that the
        first press wasted budget while snapping `@` onto the PC; only
        the second press moved the PC. This pins both presses to a
        real advance so a regression that re-introduces the snap-then-
        move pattern fails immediately."""
        _force_player_turn(session)

        party = session.entity_manager.get_party_members()
        assert len(party) == 1
        pc_entity = party[0]
        # PC at (3, 4); `@` lags at (3, 5).
        pc_entity.grid_x = 3
        pc_entity.grid_y = 4
        assert (session.player_x, session.player_y) == (3, 5)

        starting_movement = session.engine.get_current_turn_state().movement_remaining

        session.combat_move("north")
        session.combat_move("north")

        # PC advances two tiles north of its true starting tile.
        assert (pc_entity.grid_x, pc_entity.grid_y) == (3, 2)
        assert (session.player_x, session.player_y) == (3, 2)
        assert (
            session.engine.get_current_turn_state().movement_remaining
            == starting_movement - 10
        )


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

    def test_step_off_map_wire_string(self, session) -> None:
        """When the engine rejects with ``out of bounds``, the session
        must surface the legacy ``"Path blocked! Cannot move outside
        room."`` wire string so MCP consumers branching on the OOB
        phrase keep working.

        Uses a custom 3x3 all-floor Map so the PC can sit at the (0, 0)
        corner and a north step lands at (0, -1) which has no entry in
        the Map — exactly the OOB case the engine distinguishes from
        in-bounds walls. The scenario's RoomLayout is wall-bordered so
        it can't reproduce the OOB shape directly.
        """
        from dnd_engine.core.map import Map, TileType

        _force_player_turn(session)
        # Park the PC at (0, 0) of the synthetic map.
        target_x, target_y = 0, 0
        session.player_x = target_x
        session.player_y = target_y
        for ent in session.entity_manager.get_party_members():
            ent.grid_x = target_x
            ent.grid_y = target_y

        # 3x3 all-floor Map so (0, -1) is OOB (tile_at returns None)
        # rather than an in-bounds wall.
        tiles = {
            (x, y): TileType.FLOOR for x in range(3) for y in range(3)
        }
        engine_map = Map(width=3, height=3, tiles=tiles)
        game_state = session.engine.game_state
        game_state.bootstrap_spatial(engine_map)
        pc = session.engine.party.characters[0]
        entity_id = f"pc_{pc.name.lower().replace(' ', '_')}"
        game_state.set_position(entity_id, target_x, target_y)
        _force_player_turn(session)

        result = session.combat_move("north")

        # First line + newline exactly match the legacy OOB string.
        assert result.startswith("Path blocked! Cannot move outside room.\n") or (
            result == "Path blocked! Cannot move outside room."
        )

    def test_engine_path_auto_places_pc_when_unplaced(self, session) -> None:
        """F2: when spatial is bootstrapped but the PC is not yet placed,
        the engine path must auto-place the PC at the session's current
        coords and then drive the move through ``attempt_combat_step``
        — not silently fall back to legacy (which would never write to
        spatial and leave the desync intact).
        """
        from dnd_engine.core.map import Map

        _force_player_turn(session)
        target_x, target_y = 5, 5
        session.player_x = target_x
        session.player_y = target_y
        for ent in session.entity_manager.get_party_members():
            ent.grid_x = target_x
            ent.grid_y = target_y

        # Bootstrap spatial but DO NOT call set_position for the PC.
        game_state = session.engine.game_state
        engine_map = Map.from_room_layout(session.room_layout)
        game_state.bootstrap_spatial(engine_map)
        current = session.engine.get_current_combatant()
        entity_id = f"pc_{current['creature'].name.lower().replace(' ', '_')}"
        assert game_state.spatial.position_of(entity_id) is None

        starting_movement = session.engine.get_current_turn_state().movement_remaining

        result = session.combat_move("north")

        # PC ended up placed in spatial at the new tile (proving the
        # engine path ran and committed; the legacy path would never
        # write to spatial).
        from dnd_engine.core.position import Position

        assert game_state.spatial.position_of(entity_id) == Position(
            target_x, target_y - 1
        )
        # And the wire format is the engine format (Movement remaining
        # deducts 5 ft for a normal-terrain step).
        expected_first_line = (
            f"Moved north. Movement remaining: {starting_movement - 5} ft."
        )
        assert result.startswith(expected_first_line + "\n")

    def test_engine_path_blocks_on_entity_manager_only_entity(self, session) -> None:
        """F3: an entity present in entity_manager but NOT in spatial
        must still block the move. Until the bootstrap-wiring slice
        unifies the two sources, the session must consult both and
        treat any entity_manager occupant as blocking with the legacy
        ``"Path blocked! <Name> is in the way."`` wire string.
        """
        from dnd_engine.core.map import Map
        from dnd_engine.core.position import Position

        _force_player_turn(session)
        target_x, target_y = 5, 5
        session.player_x = target_x
        session.player_y = target_y
        for ent in session.entity_manager.get_party_members():
            ent.grid_x = target_x
            ent.grid_y = target_y

        # Spawn a fresh goblin one tile north — into the entity_manager
        # via spawn_monster. spawn_monster does NOT place into spatial,
        # so the goblin is entity_manager-only by construction.
        north_x, north_y = target_x, target_y - 1
        session.spawn_monster("goblin", north_x, north_y)

        # Now bootstrap spatial and place ONLY the PC. The goblin stays
        # absent from spatial — exactly the divergence F3 fixes. Derive
        # the PC entity_id from the actual PC creature (not from the
        # current combatant, which spawn_monster has just rotated onto
        # the new goblin).
        game_state = session.engine.game_state
        engine_map = Map.from_room_layout(session.room_layout)
        game_state.bootstrap_spatial(engine_map)
        pc = session.engine.party.characters[0]
        entity_id = f"pc_{pc.name.lower().replace(' ', '_')}"
        game_state.set_position(entity_id, target_x, target_y)
        # Sanity: spatial does NOT know about the goblin.
        assert game_state.spatial.occupant_at(Position(north_x, north_y)) is None
        _force_player_turn(session)

        result = session.combat_move("north")

        assert "Path blocked!" in result
        assert "is in the way" in result
        # PC must not have moved.
        assert (session.player_x, session.player_y) == (target_x, target_y)

    def test_engine_path_unknown_reason_returns_generic_message(
        self, session, monkeypatch
    ) -> None:
        """F6: an unrecognized ``MoveResult.reason`` must surface a
        generic message rather than silently falling back to the
        legacy path (which would execute a move the engine just
        rejected).
        """
        from dnd_engine.core.map import Map
        from dnd_engine.core.move_result import MoveResult
        from dnd_engine.core.position import Position

        _force_player_turn(session)
        target_x, target_y = 5, 5
        session.player_x = target_x
        session.player_y = target_y
        for ent in session.entity_manager.get_party_members():
            ent.grid_x = target_x
            ent.grid_y = target_y

        game_state = session.engine.game_state
        engine_map = Map.from_room_layout(session.room_layout)
        game_state.bootstrap_spatial(engine_map)
        current = session.engine.get_current_combatant()
        entity_id = f"pc_{current['creature'].name.lower().replace(' ', '_')}"
        game_state.set_position(entity_id, target_x, target_y)

        # Force the engine to return an invented reason that the session
        # has no branch for.
        def _fake_step(self, _entity_id, _dx, _dy, **_kwargs):  # noqa: ANN001
            return MoveResult(
                ok=False,
                reason="prone",
                position=Position(target_x, target_y),
                movement_remaining=30,
            )

        monkeypatch.setattr(
            type(game_state), "attempt_combat_step", _fake_step, raising=True
        )

        result = session.combat_move("north")

        assert result == "Cannot move: prone"
        # PC must not have moved on the unknown rejection.
        assert (session.player_x, session.player_y) == (target_x, target_y)


def _force_combatant_turn(session, creature) -> None:
    """Point the initiative tracker at a specific creature.

    Generalises ``_force_player_turn`` to any combatant (PC or enemy).
    """
    tracker = session.engine._game_state.initiative_tracker
    for idx, entry in enumerate(tracker.combatants):
        if entry.creature is creature:
            tracker.current_turn_index = idx
            return
    raise AssertionError(f"{creature} missing from initiative tracker")


class TestSessionDrainEnemyTurns:
    """Plan #570 fix Phase 1: per-call combat event accumulator.

    The MCP request path drains the combat state machine forward to the
    next PC turn synchronously inside ``attack()`` / ``wait()``. Before
    this fix the drained turns left no trace in the MCP response — the
    only artifact was windowed-mode's rolling combat log, which the MCP
    formatter never reads. ``_drain_enemy_turns`` wraps the drain loop
    and accumulates one entry per processed turn into
    ``_pending_combat_events`` so MCP-facing code can surface what
    happened between the player's actions.
    """

    def test_pending_events_starts_empty(self, session) -> None:
        """A freshly loaded session has no buffered combat events."""
        assert session._pending_combat_events == []
        assert session._consume_pending_events() == []

    def test_drain_is_noop_when_no_enemy_turn_pending(self, session) -> None:
        """With ``processing_enemy_turn`` False the drain returns
        immediately and the accumulator stays empty."""
        session.processing_enemy_turn = False
        session._pending_combat_events = []
        session._drain_enemy_turns()
        assert session._pending_combat_events == []

    def test_consume_returns_and_clears_pending_events(self, session) -> None:
        """``_consume_pending_events`` returns the buffer and drains it,
        so a subsequent call returns the empty list."""
        session._pending_combat_events = ["seeded line 1", "seeded line 2"]
        first = session._consume_pending_events()
        assert first == ["seeded line 1", "seeded line 2"]
        assert session._consume_pending_events() == []

    def test_drain_captures_enemy_attack_line(self, session) -> None:
        """A goblin's turn during the drain leaves a readable line in
        the accumulator naming the goblin and describing the outcome.

        Setup: spawn a goblin adjacent to Archy so the AI's first turn
        produces a melee attack (rather than a movement-only turn while
        the goblin closes distance). Force initiative onto the goblin.
        Deterministic seed pins dice rolls so this test stays stable.
        """
        adjacent_x = session.player_x + 1
        adjacent_y = session.player_y
        session.spawn_monster("goblin", adjacent_x, adjacent_y)

        goblin = session.engine.game_state.active_enemies[-1]
        _force_combatant_turn(session, goblin)
        session.set_seed(42)

        # Clear setup noise so we only assert on this drain's events.
        session.combat_log.clear()
        session._pending_combat_events.clear()

        session.processing_enemy_turn = True
        session._drain_enemy_turns()

        events = session._consume_pending_events()
        assert events, "drain should produce at least one event line"
        joined = " ".join(events).lower()
        assert "goblin" in joined, f"goblin not named in events: {events!r}"
        assert any(kw in joined for kw in ("hit", "miss", "damage", "no action")), (
            f"no readable action verb in events: {events!r}"
        )

    def test_drain_advances_initiative_back_to_player(self, session) -> None:
        """After draining the goblin's turn, initiative rotates back to
        the party so the PC can act on the next MCP call."""
        adjacent_x = session.player_x + 1
        adjacent_y = session.player_y
        session.spawn_monster("goblin", adjacent_x, adjacent_y)

        goblin = session.engine.game_state.active_enemies[-1]
        _force_combatant_turn(session, goblin)
        session.set_seed(42)

        session.processing_enemy_turn = True
        session._drain_enemy_turns()

        # Drain must terminate (no infinite loop) and leave the FSM
        # ready for player input.
        assert session.processing_enemy_turn is False

    def test_buffer_is_empty_immediately_after_consume(self, session) -> None:
        """Once the caller consumes the buffer, the next drain starts
        from an empty accumulator. Pins the contract that prevents lines
        from one MCP call leaking into the next response."""
        adjacent_x = session.player_x + 1
        adjacent_y = session.player_y
        session.spawn_monster("goblin", adjacent_x, adjacent_y)
        goblin = session.engine.game_state.active_enemies[-1]
        session.set_seed(42)

        _force_combatant_turn(session, goblin)
        session.combat_log.clear()
        session._pending_combat_events.clear()
        session.processing_enemy_turn = True
        session._drain_enemy_turns()

        first_events = session._consume_pending_events()
        assert first_events, "sanity: first drain produced events"

        # The instant the caller consumes, the buffer must be empty.
        # If two MCP calls landed back-to-back without an intervening
        # drain, the second response would otherwise inherit the first
        # response's events.
        assert session._pending_combat_events == []
        assert session._consume_pending_events() == []


class TestSessionMCPResponseSurfacesCombatEvents:
    """Plan #570 fix Phase 2: surface drained enemy-turn events in MCP responses.

    The acceptance criterion from the bug report: an MCP caller invoking
    ``wait()`` while a hostile enemy is in initiative must see what the
    enemy did during the drained turn. Before this fix the response was
    a state snapshot with no trace of the goblin's attack — the party
    could be wiped between calls with zero visibility (#570).
    """

    HEADER = "Between turns:"

    def test_wait_response_includes_goblin_attack_line(self, session) -> None:
        """Acceptance test: ``wait()`` reply contains the goblin's
        attack outcome line, not just the post-drain state snapshot."""
        adjacent_x = session.player_x + 1
        adjacent_y = session.player_y
        session.spawn_monster("goblin", adjacent_x, adjacent_y)

        # Pin Archy as the current combatant so wait() yields to the
        # goblin and the drain processes the goblin's turn.
        _force_player_turn(session)
        session.set_seed(42)

        response = session.wait()

        assert "Goblin" in response, (
            f"goblin not named anywhere in wait() reply:\n{response}"
        )
        # ``_process_enemy_turn`` writes either an attack-roll-detail
        # line (HIT/MISS/CRITICAL HIT) or a non-attack action line.
        # One of those tokens must be present for the reporter to know
        # what happened during the drain (#570).
        verbs = ("HIT", "MISS", "takes no action", "has no", "cannot act")
        assert any(v in response for v in verbs), (
            f"no enemy-action verb in wait() reply:\n{response}"
        )

    def test_wait_response_uses_between_turns_header(self, session) -> None:
        """Stable grep target: the surfaced events live under a
        ``Between turns:`` header so MCP consumers can find them in the
        unstructured response string."""
        adjacent_x = session.player_x + 1
        adjacent_y = session.player_y
        session.spawn_monster("goblin", adjacent_x, adjacent_y)

        _force_player_turn(session)
        session.set_seed(42)

        response = session.wait()

        assert self.HEADER in response, (
            f"missing {self.HEADER!r} header in wait() reply:\n{response}"
        )

    def test_between_turns_block_formatter_renders_lines(self, session) -> None:
        """Unit test for the formatter helper: non-empty event list
        produces a header + indented lines; empty list produces the
        empty string so callers can unconditionally splice the block
        into a response."""
        block = session._format_between_turns_block(
            ["Goblin hits Archy for 5 damage!", "Archy is down!"]
        )
        assert "Between turns:" in block
        assert "Goblin hits Archy for 5 damage!" in block
        assert "Archy is down!" in block

        # Empty list → empty string (no orphan header).
        assert session._format_between_turns_block([]) == ""

    def test_attack_response_wires_pending_events_through_drain(self, session) -> None:
        """When the drain populates events, ``attack()``'s response
        includes the ``Between turns:`` block. Monkeypatch the drain so
        this is decoupled from scenario-specific weapon/ammo issues —
        the integration acceptance is covered by the ``wait()`` test
        above; this test pins the attack-path surfacing wiring."""
        adjacent_x = session.player_x + 1
        adjacent_y = session.player_y
        session.spawn_monster("goblin", adjacent_x, adjacent_y)
        _force_player_turn(session)

        # Stub the drain to inject events as if the goblin had acted.
        # ``attack()`` then consumes them via the same code path as the
        # real drain.
        def fake_drain() -> None:
            session._pending_combat_events.append("Goblin hits Archy for 5 damage!")
            session.processing_enemy_turn = False

        session._drain_enemy_turns = fake_drain  # type: ignore[assignment]
        session.processing_enemy_turn = True

        monsters = session.entity_manager.get_monsters()
        target_idx = next(
            i for i, m in enumerate(monsters)
            if (m.grid_x, m.grid_y) == (adjacent_x, adjacent_y)
        )
        response = session.attack(target_idx)

        assert self.HEADER in response, (
            f"missing {self.HEADER!r} header in attack() reply:\n{response}"
        )
        assert "Goblin hits Archy for 5 damage!" in response

    def test_response_omits_header_when_no_enemy_turns_drained(self, session) -> None:
        """If no enemy turn ran during the call (e.g. attack ended
        combat or only the PC acted), the response should not include
        an empty ``Between turns:`` block."""
        # No goblin in adjacency, force PC turn; wait() will still pass
        # to the next combatant. The scenario goblin is at (10,5) — far
        # enough that the AI might not produce an attack line. But the
        # accumulator captures *any* combat_log line per processed turn,
        # so this test instead verifies the empty-block guard at the
        # formatter level by manually clearing the buffer after the drain.
        _force_player_turn(session)

        # Patch the helper to no-op so wait() drains nothing.
        original_drain = session._drain_enemy_turns
        session._drain_enemy_turns = lambda: None  # type: ignore[assignment]
        try:
            response = session.wait()
        finally:
            session._drain_enemy_turns = original_drain  # type: ignore[assignment]

        assert self.HEADER not in response, (
            f"empty {self.HEADER!r} block leaked into reply:\n{response}"
        )

    def test_get_state_does_not_consume_pending_events(self, session) -> None:
        """``get_state()`` is a pure read with no side effect on the
        combat-event buffer. The contract is that ``attack()`` /
        ``wait()`` own consumption via ``_format_between_turns_block``
        before calling ``get_state()``; any path that drains without
        surfacing is a bug in that path, not a case for ``get_state()``
        to paper over silently."""
        session._pending_combat_events = ["Goblin hits Archy for 5 damage!"]

        state = session.get_state()

        # The buffer is untouched, and the state response does not
        # silently surface pending events under a ``Recent Combat:``
        # header.
        assert session._pending_combat_events == ["Goblin hits Archy for 5 damage!"]
        assert "Recent Combat:" not in state
        assert "Goblin hits Archy for 5 damage!" not in state


class TestSessionWaitOnEnemyTurn:
    """Regression tests for #572.

    Calling ``wait()`` while a non-PC is the current combatant must
    drain enemy turns rather than burn the enemy's slot via
    ``pass_turn()``. The bug was that ``wait()`` unconditionally called
    ``pass_turn()`` (which logs ``"X waits..."`` and advances initiative
    past whoever is current — including an enemy), so the enemy's AI
    never ran and the response was silent.
    """

    HEADER = "Between turns:"

    def test_wait_on_enemy_turn_drains_instead_of_skipping(self, session) -> None:
        """When ``wait()`` is invoked on an enemy's turn, the enemy AI
        runs and surfaces in the response under the ``Between turns:``
        header — instead of being silently skipped."""
        adjacent_x = session.player_x + 1
        adjacent_y = session.player_y
        session.spawn_monster("goblin", adjacent_x, adjacent_y)

        # Pin the goblin as the current combatant so wait() is invoked on
        # its turn. Lower the drain gate to simulate the pre-#572-fix
        # state for spawn_monster (also covered by separate tests below).
        goblin = session.engine.game_state.active_enemies[-1]
        _force_combatant_turn(session, goblin)
        session.processing_enemy_turn = False
        session.set_seed(42)

        response = session.wait()

        # Goblin's per-turn handler must have produced an action line.
        # Post-#570 the attack outcome appears as HIT/MISS/CRITICAL HIT
        # inside an attack-roll-detail line; the legacy hits/misses
        # tokens are gone.
        verbs = ("HIT", "MISS", "takes no action", "has no", "cannot act")
        assert any(v in response for v in verbs), (
            f"no enemy-action verb in wait() reply "
            f"(goblin turn was skipped):\n{response}"
        )
        assert self.HEADER in response, (
            f"missing {self.HEADER!r} header in wait() reply:\n{response}"
        )

    def test_wait_on_enemy_turn_does_not_log_pc_waits(self, session) -> None:
        """``wait()`` on an enemy's turn must not call ``pass_turn()`` —
        which would write a ``"Goblin waits..."`` line and advance off
        the goblin without running its AI.

        The leaked line lives in ``session.combat_log`` rather than the
        response string (``pass_turn`` appends *before* the drain so the
        line is not captured into ``_pending_combat_events``), so we
        assert against the log directly.
        """
        adjacent_x = session.player_x + 1
        adjacent_y = session.player_y
        session.spawn_monster("goblin", adjacent_x, adjacent_y)

        goblin = session.engine.game_state.active_enemies[-1]
        _force_combatant_turn(session, goblin)
        session.processing_enemy_turn = False
        session.set_seed(42)

        log_before = list(session.combat_log)
        session.wait()
        new_lines = session.combat_log[len(log_before):]

        assert not any("Goblin waits" in line for line in new_lines), (
            f"goblin turn was burned via pass_turn (wait line leaked):\n"
            f"{new_lines}"
        )


class TestSessionSpawnMonsterDrainGate:
    """Regression tests for #572 companion bug.

    ``spawn_monster()`` previously never set ``processing_enemy_turn``
    even when the spawn left a non-PC as the current combatant. The
    initial-combat path in ``initialize()`` does this correctly; the fix
    mirrors that pattern in ``spawn_monster()`` so subsequent
    ``wait()`` / ``attack()`` calls find the drain gate raised.
    """

    def test_spawn_monster_raises_drain_gate_when_enemy_is_current(
        self, session, monkeypatch
    ) -> None:
        """When the engine reports a non-PC as current combatant after a
        spawn, ``processing_enemy_turn`` must be ``True`` so the next
        ``wait()`` / ``attack()`` drains the enemy AI."""
        session.processing_enemy_turn = False

        # Patch the engine's turn predicates so this test pins the fix's
        # gate-raise behavior without coupling to engine RNG or
        # initiative internals. Matches the "goblin lands first in
        # initiative" outcome described in #572.
        monkeypatch.setattr(session.engine, "is_player_turn", lambda: False)
        monkeypatch.setattr(
            session.engine, "is_current_combatant_unconscious", lambda: False
        )

        session.spawn_monster("goblin", session.player_x + 5, session.player_y)

        assert session.processing_enemy_turn is True

    def test_spawn_monster_raises_drain_gate_when_pc_unconscious(
        self, session, monkeypatch
    ) -> None:
        """Mirror the ``initialize()`` branch that handles a current PC
        who is unconscious — the drain loop owns death-save processing,
        so the gate must be raised in that case too."""
        session.processing_enemy_turn = False

        monkeypatch.setattr(session.engine, "is_player_turn", lambda: True)
        monkeypatch.setattr(
            session.engine, "is_current_combatant_unconscious", lambda: True
        )

        session.spawn_monster("goblin", session.player_x + 5, session.player_y)

        assert session.processing_enemy_turn is True

    def test_spawn_monster_leaves_gate_lowered_when_pc_is_current(
        self, session, monkeypatch
    ) -> None:
        """When the engine reports a conscious PC as current combatant
        after a spawn, ``processing_enemy_turn`` must remain ``False`` —
        the PC owes the next action and the drain must not run."""
        session.processing_enemy_turn = False

        monkeypatch.setattr(session.engine, "is_player_turn", lambda: True)
        monkeypatch.setattr(
            session.engine, "is_current_combatant_unconscious", lambda: False
        )

        session.spawn_monster("goblin", session.player_x + 5, session.player_y)

        assert session.processing_enemy_turn is False


class TestSessionSpawnMonsterOccupancy:
    """Regression tests for #568.

    ``spawn_monster()`` previously placed a monster on any tile,
    including tiles already occupied by the player marker ``@``, a
    party member, an existing monster, or a wall. The fix rejects the
    spawn with a clear error and leaves engine + entity manager + the
    SpatialIndex untouched so the dev can retry at a free tile.
    """

    def test_spawn_monster_on_player_marker_tile_rejected(self, session) -> None:
        """Spawning on the ``@`` marker's tile must fail without mutating
        state. This is the literal reproducer from #568 — goblin was
        invisible because it was placed under ``@``."""
        before_enemies = list(session.engine.game_state.active_enemies)
        before_monsters = {
            e.entity_id: (e.grid_x, e.grid_y) for e in session.entity_manager.get_monsters()
        }

        result = session.spawn_monster("goblin", session.player_x, session.player_y)

        assert "occupied" in result.lower() or "blocked" in result.lower(), (
            f"expected occupancy rejection, got: {result!r}"
        )
        # Engine state untouched: no new enemy entry.
        assert session.engine.game_state.active_enemies == before_enemies
        # Entity manager untouched: no new monster entity.
        after_monsters = {
            e.entity_id: (e.grid_x, e.grid_y) for e in session.entity_manager.get_monsters()
        }
        assert after_monsters == before_monsters

    def test_spawn_monster_on_party_member_tile_rejected(self, session) -> None:
        """Spawning on a party member's tile must fail with no state
        mutation, regardless of whether ``@`` happens to share that tile."""
        party = session.entity_manager.get_party_members()
        assert party, "fixture should populate at least one party member"
        pm = party[0]
        before_enemies = list(session.engine.game_state.active_enemies)
        before_monsters = {
            e.entity_id: (e.grid_x, e.grid_y) for e in session.entity_manager.get_monsters()
        }

        result = session.spawn_monster("goblin", pm.grid_x, pm.grid_y)

        assert "occupied" in result.lower() or "blocked" in result.lower(), (
            f"expected occupancy rejection, got: {result!r}"
        )
        assert session.engine.game_state.active_enemies == before_enemies
        after_monsters = {
            e.entity_id: (e.grid_x, e.grid_y) for e in session.entity_manager.get_monsters()
        }
        assert after_monsters == before_monsters

    def test_spawn_monster_on_existing_monster_tile_rejected(self, session) -> None:
        """A second spawn on a tile already holding a monster must fail."""
        monsters = session.entity_manager.get_monsters()
        assert monsters, "fixture should populate at least one monster"
        m = monsters[0]
        before_enemies = list(session.engine.game_state.active_enemies)

        result = session.spawn_monster("goblin", m.grid_x, m.grid_y)

        assert "occupied" in result.lower() or "blocked" in result.lower(), (
            f"expected occupancy rejection, got: {result!r}"
        )
        assert session.engine.game_state.active_enemies == before_enemies

    def test_spawn_monster_on_free_tile_still_succeeds(self, session) -> None:
        """Sanity check — the occupancy gate must not block legitimate
        spawns on empty tiles."""
        gx, gy = session.player_x + 3, session.player_y
        # Confirm the target tile is genuinely free in this fixture.
        assert session.entity_manager.get_at_position(gx, gy) is None
        assert (gx, gy) != (session.player_x, session.player_y)

        result = session.spawn_monster("giant_rat", gx, gy)

        assert "occupied" not in result.lower()
        assert "blocked" not in result.lower()
        # Monster reached the entity manager at the requested tile.
        ent = session.entity_manager.get_at_position(gx, gy)
        assert ent is not None
        assert ent.sub_type == "giant_rat"


class TestSessionEnemyTurnSingleAdvance:
    """Regression tests for #569.

    Before the fix, ``_process_enemy_turn()`` called
    ``engine.advance_turn()`` *after* ``engine.process_enemy_turn()``,
    but the engine's ``process_enemy_turn`` already advances the
    initiative tracker internally on every return path (party-wipe
    branch aside). The result was a double-``next_turn()`` per enemy
    turn — the next combatant was silently skipped and their
    ``TurnState`` was never observed.

    The symptom in playtest was a "Movement: N ft remaining" line that
    appeared to carry over stale movement budget between combatant
    turns: with the skipped combatant invisible to the MCP renderer,
    each enemy drain pushed initiative forward by 2 slots and the
    user couldn't see whose turn state was actually being rendered.
    """

    def test_process_enemy_turn_advances_initiative_by_one(self, session) -> None:
        """One ``_process_enemy_turn()`` call must advance the initiative
        index by exactly one slot — not two."""
        # Add a second PC so we have ≥3 combatants and can detect a
        # turn-skip (with 2 combatants the wrap masks the bug).
        session.spawn_character("wizard", "human", ["dagger"], 4, 5, name="Bob")
        tracker = session.engine.game_state.initiative_tracker
        combatants = tracker.get_all_combatants()

        # Force the goblin to be current so we exercise the non-PC path.
        goblin_idx = next(
            i for i, c in enumerate(combatants) if "goblin" in c.creature.name.lower()
        )
        tracker.current_turn_index = goblin_idx
        # Reset goblin's turn state so the start condition is well-defined.
        tracker.get_current_turn_state().reset(
            speed=tracker.get_current_combatant().creature.speed
        )

        session.processing_enemy_turn = True
        session._process_enemy_turn()

        expected_idx = (goblin_idx + 1) % len(combatants)
        expected_name = combatants[expected_idx].creature.name
        actual_name = tracker.get_current_combatant().creature.name
        assert actual_name == expected_name, (
            f"_process_enemy_turn skipped a combatant: expected next = "
            f"{expected_name} (idx {expected_idx}), got {actual_name} "
            f"(idx {tracker.current_turn_index})"
        )

    def test_process_enemy_turn_calls_next_turn_once(self, session) -> None:
        """The session's enemy-turn handler must not double-trigger
        ``initiative_tracker.next_turn()`` — once via the engine's
        ``process_enemy_turn`` (which already advances) and once via a
        redundant session-side ``advance_turn`` call."""
        session.spawn_character("wizard", "human", ["dagger"], 4, 5, name="Bob")
        tracker = session.engine.game_state.initiative_tracker

        # Force the goblin current.
        combatants = tracker.get_all_combatants()
        goblin_idx = next(
            i for i, c in enumerate(combatants) if "goblin" in c.creature.name.lower()
        )
        tracker.current_turn_index = goblin_idx
        tracker.get_current_turn_state().reset(
            speed=tracker.get_current_combatant().creature.speed
        )

        # Count next_turn() calls.
        original_next_turn = tracker.next_turn
        call_count = {"n": 0}

        def counting_next_turn() -> None:
            call_count["n"] += 1
            original_next_turn()

        tracker.next_turn = counting_next_turn

        session.processing_enemy_turn = True
        session._process_enemy_turn()

        assert call_count["n"] == 1, (
            f"expected exactly one next_turn() per enemy turn, got {call_count['n']}"
        )

    def test_next_combatant_after_enemy_turn_has_full_movement(self, session) -> None:
        """After a single enemy turn drain, the new current combatant's
        ``movement_remaining`` must equal their full speed — proving the
        engine's per-turn reset wasn't masked by a skipped slot."""
        session.spawn_character("wizard", "human", ["dagger"], 4, 5, name="Bob")
        tracker = session.engine.game_state.initiative_tracker
        combatants = tracker.get_all_combatants()

        goblin_idx = next(
            i for i, c in enumerate(combatants) if "goblin" in c.creature.name.lower()
        )
        tracker.current_turn_index = goblin_idx
        tracker.get_current_turn_state().reset(
            speed=tracker.get_current_combatant().creature.speed
        )

        session.processing_enemy_turn = True
        session._process_enemy_turn()

        new_current = tracker.get_current_combatant()
        new_turn_state = tracker.get_current_turn_state()
        assert new_turn_state.movement_remaining == new_current.creature.speed, (
            f"{new_current.creature.name} movement_remaining is "
            f"{new_turn_state.movement_remaining}, expected "
            f"{new_current.creature.speed}"
        )


class TestEngineAdapterEnemyTurnRichFields:
    """Plan #570 fix Phase 3: pass through rich ``EnemyTurnResult`` fields.

    The engine returns an ``EnemyTurnResult`` dataclass packed with attack
    roll details, saving throw outcomes, turn-effect messages, and the
    distinguishing ``action_taken`` enum. Before this fix the engine
    adapter flattened the result to seven fields, dropping everything the
    MCP-facing session layer needs to render an informative ``Between
    turns:`` block. The session then collapsed all five "no attack" action
    paths to a single ``"<enemy> takes no action."`` line — so a goblin
    that died before its turn looked identical to one that's stunned or
    out of targets (#570).
    """

    def test_adapter_passes_attack_roll_details(self, session) -> None:
        """When the goblin attacks, the adapter dict must include
        ``attack_roll``, ``attack_bonus``, ``target_ac``, and ``critical``
        so the session can render the same ``roll X+Y=Z vs AC W`` line PC
        attacks already produce."""
        adjacent_x = session.player_x + 1
        adjacent_y = session.player_y
        session.spawn_monster("goblin", adjacent_x, adjacent_y)

        goblin = session.engine.game_state.active_enemies[-1]
        _force_combatant_turn(session, goblin)
        session.set_seed(42)

        result = session.engine.process_enemy_turn()

        assert result["success"] is True
        assert result["action"] == "ATTACK"
        # Attack-resolution fields land regardless of hit/miss.
        assert "attack_roll" in result and isinstance(result["attack_roll"], int)
        assert "attack_bonus" in result and isinstance(result["attack_bonus"], int)
        assert "target_ac" in result and isinstance(result["target_ac"], int)
        assert "critical" in result and isinstance(result["critical"], bool)

    def test_adapter_passes_turn_effect_messages_as_strings(self, session) -> None:
        """``turn_start_effects`` / ``turn_end_effects`` arrive as lists
        of plain strings — the session layer must not need to import
        engine dataclasses to render them. Even on a vanilla goblin turn
        with no effects, the keys are present and empty."""
        adjacent_x = session.player_x + 1
        adjacent_y = session.player_y
        session.spawn_monster("goblin", adjacent_x, adjacent_y)

        goblin = session.engine.game_state.active_enemies[-1]
        _force_combatant_turn(session, goblin)
        session.set_seed(42)

        result = session.engine.process_enemy_turn()

        assert "turn_start_effects" in result
        assert isinstance(result["turn_start_effects"], list)
        assert all(isinstance(m, str) for m in result["turn_start_effects"])
        assert "turn_end_effects" in result
        assert isinstance(result["turn_end_effects"], list)
        assert all(isinstance(m, str) for m in result["turn_end_effects"])

    def test_adapter_passes_saving_throw_fields(self, session) -> None:
        """Saving throw fields are present (with ``None`` defaults when
        the attack didn't trigger one) so the session's save-line emitter
        can branch on ``saving_throw_triggered`` without ``KeyError``."""
        adjacent_x = session.player_x + 1
        adjacent_y = session.player_y
        session.spawn_monster("goblin", adjacent_x, adjacent_y)

        goblin = session.engine.game_state.active_enemies[-1]
        _force_combatant_turn(session, goblin)
        session.set_seed(42)

        result = session.engine.process_enemy_turn()

        assert "saving_throw_triggered" in result
        assert isinstance(result["saving_throw_triggered"], bool)
        # save_ability / save_dc / save_succeeded may be None when not
        # triggered, but the keys must be present.
        assert "save_ability" in result
        assert "save_dc" in result
        assert "save_succeeded" in result
        assert "conditions_applied" in result
        assert isinstance(result["conditions_applied"], list)

    def test_adapter_passes_misc_rich_fields(self, session) -> None:
        """``incapacitating_conditions``, ``condition_removal_message``,
        and ``concentration_broken`` round out the surface the session
        needs. All present with safe defaults when not applicable."""
        adjacent_x = session.player_x + 1
        adjacent_y = session.player_y
        session.spawn_monster("goblin", adjacent_x, adjacent_y)

        goblin = session.engine.game_state.active_enemies[-1]
        _force_combatant_turn(session, goblin)
        session.set_seed(42)

        result = session.engine.process_enemy_turn()

        assert "incapacitating_conditions" in result
        assert isinstance(result["incapacitating_conditions"], list)
        assert "condition_removal_message" in result
        # ``None`` when no condition-removal attempt was made.
        assert result["condition_removal_message"] is None or isinstance(
            result["condition_removal_message"], str
        )
        assert "concentration_broken" in result
        # ``None`` when no concentration check fired.
        assert result["concentration_broken"] is None or isinstance(
            result["concentration_broken"], dict
        )


def _enemy_turn_stub(**overrides) -> dict:
    """Build a baseline adapter ``process_enemy_turn`` result dict.

    Monkeypatch helper for the action-type / rich-detail surface tests
    below: pass only the keys that differ from a vanilla goblin attack
    and the rest fill in with safe defaults that mirror the real
    adapter's shape (#570).
    """
    base = {
        "success": True,
        "action": "ATTACK",
        "enemy_name": "Goblin",
        "target_name": "Archy",
        "hit": True,
        "damage": 4,
        "target_killed": False,
        "combat_ended": False,
        "attack_roll": 15,
        "attack_bonus": 4,
        "target_ac": 12,
        "critical": False,
        "action_name": "Bite",
        "saving_throw_triggered": False,
        "save_ability": None,
        "save_dc": None,
        "save_succeeded": None,
        "conditions_applied": [],
        "incapacitating_conditions": [],
        "condition_removal_message": None,
        "concentration_broken": None,
        "turn_start_effects": [],
        "turn_end_effects": [],
    }
    base.update(overrides)
    return base


class TestEnemyTurnActionTypes:
    """Plan #570 fix Phase 4: distinguish the five non-ATTACK action types.

    ``GameSession._process_enemy_turn`` previously collapsed every
    non-attack path to ``"<enemy> takes no action."`` — a goblin that
    died before its turn looked identical to one that's stunned, has no
    targets, has no usable attack, or is shaking off a condition. The
    fix branches on ``result["action"]`` and emits a distinguishing line
    so the MCP-facing ``Between turns:`` block tells the player WHY
    combat is stalling.
    """

    def _drain_one_enemy_turn(self, session, stub_result: dict) -> list[str]:
        """Run the drain through a single monkeypatched enemy turn and
        return the resulting per-turn event lines.

        Pins is_player_turn to ``False`` for the first drain iteration
        (so ``_process_enemy_turn`` runs against the stubbed adapter)
        and ``True`` for every subsequent iteration (so the drain
        exits cleanly after one step regardless of the real initiative
        state).
        """
        session.engine.process_enemy_turn = lambda: stub_result  # type: ignore[assignment]
        session.engine.is_current_combatant_unconscious = lambda: False  # type: ignore[assignment]

        calls = {"n": 0}

        def enemy_then_player() -> bool:
            calls["n"] += 1
            return calls["n"] > 1

        session.engine.is_player_turn = enemy_then_player  # type: ignore[assignment]
        session.processing_enemy_turn = True
        session._pending_combat_events.clear()
        session._drain_enemy_turns()
        return list(session._pending_combat_events)

    def test_died_start_of_turn_emits_distinct_line(self, session) -> None:
        """A goblin that drops dead from start-of-turn poison damage
        produces a line that names the cause, not the generic
        ``"takes no action"``."""
        events = self._drain_one_enemy_turn(
            session,
            _enemy_turn_stub(action="DIED_START_OF_TURN", hit=None, damage=0),
        )
        joined = " | ".join(events).lower()
        assert "died before its turn" in joined, (
            f"missing died-start-of-turn line:\n{events}"
        )
        assert "takes no action" not in joined

    def test_incapacitated_emits_distinct_line(self, session) -> None:
        """A stunned / paralyzed goblin produces a line that names the
        incapacitating condition."""
        events = self._drain_one_enemy_turn(
            session,
            _enemy_turn_stub(
                action="INCAPACITATED",
                hit=None,
                damage=0,
                incapacitating_conditions=["STUNNED"],
            ),
        )
        joined = " | ".join(events).lower()
        assert "cannot act" in joined, f"missing cannot-act line:\n{events}"
        assert "stunned" in joined, f"missing condition name:\n{events}"
        assert "takes no action" not in joined

    def test_no_targets_emits_distinct_line(self, session) -> None:
        """When the AI finds no valid target the response says so —
        otherwise the player has no idea why combat is stalling."""
        events = self._drain_one_enemy_turn(
            session,
            _enemy_turn_stub(action="NO_TARGETS", hit=None, damage=0, target_name=None),
        )
        joined = " | ".join(events).lower()
        assert "no valid targets" in joined, (
            f"missing no-valid-targets line:\n{events}"
        )
        assert "takes no action" not in joined

    def test_no_valid_attack_emits_distinct_line(self, session) -> None:
        """Distinct from NO_TARGETS — the AI sees the PC but has no
        weapon/action that reaches them."""
        events = self._drain_one_enemy_turn(
            session,
            _enemy_turn_stub(action="NO_VALID_ATTACK", hit=None, damage=0),
        )
        joined = " | ".join(events).lower()
        assert "no usable attack" in joined, (
            f"missing no-usable-attack line:\n{events}"
        )
        assert "takes no action" not in joined

    def test_condition_removal_emits_message(self, session) -> None:
        """When the goblin uses its turn to shake off a condition, the
        engine's removal message surfaces in the response — players see
        why the AI didn't attack this round."""
        events = self._drain_one_enemy_turn(
            session,
            _enemy_turn_stub(
                action="CONDITION_REMOVAL",
                hit=None,
                damage=0,
                condition_removal_message=(
                    "Goblin attempts to shake off POISONED - SUCCESS!"
                ),
            ),
        )
        assert any(
            "shake off POISONED" in line for line in events
        ), f"missing condition-removal message:\n{events}"


class TestEnemyTurnAttackRollDetail:
    """Plan #570 fix Phase 5: attack-roll detail parity with PC attacks.

    PC attacks render ``roll X+Y=Z vs AC W -> HIT/MISS`` in the response
    so the player can audit the math. Enemy attacks used to render only
    ``"Goblin hits Abe for 4 damage!"`` — the player saw HP drop without
    knowing the roll or AC, and couldn't tell whether the AI was rolling
    above-average. This phase brings enemy attacks to parity.
    """

    HIT_LINE_PREFIX = "Goblin attacks Archy with Bite:"

    def test_hit_line_includes_roll_bonus_and_ac(self, session) -> None:
        """Hit line carries the d20, bonus, total, AC, and damage."""
        events = TestEnemyTurnActionTypes()._drain_one_enemy_turn(
            session,
            _enemy_turn_stub(
                hit=True,
                attack_roll=15,
                attack_bonus=4,
                target_ac=12,
                damage=5,
            ),
        )
        attack_lines = [line for line in events if "Goblin attacks Archy" in line]
        assert attack_lines, f"missing attack-roll line:\n{events}"
        line = attack_lines[0]
        assert "roll 15+4=19" in line, line
        assert "AC 12" in line, line
        assert "HIT" in line, line
        assert "5 damage" in line, line

    def test_miss_line_includes_roll_bonus_and_ac(self, session) -> None:
        """Miss line carries the same detail so the player sees why."""
        events = TestEnemyTurnActionTypes()._drain_one_enemy_turn(
            session,
            _enemy_turn_stub(
                hit=False,
                damage=0,
                attack_roll=3,
                attack_bonus=4,
                target_ac=15,
            ),
        )
        attack_lines = [line for line in events if "Goblin attacks Archy" in line]
        assert attack_lines, f"missing attack-roll line:\n{events}"
        line = attack_lines[0]
        assert "roll 3+4=7" in line, line
        assert "AC 15" in line, line
        assert "MISS" in line, line

    def test_critical_hit_annotated(self, session) -> None:
        """A nat-20 must annotate the line as a CRITICAL HIT."""
        events = TestEnemyTurnActionTypes()._drain_one_enemy_turn(
            session,
            _enemy_turn_stub(
                hit=True,
                critical=True,
                attack_roll=20,
                attack_bonus=4,
                target_ac=12,
                damage=9,
            ),
        )
        attack_lines = [line for line in events if "Goblin attacks Archy" in line]
        assert attack_lines, f"missing attack-roll line:\n{events}"
        assert "CRITICAL HIT" in attack_lines[0], attack_lines[0]

    def test_target_down_line_still_emitted_on_killing_blow(self, session) -> None:
        """The ``"<target> is down!"`` line still surfaces alongside the
        attack-roll line on a killing blow."""
        events = TestEnemyTurnActionTypes()._drain_one_enemy_turn(
            session,
            _enemy_turn_stub(
                hit=True,
                target_killed=True,
                damage=8,
                attack_roll=18,
                attack_bonus=4,
                target_ac=12,
            ),
        )
        assert any("is down" in line for line in events), (
            f"missing down line:\n{events}"
        )

    def test_unnamed_action_falls_back_to_attack(self, session) -> None:
        """When the engine omits ``action_name`` (e.g. legacy data), the
        line still renders sensibly using ``"attack"`` rather than
        ``"None"``."""
        events = TestEnemyTurnActionTypes()._drain_one_enemy_turn(
            session,
            _enemy_turn_stub(hit=True, action_name=None),
        )
        attack_lines = [line for line in events if "Goblin attacks Archy" in line]
        assert attack_lines, f"missing attack-roll line:\n{events}"
        assert "None" not in attack_lines[0], attack_lines[0]
        assert "attack" in attack_lines[0].lower(), attack_lines[0]


class TestEnemyTurnEffectMessages:
    """Plan #570 fix Phase 6: surface per-turn effect messages.

    ``EnemyTurnResult`` carries ``turn_start_effects`` (e.g. ongoing
    poison damage at start of turn) and ``turn_end_effects`` (e.g.
    POISONED condition expired). Both were silent in the response;
    players could not see why an enemy's HP changed or why a condition
    they'd applied vanished mid-fight.
    """

    def test_turn_start_effect_messages_surface(self, session) -> None:
        """Start-of-turn effect strings appear before the action line."""
        events = TestEnemyTurnActionTypes()._drain_one_enemy_turn(
            session,
            _enemy_turn_stub(
                turn_start_effects=[
                    "Goblin takes 2 poison damage at start of turn."
                ],
            ),
        )
        assert any(
            "2 poison damage" in line for line in events
        ), f"missing turn-start effect line:\n{events}"

    def test_turn_end_effect_messages_surface(self, session) -> None:
        """End-of-turn effect strings appear after the action line."""
        events = TestEnemyTurnActionTypes()._drain_one_enemy_turn(
            session,
            _enemy_turn_stub(
                turn_end_effects=[
                    "POISONED on Goblin has expired!",
                ],
            ),
        )
        assert any(
            "expired" in line.lower() for line in events
        ), f"missing turn-end effect line:\n{events}"

    def test_effect_messages_preserve_order_around_action_line(self, session) -> None:
        """Start effects come before the attack line; end effects come
        after. Order matters because effects narrate the timing of when
        damage / conditions resolved (start of turn vs end of turn)."""
        events = TestEnemyTurnActionTypes()._drain_one_enemy_turn(
            session,
            _enemy_turn_stub(
                turn_start_effects=["Goblin takes 2 poison damage at start of turn."],
                turn_end_effects=["POISONED on Goblin has expired!"],
            ),
        )
        start_idx = next(
            (i for i, line in enumerate(events) if "poison damage" in line), -1
        )
        attack_idx = next(
            (i for i, line in enumerate(events) if "Goblin attacks Archy" in line), -1
        )
        end_idx = next(
            (i for i, line in enumerate(events) if "expired" in line.lower()), -1
        )
        assert start_idx != -1 and attack_idx != -1 and end_idx != -1, (
            f"missing one of start/attack/end lines:\n{events}"
        )
        assert start_idx < attack_idx < end_idx, (
            f"line order wrong (start={start_idx}, attack={attack_idx}, "
            f"end={end_idx}):\n{events}"
        )

    def test_effect_messages_surface_even_when_no_attack(self, session) -> None:
        """A stunned goblin with a turn-start poison tick produces both
        the poison line and the "cannot act" line."""
        events = TestEnemyTurnActionTypes()._drain_one_enemy_turn(
            session,
            _enemy_turn_stub(
                action="INCAPACITATED",
                hit=None,
                damage=0,
                incapacitating_conditions=["STUNNED"],
                turn_start_effects=["Goblin takes 1 fire damage at start of turn."],
            ),
        )
        assert any("fire damage" in line for line in events), events
        assert any("cannot act" in line.lower() for line in events), events


class TestEnemyTurnSavingThrowLine:
    """Plan #570 fix Phase 7: surface saving throws triggered by enemy attacks.

    A goblin's poison-bite or a stirge's blood-drain can force the
    target to make a saving throw. ``EnemyTurnResult`` carries
    ``saving_throw_triggered`` + ability + DC + outcome + conditions
    applied, but the session dropped all of it. The target's player saw
    bite damage land but had no idea a condition was about to be
    applied or that they passed the save.
    """

    def test_failed_save_emits_line_with_condition_applied(self, session) -> None:
        events = TestEnemyTurnActionTypes()._drain_one_enemy_turn(
            session,
            _enemy_turn_stub(
                hit=True,
                damage=4,
                saving_throw_triggered=True,
                save_ability="Constitution",
                save_dc=11,
                save_succeeded=False,
                conditions_applied=["poisoned"],
            ),
        )
        save_lines = [line for line in events if "save" in line.lower()]
        assert save_lines, f"missing save line:\n{events}"
        line = save_lines[0]
        assert "DC 11" in line, line
        assert "Constitution" in line, line
        assert "FAILED" in line, line
        assert "POISONED" in line, line

    def test_successful_save_emits_line_without_condition(self, session) -> None:
        events = TestEnemyTurnActionTypes()._drain_one_enemy_turn(
            session,
            _enemy_turn_stub(
                hit=True,
                damage=4,
                saving_throw_triggered=True,
                save_ability="Constitution",
                save_dc=11,
                save_succeeded=True,
                conditions_applied=[],
            ),
        )
        save_lines = [line for line in events if "save" in line.lower()]
        assert save_lines, f"missing save line:\n{events}"
        line = save_lines[0]
        assert "DC 11" in line, line
        assert "Constitution" in line, line
        assert "SUCCEEDED" in line, line
        # No condition applied on a successful save.
        assert "POISONED" not in line, line

    def test_no_save_line_when_save_not_triggered(self, session) -> None:
        """A vanilla bite that didn't trigger a save produces NO save
        line — the line is gated on ``saving_throw_triggered``."""
        events = TestEnemyTurnActionTypes()._drain_one_enemy_turn(
            session,
            _enemy_turn_stub(hit=True, damage=4, saving_throw_triggered=False),
        )
        assert not any("save" in line.lower() for line in events), (
            f"unexpected save line:\n{events}"
        )


class TestEnemyTurnConcentrationBroken:
    """Plan #570 fix Phase 8: surface concentration breaks.

    When an enemy attack damages a concentrating spellcaster and the
    target fails the resulting Constitution save, ``EnemyTurnResult``
    sets ``concentration_broken`` with the spell name + DC. The session
    dropped this entirely, so a wizard's bless or hold-person silently
    ended mid-fight with no log line — the caster's player had to
    notice from a missing buff bar.
    """

    def test_concentration_broken_line_surfaces(self, session) -> None:
        events = TestEnemyTurnActionTypes()._drain_one_enemy_turn(
            session,
            _enemy_turn_stub(
                hit=True,
                damage=8,
                concentration_broken={
                    "was_concentrating": True,
                    "concentration_broken": True,
                    "spell_name": "bless",
                    "dc": 10,
                    "save_result": {"success": False, "total": 7},
                },
            ),
        )
        conc_lines = [line for line in events if "concentration" in line.lower()]
        assert conc_lines, f"missing concentration-broken line:\n{events}"
        line = conc_lines[0]
        assert "Archy" in line, line
        assert "bless" in line, line

    def test_no_concentration_line_when_payload_absent(self, session) -> None:
        events = TestEnemyTurnActionTypes()._drain_one_enemy_turn(
            session,
            _enemy_turn_stub(hit=True, damage=4, concentration_broken=None),
        )
        assert not any(
            "concentration" in line.lower() for line in events
        ), f"unexpected concentration line:\n{events}"


class TestIssue570Reproduction:
    """End-to-end acceptance for the #570 bug report.

    Recreates the reporter's trace as faithfully as the test fixtures
    allow: spawn an adjacent goblin, pin its turn, and call ``wait()``.
    The response string must contain the ``Between turns:`` header
    AND an attack-roll-detail line (``roll X+Y=Z vs AC W``) — without
    that the caller has no way to audit the 14→0 HP TPK the reporter
    saw.
    """

    def test_wait_response_contains_attack_roll_detail(self, session) -> None:
        adjacent_x = session.player_x + 1
        adjacent_y = session.player_y
        session.spawn_monster("goblin", adjacent_x, adjacent_y)

        goblin = session.engine.game_state.active_enemies[-1]
        _force_combatant_turn(session, goblin)
        session.processing_enemy_turn = False
        session.set_seed(42)

        response = session.wait()

        assert "Between turns:" in response, (
            f"missing Between turns header:\n{response}"
        )
        # Attack-roll-detail line is the acceptance criterion — without
        # it the caller can't audit the goblin's roll vs. AC or know
        # what action was used.
        assert "Goblin attacks" in response, (
            f"missing 'Goblin attacks' phrasing:\n{response}"
        )
        assert " vs AC " in response, (
            f"missing AC annotation:\n{response}"
        )
        assert " roll " in response, (
            f"missing roll annotation:\n{response}"
        )
        # And one of HIT/MISS/CRITICAL HIT must be present.
        assert any(
            tok in response for tok in ("HIT", "MISS", "CRITICAL HIT")
        ), f"missing outcome token:\n{response}"

    def test_wait_response_includes_hp_or_damage_detail(self, session) -> None:
        """On a hit the response includes the damage. On a miss the
        attack-roll line itself carries the AC vs. roll detail. Either
        way the caller can tell what happened to the party."""
        adjacent_x = session.player_x + 1
        adjacent_y = session.player_y
        session.spawn_monster("goblin", adjacent_x, adjacent_y)

        goblin = session.engine.game_state.active_enemies[-1]
        _force_combatant_turn(session, goblin)
        session.processing_enemy_turn = False
        session.set_seed(42)

        response = session.wait()

        # Either a damage annotation (hit) or the explicit "MISS" form.
        assert " damage" in response or "MISS" in response, (
            f"response carries neither damage nor MISS:\n{response}"
        )
