# ABOUTME: Integration test — the 2D client surfaces monster Opportunity Attacks
# ABOUTME: triggered when a PC moves out of reach during combat (plan-10 W1).

"""When a PC leaves a hostile creature's reach, the engine already fires
and resolves the Opportunity Attack and emits ``DAMAGE_DEALT`` tagged
``opportunity_attack`` (see dnd-engine test_oa_combat_step_integration).

This test asserts the *client* surfaces that hit in the ``combat_move``
wire response, rather than letting the PC silently take damage that only
shows up as an HP delta in the next state dump.
"""

from __future__ import annotations

from pathlib import Path

import pytest

SCENARIO_DIR = Path(__file__).parent.parent.parent / "dnd-engine" / "tests" / "scenarios" / "yaml"


@pytest.fixture
def combat_session():
    """A scenario-loaded session in combat with one goblin and Archy."""
    from client_2d.session import GameSession

    s = GameSession(enable_mcp=False, dev_mode=True)
    s.load_scenario(SCENARIO_DIR / "ranged_attack_basic.yaml")
    return s


def _force_player_turn(session, pc) -> None:
    """Make the PC the current combatant with a full movement budget so
    ``combat_move`` runs the engine step instead of bouncing on
    'Not your turn'."""
    tracker = session.engine.game_state.initiative_tracker
    pc_index = next(
        i for i, entry in enumerate(tracker.combatants) if entry.creature is pc
    )
    tracker.current_turn_index = pc_index
    tracker.turn_states[pc].reset(speed=pc.speed)


class TestClientSurfacesOpportunityAttack:
    def test_combat_move_out_of_reach_surfaces_oa_hit(self, combat_session) -> None:
        session = combat_session
        game_state = session.engine.game_state
        assert game_state.spatial is not None, "scenario must bootstrap spatial"

        pc = session.engine.party.characters[0]
        # Force the goblin's Opportunity Attack to connect deterministically:
        # AC 1 means only a natural 1 misses, and we pin the dice seed.
        pc.ac = 1
        session.set_seed(7)

        # Stand the PC and the goblin adjacent (5 ft) so a single step puts
        # the PC 10 ft away — leaving the goblin's reach and provoking.
        session.set_position("pc_archy", 5, 5)
        session.set_position("goblin_0", 5, 6)
        _force_player_turn(session, pc)

        # PC steps north (5,5) -> (5,4): now 10 ft from the goblin.
        response = session.combat_move("north")

        # The move itself succeeds...
        assert "Moved north" in response
        # ...and the provoked Opportunity Attack is surfaced to the player.
        assert "opportunity attack" in response.lower(), (
            "combat_move must surface the goblin's Opportunity Attack, not "
            f"drop it silently. Got:\n{response}"
        )
        assert "Goblin" in response
