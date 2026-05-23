# ABOUTME: SRD conformance audit for "Playing the Game > Hazards".
# ABOUTME: Cross-references docs/srd/playing-the-game/hazards.md against engine code.

"""SRD conformance: Hazards.

Maps every rule in `docs/srd/playing-the-game/hazards.md` to a test.
Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The Hazards section is a *cataloging* section: it enumerates five
hazards (Burning, Dehydration, Falling, Malnutrition, Suffocation) that
the SRD's Rules Glossary then defines in detail. The section's only
direct content is the catalog — so the audit's job is to verify that
the engine has a real model for each named hazard, or to mark the gap.

A common finding: of the five hazards, only **Burning** has any engine
presence at all (the `on_fire` condition in `conditions.json`), and even
that is a personal *condition* rather than an environmental *hazard
zone* — there is no per-room or per-tile "this area inflicts the
hazard" data field. The other four hazards have zero engine surface.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.systems.condition_manager import ConditionManager

pytestmark = pytest.mark.srd(
    "playing-the-game/hazards.md",
    lines="1650-1661",
)


CONDITIONS_JSON = (
    Path(__file__).resolve().parents[3]
    / "dnd_engine"
    / "data"
    / "srd"
    / "conditions.json"
)


def _make_creature(name: str = "Subject", hp: int = 20) -> Creature:
    """Build a plain creature for hazard-damage tests."""
    abilities = Abilities(
        strength=10,
        dexterity=10,
        constitution=10,
        intelligence=10,
        wisdom=10,
        charisma=10,
    )
    return Creature(name=name, max_hp=hp, ac=10, abilities=abilities)


class TestHazards_IntroFraming:
    """SRD § Playing the Game › Hazards › Intro framing.

    > Monsters are the main perils characters face, but other dangers
    > await. "Rules Glossary" defines the following hazards: ...
    """

    def test_hazards_catalog_is_finite_and_enumerated(self) -> None:
        """Source-level guard: the SRD lists exactly five hazards.

        The conformance file enumerates these explicitly so a future
        SRD revision that adds or removes a hazard surfaces here as a
        failing assertion rather than silently drifting from the
        document.
        """
        srd_doc = (
            Path(__file__).resolve().parents[3].parent
            / "docs"
            / "srd"
            / "playing-the-game"
            / "hazards.md"
        )
        body = srd_doc.read_text()
        for hazard in ("Burning", "Dehydration", "Falling", "Malnutrition", "Suffocation"):
            assert hazard in body, (
                f"Hazards SRD doc must enumerate {hazard!r}. If this "
                "fails, the SRD has been re-issued; bump the audit and "
                "issues #508/#509/#510/#512."
            )


class TestHazards_Burning:
    """SRD § Playing the Game › Hazards › Burning.

    > Burning [hazard, defined in Rules Glossary]

    Per the Rules Glossary, a creature subjected to the Burning hazard
    takes ongoing fire damage at the start of each of its turns until
    it ends the effect (typically a Dex check action to put out the
    flames). The engine models the personal `on_fire` *condition* but
    not the environmental *hazard zone* that would inflict it.
    """

    def test_on_fire_condition_is_catalogued(self) -> None:
        """`on_fire` is the engine's encoding of the SRD Burning rule.

        Data-parity check: `dnd_engine/data/srd/conditions.json` must
        carry an `on_fire` entry with a turn-start fire-damage effect
        and a Dex-check escape, matching the SRD's "burning" hazard
        shape.
        """
        conditions = json.loads(CONDITIONS_JSON.read_text())["conditions"]
        assert "on_fire" in conditions, (
            "Conditions catalog must declare `on_fire` so the SRD's "
            "Burning hazard has a real engine encoding."
        )
        on_fire = conditions["on_fire"]
        effect = on_fire.get("turn_start_effect", {})
        assert effect.get("type") == "damage"
        assert effect.get("damage_type") == "fire", (
            "Burning must deal fire-type damage per the SRD."
        )
        escape = on_fire.get("can_end_early", {})
        assert escape.get("method") == "ability_check"
        assert escape.get("ability") == "dexterity", (
            "SRD specifies the escape is a Dex check (douse the flames)."
        )

    def test_on_fire_damage_is_applied_at_turn_start(self) -> None:
        """`ConditionManager.process_turn_start_effects` applies the damage.

        End-to-end on the production path: a creature with `on_fire`
        takes fire damage on each turn-start tick, matching the SRD
        Burning hazard's "ongoing damage" shape.
        """
        manager = ConditionManager(dice_roller=DiceRoller(seed=42))
        creature = _make_creature(hp=20)
        creature.add_condition("on_fire")
        hp_before = creature.current_hp

        results = manager.process_turn_start_effects(creature)

        assert len(results) == 1
        assert results[0].condition_id == "on_fire"
        assert results[0].effect_type == "damage"
        assert 1 <= results[0].amount <= 4, "1d4 fire damage per SRD."
        assert creature.current_hp == hp_before - results[0].amount

    def test_environmental_burning_zone_applies_on_fire_on_entry(self) -> None:
        pytest.skip(
            "GAP: there is no environmental Burning hazard. The engine "
            "models `on_fire` as a personal *condition* applied by "
            "items (Alchemist's Fire via `systems/item_effects._apply_"
            "damage_effect`) but has no per-room or per-tile 'this "
            "area is on fire' data field. `GameState.move_to_room` "
            "does not consult any hazard list when a creature enters "
            "a room. The SRD's Hazards section treats Burning as an "
            "environment-level hazard, which the engine cannot "
            "represent. Tracked by issue #508."
        )

    def test_burning_hazard_severity_levels_are_data_driven(self) -> None:
        pytest.skip(
            "GAP: the SRD Rules Glossary entry for Burning carries "
            "severity tiers (e.g., 1d4 for a torch / brazier, 1d6+ for "
            "larger flames). The engine collapses this to a single "
            "hard-coded `damage: '1d4'` in `dnd_engine/data/srd/"
            "conditions.json:11`. There is no way to express a more "
            "severe burning hazard short of editing the condition "
            "data file. Tracked by issue #508."
        )


class TestHazards_Dehydration:
    """SRD § Playing the Game › Hazards › Dehydration.

    > Dehydration [hazard, defined in Rules Glossary]

    Per the Rules Glossary, a creature that does not drink enough
    water per day suffers levels of Exhaustion. Requires a long-
    duration day-tick tracker and an Exhaustion condition.
    """

    def test_dehydration_concept_exists_in_engine(self) -> None:
        pytest.skip(
            "GAP: Dehydration is not modeled. `rg -i 'dehydrat|thirst' "
            "dnd_engine/` returns zero matches. No per-creature "
            "water-intake tracker, no day-tick clock, no Exhaustion "
            "condition in `dnd_engine/data/srd/conditions.json` (only "
            "`on_fire` and `surprised` are catalogued). Tracked by "
            "issue #512."
        )

    def test_dehydration_imposes_exhaustion_levels(self) -> None:
        pytest.skip(
            "GAP: the Exhaustion condition does not exist as an "
            "engine concept. With no Exhaustion catalog entry there is "
            "no consequence layer for Dehydration to escalate into. "
            "Tracked by issue #512 (and a downstream Exhaustion "
            "issue if/when this lands)."
        )


class TestHazards_Falling:
    """SRD § Playing the Game › Hazards › Falling.

    > Falling [hazard, defined in Rules Glossary]

    Per the Rules Glossary, a creature that falls more than 10 ft
    takes 1d6 bludgeoning damage per 10 ft fallen (cap 20d6) and
    lands Prone.
    """

    def test_falling_damage_calculation_helper_exists(self) -> None:
        pytest.skip(
            "GAP: there is no `resolve_fall(distance_ft)` helper "
            "anywhere in `dnd_engine/`. `rg -i 'falling|fall_damage|"
            "fall_distance' dnd_engine/` returns only unrelated "
            "'fallback' matches. No falling system exists because no "
            "campaign content has verticality today — the 2D client "
            "is tile-grid with no z-axis. Tracked by issue #509."
        )

    def test_falling_applies_prone_condition(self) -> None:
        pytest.skip(
            "GAP: the Prone condition is not catalogued in "
            "`dnd_engine/data/srd/conditions.json` (only `on_fire` "
            "and `surprised`). Even if a fall helper existed, there is "
            "no Prone state to apply. Tracked by issue #509."
        )

    def test_falling_damage_is_bludgeoning_type(self) -> None:
        pytest.skip(
            "GAP: `Creature.take_damage` (`dnd_engine/core/creature.py`) "
            "accepts a raw `amount: int` with no `damage_type` "
            "parameter. Bludgeoning damage cannot be typed through the "
            "current API — every damage event is untyped at the "
            "creature-receive layer. Tracked by issues #509 (falling) "
            "and #461 (damage_type pipeline)."
        )


class TestHazards_Malnutrition:
    """SRD § Playing the Game › Hazards › Malnutrition.

    > Malnutrition [hazard, defined in Rules Glossary]

    Per the Rules Glossary, a creature that goes without food longer
    than its CON modifier of days begins accruing Exhaustion levels.
    """

    def test_malnutrition_concept_exists_in_engine(self) -> None:
        pytest.skip(
            "GAP: Malnutrition is not modeled. `rg -i 'malnutri|starv|"
            "rations' dnd_engine/` returns zero matches. No "
            "per-creature food-intake tracker, no day-tick clock. "
            "Same root gap as Dehydration. Tracked by issue #512."
        )

    def test_malnutrition_consumes_days_until_constitution_threshold(self) -> None:
        pytest.skip(
            "GAP: the SRD ties Malnutrition's grace period to the "
            "creature's CON modifier (creatures with high CON can "
            "skip more days without food). The engine has no "
            "per-creature day-counter and no daily tick hook to "
            "consult `creature.abilities.constitution`. Tracked by "
            "issue #512."
        )


class TestHazards_Suffocation:
    """SRD § Playing the Game › Hazards › Suffocation.

    > Suffocation [hazard, defined in Rules Glossary]

    Per the Rules Glossary, a creature can hold its breath for
    `1 + CON modifier` minutes (min 30 seconds). After that, on each
    turn it must make a CON save or drop to 0 HP. Cross-cuts the
    Underwater Combat section: a creature without a Swim Speed or
    Water Breathing eventually suffocates underwater.
    """

    def test_suffocation_concept_exists_in_engine(self) -> None:
        pytest.skip(
            "GAP: Suffocation is not modeled. `rg -i 'suffocat|drown|"
            "hold.breath' dnd_engine/` returns zero matches. No "
            "`breath_remaining_seconds` field on `Creature` or "
            "`Character`, no turn-start hook that decrements breath. "
            "Tracked by issue #510."
        )

    def test_water_breathing_capability_is_consumed_to_prevent_suffocation(self) -> None:
        pytest.skip(
            "GAP: `Capability.WATER_BREATHING` is declared "
            "(`dnd_engine/systems/capabilities.py:25`) but no code "
            "reads it — `rg 'WATER_BREATHING|water_breathing' "
            "dnd_engine/` returns only the declaration. The Water "
            "Breathing spell is not in `dnd_engine/data/srd/spells."
            "json`. Without a suffocation system there is nothing for "
            "this capability to gate. Tracked by issue #510."
        )

    def test_suffocation_forces_con_save_or_zero_hp(self) -> None:
        pytest.skip(
            "GAP: there is no auto-drop-to-0 path keyed on a failed "
            "CON save. The existing auto-fail logic — `GameState."
            "_apply_lighting_penalties` (`dnd_engine/core/game_state."
            "py:698-756`) — is hard-coded for sight-based Perception "
            "in darkness and is not a reusable 'auto-fail-and-apply-"
            "consequence' primitive. Tracked by issue #510."
        )


class TestHazards_EngineSurface_NoEnvironmentalHazardSystem:
    """Cross-cut: there is no environmental Hazard system at all.

    The SRD Hazards section presumes the engine can attach a hazard to
    a place (a room of fire, a stretch of desert, a flooded vault).
    The engine cannot. Pin the absence here so the moment a Hazard
    registry lands the next consumer can find it.
    """

    def test_room_data_can_declare_hazards(self) -> None:
        pytest.skip(
            "GAP: room schema in `dnd_engine/data/campaigns/` does not "
            "carry a `hazards` field. The Burning condition exists as "
            "a personal effect from items only; no campaign room "
            "inflicts it on entry. Tracked by issue #508 (Burning) — "
            "but the room-schema seam is shared by all five hazards "
            "and is the root architectural gap surfaced by this audit."
        )

    def test_game_state_applies_room_hazards_on_entry(self) -> None:
        pytest.skip(
            "GAP: `GameState.move_to_room` does not consult any "
            "hazard list when a creature enters a room. With no "
            "`hazards` schema on rooms and no application hook, all "
            "five SRD hazards have no entry point into the engine. "
            "Tracked by issue #508 (architectural seam shared across "
            "#508, #509, #510, #512)."
        )
