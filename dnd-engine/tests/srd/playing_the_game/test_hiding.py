# ABOUTME: SRD conformance audit for "Playing the Game > Hiding".
# ABOUTME: Cross-references docs/srd/playing-the-game/hiding.md against engine code.

"""SRD conformance: Hiding.

Maps every rule in `docs/srd/playing-the-game/hiding.md` to a test.
Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The Hiding section is short (6 lines of source), but it carries three
discrete rules: hiding exists as a recognized activity (intro framing),
the GM gates when hiding is allowed (GM discretion), and the
mechanical entry point is the Hide action.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import inspect

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.systems.action_economy import ActionType
from dnd_engine.systems.initiative import InitiativeTracker
from dnd_engine.systems.perception import VisibilityRelation

pytestmark = pytest.mark.srd(
    "playing-the-game/hiding.md",
    lines="1579-1584",
)


def _make_stealthy_character() -> Character:
    """Rogue-like character with proficiency in Stealth."""
    abilities = Abilities(
        strength=10,
        dexterity=16,  # +3 mod for Stealth
        constitution=10,
        intelligence=10,
        wisdom=10,
        charisma=10,
    )
    char = Character(
        name="Sneak",
        character_class=CharacterClass.ROGUE,
        level=1,
        abilities=abilities,
        max_hp=8,
        ac=14,
        race="halfling",
        skill_proficiencies=["stealth"],
    )
    return char


def _unmissable_hider() -> Character:
    """A hider whose Stealth check clears the DC-10 baseline on any roll.

    DEX 20 (+5) plus Stealth expertise (proficiency 2 doubled = +4) gives
    a +9 modifier, so even a natural 1 totals 10 — guaranteeing success
    against the no-enemies baseline DC of 10. Used to exercise the
    success branch deterministically.
    """
    char = _make_stealthy_character()
    char.abilities = Abilities(
        strength=10, dexterity=20, constitution=10, intelligence=10, wisdom=10, charisma=10
    )
    char.expertise_skills = ["stealth"]
    return char


def _dummy_enemy(name: str = "Zombie") -> Creature:
    return Creature(
        name=name, max_hp=22, ac=8, abilities=Abilities(13, 6, 16, 3, 6, 5)
    )


def _combat_state(char: Character, *, concealing: bool = True) -> GameState:
    """A crypt-room GameState in combat with ``char`` as the current turn.

    When ``concealing`` the room is made Heavily Obscured (heavy fog) so
    the SRD 5.2.1 hide gate is satisfied; otherwise it's an open, brightly
    lit room where hiding isn't permitted (used by tests that set the
    Hidden condition directly to probe the unseen-attacker rules).
    """
    party = Party([char])
    gs = GameState(party, "crypt", campaign_id="the_unquiet_dead")
    gs.current_room_id = "crypt.hall_of_the_dead"
    room = gs.get_current_room()
    room["lighting"] = "bright"
    room["obscurement_sources"] = ["heavy_fog"] if concealing else []
    room["cover"] = "none"
    gs.in_combat = True
    gs.initiative_tracker = InitiativeTracker(gs.dice_roller, gs.time_manager)
    gs.initiative_tracker.add_combatant(char)
    return gs


class TestHiding_Intro:
    """SRD § Playing the Game › Hiding › Intro.

    > Adventurers and monsters often hide, whether to spy on one
    > another, sneak past a guardian, or set an ambush.
    """

    def test_stealth_skill_exists_as_recognized_activity(self):
        """`stealth` is in the skill catalog as a DEX skill.

        The SRD framing of "hiding" as a recognized adventuring
        activity is reflected by the catalog presence of the Stealth
        skill in `dnd-engine/dnd_engine/data/srd/skills.json` and the
        ability check primitive on Character. Without this, no
        downstream Hide rule could land.
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
        assert "stealth" in skills, (
            "Stealth skill must be catalogued so the SRD's 'often "
            "hide' framing has a concrete check primitive."
        )
        assert skills["stealth"]["ability"] == "dex"

    def test_stealth_check_primitive_is_callable_on_a_character(self):
        """`Character.make_skill_check('stealth', ...)` is the primitive.

        The SRD's "hide" framing presumes a Stealth check exists. The
        engine wires this through `Character.make_skill_check`
        (`dnd-engine/dnd_engine/core/character.py:697`), which is
        already used for surprise rounds in
        `GameState._check_for_surprise`
        (`dnd-engine/dnd_engine/core/game_state.py:3050`). This is the
        primitive a Hide action would consume.
        """
        char = _make_stealthy_character()
        assert hasattr(char, "make_skill_check")
        assert callable(char.make_skill_check)

    def test_engine_uses_stealth_check_for_pre_combat_surprise(self):
        """`_check_for_surprise` makes a Stealth check vs. enemy passive Perception.

        The SRD lists "set an ambush" as a hiding motive. The engine
        does fire a Stealth check in exactly that scenario:
        `GameState._check_for_surprise`
        (`dnd-engine/dnd_engine/core/game_state.py:3014-3083`) runs a
        group Stealth check vs the highest enemy passive Perception
        before combat starts. Source-level guard so this connection
        from the SRD's "ambush" framing to the engine's surprise
        mechanic can't silently regress.
        """
        src = inspect.getsource(GameState._check_for_surprise)
        assert '"stealth"' in src or "'stealth'" in src, (
            "Pre-combat surprise must invoke a Stealth check so the "
            "SRD's 'set an ambush' hiding motive has a real "
            "implementation."
        )
        assert "passive_perception" in src.lower() or "passive perception" in src.lower(), (
            "The Stealth check must be contested against passive "
            "Perception, matching the SRD's surprise / hide model."
        )


