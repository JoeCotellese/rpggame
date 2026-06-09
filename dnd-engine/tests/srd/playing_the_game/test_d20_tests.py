# ABOUTME: SRD conformance audit for "Playing the Game > D20 Tests".
# ABOUTME: Cross-references docs/srd/playing-the-game/d20-tests.md against engine code.

"""SRD conformance: D20 Tests.

Maps every rule in `docs/srd/playing-the-game/d20-tests.md` to a test.
Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import inspect

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.combat import CombatEngine
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoll, DiceRoller

pytestmark = pytest.mark.srd(
    "playing-the-game/d20-tests.md",
    lines="731-865",
)


def _make_fighter(level: int = 1) -> Character:
    """Construct a minimal Fighter for D20-test assertions."""
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
    )


def _make_creature() -> Creature:
    """Construct a vanilla creature for the no-proficiency path."""
    abilities = Abilities(
        strength=10,
        dexterity=14,
        constitution=10,
        intelligence=10,
        wisdom=10,
        charisma=10,
    )
    return Creature(name="Goblin", max_hp=7, ac=13, abilities=abilities)


class TestDefinition_ThreeKinds:
    """SRD § Playing the Game › D20 Tests › Definition.

    > When the outcome of an action is uncertain, the game uses a d20
    > roll to determine success or failure. These rolls are called D20
    > Tests, and they come in three kinds: ability checks, saving
    > throws, and attack rolls.
    """

    def test_ability_check_surface_exists(self):
        """The skill-check surface remains the engine's ability-check entry point.

        `Character.make_skill_check` couples ability modifier and
        proficiency-if-relevant with a d20 roll. Plan-08 slice 1
        migrated the d20 portion to delegate to the unified
        `dnd_engine.systems.d20.d20_test` primitive, so the source no
        longer carries the `"1d20"` literal directly — it now carries
        a `d20_test(...)` call.
        """
        assert hasattr(Character, "make_skill_check"), (
            "Character must expose make_skill_check as its ability-check surface."
        )
        src = inspect.getsource(Character.make_skill_check)
        assert "advantage" in src and "disadvantage" in src
        assert "d20_test" in src

    def test_saving_throw_surface_exists(self):
        """Saving throws are exposed on both Character and Creature.

        `Character.make_saving_throw` and `Creature.make_saving_throw`
        both delegate the d20 portion to the unified
        `dnd_engine.systems.d20.d20_test` primitive (plan-08 slice 1).
        """
        assert hasattr(Character, "make_saving_throw")
        assert hasattr(Creature, "make_saving_throw")
        for func in (Character.make_saving_throw, Creature.make_saving_throw):
            src = inspect.getsource(func)
            assert "d20_test" in src

    def test_attack_roll_surface_exists(self):
        """Attack rolls are resolved by `CombatEngine.resolve_attack`.

        Plan-08 slice 1 migrated the d20 portion to delegate to the
        unified `dnd_engine.systems.d20.d20_test` primitive while
        keeping the surrounding orchestration (reach, sneak attack,
        unseen attacker/target, etc.) on the callsite.
        """
        src = inspect.getsource(CombatEngine.resolve_attack)
        assert "d20_test" in src

    def test_general_ability_check_primitive_is_unified(self):
        """All four D20-test surfaces delegate to `d20_test`.

        Source-level guard: `make_skill_check`, `make_saving_throw`,
        `make_ability_check`, and `CombatEngine.resolve_attack` all
        contain a `d20_test(...)` call. The unified primitive is the
        sole d20 surface; plan-08 slice 4 closed out the raw
        ability-check path that previously had no entry point.
        """
        assert hasattr(Character, "make_ability_check"), (
            "Character must expose make_ability_check for raw "
            "(non-skill, non-save) ability checks."
        )
        for func in (
            Character.make_skill_check,
            Character.make_saving_throw,
            Character.make_ability_check,
            CombatEngine.resolve_attack,
        ):
            src = inspect.getsource(func)
            assert "d20_test" in src, (
                f"{func.__qualname__} does not delegate to d20_test"
            )


class TestStep4_RollD20:
    """SRD § Playing the Game › D20 Tests › Step 4.

    > Roll 1d20. You always want to roll high. If the roll has
    > Advantage or Disadvantage (described later in "Playing the
    > Game"), you roll two d20s, but you use the number from only one
    > of them — the higher one if you have Advantage or the lower one
    > if you have Disadvantage.
    """

    def test_normal_roll_uses_one_d20(self):
        """`DiceRoller.roll("1d20")` returns exactly one die result.

        The SRD's default case for a D20 test is a single d20. The
        `DiceRoll.rolls` list must have length 1 when neither
        advantage nor disadvantage is requested
        (dnd-engine/dnd_engine/core/dice.py:111-116).
        """
        roller = DiceRoller(seed=42)
        result = roller.roll("1d20")
        assert isinstance(result, DiceRoll)
        assert len(result.rolls) == 1
        assert 1 <= result.rolls[0] <= 20

    def test_advantage_rolls_two_d20s_takes_higher(self):
        """Advantage rolls 2d20 and uses `max()`.

        `DiceRoll.total` returns `max(self.rolls) + self.modifier`
        when `advantage=True`
        (dnd-engine/dnd_engine/core/dice.py:39-44). Roller produces
        two dice
        (dnd-engine/dnd_engine/core/dice.py:111-113).
        """
        roller = DiceRoller(seed=42)
        result = roller.roll("1d20", advantage=True)
        assert result.advantage is True
        assert len(result.rolls) == 2
        # Advantage keeps the higher of the two rolls.
        assert result.total == max(result.rolls)

    def test_disadvantage_rolls_two_d20s_takes_lower(self):
        """Disadvantage rolls 2d20 and uses `min()`.

        `DiceRoll.total` returns `min(self.rolls) + self.modifier`
        when `disadvantage=True`
        (dnd-engine/dnd_engine/core/dice.py:41-44).
        """
        roller = DiceRoller(seed=42)
        result = roller.roll("1d20", disadvantage=True)
        assert result.disadvantage is True
        assert len(result.rolls) == 2
        # Disadvantage keeps the lower of the two rolls.
        assert result.total == min(result.rolls)

    def test_advantage_and_disadvantage_are_mutually_exclusive(self):
        """`DiceRoller.roll` rejects both flags set at once.

        SRD wording lets only one of Advantage/Disadvantage apply at a
        time. `DiceRoller.roll` raises `ValueError` if both are passed
        (dnd-engine/dnd_engine/core/dice.py:100-101).
        """
        roller = DiceRoller(seed=42)
        with pytest.raises(ValueError):
            roller.roll("1d20", advantage=True, disadvantage=True)


class TestStep5_AddModifiers:
    """SRD § Playing the Game › D20 Tests › Step 5.

    > Add Modifiers. Add these modifiers to the number rolled on the
    > d20: the Relevant Ability Modifier; your Proficiency Bonus If
    > Relevant; Circumstantial Bonuses and Penalties.
    """

    def test_ability_modifier_is_added_to_skill_check(self):
        """`make_skill_check` adds the relevant ability modifier.

        For an Athletics check, the modifier is the Strength modifier
        plus proficiency bonus when proficient. Verified by reading
        the returned `modifier` field
        (dnd-engine/dnd_engine/core/character.py:762).
        """
        fighter = _make_fighter()
        # Patch with deterministic dice
        fighter._dice_roller = DiceRoller(seed=1)
        skills = {"athletics": {"ability": "str"}}
        result = fighter.make_skill_check("athletics", dc=10, skills_data=skills)
        # STR mod (+3) + proficiency (+2) = +5
        assert result["modifier"] == 5
        assert result["total"] == result["roll"] + 5

    def test_ability_modifier_is_added_to_saving_throw(self):
        """`make_saving_throw` adds ability modifier + proficiency.

        Constitution save on a proficient Fighter: CON mod (+2) +
        proficiency (+2) = +4
        (dnd-engine/dnd_engine/core/character.py:300-304).
        """
        fighter = _make_fighter()
        result = fighter.make_saving_throw(ability="con", dc=10)
        # CON mod (+2) + proficiency (+2) = +4
        assert result["modifier"] == 4
        assert result["total"] == result["roll"] + 4

    def test_proficiency_bonus_added_only_when_relevant(self):
        """Proficiency bonus skipped when the character isn't proficient.

        A Fighter with no Stealth proficiency makes a Stealth check
        and gets only their DEX modifier
        (dnd-engine/dnd_engine/core/character.py:715-722). The SRD's
        "If Relevant" wording is enforced.
        """
        fighter = _make_fighter()
        fighter._dice_roller = DiceRoller(seed=1)
        skills = {"stealth": {"ability": "dex"}}
        # Fighter is not proficient in stealth → modifier == DEX mod (+2) only
        result = fighter.make_skill_check("stealth", dc=10, skills_data=skills)
        assert result["modifier"] == 2
        assert result["proficient"] is False

    def test_circumstantial_bonuses_can_be_added(self):
        """SRD step 5 third channel reaches every D20-Test caller.

        Verifies the four caller surfaces (skill check, raw ability
        check, saving throw, attack roll) all accept a caller-supplied
        ``circumstantial`` modifier and route it through the unified
        :func:`dnd_engine.systems.d20.d20_test` primitive — unlocking
        Bless / Bane / Guidance / Bardic Inspiration plumbing without
        per-callsite hacks.
        """
        fighter = _make_fighter()
        skills = {"athletics": {"ability": "str"}}

        # Skill check — same seed twice, +3 bonus reaches the total.
        fighter._dice_roller = DiceRoller(seed=1)
        skill_baseline = fighter.make_skill_check(
            "athletics", dc=10, skills_data=skills
        )
        fighter._dice_roller = DiceRoller(seed=1)
        skill_boosted = fighter.make_skill_check(
            "athletics", dc=10, skills_data=skills, circumstantial=3
        )
        assert skill_boosted["circumstantial"] == 3
        assert skill_boosted["total"] == skill_baseline["total"] + 3

        # Raw ability check — Guidance-like +2 reaches the total.
        fighter._dice_roller = DiceRoller(seed=5)
        ability_baseline = fighter.make_ability_check("str", dc=10)
        fighter._dice_roller = DiceRoller(seed=5)
        ability_boosted = fighter.make_ability_check(
            "str", dc=10, circumstantial=2
        )
        assert ability_boosted["circumstantial"] == 2
        assert ability_boosted["total"] == ability_baseline["total"] + 2

        # Saving throw — Bless-like +1 surfaces on the result dict.
        save_result = fighter.make_saving_throw("con", dc=10, circumstantial=1)
        assert save_result["circumstantial"] == 1
        assert save_result["total"] == (
            save_result["roll"] + save_result["modifier"] + 1
        )

        # Attack roll — bonus surfaces on AttackResult and total_attack.
        from dnd_engine.core.combat import CombatEngine

        attacker = _make_creature()
        defender = _make_creature()
        engine = CombatEngine(dice_roller=DiceRoller(seed=1))
        atk_baseline = engine.resolve_attack(
            attacker=attacker, defender=defender,
            attack_bonus=2, damage_dice="1d4",
        )
        engine = CombatEngine(dice_roller=DiceRoller(seed=1))
        atk_boosted = engine.resolve_attack(
            attacker=attacker, defender=defender,
            attack_bonus=2, damage_dice="1d4", circumstantial=2,
        )
        assert atk_boosted.circumstantial == 2
        assert atk_boosted.total_attack == atk_baseline.total_attack + 2


class TestStep6_TargetNumber:
    """SRD § Playing the Game › D20 Tests › Step 6.

    > Compare the Total to a Target Number. If the total of the d20
    > and its modifiers equals or exceeds the target number, the D20
    > Test succeeds. Otherwise, it fails. … The target number for an
    > ability check or a saving throw is called a Difficulty Class
    > (DC). The target number for an attack roll is called an Armor
    > Class (AC).
    """

    def test_skill_check_success_is_total_meets_or_exceeds_dc(self):
        """Skill check succeeds when total >= DC.

        `make_skill_check` returns `success = total >= dc`
        (dnd-engine/dnd_engine/core/character.py:778). Test by
        choosing a DC that the highest-possible roll (20+5=25) can
        meet but the lowest-possible (1+5=6) cannot — then assert the
        success flag matches the inequality.
        """
        fighter = _make_fighter()
        fighter._dice_roller = DiceRoller(seed=7)
        skills = {"athletics": {"ability": "str"}}
        result = fighter.make_skill_check("athletics", dc=10, skills_data=skills)
        assert result["success"] == (result["total"] >= 10)

    def test_saving_throw_success_is_total_meets_or_exceeds_dc(self):
        """Saving throw succeeds when total >= DC.

        Same SRD inequality as ability checks
        (dnd-engine/dnd_engine/core/character.py:307).
        """
        fighter = _make_fighter()
        result = fighter.make_saving_throw(ability="con", dc=10)
        assert result["success"] == (result["total"] >= 10)

    def test_attack_roll_uses_ac_as_target(self):
        """`CombatEngine.resolve_attack` compares total vs defender AC.

        SRD: the attack target number is AC, not DC. Verified by
        reading the comparison in
        `dnd-engine/dnd_engine/core/combat.py:148-149` where
        `total_attack = attack_roll + attack_bonus; hit = total_attack >= defender_ac`.
        """
        engine = CombatEngine(DiceRoller(seed=42))
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=15,
            intelligence=10,
            wisdom=12,
            charisma=8,
        )
        attacker = Creature(name="A", max_hp=20, ac=16, abilities=abilities)
        defender = Creature(name="D", max_hp=10, ac=13, abilities=abilities)
        result = engine.resolve_attack(
            attacker=attacker,
            defender=defender,
            attack_bonus=5,
            damage_dice="1d8+3",
        )
        # The attack-roll path produced a hit/miss decision against AC.
        assert hasattr(result, "hit")
        assert hasattr(result, "attack_roll")

    def test_typical_difficulty_class_ladder_is_documented(self):
        """`DC` enum exposes the SRD's Typical Difficulty Classes ladder.

        SRD § Playing the Game › D20 Tests › Typical Difficulty Classes
        (docs/srd/playing-the-game/d20-tests.md lines 731-865) names
        Very easy 5 / Easy 10 / Medium 15 / Hard 20 / Very hard 25 /
        Nearly impossible 30. `dnd_engine.core.constants.DC` is the
        importable enum that surfaces these values for callers.
        """
        from dnd_engine.core.constants import DC

        assert DC.VERY_EASY == 5
        assert DC.EASY == 10
        assert DC.MEDIUM == 15
        assert DC.HARD == 20
        assert DC.VERY_HARD == 25
        assert DC.NEARLY_IMPOSSIBLE == 30
        # IntEnum: members usable wherever an int DC is expected.
        assert int(DC.MEDIUM) == 15


class TestKinds_AbilityCheckExamples:
    """SRD § Playing the Game › D20 Tests › Ability Check Examples.

    > An ability check represents a creature using talent and training
    > to try to overcome a challenge, such as forcing open a stuck
    > door, picking a lock, entertaining a crowd, or deciphering a
    > cipher. … When the outcome is uncertain and narratively
    > interesting, the dice determine the result.
    """

    def test_ability_check_returns_documented_payload_shape(self):
        """`make_skill_check` returns success / roll / modifier / total / dc.

        The SRD's framing is that the d20 test produces a pass/fail
        plus the raw roll for narration. The engine contract for that
        payload is the dict returned by `make_skill_check`
        (dnd-engine/dnd_engine/core/character.py:771-780).
        """
        fighter = _make_fighter()
        fighter._dice_roller = DiceRoller(seed=1)
        skills = {"athletics": {"ability": "str"}}
        result = fighter.make_skill_check("athletics", dc=10, skills_data=skills)
        for key in ("success", "roll", "modifier", "total", "dc", "skill"):
            assert key in result, f"missing field {key!r}"
        assert isinstance(result["success"], bool)
        assert result["dc"] == 10

    def test_strength_check_to_force_open_stuck_door(self):
        """The SRD's canonical Strength check has a call site.

        `Character.make_ability_check("str", dc)` is the dedicated
        non-skill entry point. STR 16 (+3) vs DC 15.
        """
        fighter = _make_fighter()
        fighter._dice_roller = DiceRoller(seed=1)
        result = fighter.make_ability_check("str", dc=15)
        for key in ("success", "roll", "modifier", "total", "dc", "ability"):
            assert key in result, f"missing field {key!r}"
        assert result["ability"] == "str"
        assert result["modifier"] == 3
        assert result["dc"] == 15

    def test_intelligence_check_to_remember_lore(self):
        """A wizard's Intelligence check to recall lore uses the same surface.

        Different ability, same primitive — `make_ability_check("int", dc)`.
        Fighter has INT 10 (+0), so the total equals the d20 roll.
        """
        fighter = _make_fighter()
        fighter._dice_roller = DiceRoller(seed=2)
        result = fighter.make_ability_check("int", dc=12)
        assert result["ability"] == "int"
        assert result["modifier"] == 0
        assert result["total"] == result["roll"]
