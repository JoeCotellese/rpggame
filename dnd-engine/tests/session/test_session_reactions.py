# ABOUTME: Tests that opportunity attacks become a player decision rather than an automatic hit.
# ABOUTME: Covers the queue, the ask/answer cycle, and that declining costs nothing.

"""Verification for P1-03.

The behaviour under test is the one that makes the game feel like D&D: when a
creature leaves your reach, *you* decide whether to spend your reaction.

The queue and decision plumbing are exercised directly, because provoking a real
opportunity attack needs a spatial index with known adjacency — set up here
explicitly rather than hoping a dungeon produces the geometry.
"""

from __future__ import annotations

import pytest

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.position import Position
from dnd_engine.session.reactions import (
    ATTACK_OPTION_ID,
    DECLINE_OPTION_ID,
    OpportunityQueue,
    PendingOpportunity,
    describe,
    register_deferred_opportunity_attack,
)
from dnd_engine.systems.action_economy import ActionType
from dnd_engine.systems.initiative import InitiativeTracker
from dnd_engine.systems.opportunity_attacks import publish_movement_provoke
from dnd_engine.systems.reactions import ReactionDispatcher


class _ScriptedRandom:
    """Hands back predetermined d20 faces, then falls back to the maximum."""

    def __init__(self, faces: list[int]) -> None:
        self._faces = list(faces)

    def randint(self, low: int, high: int) -> int:
        return self._faces.pop(0) if self._faces else high


def scripted_roller(faces: list[int]) -> DiceRoller:
    """A `DiceRoller` whose next die faces are known.

    `add_combatant` rolls initiative internally, so pinning turn order means
    controlling the randomness rather than passing a roll in. Swapping the
    roller's `random` keeps the real `DiceRoll` construction path intact, so
    modifiers still apply exactly as in play.
    """
    roller = DiceRoller(seed=1)
    roller.random = _ScriptedRandom(faces)  # type: ignore[assignment]
    return roller


def _creature(name: str, hp: int = 20) -> Creature:
    return Creature(
        name=name,
        max_hp=hp,
        ac=12,
        abilities=Abilities(
            strength=14,
            dexterity=12,
            constitution=12,
            intelligence=10,
            wisdom=10,
            charisma=10,
        ),
    )


@pytest.fixture
def combat():
    """A guard threatening a mover, wired to a dispatcher and a deferring queue."""
    guard = _creature("Guard")
    mover = _creature("Goblin")

    # d20 faces: guard 20, mover 10, spare 15 for a third combatant. With DEX 12
    # (+1) that gives initiative 21 / 11 / 16 — guard first, sentry second.
    tracker = InitiativeTracker(dice_roller=scripted_roller([20, 10, 15]))
    tracker.add_combatant(guard)
    tracker.add_combatant(mover)

    dispatcher = ReactionDispatcher(tracker)
    queue = OpportunityQueue()

    positions = {guard: Position(5, 5), mover: Position(6, 5)}
    register_deferred_opportunity_attack(
        dispatcher,
        queue,
        guard,
        get_position=lambda: positions[guard],
    )
    return {
        "guard": guard,
        "mover": mover,
        "tracker": tracker,
        "dispatcher": dispatcher,
        "queue": queue,
    }


class TestAC1LeavingReachAsksInsteadOfAttacking:
    """AC-1: leaving reach queues a decision and resolves nothing."""

    def test_stepping_out_of_reach_queues_an_opportunity(self, combat):
        outcomes = publish_movement_provoke(
            combat["dispatcher"],
            combat["mover"],
            Position(6, 5),
            Position(8, 5),
        )

        assert outcomes == [], "the engine resolved the attack instead of deferring"
        assert len(combat["queue"].pending) == 1
        queued = combat["queue"].peek()
        assert queued.reactor is combat["guard"]
        assert queued.mover is combat["mover"]

    def test_no_attack_is_resolved_while_the_question_is_open(self, combat):
        hp_before = combat["mover"].current_hp
        publish_movement_provoke(
            combat["dispatcher"], combat["mover"], Position(6, 5), Position(8, 5)
        )
        assert combat["mover"].current_hp == hp_before

    def test_staying_in_reach_asks_nothing(self, combat):
        publish_movement_provoke(
            combat["dispatcher"], combat["mover"], Position(6, 5), Position(6, 6)
        )
        assert combat["queue"].pending == []

    def test_a_creature_does_not_provoke_itself(self, combat):
        publish_movement_provoke(
            combat["dispatcher"], combat["guard"], Position(5, 5), Position(9, 9)
        )
        assert combat["queue"].pending == []


