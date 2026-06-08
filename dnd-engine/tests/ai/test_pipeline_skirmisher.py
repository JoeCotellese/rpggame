# ABOUTME: Pipeline tests for the Skirmisher strategy (#649).
# ABOUTME: Covers decide() Intent shape and execute() AttackStep/retreat orchestration.

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

from dnd_engine.core.combat import AttackResult
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.move_result import MoveResult
from dnd_engine.core.position import Position
from dnd_engine.systems.ai import pipeline
from dnd_engine.systems.ai.context import TurnContext
from dnd_engine.systems.ai.intent import AttackStep, Intent, MoveStep
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
            strength=10,
            dexterity=10,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
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
            _StubState(),
            actor,
            target_pool=[target],
            monster_data=SKIRMISHER_DATA,
        )
        intent = pipeline.decide(ctx)
        assert len(intent.steps) == 3
        assert isinstance(intent.steps[0], MoveStep)
        assert intent.steps[0].path == [
            Position(5, 6),
            Position(5, 7),
            Position(5, 8),
            Position(5, 9),
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
            _StubState(),
            actor,
            target_pool=[target],
            monster_data=SKIRMISHER_DATA,
        )
        intent = pipeline.decide(ctx)
        assert len(intent.steps) == 2
        assert isinstance(intent.steps[0], MoveStep)
        assert intent.steps[0].path == [
            Position(1, 0),
            Position(2, 0),
            Position(3, 0),
            Position(4, 0),
            Position(5, 0),
            Position(6, 0),
        ]
        assert isinstance(intent.steps[1], AttackStep)

    def test_attack_then_retreat_when_already_in_reach(self):
        # Goblin starts adjacent — no close phase needed, but it should
        # still attack and retreat.
        actor = _make_creature("Goblin", 5, 9)
        target = _make_creature("Brick", 5, 10)
        ctx = TurnContext.build(
            _StubState(),
            actor,
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
            _StubState(),
            actor,
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
            _StubState(),
            actor,
            target_pool=[target],
            monster_data={"actions": [SCIMITAR]},
        )
        intent = pipeline.decide(ctx)
        assert intent.steps == []


# ---------- execute() tests ----------


@dataclass
class _StubSpatial:
    occupants: dict[Position, str] = field(default_factory=dict)

    def occupant_at(self, pos: Position) -> str | None:
        return self.occupants.get(pos)


@dataclass
class _StubGameState:
    """Stub state that scripts attempt_combat_step results in order."""

    spatial: _StubSpatial = field(default_factory=_StubSpatial)
    step_results: list[MoveResult] = field(default_factory=list)
    enemy: Creature | None = None
    on_each_step: Any = None  # callable hook, e.g., flip enemy.is_alive

    def attempt_combat_step(self, entity_id: str, dx: int, dy: int) -> MoveResult:
        result = self.step_results.pop(0)
        if result.ok and result.position is not None and self.enemy is not None:
            self.enemy.position = result.position
        if self.on_each_step is not None:
            self.on_each_step(entity_id, dx, dy)
        return result


def _ok_step(pos: Position) -> MoveResult:
    return MoveResult(ok=True, reason=None, position=pos, movement_remaining=25)


def _attack_outcome(hit: bool = True, damage: int = 5) -> AttackResult:
    return AttackResult(
        attacker_name="Goblin",
        defender_name="Brick",
        attack_roll=15,
        attack_bonus=4,
        target_ac=15,
        hit=hit,
        damage=damage,
        critical_hit=False,
        advantage=False,
        disadvantage=False,
    )


