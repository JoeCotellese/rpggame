# ABOUTME: Unit tests for the AI pipeline registry + decide() (#647 commit 3).
# ABOUTME: Asserts strategy lookup fallback and Intent shape under varied contexts.

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.position import Position
from dnd_engine.systems.ai import pipeline
from dnd_engine.systems.ai.context import TurnContext
from dnd_engine.systems.ai.intent import MoveStep, WaitStep
from dnd_engine.systems.ai.strategies.aggressive import AggressiveAdvance


@dataclass
class _StubState:
    data_loader: Any = None


def _make_creature(name: str, x: int, y: int, speed: int = 30) -> Creature:
    c = Creature(
        name=name,
        max_hp=20,
        ac=15,
        abilities=Abilities(
            strength=10, dexterity=10, constitution=10,
            intelligence=10, wisdom=10, charisma=10,
        ),
        speed=speed,
    )
    c.position = Position(x, y)
    return c


SCIMITAR = {"name": "Scimitar", "reach": "5 ft.", "damage": "1d6", "attack_bonus": 4}


class TestGetStrategy:
    def test_returns_registered_strategy(self):
        strategy = pipeline.get_strategy("aggressive")
        assert isinstance(strategy, AggressiveAdvance)

    def test_unknown_name_falls_back_to_default(self, caplog):
        with caplog.at_level(logging.WARNING, logger="dnd_engine.systems.ai.pipeline"):
            strategy = pipeline.get_strategy("nonexistent")
        assert isinstance(strategy, AggressiveAdvance)
        assert any("nonexistent" in rec.message for rec in caplog.records)


class TestDecide:
    def test_no_targets_yields_wait_step(self):
        actor = _make_creature("Goblin", 0, 0)
        ctx = TurnContext.build(
            _StubState(), actor,
            target_pool=[],
            monster_data={"actions": [SCIMITAR]},
        )
        intent = pipeline.decide(ctx)
        assert len(intent.steps) == 1
        assert isinstance(intent.steps[0], WaitStep)
        assert intent.steps[0].reason == "no_targets"

    def test_already_in_reach_yields_empty_intent(self):
        actor = _make_creature("Goblin", 0, 0)
        target = _make_creature("Brick", 1, 0)
        ctx = TurnContext.build(
            _StubState(), actor,
            target_pool=[target],
            monster_data={"actions": [SCIMITAR]},
        )
        intent = pipeline.decide(ctx)
        assert intent.steps == []

    def test_out_of_reach_yields_move_step(self):
        actor = _make_creature("Goblin", 0, 0)
        target = _make_creature("Brick", 5, 0)
        ctx = TurnContext.build(
            _StubState(), actor,
            target_pool=[target],
            monster_data={"actions": [SCIMITAR]},
        )
        intent = pipeline.decide(ctx)
        assert len(intent.steps) == 1
        assert isinstance(intent.steps[0], MoveStep)
        assert intent.steps[0].path == [
            Position(1, 0), Position(2, 0), Position(3, 0), Position(4, 0),
        ]

    def test_ranged_action_yields_no_movement(self):
        actor = _make_creature("Goblin", 0, 0)
        target = _make_creature("Brick", 5, 0)
        ranged = {"name": "Shortbow", "range": "80/320 ft.", "damage": "1d6", "attack_bonus": 4}
        ctx = TurnContext.build(
            _StubState(), actor,
            target_pool=[target],
            monster_data={"actions": [ranged]},
        )
        intent = pipeline.decide(ctx)
        assert intent.steps == []

    def test_no_action_data_yields_empty_intent(self):
        actor = _make_creature("Goblin", 0, 0)
        target = _make_creature("Brick", 5, 0)
        ctx = TurnContext.build(
            _StubState(), actor,
            target_pool=[target],
            monster_data={},
        )
        intent = pipeline.decide(ctx)
        assert intent.steps == []

    def test_tie_break_by_name_when_two_equidistant(self):
        actor = _make_creature("Goblin", 0, 0)
        # "Alice" alphabetically precedes "Brick".
        alice = _make_creature("Alice", 5, 0)
        brick = _make_creature("Brick", 5, 0)
        ctx = TurnContext.build(
            _StubState(), actor,
            target_pool=[brick, alice],
            monster_data={"actions": [SCIMITAR]},
        )
        intent = pipeline.decide(ctx)
        assert isinstance(intent.steps[0], MoveStep)
        assert "Alice" in intent.rationale

    def test_unknown_strategy_in_monster_data_falls_back(self, caplog):
        actor = _make_creature("Goblin", 0, 0)
        target = _make_creature("Brick", 5, 0)
        ctx = TurnContext.build(
            _StubState(), actor,
            target_pool=[target],
            monster_data={
                "actions": [SCIMITAR],
                "ai": {"movement_strategy": "nonexistent_strategy"},
            },
        )
        with caplog.at_level(logging.WARNING, logger="dnd_engine.systems.ai.pipeline"):
            intent = pipeline.decide(ctx)
        # Still produces a movement path via the fallback strategy.
        assert len(intent.steps) == 1
        assert isinstance(intent.steps[0], MoveStep)
        assert any("nonexistent_strategy" in rec.message for rec in caplog.records)


class TestExecuteEmptyIntent:
    """`execute` with an empty Intent is a no-op — sanity for the WaitStep / already-in-reach paths."""

    def test_empty_intent_yields_zero_movement(self):
        actor = _make_creature("Goblin", 0, 0)

        @dataclass
        class _StubSpatial:
            def occupant_at(self, _pos):  # noqa: ANN001
                return None

        @dataclass
        class _StubGameState:
            spatial: Any = None

        from dnd_engine.systems.ai.intent import Intent
        result = pipeline.execute(
            Intent(steps=[]),
            _StubGameState(spatial=_StubSpatial()),
            actor,
            reach_ft=5,
            target_pool=[],
        )
        assert result.moved_squares == 0
        assert result.final_position == Position(0, 0)
