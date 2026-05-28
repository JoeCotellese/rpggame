# ABOUTME: Canonical damage-type modifier pipeline (Immunity/Resistance/Vulnerability) as pure rules.
# ABOUTME: Single chokepoint reused by CombatEngine, condition ticks, auto-hit spells, and thrown items.

"""Canonical damage-modifier pipeline.

The SRD's Resistance, Immunity, and Vulnerability rules key off a single
deterministic transform from raw rolled damage to the amount a creature
actually takes. This module is that chokepoint, expressed as pure
functions so any caller can route typed damage through it without
depending on `CombatEngine`. It mirrors how the sibling AC-formula
selector lives in `rules/ac_formulas.py`.

SRD § Playing the Game › Resistance and Vulnerability › Order of
Application:
    "Modifiers to damage are applied in the following order: adjustments
     such as bonuses, penalties, or multipliers are applied first;
     Resistance is applied second; and Vulnerability is applied third."
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dnd_engine.core.creature import Creature


def apply_damage_adjustments(target: Creature, damage: int, damage_type: str) -> int:
    """
    Apply pre-Resistance flat adjustments (bonuses, penalties,
    multipliers) to the running damage.

    Extension hook for the "adjustments" stage of the SRD damage
    modifier pipeline (§ Resistance and Vulnerability › Order of
    Application). Default behavior reads a single
    `damage_taken_reduction` attribute on the target — a
    non-negative integer subtracted from the damage — which covers
    the SRD's worked example of a "magical aura that reduces all
    damage by 5".

    Hook contract:
      - Receives the post-Immunity, pre-Resistance damage and the
        normalized (lowercase) damage type.
      - Returns the adjusted damage (must be a non-negative int;
        the implementation clamps to 0 so a 3-damage hit against a
        -5 aura cannot become negative damage).
      - New sources should be additive on top of the default
        reader rather than replacing it, to preserve existing
        behavior.

    Args:
        target: The creature taking the damage.
        damage: Damage after Immunity short-circuit, before
            Resistance halving.
        damage_type: Normalized (lowercase) SRD damage type. Passed
            through for future per-type adjustment sources; the
            default reader is type-agnostic.

    Returns:
        The adjusted damage, clamped at 0.
    """
    reduction = getattr(target, "damage_taken_reduction", 0) or 0
    adjusted = damage - reduction
    return max(adjusted, 0)


def apply_damage_modifiers(
    target: Creature,
    raw_damage: int,
    damage_type: str | None,
    environment: str | None = None,
) -> int:
    """
    Scale raw damage by the target's per-type Resistance, Immunity,
    Vulnerability, and flat adjustments.

    Single chokepoint that the SRD's Resistance, Immunity, and
    Vulnerability rules key off of.

    Pipeline order:
      1. Immunity (zero) — short-circuits everything else.
      2. Adjustments (flat bonus / penalty hook).
      3. Resistance (halve, floor).
      4. Vulnerability (double).

    Immunity is placed BEFORE the adjustments stage even though the
    SRD's order-of-application sentence only names the
    adjustments/Resistance/Vulnerability trio. The SRD defines
    Immunity as "you don't take damage of that type" — an absolute
    zero-out, not a multiplier. Running adjustments on an immune
    target would let a `damage_taken_reduction` of 5 turn into
    post-immunity "damage" of -5 (then clamped), which contradicts
    the plain-language reading of Immunity. The SRD's worked
    example does not mix Immunity with adjustments, so this is a
    defensible reading rather than a contradiction.

    Consults two sources of per-type modifiers, in parity across
    Resistance, Immunity, and Vulnerability:
      1. Creature condition flags — `has_resistance_{type}`,
         `has_immunity_{type}`, and `has_vulnerability_{type}`. The
         Resistance stage additionally recognizes `has_resistance_all`
         as a blanket "Resistance to all damage" source.
      2. Monster catalog fields — `damage_resistances`,
         `damage_immunities`, and `damage_vulnerabilities` list
         attributes on the Creature instance (populated by
         `DataLoader.create_monster` from `monsters.json`). The
         Resistance stage additionally recognizes the literal token
         `"all"` in `damage_resistances` as a blanket source.

    Environment-granted Resistance:
        SRD § Playing the Game › Underwater Combat carves out a
        third Resistance source: "Anything underwater has
        Resistance to Fire damage." This is environmental, not
        creature-typed or condition-applied. When `environment ==
        "underwater"` and `damage_type == "fire"`, the Resistance
        stage halves the damage exactly once (No Stacking still
        holds with any other Fire-Resistance source).

    SRD § Playing the Game › Resistance and Vulnerability:
        "If you have Resistance to a damage type, damage of that
         type is halved against you (round down)."
        "If you have Vulnerability to a damage type, damage of that
         type is doubled against you."
        "Multiple instances of Resistance or Vulnerability that
         affect the same damage type count as only one instance."
    SRD § Playing the Game › Immunity:
        "Immunity to a damage type means you don't take damage of
         that type."

    Args:
        target: The creature taking the damage.
        raw_damage: Damage rolled before per-type scaling.
        damage_type: SRD damage type (e.g. "fire", "cold",
            "slashing"). If None, no per-type scaling can apply
            and `raw_damage` is returned unchanged.
        environment: Optional environment tag for the target's
            current room (e.g. "underwater"). When provided, the
            Resistance stage consults SRD environment carve-outs
            (currently: underwater → Fire Resistance). Defaults to
            None for callers that have no environment context;
            this preserves legacy behavior.

    Returns:
        The damage amount after the full modifier pipeline.
    """
    # Untyped damage cannot consult per-type modifiers; return as-is.
    if damage_type is None:
        return raw_damage

    # Normalize: SRD damage-type tokens are lowercase in the catalog.
    normalized_type = damage_type.lower()

    # --- Immunity stage --------------------------------------------------
    # Immunity zeroes damage of the matching type; both the
    # condition-flag form and the catalog-field form are honored.
    # Placed first because Immunity is absolute ("you don't take
    # damage of that type"), not a multiplier — see method docstring.
    immunity_condition = f"has_immunity_{normalized_type}"
    catalog_immunities = [t.lower() for t in (getattr(target, "damage_immunities", None) or [])]
    if target.has_condition(immunity_condition) or normalized_type in catalog_immunities:
        return 0

    # --- Adjustments stage ----------------------------------------------
    # Pre-Resistance flat bonuses / penalties / multipliers. The SRD
    # worked example uses "a magical aura that reduces all damage
    # by 5". The extension hook here reads a single
    # `damage_taken_reduction` attribute (a non-negative int) and
    # subtracts it from the running damage.
    damage = apply_damage_adjustments(target, raw_damage, normalized_type)

    # --- Resistance stage ------------------------------------------------
    # Resistance halves matching damage with floor rounding. The
    # No-Stacking rule is satisfied by a single boolean branch:
    # multiple sources (condition flag, per-type catalog entry,
    # blanket "all", environment carve-out) still halve exactly once.
    resistance_condition = f"has_resistance_{normalized_type}"
    catalog_resistances = [t.lower() for t in (getattr(target, "damage_resistances", None) or [])]
    # SRD § Underwater Combat: "Anything underwater has Resistance
    # to Fire damage." Environment-granted, not catalog or condition.
    environment_grants_resistance = environment == "underwater" and normalized_type == "fire"
    has_resistance = (
        target.has_condition(resistance_condition)
        or target.has_condition("has_resistance_all")
        or normalized_type in catalog_resistances
        or "all" in catalog_resistances
        or environment_grants_resistance
    )
    if has_resistance:
        damage = damage // 2

    # --- Vulnerability stage --------------------------------------------
    # Vulnerability doubles matching damage. Two sources (condition
    # flag + catalog field) still double exactly once — the SRD's
    # No-Stacking rule is satisfied by a single boolean branch
    # rather than a counted multiplier.
    vulnerability_condition = f"has_vulnerability_{normalized_type}"
    catalog_vulnerabilities = [
        t.lower() for t in (getattr(target, "damage_vulnerabilities", None) or [])
    ]
    if target.has_condition(vulnerability_condition) or normalized_type in catalog_vulnerabilities:
        damage = damage * 2

    return damage
