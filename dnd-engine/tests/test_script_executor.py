# ABOUTME: Tests for the YAML scenario script executor (issue #363).
# ABOUTME: Covers wait/attack actions, range rejection, and disadvantage flagging.

"""Unit + integration tests for ``dnd_engine.scenarios.script_executor``.

The executor takes a ``LoadedScenario`` (produced by ``ScenarioLoader``)
and runs its ``script`` field — a list of action dicts — against the
underlying ``GameState``, recording effects on a ``ScriptContext``.
These tests verify the action vocabulary (``wait``, ``attack``), the
disadvantage flag at long range, and the out-of-range rejection path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_engine.scenarios import ScenarioLoader
from dnd_engine.scenarios.script_executor import (
    ScriptContext,
    ScriptExecutionError,
    ScriptExecutor,
)


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "scenario.yaml"
    p.write_text(body.lstrip())
    return p


# Inline scenario body for short-range attack tests. High-elf fighter
# with shortbow vs a goblin 7 tiles (35 ft) away — comfortably in
# normal range (80 ft). Seed pinned so attack rolls are reproducible.
SHORT_RANGE_YAML = """
name: exec_short_range
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
"""

# Long-range body: dagger thrown beyond normal range (20 ft) but
# within max (60 ft). Dagger normal 20 ft → 4 tiles. Distance 5 tiles
# = 25 ft sits in long range and must flip the disadvantage flag on.
LONG_RANGE_YAML = """
name: exec_long_range
seed: 42
map:
  dungeon: laboratory
  campaign: poisoned_laboratory
  start_room: laboratory.entrance
party:
  - class: fighter
    race: high_elf
    weapons: [dagger]
    position: [3, 5]
    name: Archy
enemies:
  - monster_id: goblin
    position: [8, 5]
"""

# Out-of-range body: dagger past long range. Distance 17 tiles
# = 85 ft, beyond dagger long range of 60 ft. Attack must be
# rejected without invoking the engine.
OUT_OF_RANGE_YAML = """
name: exec_out_of_range
seed: 42
map:
  dungeon: laboratory
  campaign: poisoned_laboratory
  start_room: laboratory.entrance
party:
  - class: fighter
    race: high_elf
    weapons: [dagger]
    position: [3, 5]
    name: Archy
enemies:
  - monster_id: goblin
    position: [20, 5]
"""

# Adjacent enemy for melee: distance 1 tile = 5 ft, well within
# longsword's melee reach.
MELEE_ADJACENT_YAML = """
name: exec_melee
seed: 42
map:
  dungeon: laboratory
  campaign: poisoned_laboratory
  start_room: laboratory.entrance
party:
  - class: fighter
    race: high_elf
    weapons: [longsword]
    position: [3, 5]
    name: Archy
enemies:
  - monster_id: goblin
    position: [4, 5]
