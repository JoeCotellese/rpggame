# ABOUTME: SRD conformance audit for "Playing the Game > Bonus Actions".
# ABOUTME: Cross-references docs/srd/playing-the-game/bonus-actions.md against engine code.

"""SRD conformance: Bonus Actions.

Maps every rule in `docs/srd/playing-the-game/bonus-actions.md` to a
test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.systems.action_economy import ActionType, TurnState
from dnd_engine.systems.initiative import InitiativeTracker

pytestmark = pytest.mark.srd(
    "playing-the-game/bonus-actions.md",
    lines="1416-1437",
)


SPELLS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "spells.json"
)
ITEMS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "items.json"
)


def _make_turn_state() -> TurnState:
    """Fresh TurnState with every action available."""
    return TurnState()


def _make_creature(name: str = "Hero") -> Creature:
    abilities = Abilities(
        strength=14,
        dexterity=14,
        constitution=14,
        intelligence=10,
        wisdom=10,
        charisma=10,
    )
    return Creature(name=name, max_hp=20, ac=14, abilities=abilities)


class TestBonusAction_Definition:
    """SRD § Playing the Game › Bonus Actions › Definition.

    > Various class features, spells, and other abilities let you take
    > an additional action on your turn called a Bonus Action. The
    > Cunning Action feature, for example, allows a Rogue to take a
    > Bonus Action.
    """

    def test_bonus_action_is_a_first_class_action_type(self):
        """`ActionType.BONUS_ACTION` exists and is distinct from `ACTION`.

        Defines the type-level surface the SRD's "additional action"
        wording demands: a separate slot from the main action, not just
        a flag on the main one. action_economy.py:14-22 enumerates the
        four types; this guards the contract.
        """
        assert ActionType.BONUS_ACTION.value == "bonus_action"
        assert ActionType.BONUS_ACTION is not ActionType.ACTION

    def test_turn_state_tracks_bonus_action_separately_from_action(self):
        """`TurnState.bonus_action_available` is a standalone field.

        Consuming the main action must not consume the bonus action and
        vice versa. action_economy.py:36-39 defines the two flags.
        """
        turn = _make_turn_state()

        assert turn.consume_action(ActionType.ACTION) is True
        assert turn.is_action_available(ActionType.ACTION) is False
        # Bonus action stays open after the main action is spent.
        assert turn.is_action_available(ActionType.BONUS_ACTION) is True
        assert turn.consume_action(ActionType.BONUS_ACTION) is True

    def test_data_layer_carries_bonus_action_casting_time(self):
        """Spells with bonus-action casting time live in the SRD catalog.

        The "spells" half of the SRD's "class features, spells, and
        other abilities" clause is reflected in `spells.json` via
        `casting_time: "1 bonus action"`. This is a data-parity check —
        gating the consumption on that field is a separate concern
        (see TestBonusAction_GatedByFeature).
        """
        spells = json.loads(SPELLS_JSON.read_text())
        bonus_action_spells = [
            sid
            for sid, sdata in spells.items()
            if sdata.get("casting_time") == "1 bonus action"
        ]
        assert bonus_action_spells, (
            "Expected at least one spell in spells.json with "
            "casting_time == '1 bonus action' (e.g., misty_step, "
            "spiritual_weapon)."
        )


class TestBonusAction_GatedByFeature:
    """SRD § Playing the Game › Bonus Actions › Gated by features.

    > You can take a Bonus Action only when a special ability, a
    > spell, or another feature of the game states that you can do
    > something as a Bonus Action. You otherwise don't have a Bonus
    > Action to take.
    """

    def test_bonus_action_consumption_is_not_gated_by_feature_ownership(self):
        """GAP — `TurnState.bonus_action_available` defaults to True for everyone.

        The SRD says a Bonus Action only exists when a feature grants
        one; today every combatant starts each turn with
        `bonus_action_available = True` regardless of class/spell list
        (action_economy.py:38). Nothing on the engine checks "does this
        actor have a feature/spell that grants a bonus action?" before
        consuming the slot. A Wizard with no bonus-action options can
        nominally consume one without consequence.
        """
        # The default is "available", with no feature check.
        turn = _make_turn_state()
        assert turn.bonus_action_available is True

        # No feature-ownership check exists on the consumption path.
        src = inspect.getsource(TurnState.consume_action)
        assert "feature" not in src.lower(), (
            "If consume_action grows a feature-ownership check, update "
            "this guard and convert the next test below to a real "
            "assertion."
        )

        pytest.skip(
            "GAP: Bonus Action slot is always granted, not gated by "
            "the actor having a feature/spell that confers one. SRD "
            "requires a per-actor opt-in (e.g., Cunning Action, Two-"
            "Weapon Fighting, a bonus-action spell). Today the slot "
            "is open by default in TurnState "
            "(dnd-engine/dnd_engine/systems/action_economy.py:38). "
            "Tracked by issue #434."
        )

    def test_bonus_action_spell_dispatch_uses_casting_time(self):
        """GAP — CLI hardcodes `ActionType.ACTION` for every spell cast.

        `client-terminal/terminal_client/ui/cli.py:2909` always passes
        `action_type=ActionType.ACTION` to the executor for spell
        casts, regardless of whether the spell's `casting_time` is
        "1 action" or "1 bonus action". `GameState.cast_spell_combat`
        (`dnd-engine/dnd_engine/core/game_state.py:2077`) likewise
        never reads the field. Consequence: casting Misty Step or
        Spiritual Weapon today consumes the main Action and leaves the
        Bonus Action untouched — the inverse of the SRD intent.
        """
        spells = json.loads(SPELLS_JSON.read_text())
        misty_step = spells.get("misty_step")
        assert misty_step is not None, "misty_step expected in SRD catalog"
        assert misty_step.get("casting_time") == "1 bonus action", (
            "misty_step's casting_time should be '1 bonus action' in "
            "the catalog."
        )

        pytest.skip(
            "GAP: spell `casting_time` is never consulted on the "
            "consumption path. CLI hardcodes ActionType.ACTION at "
            "client-terminal/terminal_client/ui/cli.py:2909 and "
            "GameState.cast_spell_combat never reads the field "
            "(dnd-engine/dnd_engine/core/game_state.py:2077). Bonus-"
            "action spells incorrectly consume the main Action. "
            "Tracked by issue #437."
        )

    def test_bonus_action_item_dispatch_path_recognizes_bonus_action(self):
        """`use_item_combat` recognizes "bonus_action" in `action_required`.

        Items declare their cost via `action_required`; the engine
        maps that string to an `ActionType` and consumes the right
        slot (game_state.py:4467-4474, 4618-4626). This is the
        opposite shape of the spell gap above — items DO consume the
        slot their data declares. We don't ship any bonus-action
        consumables today, but the dispatch path recognizes the
        `"bonus_action"` value when it appears in data.
        """
        # Source-level guard: the dispatch maps in game_state.py
        # include the "bonus_action" -> ActionType.BONUS_ACTION entry
        # used by use_combat_attack_item / use_item_combat.
        from dnd_engine.core.game_state import GameState

        attack_src = inspect.getsource(GameState.use_combat_attack_item)
        use_src = inspect.getsource(GameState.use_item_combat)
        for label, src in (
            ("use_combat_attack_item", attack_src),
            ("use_item_combat", use_src),
        ):
            assert '"bonus_action": ActionType.BONUS_ACTION' in src, (
                f"{label} must map 'bonus_action' -> ActionType.BONUS_ACTION "
                f"in its action_required dispatch table."
            )


class TestBonusAction_OnePerTurn:
    """SRD § Playing the Game › Bonus Actions › One per turn.

    > You can take only one Bonus Action on your turn, so you must
    > choose which Bonus Action to use if you have more than one
    > available.
    """

    def test_second_bonus_action_in_same_turn_is_rejected(self):
        """`consume_action(BONUS_ACTION)` returns False on second call.

        action_economy.py:65-69 — the slot flips to unavailable on
        first consumption, so a second attempt within the same turn
        cannot land. This is the engine's primary "one Bonus Action
        per turn" guard.
        """
        turn = _make_turn_state()

        assert turn.consume_action(ActionType.BONUS_ACTION) is True
        assert turn.is_action_available(ActionType.BONUS_ACTION) is False
        # Second attempt within the same turn must be rejected.
        assert turn.consume_action(ActionType.BONUS_ACTION) is False

    def test_bonus_action_slot_resets_each_turn(self):
        """`TurnState.reset()` refreshes the bonus action slot.

        action_economy.py:125-138 — `reset()` is called by
        `InitiativeTracker` between turns. A creature that spent its
        bonus action last turn must regain one this turn. The
        InitiativeTracker integration is covered separately in
        tests/test_action_economy.py.
        """
        tracker = InitiativeTracker()
        first = _make_creature("First")
        second = _make_creature("Second")
        tracker.add_combatant(first)
        tracker.add_combatant(second)

        # First combatant spends bonus action.
        t1 = tracker.get_current_turn_state()
        assert t1.consume_action(ActionType.BONUS_ACTION) is True
        assert t1.bonus_action_available is False

        # Advance to second combatant — their slot is fresh.
        tracker.next_turn()
        t2 = tracker.get_current_turn_state()
        assert t2.bonus_action_available is True

        # Wrap back to first combatant — their slot was reset too.
        tracker.next_turn()
        t1_again = tracker.get_current_turn_state()
        assert t1_again.bonus_action_available is True

    def test_choosing_between_competing_bonus_actions_is_not_modeled(self):
        """GAP — there is no "available bonus actions" menu the player picks from.

        The SRD "must choose which Bonus Action to use if you have
        more than one available" sentence is only load-bearing once
        per-actor bonus-action options exist (Cunning Action, Two-
        Weapon Fighting bonus attack, bonus-action spells, etc.). The
        engine ships none of these as selectable actions today, so the
        "choose one" constraint is vacuously satisfied — but it has
        nothing to guard. Becomes load-bearing the moment two bonus-
        action options coexist for one character.
        """
        pytest.skip(
            "LATENT: no character/class today owns more than one "
            "bonus-action option, so the 'must choose' constraint has "
            "nothing to enforce. Becomes live once Cunning Action, "
            "Two-Weapon Fighting bonus attack, and/or bonus-action "
            "spells become selectable. Depends on issue #434 "
            "(feature-ownership gating)."
        )


class TestBonusAction_Timing:
    """SRD § Playing the Game › Bonus Actions › Timing.

    > You choose when to take a Bonus Action during your turn unless
    > the Bonus Action's timing is specified.
    """

    def test_bonus_action_can_be_taken_before_or_after_main_action(self):
        """Slot order is unconstrained — bonus before action is legal.

        action_economy.py — `bonus_action_available` and
        `action_available` are independent fields with no ordering
        guard. A creature can spend its Bonus Action first, then its
        Action (or vice versa), satisfying the SRD's "you choose when".
        """
        turn = _make_turn_state()

        # Bonus action first, then main action — both must succeed.
        assert turn.consume_action(ActionType.BONUS_ACTION) is True
        assert turn.consume_action(ActionType.ACTION) is True

        # Reversed order on a fresh slot, same outcome.
        turn.reset()
        assert turn.consume_action(ActionType.ACTION) is True
        assert turn.consume_action(ActionType.BONUS_ACTION) is True

    def test_bonus_action_with_specified_timing_is_not_modeled(self):
        """GAP — no feature/spell carries a timing constraint today.

        SRD carves out features whose Bonus Action timing IS specified
        (e.g., a feature that says "when you take the Attack action,
        you can ... as a Bonus Action"). The engine has no
        timing-constraint field on bonus actions and no enforcement
        path. Becomes load-bearing once such a feature lands (e.g.,
        the Rogue's Steady Aim, Two-Weapon Fighting's bonus attack
        after the Attack action).
        """
        pytest.skip(
            "LATENT: no engine surface today encodes a Bonus Action's "
            "required timing (e.g., 'only after taking the Attack "
            "action'). Becomes live with Two-Weapon Fighting's bonus "
            "attack or any timing-constrained feature. Depends on "
            "issue #434 (feature-ownership gating)."
        )


class TestBonusAction_DeprivedWithActions:
    """SRD § Playing the Game › Bonus Actions › Deprivation.

    > Anything that deprives you of your ability to take actions also
    > prevents you from taking a Bonus Action.
    """

    def test_incapacitated_creature_can_take_actions_returns_false(self):
        """Incapacitating conditions short-circuit `can_take_actions()`.

        creature.py:308-318 — Paralyzed/Stunned/Unconscious/Petrified/
        Surprised all flip `can_take_actions()` to False. The SRD
        rule requires that this same gate cover Bonus Actions; we
        defend the gate's input side here (the gate fires when
        expected) and exercise the output side below.
        """
        creature = _make_creature()
        for cond in ("paralyzed", "stunned", "unconscious", "petrified"):
            creature.conditions.clear()
            creature.add_condition(cond)
            assert creature.can_take_actions() is False, (
                f"Condition '{cond}' must suppress can_take_actions()."
            )

    def test_enemy_turn_skips_actions_when_can_take_actions_false(self):
        """Enemy turn loop honors `can_take_actions()` for the whole turn.

        game_state.py:3910-3934 — `process_enemy_turn` checks
        `can_take_actions()` and short-circuits the entire turn with
        `EnemyTurnAction.INCAPACITATED`. Because the early return
        happens before any action or bonus-action dispatch, an
        incapacitated enemy cannot spend either slot. This satisfies
        the SRD's "also prevents you from taking a Bonus Action"
        clause for enemies via the action-suppression that comes
        first.
        """
        from dnd_engine.core.game_state import GameState

        src = inspect.getsource(GameState.process_enemy_turn)
        assert "can_take_actions" in src, (
            "process_enemy_turn must consult can_take_actions() to "
            "honor the SRD deprivation rule."
        )
        assert "INCAPACITATED" in src, (
            "process_enemy_turn must short-circuit with INCAPACITATED "
            "when actions are suppressed, which transitively blocks "
            "the bonus-action slot."
        )

    def test_player_bonus_action_is_not_guarded_when_actions_deprived(self):
        """GAP — no player-side guard mirrors the enemy `can_take_actions` check.

        Players go through `CombatActionExecutor` middleware
        (combat_middleware.py:73-113 TurnValidationMiddleware), which
        validates whose turn it is and that the actor is alive — but
        does NOT check `can_take_actions()` / `is_incapacitated()`.
        A player character that is Stunned but somehow gets prompted
        could call `consume_action(BONUS_ACTION)` and succeed, in
        violation of the SRD rule. In practice the CLI gates turn
        entry separately, but the engine-level guard is missing.
        """
        from dnd_engine.systems.combat_middleware import TurnValidationMiddleware

        src = inspect.getsource(TurnValidationMiddleware.process)
        assert "can_take_actions" not in src and "is_incapacitated" not in src, (
            "If TurnValidationMiddleware grows a condition guard, "
            "convert this stub to a live assertion against it."
        )

        pytest.skip(
            "GAP: player-side action/bonus-action dispatch does not "
            "check `can_take_actions()` or `is_incapacitated()`. The "
            "middleware chain "
            "(dnd-engine/dnd_engine/systems/combat_middleware.py:73"
            "-113) only validates turn ownership and is_alive. SRD "
            "requires that conditions which deprive actions also "
            "deprive bonus actions; the engine has no shared guard "
            "for the player path equivalent to the enemy-side check "
            "at game_state.py:3910. Tracked by issue #440."
        )
