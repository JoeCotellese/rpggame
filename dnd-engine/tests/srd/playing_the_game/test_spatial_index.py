# ABOUTME: Tests for SpatialIndex (plan-03 P3): placements, distance, LoS, range.
# ABOUTME: Pins supercover LoS, blocking-endpoint guard, are_adjacent_tiles, and range validation.

from __future__ import annotations

from types import MappingProxyType

import pytest

from dnd_engine.core.map import Map, TileType
from dnd_engine.core.position import Position
from dnd_engine.systems.spatial_index import SpatialIndex


def _build_map_5x5() -> Map:
    """5x5 fixture map.

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
def index(map_5x5: Map) -> SpatialIndex:
    """Fresh SpatialIndex per test."""
    return SpatialIndex(map_5x5)


class TestPlacement:
    """place() inserts entities, rejecting duplicates, walls, and occupied tiles."""

    def test_place_sets_position_and_occupant(self, index: SpatialIndex) -> None:
        index.place("goblin", Position(0, 0))
        assert index.position_of("goblin") == Position(0, 0)
        assert index.occupant_at(Position(0, 0)) == "goblin"

    def test_place_same_entity_twice_raises(self, index: SpatialIndex) -> None:
        index.place("goblin", Position(0, 0))
        with pytest.raises(ValueError, match="already placed"):
            index.place("goblin", Position(1, 0))

    def test_place_on_wall_raises(self, index: SpatialIndex) -> None:
        with pytest.raises(ValueError, match="blocking"):
            index.place("goblin", Position(2, 1))

    def test_place_on_occupied_tile_raises(self, index: SpatialIndex) -> None:
        index.place("goblin", Position(0, 0))
        with pytest.raises(ValueError, match="occupied"):
            index.place("orc", Position(0, 0))

    def test_place_out_of_bounds_raises(self, index: SpatialIndex) -> None:
        # Map treats out-of-bounds as blocking; placement should refuse it.
        with pytest.raises(ValueError, match="blocking"):
            index.place("goblin", Position(10, 10))


class TestMove:
    """move() relocates existing occupants under the same blocking/occupied rules."""

    def test_move_to_empty_tile(self, index: SpatialIndex) -> None:
        index.place("goblin", Position(0, 0))
        index.move("goblin", Position(1, 0))
        assert index.position_of("goblin") == Position(1, 0)
        assert index.occupant_at(Position(0, 0)) is None
        assert index.occupant_at(Position(1, 0)) == "goblin"

    def test_move_unplaced_entity_raises_key_error(self, index: SpatialIndex) -> None:
        with pytest.raises(KeyError):
            index.move("ghost", Position(0, 0))

    def test_move_into_occupied_tile_raises(self, index: SpatialIndex) -> None:
        index.place("goblin", Position(0, 0))
        index.place("orc", Position(1, 0))
        with pytest.raises(ValueError, match="occupied"):
            index.move("goblin", Position(1, 0))

    def test_move_into_wall_raises(self, index: SpatialIndex) -> None:
        index.place("goblin", Position(0, 0))
        with pytest.raises(ValueError, match="blocking"):
            index.move("goblin", Position(2, 1))

    def test_move_to_current_position_is_noop(self, index: SpatialIndex) -> None:
        index.place("goblin", Position(0, 0))
        index.move("goblin", Position(0, 0))  # must not raise
        assert index.position_of("goblin") == Position(0, 0)
        assert index.occupant_at(Position(0, 0)) == "goblin"


class TestRemove:
    """remove() clears an entity; missing entities are silently ignored."""

    def test_remove_clears_position_and_occupant(self, index: SpatialIndex) -> None:
        index.place("goblin", Position(0, 0))
        index.remove("goblin")
        assert index.position_of("goblin") is None
        assert index.occupant_at(Position(0, 0)) is None

    def test_remove_unplaced_is_noop(self, index: SpatialIndex) -> None:
        # Must not raise.
        index.remove("never_placed")

    def test_round_trip_place_remove_replace_at_same_tile(self, index: SpatialIndex) -> None:
        # Place, remove, then place a DIFFERENT entity at the same tile.
        # Catches forgotten reverse-dict cleanup in ``remove`` — if the
        # reverse mapping still pointed at the original id, the re-place
        # would raise ``"occupied by goblin"`` even though goblin was
        # removed.
        tile = Position(2, 2)
        index.place("goblin", tile)
        index.remove("goblin")
        index.place("orc", tile)
        assert index.position_of("orc") == tile
        assert index.occupant_at(tile) == "orc"
        assert index.position_of("goblin") is None


class TestAllowOverlap:
    """``allow_overlap=True`` lets place/move share a tile with another entity.

    Default behavior (``allow_overlap=False``) still rejects double-
    occupancy. The primitive is the foundation for the SRD pass-through
    carve-outs that ``GameState.attempt_combat_step`` evaluates; the
    index itself stays rule-agnostic — it only widens the gate.
    """

    def test_place_with_allow_overlap_shares_tile(self, index: SpatialIndex) -> None:
        index.place("goblin", Position(0, 0))
        index.place("orc", Position(0, 0), allow_overlap=True)
        assert index.position_of("goblin") == Position(0, 0)
        assert index.position_of("orc") == Position(0, 0)

    def test_place_with_allow_overlap_still_rejects_blocking(self, index: SpatialIndex) -> None:
        with pytest.raises(ValueError, match="blocking"):
            index.place("goblin", Position(2, 1), allow_overlap=True)

    def test_place_with_allow_overlap_still_rejects_duplicate_entity(
        self, index: SpatialIndex
    ) -> None:
        index.place("goblin", Position(0, 0))
        with pytest.raises(ValueError, match="already placed"):
            index.place("goblin", Position(1, 0), allow_overlap=True)

    def test_move_with_allow_overlap_into_occupied_tile(self, index: SpatialIndex) -> None:
        index.place("goblin", Position(0, 0))
        index.place("orc", Position(1, 0))
        index.move("goblin", Position(1, 0), allow_overlap=True)
        assert index.position_of("goblin") == Position(1, 0)
        assert index.position_of("orc") == Position(1, 0)

    def test_move_with_allow_overlap_still_rejects_blocking(self, index: SpatialIndex) -> None:
        index.place("goblin", Position(0, 0))
        with pytest.raises(ValueError, match="blocking"):
            index.move("goblin", Position(2, 1), allow_overlap=True)

    def test_default_still_rejects_occupied_tile(self, index: SpatialIndex) -> None:
        # The new kwarg defaults to False; existing callers see no
        # behavioral change. The double-occupancy gate stays closed.
        index.place("goblin", Position(0, 0))
        with pytest.raises(ValueError, match="occupied"):
            index.place("orc", Position(0, 0))
        index.place("orc", Position(1, 0))
        with pytest.raises(ValueError, match="occupied"):
            index.move("orc", Position(0, 0))

    def test_remove_after_overlap_leaves_remaining_occupant(self, index: SpatialIndex) -> None:
        # Two creatures share a tile; removing the original placer must
        # not orphan the second one — ``occupant_at`` still resolves to
        # the remaining entity.
        index.place("goblin", Position(0, 0))
        index.place("orc", Position(0, 0), allow_overlap=True)
        index.remove("goblin")
        assert index.position_of("orc") == Position(0, 0)
        assert index.occupant_at(Position(0, 0)) == "orc"
        assert index.position_of("goblin") is None


class TestQueries:
    """position_of / occupant_at default to None when empty."""

    def test_position_of_missing_returns_none(self, index: SpatialIndex) -> None:
        assert index.position_of("ghost") is None

    def test_occupant_at_empty_returns_none(self, index: SpatialIndex) -> None:
        assert index.occupant_at(Position(4, 4)) is None


@pytest.mark.parametrize(
    "a,b,expected",
    [
        (Position(0, 0), Position(0, 0), 0),
        (Position(0, 0), Position(3, 0), 3),
        (Position(0, 0), Position(3, 4), 4),
        (Position(1, 1), Position(4, 5), 4),
    ],
)
def test_distance_chebyshev(index: SpatialIndex, a: Position, b: Position, expected: int) -> None:
    assert index.distance(a, b) == expected


def test_distance_in_feet_uses_5ft_per_tile(index: SpatialIndex) -> None:
    assert index.distance_in_feet(Position(0, 0), Position(3, 4)) == 20


class TestAreAdjacentTiles:
    def test_diagonal_is_adjacent(self, index: SpatialIndex) -> None:
        assert index.are_adjacent_tiles(Position(0, 0), Position(1, 1)) is True

    def test_same_position_is_not_adjacent(self, index: SpatialIndex) -> None:
        # Chebyshev 0 != 1, so same square is NOT adjacent under this contract.
        assert index.are_adjacent_tiles(Position(0, 0), Position(0, 0)) is False

    def test_two_squares_apart_is_not_adjacent(self, index: SpatialIndex) -> None:
        assert index.are_adjacent_tiles(Position(0, 0), Position(2, 0)) is False


class TestTilesInRange:
    """tiles_in_range yields the full Chebyshev square, no walkability filter."""

    def test_5ft_returns_3x3_block(self, index: SpatialIndex) -> None:
        tiles = index.tiles_in_range(Position(2, 2), 5)
        expected = {Position(x, y) for x in range(1, 4) for y in range(1, 4)}
        assert tiles == expected
        assert len(tiles) == 9

    def test_10ft_returns_5x5_block(self, index: SpatialIndex) -> None:
        tiles = index.tiles_in_range(Position(2, 2), 10)
        expected = {Position(x, y) for x in range(0, 5) for y in range(0, 5)}
        assert tiles == expected
        assert len(tiles) == 25

    def test_zero_feet_returns_only_origin(self, index: SpatialIndex) -> None:
        assert index.tiles_in_range(Position(2, 2), 0) == {Position(2, 2)}

    @pytest.mark.parametrize("range_feet", [-1, -5, -100])
    def test_negative_range_raises(self, index: SpatialIndex, range_feet: int) -> None:
        # Negative ranges previously yielded an empty set silently; the
        # contract now requires an explicit ValueError so callers cannot
        # pass through a bad range and assume "nothing in range".
        with pytest.raises(ValueError, match="non-negative"):
            index.tiles_in_range(Position(2, 2), range_feet)


class TestLineOfSight:
    """has_line_of_sight uses a supercover line vs Map.is_blocking."""

    def test_open_vertical(self, index: SpatialIndex) -> None:
        assert index.has_line_of_sight(Position(0, 0), Position(0, 4)) is True

    def test_open_horizontal(self, index: SpatialIndex) -> None:
        assert index.has_line_of_sight(Position(0, 0), Position(4, 0)) is True

    def test_blocked_horizontal_by_wall_at_2_1(self, index: SpatialIndex) -> None:
        # Row y=1: floor floor wall floor floor — Bresenham from (1,1)->(3,1)
        # steps through (2,1) which is a wall.
        assert index.has_line_of_sight(Position(1, 1), Position(3, 1)) is False

    def test_blocked_horizontal_through_two_walls_in_row_3(self, index: SpatialIndex) -> None:
        # Row y=3: floor wall floor wall floor — straight scan from (0,3)->(4,3)
        # hits walls at (1,3) and (3,3).
        assert index.has_line_of_sight(Position(0, 3), Position(4, 3)) is False

    def test_open_diagonal_corner_to_corner(self, index: SpatialIndex) -> None:
        # Bresenham (0,0) -> (4,4) walks the major diagonal: (0,0), (1,1),
        # (2,2), (3,3), (4,4). (3,3) is a wall in this map, so LoS is False.
        # Documenting the actual line: with walls at (1,3) and (3,3), the
        # diagonal does pass through (3,3) and is blocked.
        assert index.has_line_of_sight(Position(0, 0), Position(4, 4)) is False

    def test_open_diagonal_avoiding_walls(self, index: SpatialIndex) -> None:
        # (0,0) -> (4,2) walks a shallow diagonal that avoids all walls.
        # Bresenham steps (rounded toward smooth integer line):
        # (0,0), (1,0) or (1,1), (2,1)... Let's just verify open: the only
        # walls are at (2,1), (1,3), (3,3). Use a route guaranteed to skip
        # walls: (0,4) -> (4,4) all floor along row y=4.
        assert index.has_line_of_sight(Position(0, 4), Position(4, 4)) is True

    def test_same_position_has_line_of_sight(self, index: SpatialIndex) -> None:
        assert index.has_line_of_sight(Position(2, 2), Position(2, 2)) is True

    def test_endpoint_blocking_returns_false(self, index: SpatialIndex) -> None:
        # If either endpoint is itself a blocking tile (a wall here), LoS
        # must be False — you cannot see "through" or "into" a wall.
        wall = Position(2, 1)
        floor = Position(0, 0)
        assert index.has_line_of_sight(floor, wall) is False
        assert index.has_line_of_sight(wall, floor) is False

    def test_same_position_on_wall_returns_false(self, index: SpatialIndex) -> None:
        # a == b on a wall: degenerate query but it still must respect the
        # blocking endpoint guard. A wall cannot have LoS to itself.
        wall = Position(2, 1)
        assert index.has_line_of_sight(wall, wall) is False

    def test_endpoint_out_of_bounds_returns_false(self, index: SpatialIndex) -> None:
        # OOB is reported as blocking by Map.is_blocking, so an OOB endpoint
        # is treated the same as a wall endpoint.
        oob = Position(10, 10)
        assert index.has_line_of_sight(Position(0, 0), oob) is False

    def test_supercover_visits_shallow_line_clipped_tile(self) -> None:
        # Supercover traversal of (0,0)->(3,1) must visit (1,1). A standard
        # single-step Bresenham yields (0,0),(1,0),(2,1),(3,1) and skips
        # (1,1); a wall at (1,1) would then NOT block LoS — that's the bug
        # this test guards against.
        tiles: dict[tuple[int, int], TileType] = {}
        for y in range(2):
            for x in range(4):
                tiles[(x, y)] = TileType.FLOOR
        tiles[(1, 1)] = TileType.WALL
        m = Map(width=4, height=2, tiles=tiles)
        si = SpatialIndex(m)
        assert si.has_line_of_sight(Position(0, 0), Position(3, 1)) is False

    def test_has_line_of_sight_short_circuits_on_first_blocker(self) -> None:
        # An early blocker on a long segment must not cost O(length) tile
        # inspections. We wrap is_blocking to count calls and assert the
        # generator stops walking once the first interior blocker rejects
        # LoS.
        width, height = 1000, 1
        tiles: dict[tuple[int, int], TileType] = {(x, 0): TileType.FLOOR for x in range(width)}
        tiles[(2, 0)] = TileType.WALL  # blocker very close to the start
        m = Map(width=width, height=height, tiles=tiles)

        call_count = 0
        original_is_blocking = m.is_blocking

        def counting_is_blocking(x: int, y: int) -> bool:
            nonlocal call_count
            call_count += 1
            return original_is_blocking(x, y)

        m.is_blocking = counting_is_blocking  # type: ignore[method-assign]
        si = SpatialIndex(m)
        assert si.has_line_of_sight(Position(0, 0), Position(width - 1, 0)) is False
        # Two endpoint guards + a small number of interior probes before the
        # early blocker rejects. A non-short-circuiting implementation would
        # call is_blocking ~width times.
        assert call_count < 10, f"expected short-circuit before ~10 probes, got {call_count}"


class TestCornerCuttingDiagonal:
    """Supercover traversal visits one of the corner walls on the diagonal,
    blocking LoS — closes the corner-cutting concern that P7 was originally
    going to address.

    Layout for this test (2x2):
        .#
        #.

    Two walls form a diagonal pinch between (0,0) and (1,1). Supercover
    traversal of (0,0)->(1,1) steps through (0,1) (or (1,0), depending on
    error tiebreak), both of which are walls, so LoS is False.
    """

    def test_corner_diagonal_blocked_by_supercover(self) -> None:
        # 2x2 with walls at (1,0) and (0,1); floor at (0,0) and (1,1).
        tiles: dict[tuple[int, int], TileType] = {
            (0, 0): TileType.FLOOR,
            (1, 0): TileType.WALL,
            (0, 1): TileType.WALL,
            (1, 1): TileType.FLOOR,
        }
        m = Map(width=2, height=2, tiles=tiles)
        si = SpatialIndex(m)
        # Supercover visits an intermediate corner-wall tile on the (0,0)->
        # (1,1) diagonal, so LoS is False.
        assert si.has_line_of_sight(Position(0, 0), Position(1, 1)) is False


class TestOccupantsView:
    """occupants() returns a read-only mapping; mutation must not affect state."""

    def test_occupants_returns_expected_pairs(self, index: SpatialIndex) -> None:
        index.place("goblin", Position(0, 0))
        index.place("orc", Position(1, 0))
        index.place("kobold", Position(2, 2))
        result = index.occupants()
        assert dict(result) == {
            "goblin": Position(0, 0),
            "orc": Position(1, 0),
            "kobold": Position(2, 2),
        }

    def test_occupants_view_is_read_only(self, index: SpatialIndex) -> None:
        index.place("goblin", Position(0, 0))
        view = index.occupants()
        # We chose MappingProxyType so direct mutation raises TypeError.
        assert isinstance(view, MappingProxyType)
        with pytest.raises(TypeError):
            view["intruder"] = Position(1, 1)  # type: ignore[index]


class TestFootprint:
    """SpatialIndex honors multi-tile creature footprints (#442).

    SRD § Playing the Game › Movement and Position › Creature Size:
    Large creatures fill a 2x2 block, Huge 3x3, Gargantuan 4x4. The
    anchor Position is the minimum-x / minimum-y corner; the block
    extends toward +x and +y.
    """

    def _clear_index(self, n: int = 6) -> SpatialIndex:
        """A wall-free n x n index, for unobstructed footprint geometry."""
        tiles = {(x, y): TileType.FLOOR for x in range(n) for y in range(n)}
        return SpatialIndex(Map(width=n, height=n, tiles=tiles))

    # -- pure geometry ---------------------------------------------------- #

    def test_footprint_tiles_medium_is_single_anchor(self) -> None:
        from dnd_engine.core.creature import Size

        assert SpatialIndex.footprint_tiles(Position(2, 2), Size.MEDIUM) == frozenset(
            {Position(2, 2)}
        )

    def test_footprint_tiles_large_is_2x2_extending_positive(self) -> None:
        from dnd_engine.core.creature import Size

        assert SpatialIndex.footprint_tiles(Position(1, 1), Size.LARGE) == frozenset(
            {Position(1, 1), Position(2, 1), Position(1, 2), Position(2, 2)}
        )

    def test_footprint_tiles_huge_is_3x3(self) -> None:
        from dnd_engine.core.creature import Size

        tiles = SpatialIndex.footprint_tiles(Position(0, 0), Size.HUGE)
        assert tiles == frozenset(Position(x, y) for x in range(3) for y in range(3))

    # -- placement -------------------------------------------------------- #

    def test_place_large_registers_full_2x2_footprint(self) -> None:
        from dnd_engine.core.creature import Size

        idx = self._clear_index()
        idx.place("ogre", Position(1, 1), size=Size.LARGE)
        assert idx.footprint_of("ogre") == frozenset(
            {Position(1, 1), Position(2, 1), Position(1, 2), Position(2, 2)}
        )

    def test_occupant_at_is_footprint_aware(self) -> None:
        from dnd_engine.core.creature import Size

        idx = self._clear_index()
        idx.place("ogre", Position(1, 1), size=Size.LARGE)
        # The anchor and every covered tile resolve to the ogre.
        assert idx.occupant_at(Position(1, 1)) == "ogre"
        assert idx.occupant_at(Position(2, 1)) == "ogre"
        assert idx.occupant_at(Position(2, 2)) == "ogre"
        # A tile outside the footprint is clear; the anchor is the
        # reported position.
        assert idx.occupant_at(Position(3, 3)) is None
        assert idx.position_of("ogre") == Position(1, 1)

    def test_place_onto_existing_footprint_tile_raises(self) -> None:
        from dnd_engine.core.creature import Size

        idx = self._clear_index()
        idx.place("ogre", Position(1, 1), size=Size.LARGE)
        with pytest.raises(ValueError, match="occupied"):
            idx.place("goblin", Position(2, 2))  # inside the ogre's 2x2 block

    def test_place_footprint_off_map_raises(self) -> None:
        from dnd_engine.core.creature import Size

        idx = self._clear_index()  # 6x6, valid indices 0..5
        with pytest.raises(ValueError, match="blocking"):
            # A 2x2 anchored at (5,5) would spill onto x=6 / y=6.
            idx.place("ogre", Position(5, 5), size=Size.LARGE)

    def test_place_footprint_onto_wall_raises(self) -> None:
        from dnd_engine.core.creature import Size

        tiles = {(x, y): TileType.FLOOR for x in range(6) for y in range(6)}
        tiles[(2, 1)] = TileType.WALL
        idx = SpatialIndex(Map(width=6, height=6, tiles=tiles))
        with pytest.raises(ValueError, match="blocking"):
            # The 2x2 block from (1,1) covers the wall at (2,1).
            idx.place("ogre", Position(1, 1), size=Size.LARGE)

    def test_place_without_size_keeps_single_tile_behavior(self) -> None:
        idx = self._clear_index()
        idx.place("goblin", Position(2, 2))
        assert idx.footprint_of("goblin") == frozenset({Position(2, 2)})
        # Default size is Medium → one tile, leaving neighbors clear.
        assert idx.occupant_at(Position(3, 2)) is None

    # -- movement --------------------------------------------------------- #

    def test_move_relocates_whole_block_and_clears_old_tiles(self) -> None:
        from dnd_engine.core.creature import Size

        idx = self._clear_index()
        idx.place("ogre", Position(0, 0), size=Size.LARGE)
        idx.move("ogre", Position(3, 3))
        # Old tiles are vacated.
        assert idx.occupant_at(Position(0, 0)) is None
        assert idx.occupant_at(Position(1, 1)) is None
        # The full new footprint is registered.
        assert idx.footprint_of("ogre") == frozenset(
            {Position(3, 3), Position(4, 3), Position(3, 4), Position(4, 4)}
        )
        assert idx.occupant_at(Position(4, 4)) == "ogre"

    def test_move_into_own_overlapping_footprint_succeeds(self) -> None:
        from dnd_engine.core.creature import Size

        # Sliding a Large creature so the new block overlaps the old must
        # not trip the occupied-tile guard against the creature itself.
        idx = self._clear_index()
        idx.place("ogre", Position(1, 1), size=Size.LARGE)
        idx.move("ogre", Position(2, 2))  # new block overlaps old (2,2)
        assert idx.position_of("ogre") == Position(2, 2)
        assert idx.occupant_at(Position(1, 1)) is None
        assert idx.occupant_at(Position(3, 3)) == "ogre"

    def test_move_blocked_by_other_entity_in_target_footprint(self) -> None:
        from dnd_engine.core.creature import Size

        idx = self._clear_index()
        idx.place("ogre", Position(0, 0), size=Size.LARGE)
        idx.place("goblin", Position(3, 3))
        with pytest.raises(ValueError, match="occupied"):
            # The 2x2 block anchored at (2,2) would cover the goblin (3,3).
            idx.move("ogre", Position(2, 2))

    def test_remove_clears_entire_footprint(self) -> None:
        from dnd_engine.core.creature import Size

        idx = self._clear_index()
        idx.place("ogre", Position(1, 1), size=Size.LARGE)
        idx.remove("ogre")
        for tile in (
            Position(1, 1),
            Position(2, 1),
            Position(1, 2),
            Position(2, 2),
        ):
            assert idx.occupant_at(tile) is None
        assert idx.position_of("ogre") is None
