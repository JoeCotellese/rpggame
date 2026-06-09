# ABOUTME: SRD conformance audit for "Playing the Game > Exploration".
# ABOUTME: Cross-references docs/srd/playing-the-game/exploration.md against engine code.

"""SRD conformance: Exploration.

Maps every rule in `docs/srd/playing-the-game/exploration.md` to a test.
Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The Exploration section is short (lines 1511-1536 of SRD_CC_v5.2.1.txt)
and is mostly a pointer into the Equipment chapter: it asserts that
adventuring gear (Ladder, Torch, Thieves' Tools, Caltrops, weapons used
non-combatively) helps adventurers interact with the environment. The
audit therefore focuses on data-parity — the catalog must carry these
items so the SRD's "for example, they can reach out-of-the-way places
with a Ladder..." promises map to real game objects — plus a handful of
engine-enforcement checks (lock-pick path consumes the Thieves' Tools
proficiency surface, Torch effect resolves through the item-effects
system, etc.).

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.systems.item_effects import apply_item_effect

pytestmark = pytest.mark.srd(
    "playing-the-game/exploration.md",
    lines="1511-1536",
)


ITEMS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "items.json"
)
CLASSES_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "classes.json"
)


def _load_items() -> dict:
    return json.loads(ITEMS_JSON.read_text())


def _make_rogue() -> Character:
    """Rogue with Thieves' Tools proficiency — the lock-pick exemplar."""
    abilities = Abilities(
        strength=10,
        dexterity=16,
        constitution=10,
        intelligence=12,
        wisdom=10,
        charisma=10,
    )
    return Character(
        name="Picker",
        character_class=CharacterClass.ROGUE,
        level=1,
        abilities=abilities,
        max_hp=8,
        ac=14,
        race="halfling",
        skill_proficiencies=["stealth"],
        tool_proficiencies=["thieves_tools"],
    )


class TestExploration_Intro:
    """SRD § Playing the Game › Exploration › Intro.

    > Exploration involves delving into places that are dangerous and
    > full of mystery. The rules in this section detail some of the ways
    > adventurers interact with the environment in such places.
    """

    def test_engine_has_an_exploration_mode_distinct_from_combat(self) -> None:
        """`GameState.cast_spell_exploration` is the engine's exploration entry point.

        The SRD frames exploration as a discrete rules mode ("delving
        into places... interact with the environment"). The engine
        carries an out-of-combat exploration surface:
        `GameState.cast_spell_exploration`
        (`dnd-engine/dnd_engine/core/game_state.py:1897`) handles
        non-combat spell casting, and
        `Character.get_out_of_combat_spells`
        (`dnd-engine/dnd_engine/core/character.py:1750`) filters the
        spell list for exploration-appropriate utility. This guards
        the SRD framing has at least one engine attach-point.
        """
        assert callable(getattr(GameState, "cast_spell_exploration", None)), (
            "GameState must expose an out-of-combat / exploration spell "
            "entry point to honor the SRD's 'exploration involves... "
            "interact with the environment' framing."
        )
        assert callable(getattr(Character, "get_out_of_combat_spells", None)), (
            "Character must expose an exploration-appropriate spell "
            "filter so the LLM/UI can offer the right options outside "
            "of combat."
        )

    def test_event_taxonomy_distinguishes_exploration_events(self) -> None:
        """The event bus has a dedicated Exploration event family.

        `dnd_engine/utils/events.py:41` carries the comment
        "# Exploration events", marking off a discrete category of
        bus traffic for exploration-time signals (room entry, examine,
        unlock, etc.). This is the engine's bookkeeping that the SRD's
        "rules in this section" form their own audience-on-bus
        bracket.
        """
        events_src = (
            Path(__file__).resolve().parents[3]
            / "dnd_engine"
            / "utils"
            / "events.py"
        ).read_text()
        assert "Exploration events" in events_src, (
            "events.py must continue to label its exploration event "
            "family so SRD-aligned exploration signals stay greppable."
        )


