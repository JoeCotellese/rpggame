# ABOUTME: SRD conformance audit for "Playing the Game > Interacting with Objects".
# ABOUTME: Cross-references docs/srd/playing-the-game/interacting-with-objects.md against engine code.

"""SRD conformance: Interacting with Objects.

Maps every rule in `docs/srd/playing-the-game/interacting-with-objects.md`
to a test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import inspect

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.systems.action_economy import ActionType, TurnState

pytestmark = pytest.mark.srd(
    "playing-the-game/interacting-with-objects.md",
    lines="1585-1649",
)


def _make_character(name: str = "Adventurer", *, wis: int = 14, strength: int = 10) -> Character:
    """Plain Medium humanoid character fixture for object-interaction tests."""
    abilities = Abilities(
        strength=strength,
        dexterity=10,
        constitution=12,
        intelligence=10,
        wisdom=wis,
        charisma=10,
    )
    return Character(
        name=name,
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=10,
        ac=12,
        race="human",
        skill_proficiencies=["perception"],
    )


class TestInteractingWithObjects_Intro:
    """SRD § Playing the Game › Interacting with Objects › Intro.

    > Interacting with objects is often simple to resolve. The player
    > tells the GM that their character is doing something, such as
    > moving a lever or opening a door, and the GM describes what
    > happens. Sometimes, however, rules govern what you can do with
    > an object, as detailed in the following sections.
    """

    def test_player_can_open_a_door_as_a_basic_interaction(self) -> None:
        """`GameState.move` walks through an unlocked exit (door).

        The SRD's "opening a door" framing maps to the engine's
        exit-traversal in `GameState.move`
        (`dnd_engine/core/game_state.py:774`). Unlocked exits are
        traversed automatically without a check; locked exits short-
        circuit to `is_exit_locked` and require `attempt_unlock`. This
        confirms the "often simple to resolve" baseline.
        """
        assert callable(getattr(GameState, "move", None))
        src = inspect.getsource(GameState.move)
        assert "is_exit_locked" in src, (
            "GameState.move must consult is_exit_locked so unlocked "
            "doors traverse automatically (SRD: 'often simple to "
            "resolve')."
        )

    def test_locked_doors_require_an_attempt_unlock_routine(self) -> None:
        """`GameState.attempt_unlock` is the locked-door interaction surface.

        The SRD's "Sometimes, however, rules govern what you can do
        with an object" carve-out lands on the locked-door path:
        `attempt_unlock` (`dnd_engine/core/game_state.py:1021`)
        accepts a direction + method (key, lockpick) and reports
        success/failure. This is the canonical "rules govern object
        interaction" path the SRD anticipates.
        """
        assert callable(getattr(GameState, "attempt_unlock", None))


class TestInteractingWithObjects_WhatIsAnObject:
    """SRD § Playing the Game › Interacting with Objects › What Is an Object?

    > For the purpose of the rules, an object is a discrete,
    > inanimate item like a window, door, sword, book, table, chair,
    > or stone. It isn't a building or a vehicle, which are composed
    > of many objects.
    """

    def test_engine_models_objects_with_hp_and_ac(self) -> None:
        pytest.skip(
            "GAP: There is no first-class `Object` type with hit "
            "points or AC. Doors carry only `locked` / "
            "`hidden_until_unlocked` flags (see `GameState."
            "is_exit_locked`, dnd_engine/core/game_state.py:895); they "
            "are not attackable. Items in inventory carry no AC/HP. "
            "`CombatEngine.resolve_attack` "
            "(dnd_engine/core/combat.py) accepts only Creature/"
            "Character targets. The SRD's definition of 'object' as a "
            "discrete, inanimate item is honored conceptually (rooms "
            "carry doors/items/scenery as data) but the engine has no "
            "type for it. Tracked by issue #511."
        )

    def test_engine_distinguishes_objects_from_buildings_and_vehicles(self) -> None:
        pytest.skip(
            "GAP: depends on issue #511. Without an `Object` type, the "
            "SRD's exclusion ('not a building or a vehicle, which are "
            "composed of many objects') has nothing to enforce. "
            "Dungeons are composed of rooms which are dicts; there is "
            "no `Vehicle` or `Building` aggregate type. Tracked by "
            "issue #511."
        )


class TestInteractingWithObjects_TimeLimitedInteractions:
    """SRD § Playing the Game › Interacting with Objects › Time-Limited Object Interactions.

    > When time is short, such as in combat, interactions with objects
    > are limited: one free interaction per turn. That interaction
    > must occur during a creature's movement or action. Any
    > additional interactions require the Utilize action, as
    > explained in "Combat" later in "Playing the Game."
    """

    def test_one_free_object_interaction_per_turn(self) -> None:
        """`TurnState.free_object_interaction_used` caps free interactions at one per turn.

        The SRD's "one free interaction per turn" is enforced at
        `dnd_engine/systems/action_economy.py:71-75`: the first
        `consume_action(FREE_OBJECT)` flips
        `free_object_interaction_used` to True; a second call returns
        False. This is the canonical engine seam.

        Coordinates with the actions audit (`test_actions.py` ::
        `TestAction_Utilize::test_free_object_interaction_is_modeled_distinct_from_utilize`)
        which establishes the same primitive.
        """
        turn = TurnState()
        assert turn.is_action_available(ActionType.FREE_OBJECT) is True
        assert turn.consume_action(ActionType.FREE_OBJECT) is True
        # Second free-object interaction in the same turn is rejected.
        assert turn.consume_action(ActionType.FREE_OBJECT) is False
        assert turn.is_action_available(ActionType.FREE_OBJECT) is False

    def test_free_object_interaction_resets_at_start_of_next_turn(self) -> None:
        """`TurnState.reset()` restores the per-turn free interaction.

        SRD: the free interaction is *per turn*. `TurnState.reset`
        (`action_economy.py:125-138`) clears
        `free_object_interaction_used` back to False so the next turn
        gets its own free interaction. `InitiativeTracker.next_turn`
        (`systems/initiative.py:199-202`) invokes `.reset()` on the
        incoming combatant, so this propagates correctly.
        """
        turn = TurnState()
        turn.consume_action(ActionType.FREE_OBJECT)
        assert turn.is_action_available(ActionType.FREE_OBJECT) is False
        turn.reset(speed=30)
        assert turn.is_action_available(ActionType.FREE_OBJECT) is True

    def test_additional_interactions_route_through_utilize_action(self) -> None:
        """`use_item_combat` is the Utilize surface for additional interactions.

        The SRD's "any additional interactions require the Utilize
        action" is mirrored by `GameState.use_item_combat`
        (`dnd_engine/core/game_state.py:4578`), which routes object
        use through `ActionType.ACTION` (or whichever action_type the
        item's JSON declares — see `action_required_str` parsing at
        line 4619). Coordinates with `test_actions.py::TestAction_Utilize`
        which is the primary site for this rule.
        """
        assert callable(getattr(GameState, "use_item_combat", None))
        src = inspect.getsource(GameState.use_item_combat)
        # use_item_combat must speak action_economy language.
        assert "ActionType" in src or "action_type" in src.lower()

    def test_free_interaction_must_occur_during_movement_or_action(self) -> None:
        pytest.skip(
            "GAP: The SRD's 'must occur during a creature's movement "
            "or action' temporal binding is not enforced. `TurnState` "
            "(dnd_engine/systems/action_economy.py:26-40) has no "
            "`current_phase` field; `consume_action(FREE_OBJECT)` "
            "succeeds at any moment in the turn. There is no notion "
            "of 'mid-movement' vs 'mid-action' vs 'idle' on the turn "
            "state, so an interaction declared between movement and "
            "action is indistinguishable from one declared during "
            "either. Tracked by issue #519."
        )


class TestInteractingWithObjects_FindingHiddenObjects:
    """SRD § Playing the Game › Interacting with Objects › Finding Hidden Objects.

    > When your character searches for hidden things, such as a
    > secret door or a trap, the GM typically asks you to make a
    > Wisdom (Perception) check, provided you describe the character
    > searching in the hidden object's vicinity. On a success, you
    > find the object, other important details, or both.
    > If you describe your character searching nowhere near a hidden
    > object, a Wisdom (Perception) check won't reveal the object,
    > no matter the check's total.
    """

    def test_passive_perception_reveals_hidden_features_on_room_entry(self) -> None:
        """`_check_passive_perception` runs Wisdom-based Perception on entry.

        The SRD's "Wisdom (Perception) check" for hidden things has a
        partial engine analog: `GameState._check_passive_perception`
        (`dnd_engine/core/game_state.py:2913`) computes
        `10 + perception_mod` and compares it against per-feature DCs
        on room entry. This honors the "Wisdom (Perception) check"
        clause for the passive case; active on-demand search is gapped
        below.
        """
        src = inspect.getsource(GameState._check_passive_perception)
        assert "perception" in src.lower()
        assert (
            "passive_perception" in src.lower() or "passive perception" in src.lower()
        ), (
            "_check_passive_perception must compute passive Perception "
            "(10 + Perception mod) so the SRD's hidden-object check "
            "primitive is grounded."
        )

    def test_search_room_uses_a_skill_check_when_room_declares_search_checks(self) -> None:
        """`GameState.search_room` makes a skill check when configured.

        SRD: "the GM typically asks you to make a Wisdom (Perception)
        check." `search_room` (`dnd_engine/core/game_state.py:1409`)
        consumes `search_checks` from the room JSON and calls
        `character.make_skill_check(skill, dc, skills_data)` (line
        1484). The skill is whatever the room JSON names (often
        Investigation or Perception) — this is the engine's primary
        "searching reveals hidden things" surface.
        """
        assert callable(getattr(GameState, "search_room", None))
        src = inspect.getsource(GameState.search_room)
        assert "make_skill_check" in src, (
            "search_room must call Character.make_skill_check so the "
            "SRD's hidden-object check has a real implementation."
        )
        assert "hidden_items" in src, (
            "search_room must surface hidden items so the SRD's 'find "
            "the object' clause has an effect."
        )

    def test_perception_is_a_wisdom_skill_in_the_catalog(self) -> None:
        """Skills catalog lists Perception as a Wisdom skill.

        Data-parity check: the SRD names Wisdom (Perception)
        specifically. `dnd-engine/dnd_engine/data/srd/skills.json`
        must catalogue `perception` with `ability: "wis"` so the
        check primitive routes to the right modifier.
        """
        import json
        from pathlib import Path

        skills_path = (
            Path(__file__).resolve().parents[3]
            / "dnd_engine"
            / "data"
            / "srd"
            / "skills.json"
        )
        skills = json.loads(skills_path.read_text())
        assert "perception" in skills
        assert skills["perception"]["ability"] == "wis"

    def test_player_can_initiate_an_on_demand_perception_check_in_a_vicinity(self) -> None:
        pytest.skip(
            "GAP: There is no player-initiated on-demand Wisdom "
            "(Perception) check. `_check_passive_perception` "
            "(dnd_engine/core/game_state.py:2913) runs on room entry "
            "only — `room['passive_checks_done']` (line 2929-2937) "
            "blocks re-checks. `search_room` (line 1409) consumes "
            "room-level `search_checks` (often Investigation, not "
            "Perception) and does not accept a player-supplied "
            "vicinity description. The SRD's 'searching in the "
            "hidden object's vicinity' locality requirement has no "
            "engine analog. Tracked by issue #517."
        )

    def test_search_nowhere_near_a_hidden_object_cannot_reveal_it(self) -> None:
        pytest.skip(
            "GAP: The SRD's locality clause ('if you describe your "
            "character searching nowhere near a hidden object, a "
            "Wisdom (Perception) check won't reveal the object') "
            "requires per-feature vicinity metadata. `hidden_features` "
            "JSON has no `vicinity` field; `_check_passive_perception` "
            "applies all features on entry without considering "
            "location within the room. Tracked by issue #517."
        )


class TestInteractingWithObjects_CarryingObjects:
    """SRD § Playing the Game › Interacting with Objects › Carrying Objects.

    > You can usually carry your gear and treasure without worrying
    > about the weight of those objects. If you try to haul an
    > unusually heavy object or a massive number of lighter objects,
    > the GM might require you to abide by the rules for carrying
    > capacity in "Rules Glossary."
    """

    def test_character_has_a_carrying_capacity_derived_from_strength(self) -> None:
        pytest.skip(
            "GAP: `Character` (dnd_engine/core/character.py) has no "
            "`carrying_capacity_lb` or `current_load_lb` field. The "
            "SRD formula is `strength_score * 15`, but no method on "
            "Character computes it. The only `weight_limit_lb` "
            "reference in the codebase governs the Mage Hand spell "
            "(dnd_engine/spells/effects/manipulation.py:25), not the "
            "carrying character. Tracked by issue #513."
        )

    def test_inventory_refuses_to_exceed_carrying_capacity(self) -> None:
        pytest.skip(
            "GAP: `Inventory.add_item` (dnd_engine/systems/inventory.py) "
            "tracks counts but does not sum item weights against a "
            "per-character capacity. The SRD's 'GM might require you "
            "to abide by the rules' is therefore a no-op in the "
            "engine — players can carry arbitrary amounts. Tracked by "
            "issue #513."
        )

    def test_encumbrance_affects_movement_or_attack(self) -> None:
        pytest.skip(
            "GAP: No Encumbrance / Heavily-Encumbered state exists. "
            "The SRD Rules Glossary uses Encumbered (-10 ft speed) "
            "and Heavily Encumbered (-20 ft speed, disadvantage on "
            "STR/DEX/CON checks and attacks). `Creature.speed` is a "
            "static int (dnd_engine/core/creature.py); nothing "
            "subtracts encumbrance penalties from it. Tracked by "
            "issue #513."
        )


class TestInteractingWithObjects_BreakingObjects:
    """SRD § Playing the Game › Interacting with Objects › Breaking Objects.

    > As an action, you can automatically break or otherwise destroy
    > a fragile, nonmagical object, such as a glass container or a
    > piece of paper. If you try to damage something more resilient,
    > the GM might use the rules on breaking objects in "Rules
    > Glossary."
    """

    def test_fragile_nonmagical_object_breaks_automatically_as_an_action(self) -> None:
        pytest.skip(
            "GAP: There is no `break_object` action and no `fragile` "
            "flag on objects. The script executor (dnd_engine/"
            "scenarios/script_executor.py:200-224) rejects any action "
            "other than 'wait', 'attack', 'monster_attack'. "
            "`GameState.get_available_actions()` (game_state.py:758) "
            "returns `[attack, use_item]` in combat — no `break` "
            "verb. The SRD's auto-break-fragile rule has no engine "
            "surface. Tracked by issue #511."
        )

    def test_resilient_object_breaking_uses_rules_glossary_thresholds(self) -> None:
        pytest.skip(
            "GAP: The SRD's Rules Glossary breaks-objects table "
            "(damage threshold, HP by material/size) is unimplemented. "
            "There is no object-AC / object-HP model "
            "(dnd_engine/core/game_state.py doors carry only "
            "`locked` / `hidden_until_unlocked`). `CombatEngine."
            "resolve_attack` (dnd_engine/core/combat.py) cannot "
            "target objects. Tracked by issue #511."
        )

    def test_break_object_consumes_the_turn_action_slot(self) -> None:
        pytest.skip(
            "GAP: The SRD prefaces the rule with 'As an action' — the "
            "break-object verb should consume `ActionType.ACTION` via "
            "`TurnState.consume_action`. Action economy is modeled "
            "(action_economy.py:42-81) but no break-object handler "
            "invokes it. Tracked by issue #511."
        )


class TestInteractingWithObjects_MarchingOrder:
    """SRD § Playing the Game › Interacting with Objects › Marching Order.

    > The adventurers should establish a marching order while they
    > travel, whether indoors or outdoors. A marching order makes it
    > easier to determine which characters are affected by traps,
    > which ones can spot hidden enemies, and which ones are the
    > closest to those enemies if a fight breaks out. You can change
    > your marching order outside combat and record the order any
    > way you like.
    """

    def test_party_exposes_a_marching_order(self) -> None:
        pytest.skip(
            "GAP: `Party` (dnd_engine/core/party.py) holds `characters: "
            "list[Character]` in insertion order with no `marching_"
            "order` field, no `set_marching_order()` setter, and no "
            "front/back rank distinction. The list order happens to "
            "double as a *de facto* order but is never consulted for "
            "the SRD's three named consequences (traps, hidden "
            "enemies, combat starting positions). Tracked by issue "
            "#515."
        )

    def test_marching_order_determines_who_triggers_a_trap_first(self) -> None:
        pytest.skip(
            "GAP: Trap triggering is uniform across the party. "
            "`GameState._check_passive_perception` (game_state.py:"
            "2913) iterates `self.party.characters` for every hidden "
            "feature without consulting marching order; the front-"
            "rank character does not get first crack at spotting / "
            "triggering. Tracked by issue #515."
        )

    def test_marching_order_seeds_combat_starting_positions(self) -> None:
        pytest.skip(
            "GAP: Combat starting positions are inherited from the "
            "client-2d `RoomLayout` (client-2d/src/client_2d/) with no "
            "input from a party marching order. `GameState."
            "_start_combat` (game_state.py:3085) sets `in_combat = "
            "True` and rolls initiative without positioning the front "
            "rank closest to enemies. Tracked by issue #515; see also "
            "the broader tactical-grid gaps referenced in #436."
        )

    def test_marching_order_can_be_changed_outside_combat(self) -> None:
        pytest.skip(
            "GAP: depends on issue #515 (no marching_order field yet). "
            "The SRD's 'you can change your marching order outside "
            "combat' clause is moot until a marching order exists. "
            "Once it lands, the setter must check `not self.in_combat` "
            "before allowing reorders."
        )
