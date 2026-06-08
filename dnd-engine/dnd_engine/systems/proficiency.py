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


class ProficiencyApplication:
    """One PB application per D20 Test (SRD "The Bonus Doesn't Stack").

    Encapsulates the per-check guard: a creature's Proficiency Bonus
    may be added to a roll at most once, and any multiplier on it
    (e.g., Expertise) may be applied at most once
    (``docs/srd/playing-the-game/proficiency.md`` § "The Bonus Doesn't
    Stack").

    Construct a fresh instance for every calculation. Each ``add()``
    after the first short-circuits to ``0`` so the additive slot is
    consumed; a second multiplier attempt raises ``ValueError`` so the
    invariant is loud rather than silent.
    """

    def __init__(self, proficiency_bonus: int) -> None:
        self._pb = proficiency_bonus
        self._added = False
        self._multiplied = False

    @property
    def added(self) -> bool:
        """True iff PB has been added (with any multiplier) to a roll."""
        return self._added

    @property
    def multiplied(self) -> bool:
        """True iff a non-identity multiplier has been applied to PB."""
        return self._multiplied

    def add(self, *, multiplier: int = 1) -> int:
        """Return the PB to add to a roll, applying SRD stacking rules.

        Args:
            multiplier: Scalar applied to PB before returning. Pass
                ``2`` for Expertise (and similar doubling features);
                the default ``1`` is the plain additive case.

        Returns:
            ``proficiency_bonus * multiplier`` on the first call; ``0``
            on any subsequent additive call (the additive slot is
            already consumed).

        Raises:
            ValueError: If a second non-identity multiplier is applied
                after one is already in effect. SRD: "Whenever the
                bonus is used, it can be multiplied only once and
                divided only once." Raising — rather than silently
                short-circuiting — surfaces a buggy callsite during
                development.
        """
        if multiplier != 1 and self._multiplied:
            raise ValueError(
                "Proficiency Bonus already multiplied this calculation (SRD: multiplied only once)."
            )
        if self._added:
            return 0
        if multiplier != 1:
            self._multiplied = True
        self._added = True
        return self._pb * multiplier
