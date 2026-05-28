# ABOUTME: Tests for the class-feature registry (#591) — catalog, dispatcher, cohort
# ABOUTME: Unit (registry mechanics), integration (real Character + pools + rest), data-parity guardrail

import json
from pathlib import Path

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.systems.action_economy import ActionType, TurnState
from dnd_engine.systems.class_features import (
    ClassFeature,
    FeatureResult,
    get_feature,
    list_features,
    register,
    use_feature,
)
from dnd_engine.systems.resources import ResourcePool

CLASSES_JSON = Path(__file__).resolve().parents[1] / "dnd_engine" / "data" / "srd" / "classes.json"


def _fighter(level: int = 1, max_hp: int = 20) -> Character:
    return Character(
        name="Test Fighter",
        character_class=CharacterClass.FIGHTER,
        level=level,
        abilities=Abilities(16, 14, 14, 10, 12, 8),
        max_hp=max_hp,
        ac=16,
    )


def _wizard(level: int = 2, max_hp: int = 14) -> Character:
    return Character(
        name="Test Wizard",
        character_class=CharacterClass.WIZARD,
        level=level,
        abilities=Abilities(8, 14, 12, 16, 12, 10),
        max_hp=max_hp,
        ac=12,
    )


class TestRegistryMechanics:
    """Unit: register / get / list and the use_feature gate logic.

    These exercise the dispatcher in isolation against an isolated
    registry dict so they neither depend on nor pollute the global
    FEATURE_REGISTRY.
    """

    def test_register_get_list_roundtrip(self):
        reg: dict[str, ClassFeature] = {}

        @register(
            "test.noop",
            "No-Op",
            ActionType.ACTION,
            None,
            registry=reg,
        )
        def _noop(actor, turn_state, target, payload):
            return FeatureResult(True, "noop")

        feature = get_feature("test.noop", registry=reg)
        assert feature is not None
        assert feature.feature_id == "test.noop"
        assert feature.name == "No-Op"
        assert feature.action_cost is ActionType.ACTION
        assert feature.resource_pool is None
        assert feature in list_features(registry=reg)

    def test_use_feature_unknown_id_returns_failure(self):
        actor = _fighter()
        turn = TurnState()
        turn.reset()
        result = use_feature(actor, turn, "does.not.exist", registry={})
        assert result.success is False
        assert "unknown feature" in (result.message or "")

    def test_use_feature_result_shape_on_success(self):
        reg: dict[str, ClassFeature] = {}

        @register("test.ok", "Ok", ActionType.NO_ACTION, None, registry=reg)
        def _ok(actor, turn_state, target, payload):
            return FeatureResult(True, "done", {"k": "v"})

        result = use_feature(_fighter(), TurnState(), "test.ok", registry=reg)
        assert isinstance(result, FeatureResult)
        assert result.success is True
        assert result.message == "done"
        assert result.data == {"k": "v"}

    def test_gate_fails_when_action_slot_unavailable_resource_untouched(self):
        reg: dict[str, ClassFeature] = {}

        @register("test.bonus", "B", ActionType.BONUS_ACTION, "pool", registry=reg)
        def _b(actor, turn_state, target, payload):
            return FeatureResult(True)

        actor = _fighter()
        actor.add_resource_pool(ResourcePool("pool", 1, 1, "short_rest"))
        turn = TurnState()
        turn.reset()
        turn.consume_action(ActionType.BONUS_ACTION)  # spend the bonus action

        result = use_feature(actor, turn, "test.bonus", registry=reg)

        assert result.success is False
        assert "action" in (result.message or "")
        # gate ran before consume: the resource pool is untouched
        assert actor.get_resource_pool("pool").current == 1

    def test_gate_fails_when_resource_empty_action_untouched(self):
        reg: dict[str, ClassFeature] = {}

        @register("test.bonus2", "B2", ActionType.BONUS_ACTION, "pool", registry=reg)
        def _b2(actor, turn_state, target, payload):
            return FeatureResult(True)

        actor = _fighter()
        actor.add_resource_pool(ResourcePool("pool", 0, 1, "short_rest"))  # empty
        turn = TurnState()
        turn.reset()

        result = use_feature(actor, turn, "test.bonus2", registry=reg)

        assert result.success is False
        assert "resource" in (result.message or "")
        # gate ran before consume: the bonus action is still available
        assert turn.bonus_action_available is True


