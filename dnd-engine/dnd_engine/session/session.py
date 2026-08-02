# ABOUTME: Session facade that owns D&D's turn loop and returns one result per intent.
# ABOUTME: Composes GameState without modifying it, so existing callers are unaffected.

"""The session facade.

A client submits an :class:`~dnd_engine.session.protocol.Intent` and receives an
:class:`~dnd_engine.session.protocol.ActionResult` describing everything that
happened. The session — not the caller — advances initiative, drains enemy
turns, runs death saves, and decides when combat is over.

That division is the point. Today `client-terminal`'s run loop calls
``initiative_tracker.next_turn()`` from five separate branches and reaches into
the private ``GameState._check_combat_end()``, while `client-2d` carries its own
independent combat state machine. Both are re-implementations of one rulebook.
Everything either of them knows about turn structure belongs here instead.

`GameState` is composed, never modified: this module is purely additive and no
existing caller changes behaviour.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dnd_engine.core.entity_ids import pc_entity_id
from dnd_engine.session.protocol import (
    ActionResult,
    AttackIntent,
    DecisionKind,
    DecisionOption,
    ErrorKind,
    FreeformIntent,
    GameEvent,
    Intent,
    MoveIntent,
    PendingDecision,
    WaitIntent,
    to_jsonable,
)
from dnd_engine.session.reactions import (
    ATTACK_OPTION_ID,
    DECLINE_OPTION_ID,
    OpportunityQueue,
    describe,
    register_deferred_opportunity_attack,
)
from dnd_engine.utils.events import Event, EventType

if TYPE_CHECKING:  # pragma: no cover - typing only
    from dnd_engine.core.character import Character
    from dnd_engine.core.creature import Creature
    from dnd_engine.core.game_state import GameState

# A malformed initiative order must not hang a client. Generous enough that no
# legitimate round of turn-skipping reaches it.
MAX_TURN_ADVANCE_STEPS = 200


class _EventRecorder:
    """Collects events from both sources in true chronological order.

    Two things produce events during one action, and a client needs them
    interleaved correctly:

    - the engine's :class:`~dnd_engine.utils.events.EventBus`, for everything
      that genuinely publishes
    - synthesis from returned result objects, for everything that does not

    The second exists because weapon attacks emit nothing to the bus.
    ``CombatEngine`` is constructed without a bus at all, and ``ATTACK_ROLL`` is
    published only from the spell path, so a bus subscriber cannot observe a
    sword swing. Appending both sources to one recorder as they occur is what
    keeps ``sequence`` faithful to what actually happened.
    """

    def __init__(self) -> None:
        """Start an empty recording."""
        self._events: list[GameEvent] = []

    def record(
        self, event_type: EventType, data: dict[str, Any], message: str | None = None
    ) -> None:
        """Append one event, numbering it by arrival."""
        self._events.append(
            GameEvent(
                type=event_type,
                data=data,
                sequence=len(self._events),
                message=message,
            )
        )

    def record_bus_event(self, event: Event) -> None:
        """Append an event published on the engine's bus."""
        self.record(event.type, event.data)

    def drain(self) -> tuple[GameEvent, ...]:
        """Return everything recorded, in order, and reset."""
        recorded = tuple(self._events)
        self._events = []
        return recorded