"""


# --- scaffold ---------------------------------------------------------------


def test_empty_script_is_noop(tmp_path: Path) -> None:
    path = _write(tmp_path, SHORT_RANGE_YAML)
    loaded = ScenarioLoader().load(path)

    ctx = ScriptExecutor(loaded).run([])

    assert isinstance(ctx, ScriptContext)
    assert ctx.turn_count == 0
    assert ctx.last_attack is None
    assert ctx.last_attack_error is None
    assert ctx.game_state is loaded.game_state


def test_executor_seeds_context_with_entity_ids(tmp_path: Path) -> None:
    path = _write(tmp_path, SHORT_RANGE_YAML)
    loaded = ScenarioLoader().load(path)

    ctx = ScriptExecutor(loaded).run([])

    assert ctx.party_entity_ids == ["pc_archy"]
    assert ctx.enemy_entity_ids == ["goblin_0"]
    assert ctx.party_positions["pc_archy"] == (3, 5)
    assert ctx.enemy_positions["goblin_0"] == (10, 5)


# --- wait action ------------------------------------------------------------


def test_wait_advances_turn_count(tmp_path: Path) -> None:
    path = _write(tmp_path, SHORT_RANGE_YAML)
    loaded = ScenarioLoader().load(path)

    ctx = ScriptExecutor(loaded).run([{"action": "wait"}])

    assert ctx.turn_count == 1


def test_wait_calls_initiative_next_turn(tmp_path: Path) -> None:
    path = _write(tmp_path, SHORT_RANGE_YAML)
    loaded = ScenarioLoader().load(path)
    tracker = loaded.game_state.initiative_tracker
    assert tracker is not None
    starting_total = tracker.total_turns_taken

    ScriptExecutor(loaded).run([{"action": "wait"}])

    assert tracker.total_turns_taken == starting_total + 1


# --- attack: in-range hit/miss path ----------------------------------------


def test_attack_in_range_stores_attack_result(tmp_path: Path) -> None:
    path = _write(tmp_path, SHORT_RANGE_YAML)
    loaded = ScenarioLoader().load(path)

    ctx = ScriptExecutor(loaded).run(
        [{"action": "attack", "target": "goblin_0"}]
    )

    assert ctx.last_attack is not None
    assert ctx.last_attack_error is None
    # Every AttackResult has these fields — pinning their presence guards
    # the contract the assertions rely on without baking in a particular
    # roll outcome.
    assert hasattr(ctx.last_attack, "hit")
    assert hasattr(ctx.last_attack, "damage")
    assert hasattr(ctx.last_attack, "attack_roll")


def test_attack_in_range_advances_turn(tmp_path: Path) -> None:
    path = _write(tmp_path, SHORT_RANGE_YAML)
    loaded = ScenarioLoader().load(path)

    ctx = ScriptExecutor(loaded).run(
        [{"action": "attack", "target": "goblin_0"}]
    )

    assert ctx.turn_count == 1


def test_melee_attack_in_range_resolves(tmp_path: Path) -> None:
    path = _write(tmp_path, MELEE_ADJACENT_YAML)
    loaded = ScenarioLoader().load(path)

    ctx = ScriptExecutor(loaded).run(
        [{"action": "attack", "target": "goblin_0"}]
    )

    assert ctx.last_attack is not None
    assert ctx.last_attack_error is None


# --- attack: out-of-range rejection ----------------------------------------


def test_attack_out_of_range_rejects_without_resolving(tmp_path: Path) -> None:
    path = _write(tmp_path, OUT_OF_RANGE_YAML)
    loaded = ScenarioLoader().load(path)
    goblin = loaded.game_state.active_enemies[0]
    starting_hp = goblin.current_hp

    ctx = ScriptExecutor(loaded).run(
        [{"action": "attack", "target": "goblin_0"}]
    )

    assert ctx.last_attack is None
    assert ctx.last_attack_error is not None
    assert "range" in ctx.last_attack_error.lower()
    # Rejection must not consume the attacker's turn, otherwise scenarios
    # can't deterministically distinguish "out of range" from "missed
    # and turn passed".
    assert ctx.turn_count == 0
    assert goblin.current_hp == starting_hp


# --- attack: long-range disadvantage flag ----------------------------------


def test_attack_in_long_range_sets_disadvantage_flag(tmp_path: Path) -> None:
    path = _write(tmp_path, LONG_RANGE_YAML)
    loaded = ScenarioLoader().load(path)

    ctx = ScriptExecutor(loaded).run(
        [{"action": "attack", "target": "goblin_0"}]
    )

    assert ctx.last_attack is not None
    assert ctx.last_attack_disadvantage is True


def test_attack_in_normal_range_leaves_disadvantage_off(tmp_path: Path) -> None:
    path = _write(tmp_path, SHORT_RANGE_YAML)
    loaded = ScenarioLoader().load(path)

    ctx = ScriptExecutor(loaded).run(
        [{"action": "attack", "target": "goblin_0"}]
    )

    assert ctx.last_attack_disadvantage is False


# --- error handling --------------------------------------------------------


def test_unknown_target_raises_clear_error(tmp_path: Path) -> None:
    path = _write(tmp_path, SHORT_RANGE_YAML)
    loaded = ScenarioLoader().load(path)

    with pytest.raises(ScriptExecutionError) as exc:
        ScriptExecutor(loaded).run(
            [{"action": "attack", "target": "ghost_0"}]
        )
    assert "ghost_0" in str(exc.value)


def test_unknown_action_raises_clear_error(tmp_path: Path) -> None:
    path = _write(tmp_path, SHORT_RANGE_YAML)
    loaded = ScenarioLoader().load(path)

    with pytest.raises(ScriptExecutionError) as exc:
        ScriptExecutor(loaded).run([{"action": "teleport"}])
    msg = str(exc.value).lower()
    assert "teleport" in msg
    assert "unknown" in msg
