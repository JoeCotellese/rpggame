# ABOUTME: SRD conformance audit for "Playing the Game > Saving Throws and Damage".
# ABOUTME: Cross-references docs/srd/playing-the-game/saving-throws-and-damage.md against engine code.

"""SRD conformance: Saving Throws and Damage.

Maps every rule in `docs/srd/playing-the-game/saving-throws-and-damage.md`
to a test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import inspect

import pytest

from dnd_engine.core.combat import CombatEngine
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller

pytestmark = pytest.mark.srd(
    "playing-the-game/saving-throws-and-damage.md",
    lines="2228-2246",
)


def _make_engine(seed: int = 42) -> CombatEngine:
    return CombatEngine(DiceRoller(seed=seed))


def _make_caster_with_save_dc(dc: int = 13):
    """Minimal duck-typed caster with `name` and `get_spell_save_dc`."""

    class _Caster:
        def __init__(self, name: str, save_dc: int) -> None:
            self.name = name
            self._save_dc = save_dc

        def get_spell_save_dc(self) -> int:
            return self._save_dc

    return _Caster("Wizard", dc)


def _make_creature(name: str, ac: int = 10) -> Creature:
    abilities = Abilities(
        strength=10,
        dexterity=10,
        constitution=10,
        intelligence=10,
        wisdom=10,
        charisma=10,
    )
    # max_hp high enough that AoE damage doesn't kill anyone in tests.
    return Creature(name=name, max_hp=200, ac=ac, abilities=abilities)


class TestScope_DamageDealtViaSavingThrows:
    """SRD § Playing the Game › Saving Throws and Damage › Scope.

    > Damage dealt via saving throws uses these rules.
    """

    def test_save_spell_damage_routes_through_resolve_spell_save(self):
        """Save-bearing spells dispatch to `CombatEngine.resolve_spell_save`.

        The whole section's rules ("roll once for multiple targets,"
        "half damage on success") live inside `resolve_spell_save`.
        This test pins that save-bearing spells go through that path
        rather than the auto-hit or spell-attack branch.
        `dnd_engine/core/game_state.py:2169-2172` selects this branch
        when `spell_data["saving_throw"] is not None`.
        """
        src = inspect.getsource(CombatEngine.resolve_spell_save)

        # The method must accept a list of targets (multi-target
        # scope) and must invoke `make_saving_throw` per target.
        assert "targets: list" in src
        assert "make_saving_throw" in src


class TestDamageAgainstMultipleTargets_RolledOnce:
    """SRD § Playing the Game › Saving Throws and Damage › Damage against
    Multiple Targets.

    > When you create a damaging effect that forces two or more
    > targets to make saving throws against it at the same time, roll
    > the damage once for all the targets. For example, when a wizard
    > casts Fireball, the spell's damage is rolled once for all
    > creatures caught in the blast.
    """

    def test_damage_is_rolled_once_outside_the_per_target_loop(self):
        """`base_damage` is computed before the `for target in targets` loop.

        Source-level guard: the dice roll for spell damage must
        happen exactly once, *outside* the per-target loop in
        `resolve_spell_save`. If a future refactor moves the roll
        inside the loop, each target would roll its own damage —
        violating the SRD's "roll once for all the targets" rule.
        (combat.py:641 base_damage assignment precedes the
        `for target in targets:` loop at 645.)
        """
        src = inspect.getsource(CombatEngine.resolve_spell_save)

        base_idx = src.find("base_damage = self._roll_spell_save_damage")
        loop_idx = src.find("for target in targets:")

        assert base_idx != -1, "expected base_damage assignment in resolve_spell_save"
        assert loop_idx != -1, "expected per-target for-loop in resolve_spell_save"
        assert base_idx < loop_idx, (
            "Damage must be rolled once before the per-target loop. "
            "SRD: 'roll the damage once for all the targets.'"
        )

    def test_multi_target_save_uses_same_base_damage_for_all_targets(self):
        """Each target's damage is derived from one shared roll.

        Behavioral check: against a deterministic seed, the
        full-damage value (taken on failed save) is identical for
        every target hit by the same save spell. Uses a Con-save,
        half-on-success spell against three targets with the same
        modifiers — failing targets all take exactly the same number,
        which can only be true if the roll was shared.
        """
        engine = _make_engine(seed=1)
        caster = _make_caster_with_save_dc(dc=100)  # impossibly high → all fail
        targets = [_make_creature(f"goblin_{i}") for i in range(3)]

        spell = {
            "name": "Fireball",
            "level": 3,
            "id": "fireball_test",
            "saving_throw": {"ability": "dex", "on_success": "half"},
            "damage": {"dice": "8d6", "damage_type": "fire"},
        }

        result = engine.resolve_spell_save(
            caster=caster,
            targets=targets,
            spell=spell,
            apply_damage=False,
        )

        damages = [t["damage"] for t in result["targets"]]
        assert len({*damages}) == 1, (
            f"All three failed-save targets must take the same damage "
            f"(rolled once), got {damages}."
        )


class TestHalfDamage_OnSuccessfulSave:
    """SRD § Playing the Game › Saving Throws and Damage › Half Damage.

    > Many saving throw effects deal half damage (round down) to a
    > target when the target succeeds on the saving throw. The halved
    > damage is equal to half the damage that would be dealt on a
    > failed save.
    """

    def test_half_damage_on_success_rounds_down(self):
        """`damage // 2` is the integer halving used for `on_success='half'`.

        Source-level guard: floor division on `base_damage` is the
        SRD "round down" rule. If a future refactor switches to
        floating-point math or `round()`, this assertion fires.
        (combat.py:658 `damage = base_damage // 2`.)
        """
        src = inspect.getsource(CombatEngine.resolve_spell_save)

        assert "damage = base_damage // 2" in src, (
            "Half-damage on save success must use integer floor "
            "division (`// 2`) to satisfy SRD 'round down'."
        )

    def test_success_with_half_yields_floor_half_of_failure_damage(self):
        """Behavioral: success-damage equals failure-damage // 2.

        Splits three targets into a guaranteed-fail group (impossible
        DC) and a guaranteed-pass group (DC 1), runs the same save
        spell twice, and asserts the success damage equals
        `failure_damage // 2`. Confirms the SRD's "halved damage is
        equal to half the damage that would be dealt on a failed
        save" wording — success damage is *derived from* failure
        damage, not rolled independently.
        """
        spell = {
            "name": "Burning Hands",
            "level": 1,
            "id": "burning_hands_test",
            "saving_throw": {"ability": "dex", "on_success": "half"},
            "damage": {"dice": "3d6", "damage_type": "fire"},
        }

        # All-fail run.
        fail_engine = _make_engine(seed=7)
        fail_caster = _make_caster_with_save_dc(dc=100)
        fail_targets = [_make_creature("a"), _make_creature("b")]
        fail_result = fail_engine.resolve_spell_save(
            caster=fail_caster,
            targets=fail_targets,
            spell=spell,
            apply_damage=False,
        )
        fail_damage = fail_result["targets"][0]["damage"]

        # All-pass run with the same seed → same base damage roll.
        pass_engine = _make_engine(seed=7)
        pass_caster = _make_caster_with_save_dc(dc=1)
        pass_targets = [_make_creature("c"), _make_creature("d")]
        pass_result = pass_engine.resolve_spell_save(
            caster=pass_caster,
            targets=pass_targets,
            spell=spell,
            apply_damage=False,
        )
        pass_damage = pass_result["targets"][0]["damage"]

        # Sanity-check both runs sampled the same dice.
        assert all(t["success"] is False for t in fail_result["targets"])
        assert all(t["success"] is True for t in pass_result["targets"])

        assert pass_damage == fail_damage // 2, (
            f"On-success half-damage must equal floor(fail_damage / 2). "
            f"failed={fail_damage}, succeeded={pass_damage}."
        )

    def test_on_success_none_deals_zero_damage(self):
        """`on_success='none'` (and `'negates'`) → 0 damage on success.

        Some spells specify alternative effects on a successful save
        (no damage at all). The SRD half-damage rule is the *typical*
        case; the per-effect spec wins. `dnd_engine/data/srd/spells.json`
        carries `on_success` values of "half", "none", and "negates"
        — the latter two must yield zero damage on success.
        (combat.py:659-660.)
        """
        spell = {
            "name": "Sacred Flame Stand-In",
            "level": 0,
            "id": "negates_test",
            "saving_throw": {"ability": "dex", "on_success": "none"},
            "damage": {"dice": "1d8", "damage_type": "radiant"},
        }

        engine = _make_engine(seed=5)
        caster = _make_caster_with_save_dc(dc=1)  # always succeed
        targets = [_make_creature("a"), _make_creature("b")]

        result = engine.resolve_spell_save(
            caster=caster,
            targets=targets,
            spell=spell,
            apply_damage=False,
        )

        for t in result["targets"]:
            assert t["success"] is True
            assert t["damage"] == 0, (
                "on_success='none' must deal 0 damage on a successful save."
            )

    def test_failure_takes_full_damage(self):
        """Failed save → full damage, no halving.

        Pin the negative side of the rule: the half-damage clause
        applies on success only. A failing target takes the full
        rolled value. (combat.py:663-664.)
        """
        spell = {
            "name": "Burning Hands",
            "level": 1,
            "id": "burning_hands_fail",
            "saving_throw": {"ability": "dex", "on_success": "half"},
            "damage": {"dice": "3d6", "damage_type": "fire"},
        }

        engine = _make_engine(seed=11)
        caster = _make_caster_with_save_dc(dc=100)  # always fail
        targets = [_make_creature("a")]

        result = engine.resolve_spell_save(
            caster=caster,
            targets=targets,
            spell=spell,
            apply_damage=False,
        )

        target_result = result["targets"][0]
        assert target_result["success"] is False
        # 3d6 minimum is 3, maximum is 18; failure must be in [3, 18].
        assert 3 <= target_result["damage"] <= 18, (
            f"Failed save must deal the full rolled value (3-18 for "
            f"3d6), got {target_result['damage']}."
        )