class TestHiding_GMDiscretion:
    """SRD § Playing the Game › Hiding › GM discretion.

    > The Game Master decides when circumstances are appropriate for
    > hiding.
    """

    def test_engine_gates_hide_attempts_on_appropriate_circumstances(self):
        """The engine consults the environment before allowing a hide.

        SRD 5.2.1 makes hiding available only when the surroundings
        offer concealment: a creature can attempt to hide when its area
        is **Heavily Obscured** OR it has at least **three-quarters
        cover**. Lighter conditions (Lightly Obscured, half cover, or a
        clear open space) do not qualify — this is stricter than
        plan-05's looser "Lightly Obscured" draft, and the SRD threshold
        is canonical (issue #496).

        Two layers are gated:

        - The pure rule `perception.can_attempt_hide(obscurement, cover)`
          decides eligibility from an area's obscurement and cover.
        - `GameState.can_attempt_hide(creature)` resolves the current
          room's effective obscurement (lighting + ambient sources) and
          its cover signal, then delegates to the rule.
        """
        from dnd_engine.systems.perception import (
            Cover,
            Obscurement,
            can_attempt_hide,
        )

        # --- Pure rule: obscurement gate at the SRD threshold ---
        # Heavily Obscured qualifies; nothing lighter does.
        assert can_attempt_hide(Obscurement.HEAVILY, Cover.NONE) is True
        assert can_attempt_hide(Obscurement.LIGHTLY, Cover.NONE) is False
        assert can_attempt_hide(Obscurement.CLEAR, Cover.NONE) is False

        # --- Pure rule: cover gate at the SRD threshold ---
        # Three-quarters and total cover qualify; half cover does not.
        assert can_attempt_hide(Obscurement.CLEAR, Cover.THREE_QUARTERS) is True
        assert can_attempt_hide(Obscurement.CLEAR, Cover.TOTAL) is True
        assert can_attempt_hide(Obscurement.CLEAR, Cover.HALF) is False

        # --- GameState integration: room data drives the gate ---
        char = _make_stealthy_character()
        party = Party([char])
        game_state = GameState(party, "crypt", campaign_id="the_unquiet_dead")
        game_state.current_room_id = "crypt.hall_of_the_dead"
        room = game_state.get_current_room()

        # A heavily fogged room qualifies even in Bright Light: the area
        # is Heavily Obscured regardless of illumination.
        room["lighting"] = "bright"
        room["obscurement_sources"] = ["heavy_fog"]
        room["cover"] = "none"
        assert game_state.can_attempt_hide(char) is True

        # A clear, brightly lit room with no cover does not qualify.
        room["obscurement_sources"] = []
        room["cover"] = "none"
        assert game_state.can_attempt_hide(char) is False

        # Three-quarters cover qualifies even in a clear, bright room.
        room["cover"] = "three_quarters"
        assert game_state.can_attempt_hide(char) is True

    def test_party_cannot_hide_in_an_open_brightly_lit_empty_room(self):
        """Hiding is unavailable in an open, brightly lit, featureless room.

        The SRD's GM-discretion clause means a creature standing in the
        open with full illumination and nothing to hide behind cannot
        attempt the Hide action: the area is not obscured and offers no
        cover. `GameState.can_attempt_hide` must refuse here (issue
        #496).
        """
        char = _make_stealthy_character()
        party = Party([char])
        game_state = GameState(party, "crypt", campaign_id="the_unquiet_dead")
        game_state.current_room_id = "crypt.hall_of_the_dead"
        room = game_state.get_current_room()
        room["lighting"] = "bright"
        room["obscurement_sources"] = []
        room["cover"] = "none"

        assert game_state.can_attempt_hide(char) is False

    def test_shipped_dungeon_room_carries_the_obscurement_hide_signal(self):
        """Shipped content exercises the hide gate from room data.

        The acceptance criterion for issue #496 requires room data to
        carry the obscurement / cover signal that drives the gate. The
        Poisoned Laboratory's steam-choked boiler room declares
        `obscurement_sources: ["heavy_fog"]`, making it Heavily Obscured,
        so a creature there can attempt to hide — while the adjacent
        open furnace room cannot. This guards the data wiring so the
        signal can't silently disappear from the dungeon.
        """
        char = _make_stealthy_character()
        party = Party([char])
        game_state = GameState(
            party, "laboratory", campaign_id="poisoned_laboratory"
        )

        game_state.current_room_id = "laboratory.boiler_room"
        assert game_state.can_attempt_hide(char) is True

        game_state.current_room_id = "laboratory.furnace_room"
        assert game_state.can_attempt_hide(char) is False