class TestExploration_AdventuringEquipment_Ladder:
    """SRD § Playing the Game › Exploration › Adventuring Equipment (Ladder).

    > As adventurers explore, their equipment can help them in many
    > ways. For example, they can reach out-of-the-way places with a
    > Ladder...
    """

    def test_ladder_is_in_the_equipment_catalog(self) -> None:
        """A Ladder entry exists in `items.json` under `equipment`.

        The SRD's "reach out-of-the-way places with a Ladder" example
        needs a real ladder object to point at. `data/srd/items.json`
        carries one with the canonical "Ladder (10-foot)" name.
        """
        items = _load_items()
        assert "ladder" in items["equipment"], (
            "items.json must catalog a `ladder` under `equipment` so the "
            "SRD's 'reach out-of-the-way places with a Ladder' example "
            "has a real game object to reference."
        )
        ladder = items["equipment"]["ladder"]
        assert "Ladder" in ladder["name"], (
            "Ladder catalog entry must keep the 'Ladder' name so it is "
            "discoverable by the SRD-aligned vocabulary."
        )

    def test_ladder_supports_vertical_traversal_in_engine(self) -> None:
        pytest.skip(
            "GAP: there is no engine-side ladder traversal action. The "
            "`ladder` item is catalog-only — no `Capability.LADDER` in "
            "`dnd_engine/systems/capabilities.py:21`, no per-room "
            "`vertical_exit` field, no `climb_ladder` action handler. "
            "Movement to vertically separated rooms is currently "
            "modeled, if at all, via flat-direction `exits` in dungeon "
            "JSON. Closing this would let the SRD's 'reach out-of-the-"
            "way places' clause translate into a real action."
        )


class TestExploration_AdventuringEquipment_Torch:
    """SRD § Playing the Game › Exploration › Adventuring Equipment (Torch).

    > ...perceive things they wouldn't otherwise notice with a Torch or
    > another light source...
    """

    def test_torch_is_in_the_consumables_catalog(self) -> None:
        """`items.json` carries a `torch` consumable that grants light.

        The SRD's Torch example needs an entry that wires through the
        engine's light-providing path. The `torch` entry in `items.json`
        under `consumables` carries `effect_type: light`,
        `light_level: bright`, and a 60-minute duration — matching the
        SRD's "burns for 1 hour, bright light in a 20-foot radius and
        dim light for an additional 20 feet" description.
        """
        items = _load_items()
        assert "torch" in items["consumables"], (
            "items.json must catalog `torch` under `consumables` to "
            "back the SRD's 'perceive things with a Torch' example."
        )
        torch = items["consumables"]["torch"]
        assert torch["effect_type"] == "light", (
            "Torch must declare `effect_type: light` so the item-effects "
            "dispatcher routes it to the light-source handler."
        )
        assert torch["light_level"] == "bright", (
            "Torch must declare `light_level: bright` per SRD: "
            "'bright light in a 20-foot radius'."
        )
        assert torch["duration_minutes"] == 60, (
            "Torch must declare `duration_minutes: 60` per SRD: "
            "'burns for 1 hour'."
        )

    def test_torch_light_effect_resolves_through_item_effects_dispatch(self) -> None:
        """`apply_item_effect` recognizes the torch's `light` effect.

        The SRD's "another light source" branch is closed by the
        item-effects dispatcher: `apply_item_effect` in
        `dnd_engine/systems/item_effects.py` returns a recognized
        `effect_type` of "light" rather than the unimplemented-effect
        fallback. Without a `TimeManager`, the call returns a result
        flagged as unimplemented (light effects need timed tracking),
        but the dispatcher itself recognizes the type — which is the
        engine seam this audit guards.
        """
        items = _load_items()
        torch = items["consumables"]["torch"]
        char = _make_rogue()
        # No TimeManager passed — the light handler short-circuits but the
        # dispatcher still routes to a 'light' effect_type, not 'unknown'.
        result = apply_item_effect(torch, char, time_manager=None)
        assert result.effect_type == "light", (
            "apply_item_effect must dispatch torch to the 'light' "
            "handler so the SRD's 'Torch or another light source' "
            "example has a real engine seam."
        )

    def test_torch_carries_capability_in_capabilities_map(self) -> None:
        """The capabilities module declares Torch grants `LIGHT_SOURCE`.

        `dnd_engine/systems/capabilities.py:83` maps `"torch"` to
        `[Capability.LIGHT_SOURCE]`. This is the engine record that
        Torch is the canonical "perceive things... with a Torch" item
        from the SRD.
        """
        capabilities_src = (
            Path(__file__).resolve().parents[3]
            / "dnd_engine"
            / "systems"
            / "capabilities.py"
        ).read_text()
        assert '"torch"' in capabilities_src or "'torch'" in capabilities_src, (
            "capabilities.py must list `torch` as a LIGHT_SOURCE "
            "provider so the SRD's exploration example has a "
            "capability-layer attach-point."
        )
        assert "LIGHT_SOURCE" in capabilities_src, (
            "capabilities.py must continue to declare the LIGHT_SOURCE "
            "capability tag."
        )


