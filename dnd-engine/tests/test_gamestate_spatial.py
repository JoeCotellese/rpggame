# ABOUTME: Tests for GameState.spatial wiring (plan-03 P4): placement, move, remove + events.
# ABOUTME: Pins CREATURE_PLACED/MOVED/REMOVED emission and the spatial-required ValueError path.

from __future__ import annotations

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature, Size
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.game_state import GameState
from dnd_engine.core.map import Map, TileType
from dnd_engine.core.party import Party
from dnd_engine.core.position import Position
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.spatial_index import SpatialIndex
from dnd_engine.utils.events import Event, EventBus, EventType


def _build_map_5x5() -> Map:
    """5x5 fixture map matching tests/srd/playing_the_game/test_spatial_index.py.

    Layout (y increases downward):
        .....
        ..#..
        .....
        .#.#.
        .....

    Walls at (2,1), (1,3), (3,3); everything else is floor.
    """
    wall_coords = {(2, 1), (1, 3), (3, 3)}
    tiles: dict[tuple[int, int], TileType] = {}
    for y in range(5):
        for x in range(5):
            tiles[(x, y)] = TileType.WALL if (x, y) in wall_coords else TileType.FLOOR
    return Map(width=5, height=5, tiles=tiles)


@pytest.fixture
def map_5x5() -> Map:
    return _build_map_5x5()


