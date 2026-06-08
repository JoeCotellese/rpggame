# ABOUTME: SRD conformance for the unified D20 Test primitive (plan-08 slice 1).
# ABOUTME: Locks the contract for `dnd_engine.systems.d20.d20_test`.

"""SRD conformance: unified D20 Test primitive.

Companion to ``test_d20_tests.py`` (which audits the three legacy
surfaces — ``Character.make_skill_check``, ``make_saving_throw``, and
``CombatEngine.resolve_attack``). This file pins the single primitive
that those surfaces will delegate to. Each parametrized case maps to a
rule from ``docs/srd/playing-the-game/d20-tests.md``.

The conformance "report" is ``pytest --collect-only -q tests/srd/``.
"""

from __future__ import annotations

import pytest

from dnd_engine.core.dice import DiceRoller
from dnd_engine.systems.d20 import AdvantageState, D20Result, d20_test

pytestmark = pytest.mark.srd(
    "playing-the-game/d20-tests.md",
    lines="731-865",
)


# ---------------------------------------------------------------------------
# Structural contract
# ---------------------------------------------------------------------------


class TestResultShape:
    """The primitive returns a ``D20Result`` with the contracted fields."""

    def test_returns_d20result(self):
        result = d20_test(roller=DiceRoller(seed=1))
        assert isinstance(result, D20Result)

    def test_components_dict_itemizes_all_channels(self):
        """``components`` carries every additive channel by name.

        SRD step 5 names three additive sources: ability modifier,
        proficiency bonus (if relevant), and circumstantial
        bonuses/penalties. Each gets a named key so callers (and
        narration code) can render the breakdown.
        """
        result = d20_test(
            ability_mod=3,
            proficient=True,
            proficiency_bonus=2,
            circumstantial=1,
            roller=DiceRoller(seed=1),
        )
        assert set(result.components.keys()) == {
            "ability_mod",
            "proficiency",
            "circumstantial",
        }


# ---------------------------------------------------------------------------
# SRD step 4 — Roll 1d20 (with optional Advantage/Disadvantage)
# ---------------------------------------------------------------------------


class TestRollD20:
    """SRD § D20 Tests › Step 4."""

    def test_normal_roll_uses_one_d20(self):
        result = d20_test(roller=DiceRoller(seed=1))
        assert result.advantage_state is AdvantageState.NORMAL
        assert len(result.rolls) == 1
        assert 1 <= result.d20 <= 20
        assert result.d20 == result.rolls[0]

    def test_advantage_takes_higher_of_two(self):
        result = d20_test(advantage=True, roller=DiceRoller(seed=1))
        assert result.advantage_state is AdvantageState.ADVANTAGE
        assert len(result.rolls) == 2
        assert result.d20 == max(result.rolls)

    def test_disadvantage_takes_lower_of_two(self):
        result = d20_test(disadvantage=True, roller=DiceRoller(seed=1))
        assert result.advantage_state is AdvantageState.DISADVANTAGE
        assert len(result.rolls) == 2
        assert result.d20 == min(result.rolls)

    def test_advantage_and_disadvantage_cancel(self):
        """SRD: "If circumstances cause a roll to have both advantage and
        disadvantage, you're considered to have neither of them." The
        primitive cancels before delegating to ``DiceRoller.roll`` (which
        raises if both are set)."""
        result = d20_test(
            advantage=True,
            disadvantage=True,
            roller=DiceRoller(seed=1),
        )
        assert result.advantage_state is AdvantageState.NORMAL
        assert len(result.rolls) == 1


# ---------------------------------------------------------------------------
# SRD step 5 — Add modifiers (ability + proficiency-if-relevant + circumstantial)
# ---------------------------------------------------------------------------


