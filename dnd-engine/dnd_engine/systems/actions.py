# ABOUTME: Core action handlers for the SRD's missing combat-turn actions
# ABOUTME: Dash, Disengage, Drop Prone, Stand Up, Dodge, Help — plan-01 slices 5a/5b

from __future__ import annotations

from typing import TYPE_CHECKING

from dnd_engine.systems.action_economy import ActionType, TurnState

if TYPE_CHECKING:
    from dnd_engine.core.creature import Creature


ActionResult = tuple[bool, str | None]


def dash(turn_state: TurnState) -> ActionResult:
    """Take the Dash action.

    SRD § Actions › Dash: "For the rest of the turn, give yourself
    extra movement equal to your Speed." Additive on top of any
    remaining movement (the actor may have already moved before
    Dashing).

    Args:
        turn_state: The acting creature's TurnState. Must have its
            ``speed`` set (typically via ``reset(speed)`` at the start
            of the turn).

    Returns:
        ``(True, None)`` on success. ``(False, reason)`` when the
        actor's Action slot is already consumed.
    """
    if not turn_state.consume_action(ActionType.ACTION):
        return False, "no action available"
    turn_state.movement_remaining += turn_state.speed
    return True, None


def disengage(turn_state: TurnState) -> ActionResult:
    """Take the Disengage action.

    SRD § Actions › Disengage: "Your movement doesn't provoke
    Opportunity Attacks for the rest of the turn." Sets a flag the
    Opportunity Attack handler in ``opportunity_attacks.py`` consults
    before reacting. The flag is cleared by ``TurnState.reset`` at the
    actor's next turn — naturally ending the "rest of the turn" window.

    Args:
        turn_state: The acting creature's TurnState.

    Returns:
        ``(True, None)`` on success. ``(False, reason)`` when the
        actor's Action slot is already consumed.
    """
    if not turn_state.consume_action(ActionType.ACTION):
        return False, "no action available"
    turn_state.disengaged_this_turn = True
    return True, None


def drop_prone(creature: Creature, turn_state: TurnState) -> ActionResult:
    """Voluntarily drop prone on the actor's own turn.

    SRD § Movement › Dropping Prone: "On your turn, you can give
    yourself the Prone condition without using an action or any of
    your Speed, but you can't do so if your Speed is 0."

    Args:
        creature: The actor dropping prone.
        turn_state: The actor's TurnState. ``speed`` is consulted for
            the Speed-zero carve-out.

    Returns:
        ``(True, None)`` on success. ``(False, "speed is 0")`` when
        the actor's effective Speed is 0.
    """
    if turn_state.speed == 0:
        return False, "speed is 0"
    creature.add_condition("prone")
    return True, None


def dodge(creature: Creature, turn_state: TurnState) -> ActionResult:
    """Take the Dodge action.

    SRD § Actions › Dodge: "Until the start of your next turn, attack
    rolls against you have Disadvantage, and you make Dexterity saving
    throws with Advantage. You lose this benefit if you have the
    Incapacitated condition or if your Speed is 0."

    The benefit is exposed via ``Creature.is_dodging`` and consulted at
    the consumption sites (``CombatEngine.resolve_attack`` for incoming
    attacks; ``make_saving_throw`` for DEX saves). Those sites re-check
    the Incapacitated / Speed-0 revocation triple each time, so the
    flag itself stays True for the duration; revocation is computed
    live. The flag is cleared by ``InitiativeTracker.next_turn`` at
    the start of the dodger's own next turn.

    Args:
        creature: The actor taking Dodge.
        turn_state: The actor's TurnState. ``speed`` is consulted for
            the Speed-0 carve-out.

    Returns:
        ``(True, None)`` on success. ``(False, "speed is 0")`` when
        the actor's effective Speed is 0. ``(False, "incapacitated")``
        when the actor is Incapacitated at decision time.
        ``(False, "no action available")`` when the Action slot is
        already consumed.
    """
    if turn_state.speed == 0:
        return False, "speed is 0"
    if creature.is_incapacitated():
        return False, "incapacitated"
    if not turn_state.consume_action(ActionType.ACTION):
        return False, "no action available"
    creature.is_dodging = True
    return True, None


def stand_up(creature: Creature, turn_state: TurnState) -> ActionResult:
    """Stand up from prone, consuming half the actor's Speed.

    Rules Glossary › Prone: "Standing up from prone costs half the
    creature's Speed." Implemented as a ``consume_movement`` deduction
    of ``speed // 2``. Refuses to clear Prone if the actor isn't
    currently prone, or if the actor lacks the movement budget.

    Args:
        creature: The actor standing up.
        turn_state: The actor's TurnState. ``speed`` determines the
            cost; ``movement_remaining`` is the budget consulted.

    Returns:
        ``(True, None)`` on success. ``(False, "not prone")`` when the
        actor isn't prone. ``(False, "insufficient movement")`` when
        the actor cannot afford the half-Speed cost. On failure neither
        the condition nor the movement pool is modified.
    """
    if not creature.has_condition("prone"):
        return False, "not prone"
    cost = turn_state.speed // 2
    if not turn_state.consume_movement(cost):
        return False, "insufficient movement"
    creature.remove_condition("prone")
    return True, None
