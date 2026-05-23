# ABOUTME: SRD conformance audit for "Playing the Game > Making an Attack".
# ABOUTME: Cross-references docs/srd/playing-the-game/making-an-attack.md against engine code.

"""SRD conformance: Making an Attack.

Maps every rule in `docs/srd/playing-the-game/making-an-attack.md` to a
test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

This doc is the *procedural wrapper* for an attack — the four-step
recipe (choose a target, determine modifiers, resolve the attack, apply
effects), plus the Unseen Attackers / Targets carve-outs and Cover.
Rules that overlap with `attack-rolls.md` (the d20 mechanics
themselves) are exercised in `test_attack_rolls.py`; the tests here
assert that the procedural seam *exists*, not that the dice math is
right.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import inspect

import pytest

from dnd_engine.core.combat import CombatEngine
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller

pytestmark = pytest.mark.srd(
    "playing-the-game/making-an-attack.md",
    lines="1975-2051",
)


def _make_engine_and_combatants() -> tuple[CombatEngine, Creature, Creature]:
    """Two-creature fixture mirroring tests/test_combat.py conventions."""
    engine = CombatEngine(DiceRoller(seed=42))
    abilities = Abilities(
        strength=16,
        dexterity=14,
        constitution=15,
        intelligence=10,
        wisdom=12,
        charisma=8,
    )
    attacker = Creature(name="Attacker", max_hp=20, ac=16, abilities=abilities)
    defender = Creature(name="Defender", max_hp=7, ac=13, abilities=abilities)
    return engine, attacker, defender


class TestMakingAnAttack_Intro:
    """SRD § Playing the Game › Making an Attack › Intro.

    > When you take the Attack action, you make an attack. Some other
    > actions, Bonus Actions, and Reactions also let you make an attack.
    > Whether you strike with a Melee weapon, fire a Ranged weapon, or
    > make an attack roll as part of a spell, an attack has the
    > following structure.
    """

    def test_resolve_attack_is_the_single_attack_surface(self) -> None:
        """`CombatEngine.resolve_attack` is the one procedural surface.

        The SRD's framing — every attack (weapon, ranged, spell) flows
        through the same four-step recipe — is honored by routing every
        attack form through the same engine entry point at
        `dnd-engine/dnd_engine/core/combat.py:91`. Asserts the callable
        exists and accepts the rule-shaped inputs (attacker, defender,
        bonus, damage dice).
        """
        engine, attacker, defender = _make_engine_and_combatants()
        result = engine.resolve_attack(
            attacker=attacker,
            defender=defender,
            attack_bonus=5,
            damage_dice="1d8+3",
        )
        # Result carries the four-step output shape: roll, hit decision,
        # damage. (Step-by-step assertions live in the per-step classes
        # below.)
        assert hasattr(result, "attack_roll")
        assert hasattr(result, "hit")
        assert hasattr(result, "damage")


class TestUnseenAttackersAndTargets_TargetCannotBeSeen:
    """SRD § Playing the Game › Making an Attack › Unseen Targets.

    > When you make an attack roll against a target you can't see, you
    > have Disadvantage on the roll. This is true whether you're
    > guessing the target's location or targeting a creature you can
    > hear but not see.
    """

    def test_engine_accepts_disadvantage_flag_for_unseen_target(self) -> None:
        """`resolve_attack(disadvantage=True)` is the consumption seam.

        The d20 plumbing exists (combat.py:122-132). What's missing is
        the *deriver* — no code path inspects "attacker can see
        defender" and flips this flag. So this test confirms only the
        consumption seam; the deriver gap is the skip below.
        """
        engine, attacker, defender = _make_engine_and_combatants()
        result = engine.resolve_attack(
            attacker=attacker,
            defender=defender,
            attack_bonus=5,
            damage_dice="1d8+3",
            disadvantage=True,
        )
        assert result.disadvantage is True
        assert 1 <= result.attack_roll <= 20

    def test_engine_auto_disadvantages_attack_against_unseen_target(self) -> None:
        pytest.skip(
            "GAP: nothing in the engine derives disadvantage from "
            "attacker-target visibility. `CombatEngine.resolve_attack` "
            "(dnd-engine/dnd_engine/core/combat.py:91) takes "
            "`disadvantage` as a flag but no caller computes it from "
            "the defender's visibility to the attacker. The only "
            "visibility-aware helper is "
            "dnd-engine/dnd_engine/systems/ranged_attacks.py:24 "
            "(`is_close_combat_ranged_disadvantage`), which is the "
            "symmetric case (enemy can see *attacker*). Tracked by "
            "issue #475."
        )


class TestUnseenAttackersAndTargets_TargetLocationMiss:
    """SRD § Playing the Game › Making an Attack › Targeting a Location.

    > If the target isn't in the location you targeted, you miss.
    """

    def test_attack_at_empty_location_resolves_as_a_miss(self) -> None:
        pytest.skip(
            "GAP: there is no location-targeting attack surface. "
            "`GameState.execute_player_attack` "
            "(dnd-engine/dnd_engine/core/game_state.py:2182) always "
            "takes a `target: Creature` — you cannot guess a square and "
            "have the engine produce an automatic miss if the creature "
            "isn't actually there. The closest analog is the location-"
            "untargeted miss in `resolve_attack`, which only handles "
            "the dice case. Tracked by issues #477 (location/object "
            "target support) and #475 (visibility-driven attack "
            "modifiers)."
        )


class TestUnseenAttackersAndTargets_AttackerCannotBeSeen:
    """SRD § Playing the Game › Making an Attack › Unseen Attacker.

    > When a creature can't see you, you have Advantage on attack rolls
    > against it.
    """

    def test_engine_accepts_advantage_flag_for_unseen_attacker(self) -> None:
        """`resolve_attack(advantage=True)` is the consumption seam.

        Same shape as the unseen-target disadvantage seam above; the
        d20 mechanism honors the flag (combat.py:122-132) but no
        derivation flips it. Symmetric-pair check with
        `TestUnseenAttackersAndTargets_TargetCannotBeSeen`.
        """
        engine, attacker, defender = _make_engine_and_combatants()
        result = engine.resolve_attack(
            attacker=attacker,
            defender=defender,
            attack_bonus=5,
            damage_dice="1d8+3",
            advantage=True,
        )
        assert result.advantage is True
        assert 1 <= result.attack_roll <= 20

    def test_engine_auto_advantages_attack_when_target_cannot_see_attacker(self) -> None:
        pytest.skip(
            "GAP: nothing derives advantage from defender-cannot-see-"
            "attacker. The Blinded condition exists "
            "(dnd-engine/dnd_engine/core/creature.py — `add_condition`) "
            "and the ranged-in-close-combat helper "
            "(`dnd-engine/dnd_engine/systems/ranged_attacks.py:71`) "
            "already checks `enemy.has_condition('blinded')` to *skip* "
            "the disadvantage rule, but no symmetric path uses Blinded "
            "to *grant* advantage to the attacker on attacks against "
            "that blinded defender. Tracked by issue #475."
        )


class TestUnseenAttackersAndTargets_HiddenAttackerRevealed:
    """SRD § Playing the Game › Making an Attack › Hidden Attacker Reveal.

    > If you are hidden when you make an attack roll, you give away
    > your location when the attack hits or misses.
    """

    def test_hidden_attacker_loses_hidden_state_after_resolving_attack(self) -> None:
        pytest.skip(
            "GAP: there is no hidden-attacker state to lose. The Hide "
            "action is unimplemented (issue #443) and "
            "`CombatEngine.resolve_attack` "
            "(dnd-engine/dnd_engine/core/combat.py:91) has no post-roll "
            "hook that would clear a 'hidden' flag on the attacker. "
            "Tracked by issue #443 (Hide action / hidden state) and "
            "issue #475 (reveal hook on resolve_attack)."
        )


class TestAttackStructure_Step1_ChooseATarget:
    """SRD § Playing the Game › Making an Attack › Step 1: Choose a Target.

    > Pick a target within your attack's range: a creature, an object,
    > or a location.
    """

    def test_engine_accepts_a_creature_target(self) -> None:
        """Creature is the supported target shape today.

        The Step-1 input that *is* implemented: `resolve_attack`
        accepts a `defender: Creature`. This is the procedural seam;
        the dice math is tested in `test_attack_rolls.py`.
        """
        engine, attacker, defender = _make_engine_and_combatants()
        result = engine.resolve_attack(
            attacker=attacker,
            defender=defender,
            attack_bonus=5,
            damage_dice="1d8+3",
        )
        assert result.defender_name == "Defender"

    def test_engine_accepts_an_object_target(self) -> None:
        pytest.skip(
            "GAP: Step 1 allows targeting an *object*, but the engine "
            "only accepts `Creature` defenders. `CombatEngine."
            "resolve_attack` (dnd-engine/dnd_engine/core/combat.py:91) "
            "is typed `defender: Creature` and "
            "`GameState.execute_player_attack` "
            "(dnd-engine/dnd_engine/core/game_state.py:2182) requires "
            "`target: Creature`. No object/door/lock HP-pool target "
            "shape exists. Tracked by issue #477."
        )

    def test_engine_accepts_a_location_target(self) -> None:
        pytest.skip(
            "GAP: Step 1 allows targeting a *location* (used to guess "
            "an unseen creature's square). The engine has no location-"
            "targeting surface; `execute_player_attack` requires a "
            "`Creature` target. Tracked by issues #477 (target shape) "
            "and #475 (the location-miss consequence)."
        )

    def test_engine_enforces_attack_range_at_choose_target_step(self) -> None:
        pytest.skip(
            "GAP: the engine layer does not enforce 'within your "
            "attack's range' at Step 1. Range rejection lives at the "
            "client layer "
            "(client-2d/src/client_2d/session.py:982 and "
            "dnd-engine/dnd_engine/scenarios/script_executor.py:207); "
            "see also the ranged-attacks audit "
            "(`tests/srd/playing_the_game/test_ranged_attacks.py` "
            "`TestRange_TwoRangeWeapons::"
            "test_attack_beyond_long_range_is_rejected_by_engine`). "
            "A new third-party client would silently skip the rule."
        )


class TestAttackStructure_Step2_DetermineModifiers:
    """SRD § Playing the Game › Making an Attack › Step 2: Determine Modifiers.

    > The GM determines whether the target has Cover (see the next
    > section) and whether you have Advantage or Disadvantage against
    > the target. In addition, spells, special abilities, and other
    > effects can apply penalties or bonuses to your attack roll.
    """

    def test_attack_bonus_is_an_input_to_resolve_attack(self) -> None:
        """`attack_bonus` is the Step-2 "penalties or bonuses" seam.

        The SRD's "spells, special abilities, and other effects can
        apply penalties or bonuses to your attack roll" carve-out is
        realized by the `attack_bonus` integer parameter on
        `CombatEngine.resolve_attack` (combat.py:91). Asserting that
        the parameter exists and feeds the total attack defends Step 2
        from accidental refactor.
        """
        sig = inspect.signature(CombatEngine.resolve_attack)
        assert "attack_bonus" in sig.parameters
        engine, attacker, defender = _make_engine_and_combatants()
        result = engine.resolve_attack(
            attacker=attacker,
            defender=defender,
            attack_bonus=7,
            damage_dice="1d8+3",
        )
        assert result.attack_bonus == 7
        assert result.total_attack == result.attack_roll + 7

    def test_advantage_and_disadvantage_are_inputs_to_resolve_attack(self) -> None:
        """`advantage` / `disadvantage` are the Step-2 adv/disadv seams.

        The SRD's "whether you have Advantage or Disadvantage against
        the target" half of Step 2 is realized by the two flags on
        `resolve_attack`. Dice-mechanics correctness is covered in
        `tests/srd/playing_the_game/test_attack_rolls.py`; this test
        is the procedural seam.
        """
        sig = inspect.signature(CombatEngine.resolve_attack)
        assert "advantage" in sig.parameters
        assert "disadvantage" in sig.parameters

    def test_cover_is_an_input_to_step_2(self) -> None:
        pytest.skip(
            "GAP: Cover is the headline Step-2 modifier, and it is not "
            "implemented anywhere. `CombatEngine.resolve_attack` "
            "(dnd-engine/dnd_engine/core/combat.py:91) has no `cover` "
            "parameter, `GameState.get_effective_ac` "
            "(dnd-engine/dnd_engine/core/game_state.py:2777) layers AC "
            "modifiers but has no cover source, and no code path "
            "applies the SRD's +2 / +5 AC bonus. Tracked by issue "
            "#473."
        )


class TestAttackStructure_Step3_ResolveTheAttack:
    """SRD § Playing the Game › Making an Attack › Step 3: Resolve the Attack.

    > Make the attack roll, as detailed earlier in "Playing the Game."
    > On a hit, you roll damage unless the particular attack has rules
    > that specify otherwise. Some attacks cause special effects in
    > addition to or instead of damage.
    """

    def test_resolve_attack_produces_a_hit_decision_and_damage(self) -> None:
        """Step 3's body — d20 roll, hit decision, damage on hit.

        Cross-reference: dice math (>= AC, nat-20, nat-1) is tested in
        `tests/srd/playing_the_game/test_attack_rolls.py`. Here we
        confirm the procedural step *exists* — every attack flows
        through `resolve_attack`, which yields a hit/miss decision and
        zeroes damage on miss.
        """
        engine, attacker, defender = _make_engine_and_combatants()
        # Force a guaranteed miss via huge AC + zero bonus, looping
        # until we see a non-crit miss.
        defender_high_ac = Creature(
            name="Stone Golem",
            max_hp=30,
            ac=30,
            abilities=defender.abilities,
        )
        for _ in range(50):
            result = engine.resolve_attack(
                attacker=attacker,
                defender=defender_high_ac,
                attack_bonus=0,
                damage_dice="1d8+3",
            )
            if not result.critical_hit and not result.hit:
                assert result.damage == 0, (
                    "On a miss, Step 3 must skip the damage roll "
                    "(SRD: 'On a hit, you roll damage')."
                )
                return
        pytest.fail("Did not observe a non-crit miss in 50 attacks against AC 30.")

    def test_resolve_attack_supports_special_effects_in_addition_to_damage(self) -> None:
        """Step 3's "special effects" branch — `action.saving_throw`.

        Some monster attacks impose a condition on hit (e.g., ghoul's
        Claw paralyzes on a failed CON save). The engine's hook is the
        `action` kwarg on `resolve_attack` plus
        `CombatEngine._process_saving_throw_effect`
        (dnd-engine/dnd_engine/core/combat.py:371) — confirming the
        seam exists is the Step-3 procedural assertion.
        """
        src = inspect.getsource(CombatEngine._process_saving_throw_effect)
        assert "apply_condition_with_metadata" in src, (
            "Step 3's 'special effects in addition to or instead of "
            "damage' branch must apply on-fail conditions through the "
            "saving-throw effect handler."
        )

    def test_resolve_attack_can_skip_damage_when_attack_specifies_otherwise(self) -> None:
        pytest.skip(
            "GAP: SRD allows 'instead of damage' attacks (no damage, "
            "just a condition). The engine's `resolve_attack` "
            "(dnd-engine/dnd_engine/core/combat.py:91) requires a "
            "`damage_dice` string and always rolls it on a hit; "
            "callers cannot opt out. The Grappled / Shoved attack "
            "actions in the SRD's Unarmed Strike rules would consume "
            "this surface but are not implemented."
        )


class TestCover_Intro:
    """SRD § Playing the Game › Making an Attack › Cover › Intro.

    > Walls, trees, creatures, and other obstacles can provide cover,
    > making a target more difficult to harm. As detailed in the Cover
    > table, there are three degrees of cover, each of which gives a
    > different benefit to a target.
    """

    def test_cover_state_is_representable_on_an_attack(self) -> None:
        pytest.skip(
            "GAP: cover is not modeled anywhere. There is no enum / "
            "string for the three degrees, no `cover` parameter on "
            "`CombatEngine.resolve_attack` "
            "(dnd-engine/dnd_engine/core/combat.py:91), and no cover-"
            "modifier source in `GameState.get_effective_ac` "
            "(dnd-engine/dnd_engine/core/game_state.py:2777). Tracked "
            "by issue #473."
        )


class TestCover_Geometry:
    """SRD § Playing the Game › Making an Attack › Cover › Geometry.

    > A target can benefit from cover only when an attack or other
    > effect originates on the opposite side of the cover.
    """

    def test_cover_only_applies_when_attack_originates_on_opposite_side(self) -> None:
        pytest.skip(
            "GAP: no cover system exists, so the geometric carve-out "
            "is also missing. Once `resolve_attack` accepts a `cover` "
            "parameter (#473), this rule lives in the *caller* (the "
            "client computes line-of-sight, akin to how "
            "`dnd-engine/dnd_engine/systems/ranged_attacks.py:24` "
            "currently lets the caller pass an `attacker_visible_to` "
            "callback). Tracked by issue #473."
        )


class TestCover_NoStacking:
    """SRD § Playing the Game › Making an Attack › Cover › No Stacking.

    > If a target is behind multiple sources of cover, only the most
    > protective degree of cover applies; the degrees aren't added
    > together. For example, if a target is behind a creature that
    > gives Half Cover and a tree trunk that gives Three-Quarters
    > Cover, the target has Three-Quarters Cover.
    """

    def test_only_most_protective_cover_applies(self) -> None:
        pytest.skip(
            "GAP: with no cover system in place (issue #473), the "
            "'most protective applies' no-stacking rule has no code "
            "path. Mirrors the no-stacking rule for damage modifiers "
            "(issue #468), which is also pending a pipeline. Tracked "
            "by issue #473."
        )


class TestCover_HalfCover:
    """SRD § Playing the Game › Making an Attack › Cover › Half Cover.

    > Half Cover: +2 bonus to AC and Dexterity saving throws. Offered
    > by another creature or an object that covers at least half of the
    > target.
    """

    def test_half_cover_grants_plus_two_ac(self) -> None:
        pytest.skip(
            "GAP: no cover system, so no +2 AC application. "
            "`GameState.get_effective_ac` "
            "(dnd-engine/dnd_engine/core/game_state.py:2777) layers AC "
            "modifiers from spells and effects but has no per-attack "
            "cover input — cover is a property of *this* attack's "
            "geometry, not of the defender's persistent state. Tracked "
            "by issue #473."
        )

    def test_half_cover_grants_plus_two_to_dex_saves(self) -> None:
        pytest.skip(
            "GAP: cover's saving-throw side is not implemented. "
            "`Creature.make_saving_throw` "
            "(dnd-engine/dnd_engine/core/creature.py) has no `cover` "
            "kwarg, and no spell-save path (e.g., Fireball) bumps DEX "
            "saves by +2 when the target is behind half cover. Tracked "
            "by issue #473."
        )


class TestCover_ThreeQuartersCover:
    """SRD § Playing the Game › Making an Attack › Cover › Three-Quarters.

    > Three-Quarters Cover: +5 bonus to AC and Dexterity saving throws.
    > Offered by an object that covers at least three-quarters of the
    > target.
    """

    def test_three_quarters_cover_grants_plus_five_ac(self) -> None:
        pytest.skip(
            "GAP: no cover system. Same code path as the half-cover AC "
            "bonus above — `resolve_attack` "
            "(dnd-engine/dnd_engine/core/combat.py:91) lacks a `cover` "
            "parameter and `get_effective_ac` has no cover source. "
            "Tracked by issue #473."
        )

    def test_three_quarters_cover_grants_plus_five_to_dex_saves(self) -> None:
        pytest.skip(
            "GAP: cover's saving-throw side is not implemented. "
            "`Creature.make_saving_throw` "
            "(dnd-engine/dnd_engine/core/creature.py) has no `cover` "
            "kwarg. Tracked by issue #473."
        )


class TestCover_TotalCover:
    """SRD § Playing the Game › Making an Attack › Cover › Total Cover.

    > Total Cover: can't be targeted directly. Offered by an object
    > that covers the whole target.
    """

    def test_total_cover_rejects_an_attack_at_step_1(self) -> None:
        pytest.skip(
            "GAP: there is no early-rejection path for an attack "
            "against a Total-cover target. `CombatEngine.resolve_attack`"
            " (dnd-engine/dnd_engine/core/combat.py:91) and "
            "`GameState.execute_player_attack` "
            "(dnd-engine/dnd_engine/core/game_state.py:2182) will both "
            "happily roll dice against a fully-covered creature. The "
            "Total-cover rule belongs at Step 1 ('can't be targeted "
            "directly') rather than at the AC layer. Tracked by issue "
            "#473."
        )