class Session:
    """Plays the game through one intent-in, result-out call.

    Usage::

        session = Session(game_state)
        result = session.perform(AttackIntent(actor_id="pc_thorin", target_ref="Skeleton"))
        for event in result.events:
            render(event)
        while session.awaiting_actor_id is None and not session.is_over:
            ...

    After every :meth:`perform`, either :attr:`awaiting_actor_id` names a
    conscious player character whose input is needed, or the session is out of
    combat or over. A caller never has to ask whose turn it is or advance it.

    The one exception is entering combat: an enemy may hold the first initiative
    slot, so a freshly-started fight can begin with nobody to act as. Call
    :meth:`advance` whenever :attr:`awaiting_actor_id` is ``None`` while
    :attr:`in_combat` is ``True``.
    """

    def __init__(self, game_state: GameState) -> None:
        """Wrap an already-started :class:`GameState`.

        Args:
            game_state: The engine state to drive. Not modified by this class;
                the session only calls its public surface.
        """
        self._game = game_state
        self._recorder = _EventRecorder()
        self._subscribed = False
        self._numbered_combat = False
        self._opportunities = OpportunityQueue()
        self._deferred_reactions = False

    # ------------------------------------------------------------------
    # Read-only state a client needs to render, in JSON-native form
    # ------------------------------------------------------------------

    @property
    def in_combat(self) -> bool:
        """Whether combat is currently running."""
        return bool(self._game.in_combat)

    @property
    def is_over(self) -> bool:
        """Whether the game has ended (party wiped)."""
        return bool(self._game.is_game_over())

    @property
    def awaiting_actor_id(self) -> str | None:
        """Entity id of the player character whose input is needed.

        ``None`` when nobody's input is pending — out of combat, game over, or
        an enemy is up (which :meth:`perform` drains before returning, so a
        caller should not normally observe that case).
        """
        if self.is_over or not self.in_combat:
            return None
        character = self._current_player_character()
        return pc_entity_id(character.name) if character is not None else None

    def _ensure_combat_numbers(self) -> None:
        """Give same-named enemies distinct display names ("Skeleton 1", "2").

        `InitiativeTracker.assign_combat_numbers` exists for exactly this, but
        nothing in the engine calls it — only `client-terminal` does
        (`cli.py:6243`). The consequence is that terminal players can tell two
        skeletons apart and every other client cannot, which makes precise
        targeting impossible: a caller asking for one of them silently gets
        whichever the engine lists first.

        Doing it here means every client inherits the disambiguation, which is
        the whole point of the facade.
        """
        if self._numbered_combat or not self.in_combat:
            return
        tracker = getattr(self._game, "initiative_tracker", None)
        assign = getattr(tracker, "assign_combat_numbers", None)
        if assign is None:
            return
        assign(list(self._game.party.characters))
        self._numbered_combat = True

    def _ensure_deferred_reactions(self) -> None:
        """Take over opportunity-attack decisions from the engine's auto-handler.

        Registered once per fight and only while a session is driving. A
        ``GameState`` used without a ``Session`` keeps the engine's automatic
        behaviour untouched, which is what makes this additive.
        """
        if self._deferred_reactions or not self.in_combat:
            return
        dispatcher = getattr(self._game, "reaction_dispatcher", None)
        spatial = getattr(self._game, "spatial", None)
        if dispatcher is None or spatial is None:
            return

        for entity_id in list(spatial.occupants().keys()):
            creature = self._game._find_creature_by_id(entity_id)
            if creature is None:
                continue

            # Only a party member's reaction is the player's to spend. A
            # monster keeps the engine's default auto-attack handler — asking
            # "should the skeleton strike you?" is not a decision anyone wants,
            # and it also keeps NPC behaviour identical to today.
            if self._as_party_character(creature) is None:
                continue

            def _position_lookup(eid: str = entity_id) -> Any:
                return spatial.position_of(eid)

            def _can_see(target: Any, eid: str = entity_id) -> bool:
                origin = spatial.position_of(eid)
                if origin is None:
                    return False
                return bool(spatial.has_line_of_sight(origin, target))

            register_deferred_opportunity_attack(
                dispatcher,
                self._opportunities,
                creature,
                get_position=_position_lookup,
                can_see=_can_see,
            )
        self._deferred_reactions = True

    def _enemy_display_name(self, enemy: Creature) -> str:
        """The enemy's combat-numbered display name, falling back to its name."""
        tracker = getattr(self._game, "initiative_tracker", None)
        if tracker is not None:
            for entry in tracker.get_all_combatants():
                if entry.creature is enemy:
                    return entry.display_name or enemy.name
        return enemy.name

    def snapshot(self) -> dict[str, Any]:
        """Renderable state as JSON-native data.

        Deliberately not a `GameState` handle: a client that renders from this
        plus :class:`ActionResult` never needs engine objects.
        """
        snapshot: dict[str, Any] = to_jsonable(
            {
                "in_combat": self.in_combat,
                "is_over": self.is_over,
                "awaiting_actor_id": self.awaiting_actor_id,
                "party": [
                    {
                        "entity_id": pc_entity_id(c.name),
                        "name": c.name,
                        "hp": c.current_hp,
                        "max_hp": c.max_hp,
                        "is_alive": c.is_alive,
                        "is_unconscious": c.is_unconscious,
                    }
                    for c in self._game.party.characters
                ],
                "enemies": [
                    {
                        "name": e.name,
                        "display_name": self._enemy_display_name(e),
                        "hp": e.current_hp,
                        "is_alive": e.is_alive,
                    }
                    for e in (self._game.active_enemies or [])
                ],
            }
        )
        return snapshot

    # ------------------------------------------------------------------
    # The one entry point
    # ------------------------------------------------------------------

    def perform(self, intent: Intent) -> ActionResult:
        """Carry out an intent and advance the game to the next decision point.

        Args:
            intent: What the actor wants to do.

        Returns:
            An :class:`ActionResult` carrying every event produced — by the
            acting creature and by everyone who acted afterwards, up to the next
            point a player must choose. Rejections carry
            :attr:`ErrorKind.RULE`; unexpected engine failures carry
            :attr:`ErrorKind.INTERNAL` and leave the session usable.
        """
        self._recorder.drain()

        if self.is_over:
            return self._reject("the game is over")

        outstanding = self.pending_decision
        if outstanding is not None:
            return self._reject(
                f"a decision is outstanding ({outstanding.decision_id}: "
                f"{outstanding.prompt}) — call Session.resolve() first"
            )

        self._ensure_combat_numbers()
        self._ensure_deferred_reactions()
        actor_error = self._validate_actor(intent)
        if actor_error is not None:
            return self._reject(actor_error)

        try:
            with self._recording():
                rejection = self._dispatch(intent)
                if rejection is not None:
                    self._recorder.drain()
                    return self._reject(rejection)
                # A step may have provoked. Hold the turn open until every
                # reaction has been answered — advancing now would resolve
                # turns out of order.
                if not self._opportunities.pending:
                    self._advance_to_next_actionable_turn()
        except Exception as exc:  # noqa: BLE001 - boundary: never leak engine faults
            self._recorder.drain()
            return ActionResult(
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
                error_kind=ErrorKind.INTERNAL,
            )

        self._reset_numbering_if_combat_ended()
        return ActionResult(
            ok=True,
            events=self._recorder.drain(),
            pending=self.pending_decision,
        )

    @property
    def pending_decision(self) -> PendingDecision | None:
        """The question the engine is waiting on, or ``None``.

        While this is set, :meth:`perform` refuses new intents — the engine is
        mid-interrupt and letting an action through would resolve turns out of
        order.
        """
        opportunity = self._opportunities.peek()
        if opportunity is None:
            return None

        wording = describe(opportunity, self._enemy_display_name(opportunity.mover))
        return PendingDecision(
            decision_id=opportunity.decision_id,
            kind=DecisionKind.REACTION,
            actor_id=pc_entity_id(opportunity.reactor.name),
            prompt=wording["prompt"],
            options=(
                DecisionOption(
                    ATTACK_OPTION_ID,
                    "Take the opportunity attack",
                    "Spend your reaction to strike as they withdraw",
                ),
                DecisionOption(
                    DECLINE_OPTION_ID,
                    "Decline",
                    "Keep your reaction for something else this round",
                ),
            ),
            # Attacking is the default because it is what the engine has always
            # done. A caller that cannot ask a human must keep getting today's
            # behaviour, not a quietly different game.
            default_option_id=ATTACK_OPTION_ID,
            context=wording["context"],
        )

    def resolve(self, decision_id: str, option_id: str) -> ActionResult:
        """Answer an outstanding decision and continue play.

        Args:
            decision_id: The id from the :class:`PendingDecision`.
            option_id: Which option the player chose.

        Returns:
            The events produced by the answer, plus the next decision if more
            creatures are waiting to be asked.
        """
        self._recorder.drain()

        # Validate before removing. Taking the entry out and putting it back on
        # a bad answer appended it to the end of the queue, silently reordering
        # who gets asked next — which broke initiative order for a typo.
        opportunity = self._opportunities.find(decision_id)
        if opportunity is None:
            return self._reject(f"no pending decision with id {decision_id!r}")

        if option_id not in (ATTACK_OPTION_ID, DECLINE_OPTION_ID):
            return self._reject(
                f"unknown option {option_id!r}; expected "
                f"{ATTACK_OPTION_ID!r} or {DECLINE_OPTION_ID!r}"
            )

        self._opportunities.take(decision_id)

        try:
            with self._recording():
                if option_id == ATTACK_OPTION_ID:
                    self._resolve_opportunity_attack(opportunity)
                else:
                    self._recorder.record(
                        EventType.REACTION_DECLINED,
                        {
                            "reactor": opportunity.reactor.name,
                            "mover": opportunity.mover.name,
                        },
                        message=(
                            f"{opportunity.reactor.name} lets "
                            f"{opportunity.mover.name} go."
                        ),
                    )
                if not self._opportunities.pending:
                    self._advance_to_next_actionable_turn()
        except Exception as exc:  # noqa: BLE001 - boundary: never leak engine faults
            self._recorder.drain()
            return ActionResult(
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
                error_kind=ErrorKind.INTERNAL,
            )

        self._reset_numbering_if_combat_ended()
        return ActionResult(
            ok=True,
            events=self._recorder.drain(),
            pending=self.pending_decision,
        )

    def _resolve_opportunity_attack(self, opportunity: Any) -> None:
        """Spend the reaction and resolve the attack the player chose to take.

        A queued decision can go stale: another reactor earlier in initiative may
        have dropped the mover, or the reactor themselves may have fallen before
        answering. Resolving anyway would roll an attack against a corpse and
        re-announce a death that already happened.
        """
        if not opportunity.reactor.is_alive:
            self._recorder.record(
                EventType.REACTION_DECLINED,
                {
                    "reactor": opportunity.reactor.name,
                    "mover": opportunity.mover.name,
                    "reason": "reactor_down",
                },
                message=(
                    f"{opportunity.reactor.name} is in no state to take the "
                    f"opportunity attack."
                ),
            )
            return

        if not opportunity.mover.is_alive:
            self._recorder.record(
                EventType.REACTION_DECLINED,
                {
                    "reactor": opportunity.reactor.name,
                    "mover": opportunity.mover.name,
                    "reason": "target_already_down",
                },
                message=(
                    f"{opportunity.mover.name} is already down — "
                    f"{opportunity.reactor.name} holds the blow."
                ),
            )
            return

        tracker = self._require_tracker()
        turn_state = tracker.turn_states.get(opportunity.reactor)
        if turn_state is not None:
            from dnd_engine.systems.action_economy import ActionType

            turn_state.consume_action(ActionType.REACTION)

        result = self._game.combat_engine.resolve_attack(
            attacker=opportunity.reactor,
            defender=opportunity.mover,
            attack_bonus=getattr(opportunity.reactor, "attack_bonus", 0),
            damage_dice=getattr(opportunity.reactor, "damage_dice", "1d4"),
            apply_damage=True,
        )

        self._recorder.record(
            EventType.OPPORTUNITY_ATTACK,
            to_jsonable(
                {
                    "attacker": opportunity.reactor.name,
                    "target": opportunity.mover.name,
                    "hit": getattr(result, "hit", False),
                    "attack_roll": getattr(result, "attack_roll", None),
                    "target_ac": getattr(result, "target_ac", None),
                }
            ),
            message=(
                f"{opportunity.reactor.name} takes an opportunity attack on "
                f"{opportunity.mover.name} — "
                f"{'hit' if getattr(result, 'hit', False) else 'miss'}."
            ),
        )
        self._record_attack(
            attacker_name=opportunity.reactor.name,
            target_name=opportunity.mover.name,
            weapon="opportunity attack",
            attack_result=result,
            target_killed=not opportunity.mover.is_alive,
        )

    def advance(self) -> ActionResult:
        """Run the game forward while nobody's input is needed.

        Call this when :attr:`awaiting_actor_id` is ``None`` but
        :attr:`in_combat` is ``True`` — most importantly **right after combat
        starts**, because an enemy may hold the first initiative slot. Enemy
        turns are drained only inside a session call, so without this a client
        that waits for an actor it can act as would wait forever.

        Safe to call at any time; a no-op when a player is already up.

        Returns:
            An :class:`ActionResult` carrying everything that happened while
            control was not with a player.
        """
        self._recorder.drain()

        if self.is_over or not self.in_combat:
            return ActionResult(ok=True)

        self._ensure_combat_numbers()

        try:
            with self._recording():
                self._advance_to_next_actionable_turn(skip_current=False)
        except Exception as exc:  # noqa: BLE001 - boundary: never leak engine faults
            self._recorder.drain()
            return ActionResult(
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
                error_kind=ErrorKind.INTERNAL,
            )

        self._reset_numbering_if_combat_ended()
        return ActionResult(
            ok=True, events=self._recorder.drain(), pending=self.pending_decision
        )

    # ------------------------------------------------------------------
    # Intent dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, intent: Intent) -> str | None:
        """Execute one intent. Returns a rejection reason, or ``None`` if done."""
        if isinstance(intent, AttackIntent):
            return self._do_attack(intent)
        if isinstance(intent, MoveIntent):
            return self._do_move(intent)
        if isinstance(intent, WaitIntent):
            return None
        if isinstance(intent, FreeformIntent):
            return "freeform intents are not adjudicated yet"
        return f"unsupported intent kind: {type(intent).__name__}"

    def _do_attack(self, intent: AttackIntent) -> str | None:
        """Resolve a weapon attack and synthesize its events."""
        attacker = self._character_for(intent.actor_id)
        if attacker is None:
            return f"no such actor: {intent.actor_id}"

        target = self._resolve_target(intent.target_ref)
        if target is None:
            return f"no living target matching {intent.target_ref!r}"

        target_display = self._enemy_display_name(target)
        result = self._game.execute_player_attack(attacker, target)
        if result.error:
            return result.error

        self._record_attack(
            attacker_name=result.attacker_name,
            # Display name, not `result.target_name`: the raw name is ambiguous
            # when two creatures share it, and a combat log that reads
            # "Skeleton takes 9 damage" cannot tell the player which one.
            target_name=target_display,
            weapon=result.weapon_name,
            attack_result=result.attack_result,
            target_killed=result.target_killed,
        )
        return None

    def _do_move(self, intent: MoveIntent) -> str | None:
        """Move the actor, using the combat-legal path when in combat."""
        if self.in_combat:
            delta = _DIRECTION_DELTAS.get(intent.direction.lower())
            if delta is None:
                return f"unknown direction: {intent.direction}"
            move = self._game.attempt_combat_step(intent.actor_id, delta[0], delta[1])
            if not move.ok:
                return move.reason or "move rejected"
            self._recorder.record(
                EventType.CREATURE_MOVED,
                {
                    "entity_id": intent.actor_id,
                    "to": move.position,
                    "movement_remaining": move.movement_remaining,
                },
                message=f"{intent.actor_id} moves {intent.direction}.",
            )
            return None

        if not self._game.move(intent.direction):
            return f"cannot move {intent.direction} from here"
        return None

    # ------------------------------------------------------------------
    # Turn advancement — the rules the clients currently carry
    # ------------------------------------------------------------------

    def _advance_to_next_actionable_turn(self, *, skip_current: bool = True) -> None:
        """Advance until a conscious player character is up, or combat ends.

        Args:
            skip_current: Whether the combatant currently up has already acted
                and should be passed over. True after an intent resolves; False
                when entering the loop cold, as :meth:`advance` does at combat
                start where nobody has acted yet.

        Mirrors the branch structure of `client-terminal`'s run loop so the
        facade is behaviourally faithful to what players experience today:
        dead combatants are skipped, unconscious characters roll death saves
        (stabilized ones simply skip), incapacitated characters process
        end-of-turn conditions, and enemy turns are drained.
        """
        if not self.in_combat:
            return

        tracker = self._require_tracker()
        if skip_current:
            tracker.next_turn()
            self._game._check_combat_end()

        for _ in range(MAX_TURN_ADVANCE_STEPS):
            if not self.in_combat or self.is_over:
                return

            # A reaction was provoked mid-advancement — most often by an enemy
            # withdrawing on its own turn. Stop here: draining further turns
            # while a player's reaction is unanswered resolves combat out of
            # order. `resolve()` re-enters this loop once the queue is empty.
            if self._opportunities.pending:
                return

            current = tracker.get_current_combatant()
            if current is None:
                return

            creature = current.creature

            if self._should_skip(creature):
                tracker.next_turn()
                continue

            character = self._as_party_character(creature)
            if character is None:
                if self._drain_one_enemy_turn():
                    continue
                return

            if character.is_unconscious:
                self._handle_unconscious_turn(character)
                continue

            if not character.can_take_actions():
                self._handle_incapacitated_turn(character)
                continue

            self._run_turn_start_effects(character)
            if not character.is_alive:
                tracker.next_turn()
                continue

            return  # A conscious player character is up: hand control back.

    def _reset_numbering_if_combat_ended(self) -> None:
        """Let the next fight assign its own combat numbers."""
        if not self.in_combat:
            self._numbered_combat = False
            self._deferred_reactions = False
            self._opportunities.clear()

    def _should_skip(self, creature: Creature) -> bool:
        """Whether this combatant is skipped outright.

        Characters use ``is_dead`` (three failed death saves) rather than
        ``is_alive``, because an unconscious character is not alive but still
        takes a turn to roll death saves.
        """
        if hasattr(creature, "is_dead"):
            return bool(creature.is_dead)
        return not creature.is_alive

    def _handle_unconscious_turn(self, character: Character) -> None:
        """Roll a death save, or skip a stabilized character."""
        if character.stabilized:
            self._recorder.record(
                EventType.TURN_END,
                {"actor": character.name, "reason": "stabilized"},
                message=f"{character.name} is unconscious but stable.",
            )
            self._require_tracker().next_turn()
            self._game._check_combat_end()
            return

        result = self._game.process_unconscious_turn()
        if result is not None:
            # Deliberately not synthesized: the engine publishes DEATH_SAVE to the
            # bus already, with a richer payload (roll, success, natural_20,
            # stabilized, dead, conscious). Synthesizing here too made every death
            # save appear twice in the stream. Synthesis exists only to cover what
            # the bus does not emit — see `_record_attack`.
            # process_unconscious_turn advances initiative itself.
            self._game._check_combat_end()
            return

        self._require_tracker().next_turn()
        self._game._check_combat_end()

    def _handle_incapacitated_turn(self, character: Character) -> None:
        """Process end-of-turn conditions for a character who cannot act."""
        for outcome in character.process_end_of_turn_conditions(self._game.event_bus):
            self._recorder.record(
                EventType.CONDITION_REMOVED
                if outcome.get("type") in {"repeat_save_success", "condition_expired"}
                else EventType.CONDITION_APPLIED,
                to_jsonable({"actor": character.name, **outcome}),
            )
        self._recorder.record(
            EventType.TURN_END,
            {"actor": character.name, "reason": "incapacitated"},
            message=f"{character.name} cannot act this turn.",
        )
        self._require_tracker().next_turn()

    def _run_turn_start_effects(self, character: Character) -> None:
        """Apply start-of-turn condition effects (ongoing damage and the like).

        Uses the engine's own `ConditionManager` rather than constructing one —
        `GameState` already owns it.
        """
        manager = getattr(self._game, "condition_manager", None)
        if manager is None:
            return
        for effect in manager.process_turn_start_effects(character):
            self._recorder.record(
                EventType.DAMAGE_TAKEN,
                to_jsonable({"actor": character.name, "condition": effect.condition_id}),
                message=getattr(effect, "message", None),
            )

    def _drain_one_enemy_turn(self) -> bool:
        """Process one enemy turn. Returns False when it is not an enemy's turn."""
        result = self._game.process_enemy_turn()
        if result is None:
            return False

        if result.error:
            self._recorder.record(
                EventType.TURN_END,
                {"actor": result.enemy_display_name, "error": result.error},
            )
        elif result.attack_result is not None:
            self._record_attack(
                attacker_name=result.enemy_display_name,
                target_name=result.target_name or "",
                weapon=(result.action_data or {}).get("name", "attack"),
                attack_result=result.attack_result,
                target_killed=result.target_killed,
            )
        else:
            self._recorder.record(
                EventType.TURN_END,
                to_jsonable(
                    {
                        "actor": result.enemy_display_name,
                        "action": result.action_taken,
                        "moved_squares": result.moved_squares,
                    }
                ),
            )
        return not result.combat_ended

    # ------------------------------------------------------------------
    # Event synthesis
    # ------------------------------------------------------------------

    def _record_attack(
        self,
        *,
        attacker_name: str,
        target_name: str,
        weapon: str,
        attack_result: Any,
        target_killed: bool,
    ) -> None:
        """Turn an attack result into the events the bus never publishes."""
        hit = bool(getattr(attack_result, "hit", False))
        self._recorder.record(
            EventType.ATTACK_ROLL,
            to_jsonable(
                {
                    "attacker": attacker_name,
                    "target": target_name,
                    "weapon": weapon,
                    "attack_roll": getattr(attack_result, "attack_roll", None),
                    "total": getattr(attack_result, "total_attack", None),
                    "target_ac": getattr(attack_result, "target_ac", None),
                    "hit": hit,
                    "critical_hit": getattr(attack_result, "critical_hit", False),
                }
            ),
            message=(
                f"{attacker_name} {'hits' if hit else 'misses'} {target_name} with {weapon}."
            ),
        )

        damage = getattr(attack_result, "damage", 0) or 0
        if hit and damage:
            self._recorder.record(
                EventType.DAMAGE_DEALT,
                to_jsonable(
                    {"attacker": attacker_name, "target": target_name, "amount": damage}
                ),
                message=f"{target_name} takes {damage} damage.",
            )

        if target_killed:
            self._recorder.record(
                EventType.CHARACTER_DEATH,
                {"name": target_name},
                message=f"{target_name} falls.",
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate_actor(self, intent: Intent) -> str | None:
        """Reject an intent from someone who cannot act right now."""
        if not self.in_combat:
            return None  # Exploration: no initiative to respect.
        awaiting = self.awaiting_actor_id
        if awaiting is None:
            return (
                "no player character is currently able to act — an enemy holds "
                "initiative; call Session.advance() to run the game forward"
            )
        if intent.actor_id != awaiting:
            return f"it is not {intent.actor_id}'s turn (waiting on {awaiting})"
        return None

    def _require_tracker(self) -> Any:
        """The initiative tracker, or a clear failure.

        `GameState.initiative_tracker` is optional, so every advancement call
        site would otherwise be an unguarded `NoneType` access. Being in combat
        without a tracker is an engine fault, not a rules outcome — raising here
        routes it through `perform()`'s boundary and surfaces as
        `ErrorKind.INTERNAL` rather than crashing inside the client.
        """
        tracker = getattr(self._game, "initiative_tracker", None)
        if tracker is None:
            raise RuntimeError("in combat but GameState has no initiative_tracker")
        return tracker

    def _current_player_character(self) -> Character | None:
        """The party member whose turn it is, if any."""
        tracker = getattr(self._game, "initiative_tracker", None)
        if tracker is None:
            return None
        current = tracker.get_current_combatant()
        if current is None:
            return None
        return self._as_party_character(current.creature)

    def _as_party_character(self, creature: Creature) -> Character | None:
        """Return the creature as a party member, or ``None`` if it is not one."""
        for character in self._game.party.characters:
            if creature is character:
                return character
        return None

    def _character_for(self, actor_id: str) -> Character | None:
        """Find a party member by entity id."""
        for character in self._game.party.characters:
            if pc_entity_id(character.name) == actor_id:
                return character
        return None

    def _resolve_target(self, target_ref: str) -> Creature | None:
        """Resolve a target by entity id or display name, living enemies only."""
        wanted = target_ref.strip().lower()
        living = [e for e in (self._game.active_enemies or []) if e.is_alive]

        # Display name first: it is the only handle guaranteed unique within a
        # fight, so "Skeleton 2" resolves to the intended creature rather than
        # to whichever skeleton the engine happens to list first.
        for enemy in living:
            if self._enemy_display_name(enemy).lower() == wanted:
                return enemy
        for enemy in living:
            if enemy.name.lower() == wanted:
                return enemy
        for enemy in living:
            if wanted in self._enemy_display_name(enemy).lower():
                return enemy
        return None

    def _reject(self, reason: str) -> ActionResult:
        """A rules-level refusal: normal play, not a defect."""
        return ActionResult(ok=False, error=reason, error_kind=ErrorKind.RULE)

    def _recording(self) -> _BusRecording:
        """Capture bus events for the duration of a block."""
        return _BusRecording(self._game.event_bus, self._recorder)


class _BusRecording:
    """Subscribes the recorder to every event type for the life of a block."""

    def __init__(self, event_bus: Any, recorder: _EventRecorder) -> None:
        """Hold the bus and recorder to wire together on entry."""
        self._bus = event_bus
        self._recorder = recorder

    def __enter__(self) -> _BusRecording:
        """Subscribe to every event type."""
        for event_type in EventType:
            self._bus.subscribe(event_type, self._recorder.record_bus_event)
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Unsubscribe, even when the block raised."""
        for event_type in EventType:
            self._bus.unsubscribe(event_type, self._recorder.record_bus_event)


_DIRECTION_DELTAS: dict[str, tuple[int, int]] = {
    "north": (0, -1),
    "south": (0, 1),
    "east": (1, 0),
    "west": (-1, 0),
}
