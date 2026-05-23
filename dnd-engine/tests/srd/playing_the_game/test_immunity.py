# ABOUTME: SRD conformance audit for "Playing the Game > Immunity".
# ABOUTME: Cross-references docs/srd/playing-the-game/immunity.md against engine code.

"""SRD conformance: Immunity.

Maps every rule in `docs/srd/playing-the-game/immunity.md` to a test.
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

from dnd_engine.core.combat import CombatEngine

pytestmark = pytest.mark.srd(
    "playing-the-game/immunity.md",
    lines="2287-2293",
)


MONSTERS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "monsters.json"
)


class TestImmunity_ToDamageType:
    """SRD § Playing the Game › Immunity › Damage-type immunity.

    > Immunity to a damage type means you don't take damage of that
    > type.
    """

    def test_damage_type_immunity_zeroes_damage(self):
        """A creature immune to a damage type takes 0 damage of that
        type from an attack that hits.

        SRD acceptance: a fire-immune bearded devil takes 0 damage from
        a fire-typed attack (e.g., Fire Bolt), regardless of the attack
        roll, because `_apply_damage_modifiers` zeroes the rolled
        damage in the chokepoint before it is applied to HP.
        """
        from dnd_engine.core.combat import CombatEngine
        from dnd_engine.core.creature import Abilities, Creature
        from dnd_engine.core.dice import DiceRoller

        attacker = Creature(
            name="Wizard",
            max_hp=20,
            ac=12,
            abilities=Abilities(
                strength=10,
                dexterity=10,
                constitution=10,
                intelligence=16,
                wisdom=10,
                charisma=10,
            ),
        )
        bearded_devil = Creature(
            name="Bearded Devil",
            max_hp=52,
            ac=13,
            abilities=Abilities(
                strength=16,
                dexterity=15,
                constitution=15,
                intelligence=9,
                wisdom=11,
                charisma=11,
            ),
        )
        # Mirror what `DataLoader.create_monster` attaches from the
        # bearded devil's monsters.json entry.
        bearded_devil.damage_immunities = ["fire", "poison"]

        engine = CombatEngine(DiceRoller(seed=1))
        # `attack_bonus=20` against AC 13 guarantees a hit so the
        # damage pipeline runs — the assertion is on the post-modifier
        # damage, not on hit/miss probability.
        result = engine.resolve_attack(
            attacker=attacker,
            defender=bearded_devil,
            attack_bonus=20,
            damage_dice="1d10",  # Fire Bolt at level 1
            damage_type="fire",
            apply_damage=True,
        )

        assert result.hit is True
        assert result.damage == 0, (
            "Fire-immune defender must take 0 fire damage (SRD: "
            "'Immunity to a damage type means you don't take damage of "
            "that type.')."
        )
        assert bearded_devil.current_hp == bearded_devil.max_hp, (
            "Immunity must prevent any HP loss from the matching type."
        )

    def test_damage_type_immunity_is_per_type(self):
        """Immunity is scoped per damage type — a fire-immune creature
        still takes full damage from a different type (e.g., cold).
        """
        from dnd_engine.core.combat import CombatEngine
        from dnd_engine.core.creature import Abilities, Creature
        from dnd_engine.core.dice import DiceRoller

        target = Creature(
            name="Fire-Immune Target",
            max_hp=100,
            ac=10,
            abilities=Abilities(
                strength=10,
                dexterity=10,
                constitution=10,
                intelligence=10,
                wisdom=10,
                charisma=10,
            ),
        )
        target.damage_immunities = ["fire"]

        engine = CombatEngine(DiceRoller(seed=1))

        fire_scaled = engine._apply_damage_modifiers(target, raw_damage=20, damage_type="fire")
        cold_scaled = engine._apply_damage_modifiers(target, raw_damage=20, damage_type="cold")

        assert fire_scaled == 0, "Fire-immune target must take 0 fire damage."
        assert cold_scaled == 20, (
            "Immunity is per-type — a fire-immune target takes full "
            "damage from other types (SRD scopes immunity to the "
            "named damage type)."
        )

    def test_monster_damage_immunities_field_is_consumed(self):
        """A monster's catalog `damage_immunities` zeroes damage of
        that type via the engine chokepoint.

        Per #461, `CombatEngine._apply_damage_modifiers` reads the
        Creature's `damage_immunities` list attribute (populated by
        `DataLoader.create_monster` from monsters.json). A bearded
        devil with `["fire", "poison"]` therefore takes 0 damage from
        a fire-typed attack without needing a manual condition.
        """
        from dnd_engine.core.combat import CombatEngine
        from dnd_engine.core.creature import Abilities, Creature
        from dnd_engine.core.dice import DiceRoller

        # Mirror what `DataLoader.create_monster` would attach for the
        # bearded devil (`monsters.json` ships `[fire, poison]`).
        abilities = Abilities(
            strength=16,
            dexterity=10,
            constitution=15,
            intelligence=9,
            wisdom=11,
            charisma=11,
        )
        bearded_devil = Creature(name="Bearded Devil", max_hp=52, ac=13, abilities=abilities)
        bearded_devil.damage_immunities = ["fire", "poison"]

        engine = CombatEngine(DiceRoller(seed=1))
        scaled = engine._apply_damage_modifiers(bearded_devil, raw_damage=22, damage_type="fire")

        assert scaled == 0, (
            "Catalog `damage_immunities` must zero damage of the "
            "matching type via the engine chokepoint (SRD: 'Immunity "
            "to a damage type means you don't take damage of that "
            "type.')."
        )


class TestImmunity_ToCondition:
    """SRD § Playing the Game › Immunity › Condition immunity.

    > Immunity to a condition means you aren't affected by it.
    """

    def test_creature_type_grants_condition_immunity(self):
        """`CombatEngine.resolve_spell_hp_pool` honors creature-type-
        based condition immunities for Sleep.

        Today this is the *only* honored condition-immunity path in
        the engine: undead and constructs are coded as immune to
        Sleep at `dnd-engine/dnd_engine/core/combat.py:843-864`
        (inside `resolve_spell_hp_pool`). Source-level guard so the
        path can't silently regress. The general saving-throw path
        (`CombatEngine._process_saving_throw_effect`, combat.py:371)
        does NOT consult any immunity table — see the gap stub below.
        """
        src = inspect.getsource(CombatEngine.resolve_spell_hp_pool)
        assert "immune_types" in src, (
            "HP-pool spell resolution (Sleep) must declare a list of "
            "creature-type immunities (SRD: 'Immunity to a condition "
            "means you aren't affected by it.')."
        )
        assert "creature_type" in src and "immune_targets" in src, (
            "HP-pool spell resolution must filter targets by creature-"
            "type immunity so immune creatures are not affected."
        )

    def test_general_saving_throw_path_consults_condition_immunity(self):
        """The saving-throw effect path must skip on-fail condition
        application when the defender is immune to that condition.

        SRD acceptance: a bearded devil (condition_immunities:
        [poisoned]) hit by an action that triggers a Constitution save
        on hit with on_fail condition "poisoned" must not receive the
        Poisoned condition, regardless of save success/failure. The
        guard lives on `Creature.add_condition` /
        `apply_condition_with_metadata` so any caller benefits.
        """
        from dnd_engine.core.combat import CombatEngine
        from dnd_engine.core.creature import Abilities, Creature
        from dnd_engine.core.dice import DiceRoller

        attacker = Creature(
            name="Bearded Devil Attacker",
            max_hp=52,
            ac=13,
            abilities=Abilities(
                strength=16,
                dexterity=15,
                constitution=15,
                intelligence=9,
                wisdom=11,
                charisma=11,
            ),
        )
        defender = Creature(
            name="Bearded Devil Defender",
            max_hp=52,
            ac=13,
            abilities=Abilities(
                strength=16,
                dexterity=15,
                constitution=15,
                intelligence=9,
                wisdom=11,
                charisma=11,
            ),
        )
        # Mirror what `DataLoader.create_monster` attaches from the
        # bearded devil's monsters.json entry.
        defender.condition_immunities = ["poisoned"]

        # Force the saving throw to fail by setting an impossibly high
        # DC; on a failure the on-fail condition would normally attach.
        saving_throw_data = {
            "trigger": "on_hit",
            "ability": "constitution",
            "dc": 99,
            "on_fail": {
                "condition": "poisoned",
                "duration_type": "rounds",
                "duration": 10,
                "allow_repeat_save": True,
                "repeat_timing": "end_of_turn",
            },
        }

        engine = CombatEngine(DiceRoller(seed=1))
        result = engine._process_saving_throw_effect(saving_throw_data, attacker, defender)

        assert result is not None
        assert result["save_result"]["success"] is False, (
            "DC 99 should force a failed save so the on-fail path runs."
        )
        assert result["condition_applied"] is None, (
            "Condition must not be applied to a defender immune to it "
            "(SRD: 'Immunity to a condition means you aren't affected "
            "by it.')."
        )
        assert not defender.has_condition("poisoned"), (
            "Defender immune to Poisoned must not have the condition attached after a failed save."
        )

    def test_monster_condition_immunities_field_is_consumed(self):
        """A monster's catalog `condition_immunities` blocks the
        matching condition from attaching via `Creature.add_condition`
        and `apply_condition_with_metadata`.

        Per #466, `DataLoader.create_monster` threads
        `condition_immunities` onto the Creature, and the Creature's
        condition-application APIs consult it via
        `Creature.is_immune_to_condition`. A bearded devil with
        `condition_immunities: [poisoned]` therefore cannot be made
        Poisoned, no matter who calls `add_condition`.
        """
        from dnd_engine.core.creature import Abilities, Creature

        abilities = Abilities(
            strength=16,
            dexterity=10,
            constitution=15,
            intelligence=9,
            wisdom=11,
            charisma=11,
        )
        bearded_devil = Creature(name="Bearded Devil", max_hp=52, ac=13, abilities=abilities)
        # Mirror what `DataLoader.create_monster` attaches from the
        # bearded devil's monsters.json entry.
        bearded_devil.condition_immunities = ["poisoned"]

        bearded_devil.add_condition("poisoned")
        assert not bearded_devil.has_condition("poisoned"), (
            "Catalog `condition_immunities` must block `add_condition` for matching conditions."
        )

        bearded_devil.apply_condition_with_metadata(
            condition="poisoned",
            duration_type="rounds",
            duration=10,
        )
        assert not bearded_devil.has_condition("poisoned"), (
            "Catalog `condition_immunities` must block "
            "`apply_condition_with_metadata` for matching conditions."
        )

    def test_condition_immunity_blocks_condition_application(self):
        """A central guard on `Creature` prevents matching conditions
        from attaching.

        Two sources are honored in parity with the damage-immunity
        path:
          1. Catalog field `condition_immunities` (list attribute)
          2. Condition flag `has_immunity_{condition}` (matches the
             existing `has_immunity_{type}` convention used for
             damage-type immunity).
        """
        from dnd_engine.core.creature import Abilities, Creature

        abilities = Abilities(
            strength=10,
            dexterity=10,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
        )

        # Source 1: catalog field.
        catalog_immune = Creature(name="Catalog Immune", max_hp=20, ac=10, abilities=abilities)
        catalog_immune.condition_immunities = ["paralyzed"]
        catalog_immune.apply_condition_with_metadata(
            condition="paralyzed",
            duration_type="rounds",
            duration=3,
        )
        assert not catalog_immune.has_condition("paralyzed"), (
            "Catalog field `condition_immunities` must block condition application."
        )

        # Source 2: condition-flag form.
        flag_immune = Creature(name="Flag Immune", max_hp=20, ac=10, abilities=abilities)
        flag_immune.add_condition("has_immunity_paralyzed")
        flag_immune.apply_condition_with_metadata(
            condition="paralyzed",
            duration_type="rounds",
            duration=3,
        )
        assert not flag_immune.has_condition("paralyzed"), (
            "Condition-flag `has_immunity_{condition}` must block "
            "condition application (parity with damage-immunity path)."
        )

        # Non-immune control: condition does attach normally.
        not_immune = Creature(name="Not Immune", max_hp=20, ac=10, abilities=abilities)
        not_immune.apply_condition_with_metadata(
            condition="paralyzed",
            duration_type="rounds",
            duration=3,
        )
        assert not_immune.has_condition("paralyzed"), (
            "Sanity check: a non-immune creature still receives the condition normally."
        )


class TestImmunity_DataParity:
    """SRD § Playing the Game › Immunity › Catalog data parity.

    Immunity rules rely on per-creature data. The catalog must declare
    the fields even ahead of engine enforcement so the data is
    available the moment the engine starts consuming it.
    """

    def test_at_least_one_monster_declares_damage_immunities(self):
        """Catalog includes at least one monster with damage immunity.

        Bearded Devil, Skeleton, Ghast, Ghoul, and Animated Armor are
        all expected to carry the field. The test asserts the catalog
        commitment, independent of whether the engine reads it.
        """
        monsters: dict = json.loads(MONSTERS_JSON.read_text())
        with_immunity = [mid for mid, mdata in monsters.items() if mdata.get("damage_immunities")]
        assert with_immunity, (
            "Expected at least one monster with `damage_immunities` "
            "in monsters.json (e.g., bearded_devil: fire, poison)."
        )

    def test_at_least_one_monster_declares_condition_immunities(self):
        """Catalog includes at least one monster with condition immunity.

        Bearded Devil ships `condition_immunities: [poisoned]`. Same
        rationale as the damage-immunity field check.
        """
        monsters: dict = json.loads(MONSTERS_JSON.read_text())
        with_immunity = [
            mid for mid, mdata in monsters.items() if mdata.get("condition_immunities")
        ]
        assert with_immunity, (
            "Expected at least one monster with `condition_immunities` "
            "in monsters.json (e.g., bearded_devil: poisoned)."
        )
