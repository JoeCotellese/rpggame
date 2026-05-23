# ABOUTME: Rule helpers for ranged attacks (SRD § Playing the Game > Ranged Attacks).
# ABOUTME: Currently implements the close-combat disadvantage rule.

"""Ranged attack rule helpers.

The engine does not track positions; clients (graphical and scripted) do.
This module exposes pure rule helpers that take positional data as input
so multiple clients can share a single source of truth for ranged-attack
rules without duplicating logic.

See also:
    docs/srd/playing-the-game/ranged-attacks.md
    dnd_engine.core.distance — spatial primitives this module builds on
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from dnd_engine.core.creature import Creature
from dnd_engine.core.distance import is_adjacent


def is_close_combat_ranged_disadvantage(
    attacker_pos: tuple[int, int],
    enemies: Iterable[tuple[tuple[int, int], Creature]],
    *,
    attacker_visible_to: Callable[[Creature], bool] = lambda _enemy: True,
) -> bool:
    """Return True if a ranged attack has Disadvantage from close combat.

    Per SRD § Playing the Game > Ranged Attacks in Close Combat:

        When you make a ranged attack roll with a weapon, a spell, or some
        other means, you have Disadvantage on the roll if you are within 5
        feet of an enemy who can see you and doesn't have the Incapacitated
        condition.

    An enemy threatens the attacker for this rule when ALL of the following
    are true:

      - The enemy is alive.
      - The enemy is within 5 ft (Chebyshev distance ≤ 1 square).
      - The enemy is not Incapacitated (see ``Creature.is_incapacitated``).
      - The enemy is not Blinded.
      - The visibility callback reports the enemy can see the attacker
        (covers invisibility, total cover, etc. — defaults to True).

    Args:
        attacker_pos: Attacker's (x, y) grid coordinates.
        enemies: Iterable of ``((x, y), creature)`` pairs for any enemies
            the caller wants considered. Callers should pre-filter to
            hostile creatures only; the helper does not know friend-vs-foe.
        attacker_visible_to: Optional callable taking an enemy creature and
            returning True if that enemy can see the attacker. Defaults to
            always True, matching the SRD baseline; clients with fog-of-war
            or invisibility tracking can pass a real query.

    Returns:
        True if at least one enemy meets all threatening criteria, meaning
        the ranged attack roll should be made with disadvantage.
    """
    ax, ay = attacker_pos
    for (ex, ey), enemy in enemies:
        if not enemy.is_alive:
            continue
        if not is_adjacent(ax, ay, ex, ey):
            continue
        if enemy.is_incapacitated():
            continue
        if enemy.has_condition("blinded"):
            continue
        if not attacker_visible_to(enemy):
            continue
        return True
    return False
