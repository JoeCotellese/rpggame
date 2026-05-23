# ABOUTME: SRD conformance audit for "Character Creation > Level Advancement".
# ABOUTME: Cross-references docs/srd/character-creation/level-advancement.md against engine code.

"""SRD conformance: Level Advancement.

Maps every rule in `docs/srd/character-creation/level-advancement.md` to
a test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities

pytestmark = pytest.mark.srd(
    "character-creation/level-advancement.md",
    lines="3310-3555",
)

# SRD 5.2.1 Character Advancement table (level -> XP threshold).
# Verbatim from docs/srd/character-creation/level-advancement.md.
SRD_XP_BY_LEVEL: dict[int, int] = {
    1: 0,
    2: 300,
    3: 900,
    4: 2_700,
    5: 6_500,
    6: 14_000,
    7: 23_000,
    8: 34_000,
    9: 48_000,
    10: 64_000,
    11: 85_000,
    12: 100_000,
    13: 120_000,
    14: 140_000,
    15: 165_000,
    16: 195_000,
    17: 225_000,
    18: 265_000,
    19: 305_000,
    20: 355_000,
}

# SRD 5.2.1 proficiency bonus by level.
SRD_PROFICIENCY_BY_LEVEL: dict[int, int] = {
    **dict.fromkeys(range(1, 5), 2),
    **dict.fromkeys(range(5, 9), 3),
    **dict.fromkeys(range(9, 13), 4),
    **dict.fromkeys(range(13, 17), 5),
    **dict.fromkeys(range(17, 21), 6),
}

# SRD 5.2.1 Fixed Hit Points by Class table.
SRD_FIXED_HP_BY_CLASS: dict[str, int] = {
    "barbarian": 7,
    "fighter": 6,
    "paladin": 6,
    "ranger": 6,
    "bard": 5,
    "cleric": 5,
    "druid": 5,
    "monk": 5,
    "rogue": 5,
    "warlock": 5,
    "sorcerer": 4,
    "wizard": 4,
}

# SRD hit dice per class (from class entries; cross-checked against
# Fixed Hit Points by Class which equals max_hit_die_face/2 + 1).
SRD_HIT_DIE_BY_CLASS: dict[str, str] = {
    "barbarian": "1d12",
    "fighter": "1d10",
    "paladin": "1d10",
    "ranger": "1d10",
    "bard": "1d8",
    "cleric": "1d8",
    "druid": "1d8",
    "monk": "1d8",
    "rogue": "1d8",
    "warlock": "1d8",
    "sorcerer": "1d6",
    "wizard": "1d6",
}

PROGRESSION_PATH = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "progression.json"
)
CLASSES_PATH = Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "classes.json"


def _make_character(level: int, char_class: CharacterClass = CharacterClass.FIGHTER) -> Character:
    """Minimal Character with the given level for property-under-test checks."""
    abilities = Abilities(
        strength=16,
        dexterity=14,
        constitution=14,
        intelligence=10,
        wisdom=12,
        charisma=8,
    )
    return Character(
        name="Test",
        character_class=char_class,
        level=level,
        abilities=abilities,
        max_hp=10,
        ac=16,
    )


class TestCharacterAdvancementTable:
    """SRD § Character Creation › Level Advancement › Character Advancement.

    > The Character Advancement table lists the XP you need to advance to
    > a level and the Proficiency Bonus for a character of that level.
    > When your XP total equals or exceeds a number in the Experience
    > Points column, you reach the corresponding level.
    """

    def test_xp_by_level_data_matches_srd(self):
        """`progression.json` XP thresholds match the SRD table verbatim."""
        data = json.loads(PROGRESSION_PATH.read_text())
        engine_xp = {int(k): v for k, v in data["xp_by_level"].items()}

        assert engine_xp == SRD_XP_BY_LEVEL

    def test_proficiency_bonus_by_level_data_matches_srd(self):
        """`progression.json` proficiency table matches the SRD table verbatim."""
        data = json.loads(PROGRESSION_PATH.read_text())
        engine_pb = {int(k): v for k, v in data["proficiency_by_level"].items()}

        assert engine_pb == SRD_PROFICIENCY_BY_LEVEL

    @pytest.mark.parametrize("level,expected_pb", sorted(SRD_PROFICIENCY_BY_LEVEL.items()))
    def test_character_proficiency_bonus_property_matches_srd(self, level: int, expected_pb: int):
        """`Character.proficiency_bonus` returns the SRD value for every level 1-20."""
        char = _make_character(level=level)

        assert char.proficiency_bonus == expected_pb


class TestGainingALevel_Step2_HitPoints:
    """SRD § Character Creation › Level Advancement › Gaining a Level › Step 2.

    > Adjust Hit Points and Hit Point Dice. Each time you gain a level,
    > you gain an additional Hit Die. Roll that die, add your
    > Constitution modifier to the roll, and add the total (minimum of 1)
    > to your Hit Point maximum. Instead of rolling, you can use the
    > fixed value shown in the Fixed Hit Points by Class table.
    """

    def test_class_hit_dice_data_matches_srd_for_supported_classes(self):
        """Each class defined in `classes.json` carries the SRD hit die.

        Note: the engine currently ships data for only 3 of the 12 SRD
        classes (fighter, rogue, wizard). The other 9 are absent — that
        gap belongs to the classes / catalog audit, not this one. Here we
        verify only that the classes that DO exist match the SRD.
        """
        data = json.loads(CLASSES_PATH.read_text())

        for class_name, class_data in data.items():
            srd_die = SRD_HIT_DIE_BY_CLASS.get(class_name)
            assert srd_die is not None, f"engine has class '{class_name}' not in SRD — investigate"
            assert class_data["hit_die"] == srd_die, (
                f"{class_name}: engine={class_data['hit_die']!r}, SRD={srd_die!r}"
            )

    def test_hit_point_increase_uses_hit_die_plus_con_mod_minimum_one(self):
        pytest.skip(
            "GAP-COVERAGE: rule is implemented at "
            "dnd_engine/core/character.py:618-644 (_increase_hp): rolls "
            "the class hit die, adds CON mod, clamps to minimum 1. The "
            "audit verification needs a seeded DiceRoller fixture and a "
            "DataLoader stub, which existing tests in "
            "tests/test_character_factory.py and tests/test_character_*.py "
            "already cover. Promote one of those to an SRD-marked "
            "verification rather than reinventing the fixture here."
        )

    def test_fixed_hit_points_per_class_alternative_to_rolling(self):
        pytest.skip(
            "GAP: SRD offers 'Instead of rolling, you can use the fixed "
            "value shown in the Fixed Hit Points by Class table.' The "
            "engine's _increase_hp (character.py:618) always rolls; "
            "there is no API surface for the fixed-value alternative. "
            "Players who prefer deterministic HP cannot opt in. File "
            "issue to add a `roll: bool = True` parameter or similar."
        )


class TestGainingALevel_Step1_ChooseClass:
    """SRD § Character Creation › Level Advancement › Gaining a Level › Step 1.

    > Choose a Class. Most characters advance in the same class. However,
    > you might decide to gain a level in another class using the rules
    > in the "Multiclassing" section.
    """

    def test_level_up_advances_in_same_class_by_default(self):
        pytest.skip(
            "GAP-COVERAGE: `_level_up` at character.py:582 advances "
            "self.level by 1 in the existing self.character_class — "
            "by construction, same-class advancement is the only path. "
            "Verification trivial but requires DataLoader fixture; "
            "covered indirectly by existing level-up tests."
        )

    def test_level_up_supports_choosing_a_different_class_multiclass(self):
        pytest.skip(
            "GAP: multiclassing is not implemented at the level-up entry "
            "point. `_level_up` (character.py:582-616) assumes "
            "self.character_class is the class being levelled. No "
            "parameter to specify a different class. See SRD § "
            "Multiclassing — separate conformance audit when "
            "tests/srd/character_creation/test_multiclassing.py lands."
        )


class TestGainingALevel_Step4_ProficiencyBonus:
    """SRD § Character Creation › Level Advancement › Gaining a Level › Step 4.

    > Adjust Proficiency Bonus. A character's Proficiency Bonus increases
    > at certain levels, as shown in the Character Advancement table and
    > your class features table in "Classes." When your Proficiency Bonus
    > increases, increase all the numbers on your character sheet that
    > include your Proficiency Bonus.
    """

    @pytest.mark.parametrize(
        "old_level,new_level,pb_changes",
        [
            (1, 2, False),
            (4, 5, True),
            (5, 6, False),
            (8, 9, True),
            (12, 13, True),
            (16, 17, True),
        ],
    )
    def test_proficiency_bonus_property_updates_on_level_change(
        self, old_level: int, new_level: int, pb_changes: bool
    ):
        """The PB property recomputes from level; no manual recalc needed.

        Because `Character.proficiency_bonus` is a computed property
        (character.py:130), any read after a level change returns the
        new value. The SRD's instruction to "increase all the numbers
        on your character sheet that include your Proficiency Bonus"
        is satisfied by construction — there are no cached PB-derived
        fields to update.
        """
        char = _make_character(level=old_level)
        old_pb = char.proficiency_bonus

        char.level = new_level

        if pb_changes:
            assert char.proficiency_bonus != old_pb
        else:
            assert char.proficiency_bonus == old_pb


class TestGainingALevel_Step5_AbilityModifiers:
    """SRD § Character Creation › Level Advancement › Gaining a Level › Step 5.

    > Adjust Ability Modifiers. If you choose a feat that increases one
    > or more of your ability scores, your ability modifier also changes
    > if the new score is an even number. When that happens, adjust all
    > the numbers on your character sheet that use that ability modifier.
    > When your Constitution modifier increases by 1, your Hit Point
    > maximum increases by 1 for each level you have attained.
    """

    def test_ability_score_increase_from_feat_recomputes_dependent_modifiers(self):
        pytest.skip(
            "GAP: feat/ASI level-up flow not visible. Grep for 'feat', "
            "'ability_score_increase', or 'asi' in core/character.py "
            "returns no matches in the level-up path. Either the engine "
            "does not yet support feats at level-up, or it relies on "
            "callers mutating Abilities directly — in which case the "
            "modifier recalculation is automatic (Abilities.*_mod are "
            "computed properties), but the feat-selection workflow "
            "itself doesn't exist."
        )

    def test_constitution_modifier_increase_recalculates_max_hp_retroactively(self):
        pytest.skip(
            "GAP: SRD requires that when CON mod increases by 1, HP max "
            "increases by 1 per attained level (e.g., level 8 character "
            "going from CON 17 to 18 gains +8 HP). Grep for retroactive "
            "HP recalculation across character.py shows no such path. "
            "Currently CON mod only affects HP gained on the next "
            "level-up (character.py:636-637), not on a CON-only change. "
            "File issue."
        )


class TestTiersOfPlay:
    """SRD § Character Creation › Level Advancement › Tiers of Play.

    > These tiers don't have any rules associated with them; they point
    > to the fact that the play experience evolves as characters gain
    > levels.
    """

    def test_tiers_of_play_have_no_mechanical_rule(self):
        """SRD explicitly states tiers carry no mechanical rule.

        Documented here for completeness so the audit doesn't appear to
        skip the section. Tier-based UX (e.g., narrative scaling) is
        out of scope for SRD conformance.
        """
        # Intentionally empty: the SRD itself declares no rule to enforce.
        assert True
