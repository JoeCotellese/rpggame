# ABOUTME: SRD tests that ongoing condition-tick damage honors Immunity/Resistance/Vulnerability.
# ABOUTME: Guards #595 — condition ticks must route through the canonical damage pipeline.

"""Ongoing condition damage must respect damage-type modifiers.

SRD § Immunity / Resistance / Vulnerability apply to *all* damage of a
type, including recurring damage from a condition (e.g. the burning
"On Fire" effect deals 1d4 fire each turn). Before #595 the condition
turn-start handler applied the raw roll directly, so a fire-immune
creature still burned. These tests pin the fix: condition damage is
routed through `rules.damage.apply_damage_modifiers`.
"""

from __future__ import annotations

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.systems.condition_manager import ConditionManager


def _make_creature(name: str = "Target", hp: int = 100) -> Creature:
    abilities = Abilities(
        strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10
    )
    return Creature(name=name, max_hp=hp, ac=10, abilities=abilities)


def _tick_on_fire(creature: Creature, seed: int = 7):
    """Run one turn-start tick of the On Fire (1d4 fire) condition."""
    manager = ConditionManager(dice_roller=DiceRoller(seed=seed))
    creature.add_condition("on_fire")
    results = manager.process_turn_start_effects(creature)
    return next(r for r in results if r.effect_type == "damage")


class TestConditionDamageImmunity:
    """SRD § Immunity: a fire-immune creature takes no fire condition damage."""

    def test_fire_immune_takes_zero_from_on_fire(self) -> None:
        creature = _make_creature()
        creature.add_condition("has_immunity_fire")

        result = _tick_on_fire(creature)

        assert result.amount == 0
        assert creature.current_hp == 100


class TestConditionDamageResistance:
    """SRD § Resistance: fire condition damage is halved (round down)."""

    def test_fire_resistant_halves_on_fire(self) -> None:
        # Same seed → identical 1d4 roll; resistant result must be floor(raw / 2).
        baseline = _make_creature("Baseline")
        baseline_result = _tick_on_fire(baseline)
        raw = baseline_result.amount

        resistant = _make_creature("Resistant")
        resistant.add_condition("has_resistance_fire")
        resistant_result = _tick_on_fire(resistant)

        assert resistant_result.amount == raw // 2
        assert resistant.current_hp == 100 - (raw // 2)


class TestConditionDamageVulnerability:
    """SRD § Vulnerability: fire condition damage is doubled."""

    def test_fire_vulnerable_doubles_on_fire(self) -> None:
        baseline = _make_creature("Baseline")
        raw = _tick_on_fire(baseline).amount

        vulnerable = _make_creature("Vulnerable")
        vulnerable.add_condition("has_vulnerability_fire")
        vulnerable_result = _tick_on_fire(vulnerable)

        assert vulnerable_result.amount == raw * 2
        assert vulnerable.current_hp == 100 - (raw * 2)
