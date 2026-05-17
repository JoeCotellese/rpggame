# ABOUTME: Scenario package — YAML-driven test setups for reproducible playtests.
# ABOUTME: Exposes the ScenarioLoader entry point and supporting types.

"""Public API for the scenario loader (issue #361).

Usage::

    from dnd_engine.scenarios import ScenarioLoader

    loaded = ScenarioLoader().load("path/to/scenario.yaml")
    loaded.game_state          # ready-to-play GameState
    loaded.party_positions     # {entity_id: (x, y)} for visual placement
    loaded.enemy_positions     # {entity_id: (x, y)} for visual placement
"""

from dnd_engine.scenarios.loader import (
    LoadedScenario,
    ScenarioLoader,
    ScenarioValidationError,
)

__all__ = [
    "LoadedScenario",
    "ScenarioLoader",
    "ScenarioValidationError",
]
