# ABOUTME: SRD conformance audit for "Playing the Game > Ability Checks".
# ABOUTME: Cross-references docs/srd/playing-the-game/ability-checks.md against engine code.

"""SRD conformance: Ability Checks.

Maps every rule in `docs/srd/playing-the-game/ability-checks.md` to a
test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import inspect

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller

pytestmark = pytest.mark.srd(
    "playing-the-game/ability-checks.md",
    lines="656-730",
)


def _make_fighter(level: int = 1) -> Character:
    """Construct a minimal Fighter for ability-check assertions."""
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
        level=level,
        abilities=abilities,
        max_hp=12,
        ac=16,
        saving_throw_proficiencies=["str", "con"],
        skill_proficiencies=["athletics"],
        expertise_skills=[],
    )


class TestAbilityModifierTable:
    """SRD § Playing the Game › Ability Checks › Ability Modifier table.

    The SRD's Ability Modifiers table pairs each ability score with its
    modifier. The whole-table contract is `(score - 10) // 2`, but with
    the SRD bounds documented at 1 → -5 and 30 → +10 and the table
    rounding pairs (e.g., scores 14-15 both → +2). The engine encodes
    this as integer floor-divide-by-2 on `Abilities`
    (dnd-engine/dnd_engine/core/creature.py:26-54).
    """

    def test_score_1_yields_minus_5(self):
        """Score 1 → -5 modifier (SRD lower bound).

        `Abilities.str_mod` returns `(1 - 10) // 2 = -5`
        (dnd-engine/dnd_engine/core/creature.py:26-29).
        """
        abilities = Abilities(
            strength=1,
            dexterity=10,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
        )
        assert abilities.str_mod == -5

    def test_score_10_to_11_yields_zero(self):
        """Scores 10 and 11 both → +0.

        Floor-divide of (0 or 1) by 2 → 0
        (dnd-engine/dnd_engine/core/creature.py:36-39).
        """
        a10 = Abilities(
            strength=10, dexterity=10, constitution=10,
            intelligence=10, wisdom=10, charisma=10,
        )
        a11 = Abilities(
            strength=11, dexterity=11, constitution=11,
            intelligence=11, wisdom=11, charisma=11,
        )
        assert a10.con_mod == 0
        assert a11.con_mod == 0

    def test_score_14_to_15_yields_plus_2(self):
        """Scores 14 and 15 both → +2 (SRD pair)."""
        a14 = Abilities(
            strength=14, dexterity=14, constitution=14,
            intelligence=14, wisdom=14, charisma=14,
        )
        a15 = Abilities(
            strength=15, dexterity=15, constitution=15,
            intelligence=15, wisdom=15, charisma=15,
        )
        assert a14.dex_mod == 2
        assert a15.dex_mod == 2

    def test_score_20_to_21_yields_plus_5(self):
        """Scores 20 and 21 both → +5 (PC cap pair)."""
        a20 = Abilities(
            strength=20, dexterity=20, constitution=20,
            intelligence=20, wisdom=20, charisma=20,
        )
        a21 = Abilities(
            strength=21, dexterity=21, constitution=21,
            intelligence=21, wisdom=21, charisma=21,
        )
        assert a20.str_mod == 5
        assert a21.str_mod == 5

    def test_score_30_yields_plus_10(self):
        """Score 30 → +10 (SRD upper bound).

        `(30 - 10) // 2 == 10`
        (dnd-engine/dnd_engine/core/creature.py:36-39).
        """
        abilities = Abilities(
            strength=30, dexterity=10, constitution=10,
            intelligence=10, wisdom=10, charisma=10,
        )
        assert abilities.str_mod == 10

    def test_all_six_abilities_have_modifier_properties(self):
        """`Abilities` exposes one `_mod` property per SRD ability.

        SRD names the six abilities (STR / DEX / CON / INT / WIS /
        CHA). The dataclass declares all six fields and a `_mod`
        property each (dnd-engine/dnd_engine/core/creature.py:18-54).
        """
        abilities = Abilities(
            strength=12, dexterity=14, constitution=10,
            intelligence=8, wisdom=16, charisma=11,
        )
        assert abilities.str_mod == 1
        assert abilities.dex_mod == 2
        assert abilities.con_mod == 0
        assert abilities.int_mod == -1
        assert abilities.wis_mod == 3
        assert abilities.cha_mod == 0


class TestAbilityCheck_Primitive:
    """SRD § Playing the Game › Ability Checks › Naming + ability.

    > An ability check is named for the ability modifier it uses: a
    > Strength check, an Intelligence check, and so on. Different
    > ability checks are called for in different situations, depending
    > on which ability is most relevant.
    """

    def test_skill_check_uses_named_ability_modifier(self):
        """An Athletics check uses the Strength modifier.

        The SRD says the check is "named for the ability modifier it
        uses." `Character.make_skill_check` looks up the skill's
        ability and reads that modifier from `Abilities`
        (dnd-engine/dnd_engine/core/character.py:705-722). For an
        Athletics check, the ability is Strength.
        """
        fighter = _make_fighter()
        fighter._dice_roller = DiceRoller(seed=11)
        skills = {"athletics": {"ability": "str"}}
        result = fighter.make_skill_check("athletics", dc=10, skills_data=skills)
        # STR mod (+3) + proficiency (+2) = +5
        assert result["modifier"] == 5
        assert result["ability"] == "str"

    def test_skill_check_for_different_ability_uses_that_modifier(self):
        """A Stealth check uses the Dexterity modifier.

        Same plumbing as Athletics, different ability. Confirms the
        "named for the ability modifier" rule generalizes.
        """
        fighter = _make_fighter()
        fighter._dice_roller = DiceRoller(seed=11)
        skills = {"stealth": {"ability": "dex"}}
        result = fighter.make_skill_check("stealth", dc=10, skills_data=skills)
        # DEX mod (+2), not proficient
        assert result["modifier"] == 2
        assert result["ability"] == "dex"

    def test_ability_check_primitive_exists_for_non_skill_checks(self):
        """`Character.make_ability_check(ability, dc)` rolls a raw ability check.

        SRD: an ability check is `d20 + ability modifier` vs a DC. No
        skill, no tool — just the ability. The fighter has STR 16
        (+3); rolling against DC 10 produces ``total = roll + 3``.
        """
        fighter = _make_fighter()
        fighter._dice_roller = DiceRoller(seed=1)
        result = fighter.make_ability_check("str", dc=10)
        # STR mod (+3), no proficiency
        assert result["modifier"] == 3
        assert result["total"] == result["roll"] + 3
        assert result["ability"] == "str"
        assert result["dc"] == 10
        assert result["success"] == (result["total"] >= 10)

    def test_ability_check_accepts_advantage_and_disadvantage(self):
        """`make_ability_check` plumbs Advantage/Disadvantage through `d20_test`.

        Advantage takes the higher of two d20s; the returned `roll`
        field is the consumed die.
        """
        fighter = _make_fighter()
        fighter._dice_roller = DiceRoller(seed=7)
        adv = fighter.make_ability_check("str", dc=10, advantage=True)
        fighter._dice_roller = DiceRoller(seed=7)
        dis = fighter.make_ability_check("str", dc=10, disadvantage=True)
        # Same seed but different selection rule — adv >= dis.
        assert adv["roll"] >= dis["roll"]

    def test_ability_check_accepts_full_and_short_ability_names(self):
        """Both `"str"` and `"strength"` resolve to the STR modifier."""
        fighter = _make_fighter()
        fighter._dice_roller = DiceRoller(seed=3)
        short = fighter.make_ability_check("str", dc=10)
        fighter._dice_roller = DiceRoller(seed=3)
        long = fighter.make_ability_check("strength", dc=10)
        assert short["modifier"] == long["modifier"] == 3
        assert short["ability"] == long["ability"] == "str"


class TestAbilityCheck_ProficiencyBonusOptional:
    """SRD § Playing the Game › Ability Checks › Proficiency Bonus.

    > Add your Proficiency Bonus to an ability check when the GM
    > determines that a skill or tool proficiency is relevant to the
    > check and you have that proficiency. For example, if a rule
    > refers to a Strength (Acrobatics or Athletics) check, you can
    > add your Proficiency Bonus to the check if you have proficiency
    > in the Acrobatics or Athletics skill.
    """

    def test_proficiency_added_when_skill_is_proficient(self):
        """Proficient skill check adds proficiency bonus.

        `get_skill_modifier` adds `self.proficiency_bonus` when the
        skill is in `skill_proficiencies`
        (dnd-engine/dnd_engine/core/character.py:715-722).
        """
        fighter = _make_fighter()
        skills = {"athletics": {"ability": "str"}}
        mod = fighter.get_skill_modifier("athletics", skills)
        # STR (+3) + proficiency (+2) = +5
        assert mod == 5

    def test_proficiency_not_added_when_skill_is_not_proficient(self):
        """Non-proficient skill check uses ability modifier only.

        `get_skill_modifier` skips the proficiency add when the skill
        is absent from `skill_proficiencies`
        (dnd-engine/dnd_engine/core/character.py:716-722).
        """
        fighter = _make_fighter()
        skills = {"stealth": {"ability": "dex"}}
        mod = fighter.get_skill_modifier("stealth", skills)
        # DEX (+2) only — no proficiency
        assert mod == 2

    def test_expertise_doubles_proficiency_bonus(self):
        """Expertise skills double the proficiency bonus on the check.

        SRD rule (paraphrased — full text in Rules Glossary):
        Expertise in a skill doubles the proficiency bonus. Engine
        implements this at
        `dnd-engine/dnd_engine/core/character.py:718-720`.
        """
        abilities = Abilities(
            strength=10, dexterity=16, constitution=10,
            intelligence=10, wisdom=10, charisma=10,
        )
        rogue = Character(
            name="Rogue",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities,
            max_hp=8,
            ac=14,
            skill_proficiencies=["stealth"],
            expertise_skills=["stealth"],
        )
        skills = {"stealth": {"ability": "dex"}}
        mod = rogue.get_skill_modifier("stealth", skills)
        # DEX (+3) + proficiency (+2) * 2 = +7
        assert mod == 7

    def test_proficiency_bonus_scales_with_level(self):
        """Proficiency bonus follows the SRD level→PB table.

        `Character.proficiency_bonus` returns
        `2 + (level - 1) // 4` (dnd-engine/dnd_engine/core/character.py:130-143),
        giving +2 at 1-4, +3 at 5-8, +4 at 9-12, etc.
        """
        for level, expected in [(1, 2), (4, 2), (5, 3), (8, 3), (9, 4), (12, 4)]:
            fighter = _make_fighter(level=level)
            assert fighter.proficiency_bonus == expected, (
                f"level {level} expected PB {expected}, got {fighter.proficiency_bonus}"
            )

    def test_ability_check_with_tool_proficiency(self):
        pytest.skip(
            "GAP: the SRD names *skill or tool* proficiency as "
            "relevance gates. Skill proficiencies are honored "
            "(dnd-engine/dnd_engine/core/character.py:715-722). Tool "
            "proficiencies are stored on `Character` "
            "(character.py:109, `tool_proficiencies`) but no ability-"
            "check call site consults them. A 'Dexterity (thieves' "
            "tools) check' adds proficiency only if Thieves' Tools is "
            "in `tool_proficiencies` — that wiring doesn't exist. "
            "Tracked by issue #484."
        )


class TestAbilityCheck_DifficultyClass:
    """SRD § Playing the Game › Ability Checks › Difficulty Class.

    > The Difficulty Class of an ability check represents the task's
    > difficulty. The more difficult the task, the higher its DC. The
    > rules provide DCs for certain checks, but the GM ultimately sets
    > them.
    """

    def test_skill_check_takes_caller_supplied_dc(self):
        """`make_skill_check` takes a DC and uses it for success.

        The SRD framing is that the GM provides the DC. The engine's
        surface accepts it as a parameter and returns
        `success = total >= dc`
        (dnd-engine/dnd_engine/core/character.py:778).
        """
        fighter = _make_fighter()
        fighter._dice_roller = DiceRoller(seed=2)
        skills = {"athletics": {"ability": "str"}}
        result = fighter.make_skill_check("athletics", dc=20, skills_data=skills)
        assert result["dc"] == 20
        assert result["success"] == (result["total"] >= 20)

    def test_skill_check_unknown_skill_raises(self):
        """`make_skill_check` raises `KeyError` for an unknown skill.

        Defensive contract at
        `dnd-engine/dnd_engine/core/character.py:758-759`. Prevents
        silent miscategorization (e.g., a typo in a scenario YAML).
        """
        fighter = _make_fighter()
        skills = {"athletics": {"ability": "str"}}
        with pytest.raises(KeyError):
            fighter.make_skill_check("athleticism", dc=10, skills_data=skills)


class TestAbilityCheck_CreatureParity:
    """SRD § Playing the Game › Ability Checks › Creature parity.

    The SRD doesn't carve PCs out from monsters for ability checks.
    Both should be able to make a Strength check to push a boulder, a
    Wisdom check to spot something, etc.
    """

    def test_creature_can_make_ability_check_for_condition_removal(self):
        """`ConditionManager.attempt_condition_removal` makes an ability check.

        This is the *only* general-creature ability-check surface
        today (dnd-engine/dnd_engine/systems/condition_manager.py:220-292).
        It rolls 1d20 + ability modifier vs DC and emits an
        `ABILITY_CHECK` event. Source-level guard so the path doesn't
        regress.
        """
        src = inspect.getsource(
            __import__(
                "dnd_engine.systems.condition_manager",
                fromlist=["ConditionManager"],
            ).ConditionManager.attempt_condition_removal
        )
        assert "1d20" in src
        assert "ability_mod" in src or "_get_ability_modifier" in src
        assert ">= dc" in src or "roll_total >= dc" in src

    def test_creature_has_general_purpose_ability_check_primitive(self):
        pytest.skip(
            "GAP: `Creature` exposes `make_saving_throw` "
            "(dnd-engine/dnd_engine/core/creature.py:478) but no "
            "`make_ability_check` — a monster cannot roll a Strength "
            "check to escape a pit, an Intelligence check to puzzle "
            "out a glyph, etc. The condition-removal helper "
            "(systems/condition_manager.py:220) is dedicated. Tracked "
            "by issue #484."
        )
