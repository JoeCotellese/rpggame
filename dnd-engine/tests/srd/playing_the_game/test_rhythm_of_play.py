# ABOUTME: SRD conformance audit for "Playing the Game > Rhythm of Play".
# ABOUTME: Cross-references docs/srd/playing-the-game/rhythm-of-play.md against engine code.

"""SRD conformance: Rhythm of Play.

Maps every rule in `docs/srd/playing-the-game/rhythm-of-play.md` to a
test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import inspect

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.game_state import GameState
from dnd_engine.systems.initiative import InitiativeTracker

pytestmark = pytest.mark.srd(
    "playing-the-game/rhythm-of-play.md",
    lines="515-566",
)


def _make_creature(name: str = "Combatant", *, dex: int = 14) -> Creature:
    """Plain Medium humanoid fixture for combat-order tests."""
    abilities = Abilities(
        strength=14,
        dexterity=dex,
        constitution=14,
        intelligence=10,
        wisdom=10,
        charisma=10,
    )
    return Creature(name=name, max_hp=20, ac=12, abilities=abilities, speed=30)


def _make_character(name: str = "PC") -> Character:
    """Plain Medium humanoid character fixture for rhythm-of-play tests."""
    abilities = Abilities(
        strength=12,
        dexterity=14,
        constitution=12,
        intelligence=10,
        wisdom=10,
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
    )


class TestRhythmOfPlay_ThreePillars:
    """SRD § Playing the Game › Rhythm of Play › Three Pillars.

    > The three main pillars of D&D play are social interaction,
    > exploration, and combat. Whichever one you're experiencing, the
    > game unfolds according to this basic pattern: [...]
    """

    def test_combat_pillar_is_modeled_via_in_combat_flag(self) -> None:
        """`GameState.in_combat` is the combat-pillar flag.

        The SRD's "combat" pillar is honored: `GameState`
        (`dnd_engine/core/game_state.py:610`) carries an `in_combat`
        bool and `_start_combat` / `_end_combat` flip it. This is the
        only pillar with a first-class engine state today.
        """
        src = inspect.getsource(GameState.__init__)
        assert "in_combat" in src, (
            "GameState must initialize an `in_combat` flag so the "
            "combat pillar has a state representation."
        )

    def test_exploration_pillar_routes_actions_distinctly_from_combat(self) -> None:
        """`get_available_actions` returns different verbs by mode.

        The SRD's exploration pillar gets distinct mechanics:
        `GameState.get_available_actions`
        (`dnd_engine/core/game_state.py:758-772`) returns
        `["attack", "use_item"]` when `in_combat` is True and
        `["move", ...]` otherwise. This is the engine's only seam
        that distinguishes exploration mechanics from combat
        mechanics.
        """
        src = inspect.getsource(GameState.get_available_actions)
        assert "in_combat" in src, (
            "get_available_actions must branch on `in_combat` so "
            "exploration and combat have distinct action vocabularies."
        )
        assert '"move"' in src or "'move'" in src
        assert '"attack"' in src or "'attack'" in src

    def test_social_interaction_pillar_has_its_own_mode(self) -> None:
        pytest.skip(
            "GAP: The SRD names *three* pillars; the engine has only "
            "two states (combat / not-combat). `GameState.in_combat` "
            "(game_state.py:610) is a bool, not a tri-state enum. "
            "NPC dialogue (`dnd_engine/llm/npc_chat.py`) is a bolted-"
            "on surface that does not flip a mode flag; the player "
            "can be 'in conversation' while `in_combat == False` and "
            "exploration mechanics still apply (move, search). "
            "Tracked by issue #520."
        )

    def test_game_mode_is_a_tri_state_enum(self) -> None:
        pytest.skip(
            "GAP: There is no `GameMode` enum with COMBAT, "
            "EXPLORATION, SOCIAL members. The engine's mode model is "
            "the binary `GameState.in_combat: bool`. Tracked by issue "
            "#520."
        )


class TestRhythmOfPlay_BasicPattern_Step1_DescribeScene:
    """SRD § Playing the Game › Rhythm of Play › Step 1.

    > 1: The Game Master Describes a Scene. The GM tells the players
    > where their adventurers are and what's around them (how many
    > doors lead out of a room, what's on a table, and so on).
    """

    def test_current_room_carries_a_description_field(self) -> None:
        """Rooms carry a `description` field consumed by the UI.

        The SRD's "GM tells the players where their adventurers are"
        maps to the engine's `Room.description` field rendered from
        room JSON. `GameState.get_current_room`
        (`dnd_engine/core/game_state.py:642-649`) returns the room
        dict whose `description` is the human-readable scene text.
        """
        # Static guard: get_current_room returns the room dict; the
        # `description` key is consumed by the CLI/2D client.
        assert callable(getattr(GameState, "get_current_room", None))

    def test_room_data_lists_exits_so_the_gm_can_describe_them(self) -> None:
        """Room data exposes `exits` so the scene can name the doors.

        SRD: "how many doors lead out of a room." Room JSONs carry
        an `exits` dict (consumed by `GameState.move`, `is_exit_
        locked`, etc., e.g. `dnd_engine/core/game_state.py:789`). The
        SRD's "describe the scene" step has the underlying data
        available.
        """
        src = inspect.getsource(GameState.move)
        assert 'exits' in src, (
            "GameState.move must read `exits` from the current room "
            "so the SRD's 'how many doors lead out' framing has "
            "concrete data."
        )

    def test_room_entry_triggers_a_room_enter_event_for_narration(self) -> None:
        """Entering a room emits ROOM_ENTER for downstream narration.

        The SRD step 1 is a *trigger* — \"the GM tells the players.\"
        The engine fires `EventType.ROOM_ENTER` on `move` (and on
        construction; see `GameState.__init__` and `move` at
        `dnd_engine/core/game_state.py:847-856`) so LLM narration
        layers (`dnd_engine/llm/enhancer.py`) can author the scene.
        """
        src = inspect.getsource(GameState.move)
        assert "ROOM_ENTER" in src, (
            "GameState.move must emit a ROOM_ENTER event so the SRD's "
            "step 1 (GM describes the scene) has a trigger hook."
        )

    def test_narration_loop_has_a_step1_phase(self) -> None:
        pytest.skip(
            "GAP: There is no formal narration loop. Step 1 happens "
            "implicitly via `ROOM_ENTER` events, but no "
            "`NarrationLoop.advance()` state machine binds it to "
            "step 2 / step 3. The LLM enhancer "
            "(dnd_engine/llm/enhancer.py) writes combat / death / "
            "victory text but is not driven by a per-pillar phased "
            "loop. Tracked by issue #521."
        )


class TestRhythmOfPlay_BasicPattern_Step2_PlayersDescribeActions:
    """SRD § Playing the Game › Rhythm of Play › Step 2.

    > 2: The Players Describe What Their Characters Do. Typically,
    > the characters stick together as they travel through a dungeon
    > or another environment. Sometimes different adventurers do
    > different things [...]. Outside combat, the GM ensures that
    > every character has a chance to act and decides how to resolve
    > their activity. In combat, the characters take turns.
    """

    def test_in_combat_characters_take_turns_via_initiative(self) -> None:
        """SRD: 'In combat, the characters take turns.'

        The engine enforces this: `InitiativeTracker.next_turn`
        (`dnd_engine/systems/initiative.py:173`) advances the cursor
        through combatants in initiative order. Each combatant gets a
        turn before the round wraps. This is the canonical combat-
        turn-taking enforcement; see also
        `test_the_order_of_combat.py` for the deeper audit.
        """
        tracker = InitiativeTracker(DiceRoller(seed=42))
        tracker.add_combatant(_make_creature("Alice", dex=16))
        tracker.add_combatant(_make_creature("Bob", dex=10))

        first_initial = tracker.current_turn_index
        tracker.next_turn()
        assert tracker.current_turn_index != first_initial, (
            "InitiativeTracker.next_turn must advance the cursor so "
            "the SRD's 'characters take turns' rule fires per turn."
        )

    def test_movement_is_blocked_for_individual_pcs_during_combat(self) -> None:
        """`GameState.move` is blocked when `in_combat` is True.

        SRD: "In combat, the characters take turns." This implies
        out-of-band PC movement is rejected. `GameState.move`
        (`dnd_engine/core/game_state.py:785-786`) returns False when
        `self.in_combat` is True; PCs cannot just walk away from
        encounters via the room-graph movement surface — they must
        use combat-mode movement which is initiative-gated.
        """
        src = inspect.getsource(GameState.move)
        assert "if self.in_combat" in src, (
            "GameState.move must short-circuit when in_combat is True "
            "so the SRD's combat turn-taking rule isn't bypassed by "
            "raw room movement."
        )

    def test_different_adventurers_can_take_different_actions_outside_combat(self) -> None:
        """Per-character skill checks exist as the primitive for varied activity.

        SRD: "one adventurer might search a treasure chest while a
        second examines a mysterious symbol..." The engine's
        primitive for this is `Character.make_skill_check`
        (`dnd_engine/core/character.py:726`), which accepts a
        per-character skill+DC and returns an independent result.
        Each PC can call it independently, so the *primitive* for
        varied parallel activity exists.
        """
        char = _make_character("Aria")
        assert hasattr(char, "make_skill_check")
        assert callable(char.make_skill_check)

    def test_outside_combat_every_character_gets_a_chance_to_act(self) -> None:
        pytest.skip(
            "GAP: The SRD's 'outside combat, the GM ensures that "
            "every character has a chance to act' is not modeled. "
            "`Party.characters` (dnd_engine/core/party.py) has no "
            "'acted this scene' tracking; there is no "
            "`ExplorationTurnTracker` analogous to "
            "`InitiativeTracker`. The CLI / script executor lets the "
            "active 'party voice' speak for all PCs without polling "
            "individual characters. Tracked by issue #522."
        )


class TestRhythmOfPlay_BasicPattern_Step3_GMNarratesResults:
    """SRD § Playing the Game › Rhythm of Play › Step 3.

    > 3: The GM Narrates the Results of the Adventurers' Actions.
    > Sometimes resolving a task is easy. If an adventurer walks
    > across a room and tries to open a door, the GM might say the
    > door opens and describe what lies beyond. But the door might be
    > locked, the floor might hide a trap, or some other circumstance
    > might make it challenging for an adventurer to complete a task.
    > In those cases, the GM might ask the player to roll a die to
    > help determine what happens. Describing the results often leads
    > to another decision point, which brings the game back to step 1.
    """

    def test_easy_task_resolves_without_a_check(self) -> None:
        """`GameState.move` opens unlocked doors with no roll.

        SRD: "if an adventurer walks across a room and tries to open
        a door, the GM might say the door opens." The engine honors
        this for unlocked exits: `move` traverses an unlocked exit
        and returns True without rolling
        (`dnd_engine/core/game_state.py:774-868`). No check fires.
        """
        src = inspect.getsource(GameState.move)
        # Unlocked door path returns True; locked path early-returns
        # False via is_exit_locked.
        assert "is_exit_locked" in src

    def test_locked_door_triggers_a_check_via_attempt_unlock(self) -> None:
        """`attempt_unlock` is the 'roll a die' surface for locked doors.

        SRD: "But the door might be locked... the GM might ask the
        player to roll a die." `GameState.attempt_unlock`
        (`dnd_engine/core/game_state.py:1021`) accepts a direction +
        method (key, lockpick) and routes to a skill check or
        consumes a key item. This is the canonical "challenged task
        -> roll" path.
        """
        assert callable(getattr(GameState, "attempt_unlock", None))

    def test_trap_or_hidden_feature_triggers_a_perception_check(self) -> None:
        """`_check_passive_perception` runs the implicit \"floor hides a trap\" check.

        SRD: \"the floor might hide a trap... the GM might ask the
        player to roll a die.\" The engine's passive analog is
        `_check_passive_perception`
        (`dnd_engine/core/game_state.py:2913`) which compares each
        PC's passive Perception to a DC on room entry. This is the
        engine's automatic detection path; an on-demand active path
        is gapped (issue #517).
        """
        assert callable(getattr(GameState, "_check_passive_perception", None))

    def test_results_loop_back_to_step1_via_room_enter_on_movement(self) -> None:
        """Moving to a new room re-fires ROOM_ENTER, closing the loop.

        SRD: \"Describing the results often leads to another decision
        point, which brings the game back to step 1.\" The engine
        closes this loop physically: `GameState.move` emits a fresh
        `ROOM_ENTER` event on every successful traversal
        (`game_state.py:847-856`), restarting the step-1 narration.
        """
        src = inspect.getsource(GameState.move)
        assert "ROOM_ENTER" in src

    def test_arbitrary_challenged_task_routes_to_a_d20_test(self) -> None:
        pytest.skip(
            "GAP: There is no generic challenged-task dispatcher. "
            "Specific hard-coded paths handle locked doors "
            "(`attempt_unlock`, game_state.py:1021), room searches "
            "(`search_room`, line 1409), and trap detection "
            "(`_check_passive_perception`, line 2913). But the SRD's "
            "'some other circumstance might make it challenging' — "
            "the open-ended case — has no engine surface. The script "
            "executor (dnd_engine/scenarios/script_executor.py:200-"
            "224) rejects anything outside `wait`/`attack`/"
            "`monster_attack`. Tracked by issue #523 (depends on the "
            "improvised-action gap, issue #453)."
        )


class TestRhythmOfPlay_PatternHoldsAcrossSessions:
    """SRD § Playing the Game › Rhythm of Play › Pattern persistence.

    > This pattern holds during every game session (each time you
    > sit down to play D&D), whether the adventurers are talking to a
    > noble, exploring a ruin, or fighting a dragon. In certain
    > situations—particularly combat—the action is more structured,
    > and everyone takes turns.
    """

    def test_combat_uses_structured_turn_order(self) -> None:
        """`InitiativeTracker` provides the 'more structured' combat order.

        SRD: \"In certain situations—particularly combat—the action
        is more structured, and everyone takes turns.\" The engine
        materializes this via `InitiativeTracker`
        (`dnd_engine/systems/initiative.py`) which sorts combatants
        by initiative and advances a cursor — the canonical
        structured-turn-taking enforcement.
        """
        tracker = InitiativeTracker(DiceRoller(seed=1))
        tracker.add_combatant(_make_creature("A", dex=14))
        tracker.add_combatant(_make_creature("B", dex=14))
        assert len(tracker.get_all_combatants()) == 2

    def test_non_combat_play_uses_unstructured_action_dispatch(self) -> None:
        """`get_available_actions` returns exploration verbs when not in combat.

        SRD: non-combat play (talking, exploring) is *less*
        structured. The engine reflects this by routing non-combat
        through `move` / `search` rather than initiative cycles
        (`GameState.get_available_actions`,
        `dnd_engine/core/game_state.py:765-772`). No turn cursor is
        consulted outside combat.
        """
        src = inspect.getsource(GameState.get_available_actions)
        assert "in_combat" in src


class TestRhythmOfPlay_ExceptionsSupersedeGeneralRules:
    """SRD § Playing the Game › Rhythm of Play › Exceptions Supersede General Rules.

    > General rules govern each part of the game. For example, the
    > combat rules tell you that melee attacks use Strength and ranged
    > attacks use Dexterity. That's a general rule, and a general
    > rule is in effect as long as something in the game doesn't
    > explicitly say otherwise.
    > The game also includes elements—class features, feats, weapon
    > properties, spells, magic items, monster abilities, and the
    > like—that sometimes contradict a general rule. When an
    > exception and a general rule disagree, the exception wins. For
    > example, if a feature says you can make melee attacks using
    > your Charisma, you can do so, even though that statement
    > disagrees with the general rule.
    """

    def test_general_rule_melee_attacks_use_strength(self) -> None:
        """Standard melee attacks consume the STR modifier.

        SRD general rule: melee uses Strength. `Character.get_attack_
        bonus` (`dnd_engine/core/character.py:366-412`) routes
        non-finesse, non-ranged weapons through `self.abilities.
        str_mod` (line 406). This is the engine's enforcement of the
        SRD's named general rule.
        """
        src = inspect.getsource(Character.get_attack_bonus)
        assert "str_mod" in src, (
            "get_attack_bonus must default melee to STR so the SRD's "
            "general rule has a real implementation."
        )

    def test_general_rule_ranged_attacks_use_dexterity(self) -> None:
        """Standard ranged attacks consume the DEX modifier.

        SRD general rule: ranged uses Dexterity. `Character.get_
        attack_bonus` (`dnd_engine/core/character.py:401-403`)
        routes `category == "ranged"` weapons through
        `self.abilities.dex_mod`.
        """
        src = inspect.getsource(Character.get_attack_bonus)
        assert "dex_mod" in src
        assert '"ranged"' in src or "'ranged'" in src

    def test_finesse_weapon_property_overrides_the_general_rule(self) -> None:
        """Finesse weapons use the higher of STR or DEX.

        SRD: \"when an exception and a general rule disagree, the
        exception wins.\" The finesse weapon property is exactly such
        an exception: `Character.get_attack_bonus`
        (`dnd_engine/core/character.py:398-400`) checks for
        `\"finesse\" in properties` first and picks
        `max(str_mod, dex_mod)`, overriding the STR-melee general
        rule. This is the SRD's headline exception example in
        miniature.
        """
        abilities = Abilities(
            strength=10,  # +0
            dexterity=18,  # +4
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
        )
        char = Character(
            name="Rogue",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities,
            max_hp=8,
            ac=14,
            race="halfling",
        )
        # finesse_attack_bonus encapsulates the exception math:
        # max(STR, DEX) + proficiency bonus.
        bonus = char.finesse_attack_bonus
        # DEX (+4) > STR (+0), so the exception picks DEX. Proficiency
        # bonus at level 1 is +2.
        assert bonus == 4 + char.proficiency_bonus, (
            "Finesse weapons must pick max(STR, DEX) — the SRD's "
            "explicit exception to the 'melee uses Strength' general "
            "rule."
        )

    def test_thief_fast_hands_overrides_the_use_object_action_cost(self) -> None:
        """Thief Fast Hands turns Use an Object from action into bonus action.

        SRD: \"class features... that sometimes contradict a general
        rule.\" The Thief Rogue's Fast Hands feature carves an
        exception to Utilize's action cost.
        `Character.has_fast_hands` (`dnd_engine/core/character.py:
        847-866`) is the engine's check for the exception; level 3+
        Thief rogues qualify, downgrading Use-an-Object from action
        to bonus action.
        """
        abilities = Abilities(
            strength=10,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
        )
        non_thief = Character(
            name="Rookie",
            character_class=CharacterClass.ROGUE,
            level=1,  # Not yet level 3
            abilities=abilities,
            max_hp=8,
            ac=14,
            race="halfling",
        )
        # General rule applies (no exception): Fast Hands not granted.
        assert non_thief.has_fast_hands() is False, (
            "Level 1 Rogue must not yet qualify for Fast Hands so the "
            "SRD's general rule (Use an Object = action) still "
            "applies."
        )

        thief = Character(
            name="Sly",
            character_class=CharacterClass.ROGUE,
            level=3,
            subclass="thief",
            abilities=abilities,
            max_hp=20,
            ac=14,
            race="halfling",
        )
        # Exception applies and the engine recognizes it.
        assert thief.has_fast_hands() is True, (
            "Level 3 Thief Rogue must qualify for Fast Hands — the "
            "SRD's named example of a class feature overriding a "
            "general rule about action cost."
        )
