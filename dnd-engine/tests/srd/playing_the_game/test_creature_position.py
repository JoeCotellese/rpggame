# ABOUTME: Tests Creature.position kwarg threading for plan-03 phase 1.
# ABOUTME: Verifies the nullable position field defaults to None and accepts a Position.

from __future__ import annotations

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.position import Position
from dnd_engine.rules.loader import DataLoader


def _abilities() -> Abilities:
    return Abilities(10, 10, 10, 10, 10, 10)


class TestCreaturePositionDefault:
    """A Creature constructed without a position has `position is None`."""

    def test_bare_creature_has_none_position(self) -> None:
        creature = Creature(name="x", max_hp=10, ac=10, abilities=_abilities())
        assert creature.position is None


class TestCreaturePositionExplicit:
    """Passing `position=Position(...)` stores the supplied Position verbatim."""

    def test_explicit_position_is_stored(self) -> None:
        pos = Position(3, 4)
        creature = Creature(
            name="x",
            max_hp=10,
            ac=10,
            abilities=_abilities(),
            position=pos,
        )
        assert creature.position == Position(3, 4)


class TestCreaturePositionBackcompat:
    """Existing callers that omit `position` (e.g., monsters.json via DataLoader) still work."""

    def test_data_loader_goblin_has_none_position(self) -> None:
        loader = DataLoader()
        goblin = loader.create_monster("goblin")
        assert goblin.position is None