class TestAddModifiers:
    """SRD § D20 Tests › Step 5."""

    def test_ability_modifier_added_to_total(self):
        result = d20_test(ability_mod=4, roller=DiceRoller(seed=1))
        assert result.components["ability_mod"] == 4
        assert result.total == result.d20 + 4

    def test_proficiency_bonus_added_when_proficient(self):
        result = d20_test(
            proficient=True,
            proficiency_bonus=2,
            roller=DiceRoller(seed=1),
        )
        assert result.components["proficiency"] == 2
        assert result.total == result.d20 + 2

    def test_proficiency_bonus_skipped_when_not_proficient(self):
        """SRD step 5: PB applies "If Relevant" — i.e. only when proficient."""
        result = d20_test(
            proficient=False,
            proficiency_bonus=2,
            roller=DiceRoller(seed=1),
        )
        assert result.components["proficiency"] == 0
        assert result.total == result.d20

    def test_expertise_doubles_pb_when_proficient(self):
        """SRD § Skills › Expertise: a character with Expertise doubles
        their PB on a check using that skill."""
        result = d20_test(
            proficient=True,
            proficiency_bonus=3,
            expertise=True,
            roller=DiceRoller(seed=1),
        )
        assert result.components["proficiency"] == 6
        assert result.total == result.d20 + 6

    def test_expertise_without_proficiency_is_a_noop(self):
        """Defense: Expertise has no rules effect on a character who is
        not proficient. The flag should be ignored, not silently
        promoted to "double zero plus PB"."""
        result = d20_test(
            proficient=False,
            proficiency_bonus=3,
            expertise=True,
            roller=DiceRoller(seed=1),
        )
        assert result.components["proficiency"] == 0
        assert result.total == result.d20

    def test_circumstantial_modifier_added(self):
        """SRD step 5: "Circumstantial Bonuses and Penalties" — the third
        additive channel. Caller passes a signed int; the primitive
        sums it into the total."""
        result = d20_test(circumstantial=-1, roller=DiceRoller(seed=1))
        assert result.components["circumstantial"] == -1
        assert result.total == result.d20 - 1

    def test_all_channels_sum_into_total(self):
        result = d20_test(
            ability_mod=2,
            proficient=True,
            proficiency_bonus=2,
            expertise=True,
            circumstantial=1,
            roller=DiceRoller(seed=1),
        )
        assert result.total == result.d20 + 2 + 4 + 1


# ---------------------------------------------------------------------------
# SRD step 6 — Compare total to a target number
# ---------------------------------------------------------------------------


class TestTargetNumber:
    """SRD § D20 Tests › Step 6."""

    def test_succeeds_against_uses_total_geq_dc(self):
        """Same inequality for ability checks (DC), saving throws (DC),
        and attack rolls (AC). The helper takes the target number and
        returns ``total >= target``."""
        result = d20_test(ability_mod=5, roller=DiceRoller(seed=42))
        assert result.succeeds_against(result.total) is True
        assert result.succeeds_against(result.total - 1) is True
        assert result.succeeds_against(result.total + 1) is False


# ---------------------------------------------------------------------------
# Determinism — caller-supplied roller is honored verbatim
# ---------------------------------------------------------------------------


class TestRollerInjection:
    """The primitive does not bypass a caller's seeded roller."""

    def test_uses_caller_supplied_roller_for_normal_roll(self):
        roller = DiceRoller(seed=12345)
        expected = roller.roll("1d20").rolls[0]
        # Re-seed and run through the primitive — should produce the
        # same first die outcome.
        result = d20_test(roller=DiceRoller(seed=12345))
        assert result.d20 == expected

    def test_uses_caller_supplied_roller_for_advantage(self):
        roller = DiceRoller(seed=12345)
        expected_rolls = roller.roll("1d20", advantage=True).rolls
        result = d20_test(advantage=True, roller=DiceRoller(seed=12345))
        assert tuple(expected_rolls) == result.rolls

    def test_consumes_exactly_one_roller_call(self):
        """Determinism guarantee for the migration: the primitive makes
        a single ``roller.roll("1d20", ...)`` call so existing
        sequence-sensitive tests don't drift after callsites migrate."""

        class CountingRoller:
            def __init__(self, inner: DiceRoller) -> None:
                self.inner = inner
                self.calls = 0

            def roll(self, *args, **kwargs):
                self.calls += 1
                return self.inner.roll(*args, **kwargs)

        counter = CountingRoller(DiceRoller(seed=1))
        d20_test(advantage=True, roller=counter)
        assert counter.calls == 1
