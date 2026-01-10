# ABOUTME: Unit tests for the spell effects plugin system.
# ABOUTME: Tests effect handlers for illumination, manipulation, detection, and utility spells.

from unittest.mock import MagicMock

import pytest

from dnd_engine.spells.effects import (
    SpellEffectResult,
    get_effect_handler,
    list_effect_types,
    register,
)
from dnd_engine.spells.effects.base import SpellEffect as BaseSpellEffect
from dnd_engine.spells.effects.detection import DetectionEffect
from dnd_engine.spells.effects.illumination import IlluminationEffect
from dnd_engine.spells.effects.manipulation import ManipulationEffect
from dnd_engine.spells.effects.utility import UtilityEffect


class TestSpellEffectRegistry:
    """Tests for the spell effect registry."""

    def test_list_effect_types_returns_registered_types(self):
        """All expected effect types should be registered."""
        effect_types = list_effect_types()

        assert "illumination" in effect_types
        assert "manipulation" in effect_types
        assert "detection" in effect_types
        assert "utility" in effect_types

    def test_get_effect_handler_returns_correct_handler(self):
        """get_effect_handler should return the correct handler type."""
        assert isinstance(get_effect_handler("illumination"), IlluminationEffect)
        assert isinstance(get_effect_handler("manipulation"), ManipulationEffect)
        assert isinstance(get_effect_handler("detection"), DetectionEffect)
        assert isinstance(get_effect_handler("utility"), UtilityEffect)

    def test_get_effect_handler_returns_none_for_unknown(self):
        """get_effect_handler should return None for unknown effect types."""
        assert get_effect_handler("nonexistent_effect") is None

    def test_register_adds_handler(self):
        """register should add a new handler to the registry."""

        class TestEffect(BaseSpellEffect):
            effect_type = "test_effect_unique"

            def apply(self, spell_data, caster, target, game_state):
                return SpellEffectResult(success=True, message="Test")

        handler = TestEffect()
        register(handler)

        assert get_effect_handler("test_effect_unique") is handler


class TestIlluminationEffect:
    """Tests for the IlluminationEffect handler."""

    @pytest.fixture
    def handler(self):
        return IlluminationEffect()

    @pytest.fixture
    def mock_caster(self):
        caster = MagicMock()
        caster.name = "Gandalf"
        return caster

    @pytest.fixture
    def mock_game_state(self):
        return MagicMock()

    @pytest.fixture
    def light_spell_data(self):
        return {
            "name": "Light",
            "effect": {
                "effect_type": "illumination",
                "light_level": "bright",
                "radius_ft": 20,
            },
        }

    def test_apply_returns_success(self, handler, mock_caster, mock_game_state, light_spell_data):
        """apply() should return a successful result."""
        result = handler.apply(light_spell_data, mock_caster, None, mock_game_state)

        assert result.success is True
        assert "bright" in result.message.lower()
        assert result.effect_data["light_level"] == "bright"
        assert result.effect_data["radius_ft"] == 20

    def test_apply_uses_default_light_level(self, handler, mock_caster, mock_game_state):
        """apply() should use bright as default light level."""
        spell_data = {"name": "Light", "effect": {"effect_type": "illumination"}}

        result = handler.apply(spell_data, mock_caster, None, mock_game_state)

        assert result.effect_data["light_level"] == "bright"

    def test_apply_with_dim_light(self, handler, mock_caster, mock_game_state):
        """apply() should handle dim light level."""
        spell_data = {
            "name": "Dancing Lights",
            "effect": {"effect_type": "illumination", "light_level": "dim", "radius_ft": 10},
        }

        result = handler.apply(spell_data, mock_caster, None, mock_game_state)

        assert result.effect_data["light_level"] == "dim"
        assert "dim" in result.message.lower() or "soft" in result.message.lower()

    def test_on_expire_returns_message(self, handler, mock_game_state):
        """on_expire() should return an expiration message."""
        effect = MagicMock()
        effect.effect_data = {"spell_name": "Light"}

        message = handler.on_expire(effect, mock_game_state)

        assert message is not None
        assert "Light" in message
        assert "fades" in message.lower()