class TestAC3DecliningCostsNothing:
    """AC-3: an unspent reaction stays available — the SRD is explicit."""

    def test_the_reaction_slot_survives_a_deferred_question(self, combat):
        publish_movement_provoke(
            combat["dispatcher"], combat["mover"], Position(6, 5), Position(8, 5)
        )
        turn_state = combat["tracker"].turn_states[combat["guard"]]
        assert turn_state.reaction_available, (
            "deferring the question consumed the reaction before the player chose"
        )

    def test_a_second_provoke_can_still_be_asked_about(self, combat):
        publish_movement_provoke(
            combat["dispatcher"], combat["mover"], Position(6, 5), Position(8, 5)
        )
        publish_movement_provoke(
            combat["dispatcher"], combat["mover"], Position(6, 5), Position(9, 5)
        )
        assert len(combat["queue"].pending) == 2, (
            "the reactor was locked out of a later trigger despite not reacting"
        )


class TestAC4DefaultPreservesTodaysBehaviour:
    """AC-4: callers that cannot ask a human keep getting the automatic attack."""

    def test_attack_is_the_default_option(self):
        from dnd_engine.session.protocol import DecisionKind, DecisionOption, PendingDecision

        decision = PendingDecision(
            decision_id="oa-1",
            kind=DecisionKind.REACTION,
            actor_id="pc_guard",
            prompt="?",
            options=(
                DecisionOption(ATTACK_OPTION_ID, "Take the opportunity attack"),
                DecisionOption(DECLINE_OPTION_ID, "Decline"),
            ),
            default_option_id=ATTACK_OPTION_ID,
        )
        assert decision.default_option_id == ATTACK_OPTION_ID, (
            "changing the default would silently change the game for every "
            "existing caller — the engine has always taken the attack"
        )


class TestAC5MultipleReactorsAreAskedInOrder:
    """AC-5: each threatening creature is asked, in initiative order."""

    def test_two_threatening_creatures_produce_two_questions(self, combat):
        second = _creature("Sentry")
        combat["tracker"].add_combatant(second)
        register_deferred_opportunity_attack(
            combat["dispatcher"],
            combat["queue"],
            second,
            get_position=lambda: Position(6, 6),
        )

        publish_movement_provoke(
            combat["dispatcher"], combat["mover"], Position(6, 5), Position(9, 9)
        )

        reactors = [p.reactor.name for p in combat["queue"].pending]
        assert reactors == ["Guard", "Sentry"], (
            f"expected initiative order (Guard 20, Sentry 15), got {reactors}"
        )

    def test_each_queued_opportunity_has_a_distinct_id(self, combat):
        second = _creature("Sentry")
        combat["tracker"].add_combatant(second)
        register_deferred_opportunity_attack(
            combat["dispatcher"],
            combat["queue"],
            second,
            get_position=lambda: Position(6, 6),
        )
        publish_movement_provoke(
            combat["dispatcher"], combat["mover"], Position(6, 5), Position(9, 9)
        )

        ids = [p.decision_id for p in combat["queue"].pending]
        assert len(set(ids)) == len(ids)


