# ABOUTME: Tests for EngineAdapter spatial integration with GameState.spatial / SpatialIndex.
# ABOUTME: Pins set_position / spawn / cleanup behavior when the engine spatial model is wired.

"""Tests for EngineAdapter spatial bridging.

When ``GameState.spatial`` is wired up (Map bootstrapped, SpatialIndex
installed), the adapter's spawn / set_position / cleanup primitives must
keep the engine's spatial model consistent with the visual EntityManager.
These tests pin that contract.
"""

from __future__ import annotations

import pytest


def _build_open_map(width: int = 20, height: int = 20):
    """A floor-only map with a single wall at (5, 5) for blocking tests."""
    from dnd_engine.core.map import Map, TileType

    tiles = {}
    for y in range(height):
        for x in range(width):
            tiles[(x, y)] = TileType.WALL if (x, y) == (5, 5) else TileType.FLOOR
    return Map(width=width, height=height, tiles=tiles)


@pytest.fixture
def initialized_adapter():
    """An EngineAdapter wired to a real cellar GameState (no vault dep)."""
    from client_2d.integration.engine_adapter import EngineAdapter

    from dnd_engine.core.character_factory import CharacterFactory
    from dnd_engine.core.game_state import GameState
    from dnd_engine.core.party import Party
    from dnd_engine.rules.loader import DataLoader
    from dnd_engine.utils.events import EventBus

    data_loader = DataLoader()
    factory = CharacterFactory()
    fighter = factory.create_character(
        "fighter", "human", data_loader, name="Tester",
    )
    party = Party([fighter])
    event_bus = EventBus()
    game_state = GameState(
        party=party,
        dungeon_name="cellar",
        event_bus=event_bus,
        data_loader=data_loader,
        campaign_id="poisoned_laboratory",
    )

    adapter = EngineAdapter()
    adapter._party = party
    adapter._event_bus = event_bus
    adapter._game_state = game_state
    adapter._initialized = True
    return adapter


@pytest.fixture
def adapter_with_spatial(initialized_adapter):
    """Adapter whose GameState has a SpatialIndex bootstrapped on a 20x20 map."""
    initialized_adapter.game_state.bootstrap_spatial(_build_open_map())
    return initialized_adapter


class TestSetPositionBlocking:
    """F1 — set_position on a blocking tile surfaces a structured error."""

    def test_set_position_blocking_returns_error(self, adapter_with_spatial) -> None:
        """A blocking destination produces a {"error": ...} dict, not an exception."""
        adapter = adapter_with_spatial

        result = adapter.set_position("goblin_0", 5, 5)  # (5, 5) is a wall

        assert result["entity_id"] == "goblin_0"
        assert "error" in result
        assert result["position"] == [5, 5]
        # The SpatialIndex must remain untouched on rejection.
        assert adapter.game_state.spatial.position_of("goblin_0") is None


class TestSetPositionAuthoritative:
    """F4 — set_position returns the engine-authoritative Position."""

    def test_set_position_returns_engine_position(self, adapter_with_spatial) -> None:
        """On success the dict's position comes from the engine's Position object."""
        result = adapter_with_spatial.set_position("goblin_0", 3, 4)

        assert result == {"entity_id": "goblin_0", "position": [3, 4]}


class TestClearEnemiesSpatialCleanup:
    """F2 — clear_enemies removes monsters from the SpatialIndex."""

    def test_clear_enemies_clears_spatial(self, adapter_with_spatial) -> None:
        adapter = adapter_with_spatial
        adapter.spawn_monster("goblin", 1, 1)
        adapter.spawn_monster("goblin", 2, 2)
        # spawn_monster (F3) writes to spatial — sanity check the precondition.
        assert len(adapter.game_state.spatial.occupants()) == 2

        adapter.clear_enemies()

        assert adapter.game_state.spatial.occupants() == {}


class TestResetGameSpatialCleanup:
    """F2 — reset_game removes both party and enemies from the SpatialIndex."""

    def test_reset_game_clears_spatial(self, adapter_with_spatial) -> None:
        adapter = adapter_with_spatial
        adapter.spawn_character(
            "fighter", "human", ["longsword"], 3, 3, name="Extra",
        )
        adapter.spawn_monster("goblin", 1, 1)
        # Both writes should be present in spatial.
        assert len(adapter.game_state.spatial.occupants()) == 2

        adapter.reset_game()

        assert adapter.game_state.spatial.occupants() == {}


class TestSpawnMonsterSpatial:
    """F3 — spawn_monster writes to the SpatialIndex when spatial is wired."""

    def test_spawn_monster_writes_to_spatial(self, adapter_with_spatial) -> None:
        from dnd_engine.core.position import Position

        adapter = adapter_with_spatial

        result = adapter.spawn_monster("goblin", 7, 8)

        entity_id = result["entity_id"]
        assert adapter.game_state.spatial.occupant_at(Position(7, 8)) == entity_id
        assert result["position"] == [7, 8]
        assert "error" not in result

    def test_spawn_monster_on_wall_returns_error_no_spatial_change(
        self, adapter_with_spatial
    ) -> None:
        adapter = adapter_with_spatial
        before = dict(adapter.game_state.spatial.occupants())

        result = adapter.spawn_monster("goblin", 5, 5)  # wall

        assert "error" in result
        assert result["position"] == [5, 5]
        # SpatialIndex is unchanged.
        assert dict(adapter.game_state.spatial.occupants()) == before


