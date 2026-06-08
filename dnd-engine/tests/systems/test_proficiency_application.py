# ABOUTME: Unit tests for ProficiencyApplication, the per-check PB guard.
# ABOUTME: SRD § Proficiency — "The Bonus Doesn't Stack" + multiplier-once invariant.

"""Unit tests for ``dnd_engine.systems.proficiency.ProficiencyApplication``.

The helper encapsulates a single D20 Test's Proficiency Bonus
application. It enforces the SRD invariant that PB is added at most
once and multiplied at most once per check (see
``docs/srd/playing-the-game/proficiency.md`` § "The Bonus Doesn't Stack").
"""

from __future__ import annotations

import pytest

from dnd_engine.systems.proficiency import ProficiencyApplication


class TestProficiencyApplication_InitialState:
    """A fresh application has neither added nor multiplied PB."""

    def test_starts_unadded(self) -> None:
        app = ProficiencyApplication(proficiency_bonus=3)
        assert app.added is False
        assert app.multiplied is False


class TestProficiencyApplication_Add:
    """``add()`` applies PB once, then short-circuits to 0."""

    def test_first_additive_call_returns_pb(self) -> None:
        app = ProficiencyApplication(proficiency_bonus=3)
        assert app.add() == 3
        assert app.added is True
        assert app.multiplied is False

    def test_second_additive_call_returns_zero(self) -> None:
        """SRD: 'Your Proficiency Bonus can't be added to a die roll or
        another number more than once.'"""
        app = ProficiencyApplication(proficiency_bonus=3)
        app.add()
        assert app.add() == 0

    def test_add_with_zero_pb_returns_zero(self) -> None:
        """An unproficient creature passes PB=0; the helper still marks
        the slot as consumed so later attempts are no-ops."""
        app = ProficiencyApplication(proficiency_bonus=0)
        assert app.add() == 0
        assert app.added is True


class TestProficiencyApplication_Multiplier:
    """A multiplier (e.g., Expertise) may be applied at most once."""

    def test_first_multiplier_call_returns_multiplied_pb(self) -> None:
        app = ProficiencyApplication(proficiency_bonus=3)
        assert app.add(multiplier=2) == 6
        assert app.added is True
        assert app.multiplied is True

    def test_second_multiplier_call_raises(self) -> None:
        """SRD: 'Whenever the bonus is used, it can be multiplied only
        once and divided only once.'"""
        app = ProficiencyApplication(proficiency_bonus=3)
        app.add(multiplier=2)
        with pytest.raises(ValueError, match="multiplied"):
            app.add(multiplier=2)

    def test_additive_then_multiplier_short_circuits(self) -> None:
        """Once PB has been added, a follow-up multiplier attempt is a
        no-op (returns 0) — the slot is already consumed and the
        multiplier guard is untouched."""
        app = ProficiencyApplication(proficiency_bonus=3)
        app.add()
        assert app.add(multiplier=2) == 0
        assert app.multiplied is False

    def test_multiplier_then_additive_short_circuits(self) -> None:
        """A bare ``add()`` after a multiplier returns 0 (already
        consumed) without raising."""
        app = ProficiencyApplication(proficiency_bonus=3)
        app.add(multiplier=2)
        assert app.add() == 0

    def test_multiplier_of_one_does_not_set_multiplied_flag(self) -> None:
        """``multiplier=1`` is the default and is semantically additive;
        it must not consume the multiplier slot."""
        app = ProficiencyApplication(proficiency_bonus=3)
        app.add(multiplier=1)
        assert app.multiplied is False
