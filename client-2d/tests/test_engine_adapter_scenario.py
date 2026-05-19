# ABOUTME: Tests for EngineAdapter.load_scenario() (#361).
# ABOUTME: Verifies the adapter swaps in scenario-driven state and exposes positions.

"""Adapter-level tests for the YAML scenario loader integration.

The engine-only loader is tested in dnd-engine/tests. These tests cover
the client-2d wrapper that uses the loader: it must replace any existing
party/state on the adapter and surface positions for the GameWindow
handler to apply on the visual layer.
"""

from __future__ import annotations

from pathlib import Path

# Resolve the starter scenario shipped under dnd-engine/tests so the
# adapter test stays in lockstep with the engine-side fixtures.
SCENARIO_DIR = (
    Path(__file__).parent.parent.parent
    / "dnd-engine"
    / "tests"
    / "scenarios"
    / "yaml"
)


def test_load_scenario_replaces_party_and_state() -> None:
    """A fresh adapter loading a scenario YAML gets a fully wired state."""
    from client_2d.integration.engine_adapter import EngineAdapter

    adapter = EngineAdapter()
    result = adapter.load_scenario(SCENARIO_DIR / "ranged_attack_basic.yaml")

    # The adapter must now have the scenario's party and game state.
    assert adapter.party is not None
    assert len(adapter.party.characters) == 1
    assert adapter.party.characters[0].name == "Archy"
    assert adapter.game_state is not None
    assert adapter.in_combat is True

    # The return payload must carry the positions the GameWindow needs
    # to wire up the visual entities.
    assert result["name"] == "ranged_attack_basic"
    assert result["seed"] == 42
    assert result["party_positions"]["pc_archy"] == (3, 5)
    assert result["enemy_positions"]["goblin_0"] == (10, 5)


def test_load_scenario_overwrites_previous_state() -> None:
    """Loading a second scenario must wipe the first one's party."""
    from client_2d.integration.engine_adapter import EngineAdapter

    adapter = EngineAdapter()
    adapter.load_scenario(SCENARIO_DIR / "ranged_attack_basic.yaml")
    first_state_id = id(adapter.game_state)

    adapter.load_scenario(SCENARIO_DIR / "ranged_out_of_range.yaml")

    # New GameState (object identity changes), and the equipped weapon
    # reflects the dagger from the second scenario.
    assert id(adapter.game_state) != first_state_id
    from dnd_engine.systems.inventory import EquipmentSlot

    archy = adapter.party.characters[0]
    assert archy.inventory.get_equipped_item(EquipmentSlot.WEAPON) == "dagger"
