# ABOUTME: SRD tests that thrown-item damage honors Immunity/Vulnerability/catalog modifiers.
# ABOUTME: Guards #595 — item damage routes its applied number through the canonical pipeline.

"""Thrown-item damage must respect damage-type modifiers beyond Resistance.

Item-driven damage (alchemist's fire, acid vial, holy water) historically
only consulted a per-type Resistance condition by hand, missing Immunity,
Vulnerability, and the monster catalog fields. #595 routes the applied
amount through `rules.damage.apply_damage_modifiers` so those rules apply.

Environment-granted Resistance for items (e.g. thrown fire underwater) is
intentionally still out of scope here — that gap remains documented by the
guard in test_underwater_combat.py.
"""

from __future__ import annotations

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.systems.item_effects import _apply_damage_effect


def _make_target(name: str = "Target", hp: int = 100) -> Creature:
    abilities = Abilities(
        strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10
    )
    return Creature(name=name, max_hp=hp, ac=10, abilities=abilities)


def _throw_fire(target: Creature):
    """Apply a fixed 10 fire damage thrown item (no dice noise)."""
    return _apply_damage_effect(
        item_info={"name": "Alchemist's Fire", "damage": "0d4+10", "damage_type": "fire"},
        target=target,
        dice_roller=DiceRoller(seed=1),
        event_bus=None,
    )


class TestItemDamageImmunity:
    """SRD § Immunity: a fire-immune target takes no fire item damage."""

    def test_condition_flag_immunity_zeroes(self) -> None:
        target = _make_target()
        target.add_condition("has_immunity_fire")

        result = _throw_fire(target)

        assert result.amount == 0
        assert target.current_hp == 100

    def test_catalog_immunity_zeroes(self) -> None:
        target = _make_target()
        target.damage_immunities = ["fire"]

        result = _throw_fire(target)

        assert result.amount == 0
        assert target.current_hp == 100


class TestItemDamageVulnerability:
    """SRD § Vulnerability: a fire-vulnerable target takes doubled fire item damage."""

    def test_condition_flag_vulnerability_doubles(self) -> None:
        target = _make_target()
        target.add_condition("has_vulnerability_fire")

        result = _throw_fire(target)

        assert result.amount == 20
        assert target.current_hp == 80


class TestItemDamageMessageReflectsPipeline:
    """The result message/event must describe what the pipeline actually did.

    The displayed annotation historically keyed off a per-type Resistance
    *condition* only, so catalog Resistance/Immunity/Vulnerability — now
    honored by the pipeline — produced messages that under- or mis-described
    the applied number. The annotation must instead derive from the real
    outcome.
    """

    def test_catalog_resistance_message_notes_halving(self) -> None:
        target = _make_target()
        target.damage_resistances = ["fire"]

        result = _throw_fire(target)

        assert result.amount == 5
        assert "halved by resistance" in result.message

    def test_catalog_vulnerability_message_notes_doubling(self) -> None:
        target = _make_target()
        target.damage_vulnerabilities = ["fire"]

        result = _throw_fire(target)

        assert result.amount == 20
        assert "doubled by vulnerability" in result.message

    def test_catalog_immunity_message_notes_immunity(self) -> None:
        target = _make_target()
        target.damage_immunities = ["fire"]

        result = _throw_fire(target)

        assert result.amount == 0
        assert "immune" in result.message

    def test_condition_resistance_still_notes_halving(self) -> None:
        target = _make_target()
        target.add_condition("has_resistance_fire")

        result = _throw_fire(target)

        assert result.amount == 5
        assert "halved by resistance" in result.message


class TestItemDamageEnvironment:
    """SRD § Underwater Combat: anything underwater has Resistance to Fire."""

    def test_underwater_halves_thrown_fire(self) -> None:
        target = _make_target()
        assert not target.has_condition("has_resistance_fire")

        result = _apply_damage_effect(
            item_info={"name": "Alchemist's Fire", "damage": "0d4+10", "damage_type": "fire"},
            target=target,
            dice_roller=DiceRoller(seed=1),
            event_bus=None,
            environment="underwater",
        )

        assert result.amount == 5
        assert target.current_hp == 95