@pytest.fixture
def test_abilities() -> Abilities:
    return Abilities(
        strength=15, dexterity=14, constitution=13, intelligence=10, wisdom=12, charisma=8
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
def game_state(party_of_one: Party) -> GameState:
    return GameState(
        party=party_of_one,
        dungeon_name="test_dungeon",
        event_bus=EventBus(),
        data_loader=DataLoader(),
        dice_roller=DiceRoller(),
    )


def _capture(bus: EventBus, event_type: EventType) -> list[Event]:
    """Subscribe a list-capturing handler and return the list."""
    captured: list[Event] = []
    bus.subscribe(event_type, captured.append)
    return captured


class TestGameStateSpatialAttribute:
    """The new spatial attribute is None until the caller wires up a SpatialIndex."""

    def test_spatial_attr_defaults_to_none(self, game_state: GameState) -> None:
        assert game_state.spatial is None

    def test_set_position_without_spatial_raises_value_error(
        self, game_state: GameState
    ) -> None:
        with pytest.raises(ValueError, match=r"(?i)spatial|map") as excinfo:
            game_state.set_position("goblin", 3, 4)
        # Sanity-check the message mentions the bootstrap, so callers know
        # what went wrong without reading the GameState source.
        assert "spatial" in str(excinfo.value).lower() or "map" in str(excinfo.value).lower()


class TestSetPosition:
    """set_position delegates to SpatialIndex and emits PLACED-then-MOVED."""

    def test_first_call_places_and_returns_position(
        self, game_state: GameState, map_5x5: Map
    ) -> None:
        game_state.spatial = SpatialIndex(map_5x5)
        result = game_state.set_position("goblin", 0, 0)
        assert result == Position(0, 0)
        assert game_state.spatial.position_of("goblin") == Position(0, 0)

    def test_first_call_emits_creature_placed(
        self, game_state: GameState, map_5x5: Map
    ) -> None:
        game_state.spatial = SpatialIndex(map_5x5)
        placed = _capture(game_state.event_bus, EventType.CREATURE_PLACED)
        moved = _capture(game_state.event_bus, EventType.CREATURE_MOVED)

        game_state.set_position("goblin", 0, 0)

        assert len(placed) == 1
        assert placed[0].type == EventType.CREATURE_PLACED
        assert placed[0].data == {"entity_id": "goblin", "position": Position(0, 0)}
        assert moved == []

    def test_second_call_emits_creature_moved(
        self, game_state: GameState, map_5x5: Map
    ) -> None:
        game_state.spatial = SpatialIndex(map_5x5)
        placed = _capture(game_state.event_bus, EventType.CREATURE_PLACED)
        moved = _capture(game_state.event_bus, EventType.CREATURE_MOVED)

        game_state.set_position("goblin", 0, 0)
        game_state.set_position("goblin", 1, 0)

        assert len(placed) == 1  # Still only the initial placement
        assert len(moved) == 1
        assert moved[0].data == {
            "entity_id": "goblin",
            "origin": Position(0, 0),
            "to": Position(1, 0),
        }
        assert game_state.spatial.position_of("goblin") == Position(1, 0)

    def test_blocking_destination_raises_value_error(
        self, game_state: GameState, map_5x5: Map
    ) -> None:
        game_state.spatial = SpatialIndex(map_5x5)
        # (2, 1) is a wall in the fixture map.
        with pytest.raises(ValueError):
            game_state.set_position("goblin", 2, 1)


class TestMoveCreature:
    """move_creature applies a delta and emits CREATURE_MOVED."""

    def test_move_creature_updates_position_and_emits_moved(
        self, game_state: GameState, map_5x5: Map
    ) -> None:
        game_state.spatial = SpatialIndex(map_5x5)
        game_state.set_position("goblin", 0, 0)
        moved = _capture(game_state.event_bus, EventType.CREATURE_MOVED)

        result = game_state.move_creature("goblin", 1, 0)

        assert result == Position(1, 0)
        assert game_state.spatial.position_of("goblin") == Position(1, 0)
        assert len(moved) == 1
        assert moved[0].data == {
            "entity_id": "goblin",
            "origin": Position(0, 0),
            "to": Position(1, 0),
        }

    def test_move_creature_not_placed_raises_key_error(
        self, game_state: GameState, map_5x5: Map
    ) -> None:
        game_state.spatial = SpatialIndex(map_5x5)
        with pytest.raises(KeyError):
            game_state.move_creature("not_placed", 1, 0)

    def test_move_creature_without_spatial_raises_value_error(
        self, game_state: GameState
    ) -> None:
        with pytest.raises(ValueError, match=r"(?i)spatial|map"):
            game_state.move_creature("goblin", 1, 0)


class TestRemoveCreaturePosition:
    """remove_creature_position emits CREATURE_REMOVED only when something is dropped."""

    def test_remove_emits_creature_removed(
        self, game_state: GameState, map_5x5: Map
    ) -> None:
        game_state.spatial = SpatialIndex(map_5x5)
        game_state.set_position("goblin", 0, 0)
        removed = _capture(game_state.event_bus, EventType.CREATURE_REMOVED)

        game_state.remove_creature_position("goblin")

        assert len(removed) == 1
        assert removed[0].data == {"entity_id": "goblin", "position": Position(0, 0)}
        assert game_state.spatial.position_of("goblin") is None

    def test_remove_is_idempotent_no_double_event(
        self, game_state: GameState, map_5x5: Map
    ) -> None:
        game_state.spatial = SpatialIndex(map_5x5)
        game_state.set_position("goblin", 0, 0)
        removed = _capture(game_state.event_bus, EventType.CREATURE_REMOVED)

        game_state.remove_creature_position("goblin")
        game_state.remove_creature_position("goblin")  # No-op, no second event.

        assert len(removed) == 1

    def test_remove_without_spatial_raises_value_error(
        self, game_state: GameState
    ) -> None:
        with pytest.raises(ValueError, match=r"(?i)spatial|map"):
            game_state.remove_creature_position("goblin")


class TestSetPositionNoOp:
    """No-op set_position / move_creature should NOT emit CREATURE_MOVED."""

    def test_set_position_to_same_tile_after_placement_emits_nothing(
        self, game_state: GameState, map_5x5: Map
    ) -> None:
        game_state.spatial = SpatialIndex(map_5x5)
        game_state.set_position("goblin", 0, 0)  # initial placement
        moved = _capture(game_state.event_bus, EventType.CREATURE_MOVED)

        result = game_state.set_position("goblin", 0, 0)  # same tile

        assert result == Position(0, 0)
        assert moved == []
        assert game_state.spatial.position_of("goblin") == Position(0, 0)

    def test_move_creature_zero_delta_emits_nothing(
        self, game_state: GameState, map_5x5: Map
    ) -> None:
        game_state.spatial = SpatialIndex(map_5x5)
        game_state.set_position("goblin", 0, 0)
        moved = _capture(game_state.event_bus, EventType.CREATURE_MOVED)

        result = game_state.move_creature("goblin", 0, 0)

        assert result == Position(0, 0)
        assert moved == []
        assert game_state.spatial.position_of("goblin") == Position(0, 0)


class TestSetPositionCreatureSync:
    """set_position / move_creature / remove_creature_position keep
    Creature.position in sync with the SpatialIndex when the entity_id maps
    to a real Creature in the roster (party or active_enemies).
    """

    def test_set_position_syncs_creature_position_when_creature_in_roster(
        self, game_state: GameState, map_5x5: Map, party_of_one: Party
    ) -> None:
        game_state.spatial = SpatialIndex(map_5x5)
        character = party_of_one.characters[0]
        # spawn_character formats PC entity_ids as ``pc_<name_lower>``.
        entity_id = f"pc_{character.name.lower().replace(' ', '_')}"

        game_state.set_position(entity_id, 2, 2)

        assert character.position == Position(2, 2)

    def test_set_position_unknown_entity_id_silently_skips_creature_sync(
        self, game_state: GameState, map_5x5: Map
    ) -> None:
        game_state.spatial = SpatialIndex(map_5x5)
        # entity_id has no matching Creature in party or active_enemies.
        # Should succeed (SpatialIndex updated) without raising.
        result = game_state.set_position("ghost", 1, 1)

        assert result == Position(1, 1)
        assert game_state.spatial.position_of("ghost") == Position(1, 1)

    def test_move_creature_syncs_creature_position(
        self, game_state: GameState, map_5x5: Map, party_of_one: Party
    ) -> None:
        game_state.spatial = SpatialIndex(map_5x5)
        character = party_of_one.characters[0]
        entity_id = f"pc_{character.name.lower().replace(' ', '_')}"
        game_state.set_position(entity_id, 0, 0)

        game_state.move_creature(entity_id, 1, 0)

        assert character.position == Position(1, 0)

    def test_remove_creature_position_clears_creature_position(
        self, game_state: GameState, map_5x5: Map, party_of_one: Party
    ) -> None:
        game_state.spatial = SpatialIndex(map_5x5)
        character = party_of_one.characters[0]
        entity_id = f"pc_{character.name.lower().replace(' ', '_')}"
        game_state.set_position(entity_id, 0, 0)
        assert character.position == Position(0, 0)

        game_state.remove_creature_position(entity_id)

        assert character.position is None

    def test_set_position_threads_creature_size_into_footprint(
        self, game_state: GameState, map_5x5: Map
    ) -> None:
        """A Large creature placed via set_position claims its full 2x2 block.

        ``_find_creature_by_id`` resolves ``<id>_<index>`` to
        ``active_enemies[index]``, so an enemy's size flows through to the
        SpatialIndex footprint rather than collapsing to a single tile.
        """
        game_state.spatial = SpatialIndex(map_5x5)
        ogre = Creature(
            name="Ogre",
            max_hp=59,
            ac=11,
            abilities=Abilities(
                strength=19,
                dexterity=8,
                constitution=16,
                intelligence=5,
                wisdom=7,
                charisma=7,
            ),
            size=Size.LARGE,
        )
        game_state.active_enemies.append(ogre)

        # (0,0) anchors a 2x2 block clear of the fixture walls.
        game_state.set_position("ogre_0", 0, 0)

        assert game_state.spatial.footprint_of("ogre_0") == frozenset(
            {Position(0, 0), Position(1, 0), Position(0, 1), Position(1, 1)}
        )
        # Occupancy resolves a non-anchor footprint tile to the ogre.
        assert game_state.spatial.occupant_at(Position(1, 1)) == "ogre_0"


class TestBootstrapSpatial:
    """GameState.bootstrap_spatial(map, *, replace=False) factory."""

    def test_bootstrap_spatial_sets_attribute_and_returns_index(
        self, game_state: GameState, map_5x5: Map
    ) -> None:
        result = game_state.bootstrap_spatial(map_5x5)

        assert isinstance(result, SpatialIndex)
        assert game_state.spatial is result

    def test_bootstrap_spatial_double_call_raises_without_replace(
        self, game_state: GameState, map_5x5: Map
    ) -> None:
        game_state.bootstrap_spatial(map_5x5)

        with pytest.raises(ValueError, match=r"(?i)spatial|already"):
            game_state.bootstrap_spatial(map_5x5)

    def test_bootstrap_spatial_replace_succeeds(
        self, game_state: GameState, map_5x5: Map
    ) -> None:
        first = game_state.bootstrap_spatial(map_5x5)
        second = game_state.bootstrap_spatial(map_5x5, replace=True)

        assert second is not first
        assert game_state.spatial is second


class TestCreatureMovedPayloadConsistency:
    """CREATURE_MOVED payload shape must be identical across every emit path.

    Two GameState methods emit ``CREATURE_MOVED``: ``set_position`` (on
    the non-first call, when the entity is being moved rather than
    placed) and ``move_creature`` (delta moves). ``attempt_combat_step``
    delegates to ``move_creature`` so it shares the same emit site.
    Subscribers wired to ``CREATURE_MOVED`` should never need to branch
    on the emitter — same keys, same value types — so a single test
    pins the contract across both.
    """

    def test_payload_shape_identical_across_emit_paths(
        self, game_state: GameState, map_5x5: Map
    ) -> None:
        game_state.bootstrap_spatial(map_5x5)
        moved = _capture(game_state.event_bus, EventType.CREATURE_MOVED)

        # Seed an initial placement so set_position's next call goes
        # down the MOVED branch rather than the PLACED branch.
        game_state.set_position("goblin", 0, 0)
        # Path 1: set_position emits CREATURE_MOVED.
        game_state.set_position("goblin", 1, 0)
        # Path 2: move_creature emits CREATURE_MOVED.
        game_state.move_creature("goblin", 1, 0)

        assert len(moved) == 2, (
            f"expected one CREATURE_MOVED per emit path, got {len(moved)}"
        )
        for event in moved:
            assert set(event.data.keys()) == {"entity_id", "origin", "to"}
            assert isinstance(event.data["entity_id"], str)
            assert isinstance(event.data["origin"], Position)
            assert isinstance(event.data["to"], Position)
            # ``from`` is a Python reserved word; payload must NOT use it.
            assert "from" not in event.data
