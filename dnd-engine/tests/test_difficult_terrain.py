# ABOUTME: Tests for difficult-terrain movement cost multiplier (issue #436)
# ABOUTME: Verifies Terrain enum, cost_for helper, and TurnState.consume_movement(terrain=...)

import pytest

from dnd_engine.systems.action_economy import Terrain, TurnState, cost_for


class TestTerrainEnum:
    """Terrain enum exposes the SRD-relevant terrain kinds."""

    def test_normal_value(self):
        assert Terrain.NORMAL.value == "normal"

    def test_difficult_value(self):
        assert Terrain.DIFFICULT.value == "difficult"

    def test_terrain_is_str_enum(self):
        # Terrain(str, Enum) matches the pattern used by ActionType-style enums
        # elsewhere in the codebase and allows JSON-friendly serialization.
        assert isinstance(Terrain.NORMAL.value, str)
        assert isinstance(Terrain.DIFFICULT.value, str)


class TestCostFor:
    """cost_for centralizes the per-foot multiplier for a terrain kind."""

    def test_normal_terrain_is_one_to_one(self):
        assert cost_for(5, Terrain.NORMAL) == 5

    def test_difficult_terrain_doubles_cost(self):
        # SRD: "Each foot of movement in difficult terrain costs 1 extra foot."
        assert cost_for(5, Terrain.DIFFICULT) == 10

    def test_zero_feet_normal_is_zero(self):
        assert cost_for(0, Terrain.NORMAL) == 0

    def test_zero_feet_difficult_is_zero(self):
        assert cost_for(0, Terrain.DIFFICULT) == 0

    def test_fifteen_feet_difficult(self):
        assert cost_for(15, Terrain.DIFFICULT) == 30

    @pytest.mark.parametrize(
        "feet,terrain,expected_cost",
        [
            (5, Terrain.NORMAL, 5),
            (5, Terrain.DIFFICULT, 10),
            (10, Terrain.NORMAL, 10),
            (10, Terrain.DIFFICULT, 20),
            (1, Terrain.DIFFICULT, 2),
        ],
    )
    def test_cost_table(self, feet, terrain, expected_cost):
        assert cost_for(feet, terrain) == expected_cost


class TestConsumeMovementBackwardCompat:
    """Existing callers (no terrain kwarg) continue to behave exactly as before."""

    def test_default_terrain_normal_deducts_feet_unchanged(self):
        turn = TurnState(movement_remaining=30)
        result = turn.consume_movement(feet=5)
        assert result is True
        assert turn.movement_remaining == 25

    def test_default_call_with_no_args_still_deducts_five(self):
        turn = TurnState(movement_remaining=30)
        result = turn.consume_movement()
        assert result is True
        assert turn.movement_remaining == 25


class TestConsumeMovementDifficultTerrain:
    """Difficult terrain doubles the cost deducted from movement_remaining."""

    def test_difficult_terrain_deducts_double(self):
        turn = TurnState(movement_remaining=30)
        result = turn.consume_movement(feet=5, terrain=Terrain.DIFFICULT)
        assert result is True
        assert turn.movement_remaining == 20

    def test_difficult_terrain_explicit_normal_matches_default(self):
        turn = TurnState(movement_remaining=30)
        result = turn.consume_movement(feet=5, terrain=Terrain.NORMAL)
        assert result is True
        assert turn.movement_remaining == 25

    def test_insufficient_movement_in_difficult_terrain_does_not_deduct(self):
        # consume_movement's existing contract: check bounds, return False
        # without deducting if insufficient. Difficult terrain must respect
        # the same contract.
        turn = TurnState(movement_remaining=5)
        result = turn.consume_movement(feet=5, terrain=Terrain.DIFFICULT)
        assert result is False
        assert turn.movement_remaining == 5

    def test_exactly_enough_movement_in_difficult_terrain(self):
        turn = TurnState(movement_remaining=10)
        result = turn.consume_movement(feet=5, terrain=Terrain.DIFFICULT)
        assert result is True
        assert turn.movement_remaining == 0
