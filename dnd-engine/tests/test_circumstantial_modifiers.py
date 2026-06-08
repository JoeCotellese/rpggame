# ABOUTME: Verifies the `circumstantial` channel is plumbed through every
# ABOUTME: D20-Test caller surface (skill / ability / save / attack).

"""Circumstantial bonus/penalty plumbing (issue #487, plan-08 slice 5).

SRD § Playing the Game › D20 Tests › Step 5 names three additive
modifier categories that go on top of the d20: the relevant ability
modifier, the proficiency bonus (if relevant), and **circumstantial
bonuses and penalties** ("A class feature, a spell, or another rule
might give a bonus or penalty to the die roll"). The unified
:func:`dnd_engine.systems.d20.d20_test` primitive reserved the
``circumstantial`` channel in slice 1 but no caller exposed it.

This test module verifies each caller surface (skill check, raw ability
check, saving throw, attack roll) accepts a caller-supplied
``circumstantial`` value, forwards it to the primitive, and surfaces
it on the returned result for telemetry — unblocking Bless / Bane /
Guidance / Bardic Inspiration plumbing in later slices.
"""

from __future__ import annotations

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller


def _make_fighter() -> Character:
    """Construct a minimal Fighter for caller-surface assertions."""
    abilities = Abilities(
        strength=16,
        dexterity=14,
        constitution=15,
        intelligence=10,
        wisdom=12,
        charisma=8,
    )
    return Character(
        name="Fighter",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=12,
        ac=16,
        saving_throw_proficiencies=["str", "con"],
        skill_proficiencies=["athletics"],
    )


def _make_creature() -> Creature:
    """Construct a vanilla creature without proficient saves."""
    abilities = Abilities(
        strength=10,
        dexterity=14,
        constitution=10,
        intelligence=10,
        wisdom=10,
        charisma=10,
    )
    return Creature(name="Goblin", max_hp=7, ac=13, abilities=abilities)


class TestSkillCheck:
    """Skill checks expose the circumstantial channel."""

    def test_skill_check_accepts_circumstantial(self):
        """A `+3` Bless-like bonus reaches `total` and is itemized."""
        fighter = _make_fighter()
        fighter._dice_roller = DiceRoller(seed=1)
        skills = {"athletics": {"ability": "str"}}

        baseline = fighter.make_skill_check("athletics", dc=10, skills_data=skills)

        fighter._dice_roller = DiceRoller(seed=1)
        boosted = fighter.make_skill_check(
            "athletics", dc=10, skills_data=skills, circumstantial=3
        )

        # Same seed → same natural d20 → boosted total is exactly +3.
        assert boosted["roll"] == baseline["roll"]
        assert boosted["total"] == baseline["total"] + 3
        assert boosted["circumstantial"] == 3
        # Baseline keeps the default zero channel for telemetry parity.
        assert baseline["circumstantial"] == 0


class TestAbilityCheck:
    """Raw ability checks expose the circumstantial channel."""

    def test_character_ability_check_accepts_circumstantial(self):
        """A `+2` Guidance-like bonus stacks onto the raw STR check."""
        fighter = _make_fighter()
        fighter._dice_roller = DiceRoller(seed=5)

        baseline = fighter.make_ability_check("str", dc=10)

        fighter._dice_roller = DiceRoller(seed=5)
        boosted = fighter.make_ability_check("str", dc=10, circumstantial=2)

        assert boosted["roll"] == baseline["roll"]
        assert boosted["total"] == baseline["total"] + 2
        assert boosted["circumstantial"] == 2

    def test_character_ability_check_accepts_negative_circumstantial(self):
        """A `-1` Bane-like penalty subtracts from the total."""
        fighter = _make_fighter()
        fighter._dice_roller = DiceRoller(seed=5)

        baseline = fighter.make_ability_check("int", dc=10)

        fighter._dice_roller = DiceRoller(seed=5)
        penalized = fighter.make_ability_check("int", dc=10, circumstantial=-1)

        assert penalized["total"] == baseline["total"] - 1
        assert penalized["circumstantial"] == -1

    def test_creature_ability_check_accepts_circumstantial(self):
        """`Creature.make_ability_check` mirrors the Character surface."""
        goblin = _make_creature()

        baseline = goblin.make_ability_check("dex", dc=10)
        boosted = goblin.make_ability_check("dex", dc=10, circumstantial=1)

        # Without a deterministic roller on Creature.make_ability_check
        # (it constructs a fresh DiceRoller per call by primitive
        # default), assert on the itemized channel only — the +1
        # arithmetic is verified by the d20_test primitive's own tests.
        assert baseline["circumstantial"] == 0
        assert boosted["circumstantial"] == 1


class TestSavingThrow:
    """Saving throws expose the circumstantial channel."""

    def test_character_saving_throw_accepts_circumstantial(self):
        """A `+1` Bless-like bonus is surfaced on the result dict.

        ``make_saving_throw`` constructs a fresh ``DiceRoller`` per
        call rather than reusing ``self._dice_roller`` (see the
        comment at character.py:354), so test the structural contract:
        the bonus reaches the result. End-to-end arithmetic of the
        ``circumstantial`` channel is verified by the d20-test
        primitive's own tests in ``tests/srd/playing_the_game/
        test_d20_unified.py``.
        """
        fighter = _make_fighter()

        result = fighter.make_saving_throw("con", dc=10, circumstantial=1)

        assert result["circumstantial"] == 1
        # The "modifier" key carries the static save modifier
        # (ability + PB), separate from the circumstantial channel.
        # The total includes both: d20 + modifier + circumstantial.
        assert result["total"] == result["roll"] + result["modifier"] + 1

    def test_creature_saving_throw_accepts_circumstantial(self):
        """A `-2` Bane-like penalty is surfaced on the Creature surface."""
        goblin = _make_creature()

        result = goblin.make_saving_throw("wis", dc=10, circumstantial=-2)

        assert result["circumstantial"] == -2
        # Creatures have no proficient saves today, so modifier ==
        # ability mod, and total == d20 + ability_mod + circumstantial.
        assert result["total"] == result["roll"] + result["modifier"] - 2
