# ABOUTME: SRD conformance audit for "Playing the Game > Actions".
# ABOUTME: Cross-references docs/srd/playing-the-game/actions.md against engine code.

"""SRD conformance: Actions.

Maps every rule in `docs/srd/playing-the-game/actions.md` to a test.
Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from dnd_engine.core.combat import CombatEngine
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.game_state import GameState
from dnd_engine.scenarios import script_executor as script_executor_mod
from dnd_engine.systems.action_economy import ActionType, TurnState

pytestmark = pytest.mark.srd(
    "playing-the-game/actions.md",
    lines="1317-1415",
)


CLASSES_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "classes.json"
)
MONSTERS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "monsters.json"
)
SKILLS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "skills.json"
)


def _make_engine_and_combatants() -> tuple[CombatEngine, Creature, Creature]:
    """Two-creature fixture for engine-level attack resolution."""
    engine = CombatEngine(DiceRoller(seed=42))
    abilities = Abilities(
        strength=16,
        dexterity=14,
        constitution=15,
        intelligence=10,
        wisdom=12,
        charisma=8,
    )
    attacker = Creature(name="Attacker", max_hp=20, ac=16, abilities=abilities)
    defender = Creature(name="Defender", max_hp=7, ac=13, abilities=abilities)
    return engine, attacker, defender


class TestActions_Intro:
    """SRD § Playing the Game › Actions › Intro.

    > When you do something other than moving or communicating, you
    > typically take an action. The Action table lists the game's main
    > actions, which are defined in more detail in "Rules Glossary."
    """

    def test_turn_state_models_one_action_per_turn(self) -> None:
        """`TurnState` models a single per-turn action slot.

        The SRD's framing — actions are the discrete units of "doing
        something" each turn — maps directly to the boolean
        `action_available` slot in `TurnState` (action_economy.py:37).
        Movement and free-form communication ride separate counters
        (`movement_remaining`, `NO_ACTION`), matching the SRD's
        carve-out for "moving or communicating."
        """
        turn = TurnState()
        assert turn.action_available is True
        assert turn.is_action_available(ActionType.ACTION) is True

    def test_action_type_enum_distinguishes_action_from_movement_and_chatter(self) -> None:
        """`ActionType` separates ACTION from NO_ACTION (free chatter).

        Source-level guard: the enum carries discrete members for the
        SRD's "action" vs. its "moving or communicating" carve-out
        (movement uses `TurnState.movement_remaining`; speech and
        item-drops use `ActionType.NO_ACTION`).
        """
        names = {m.name for m in ActionType}
        assert {"ACTION", "BONUS_ACTION", "FREE_OBJECT", "NO_ACTION"} <= names


class TestAction_Attack:
    """SRD § Playing the Game › Actions › Attack.

    > Attack with a weapon or an Unarmed Strike.
    """

    def test_engine_resolves_a_weapon_attack(self) -> None:
        """`CombatEngine.resolve_attack` is the Attack-action surface.

        The Attack action's mechanical body lives in
        `dnd_engine/core/combat.py`. Asserting it produces a hit/damage
        outcome confirms the rule has a real implementation, distinct
        from the unimplemented Dash/Disengage/Dodge bodies below.
        """
        engine, attacker, defender = _make_engine_and_combatants()
        result = engine.resolve_attack(
            attacker=attacker,
            defender=defender,
            attack_bonus=5,
            damage_dice="1d8+3",
        )
        assert hasattr(result, "hit")
        assert hasattr(result, "damage")
        assert result.attack_roll >= 1

    def test_script_executor_exposes_attack_action(self) -> None:
        """Scenario YAMLs can express `action: attack`.

        The script executor's action dispatcher (script_executor.py:
        200-224) accepts `attack` as a first-class action type, which
        is how the SRD-named Attack action surfaces to test scenarios.
        """
        src = inspect.getsource(script_executor_mod.ScriptExecutor._run_action)
        assert '"attack"' in src or "'attack'" in src


class TestAction_Dash:
    """SRD § Playing the Game › Actions › Dash.

    > For the rest of the turn, give yourself extra movement equal to
    > your Speed.
    """

    def test_dash_action_doubles_movement_for_the_turn(self) -> None:
        """Dash consumes the Action and adds the actor's Speed to the
        remaining movement pool for the rest of the turn (SRD: 'For
        the rest of the turn, give yourself extra movement equal to
        your Speed')."""
        from dnd_engine.systems.actions import dash

        turn = TurnState()
        turn.reset(speed=30)
        ok, _ = dash(turn)

        assert ok is True
        assert turn.action_available is False
        assert turn.movement_remaining == 60  # 30 base + 30 from Dash


class TestAction_Disengage:
    """SRD § Playing the Game › Actions › Disengage.

    > Your movement doesn't provoke Opportunity Attacks for the rest
    > of the turn.
    """

    def test_disengage_action_suppresses_opportunity_attacks_this_turn(self) -> None:
        """Disengage consumes the Action and sets the per-turn flag
        the OA publish path consults; while the flag is set, the
        actor's movement does not provoke Opportunity Attacks (SRD:
        'Your movement doesn't provoke Opportunity Attacks for the
        rest of the turn')."""
        from dnd_engine.core.position import Position
        from dnd_engine.systems.actions import disengage
        from dnd_engine.systems.initiative import InitiativeTracker
        from dnd_engine.systems.opportunity_attacks import (
            publish_movement_provoke,
            register_default_opportunity_attack,
        )
        from dnd_engine.systems.reactions import ReactionDispatcher

        abilities = Abilities(10, 10, 10, 10, 10, 10)
        reactor = Creature("Fighter", max_hp=20, ac=15, abilities=abilities)
        mover = Creature("Goblin", max_hp=20, ac=15, abilities=abilities)
        tracker = InitiativeTracker(DiceRoller(seed=1))
        tracker.add_combatant(reactor)
        tracker.add_combatant(mover)
        dispatcher = ReactionDispatcher(tracker)
        register_default_opportunity_attack(
            dispatcher, reactor, get_position=lambda: Position(5, 5)
        )

        ok, _ = disengage(tracker.turn_states[mover])
        assert ok is True

        outcomes = publish_movement_provoke(
            dispatcher,
            mover=mover,
            from_position=Position(6, 5),
            to_position=Position(8, 5),
        )

        assert outcomes == []
        assert tracker.turn_states[reactor].reaction_available is True


class TestAction_Dodge:
    """SRD § Playing the Game › Actions › Dodge.

    > Until the start of your next turn, attack rolls against you have
    > Disadvantage, and you make Dexterity saving throws with
    > Advantage. You lose this benefit if you have the Incapacitated
    > condition or if your Speed is 0.
    """

    def test_dodging_creature_imposes_disadvantage_on_attackers(self) -> None:
        """A dodging defender forces attack rolls against them to
        disadvantage (SRD: 'attack rolls against you have
        Disadvantage')."""
        from dnd_engine.systems.actions import dodge

        engine, attacker, defender = _make_engine_and_combatants()
        defender_turn = TurnState()
        defender_turn.reset(speed=defender.speed)
        ok, _ = dodge(defender, defender_turn)
        assert ok is True

        result = engine.resolve_attack(
            attacker=attacker,
            defender=defender,
            attack_bonus=5,
            damage_dice="1d8+3",
        )

        assert result.disadvantage is True

    def test_dodging_creature_rolls_dex_saves_with_advantage(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A dodging creature rolls DEX saves with advantage (SRD:
        'you make Dexterity saving throws with Advantage')."""
        from dnd_engine.core.dice import DiceRoller
        from dnd_engine.systems.actions import dodge

        _, _, defender = _make_engine_and_combatants()
        defender_turn = TurnState()
        defender_turn.reset(speed=defender.speed)
        ok, _ = dodge(defender, defender_turn)
        assert ok is True

        captured: dict[str, bool] = {}
        original_roll = DiceRoller.roll

        def spy(self, dice, advantage=False, disadvantage=False, **kwargs):
            captured["advantage"] = advantage
            captured["disadvantage"] = disadvantage
            return original_roll(
                self, dice, advantage=advantage, disadvantage=disadvantage, **kwargs
            )

        monkeypatch.setattr(DiceRoller, "roll", spy)

        defender.make_saving_throw("dex", dc=10)

        assert captured.get("advantage") is True
        assert captured.get("disadvantage") is False

    def test_dodge_benefit_ends_with_incapacitated_or_speed_zero(self) -> None:
        """The dodge benefit is suppressed if the dodger is
        Incapacitated or their effective Speed is 0 (SRD: 'You lose
        this benefit if you have the Incapacitated condition or if
        your Speed is 0'). Also: taking Dodge while already
        incapacitated fails outright."""
        from dnd_engine.systems.actions import dodge

        # (a) Incapacitated dodger: attackers do NOT get disadvantage.
        engine, attacker, defender = _make_engine_and_combatants()
        defender_turn = TurnState()
        defender_turn.reset(speed=defender.speed)
        ok, _ = dodge(defender, defender_turn)
        assert ok is True
        defender.add_condition("stunned")  # Stunned imposes Incapacitated.
        result = engine.resolve_attack(
            attacker=attacker,
            defender=defender,
            attack_bonus=5,
            damage_dice="1d8+3",
        )
        assert result.disadvantage is False

        # (b) Speed-zero dodger: benefit suppressed.
        engine, attacker, defender = _make_engine_and_combatants()
        defender_turn = TurnState()
        defender_turn.reset(speed=defender.speed)
        ok, _ = dodge(defender, defender_turn)
        assert ok is True
        defender.speed = 0
        result = engine.resolve_attack(
            attacker=attacker,
            defender=defender,
            attack_bonus=5,
            damage_dice="1d8+3",
        )
        assert result.disadvantage is False

        # (c) Cannot take Dodge while already Incapacitated.
        _, _, defender = _make_engine_and_combatants()
        defender.add_condition("paralyzed")
        defender_turn = TurnState()
        defender_turn.reset(speed=defender.speed)
        ok, reason = dodge(defender, defender_turn)
        assert ok is False
        assert reason == "incapacitated"
        assert defender_turn.action_available is True  # Not consumed on rejection.

    def test_dodge_benefit_ends_at_start_of_dodgers_next_turn(self) -> None:
        """The dodge flag clears when the dodger's own next turn
        starts via ``InitiativeTracker.next_turn`` (SRD: 'Until the
        start of your next turn')."""
        from dnd_engine.systems.actions import dodge
        from dnd_engine.systems.initiative import InitiativeTracker

        abilities = Abilities(10, 10, 10, 10, 10, 10)
        dodger = Creature("Dodger", max_hp=10, ac=12, abilities=abilities)
        other = Creature("Other", max_hp=10, ac=12, abilities=abilities)
        tracker = InitiativeTracker(DiceRoller(seed=1))
        tracker.add_combatant(dodger)
        tracker.add_combatant(other)

        # Advance to the dodger's turn (initiative order is rolled and
        # order-agnostic for this test).
        while tracker.get_current_combatant().creature is not dodger:
            tracker.next_turn()

        ok, _ = dodge(dodger, tracker.turn_states[dodger])
        assert ok is True
        assert dodger.is_dodging is True

        # Next combatant's turn — dodge still active.
        tracker.next_turn()
        assert tracker.get_current_combatant().creature is not dodger
        assert dodger.is_dodging is True

        # Back to dodger — benefit ends at the start of their next turn.
        tracker.next_turn()
        assert tracker.get_current_combatant().creature is dodger
        assert dodger.is_dodging is False


class TestAction_Help:
    """SRD § Playing the Game › Actions › Help.

    > Help another creature's ability check or attack roll, or
    > administer first aid.
    """

    def test_help_grants_advantage_on_helped_creatures_next_check_or_attack(self) -> None:
        pytest.skip(
            "GAP: Help is not a playable action. There is no helper "
            "registration, no 'helped_by' flag, and no plumbing that "
            "grants advantage on the helped creature's next ability "
            "check or attack roll. The combat engine's "
            "advantage/disadvantage parameter would be the consumption "
            "site (dnd_engine/core/combat.py:122) but nothing sets it "
            "via Help. Tracked by issue #441."
        )

    def test_help_first_aid_stabilizes_a_zero_hp_ally(self) -> None:
        pytest.skip(
            "GAP: stabilization plumbing exists "
            "(dnd_engine/core/character.py:1330-1380 — death saves "
            "auto-stabilize on 3 successes, and the healer's kit item "
            "description in items.json names stabilization as an "
            "action) but no Help-action handler invokes it. A teammate "
            "cannot take the Help action to stabilize a downed ally. "
            "Tracked by issue #441; see also #352 (2D Client: "
            "stabilize ally)."
        )


class TestAction_Hide:
    """SRD § Playing the Game › Actions › Hide.

    > Make a Dexterity (Stealth) check.
    """

    def test_hide_makes_a_dexterity_stealth_check(self) -> None:
        pytest.skip(
            "GAP: There is no `Hide` action handler. A Stealth check "
            "primitive exists "
            "(`Character.make_skill_check('stealth', ...)` "
            "in dnd_engine/core/character.py:726) and is used for "
            "surprise rounds (game_state.py:3050), but no action "
            "dispatches it on demand, no hidden/unseen flag is set on "
            "the hider, and visibility is not consulted by attack "
            "resolution. Tracked by issue #443."
        )


class TestAction_Influence:
    """SRD § Playing the Game › Actions › Influence.

    > Make a Charisma (Deception, Intimidation, Performance, or
    > Persuasion) or Wisdom (Animal Handling) check to alter a
    > creature's attitude.
    """

    def test_influence_skill_catalog_covers_srd_options(self) -> None:
        """Skill catalog encodes the SRD's allowed Influence skills.

        Data-parity check: the five Influence-eligible skills the SRD
        names (Deception, Intimidation, Performance, Persuasion,
        Animal Handling) are all present in skills.json with the
        correct backing ability (CHA for the first four, WIS for
        Animal Handling). This confirms the *check* primitive exists
        even though no Influence action consumes it.
        """
        skills = json.loads(SKILLS_JSON.read_text())
        assert skills["deception"]["ability"] == "cha"
        assert skills["intimidation"]["ability"] == "cha"
        assert skills["performance"]["ability"] == "cha"
        assert skills["persuasion"]["ability"] == "cha"
        assert skills["animal_handling"]["ability"] == "wis"

    def test_influence_action_alters_creature_attitude(self) -> None:
        pytest.skip(
            "GAP: There is no Influence action handler and no NPC "
            "attitude model. The skill checks exist "
            "(`make_skill_check('persuasion', ...)` etc., "
            "character.py:726) but no action dispatches them at an "
            "NPC, and no NPC carries an attitude axis (friendly / "
            "indifferent / hostile) for the check to shift. Tracked by "
            "issue #444."
        )


class TestAction_Magic:
    """SRD § Playing the Game › Actions › Magic.

    > Cast a spell, use a magic item, or use a magical feature.
    """

    def test_cast_spell_combat_resolves_a_spell_in_combat(self) -> None:
        """`GameState.cast_spell_combat` is the Magic-action surface for spells.

        The Magic action's spell branch is implemented at
        `dnd_engine/core/game_state.py:2077`. The method validates and
        consumes a spell slot, resolves the spell, and emits events —
        i.e., it is the engine-side body of the SRD Magic action when
        the chosen output is a spell.
        """
        assert callable(getattr(GameState, "cast_spell_combat", None))
        src = inspect.getsource(GameState.cast_spell_combat)
        assert "spell_slot" in src or "spell_level" in src, (
            "cast_spell_combat must consult spell slots so the Magic "
            "action honors the casting cost."
        )

    def test_use_item_combat_resolves_a_magic_item_in_combat(self) -> None:
        """`GameState.use_item_combat` is the Magic/Utilize surface for items.

        The Magic action also covers "use a magic item." The combat
        item-use path lives at `dnd_engine/core/game_state.py:4578`
        and validates action economy + applies the item effect. The
        Utilize action below (use a *nonmagical* object) is the
        unimplemented sibling.
        """
        assert callable(getattr(GameState, "use_item_combat", None))
        src = inspect.getsource(GameState.use_item_combat)
        assert "action economy" in src.lower() or "consume" in src.lower()

    def test_magical_feature_class_action_dispatch(self) -> None:
        pytest.skip(
            "GAP: 'use a magical feature' (the third Magic-action "
            "branch — e.g., Channel Divinity, Wild Shape, racial "
            "spell-likes) has no engine-side dispatcher. Class features "
            "are stored as descriptive strings in "
            "dnd_engine/data/srd/classes.json with no executable "
            "handler. Tracked by issue #446."
        )


class TestAction_Ready:
    """SRD § Playing the Game › Actions › Ready.

    > Prepare to take an action in response to a trigger you define.
    """

    def test_ready_action_holds_an_action_for_a_trigger(self) -> None:
        pytest.skip(
            "GAP: Ready is not a playable action. The Reaction "
            "economy itself is not modeled (see issue #412), and Ready "
            "specifically requires a trigger -> reaction dispatcher "
            "(see issue #429) plus pause/resume of the readier's turn "
            "(see issue #430). No 'readied action' slot exists on "
            "`TurnState` (dnd_engine/systems/action_economy.py:26-40). "
            "Tracked under #412/#429/#430."
        )


class TestAction_Search:
    """SRD § Playing the Game › Actions › Search.

    > Make a Wisdom (Insight, Medicine, Perception, or Survival)
    > check.
    """

    def test_search_skill_catalog_covers_srd_options(self) -> None:
        """Skill catalog encodes the SRD's allowed Search skills.

        Data-parity check: the four Search-eligible WIS skills
        (Insight, Medicine, Perception, Survival) are all present in
        skills.json under Wisdom. The check primitive exists even
        though no SRD-shaped Search action dispatches it.
        """
        skills = json.loads(SKILLS_JSON.read_text())
        assert skills["insight"]["ability"] == "wis"
        assert skills["medicine"]["ability"] == "wis"
        assert skills["perception"]["ability"] == "wis"
        assert skills["survival"]["ability"] == "wis"

    def test_srd_search_action_makes_a_wisdom_check(self) -> None:
        pytest.skip(
            "GAP: The 'search' string in the engine "
            "(game_state.py:1409 `search_room`, action token in "
            "game_state.py:770-771) is the *exploration* Search — find "
            "items / traps in a room — not the SRD Actions §  Search "
            "WIS check that a creature can choose on its combat turn. "
            "The exploration version sometimes triggers an "
            "Investigation/Perception check, but no action takes a "
            "Wisdom (Insight/Medicine/Perception/Survival) check at "
            "the player's choice as a discrete combat action. Tracked "
            "by issue #449."
        )


class TestAction_Study:
    """SRD § Playing the Game › Actions › Study.

    > Make an Intelligence (Arcana, History, Investigation, Nature,
    > or Religion) check.
    """

    def test_study_skill_catalog_covers_srd_options(self) -> None:
        """Skill catalog encodes the SRD's allowed Study skills.

        Data-parity check: the five Study-eligible INT skills
        (Arcana, History, Investigation, Nature, Religion) are all
        present in skills.json under Intelligence.
        """
        skills = json.loads(SKILLS_JSON.read_text())
        assert skills["arcana"]["ability"] == "int"
        assert skills["history"]["ability"] == "int"
        assert skills["investigation"]["ability"] == "int"
        assert skills["nature"]["ability"] == "int"
        assert skills["religion"]["ability"] == "int"

    def test_study_action_makes_an_intelligence_check(self) -> None:
        pytest.skip(
            "GAP: Study is not a playable action. The underlying INT "
            "skill checks exist via `make_skill_check` "
            "(character.py:726) but no action dispatcher offers Study "
            "as a player choice on a combat turn. Tracked by issue "
            "#451."
        )


class TestAction_Utilize:
    """SRD § Playing the Game › Actions › Utilize.

    > Use a nonmagical object.

    Note: the SRD source for actions.md prints this entry as "Utilize"
    in the table. The accompanying prose elsewhere in the SRD also
    refers to it via the verb "use", and the engine's available-action
    string is `"use_item"` (game_state.py:766).
    """

    def test_use_item_combat_is_the_utilize_surface_for_objects(self) -> None:
        """`use_item_combat` consumes a turn action to use an object.

        The Utilize body lives at `dnd_engine/core/game_state.py:4578`
        and routes through action-economy validation; this is the
        engine's mechanical home for the SRD's "Use a nonmagical
        object" action. Magic items currently share this surface
        (Magic action overlaps).
        """
        assert callable(getattr(GameState, "use_item_combat", None))
        src = inspect.getsource(GameState.use_item_combat)
        # Action-economy gating must be invoked so Utilize costs the
        # turn's action, not be free.
        assert "action economy" in src.lower() or "consume" in src.lower()

    def test_free_object_interaction_is_modeled_distinct_from_utilize(self) -> None:
        """`FREE_OBJECT` covers the one-per-turn free object interaction.

        SRD's Utilize action sits next to the free per-turn object
        interaction (draw a weapon, open an unstuck door) — the engine
        models that distinction with a separate `ActionType.FREE_OBJECT`
        slot (action_economy.py:21, :71-75). Confirming both seams
        exist defends Utilize from being silently merged with the free
        interaction.
        """
        turn = TurnState()
        # First free-object use succeeds.
        assert turn.consume_action(ActionType.FREE_OBJECT) is True
        # Second free-object use the same turn is rejected.
        assert turn.consume_action(ActionType.FREE_OBJECT) is False
        # The full ACTION slot is independent and still available.
        assert turn.is_action_available(ActionType.ACTION) is True


class TestActions_ImprovisedAndOther:
    """SRD § Playing the Game › Actions › Improvised actions.

    > Player characters and monsters can also do things not covered by
    > these actions. Many class features and other abilities provide
    > additional action options, and you can improvise other actions.
    > When you describe an action not detailed elsewhere in the rules,
    > the Game Master tells you whether that action is possible and
    > what kind of D20 Test you need to make, if any.
    """

    def test_class_features_provide_additional_action_options(self) -> None:
        """classes.json carries class features that name additional actions.

        Data-parity check: at least one class feature in classes.json
        describes itself as enabling additional action options (e.g.,
        rogue Cunning Action enables bonus-action Dash/Disengage/Hide).
        The SRD's "many class features and other abilities provide
        additional action options" clause is therefore reflected in
        the catalog, even though the named actions themselves are
        unimplemented (see Dash/Disengage/Hide above).
        """
        classes = json.loads(CLASSES_JSON.read_text())
        cunning_action_seen = False
        for _class_id, cdata in classes.items():
            for feature_list in cdata.get("features_by_level", {}).values():
                # `features_by_level` is a level-keyed dict of lists of dicts.
                if not isinstance(feature_list, list):
                    continue
                for feature in feature_list:
                    desc = (feature.get("description") or "").lower()
                    if "dash" in desc and "disengage" in desc:
                        cunning_action_seen = True
                        break
        assert cunning_action_seen, (
            "Expected at least one class feature in classes.json to "
            "reference Dash/Disengage as additional action options "
            "(e.g., rogue Cunning Action)."
        )

    def test_improvised_action_dispatch_uses_a_d20_test_at_gm_discretion(self) -> None:
        pytest.skip(
            "GAP: There is no improvised-action surface. The script "
            "executor dispatcher rejects anything that is not 'wait', "
            "'attack', or 'monster_attack' with a "
            "`ScriptExecutionError(\"unknown script action\")` "
            "(dnd_engine/scenarios/script_executor.py:221-224). A "
            "player cannot describe an improvised action and have the "
            "engine route them to a GM-chosen D20 test. The "
            "`make_skill_check` primitive (character.py:726) is the "
            "obvious building block but is not exposed as an action. "
            "Tracked by issue #453."
        )


class TestActions_OneThingAtATime:
    """SRD § Playing the Game › Actions › One Thing at a Time.

    > The game uses actions to govern how much you can do at one
    > time. You can take only one action at a time. This principle is
    > most important in combat, as explained in "Combat" later in
    > "Playing the Game." Actions can come up in other situations,
    > too: in a social interaction, you can try to Influence a
    > creature or use the Search action to read the creature's body
    > language, but you can't do both at the same time. And when
    > you're exploring a dungeon, you can't simultaneously use the
    > Search action to look for traps and use the Help action to aid
    > another character who's trying to open a stuck door (with the
    > Utilize action).
    """

    def test_only_one_action_per_combat_turn(self) -> None:
        """`TurnState.consume_action(ACTION)` succeeds once, then fails.

        This is the engine's enforcement of the SRD's "you can take
        only one action at a time" rule in combat. The first
        consumption flips `action_available` to False; a second
        consumption returns False (action_economy.py:59-63). Movement
        and free object interaction stay on independent counters and
        are unaffected.
        """
        turn = TurnState()
        assert turn.consume_action(ActionType.ACTION) is True
        assert turn.consume_action(ActionType.ACTION) is False
        # Movement and free-object remain untouched.
        assert turn.movement_remaining == 30
        assert turn.is_action_available(ActionType.FREE_OBJECT) is True

    def test_action_resets_at_start_of_next_turn(self) -> None:
        """`TurnState.reset()` restores the single action slot per turn.

        Verifies the per-turn cadence of the "one action at a time"
        rule: after consuming an action and ending the turn,
        `reset(speed=30)` gives the creature its action back for the
        new turn (action_economy.py:125-138).
        """
        turn = TurnState()
        turn.consume_action(ActionType.ACTION)
        assert turn.is_action_available(ActionType.ACTION) is False
        turn.reset(speed=30)
        assert turn.is_action_available(ActionType.ACTION) is True
        assert turn.movement_remaining == 30

    def test_one_action_at_a_time_enforced_outside_combat(self) -> None:
        pytest.skip(
            "GAP: The 'one action at a time' rule has no enforcement "
            "outside combat. `TurnState` is per-combat-turn (created "
            "by the initiative system, dnd_engine/systems/initiative.py"
            ":9) and is not consulted for exploration or social-"
            "interaction actions. The SRD example — 'you can't "
            "simultaneously use the Search action to look for traps "
            "and use the Help action [...]' — has no engine-level "
            "gate. Tracked by issue #455."
        )
