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
SCENARIO_DIR = (
    Path(__file__).parent.parent.parent
    / "dnd-engine"
    / "tests"
    / "scenarios"
    / "yaml"
)


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
        assert session.engine.game_state.active_enemies[0].name.lower().startswith(
            "goblin"
        )

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
        session.spawn_character(
            "fighter", "human", ["longsword"], 4, 5, name="Probe"
        )
        after = len(session.engine.party.characters)
        assert after == before + 1
        assert session.engine.party.characters[-1].name == "Probe"

    def test_spawn_monster_from_exploration_keeps_party_positions(
        self, session
    ) -> None:
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
            e.entity_id: (e.grid_x, e.grid_y)
            for e in session.entity_manager.get_party_members()
        }
        assert before, "fixture should have at least one party member"

        session.spawn_monster("goblin", 12, 5)

        # Same ids, same positions — no spread.
        after = {
            e.entity_id: (e.grid_x, e.grid_y)
            for e in session.entity_manager.get_party_members()
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

    def test_spawn_monster_in_combat_preserves_party_positions(
        self, session
    ) -> None:
        """Spawning a second enemy while already in combat must not respread.

        Pins the existing in-combat path: party positions stay put, second
        monster gets entity_id <monster_id>_1 at the requested tile.
        """
        before = {
            e.entity_id: (e.grid_x, e.grid_y)
            for e in session.entity_manager.get_party_members()
        }
        assert session.engine.in_combat is True

        session.spawn_monster("goblin", 8, 6)

        after = {
            e.entity_id: (e.grid_x, e.grid_y)
            for e in session.entity_manager.get_party_members()
        }
        assert after == before

        monsters = {
            e.entity_id: (e.grid_x, e.grid_y)
            for e in session.entity_manager.get_monsters()
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
