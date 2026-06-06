# ABOUTME: Unit tests for TurnContext.build (#647 commit 1).
# ABOUTME: Verifies action selection, reach parsing, and ranged detection.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.systems.ai.context import TurnContext


@dataclass
class _StubLoader:
    """Minimal stand-in for DataLoader.load_monsters()."""

    monsters: dict[str, Any]

    def load_monsters(self) -> dict[str, Any]:
        return self.monsters


@dataclass
class _StubState:
    """Just enough GameState surface for TurnContext.build."""

    data_loader: Any


def _make_enemy(name: str = "Goblin") -> Creature:
    return Creature(
        name=name,
        max_hp=7,
        ac=15,
        abilities=Abilities(
            strength=8, dexterity=14, constitution=10,
            intelligence=10, wisdom=8, charisma=8,
        ),
    )


class TestTurnContextBuild:
    def test_uses_provided_monster_data_when_passed(self):
        enemy = _make_enemy()
        state = _StubState(data_loader=None)
        monster_data = {
            "actions": [{"name": "Scimitar", "reach": "5 ft.", "damage": "1d6+2"}],
        }
        ctx = TurnContext.build(state, enemy, monster_data=monster_data)
        assert ctx.actor is enemy
        assert ctx.monster_data is monster_data
        assert ctx.action_data is not None
        assert ctx.action_data["name"] == "Scimitar"
        assert ctx.reach_ft == 5
        assert ctx.is_ranged is False

    def test_resolves_monster_data_from_loader_by_lowercase_name(self):
        enemy = _make_enemy("Goblin Boss")
        catalog = {
            "goblin_boss": {
                "actions": [{"name": "Scimitar", "reach": "5 ft.", "damage": "1d6+2"}],
            },
        }
        state = _StubState(data_loader=_StubLoader(monsters=catalog))
        ctx = TurnContext.build(state, enemy)
        assert ctx.action_data is not None
        assert ctx.action_data["name"] == "Scimitar"

    def test_skips_multiattack_picks_next_action(self):
        enemy = _make_enemy()
        state = _StubState(data_loader=None)
        monster_data = {
            "actions": [
                {"name": "Multiattack", "description": "two attacks"},
                {"name": "Scimitar", "reach": "5 ft.", "damage": "1d6+2"},
            ],
        }
        ctx = TurnContext.build(state, enemy, monster_data=monster_data)
        assert ctx.action_data is not None
        assert ctx.action_data["name"] == "Scimitar"
        assert ctx.reach_ft == 5

    def test_detects_ranged_action(self):
        enemy = _make_enemy()
        state = _StubState(data_loader=None)
        monster_data = {
            "actions": [{"name": "Shortbow", "range": "80/320 ft.", "damage": "1d6+2"}],
        }
        ctx = TurnContext.build(state, enemy, monster_data=monster_data)
        assert ctx.action_data is not None
        assert ctx.is_ranged is True

    def test_no_actions_yields_none_action_data(self):
        enemy = _make_enemy()
        state = _StubState(data_loader=None)
        ctx = TurnContext.build(state, enemy, monster_data={})
        assert ctx.action_data is None
        assert ctx.reach_ft is None
        assert ctx.is_ranged is False

    def test_unknown_monster_in_catalog_falls_back_to_empty(self):
        enemy = _make_enemy("Unknown Beast")
        state = _StubState(data_loader=_StubLoader(monsters={}))
        ctx = TurnContext.build(state, enemy)
        assert ctx.monster_data == {}
        assert ctx.action_data is None

    def test_default_target_pool_is_empty_list(self):
        enemy = _make_enemy()
        state = _StubState(data_loader=None)
        ctx = TurnContext.build(state, enemy, monster_data={})
        assert ctx.target_pool == []

    def test_provided_target_pool_passes_through(self):
        enemy = _make_enemy()
        state = _StubState(data_loader=None)
        pc = _make_enemy("Brick")
        ctx = TurnContext.build(state, enemy, target_pool=[pc], monster_data={})
        assert ctx.target_pool == [pc]

    def test_context_is_frozen(self):
        enemy = _make_enemy()
        state = _StubState(data_loader=None)
        ctx = TurnContext.build(state, enemy, monster_data={})
        with pytest.raises((AttributeError, TypeError)):
            ctx.actor = None  # type: ignore[misc]
