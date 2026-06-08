# ABOUTME: SRD conformance audit for "Playing the Game > Proficiency".
# ABOUTME: Cross-references docs/srd/playing-the-game/proficiency.md against engine code.

"""SRD conformance: Proficiency.

Maps every rule in `docs/srd/playing-the-game/proficiency.md` to a test.
Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities

pytestmark = pytest.mark.srd(
    "playing-the-game/proficiency.md",
    lines="1012-1316",
)


DATA_DIR = Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd"
CLASSES_JSON = DATA_DIR / "classes.json"
SKILLS_JSON = DATA_DIR / "skills.json"
PROGRESSION_JSON = DATA_DIR / "progression.json"
RACES_JSON = DATA_DIR / "races.json"


def _make_fighter(level: int = 1, abilities: Abilities | None = None) -> Character:
    """Construct a baseline fighter at a given level for PB tests."""
    if abilities is None:
        abilities = Abilities(
            strength=16,
            dexterity=12,
            constitution=14,
            intelligence=10,
            wisdom=10,
            charisma=8,
        )
    return Character(
        name="Tester",
        character_class=CharacterClass.FIGHTER,
        level=level,
        abilities=abilities,
        max_hp=10 + level,
        ac=16,
        saving_throw_proficiencies=["str", "con"],
        skill_proficiencies=["athletics"],
        weapon_proficiencies=["simple", "martial"],
        armor_proficiencies=["light", "medium", "heavy", "shields"],
        tool_proficiencies=[],
    )


class TestProficiency_HeroicInspiration:
    """SRD § Playing the Game › Proficiency › Heroic Inspiration sidebar.

    > If you have Heroic Inspiration, you can expend it to reroll any
    > die immediately after rolling it, and you must use the new roll.
    """

    def test_heroic_inspiration_lets_you_reroll_any_die(self) -> None:
        pytest.skip(
            "GAP: Heroic Inspiration is not implemented anywhere. No "
            "`has_heroic_inspiration` flag on `Character` (dnd-engine/"
            "dnd_engine/core/character.py:23), and `DiceRoller` "
            "(dnd-engine/dnd_engine/core/dice.py) has no consume-to-"
            "reroll API. Tracked by issue #478."
        )

    def test_heroic_inspiration_cap_of_one_instance(self) -> None:
        pytest.skip(
            "GAP: SRD: 'You can never have more than one instance of "
            "Heroic Inspiration. If something gives you Heroic "
            "Inspiration and you already have it, you can give it to a "
            "player character in your group who lacks it.' No cap-and-"
            "transfer surface on `Character`. Tracked by issue #478."
        )

    def test_human_starts_each_day_with_heroic_inspiration(self) -> None:
        pytest.skip(
            "GAP: SRD: 'Human characters start each day with Heroic "
            "Inspiration.' `races.json` defines a Human entry but no "
            "engine code grants the flag at session start or after a "
            "long rest. Tracked by issue #478."
        )


class TestProficiency_BonusByLevel:
    """SRD § Playing the Game › Proficiency › Proficiency Bonus table (PC).

    > A character's Proficiency Bonus increases as the character gains
    > levels.
    >
    > | Level | Bonus |
    > |-------|-------|
    > | 1-4   | +2    |
    > | 5-8   | +3    |
    > | 9-12  | +4    |
    > | 13-16 | +5    |
    > | 17-20 | +6    |
    """

    @pytest.mark.parametrize(
        "level,expected_pb",
        [
            (1, 2),
            (2, 2),
            (3, 2),
            (4, 2),
            (5, 3),
            (6, 3),
            (7, 3),
            (8, 3),
            (9, 4),
            (10, 4),
            (11, 4),
            (12, 4),
            (13, 5),
            (14, 5),
            (15, 5),
            (16, 5),
            (17, 6),
            (18, 6),
            (19, 6),
            (20, 6),
        ],
    )
    def test_character_proficiency_bonus_matches_srd_table(
        self, level: int, expected_pb: int
    ) -> None:
        """`Character.proficiency_bonus` returns +2..+6 by SRD bands.

        Source-level binding at dnd-engine/dnd_engine/core/character.py:
        129-143. The formula `2 + (level - 1) // 4` reproduces the SRD
        table for levels 1-20.
        """
        char = _make_fighter(level=level)
        assert char.proficiency_bonus == expected_pb

    def test_progression_data_matches_srd_table_for_pc_levels(self) -> None:
        """Catalog parity: progression.json mirrors the SRD PB table.

        The JSON-driven proficiency-by-level lookup must agree with the
        SRD's banded values for levels 1-20.
        """
        progression: dict = json.loads(PROGRESSION_JSON.read_text())
        pb_by_level = progression["proficiency_by_level"]
        expected = {
            **dict.fromkeys(range(1, 5), 2),
            **dict.fromkeys(range(5, 9), 3),
            **dict.fromkeys(range(9, 13), 4),
            **dict.fromkeys(range(13, 17), 5),
            **dict.fromkeys(range(17, 21), 6),
        }
        for level, want in expected.items():
            assert int(pb_by_level[str(level)]) == want, (
                f"progression.proficiency_by_level[{level}] = "
                f"{pb_by_level[str(level)]}, expected {want}"
            )


class TestProficiency_BonusByCR:
    """SRD § Playing the Game › Proficiency › Proficiency Bonus table (monster).

    > A monster's Proficiency Bonus is based on its Challenge Rating.
    """

    def test_creature_does_not_expose_proficiency_bonus_from_cr(self) -> None:
        pytest.skip(
            "GAP: `Creature` (dnd-engine/dnd_engine/core/creature.py:"
            "57) has no `proficiency_bonus` property. Only `Character."
            "proficiency_bonus` (character.py:130) exists, derived from "
            "PC level. Nothing maps the `cr` field in monsters.json to "
            "the SRD PB band. Tracked by issue #480."
        )

    def test_monster_save_totals_decompose_to_ability_mod_plus_pb(self) -> None:
        pytest.skip(
            "GAP: monsters.json stores `saving_throws` as raw final "
            "totals (e.g., bearded_devil: str=5, con=4, wis=2 at "
            "dnd_engine/data/srd/monsters.json:969). Without a "
            "CR->PB mapping on `Creature`, the engine cannot validate "
            "that those totals equal `ability_mod + PB` for the "
            "proficient saves. Tracked by issue #480."
        )


class TestProficiency_BonusApplication:
    """SRD § Playing the Game › Proficiency › Bonus Application.

    > This bonus is applied to a D20 Test when the creature has
    > proficiency in a skill, in a saving throw, or with an item that
    > the creature uses to make the D20 Test. The bonus is also used
    > for spell attacks and for calculating the DC of saving throws
    > for spells.
    """

    def test_save_proficiency_adds_pb_to_saving_throw_modifier(self) -> None:
        """Proficient saves include PB; non-proficient saves don't.

        Source-level binding at dnd-engine/dnd_engine/core/character.py:
        169-235. STR/CON are proficient for the test fighter; INT/DEX
        are not.
        """
        char = _make_fighter(level=5)  # PB = +3
        # STR mod = +3 (16), proficient → +3 + 3 = +6
        assert char.get_saving_throw_modifier("str") == 6
        # INT mod = 0 (10), not proficient → 0
        assert char.get_saving_throw_modifier("int") == 0
        # DEX mod = +1 (12), not proficient → +1
        assert char.get_saving_throw_modifier("dex") == 1
        # CON mod = +2 (14), proficient → +2 + 3 = +5
        assert char.get_saving_throw_modifier("con") == 5

    def test_skill_proficiency_adds_pb_to_skill_modifier(self) -> None:
        """Proficient skills include PB; non-proficient skills don't.

        Source-level binding at dnd-engine/dnd_engine/core/character.py:
        689-724.
        """
        skills_data = json.loads(SKILLS_JSON.read_text())
        char = _make_fighter(level=5)  # PB = +3
        # Athletics (STR): proficient → STR mod (+3) + PB (+3) = +6
        assert char.get_skill_modifier("athletics", skills_data) == 6
        # Stealth (DEX): not proficient → DEX mod (+1) = +1
        assert char.get_skill_modifier("stealth", skills_data) == 1

    def test_weapon_proficiency_adds_pb_to_attack_roll(self) -> None:
        """Weapon proficiency surfaces PB on the attack roll.

        Source-level binding at dnd-engine/dnd_engine/core/character.py:
        366-412 (`get_attack_bonus` adds PB only when proficient).
        """
        # Fighter is proficient with simple and martial weapons,
        # so a longsword (martial) attack should include PB.
        char = _make_fighter(level=5)  # PB = +3, STR mod = +3
        items_data = {
            "weapons": {
                "longsword": {
                    "weapon_type": "martial",
                    "category": "melee",
                    "properties": [],
                }
            }
        }
        # PB (+3) + STR mod (+3) = +6
        assert char.get_attack_bonus("longsword", items_data) == 6

    def test_non_proficient_weapon_excludes_pb(self) -> None:
        """Without weapon proficiency the engine omits PB.

        Source-level binding at dnd-engine/dnd_engine/core/character.py:
        408-412 (the `is_proficient` branch). Locks the negative case
        so the SRD's conditional ("when the creature has proficiency")
        can't drift to "always add PB."
        """
        char = _make_fighter(level=5)
        # Override proficiencies so the test weapon is not covered.
        char.weapon_proficiencies = ["simple"]
        items_data = {
            "weapons": {
                "exotic_blade": {
                    "weapon_type": "exotic",
                    "category": "melee",
                    "properties": [],
                }
            }
        }
        # Just STR mod (+3), no PB
        assert char.get_attack_bonus("exotic_blade", items_data) == 3

    def test_spell_attack_bonus_includes_pb(self) -> None:
        """Spell attack bonus = PB + spellcasting ability modifier.

        Source-level binding at dnd-engine/dnd_engine/core/character.py:
        907-960 (`get_spell_attack_bonus`).
        """
        abilities = Abilities(
            strength=8,
            dexterity=14,
            constitution=12,
            intelligence=18,  # +4
            wisdom=10,
            charisma=10,
        )
        wiz = Character(
            name="Magus",
            character_class=CharacterClass.WIZARD,
            level=5,  # PB = +3
            abilities=abilities,
            max_hp=20,
            ac=12,
            spellcasting_ability="int",
        )
        # PB (+3) + INT mod (+4) = +7
        assert wiz.get_spell_attack_bonus("int") == 7

    def test_spell_save_dc_includes_pb(self) -> None:
        """Spell save DC = 8 + PB + spellcasting ability modifier.

        Source-level binding at dnd-engine/dnd_engine/core/character.py:
        1532-1550 (`get_spell_save_dc`).
        """
        abilities = Abilities(
            strength=8,
            dexterity=14,
            constitution=12,
            intelligence=18,  # +4
            wisdom=10,
            charisma=10,
        )
        wiz = Character(
            name="Magus",
            character_class=CharacterClass.WIZARD,
            level=5,  # PB = +3
            abilities=abilities,
            max_hp=20,
            ac=12,
            spellcasting_ability="int",
        )
        # 8 + PB (+3) + INT mod (+4) = 15
        assert wiz.get_spell_save_dc() == 15


class TestProficiency_BonusDoesntStack:
    """SRD § Playing the Game › Proficiency › The Bonus Doesn't Stack.

    > Your Proficiency Bonus can't be added to a die roll or another
    > number more than once. For example, if a rule allows you to make
    > a Charisma (Deception or Persuasion) check, you add your
    > Proficiency Bonus if you're proficient in either skill, but you
    > don't add it twice if you're proficient in both skills.
    >
    > Occasionally, a Proficiency Bonus might be multiplied or divided.
    > Whenever the bonus is used, it can be multiplied only once and
    > divided only once.

    Locked by ``Character.get_either_or_skill_modifier`` and
    ``dnd_engine.systems.proficiency.ProficiencyApplication`` (issue
    #481, plan-08 slice 3). The detailed behavior matrix lives in
    ``TestProficiency_EitherOrSkillModifier`` and
    ``tests/systems/test_proficiency_application.py``; these two cases
    pin the SRD-quoted invariants directly.
    """

    def test_either_or_skill_check_applies_pb_once(self) -> None:
        """SRD: 'you don't add [PB] twice if you're proficient in both.'

        A character proficient in both Deception and Persuasion must
        get the same either-or modifier as one proficient in only one.
        """
        skills_data = json.loads(SKILLS_JSON.read_text())
        abilities = Abilities(
            strength=10,
            dexterity=12,
            constitution=12,
            intelligence=10,
            wisdom=10,
            charisma=16,  # +3
        )
        proficient_in_one = Character(
            name="One",
            character_class=CharacterClass.ROGUE,
            level=5,  # PB +3
            abilities=abilities,
            max_hp=30,
            ac=13,
            skill_proficiencies=["deception"],
        )
        proficient_in_both = Character(
            name="Both",
            character_class=CharacterClass.ROGUE,
            level=5,
            abilities=abilities,
            max_hp=30,
            ac=13,
            skill_proficiencies=["deception", "persuasion"],
        )
        either_or = ["deception", "persuasion"]
        assert proficient_in_one.get_either_or_skill_modifier(
            either_or, skills_data
        ) == proficient_in_both.get_either_or_skill_modifier(either_or, skills_data)

    def test_proficiency_application_blocks_second_multiplier(self) -> None:
        """SRD: 'it can be multiplied only once and divided only once.'

        Source-level binding at ``dnd_engine/systems/proficiency.py``:
        ``ProficiencyApplication.add`` raises on a second non-identity
        multiplier so a future feature stacking on Expertise (or a
        bug) is loud, not silent.
        """
        from dnd_engine.systems.proficiency import ProficiencyApplication

        pb = ProficiencyApplication(proficiency_bonus=3)
        # First multiplier (e.g., Expertise) is allowed.
        assert pb.add(multiplier=2) == 6
        # Second multiplier attempt raises.
        with pytest.raises(ValueError, match="multiplied only once"):
            pb.add(multiplier=2)


class TestProficiency_EitherOrSkillModifier:
    """SRD § Playing the Game › Proficiency › Either-or skill checks.

    > If a rule allows you to make a Charisma (Deception or Persuasion)
    > check, you add your Proficiency Bonus if you're proficient in
    > either skill, but you don't add it twice if you're proficient in
    > both skills.

    Locked behavior for ``Character.get_either_or_skill_modifier``.
    """

    @staticmethod
    def _silver_tongue(
        *,
        skill_proficiencies: list[str] | None = None,
        expertise_skills: list[str] | None = None,
    ) -> Character:
        """Charismatic rogue at level 5 (PB +3) with CHA 16 (+3 mod)."""
        abilities = Abilities(
            strength=10,
            dexterity=12,
            constitution=12,
            intelligence=10,
            wisdom=10,
            charisma=16,  # +3
        )
        return Character(
            name="Voice",
            character_class=CharacterClass.ROGUE,
            level=5,
            abilities=abilities,
            max_hp=30,
            ac=13,
            skill_proficiencies=skill_proficiencies or [],
            expertise_skills=expertise_skills or [],
        )

    def test_proficient_in_one_of_two_skills_adds_pb_once(self) -> None:
        """Proficient in Deception only: CHA mod (+3) + PB (+3) = +6."""
        skills_data = json.loads(SKILLS_JSON.read_text())
        bard = self._silver_tongue(skill_proficiencies=["deception"])
        result = bard.get_either_or_skill_modifier(["deception", "persuasion"], skills_data)
        assert result == 6

    def test_proficient_in_both_skills_adds_pb_once_not_twice(self) -> None:
        """The locked SRD rule: proficient in both → same as one.

        CHA mod (+3) + PB (+3) = +6 — NOT +9.
        """
        skills_data = json.loads(SKILLS_JSON.read_text())
        bard = self._silver_tongue(skill_proficiencies=["deception", "persuasion"])
        result = bard.get_either_or_skill_modifier(["deception", "persuasion"], skills_data)
        assert result == 6

    def test_proficient_in_neither_skill_omits_pb(self) -> None:
        """No proficiency in either → just the ability modifier."""
        skills_data = json.loads(SKILLS_JSON.read_text())
        bard = self._silver_tongue()
        result = bard.get_either_or_skill_modifier(["deception", "persuasion"], skills_data)
        assert result == 3  # CHA mod, no PB

    def test_expertise_in_one_skill_doubles_pb_once(self) -> None:
        """Expertise in one of the listed skills doubles PB once.

        CHA mod (+3) + PB doubled (+6) = +9.
        """
        skills_data = json.loads(SKILLS_JSON.read_text())
        bard = self._silver_tongue(
            skill_proficiencies=["deception"],
            expertise_skills=["deception"],
        )
        result = bard.get_either_or_skill_modifier(["deception", "persuasion"], skills_data)
        assert result == 9

    def test_proficient_in_both_expertise_in_one_doubles_pb_once(self) -> None:
        """Proficient in both, expertise in one → PB doubled once, not
        applied twice. CHA mod (+3) + PB doubled (+6) = +9.
        """
        skills_data = json.loads(SKILLS_JSON.read_text())
        bard = self._silver_tongue(
            skill_proficiencies=["deception", "persuasion"],
            expertise_skills=["deception"],
        )
        result = bard.get_either_or_skill_modifier(["deception", "persuasion"], skills_data)
        assert result == 9

    def test_mismatched_abilities_raises(self) -> None:
        """Either-or only makes sense when the candidate skills share an
        ability (the SRD's parenthesized "Charisma (X or Y)" pattern).
        Mixed-ability lists are a callsite bug.
        """
        skills_data = json.loads(SKILLS_JSON.read_text())
        bard = self._silver_tongue(skill_proficiencies=["deception"])
        with pytest.raises(ValueError, match="ability"):
            bard.get_either_or_skill_modifier(["deception", "athletics"], skills_data)

    def test_empty_skill_list_raises(self) -> None:
        """An empty candidate list has no ability to use; reject."""
        skills_data = json.loads(SKILLS_JSON.read_text())
        bard = self._silver_tongue()
        with pytest.raises(ValueError, match="empty"):
            bard.get_either_or_skill_modifier([], skills_data)

    def test_unknown_skill_in_list_raises(self) -> None:
        """An unknown skill is the same callsite bug as in
        ``get_skill_modifier``."""
        skills_data = json.loads(SKILLS_JSON.read_text())
        bard = self._silver_tongue()
        with pytest.raises(KeyError, match="Unknown skill"):
            bard.get_either_or_skill_modifier(["deception", "made_up_skill"], skills_data)

    def test_single_skill_list_matches_get_skill_modifier(self) -> None:
        """Defense: a list of one skill collapses to the per-skill
        helper. Same modifier as ``get_skill_modifier``."""
        skills_data = json.loads(SKILLS_JSON.read_text())
        bard = self._silver_tongue(skill_proficiencies=["deception"])
        assert bard.get_either_or_skill_modifier(
            ["deception"], skills_data
        ) == bard.get_skill_modifier("deception", skills_data)


class TestProficiency_Skills:
    """SRD § Playing the Game › Proficiency › Skill Proficiencies.

    > If a creature is proficient in a skill, the creature applies its
    > Proficiency Bonus to ability checks involving that skill.
    > Without proficiency in a skill, a creature can still make ability
    > checks involving that skill but doesn't add its Proficiency Bonus.
    """

    def test_skills_json_carries_all_eighteen_srd_skills(self) -> None:
        """Catalog parity: skills.json lists every SRD skill.

        The SRD Skills table names 18 skills. The data file is the
        canonical lookup for ability mapping.
        """
        skills: dict = json.loads(SKILLS_JSON.read_text())
        expected = {
            "acrobatics",
            "animal_handling",
            "arcana",
            "athletics",
            "deception",
            "history",
            "insight",
            "intimidation",
            "investigation",
            "medicine",
            "nature",
            "perception",
            "performance",
            "persuasion",
            "religion",
            "sleight_of_hand",
            "stealth",
            "survival",
        }
        assert set(skills.keys()) == expected

    def test_skills_json_ability_assignments_match_srd_table(self) -> None:
        """Catalog parity: every skill's ability matches the SRD table.

        Locked SRD Skills table:
        - Acrobatics, Sleight of Hand, Stealth → DEX
        - Athletics → STR
        - Animal Handling, Insight, Medicine, Perception, Survival → WIS
        - Arcana, History, Investigation, Nature, Religion → INT
        - Deception, Intimidation, Performance, Persuasion → CHA
        """
        skills: dict = json.loads(SKILLS_JSON.read_text())
        expected = {
            "acrobatics": "dex",
            "animal_handling": "wis",
            "arcana": "int",
            "athletics": "str",
            "deception": "cha",
            "history": "int",
            "insight": "wis",
            "intimidation": "cha",
            "investigation": "int",
            "medicine": "wis",
            "nature": "int",
            "perception": "wis",
            "performance": "cha",
            "persuasion": "cha",
            "religion": "int",
            "sleight_of_hand": "dex",
            "stealth": "dex",
            "survival": "wis",
        }
        for skill_id, want_ability in expected.items():
            assert skills[skill_id]["ability"] == want_ability, skill_id

    def test_non_proficient_skill_check_omits_pb(self) -> None:
        """Without skill proficiency the engine omits PB.

        Source-level binding at dnd-engine/dnd_engine/core/character.py:
        715-722. The non-proficient branch falls through to `modifier =
        ability_mod` only.
        """
        skills_data = json.loads(SKILLS_JSON.read_text())
        char = _make_fighter(level=5)  # PB = +3
        # Stealth (DEX): not proficient → DEX mod (+1), no PB
        assert char.get_skill_modifier("stealth", skills_data) == 1


class TestProficiency_DeterminingSkills:
    """SRD § Playing the Game › Proficiency › Determining Skills.

    > A character's starting skill proficiencies are determined at
    > character creation, and a monster's skill proficiencies appear in
    > its stat block.
    """

    def test_classes_declare_starting_skill_proficiency_choices(self) -> None:
        """Catalog parity: each class declares a skill-proficiency choice.

        The PC's "skill proficiencies are determined at character
        creation" requires the catalog to provide the menu. Tests the
        classes.json shape that drives the character factory.
        """
        classes: dict = json.loads(CLASSES_JSON.read_text())
        for class_id, cdata in classes.items():
            choice = cdata.get("skill_proficiencies")
            assert choice is not None, f"class {class_id} is missing skill_proficiencies"
            assert "choose" in choice and "from" in choice, (
                f"class {class_id}.skill_proficiencies must declare a {{choose, from}} block"
            )

    def test_monster_skill_proficiencies_appear_in_stat_block(self) -> None:
        """Catalog parity: monsters declare a `skills` block.

        The SRD says a monster's skill proficiencies "appear in its
        stat block." The catalog represents the stat block as JSON, and
        every monster entry must carry a `skills` key (even if empty).
        """
        monsters_path = DATA_DIR / "monsters.json"
        monsters: dict = json.loads(monsters_path.read_text())
        for monster_id, mdata in monsters.items():
            assert "skills" in mdata, f"monster {monster_id} is missing a `skills` block"


class TestProficiency_SavingThrows:
    """SRD § Playing the Game › Proficiency › Saving Throw Proficiencies.

    > Proficiency in a saving throw lets a character add their
    > Proficiency Bonus to saves that use a particular ability.
    > Each class gives proficiency in at least two saving throws.
    """

    def test_each_class_declares_at_least_two_save_proficiencies(self) -> None:
        """Catalog parity: every class lists >= 2 save proficiencies.

        Source: dnd_engine/data/srd/classes.json.
        """
        classes: dict = json.loads(CLASSES_JSON.read_text())
        for class_id, cdata in classes.items():
            saves = cdata.get("saving_throw_proficiencies", [])
            assert len(saves) >= 2, (
                f"class {class_id} declares {len(saves)} save "
                f"proficiencies; SRD requires at least 2"
            )

    def test_save_proficiency_grants_pb_to_that_ability_only(self) -> None:
        """Save proficiency is per-ability.

        Source-level binding at dnd-engine/dnd_engine/core/character.py:
        231-235 (only the matching `ability_short` adds PB).
        """
        char = _make_fighter(level=5)  # PB +3; proficient STR, CON
        # STR proficient
        assert char.get_saving_throw_modifier("str") == 6
        # WIS not proficient — even though it's a valid save
        # ability, it gets no PB.
        wis_mod = char.abilities.wis_mod
        assert char.get_saving_throw_modifier("wis") == wis_mod


class TestProficiency_Weapons:
    """SRD § Playing the Game › Proficiency › Equipment Proficiencies › Weapons.

    > Anyone can wield a weapon, but proficiency makes you better at
    > wielding it. If you have proficiency with a weapon, you add your
    > Proficiency Bonus to attack rolls you make with it.
    """

    def test_weapon_proficiency_adds_pb_to_attack(self) -> None:
        """Proficient weapon → PB added to attack roll.

        Source-level binding at dnd-engine/dnd_engine/core/character.py:
        408-412. Mirrors the SRD line "you add your Proficiency Bonus
        to attack rolls you make with it."
        """
        char = _make_fighter(level=5)  # PB +3, STR mod +3, proficient martial
        items_data = {
            "weapons": {
                "longsword": {
                    "weapon_type": "martial",
                    "category": "melee",
                    "properties": [],
                }
            }
        }
        assert char.get_attack_bonus("longsword", items_data) == 6

    def test_anyone_can_wield_a_weapon_without_proficiency(self) -> None:
        """Non-proficient wielders still get the ability modifier.

        Source-level binding at dnd-engine/dnd_engine/core/character.py:
        408-412 — the non-proficient branch returns `ability_mod` only,
        not zero. SRD: "Anyone can wield a weapon."
        """
        char = _make_fighter(level=5)
        char.weapon_proficiencies = []  # strip all
        items_data = {
            "weapons": {
                "longsword": {
                    "weapon_type": "martial",
                    "category": "melee",
                    "properties": [],
                }
            }
        }
        # STR mod (+3), no PB
        assert char.get_attack_bonus("longsword", items_data) == 3


class TestProficiency_Tools:
    """SRD § Playing the Game › Proficiency › Equipment Proficiencies › Tools.

    > If you have proficiency with a tool, you can add your Proficiency
    > Bonus to any ability check you make that uses the tool. If you
    > have proficiency in the skill that's also used with that check,
    > you have Advantage on the check too.
    """

    def test_character_tracks_tool_proficiencies(self) -> None:
        """`Character.tool_proficiencies` exists and is settable.

        Source-level binding at dnd-engine/dnd_engine/core/character.py:
        109. Locks the storage so the data is available the moment the
        engine starts consuming it.
        """
        char = _make_fighter(level=1)
        char.tool_proficiencies = ["thieves_tools"]
        assert "thieves_tools" in char.tool_proficiencies

    def test_tool_check_adds_pb_when_proficient(self) -> None:
        pytest.skip(
            "GAP: `Character.tool_proficiencies` is stored (dnd-engine/"
            "dnd_engine/core/character.py:109) but no `make_tool_check` "
            "or `is_proficient_with_tool` API exists. No ability-check "
            "surface adds PB based on the tool being used. Tracked by "
            "issue #483."
        )

    def test_tool_plus_skill_proficiency_grants_advantage(self) -> None:
        pytest.skip(
            "GAP: SRD: 'If you have proficiency in the skill that's "
            "also used with that check, you have Advantage on the "
            "check too.' `Character.make_skill_check` (dnd-engine/"
            "dnd_engine/core/character.py:726) accepts advantage flags "
            "but never auto-derives advantage from tool+skill overlap. "
            "Tracked by issue #483."
        )


class TestProficiency_Expertise:
    """SRD § Playing the Game › Proficiency › Expertise (multiplier example).

    The SRD line "Occasionally, a Proficiency Bonus might be multiplied
    or divided (doubled or halved, for example) before being added" is
    illustrated by the Expertise feature (referenced from this section
    and defined in Rules Glossary). `Character` supports it for skills.
    """

    def test_expertise_doubles_pb_for_skill(self) -> None:
        """Expertise in a skill doubles PB on that skill's check.

        Source-level binding at dnd-engine/dnd_engine/core/character.py:
        718-722. Locks the doubling so the SRD multiplier example has a
        callable proof.
        """
        skills_data = json.loads(SKILLS_JSON.read_text())
        abilities = Abilities(
            strength=10,
            dexterity=16,  # +3
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
        )
        rogue = Character(
            name="Pickpocket",
            character_class=CharacterClass.ROGUE,
            level=5,  # PB +3
            abilities=abilities,
            max_hp=20,
            ac=14,
            skill_proficiencies=["stealth"],
            expertise_skills=["stealth"],
        )
        # DEX mod (+3) + PB doubled (+6) = +9
        assert rogue.get_skill_modifier("stealth", skills_data) == 9

    def test_expertise_only_applies_when_already_proficient(self) -> None:
        """Expertise is a *multiplier* on PB, not a grant of PB.

        Source-level binding at dnd-engine/dnd_engine/core/character.py:
        718-722: the doubled-PB branch is inside the `if skill in
        self.skill_proficiencies:` block. A character listed in
        `expertise_skills` for a skill they aren't proficient in gets
        no PB at all. Mirrors the SRD's framing of expertise as
        "multiplying" the bonus, not creating it.
        """
        skills_data = json.loads(SKILLS_JSON.read_text())
        abilities = Abilities(
            strength=10,
            dexterity=16,  # +3
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
        )
        rogue = Character(
            name="Pickpocket",
            character_class=CharacterClass.ROGUE,
            level=5,  # PB +3
            abilities=abilities,
            max_hp=20,
            ac=14,
            skill_proficiencies=[],  # not proficient
            expertise_skills=["stealth"],  # but listed for expertise
        )
        # Just DEX mod (+3), no PB doubled or otherwise
        assert rogue.get_skill_modifier("stealth", skills_data) == 3
