# ABOUTME: Tests for GameState.attempt_combat_step — plan-03 P5 engine-owned combat-move validation.
# ABOUTME: Covers placement, blocking tile, occupancy, no-movement, terrain cost, and event emission.

from __future__ import annotations

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.game_state import GameState
from dnd_engine.core.map import Map, TileType
from dnd_engine.core.move_result import MoveResult
from dnd_engine.core.party import Party
from dnd_engine.core.position import Position
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.action_economy import Terrain, TurnState
from dnd_engine.systems.initiative import InitiativeTracker
from dnd_engine.utils.events import Event, EventBus, EventType


def _build_map_5x5_with_difficult() -> Map:
    """5x5 fixture: floors + a wall at (2, 1) + water (difficult) at (3, 0)."""
    tiles: dict[tuple[int, int], TileType] = {}
    for y in range(5):
        for x in range(5):
            tiles[(x, y)] = TileType.FLOOR
    tiles[(2, 1)] = TileType.WALL
    tiles[(3, 0)] = TileType.WATER  # walkable, difficult terrain
    return Map(width=5, height=5, tiles=tiles)


@pytest.fixture
def map_fixture() -> Map:
    return _build_map_5x5_with_difficult()


@pytest.fixture
def test_abilities() -> Abilities:
    return Abilities(
        strength=15, dexterity=14, constitution=13,
        intelligence=10, wisdom=12, charisma=8,
    )


@pytest.fixture
def party_of_one(test_abilities: Abilities) -> Party:
    fighter = Character(
        name="Fighter 1",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=test_abilities,
        max_hp=12,
        ac=16,
        xp=0,
    )
    return Party(characters=[fighter])


@pytest.fixture
def game_state(party_of_one: Party, map_fixture: Map) -> GameState:
    gs = GameState(
        party=party_of_one,
        dungeon_name="test_dungeon",
        event_bus=EventBus(),
        data_loader=DataLoader(),
        dice_roller=DiceRoller(),
    )
    gs.bootstrap_spatial(map_fixture)
    # Wire an initiative tracker with the party member so the engine
    # can find a TurnState. attempt_combat_step queries
    # initiative_tracker.get_current_turn_state().
    gs.initiative_tracker = InitiativeTracker(dice_roller=gs.dice_roller)
    pc = party_of_one.characters[0]
    gs.initiative_tracker.add_combatant(pc)
    # Force the tracker onto the PC so its TurnState is the current one.
    for idx, entry in enumerate(gs.initiative_tracker.combatants):
        if entry.creature is pc:
            gs.initiative_tracker.current_turn_index = idx
            break
    gs.initiative_tracker.turn_states[pc].reset(speed=pc.speed)
    return gs


@pytest.fixture
def entity_id(party_of_one: Party) -> str:
    pc = party_of_one.characters[0]
    return f"pc_{pc.name.lower().replace(' ', '_')}"


def _current_turn_state(gs: GameState) -> TurnState:
    ts = gs.initiative_tracker.get_current_turn_state()
    assert ts is not None
    return ts


def _capture(bus: EventBus, event_type: EventType) -> list[Event]:
    captured: list[Event] = []
    bus.subscribe(event_type, captured.append)
    return captured


class TestAttemptCombatStepSuccessNormal:
    def test_step_5ft_normal_returns_move_result_type(
        self, game_state, entity_id
    ) -> None:
        game_state.set_position(entity_id, 1, 1)

        result = game_state.attempt_combat_step(entity_id, 0, 1)

        assert isinstance(result, MoveResult)

    def test_step_5ft_normal_moves_one_tile(self, game_state, entity_id) -> None:
        game_state.set_position(entity_id, 1, 1)
        starting = _current_turn_state(game_state).movement_remaining

        # (1, 2) is FLOOR (normal terrain).
        result = game_state.attempt_combat_step(entity_id, 0, 1)

        assert result.ok is True
        assert result.reason is None
        assert result.position == Position(1, 2)
        assert result.movement_remaining == starting - 5
        assert game_state.spatial.position_of(entity_id) == Position(1, 2)

    def test_step_emits_creature_moved(self, game_state, entity_id) -> None:
        game_state.set_position(entity_id, 1, 1)
        moved = _capture(game_state.event_bus, EventType.CREATURE_MOVED)

        game_state.attempt_combat_step(entity_id, 0, 1)

        assert len(moved) == 1
        assert moved[0].data == {
            "entity_id": entity_id,
            "from": Position(1, 1),
            "to": Position(1, 2),
        }


