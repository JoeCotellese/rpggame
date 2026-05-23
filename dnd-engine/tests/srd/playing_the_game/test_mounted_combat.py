# ABOUTME: SRD conformance audit for "Playing the Game > Mounted Combat".
# ABOUTME: Cross-references docs/srd/playing-the-game/mounted-combat.md against engine code.

"""SRD conformance: Mounted Combat.

Maps every rule in `docs/srd/playing-the-game/mounted-combat.md` to a
test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The Mounted Combat section is short (32 lines) but it carries five
discrete rule clusters:

  1. Size and willingness gate — a creature must be one size larger and
     have appropriate anatomy to serve as a mount.
  2. Mount / Dismount cost — costs half your Speed during your move.
  3. Controlling a mount — only if trained; mount inherits your
     initiative and is limited to Dash / Disengage / Dodge.
  4. Independent mount — keeps its own initiative and acts on its own.
  5. Falling Off — DC 10 DEX save when the mount is forced-moved or
     when the rider or mount is knocked Prone; failure means Prone in
     an unoccupied 5-ft space.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.systems.action_economy import TurnState

pytestmark = pytest.mark.srd(
    "playing-the-game/mounted-combat.md",
    lines="2116-2152",
)


MONSTERS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "monsters.json"
)


def _make_creature(name: str = "Rider", *, dex: int = 14, speed: int = 30) -> Creature:
    """Plain Medium humanoid fixture for mounted-combat tests."""
    abilities = Abilities(
        strength=14,
        dexterity=dex,
        constitution=14,
        intelligence=10,
        wisdom=10,
        charisma=10,
    )
    return Creature(name=name, max_hp=20, ac=12, abilities=abilities, speed=speed)


class TestMountedCombat_SizeAndWillingnessGate:
    """SRD § Playing the Game › Mounted Combat › Intro.

    > A willing creature that is at least one size larger than a rider
    > and that has an appropriate anatomy can serve as a mount, using
    > the following rules.
    """

    def test_creature_class_has_no_size_attribute(self) -> None:
        """Source-level guard: `Creature` does not carry a `size` field.

        The SRD's "at least one size larger than a rider" gate requires
        each creature to declare a size category (Tiny / Small /
        Medium / Large / Huge / Gargantuan). `monsters.json` records
        `size` per stat block (e.g., goblin = "small") but
        `Creature` (`dnd_engine/core/creature.py:61`) carries only
        `name`, `max_hp`, `ac`, `abilities`, `speed`, and
        `active_conditions` — no `size` attribute exists. The mount
        gate therefore has nothing to check. Tracked by issue #442
        (creature size categories).
        """
        creature = _make_creature()
        assert not hasattr(creature, "size"), (
            "Creature now has a `size` attribute — the engine-side "
            "creature-size gap (#442) appears to be closing. Flip "
            "`test_mount_must_be_one_size_larger_than_rider` to a "
            "real assertion."
        )

    def test_monsters_json_carries_size_per_stat_block(self) -> None:
        """Data-parity check: `monsters.json` records a `size` per monster.

        Mount eligibility on the data side is anchored to the catalog,
        even though it's not consumed by engine logic. Every monster
        stat block declares a `size` (small / medium / large / ...).
        This test pins the data-layer side of the SRD's size gate.
        """
        monsters = json.loads(MONSTERS_JSON.read_text())
        assert monsters, "monsters.json must be non-empty"
        # Sample a few to confirm `size` is present and a known category.
        valid_sizes = {"tiny", "small", "medium", "large", "huge", "gargantuan"}
        sized = [
            (mid, m.get("size", "").lower())
            for mid, m in monsters.items()
            if m.get("size")
        ]
        assert sized, "Expected at least one monster with a `size` field"
        for mid, sz in sized:
            assert sz in valid_sizes, f"Monster {mid} has unrecognized size {sz!r}"

    def test_mount_must_be_one_size_larger_than_rider(self) -> None:
        pytest.skip(
            "GAP: there is no mount eligibility check anywhere. The "
            "SRD requires that a mount be 'at least one size larger "
            "than a rider'. No engine helper compares rider and mount "
            "size categories — and indeed Creature has no size "
            "category to compare (issue #442). Tracked by issue "
            "#526 (this audit), which depends on #442."
        )

    def test_mount_must_have_appropriate_anatomy(self) -> None:
        pytest.skip(
            "GAP: there is no anatomy / can-be-ridden flag on "
            "Creature or in monsters.json. The SRD's 'appropriate "
            "anatomy' clause (e.g., a quadruped with a back, not a "
            "puddle of slime) has no data field; nothing in "
            "monsters.json carries a `can_be_mount` / `rideable` "
            "predicate. Tracked by issue #526."
        )

    def test_mount_must_be_willing(self) -> None:
        pytest.skip(
            "GAP: there is no consent / willingness axis for monsters "
            "in the engine. The SRD's 'willing creature' clause "
            "presumes a per-creature attitude that can refuse to be "
            "ridden. No such state exists on Creature "
            "(`dnd_engine/core/creature.py`); the closest is the "
            "NPC disposition enum on `dnd_engine/core/npc.py:9` which "
            "is for conversational NPCs, not animal companions or "
            "mounts. Tracked by issue #526."
        )


class TestMountedCombat_MountAndDismountCost:
    """SRD § Playing the Game › Mounted Combat › Mounting and Dismounting.

    > During your move, you can mount a creature that is within 5 feet
    > of you or dismount. Doing so costs an amount of movement equal to
    > half your Speed (round down). For example, if your Speed is 30
    > feet, you spend 15 feet of movement to mount a horse.
    """

    def test_turn_state_can_in_principle_charge_half_speed_for_a_mount(self) -> None:
        """`TurnState.consume_movement` is the slot the cost would land in.

        The SRD's half-Speed cost would be paid out of the rider's
        per-turn movement pool. `TurnState.consume_movement(feet)`
        (`dnd_engine/systems/action_economy.py:83`) is the only path
        that drains the movement pool. This source-level guard confirms
        the slot the half-Speed cost would consume exists, even though
        no `mount_creature(target)` / `dismount()` handler invokes it.
        """
        state = TurnState(movement_remaining=30)
        # Half of 30 = 15. Burning 15 ft would leave 15 ft for the rest
        # of the turn — that's the SRD's worked example.
        assert state.consume_movement(15) is True
        assert state.movement_remaining == 15

    def test_mount_action_handler_exists(self) -> None:
        pytest.skip(
            "GAP: there is no `mount` / `dismount` handler. The "
            "scenario script executor dispatcher "
            "(`dnd_engine/scenarios/script_executor.py:200-224`) only "
            "accepts 'wait', 'attack', and 'monster_attack'. The "
            "combat-mode `available_actions` list "
            "(`dnd_engine/core/game_state.py:766`) is "
            "`['attack', 'use_item']` — no 'mount' or 'dismount'. "
            "Tracked by issue #526."
        )

    def test_mount_dismount_costs_half_speed_rounded_down(self) -> None:
        pytest.skip(
            "GAP: no mount handler exists to charge any cost (see "
            "above). The SRD's specific 'half your Speed, round down' "
            "formula (Speed 30 -> 15 ft; Speed 25 -> 12 ft) has no "
            "implementation site. `TurnState.consume_movement` "
            "(`action_economy.py:83`) takes a flat feet argument and "
            "would be the consumer once a handler is wired up. "
            "Tracked by issue #526."
        )

    def test_mount_target_must_be_within_5_feet(self) -> None:
        pytest.skip(
            "GAP: no proximity check for a mount action. The SRD's "
            "'within 5 feet of you' gate requires the same adjacency "
            "primitive used elsewhere "
            "(`dnd_engine.core.distance.is_adjacent` — "
            "`distance.py:38-56`), but no handler invokes it for a "
            "mount target. Tracked by issue #526."
        )


class TestMountedCombat_ControllingAMount:
    """SRD § Playing the Game › Mounted Combat › Controlling a Mount.

    > You can control a mount only if it has been trained to accept a
    > rider. Domesticated horses, mules, and similar creatures have
    > such training.
    > The Initiative of a controlled mount changes to match yours when
    > you mount it. It moves on your turn as you direct it, and it has
    > only three action options during that turn: Dash, Disengage, and
    > Dodge.
    > A controlled mount can move and act even on the turn that you
    > mount it.
    """

    def test_no_controlled_mount_state_exists_on_creature(self) -> None:
        """Source-level guard: `Creature` does not carry a controlled-mount link.

        The SRD model needs at least:
          - `rider`: optional Creature reference on the mount
          - `mount`: optional Creature reference on the rider
          - a per-mount "trained / controlled" flag.

        `Creature` (`dnd_engine/core/creature.py:61-93`) carries none of
        these. The active_conditions dict could carry a 'mounted_by'
        tag, but no code reads or writes one. Tracked by issue
        #526.
        """
        creature = _make_creature()
        assert not hasattr(creature, "rider")
        assert not hasattr(creature, "mount")
        assert "mounted" not in creature.active_conditions
        assert "rider" not in creature.active_conditions

    def test_mount_training_data_exists(self) -> None:
        pytest.skip(
            "GAP: there is no `trained` / `mount_trained` data field "
            "on monsters in `dnd_engine/data/srd/monsters.json`. The "
            "SRD calls out horses, mules, etc. as having training; "
            "no engine code distinguishes them from a wolf or a "
            "wyvern for the purposes of control. Tracked by issue "
            "#526."
        )

    def test_controlled_mount_initiative_matches_riders(self) -> None:
        pytest.skip(
            "GAP: `InitiativeTracker.add_combatant` "
            "(`dnd_engine/systems/initiative.py:77-102`) rolls 1d20 "
            "for each combatant independently — there is no "
            "'inherit initiative from another combatant' path. The "
            "SRD's 'Initiative of a controlled mount changes to "
            "match yours when you mount it' rule has no enforcement "
            "site; rider and mount would simply roll separately. "
            "Tracked by issue #526."
        )

    def test_controlled_mount_action_options_restricted_to_dash_disengage_dodge(
        self,
    ) -> None:
        pytest.skip(
            "GAP: the SRD restricts a controlled mount to Dash, "
            "Disengage, and Dodge on its (rider's) turn. None of "
            "Dash (issue #435), Disengage (#414), or Dodge (#438) "
            "is implemented as a playable action; there is no "
            "filter that restricts a mounted creature's action menu "
            "to those three. Tracked by issue #526 "
            "(downstream of #435 / #414 / #438)."
        )

    def test_controlled_mount_acts_on_riders_turn(self) -> None:
        pytest.skip(
            "GAP: the engine has no shared-turn / linked-turn "
            "mechanic. `InitiativeTracker.next_turn` "
            "(`initiative.py:173-202`) advances one combatant at a "
            "time; nothing 'attaches' the mount's turn to the "
            "rider's. With no rider/mount link on Creature (see "
            "above), there is also nothing for the turn loop to "
            "co-act. Tracked by issue #526."
        )

    def test_controlled_mount_can_act_on_the_turn_it_is_mounted(self) -> None:
        pytest.skip(
            "GAP: same root cause — no mount/rider linkage in the "
            "turn loop. The SRD's 'A controlled mount can move and "
            "act even on the turn that you mount it' carve-out has "
            "nothing to enable, because the base mount/dismount "
            "action handler is also missing. Tracked by issue "
            "#526."
        )


class TestMountedCombat_IndependentMount:
    """SRD § Playing the Game › Mounted Combat › Independent Mount.

    > In contrast, an independent mount—one that lets you ride but
    > ignores your control—retains its place in the Initiative order
    > and moves and acts as it likes.
    """

    def test_independent_mount_retains_its_own_initiative_slot(self) -> None:
        pytest.skip(
            "GAP: there is no 'independent mount' branch because "
            "there is no mount linkage to begin with (see "
            "TestMountedCombat_ControllingAMount). Without a "
            "controlled-vs-independent flag on a mount/rider pair, "
            "the SRD's carve-out that an independent mount keeps "
            "its own initiative entry is moot. Tracked by issue "
            "#526."
        )

    def test_independent_mount_acts_on_its_own_turn_not_riders(self) -> None:
        pytest.skip(
            "GAP: same root cause — no mount linkage and no shared "
            "turn loop. An independent mount would simply be 'just "
            "another combatant in the tracker' today, which is the "
            "right default — but the system can't *distinguish* it "
            "from a controlled mount because the controlled-mount "
            "carve-out also does not exist. Tracked by issue "
            "#526."
        )


class TestMountedCombat_FallingOff:
    """SRD § Playing the Game › Mounted Combat › Falling Off.

    > If an effect is about to move your mount against its will while
    > you're on it, you must succeed on a DC 10 Dexterity saving throw
    > or fall off, landing with the Prone condition (see "Rules
    > Glossary") in an unoccupied space within 5 feet of the mount.
    > While mounted, you must make the same save if you're knocked
    > Prone or the mount is.
    """

    def test_dex_save_primitive_exists(self) -> None:
        """`Creature.make_saving_throw('dex', dc=10)` exists.

        The SRD's "DC 10 Dexterity saving throw" requires the engine's
        DEX save primitive, which is implemented at
        `dnd_engine/core/creature.py:475` and is already used by
        spell-effect save paths. This guard pins the primitive's
        existence so the SRD's specific DC10 DEX save has a callable
        site to wire up later.
        """
        creature = _make_creature(dex=14)
        result = creature.make_saving_throw("dex", dc=10)
        assert isinstance(result, dict)
        assert "success" in result
        assert "total" in result
        assert result["dc"] == 10

    def test_prone_condition_exists_as_addable_condition(self) -> None:
        """Prone is a recognized condition on `Creature.add_condition`.

        SRD: "landing with the Prone condition." The engine's
        `Creature.add_condition` (`creature.py:242-252`) is a generic
        condition setter; 'prone' is the de-facto string used elsewhere
        (the SRD's Conditions glossary lists it). This guard confirms
        the consuming primitive exists; the dispatcher that *applies*
        it on a failed falling-off save is the gap below.
        """
        creature = _make_creature()
        creature.add_condition("prone")
        assert "prone" in creature.active_conditions

    def test_forced_mount_movement_triggers_riders_dex_save(self) -> None:
        pytest.skip(
            "GAP: no forced-movement / shove / push path consults a "
            "rider. There is no rider/mount link on Creature (see "
            "TestMountedCombat_ControllingAMount), so when a "
            "movement effect would relocate a mount, nothing alerts "
            "the rider. The Falling Off DEX save therefore has no "
            "trigger site. Tracked by issue #526."
        )

    def test_mount_knocked_prone_triggers_riders_dex_save(self) -> None:
        pytest.skip(
            "GAP: when a creature has the Prone condition applied via "
            "`Creature.add_condition('prone')` "
            "(`creature.py:242-252`), no callback fires for any "
            "linked rider. Riders and mounts are not linked in the "
            "first place. Tracked by issue #526."
        )

    def test_rider_knocked_prone_triggers_their_own_dex_save_to_stay_seated(
        self,
    ) -> None:
        pytest.skip(
            "GAP: the SRD distinguishes 'you fall off due to being "
            "knocked Prone yourself' (still requires the DC 10 DEX "
            "save) from 'mount is knocked Prone' (same save). With "
            "no rider/mount linkage, the engine can't know that a "
            "newly-prone creature is currently mounted. Tracked by "
            "issue #526."
        )

    def test_failed_save_lands_rider_prone_in_unoccupied_5ft_space(self) -> None:
        pytest.skip(
            "GAP: the SRD's 'landing with the Prone condition in an "
            "unoccupied space within 5 feet of the mount' clause "
            "requires (a) a fall-off trigger, (b) a space-search for "
            "an unoccupied adjacent tile, and (c) an entity-move + "
            "add-condition combo. None of (a)/(b)/(c) is currently "
            "wired up for a mount/rider pair. The grid primitives "
            "exist (`dnd_engine.core.distance.is_adjacent`, "
            "`distance.py:38-56`) and the prone condition exists "
            "(see test_prone_condition_exists_as_addable_condition "
            "above), so the gap is the dispatcher. Tracked by issue "
            "#526."
        )


class TestMountedCombat_CoverageMatrix:
    """Coverage matrix: every clause in mounted-combat.md is mapped.

    This class is intentionally a comment-style catalog. Each row maps
    one SRD clause to either a real test or a skipped GAP-stub above.
    """

    def test_every_srd_clause_is_audited_above(self) -> None:
        """Self-check: this audit covers every clause of the SRD section.

        Clause mapping:

          1. "willing creature ... at least one size larger ... and ...
             appropriate anatomy can serve as a mount"
             -> TestMountedCombat_SizeAndWillingnessGate (4 tests)

          2. "During your move, you can mount a creature that is
             within 5 feet of you or dismount."
             -> TestMountedCombat_MountAndDismountCost ::
                test_mount_target_must_be_within_5_feet
                + test_mount_action_handler_exists

          3. "Doing so costs an amount of movement equal to half your
             Speed (round down)."
             -> TestMountedCombat_MountAndDismountCost ::
                test_turn_state_can_in_principle_charge_half_speed_for_a_mount
                + test_mount_dismount_costs_half_speed_rounded_down

          4. "You can control a mount only if it has been trained..."
             -> TestMountedCombat_ControllingAMount ::
                test_mount_training_data_exists

          5. "Initiative of a controlled mount changes to match yours"
             -> TestMountedCombat_ControllingAMount ::
                test_controlled_mount_initiative_matches_riders

          6. "It moves on your turn as you direct it, and it has only
             three action options ... : Dash, Disengage, and Dodge."
             -> TestMountedCombat_ControllingAMount ::
                test_controlled_mount_acts_on_riders_turn
                + test_controlled_mount_action_options_restricted_to_dash_disengage_dodge

          7. "A controlled mount can move and act even on the turn
             that you mount it."
             -> TestMountedCombat_ControllingAMount ::
                test_controlled_mount_can_act_on_the_turn_it_is_mounted

          8. "In contrast, an independent mount ... retains its place
             in the Initiative order and moves and acts as it likes."
             -> TestMountedCombat_IndependentMount (2 tests)

          9. "If an effect is about to move your mount against its
             will while you're on it, you must succeed on a DC 10
             Dexterity saving throw or fall off, landing with the
             Prone condition ... within 5 feet of the mount."
             -> TestMountedCombat_FallingOff ::
                test_forced_mount_movement_triggers_riders_dex_save
                + test_failed_save_lands_rider_prone_in_unoccupied_5ft_space

         10. "While mounted, you must make the same save if you're
             knocked Prone or the mount is."
             -> TestMountedCombat_FallingOff ::
                test_mount_knocked_prone_triggers_riders_dex_save
                + test_rider_knocked_prone_triggers_their_own_dex_save_to_stay_seated

        Engine surfaces that *do* exist and are reused above:
          - Creature.make_saving_throw  (creature.py:475)
          - Creature.add_condition      (creature.py:242)
          - TurnState.consume_movement  (action_economy.py:83)
          - is_adjacent helper          (distance.py:38)

        Engine surfaces that *don't* exist (rolled up as the gap):
          - Creature.size               (#442)
          - rider/mount linkage         (#526)
          - mount/dismount action       (#526)
          - Dash/Disengage/Dodce        (#435 / #414 / #438)
          - falling-off save dispatcher (#526)
        """
        # The mapping above is the assertion in human-readable form.
        # This test exists as a citation anchor and to make the
        # coverage matrix collectable by `pytest --collect-only`.
        assert True