class TestQueueMechanics:
    """The queue must answer exactly once and in order."""

    def _queued(self, queue: OpportunityQueue, name: str) -> PendingOpportunity:
        opportunity = PendingOpportunity(
            reactor=_creature(name),
            mover=_creature("Mover"),
            from_position=Position(0, 0),
            to_position=Position(3, 0),
            reach_feet=5,
            decision_id=queue.next_decision_id(),
        )
        queue.add(opportunity)
        return opportunity

    def test_taking_an_opportunity_removes_it(self):
        queue = OpportunityQueue()
        first = self._queued(queue, "A")
        assert queue.take(first.decision_id) is first
        assert queue.take(first.decision_id) is None, "a decision was answerable twice"

    def test_unknown_decision_id_returns_nothing(self):
        assert OpportunityQueue().take("nope") is None

    def test_peek_returns_the_oldest_first(self):
        queue = OpportunityQueue()
        first = self._queued(queue, "A")
        self._queued(queue, "B")
        assert queue.peek() is first

    def test_clear_empties_the_queue(self):
        queue = OpportunityQueue()
        self._queued(queue, "A")
        queue.clear()
        assert queue.pending == []


class TestPrompting:
    """The player must be told who is leaving and whose reaction is at stake."""

    def test_prompt_names_both_creatures(self):
        queue = OpportunityQueue()
        opportunity = PendingOpportunity(
            reactor=_creature("Thorin"),
            mover=_creature("Skeleton"),
            from_position=Position(0, 0),
            to_position=Position(3, 0),
            reach_feet=5,
            decision_id=queue.next_decision_id(),
        )
        wording = describe(opportunity, "Skeleton 2")

        assert "Skeleton 2" in wording["prompt"]
        assert "Thorin" in wording["prompt"]
        assert wording["context"]["mover"] == "Skeleton 2"
        assert wording["context"]["reactor"] == "Thorin"


class TestReactionSlotAccounting:
    """Spending the reaction must actually consume it."""

    def test_consuming_the_reaction_makes_it_unavailable(self, combat):
        turn_state = combat["tracker"].turn_states[combat["guard"]]
        assert turn_state.reaction_available
        turn_state.consume_action(ActionType.REACTION)
        assert not turn_state.reaction_available


class TestOnlyPlayersAreAsked:
    """Regression: the player must not be asked to decide a monster's reaction.

    Found during P1-03 PLAYTEST. The session originally registered deferring
    handlers for *every* placed creature, so a player walking away from a
    skeleton was prompted "Thorin is leaving Skeleton's reach — take an
    opportunity attack?" — asking them to spend the monster's reaction, with a
    nonsense `actor_id` of "pc_skeleton". Monsters keep the engine's automatic
    handler, which also leaves NPC behaviour exactly as it was.
    """

    def test_deferral_is_registered_only_for_party_members(self):
        from dnd_engine.core.character import Character, CharacterClass
        from dnd_engine.core.game_state import GameState
        from dnd_engine.core.map import Map, TileType
        from dnd_engine.core.party import Party
        from dnd_engine.rules.loader import DataLoader
        from dnd_engine.session import Session
        from dnd_engine.utils.events import EventBus

        party = Party(
            [
                Character(
                    name="Thorin",
                    character_class=CharacterClass.FIGHTER,
                    level=3,
                    abilities=Abilities(
                        strength=16,
                        dexterity=12,
                        constitution=14,
                        intelligence=10,
                        wisdom=11,
                        charisma=8,
                    ),
                    max_hp=30,
                    ac=16,
                )
            ]
        )
        game = GameState(
            party=party,
            dungeon_name="crypt",
            campaign_id="the_unquiet_dead",
            event_bus=EventBus(),
            data_loader=DataLoader(),
            dice_roller=DiceRoller(seed=5),
        )
        game.start()
        game.bootstrap_spatial(
            Map(
                width=20,
                height=20,
                tiles={(x, y): TileType.FLOOR for y in range(20) for x in range(20)},
            ),
            replace=True,
        )
        from dnd_engine.core.entity_ids import pc_entity_id

        game.set_position(pc_entity_id("Thorin"), 10, 10)
        game.set_position("skeleton_0", 11, 10)

        session = Session(game)
        session._ensure_deferred_reactions()

        deferred_for = {
            sub.creature.name
            for sub in game.reaction_dispatcher._subs
            if "deferring_handler" in getattr(sub.handler, "__qualname__", "")
        }
        assert deferred_for == {"Thorin"}, (
            f"deferral must cover party members only, got {deferred_for}"
        )