class TestManipulationEffect:
    """Tests for the ManipulationEffect handler."""

    @pytest.fixture
    def handler(self):
        return ManipulationEffect()

    @pytest.fixture
    def mock_caster(self):
        caster = MagicMock()
        caster.name = "Merlin"
        return caster

    @pytest.fixture
    def mock_game_state(self):
        return MagicMock()

    @pytest.fixture
    def mage_hand_spell_data(self):
        return {
            "name": "Mage Hand",
            "range_ft": 30,
            "effect": {
                "effect_type": "manipulation",
                "capabilities": ["interact_at_range", "trigger_pressure_plates"],
                "range_ft": 30,
                "weight_limit_lb": 10,
            },
        }

    def test_apply_returns_success(self, handler, mock_caster, mock_game_state, mage_hand_spell_data):
        """apply() should return a successful result with capabilities."""
        result = handler.apply(mage_hand_spell_data, mock_caster, None, mock_game_state)

        assert result.success is True
        assert "spectral" in result.message.lower() or "hand" in result.message.lower()
        assert "interact_at_range" in result.effect_data["capabilities"]
        assert result.effect_data["weight_limit_lb"] == 10

    def test_apply_stores_caster_name(self, handler, mock_caster, mock_game_state, mage_hand_spell_data):
        """apply() should store the caster name in effect_data."""
        result = handler.apply(mage_hand_spell_data, mock_caster, None, mock_game_state)

        assert result.effect_data["caster_name"] == "Merlin"

    def test_get_available_actions_returns_actions(self, handler, mock_game_state):
        """get_available_actions() should return manipulation actions."""
        effect = MagicMock()
        effect.effect_data = {
            "spell_name": "Mage Hand",
            "capabilities": ["interact_at_range", "trigger_pressure_plates"],
            "weight_limit_lb": 10,
        }

        actions = handler.get_available_actions(effect, mock_game_state)

        assert len(actions) >= 1
        action_ids = [a["id"] for a in actions]
        assert "manipulate_object" in action_ids or "trigger_trap" in action_ids

    def test_handle_action_manipulate_object(self, handler, mock_game_state):
        """handle_action() should handle manipulate_object action."""
        effect = MagicMock()
        effect.effect_data = {"spell_name": "Mage Hand"}

        result = handler.handle_action(
            "manipulate_object", effect, mock_game_state, target_object="a lever"
        )

        assert result.success is True
        assert "lever" in result.message

    def test_on_expire_returns_message(self, handler, mock_game_state):
        """on_expire() should return an expiration message."""
        effect = MagicMock()
        effect.effect_data = {"spell_name": "Mage Hand"}

        message = handler.on_expire(effect, mock_game_state)

        assert message is not None
        assert "fades" in message.lower() or "vanishes" in message.lower()


class TestDetectionEffect:
    """Tests for the DetectionEffect handler."""

    @pytest.fixture
    def handler(self):
        return DetectionEffect()

    @pytest.fixture
    def mock_caster(self):
        caster = MagicMock()
        caster.name = "Elminster"
        return caster

    @pytest.fixture
    def mock_game_state(self):
        game_state = MagicMock()
        game_state.party.characters = []
        game_state.time_manager.get_all_effects.return_value = []
        return game_state

    @pytest.fixture
    def detect_magic_spell_data(self):
        return {
            "name": "Detect Magic",
            "effect": {
                "effect_type": "detection",
                "reveals": ["magical_items", "magical_effects", "magical_auras"],
                "range_ft": 30,
            },
        }

    def test_apply_returns_success(self, handler, mock_caster, mock_game_state, detect_magic_spell_data):
        """apply() should return a successful result."""
        result = handler.apply(detect_magic_spell_data, mock_caster, None, mock_game_state)

        assert result.success is True
        assert "Elminster" in result.message
        assert "magical_items" in result.effect_data["reveals"]

    def test_apply_stores_caster_name(self, handler, mock_caster, mock_game_state, detect_magic_spell_data):
        """apply() should store the caster name in effect_data."""
        result = handler.apply(detect_magic_spell_data, mock_caster, None, mock_game_state)

        assert result.effect_data["caster_name"] == "Elminster"

    def test_on_expire_returns_message(self, handler, mock_game_state):
        """on_expire() should return an expiration message."""
        effect = MagicMock()
        effect.effect_data = {"spell_name": "Detect Magic", "caster_name": "Elminster"}

        message = handler.on_expire(effect, mock_game_state)

        assert message is not None
        assert "Elminster" in message


