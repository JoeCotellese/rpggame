# ABOUTME: Unit tests for the canonical damage-modifier pipeline as a pure rules function.
# ABOUTME: Exercises apply_damage_modifiers (rules/damage.py) directly, decoupled from CombatEngine.

"""Tests for `dnd_engine.rules.damage.apply_damage_modifiers`.

The damage-type modifier pipeline (Immunity → Adjustments → Resistance →
Vulnerability) is a deterministic D&D rule. plan-02 shipped it as a method
on `CombatEngine`; this suite pins it as a standalone rules-layer function
so non-combat callers (condition ticks, auto-hit spells, thrown items) can
reuse the single canonical pipeline without depending on `CombatEngine`.
This mirrors how the sibling AC-formula selector lives in
`rules/ac_formulas.py`.
"""

from __future__ import annotations

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.rules.damage import apply_damage_modifiers


def _make_target(name: str = "Target", hp: int = 100) -> Creature:
    abilities = Abilities(
        strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10
    )
    return Creature(name=name, max_hp=hp, ac=10, abilities=abilities)


class TestUntypedDamage:
    def test_none_damage_type_returns_raw_unchanged(self) -> None:
        """Untyped damage cannot consult per-type modifiers."""
        target = _make_target()
        assert apply_damage_modifiers(target, 17, None) == 17


class TestImmunity:
    """SRD § Immunity: "you don't take damage of that type" — absolute zero."""

    def test_condition_flag_immunity_zeroes_matching_type(self) -> None:
        target = _make_target()
        target.add_condition("has_immunity_poison")
        assert apply_damage_modifiers(target, 20, "poison") == 0

    def test_catalog_immunity_zeroes_matching_type(self) -> None:
        target = _make_target()
        target.damage_immunities = ["poison"]
        assert apply_damage_modifiers(target, 20, "poison") == 0

    def test_immunity_scopes_by_type(self) -> None:
        target = _make_target()
        target.add_condition("has_immunity_poison")
        assert apply_damage_modifiers(target, 20, "fire") == 20


class TestResistance:
    """SRD § Resistance: damage of that type is halved (round down)."""

    def test_condition_flag_resistance_halves_with_floor(self) -> None:
        target = _make_target()
        target.add_condition("has_resistance_fire")
        assert apply_damage_modifiers(target, 5, "fire") == 2

    def test_resistance_all_halves_any_type(self) -> None:
        target = _make_target()
        target.add_condition("has_resistance_all")
        assert apply_damage_modifiers(target, 9, "cold") == 4


class TestVulnerability:
    """SRD § Vulnerability: damage of that type is doubled."""

    def test_condition_flag_vulnerability_doubles(self) -> None:
        target = _make_target()
        target.add_condition("has_vulnerability_cold")
        assert apply_damage_modifiers(target, 7, "cold") == 14


class TestAdjustments:
    """Pre-Resistance flat adjustment hook (damage_taken_reduction), clamped at 0."""

    def test_reduction_subtracts_before_resistance(self) -> None:
        target = _make_target()
        target.damage_taken_reduction = 3
        assert apply_damage_modifiers(target, 10, "fire") == 7

    def test_reduction_clamps_at_zero(self) -> None:
        target = _make_target()
        target.damage_taken_reduction = 5
        assert apply_damage_modifiers(target, 3, "fire") == 0


class TestEnvironment:
    """SRD § Underwater Combat: anything underwater has Resistance to Fire."""

    def test_underwater_halves_fire(self) -> None:
        target = _make_target()
        assert apply_damage_modifiers(target, 8, "fire", environment="underwater") == 4

    def test_underwater_does_not_affect_cold(self) -> None:
        target = _make_target()
        assert apply_damage_modifiers(target, 8, "cold", environment="underwater") == 8
