# ABOUTME: Unit tests for the close-combat ranged attack disadvantage helper.
# ABOUTME: Exercises dnd_engine.systems.ranged_attacks.is_close_combat_ranged_disadvantage.

"""Unit tests for the close-combat ranged disadvantage rule helper.

Per SRD § Playing the Game › Ranged Attacks in Close Combat:

> When you make a ranged attack roll with a weapon, a spell, or some other
> means, you have Disadvantage on the roll if you are within 5 feet of an
> enemy who can see you and doesn't have the Incapacitated condition.

The helper takes the attacker's position, an iterable of (position, creature)
pairs for potentially threatening enemies, and an optional visibility
callback for the "enemy can see attacker" check. It returns True when
disadvantage should apply.
"""

from __future__ import annotations

import pytest

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.systems.ranged_attacks import is_close_combat_ranged_disadvantage


@pytest.fixture
def goblin_abilities() -> Abilities:
    return Abilities(
        strength=8,
        dexterity=14,
        constitution=10,
        intelligence=10,
        wisdom=8,
        charisma=8,
    )


def _make_goblin(name: str, abilities: Abilities) -> Creature:
    return Creature(name=name, max_hp=7, ac=15, abilities=abilities)


class TestAdjacency:
    """Distance checks: enemy must be within 5 ft (Chebyshev <= 1 square)."""

    def test_no_enemies_returns_false(self, goblin_abilities):
        assert is_close_combat_ranged_disadvantage((5, 5), []) is False

    def test_orthogonally_adjacent_enemy_triggers_disadvantage(self, goblin_abilities):
        goblin = _make_goblin("Goblin", goblin_abilities)
        enemies = [((6, 5), goblin)]  # 1 square east
        assert is_close_combat_ranged_disadvantage((5, 5), enemies) is True

    def test_diagonally_adjacent_enemy_triggers_disadvantage(self, goblin_abilities):
        goblin = _make_goblin("Goblin", goblin_abilities)
        enemies = [((6, 6), goblin)]  # 1 square NE
        assert is_close_combat_ranged_disadvantage((5, 5), enemies) is True

    def test_two_squares_away_does_not_trigger(self, goblin_abilities):
        goblin = _make_goblin("Goblin", goblin_abilities)
        enemies = [((7, 5), goblin)]  # 10 ft away
        assert is_close_combat_ranged_disadvantage((5, 5), enemies) is False

    def test_mixed_enemies_returns_true_if_any_adjacent(self, goblin_abilities):
        adjacent = _make_goblin("Adjacent", goblin_abilities)
        distant = _make_goblin("Distant", goblin_abilities)
        enemies = [((20, 20), distant), ((5, 6), adjacent)]
        assert is_close_combat_ranged_disadvantage((5, 5), enemies) is True


class TestLivingFilter:
    """Dead enemies don't impose disadvantage."""

    def test_dead_adjacent_enemy_does_not_trigger(self, goblin_abilities):
        goblin = _make_goblin("Goblin", goblin_abilities)
        goblin.take_damage(99)  # Drop to 0 HP
        assert goblin.is_alive is False
        enemies = [((6, 5), goblin)]
        assert is_close_combat_ranged_disadvantage((5, 5), enemies) is False


class TestIncapacitatedException:
    """SRD carve-out: no disadvantage if the adjacent enemy is Incapacitated."""

    @pytest.mark.parametrize(
        "condition",
        ["incapacitated", "paralyzed", "stunned", "unconscious", "petrified"],
    )
    def test_incapacitated_enemy_does_not_trigger(self, goblin_abilities, condition):
        goblin = _make_goblin("Goblin", goblin_abilities)
        goblin.add_condition(condition)
        enemies = [((6, 5), goblin)]
        assert is_close_combat_ranged_disadvantage((5, 5), enemies) is False


class TestVisibilityException:
    """SRD carve-out: no disadvantage if the enemy cannot see the attacker."""

    def test_blinded_enemy_does_not_trigger(self, goblin_abilities):
        goblin = _make_goblin("Goblin", goblin_abilities)
        goblin.add_condition("blinded")
        enemies = [((6, 5), goblin)]
        assert is_close_combat_ranged_disadvantage((5, 5), enemies) is False

    def test_visibility_callback_returning_false_does_not_trigger(self, goblin_abilities):
        """E.g. attacker is invisible — caller passes a callback that
        returns False for enemies that cannot see the attacker."""
        goblin = _make_goblin("Goblin", goblin_abilities)
        enemies = [((6, 5), goblin)]
        assert (
            is_close_combat_ranged_disadvantage(
                (5, 5),
                enemies,
                attacker_visible_to=lambda _enemy: False,
            )
            is False
        )

    def test_default_visibility_is_true(self, goblin_abilities):
        """Default callback returns True (most enemies can see)."""
        goblin = _make_goblin("Goblin", goblin_abilities)
        enemies = [((6, 5), goblin)]
        assert is_close_combat_ranged_disadvantage((5, 5), enemies) is True


class TestPartialExceptions:
    """If one adjacent enemy is exempt but another threatens, disadvantage applies."""

    def test_one_incapacitated_one_not_still_triggers(self, goblin_abilities):
        incapacitated = _make_goblin("Sleeper", goblin_abilities)
        incapacitated.add_condition("unconscious")
        alert = _make_goblin("Alert", goblin_abilities)
        enemies = [((6, 5), incapacitated), ((5, 6), alert)]
        assert is_close_combat_ranged_disadvantage((5, 5), enemies) is True