class TestExecuteAttackStep:
    """execute() routes AttackStep through the supplied attack_resolver."""

    def test_resolver_called_with_actor_target_id_and_action(self):
        actor = _make_creature("Goblin", 5, 9)
        target = _make_creature("Brick", 5, 10)
        spatial = _StubSpatial(occupants={Position(5, 9): "goblin_0"})
        state = _StubGameState(spatial=spatial, enemy=actor)
        resolver = MagicMock(return_value=_attack_outcome())

        intent = Intent(steps=[AttackStep(target_id="Brick", action=SCIMITAR)])
        result = pipeline.execute(
            intent,
            state,
            actor,
            reach_ft=5,
            target_pool=[target],
            attack_resolver=resolver,
        )

        resolver.assert_called_once_with(actor, "Brick", SCIMITAR)
        assert result.attack_outcome is not None
        assert result.attack_outcome.hit is True

    def test_skips_retreat_when_attack_kills_target(self):
        actor = _make_creature("Goblin", 5, 9)
        target = _make_creature("Brick", 5, 10)
        spatial = _StubSpatial(occupants={Position(5, 9): "goblin_0"})
        state = _StubGameState(spatial=spatial, enemy=actor)

        def killer(_actor: Creature, _tid: str, _action: dict) -> AttackResult:
            target.current_hp = 0  # kill the target
            return _attack_outcome(damage=20)

        intent = Intent(
            steps=[
                AttackStep(target_id="Brick", action=SCIMITAR),
                MoveStep(path=[Position(5, 8)]),
            ]
        )
        result = pipeline.execute(
            intent,
            state,
            actor,
            reach_ft=5,
            target_pool=[target],
            attack_resolver=killer,
        )

        assert result.stopped_reason == "target_killed_no_retreat"
        assert result.moved_squares == 0
        assert result.attack_outcome is not None

    def test_attackstep_without_resolver_logs_warning_and_continues(self, caplog):
        actor = _make_creature("Goblin", 5, 9)
        target = _make_creature("Brick", 5, 10)
        spatial = _StubSpatial(occupants={Position(5, 9): "goblin_0"})
        state = _StubGameState(
            spatial=spatial,
            enemy=actor,
            step_results=[_ok_step(Position(5, 8))],
        )

        intent = Intent(
            steps=[
                AttackStep(target_id="Brick", action=SCIMITAR),
                MoveStep(path=[Position(5, 8)]),
            ]
        )
        with caplog.at_level(logging.WARNING, logger="dnd_engine.systems.ai.pipeline"):
            result = pipeline.execute(
                intent,
                state,
                actor,
                reach_ft=5,
                target_pool=[target],
                attack_resolver=None,
            )

        assert result.attack_outcome is None
        # Retreat still walked despite missing resolver.
        assert result.moved_squares == 1
        assert any("attack_resolver" in rec.message for rec in caplog.records)


class TestExecuteFullSkirmish:
    """A complete close → attack → retreat sequence."""

    def test_completes_all_phases(self):
        actor = _make_creature("Goblin", 5, 5)
        target = _make_creature("Brick", 5, 10)
        spatial = _StubSpatial(occupants={Position(5, 5): "goblin_0"})
        state = _StubGameState(
            spatial=spatial,
            enemy=actor,
            step_results=[
                # Close phase: 4 tiles to (5, 9).
                _ok_step(Position(5, 6)),
                _ok_step(Position(5, 7)),
                _ok_step(Position(5, 8)),
                _ok_step(Position(5, 9)),
                # Retreat phase: 1 tile back to (5, 8).
                _ok_step(Position(5, 8)),
            ],
        )
        resolver = MagicMock(return_value=_attack_outcome())

        intent = Intent(
            steps=[
                MoveStep(
                    path=[
                        Position(5, 6),
                        Position(5, 7),
                        Position(5, 8),
                        Position(5, 9),
                    ]
                ),
                AttackStep(target_id="Brick", action=SCIMITAR),
                MoveStep(path=[Position(5, 8)]),
            ]
        )
        result = pipeline.execute(
            intent,
            state,
            actor,
            reach_ft=5,
            target_pool=[target],
            attack_resolver=resolver,
        )

        assert result.moved_squares == 5
        assert result.attack_outcome is not None
        assert result.stopped_reason == "retreated"
        assert state.step_results == []  # all scripted steps consumed
        resolver.assert_called_once()

    def test_stops_when_enemy_dies_during_retreat(self):
        actor = _make_creature("Goblin", 5, 9)
        target = _make_creature("Brick", 5, 10)
        spatial = _StubSpatial(occupants={Position(5, 9): "goblin_0"})

        def kill_after_first_retreat(_eid: str, _dx: int, _dy: int) -> None:
            actor.current_hp = 0

        state = _StubGameState(
            spatial=spatial,
            enemy=actor,
            step_results=[
                _ok_step(Position(5, 8)),  # first retreat step (OA kills)
                _ok_step(Position(5, 7)),  # would be 2nd step (should not run)
            ],
            on_each_step=kill_after_first_retreat,
        )
        resolver = MagicMock(return_value=_attack_outcome())

        intent = Intent(
            steps=[
                AttackStep(target_id="Brick", action=SCIMITAR),
                MoveStep(path=[Position(5, 8), Position(5, 7)]),
            ]
        )
        result = pipeline.execute(
            intent,
            state,
            actor,
            reach_ft=5,
            target_pool=[target],
            attack_resolver=resolver,
        )

        assert result.stopped_reason == "enemy_died_mid_retreat"
        assert result.moved_squares == 1
        # Second tile MUST NOT be walked.
        assert len(state.step_results) == 1


