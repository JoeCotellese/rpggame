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

# Thrown-melee weapon (dagger) with an adjacent enemy and a distant
# target. Per SRD, a thrown weapon attack IS a ranged attack and must
# incur close-combat disadvantage even though dagger.category == 'melee'.
THROWN_CLOSE_COMBAT_YAML = """
name: exec_thrown_close_combat
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
    position: [4, 5]
  - monster_id: goblin
    position: [6, 5]
"""

# Ranged attacker with TWO goblins — one adjacent (close combat), one
# at 35 ft (the intended ranged target). SRD § Ranged Attacks in Close
# Combat (#400) requires disadvantage even when shooting the far target.
CLOSE_COMBAT_RANGED_YAML = """
name: exec_close_combat_ranged
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
    position: [4, 5]
  - monster_id: goblin
    position: [10, 5]
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


# --- attack: close-combat disadvantage flag (#400) -------------------------


def test_ranged_attack_with_adjacent_enemy_sets_disadvantage(tmp_path: Path) -> None:
    """SRD § Ranged Attacks in Close Combat: an adjacent (≤5 ft) hostile
    that can see the attacker and isn't Incapacitated imposes disadvantage
    on a ranged attack, even when the attack is aimed at a different,
    distant target.
    """
    path = _write(tmp_path, CLOSE_COMBAT_RANGED_YAML)
    loaded = ScenarioLoader().load(path)

    # goblin_0 is adjacent (4,5), goblin_1 is 35 ft away (10,5).
    # Shooting at goblin_1 must still incur close-combat disadvantage.
    ctx = ScriptExecutor(loaded).run(
        [{"action": "attack", "target": "goblin_1"}]
    )

    assert ctx.last_attack is not None
    assert ctx.last_attack_disadvantage is True


def test_melee_attack_with_adjacent_enemy_does_not_set_disadvantage(
    tmp_path: Path,
) -> None:
    """Close-combat disadvantage only applies to ranged attacks. A melee
    weapon swinging at an adjacent foe must not be flagged.
    """
    path = _write(tmp_path, MELEE_ADJACENT_YAML)
    loaded = ScenarioLoader().load(path)

    ctx = ScriptExecutor(loaded).run(
        [{"action": "attack", "target": "goblin_0"}]
    )

    assert ctx.last_attack_disadvantage is False


def test_ranged_attack_with_incapacitated_adjacent_enemy_no_disadvantage(
    tmp_path: Path,
) -> None:
    """SRD carve-out: an Incapacitated adjacent enemy does not impose
    disadvantage on a ranged attack.
    """
    path = _write(tmp_path, CLOSE_COMBAT_RANGED_YAML)
    loaded = ScenarioLoader().load(path)

    # Knock out the adjacent goblin before the script runs.
    adjacent_goblin = loaded.game_state.active_enemies[0]
    adjacent_goblin.add_condition("incapacitated")

    ctx = ScriptExecutor(loaded).run(
        [{"action": "attack", "target": "goblin_1"}]
    )

    assert ctx.last_attack_disadvantage is False


def test_thrown_attack_with_adjacent_enemy_sets_disadvantage(
    tmp_path: Path,
) -> None:
    """SRD: thrown weapon attacks are ranged attacks. A dagger thrown at a
    distant target while a hostile goblin is adjacent must roll with
    disadvantage even though dagger.category == 'melee'.
    """
    path = _write(tmp_path, THROWN_CLOSE_COMBAT_YAML)
    loaded = ScenarioLoader().load(path)

    # goblin_0 at (4,5) is 5 ft from Archy at (3,5); throw at goblin_1
    # at (6,5), 15 ft away (within dagger thrown range 20/60).
    ctx = ScriptExecutor(loaded).run(
        [{"action": "attack", "target": "goblin_1"}]
    )

    assert ctx.last_attack is not None
    assert ctx.last_attack_disadvantage is True


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


# --- monster reach parsing (#411) ------------------------------------------


def test_attack_reach_for_parses_five_foot_default() -> None:
    """A `5 ft.` reach string maps to 5."""
    from dnd_engine.scenarios.script_executor import _attack_reach_for

    assert _attack_reach_for({"reach": "5 ft."}) == 5


def test_attack_reach_for_parses_ten_foot_extended() -> None:
    """A `10 ft.` reach (bearded devil glaive) maps to 10."""
    from dnd_engine.scenarios.script_executor import _attack_reach_for

    assert _attack_reach_for({"reach": "10 ft."}) == 10


def test_attack_reach_for_defaults_when_missing() -> None:
    """Missing or empty reach falls back to the SRD default (5 ft).

    Guards against silent reach-widening when a catalog row omits the
    field — e.g., a homebrew monster JSON.
    """
    from dnd_engine.scenarios.script_executor import _attack_reach_for

    assert _attack_reach_for({}) == 5
    assert _attack_reach_for({"reach": None}) == 5
    assert _attack_reach_for({"reach": ""}) == 5
    assert _attack_reach_for(None) == 5


def test_attack_reach_for_defaults_when_unparseable() -> None:
    """A non-numeric reach value falls back to 5 ft.

    Defensive: rather than crash on a malformed string, the helper
    degrades to vanilla melee. Loud data errors are catalog-validator
    territory, not attack-resolution territory.
    """
    from dnd_engine.scenarios.script_executor import _attack_reach_for

    assert _attack_reach_for({"reach": "abc"}) == 5


# --- monster_attack action (#411) ------------------------------------------

# Fighter at (3, 5), bearded devil at (5, 5) — 2 tiles = 10 ft. The
# devil's Glaive has reach 10 ft, so it can hit at this range.
MONSTER_EXTENDED_REACH_YAML = """
name: exec_monster_extended_reach
seed: 7
map:
  dungeon: laboratory
  campaign: poisoned_laboratory
  start_room: laboratory.entrance
