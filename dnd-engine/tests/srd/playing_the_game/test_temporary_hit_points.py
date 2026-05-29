# ABOUTME: SRD conformance audit for "Playing the Game > Temporary Hit Points".
# ABOUTME: Cross-references docs/srd/playing-the-game/temporary-hit-points.md against engine code.

"""SRD conformance: Temporary Hit Points.

Maps every rule in `docs/srd/playing-the-game/temporary-hit-points.md`
to a test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import inspect

import pytest

from dnd_engine.core.creature import Abilities, Creature

pytestmark = pytest.mark.srd(
    "playing-the-game/temporary-hit-points.md",
    lines="2393-2433",
)


def _make_creature(max_hp: int = 20, current_hp: int | None = None) -> Creature:
    """Build a bare Creature for Temp HP assertions.

    Ability scores are arbitrary (Temp HP behavior doesn't depend on
    them); only `max_hp`/`current_hp` matter for the buffer/carryover
    rules under test.
    """
    return Creature(
        name="Subject",
        max_hp=max_hp,
        ac=10,
        abilities=Abilities(
            strength=10,
            dexterity=10,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
        ),
        current_hp=current_hp,
    )


def _make_character(max_hp: int = 20, current_hp: int | None = None):
    """Build a level-1 Fighter for Temp HP assertions that need the
    full Character rest / death-save machinery (the bare Creature has
    neither)."""
    from dnd_engine.core.character import Character, CharacterClass

    return Character(
        name="Hero",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=Abilities(
            strength=14,
            dexterity=12,
            constitution=13,
            intelligence=10,
            wisdom=11,
            charisma=8,
        ),
        max_hp=max_hp,
        ac=16,
        current_hp=current_hp,
    )


class TestTempHP_Intro:
    """SRD § Playing the Game › Temporary Hit Points › Intro.

    > Some spells and other effects confer Temporary Hit Points, which
    > are a buffer against losing actual Hit Points, as explained below.
    """

    def test_creature_has_a_temporary_hit_points_field(self) -> None:
        creature = _make_creature(max_hp=10)
        assert creature.temporary_hit_points == 0

    def test_item_effects_temporary_hp_buff_placeholder_is_documented(self) -> None:
        """Source-level guard: the placeholder is still labeled TODO.

        Until the real Temp HP system lands (issue #482), the engine
        carries a placeholder buff at
        `dnd_engine/systems/item_effects.py:364-368`. This test pins
        that placeholder so it can't silently start claiming Temp-HP
        semantics without being rewritten.
        """
        from dnd_engine.systems import item_effects

        src = inspect.getsource(item_effects)
        assert "TODO: Implement proper temporary HP system" in src, (
            "Placeholder Temp-HP buff at "
            "dnd_engine/systems/item_effects.py:364-368 must remain "
            "labeled TODO until the real system (issue #482) lands."
        )


class TestTempHP_LoseTempHPFirst:
    """SRD § Playing the Game › Temporary Hit Points › Lose Temp HP First.

    > If you have Temporary Hit Points and take damage, those points
    > are lost first, and any leftover damage carries over to your Hit
    > Points. For example, if you have 5 Temporary Hit Points and take
    > 7 damage, you lose those points and then lose 2 Hit Points.
    """

    def test_damage_subtracts_from_temp_hp_before_hp(self) -> None:
        # SRD worked example: 5 Temp HP + 7 damage = 0 Temp HP, 2 HP lost.
        creature = _make_creature(max_hp=20, current_hp=20)
        creature.temporary_hit_points = 5
        carryover = creature.take_damage(7)
        assert creature.temporary_hit_points == 0
        assert creature.current_hp == 18
        # take_damage reports the HP damage that actually landed (the
        # leftover after the buffer absorbed what it could).
        assert carryover == 2

    def test_damage_exactly_equal_to_temp_hp_leaves_real_hp_untouched(self) -> None:
        # A clean boundary: 5 damage against 5 Temp HP consumes the
        # whole buffer and leaves real HP untouched.
        creature = _make_creature(max_hp=20, current_hp=20)
        creature.temporary_hit_points = 5
        carryover = creature.take_damage(5)
        assert creature.temporary_hit_points == 0
        assert creature.current_hp == 20
        assert carryover == 0


class TestTempHP_Duration:
    """SRD § Playing the Game › Temporary Hit Points › Duration.

    > Temporary Hit Points last until they're depleted or you finish a
    > Long Rest (see "Rules Glossary").
    """

    def test_long_rest_clears_temporary_hit_points(self) -> None:
        # SRD: Temp HP last until depleted or a Long Rest.
        character = _make_character(max_hp=20, current_hp=15)
        character.set_temporary_hit_points(8)
        character.take_long_rest()
        assert character.temporary_hit_points == 0

    def test_short_rest_does_not_clear_temporary_hit_points(self) -> None:
        # SRD scopes expiry to a Long Rest specifically — a Short Rest
        # must leave the buffer intact.
        character = _make_character(max_hp=20, current_hp=15)
        character.set_temporary_hit_points(8)
        character.take_short_rest()
        assert character.temporary_hit_points == 8


class TestTempHP_DontStack:
    """SRD § Playing the Game › Temporary Hit Points › Don't Stack.

    > Temporary Hit Points can't be added together. If you have
    > Temporary Hit Points and receive more of them, you decide whether
    > to keep the ones you have or to gain the new ones. For example,
    > if a spell grants you 12 Temporary Hit Points when you already
    > have 10, you can have 12 or 10, not 22.
    """

    def test_receiving_new_temp_hp_does_not_sum_with_existing(self) -> None:
        # SRD worked example: 12 granted over an existing 10 yields 12,
        # never 22 — Temp HP can't be added together.
        creature = _make_creature()
        creature.set_temporary_hit_points(10)
        creature.set_temporary_hit_points(12)
        assert creature.temporary_hit_points == 12
        # A lower grant doesn't shrink the buffer either (keep-greater).
        creature.set_temporary_hit_points(5)
        assert creature.temporary_hit_points == 12

    def test_caller_chooses_to_keep_or_replace_temp_hp(self) -> None:
        # SRD reserves the choice to the recipient. The default
        # auto-resolves to the greater pool; a caller honoring an
        # explicit "take the new pool" choice passes replace=True, which
        # installs the new amount even when it is lower than the old.
        creature = _make_creature()
        creature.set_temporary_hit_points(10)
        creature.set_temporary_hit_points(5)  # default: keep the greater
        assert creature.temporary_hit_points == 10
        result = creature.set_temporary_hit_points(5, replace=True)
        assert creature.temporary_hit_points == 5
        assert result == 5  # helper returns the resulting pool


class TestTempHP_NotHitPointsNotHealing:
    """SRD § Playing the Game › Temporary Hit Points › Not Hit Points or Healing.

    > Temporary Hit Points can't be added to your Hit Points, healing
    > can't restore them, and receiving Temporary Hit Points doesn't
    > count as healing. Because Temporary Hit Points aren't Hit Points,
    > a creature can be at full Hit Points and receive Temporary Hit
    > Points.
    """

    def test_healing_does_not_restore_temporary_hit_points(self) -> None:
        # Drain part of a buffer, then heal: healing restores HP only,
        # never the depleted Temp HP pool.
        creature = _make_creature(max_hp=20, current_hp=20)
        creature.set_temporary_hit_points(5)
        creature.take_damage(8)  # 5 absorbed, 3 to HP
        assert creature.temporary_hit_points == 0
        assert creature.current_hp == 17
        creature.heal(5)
        assert creature.current_hp == 20  # capped at max
        assert creature.temporary_hit_points == 0  # heal can't refill Temp HP

    def test_full_hp_creature_can_still_receive_temp_hp(self) -> None:
        # SRD: 'a creature can be at full Hit Points and receive
        # Temporary Hit Points.' The grant must not short-circuit on
        # full HP the way healing does.
        creature = _make_creature(max_hp=20, current_hp=20)
        creature.set_temporary_hit_points(7)
        assert creature.current_hp == 20  # HP untouched
        assert creature.temporary_hit_points == 7

    def test_temp_hp_grant_is_not_a_healing_event(self) -> None:
        # 'Receiving Temporary Hit Points doesn't count as healing.' The
        # grant API is a pure pool operation on Creature — it takes no
        # event bus and cannot raise HP, so it can never be observed as
        # a heal (no HEALING_DONE, no current_hp change).
        import inspect

        sig = inspect.signature(Creature.set_temporary_hit_points)
        assert "event_bus" not in sig.parameters, (
            "set_temporary_hit_points must not accept an event bus — a "
            "Temp HP grant is not a healing event."
        )
        creature = _make_creature(max_hp=20, current_hp=12)
        creature.set_temporary_hit_points(6)
        assert creature.current_hp == 12  # grant did not heal


class TestTempHP_ZeroHpInteraction:
    """SRD § Playing the Game › Temporary Hit Points › 0 HP Interaction.

    > If you have 0 Hit Points, receiving Temporary Hit Points doesn't
    > restore you to consciousness. Only true healing can save you.
    """

    def test_temp_hp_grant_does_not_revive_unconscious_creature(self) -> None:
        # SRD: at 0 HP, receiving Temp HP does NOT restore consciousness.
        from dnd_engine.core.character import Character, CharacterClass

        character = Character(
            name="Downed",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(
                strength=14,
                dexterity=12,
                constitution=13,
                intelligence=10,
                wisdom=11,
                charisma=8,
            ),
            max_hp=20,
            ac=16,
            current_hp=0,
        )
        character.death_save_failures = 1
        character.set_temporary_hit_points(8)
        assert character.temporary_hit_points == 8
        assert character.current_hp == 0  # still down — grant is not healing
        assert character.is_unconscious  # not revived
        assert character.death_save_failures == 1  # death saves untouched

    def test_temp_hp_absorbs_damage_at_0_hp_without_a_death_save_failure(self) -> None:
        # A downed creature holding Temp HP that fully absorbs a blow
        # loses no Hit Points, so it suffers no new death-save failure.
        # (When the buffer is empty — every existing death-save test —
        # carryover equals the incoming amount and the failure still
        # fires, so this path is purely additive.)
        from dnd_engine.core.character import Character, CharacterClass

        character = Character(
            name="Downed",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(
                strength=14,
                dexterity=12,
                constitution=13,
                intelligence=10,
                wisdom=11,
                charisma=8,
            ),
            max_hp=20,
            ac=16,
            current_hp=0,
        )
        character.death_save_failures = 0
        character.set_temporary_hit_points(10)
        character.take_damage(6)  # fully absorbed by the buffer
        assert character.temporary_hit_points == 4
        assert character.current_hp == 0
        assert character.death_save_failures == 0  # no HP lost → no failure
        assert character.is_unconscious

    def test_only_true_healing_revives_a_zero_hp_creature(self) -> None:
        """Healing (not Temp HP) is what revives a downed creature.

        `Character.recover_hp` (`dnd_engine/core/character.py:1162-
        1173`) resets death saves when the heal brings the character
        above 0. This is the SRD's "only true healing can save you" —
        Temp HP would not flow through this path. Once issue #482
        lands, the negative side of this rule becomes testable.
        """
        # Sanity-check the positive half here so the SRD half-rule has
        # at least one real assertion: true healing DOES revive.
        from dnd_engine.core.character import Character, CharacterClass
        from dnd_engine.core.creature import Abilities

        character = Character(
            name="Hero",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(
                strength=14,
                dexterity=12,
                constitution=13,
                intelligence=10,
                wisdom=11,
                charisma=8,
            ),
            max_hp=20,
            ac=16,
            current_hp=0,
        )
        # Set death save state to simulate downed (but not dead) character.
        character.death_save_failures = 1
        character.death_save_successes = 0
        amount = character.recover_hp(5)
        assert amount == 5
        assert character.current_hp == 5
        # Death saves reset by recover_hp when leaving 0 HP.
        assert character.death_save_failures == 0


class TestTempHP_PlaceholderInItemEffects:
    """SRD § Playing the Game › Temporary Hit Points › Catalog parity.

    Items and spells that confer Temp HP exist in the SRD (e.g.,
    False Life, Heroism, various potions). This section guards the
    catalog seam.
    """

    def test_item_effects_recognizes_temporary_hp_buff_type(self) -> None:
        """`_apply_buff_effect` has a `buff_type == "temporary_hp"` branch.

        Source: `dnd_engine/systems/item_effects.py:364-368`. The
        branch exists today as a placeholder that attaches a
        condition but does NOT track a pool. This test pins the
        catalog-facing seam so the engine work in issue #482 can
        replace the body without renaming the branch.
        """
        from dnd_engine.systems import item_effects

        src = inspect.getsource(item_effects._apply_buff_effect)
        assert 'buff_type == "temporary_hp"' in src, (
            "`_apply_buff_effect` must keep its `temporary_hp` branch "
            "as the catalog entry point for Temp-HP grants — issue "
            "#482 will replace the body with a real pool."
        )


# Hint to anyone running this file: every test above except the one
# real assertion in TestTempHP_ZeroHpInteraction and the two source-
# level guards is a stub. That is intentional — the Temporary Hit
# Points system is unimplemented in its entirety. See issue #482.
_ = Creature  # keep the import live for any future real tests
