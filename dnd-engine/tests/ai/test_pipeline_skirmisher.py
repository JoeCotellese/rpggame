# ABOUTME: Pipeline tests for the Skirmisher strategy (#649).
# ABOUTME: Covers decide() Intent shape and execute() AttackStep/retreat orchestration.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.position import Position
from dnd_engine.systems.ai import pipeline
from dnd_engine.systems.ai.context import TurnContext
from dnd_engine.systems.ai.intent import AttackStep, MoveStep
from dnd_engine.systems.ai.strategies.skirmisher import Skirmisher


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
SKIRMISHER_DATA = {"actions": [SCIMITAR], "ai": {"movement_strategy": "skirmisher"}}


class TestSkirmisherRegistered:
    def test_registry_has_skirmisher(self):
        strategy = pipeline.get_strategy("skirmisher")
        assert isinstance(strategy, Skirmisher)


class TestDecideSkirmisher:
    """When monster_data names skirmisher, decide() emits the 3-step Intent."""

    def test_close_attack_retreat_when_out_of_reach(self):
        actor = _make_creature("Goblin", 5, 5)
        target = _make_creature("Brick", 5, 10)
        ctx = TurnContext.build(
            _StubState(), actor,
            target_pool=[target],
            monster_data=SKIRMISHER_DATA,
        )
        intent = pipeline.decide(ctx)
        assert len(intent.steps) == 3
        assert isinstance(intent.steps[0], MoveStep)
        assert intent.steps[0].path == [
            Position(5, 6), Position(5, 7), Position(5, 8), Position(5, 9),
        ]
        assert isinstance(intent.steps[1], AttackStep)
        assert intent.steps[1].target_id == "Brick"
        assert intent.steps[1].action == SCIMITAR
        assert isinstance(intent.steps[2], MoveStep)
        # Greedy retreat away from (5,10): one tile (5,8) breaks reach 5.
        assert intent.steps[2].path == [Position(5, 8)]
        assert "skirmish" in intent.rationale.lower()

    def test_two_steps_when_close_budget_exhausts_speed(self):
        # Speed 30 → 6-tile budget. Target at (7,0) = 35 ft away. Close
        # walks the full 6 tiles to (6,0) (5 ft from target → in reach),
        # leaving zero budget for retreat.
        actor = _make_creature("Goblin", 0, 0, speed=30)
        target = _make_creature("Brick", 7, 0)
        ctx = TurnContext.build(
            _StubState(), actor,
            target_pool=[target],
            monster_data=SKIRMISHER_DATA,
        )
        intent = pipeline.decide(ctx)
        assert len(intent.steps) == 2
        assert isinstance(intent.steps[0], MoveStep)
        assert intent.steps[0].path == [
            Position(1, 0), Position(2, 0), Position(3, 0),
            Position(4, 0), Position(5, 0), Position(6, 0),
        ]
        assert isinstance(intent.steps[1], AttackStep)

    def test_attack_then_retreat_when_already_in_reach(self):
        # Goblin starts adjacent — no close phase needed, but it should
        # still attack and retreat.
        actor = _make_creature("Goblin", 5, 9)
        target = _make_creature("Brick", 5, 10)
        ctx = TurnContext.build(
            _StubState(), actor,
            target_pool=[target],
            monster_data=SKIRMISHER_DATA,
        )
        intent = pipeline.decide(ctx)
        assert len(intent.steps) == 2
        assert isinstance(intent.steps[0], AttackStep)
        assert intent.steps[0].target_id == "Brick"
        assert isinstance(intent.steps[1], MoveStep)
        assert intent.steps[1].path == [Position(5, 8)]


class TestDecideAggressiveStillWorks:
    """Backstop: aggressive monsters get the same single-MoveStep Intent."""

    def test_aggressive_out_of_reach_emits_single_move(self):
        actor = _make_creature("Bandit", 0, 0)
        target = _make_creature("Brick", 5, 0)
        ctx = TurnContext.build(
            _StubState(), actor,
            target_pool=[target],
            monster_data={"actions": [SCIMITAR]},
        )
        intent = pipeline.decide(ctx)
        assert len(intent.steps) == 1
        assert isinstance(intent.steps[0], MoveStep)

    def test_aggressive_already_in_reach_emits_empty(self):
        actor = _make_creature("Bandit", 0, 0)
        target = _make_creature("Brick", 1, 0)
        ctx = TurnContext.build(
            _StubState(), actor,
            target_pool=[target],
            monster_data={"actions": [SCIMITAR]},
        )
        intent = pipeline.decide(ctx)
        assert intent.steps == []