class TestHiding_HideAction:
    """SRD § Playing the Game › Hiding › Hide action entry.

    > When you try to hide, you take the Hide action.
    """

    def test_hide_action_is_dispatchable_as_a_playable_action(self):
        """Hide is surfaced as a combat action when the room permits it.

        `GameState.get_available_actions` lists "hide" during combat
        only when the current combatant's surroundings satisfy the SRD
        5.2.1 gate, making it a real, player-selectable action (issue
        #443). In an open, brightly lit room it is not offered.
        """
        char = _make_stealthy_character()
        gs = _combat_state(char)
        assert "hide" in gs.get_available_actions()

        # Remove the concealment: the action is no longer offered.
        gs.get_current_room()["obscurement_sources"] = []
        assert "hide" not in gs.get_available_actions()

    def test_hide_action_makes_a_dexterity_stealth_check(self):
        """`GameState.attempt_hide` rolls a Dexterity (Stealth) check.

        SRD § Actions › Hide: "Make a Dexterity (Stealth) check." The
        attempt surfaces the rolled check (skill ``stealth``, ability
        ``dex``) contested against a DC drawn from enemy passive
        Perception.
        """
        char = _make_stealthy_character()
        gs = _combat_state(char)

        result = gs.attempt_hide(char)

        assert result.attempted is True
        assert result.check_result is not None
        assert result.check_result["skill"] == "stealth"
        assert result.check_result["ability"] == "dex"
        assert result.dc is not None

    def test_hide_action_consumes_the_turn_action_slot(self):
        """Taking the Hide action spends the turn's Action slot."""
        char = _make_stealthy_character()
        gs = _combat_state(char)
        turn_state = gs.initiative_tracker.get_current_turn_state()
        assert turn_state.action_available is True

        result = gs.attempt_hide(char)

        assert result.action_consumed == ActionType.ACTION
        assert turn_state.action_available is False

    def test_successful_hide_sets_unseen_state_on_the_hider(self):
        """A successful Hide gives the hider the Hidden (unseen) condition.

        The Hidden condition is what the unseen-attacker/target rules
        consume (issue #475); ``compute_visibility`` already treats a
        Hidden target as ``UNSEEN``.
        """
        char = _unmissable_hider()
        gs = _combat_state(char)

        result = gs.attempt_hide(char)

        assert result.success is True
        assert char.has_condition("hidden") is True

    def test_attacks_against_unseen_attacker_or_target_apply_visibility_advantage(self):
        """A Hidden creature is unseen for the attack-roll rules.

        SRD § Combat › Unseen Attackers and Targets: an attacker the
        target can't see has Advantage; a target the attacker can't see
        is attacked with Disadvantage. With the hider in a clear, lit
        room (so only the Hidden condition — not ambient fog — drives
        visibility), the relations resolve exactly that way.
        """
        char = _make_stealthy_character()
        gs = _combat_state(char, concealing=False)
        enemy = _dummy_enemy()
        gs.active_enemies = [enemy]
        char.add_condition("hidden")

        # Enemy attacks the hidden hider → target unseen → Disadvantage.
        attacker_sees, defender_sees = gs.attack_visibility(enemy, char)
        assert attacker_sees == VisibilityRelation.UNSEEN
        incoming = gs.combat_engine.resolve_attack(
            attacker=enemy,
            defender=char,
            attack_bonus=3,
            damage_dice="1d6",
            attacker_sees_defender=attacker_sees,
            defender_sees_attacker=defender_sees,
            game_state=gs,
        )
        assert incoming.disadvantage is True
        assert incoming.advantage is False

        # Hidden hider attacks the enemy → attacker unseen → Advantage.
        char.add_condition("hidden")  # re-hide (the prior attack didn't reveal char)
        saw_defender, saw_attacker = gs.attack_visibility(char, enemy)
        assert saw_attacker == VisibilityRelation.UNSEEN
        outgoing = gs.combat_engine.resolve_attack(
            attacker=char,
            defender=enemy,
            attack_bonus=4,
            damage_dice="1d6",
            attacker_sees_defender=saw_defender,
            defender_sees_attacker=saw_attacker,
            game_state=gs,
        )
        assert outgoing.advantage is True

    def test_hidden_attacker_reveals_location_on_attack(self):
        """A Hidden creature reveals itself the moment it attacks.

        SRD § Hide: making an attack roll ends the hidden state. The
        hider keeps its one advantaged shot (the relation was captured
        before the roll), then is no longer Hidden.
        """
        char = _make_stealthy_character()
        gs = _combat_state(char, concealing=False)
        enemy = _dummy_enemy()
        gs.active_enemies = [enemy]
        char.add_condition("hidden")
        assert char.has_condition("hidden") is True

        saw_defender, saw_attacker = gs.attack_visibility(char, enemy)
        gs.combat_engine.resolve_attack(
            attacker=char,
            defender=enemy,
            attack_bonus=4,
            damage_dice="1d6",
            attacker_sees_defender=saw_defender,
            defender_sees_attacker=saw_attacker,
            game_state=gs,
        )

        assert char.has_condition("hidden") is False
