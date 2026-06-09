# ABOUTME: SRD conformance audit for "Playing the Game > Saving Throws".
# ABOUTME: Cross-references docs/srd/playing-the-game/saving-throws.md against engine code.

"""SRD conformance: Saving Throws.

Maps every rule in `docs/srd/playing-the-game/saving-throws.md` to a
test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import inspect

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.systems.d20 import AdvantageState, D20Result

pytestmark = pytest.mark.srd(
    "playing-the-game/saving-throws.md",
    lines="866-946",
)


def _make_fighter(
    *,
    level: int = 1,
    abilities: Abilities | None = None,
    saving_throw_proficiencies: list[str] | None = None,
) -> Character:
    """Construct a minimal Fighter for save-modifier assertions."""
    if abilities is None:
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
        saving_throw_proficiencies=(
            saving_throw_proficiencies
            if saving_throw_proficiencies is not None
            else ["str", "con"]
        ),
    )


def _make_creature(ac: int = 12) -> Creature:
    """Construct a vanilla creature for the non-proficient save path."""
    abilities = Abilities(
        strength=8,
        dexterity=14,
        constitution=10,
        intelligence=10,
        wisdom=8,
        charisma=8,
    )
    return Creature(name="Goblin", max_hp=7, ac=ac, abilities=abilities)


class TestDefinition_TriggeredByEffect:
    """SRD § Playing the Game › Saving Throws › Definition.

    > A saving throw—also called a save—represents an attempt to
    > evade or resist a threat, such as a fiery explosion, a blast of
    > poisonous gas, or a spell trying to invade your mind. You don't
    > normally choose to make a save; you must make one because your
    > character or a monster (if you're the GM) is at risk. A save's
    > result is detailed in the effect that caused it.
    """

    def test_make_saving_throw_returns_documented_payload_shape(self):
        """`Character.make_saving_throw` returns success / roll / total / dc / ability.

        The SRD framing is that a save's result is "detailed in the
        effect that caused it." The engine's contract for surfacing
        that result is the dict returned by `make_saving_throw`. This
        test pins the field set so downstream effect handlers can rely
        on it.
        """
        fighter = _make_fighter()

        result = fighter.make_saving_throw(ability="con", dc=10)

        for key in ("success", "roll", "modifier", "total", "dc", "ability"):
            assert key in result, f"saving throw result missing field {key!r}"
        assert isinstance(result["success"], bool)
        assert result["dc"] == 10
        assert result["ability"] == "con"

    def test_creatures_can_be_compelled_to_save(self):
        """Monsters (`Creature`) also expose `make_saving_throw`.

        SRD: "...because your character or a monster (if you're the
        GM) is at risk." Both sides of the table must be able to be
        forced into a save by an effect.
        """
        creature = _make_creature()

        assert callable(getattr(creature, "make_saving_throw", None))

        result = creature.make_saving_throw(ability="dex", dc=10)
        assert "success" in result
        assert result["ability"] == "dex"


class TestDefinition_ChooseToFail:
    """SRD § Playing the Game › Saving Throws › Choose to Fail.

    > If you don't want to resist the effect, you can choose to fail
    > the save without rolling.
    """

    def test_save_target_can_opt_to_fail_without_rolling(self):
        """`auto_fail=True` short-circuits the save before any d20 roll.

        SRD: "If you don't want to resist the effect, you can choose
        to fail the save without rolling." Engine surface is an
        `auto_fail` kwarg on `Character.make_saving_throw` and
        `Creature.make_saving_throw`. When set, the methods return the
        same SRD-shaped result dict as the rolling path but with
        `success=False`, `roll=0`, and `total=modifier` — no d20 is
        rolled.
        """
        fighter = _make_fighter()

        result = fighter.make_saving_throw(
            ability="con", dc=10, auto_fail=True
        )

        assert result["success"] is False
        assert result["roll"] == 0
        assert result["ability"] == "con"
        assert result["dc"] == 10
        # All documented payload keys are still present so downstream
        # effect handlers don't have to special-case voluntary fails.
        for key in (
            "success",
            "roll",
            "modifier",
            "total",
            "dc",
            "ability",
            "circumstantial",
        ):
            assert key in result, f"auto_fail result missing field {key!r}"

        # Creatures (monsters) expose the same opt-in.
        creature = _make_creature()
        creature_result = creature.make_saving_throw(
            ability="dex", dc=15, auto_fail=True
        )
        assert creature_result["success"] is False
        assert creature_result["roll"] == 0
        assert creature_result["ability"] == "dex"
        assert creature_result["dc"] == 15


class TestAbilityModifier_NamedForAbility:
    """SRD § Playing the Game › Saving Throws › Ability Modifier.

    > Saving throws are named for the ability modifiers they use: a
    > Constitution saving throw, a Wisdom saving throw, and so on.
    > Different saving throws are used to resist different kinds of
    > effects, as shown on the Saving Throw Examples table.
    """

    def test_save_uses_named_ability_modifier(self):
        """Each named ability's modifier flows through to the save total.

        Spot-checks all six abilities: with no proficiency, the save's
        `modifier` field must equal the corresponding ability modifier
        from the `(score - 10) // 2` formula. This is the SRD's
        "named for the ability modifiers they use" clause made
        concrete.
        """
        abilities = Abilities(
            strength=18,
            dexterity=14,
            constitution=12,
            intelligence=10,
            wisdom=8,
            charisma=6,
        )
        fighter = _make_fighter(
            abilities=abilities,
            saving_throw_proficiencies=[],  # no profs, so modifier == ability mod
        )

        expected = {
            "str": 4,
            "dex": 2,
            "con": 1,
            "int": 0,
            "wis": -1,
            "cha": -2,
        }
        for ability, mod in expected.items():
            assert fighter.get_saving_throw_modifier(ability) == mod, (
                f"{ability} save modifier should equal ability mod {mod}"
            )

    def test_save_accepts_both_short_and_full_ability_names(self):
        """`get_saving_throw_modifier` accepts 'str' and 'strength'.

        The SRD names saves by their full ability ("Constitution
        saving throw"). The engine surface must accept both the
        catalogue-friendly short form (`con`) and the human-readable
        full form (`constitution`) so spell/monster data can use
        whichever reads better.
        """
        fighter = _make_fighter()

        # Same fighter, two names — same result.
        assert (
            fighter.get_saving_throw_modifier("str")
            == fighter.get_saving_throw_modifier("strength")
        )
        assert (
            fighter.get_saving_throw_modifier("cha")
            == fighter.get_saving_throw_modifier("charisma")
        )


class TestAbilityModifier_SaveExamplesTable:
    """SRD § Playing the Game › Saving Throws › Saving Throw Examples.

    > Saving Throw Examples
    > Strength — Physically resist direct force
    > Dexterity — Dodge out of harm's way
    > Constitution — Endure a toxic hazard
    > Intelligence — Recognize an illusion as fake
    > Wisdom — Resist a mental assault
    > Charisma — Assert your identity
    """

    def test_effects_default_to_srd_recommended_save_ability(self):
        pytest.skip(
            "GAP: The engine has no central mapping from effect "
            "category (force / dodge / poison / illusion / mental / "
            "identity) to its recommended save ability. Each spell "
            "and monster trait hardcodes its save in JSON "
            "(`dnd_engine/data/srd/spells.json`, "
            "`dnd_engine/data/srd/monsters.json`), so a content "
            "author can — and sometimes does — pick a save that "
            "doesn't match the SRD examples table. No validator "
            "checks this. The examples table is advisory, not "
            "normative, so this gap is low-severity but worth a "
            "lint-style audit. Tracked by issue #450."
        )


class TestProficiencyBonus_AppliedWhenProficient:
    """SRD § Playing the Game › Saving Throws › Proficiency Bonus.

    > You add your Proficiency Bonus to your saving throw if you have
    > proficiency in that kind of save. See "Proficiency" later in
    > "Playing the Game."
    """

    def test_proficient_save_adds_proficiency_bonus(self):
        """Fighter proficient in STR saves: modifier = STR + prof.

        STR 16 (+3) at level 1 (prof +2) with STR save proficiency:
        modifier = +3 + +2 = +5. Drops to +3 if proficiency leaks
        out, which is the regression this guards.
        """
        fighter = _make_fighter(saving_throw_proficiencies=["str", "con"])

        assert fighter.get_saving_throw_modifier("str") == 5

    def test_non_proficient_save_omits_proficiency_bonus(self):
        """Fighter NOT proficient in DEX saves: modifier = DEX only.

        DEX 14 (+2) with no DEX save proficiency: modifier = +2, not
        +4. SRD's "if you have proficiency in that kind of save" is
        a gate, not a default. (character.py:231-233)
        """
        fighter = _make_fighter(saving_throw_proficiencies=["str", "con"])

        assert fighter.get_saving_throw_modifier("dex") == 2

    def test_creature_save_does_not_apply_proficiency_bonus_by_default(self):
        """Vanilla `Creature.make_saving_throw` returns ability-mod only.

        Most monsters' base saves are just the ability modifier — the
        SRD only adds proficiency when the stat block explicitly
        lists a save proficiency. The base `Creature` class does not
        encode per-ability save proficiencies, so the returned
        modifier should equal the raw ability modifier for any
        ability. (creature.py:475-578)
        """
        creature = _make_creature()

        result = creature.make_saving_throw(ability="dex", dc=10)
        # DEX 14 → +2; with no proficiency the modifier must equal +2.
        assert result["modifier"] == 2

    def test_proficiency_bonus_scales_with_level_on_proficient_save(self):
        """Same fighter at higher level → larger prof bonus on proficient save.

        Level 1 (prof +2) STR-prof save: +3 + +2 = +5.
        Level 5 (prof +3) STR-prof save: +3 + +3 = +6.
        Level 9 (prof +4) STR-prof save: +3 + +3 + ... = +7.
        The proficiency-bonus table is the same one driving attack
        rolls; this is the save-side guard.
        """
        for lvl, expected in ((1, 5), (5, 6), (9, 7)):
            fighter = _make_fighter(
                level=lvl, saving_throw_proficiencies=["str"]
            )
            assert fighter.get_saving_throw_modifier("str") == expected


class TestDifficultyClass_SetByEffect:
    """SRD § Playing the Game › Saving Throws › Difficulty Class.

    > The Difficulty Class for a saving throw is determined by the
    > effect that causes it or by the GM. For example, if a spell
    > forces you to make a save, the DC is determined by the caster's
    > spellcasting ability and Proficiency Bonus. Monster abilities
    > that call for saves specify the DC.
    """

    def test_spell_save_dc_uses_caster_proficiency_and_spellcasting_ability(self):
        """`get_spell_save_dc()` = 8 + proficiency + spellcasting mod.

        This is the SRD's explicit spell-DC formula (the "example"
        cited in the rule text). Defends the formula at
        character.py:1532-1550 against drift.
        """
        src = inspect.getsource(Character.get_spell_save_dc)

        assert "8 + self.proficiency_bonus + ability_mod" in src, (
            "Spell save DC must equal 8 + proficiency bonus + "
            "spellcasting ability modifier per SRD."
        )

    def test_save_caller_supplies_dc_not_derived_from_target(self):
        """`make_saving_throw(dc=...)` requires the DC as a parameter.

        The SRD makes the DC the responsibility of the *effect*, not
        the target. Engine-side, that means the saver doesn't compute
        its own DC; the call site (spell handler, monster trait,
        trap, GM ruling) passes the DC in. This test pins the
        signature so a future refactor can't accidentally invert it.
        """
        sig = inspect.signature(Character.make_saving_throw)

        assert "dc" in sig.parameters, (
            "make_saving_throw must take the DC as a parameter — the "
            "SRD assigns the DC to the effect, not the saver."
        )
        # DC must be a required positional/keyword param (no default).
        assert sig.parameters["dc"].default is inspect.Parameter.empty

    def test_monster_ability_saving_throw_dc_is_carried_in_data(self):
        """Monster `saving_throw` entries specify the DC in monsters.json.

        SRD: "Monster abilities that call for saves specify the DC."
        Verifies the data-layer encoding — at least one monster
        action carries an explicit `dc` under its `saving_throw`
        block — so save-bearing monster abilities can be auditable
        from the JSON catalog without consulting code.
        """
        import json
        from pathlib import Path

        monsters_path = (
            Path(__file__).resolve().parents[3]
            / "dnd_engine"
            / "data"
            / "srd"
            / "monsters.json"
        )
        monsters = json.loads(monsters_path.read_text())

        with_save_dc = [
            (mid, action.get("name"), action["saving_throw"].get("dc"))
            for mid, mdata in monsters.items()
            for action in (mdata.get("actions") or [])
            if action.get("saving_throw") and "dc" in action["saving_throw"]
        ]

        assert with_save_dc, (
            "Expected at least one monster action carrying an explicit "
            "`saving_throw.dc` in monsters.json (e.g., ghoul Claws). "
            "SRD requires monster save abilities to specify their DC."
        )

    def test_save_success_uses_total_meets_or_exceeds_dc(self):
        """Meeting the DC is a success.

        SRD doesn't use "above the DC"; the standard reading and
        every official rules supplement treat ties as successes. This
        is the analogue of the `>= AC` rule on the attack side
        (#attack-rolls.md). Plan-08 slice 1 moved the `>=` check into
        :meth:`dnd_engine.systems.d20.D20Result.succeeds_against`, so
        the source-level guard now lives there. Behavior is also
        verified by a runtime check: a Character rolling exactly the
        DC succeeds.
        """
        src = inspect.getsource(D20Result.succeeds_against)
        assert ">=" in src, (
            "`D20Result.succeeds_against` must use `>=` so that a roll "
            "exactly equal to the DC/AC succeeds."
        )
        # Behavior: a roll exactly meeting the DC succeeds.
        result = D20Result(
            d20=10,
            total=10,
            advantage_state=AdvantageState.NORMAL,
            components={"ability_mod": 0, "proficiency": 0, "circumstantial": 0},
            rolls=(10,),
        )
        assert result.succeeds_against(10) is True
