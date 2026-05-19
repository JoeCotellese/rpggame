# ABOUTME: Parametrized auto-discovery test — every YAML in scenarios/yaml/auto/ runs as a test.
# ABOUTME: Adding a scenario YAML grows the suite without touching Python code.

"""Auto-play regression suite (issue #363).

This module is intentionally tiny: the real work lives in the YAMLs
under ``tests/scenarios/yaml/auto/``. The conftest's
``pytest_generate_tests`` walks that directory and parametrizes the
test below across every file, so dropping a new YAML in is sufficient
to grow the suite — no Python changes required (acceptance criterion
3).

The deliberate-corruption test at the bottom guards acceptance
criterion 2: a wrong assertion must produce a clear, useful failure.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_engine.scenarios import ScenarioLoader
from dnd_engine.scenarios.assertions import ScenarioAssertionError


@pytest.mark.scenario
def test_scenario_runs_and_assertions_pass(scenario_session) -> None:
    """Drive every YAML in ``auto/`` through its script and assertions.

    A failure here means either the engine regressed against the
    scenario's expected outcome, or the scenario itself drifted from
    reality. The parametrization id is the YAML filename stem, so
    ``pytest -k ranged_long_range`` selects a single scenario.
    """
    scenario_session.run()


def test_corrupted_assertion_produces_clear_failure(tmp_path: Path) -> None:
    """Acceptance criterion: corrupting an assertion fails informatively.

    Take a known-good auto-play scenario, mutate its damage range to
    impossible bounds, and verify the resulting error names the
    assertion type and the offending values. Catches regressions that
    would swap a precise assertion failure for a generic crash.
    """
    src = (
        Path(__file__).parent / "scenarios" / "yaml" / "auto" / "ranged_short_hit.yaml"
    )
    body = src.read_text()
    # Replace the in-range damage bound with one no real shortbow can hit.
    corrupted = body.replace(
        "    min: 1\n    max: 20",
        "    min: 9000\n    max: 9001",
    )
    bad_path = tmp_path / "corrupted.yaml"
    bad_path.write_text(corrupted)

    loaded = ScenarioLoader().load(bad_path)

    with pytest.raises(ScenarioAssertionError) as exc:
        loaded.run()
    msg = str(exc.value)
    assert "last_attack_damage_in_range" in msg
    assert "9000" in msg
