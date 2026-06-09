# ABOUTME: SRD conformance audit for "Playing the Game > The Six Abilities".
# ABOUTME: Cross-references docs/srd/playing-the-game/the-six-abilities.md against engine code.

"""SRD conformance: The Six Abilities.

Maps every rule in `docs/srd/playing-the-game/the-six-abilities.md` to a
test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest

from dnd_engine.core.creature import Abilities, Creature

pytestmark = pytest.mark.srd(
    "playing-the-game/the-six-abilities.md",
    lines="567-655",
)


SKILLS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "skills.json"
)


class TestSixAbilities_Roster:
    """SRD § Playing the Game › The Six Abilities › Ability Descriptions table.

    > All creatures—characters and monsters—have six abilities that
    > measure physical and mental characteristics.
    """

    def test_abilities_dataclass_carries_all_six(self) -> None:
        """`Abilities` exposes the SRD's six and only those six.

        The dataclass (dnd-engine/dnd_engine/core/creature.py:11) is the
        sole carrier of STR/DEX/CON/INT/WIS/CHA. Any future drift to a
        different roster (e.g., a seventh ability) would silently break
        SRD conformance, so the field set is locked here.
        """
        names = {f.name for f in fields(Abilities)}
        assert names == {
            "strength",
            "dexterity",
            "constitution",
            "intelligence",
            "wisdom",
            "charisma",
        }

    def test_creature_carries_an_abilities_instance(self) -> None:
        """Every Creature instance carries the SRD ability block.

        The SRD line "All creatures—characters and monsters—have six
        abilities" maps directly to `Creature.__init__` requiring an
        `abilities: Abilities` parameter (creature.py:64).
        """
        abilities = Abilities(
            strength=10,
            dexterity=10,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
        )
        c = Creature(name="Anyone", max_hp=10, ac=10, abilities=abilities)
        assert isinstance(c.abilities, Abilities)


class TestSixAbilities_Strength:
    """SRD § Playing the Game › The Six Abilities › Strength.

    > Strength measures physical might.

    The SRD's "Skills" table (in proficiency.md) pins Strength as the
    ability for Athletics. Cross-checked here as the canonical data
    parity for what Strength governs.
    """

    def test_athletics_is_strength_based(self) -> None:
        skills: dict = json.loads(SKILLS_JSON.read_text())
        assert skills["athletics"]["ability"] == "str"


class TestSixAbilities_Dexterity:
    """SRD § Playing the Game › The Six Abilities › Dexterity.

    > Dexterity measures agility, reflexes, and balance.

    Per the Skills table, Dexterity governs Acrobatics, Sleight of Hand,
    and Stealth. Dexterity also drives the Initiative modifier.
    """

    def test_dex_skills_are_dexterity_based(self) -> None:
        skills: dict = json.loads(SKILLS_JSON.read_text())
        for skill_id in ("acrobatics", "sleight_of_hand", "stealth"):
            assert skills[skill_id]["ability"] == "dex", skill_id

    def test_initiative_uses_dex_modifier(self) -> None:
        """`Creature.initiative_modifier` returns the DEX modifier.

        Source-level binding at dnd-engine/dnd_engine/core/creature.py:
        110-112. The SRD frames Dexterity as "reflexes," which the
        initiative rule (in a later chapter) consumes — we lock the
        modifier source here.
        """
        abilities = Abilities(
            strength=8,
            dexterity=18,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
        )
        c = Creature(name="Quick", max_hp=10, ac=10, abilities=abilities)
        assert c.initiative_modifier == abilities.dex_mod == 4


class TestSixAbilities_Constitution:
    """SRD § Playing the Game › The Six Abilities › Constitution.

    > Constitution measures health and stamina.

    No SRD skill is CON-based; CON's primary mechanical surface is HP
    on level-up and CON saving throws.
    """

    def test_no_skill_is_constitution_based(self) -> None:
        skills: dict = json.loads(SKILLS_JSON.read_text())
        con_skills = [
            sid for sid, sdata in skills.items() if sdata["ability"] == "con"
        ]
        assert con_skills == [], (
            "SRD: no skill is CON-based; CON drives HP and CON saves."
        )


class TestSixAbilities_Intelligence:
    """SRD § Playing the Game › The Six Abilities › Intelligence.

    > Intelligence measures reasoning and memory.

    Per the Skills table, Intelligence governs Arcana, History,
    Investigation, Nature, and Religion.
    """

    def test_int_skills_are_intelligence_based(self) -> None:
        skills: dict = json.loads(SKILLS_JSON.read_text())
        for skill_id in (
            "arcana",
            "history",
            "investigation",
            "nature",
            "religion",
        ):
            assert skills[skill_id]["ability"] == "int", skill_id


class TestSixAbilities_Wisdom:
    """SRD § Playing the Game › The Six Abilities › Wisdom.

    > Wisdom measures perceptiveness and mental fortitude.

    Per the Skills table, Wisdom governs Animal Handling, Insight,
    Medicine, Perception, and Survival.
    """

    def test_wis_skills_are_wisdom_based(self) -> None:
        skills: dict = json.loads(SKILLS_JSON.read_text())
        for skill_id in (
            "animal_handling",
            "insight",
            "medicine",
            "perception",
            "survival",
        ):
            assert skills[skill_id]["ability"] == "wis", skill_id


class TestSixAbilities_Charisma:
    """SRD § Playing the Game › The Six Abilities › Charisma.

    > Charisma measures confidence, poise, and charm.

    Per the Skills table, Charisma governs Deception, Intimidation,
    Performance, and Persuasion.
    """

    def test_cha_skills_are_charisma_based(self) -> None:
        skills: dict = json.loads(SKILLS_JSON.read_text())
        for skill_id in (
            "deception",
            "intimidation",
            "performance",
            "persuasion",
        ):
            assert skills[skill_id]["ability"] == "cha", skill_id


class TestSixAbilities_ScoreRange:
    """SRD § Playing the Game › The Six Abilities › Ability Scores.

    > Each ability has a score from 1 to 20, although some monsters
    > have a score as high as 30.
    """

    def test_score_floor_of_one_is_enforced_at_construction(self) -> None:
        """`Abilities(strength=0, ...)` raises ``ValueError``.

        SRD pins the floor at 1; a score of 0 is only reachable
        transiently via :meth:`Abilities.reduce_score`, never at
        construction. Source-level binding at
        dnd-engine/dnd_engine/core/creature.py — `Abilities.__post_init__`.
        """
        with pytest.raises(ValueError, match="strength=0"):
            Abilities(
                strength=0,
                dexterity=10,
                constitution=10,
                intelligence=10,
                wisdom=10,
                charisma=10,
            )

    def test_adventurer_score_cap_of_20_is_enforced(self) -> None:
        """`Abilities.for_adventurer(..., strength=21)` raises by default.

        SRD pins a soft cap of 20 for adventurers (player characters),
        with 21-30 reserved for extraordinary creatures or feature-gated
        edge cases. :meth:`Abilities.for_adventurer` enforces the 20
        ceiling unless the caller passes
        ``features_allowing_above_20`` naming the feature that permits
        the higher value.
        """
        with pytest.raises(ValueError, match="adventurer cap"):
            Abilities.for_adventurer(
                strength=21,
                dexterity=10,
                constitution=10,
                intelligence=10,
                wisdom=10,
                charisma=10,
            )

        # Feature override permits exceeding 20 (still bounded by the
        # absolute [1, 30] ceiling from __post_init__).
        abilities = Abilities.for_adventurer(
            strength=22,
            dexterity=10,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
            features_allowing_above_20=("Manual of Gainful Exercise",),
        )
        assert abilities.strength == 22

    def test_hard_score_cap_of_30_is_enforced(self) -> None:
        """`Abilities(strength=31, ...)` raises ``ValueError``.

        SRD pins an absolute ceiling of 30 for any creature.
        Source-level binding at
        dnd-engine/dnd_engine/core/creature.py — `Abilities.__post_init__`.
        """
        with pytest.raises(ValueError, match="strength=31"):
            Abilities(
                strength=31,
                dexterity=10,
                constitution=10,
                intelligence=10,
                wisdom=10,
                charisma=10,
            )

    def test_monster_ability_scores_are_within_one_to_thirty(self) -> None:
        """Catalog parity: every monster's ability scores are in [1, 30].

        Even ahead of engine enforcement, the data must respect the
        SRD's 1-30 range. This is a forward-compatible lint that the
        catalog won't seed an out-of-range value.
        """
        monsters_path = (
            Path(__file__).resolve().parents[3]
            / "dnd_engine"
            / "data"
            / "srd"
            / "monsters.json"
        )
        monsters: dict = json.loads(monsters_path.read_text())
        for monster_id, mdata in monsters.items():
            abilities = mdata.get("abilities", {})
            for key, value in abilities.items():
                assert 1 <= value <= 30, (
                    f"{monster_id}.abilities.{key} = {value} is outside "
                    f"SRD's 1-30 range (the-six-abilities.md)."
                )


class TestSixAbilities_ScoreReducedToZero:
    """SRD § Playing the Game › The Six Abilities › Ability Scores › Score 1.

    > If an effect reduces a score to 0, that effect explains what
    > happens.
    """

    def test_reduce_score_mutator_requires_a_named_source(self) -> None:
        """`Abilities.reduce_score` requires a non-empty ``source``.

        The SRD requires that any effect reducing a score to 0 *explain*
        the consequences. :meth:`Abilities.reduce_score` enforces that by
        refusing to mutate unless the caller names the effect, so a
        score cannot be driven to 0 anonymously. The score floors at 0
        rather than going negative.
        """
        abilities = Abilities(
            strength=10,
            dexterity=10,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
        )

        # Anonymous reduction is rejected.
        with pytest.raises(ValueError, match="non-empty `source`"):
            abilities.reduce_score("strength", 5, source="")
        assert abilities.strength == 10  # unchanged

        # Named reduction is allowed and floors at 0 (not negative).
        abilities.reduce_score(
            "strength", amount=15, source="Shadow strength drain"
        )
        assert abilities.strength == 0

        # Reduction by 0 with a named source is a no-op (but still requires source).
        abilities.reduce_score("dexterity", 0, source="Slow spell")
        assert abilities.dexterity == 10

        # Unknown ability names are rejected.
        with pytest.raises(ValueError, match="Unknown ability"):
            abilities.reduce_score("luck", 1, source="Anything")


class TestSixAbilities_Modifiers:
    """SRD § Playing the Game › The Six Abilities › Ability Modifiers.

    > An ability modifier is derived from its score, as shown in the
    > Ability Modifiers table.

    SRD modifier formula: `(score - 10) // 2`, floored (see Round Down).
    """

    def test_modifier_formula_matches_score_minus_ten_div_two(self) -> None:
        """All six modifier properties use `(score - 10) // 2`.

        Source-level binding at dnd-engine/dnd_engine/core/creature.py:
        26-54. Exhaustive over the canonical SRD value examples.
        """
        # SRD Ability Modifiers table examples (score: expected modifier)
        cases = {
            1: -5,
            2: -4,
            3: -4,
            4: -3,
            5: -3,
            6: -2,
            7: -2,
            8: -1,
            9: -1,
            10: 0,
            11: 0,
            12: 1,
            13: 1,
            14: 2,
            15: 2,
            16: 3,
            17: 3,
            18: 4,
            19: 4,
            20: 5,
            30: 10,
        }
        for score, expected in cases.items():
            a = Abilities(
                strength=score,
                dexterity=score,
                constitution=score,
                intelligence=score,
                wisdom=score,
                charisma=score,
            )
            assert a.str_mod == expected, f"STR {score} → expected {expected}"
            assert a.dex_mod == expected, f"DEX {score} → expected {expected}"
            assert a.con_mod == expected, f"CON {score} → expected {expected}"
            assert a.int_mod == expected, f"INT {score} → expected {expected}"
            assert a.wis_mod == expected, f"WIS {score} → expected {expected}"
            assert a.cha_mod == expected, f"CHA {score} → expected {expected}"

    def test_modifier_is_applied_to_d20_tests(self) -> None:
        """Ability modifiers feed into the D20-Test surfaces.

        Source-level: `Character.get_saving_throw_modifier` (dnd-engine/
        dnd_engine/core/character.py:169) adds an ability modifier, and
        `Character.get_skill_modifier` (character.py:689) does likewise.
        Locked here so the SRD line "you apply [the modifier] whenever
        you make a D20 Test with that ability" has a callable proof.
        """
        from dnd_engine.core.character import Character, CharacterClass

        abilities = Abilities(
            strength=18,  # +4
            dexterity=10,
            constitution=14,  # +2
            intelligence=8,  # -1
            wisdom=10,
            charisma=10,
        )
        char = Character(
            name="Tester",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=15,
        )
        # STR save w/o proficiency = STR mod
        assert char.get_saving_throw_modifier("str") == 4
        # CON save w/o proficiency = CON mod
        assert char.get_saving_throw_modifier("con") == 2
        # INT save w/o proficiency = INT mod
        assert char.get_saving_throw_modifier("int") == -1


class TestSixAbilities_RoundDown:
    """SRD § Playing the Game › The Six Abilities › Round Down sidebar.

    > Whenever you divide or multiply a number in the game, round down
    > if you end up with a fraction, even if the fraction is one-half
    > or greater. Some rules make an exception and tell you to round up.
    """

    def test_modifier_division_rounds_down_for_odd_scores(self) -> None:
        """Odd ability scores round their modifier *down*.

        SRD example: score 9 → modifier -1 (not 0). The use of `//` in
        `Abilities.*_mod` (creature.py:26-54) enforces this for every
        ability. Source-level binding so the formula can't silently
        drift to `round()` (banker's rounding) or `int()` (toward 0).
        """
        # Odd negative-bracket scores: SRD says floor, not toward-zero.
        # Python's `//` already floors for negatives.
        a = Abilities(
            strength=9,  # (9-10)//2 = -1
            dexterity=7,  # (7-10)//2 = -2
            constitution=5,  # (5-10)//2 = -3
            intelligence=3,  # (3-10)//2 = -4
            wisdom=11,  # (11-10)//2 = 0 (floor of 0.5)
            charisma=13,  # (13-10)//2 = 1
        )
        assert a.str_mod == -1
        assert a.dex_mod == -2
        assert a.con_mod == -3
        assert a.int_mod == -4
        assert a.wis_mod == 0
        assert a.cha_mod == 1
