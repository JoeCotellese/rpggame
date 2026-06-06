# ABOUTME: Shared geometry helpers for combat resolution (reach parsing, distance helpers).
# ABOUTME: Lives in core so both the engine (resolve_attack) and scenario script executor share one parser.

from typing import Any


def attack_reach_for(monster_action: dict[str, Any] | None) -> int:
    """Parse a monster action's ``reach`` string into feet.

    ``monsters.json`` encodes reach per attack action as ``"5 ft."`` or
    ``"10 ft."``. Per SRD § Playing the Game › Melee Attacks, a creature
    has a 5-foot reach by default; creatures with greater reach declare
    it on the action. This helper returns the integer feet so callers
    can gate attack resolution on distance.

    Missing or unparseable values fall back to the SRD default (5 ft) so
    a malformed catalog row degrades to vanilla melee rather than
    silently widening reach.
    """
    if not monster_action:
        return 5
    raw = monster_action.get("reach")
    if not raw:
        return 5
    # "10 ft." -> "10"; tolerate stray whitespace too.
    head = str(raw).strip().split()[0]
    try:
        return int(head)
    except ValueError:
        return 5


def is_ranged_action(monster_action: dict[str, Any] | None) -> bool:
    """Return True when a monster action is a ranged attack.

    Monster catalog actions distinguish melee from ranged by which
    field they carry: a melee action declares ``reach``, a ranged
    action declares ``range``. The reach gate must skip ranged actions
    so a Longbow at 80 ft isn't rejected as "out of reach". When both
    fields are absent (rare; usually a malformed row) the action is
    treated as melee so the conservative 5-ft default applies.
    """
    if not monster_action:
        return False
    return monster_action.get("range") is not None and monster_action.get("reach") is None
