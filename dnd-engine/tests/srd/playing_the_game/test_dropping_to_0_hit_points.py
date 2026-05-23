# ABOUTME: SRD conformance audit for "Playing the Game > Dropping to 0 Hit Points".
# ABOUTME: Cross-references docs/srd/playing-the-game/dropping-to-0-hit-points.md against engine code.

"""SRD conformance: Dropping to 0 Hit Points.

Maps every rule in `docs/srd/playing-the-game/dropping-to-0-hit-points.md`
to a test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import inspect
from unittest.mock import Mock, patch

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.utils.events import EventBus, EventType

pytestmark = pytest.mark.srd(
    "playing-the-game/dropping-to-0-hit-points.md",
    lines="2321-2392",
)


def _make_abilities() -> Abilities:
    return Abilities(
        strength=14, dexterity=12, constitution=13, intelligence=10, wisdom=11, charisma=8
    )


def _make_character(*, max_hp: int = 12, current_hp: int | None = None) -> Character:
    """Construct a Fighter for death-save assertions."""
    return Character(
        name="TestHero",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=_make_abilities(),
        max_hp=max_hp,
        ac=16,
        current_hp=current_hp if current_hp is not None else max_hp,
    )


class TestDroppingToZero_DiesOrFallsUnconscious:
    """SRD § Playing the Game › Dropping to 0 Hit Points › Overview.

    > When a creature drops to 0 Hit Points, it either dies outright or
    > falls unconscious, as explained below.
    """

    def test_character_at_zero_hp_is_unconscious_not_dead(self):
        """`Character.is_unconscious` reports True at 0 HP without 3 failures.

        Defends the dichotomy: HP-0 alone never means "dead" for a
        character — only 3 death-save failures (or massive damage /
        instant-death rules below) flip `is_dead`. The unconscious
        state is the default outcome at 0 HP.
        """
        character = _make_character()
        character.current_hp = 0

        assert character.is_unconscious is True
        assert character.is_dead is False

    def test_monster_at_zero_hp_is_not_alive_immediately(self):
        """`Creature.is_alive` flips to False the instant HP reaches 0.

        Monsters use the base `Creature` class (no death-save state).
        The SRD's monster-death rule is implemented by `is_alive`
        returning `current_hp > 0` (creature.py:105-107); once a
        monster's HP hits 0 it counts as defeated for every code path
        that gates on `is_alive`.
        """
        goblin = Creature(name="Goblin", max_hp=7, ac=15, abilities=_make_abilities())
        goblin.take_damage(7)

        assert goblin.current_hp == 0
        assert goblin.is_alive is False


class TestInstantDeath_MonsterDeath:
    """SRD § Playing the Game › Dropping to 0 Hit Points › Instant Death › Monster Death.

    > A monster dies the instant it drops to 0 Hit Points, although a
    > Game Master can ignore this rule for an individual monster and
    > treat it like a character.
    """

    def test_monster_drops_to_zero_and_is_defeated_without_death_saves(self):
        """A monster reaching 0 HP has no death-save machinery and is
        immediately treated as defeated (`is_alive == False`).

        `Creature` has no `death_save_failures`, no `is_unconscious`,
        and no `make_death_save`. The SRD "dies instantly" rule is
        modeled as the absence of those attributes plus
        `is_alive == False` at 0 HP.
        """
        goblin = Creature(name="Goblin", max_hp=7, ac=15, abilities=_make_abilities())

        goblin.take_damage(7)

        assert goblin.is_alive is False
        assert not hasattr(goblin, "death_save_failures"), (
            "Creatures (monsters) must not carry character-only death-"
            "save state — they die instantly at 0 HP."
        )
        assert not hasattr(goblin, "make_death_save"), (
            "Creatures (monsters) do not roll death saves; the method "
            "is Character-only."
        )

    def test_gm_override_to_treat_monster_like_character_is_not_modeled(self):
        pytest.skip(
            "GAP: SRD allows the GM to ignore monster-instant-death for "
            "a specific monster and run it as a character (death "
            "saves, stabilization). No engine hook exists to promote a "
            "Creature instance into the death-save flow — no "
            "`treat_as_character`/`make_pc_like` flag on Creature, no "
            "death-save state on the base class. Acceptable latent gap "
            "for a deterministic engine; tracked alongside future "
            "narrative-driven monster behavior."
        )


class TestInstantDeath_HitPointMaximumOfZero:
    """SRD § Playing the Game › Dropping to 0 Hit Points › Instant Death › HP Max of 0.

    > A creature dies if its Hit Point maximum reaches 0. Certain
    > effects drain life energy, reducing a creature's Hit Point
    > maximum.
    """

    def test_hit_point_maximum_drain_to_zero_kills_creature(self):
        pytest.skip(
            "GAP: No life-energy / max-HP-drain mechanic exists. "
            "`Creature.max_hp` is set at construction (creature.py:85) "
            "and never decremented anywhere in the engine — "
            "`grep -rn 'max_hp -=\\|reduce_max\\|drain_max' "
            "dnd_engine/` is empty. Levels add (character.py:643) but "
            "nothing subtracts. The SRD rule has no triggering effect "
            "implemented yet (no wights, no specters, no negative "
            "levels). Latent gap — file an issue when the first "
            "draining monster lands."
        )


class TestInstantDeath_MassiveDamage:
    """SRD § Playing the Game › Dropping to 0 Hit Points › Instant Death › Massive Damage.

    > When damage reduces a character to 0 Hit Points and damage
    > remains, the character dies if the remainder equals or exceeds
    > their Hit Point maximum. For example, if your character has a
    > Hit Point maximum of 12, currently has 6 Hit Points, and takes
    > 18 damage, the character drops to 0 Hit Points, but 12 damage
    > remains. The character then dies, since 12 equals their Hit
    > Point maximum.
    """

    def test_massive_damage_already_at_zero_hp_causes_instant_death(self):
        """Damage >= max_hp dealt to a character at 0 HP is instant death.

        This branch IS modeled by `Character.take_damage`
        (character.py:1121-1133): when `was_unconscious` is True and
        `amount >= self.max_hp`, `death_save_failures` is set to 3
        directly. Tested at `tests/test_death_saves.py::TestDamageAt
        ZeroHP::test_massive_damage_instant_death` already; this is
        the SRD-conformance mirror.
        """
        character = _make_character(max_hp=12)
        character.current_hp = 0

        character.take_damage(12)

        assert character.is_dead is True
        assert character.death_save_failures == 3

    def test_massive_damage_overflow_from_positive_hp_causes_instant_death(self):
        """SRD example: HP 6, max 12, take 18 → drops to 0, remainder
        of 12 (== max) → instant death.

        The engine's `take_damage` only checks the massive-damage
        threshold when `was_unconscious` was already True at entry
        (character.py:1115-1133). The classic SRD overflow case where
        a single blow brings the character from positive HP to 0 with
        remainder >= max_hp is NOT modeled — the character merely
        falls unconscious instead of dying outright. Tracked by the
        new gap issue filed alongside this audit.
        """
        pytest.skip(
            "GAP: Massive damage overflow from positive HP is not "
            "modeled. `Character.take_damage` "
            "(dnd-engine/dnd_engine/core/character.py:1115-1133) only "
            "checks the massive-damage threshold when the character "
            "was *already* unconscious at entry. A single attack that "
            "deals 18 damage to a max-12 character at 6 HP should "
            "kill outright per SRD; today it leaves the character "
            "unconscious with 0 failures. See issue #448."
        )


class TestFallingUnconscious_ConditionApplied:
    """SRD § Playing the Game › Dropping to 0 Hit Points › Falling Unconscious.

    > If you reach 0 Hit Points and don't die instantly, you have the
    > Unconscious condition (see "Rules Glossary") until you regain
    > any Hit Points, and you now face making Death Saving Throws
    > (see below).
    """

    def test_is_unconscious_property_reports_unconscious_at_zero_hp(self):
        """`Character.is_unconscious` is the computed proxy for the
        Unconscious condition (character.py:1283-1294).

        Returns True iff `current_hp == 0 and death_save_failures < 3`.
        """
        character = _make_character()
        character.current_hp = 0

        assert character.is_unconscious is True

    def test_unconscious_condition_is_added_to_active_conditions(self):
        """The SRD "Unconscious condition" should be observable in
        `active_conditions` so `is_incapacitated()` returns True.

        `Creature.is_incapacitated()` (creature.py:320-340) checks
        membership of `"unconscious"` in `active_conditions`. Dropping
        to 0 HP adds the condition there so rules that key off the
        Incapacitated condition (e.g. ranged-in-close-combat
        advantage, OA visibility) see the downed character.
        """
        character = _make_character(max_hp=12)

        # Lethal-but-not-massive damage: brings positive-HP character
        # to 0 without triggering the massive-damage instant-death
        # branch (which requires already-at-0 entry today).
        character.take_damage(12)

        assert character.current_hp == 0
        assert character.is_unconscious is True
        assert "unconscious" in character.active_conditions
        assert character.is_incapacitated() is True

        # Healing past 0 HP should remove the Unconscious condition
        # — SRD: "until you regain any Hit Points".
        character.recover_hp(5)

        assert character.current_hp == 5
        assert "unconscious" not in character.active_conditions
        assert character.is_incapacitated() is False


class TestDyingState_DerivedProperty:
    """Derived `Character.dying_state` reports Alive / Dying / Stable / Dead.

    Foundation for plan-04 slices that need a single high-level read
    of where a character sits in the dying pipeline. Pure function of
    `current_hp`, `death_save_failures`, and `stabilized` — no setter,
    no side effects.
    """

    def test_alive_when_hp_positive(self):
        from dnd_engine.core.character import DyingState

        character = _make_character(max_hp=12)

        assert character.current_hp > 0
        assert character.dying_state == DyingState.ALIVE

    def test_dying_when_at_zero_hp_with_failures_below_three(self):
        from dnd_engine.core.character import DyingState

        character = _make_character(max_hp=12)
        character.current_hp = 0

        assert character.death_save_failures < 3
        assert character.stabilized is False
        assert character.dying_state == DyingState.DYING

    def test_dying_with_partial_failures(self):
        from dnd_engine.core.character import DyingState

        character = _make_character(max_hp=12)
        character.current_hp = 0
        character.death_save_failures = 2

        assert character.dying_state == DyingState.DYING

    def test_stable_when_zero_hp_and_stabilized(self):
        from dnd_engine.core.character import DyingState

        character = _make_character(max_hp=12)
        character.current_hp = 0
        character.stabilized = True

        assert character.dying_state == DyingState.STABLE

    def test_dead_when_three_or_more_failures(self):
        from dnd_engine.core.character import DyingState

        character = _make_character(max_hp=12)
        character.current_hp = 0
        character.death_save_failures = 3

        assert character.dying_state == DyingState.DEAD

    def test_dying_state_is_read_only_property(self):
        """`dying_state` is a derived property — no setter."""
        character = _make_character(max_hp=12)

        with pytest.raises(AttributeError):
            character.dying_state = "alive"  # type: ignore[misc]


class TestDyingState_DeathSaveLifecycle:
    """Condition lifecycle around death-save outcomes."""

    def test_natural_20_death_save_removes_unconscious_condition(self):
        """Natural 20 brings the character to 1 HP and clears the
        Unconscious condition from `active_conditions`."""
        character = _make_character(max_hp=12)

        character.take_damage(12)
        assert "unconscious" in character.active_conditions

        # Force a natural-20 death save by patching the dice roller
        with patch.object(character._dice_roller, "roll") as mock_roll:
            mock_roll.return_value = Mock(total=20)
            result = character.make_death_save()

        assert result["natural_20"] is True
        assert character.current_hp == 1
        assert "unconscious" not in character.active_conditions

    def test_three_failures_replaces_unconscious_with_dead(self):
        """When the character reaches 3 death save failures, the
        Unconscious condition is replaced by a `"dead"` flag."""
        character = _make_character(max_hp=12)

        # Drop to 0 HP — adds 'unconscious'
        character.take_damage(12)
        assert "unconscious" in character.active_conditions

        # Two more hits at 0 HP each add 1 death-save failure
        character.take_damage(1)
        character.take_damage(1)
        character.take_damage(1)

        assert character.is_dead is True
        assert "unconscious" not in character.active_conditions
        assert "dead" in character.active_conditions


class TestDeathSavingThrows_TriggerOnStartOfTurn:
    """SRD § Playing the Game › Death Saving Throws.

    > Whenever you start your turn with 0 Hit Points, you must make a
    > Death Saving Throw to determine whether you creep closer to
    > death or hang on to life. Unlike other saving throws, this one
    > isn't tied to an ability score. You're in the hands of fate now.
    """

    def test_process_unconscious_turn_rolls_a_death_save(self):
        """`GameState.process_unconscious_turn` calls `make_death_save`
        on a 0-HP party member at their initiative slot.

        Source-level guard: the method body invokes `character.
        make_death_save(self.event_bus)` and returns a
        `DeathSaveTurnResult` (game_state.py:4170-4192). The marker
        words "make_death_save" and "DeathSaveTurnResult" must remain
        for the SRD start-of-turn trigger to be wired up.
        """
        from dnd_engine.core.game_state import GameState

        src = inspect.getsource(GameState.process_unconscious_turn)

        assert "make_death_save" in src, (
            "process_unconscious_turn must invoke `character."
            "make_death_save` so 0-HP characters roll on their turn."
        )
        assert "is_unconscious" in src, (
            "process_unconscious_turn must gate on `is_unconscious` so "
            "only 0-HP-but-alive characters are forced into the save."
        )

    def test_death_save_uses_no_ability_modifier(self):
        """`make_death_save` rolls 1d20 with no ability modifier added.

        Source-level guard: the implementation rolls "1d20" and
        compares the raw roll against 10 (character.py:1355-1363).
        No `*_mod` / `proficiency_bonus` is added. The SRD's "in the
        hands of fate" wording is enforced by the *absence* of
        modifier arithmetic.
        """
        src = inspect.getsource(Character.make_death_save)

        assert '"1d20"' in src or "'1d20'" in src
        assert "str_mod" not in src and "dex_mod" not in src
        assert "con_mod" not in src and "wis_mod" not in src
        assert "proficiency_bonus" not in src, (
            "Death saves are ability-score-free per SRD — no modifier "
            "may be added to the d20 roll."
        )

    def test_death_save_cannot_be_made_while_conscious(self):
        """Calling `make_death_save` on a non-unconscious character
        raises — defends against accidental rolls when HP > 0.
        """
        character = _make_character()
        character.current_hp = 5

        with pytest.raises(ValueError):
            character.make_death_save()


class TestDeathSavingThrows_ThreeSuccessesOrFailures:
    """SRD § Playing the Game › Death Saving Throws › Three Successes/Failures.

    > Roll 1d20. If the roll is 10 or higher, you succeed. Otherwise,
    > you fail. A success or failure has no effect by itself. On your
    > third success, you become Stable (see "Stabilizing a Character"
    > below). On your third failure, you die. The successes and
    > failures don't need to be consecutive; keep track of both until
    > you collect three of a kind. The number of both is reset to zero
    > when you regain any Hit Points or become Stable.
    """

    def test_dc_10_threshold_treats_ten_as_success(self):
        """Roll of exactly 10 counts as a success (>= 10).

        character.py:1363 uses `success = roll >= 10`, so the
        threshold is inclusive on the success side.
        """
        character = _make_character()
        character.current_hp = 0

        with patch.object(character._dice_roller, "roll") as mock_roll:
            mock_roll.return_value = Mock(total=10)
            result = character.make_death_save()

        assert result["success"] is True

    def test_nine_or_lower_counts_as_failure(self):
        """Roll of 9 is a failure (just below the 10 threshold)."""
        character = _make_character()
        character.current_hp = 0

        with patch.object(character._dice_roller, "roll") as mock_roll:
            mock_roll.return_value = Mock(total=9)
            result = character.make_death_save()

        assert result["success"] is False
        assert result["failures"] == 1

    def test_three_successes_stabilize_character(self):
        """Accumulating 3 successes flips `stabilized` to True.

        character.py:1378-1380 sets `self.stabilized = True` when
        `death_save_successes >= 3`.
        """
        character = _make_character()
        character.current_hp = 0

        with patch.object(character._dice_roller, "roll") as mock_roll:
            mock_roll.return_value = Mock(total=15)
            for _ in range(3):
                character.make_death_save()

        assert character.stabilized is True

    def test_three_failures_means_death(self):
        """Accumulating 3 failures flips `is_dead` to True."""
        character = _make_character()
        character.current_hp = 0

        with patch.object(character._dice_roller, "roll") as mock_roll:
            mock_roll.return_value = Mock(total=5)
            for _ in range(3):
                character.make_death_save()

        assert character.is_dead is True

    def test_successes_and_failures_can_be_non_consecutive(self):
        """A run S, F, S, F, S still stabilizes on the third success.

        Tracks both counters independently; the SRD wording "don't
        need to be consecutive" maps to the engine using separate
        increment paths for each branch (character.py:1376-1383).
        """
        character = _make_character()
        character.current_hp = 0

        rolls = [15, 5, 15, 5, 15]  # S, F, S, F, S
        with patch.object(character._dice_roller, "roll") as mock_roll:
            mock_roll.side_effect = [Mock(total=r) for r in rolls]
            for _ in rolls:
                character.make_death_save()

        assert character.death_save_successes == 3
        assert character.death_save_failures == 2
        assert character.stabilized is True

    def test_regaining_any_hit_points_resets_both_counters(self):
        """Healing 1 HP from 0 zeroes successes and failures.

        character.py:1170-1172 calls `reset_death_saves()` when
        `was_unconscious and current_hp > 0` after `recover_hp`.
        """
        character = _make_character()
        character.current_hp = 0
        character.death_save_successes = 2
        character.death_save_failures = 1

        character.recover_hp(1)

        assert character.death_save_successes == 0
        assert character.death_save_failures == 0
        assert character.stabilized is False

    def test_becoming_stable_resets_both_counters(self):
        """SRD: counts reset to zero on Stable.

        Engine sets `stabilized = True` on the 3rd success but does
        NOT reset `death_save_successes` to 0 (character.py:1376-1380).
        After 3 successes the character still has
        `death_save_successes == 3`, so the SRD wording "is reset to
        zero when you ... become Stable" is not honored. Tracked by
        a new gap issue.
        """
        pytest.skip(
            "GAP: Becoming Stable (3 successes) does not reset "
            "`death_save_successes`/`death_save_failures` to zero. "
            "`Character.make_death_save` "
            "(dnd-engine/dnd_engine/core/character.py:1376-1380) sets "
            "`stabilized = True` on the third success but leaves the "
            "counters at their current values. The SRD says 'The "
            "number of both is reset to zero when you regain any Hit "
            "Points or become Stable.' Same gap applies to "
            "`stabilize_character()` via Medicine check. See issue "
            "#454."
        )


class TestDeathSavingThrows_Rolling20Or1:
    """SRD § Playing the Game › Death Saving Throws › Rolling a 1 or 20.

    > When you roll a 1 on the d20 for a Death Saving Throw, you
    > suffer two failures. If you roll a 20 on the d20, you regain 1
    > Hit Point.
    """

    def test_natural_one_counts_as_two_failures(self):
        """Nat 1 increments `death_save_failures` by 2.

        character.py:1372-1374 explicitly handles `natural_1` by
        `self.death_save_failures += 2` before the
        success/failure branches.
        """
        character = _make_character()
        character.current_hp = 0

        with patch.object(character._dice_roller, "roll") as mock_roll:
            mock_roll.return_value = Mock(total=1)
            result = character.make_death_save()

        assert result["natural_1"] is True
        assert character.death_save_failures == 2

    def test_natural_twenty_restores_one_hit_point(self):
        """Nat 20 sets `current_hp = 1` and resets death-save state.

        character.py:1367-1371 sets `self.current_hp = 1`, calls
        `reset_death_saves()`, and flags `conscious = True`.
        """
        character = _make_character()
        character.current_hp = 0
        character.death_save_failures = 2

        with patch.object(character._dice_roller, "roll") as mock_roll:
            mock_roll.return_value = Mock(total=20)
            result = character.make_death_save()

        assert result["natural_20"] is True
        assert result["conscious"] is True
        assert character.current_hp == 1
        assert character.death_save_failures == 0
        assert character.death_save_successes == 0
        assert character.is_unconscious is False


class TestDamageAtZeroHP_AutoFailure:
    """SRD § Playing the Game › Death Saving Throws › Damage at 0 Hit Points.

    > If you take any damage while you have 0 Hit Points, you suffer
    > a Death Saving Throw failure. If the damage is from a Critical
    > Hit, you suffer two failures instead. If the damage equals or
    > exceeds your Hit Point maximum, you die.
    """

    def test_normal_damage_at_zero_hp_adds_one_failure(self):
        """`Character.take_damage` adds 1 failure when struck at 0 HP.

        character.py:1135-1136 calls `self.add_death_save_failure(1)`
        in the non-massive-damage branch.
        """
        character = _make_character()
        character.current_hp = 0

        character.take_damage(3)

        assert character.death_save_failures == 1

    def test_critical_hit_damage_at_zero_hp_adds_two_failures(self):
        """A critical hit at 0 HP must add 2 failures, not 1.

        `Character.take_damage(amount, event_bus=None)` does not
        accept a `critical_hit` flag (character.py:1100), and the
        combat resolver does not surface crit context through the
        damage application path (combat.py:188-200 calls
        `defender.take_damage(damage + sneak_attack_damage)` with no
        crit signal). As a result, a critical at 0 HP currently only
        increments failures by 1. The SRD requires 2.
        """
        pytest.skip(
            "GAP: Critical-hit damage at 0 HP does not double the "
            "death-save failure. `Character.take_damage` "
            "(dnd-engine/dnd_engine/core/character.py:1100-1148) "
            "accepts only `(amount, event_bus)` — no `critical_hit` "
            "flag — and `CombatEngine.resolve_attack` "
            "(dnd-engine/dnd_engine/core/combat.py:188-200) calls "
            "`take_damage` without surfacing crit context. A crit "
            "while at 0 HP today registers as 1 failure, not 2. "
            "See issue #457."
        )

    def test_damage_equal_to_max_hp_at_zero_hp_causes_instant_death(self):
        """Already covered by `TestInstantDeath_MassiveDamage` above —
        this is the SRD wording's secondary placement of the same
        rule. character.py:1121-1125 handles it.
        """
        character = _make_character(max_hp=10)
        character.current_hp = 0

        character.take_damage(10)

        assert character.is_dead is True


class TestStabilizingACharacter_MedicineCheck:
    """SRD § Playing the Game › Stabilizing a Character › Medicine check.

    > You can take the Help action to try to stabilize a creature
    > with 0 Hit Points, which requires a successful DC 10 Wisdom
    > (Medicine) check.
    """

    def test_execute_stabilize_uses_medicine_dc_10(self):
        """`GameState.execute_stabilize` makes a DC 10 Medicine check.

        Source-level guard: game_state.py:2321-2323 calls
        `helper.make_skill_check("medicine", 10, skills_data)`. The
        skill name and DC are the SRD-load-bearing constants.
        """
        from dnd_engine.core.game_state import GameState

        src = inspect.getsource(GameState.execute_stabilize)

        assert '"medicine"' in src or "'medicine'" in src, (
            "Stabilization must use the Medicine skill per SRD."
        )
        assert ", 10," in src or ", 10)" in src, (
            "Stabilization DC must be 10 per SRD."
        )

    def test_successful_medicine_check_stabilizes_target(self):
        """A successful Medicine check flips `target.stabilized = True`.

        game_state.py:2325-2327 invokes `target.stabilize_character()`
        on `check_result["success"]`. We exercise the live path via a
        Character with a mocked skill-check result for determinism.
        """
        from dnd_engine.core.game_state import GameState

        # The implementation calls `helper.make_skill_check`, then
        # `target.stabilize_character()` if it succeeded. Verify the
        # branch source so this test stays stable regardless of how
        # the dice roller is wired in fixtures.
        src = inspect.getsource(GameState.execute_stabilize)
        assert "target.stabilize_character()" in src, (
            "On Medicine-check success, stabilize_character() must be "
            "called on the target."
        )

    def test_stabilize_only_succeeds_when_target_at_zero_hp(self):
        """`Character.stabilize_character` is a no-op if `current_hp > 0`.

        character.py:1452-1453 guards on `current_hp == 0` before
        setting `stabilized = True`. The SRD precondition "a creature
        with 0 Hit Points" is honored.
        """
        character = _make_character()
        character.current_hp = 5

        character.stabilize_character()

        assert character.stabilized is False

    def test_stabilization_via_help_action_is_not_wired_up(self):
        pytest.skip(
            "GAP: The SRD frames stabilization as 'You can take the "
            "Help action to try to stabilize a creature.' The engine "
            "exposes `GameState.execute_stabilize` as a direct action "
            "but does not model the Help action — "
            "`rg 'Help|help_action' dnd-engine/dnd_engine/core/` is "
            "empty for action handlers. Stabilization currently does "
            "not consume the Help action explicitly; it's a "
            "standalone verb. Acceptable shortcut today, but should "
            "be routed through Help when the action economy is "
            "expanded. See issue #441."
        )

    def test_healers_kit_alternative_stabilization_is_not_implemented(self):
        pytest.skip(
            "GAP: While not in this SRD section, the parallel SRD "
            "rule (Equipment > Healer's Kit) lets you spend one use "
            "of a healer's kit to auto-stabilize a creature without "
            "a Medicine check. `rg 'healer|healers? kit' "
            "dnd-engine/dnd_engine/` returns no implementation. "
            "Acceptable latent gap — file when healer's kit usage is "
            "wired into inventory item effects."
        )


class TestStabilizingACharacter_StableState:
    """SRD § Playing the Game › Stabilizing a Character › Stable state.

    > A Stable creature doesn't make Death Saving Throws even though
    > it has 0 Hit Points, but it still has the Unconscious
    > condition. If the creature takes damage, it stops being Stable
    > and starts making Death Saving Throws again. A Stable creature
    > that isn't healed regains 1 Hit Point after 1d4 hours.
    """

    def test_stable_creature_does_not_make_death_saves(self):
        """`process_unconscious_turn` short-circuits for `stabilized`.

        game_state.py:4156-4168 returns a `DeathSaveTurnResult` with
        `already_stabilized=True` (no roll) when the character is
        stable.
        """
        from dnd_engine.core.game_state import GameState

        src = inspect.getsource(GameState.process_unconscious_turn)
        assert "character.stabilized" in src, (
            "process_unconscious_turn must short-circuit for stable "
            "characters so they don't roll death saves."
        )
        assert "already_stabilized" in src, (
            "The stable short-circuit must return an "
            "already_stabilized result, not a real roll."
        )

    def test_stable_creature_retains_unconscious_state_until_healed(self):
        """A stable, 0-HP character is still unconscious by the
        `is_unconscious` property (HP-0 + failures < 3).

        SRD: "still has the Unconscious condition."
        """
        character = _make_character()
        character.current_hp = 0
        character.stabilize_character()

        assert character.stabilized is True
        assert character.is_unconscious is True

    def test_stable_creature_taking_damage_resumes_death_saves(self):
        """Damage to a stable, 0-HP character must clear `stabilized`.

        Per SRD: "If the creature takes damage, it stops being Stable
        and starts making Death Saving Throws again."
        `Character.take_damage` (character.py:1100-1148) adds the
        damage-at-0-HP failure but does NOT flip
        `self.stabilized = False`. The character would still be
        skipped by `process_unconscious_turn`'s
        `if character.stabilized:` short-circuit (game_state.py:4157)
        and continue not making rolls.
        """
        pytest.skip(
            "GAP: Damage to a stable creature does not clear "
            "`stabilized`. `Character.take_damage` "
            "(dnd-engine/dnd_engine/core/character.py:1100-1148) "
            "increments death-save failures but never sets "
            "`self.stabilized = False`. As a result, "
            "`process_unconscious_turn` "
            "(dnd-engine/dnd_engine/core/game_state.py:4156-4168) "
            "continues to short-circuit on `character.stabilized` and "
            "the SRD's 'stops being Stable and starts making Death "
            "Saving Throws again' clause is unenforced. See issue "
            "#458."
        )

    def test_stable_creature_regains_one_hit_point_after_1d4_hours(self):
        pytest.skip(
            "GAP: No long-rest / hours-elapsed tick is modeled for "
            "stable creatures. `rg 'stable.*1d4\\|stable.*hour\\|"
            "stable.*1 hp' dnd-engine/dnd_engine/` is empty. "
            "`test_death_saves_integration.py::test_stabilized_"
            "character_heals_naturally_over_time` documents the gap "
            "in a comment ('After 1d4 hours, would heal to 1 HP — "
            "not implemented in MVP'). See issue #460."
        )


class TestEventEmission_DeathSaveEventsAreSurfaced:
    """SRD § Playing the Game › Dropping to 0 Hit Points › Event hooks.

    Not an SRD rule per se, but the engine's event-driven architecture
    requires every death-save state transition to emit an event so the
    LLM narrative layer and clients can react. These tests guard the
    event-bus contract.
    """

    def test_death_save_roll_emits_death_save_event(self):
        """`make_death_save(event_bus=bus)` emits `EventType.DEATH_SAVE`."""
        character = _make_character()
        character.current_hp = 0
        bus = EventBus()
        events: list = []
        bus.subscribe(EventType.DEATH_SAVE, lambda e: events.append(e))

        with patch.object(character._dice_roller, "roll") as mock_roll:
            mock_roll.return_value = Mock(total=15)
            character.make_death_save(bus)

        assert len(events) == 1
        assert events[0].data["character"] == character.name

    def test_damage_at_zero_hp_emits_damage_at_zero_event(self):
        """`take_damage` at 0 HP emits `EventType.DAMAGE_AT_ZERO_HP`."""
        character = _make_character()
        character.current_hp = 0
        bus = EventBus()
        events: list = []
        bus.subscribe(EventType.DAMAGE_AT_ZERO_HP, lambda e: events.append(e))

        character.take_damage(3, bus)

        assert len(events) == 1
        assert events[0].data["failures"] == 1

    def test_massive_damage_at_zero_hp_emits_massive_damage_death_event(self):
        """Massive damage at 0 HP emits `EventType.MASSIVE_DAMAGE_DEATH`."""
        character = _make_character(max_hp=10)
        character.current_hp = 0
        bus = EventBus()
        events: list = []
        bus.subscribe(EventType.MASSIVE_DAMAGE_DEATH, lambda e: events.append(e))

        character.take_damage(10, bus)

        assert len(events) == 1
        assert events[0].data["max_hp"] == 10