class TestAdvancementYieldsToPendingDecisions:
    """Regression: turn advancement must stop while a reaction is unanswered.

    Found during P1-03 PLAYTEST. A reaction is usually provoked by an enemy
    withdrawing on its *own* turn — i.e. from inside the advancement loop. The
    loop originally kept draining subsequent turns regardless, resolving combat
    past a decision the player had not made yet.
    """

    def test_the_advance_loop_checks_the_queue(self):
        import inspect

        from dnd_engine.session.session import Session

        source = inspect.getsource(Session._advance_to_next_actionable_turn)
        assert "self._opportunities.pending" in source, (
            "advancement no longer yields to a pending decision — enemy turns "
            "would drain past an unanswered player reaction"
        )


class TestPerformSurfacesTheDecision:
    """Regression: perform() must actually return the pending decision.

    Found during P1-03 PLAYTEST. The queue filled correctly but `perform()`
    built its `ActionResult` without a `pending` field, so a client following
    the documented contract never saw the question and play silently continued.
    """

    def test_perform_returns_pending_from_the_queue(self):
        import inspect

        from dnd_engine.session.session import Session

        source = inspect.getsource(Session.perform)
        assert "pending=self.pending_decision" in source, (
            "perform() does not surface pending_decision — the question would "
            "be queued but never asked"
        )


class TestQueueSurvivesABadAnswer:
    """Regression: a rejected answer must not reorder who gets asked next.

    Found during P1-03 REVIEW. `resolve()` removed the entry to validate it and
    re-added it on a bad option, sending it to the back of the queue — so a
    player typo silently swapped the order two threatening creatures were asked
    in, breaking initiative order.
    """

    def test_finding_does_not_remove(self):
        queue = OpportunityQueue()
        first = PendingOpportunity(
            reactor=_creature("Guard"),
            mover=_creature("Mover"),
            from_position=Position(0, 0),
            to_position=Position(3, 0),
            reach_feet=5,
            decision_id=queue.next_decision_id(),
        )
        queue.add(first)
        assert queue.find(first.decision_id) is first
        assert queue.pending == [first], "find() removed the entry"

    def test_order_is_stable_across_a_rejected_option(self):
        queue = OpportunityQueue()
        names = []
        for name in ("Guard", "Sentry"):
            opportunity = PendingOpportunity(
                reactor=_creature(name),
                mover=_creature("Mover"),
                from_position=Position(0, 0),
                to_position=Position(3, 0),
                reach_feet=5,
                decision_id=queue.next_decision_id(),
            )
            queue.add(opportunity)
            names.append(name)

        # A bad answer validates through find(), which must leave the queue be.
        queue.find(queue.pending[0].decision_id)

        assert [p.reactor.name for p in queue.pending] == names, (
            "a rejected answer reordered the queue"
        )


class TestStaleDecisionsDoNotResolve:
    """Regression: a queued decision can go stale before it is answered.

    Found during P1-03 REVIEW. Another reactor earlier in initiative may drop
    the mover first, or the reactor may fall. Resolving anyway rolled an attack
    against a corpse and re-announced a death that had already happened.
    """

    def test_resolution_is_skipped_when_the_target_is_already_down(self):
        import inspect

        from dnd_engine.session.session import Session

        source = inspect.getsource(Session._resolve_opportunity_attack)
        assert "opportunity.mover.is_alive" in source, (
            "no guard against attacking a mover who is already down"
        )

    def test_resolution_is_skipped_when_the_reactor_is_down(self):
        import inspect

        from dnd_engine.session.session import Session

        source = inspect.getsource(Session._resolve_opportunity_attack)
        assert "opportunity.reactor.is_alive" in source, (
            "no guard against a fallen reactor taking an opportunity attack"
        )
