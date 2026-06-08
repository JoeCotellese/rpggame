# ABOUTME: SRD § Playing the Game › Proficiency Bonus — monster PB from CR.
# ABOUTME: Plan-08 slice 2 — pure helper mapping a Challenge Rating to a PB.

"""Monster Proficiency Bonus derived from Challenge Rating.

The 2024 SRD pins a monster's Proficiency Bonus to its Challenge
Rating via a single table (see ``docs/srd/playing-the-game/proficiency.md``):

    | CR          | PB |
    | ----------- | -- |
    | Up to 4     | +2 |
    | 5–8         | +3 |
    | 9–12        | +4 |
    | 13–16       | +5 |
    | 17–20       | +6 |
    | 21–24       | +7 |
    | 25–28       | +8 |
    | 29–30       | +9 |

This module exposes a single pure helper —
:func:`proficiency_bonus_from_cr` — that consumers (``Creature``,
``DataLoader``, and future D20 surfaces in plan-08 slice 3) call to
derive a monster's PB from the catalog ``cr`` string. Characters use
their own level-based derivation (see ``Character.proficiency_bonus``);
this helper is monster-side only.
"""

from __future__ import annotations

from typing import Final

# CR strings recognized by the catalog. Fractional CRs all map to +2
# per the SRD table's "Up to 4" row.
_FRACTIONAL_CR: Final[set[str]] = {"0", "1/8", "1/4", "1/2"}

# Inclusive integer-CR ranges keyed by Proficiency Bonus.
_CR_BANDS: Final[tuple[tuple[int, int, int], ...]] = (
    (0, 4, 2),
    (5, 8, 3),
    (9, 12, 4),
    (13, 16, 5),
    (17, 20, 6),
    (21, 24, 7),
    (25, 28, 8),
    (29, 30, 9),
)


def _normalize(cr: str | int | float) -> str:
    """Return the canonical CR string for ``cr``.

    Accepts the catalog's fractional strings (``"1/8"``, ``"1/4"``,
    ``"1/2"``), integer-shaped strings, ``int``, and ``float`` (so a
    caller may pass ``0.25`` interchangeably with ``"1/4"``).
    """
    if isinstance(cr, str):
        return cr.strip()
    if isinstance(cr, int):
        return str(cr)
    # float: map the three SRD fractionals; otherwise round to int.
    fractionals = {0.0: "0", 0.125: "1/8", 0.25: "1/4", 0.5: "1/2"}
    if cr in fractionals:
        return fractionals[cr]
    if cr == int(cr):
        return str(int(cr))
    raise ValueError(f"Unrecognized CR value: {cr!r}")


def proficiency_bonus_from_cr(cr: str | int | float) -> int:
    """Return the Proficiency Bonus for a monster with the given CR.

    Args:
        cr: Challenge Rating. May be a catalog string (``"0"``, ``"1/8"``,
            ``"1/4"``, ``"1/2"``, or the integer CRs ``"1"`` through
            ``"30"``), or the equivalent ``int``/``float``.

    Returns:
        The Proficiency Bonus per the SRD CR table.

    Raises:
        ValueError: If ``cr`` is not one of the SRD-defined values
            (e.g., ``"31"``, ``"1/3"``, or arbitrary strings).
    """
    canonical = _normalize(cr)
    if canonical in _FRACTIONAL_CR:
        return 2
    try:
        cr_int = int(canonical)
    except ValueError as exc:
        raise ValueError(f"Unrecognized CR value: {cr!r}") from exc
    for low, high, pb in _CR_BANDS:
        if low <= cr_int <= high:
            return pb
    raise ValueError(f"CR {cr!r} is outside the SRD table (0–30)")