class TestAttemptCombatStepDifficultTerrain:
    def test_step_into_difficult_terrain_deducts_10(self, game_state, entity_id) -> None:
        # Place at (2, 0); step east into (3, 0) which is WATER (difficult).
        game_state.set_position(entity_id, 2, 0)
        starting = _current_turn_state(game_state).movement_remaining

        result = game_state.attempt_combat_step(entity_id, 1, 0)

        assert result.ok is True
        assert result.position == Position(3, 0)
        # Difficult terrain costs 10 ft per 5-ft step.
        assert result.movement_remaining == starting - 10

    def test_explicit_terrain_kwarg_overrides_map(self, game_state, entity_id) -> None:
        """Caller can override the map's terrain via the terrain kwarg."""
        game_state.set_position(entity_id, 1, 1)
        starting = _current_turn_state(game_state).movement_remaining

        # (1, 2) is FLOOR (normal), but we force DIFFICULT via the kwarg.
        result = game_state.attempt_combat_step(
            entity_id, 0, 1, terrain=Terrain.DIFFICULT
        )

        assert result.ok is True
        assert result.position == Position(1, 2)
        assert result.movement_remaining == starting - 10


class TestAttemptCombatStepBlocking:
    def test_step_into_wall_returns_blocking(self, game_state, entity_id) -> None:
        # Place at (1, 1); step east into (2, 1) which is a WALL.
        game_state.set_position(entity_id, 1, 1)
        starting = _current_turn_state(game_state).movement_remaining

        result = game_state.attempt_combat_step(entity_id, 1, 0)

        assert result.ok is False
        assert result.reason == "blocking"
        assert result.position == Position(1, 1)
        # Movement budget must NOT be deducted on rejection.
        assert result.movement_remaining == starting
        # Spatial position must NOT have changed.
        assert game_state.spatial.position_of(entity_id) == Position(1, 1)


class TestAttemptCombatStepOccupied:
    def test_step_into_other_entity_returns_occupied(self, game_state, entity_id) -> None:
        game_state.set_position(entity_id, 1, 1)
        # Place a synthetic occupant at the destination.
        game_state.set_position("goblin", 1, 2)
        starting = _current_turn_state(game_state).movement_remaining

        result = game_state.attempt_combat_step(entity_id, 0, 1)

        assert result.ok is False
        assert result.reason is not None
        assert result.reason.startswith("occupied")
        assert "goblin" in result.reason
        assert result.position == Position(1, 1)
        assert result.movement_remaining == starting


class TestAttemptCombatStepNoMovementRemaining:
    def test_step_with_zero_movement_remaining_returns_no_movement(
        self, game_state, entity_id
    ) -> None:
        game_state.set_position(entity_id, 1, 1)
        ts = _current_turn_state(game_state)
        ts.movement_remaining = 0

        result = game_state.attempt_combat_step(entity_id, 0, 1)

        assert result.ok is False
        assert result.reason == "no movement remaining"
        # Position unchanged.
        assert result.position == Position(1, 1)
        assert result.movement_remaining == 0
        # Spatial unchanged.
        assert game_state.spatial.position_of(entity_id) == Position(1, 1)

    def test_step_with_insufficient_for_difficult_returns_no_movement(
        self, game_state, entity_id
    ) -> None:
        # Difficult terrain costs 10; leave only 5 in the pool.
        game_state.set_position(entity_id, 2, 0)
        ts = _current_turn_state(game_state)
        ts.movement_remaining = 5

        # (3, 0) is WATER (difficult). 5 ft pool < 10 ft cost — reject.
        result = game_state.attempt_combat_step(entity_id, 1, 0)

        assert result.ok is False
        assert result.reason == "no movement remaining"
        assert result.position == Position(2, 0)
        # Budget must be untouched on rejection.
        assert result.movement_remaining == 5