class TestUtilityEffect:
    """Tests for the UtilityEffect handler."""

    @pytest.fixture
    def handler(self):
        return UtilityEffect()

    @pytest.fixture
    def mock_caster(self):
        caster = MagicMock()
        caster.name = "Rincewind"
        return caster

    @pytest.fixture
    def mock_game_state(self):
        return MagicMock()

    @pytest.fixture
    def prestidigitation_spell_data(self):
        return {
            "name": "Prestidigitation",
            "effect": {"effect_type": "utility", "utility_type": "prestidigitation"},
        }

    def test_apply_returns_success(self, handler, mock_caster, mock_game_state, prestidigitation_spell_data):
        """apply() should return a successful result."""
        result = handler.apply(prestidigitation_spell_data, mock_caster, None, mock_game_state)

        assert result.success is True
        assert "Rincewind" in result.message

    def test_apply_stores_capabilities(self, handler, mock_caster, mock_game_state, prestidigitation_spell_data):
        """apply() should store prestidigitation capabilities."""
        result = handler.apply(prestidigitation_spell_data, mock_caster, None, mock_game_state)

        capabilities = result.effect_data["capabilities"]
        assert "create_sensory_effect" in capabilities
        assert "clean_or_soil" in capabilities

    def test_get_available_actions_returns_actions(self, handler, mock_game_state):
        """get_available_actions() should return utility actions."""
        effect = MagicMock()
        effect.effect_data = {
            "spell_name": "Prestidigitation",
            "capabilities": ["create_sensory_effect", "clean_or_soil", "flavor_food"],
        }

        actions = handler.get_available_actions(effect, mock_game_state)

        assert len(actions) >= 1

    def test_handle_action_sensory_effect(self, handler, mock_game_state):
        """handle_action() should handle sensory_effect action."""
        effect = MagicMock()
        effect.effect_data = {"spell_name": "Prestidigitation", "caster_name": "Rincewind"}

        result = handler.handle_action("sensory_effect", effect, mock_game_state)

        assert result.success is True

    def test_on_expire_prestidigitation_returns_message(self, handler, mock_game_state):
        """on_expire() should return message for prestidigitation."""
        effect = MagicMock()
        effect.effect_data = {"spell_name": "Prestidigitation"}

        message = handler.on_expire(effect, mock_game_state)

        assert message is not None
        assert "prestidigitation" in message.lower()


class TestSpellEffectResult:
    """Tests for SpellEffectResult dataclass."""

    def test_create_success_result(self):
        """Should create a successful result."""
        result = SpellEffectResult(
            success=True, message="Spell cast successfully", effect_data={"key": "value"}
        )

        assert result.success is True
        assert result.message == "Spell cast successfully"
        assert result.effect_data == {"key": "value"}

    def test_create_failure_result(self):
        """Should create a failure result."""
        result = SpellEffectResult(success=False, message="Spell failed")

        assert result.success is False
        assert result.message == "Spell failed"
        assert result.effect_data == {}

    def test_default_effect_data(self):
        """effect_data should default to empty dict."""
        result = SpellEffectResult(success=True, message="Test")

        assert result.effect_data == {}
