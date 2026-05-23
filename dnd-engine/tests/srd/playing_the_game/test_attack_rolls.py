# ABOUTME: SRD conformance audit for "Playing the Game > Attack Rolls".
# ABOUTME: Cross-references docs/srd/playing-the-game/attack-rolls.md against engine code.

"""SRD conformance: Attack Rolls.

Maps every rule in `docs/srd/playing-the-game/attack-rolls.md` to a
test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.combat import CombatEngine
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller

pytestmark = pytest.mark.srd(
    "playing-the-game/attack-rolls.md",
    lines="947-1001",
)


ITEMS_JSON = Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "items.json"


def _make_engine() -> CombatEngine:
    return CombatEngine(DiceRoller(seed=42))


def _make_combatants(defender_ac: int = 15) -> tuple[Creature, Creature]:
    abilities = Abilities(
        strength=16, dexterity=14, constitution=15, intelligence=10, wisdom=12, charisma=8
    )
    attacker = Creature(name="Attacker", max_hp=20, ac=16, abilities=abilities)
    defender = Creature(name="Defender", max_hp=7, ac=defender_ac, abilities=abilities)
    return attacker, defender


def _make_fighter(
    *,
    level: int = 1,
    strength: int = 16,
    dexterity: int = 14,
    weapon_proficiencies: list[str] | None = None,
) -> Character:
    """Construct a minimal Fighter for attack-bonus assertions."""
    abilities = Abilities(
        strength=strength,
        dexterity=dexterity,
        constitution=14,
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
        weapon_proficiencies=(
            weapon_proficiencies if weapon_proficiencies is not None else ["simple", "martial"]
        ),
    )


def _load_items() -> dict:
    return json.loads(ITEMS_JSON.read_text())


class TestHitThreshold_EqualsOrExceedsAC:
    """SRD § Playing the Game › Attack Rolls › Definition.

    > An attack roll determines whether an attack hits a target. An
    > attack roll hits if the roll equals or exceeds the target's
    > Armor Class.
    """

    def test_total_attack_equal_to_ac_hits(self):
        """`total_attack >= defender_ac` — equality counts as a hit.

        Asserts the comparison operator in `CombatEngine.resolve_attack`
        (combat.py:149) is `>=`, not `>`. A literal source-level guard
        is the most stable assertion because the dice roll is
        stochastic; the comparison itself is the invariant.
        """
        src = inspect.getsource(CombatEngine.resolve_attack)
        assert "total_attack >= defender_ac" in src, (
            "Hit threshold must use `>=` so that an attack roll equal "
            "to AC counts as a hit. SRD: 'equals or exceeds the "
            "target's Armor Class.'"
        )

    def test_attack_roll_below_ac_misses(self):
        """A roll well below AC misses — sanity check on the live path.

        Uses a deterministic seed and a high defender AC so the
        non-crit branch reliably misses, verifying the `hit` flag
        respects the threshold (and isn't always True).
        """
        engine = _make_engine()
        attacker, defender = _make_combatants(defender_ac=25)

        # Replay enough attacks that we see at least one non-crit miss.
        saw_miss = False
        for _ in range(50):
            result = engine.resolve_attack(
                attacker=attacker,
                defender=defender,
                attack_bonus=0,
                damage_dice="1d4",
            )
            if not result.critical_hit and not result.hit:
                saw_miss = True
                assert result.attack_roll + result.attack_bonus < defender.ac
                break

        assert saw_miss, (
            "Expected at least one non-crit miss against AC 25 with attack_bonus=0 in 50 attempts."
        )


class TestAbilityModifier_PerWeaponType:
    """SRD § Playing the Game › Attack Rolls › Ability Modifier.

    > The Attack Roll Abilities table shows which ability modifier to
    > use for different types of attack rolls.

    The SRD table maps melee weapons to Strength and ranged weapons to
    Dexterity by default; the Finesse property is the headline
    exception, covered in its own class below.
    """

    def test_melee_weapon_uses_strength_modifier(self):
        """Longsword (melee, non-finesse) uses STR for the attack bonus.

        Fighter with STR 16 (+3), DEX 14 (+2), prof +2, proficient in
        martial weapons: longsword bonus = +3 (STR) + +2 (prof) = +5.
        """
        fighter = _make_fighter(strength=16, dexterity=14)
        items = _load_items()

        assert fighter.get_attack_bonus("longsword", items) == 5

    def test_ranged_weapon_uses_dexterity_modifier(self):
        """Longbow (ranged) uses DEX for the attack bonus.

        Fighter with STR 16 (+3), DEX 14 (+2), prof +2, proficient in
        martial weapons: longbow bonus = +2 (DEX) + +2 (prof) = +4.
        """
        fighter = _make_fighter(strength=16, dexterity=14)
        items = _load_items()

        assert fighter.get_attack_bonus("longbow", items) == 4

    def test_ability_modifier_formula_matches_srd(self):
        """`Abilities.*_mod` matches the SRD `(score - 10) // 2` formula.

        Defends the underlying modifier formula that every attack roll
        (and saving throw, ability check, etc.) depends on.
        """
        a = Abilities(
            strength=10,
            dexterity=11,
            constitution=14,
            intelligence=8,
            wisdom=18,
            charisma=1,
        )

        assert a.str_mod == 0
        assert a.dex_mod == 0  # 11 → 0, not 1 (floor division)
        assert a.con_mod == 2
        assert a.int_mod == -1
        assert a.wis_mod == 4
        assert a.cha_mod == -5


class TestAbilityModifier_Finesse:
    """SRD § Playing the Game › Attack Rolls › Finesse exception.

    > Some features let you use different ability modifiers from
    > those listed. For example, the Finesse property (see
    > "Equipment") lets you use Strength or Dexterity with a weapon
    > that has that property.
    """

    def test_finesse_weapon_picks_higher_of_strength_or_dexterity(self):
        """Rapier (finesse) uses max(STR, DEX) for the attack bonus.

        Fighter with STR 12 (+1), DEX 16 (+3) and martial proficiency:
        rapier bonus = +3 (max of +1/+3) + +2 (prof) = +5. Inverting
        the scores would flip the chosen modifier; we test the
        DEX-higher case here and the STR-higher case in the companion
        below.
        """
        fighter = _make_fighter(strength=12, dexterity=16)
        items = _load_items()

        assert fighter.get_attack_bonus("rapier", items) == 5

    def test_finesse_weapon_uses_strength_when_higher(self):
        """Same rapier, swapped scores — uses STR when it's higher.

        Fighter with STR 18 (+4), DEX 10 (+0) and martial proficiency:
        rapier bonus = +4 (max of +4/+0) + +2 (prof) = +6.
        """
        fighter = _make_fighter(strength=18, dexterity=10)
        items = _load_items()

        assert fighter.get_attack_bonus("rapier", items) == 6


class TestProficiencyBonus_AddedWhenProficient:
    """SRD § Playing the Game › Attack Rolls › Proficiency Bonus.

    > You add your Proficiency Bonus to your attack roll when you
    > attack using a weapon you have proficiency with, as well as
    > when you attack with a spell.
    """

    def test_proficiency_bonus_formula_matches_srd(self):
        """`+2` at levels 1-4, `+3` at 5-8, `+4` at 9-12, etc.

        Defends the level-keyed proficiency bonus table that drives
        every proficient attack and save in the system.
        """
        for lvl in (1, 2, 3, 4):
            assert _make_fighter(level=lvl).proficiency_bonus == 2
        for lvl in (5, 6, 7, 8):
            assert _make_fighter(level=lvl).proficiency_bonus == 3
        assert _make_fighter(level=9).proficiency_bonus == 4
        assert _make_fighter(level=13).proficiency_bonus == 5

    def test_proficient_attack_includes_proficiency_bonus(self):
        """A martial-proficient fighter wielding a longsword adds prof.

        STR 16 (+3) + prof +2 = +5; dropping the +2 prof component
        would land at +3 — so a +5 result confirms the bonus was
        applied.
        """
        fighter = _make_fighter(strength=16, weapon_proficiencies=["martial"])
        items = _load_items()

        assert fighter.get_attack_bonus("longsword", items) == 5

    def test_non_proficient_attack_omits_proficiency_bonus(self):
        """A character lacking the weapon's proficiency doesn't add prof.

        Same fighter, but with `weapon_proficiencies=[]` (no martial,
        no simple). Longsword bonus = +3 (STR) only, no +2 prof. This
        is the SRD's negative side of the proficiency rule: prof is
        gated, not always-on. (character.py:395, 408-412)
        """
        fighter = _make_fighter(strength=16, weapon_proficiencies=[])
        items = _load_items()

        assert fighter.get_attack_bonus("longsword", items) == 3


class TestArmorClass_BaseFormula:
    """SRD § Playing the Game › Attack Rolls › Armor Class.

    > All creatures start with the same base AC calculation:
    > Base AC = 10 + the creature's Dexterity modifier
    > A creature's AC can then be modified by armor, magic items,
    > spells, and more.
    """

    def test_unarmored_ac_is_ten_plus_dex_mod(self):
        """`CharacterFactory.calculate_ac(None, dex_mod)` returns `10 + dex_mod`.

        Unit-tests the unarmored branch of the AC calculation
        (character_factory.py:211-213) with a sweep over positive,
        zero, and negative DEX modifiers.
        """
        for dex_mod in (-2, 0, 2, 5):
            assert CharacterFactory.calculate_ac(None, dex_mod) == 10 + dex_mod

    def test_armor_ac_overlays_base_with_dex_when_allowed(self):
        """Light/medium armor adds DEX on top of armor base.

        SRD wording is "modified by armor"; the engine encodes the
        per-armor-type DEX policy via the `ac_bonus_dex` data field.
        Leather (AC 11 base, DEX allowed) with DEX +3 → AC 14.
        """
        leather = {"ac": 11, "ac_bonus_dex": True}
        assert CharacterFactory.calculate_ac(leather, 3) == 14

    def test_heavy_armor_does_not_add_dex(self):
        """Heavy armor (e.g., chain mail) ignores DEX modifier.

        SRD's "modified by armor, magic items, spells, and more"
        clause is honored via per-armor-type rules; chain mail
        (AC 16, no DEX) with DEX +3 still yields AC 16.
        """
        chain_mail = {"ac": 16, "ac_bonus_dex": False}
        assert CharacterFactory.calculate_ac(chain_mail, 3) == 16


class TestArmorClass_OnlyOneBaseAC:
    """SRD § Playing the Game › Attack Rolls › Only One Base AC.

    > Some spells and class features give characters a different
    > way to calculate their AC. A character with multiple features
    > that give different ways to calculate AC must choose which one
    > to use; only one base calculation can be in effect for a
    > creature.
    """

    def test_only_one_base_ac_selection_is_enforced(self):
        pytest.skip(
            "LATENT: no engine support for alternate base-AC formulas, "
            "so the 'choose one' constraint cannot be violated today. "
            "The unarmored default (character_factory.calculate_ac) is "
            "the sole base-AC code path; there is no Mage Armor, "
            "Barbarian Unarmored Defense, Monk Unarmored Defense, or "
            "Draconic Resilience implementation that could compete. "
            "When the first alternate base-AC feature lands, this test "
            "becomes load-bearing: it must assert that activating one "
            "alt-AC formula deactivates any other on the same creature. "
            "Tracked by issue #418."
        )

    def test_layered_modifiers_are_not_base_ac_alternatives(self):
        """Effective-AC overlays (Shield spell, etc.) are not 'base' AC.

        Source-level guard: `Creature.ac` returns the stored `_base_ac`
        and the docstring explicitly directs callers to
        `GameState.get_effective_ac` for spell overlays. This
        separates the SRD 'base calculation' from layered, temporary
        AC modifiers, keeping the 'Only One Base AC' rule unviolated.
        """
        src = inspect.getsource(Creature.ac.fget)
        assert "_base_ac" in src
        assert "get_effective_ac" in src or "spell modifiers" in src.lower(), (
            "Creature.ac docstring must steer callers to the effective-"
            "AC API for overlay effects so 'base AC' stays singular."
        )


class TestRolling20Or1_NaturalTwentyAlwaysHits:
    """SRD § Playing the Game › Attack Rolls › Rolling 20 or 1.

    > If you roll a 20 on the d20 (called a "natural 20") for an
    > attack roll, the attack hits regardless of any modifiers or
    > the target's AC.
    """

    def test_natural_twenty_hits_against_unreachable_ac(self):
        """A nat 20 against AC 30 with attack_bonus=0 still hits.

        `total_attack` (0 + 20) is 10 short of AC; only the
        critical-hit override at combat.py:152-153 can turn this into
        a hit. Loops a deterministic seed until the nat-20 lands.
        """
        engine = _make_engine()
        attacker, defender = _make_combatants(defender_ac=30)

        for _ in range(200):
            result = engine.resolve_attack(
                attacker=attacker,
                defender=defender,
                attack_bonus=0,
                damage_dice="1d4",
            )
            if result.attack_roll == 20:
                assert result.critical_hit is True
                assert result.hit is True, "Natural 20 must hit regardless of modifiers or AC."
                return

        pytest.fail("Did not observe a natural 20 in 200 attacks.")


class TestRolling20Or1_NaturalOneAlwaysMisses:
    """SRD § Playing the Game › Attack Rolls › Rolling 20 or 1.

    > If you roll a 1 on the d20 (a "natural 1") for an attack roll,
    > the attack misses regardless of any modifiers or the target's
    > AC.
    """

    def test_natural_one_misses_against_trivial_ac(self):
        """A nat 1 with attack_bonus=+20 against AC 5 still misses.

        Even though `total_attack` (1 + 20 = 21) trivially clears AC
        5, the critical-miss override at combat.py:154-155 forces a
        miss. Loops until the nat-1 lands.
        """
        engine = _make_engine()
        attacker, defender = _make_combatants(defender_ac=5)

        for _ in range(200):
            result = engine.resolve_attack(
                attacker=attacker,
                defender=defender,
                attack_bonus=20,
                damage_dice="1d4",
            )
            if result.attack_roll == 1:
                assert result.hit is False, "Natural 1 must miss regardless of modifiers or AC."
                assert result.damage == 0
                return

        pytest.fail("Did not observe a natural 1 in 200 attacks.")
