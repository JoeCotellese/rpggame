# ABOUTME: Tests for pc_entity_id helper validation and folding behavior.
# ABOUTME: Covers empty-name rejection and case/space normalization.

from __future__ import annotations

import pytest

from dnd_engine.core.entity_ids import pc_entity_id


class TestPCEntityIDValidation:
    """pc_entity_id rejects names that would produce an ambiguous id.

    Without validation the helper happily returned ``"pc_"`` for an
    empty string (or ``"pc___"`` for whitespace), which silently
    collided with every other unnamed PC in the spatial index.
    """

    def test_empty_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            pc_entity_id("")

    def test_whitespace_only_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            pc_entity_id("   ")

    def test_tab_only_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            pc_entity_id("\t\n")


class TestPCEntityIDFolding:
    """pc_entity_id normalizes case and spaces consistently.

    Two names that fold to the same id are intentionally indistinct
    in the spatial index — uniqueness enforcement lives at
    character-creation time, not here. These tests pin the fold so a
    refactor cannot drift the convention.
    """

    def test_simple_name_lowercases(self) -> None:
        assert pc_entity_id("Hero") == "pc_hero"

    def test_mixed_case_folds_to_lower(self) -> None:
        assert pc_entity_id("HERO") == "pc_hero"
        assert pc_entity_id("hero") == pc_entity_id("HERO")

    def test_spaces_become_underscores(self) -> None:
        assert pc_entity_id("Warrior Two") == "pc_warrior_two"

    def test_name_ending_in_digit_preserved(self) -> None:
        # Important: this id is what the humanizer must NOT digit-strip.
        assert pc_entity_id("Warrior 2") == "pc_warrior_2"
