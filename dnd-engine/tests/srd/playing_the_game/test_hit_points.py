# ABOUTME: SRD conformance audit for "Playing the Game > Hit Points".
# ABOUTME: Cross-references docs/srd/playing-the-game/hit-points.md against engine code.

"""SRD conformance: Hit Points.

Maps every rule in `docs/srd/playing-the-game/hit-points.md` to a test.
Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import inspect

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature

pytestmark = pytest.mark.srd(
    "playing-the-game/hit-points.md",
    lines="2177-2204",
)


def _make_abilities() -> Abilities:
    return Abilities(
        strength=14, dexterity=12, constitution=13, intelligence=10, wisdom=11, charisma=8
    )


def _make_creature(*, max_hp: int = 20, current_hp: int | None = None) -> Creature:
    return Creature(
        name="Goblin",
        max_hp=max_hp,
        ac=12,
        abilities=_make_abilities(),
        current_hp=current_hp,
    )


def _make_character(*, max_hp: int = 20, current_hp: int | None = None) -> Character:
    return Character(
        name="TestHero",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=_make_abilities(),
        max_hp=max_hp,
        ac=16,
        current_hp=current_hp if current_hp is not None else max_hp,
    )


class TestHitPoints_Intro:
    """SRD § Playing the Game › Hit Points › Intro.

    > Hit Points represent durability and the will to live. Creatures
    > with more Hit Points are more difficult to kill.
    """

    def test_creature_carries_max_hp_and_current_hp(self) -> None:
        """`Creature` models HP via `max_hp` + `current_hp`.

        Source: `dnd_engine/core/creature.py:64-87`. These two fields
        are the engine's HP representation; everything in the SRD's
        Hit Points section reduces to operations over these two.
        """
        creature = _make_creature(max_hp=20)
        assert creature.max_hp == 20
        assert creature.current_hp == 20

    def test_more_hp_means_harder_to_kill(self) -> None:
        """Damage equal to the smaller pool kills first; the bigger pool survives.

        End-to-end proof of the SRD's "creatures with more Hit Points
        are more difficult to kill" — `take_damage`
        (`dnd_engine/core/creature.py:215-224`) consumes HP one-for-one,
        and `is_alive` (`creature.py:104-107`) flips at 0. Same hit on
        an HP-30 and an HP-10 creature kills one but not the other.
        """
        tough = _make_creature(max_hp=30)
        frail = _make_creature(max_hp=10)
        tough.take_damage(15)
        frail.take_damage(15)
        assert tough.is_alive is True
        assert frail.is_alive is False


class TestHitPoints_Resting:
    """SRD § Playing the Game › Hit Points › Resting.

    > Any creature can take hour-long Short Rests in the midst of a day
    > and an 8-hour Long Rest to end it. Regaining Hit Points is one of
    > the main benefits of a rest.
    """

    def test_short_rest_action_exists(self) -> None:
        """`Character.take_short_rest` is the engine's short-rest surface.

        Source: `dnd_engine/core/character.py:1202-1234`. The method
        returns a result dict with `rest_type="short"`. The SRD's
        "hour-long Short Rests" map directly to this entry.
        """
        character = _make_character()
        result = character.take_short_rest()
        assert result["rest_type"] == "short"

    def test_long_rest_action_exists_and_recovers_hp(self) -> None:
        """`Character.take_long_rest` recovers full HP per SRD.

        Source: `dnd_engine/core/character.py:1236-1280`. Long rest is
        the SRD's primary HP-restoration mechanism for the day's end.
        `recover_hp()` (no-arg) fully restores HP for living characters.
        """
        character = _make_character(max_hp=20, current_hp=5)
        result = character.take_long_rest()
        assert result["rest_type"] == "long"
        assert result["hp_recovered"] == 15
        assert character.current_hp == 20

    def test_short_rest_does_not_restore_hp_without_hit_dice(self) -> None:
        """Short rest does not auto-heal — Hit Dice spending is unimplemented.

        Source: `dnd_engine/core/character.py:1233` declares
        `hp_recovered: 0` and comments "Hit Dice healing for future."
        The SRD allows HP regain via Hit Dice on a short rest; that
        spending mechanism is not implemented, but the short-rest
        action itself exists per the rule above. This test pins the
        current behavior.
        """
        character = _make_character(max_hp=20, current_hp=5)
        result = character.take_short_rest()
        assert result["hp_recovered"] == 0
        assert character.current_hp == 5


class TestHitPoints_RangeAndClamp:
    """SRD § Playing the Game › Hit Points › Range.

    > Your Hit Point maximum is the number of Hit Points you have when
    > uninjured. Your current Hit Points can be any number from that
    > maximum down to 0, which is the lowest Hit Points can go.
    """

    def test_uninjured_current_hp_equals_max_hp(self) -> None:
        """A newly built creature defaults `current_hp == max_hp`.

        Source: `dnd_engine/core/creature.py:86` — the constructor sets
        `current_hp = current_hp if current_hp is not None else max_hp`.
        The SRD's "Hit Point maximum is the number of Hit Points you
        have when uninjured" is the post-condition of construction.
        """
        creature = _make_creature(max_hp=20)
        assert creature.current_hp == creature.max_hp

    def test_take_damage_clamps_current_hp_at_zero(self) -> None:
        """`Creature.take_damage` clamps at 0; HP can't go negative.

        Source: `dnd_engine/core/creature.py:215-224` —
        `self.current_hp = max(0, self.current_hp - amount)`. Damage
        that exceeds remaining HP just leaves the creature at 0,
        matching the SRD's "lowest Hit Points can go" floor.
        """
        creature = _make_creature(max_hp=10, current_hp=10)
        creature.take_damage(50)
        assert creature.current_hp == 0


class TestHitPoints_DamageSubtractsHp:
    """SRD § Playing the Game › Hit Points › Damage.

    > Whenever you take damage, subtract it from your Hit Points.
    """

    def test_take_damage_subtracts_amount_from_current_hp(self) -> None:
        """`Creature.take_damage(n)` reduces current_hp by n.

        Source: `dnd_engine/core/creature.py:224` —
        `self.current_hp = max(0, self.current_hp - amount)`. Taking 7
        damage on a 20/20 creature leaves it at 13.
        """
        creature = _make_creature(max_hp=20, current_hp=20)
        creature.take_damage(7)
        assert creature.current_hp == 13


class TestHitPoints_NoEffectUntilZero:
    """SRD § Playing the Game › Hit Points › Capability.

    > Hit Point loss has no effect on your capabilities until you reach
    > 0 Hit Points.
    """

    def test_can_take_actions_while_wounded_but_alive(self) -> None:
        """A wounded-but-alive creature is fully capable.

        `Creature.can_take_actions`
        (`dnd_engine/core/creature.py:308-318`) returns True unless an
        incapacitating condition is active. HP loss alone does not
        attach any such condition, matching the SRD's "no effect on
        your capabilities until 0."
        """
        creature = _make_creature(max_hp=20, current_hp=1)
        assert creature.is_alive is True
        assert creature.can_take_actions() is True

    def test_character_take_damage_does_not_attach_capability_conditions(self) -> None:
        """Damage above 0 leaves a Character's condition set unchanged.

        Source-level proof: `Character.take_damage`
        (`dnd_engine/core/character.py:1100-1148`) only branches into
        death-save handling when the target *was* already unconscious.
        Taking nonlethal damage on a healthy character doesn't add any
        condition.
        """
        character = _make_character(max_hp=20, current_hp=20)
        before = set(character.active_conditions.keys())
        character.take_damage(5)
        assert character.current_hp == 15
        assert set(character.active_conditions.keys()) == before


class TestHitPoints_Bloodied:
    """SRD § Playing the Game › Hit Points › Bloodied.

    > If you have half your Hit Points or fewer, you're Bloodied, which
    > has no game effect on its own but which might trigger other game
    > effects.
    """

    def test_creature_at_half_hp_or_fewer_is_bloodied(self) -> None:
        """`is_bloodied` is True iff `0 < current_hp <= max_hp // 2`.

        Source: `dnd_engine/core/creature.py` `Creature.is_bloodied`.
        A creature at full HP is not Bloodied; a creature at 0 HP is
        Dying/Dead/Stable, not Bloodied.
        """
        # At exactly half HP -> Bloodied
        creature = _make_creature(max_hp=20, current_hp=10)
        assert creature.is_bloodied is True

        # Below half -> Bloodied
        creature = _make_creature(max_hp=20, current_hp=5)
        assert creature.is_bloodied is True

        # Down to 1 HP -> still Bloodied (still alive, still <= half)
        creature = _make_creature(max_hp=20, current_hp=1)
        assert creature.is_bloodied is True

        # Just above half -> not Bloodied
        creature = _make_creature(max_hp=20, current_hp=11)
        assert creature.is_bloodied is False

        # Full HP -> not Bloodied
        creature = _make_creature(max_hp=20, current_hp=20)
        assert creature.is_bloodied is False

        # 0 HP -> not Bloodied (creature is Dying/Dead/Stable, not Bloodied)
        creature = _make_creature(max_hp=20, current_hp=0)
        assert creature.is_bloodied is False

    def test_bloodied_state_has_no_inherent_mechanical_effect(self) -> None:
        """Becoming Bloodied is a flag only — no conditions, no capability shift.

        The SRD spells out that Bloodied "has no game effect on its own
        but which might trigger other game effects." This test pins the
        engine to surface the state as a pure derived property without
        attaching any modifier, condition, or action-economy change.
        """
        creature = _make_creature(max_hp=20, current_hp=20)

        # Pre-state: not bloodied, no conditions, can act, not incapacitated.
        assert creature.is_bloodied is False
        conditions_before = dict(creature.active_conditions)
        can_act_before = creature.can_take_actions()
        incapacitated_before = creature.is_incapacitated()

        # Drop below half HP -> becomes Bloodied.
        creature.take_damage(15)
        assert creature.current_hp == 5
        assert creature.is_bloodied is True

        # No conditions were added or removed by crossing the threshold.
        assert creature.active_conditions == conditions_before

        # Action-economy capabilities are unchanged.
        assert creature.can_take_actions() == can_act_before
        assert creature.is_incapacitated() == incapacitated_before


class TestHitPoints_MaxHpField:
    """SRD § Playing the Game › Hit Points › Maximum.

    > Your Hit Point maximum is the number of Hit Points you have when
    > uninjured.
    """

    def test_creature_constructor_accepts_max_hp(self) -> None:
        """`Creature` exposes `max_hp` as the SRD's "maximum."

        Source: `dnd_engine/core/creature.py:65` —
        `max_hp: int` is a required constructor argument and is stored
        as a public attribute. The SRD's "maximum" maps directly to
        this field.
        """
        sig = inspect.signature(Creature.__init__)
        assert "max_hp" in sig.parameters
        creature = _make_creature(max_hp=42)
        assert creature.max_hp == 42

    def test_healing_cannot_exceed_max_hp(self) -> None:
        """Healing past max_hp is clamped — see also test_healing.py.

        Source: `dnd_engine/core/creature.py:240` —
        `self.current_hp = min(self.max_hp, self.current_hp + amount)`.
        The SRD's "maximum" is enforced as a hard ceiling on the
        current HP value, both on healing entry and as a post-condition
        of the rule above.
        """
        creature = _make_creature(max_hp=10, current_hp=8)
        creature.heal(100)
        assert creature.current_hp == 10
