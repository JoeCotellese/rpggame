# ABOUTME: Unit tests for the scenario assertion vocabulary (issue #363).
# ABOUTME: Each assertion type gets a passing and a failing path with clear-message checks.

"""Unit tests for ``dnd_engine.scenarios.assertions``.

The assertion module is the vocabulary the YAML ``assertions:`` block
declares. Each runner takes a ``ScriptContext`` and a spec dict, returns
``None`` on success, and raises ``ScenarioAssertionError`` with a
human-readable message on failure. These tests pin both the success
shape and the message shape — corrupting an assertion in a real scenario
must surface a useful error (acceptance criterion 2 on #363).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from dnd_engine.scenarios.assertions import (
    ScenarioAssertionError,
    run_assertion,
)
from dnd_engine.scenarios.script_executor import ScriptContext


@dataclass
class _StubCreature:
    """Minimal stand-in for a Creature/Character used by assertion tests.

    Assertions only read ``current_hp``, ``is_alive``, and ``name`` —
    nothing else from the engine is needed to exercise them in
    isolation.
    """

    name: str
    current_hp: int = 10
    max_hp: int = 10
    is_alive: bool = True


@dataclass
class _StubParty:
    characters: list[_StubCreature] = field(default_factory=list)


@dataclass
class _StubGameState:
    party: _StubParty = field(default_factory=_StubParty)
    active_enemies: list[_StubCreature] = field(default_factory=list)
    in_combat: bool = False


def _ctx(
    party: list[_StubCreature] | None = None,
    enemies: list[_StubCreature] | None = None,
    in_combat: bool = False,
    last_attack: Any | None = None,
    last_attack_error: str | None = None,
    turn_count: int = 0,
) -> ScriptContext:
    """Build a ScriptContext with stubbed game state for assertion tests."""
    party = party or []
    enemies = enemies or []
    game_state = _StubGameState(
        party=_StubParty(characters=party),
        active_enemies=enemies,
        in_combat=in_combat,
    )
    party_ids = [f"pc_{c.name.lower().replace(' ', '_')}" for c in party]
    enemy_ids = [f"{e.name.lower()}_{i}" for i, e in enumerate(enemies)]
    return ScriptContext(
        game_state=game_state,
        party_positions=dict.fromkeys(party_ids, (0, 0)),
        enemy_positions=dict.fromkeys(enemy_ids, (0, 0)),
        party_entity_ids=party_ids,
        enemy_entity_ids=enemy_ids,
        last_attack=last_attack,
        last_attack_error=last_attack_error,
        turn_count=turn_count,
    )


# --- entity_hp ---------------------------------------------------------------


def test_entity_hp_passes_when_op_matches() -> None:
    ctx = _ctx(enemies=[_StubCreature(name="goblin", current_hp=4)])
    run_assertion(ctx, {"type": "entity_hp", "entity_id": "goblin_0", "op": "<=", "value": 5})


def test_entity_hp_fails_with_clear_message() -> None:
    ctx = _ctx(enemies=[_StubCreature(name="goblin", current_hp=7)])
    with pytest.raises(ScenarioAssertionError) as exc:
        run_assertion(
            ctx,
            {"type": "entity_hp", "entity_id": "goblin_0", "op": "<=", "value": 5},
        )
    msg = str(exc.value)
    assert "entity_hp" in msg
    assert "goblin_0" in msg
    assert "7" in msg
    assert "<= 5" in msg


def test_entity_hp_unknown_entity_raises_useful_error() -> None:
    ctx = _ctx()
    with pytest.raises(ScenarioAssertionError) as exc:
        run_assertion(ctx, {"type": "entity_hp", "entity_id": "ghost_0", "op": "==", "value": 0})
    assert "ghost_0" in str(exc.value)
    assert "unknown entity" in str(exc.value).lower()


def test_entity_hp_supports_all_operators() -> None:
    goblin = _StubCreature(name="goblin", current_hp=5)
    ctx = _ctx(enemies=[goblin])
    for op, value in [("==", 5), ("!=", 4), ("<", 6), (">", 4), ("<=", 5), (">=", 5)]:
        run_assertion(ctx, {"type": "entity_hp", "entity_id": "goblin_0", "op": op, "value": value})


# --- entity_present / entity_absent -----------------------------------------


def test_entity_present_passes_for_living_enemy() -> None:
    ctx = _ctx(enemies=[_StubCreature(name="goblin", is_alive=True)])
    run_assertion(ctx, {"type": "entity_present", "entity_id": "goblin_0"})


def test_entity_present_fails_for_dead_enemy() -> None:
    ctx = _ctx(enemies=[_StubCreature(name="goblin", is_alive=False, current_hp=0)])
    with pytest.raises(ScenarioAssertionError) as exc:
        run_assertion(ctx, {"type": "entity_present", "entity_id": "goblin_0"})
    assert "goblin_0" in str(exc.value)


def test_entity_absent_passes_for_dead_enemy() -> None:
    ctx = _ctx(enemies=[_StubCreature(name="goblin", is_alive=False, current_hp=0)])
    run_assertion(ctx, {"type": "entity_absent", "entity_id": "goblin_0"})


def test_entity_absent_passes_when_entity_does_not_exist() -> None:
    ctx = _ctx()
    run_assertion(ctx, {"type": "entity_absent", "entity_id": "ghost_0"})


def test_entity_absent_fails_for_living_enemy() -> None:
    ctx = _ctx(enemies=[_StubCreature(name="goblin", is_alive=True)])
    with pytest.raises(ScenarioAssertionError):
        run_assertion(ctx, {"type": "entity_absent", "entity_id": "goblin_0"})


# --- combat_active ----------------------------------------------------------


def test_combat_active_passes_when_in_combat() -> None:
    ctx = _ctx(in_combat=True)
    run_assertion(ctx, {"type": "combat_active", "value": True})


def test_combat_active_fails_when_in_combat_but_expected_out() -> None:
    ctx = _ctx(in_combat=True)
    with pytest.raises(ScenarioAssertionError):
        run_assertion(ctx, {"type": "combat_active", "value": False})


def test_combat_active_passes_when_out_of_combat() -> None:
    ctx = _ctx(in_combat=False)
    run_assertion(ctx, {"type": "combat_active", "value": False})


# --- turn_count -------------------------------------------------------------


def test_turn_count_passes_when_op_matches() -> None:
    ctx = _ctx(turn_count=3)
    run_assertion(ctx, {"type": "turn_count", "op": "==", "value": 3})
    run_assertion(ctx, {"type": "turn_count", "op": ">=", "value": 2})


def test_turn_count_fails_with_value_in_message() -> None:
    ctx = _ctx(turn_count=3)
    with pytest.raises(ScenarioAssertionError) as exc:
        run_assertion(ctx, {"type": "turn_count", "op": "==", "value": 5})
    msg = str(exc.value)
    assert "turn_count" in msg
    assert "3" in msg
    assert "== 5" in msg


# --- last_attack_hit --------------------------------------------------------


@dataclass
class _StubAttackResult:
    hit: bool
    damage: int


def test_last_attack_hit_passes_when_match() -> None:
    ctx = _ctx(last_attack=_StubAttackResult(hit=True, damage=4))
    run_assertion(ctx, {"type": "last_attack_hit", "value": True})


def test_last_attack_hit_fails_when_no_attack_made() -> None:
    ctx = _ctx()
    with pytest.raises(ScenarioAssertionError) as exc:
        run_assertion(ctx, {"type": "last_attack_hit", "value": True})
    assert "no attack" in str(exc.value).lower()


def test_last_attack_hit_fails_when_mismatch() -> None:
    ctx = _ctx(last_attack=_StubAttackResult(hit=False, damage=0))
    with pytest.raises(ScenarioAssertionError) as exc:
        run_assertion(ctx, {"type": "last_attack_hit", "value": True})
    assert "last_attack_hit" in str(exc.value)


# --- last_attack_damage_in_range -------------------------------------------


def test_last_attack_damage_in_range_passes_at_bounds() -> None:
    for damage in (3, 5, 7):
        ctx = _ctx(last_attack=_StubAttackResult(hit=True, damage=damage))
        run_assertion(
            ctx,
            {"type": "last_attack_damage_in_range", "min": 3, "max": 7},
        )


def test_last_attack_damage_in_range_fails_below_min() -> None:
    ctx = _ctx(last_attack=_StubAttackResult(hit=True, damage=2))
    with pytest.raises(ScenarioAssertionError) as exc:
        run_assertion(
            ctx,
            {"type": "last_attack_damage_in_range", "min": 3, "max": 7},
        )
    msg = str(exc.value)
    assert "2" in msg
    assert "3" in msg


def test_last_attack_damage_in_range_fails_above_max() -> None:
    ctx = _ctx(last_attack=_StubAttackResult(hit=True, damage=10))
    with pytest.raises(ScenarioAssertionError):
        run_assertion(
            ctx,
            {"type": "last_attack_damage_in_range", "min": 3, "max": 7},
        )


def test_last_attack_damage_in_range_fails_when_no_attack_made() -> None:
    ctx = _ctx()
    with pytest.raises(ScenarioAssertionError) as exc:
        run_assertion(
            ctx,
            {"type": "last_attack_damage_in_range", "min": 1, "max": 5},
        )
    assert "no attack" in str(exc.value).lower()


# --- unknown assertion type -------------------------------------------------


def test_unknown_assertion_type_raises_clear_error() -> None:
    ctx = _ctx()
    with pytest.raises(ScenarioAssertionError) as exc:
        run_assertion(ctx, {"type": "nope"})
    assert "nope" in str(exc.value)
    assert "unknown" in str(exc.value).lower()
