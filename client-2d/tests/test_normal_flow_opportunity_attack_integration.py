# ABOUTME: Integration test — the normal vault-party room-entry flow bootstraps
# ABOUTME: the engine SpatialIndex and surfaces monster Opportunity Attacks (#613).

"""The scenario load path already bootstraps spatial and surfaces Opportunity
Attacks (see test_opportunity_attack_surface_integration.py). This test proves
the *normal game* flow — vault party -> peaceful start room -> walk into a
hostile room (``_transition_room``) -> combat + party spread — does the same,
rather than leaving ``GameState.spatial`` dormant (``None``) so OAs never fire
in real play.

Driven through the genuine room-entry flow: ``initialize()`` lands in the
peaceful ``cellar.stairs`` (no enemies), then a step ``north`` transitions into
``cellar.storage`` (4 giant rats) which starts combat. This mirrors how
monsters actually enter play — ``_transition_room`` moves first (populating
``active_enemies``), then loads the room layout (creating monster entities),
then spreads the party — unlike a combat start-room where the layout loads
before enemies exist.
"""

from __future__ import annotations

import pytest

from dnd_engine.core.entity_ids import pc_entity_id


@pytest.fixture
def combat_session():
    """A normal-flow session that walked into the rat storage room."""
    from client_2d.session import GameSession

    s = GameSession(enable_mcp=False, dev_mode=True)
    s.initialize(
        dungeon_name="cellar",
        campaign_id="poisoned_laboratory",
        start_room="cellar.stairs",
    )
    if s.engine.in_combat:
        pytest.skip("start room unexpectedly started combat")

    # Walk north into cellar.storage — the real room-entry-into-combat path.
    s._move_player("north")
    if not s.engine.in_combat:
        pytest.skip("transition into cellar.storage did not start combat")
    return s


def _force_player_turn(session, pc) -> None:
    """Make the PC the current combatant with a full movement budget so
    ``combat_move`` runs the engine step instead of bouncing on
    'Not your turn'."""
    tracker = session.engine.game_state.initiative_tracker
    pc_index = next(i for i, entry in enumerate(tracker.combatants) if entry.creature is pc)
    tracker.current_turn_index = pc_index
    tracker.turn_states[pc].reset(speed=pc.speed)


class TestNormalFlowSurfacesOpportunityAttack:
    def test_initialize_bootstraps_spatial(self, combat_session) -> None:
        """The normal room-entry flow must install the SpatialIndex; without
        it the plan-03 movement stack and Opportunity Attacks stay dormant."""
        game_state = combat_session.engine.game_state
        assert game_state.spatial is not None, (
            "normal-game initialize() must bootstrap spatial like the scenario "
            "path; otherwise OAs never fire in real vault-party play"
        )

    def test_combat_move_out_of_reach_surfaces_oa_hit(self, combat_session) -> None:
        session = combat_session
        game_state = session.engine.game_state
        assert game_state.spatial is not None, "normal flow must bootstrap spatial"

        monsters = session.entity_manager.get_monsters()
        if not monsters:
            pytest.skip("no monster entities to provoke an Opportunity Attack")
        monster = monsters[0]

        pc = session.engine.party.characters[0]
        # Force the monster's Opportunity Attack to connect deterministically:
        # AC 1 means only a natural 1 misses, and we pin the dice seed.
        pc.ac = 1
        session.set_seed(7)

        # Stand the PC and the monster adjacent (5 ft) so a single step north
        # puts the PC 10 ft away — leaving the monster's reach and provoking.
        session.set_position(pc_entity_id(pc.name), 5, 5)
        session.set_position(monster.entity_id, 5, 6)
        _force_player_turn(session, pc)

        # PC steps north (5,5) -> (5,4): now 10 ft from the monster.
        response = session.combat_move("north")

        # The move itself succeeds...
        assert "Moved north" in response
        # ...and the provoked Opportunity Attack is surfaced to the player.
        assert "opportunity attack" in response.lower(), (
            "combat_move must surface the monster's Opportunity Attack, not "
            f"drop it silently. Got:\n{response}"
        )
        assert monster.creature.name in response