party:
  - class: fighter
    race: human
    weapons: [longsword]
    position: [3, 5]
    name: Brick
enemies:
  - monster_id: bearded_devil
    position: [5, 5]
"""

# Same layout but the attacker is a goblin (Scimitar, reach 5 ft).
# At 10 ft away the attack must be rejected.
MONSTER_DEFAULT_REACH_YAML = """
name: exec_monster_default_reach
seed: 7
map:
  dungeon: laboratory
  campaign: poisoned_laboratory
  start_room: laboratory.entrance
party:
  - class: fighter
    race: human
    weapons: [longsword]
    position: [3, 5]
    name: Brick
enemies:
  - monster_id: goblin
    position: [5, 5]
"""


def test_monster_attack_extended_reach_lands(tmp_path: Path) -> None:
    """Bearded devil's Glaive (10 ft) resolves at 10 ft."""
    path = _write(tmp_path, MONSTER_EXTENDED_REACH_YAML)
    loaded = ScenarioLoader().load(path)

    ctx = ScriptExecutor(loaded).run([
        {"action": "wait"},
        {
            "action": "monster_attack",
            "attacker": "bearded_devil_0",
            "target": "pc_brick",
            "monster_action": "Glaive",
        },
    ])

    assert ctx.last_attack is not None
    assert ctx.last_attack_error is None
    assert hasattr(ctx.last_attack, "hit")


def test_monster_attack_default_reach_rejected_at_ten_feet(tmp_path: Path) -> None:
    """Goblin Scimitar (5 ft) is rejected at 10 ft and HP is preserved."""
    path = _write(tmp_path, MONSTER_DEFAULT_REACH_YAML)
    loaded = ScenarioLoader().load(path)
    fighter = loaded.game_state.party.characters[0]
    starting_hp = fighter.current_hp

    ctx = ScriptExecutor(loaded).run([
        {"action": "wait"},
        {
            "action": "monster_attack",
            "attacker": "goblin_0",
            "target": "pc_brick",
            "monster_action": "Scimitar",
        },
    ])

    assert ctx.last_attack is None
    assert ctx.last_attack_error is not None
    assert "reach" in ctx.last_attack_error.lower()
    assert fighter.current_hp == starting_hp


def test_monster_attack_missing_attacker_raises(tmp_path: Path) -> None:
    """Unknown attacker entity_id surfaces a clear ScriptExecutionError."""
    path = _write(tmp_path, MONSTER_EXTENDED_REACH_YAML)
    loaded = ScenarioLoader().load(path)

    with pytest.raises(ScriptExecutionError) as exc:
        ScriptExecutor(loaded).run([
            {
                "action": "monster_attack",
                "attacker": "ghost_0",
                "target": "pc_brick",
                "monster_action": "Glaive",
            },
        ])
    assert "ghost_0" in str(exc.value)


def test_monster_attack_unknown_action_raises(tmp_path: Path) -> None:
    """Referencing an action the monster doesn't have raises an error."""
    path = _write(tmp_path, MONSTER_EXTENDED_REACH_YAML)
    loaded = ScenarioLoader().load(path)

    with pytest.raises(ScriptExecutionError) as exc:
        ScriptExecutor(loaded).run([
            {
                "action": "monster_attack",
                "attacker": "bearded_devil_0",
                "target": "pc_brick",
                "monster_action": "DoesNotExist",
            },
        ])
    assert "DoesNotExist" in str(exc.value)


def test_monster_attack_missing_required_field_raises(tmp_path: Path) -> None:
    """The action dispatcher rejects a monster_attack missing required keys."""
    path = _write(tmp_path, MONSTER_EXTENDED_REACH_YAML)
    loaded = ScenarioLoader().load(path)

    with pytest.raises(ScriptExecutionError) as exc:
        ScriptExecutor(loaded).run([
            {"action": "monster_attack", "attacker": "bearded_devil_0"},
        ])
    msg = str(exc.value).lower()
    assert "monster_attack" in msg or "target" in msg or "monster_action" in msg
