# ABOUTME: Pytest plumbing for scenario-driven auto-play tests (issue #363).
# ABOUTME: Exposes `scenario_session` + auto-discovers YAMLs under tests/scenarios/yaml/auto/.

"""Auto-play harness conftest.

Provides two pieces of pytest plumbing:

1. The ``scenario_session`` fixture — loads a YAML scenario (chosen by
   the parametrized ``scenario_path``) into a ``LoadedScenario`` ready
   for ``.run()``.
2. The ``scenario`` marker — when a test takes ``scenario_path`` or
   ``scenario_session`` as a parameter, it gets parametrized across
   every YAML under ``tests/scenarios/yaml/auto/``. Pass explicit
   paths via ``@pytest.mark.scenario("path/to/x.yaml")`` to pin a test
   to a specific file (or files).

Adding a new auto-play scenario is therefore a no-code task: drop a
YAML into the ``auto/`` directory and the parametrized test picks it
up on the next pytest run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_engine.scenarios import LoadedScenario, ScenarioLoader

AUTO_SCENARIO_DIR = Path(__file__).parent / "scenarios" / "yaml" / "auto"


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers so ``pytest --strict-markers`` is happy."""
    config.addinivalue_line(
        "markers",
        "scenario(*paths): parametrize a test across YAML scenarios. "
        "With no args, auto-discovers all YAMLs in tests/scenarios/yaml/auto/.",
    )
    config.addinivalue_line(
        "markers",
        "srd(path, lines=None): cross-reference a test to an SRD section. "
        "`path` is relative to docs/srd/ (e.g. 'playing-the-game/ranged-attacks.md'). "
        "`lines` optionally pins the source_lines range from the file's frontmatter. "
        "Use on tests under tests/srd/ to build the conformance coverage matrix.",
    )


def _discover_auto_scenarios() -> list[Path]:
    if not AUTO_SCENARIO_DIR.exists():
        return []
    return sorted(AUTO_SCENARIO_DIR.glob("*.yaml"))


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize ``scenario_path`` from the ``scenario`` marker.

    A test triggers parametrization if it takes ``scenario_path`` (or
    pulls it in transitively via ``scenario_session``). Explicit paths
    in the marker take precedence; otherwise the ``auto/`` directory is
    walked.
    """
    if "scenario_path" not in metafunc.fixturenames:
        return

    marker = metafunc.definition.get_closest_marker("scenario")
    if marker is not None and marker.args:
        paths = [Path(p) for p in marker.args]
    else:
        paths = _discover_auto_scenarios()

    if not paths:
        # Skip rather than crash so an empty auto/ directory doesn't
        # break a developer's first run.
        metafunc.parametrize("scenario_path", [], ids=[])
        return

    metafunc.parametrize(
        "scenario_path",
        paths,
        ids=[p.stem for p in paths],
    )


@pytest.fixture
def scenario_session(scenario_path: Path) -> LoadedScenario:
    """Load the parametrized scenario YAML into a ``LoadedScenario``.

    The returned object exposes ``.run()`` to execute the scenario's
    script and assertions in one call, and ``.game_state`` /
    ``.party_positions`` / ``.enemy_positions`` for tests that want to
    inspect or drive the engine manually.
    """
    return ScenarioLoader().load(scenario_path)
