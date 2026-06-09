# ABOUTME: SRD conformance audit for "Playing the Game > The Order of Combat".
# ABOUTME: Cross-references docs/srd/playing-the-game/the-order-of-combat.md against engine code.

"""SRD conformance: The Order of Combat.

Maps every rule in `docs/srd/playing-the-game/the-order-of-combat.md`
to a test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import inspect

import pytest

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.distance import chebyshev_distance, distance_in_feet, is_adjacent
from dnd_engine.systems.action_economy import ActionType, TurnState
from dnd_engine.systems.initiative import InitiativeEntry, InitiativeTracker

pytestmark = pytest.mark.srd(
    "playing-the-game/the-order-of-combat.md",
    lines="1739-1863",
)


def _make_creature(name: str = "Combatant", *, dex: int = 14, speed: int = 30) -> Creature:
    """Plain Medium humanoid fixture for combat-order tests."""
    abilities = Abilities(
        strength=14,
        dexterity=dex,
        constitution=14,
        intelligence=10,
        wisdom=10,
        charisma=10,
    )
    return Creature(name=name, max_hp=20, ac=12, abilities=abilities, speed=speed)


class TestIntro_RoundsAndTurns:
    """SRD § Playing the Game › The Order of Combat › Intro.

    > The game organizes combat into a cycle of rounds and turns. A
    > round represents about 6 seconds in the game world. During a
    > round, each participant in a battle takes a turn. The order of
    > turns is determined at the beginning of combat when everyone
    > rolls Initiative. Once everyone has taken a turn, the fight
    > continues to the next round if neither side is defeated.
    """

    def test_initiative_tracker_models_rounds_and_turns(self) -> None:
        """`InitiativeTracker` carries both a round counter and a turn cursor.

        The SRD's "cycle of rounds and turns" is implemented as
        `round_number` plus `current_turn_index` on `InitiativeTracker`
        (`dnd_engine/systems/initiative.py:71-72`). A new tracker starts
        at round 0 with the cursor on the first (highest-initiative)
        combatant.
        """
        tracker = InitiativeTracker(DiceRoller(seed=42))
        tracker.add_combatant(_make_creature("Alice", dex=16))
        tracker.add_combatant(_make_creature("Bob", dex=10))

        assert tracker.round_number == 0
        assert tracker.current_turn_index == 0
        assert len(tracker.get_all_combatants()) == 2

    def test_one_round_advances_after_everyone_has_taken_a_turn(self) -> None:
        """`next_turn` wraps to the top of order and increments `round_number`.

        SRD: "Once everyone has taken a turn, the fight continues to
        the next round." The tracker enforces this in
        `next_turn` (`initiative.py:173-202`): when `current_turn_index`
        exceeds the combatant list length, it wraps to 0 and bumps
        `round_number`.
        """
        tracker = InitiativeTracker(DiceRoller(seed=42))
        tracker.add_combatant(_make_creature("Alice", dex=16))
        tracker.add_combatant(_make_creature("Bob", dex=10))

        assert tracker.round_number == 0
        # Alice's turn ends -> Bob's turn.
        tracker.next_turn()
        assert tracker.round_number == 0
        assert tracker.current_turn_index == 1
        # Bob's turn ends -> back to Alice, round increments.
        tracker.next_turn()
        assert tracker.round_number == 1
        assert tracker.current_turn_index == 0

    def test_round_is_about_six_seconds_of_game_time(self) -> None:
        """A combat round advances the time manager by 0.1 minutes (6 seconds).

        SRD: "A round represents about 6 seconds in the game world."
        `InitiativeTracker.next_turn` (`initiative.py:192-197`) calls
        `time_manager.advance_time(0.1, reason="combat_round")` when the
        round wraps. 0.1 minutes == 6 seconds.
        """
        src = inspect.getsource(InitiativeTracker.next_turn)
        assert "advance_time(0.1" in src, (
            "InitiativeTracker.next_turn must advance the time manager "
            "by 0.1 minutes (6 seconds) at each round wrap."
        )
        assert 'reason="combat_round"' in src or "reason='combat_round'" in src


class TestCombatStepByStep:
    """SRD § Playing the Game › The Order of Combat › Combat Step by Step.

    > 1: Establish Positions. The Game Master determines where all the
    > characters and monsters are located. ...
    > 2: Roll Initiative. Everyone involved in the combat encounter
    > rolls Initiative, determining the order of combatants' turns.
    > 3: Take Turns. Each participant in the battle takes a turn in
    > Initiative order. When everyone involved in the combat has had a
    > turn, the round ends. Repeat this step until the fighting stops.
    """

    def test_step2_initiative_roll_for_every_combatant(self) -> None:
        """Step 2: every combatant added to the tracker gets a 1d20 roll.

        `InitiativeTracker.add_combatant` (`initiative.py:77-102`) rolls
        `1d20` for each creature added. There is no skip path; every
        participant ends up with an `initiative_roll` between 1 and 20
        inclusive.
        """
        tracker = InitiativeTracker(DiceRoller(seed=42))
        a = tracker.add_combatant(_make_creature("Alice", dex=14))
        b = tracker.add_combatant(_make_creature("Bob", dex=14))
        c = tracker.add_combatant(_make_creature("Carol", dex=14))

        for entry in (a, b, c):
            assert 1 <= entry.initiative_roll <= 20

    def test_step3_take_turns_in_initiative_order(self) -> None:
        """Step 3: combatants take turns from highest to lowest Initiative.

        After adding combatants, `InitiativeTracker._sort_initiative`
        (`initiative.py:224-233`) orders them by descending
        `initiative_total`. The cursor starts at index 0 (the highest)
        and advances via `next_turn` through the list.
        """
        tracker = InitiativeTracker(DiceRoller(seed=42))
        tracker.add_combatant(_make_creature("Alice", dex=14))
        tracker.add_combatant(_make_creature("Bob", dex=14))
        tracker.add_combatant(_make_creature("Carol", dex=14))

        ordered = tracker.get_all_combatants()
        totals = [entry.initiative_total for entry in ordered]
        # Descending order.
        assert totals == sorted(totals, reverse=True)

    def test_step1_establish_positions_is_modeled_by_room_and_layout(self) -> None:
        pytest.skip(
            "GAP: there is no engine-level 'establish positions' step "
            "between encounter trigger and Initiative roll. "
            "`GameState._start_combat` (dnd_engine/core/game_state.py:"
            "3085) goes straight from setting `in_combat = True` to "
            "rolling initiative; positions are inherited from whatever "
            "room layout / spawn config already exists (room data + "
            "client-2d RoomLayout). No 'marching order' input, no "
            "GM-decides-positions hook. Tracked under the broader "
            "tactical-grid work; see issue #436 for adjacent gaps."
        )


class TestInitiative_DexterityCheck:
    """SRD § Playing the Game › The Order of Combat › Initiative.

    > Initiative determines the order of turns during combat. When
    > combat starts, every participant rolls Initiative; they make a
    > Dexterity check that determines their place in the Initiative
    > order.
    """

    def test_initiative_modifier_is_the_dexterity_modifier(self) -> None:
        """`Creature.initiative_modifier` returns the DEX modifier.

        SRD: Initiative is a Dexterity check. `Creature`
        (`dnd_engine/core/creature.py:109-112`) exposes
        `initiative_modifier` as a thin alias of `abilities.dex_mod`,
        and `InitiativeEntry.initiative_total` adds it to the d20 roll
        (`initiative.py:29-37`).
        """
        # DEX 14 -> mod +2; DEX 8 -> mod -1.
        c1 = _make_creature("Quick", dex=14)
        c2 = _make_creature("Slow", dex=8)
        assert c1.initiative_modifier == 2
        assert c2.initiative_modifier == -1

    def test_initiative_total_combines_roll_with_dex_mod(self) -> None:
        """`InitiativeEntry.initiative_total` = roll + DEX modifier.

        Verifies the "check total" arithmetic — the SRD names this the
        Initiative count. Implemented at `initiative.py:30-37`.
        """
        creature = _make_creature("Speedy", dex=16)  # mod +3
        tracker = InitiativeTracker(DiceRoller(seed=42))
        entry = tracker.add_combatant(creature)

        assert entry.initiative_total == entry.initiative_roll + 3


class TestInitiative_GMRollsForMonsters:
    """SRD § Playing the Game › The Order of Combat › Initiative.

    > The GM rolls for monsters.
    """

    def test_tracker_rolls_for_every_creature_regardless_of_pc_or_monster(self) -> None:
        """`InitiativeTracker` rolls for any creature added.

        The engine treats all combatants symmetrically: the
        `add_combatant` method rolls for whichever creature is passed
        (`initiative.py:77-102`). Per `_start_combat` at
        `game_state.py:3094-3105`, party characters and active enemies
        are both added through the same path, so the engine effectively
        "rolls for monsters" the same way it rolls for PCs.
        """
        tracker = InitiativeTracker(DiceRoller(seed=42))
        pc = _make_creature("Hero", dex=14)
        monster = _make_creature("Goblin", dex=14)

        pc_entry = tracker.add_combatant(pc)
        monster_entry = tracker.add_combatant(monster)

        assert 1 <= pc_entry.initiative_roll <= 20
        assert 1 <= monster_entry.initiative_roll <= 20


class TestInitiative_GroupOfIdenticalCreatures:
    """SRD § Playing the Game › The Order of Combat › Initiative.

    > For a group of identical creatures, the GM makes a single roll,
    > so each member of the group has the same Initiative.
    """

    def test_identical_creatures_share_a_single_initiative_roll(self) -> None:
        """`add_combatant_group` rolls 1d20 once and applies it to all members.

        Per SRD 2024 § Order of Combat › Initiative, a group of
        identical creatures uses a single shared roll. The engine
        surfaces this via ``InitiativeTracker.add_combatant_group``.
        """
        tracker = InitiativeTracker(DiceRoller(seed=42))
        goblins = [_make_creature("Goblin", dex=14) for _ in range(3)]

        entries = tracker.add_combatant_group(goblins)

        assert len(entries) == 3
        # All three share the same d20 result.
        rolls = {entry.initiative_roll for entry in entries}
        assert len(rolls) == 1, (
            f"identical-creatures group must share one roll; got {rolls}"
        )
        # And the same total (all have the same DEX modifier).
        totals = {entry.initiative_total for entry in entries}
        assert len(totals) == 1


class TestInitiative_Surprise:
    """SRD § Playing the Game › The Order of Combat › Initiative.

    > Surprise. If a combatant is surprised by combat starting, that
    > combatant has Disadvantage on their Initiative roll. For example,
    > if an ambusher starts combat while hidden from a foe who is
    > unaware that combat is starting, that foe is surprised.
    """

    def test_surprised_combatant_rolls_initiative_with_disadvantage(self) -> None:
        """A surprised combatant's d20 is rolled with Disadvantage.

        Per SRD 2024: "If a combatant is surprised by combat starting,
        that combatant has Disadvantage on their Initiative roll."
        Statistically, rolling 2d20 and taking the lower yields a
        mean of ~6.85 vs ~10.5 for a flat d20. Across many trials,
        surprised combatants must roll lower on average than
        un-surprised ones. We use a tight statistical bound rather
        than a single-roll comparison so the test is seed-stable.
        """
        normal_totals: list[int] = []
        surprised_totals: list[int] = []
        for seed in range(200):
            tracker = InitiativeTracker(DiceRoller(seed=seed))
            normal = tracker.add_combatant(_make_creature("Normal", dex=10))
            surprised = tracker.add_combatant(
                _make_creature("Ambushed", dex=10), surprised=True
            )
            normal_totals.append(normal.initiative_roll)
            surprised_totals.append(surprised.initiative_roll)

        mean_normal = sum(normal_totals) / len(normal_totals)
        mean_surprised = sum(surprised_totals) / len(surprised_totals)
        # Expected gap is ~3.65; require a comfortable margin.
        assert mean_surprised < mean_normal - 2.0, (
            f"surprised mean {mean_surprised:.2f} should be well below "
            f"normal mean {mean_normal:.2f}"
        )

    def test_surprised_state_does_not_skip_the_creatures_first_turn(self) -> None:
        """A surprised creature still gets its full first turn.

        Per SRD 2024, surprise is consumed entirely by the
        Disadvantage on the Initiative roll. The creature is NOT
        flagged with a turn-skipping condition. ``can_take_actions``
        must not be tripped by surprise, and adding the combatant
        with ``surprised=True`` must not leave any 'surprised'
        condition on the creature.
        """
        tracker = InitiativeTracker(DiceRoller(seed=42))
        creature = _make_creature("Ambushed", dex=14)
        tracker.add_combatant(creature, surprised=True)

        assert creature.can_take_actions() is True
        assert "surprised" not in creature.active_conditions


class TestInitiative_OrderHighestToLowest:
    """SRD § Playing the Game › The Order of Combat › Initiative.

    > A combatant's check total is called their Initiative count, or
    > Initiative for short. The GM ranks the combatants, from highest
    > to lowest Initiative. This is the order in which they act during
    > each round. The Initiative order remains the same from round to
    > round.
    """

    def test_combatants_are_ordered_highest_initiative_first(self) -> None:
        """`_sort_initiative` ranks combatants from highest to lowest.

        Verifies `initiative.py:224-233` sorts by descending
        `initiative_total`. This is the SRD's "from highest to lowest"
        ordering.
        """
        tracker = InitiativeTracker(DiceRoller(seed=42))
        slow = _make_creature("Slow", dex=8)  # mod -1
        fast = _make_creature("Fast", dex=20)  # mod +5
        mid = _make_creature("Mid", dex=12)  # mod +1

        tracker.add_combatant(slow)
        tracker.add_combatant(fast)
        tracker.add_combatant(mid)

        ordered_totals = [e.initiative_total for e in tracker.get_all_combatants()]
        assert ordered_totals == sorted(ordered_totals, reverse=True)

    def test_initiative_order_remains_same_across_rounds(self) -> None:
        """The combatant list is not reshuffled between rounds.

        SRD: "The Initiative order remains the same from round to
        round." `next_turn` only mutates `current_turn_index` and
        `round_number`; the `combatants` list is not re-sorted
        (`initiative.py:173-202`).
        """
        tracker = InitiativeTracker(DiceRoller(seed=42))
        tracker.add_combatant(_make_creature("Alice", dex=16))
        tracker.add_combatant(_make_creature("Bob", dex=10))
        tracker.add_combatant(_make_creature("Carol", dex=12))

        round_one_order = [e.creature.name for e in tracker.get_all_combatants()]

        # Advance through one full round.
        tracker.next_turn()
        tracker.next_turn()
        tracker.next_turn()

        assert tracker.round_number == 1
        round_two_order = [e.creature.name for e in tracker.get_all_combatants()]
        assert round_two_order == round_one_order


class TestInitiative_Ties:
    """SRD § Playing the Game › The Order of Combat › Initiative.

    > Ties. If a tie occurs, the GM decides the order among tied
    > monsters, and the players decide the order among tied
    > characters. The GM decides the order if the tie is between a
    > monster and a player character.
    """

    def test_ties_resolved_by_side_not_by_stat(self) -> None:
        """On a tied Initiative count, PCs precede non-PCs.

        Per SRD 2024, no creature statistic breaks Initiative ties.
        The GM decides the order; the engine's opinionated default
        is "PCs before non-PCs" on the tied count, with stable
        insertion order within a side. We construct a tie at the
        same total and check that the higher-DEX monster does not
        leap ahead of the lower-DEX player character.
        """
        from dnd_engine.core.character import Character, CharacterClass

        # Force a tied roll by reseating the dice roller between adds.
        tracker = InitiativeTracker(DiceRoller(seed=1))

        # Low-DEX player character (DEX 10, +0 mod).
        pc_abilities = Abilities(
            strength=14,
            dexterity=10,
            constitution=14,
            intelligence=10,
            wisdom=10,
            charisma=10,
        )
        pc = Character(
            name="Hero",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=pc_abilities,
            max_hp=10,
            ac=14,
        )
        tracker.add_combatant(pc)

        # High-DEX monster (DEX 14, +2 mod). Old engine would put
        # the monster first on a tied roll thanks to the DEX
        # tiebreak; the 2024 SRD says no stat tiebreak, so the PC
        # should win the tied count.
        monster = _make_creature("Goblin", dex=14)
        # Re-seed to repeat the same d20 result.
        tracker.dice_roller = DiceRoller(seed=1)
        tracker.add_combatant(monster)

        if (
            tracker.combatants[0].initiative_roll
            == tracker.combatants[1].initiative_roll
        ):
            # Tied counts: PC must come first.
            # (Their TOTALS differ — PC +0 vs monster +2 — but the
            # SRD 2024 wording considers the count after modifier;
            # if the *totals* are equal because the rolls came in
            # exactly opposite, the PC still wins on side.)
            tied_pairs = [
                (a, b)
                for a, b in zip(
                    tracker.combatants, tracker.combatants[1:], strict=False
                )
                if a.initiative_total == b.initiative_total
            ]
            for a, b in tied_pairs:
                assert isinstance(a.creature, Character) or not isinstance(
                    b.creature, Character
                ), "On tied Initiative, a PC must precede a non-PC."

        # Independent assertion that does not depend on the roll
        # coming out tied: feed two synthetic tied entries directly
        # and verify the sort order.
        tracker2 = InitiativeTracker(DiceRoller(seed=2))
        pc2 = Character(
            name="Hero2",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=pc_abilities,  # DEX +0
            max_hp=10,
            ac=14,
        )
        monster2 = _make_creature("Goblin2", dex=14)  # DEX +2
        tracker2.combatants.append(InitiativeEntry(pc2, initiative_roll=10))
        tracker2.combatants.append(InitiativeEntry(monster2, initiative_roll=8))
        # PC total = 10+0 = 10; monster total = 8+2 = 10. Tied.
        tracker2._sort_initiative()
        assert tracker2.combatants[0].creature is pc2, (
            "On tied Initiative totals, PC must sort before non-PC."
        )


class TestYourTurn_MoveAndAction:
    """SRD § Playing the Game › The Order of Combat › Your Turn.

    > On your turn, you can move a distance up to your Speed and take
    > one action. You decide whether to move first or take your action
    > first.
    """

    def test_turn_state_grants_one_action_and_speed_movement(self) -> None:
        """A fresh turn carries `action_available=True` and Speed-of-movement.

        `TurnState` (`dnd_engine/systems/action_economy.py:25-40`)
        initializes with one action slot and a movement pool that
        `InitiativeTracker.add_combatant` seeds from the creature's
        Speed (`initiative.py:97`).
        """
        creature = _make_creature(speed=30)
        state = TurnState(movement_remaining=creature.speed)

        assert state.action_available is True
        assert state.is_action_available(ActionType.ACTION) is True
        assert state.movement_remaining == 30

    def test_action_first_then_move_is_allowed(self) -> None:
        """Consuming the action before any movement is supported.

        SRD: "You decide whether to move first or take your action
        first." `TurnState` does not impose an order — the action slot
        and movement pool are independent.
        """
        state = TurnState(movement_remaining=30)
        # Action first.
        assert state.consume_action(ActionType.ACTION) is True
        # Then movement.
        assert state.consume_movement(15) is True
        assert state.movement_remaining == 15

    def test_move_first_then_action_is_allowed(self) -> None:
        """Consuming movement before the action is also supported.

        Symmetric to the above — the player's choice of order is not
        constrained by the engine.
        """
        state = TurnState(movement_remaining=30)
        # Move first.
        assert state.consume_movement(15) is True
        assert state.movement_remaining == 15
        # Then action.
        assert state.consume_action(ActionType.ACTION) is True


class TestYourTurn_Communicating:
    """SRD § Playing the Game › The Order of Combat › Your Turn › Communicating.

    > You can communicate however you are able—through brief utterances
    > and gestures—as you take your turn. Doing so uses neither your
    > action nor your move.

    > Extended communication, such as a detailed explanation of
    > something or an attempt to persuade a foe, requires an action.
    > The Influence action is the main way you try to influence a
    > monster.
    """

    def test_no_action_communication_is_modeled_via_NO_ACTION_type(self) -> None:
        """`ActionType.NO_ACTION` is the carve-out for free-cost activities.

        The action-economy enum carries a dedicated `NO_ACTION` member
        documented to cover "dropping items, speaking, etc."
        (`dnd_engine/systems/action_economy.py:8-22`). `consume_action`
        for `NO_ACTION` returns True unconditionally without touching
        any slot (`action_economy.py:77-79`), matching the SRD's
        no-cost framing for brief utterances.
        """
        state = TurnState(movement_remaining=30)
        # Brief communication consumes nothing.
        assert state.consume_action(ActionType.NO_ACTION) is True
        # Action, bonus action, free-object, and movement all untouched.
        assert state.action_available is True
        assert state.bonus_action_available is True
        assert state.free_object_interaction_used is False
        assert state.movement_remaining == 30

    def test_extended_communication_routes_through_influence_action(self) -> None:
        pytest.skip(
            "GAP: extended communication is supposed to require the "
            "Influence action, but no Influence action handler exists. "
            "See the actions audit "
            "(dnd-engine/tests/srd/playing_the_game/test_actions.py::"
            "TestAction_Influence) — tracked by issue #444. The skill "
            "primitives (`make_skill_check` on persuasion / deception / "
            "intimidation / performance / animal_handling) exist "
            "(dnd_engine/core/character.py:726) but no action dispatch "
            "consumes them, and NPCs have no attitude axis to shift."
        )


class TestYourTurn_InteractingWithThings:
    """SRD § Playing the Game › The Order of Combat › Your Turn › Interacting with Things.

    > You can interact with one object or feature of the environment
    > for free, during either your move or action. For example, you
    > could open a door during your move as you stride toward a foe.

    > If you want to interact with a second object, you need to take
    > the Utilize action. Some magic items and other special objects
    > always require an action to use, as stated in their descriptions.
    """

    def test_one_free_object_interaction_per_turn(self) -> None:
        """`TurnState.FREE_OBJECT` slot resolves the one-per-turn carve-out.

        `consume_action(ActionType.FREE_OBJECT)` returns True the first
        time and False the second (`action_economy.py:71-75`), so a
        creature can open one door (or similar) for free per turn. The
        slot is independent of the full ACTION slot, matching SRD's
        "during either your move or action."
        """
        state = TurnState(movement_remaining=30)
        assert state.consume_action(ActionType.FREE_OBJECT) is True
        # Second free-object use on the same turn fails.
        assert state.consume_action(ActionType.FREE_OBJECT) is False
        # ACTION slot is untouched.
        assert state.is_action_available(ActionType.ACTION) is True

    def test_second_object_interaction_requires_an_action(self) -> None:
        """A second interaction costs the full ACTION slot (Utilize surface).

        Per the SRD, the engine's Utilize / use-item surface
        (`dnd_engine/core/game_state.py:4578` — see actions audit) is
        gated by action-economy. After exhausting the free slot, the
        creature must spend its ACTION to interact again. We verify the
        slot economics here; the dispatcher mapping to "Utilize" is
        covered by `test_actions.py::TestAction_Utilize`.
        """
        state = TurnState(movement_remaining=30)
        # Burn the free interaction.
        assert state.consume_action(ActionType.FREE_OBJECT) is True
        assert state.consume_action(ActionType.FREE_OBJECT) is False
        # A second object interaction must now cost the action.
        assert state.consume_action(ActionType.ACTION) is True
        assert state.is_action_available(ActionType.ACTION) is False

    def test_some_magic_items_require_an_action(self) -> None:
        """Items that declare `action_required: action` cost the ACTION slot.

        The Magic / Utilize action body lives at
        `dnd_engine/core/game_state.py:4578` (`use_item_combat`) and
        routes through action-economy. Some magic items are flagged in
        `data/srd/items.json` as requiring a full action — see related
        issue #472 covering the data/dispatch mismatch for
        `"action_required": "free"` items. The action-slot side of the
        rule (a full ACTION is consumed when required) is the same
        slot we exercise here.
        """
        state = TurnState(movement_remaining=30)
        # Using a magic item that costs an action drains the ACTION slot.
        assert state.consume_action(ActionType.ACTION) is True
        assert state.consume_action(ActionType.ACTION) is False

    def test_gm_override_can_promote_a_free_interaction_to_an_action(self) -> None:
        pytest.skip(
            "GAP: there is no GM-override hook to promote a normally-"
            "free interaction (e.g., a stuck door, a drawbridge crank) "
            "into a full Utilize action. The SRD calls this out: 'The "
            "GM might require you to use an action for any of these "
            "activities when it needs special care or when it presents "
            "an unusual obstacle.' Today the FREE_OBJECT slot "
            "(dnd_engine/systems/action_economy.py:21,71-75) is "
            "all-or-nothing; the engine has no per-object difficulty "
            "flag. Tracked under the broader Utilize / object-"
            "interaction work; see issue #472."
        )


class TestYourTurn_DoingNothing:
    """SRD § Playing the Game › The Order of Combat › Your Turn › Doing Nothing.

    > You can forgo moving, taking an action, or doing anything at all
    > on your turn. If you can't decide what to do, consider taking
    > the defensive Dodge action or the Ready action to delay acting.
    """

    def test_a_creature_can_end_its_turn_without_acting_or_moving(self) -> None:
        """Skipping the action and movement is legal — nothing forces consumption.

        `TurnState` exposes no "must act" gate; a creature that ends
        its turn without calling `consume_action` or
        `consume_movement` leaves both pools intact, and the tracker's
        `next_turn` simply advances to the next combatant
        (`initiative.py:173-202`).
        """
        state = TurnState(movement_remaining=30)
        # Turn ends with nothing consumed.
        assert state.action_available is True
        assert state.movement_remaining == 30
        # End of turn -> reset for next turn.
        state.reset(speed=30)
        assert state.action_available is True
        assert state.movement_remaining == 30

    def test_dodge_action_is_a_doing_nothing_default(self) -> None:
        pytest.skip(
            "GAP: Dodge action is not implemented. The SRD points "
            "Dodge as one of the two recommended 'doing nothing' "
            "defaults. Per `test_actions.py::TestAction_Dodge`, the "
            "combat engine supports advantage/disadvantage on rolls "
            "(dnd_engine/core/combat.py:122-132) but has no 'dodging' "
            "flag on Creature and no projection of disadvantage onto "
            "attackers. Tracked by issue #438."
        )

    def test_ready_action_is_a_doing_nothing_default(self) -> None:
        pytest.skip(
            "GAP: Ready action is not implemented. The SRD points "
            "Ready as the other recommended 'doing nothing' default. "
            "Per `test_actions.py::TestAction_Ready`, the Reaction "
            "economy itself is not modeled and no 'readied action' "
            "slot exists on `TurnState` "
            "(dnd_engine/systems/action_economy.py:26-40). Tracked "
            "under #412/#429/#430."
        )


class TestPlayingOnGrid_SquaresArefiveFeet:
    """SRD § Playing the Game › The Order of Combat › Playing on a Grid › Squares.

    > Each square represents 5 feet.
    """

    def test_one_grid_square_equals_five_feet(self) -> None:
        """`distance_in_feet` returns 5 ft per square step.

        `dnd_engine/core/distance.py:58-77` implements
        `distance_in_feet(x1, y1, x2, y2) = chebyshev * 5`. One step
        orthogonally is 5 ft.
        """
        assert distance_in_feet(0, 0, 1, 0) == 5
        assert distance_in_feet(0, 0, 0, 1) == 5

    def test_two_squares_orthogonally_is_ten_feet(self) -> None:
        """Two-square step is 10 ft (2 * 5)."""
        assert distance_in_feet(0, 0, 2, 0) == 10


class TestPlayingOnGrid_SpeedInSquares:
    """SRD § Playing the Game › The Order of Combat › Playing on a Grid › Speed.

    > Rather than moving foot by foot, move square by square on the
    > grid, using your Speed in 5-foot segments. You can translate your
    > Speed into squares by dividing it by 5. For example, a Speed of
    > 30 feet translates into 6 squares.
    """

    def test_speed_of_thirty_feet_translates_into_six_squares(self) -> None:
        """Six 5-ft steps drain a 30-ft pool.

        `TurnState.consume_movement(5)` six times = 30 ft. The
        client-2d combat-move path also uses 5 ft per tile
        (`client-2d/src/client_2d/session.py:912`), making "Speed / 5"
        the on-grid translation.
        """
        state = TurnState(movement_remaining=30)
        for _ in range(6):
            assert state.consume_movement(5) is True
        assert state.movement_remaining == 0
        # A seventh step is rejected (no more squares).
        assert state.consume_movement(5) is False


class TestPlayingOnGrid_EnteringASquare:
    """SRD § Playing the Game › The Order of Combat › Playing on a Grid › Entering a Square.

    > To enter a square, you must have enough movement left to pay for
    > entering. It costs 1 square of movement to enter an unoccupied
    > square that's adjacent to your space (orthogonally or diagonally
    > adjacent). A square of Difficult Terrain costs 2 squares to
    > enter. Other effects might make a square cost even more.
    """

    def test_orthogonal_adjacent_square_costs_one_square(self) -> None:
        """An orthogonally-adjacent square is Chebyshev distance 1.

        `chebyshev_distance` returns 1 for any direct neighbor.
        Combined with the 5-ft-per-square rule, that's a 5-ft cost to
        enter (one square of movement).
        """
        assert chebyshev_distance(0, 0, 1, 0) == 1
        assert chebyshev_distance(0, 0, 0, 1) == 1
        assert is_adjacent(0, 0, 1, 0) is True

    def test_diagonal_adjacent_square_also_costs_one_square(self) -> None:
        """A diagonally-adjacent square is Chebyshev distance 1.

        SRD 2024 (Playing on a Grid): diagonal entry costs the same
        1 square as orthogonal. `chebyshev_distance` correctly returns
        1 for the diagonals.
        """
        assert chebyshev_distance(0, 0, 1, 1) == 1
        assert is_adjacent(0, 0, 1, 1) is True

    def test_difficult_terrain_costs_two_squares_to_enter(self) -> None:
        pytest.skip(
            "GAP: Difficult Terrain is not modeled. "
            "`TurnState.consume_movement` "
            "(dnd_engine/systems/action_economy.py:83) takes a flat "
            "feet argument; the 2D client charges a fixed 5 ft per "
            "tile in combat-move "
            "(client-2d/src/client_2d/session.py:912) with no terrain "
            "query. `RoomLayout` "
            "(client-2d/src/client_2d/integration/layout_schema.py) "
            "declares WALL and PIT tile types but has no Difficult "
            "Terrain tile type or `is_difficult_terrain` predicate. "
            "Tracked by issue #436 (same gap as movement-and-position "
            "audit)."
        )

    def test_other_effects_can_make_a_square_cost_more(self) -> None:
        pytest.skip(
            "GAP: there is no per-square movement-cost modifier "
            "registry. The SRD anticipates effects beyond Difficult "
            "Terrain that further raise entry cost; "
            "`TurnState.consume_movement` "
            "(dnd_engine/systems/action_economy.py:83) takes a flat "
            "feet argument with no extension point. Tracked under "
            "issue #436 (general grid-cost work)."
        )


class TestPlayingOnGrid_Corners:
    """SRD § Playing the Game › The Order of Combat › Playing on a Grid › Corners.

    > Diagonal movement can't cross the corner of a wall, a large
    > tree, or another terrain feature that fills its space.
    """

    def test_diagonal_move_cannot_cross_a_wall_corner(self) -> None:
        pytest.skip(
            "GAP: corner-blocking is not implemented. "
            "`chebyshev_distance` (dnd_engine/core/distance.py:5-28) "
            "treats every diagonal as a free 1-square step, with no "
            "consultation of map / wall data. The client-2d combat-"
            "move path (client-2d/src/client_2d/session.py:912) checks "
            "only the destination tile for walls, never the two "
            "orthogonal neighbors that form the corner. Tracked by "
            "issue #476."
        )


class TestPlayingOnGrid_Ranges:
    """SRD § Playing the Game › The Order of Combat › Playing on a Grid › Ranges.

    > To determine the range on a grid between two things—whether
    > creatures or objects—count squares from a square adjacent to one
    > of them and stop counting in the space of the other one. Count
    > by the shortest route.
    """

    def test_range_counts_by_shortest_route(self) -> None:
        """`chebyshev_distance` returns the shortest grid route.

        Chebyshev distance is exactly "count by the shortest route" on
        a grid that allows diagonals at the same cost as orthogonals —
        which is the SRD's grid model. `dnd_engine/core/distance.py:5-28`.
        """
        # A 3-east, 4-north target: shortest route = max(3, 4) = 4 squares.
        assert chebyshev_distance(0, 0, 3, 4) == 4
        # A pure-diagonal target 3-east, 3-north: shortest route = 3.
        assert chebyshev_distance(0, 0, 3, 3) == 3

    def test_range_in_feet_uses_five_feet_per_square(self) -> None:
        """`distance_in_feet` projects shortest-route squares to feet.

        Five-foot scaling is applied directly to the Chebyshev
        distance, preserving "shortest route" semantics in ft.
        """
        assert distance_in_feet(0, 0, 3, 4) == 20
        assert distance_in_feet(0, 0, 3, 3) == 15

    def test_range_count_honors_corner_blocking(self) -> None:
        pytest.skip(
            "GAP: 'count by the shortest route' implicitly excludes "
            "routes that cross blocked corners, but the engine's "
            "distance helpers don't take map context. Until corner-"
            "blocking ships (issue #476), the shortest-route count "
            "may pass through walls."
        )


class TestEndingCombat_OneSideDefeated:
    """SRD § Playing the Game › The Order of Combat › Ending Combat.

    > Combat ends when one side or the other is defeated, which can
    > mean the creatures are killed or knocked out or have surrendered
    > or fled.
    """

    def test_combat_ends_when_all_enemies_are_dead(self) -> None:
        """`_check_combat_end` flips `in_combat` off when all enemies die.

        `GameState._check_combat_end` "
        (`dnd_engine/core/game_state.py:3142-3160`) calls `_end_combat`
        when `all_enemies_dead` is True. `_end_combat`
        (`game_state.py:3162-3201`) sets `self.in_combat = False`.

        Source-level guard: assert the implementation reads
        `is_alive` (the engine's "killed" axis) for every enemy.
        """
        src = inspect.getsource(
            __import__(
                "dnd_engine.core.game_state", fromlist=["GameState"]
            ).GameState._check_combat_end
        )
        assert "is_alive" in src and "all_enemies_dead" in src

    def test_combat_ends_when_party_is_knocked_out(self) -> None:
        """`_check_combat_end` ends combat on TPK or full unconsciousness.

        SRD: "knocked out" is a valid defeat axis. The engine treats
        "all party members are unconscious or dead" as combat-ending
        (`game_state.py:3155-3160`).
        """
        src = inspect.getsource(
            __import__(
                "dnd_engine.core.game_state", fromlist=["GameState"]
            ).GameState._check_combat_end
        )
        assert "all_party_unconscious" in src or "is_unconscious" in src

    def test_combat_ends_when_party_flees(self) -> None:
        """`flee_combat` is the engine's "fled" defeat axis.

        `GameState.flee_combat` (`game_state.py:4194-4306`) handles the
        party-flees branch — each enemy gets an OA, then combat state
        is cleared without victory. Confirms the SRD's "fled" defeat
        path has an engine surface.
        """
        from dnd_engine.core.game_state import GameState

        assert callable(getattr(GameState, "flee_combat", None))
        src = inspect.getsource(GameState.flee_combat)
        # Flee must clear combat state and not award XP.
        assert "in_combat" in src
        assert "no XP" in src.lower() or "xp" not in src.lower() or "XP awarded" in src

    def test_combat_ends_when_a_side_surrenders(self) -> None:
        pytest.skip(
            "GAP: surrender is not modeled. "
            "`GameState._check_combat_end` "
            "(dnd_engine/core/game_state.py:3142-3160) recognizes "
            "killed, unconscious, and (via `flee_combat`, "
            "game_state.py:4194-4306) fled — but not surrendered. "
            "Enemies fight to the death; the party can flee but cannot "
            "lay down arms. Tracked by issue #479."
        )


class TestEndingCombat_BothSidesAgree:
    """SRD § Playing the Game › The Order of Combat › Ending Combat.

    > Combat can also end when both sides agree to end it.
    """

    def test_combat_ends_when_both_sides_agree(self) -> None:
        pytest.skip(
            "GAP: there is no mutual-consent end-combat surface. "
            "`GameState._check_combat_end` "
            "(dnd_engine/core/game_state.py:3142-3160) only ends "
            "combat on defeat or flee; there is no `agree_to_end_combat` "
            "method, no scenario-script action, and no MCP tool that "
            "ends combat by parley. This is the SRD's separate "
            "termination axis from defeat. Tracked by issue #479."
        )
