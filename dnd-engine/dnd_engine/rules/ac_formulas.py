# ABOUTME: Registry mapping alternate base-AC formula identifiers to callables.
# ABOUTME: Used by data-driven spells (Mage Armor, Barkskin) and class features.

"""Alternate base-AC formula registry.

SRD § Playing the Game › Attack Rolls › Armor Class › "Only One Base AC"
states that a creature with multiple ways to calculate its AC must choose
which one to use. The engine honors that rule via
`Creature.register_base_ac_formula` (which stores a callable) and
`Creature.active_base_ac_formula` (which names the single live selection).

This module provides the named formulas that spell data refers to by ID
so spells.json / items.json can stay data-driven without embedding Python
callables. A spell effect of shape::

    {"modifier_type": "register_base_ac_formula", "formula_id": "mage_armor"}

instructs `GameState` to look up the callable here, register it on the
target, and activate it for the duration of the effect.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dnd_engine.core.creature import Creature


def _mage_armor_formula(creature: Creature) -> int:
    """Mage Armor: target's base AC becomes 13 + Dexterity modifier.

    SRD § Spell Descriptions › Mage Armor (docs/srd/spells/mage-armor.md):

        "You touch a willing creature who isn't wearing armor. Until the
        spell ends, the target's base AC becomes 13 plus its Dexterity
        modifier."
    """
    return 13 + creature.abilities.dex_mod


def _barkskin_formula(creature: Creature) -> int:
    """Barkskin: target's AC becomes 17 if its AC is lower than that.

    SRD § Spell Descriptions › Barkskin (docs/srd/spells/barkskin.md):

        "You touch a willing creature. Until the spell ends, the target's
        skin assumes a bark-like appearance, and the target has an Armor
        Class of 17 if its AC is lower than that."

    Barkskin is an AC floor rather than a hard replacement: it only
    raises the target's AC. We honor that by returning the maximum of
    the creature's stored `_base_ac` and 17. Because layered modifiers
    (Shield, magic-item bonuses, Haste) are applied on top of the base
    in `GameState.get_effective_ac`, the floor here is correctly
    evaluated against the unarmored / armor-derived base — not against
    a base already inflated by temporary spells.
    """
    return max(creature._base_ac, 17)


# Identifier → formula. Add entries here when introducing new
# alt-base-AC mechanics (e.g., Barbarian / Monk Unarmored Defense,
# Draconic Resilience). Keys must be stable strings used in spell /
# class data; values are pure functions of the creature.
BASE_AC_FORMULAS: dict[str, Callable[[Creature], int]] = {
    "mage_armor": _mage_armor_formula,
    "barkskin": _barkskin_formula,
}


def get_base_ac_formula(formula_id: str) -> Callable[[Creature], int] | None:
    """Return the formula callable for `formula_id`, or None if unknown.

    Args:
        formula_id: Identifier as it appears in spell / item effect data.

    Returns:
        Callable taking a `Creature` and returning its base AC, or None.
    """
    return BASE_AC_FORMULAS.get(formula_id)