class TestSpawnCharacterSpatial:
    """F3 — spawn_character writes to the SpatialIndex when spatial is wired."""

    def test_spawn_character_writes_to_spatial(self, adapter_with_spatial) -> None:
        from dnd_engine.core.position import Position

        adapter = adapter_with_spatial

        result = adapter.spawn_character(
            "fighter", "human", ["longsword"], 4, 4, name="Pos",
        )

        entity_id = result["entity_id"]
        assert adapter.game_state.spatial.occupant_at(Position(4, 4)) == entity_id


class TestMoveCreatureAdapter:
    """F8 — EngineAdapter.move_creature passes through to GameState."""

    def test_move_creature_success(self, adapter_with_spatial) -> None:
        adapter = adapter_with_spatial
        adapter.spawn_monster("goblin", 7, 7)

        result = adapter.move_creature("goblin_0", 1, 0)

        assert result == {"entity_id": "goblin_0", "position": [8, 7]}

    def test_move_creature_not_placed_returns_error(self, adapter_with_spatial) -> None:
        adapter = adapter_with_spatial

        result = adapter.move_creature("never_placed", 1, 0)

        assert result["entity_id"] == "never_placed"
        assert "error" in result

    def test_move_creature_raises_when_not_initialized(self) -> None:
        from client_2d.integration.engine_adapter import EngineAdapter

        with pytest.raises(ValueError, match="initialize_game"):
            EngineAdapter().move_creature("goblin_0", 1, 0)

    def test_move_creature_rejects_non_integer_delta(self, adapter_with_spatial) -> None:
        with pytest.raises(TypeError):
            adapter_with_spatial.move_creature("goblin_0", "east", 0)

    def test_move_creature_returns_no_position_when_spatial_unwired(
        self, initialized_adapter
    ) -> None:
        """When spatial is None (no Map bootstrapped), move_creature is a no-op."""
        result = initialized_adapter.move_creature("goblin_0", 1, 0)

        assert result == {"entity_id": "goblin_0", "position": None}


class TestRemoveCreaturePositionAdapter:
    """F8 — EngineAdapter.remove_creature_position passes through to GameState."""

    def test_remove_creature_position_success(self, adapter_with_spatial) -> None:
        adapter = adapter_with_spatial
        adapter.spawn_monster("goblin", 7, 7)

        result = adapter.remove_creature_position("goblin_0")

        assert result == {"entity_id": "goblin_0", "removed": True}
        assert adapter.game_state.spatial.position_of("goblin_0") is None

    def test_remove_creature_position_idempotent(self, adapter_with_spatial) -> None:
        """Removing a never-placed entity returns success (no-op semantics)."""
        result = adapter_with_spatial.remove_creature_position("never_placed")

        assert result == {"entity_id": "never_placed", "removed": True}

    def test_remove_creature_position_raises_when_not_initialized(self) -> None:
        from client_2d.integration.engine_adapter import EngineAdapter

        with pytest.raises(ValueError, match="initialize_game"):
            EngineAdapter().remove_creature_position("goblin_0")


class TestBootstrapSpatialFromLayout:
    """Plan-03 P7 — adapter-side hook that turns a visual RoomLayout into
    an engine Map and installs a SpatialIndex on GameState. This is the
    single seam combat-start uses to wire up engine-owned movement."""

    def _make_room_layout(self, width: int = 6, height: int = 5):
        """A small all-floor RoomLayout suitable for Map.from_room_layout."""
        from client_2d.integration.layout_schema import (
            RoomLayout,
            SpawnPoints,
            TileType,
        )

        tiles = [[int(TileType.FLOOR) for _ in range(width)] for _ in range(height)]
        return RoomLayout(
            width=width,
            height=height,
            tiles=tiles,
            spawn_points=SpawnPoints(player=(1, 1)),
        )

    def test_bootstrap_spatial_from_layout_returns_status_dict(
        self, initialized_adapter
    ) -> None:
        """Returns a status dict carrying the new Map's dimensions."""
        layout = self._make_room_layout(width=7, height=4)

        result = initialized_adapter.bootstrap_spatial_from_layout(layout)

        assert result == {"status": "bootstrapped", "width": 7, "height": 4}
        assert initialized_adapter.game_state.spatial is not None

    def test_bootstrap_spatial_from_layout_replaces_existing(
        self, adapter_with_spatial
    ) -> None:
        """A second call replaces the existing SpatialIndex (replace=True)."""
        # First bootstrap was via the fixture's 20x20 map.
        assert adapter_with_spatial.game_state.spatial is not None
        original_index = adapter_with_spatial.game_state.spatial

        layout = self._make_room_layout(width=8, height=6)
        result = adapter_with_spatial.bootstrap_spatial_from_layout(layout)

        assert result == {"status": "bootstrapped", "width": 8, "height": 6}
        # New SpatialIndex object — the old one was discarded.
        assert adapter_with_spatial.game_state.spatial is not original_index

    def test_bootstrap_spatial_from_layout_raises_without_game_state(self) -> None:
        """Init guard mirrors the other adapter primitives."""
        from client_2d.integration.engine_adapter import EngineAdapter

        with pytest.raises(ValueError, match="initialize_game"):
            EngineAdapter().bootstrap_spatial_from_layout(
                self._make_room_layout(),
            )