class TestExecuteAntiStuckGuardScope:
    """The 2-consecutive-failures guard is per-MoveStep, not lifetime.

    Regression for a bug where a failed step in the close phase poisoned
    the retreat phase: one more failed retreat step would trip the guard
    and exit with `stopped_reason="blocked"` even though the failures
    were in unrelated phases separated by an attack.
    """

    def test_close_phase_failure_does_not_poison_retreat(self):
        actor = _make_creature("Goblin", 5, 8)
        target = _make_creature("Brick", 5, 10)
        spatial = _StubSpatial(occupants={Position(5, 8): "goblin_0"})

        # Close: one failed step (e.g., transient block). Retreat: first
        # tile succeeds. With the bug, counter carries into retreat and
        # the next failed tile (if any) would trip "blocked" early.
        state = _StubGameState(
            spatial=spatial,
            enemy=actor,
            step_results=[
                MoveResult(ok=False, reason="blocked", position=None, movement_remaining=25),
                _ok_step(Position(5, 9)),  # close succeeds after retry-ish
                _ok_step(Position(5, 8)),  # retreat first tile
            ],
        )
        resolver = MagicMock(return_value=_attack_outcome())

        intent = Intent(
            steps=[
                MoveStep(path=[Position(5, 9), Position(5, 9)]),  # one fail, one ok
                AttackStep(target_id="Brick", action=SCIMITAR),
                MoveStep(path=[Position(5, 8)]),
            ]
        )
        result = pipeline.execute(
            intent,
            state,
            actor,
            reach_ft=5,
            target_pool=[target],
            attack_resolver=resolver,
        )

        # Retreat completed; guard did not fire across phases.
        assert result.stopped_reason == "retreated"
        assert result.moved_squares == 2


class TestExecuteAggressivePathUnchanged:
    """Sanity: existing single-MoveStep contract is byte-identical."""

    def test_aggressive_in_reach_short_circuits_as_before(self):
        actor = _make_creature("Bandit", 5, 5)
        target = _make_creature("Brick", 5, 6)
        spatial = _StubSpatial(occupants={Position(5, 5): "bandit_0"})
        state = _StubGameState(spatial=spatial, enemy=actor)

        intent = Intent(steps=[MoveStep(path=[Position(5, 6)])])
        result = pipeline.execute(
            intent,
            state,
            actor,
            reach_ft=5,
            target_pool=[target],
        )
        # Already in reach before stepping → in_reach short-circuit.
        assert result.stopped_reason == "in_reach"
        assert result.moved_squares == 0
        assert result.attack_outcome is None