class TestSecondWind:
    """Integration: Fighter Second Wind — bonus action, short-rest pool, heals."""

    def test_second_wind_heals_consumes_bonus_action_and_pool(self):
        char = _fighter(level=1, max_hp=20)
        char.add_resource_pool(ResourcePool("second_wind", 1, 1, "short_rest"))
        char.current_hp = 2
        turn = TurnState()
        turn.reset(speed=30)

        expected = DiceRoller(seed=42).roll("1d10+1").total
        result = use_feature(
            char,
            turn,
            "fighter.second_wind",
            payload={"dice_roller": DiceRoller(seed=42)},
        )

        assert result.success is True
        assert char.current_hp == 2 + expected
        assert char.get_resource_pool("second_wind").current == 0
        assert turn.bonus_action_available is False

    def test_second_wind_unavailable_when_pool_empty_then_recovers_on_short_rest(self):
        char = _fighter(level=1, max_hp=20)
        char.add_resource_pool(ResourcePool("second_wind", 1, 1, "short_rest"))
        char.current_hp = 2

        first_turn = TurnState()
        first_turn.reset()
        assert use_feature(char, first_turn, "fighter.second_wind").success is True

        # Fresh turn — pool is now empty, so the resource gate refuses and
        # leaves the bonus action available (gate-before-consume).
        next_turn = TurnState()
        next_turn.reset()
        denied = use_feature(char, next_turn, "fighter.second_wind")
        assert denied.success is False
        assert next_turn.bonus_action_available is True

        char.take_short_rest()
        assert char.get_resource_pool("second_wind").current == 1
        rested_turn = TurnState()
        rested_turn.reset()
        assert use_feature(char, rested_turn, "fighter.second_wind").success is True


class TestActionSurge:
    """Integration: Fighter Action Surge — no action cost, grants an extra action."""

    def test_action_surge_grants_extra_action_and_consumes_pool(self):
        char = _fighter(level=2)
        char.add_resource_pool(ResourcePool("action_surge", 1, 1, "short_rest"))
        turn = TurnState()
        turn.reset()
        turn.consume_action(ActionType.ACTION)  # main action already spent
        assert turn.action_available is False

        result = use_feature(char, turn, "fighter.action_surge")

        assert result.success is True
        assert turn.action_available is True  # extra action granted
        assert char.get_resource_pool("action_surge").current == 0


class TestArcaneRecovery:
    """Integration: Wizard Arcane Recovery — long-rest pool, handler-managed accounting.

    Its pool is consumed by Character.use_arcane_recovery itself, so the
    registry entry declares resource_pool=None to avoid double-consume.
    """

    def test_arcane_recovery_restores_slots_and_consumes_its_own_pool(self):
        wiz = _wizard(level=2)
        wiz.add_resource_pool(ResourcePool("arcane_recovery", 1, 1, "long_rest"))
        wiz.add_resource_pool(ResourcePool("1st level slots", 0, 2, "long_rest"))
        turn = TurnState()
        turn.reset()

        result = use_feature(
            wiz,
            turn,
            "wizard.arcane_recovery",
            payload={"spell_slot_levels": {1: 1}},
        )

        assert result.success is True
        assert wiz.get_resource_pool("1st level slots").current == 1
        assert wiz.get_resource_pool("arcane_recovery").current == 0


class TestDataRegistryParity:
    """Guardrail: every feature_id declared in classes.json has a handler.

    This is the safety net for future class authors: declaring a class
    feature in data with a `feature_id` but forgetting to register a
    handler fails CI here and names the registry module.
    """

    def _declared_features(self):
        data = json.loads(CLASSES_JSON.read_text())
        declared = []
        for class_data in data.values():
            for feats in (class_data.get("features_by_level") or {}).values():
                for feat in feats:
                    if "feature_id" in feat:
                        declared.append(feat)
        return declared

    def test_classes_json_declares_the_cohort(self):
        ids = {f["feature_id"] for f in self._declared_features()}
        assert {
            "fighter.second_wind",
            "fighter.action_surge",
            "wizard.arcane_recovery",
        } <= ids

    def test_every_declared_feature_id_is_registered(self):
        for feat in self._declared_features():
            fid = feat["feature_id"]
            registered = get_feature(fid)
            assert registered is not None, (
                f"classes.json declares feature_id '{fid}' with no handler "
                f"registered in dnd_engine/systems/class_features.py"
            )

    def test_dispatcher_managed_pool_matches_data(self):
        """When the registry declares a dispatcher-managed pool, it must
        match the data's resource.pool. Handler-managed features
        (resource_pool=None, e.g. Arcane Recovery) are exempt."""
        for feat in self._declared_features():
            registered = get_feature(feat["feature_id"])
            if registered.resource_pool is None:
                continue
            assert registered.resource_pool == feat["resource"]["pool"]
