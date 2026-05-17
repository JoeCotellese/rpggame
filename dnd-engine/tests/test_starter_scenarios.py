# ABOUTME: Smoke tests for the checked-in starter scenario YAML files.
# ABOUTME: Asserts each one loads with the documented party/enemy composition.

"""Loader tests against the shipped scenario fixtures (issue #361).

These tests catch the easy regressions: a starter scenario referencing
a renamed weapon, a removed monster, or a class/race that no longer
exists. They also confirm the schema reference in ``_schema.md`` stays
honest about what a valid scenario looks like.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_engine.scenarios import ScenarioLoader
from dnd_engine.systems.inventory import EquipmentSlot

SCENARIO_DIR = Path(__file__).parent / "scenarios" / "yaml"


def test_ranged_attack_basic_loads_with_expected_setup() -> None:
    result = ScenarioLoader().load(SCENARIO_DIR / "ranged_attack_basic.yaml")

    assert result.name == "ranged_attack_basic"
    assert result.seed == 42

    party = result.game_state.party
    assert len(party.characters) == 1
    archy = party.characters[0]
    assert archy.name == "Archy"
    assert archy.character_class.value.lower() == "fighter"
    assert archy.inventory.get_equipped_item(EquipmentSlot.WEAPON) == "shortbow"
    assert result.party_positions["pc_archy"] == (3, 5)

    assert len(result.game_state.active_enemies) == 1
    assert result.enemy_positions["goblin_0"] == (10, 5)
    assert result.game_state.in_combat is True


def test_ranged_out_of_range_loads_with_dagger_thrown_setup() -> None:
    result = ScenarioLoader().load(SCENARIO_DIR / "ranged_out_of_range.yaml")

    assert result.name == "ranged_out_of_range"

    archy = result.game_state.party.characters[0]
    assert archy.inventory.get_equipped_item(EquipmentSlot.WEAPON) == "dagger"
    assert result.party_positions["pc_archy"] == (3, 5)

    # 17 tiles between positions = 85 ft, past the dagger's 60 ft long
    # throw range. The scenario's whole point is exercising the
    # range-rejection path; if the positions ever drift inside long
    # range this assertion catches it.
    archy_x = result.party_positions["pc_archy"][0]
    goblin_x = result.enemy_positions["goblin_0"][0]
    tile_distance = abs(goblin_x - archy_x)
    feet = tile_distance * 5
    assert feet > 60, (
        f"Goblin must be past dagger long range (60 ft); got {feet} ft"
    )


@pytest.mark.parametrize(
    "scenario_file",
    sorted(p.name for p in SCENARIO_DIR.glob("*.yaml")),
)
def test_every_starter_scenario_loads(scenario_file: str) -> None:
    # Cheap belt-and-suspenders: any new YAML dropped in the directory
    # at least parses and builds a GameState. Detailed assertions live
    # in the per-scenario tests above.
    result = ScenarioLoader().load(SCENARIO_DIR / scenario_file)
    assert result.game_state is not None


def test_load_is_deterministic_across_reloads() -> None:
    # The schema documents `seed` as driving "all dice rolls
    # deterministically", which includes character creation HP / ability
    # rolls. Two loads of the same YAML must produce identical character
    # max_hp and ability scores.
    first = ScenarioLoader().load(SCENARIO_DIR / "ranged_attack_basic.yaml")
    second = ScenarioLoader().load(SCENARIO_DIR / "ranged_attack_basic.yaml")

    first_pc = first.game_state.party.characters[0]
    second_pc = second.game_state.party.characters[0]

    assert first_pc.max_hp == second_pc.max_hp, (
        f"max_hp drifted across reloads: {first_pc.max_hp} vs {second_pc.max_hp}"
    )
    assert first_pc.abilities.strength == second_pc.abilities.strength
    assert first_pc.abilities.dexterity == second_pc.abilities.dexterity
    assert first_pc.abilities.constitution == second_pc.abilities.constitution

    first_enemy = first.game_state.active_enemies[0]
    second_enemy = second.game_state.active_enemies[0]
    assert first_enemy.max_hp == second_enemy.max_hp
