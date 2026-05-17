# ABOUTME: Happy-path tests for the YAML scenario loader.
# ABOUTME: Asserts the loader builds GameState with the expected party, enemies, and seed.

"""Loader happy-path tests for issue #361.

The schema/validation failure paths live in
``test_scenario_schema_validation.py``. Tests here cover successful
loads: party construction, enemy spawning, combat activation, and seed
reproducibility.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_engine.scenarios import LoadedScenario, ScenarioLoader, ScenarioValidationError

# Reusable scenario body. Two members keeps tests honest about indexing
# while staying small enough that the YAML is easy to read inline.
SCENARIO_YAML = """
name: loader_smoke
seed: 7
map:
  dungeon: laboratory
  campaign: poisoned_laboratory
  start_room: laboratory.entrance
party:
  - class: fighter
    race: high_elf
    weapons: [shortbow]
    position: [3, 5]
    name: Archy
  - class: wizard
    race: human
    weapons: [dagger]
    position: [4, 5]
    name: Merlin
enemies:
  - monster_id: goblin
    position: [10, 5]
  - monster_id: giant_rat
    position: [11, 5]
"""


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "scenario.yaml"
    path.write_text(body.lstrip())
    return path


def test_load_returns_loaded_scenario_with_game_state(tmp_path: Path) -> None:
    path = _write(tmp_path, SCENARIO_YAML)

    result = ScenarioLoader().load(path)

    assert isinstance(result, LoadedScenario)
    assert result.name == "loader_smoke"
    assert result.seed == 7
    assert result.game_state is not None


def test_load_builds_party_with_classes_and_equipped_weapons(tmp_path: Path) -> None:
    from dnd_engine.systems.inventory import EquipmentSlot

    path = _write(tmp_path, SCENARIO_YAML)
    result = ScenarioLoader().load(path)

    party = result.game_state.party
    assert len(party.characters) == 2

    archy = party.characters[0]
    assert archy.name == "Archy"
    assert archy.character_class.value.lower() == "fighter"
    assert archy.inventory.get_equipped_item(EquipmentSlot.WEAPON) == "shortbow"

    merlin = party.characters[1]
    assert merlin.character_class.value.lower() == "wizard"
    assert merlin.inventory.get_equipped_item(EquipmentSlot.WEAPON) == "dagger"


def test_load_spawns_enemies_and_starts_combat(tmp_path: Path) -> None:
    path = _write(tmp_path, SCENARIO_YAML)
    result = ScenarioLoader().load(path)

    enemy_names = [e.name.lower() for e in result.game_state.active_enemies]
    assert any("goblin" in n for n in enemy_names)
    assert any("rat" in n for n in enemy_names)
    assert result.game_state.in_combat is True


def test_load_returns_positions_for_party_and_enemies(tmp_path: Path) -> None:
    path = _write(tmp_path, SCENARIO_YAML)
    result = ScenarioLoader().load(path)

    # Positions key by entity_id matching Phase 1's spawn convention:
    # pc_<name_snake> for party, <monster_id>_<index> for enemies.
    assert result.party_positions["pc_archy"] == (3, 5)
    assert result.party_positions["pc_merlin"] == (4, 5)
    assert result.enemy_positions["goblin_0"] == (10, 5)
    assert result.enemy_positions["giant_rat_1"] == (11, 5)


def test_same_seed_yields_identical_dice_sequence(tmp_path: Path) -> None:
    path = _write(tmp_path, SCENARIO_YAML)
    first = ScenarioLoader().load(path)
    second = ScenarioLoader().load(path)

    first_rolls = [first.game_state.dice_roller.roll("1d20").total for _ in range(5)]
    second_rolls = [second.game_state.dice_roller.roll("1d20").total for _ in range(5)]
    assert first_rolls == second_rolls


def test_unknown_monster_id_raises_validation_error(tmp_path: Path) -> None:
    bad = SCENARIO_YAML.replace("monster_id: goblin", "monster_id: dragon_overlord")
    path = _write(tmp_path, bad)

    with pytest.raises(ScenarioValidationError) as exc_info:
        ScenarioLoader().load(path)

    assert "dragon_overlord" in str(exc_info.value)


def test_unknown_class_raises_validation_error(tmp_path: Path) -> None:
    bad = SCENARIO_YAML.replace("class: fighter", "class: ranger")
    path = _write(tmp_path, bad)

    with pytest.raises(ScenarioValidationError) as exc_info:
        ScenarioLoader().load(path)

    assert "ranger" in str(exc_info.value)


def test_unknown_race_raises_validation_error(tmp_path: Path) -> None:
    bad = SCENARIO_YAML.replace("race: high_elf", "race: tabaxi")
    path = _write(tmp_path, bad)

    with pytest.raises(ScenarioValidationError) as exc_info:
        ScenarioLoader().load(path)

    assert "tabaxi" in str(exc_info.value)


def test_passthrough_script_and_assertions(tmp_path: Path) -> None:
    body = SCENARIO_YAML.rstrip() + (
        "\nscript:\n"
        "  - {action: move, direction: north}\n"
        "assertions:\n"
        "  - {kind: entity_hp, entity: goblin_0, op: lt, value: 7}\n"
    )
    path = _write(tmp_path, body)

    result = ScenarioLoader().load(path)
    assert result.script == [{"action": "move", "direction": "north"}]
    assert result.assertions == [
        {"kind": "entity_hp", "entity": "goblin_0", "op": "lt", "value": 7}
    ]
