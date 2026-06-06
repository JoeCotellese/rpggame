# ABOUTME: Unit tests for Intent and TurnStep variants (#647 commit 1).
# ABOUTME: Verifies frozen-ness, default values, and constructor shape.

from __future__ import annotations

import pytest

from dnd_engine.core.position import Position
from dnd_engine.systems.ai.intent import (
    AttackStep,
    ConditionRemovalStep,
    Intent,
    MoveStep,
    WaitStep,
)


class TestMoveStep:
    def test_constructs_with_path(self):
        step = MoveStep(path=[Position(1, 0), Position(2, 0)])
        assert step.path == [Position(1, 0), Position(2, 0)]

    def test_default_path_empty(self):
        step = MoveStep()
        assert step.path == []

    def test_is_frozen(self):
        step = MoveStep(path=[Position(0, 0)])
        with pytest.raises((AttributeError, TypeError)):
            step.path = []  # type: ignore[misc]


class TestAttackStep:
    def test_carries_target_and_action(self):
        action = {"name": "Scimitar", "damage": "1d6+2"}
        step = AttackStep(target_id="brick_pc", action=action)
        assert step.target_id == "brick_pc"
        assert step.action is action

    def test_is_frozen(self):
        step = AttackStep(target_id="t", action={})
        with pytest.raises((AttributeError, TypeError)):
            step.target_id = "other"  # type: ignore[misc]


class TestConditionRemovalStep:
    def test_carries_condition_id(self):
        step = ConditionRemovalStep(condition_id="on_fire")
        assert step.condition_id == "on_fire"

    def test_is_frozen(self):
        step = ConditionRemovalStep(condition_id="on_fire")
        with pytest.raises((AttributeError, TypeError)):
            step.condition_id = "stunned"  # type: ignore[misc]


class TestWaitStep:
    def test_carries_reason(self):
        step = WaitStep(reason="no_targets")
        assert step.reason == "no_targets"

    def test_is_frozen(self):
        step = WaitStep(reason="no_targets")
        with pytest.raises((AttributeError, TypeError)):
            step.reason = "other"  # type: ignore[misc]


class TestIntent:
    def test_default_steps_is_empty_list(self):
        intent = Intent()
        assert intent.steps == []
        assert intent.rationale == ""

    def test_carries_step_sequence(self):
        steps = [
            MoveStep(path=[Position(1, 0)]),
            AttackStep(target_id="t", action={"name": "Bite"}),
        ]
        intent = Intent(steps=steps, rationale="close + attack")
        assert intent.steps == steps
        assert intent.rationale == "close + attack"

    def test_supports_skirmisher_three_step_shape(self):
        steps = [
            MoveStep(path=[Position(1, 0)]),
            AttackStep(target_id="t", action={}),
            MoveStep(path=[Position(0, 0)]),
        ]
        intent = Intent(steps=steps)
        assert len(intent.steps) == 3
        assert isinstance(intent.steps[0], MoveStep)
        assert isinstance(intent.steps[1], AttackStep)
        assert isinstance(intent.steps[2], MoveStep)
