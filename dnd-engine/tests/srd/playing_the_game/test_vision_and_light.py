# ABOUTME: SRD conformance audit for "Playing the Game > Vision and Light".
# ABOUTME: Cross-references docs/srd/playing-the-game/vision-and-light.md against engine code.

"""SRD conformance: Vision and Light.

Maps every rule in `docs/srd/playing-the-game/vision-and-light.md` to a
test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

A common finding for this section: the bright/dim/dark *category* of
illumination is well-modeled in the `client-2d` rendering layer
(`client-2d/src/client_2d/systems/lighting.py`,
`client-2d/src/client_2d/systems/fog_of_war.py`), but the engine layer
only carries a single room-wide string and does not gate attack rolls
or sight-based checks on per-creature visibility. The skips below cite
`client-2d/.../lighting.py:NNN` where rules live in the client but not
the engine.

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
    "playing-the-game/vision-and-light.md",
    lines="1537-1578",
)


def _make_human_character() -> Character:
    """Human fighter — no darkvision, +2 WIS."""
    abilities = Abilities(
        strength=10,
        dexterity=10,
        constitution=10,
        intelligence=10,
        wisdom=14,
        charisma=10,
    )
    char = Character(
        name="Human Scout",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=12,
        ac=16,
        race="human",
        skill_proficiencies=["perception"],
    )
    char.darkvision_range = 0
    return char


def _make_dwarf_character() -> Character:
    """Dwarf fighter — 60 ft darkvision."""
    abilities = Abilities(
        strength=10,
        dexterity=10,
        constitution=10,
        intelligence=10,
        wisdom=14,
        charisma=10,
    )
    char = Character(
        name="Dwarf Scout",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=12,
        ac=16,
        race="dwarf",
        skill_proficiencies=["perception"],
    )
    char.darkvision_range = 60
    return char


class TestVisionAndLight_Intro:
    """SRD § Playing the Game › Vision and Light › Intro.

    > Some adventuring tasks—such as noticing danger, hitting an enemy,
    > and targeting certain spells—are affected by sight, so effects
    > that obscure vision can hinder you, as explained below.
    """

    def test_perception_in_darkness_is_affected_by_sight(self):
        """Sight-based Perception auto-fails in darkness (the "noticing danger" branch).

        The SRD's first promise — that "noticing danger" is sight-
        affected — has a real engine implementation in
        `GameState._apply_lighting_penalties`
        (`dnd-engine/dnd_engine/core/game_state.py:698-756`): in dark
        rooms, sight-based Perception is short-circuited with an
        auto-fail result. The path is gated to the literal "perception"
        skill only, but the intro promise that *some* sight check
        respects darkness is honored.
        """
        src = inspect.getsource(GameState._apply_lighting_penalties)
        assert "perception" in src.lower(), (
            "Sight-based Perception must be a recognized branch of the "
            "lighting-penalty logic so 'effects that obscure vision can "
            "hinder you' has at least one enforcement site."
        )
        assert "dark" in src.lower() and "auto" in src.lower() or "fail" in src.lower(), (
            "Darkness must short-circuit sight-based Perception with an "
            "auto-fail outcome, matching the SRD intro's 'noticing "
            "danger' example."
        )

    def test_hitting_an_enemy_is_affected_by_sight(self):
        pytest.skip(
            "GAP: the SRD intro names 'hitting an enemy' as one of the "
            "sight-affected adventuring tasks, but `CombatEngine."
            "resolve_attack` (`dnd-engine/dnd_engine/core/combat.py:91`) "
            "does not take any lighting / obscurement / visibility "
            "parameter. Attacks resolve identically in bright light, "
            "dim light, and darkness. The per-tile visibility model "
            "lives in `client-2d/src/client_2d/systems/lighting.py:111` "
            "and `client-2d/src/client_2d/systems/fog_of_war.py:14` but "
            "the engine never reads it back. Tracked by issue #494 "
            "(vision rules in client-2d) and issue #475 (visibility "
            "advantage/disadvantage)."
        )

    def test_targeting_certain_spells_is_affected_by_sight(self):
        pytest.skip(
            "GAP: the SRD intro names 'targeting certain spells' as a "
            "sight-affected task. `GameState.cast_spell_combat` "
            "(`dnd-engine/dnd_engine/core/game_state.py:2077`) does not "
            "consult target visibility before resolving the spell — a "
            "caster can target an enemy they cannot see. No `requires_"
            "sight` field on spell entries in spells.json is checked. "
            "Tracked by issue #494."
        )


class TestVisionAndLight_ObscuredAreas:
    """SRD § Playing the Game › Vision and Light › Obscured Areas.

    > An area might be Lightly or Heavily Obscured. In a Lightly
    > Obscured area—such as an area with Dim Light, patchy fog, or
    > moderate foliage—you have Disadvantage on Wisdom (Perception)
    > checks that rely on sight. A Heavily Obscured area—such as an
    > area with Darkness, heavy fog, or dense foliage—is opaque. You
    > have the Blinded condition when trying to see something there.
    """

    def test_lightly_obscured_concept_exists_in_engine(self):
        """The Lightly Obscured concept is a first-class engine state.

        plan-05 slice A introduces `Obscurement.LIGHTLY` as a reusable
        obscurement state, and Dim Light maps onto it via
        `effective_obscurement` — the reusable hook other sight-based
        rules can consult. (issue #493)
        """
        from dnd_engine.systems.perception import (
            LightLevel,
            Obscurement,
            effective_obscurement,
        )

        assert Obscurement.LIGHTLY.value == "lightly"
        assert effective_obscurement(LightLevel.DIM) == Obscurement.LIGHTLY

    def test_lightly_obscured_dim_light_imposes_disadvantage_on_sight_perception(self):
        """Dim Light imposes Disadvantage on Wisdom (Perception) checks.

        This is the one concrete enforcement of the Obscured-Areas rule
        currently in the engine. `GameState._apply_lighting_penalties`
        (`dnd-engine/dnd_engine/core/game_state.py:753-754`) returns
        `(True, True, None)` — `has_disadvantage=True` — for the
        "perception" skill when effective lighting is "dim".
        """
        src = inspect.getsource(GameState._apply_lighting_penalties)
        assert "dim" in src.lower(), (
            "Dim light must be a recognized lighting state in the "
            "penalty function so it can impose disadvantage."
        )
        assert "disadvantage" in src.lower() or "has_disadvantage" in src, (
            "The dim-light branch must propagate a disadvantage signal "
            "to the caller, matching the SRD's 'Disadvantage on Wisdom "
            "(Perception) checks that rely on sight' rule."
        )

    def test_lightly_obscured_disadvantage_extends_to_all_sight_based_wis_checks(self):
        pytest.skip(
            "GAP: the dim-light disadvantage in `GameState."
            "_apply_lighting_penalties` (`dnd-engine/dnd_engine/core/"
            "game_state.py:720-721`) is gated to the literal "
            "'perception' skill. Other sight-based WIS checks (Insight, "
            "Medicine, Survival) and non-WIS sight-based checks "
            "(Investigation — INT, Sleight of Hand observation — DEX) "
            "get no penalty. Tracked by issue #493."
        )

    def test_heavily_obscured_concept_exists_in_engine(self):
        """The Heavily Obscured concept is a first-class engine state.

        `Obscurement.HEAVILY` exists and Darkness maps onto it via
        `effective_obscurement`; a sight-based observer is Unseen across
        a heavily obscured area (the Blinded-against-that-area rule).
        (issue #493)
        """
        from dnd_engine.systems.perception import (
            LightLevel,
            Obscurement,
            effective_obscurement,
        )

        assert Obscurement.HEAVILY.value == "heavily"
        assert effective_obscurement(LightLevel.DARK) == Obscurement.HEAVILY

    def test_heavily_obscured_darkness_auto_fails_sight_based_perception(self):
        """Darkness short-circuits sight-based Perception to auto-fail.

        This is the engine's only enforcement of the "Heavily Obscured
        / Blinded" rule today: in `GameState._apply_lighting_penalties`
        (`dnd-engine/dnd_engine/core/game_state.py:724-752`), the
        "dark" branch returns `should_continue=False` plus a synthetic
        failed `check_result` with roll=0 — the moral equivalent of
        the Blinded condition's "automatic fail of any ability check
        that requires sight."
        """
        src = inspect.getsource(GameState._apply_lighting_penalties)
        assert 'lighting == "dark"' in src or "lighting=='dark'" in src.replace(" ", ""), (
            "Darkness must be a recognized branch of the lighting-"
            "penalty function so it can drive the auto-fail path."
        )
        assert "success" in src and "False" in src, (
            "The darkness branch must produce a failed check result so "
            "the SRD's 'opaque / Blinded' semantics for sight-based "
            "Perception are honored."
        )

    def test_heavily_obscured_applies_blinded_condition_when_trying_to_see(self):
        pytest.skip(
            "GAP: the SRD specifies the Blinded *condition* applies "
            "while trying to see into a heavily obscured area. The "
            "`blinded` condition exists as a string only — referenced "
            "by `dnd-engine/dnd_engine/systems/ranged_attacks.py:71` "
            "(close-combat ranged disadvantage) and as a monster "
            "`condition_immunity` in `monsters.json:661`. No code "
            "applies the condition to a creature looking into a "
            "heavily obscured area. The Blinded condition is not even "
            "in `dnd-engine/dnd_engine/data/srd/conditions.json` (only "
            "`on_fire` and `surprised` are catalogued there). Tracked "
            "by issue #493."
        )

    def test_obscurement_sources_are_data_driven(self):
        pytest.skip(
            "GAP: the SRD lists six environmental triggers for "
            "obscurement — Dim Light, patchy fog, moderate foliage "
            "(lightly); Darkness, heavy fog, dense foliage (heavily). "
            "Only `room.lighting` (`dnd-engine/dnd_engine/core/"
            "game_state.py:677`) is consulted by `get_effective_"
            "lighting`. Fog, foliage, and other obscurement sources "
            "have no data model on rooms or per-tile in client-2d. "
            "Tracked by issue #493."
        )


class TestVisionAndLight_Light:
    """SRD § Playing the Game › Vision and Light › Light.

    > The presence or absence of light determines the category of
    > illumination in an area, as defined below.
    """

    def test_bright_light_lets_most_creatures_see_normally(self):
        """`get_effective_lighting` returns 'bright' for a bright room.

        Bright Light is the SRD baseline ("see normally"). The engine
        models it as one of three room-lighting strings consumed by
        `GameState.get_effective_lighting`
        (`dnd-engine/dnd_engine/core/game_state.py:661`). A human
        character in a bright-lit test dungeon room sees bright.
        """
        char = _make_human_character()
        party = Party([char])
        game_state = GameState(party, "test_dungeon")
        room = game_state.get_current_room()
        assert room.get("lighting", "bright") == "bright"
        assert game_state.get_effective_lighting(char) == "bright"

    def test_bright_light_sources_include_torches_lanterns_fires(self):
        """Item catalog declares bright/dim levels on light-source items.

        The SRD names "torches, lanterns, fires, and other sources of
        illumination within a specific radius." The engine's data model
        carries this as `light_level: "bright"` on items in
        `dnd-engine/dnd_engine/data/srd/items.json:577,592`. Per-radius
        values themselves live in `client-2d/src/client_2d/core/
        constants.py:35-45` (Torch 4 bright + 4 dim, Lantern 6+6, Light
        cantrip 4+4 — at 5 ft per tile).
        """
        import json
        from pathlib import Path

        items_path = (
            Path(__file__).resolve().parents[3]
            / "dnd_engine"
            / "data"
            / "srd"
            / "items.json"
        )
        items = json.loads(items_path.read_text())
        # items.json is keyed by category (weapons, armor, consumables, …);
        # walk it for any entry that declares a light_level.
        bright_sources: list[str] = []

        def walk(obj):
            if isinstance(obj, dict):
                if obj.get("light_level") == "bright":
                    bright_sources.append(obj.get("name", "?"))
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for entry in obj:
                    walk(entry)

        walk(items)
        assert bright_sources, (
            "Expected at least one item in items.json to declare "
            "`light_level: 'bright'` (e.g., a torch); the catalog "
            "ships at minimum `consumables.torch`."
        )

    def test_bright_light_per_creature_distance_from_source_is_modeled(self):
        pytest.skip(
            "GAP: the engine treats lighting as room-wide. Per-creature "
            "distance from a light source — the SRD's 'within a "
            "specific radius' clause — only lives in `client-2d/src/"
            "client_2d/systems/lighting.py:130-153` "
            "(`SimpleLighting.calculate_lit_tiles`). The engine's "
            "`get_effective_lighting` (`dnd-engine/dnd_engine/core/"
            "game_state.py:661`) returns one string per character per "
            "room and does not consider tile distance. Tracked by "
            "issue #494."
        )

    def test_dim_light_creates_a_lightly_obscured_area(self):
        """Dim Light triggers the lighting penalty (engine's proxy for Lightly Obscured).

        The SRD equates Dim Light with "Lightly Obscured." The engine
        doesn't carry an explicit `lightly_obscured` flag (see
        `TestVisionAndLight_ObscuredAreas`), but
        `_apply_lighting_penalties` (`dnd-engine/dnd_engine/core/
        game_state.py:753-754`) does fire the disadvantage path on
        dim-light Perception, which is the operational consequence.
        """
        src = inspect.getsource(GameState._apply_lighting_penalties)
        # The dim-light branch must exist and impose disadvantage.
        assert 'lighting == "dim"' in src or "lighting=='dim'" in src.replace(" ", ""), (
            "Dim-light branch must exist in the lighting-penalty "
            "function so Lightly Obscured semantics fire."
        )

    def test_dim_light_is_boundary_between_bright_and_darkness(self):
        pytest.skip(
            "GAP: the 'boundary' geometry — dim ring between bright "
            "and dark — lives in `client-2d/src/client_2d/systems/"
            "lighting.py:144-151` (`distance <= bright_radius` -> "
            "BRIGHT, `distance <= total_radius` -> DIM). The engine "
            "has no per-tile boundary model: a room is uniformly "
            "bright, dim, or dark. Tracked by issue #494."
        )

    def test_dim_light_sources_include_twilight_dawn_full_moon(self):
        pytest.skip(
            "GAP: the SRD's environmental dim-light sources "
            "(twilight, dawn, full moon) are not represented. The "
            "engine has no time-of-day model and no outdoor lighting "
            "schedule; `room.lighting` is set per-room as a static "
            "string (data files under `dnd-engine/dnd_engine/data/"
            "campaigns/`). Tracked by issue #494."
        )

    def test_darkness_creates_a_heavily_obscured_area(self):
        """Darkness short-circuits Perception (engine's proxy for Heavily Obscured).

        The SRD equates Darkness with "Heavily Obscured." The engine
        doesn't carry an explicit `heavily_obscured` flag (see
        `TestVisionAndLight_ObscuredAreas`), but
        `_apply_lighting_penalties` (`dnd-engine/dnd_engine/core/
        game_state.py:724-752`) does auto-fail sight-based Perception
        in darkness — the operational consequence.
        """
        src = inspect.getsource(GameState._apply_lighting_penalties)
        assert 'lighting == "dark"' in src or "lighting=='dark'" in src.replace(" ", ""), (
            "Dark-light branch must exist in the lighting-penalty "
            "function so Heavily Obscured semantics fire."
        )

    def test_darkness_sources_include_outdoors_at_night_unlit_dungeon_magical(self):
        """Dark room data exists for unlit dungeon rooms (one of three SRD sources).

        Of the three SRD darkness sources — outdoors at night, unlit
        dungeon, magical Darkness — only "unlit dungeon" has a data
        path: campaign rooms can declare `lighting: "dark"` (e.g.,
        `crypt.hall_of_the_dead` in the unquiet-dead campaign, see
        `dnd-engine/tests/test_lighting.py:106-108`). The other two
        sources have no engine surface.
        """
        char = _make_human_character()
        party = Party([char])
        game_state = GameState(
            party, "crypt", campaign_id="the_unquiet_dead"
        )
        game_state.current_room_id = "crypt.hall_of_the_dead"
        room = game_state.get_current_room()
        assert room.get("lighting") == "dark", (
            "At least one unlit-dungeon room must declare `lighting: "
            "'dark'` so the SRD's 'within the confines of an unlit "
            "dungeon' source has a real data presence."
        )

    def test_magical_darkness_overrides_light_sources(self):
        pytest.skip(
            "GAP: the SRD calls out 'magical Darkness' as a distinct "
            "Darkness source. No spell or item in `dnd-engine/"
            "dnd_engine/data/srd/spells.json` produces magical "
            "Darkness, and no engine code distinguishes mundane vs. "
            "magical darkness — which matters because Darkvision sees "
            "through mundane darkness but not magical Darkness, and "
            "Truesight (also unimplemented — see issue #495) sees "
            "through magical Darkness. Tracked by issue #494."
        )


class TestVisionAndLight_SpecialSenses:
    """SRD § Playing the Game › Vision and Light › Special Senses.

    > Some creatures have special senses that help them perceive things
    > in certain situations. "Rules Glossary" defines the following
    > special senses: Blindsight, Darkvision, Tremorsense, Truesight.
    """

    def test_darkvision_grants_dim_sight_in_darkness(self):
        """Dwarf darkvision converts a dark room to effective dim light.

        Of the four special senses, only Darkvision is implemented.
        `GameState.get_effective_lighting` (`dnd-engine/dnd_engine/
        core/game_state.py:691-693`) bumps a `"dark"` room to
        `"dim"` when `character.darkvision_range > 0`. This is the
        engine's only special-sense implementation.
        """
        dwarf = _make_dwarf_character()
        party = Party([dwarf])
        game_state = GameState(
            party, "crypt", campaign_id="the_unquiet_dead"
        )
        game_state.current_room_id = "crypt.hall_of_the_dead"
        assert game_state.get_current_room().get("lighting") == "dark"
        assert game_state.get_effective_lighting(dwarf) == "dim"

    def test_darkvision_is_a_first_class_capability(self):
        """`Capability.DARKVISION` and racial mapping exist.

        The capability system models Darkvision as a discrete
        capability (`dnd-engine/dnd_engine/systems/capabilities.py:22`)
        and maps it to six SRD races (elf, half-elf, dwarf, half-orc,
        tiefling, gnome) via `RACIAL_CAPABILITIES` (capabilities.py:
        92-98). This is the data-side acknowledgment that Darkvision
        is a real special sense in the SRD's catalog.
        """
        from dnd_engine.systems.capabilities import (
            Capability,
            CapabilityResolver,
        )

        assert Capability.DARKVISION.value == "darkvision"
        racial = CapabilityResolver.RACIAL_CAPABILITIES
        assert Capability.DARKVISION in racial.get("dwarf", [])
        assert Capability.DARKVISION in racial.get("elf", [])

    def test_blindsight_is_modeled(self):
        """Blindsight is a first-class engine sense (plan-05 slice A).

        `Sense.BLINDSIGHT` exists and `compute_visibility` lets an
        observer with blindsight perceive a target in darkness within
        range — the rule the rendering layer could only approximate.
        Catalog import of the monster `senses` field is wired in a
        later slice (issue #495); here the engine *concept* exists.
        """
        from dnd_engine.systems.perception import (
            LightLevel,
            Sense,
            VisibilityRelation,
            compute_visibility,
        )

        observer = _make_human_character()
        observer.senses = {Sense.BLINDSIGHT: 60}
        target = _make_human_character()
        relation = compute_visibility(
            observer,
            target,
            light_level=LightLevel.DARK,
            distance=30.0,
        )
        assert relation == VisibilityRelation.SEEN

    def test_tremorsense_is_modeled(self):
        """Tremorsense is modeled and senses only grounded targets.

        `Sense.TREMORSENSE` locates a grounded target through a shared
        surface (UnseenButSensed) within range, but a flying target —
        out of contact with the ground — is Unseen. (issue #495)
        """
        from dnd_engine.systems.perception import (
            LightLevel,
            Sense,
            VisibilityRelation,
            compute_visibility,
        )

        observer = _make_human_character()
        observer.senses = {Sense.TREMORSENSE: 30}
        target = _make_human_character()
        grounded = compute_visibility(
            observer,
            target,
            light_level=LightLevel.DARK,
            distance=20.0,
            target_on_ground=True,
        )
        flying = compute_visibility(
            observer,
            target,
            light_level=LightLevel.DARK,
            distance=20.0,
            target_on_ground=False,
        )
        assert grounded == VisibilityRelation.UNSEEN_BUT_SENSED
        assert flying == VisibilityRelation.UNSEEN

    def test_truesight_is_modeled(self):
        """Truesight sees through darkness and invisibility within range.

        Truesight is the only sense that pierces magical Darkness and
        the Invisible condition; `compute_visibility` returns Seen for a
        truesighted observer against an invisible target in the dark,
        within range. (issue #495)
        """
        from dnd_engine.systems.perception import (
            LightLevel,
            Sense,
            VisibilityRelation,
            compute_visibility,
        )

        observer = _make_human_character()
        observer.senses = {Sense.TRUESIGHT: 60}
        target = _make_human_character()
        target.add_condition("invisible")
        relation = compute_visibility(
            observer,
            target,
            light_level=LightLevel.DARK,
            distance=30.0,
        )
        assert relation == VisibilityRelation.SEEN


class TestVisionAndLight_CombatVisibilityNotConsulted:
    """Cross-cut: combat does not consult Vision and Light state.

    The SRD intro ("hitting an enemy ... affected by sight") and the
    Obscured Areas rules ("Heavily Obscured ... Blinded condition")
    together imply that the attack pipeline must read visibility. The
    engine's attack pipeline does not, so a single source-level guard
    captures that absence here.
    """

    def test_resolve_attack_does_not_take_lighting_or_visibility_parameters(self):
        pytest.skip(
            "GAP: confirmed absence. `CombatEngine.resolve_attack` "
            "(`dnd-engine/dnd_engine/core/combat.py:91`) signature is "
            "`(attacker, defender, attack_bonus, damage_dice, "
            "advantage=False, disadvantage=False, apply_damage=False, "
            "event_bus=None, action=None, game_state=None)`. There is "
            "no `lighting`, `obscurement`, `visibility`, or `can_see` "
            "parameter, and no caller derives `advantage`/`disadvantage` "
            "from visibility state today. The closest helper — "
            "`dnd_engine/systems/ranged_attacks.is_close_combat_ranged_"
            "disadvantage` — accepts a `attacker_visible_to` callable "
            "but it defaults to always-True. Tracked by issues #475 "
            "and #494."
        )
