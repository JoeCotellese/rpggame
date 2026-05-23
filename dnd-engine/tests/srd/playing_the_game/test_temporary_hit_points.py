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

from dnd_engine.core.creature import Creature

pytestmark = pytest.mark.srd(
    "playing-the-game/temporary-hit-points.md",
    lines="2393-2433",
)


class TestTempHP_Intro:
    """SRD § Playing the Game › Temporary Hit Points › Intro.

    > Some spells and other effects confer Temporary Hit Points, which
    > are a buffer against losing actual Hit Points, as explained below.
    """

    def test_creature_has_a_temporary_hit_points_field(self) -> None:
        pytest.skip(
            "GAP: `Creature` (dnd_engine/core/creature.py:57-102) has "
            "no `temporary_hit_points` (or equivalent) field. The only "
            "in-engine reference to temp HP is "
            "dnd_engine/systems/item_effects.py:364-368 which attaches "
            "a flavor `has_temporary_hp_buff` condition with a TODO "
            "comment ('Implement proper temporary HP system') — no "
            "actual pool is tracked. Tracked by issue #482."
        )

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
        pytest.skip(
            "GAP: `Creature.take_damage` "
            "(dnd_engine/core/creature.py:215-224) subtracts the full "
            "damage amount from `current_hp` directly. There is no "
            "Temp HP pool to drain first, so the SRD's worked example "
            "(5 Temp HP + 7 damage = 0 Temp HP + 2 HP lost) cannot be "
            "exercised. Tracked by issue #482."
        )

    def test_damage_exactly_equal_to_temp_hp_leaves_real_hp_untouched(self) -> None:
        pytest.skip(
            "GAP: depends on the Temp HP pool field. The SRD example "
            "implies a clean boundary — 5 damage against 5 Temp HP "
            "must consume all Temp HP and leave real HP untouched. "
            "Tracked by issue #482."
        )


class TestTempHP_Duration:
    """SRD § Playing the Game › Temporary Hit Points › Duration.

    > Temporary Hit Points last until they're depleted or you finish a
    > Long Rest (see "Rules Glossary").
    """

    def test_long_rest_clears_temporary_hit_points(self) -> None:
        pytest.skip(
            "GAP: `Character.take_long_rest` "
            "(dnd_engine/core/character.py:1236-1280) restores HP and "
            "clears expired conditions but has no Temp HP pool to "
            "zero out. Tracked by issue #482."
        )

    def test_short_rest_does_not_clear_temporary_hit_points(self) -> None:
        pytest.skip(
            "GAP: depends on the Temp HP pool field. The SRD scopes "
            "expiry to Long Rest specifically — short rest must NOT "
            "drain Temp HP. `Character.take_short_rest` "
            "(dnd_engine/core/character.py:1202-1234) has no Temp HP "
            "branch to assert against. Tracked by issue #482."
        )


class TestTempHP_DontStack:
    """SRD § Playing the Game › Temporary Hit Points › Don't Stack.

    > Temporary Hit Points can't be added together. If you have
    > Temporary Hit Points and receive more of them, you decide whether
    > to keep the ones you have or to gain the new ones. For example,
    > if a spell grants you 12 Temporary Hit Points when you already
    > have 10, you can have 12 or 10, not 22.
    """

    def test_receiving_new_temp_hp_does_not_sum_with_existing(self) -> None:
        pytest.skip(
            "GAP: no Temp HP grant API exists. The placeholder buff "
            "at dnd_engine/systems/item_effects.py:364-368 attaches a "
            "condition (`has_temporary_hp_buff`) without any amount. "
            "There is nowhere to test the SRD's worked example "
            "(10 + 12 = pick one, never 22). Tracked by issue #482."
        )

    def test_caller_chooses_to_keep_or_replace_temp_hp(self) -> None:
        pytest.skip(
            "GAP: depends on the grant API. The SRD lets the recipient "
            "*decide* (keep the old or take the new). A real grant "
            "API must surface this choice — defaulting to max() is a "
            "common implementation but the SRD reserves the choice to "
            "the player. Tracked by issue #482."
        )


class TestTempHP_NotHitPointsNotHealing:
    """SRD § Playing the Game › Temporary Hit Points › Not Hit Points or Healing.

    > Temporary Hit Points can't be added to your Hit Points, healing
    > can't restore them, and receiving Temporary Hit Points doesn't
    > count as healing. Because Temporary Hit Points aren't Hit Points,
    > a creature can be at full Hit Points and receive Temporary Hit
    > Points.
    """

    def test_healing_does_not_restore_temporary_hit_points(self) -> None:
        pytest.skip(
            "GAP: depends on the Temp HP pool field. `Creature.heal` "
            "(dnd_engine/core/creature.py:226-240) and "
            "`Character.recover_hp` "
            "(dnd_engine/core/character.py:1150-1174) operate on "
            "`current_hp` only; there is no Temp HP pool to inadvertently "
            "modify, but also no way to assert the SRD's negative — "
            "'healing can't restore them' — until the field exists. "
            "Tracked by issue #482."
        )

    def test_full_hp_creature_can_still_receive_temp_hp(self) -> None:
        pytest.skip(
            "GAP: depends on the grant API. SRD: 'a creature can be at "
            "full Hit Points and receive Temporary Hit Points.' "
            "`Creature.heal` is a no-op at full HP "
            "(dnd_engine/core/creature.py:240), which is *correct* for "
            "healing — but a Temp HP grant must NOT short-circuit on "
            "full HP. There is no grant path to exercise. Tracked by "
            "issue #482."
        )

    def test_temp_hp_grant_is_not_a_healing_event(self) -> None:
        pytest.skip(
            "GAP: depends on the Temp HP grant API. The SRD calls out "
            "that 'receiving Temporary Hit Points doesn't count as "
            "healing' — so a Temp HP grant must NOT emit a HEALING_DONE "
            "event "
            "(dnd_engine/utils/events.py) or otherwise be observable as "
            "a heal. Today no such grant API exists. Tracked by "
            "issue #482."
        )


class TestTempHP_ZeroHpInteraction:
    """SRD § Playing the Game › Temporary Hit Points › 0 HP Interaction.

    > If you have 0 Hit Points, receiving Temporary Hit Points doesn't
    > restore you to consciousness. Only true healing can save you.
    """

    def test_temp_hp_grant_does_not_revive_unconscious_creature(self) -> None:
        pytest.skip(
            "GAP: depends on Temp HP grant + Unconscious linkage. "
            "`Character.recover_hp` "
            "(dnd_engine/core/character.py:1162-1173) explicitly "
            "resets death saves when leaving 0 HP — that path is "
            "*correct* for healing, but the SRD requires a Temp HP "
            "grant to NOT trigger the same revival. Without a grant "
            "API the negative cannot be exercised. Tracked by "
            "issue #482."
        )

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
