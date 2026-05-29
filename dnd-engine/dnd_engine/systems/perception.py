# ABOUTME: Engine-side visibility & special-senses model for D&D 5E (plan-05).
# ABOUTME: Computes the VisibilityRelation between an observer and a target.

"""First-class visibility / sense layer for the engine.

Vision and obscurement used to live only in the ``client-2d`` rendering
layer; the engine had no model of who can perceive whom. This module
provides that model so rules — attack advantage/disadvantage, sight-based
checks, the Hide gate — can consult a single source of truth.

The core primitive is :func:`compute_visibility`, which answers, for an
``(observer, target)`` pair under a given lighting / obscurement
condition, whether the target is ``Seen``, ``UnseenButSensed`` (located
by a non-visual sense such as tremorsense, but still unseen for the
unseen-attacker/target rules), or ``Unseen``.

SRD references:
- Playing the Game › Vision and Light › Obscured Areas.
- Rules glossary: Blindsight, Darkvision, Tremorsense, Truesight; the
  Blinded and Invisible conditions.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dnd_engine.core.creature import Creature


class LightLevel(str, Enum):
    """Ambient illumination at a location (SRD § Vision and Light)."""

    BRIGHT = "bright"
    DIM = "dim"
    DARK = "dark"


class Obscurement(str, Enum):
    """How obscured an area is for sight-based perception.

    SRD: a Lightly Obscured area (Dim Light, patchy fog, moderate
    foliage) imposes Disadvantage on sight-based Wisdom (Perception)
    checks; a Heavily Obscured area (Darkness, heavy fog, dense foliage)
    is opaque — a creature trying to see into it has the Blinded
    condition with respect to that area.
    """

    CLEAR = "clear"
    LIGHTLY = "lightly"
    HEAVILY = "heavily"


class Sense(str, Enum):
    """Perception channels a creature can possess.

    ``SIGHT`` is the default channel every creature has unless Blinded;
    the others are special senses carried (with a range in feet) in
    ``Creature.senses``.
    """

    SIGHT = "sight"
    DARKVISION = "darkvision"
    BLINDSIGHT = "blindsight"
    TREMORSENSE = "tremorsense"
    TRUESIGHT = "truesight"


class VisibilityRelation(str, Enum):
    """How an observer perceives a target.

    - ``SEEN`` — perceived by a channel that counts as seeing (normal
      sight, darkvision within range, blindsight, truesight). The
      unseen-attacker / unseen-target rules do not apply.
    - ``UNSEEN_BUT_SENSED`` — located by a non-visual sense (tremorsense)
      but still unseen: the observer knows the square but attacks are
      still made as against an unseen target.
    - ``UNSEEN`` — not perceived at all.
    """

    SEEN = "seen"
    UNSEEN_BUT_SENSED = "unseen_but_sensed"
    UNSEEN = "unseen"


# Sources of light/darkness map onto obscurement (SRD § Obscured Areas):
# Dim Light *is* a Lightly Obscured area; Darkness *is* a Heavily
# Obscured area. Bright Light contributes no obscurement of its own.
_LIGHT_OBSCUREMENT: dict[LightLevel, Obscurement] = {
    LightLevel.BRIGHT: Obscurement.CLEAR,
    LightLevel.DIM: Obscurement.LIGHTLY,
    LightLevel.DARK: Obscurement.HEAVILY,
}

# Severity ordering so we can take the "worst" of two obscurement sources.
_OBSCUREMENT_SEVERITY: dict[Obscurement, int] = {
    Obscurement.CLEAR: 0,
    Obscurement.LIGHTLY: 1,
    Obscurement.HEAVILY: 2,
}


def observer_senses(creature: Creature) -> dict[Sense, int]:
    """Resolve a creature's special senses to a ``{Sense: range_ft}`` map.

    Reconciles the canonical ``creature.senses`` dict (whose keys may be
    :class:`Sense` members or their string values) with the legacy
    ``creature.darkvision_range`` attribute that pre-dates this model.
    When both name a range for the same sense, the wider range wins.
    """
    resolved: dict[Sense, int] = {}

    raw = getattr(creature, "senses", None) or {}
    for key, range_ft in raw.items():
        sense = key if isinstance(key, Sense) else Sense(str(key).lower())
        resolved[sense] = max(resolved.get(sense, 0), int(range_ft))

    legacy_darkvision = int(getattr(creature, "darkvision_range", 0) or 0)
    if legacy_darkvision:
        resolved[Sense.DARKVISION] = max(resolved.get(Sense.DARKVISION, 0), legacy_darkvision)

    return resolved


# Matches a special sense and its foot range in an SRD stat-block
# `senses` string, e.g. "blindsight 60 ft. (blind beyond this radius)".
# Passive Perception and parenthetical qualifiers are not captured.
_SENSE_RANGE_RE = re.compile(
    r"\b(darkvision|blindsight|tremorsense|truesight)\b\s+(\d+)\s*ft",
    re.IGNORECASE,
)


def parse_senses(senses_text: str | None) -> dict[Sense, int]:
    """Parse an SRD stat-block ``senses`` string into ``{Sense: range_ft}``.

    Recognizes the four ranged special senses (Darkvision, Blindsight,
    Tremorsense, Truesight). Passive Perception and parenthetical
    qualifiers such as "(blind beyond this radius)" are ignored, and
    ordinary sight is implicit so it is never stored. When the same
    sense appears more than once, the wider range wins.

    Args:
        senses_text: The catalog ``senses`` value (may be ``None`` or
            empty for a creature with only ordinary sight).

    Returns:
        A ``{Sense: range_ft}`` map suitable for ``Creature.senses``.
    """
    resolved: dict[Sense, int] = {}
    if not senses_text:
        return resolved
    for keyword, range_ft in _SENSE_RANGE_RE.findall(senses_text):
        sense = Sense(keyword.lower())
        resolved[sense] = max(resolved.get(sense, 0), int(range_ft))
    return resolved


def effective_obscurement(
    light_level: LightLevel,
    ambient: Obscurement = Obscurement.CLEAR,
) -> Obscurement:
    """Combine lighting-derived obscurement with an ambient source.

    The result is the more severe of the obscurement implied by the
    light level (Dim → Lightly, Darkness → Heavily) and any ambient
    obscurement already present (fog, foliage). Obscurement never
    improves: two sources stack to the worse of the two.
    """
    from_light = _LIGHT_OBSCUREMENT[light_level]
    if _OBSCUREMENT_SEVERITY[ambient] >= _OBSCUREMENT_SEVERITY[from_light]:
        return ambient
    return from_light


def compute_visibility(
    observer: Creature,
    target: Creature,
    *,
    light_level: LightLevel = LightLevel.BRIGHT,
    obscurement: Obscurement = Obscurement.CLEAR,
    distance: float = 0.0,
    has_line_of_sight: bool = True,
    target_on_ground: bool = True,
) -> VisibilityRelation:
    """Compute how ``observer`` perceives ``target``.

    Args:
        observer: The perceiving creature; its senses (sight, darkvision,
            blindsight, tremorsense, truesight) and the Blinded condition
            drive the result.
        target: The creature being perceived; the Invisible and Hidden
            conditions hide it from sight.
        light_level: Ambient illumination at the target.
        obscurement: Ambient obscurement at the target (fog, foliage).
            This is *additional* to lighting; the effective obscurement
            for sight is the worse of this and the lighting-derived one.
        distance: Distance between observer and target, in feet.
        has_line_of_sight: Whether an unobstructed path exists. Total
            cover (a wall) blocks every channel modeled here, including
            blindsight and truesight.
        target_on_ground: Whether the target is in contact with a surface
            tremorsense can travel through. Flying / incorporeal targets
            are invisible to tremorsense.

    Returns:
        The :class:`VisibilityRelation` from observer to target.
    """
    if not has_line_of_sight:
        # Total cover defeats every channel modeled here.
        return VisibilityRelation.UNSEEN

    senses = observer_senses(observer)
    blinded = observer.has_condition("blinded")
    target_invisible = target.has_condition("invisible")
    target_hidden = target.has_condition("hidden")

    # Truesight sees in darkness (normal and magical), pierces invisibility,
    # and ignores obscurement, out to its range.
    truesight = senses.get(Sense.TRUESIGHT, 0)
    if truesight and distance <= truesight:
        return VisibilityRelation.SEEN

    # Blindsight perceives without relying on sight; light, invisibility,
    # and obscurement do not impede it within range.
    blindsight = senses.get(Sense.BLINDSIGHT, 0)
    if blindsight and distance <= blindsight:
        return VisibilityRelation.SEEN

    # Normal sight (optionally aided by darkvision). Sight fails if the
    # observer is Blinded, the target is Invisible or Hidden, or the area
    # is Heavily Obscured. Darkness is Heavily Obscured to ordinary sight;
    # darkvision downgrades it to Dim (still Seen) within range.
    sight_obscurement = effective_obscurement(light_level, obscurement)
    darkvision = senses.get(Sense.DARKVISION, 0)
    darkvision_reaches = bool(darkvision) and distance <= darkvision
    if light_level == LightLevel.DARK and darkvision_reaches:
        # Darkvision turns darkness into dim light for this observer.
        sight_obscurement = effective_obscurement(LightLevel.DIM, obscurement)

    if (
        not blinded
        and not target_invisible
        and not target_hidden
        and sight_obscurement != Obscurement.HEAVILY
    ):
        return VisibilityRelation.SEEN

    # Tremorsense locates a target through a shared surface, but does not
    # let the observer see it — the target remains unseen for attack
    # advantage/disadvantage purposes.
    tremorsense = senses.get(Sense.TREMORSENSE, 0)
    if tremorsense and target_on_ground and distance <= tremorsense:
        return VisibilityRelation.UNSEEN_BUT_SENSED

    return VisibilityRelation.UNSEEN
