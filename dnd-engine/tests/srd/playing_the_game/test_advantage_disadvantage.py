# ABOUTME: SRD conformance audit for "Playing the Game > Advantage/Disadvantage".
# ABOUTME: Cross-references docs/srd/playing-the-game/advantage-disadvantage.md against engine code.

"""SRD conformance: Advantage / Disadvantage.

Maps every rule in `docs/srd/playing-the-game/advantage-disadvantage.md`
to a test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import inspect
import itertools

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.combat import CombatEngine
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller

pytestmark = pytest.mark.srd(
    "playing-the-game/advantage-disadvantage.md",
    lines="1002-1011",
)


def _make_fighter() -> Character:
    """Construct a minimal Fighter for advantage/disadvantage tests."""
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


def _script_d20_faces(monkeypatch, faces):
    """Force every ``DiceRoller`` to yield ``faces`` in order, then 1s.

    Patching the single ``_roll_die`` chokepoint makes advantage /
    disadvantage outcomes deterministic regardless of which roller a
    D20-test surface constructs internally: under advantage the primitive
    rolls two d20 and takes the higher, under disadvantage the lower. By
    scripting two distinct faces we can assert the *outcome* (which die
    reached the surfaced roll) rather than grepping the source. Extra
    rolls (e.g. damage dice after a hit) fall back to 1 and don't starve
    the iterator.
    """
    stream = itertools.chain(iter(faces), itertools.repeat(1))
    monkeypatch.setattr(DiceRoller, "_roll_die", lambda self, sides: next(stream))


class TestDefinition_ModifiesD20Test:
    """SRD § Playing the Game › Advantage/Disadvantage › Definition.

    > Sometimes a D20 Test is modified by Advantage or Disadvantage.
    > Advantage reflects the positive circumstances surrounding a d20
    > roll, while Disadvantage reflects negative circumstances.
    """

    def test_dice_roller_supports_advantage_flag(self):
        """`DiceRoller.roll` accepts an `advantage=True` flag.

        The advantage mechanic is implemented at the `DiceRoller` level
        (dnd-engine/dnd_engine/core/dice.py:85-140) and surfaced
        through the d20-test entry points that wrap it.
        """
        roller = DiceRoller(seed=42)
        result = roller.roll("1d20", advantage=True)
        assert result.advantage is True
        assert len(result.rolls) == 2

    def test_dice_roller_supports_disadvantage_flag(self):
        """`DiceRoller.roll` accepts a `disadvantage=True` flag.

        Same plumbing as advantage, opposite math
        (dnd-engine/dnd_engine/core/dice.py:39-44).
        """
        roller = DiceRoller(seed=42)
        result = roller.roll("1d20", disadvantage=True)
        assert result.disadvantage is True
        assert len(result.rolls) == 2

    def test_advantage_picks_higher_of_two_d20s(self):
        """`DiceRoll.total` returns `max(rolls) + modifier` with advantage.

        Implementation: `DiceRoll.total`
        (dnd-engine/dnd_engine/core/dice.py:39-46). Confirmed by
        construction: with seed=42 the two dice are deterministic and
        we assert the total equals their max.
        """
        roller = DiceRoller(seed=42)
        result = roller.roll("1d20", advantage=True)
        assert result.total == max(result.rolls)
        # Sanity: the modifier path is also exercised under +5.
        roller2 = DiceRoller(seed=42)
        with_mod = roller2.roll("1d20+5", advantage=True)
        assert with_mod.total == max(with_mod.rolls) + 5

    def test_disadvantage_picks_lower_of_two_d20s(self):
        """`DiceRoll.total` returns `min(rolls) + modifier` with disadvantage.

        Implementation: `DiceRoll.total`
        (dnd-engine/dnd_engine/core/dice.py:41-44). Same construction
        as the advantage test, opposite math.
        """
        roller = DiceRoller(seed=42)
        result = roller.roll("1d20", disadvantage=True)
        assert result.total == min(result.rolls)
        roller2 = DiceRoller(seed=42)
        with_mod = roller2.roll("1d20-2", disadvantage=True)
        assert with_mod.total == min(with_mod.rolls) - 2


class TestAcquisition_FromSpecialAbilitiesAndActions:
    """SRD § Playing the Game › Advantage/Disadvantage › Acquisition.

    > You usually acquire Advantage or Disadvantage through the use of
    > special abilities and actions.
    """

    def test_advantage_propagates_through_attack_roll(self):
        """`CombatEngine.resolve_attack` accepts and uses `advantage=True`.

        The attack-roll surface threads the flag down to the dice
        roller (`dnd-engine/dnd_engine/core/combat.py:130-133`). This
        is the primary site where "special abilities and actions"
        confer advantage on attacks (Pack Tactics, prone targets within
        5 ft, etc.).
        """
        src = inspect.getsource(CombatEngine.resolve_attack)
        assert "advantage=advantage" in src and "disadvantage=disadvantage" in src

    def test_advantage_propagates_through_saving_throw(self, monkeypatch):
        """`Character.make_saving_throw` rolls 2d20 and takes the higher.

        Used by spells / class features that grant advantage on a
        save (e.g., Dodge action gives advantage on DEX saves). Scripting
        two distinct d20 faces (5, 18) proves the flag reaches the dice:
        without advantage only the first die (5) would surface; with it,
        the higher (18) does.
        """
        fighter = _make_fighter()
        _script_d20_faces(monkeypatch, [5, 18])
        result = fighter.make_saving_throw(ability="con", dc=1, advantage=True)
        assert result["roll"] == 18

    def test_advantage_propagates_through_skill_check(self, monkeypatch):
        """`Character.make_skill_check` rolls 2d20 and takes the higher.

        Used by the Help action (advantage on the helped creature's next
        ability check). Same scripted-faces proof as the saving-throw
        case: advantage surfaces the higher of (5, 18).
        """
        fighter = _make_fighter()
        _script_d20_faces(monkeypatch, [5, 18])
        skills = {"athletics": {"ability": "str"}}
        result = fighter.make_skill_check("athletics", dc=1, skills_data=skills, advantage=True)
        assert result["roll"] == 18

    def test_disadvantage_propagates_through_all_three_surfaces(self, monkeypatch):
        """All three D20-test surfaces take the lower of 2d20 under disadvantage.

        Symmetric to the advantage tests above and driven end-to-end:
        each surface, given scripted faces (5, 18), must surface the
        lower die (5) — proving disadvantage reaches the dice, not just
        that the parameter exists.
        """
        # Saving throw
        fighter = _make_fighter()
        _script_d20_faces(monkeypatch, [5, 18])
        save = fighter.make_saving_throw(ability="con", dc=1, disadvantage=True)
        assert save["roll"] == 5

        # Skill check
        skill_fighter = _make_fighter()
        _script_d20_faces(monkeypatch, [5, 18])
        skills = {"athletics": {"ability": "str"}}
        check = skill_fighter.make_skill_check(
            "athletics", dc=1, skills_data=skills, disadvantage=True
        )
        assert check["roll"] == 5

        # Attack roll — low bonus vs AC 16 keeps it a miss, so no damage
        # dice are rolled and the scripted faces stay aligned to the d20.
        _script_d20_faces(monkeypatch, [5, 18])
        engine = CombatEngine(DiceRoller())
        attack = engine.resolve_attack(
            attacker=_make_fighter(),
            defender=_make_fighter(),
            attack_bonus=0,
            damage_dice="1d6",
            disadvantage=True,
        )
        assert attack.attack_roll == 5


class TestHeroicInspiration:
    """SRD § Playing the Game › Advantage/Disadvantage › Heroic Inspiration.

    > [Sidebar callout — full mechanic defined in Rules Glossary:]
    > spend Heroic Inspiration to reroll any d20 and use either result.
    """

    def test_character_carries_heroic_inspiration_state(self):
        """`Character.heroic_inspiration` is a one-shot flag.

        Fresh characters do not hold Heroic Inspiration. The
        `grant_heroic_inspiration` / `spend_heroic_inspiration`
        helpers (dnd-engine/dnd_engine/core/character.py) and the
        `has_heroic_inspiration` property gate the reroll path.
        """
        fighter = _make_fighter()
        assert fighter.has_heroic_inspiration is False
        assert fighter.grant_heroic_inspiration() is True
        assert fighter.has_heroic_inspiration is True
        assert fighter.spend_heroic_inspiration() is True
        assert fighter.has_heroic_inspiration is False

    def test_heroic_inspiration_can_be_spent_to_reroll_d20(self, monkeypatch):
        """The d20-test surface reroll uses the new roll, per SRD.

        With Heroic Inspiration held, a `make_skill_check` opting in
        via `use_heroic_inspiration=True` rerolls the d20 once and
        keeps the new result (not the better of the two).
        """
        from dnd_engine.core import character as character_module
        from dnd_engine.systems.d20 import AdvantageState, D20Result

        fighter = _make_fighter()
        fighter.grant_heroic_inspiration()

        rolls = iter([
            D20Result(
                d20=3,
                total=3 + fighter.proficiency_bonus + fighter.abilities.str_mod,
                advantage_state=AdvantageState.NORMAL,
                components={
                    "ability_mod": fighter.abilities.str_mod,
                    "proficiency": fighter.proficiency_bonus,
                    "circumstantial": 0,
                },
                rolls=(3,),
            ),
            D20Result(
                d20=18,
                total=18 + fighter.proficiency_bonus + fighter.abilities.str_mod,
                advantage_state=AdvantageState.NORMAL,
                components={
                    "ability_mod": fighter.abilities.str_mod,
                    "proficiency": fighter.proficiency_bonus,
                    "circumstantial": 0,
                },
                rolls=(18,),
            ),
        ])
        monkeypatch.setattr(
            character_module,
            "d20_test",
            lambda *a, **kw: next(rolls),
        )

        skills_data = {"athletics": {"ability": "str"}}
        result = fighter.make_skill_check(
            "athletics", dc=15, skills_data=skills_data,
            use_heroic_inspiration=True,
        )

        # SRD: "must use the new roll" — second roll wins, not max.
        assert result["roll"] == 18
        assert result["heroic_inspiration_spent"] is True

    def test_heroic_inspiration_is_consumed_on_use(self, monkeypatch):
        """Spending Heroic Inspiration clears the flag.

        A second check with `use_heroic_inspiration=True` after the
        flag is consumed does not reroll and reports no spend.
        """
        from dnd_engine.core import character as character_module
        from dnd_engine.systems.d20 import AdvantageState, D20Result

        fighter = _make_fighter()
        fighter.grant_heroic_inspiration()

        def make_result(d20: int) -> D20Result:
            return D20Result(
                d20=d20,
                total=d20 + fighter.proficiency_bonus + fighter.abilities.str_mod,
                advantage_state=AdvantageState.NORMAL,
                components={
                    "ability_mod": fighter.abilities.str_mod,
                    "proficiency": fighter.proficiency_bonus,
                    "circumstantial": 0,
                },
                rolls=(d20,),
            )

        rolls = iter([make_result(1), make_result(20), make_result(5)])
        monkeypatch.setattr(
            character_module,
            "d20_test",
            lambda *a, **kw: next(rolls),
        )

        skills_data = {"athletics": {"ability": "str"}}
        first = fighter.make_skill_check(
            "athletics", dc=15, skills_data=skills_data,
            use_heroic_inspiration=True,
        )
        assert first["heroic_inspiration_spent"] is True
        assert fighter.has_heroic_inspiration is False

        second = fighter.make_skill_check(
            "athletics", dc=15, skills_data=skills_data,
            use_heroic_inspiration=True,
        )
        assert second["heroic_inspiration_spent"] is False
        assert second["roll"] == 5


class TestSurfaceParity_NotPropagatedOnCreature:
    """SRD § Playing the Game › Advantage/Disadvantage › Creature parity.

    The SRD doesn't distinguish PCs from monsters for D20 Tests — a
    monster making a save under Bless / Bane gets the same
    advantage/disadvantage math. This test confirms the engine surface
    that monsters use also accepts the flag.
    """

    def test_creature_saving_throw_accepts_advantage(self):
        """`Creature.make_saving_throw` threads advantage to the roller.

        Monsters (non-Character) make saves via this method
        (dnd-engine/dnd_engine/core/creature.py:478-578). The flag
        passes through to `DiceRoller.roll`.
        """
        abilities = Abilities(
            strength=10,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
        )
        goblin = Creature(name="Goblin", max_hp=7, ac=13, abilities=abilities)
        result = goblin.make_saving_throw(ability="dex", dc=10, advantage=True)
        assert "roll" in result
        assert "total" in result
        assert isinstance(result["success"], bool)

    def test_creature_saving_throw_accepts_disadvantage(self):
        """`Creature.make_saving_throw` threads disadvantage."""
        abilities = Abilities(
            strength=10,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
        )
        goblin = Creature(name="Goblin", max_hp=7, ac=13, abilities=abilities)
        result = goblin.make_saving_throw(ability="dex", dc=10, disadvantage=True)
        assert "roll" in result
        assert isinstance(result["success"], bool)
