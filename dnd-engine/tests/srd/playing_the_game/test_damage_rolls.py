# ABOUTME: SRD conformance audit for "Playing the Game > Damage Rolls".
# ABOUTME: Cross-references docs/srd/playing-the-game/damage-rolls.md against engine code.

"""SRD conformance: Damage Rolls.

Maps every rule in `docs/srd/playing-the-game/damage-rolls.md` to a test.
Real tests verify enforcement at the engine layer; stubs
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
from dnd_engine.core.combat import CombatEngine
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller

pytestmark = pytest.mark.srd(
    "playing-the-game/damage-rolls.md",
    lines="2205-2219",
)


ITEMS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "items.json"
)
SPELLS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "spells.json"
)


def _make_abilities(strength: int = 16, dexterity: int = 14) -> Abilities:
    return Abilities(
        strength=strength,
        dexterity=dexterity,
        constitution=15,
        intelligence=10,
        wisdom=12,
        charisma=8,
    )


def _make_character(strength: int = 16, dexterity: int = 14) -> Character:
    """Construct a Fighter for weapon-damage assertions."""
    return Character(
        name="TestHero",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=_make_abilities(strength=strength, dexterity=dexterity),
        max_hp=12,
        ac=16,
    )


class TestDamageRolls_RollAddDeal:
    """SRD § Playing the Game › Damage Rolls › Intro.

    > Each weapon, spell, and damaging monster ability specifies the
    > damage it deals. You roll the damage dice, add any modifiers, and
    > deal the damage to your target.
    """

    def test_calculate_damage_rolls_dice_and_applies_modifier(self) -> None:
        """`CombatEngine._calculate_damage` resolves NdS+M notation.

        The roll-dice-add-modifier-deal-damage primitive lives at
        `dnd_engine/core/combat.py:223-242`. The method parses the dice
        notation, rolls via the seeded `DiceRoller`, and returns the
        sum-with-modifier. Sanity bound: 1d8+3 always yields at least
        4 (min 1d8 = 1, plus +3).
        """
        engine = CombatEngine(DiceRoller(seed=42))
        damage = engine._calculate_damage("1d8+3", critical_hit=False)
        assert damage >= 4
        assert damage <= 11

    def test_resolve_attack_emits_damage_on_hit(self) -> None:
        """End-to-end: `resolve_attack` produces a numeric damage on hit.

        `dnd_engine/core/combat.py:91-221` is the public damage-rolling
        entry point: on hit it calls `_calculate_damage` and stuffs the
        result on the returned `AttackResult.damage`. This is the body
        of the SRD's "roll the damage dice ... and deal the damage."
        """
        engine = CombatEngine(DiceRoller(seed=42))
        attacker = Creature(name="A", max_hp=20, ac=16, abilities=_make_abilities())
        defender = Creature(name="D", max_hp=20, ac=1, abilities=_make_abilities())
        result = engine.resolve_attack(
            attacker=attacker,
            defender=defender,
            attack_bonus=5,
            damage_dice="1d8+3",
        )
        assert result.hit is True
        assert isinstance(result.damage, int)
        assert result.damage >= 1


class TestDamageRolls_ClampAtZero:
    """SRD § Playing the Game › Damage Rolls › Zero Floor.

    > If there's a penalty to the damage, it's possible to deal 0 damage
    > but not negative damage.
    """

    def test_negative_total_damage_is_clamped_to_zero(self) -> None:
        pytest.skip(
            "GAP: `CombatEngine._calculate_damage` "
            "(dnd_engine/core/combat.py:223-242) returns "
            "`damage_roll.total` directly with no `max(0, ...)` clamp. "
            "With a sufficiently negative ability modifier (e.g., 1d4-5 "
            "rolling a 1, total = -4), this method returns a negative "
            "value. `Creature.take_damage` "
            "(dnd_engine/core/creature.py:215-224) then computes "
            "`max(0, current_hp - amount)` which, with negative damage, "
            "becomes `max(0, current_hp + 4)` — the attack heals the "
            "defender. The SRD requires the damage value itself to be "
            "clamped at 0, not the post-application HP. Tracked by "
            "issue #490."
        )


class TestDamageRolls_AbilityModifierOnWeaponDamage:
    """SRD § Playing the Game › Damage Rolls › Ability modifier.

    > When attacking with a weapon, you add your ability modifier — the
    > same modifier used for the attack roll — to the damage roll.
    """

    def test_melee_weapon_damage_uses_strength_modifier(self) -> None:
        """`Character.get_damage_bonus` returns STR mod for a standard melee weapon.

        Source-level proof at `dnd_engine/core/character.py:414-448`:
        a non-finesse melee weapon routes to `str_mod`. With STR 16
        (mod +3) the damage bonus is +3, matching the attack-roll
        modifier from `get_attack_bonus_for_weapon`
        (`character.py:380-412`) — i.e., "the same modifier used for
        the attack roll."
        """
        character = _make_character(strength=16, dexterity=10)
        items_data = json.loads(ITEMS_JSON.read_text())
        # Longsword: standard melee, no finesse — STR-based.
        assert "longsword" in items_data["weapons"], (
            "Expected longsword in items.json for melee STR-mod assertion."
        )
        damage_bonus = character.get_damage_bonus("longsword", items_data)
        assert damage_bonus == 3

    def test_ranged_weapon_damage_uses_dexterity_modifier(self) -> None:
        """`Character.get_damage_bonus` returns DEX mod for a ranged weapon.

        `dnd_engine/core/character.py:443-445`: the `category == "ranged"`
        branch returns `dex_mod`. With DEX 14 (mod +2) the damage
        bonus is +2, matching the SRD's "same modifier used for the
        attack roll" for ranged weapons (`character.py:401-403`).
        """
        character = _make_character(strength=10, dexterity=14)
        items_data = json.loads(ITEMS_JSON.read_text())
        # Shortbow: ranged, no finesse — DEX-based.
        assert "shortbow" in items_data["weapons"], (
            "Expected shortbow in items.json for ranged DEX-mod assertion."
        )
        damage_bonus = character.get_damage_bonus("shortbow", items_data)
        assert damage_bonus == 2

    def test_finesse_weapon_damage_uses_higher_of_strength_or_dexterity(self) -> None:
        """`Character.get_damage_bonus` picks max(STR, DEX) for finesse.

        `dnd_engine/core/character.py:440-442`: finesse weapons branch
        on `max(str_mod, dex_mod)`. The SRD's "same modifier used for
        the attack roll" is honored because `get_attack_bonus_for_weapon`
        uses the same `max` (`character.py:398-400`).
        """
        character = _make_character(strength=10, dexterity=18)
        items_data = json.loads(ITEMS_JSON.read_text())
        # Rapier: finesse melee.
        assert "rapier" in items_data["weapons"], (
            "Expected rapier in items.json for finesse-weapon assertion."
        )
        damage_bonus = character.get_damage_bonus("rapier", items_data)
        # DEX 18 -> +4, beats STR 10 -> +0.
        assert damage_bonus == 4


class TestDamageRolls_SpellDamageDataDriven:
    """SRD § Playing the Game › Damage Rolls › Spell damage.

    > A spell tells you which dice to roll for damage and whether to add
    > any modifiers.
    """

    def test_spell_data_specifies_damage_dice(self) -> None:
        """spells.json carries `damage.dice` for damaging spells.

        Data-parity check: damaging spells in `dnd_engine/data/srd/spells.json`
        declare a `damage.dice` notation that the engine reads at
        `dnd_engine/core/game_state.py:2538-2541` (`_resolve_combat_auto_hit_spell`)
        and at the saving-throw spell resolver. This is the SRD's "a
        spell tells you which dice to roll" surface.
        """
        spells = json.loads(SPELLS_JSON.read_text())
        damaging = [
            sid
            for sid, sdata in spells.items()
            if isinstance(sdata.get("damage"), dict) and sdata["damage"].get("dice")
        ]
        assert damaging, (
            "Expected at least one spell in spells.json with damage.dice "
            "(e.g., magic_missile, fire_bolt, fireball)."
        )

    def test_spell_damage_resolution_uses_dice_field(self) -> None:
        """Engine reads spell `damage.dice` directly via DiceRoller.

        Source-level guard: `_resolve_combat_auto_hit_spell`
        (`dnd_engine/core/game_state.py:2522-2597`) pulls
        `damage_data.get("dice", "1d6")` and rolls it through
        `self.dice_roller.roll`. Wiring is unchanged from the SRD's
        intent: the spell's specified dice are what's rolled.
        """
        from dnd_engine.core.game_state import GameState

        src = inspect.getsource(GameState._resolve_combat_auto_hit_spell)
        assert "damage_data" in src and "dice" in src, (
            "Auto-hit spell resolver must consult `damage.dice` from "
            "spell data so the SRD's 'a spell tells you which dice to "
            "roll' rule is honored."
        )


class TestDamageRolls_FixedDamageNoModifier:
    """SRD § Playing the Game › Damage Rolls › Fixed-damage weapons.

    > Unless a rule says otherwise, you don't add your ability modifier
    > to a fixed damage amount that doesn't use a roll, such as the
    > damage of a Blowgun.
    """

    def test_fixed_damage_weapon_skips_ability_modifier(self) -> None:
        pytest.skip(
            "GAP: There is no fixed-damage weapon in the catalog and no "
            "code path that suppresses the ability modifier for one. "
            "`dnd_engine/data/srd/items.json:744-751` only carries "
            "'Blowgun Needles' (ammunition) — the Blowgun weapon itself "
            "is absent. `Character.get_damage_bonus` "
            "(dnd_engine/core/character.py:414-448) returns "
            "`ability_mod` unconditionally for ranged weapons; there is "
            "no `fixed_damage` branch returning 0. Tracked by "
            "issue #492."
        )


class TestDamageRolls_CatalogParity:
    """SRD § Playing the Game › Damage Rolls › Equipment & Spells refs.

    > See "Equipment" for weapons' damage dice and "Spells" for spells'
    > damage dice.
    """

    def test_weapons_catalog_declares_damage_dice(self) -> None:
        """items.json weapons carry a `damage` dice notation.

        Data-parity check: the SRD's pointer to "Equipment" for damage
        dice is honored by `dnd_engine/data/srd/items.json` — every
        weapon entry that is meant to deal damage carries a `damage`
        dice field, consumed at
        `dnd_engine/core/game_state.py:2219-2222` (`execute_player_attack`).
        """
        items = json.loads(ITEMS_JSON.read_text())
        weapons = items.get("weapons", {})
        assert weapons, "items.json must contain a `weapons` section."
        with_damage = [wid for wid, wdata in weapons.items() if wdata.get("damage")]
        assert with_damage, (
            "Expected at least one weapon in items.json with a `damage` "
            "dice notation (e.g., longsword: 1d8)."
        )

    def test_spells_catalog_declares_damage_dice_or_healing(self) -> None:
        """spells.json carries `damage.dice` or `healing.dice` on roll-bearing spells.

        Data-parity check: the SRD's pointer to "Spells" for damage
        dice is honored by `dnd_engine/data/srd/spells.json`. Spells
        that produce a roll (damage or healing) carry the dice notation
        the engine reads at game_state.py:2538-2541 / :1953-1955.
        """
        spells = json.loads(SPELLS_JSON.read_text())
        roll_bearing = [
            sid
            for sid, sdata in spells.items()
            if (isinstance(sdata.get("damage"), dict) and sdata["damage"].get("dice"))
            or (isinstance(sdata.get("healing"), dict) and sdata["healing"].get("dice"))
        ]
        assert roll_bearing, (
            "Expected at least one spell in spells.json with damage.dice "
            "or healing.dice (e.g., fire_bolt, cure_wounds)."
        )
