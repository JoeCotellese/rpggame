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
        pytest.skip(
            "GAP: damage-type immunity is not implemented anywhere. "
            "`systems/item_effects._apply_damage_effect` only halves "
            "for `has_resistance_{type}` — no `has_immunity_{type}` "
            "branch zeroes damage. `CombatEngine.resolve_attack` and "
            "`CombatEngine.resolve_spell_save` don't consult any per-"
            "type modifier table at all. The bearded devil's "
            "`damage_immunities: [fire, poison]` (monsters.json) is "
            "data-only. Tracked by issues #461 (damage_type pipeline "
            "wiring) and #464 (damage-type Immunity)."
        )

    def test_damage_type_immunity_is_per_type(self):
        pytest.skip(
            "GAP: depends on damage-type immunity being implemented "
            "first. The SRD scopes immunity per type — a fire-immune "
            "creature still takes full damage from other types. "
            "Tracked by issue #464."
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
        bearded_devil = Creature(
            name="Bearded Devil", max_hp=52, ac=13, abilities=abilities
        )
        bearded_devil.damage_immunities = ["fire", "poison"]

        engine = CombatEngine(DiceRoller(seed=1))
        scaled = engine._apply_damage_modifiers(
            bearded_devil, raw_damage=22, damage_type="fire"
        )

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
        pytest.skip(
            "GAP: `CombatEngine._process_saving_throw_effect` (dnd-"
            "engine/dnd_engine/core/combat.py:371) applies the on-fail "
            "condition (e.g., ghoul Paralyzed) directly via "
            "`defender.apply_condition_with_metadata` with no immunity "
            "check. The only honored condition-immunity path is the "
            "hard-coded Sleep creature-type list in "
            "`CombatEngine.resolve_spell_hp_pool` (combat.py:843-864). "
            "Tracked by issue #466."
        )

    def test_monster_condition_immunities_field_is_consumed(self):
        pytest.skip(
            "GAP: monsters.json `condition_immunities` is data-only "
            "for the catalog-driven path. The engine's only condition-"
            "immunity check is hard-coded to creature *type* (undead / "
            "construct → Sleep) at "
            "`dnd-engine/dnd_engine/core/combat.py:843-854`, not the "
            "per-monster `condition_immunities` list. A bearded "
            "devil's `condition_immunities: [poisoned]` is never "
            "consulted before applying the Poisoned condition. "
            "Tracked by issue #466."
        )

    def test_condition_immunity_blocks_condition_application(self):
        pytest.skip(
            "GAP: depends on the per-monster `condition_immunities` "
            "field being consumed. The general rule "
            "(`add_condition` / `apply_condition_with_metadata` in "
            "`dnd-engine/dnd_engine/core/creature.py`) attaches a "
            "condition unconditionally — there is no guard that "
            "skips application when the target is immune. Tracked "
            "by issue #466."
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
        with_immunity = [
            mid for mid, mdata in monsters.items() if mdata.get("damage_immunities")
        ]
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