class TestAttemptCombatStepNotPlaced:
    def test_step_for_unplaced_entity_returns_not_placed(self, game_state) -> None:
        result = game_state.attempt_combat_step("ghost", 1, 0)

        assert result.ok is False
        assert result.reason == "not placed"
        # Soft-fail position contract per the plan: Position(0, 0).
        assert result.position == Position(0, 0)
        assert result.movement_remaining == 0


class TestAttemptCombatStepOutOfBounds:
    """Engine must distinguish OOB tiles (Map.tile_at returns None) from
    walls (is_blocking True for an in-bounds tile). Collapsing both to
    ``reason="blocking"`` is wire-format drift against legacy
    ``combat_move`` which surfaced a different message for OOB.
    """

    def test_step_off_map_returns_out_of_bounds(self, game_state, entity_id) -> None:
        # Place at the NW corner and step further NW into a tile that
        # has no entry in the Map (negative x or negative y).
        game_state.set_position(entity_id, 0, 0)
        starting = _current_turn_state(game_state).movement_remaining

        result = game_state.attempt_combat_step(entity_id, -1, 0)

        assert result.ok is False
        assert result.reason == "out of bounds"
        # Position unchanged — move did not happen.
        assert result.position == Position(0, 0)
        # Budget must NOT be deducted on rejection.
        assert result.movement_remaining == starting
        # Spatial unchanged.
        assert game_state.spatial.position_of(entity_id) == Position(0, 0)


class TestAttemptCombatStepPrecedence:
    """Legacy ``combat_move`` checks movement budget FIRST, so an empty
    pool returns "No movement remaining" even when the destination is a
    wall or off-map. The engine must mirror that precedence so wire
    strings stay aligned across the spatial-vs-legacy seam.
    """

    def test_step_off_map_with_zero_budget_returns_no_movement_first(
        self, game_state, entity_id
    ) -> None:
        game_state.set_position(entity_id, 0, 0)
        ts = _current_turn_state(game_state)
        ts.movement_remaining = 0

        result = game_state.attempt_combat_step(entity_id, -1, 0)

        assert result.ok is False
        assert result.reason == "no movement remaining"
        assert result.position == Position(0, 0)
        assert result.movement_remaining == 0

    def test_step_into_wall_with_zero_budget_returns_no_movement_first(
        self, game_state, entity_id
    ) -> None:
        # (2, 1) is a WALL in the fixture; place adjacent.
        game_state.set_position(entity_id, 1, 1)
        ts = _current_turn_state(game_state)
        ts.movement_remaining = 0

        result = game_state.attempt_combat_step(entity_id, 1, 0)

        assert result.ok is False
        assert result.reason == "no movement remaining"
        assert result.position == Position(1, 1)
        assert result.movement_remaining == 0


class TestAttemptCombatStepWaterTileSRDDifficultTerrain:
    """Per SRD #436, Difficult Terrain costs 2 ft per 1 ft of movement.
    Water tiles map to ``TerrainType.DIFFICULT`` (P2
    ``Map.from_room_layout``).

    This is a deliberate behavior change vs the legacy ``combat_move``,
    which always charged 5 ft per step regardless of tile. Scenarios
    that rely on the legacy 5-ft-per-step behavior across water need
    to flatten their terrain.
    """

    def test_water_tile_costs_double_per_srd(self, game_state, entity_id) -> None:
        # Place at (2, 0); step east into (3, 0) which is WATER.
        game_state.set_position(entity_id, 2, 0)
        starting = _current_turn_state(game_state).movement_remaining

        result = game_state.attempt_combat_step(entity_id, 1, 0)

        assert result.ok is True
        assert result.position == Position(3, 0)
        # SRD-correct: 5 ft step on Difficult Terrain costs 10 ft.
        assert result.movement_remaining == starting - 10
