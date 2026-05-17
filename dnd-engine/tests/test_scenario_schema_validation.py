# ABOUTME: Schema validation tests for the YAML scenario loader.
# ABOUTME: Covers required-field, wrong-type, and malformed-YAML failure paths.

"""Validation-side tests for ScenarioLoader.

The happy paths live in ``test_scenario_loader.py``. Tests here all expect
``ScenarioValidationError`` with actionable messages — every error must
mention the offending key (or path) so a human can fix the YAML.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_engine.scenarios import ScenarioLoader, ScenarioValidationError


def _minimal_valid_yaml() -> str:
    """Return a minimal valid scenario YAML body.

    Used as a base that individual tests mutate (drop a key, break a type)
    so each test exercises exactly one validation failure mode.
    """
    return (
        "name: minimal\n"
        "seed: 1\n"
        "map:\n"
        "  dungeon: laboratory\n"
        "  campaign: poisoned_laboratory\n"
        "party:\n"
        "  - class: fighter\n"
        "    race: high_elf\n"
        "    weapons: [shortbow]\n"
        "    position: [3, 5]\n"
        "enemies:\n"
        "  - monster_id: goblin\n"
        "    position: [10, 5]\n"
    )


def _write_yaml(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "scenario.yaml"
    path.write_text(body)
    return path


@pytest.mark.parametrize(
    "missing_key",
    ["name", "seed", "map", "party", "enemies"],
)
def test_missing_required_top_level_key_raises(tmp_path: Path, missing_key: str) -> None:
    body = _minimal_valid_yaml()
    # Drop the line(s) for this key. Using a simple line filter is fine
    # because the minimal YAML keeps each top-level key on its own line.
    lines = body.splitlines()
    kept: list[str] = []
    skip_indent = False
    for line in lines:
        if line.startswith(f"{missing_key}:"):
            skip_indent = True
            continue
        if skip_indent and (line.startswith(" ") or line.startswith("-")):
            continue
        skip_indent = False
        kept.append(line)
    path = _write_yaml(tmp_path, "\n".join(kept) + "\n")

    with pytest.raises(ScenarioValidationError) as exc_info:
        ScenarioLoader().load(path)

    assert missing_key in str(exc_info.value)


def test_party_must_be_a_list(tmp_path: Path) -> None:
    body = _minimal_valid_yaml().replace(
        "party:\n  - class: fighter\n    race: high_elf\n"
        "    weapons: [shortbow]\n    position: [3, 5]\n",
        "party: not-a-list\n",
    )
    path = _write_yaml(tmp_path, body)

    with pytest.raises(ScenarioValidationError) as exc_info:
        ScenarioLoader().load(path)

    assert "party" in str(exc_info.value)
    assert "list" in str(exc_info.value).lower()


def test_position_must_be_two_ints(tmp_path: Path) -> None:
    body = _minimal_valid_yaml().replace("position: [3, 5]", "position: [3]")
    path = _write_yaml(tmp_path, body)

    with pytest.raises(ScenarioValidationError) as exc_info:
        ScenarioLoader().load(path)

    assert "position" in str(exc_info.value)


def test_malformed_yaml_raises_with_path(tmp_path: Path) -> None:
    path = _write_yaml(tmp_path, "name: minimal\n  not-indented-properly\n: [1, 2\n")

    with pytest.raises(ScenarioValidationError) as exc_info:
        ScenarioLoader().load(path)

    # Error message should mention the file so the human can find it.
    assert str(path) in str(exc_info.value) or path.name in str(exc_info.value)


def test_missing_file_raises_validation_error(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yaml"

    with pytest.raises(ScenarioValidationError) as exc_info:
        ScenarioLoader().load(missing)

    assert "nope.yaml" in str(exc_info.value)