class TestExploration_AdventuringEquipment_ThievesTools:
    """SRD § Playing the Game › Exploration › Adventuring Equipment (Thieves' Tools).

    > ...bypass locked doors and containers with Thieves' Tools...
    """

    def test_thieves_tools_is_in_the_tools_catalog(self) -> None:
        """`items.json` catalogs Thieves' Tools under `tools`.

        The SRD's "bypass locked doors and containers with Thieves'
        Tools" example needs a real tool entry. `data/srd/items.json`
        carries `tools.thieves_tools`.
        """
        items = _load_items()
        assert "thieves_tools" in items["tools"], (
            "items.json must catalog `thieves_tools` under `tools` to "
            "back the SRD's 'bypass locked doors and containers with "
            "Thieves' Tools' example."
        )
        tt = items["tools"]["thieves_tools"]
        assert "Thieves' Tools" in tt["name"]
        # SRD: "add your proficiency bonus to any ability check you make
        # to disarm traps or open locks."
        assert "lock" in tt["description"].lower() or "trap" in tt["description"].lower()

    def test_rogue_class_starts_with_thieves_tools_proficiency(self) -> None:
        """The Rogue class data lists `thieves_tools` as a tool proficiency.

        SRD-aligned exemplar: the Rogue is the canonical Thieves' Tools
        user. `data/srd/classes.json` carries `tool_proficiencies` for
        each class, and the Rogue's list includes `thieves_tools`.
        """
        classes = json.loads(CLASSES_JSON.read_text())
        rogue = classes["rogue"]
        assert "thieves_tools" in rogue["tool_proficiencies"], (
            "Rogue class data must list `thieves_tools` so the SRD's "
            "lock-bypass exemplar has a class-side proficiency."
        )

    def test_character_carries_tool_proficiencies(self) -> None:
        """`Character` exposes `tool_proficiencies` as a first-class field.

        Read by `Character.is_proficient_with_tool` /
        `Character.make_tool_check` during the skill-based unlock path
        and any other tool-mediated ability check.
        """
        rogue = _make_rogue()
        assert hasattr(rogue, "tool_proficiencies"), (
            "Character must carry a `tool_proficiencies` list so "
            "Thieves' Tools proficiency can be honored at unlock-time."
        )
        assert "thieves_tools" in rogue.tool_proficiencies

    def test_unlock_door_path_inspects_thieves_tools_proficiency(self) -> None:
        """`GameState.attempt_unlock` routes tool-flagged unlocks through
        `make_tool_check`, which is the engine's single consumer of
        `character.tool_proficiencies`.

        Source-level guard: the SRD's "bypass locked doors... with
        Thieves' Tools" promise has a real consumer at
        `dnd-engine/dnd_engine/core/game_state.py` — the unlock path
        reads `method.get("tool_proficiency")` and delegates to
        `Character.make_tool_check(...)` so PB applies when the
        character is tool-proficient and Advantage applies when they
        are also skill-proficient (SRD § Proficiency › Equipment
        Proficiencies › Tools).

        The SRD does not actually require tool proficiency to attempt
        the check; it only adds PB / Advantage. `make_tool_check`
        handles the "lacks proficiency" case (delegates to
        `make_skill_check` or a plain ability check).
        """
        unlock_src = inspect.getsource(GameState.attempt_unlock)
        assert "tool_proficiency" in unlock_src, (
            "GameState.attempt_unlock must consult the unlock method's "
            "`tool_proficiency` requirement to honor the SRD's "
            "'bypass locked doors with Thieves' Tools' clause."
        )
        assert "make_tool_check" in unlock_src, (
            "GameState.attempt_unlock must route tool-flagged unlocks "
            "through `Character.make_tool_check` so PB and the tool+"
            "skill Advantage are applied per SRD."
        )


