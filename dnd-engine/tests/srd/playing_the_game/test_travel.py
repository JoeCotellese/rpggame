# ABOUTME: SRD conformance audit for "Playing the Game > Travel".
# ABOUTME: Cross-references docs/srd/playing-the-game/travel.md against engine code.

"""SRD conformance: Travel.

Maps every rule in `docs/srd/playing-the-game/travel.md` (SRD lines
1662-1733) to a test. Real tests verify enforcement at the engine
layer; stubs (`pytest.skip("GAP: ...")`) mark known gaps and cite where
the rule is enforced today (if elsewhere) or that it isn't implemented
anywhere.

The Travel section is almost entirely unimplemented in the engine today
— the game is dungeon-crawl-focused and overland travel is summarized
narratively. The bulk of the rules in this audit therefore land as
GAPs, with citations to four newly filed issues:

- #504  Travel pace (Fast/Normal/Slow) not modeled
- #505  Mounted travel doubles pace for 1 hour, then mount needs rest
- #506  Vehicles and waterborne travel not modeled
- #507  Travel pace does not gate Perception/Survival/Stealth advantage

The audit pins a few real anchors that do exist (combat-mode movement
rules are referenced by the SRD as the "every second matters" carve-out
below) so the cross-references stay live.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.systems.action_economy import TurnState

pytestmark = pytest.mark.srd(
    "playing-the-game/travel.md",
    lines="1662-1733",
)


SKILLS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "skills.json"
)
ITEMS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "items.json"
)


def _make_creature(*, speed: int = 30) -> Creature:
    """Plain Medium humanoid fixture for travel tests."""
    abilities = Abilities(
        strength=12,
        dexterity=12,
        constitution=12,
        intelligence=10,
        wisdom=12,
        charisma=10,
    )
    return Creature(name="Traveler", max_hp=10, ac=12, abilities=abilities, speed=speed)


class TestTravel_Intro:
    """SRD § Playing the Game › Travel › Intro.

    > During an adventure, the characters might travel long distances on
    > trips that could take hours or days. The GM can summarize this
    > travel without calculating exact distances or travel times, or the
    > GM might have you use the travel pace rules below.
    """

    def test_engine_has_no_overworld_travel_layer(self) -> None:
        pytest.skip(
            "GAP: there is no engine-side overworld / long-distance "
            "travel layer. The game flow is dungeon-room-to-dungeon-"
            "room (`GameState.move_to_room` and friends in "
            "`dnd-engine/dnd_engine/core/game_state.py`), and the "
            "cross-dungeon-travel comment in "
            "`dnd-engine/dnd_engine/core/save_slot_manager.py:488` "
            "treats inter-dungeon travel as a save-state transition, "
            "not a timed journey with distance, pace, or encounters. "
            "The SRD's 'GM might have you use the travel pace rules "
            "below' phrasing has no engine analog. Tracked by issue "
            "#504 and the umbrella architecture issue #28 ('Extend "
            "location system to support settlements, regions, and "
            "world navigation')."
        )

    def test_combat_mode_movement_is_the_explicit_carveout_for_short_distances(self) -> None:
        """The SRD cross-references "Combat" movement rules for short distances.

        > If you need to know how fast you can move when every second
        > matters, see the movement rules in "Combat".

        The combat movement rules referenced here *are* implemented —
        `TurnState.movement_remaining` (see
        `tests/srd/playing_the_game/test_movement_and_position.py`).
        Guarding the existence of that mechanic keeps the SRD cross-
        reference live: when overworld travel ships, it must defer to
        the combat-movement layer for second-by-second movement.
        """
        creature = _make_creature(speed=30)
        state = TurnState(movement_remaining=creature.speed)
        assert state.movement_remaining == 30, (
            "Combat-mode movement rules ('every second matters') must "
            "continue to seed the per-turn movement pool from a "
            "creature's Speed, since the Travel chapter explicitly "
            "defers to them."
        )


class TestTravel_PaceTable:
    """SRD § Playing the Game › Travel › Travel Pace table.

    > While traveling outside combat, a group can move at a Fast,
    > Normal, or Slow pace, as shown on the Travel Pace table.

    SRD pace rates (per minute / hour / day):

    | Pace   | Per Minute | Per Hour | Per Day  |
    |--------|------------|----------|----------|
    | Fast   | 400 ft     | 4 miles  | 30 miles |
    | Normal | 300 ft     | 3 miles  | 24 miles |
    | Slow   | 200 ft     | 2 miles  | 18 miles |
    """

    def test_travel_pace_enum_exists(self) -> None:
        pytest.skip(
            "GAP: no `TravelPace` enum / constant lives anywhere in "
            "`dnd-engine/dnd_engine/`. `rg -in 'travel|pace' "
            "dnd-engine/dnd_engine/ --type py` finds only unrelated "
            "phrasing ('traveling between dungeons' in save_slot_"
            "manager.py:488, 'fast-paced combat' in llm/prompts.py). "
            "No data file declares the per-minute/hour/day rates. "
            "Tracked by issue #504."
        )

    def test_pace_rates_match_srd_table(self) -> None:
        pytest.skip(
            "GAP: there is no `PACE_RATES` table or per-pace rate "
            "lookup. The SRD's 400/300/200 ft/min, 4/3/2 mi/hr, "
            "30/24/18 mi/day rates have no engine constant or JSON "
            "datum to be checked against. Tracked by issue #504."
        )

    def test_party_carries_active_travel_pace(self) -> None:
        pytest.skip(
            "GAP: `Party` (`dnd_engine/core/party.py`) has no "
            "`travel_pace` attribute. The active pace is the load-"
            "bearing piece of state for every other Travel-section "
            "rule (perception/stealth modifiers, vehicle/mount carve-"
            "outs). Tracked by issue #504."
        )


class TestTravel_FastPaceModifiers:
    """SRD § Playing the Game › Travel › Fast pace effect.

    > Fast. Traveling at a Fast pace imposes Disadvantage on a
    > traveler's Wisdom (Perception or Survival) and Dexterity
    > (Stealth) checks.
    """

    def test_perception_and_survival_and_stealth_exist_as_skills(self) -> None:
        """Data-parity: the three skills the Fast pace modifies are catalogued.

        The SRD's Fast-pace clause references Wisdom (Perception),
        Wisdom (Survival), and Dexterity (Stealth). Each must exist in
        `data/srd/skills.json` with the correct ability mapping for any
        later pace-modifier logic to bind to. Without this, the gap is
        twice as deep.
        """
        skills = json.loads(SKILLS_JSON.read_text())
        assert "perception" in skills, "Perception skill must be catalogued."
        assert skills["perception"]["ability"] == "wis", (
            "Perception must be a Wisdom skill (SRD: 'Wisdom (Perception)')."
        )
        assert "survival" in skills, "Survival skill must be catalogued."
        assert skills["survival"]["ability"] == "wis", (
            "Survival must be a Wisdom skill (SRD: 'Wisdom (Survival)')."
        )
        assert "stealth" in skills, "Stealth skill must be catalogued."
        assert skills["stealth"]["ability"] == "dex", (
            "Stealth must be a Dexterity skill (SRD: 'Dexterity (Stealth)')."
        )

    def test_fast_pace_imposes_disadvantage_on_perception(self) -> None:
        pytest.skip(
            "GAP: no caller of `Character.make_skill_check` "
            "(`dnd_engine/core/character.py:726`) derives its "
            "`disadvantage` flag from a travel pace. The method accepts "
            "the flag but there is no `pace_modifiers(pace, skill)` "
            "helper and no `Party.travel_pace` state to drive it. "
            "Tracked by issues #504 and #507."
        )

    def test_fast_pace_imposes_disadvantage_on_survival(self) -> None:
        pytest.skip(
            "GAP: same root cause as the Perception variant — no pace "
            "-> check modifier dispatch exists. Tracked by issues #504 "
            "and #507."
        )

    def test_fast_pace_imposes_disadvantage_on_stealth(self) -> None:
        pytest.skip(
            "GAP: same root cause. The only Stealth call site today is "
            "`GameState._check_for_surprise` "
            "(`dnd_engine/core/game_state.py:3014`), which fires "
            "before combat and does not consult any travel state. "
            "Tracked by issues #504 and #507."
        )


class TestTravel_NormalPaceModifiers:
    """SRD § Playing the Game › Travel › Normal pace effect.

    > Normal. Traveling at a Normal pace imposes Disadvantage on
    > Dexterity (Stealth) checks.
    """

    def test_normal_pace_imposes_disadvantage_on_stealth(self) -> None:
        pytest.skip(
            "GAP: no pace -> check modifier dispatch exists. Without a "
            "`Party.travel_pace` and a `pace_modifiers` helper, the "
            "Normal-pace Stealth penalty cannot be applied. Tracked by "
            "issues #504 and #507."
        )

    def test_normal_pace_does_not_modify_perception_or_survival(self) -> None:
        pytest.skip(
            "GAP: the SRD's Normal pace carve-out (no Perception / "
            "Survival modifier) needs a default 'no modifier' branch "
            "in the pace-modifier helper. Without that helper "
            "(issue #507), there is nothing to encode the default. "
            "Tracked by issue #507."
        )


class TestTravel_SlowPaceModifiers:
    """SRD § Playing the Game › Travel › Slow pace effect.

    > Slow. Traveling at a Slow pace grants Advantage on Wisdom
    > (Perception or Survival) checks.
    """

    def test_slow_pace_grants_advantage_on_perception(self) -> None:
        pytest.skip(
            "GAP: `Character.make_skill_check` accepts an `advantage` "
            "flag, but no caller derives it from a Slow travel pace. "
            "No `Party.travel_pace` exists. Tracked by issues #504 "
            "and #507."
        )

    def test_slow_pace_grants_advantage_on_survival(self) -> None:
        pytest.skip(
            "GAP: same root cause as the Slow/Perception variant. "
            "Tracked by issues #504 and #507."
        )

    def test_slow_pace_does_not_modify_stealth(self) -> None:
        pytest.skip(
            "GAP: the SRD's Slow-pace carve-out (Advantage on "
            "Perception/Survival, no Stealth penalty) needs a pace-"
            "modifier helper that returns `(advantage=True, "
            "disadvantage=False)` for Perception/Survival and "
            "`(False, False)` for Stealth. None exists. Tracked by "
            "issue #507."
        )


class TestTravel_MountedTravel:
    """SRD § Playing the Game › Travel › Mounted travel.

    > ...if riding horses or other mounts, the group can move twice
    > that distance for 1 hour, after which the mounts need a Short or
    > Long Rest before they can move at that increased pace again (see
    > "Equipment" for a selection of mounts for sale).
    """

    def test_mount_catalog_exists(self) -> None:
        pytest.skip(
            "GAP: no mount entries exist. `jq '.equipment | keys[]' "
            "dnd-engine/dnd_engine/data/srd/items.json` returns no "
            "horses, ponies, mules, riding dogs, or any other mount. "
            "The string 'horse' appears only as flavor text in a "
            "campaign room description "
            "(`data/content/campaigns/the_unquiet_dead/dungeons/"
            "town_of_arden.json:38`). Tracked by issue #505."
        )

    def test_mounted_travel_doubles_pace_distance_for_one_hour(self) -> None:
        pytest.skip(
            "GAP: depends on travel pace existing (#504) and on mounts "
            "existing (#505). The SRD's 'twice that distance for 1 "
            "hour' clause has nothing to multiply and no mount-rest "
            "cooldown to track. Tracked by issue #505."
        )

    def test_mounts_need_short_or_long_rest_after_one_hour_at_double_pace(self) -> None:
        pytest.skip(
            "GAP: rest mechanics exist on Character "
            "(`Character.take_short_rest` -> "
            "`dnd-engine/dnd_engine/core/character.py:1202`, "
            "`take_long_rest` -> :1236), but Creature does not "
            "participate in them, and there is no Mount model with a "
            "fatigue counter that those rests would reset. Tracked by "
            "issue #505."
        )


class TestTravel_Vehicles_LandVehicles:
    """SRD § Playing the Game › Travel › Land vehicles.

    > Travelers in wagons, carriages, or other land vehicles choose a
    > pace as normal.
    """

    def test_land_vehicle_catalog_exists(self) -> None:
        pytest.skip(
            "GAP: no land vehicle entries exist in items.json. "
            "`jq '.equipment | keys[]' dnd-engine/dnd_engine/data/srd/"
            "items.json | rg -i 'wagon|cart|carriage'` returns no "
            "matches. Tracked by issue #506."
        )

    def test_land_vehicle_riders_still_choose_pace(self) -> None:
        pytest.skip(
            "GAP: depends on travel pace existing (#504) and on land "
            "vehicles existing (#506). The SRD's carve-out that land-"
            "vehicle riders 'choose a pace as normal' has no enforcement "
            "surface because neither side of the conditional exists yet. "
            "Tracked by issue #506."
        )


class TestTravel_Vehicles_WaterborneVessels:
    """SRD § Playing the Game › Travel › Waterborne vessels.

    > Characters in a waterborne vessel are limited to the speed of the
    > vessel, and they don't choose a travel pace. Depending on the
    > vessel and the size of the crew, ships might be able to travel
    > for up to 24 hours per day.
    """

    def test_waterborne_vessel_catalog_exists(self) -> None:
        pytest.skip(
            "GAP: no waterborne vessel entries exist in items.json. "
            "`jq '.equipment | keys[]' dnd-engine/dnd_engine/data/srd/"
            "items.json | rg -i 'boat|ship|vessel|rowboat'` returns "
            "no matches. Tracked by issue #506."
        )

    def test_waterborne_vessel_locks_pace_to_vessel_speed(self) -> None:
        pytest.skip(
            "GAP: depends on pace (#504) and vehicles (#506) existing. "
            "The SRD's 'limited to the speed of the vessel, and they "
            "don't choose a travel pace' clause needs a vessel speed "
            "attribute and a pace-selection guard that consults it. "
            "Neither exists. Tracked by issue #506."
        )

    def test_waterborne_vessel_can_travel_up_to_24_hours_per_day(self) -> None:
        pytest.skip(
            "GAP: there is no day-length / journey-time model that a "
            "vessel could opt into. The TimeManager (`dnd_engine/"
            "systems/time_manager.py`) tracks combat-rounds and spell "
            "durations but not multi-hour overland journey segments. "
            "Tracked by issue #506."
        )


class TestTravel_Coverage:
    """Coverage map: SRD rules <-> tests in this file.

    Maintainer index. Update both columns when adding a rule.

    | SRD rule (travel.md)                                                 | Test                                    |
    |----------------------------------------------------------------------|-----------------------------------------|
    | Intro: GM may summarize OR use travel pace rules                     | TestTravel_Intro                        |
    | Cross-ref: 'every second matters' -> combat movement rules           | TestTravel_Intro                        |
    | Travel Pace table (Fast/Normal/Slow, ft/min, mi/hr, mi/day)          | TestTravel_PaceTable                    |
    | Fast pace: Disadv on Perception, Survival, Stealth                   | TestTravel_FastPaceModifiers            |
    | Normal pace: Disadv on Stealth only                                  | TestTravel_NormalPaceModifiers          |
    | Slow pace: Adv on Perception, Survival                               | TestTravel_SlowPaceModifiers            |
    | Mounted travel: double pace for 1 hr, then mount rests               | TestTravel_MountedTravel                |
    | Land vehicles: riders choose pace as normal                          | TestTravel_Vehicles_LandVehicles        |
    | Waterborne vessels: locked to vessel speed, up to 24 hr/day          | TestTravel_Vehicles_WaterborneVessels   |

    Gap issues filed for this audit:
    - #504  Travel pace (Fast/Normal/Slow) not modeled
    - #505  Mounted travel doubles pace for 1 hour, then mount needs rest
    - #506  Vehicles and waterborne travel not modeled
    - #507  Travel pace does not gate Perception/Survival/Stealth advantage
    """

    def test_coverage_map_present(self) -> None:
        """Sanity check: this class's docstring carries the rule->test map."""
        assert TestTravel_Coverage.__doc__ is not None
        assert "SRD rule" in TestTravel_Coverage.__doc__
        assert "Travel Pace table" in TestTravel_Coverage.__doc__
        assert "#504" in TestTravel_Coverage.__doc__
