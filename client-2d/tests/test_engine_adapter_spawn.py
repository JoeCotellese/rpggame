# ABOUTME: Tests for EngineAdapter dev-mode spawn/setup methods (#360).
# ABOUTME: Covers set_seed, spawn_monster, spawn_character, set_position, clear_enemies.

"""Tests for the engine adapter's dev-mode spawn primitives.

These adapter methods back the --dev MCP tools. They run against a real
EngineAdapter wired to a real GameState in the cellar/poisoned_laboratory
campaign (deterministic content, no vault dependency).
"""

from __future__ import annotations

import pytest


@pytest.fixture
def initialized_adapter():
    """An EngineAdapter with a 1-member party and a real cellar GameState.

    Bypasses load_party_from_vault() so tests don't depend on the user's
    ~/.dnd_game/character_vault.json. Builds a fighter via CharacterFactory
    and constructs GameState directly.
    """
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


class TestSetSeed:
    """EngineAdapter.set_seed reseeds the live DiceRoller in place."""

    def test_reseed_makes_rolls_reproducible(self, initialized_adapter) -> None:
        """Same seed → same sequence of rolls."""
        adapter = initialized_adapter
        roller = adapter.game_state.dice_roller

        adapter.set_seed(42)
        first = [roller.roll("1d20").total for _ in range(5)]

        adapter.set_seed(42)
        second = [roller.roll("1d20").total for _ in range(5)]

        assert first == second

    def test_set_seed_returns_dict(self, initialized_adapter) -> None:
        """Returns a structured dict echoing the seed."""
        result = initialized_adapter.set_seed(123)

        assert result == {"success": True, "seed": 123}

    def test_set_seed_propagates_to_combat_engine(self, initialized_adapter) -> None:
        """Combat engine holds the same DiceRoller, so reseed affects it too."""
        adapter = initialized_adapter
        adapter.set_seed(7)
        a = adapter.game_state.combat_engine.dice_roller.roll("1d20").total

        adapter.set_seed(7)
        b = adapter.game_state.combat_engine.dice_roller.roll("1d20").total

        assert a == b

    def test_set_seed_raises_when_not_initialized(self) -> None:
        """Raises ValueError if no GameState yet (parity with other adapter methods)."""
        from client_2d.integration.engine_adapter import EngineAdapter

        adapter = EngineAdapter()
        with pytest.raises(ValueError, match="initialize_game"):
            adapter.set_seed(1)