class TestExploration_AdventuringEquipment_Caltrops:
    """SRD § Playing the Game › Exploration › Adventuring Equipment (Caltrops).

    > ...and create obstacles for pursuers with Caltrops.
    """

    def test_caltrops_is_in_the_equipment_catalog(self) -> None:
        """`items.json` carries a `caltrops` entry under `equipment`.

        The SRD's "create obstacles for pursuers with Caltrops" example
        is backed by `equipment.caltrops`, whose description carries
        the canonical "bag of 20", 5-ft square, DC 15 DEX save, 1
        piercing damage mechanics.
        """
        items = _load_items()
        assert "caltrops" in items["equipment"], (
            "items.json must catalog `caltrops` under `equipment` to "
            "back the SRD's 'create obstacles for pursuers with "
            "Caltrops' example."
        )
        ct = items["equipment"]["caltrops"]
        assert "Caltrops" in ct["name"]
        # SRD-aligned mechanics in the description:
        assert "DC 15" in ct["description"] or "dc 15" in ct["description"].lower()
        assert "Dexterity" in ct["description"] or "dexterity" in ct["description"].lower()

    def test_caltrops_is_consumed_as_an_obstacle_in_engine(self) -> None:
        pytest.skip(
            "GAP: there is no engine path that *deploys* caltrops as an "
            "area obstacle. The catalog entry exists "
            "(`items.json: equipment.caltrops`) with full SRD text in "
            "the description, but no action handler, no scenario "
            "script verb, no MCP tool, and no `apply_item_effect` "
            "branch consumes caltrops to spawn a per-tile hazard. "
            "Combat-mode available actions "
            "(`dnd_engine/core/game_state.py:766`) are `['attack', "
            "'use_item']`; `use_item` -> `apply_item_effect` "
            "(`systems/item_effects.py`) handles `healing`, `damage`, "
            "`condition_removal`, `buff`, `light`, `spell`, "
            "`information` — no `area_hazard` effect_type. Tracked by "
            "issue #503-followup: file a new issue if/when caltrops "
            "become a tactical item."
        )


class TestExploration_AdventuringEquipment_WeaponsAsTools:
    """SRD § Playing the Game › Exploration › Weapons used non-combatively.

    > The weapons in "Equipment" can also be used for more than battle;
    > you could use a Quarterstaff, for example, to push a sinister-
    > looking button that you're reluctant to touch.
    """

    def test_quarterstaff_exists_in_weapons_catalog(self) -> None:
        """A Quarterstaff is in the weapons catalog.

        The SRD's "push a sinister-looking button with a Quarterstaff"
        example needs a real Quarterstaff to wave around. `items.json`
        carries one.
        """
        items = _load_items()
        weapons = items.get("weapons", {})
        assert "quarterstaff" in weapons, (
            "items.json must catalog `quarterstaff` under `weapons` so "
            "the SRD's 'push a sinister-looking button with a "
            "Quarterstaff' exploration example has a real game object."
        )

    def test_weapons_can_be_used_non_combatively_via_examine_action(self) -> None:
        pytest.skip(
            "GAP: the SRD's 'weapons used for more than battle' clause "
            "has no first-class engine surface. Rooms declare "
            "`examinable_objects` and exits with `examine_checks` "
            "(`GameState.get_examinable_objects` -> "
            "`dnd_engine/core/game_state.py:1146`, "
            "`examine_exit` -> `:1177`), but the examine path does "
            "not consult held weapons / items to gate or modify the "
            "interaction. There is no 'reach with a 10-ft pole' "
            "carve-out, no quarterstaff-as-button-presser handler. "
            "This is a GM-mediated improvisation in the SRD; the "
            "engine could surface it via the existing `examine` path "
            "plus an item-as-reach modifier. Cross-cuts issue #453 "
            "(Improvised action surface)."
        )


class TestExploration_Coverage:
    """Coverage map: SRD rules <-> tests in this file.

    Maintainer index. Update both columns when adding a rule.

    | SRD rule (exploration.md)                                    | Test                                                                      |
    |--------------------------------------------------------------|---------------------------------------------------------------------------|
    | Intro: exploration is a discrete rules mode                  | TestExploration_Intro                                                     |
    | Ladder example (reach out-of-the-way places)                 | TestExploration_AdventuringEquipment_Ladder                               |
    | Torch / light source example (perceive things)               | TestExploration_AdventuringEquipment_Torch                                |
    | Thieves' Tools example (bypass locked doors/containers)      | TestExploration_AdventuringEquipment_ThievesTools                         |
    | Caltrops example (create obstacles for pursuers)             | TestExploration_AdventuringEquipment_Caltrops                             |
    | Weapons used non-combatively (Quarterstaff button-press)     | TestExploration_AdventuringEquipment_WeaponsAsTools                       |
    """

    def test_coverage_map_present(self) -> None:
        """Sanity check: this class's docstring carries the rule->test map."""
        assert TestExploration_Coverage.__doc__ is not None
        assert "SRD rule" in TestExploration_Coverage.__doc__
        assert "Ladder example" in TestExploration_Coverage.__doc__
