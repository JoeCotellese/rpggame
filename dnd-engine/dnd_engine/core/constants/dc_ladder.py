# ABOUTME: SRD-canonical Typical Difficulty Class ladder for D20 Tests.
# ABOUTME: Defines DC.VERY_EASY..DC.NEARLY_IMPOSSIBLE as IntEnum members.

"""Typical Difficulty Class ladder.

Source: SRD § Playing the Game › D20 Tests › Typical Difficulty Classes
(docs/srd/playing-the-game/d20-tests.md lines 731-865).

| Difficulty        | DC |
|-------------------|----|
| Very easy         |  5 |
| Easy              | 10 |
| Medium            | 15 |
| Hard              | 20 |
| Very hard         | 25 |
| Nearly impossible | 30 |

Exposed as an ``IntEnum`` so members behave as integers in numeric
comparisons (``total >= DC.MEDIUM``) and can be passed directly to call
sites that accept an ``int`` DC (``make_skill_check(skill, dc=DC.HARD)``,
``make_saving_throw(ability, dc=DC.EASY)``).
"""

from __future__ import annotations

from enum import IntEnum


class DC(IntEnum):
    """SRD Typical Difficulty Class ladder."""

    VERY_EASY = 5
    EASY = 10
    MEDIUM = 15
    HARD = 20
    VERY_HARD = 25
    NEARLY_IMPOSSIBLE = 30


__all__ = ["DC"]
