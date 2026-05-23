# ABOUTME: SRD conformance audit for "Playing the Game > Social Interaction".
# ABOUTME: Cross-references docs/srd/playing-the-game/social-interaction.md against engine code.

"""SRD conformance: Social Interaction.

Maps every rule in `docs/srd/playing-the-game/social-interaction.md` to
a test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The Social Interaction section carries four logical rule clusters:

  1. Social interaction framing — many situations would rather talk
     than fight; GM portrays NPCs.
  2. NPC attitude axis — Friendly / Indifferent / Hostile.
  3. Roleplaying — non-mechanical, but the engine must not prevent
     it; brief utterances are free (carve-out shared with the Order of
     Combat audit's `NO_ACTION` slot).
  4. Ability Checks — the Influence action routes a Charisma
     (Deception / Intimidation / Performance / Persuasion) or Wisdom
     (Animal Handling) check at an NPC.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.npc import NPC, NPCDisposition
from dnd_engine.systems.action_economy import ActionType, TurnState

pytestmark = pytest.mark.srd(
    "playing-the-game/social-interaction.md",
    lines="1452-1510",
)


SKILLS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "skills.json"
)


def _make_charismatic_character() -> Character:
    """Bard-like character with CHA 16 and Persuasion / Deception proficiency."""
    abilities = Abilities(
        strength=10,
        dexterity=10,
        constitution=10,
        intelligence=10,
        wisdom=10,
        charisma=16,  # +3 mod
    )
    return Character(
        name="Smooth",
        character_class=CharacterClass.ROGUE,  # rogue can pick CHA skills
        level=1,
        abilities=abilities,
        max_hp=8,
        ac=12,
        race="halfling",
        skill_proficiencies=["persuasion", "deception", "intimidation"],
    )


def _make_minimal_npc(disposition: str = "neutral") -> NPC:
    """Build a minimal NPC for attitude tests."""
    return NPC.from_dict(
        {
            "id": "npc_test",
            "name": "Test NPC",
            "display_name": "Test",
            "home_location": "room_1",
            "current_location": "room_1",
            "can_move": False,
            "personality": {
                "traits": ["test"],
                "speech_style": "plain",
                "attitude_default": disposition,
            },
            "knowledge": {},
            "dialogue": {"greeting": "Hello"},
        }
    )


class TestSocialInteraction_Intro:
    """SRD § Playing the Game › Social Interaction › Intro.

    > During their adventures, player characters meet many different
    > people and face some monsters that would rather talk than fight.
    > In those situations, it's time for social interaction, which
    > takes many forms. ... The Game Master assumes the roles of any
    > nonplayer characters who are participating.
    """

    def test_npc_class_exists_as_a_first_class_engine_entity(self) -> None:
        """`NPC` (`dnd_engine/core/npc.py`) is the engine's NPC model.

        The SRD's "many different people and face some monsters that
        would rather talk than fight" framing is honored at the data
        layer by a dedicated `NPC` class with personality, knowledge,
        shop, and dialogue fields. Without it, there would be no
        engine-side place for the SRD's social-interaction rules to
        land at all.
        """
        npc = _make_minimal_npc()
        assert isinstance(npc, NPC)
        assert npc.name == "Test NPC"
        assert npc.personality is not None
        assert npc.dialogue is not None

    def test_engine_routes_npc_dialogue_through_npc_chat_manager(self) -> None:
        """`NPCChatManager` is the engine's NPC-conversation surface.

        The SRD's "GM assumes the roles of any nonplayer characters" is
        modeled by `NPCChatManager` (`dnd_engine/llm/npc_chat.py:191`)
        which proxies a player message to the configured LLM provider
        under the NPC's system prompt. This is the SRD's GM-portrayal
        delegate.
        """
        from dnd_engine.llm.npc_chat import NPCChatManager

        assert NPCChatManager is not None
        # System prompts are built per NPC via `NPC.build_system_prompt`
        # (`npc.py:198`) — this is the GM-portrayal pipeline.
        npc = _make_minimal_npc()
        prompt = npc.build_system_prompt()
        assert npc.display_name in prompt
        assert "PERSONALITY" in prompt


class TestSocialInteraction_NPCAttitude:
    """SRD § Playing the Game › Social Interaction › NPC Attitude.

    > An NPC's attitude toward your character is Friendly, Indifferent,
    > or Hostile, as defined in "Rules Glossary." Friendly NPCs are
    > predisposed to help, and Hostile ones are inclined to hinder.
    """

    def test_npc_disposition_enum_includes_friendly_and_hostile(self) -> None:
        """`NPCDisposition` covers Friendly and Hostile.

        Both axis poles the SRD names are present in the enum
        (`dnd_engine/core/npc.py:9-16`). Friendly and Hostile are the
        primary axis the SRD's downstream Influence rules consult.
        """
        names = {m.name for m in NPCDisposition}
        assert "FRIENDLY" in names
        assert "HOSTILE" in names

    def test_npc_disposition_enum_is_richer_than_srd_3_axis(self) -> None:
        """Engine enum is 5-axis (HOSTILE/UNFRIENDLY/NEUTRAL/FRIENDLY/ALLIED).

        Source-level guard: the engine carries an older D&D 5-axis
        attitude scale (`npc.py:9-16`). 2024 SRD reduces this to three
        axes (Friendly / Indifferent / Hostile), so an Influence
        implementation will need to either (a) map NEUTRAL ->
        Indifferent and collapse UNFRIENDLY into HOSTILE for SRD
        Influence DCs, or (b) introduce an explicit Indifferent member
        and migrate data. This test pins the current shape so the
        Influence implementation issue (#444) has a clear delta.
        """
        names = {m.name for m in NPCDisposition}
        assert names == {"HOSTILE", "UNFRIENDLY", "NEUTRAL", "FRIENDLY", "ALLIED"}, (
            "NPCDisposition members changed — update the SRD-mapping "
            "delta in this guard (Friendly / Indifferent / Hostile)."
        )

    def test_indifferent_is_not_a_member_of_npc_disposition_today(self) -> None:
        pytest.skip(
            "GAP: SRD 2024 'Indifferent' is not modeled. The engine "
            "uses 'NEUTRAL' instead "
            "(`dnd_engine/core/npc.py:9-16`), which is semantically "
            "close but uses different vocabulary. The Influence "
            "action and the Rules Glossary cross-references for "
            "Indifferent / Friendly / Hostile will need a vocabulary "
            "alignment. Tracked by issue #444 (Influence action) and "
            "issue #527 (this audit)."
        )

    def test_npc_has_a_get_disposition_method(self) -> None:
        """`NPC.get_disposition()` is the engine's attitude query.

        The SRD makes downstream rules conditional on attitude (e.g.,
        Disadvantage on an Influence check vs a Hostile NPC, per the
        Rules Glossary 'Hostile' entry). `NPC.get_disposition`
        (`npc.py:184-196`) returns a `NPCDisposition` derived from
        `player_reputation` and the NPC's per-NPC thresholds. This is
        the query an Influence handler would consult.
        """
        npc = _make_minimal_npc()
        assert hasattr(npc, "get_disposition")
        assert callable(npc.get_disposition)
        # Default with no reputation_modifiers -> NEUTRAL.
        assert npc.get_disposition() == NPCDisposition.NEUTRAL

    def test_friendly_npc_threshold_is_consulted(self) -> None:
        """Reputation crossing the friendly threshold flips disposition.

        `NPC.get_disposition` (`npc.py:184-196`) reads
        `reputation_modifiers.friendly_threshold` and returns FRIENDLY
        when `player_reputation` meets or exceeds it. This is the
        engine's stand-in for "Friendly NPCs are predisposed to help"
        — the predisposition is encoded as a reputation gate.
        """
        npc = _make_minimal_npc()
        npc.reputation_modifiers = {"friendly_threshold": 3, "hostile_threshold": -3}
        npc.player_reputation = 5
        assert npc.get_disposition() == NPCDisposition.FRIENDLY

    def test_hostile_npc_threshold_is_consulted(self) -> None:
        """Reputation crossing the hostile threshold flips disposition.

        Symmetric to the friendly test above. SRD: "Hostile ones are
        inclined to hinder." The engine encodes hindering via a
        per-NPC hostile_greeting path
        (`NPC.get_greeting` -> `'hostile_greeting'`, `npc.py:300-305`)
        and via shop refusal in `poisoned_laboratory/npcs.json`
        ('hostile': {'refuses_service': true}).
        """
        npc = _make_minimal_npc()
        npc.reputation_modifiers = {"friendly_threshold": 3, "hostile_threshold": -3}
        npc.player_reputation = -10
        assert npc.get_disposition() == NPCDisposition.HOSTILE

    def test_npc_attitude_is_used_to_modify_influence_check_outcome(self) -> None:
        pytest.skip(
            "GAP: there is no Influence handler that consults NPC "
            "disposition. The Rules Glossary 'Hostile' entry "
            "(`docs/srd/rules-glossary/rules-glossary.md:1152-1155`) "
            "says: 'You have Disadvantage on an ability check to "
            "influence a Hostile creature' — but no engine path "
            "routes `Character.make_skill_check('persuasion', ..., "
            "disadvantage=True)` for the Hostile case. See the "
            "actions audit "
            "(`tests/srd/playing_the_game/test_actions.py::"
            "TestAction_Influence`). Tracked by issue #444."
        )


class TestSocialInteraction_TwoProgressionAxes:
    """SRD § Playing the Game › Social Interaction › Progression.

    > Social interactions progress in two ways: through roleplaying and
    > ability checks.
    """

    def test_both_progression_axes_have_engine_surfaces(self) -> None:
        """The two SRD axes both have engine-side stubs.

        - Roleplaying axis: `NPCChatManager.send_message_sync`
          (`dnd_engine/llm/npc_chat.py:388`) lets a player exchange
          freeform text with an NPC — the engine's roleplaying surface.
        - Ability-checks axis: `Character.make_skill_check`
          (`dnd_engine/core/character.py:726`) is the primitive that
          an Influence handler would invoke against CHA-skill checks.

        Both axes exist as primitives, but only the roleplaying axis
        is wired up end-to-end; the ability-check axis lacks a
        dispatcher (the Influence action — issue #444).
        """
        from dnd_engine.llm.npc_chat import NPCChatManager

        # Roleplaying axis: send_message_sync is the conversation step.
        assert hasattr(NPCChatManager, "send_message_sync")
        assert callable(NPCChatManager.send_message_sync)

        # Ability-checks axis: make_skill_check is the check primitive.
        char = _make_charismatic_character()
        assert hasattr(char, "make_skill_check")
        assert callable(char.make_skill_check)


class TestSocialInteraction_Roleplaying:
    """SRD § Playing the Game › Social Interaction › Roleplaying.

    > Roleplaying is, literally, the act of playing out a role. ... The
    > GM uses an NPC's personality and your character's actions and
    > attitudes to determine how an NPC reacts.
    """

    def test_npc_personality_is_modeled_and_fed_to_the_gm_proxy(self) -> None:
        """`NPCPersonality` is the SRD's 'personality' axis.

        The SRD calls out NPC personality as the GM's input for
        NPC reactions. `NPCPersonality` (`npc.py:62-88`) carries
        traits, speech_style, attitude_default, and
        suspicion_of_strangers, and these are baked into the system
        prompt by `NPC.build_system_prompt` (`npc.py:198`). This is
        the GM-proxy's reaction input.
        """
        npc = _make_minimal_npc()
        prompt = npc.build_system_prompt()
        assert "PERSONALITY" in prompt
        assert "SPEECH STYLE" in prompt
        assert "DEFAULT ATTITUDE" in prompt

    def test_brief_utterances_are_free_via_no_action_slot(self) -> None:
        """`ActionType.NO_ACTION` covers the SRD's free-form chatter.

        Cross-cut from the Order of Combat audit
        (`test_the_order_of_combat.py::TestYourTurn_Communicating`):
        brief utterances cost nothing on a creature's turn. The same
        carve-out applies during social interaction outside combat;
        nothing in the engine prevents free dialogue.
        """
        state = TurnState(movement_remaining=30)
        # Free chatter consumes no slot.
        assert state.consume_action(ActionType.NO_ACTION) is True
        # Action and bonus action remain available.
        assert state.action_available is True
        assert state.bonus_action_available is True

    def test_npc_reaction_uses_player_action_history_or_attitudes(self) -> None:
        pytest.skip(
            "GAP: the SRD calls out 'your character's actions and "
            "attitudes' as inputs to the NPC's reaction. Today, "
            "`NPC.get_disposition` "
            "(`dnd_engine/core/npc.py:184-196`) consults only "
            "`player_reputation` — a single signed integer that is "
            "manipulated externally. There is no model of *which* "
            "player actions moved reputation, nor of the character's "
            "stated attitudes (e.g., gruff vs courteous tone in "
            "dialogue history). The LLM system prompt is given a "
            "conversation history "
            "(`conversation_history`, `npc.py:146`) but no structured "
            "'last 3 player actions' summary is constructed for the "
            "GM-proxy. Tracked by issue #527."
        )


class TestSocialInteraction_AbilityChecks:
    """SRD § Playing the Game › Social Interaction › Ability Checks.

    > Ability checks can be key in determining the outcome of a social
    > interaction. ... In such situations, the GM will typically ask
    > you to take the Influence action.
    """

    def test_charisma_skill_primitives_exist_for_all_influence_skills(self) -> None:
        """CHA / WIS skills the Influence action consumes are catalogued.

        Data-parity check (mirror of
        `test_actions.py::TestAction_Influence::
        test_influence_skill_catalog_covers_srd_options`): the five
        Influence-eligible skills the SRD names — Deception,
        Intimidation, Performance, Persuasion (all CHA), and
        Animal Handling (WIS) — are all present in `skills.json` with
        the correct backing ability. The SRD's Influence Checks table
        (Rules Glossary, line 1253) maps interaction kind to skill.
        """
        skills = json.loads(SKILLS_JSON.read_text())
        assert skills["deception"]["ability"] == "cha"
        assert skills["intimidation"]["ability"] == "cha"
        assert skills["performance"]["ability"] == "cha"
        assert skills["persuasion"]["ability"] == "cha"
        assert skills["animal_handling"]["ability"] == "wis"

    def test_make_skill_check_runs_a_d20_plus_skill_modifier(self) -> None:
        """`Character.make_skill_check` is the d20+modifier primitive.

        The SRD's "ability check" core primitive is implemented at
        `dnd_engine/core/character.py:726-779`: rolls 1d20 with
        optional advantage/disadvantage, adds the skill's modifier
        (proficiency-aware), compares vs DC, and returns a structured
        result dict. This is the slot an Influence handler would
        invoke at the requested DC.
        """
        char = _make_charismatic_character()
        skills = json.loads(SKILLS_JSON.read_text())
        # Roll persuasion at DC 15 (the SRD default Influence DC; see
        # Rules Glossary line 1246).
        result = char.make_skill_check("persuasion", dc=15, skills_data=skills)
        assert "success" in result
        assert "total" in result
        assert result["ability"] == "cha"
        assert 1 <= result["roll"] <= 20

    def test_influence_action_exists_and_is_dispatchable(self) -> None:
        pytest.skip(
            "GAP: there is no Influence action handler. The SRD's "
            "'GM will typically ask you to take the Influence action' "
            "has no dispatcher entry. The scenario script executor "
            "(`dnd_engine/scenarios/script_executor.py:200-224`) "
            "only accepts 'wait', 'attack', and 'monster_attack' "
            "— no 'influence'. The combat-mode "
            "available-actions list "
            "(`dnd_engine/core/game_state.py:766`) is "
            "`['attack', 'use_item']` — also no 'influence'. "
            "Tracked by issue #444."
        )

    def test_influence_action_consumes_an_action_slot(self) -> None:
        pytest.skip(
            "GAP: the SRD's Influence is an Action (Rules Glossary, "
            "line 1226: 'Influence [Action]'). When taken in combat, "
            "it should cost the full `ActionType.ACTION` slot "
            "(`dnd_engine/systems/action_economy.py:8-22`). No handler "
            "consumes it. Tracked by issue #444."
        )

    def test_influence_check_default_DC_is_15_or_int_score_whichever_higher(self) -> None:
        pytest.skip(
            "GAP: the Rules Glossary 'Influence' entry "
            "(`docs/srd/rules-glossary/rules-glossary.md:1226-1251`) "
            "specifies a default DC of 'equal to 15 or the monster's "
            "Intelligence score, whichever is higher'. No code "
            "computes this DC anywhere. The check primitive "
            "(`Character.make_skill_check`, `character.py:726`) takes "
            "a DC argument but nothing calls it with the SRD-default "
            "DC for an Influence attempt. Tracked by issue #444."
        )

    def test_influence_failure_imposes_24_hour_cooldown_on_same_approach(self) -> None:
        pytest.skip(
            "GAP: the Rules Glossary specifies that on a failed "
            "Influence check 'you must wait 24 hours (or a duration "
            "set by the GM) before urging it in the same way again'. "
            "There is no per-NPC cooldown registry; "
            "`NPC.conversation_history` "
            "(`dnd_engine/core/npc.py:146`) is freeform message log "
            "with no structured 'last failed influence approach' "
            "tracker, and `TimeManager` "
            "(`dnd_engine/systems/time_manager.py`) is used for "
            "rest / travel cadence, not social cooldowns. Tracked by "
            "issue #444."
        )

    def test_influence_action_consults_skill_proficiency_advice(self) -> None:
        """Skill-proficiency choice is observable on Character.

        SRD: "Pay attention to your skill proficiencies when thinking
        of how you will interact with an NPC; use an approach that
        relies on your group's skill proficiencies." This rule is
        about player choice rather than mechanics; the only engine
        guarantee is that a Character can declare which CHA / WIS
        skills it is proficient in, and that `make_skill_check`
        respects that via the proficiency bonus. We pin both here.
        """
        char = _make_charismatic_character()
        # Character carries declared skill proficiencies the player
        # would use to "lead the discussion" with a guard.
        assert "deception" in char.skill_proficiencies
        assert "persuasion" in char.skill_proficiencies
        # And the skill_modifier path applies the proficiency bonus.
        skills = json.loads(SKILLS_JSON.read_text())
        prof_mod = char.get_skill_modifier("deception", skills)
        nonprof_mod = char.get_skill_modifier("performance", skills)
        # CHA mod is +3 either way; proficient should add the +2 PB on
        # top.
        assert prof_mod == nonprof_mod + char.proficiency_bonus


class TestSocialInteraction_CoverageMatrix:
    """Coverage matrix: every clause in social-interaction.md is mapped.

    This class is intentionally a comment-style catalog. Each row maps
    one SRD clause to either a real test or a skipped GAP-stub above.
    """

    def test_every_srd_clause_is_audited_above(self) -> None:
        """Self-check: this audit covers every clause of the SRD section.

        Clause mapping:

          1. "player characters meet many different people and face
             some monsters that would rather talk than fight"
             -> TestSocialInteraction_Intro ::
                test_npc_class_exists_as_a_first_class_engine_entity

          2. "The Game Master assumes the roles of any nonplayer
             characters who are participating."
             -> TestSocialInteraction_Intro ::
                test_engine_routes_npc_dialogue_through_npc_chat_manager

          3. "An NPC's attitude toward your character is Friendly,
             Indifferent, or Hostile, as defined in 'Rules Glossary.'"
             -> TestSocialInteraction_NPCAttitude (6 tests; Indifferent
                gap pinned at
                test_indifferent_is_not_a_member_of_npc_disposition_today)

          4. "Friendly NPCs are predisposed to help, and Hostile ones
             are inclined to hinder."
             -> TestSocialInteraction_NPCAttitude ::
                test_friendly_npc_threshold_is_consulted
                + test_hostile_npc_threshold_is_consulted
                + test_npc_attitude_is_used_to_modify_influence_check_outcome

          5. "Social interactions progress in two ways: through
             roleplaying and ability checks."
             -> TestSocialInteraction_TwoProgressionAxes ::
                test_both_progression_axes_have_engine_surfaces

          6. "Roleplaying is, literally, the act of playing out a
             role." + "GM uses an NPC's personality and your
             character's actions and attitudes to determine how an
             NPC reacts."
             -> TestSocialInteraction_Roleplaying (3 tests)

          7. "Ability checks can be key in determining the outcome of
             a social interaction."
             -> TestSocialInteraction_AbilityChecks ::
                test_charisma_skill_primitives_exist_for_all_influence_skills
                + test_make_skill_check_runs_a_d20_plus_skill_modifier

          8. "the GM will typically ask you to take the Influence
             action."
             -> TestSocialInteraction_AbilityChecks ::
                test_influence_action_exists_and_is_dispatchable
                + test_influence_action_consumes_an_action_slot
                + test_influence_check_default_DC_is_15_or_int_score_whichever_higher
                + test_influence_failure_imposes_24_hour_cooldown_on_same_approach

          9. "Pay attention to your skill proficiencies when thinking
             of how you will interact with an NPC ... rely on your
             group's skill proficiencies."
             -> TestSocialInteraction_AbilityChecks ::
                test_influence_action_consults_skill_proficiency_advice

        Engine surfaces that *do* exist and are reused above:
          - NPC                            (npc.py:120)
          - NPCDisposition                 (npc.py:9-16)
          - NPC.get_disposition            (npc.py:184)
          - NPC.build_system_prompt        (npc.py:198)
          - NPCChatManager                 (llm/npc_chat.py:191)
          - Character.make_skill_check     (character.py:726)
          - Character.get_skill_modifier   (character.py:~700)
          - skills.json (5 Influence skills)
          - ActionType.NO_ACTION           (action_economy.py:22)

        Engine surfaces that *don't* exist (rolled up as the gap):
          - Influence action dispatcher                  (#444)
          - Indifferent disposition member               (#527)
          - Attitude-driven advantage/disadvantage on
            Influence checks                             (#444)
          - 24-hour cooldown registry on failed
            Influence approach                           (#444)
          - Structured player-action/attitude inputs to
            NPC reactions (beyond a single reputation
            integer)                                     (#527)
        """
        # The mapping above is the assertion in human-readable form.
        # This test exists as a citation anchor and to make the
        # coverage matrix collectable by `pytest --collect-only`.
        assert True


# Sanity guard: `inspect` is imported for parity with sister audits
# that source-check engine code. Keep the import even if the current
# test set doesn't yet need it — the moment the Influence handler
# lands, the gating tests above will flip from skip to source-level
# assertions and consume it.
_ = inspect
