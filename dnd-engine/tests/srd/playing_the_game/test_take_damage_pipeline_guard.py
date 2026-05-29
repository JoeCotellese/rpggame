# ABOUTME: Regression guard ensuring take_damage is only called from pipeline-routing modules.
# ABOUTME: Prevents new code from bypassing rules.damage.apply_damage_modifiers (#595).

"""Guard against new `take_damage` bypasses of the canonical damage pipeline.

`Creature.take_damage` is a low-level "subtract HP, clamp at 0" primitive
with no damage-type awareness. Typed damage must first pass through
`rules.damage.apply_damage_modifiers` (Immunity / Resistance /
Vulnerability / environment) and only the reduced integer should reach
`take_damage`.

This test walks the engine source with the AST and asserts that
`.take_damage(...)` is *called* only from an explicit allowlist of
modules that route through the pipeline (or are sanctioned primitives).
A new call site anywhere else fails this test: the author must either
route the damage through `apply_damage_modifiers` (and apply it from an
already-allowed module) or consciously add their module here, forcing a
reviewer to confirm the damage is pre-reduced.

Mirrors the source-level guard style used by test_ac_seam_unification.py
for the AC_SET_BASE migration.
"""

from __future__ import annotations

import ast
from pathlib import Path

# Engine package root: tests/srd/playing_the_game/ -> dnd-engine/ -> dnd_engine/
_ENGINE_PACKAGE = Path(__file__).parents[3] / "dnd_engine"

# Modules permitted to call `take_damage`. Each either routes the amount
# through rules.damage.apply_damage_modifiers first, or is a sanctioned
# HP primitive / override.
_ALLOWED_CALLERS = {
    # Pipeline consumers — apply already-reduced, typed damage.
    "core/combat.py",  # resolve_attack, resolve_spell_save, _process_saving_throw_effect
    "core/game_state.py",  # auto-hit spells (Magic Missile)
    "systems/condition_manager.py",  # ongoing condition-tick damage
    "systems/item_effects.py",  # thrown-item damage
    # Sanctioned primitive: Character.take_damage delegates to super().
    "core/character.py",
}


def _modules_calling_take_damage() -> set[str]:
    """Return engine module paths (relative, POSIX) that *call* take_damage."""
    offenders: set[str] = set()
    for path in _ENGINE_PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            # Match calls of the form `<expr>.take_damage(...)`, not the
            # `def take_damage` definitions.
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "take_damage"
            ):
                offenders.add(path.relative_to(_ENGINE_PACKAGE).as_posix())
                break
    return offenders


def test_take_damage_only_called_from_pipeline_routing_modules() -> None:
    """No engine module outside the allowlist may call `take_damage`.

    Routing typed damage through `take_damage` directly skips Immunity,
    Resistance, and Vulnerability. New damage sources must go through
    `rules.damage.apply_damage_modifiers` first.
    """
    callers = _modules_calling_take_damage()
    unexpected = callers - _ALLOWED_CALLERS

    assert not unexpected, (
        "These modules call `take_damage` but are not in the pipeline "
        f"allowlist: {sorted(unexpected)}. Route the damage through "
        "`rules.damage.apply_damage_modifiers` before applying it, or — "
        "if the amount is genuinely pre-reduced — add the module to "
        "`_ALLOWED_CALLERS` in this test so the bypass is reviewed."
    )


def test_allowlist_has_no_stale_entries() -> None:
    """Every allowlisted module still calls `take_damage`.

    Keeps the allowlist honest: if a module stops calling take_damage
    (e.g. it gets refactored away), drop it from the allowlist rather
    than leaving a stale exemption that could mask a future bypass.
    """
    callers = _modules_calling_take_damage()
    stale = _ALLOWED_CALLERS - callers

    assert not stale, (
        f"Allowlist entries no longer call take_damage: {sorted(stale)}. "
        "Remove them from `_ALLOWED_CALLERS`."
    )
