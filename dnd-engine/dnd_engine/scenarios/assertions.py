# ABOUTME: Assertion vocabulary for YAML scenarios — readable failures, no magic.
# ABOUTME: Each runner takes a ScriptContext + spec and raises ScenarioAssertionError on mismatch.

"""Assertion runners for YAML scenario tests (issue #363).

The supported assertion types are the floor that #363 specifies:
``entity_hp``, ``entity_present``, ``entity_absent``, ``combat_active``,
``turn_count``, ``last_attack_hit``, ``last_attack_damage_in_range``.

Every failure raises :class:`ScenarioAssertionError` with a message that
includes the assertion type, the entity/value at issue, and the
expected operator + bound. Acceptance criterion 2 of the issue is that
corrupting an assertion produces a clear, useful failure — the messages
here are designed to be greppable and self-explanatory.
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from typing import Any

from dnd_engine.scenarios.script_executor import ScriptContext


class ScenarioAssertionError(AssertionError):
    """Raised when a scenario assertion fails.

    Subclasses ``AssertionError`` so pytest reports it like any other
    failed expectation, but the distinct type lets harness code
    distinguish assertion failures from engine errors.
    """


_OPS: dict[str, Callable[[Any, Any], bool]] = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


def _apply_op(op: str, lhs: Any, rhs: Any, *, assertion: str) -> bool:
    if op not in _OPS:
        raise ScenarioAssertionError(
            f"{assertion}: unknown operator '{op}'. "
            f"Valid: {', '.join(sorted(_OPS))}"
        )
    return _OPS[op](lhs, rhs)


def entity_hp(ctx: ScriptContext, spec: dict[str, Any]) -> None:
    entity_id = spec["entity_id"]
    op = spec["op"]
    value = spec["value"]
    creature = ctx.resolve_entity(entity_id)
    if creature is None:
        raise ScenarioAssertionError(
            f"entity_hp: unknown entity '{entity_id}'"
        )
    actual = getattr(creature, "current_hp", None)
    if not _apply_op(op, actual, value, assertion="entity_hp"):
        raise ScenarioAssertionError(
            f"entity_hp({entity_id}): expected {op} {value}, got {actual}"
        )


def entity_present(ctx: ScriptContext, spec: dict[str, Any]) -> None:
    entity_id = spec["entity_id"]
    creature = ctx.resolve_entity(entity_id)
    if creature is None or not getattr(creature, "is_alive", False):
        raise ScenarioAssertionError(
            f"entity_present: '{entity_id}' is not present "
            f"(creature={'missing' if creature is None else 'dead'})"
        )


def entity_absent(ctx: ScriptContext, spec: dict[str, Any]) -> None:
    entity_id = spec["entity_id"]
    creature = ctx.resolve_entity(entity_id)
    if creature is not None and getattr(creature, "is_alive", False):
        raise ScenarioAssertionError(
            f"entity_absent: '{entity_id}' is still alive"
        )


def combat_active(ctx: ScriptContext, spec: dict[str, Any]) -> None:
    expected = bool(spec["value"])
    actual = bool(getattr(ctx.game_state, "in_combat", False))
    if actual != expected:
        raise ScenarioAssertionError(
            f"combat_active: expected {expected}, got {actual}"
        )


def turn_count(ctx: ScriptContext, spec: dict[str, Any]) -> None:
    op = spec["op"]
    value = spec["value"]
    actual = ctx.turn_count
    if not _apply_op(op, actual, value, assertion="turn_count"):
        raise ScenarioAssertionError(
            f"turn_count: expected {op} {value}, got {actual}"
        )


def last_attack_hit(ctx: ScriptContext, spec: dict[str, Any]) -> None:
    expected = bool(spec["value"])
    if ctx.last_attack is None:
        raise ScenarioAssertionError(
            "last_attack_hit: no attack has been made in this scenario"
        )
    actual = bool(getattr(ctx.last_attack, "hit", False))
    if actual != expected:
        raise ScenarioAssertionError(
            f"last_attack_hit: expected {expected}, got {actual}"
        )


def last_attack_damage_in_range(ctx: ScriptContext, spec: dict[str, Any]) -> None:
    lo = int(spec["min"])
    hi = int(spec["max"])
    if ctx.last_attack is None:
        raise ScenarioAssertionError(
            "last_attack_damage_in_range: no attack has been made in this scenario"
        )
    actual = int(getattr(ctx.last_attack, "damage", 0))
    if not (lo <= actual <= hi):
        raise ScenarioAssertionError(
            f"last_attack_damage_in_range: expected {lo}..{hi}, got {actual}"
        )


_ASSERTIONS: dict[str, Callable[[ScriptContext, dict[str, Any]], None]] = {
    "entity_hp": entity_hp,
    "entity_present": entity_present,
    "entity_absent": entity_absent,
    "combat_active": combat_active,
    "turn_count": turn_count,
    "last_attack_hit": last_attack_hit,
    "last_attack_damage_in_range": last_attack_damage_in_range,
}


def run_assertion(ctx: ScriptContext, spec: dict[str, Any]) -> None:
    """Dispatch a single assertion spec to its runner.

    The ``type`` key selects the runner; everything else is the runner's
    spec. An unknown type is itself an assertion failure with a clear
    error message rather than a silent no-op.
    """
    a_type = spec.get("type")
    if a_type is None:
        raise ScenarioAssertionError(
            f"assertion missing 'type' key: {spec!r}"
        )
    runner = _ASSERTIONS.get(a_type)
    if runner is None:
        raise ScenarioAssertionError(
            f"unknown assertion type '{a_type}'. "
            f"Valid: {', '.join(sorted(_ASSERTIONS))}"
        )
    runner(ctx, spec)
