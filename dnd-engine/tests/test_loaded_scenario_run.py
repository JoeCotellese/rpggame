# ABOUTME: Tests for LoadedScenario.run() — the script+assertion convenience entry point.
# ABOUTME: Verifies end-to-end YAML → script → assertions flow in a single call.

"""Tests for ``LoadedScenario.run()`` (issue #363).

The convenience method ties the loader, executor, and assertion runner
together so a test or fixture can drive a YAML scenario to completion
in one call. These tests exercise both the happy path (script runs,
assertions pass) and the failure path (a deliberately wrong assertion
produces a clear, named error).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_engine.scenarios import ScenarioLoader
from dnd_engine.scenarios.assertions import ScenarioAssertionError


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "scenario.yaml"
    p.write_text(body.lstrip())
    return p


# Short-range happy-path scenario: shortbow attack on a goblin 35 ft
# away. The seed pins the goblin's max_hp via the data loader and the
# attack roll via the engine's DiceRoller, so the post-script HP is
# deterministic across runs.
HAPPY_YAML = """
name: lr_happy
seed: 42
map:
  dungeon: laboratory
  campaign: poisoned_laboratory
  start_room: laboratory.entrance
party:
  - class: fighter
    race: high_elf
    weapons: [shortbow]
    position: [3, 5]
    name: Archy
enemies:
  - monster_id: goblin
    position: [10, 5]
script:
  - action: attack
    target: goblin_0
assertions:
  - type: turn_count
    op: '=='
    value: 1
  - type: entity_present
    entity_id: goblin_0
"""


def test_run_executes_script_and_assertions(tmp_path: Path) -> None:
    path = _write(tmp_path, HAPPY_YAML)
    loaded = ScenarioLoader().load(path)

    ctx = loaded.run()

    assert ctx.turn_count == 1
    assert ctx.last_attack is not None


def test_run_returns_context_with_no_script_or_assertions(tmp_path: Path) -> None:
    # A scenario with no `script` and no `assertions` should still
    # return a usable context (empty effect).
    body = """
name: lr_empty
seed: 1
map:
  dungeon: laboratory
  campaign: poisoned_laboratory
  start_room: laboratory.entrance
party:
  - class: fighter
    race: human
    weapons: [shortsword]
    position: [3, 5]
    name: Quiet
enemies: []
"""
    path = _write(tmp_path, body)
    loaded = ScenarioLoader().load(path)

    ctx = loaded.run()

    assert ctx.turn_count == 0
    assert ctx.last_attack is None


def test_run_surfaces_assertion_failure_with_clear_message(tmp_path: Path) -> None:
    # Swap the damage range for an impossible bound so the assertion
    # must fail. The error message has to name the assertion type and
    # the offending value.
    bad_yaml = HAPPY_YAML + """  - type: last_attack_damage_in_range
    min: 9000
    max: 9001
"""
    path = _write(tmp_path, bad_yaml)
    loaded = ScenarioLoader().load(path)

    with pytest.raises(ScenarioAssertionError) as exc:
        loaded.run()
    msg = str(exc.value)
    assert "last_attack_damage_in_range" in msg
    assert "9000" in msg
