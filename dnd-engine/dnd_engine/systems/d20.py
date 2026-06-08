# ABOUTME: SRD § Playing the Game › D20 Tests — unified primitive backing
# ABOUTME: ability checks, saving throws, and attack rolls.

"""Unified D20 Test primitive.

The 2024 SRD treats ability checks, saving throws, and attack rolls as
three flavors of the same mechanic — a "D20 Test". Each follows the
same six-step procedure: declare the test, identify the relevant
ability, decide proficiency, decide Advantage/Disadvantage, roll the
d20 (with the higher/lower-of-two rule), add modifiers, and compare to
a target number.

This module implements that single procedure. Callers (skill checks,
saving throws, attack rolls, and future surfaces like Heroic
Inspiration rerolls or voluntary save failure) delegate the d20-roll +
modifier-sum portion here and keep their own SRD-specific orchestration
(reach gates, sneak attack, Dodge clauses, etc.) on the outside.

Slice 1 of plan-08 introduces the primitive and migrates the three
legacy surfaces to delegate. Later slices add rule guards on top —
PB-from-CR, PB-once stacking, tool+skill advantage, circumstantial
plumbing, voluntary fail, Heroic Inspiration — without further widening
the primitive's signature.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from dnd_engine.core.dice import DiceRoller


class AdvantageState(str, Enum):
    """Resolved Advantage/Disadvantage state after SRD cancellation."""

    NORMAL = "normal"
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"


@dataclass(frozen=True)
class D20Result:
    """Result of a single D20 Test.

    Attributes:
        d20: The single die outcome actually consumed by the test —
            ``max(rolls)`` under Advantage, ``min(rolls)`` under
            Disadvantage, the sole roll otherwise. This is the natural
            d20 value that determines critical hits / fumbles at the
            callsite.
        total: ``d20`` plus every additive channel in ``components``.
            Compared directly to the target number (DC or AC) via
            :meth:`succeeds_against`.
        advantage_state: Resolved state after SRD's cancellation rule
            (both Advantage and Disadvantage → neither).
        components: Itemized additive channels for narration and
            debugging. Always contains the keys ``ability_mod``,
            ``proficiency``, and ``circumstantial``. Each value is a
            signed int; the sum equals ``total - d20``.
        rolls: Raw die outcomes — one die normally, two under
            Advantage or Disadvantage.
    """

    d20: int
    total: int
    advantage_state: AdvantageState
    components: dict[str, int]
    rolls: tuple[int, ...]

    def succeeds_against(self, target: int) -> bool:
        """Return whether the total meets or beats the target number.

        SRD step 6: "If the total of the d20 and its modifiers equals
        or exceeds the target number, the D20 Test succeeds." The
        target is a DC for ability checks and saving throws, an AC
        for attack rolls.
        """
        return self.total >= target


def d20_test(
    *,
    ability_mod: int = 0,
    proficient: bool = False,
    proficiency_bonus: int = 0,
    expertise: bool = False,
    advantage: bool = False,
    disadvantage: bool = False,
    circumstantial: int = 0,
    roller: DiceRoller | None = None,
) -> D20Result:
    """Roll a single D20 Test per SRD § Playing the Game › D20 Tests.

    Args:
        ability_mod: Modifier from the test's relevant ability score.
        proficient: True iff the character is proficient with the
            relevant skill / save / weapon. Gates the proficiency
            bonus.
        proficiency_bonus: The character's Proficiency Bonus. Added
            only when ``proficient`` is true; doubled when ``expertise``
            is also true.
        expertise: True iff the character has Expertise in the
            relevant skill / tool. Has no effect when ``proficient``
            is false.
        advantage: Roll 2d20 and take the higher value.
        disadvantage: Roll 2d20 and take the lower value.
        circumstantial: Signed circumstantial bonus/penalty (Bless,
            Bane, Guidance, cover, environment, etc.). Slice 1 plumbs
            the channel; later slices wire callsite sources.
        roller: Optional ``DiceRoller`` for determinism. Defaults to a
            fresh, unseeded ``DiceRoller``.

    Returns:
        :class:`D20Result` carrying the resolved d20 outcome, modifier
        breakdown, total, and advantage state.
    """
    # SRD: "If circumstances cause a roll to have both advantage and
    # disadvantage, you're considered to have neither of them." Cancel
    # before delegating to ``DiceRoller.roll``, which raises on both.
    if advantage and disadvantage:
        advantage = False
        disadvantage = False

    roller = roller or DiceRoller()
    roll_result = roller.roll(
        "1d20",
        advantage=advantage,
        disadvantage=disadvantage,
    )

    if advantage:
        d20 = max(roll_result.rolls)
        state = AdvantageState.ADVANTAGE
    elif disadvantage:
        d20 = min(roll_result.rolls)
        state = AdvantageState.DISADVANTAGE
    else:
        d20 = roll_result.rolls[0]
        state = AdvantageState.NORMAL

    if proficient:
        proficiency = proficiency_bonus * 2 if expertise else proficiency_bonus
    else:
        proficiency = 0

    components: dict[str, int] = {
        "ability_mod": ability_mod,
        "proficiency": proficiency,
        "circumstantial": circumstantial,
    }
    total = d20 + sum(components.values())

    return D20Result(
        d20=d20,
        total=total,
        advantage_state=state,
        components=components,
        rolls=tuple(roll_result.rolls),
    )
