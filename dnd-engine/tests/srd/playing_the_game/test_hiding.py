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
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party

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
        pytest.skip(
            "GAP: there is no playable Hide action. The script "
            "executor's action dispatcher "
            "(`dnd-engine/dnd_engine/scenarios/script_executor.py:200-"
            "224`) only accepts 'wait', 'attack', and 'monster_attack' "
            "— `hide` is not a recognized action. The combat-mode "
            "available-actions list (`dnd-engine/dnd_engine/core/"
            "game_state.py:766`) is `['attack', 'use_item']` — no "
            "'hide'. The string 'Hide' appears only as flavor text in "
            "the rogue Cunning Action description "
            "(`dnd-engine/dnd_engine/data/srd/classes.json`) and in "
            "the spy monster's Nimble Escape "
            "(`dnd-engine/dnd_engine/data/srd/monsters.json`). "
            "Tracked by issue #443."
        )

    def test_hide_action_makes_a_dexterity_stealth_check(self):
        pytest.skip(
            "GAP: same as above — there is no Hide action handler, so "
            "no dispatcher invokes `make_skill_check('stealth', ...)` "
            "on demand. The check primitive exists "
            "(`dnd-engine/dnd_engine/core/character.py:697-738`) but "
            "is currently only fired by the surprise-round path, not "
            "by a player-initiated Hide. Tracked by issue #443."
        )

    def test_hide_action_consumes_the_turn_action_slot(self):
        pytest.skip(
            "GAP: the Hide action should consume `ActionType.ACTION` "
            "(or `BONUS_ACTION` via rogue Cunning Action / monster "
            "Nimble Escape). Action economy is modeled — `TurnState` "
            "in `dnd-engine/dnd_engine/systems/action_economy.py:26-"
            "40` carries the slot — but no Hide handler consumes it. "
            "Tracked by issue #443."
        )

    def test_successful_hide_sets_unseen_state_on_the_hider(self):
        pytest.skip(
            "GAP: the SRD's Hide action produces an *unseen* state "
            "(consumed by attack-roll rules — issue #475). No `hidden` "
            "/ `unseen` / `is_hidden` flag exists on Creature or "
            "Character in `dnd-engine/dnd_engine/core/creature.py` or "
            "`character.py`. The `active_conditions` dict on Creature "
            "could carry it, but no code writes 'hidden' there. "
            "Tracked by issue #443."
        )

    def test_attacks_against_unseen_attacker_or_target_apply_visibility_advantage(self):
        pytest.skip(
            "GAP: even if the Hide action set an unseen flag, the "
            "attack pipeline would not consume it. `CombatEngine."
            "resolve_attack` (`dnd-engine/dnd_engine/core/combat.py:"
            "91`) accepts `advantage` / `disadvantage` flags but no "
            "caller derives them from attacker/target visibility "
            "state. The Blinded condition is similarly unconsumed by "
            "attack rolls (only the close-combat ranged helper "
            "`dnd_engine/systems/ranged_attacks.py:71` reads it). "
            "Tracked by issue #475 (which is the *consumer* of the "
            "hidden state from #443)."
        )

    def test_hidden_attacker_reveals_location_on_attack(self):
        pytest.skip(
            "GAP: the SRD says a hidden creature reveals its location "
            "when it makes an attack roll. Today there is no hidden "
            "state to reveal (issue #443) and no post-attack reveal "
            "hook in `resolve_attack` (`dnd-engine/dnd_engine/core/"
            "combat.py:91`). Tracked by issue #475."
        )
