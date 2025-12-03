# ABOUTME: Unit tests for Sleep spell HP pool mechanics
# ABOUTME: Tests resolve_spell_hp_pool in combat engine and routing in game_state

from unittest.mock import MagicMock, patch

import pytest

from dnd_engine.core.combat import CombatEngine
from dnd_engine.core.creature import Creature
from dnd_engine.core.dice import DiceRoller


class TestResolveSpellHpPool:
    """Tests for CombatEngine.resolve_spell_hp_pool() method."""

    @pytest.fixture
    def combat_engine(self):
        """Create a combat engine with seeded dice roller."""
        roller = DiceRoller(seed=42)
        return CombatEngine(dice_roller=roller)

    @pytest.fixture
    def sleep_spell(self):
        """Sleep spell data."""
        return {
            "id": "sleep",
            "name": "Sleep",
            "level": 1,
            "hp_pool": {
                "dice": "5d8",
                "higher_levels_dice": "2d8",
                "immune_types": ["undead", "construct"],
            },
            "effect": {"condition": "unconscious", "duration_rounds": 10},
        }

    @pytest.fixture
    def caster(self):
        """Create a caster creature."""
        caster = MagicMock()
        caster.name = "Wizard"
        return caster

    @pytest.fixture
    def low_hp_target(self):
        """Create a low HP target."""
        target = MagicMock(spec=Creature)
        target.name = "Goblin"
        target.current_hp = 5
        target.is_alive = True
        target.creature_type = "humanoid"
        target.apply_condition_with_metadata = MagicMock()
        target.add_condition = MagicMock()
        return target

    @pytest.fixture
    def high_hp_target(self):
        """Create a high HP target."""
        target = MagicMock(spec=Creature)
        target.name = "Ogre"
        target.current_hp = 50
        target.is_alive = True
        target.creature_type = "giant"
        target.apply_condition_with_metadata = MagicMock()
        target.add_condition = MagicMock()
        return target

    @pytest.fixture
    def undead_target(self):
        """Create an undead target (immune to Sleep)."""
        target = MagicMock(spec=Creature)
        target.name = "Skeleton"
        target.current_hp = 8
        target.is_alive = True
        target.creature_type = "undead"
        target.apply_condition_with_metadata = MagicMock()
        target.add_condition = MagicMock()
        return target

    def test_sleep_affects_low_hp_creature(self, combat_engine, sleep_spell, caster, low_hp_target):
        """Sleep should affect creatures with HP <= pool."""
        # Seed dice to get predictable HP pool (5d8 with seed 42)
        result = combat_engine.resolve_spell_hp_pool(
            caster=caster, targets=[low_hp_target], spell=sleep_spell
        )

        assert result["spell_name"] == "Sleep"
        assert result["caster"] == "Wizard"
        assert result["hp_pool_rolled"] > 0
        assert len(result["affected_targets"]) == 1
        assert result["affected_targets"][0]["name"] == "Goblin"
        assert result["affected_targets"][0]["condition"] == "unconscious"
        low_hp_target.apply_condition_with_metadata.assert_called_once_with(
            condition="unconscious", duration_type="rounds", duration=10
        )

    def test_sleep_does_not_affect_high_hp_creature(
        self, combat_engine, sleep_spell, caster, high_hp_target
    ):
        """Sleep should not affect creatures with HP > pool."""
        result = combat_engine.resolve_spell_hp_pool(
            caster=caster, targets=[high_hp_target], spell=sleep_spell
        )

        # With 5d8 (max 40), a 50 HP creature should not be affected
        assert len(result["affected_targets"]) == 0
        assert len(result["unaffected_targets"]) == 1
        assert result["unaffected_targets"][0]["name"] == "Ogre"
        assert "not enough HP pool" in result["unaffected_targets"][0]["reason"]
        high_hp_target.apply_condition_with_metadata.assert_not_called()

    def test_sleep_targets_in_ascending_hp_order(self, combat_engine, sleep_spell, caster):
        """Sleep should affect creatures starting with lowest HP."""
        # Create targets with different HP
        target_5hp = MagicMock(spec=Creature)
        target_5hp.name = "Goblin1"
        target_5hp.current_hp = 5
        target_5hp.is_alive = True
        target_5hp.creature_type = "humanoid"
        target_5hp.apply_condition_with_metadata = MagicMock()
        target_5hp.add_condition = MagicMock()

        target_10hp = MagicMock(spec=Creature)
        target_10hp.name = "Goblin2"
        target_10hp.current_hp = 10
        target_10hp.is_alive = True
        target_10hp.creature_type = "humanoid"
        target_10hp.apply_condition_with_metadata = MagicMock()
        target_10hp.add_condition = MagicMock()

        target_15hp = MagicMock(spec=Creature)
        target_15hp.name = "Hobgoblin"
        target_15hp.current_hp = 15
        target_15hp.is_alive = True
        target_15hp.creature_type = "humanoid"
        target_15hp.apply_condition_with_metadata = MagicMock()
        target_15hp.add_condition = MagicMock()

        # Pass targets in non-sorted order
        targets = [target_15hp, target_5hp, target_10hp]

        result = combat_engine.resolve_spell_hp_pool(
            caster=caster, targets=targets, spell=sleep_spell
        )

        # Should affect lowest HP first
        affected_names = [t["name"] for t in result["affected_targets"]]
        # 5hp goblin should always be first if affected
        if affected_names:
            assert affected_names[0] == "Goblin1"

    def test_sleep_ignores_undead(self, combat_engine, sleep_spell, caster, undead_target):
        """Sleep should not affect undead creatures."""
        result = combat_engine.resolve_spell_hp_pool(
            caster=caster, targets=[undead_target], spell=sleep_spell
        )

        assert len(result["affected_targets"]) == 0
        assert len(result["unaffected_targets"]) == 1
        assert "immune" in result["unaffected_targets"][0]["reason"]
        undead_target.apply_condition_with_metadata.assert_not_called()

    def test_sleep_ignores_dead_creatures(self, combat_engine, sleep_spell, caster):
        """Sleep should skip dead creatures."""
        dead_target = MagicMock(spec=Creature)
        dead_target.name = "DeadGoblin"
        dead_target.current_hp = 0
        dead_target.is_alive = False
        dead_target.creature_type = "humanoid"
        dead_target.apply_condition_with_metadata = MagicMock()
        dead_target.add_condition = MagicMock()

        result = combat_engine.resolve_spell_hp_pool(
            caster=caster, targets=[dead_target], spell=sleep_spell
        )

        assert len(result["affected_targets"]) == 0
        # Dead creatures are filtered out, not added to unaffected
        dead_target.apply_condition_with_metadata.assert_not_called()

    def test_sleep_hp_pool_exhaustion(self, combat_engine, sleep_spell, caster):
        """Sleep should stop affecting creatures when HP pool is exhausted."""
        # Create multiple low HP targets
        targets = []
        for i in range(10):
            target = MagicMock(spec=Creature)
            target.name = f"Goblin{i}"
            target.current_hp = 7
            target.is_alive = True
            target.creature_type = "humanoid"
            target.apply_condition_with_metadata = MagicMock()
            target.add_condition = MagicMock()
            targets.append(target)

        result = combat_engine.resolve_spell_hp_pool(
            caster=caster, targets=targets, spell=sleep_spell
        )

        # With 5d8 (avg 22.5), should affect ~3 goblins at 7 HP each
        # Total affected HP should not exceed hp_pool_rolled
        total_affected_hp = sum(t["hp"] for t in result["affected_targets"])
        assert total_affected_hp <= result["hp_pool_rolled"]

        # Some should be unaffected due to exhausted pool
        assert len(result["unaffected_targets"]) > 0

    def test_sleep_returns_remaining_hp_pool(
        self, combat_engine, sleep_spell, caster, low_hp_target
    ):
        """Sleep should return the remaining HP pool after affecting targets."""
        result = combat_engine.resolve_spell_hp_pool(
            caster=caster, targets=[low_hp_target], spell=sleep_spell
        )

        # Remaining should be: rolled - affected HP
        expected_remaining = result["hp_pool_rolled"] - low_hp_target.current_hp
        assert result["hp_pool_remaining"] == expected_remaining

    def test_sleep_emits_event(self, combat_engine, sleep_spell, caster, low_hp_target):
        """Sleep should emit a SPELL_CAST event."""
        event_bus = MagicMock()

        result = combat_engine.resolve_spell_hp_pool(
            caster=caster, targets=[low_hp_target], spell=sleep_spell, event_bus=event_bus
        )

        event_bus.emit.assert_called_once()
        event = event_bus.emit.call_args[0][0]
        assert event.data["spell_name"] == "Sleep"
        assert event.data["caster"] == "Wizard"


class TestGameStateCastSpellCombatHpPool:
    """Tests for game_state.cast_spell_combat() routing to HP pool spells."""

    @pytest.fixture
    def mock_game_state(self):
        """Create a mock game state with necessary components."""
        from dnd_engine.core.game_state import GameState

        with patch.object(GameState, "__init__", lambda self: None):
            gs = GameState()
            gs.combat_engine = MagicMock()
            gs.event_bus = MagicMock()
            gs.time_manager = MagicMock()
            gs.active_enemies = []
            gs.dice_roller = DiceRoller(seed=42)

            # Mock get_concentration_spell
            gs.get_concentration_spell = MagicMock(return_value=None)
            gs._create_spell_effect = MagicMock(return_value=None)

            return gs

    @pytest.fixture
    def sleep_spell_data(self):
        """Sleep spell data dictionary."""
        return {
            "id": "sleep",
            "name": "Sleep",
            "level": 1,
            "target_type": "area",
            "concentration": False,
            "hp_pool": {
                "dice": "5d8",
                "higher_levels_dice": "2d8",
                "immune_types": ["undead", "construct"],
            },
            "effect": {"condition": "unconscious", "duration_rounds": 10},
        }

    @pytest.fixture
    def caster(self):
        """Create a caster character."""
        from dnd_engine.core.character import Character

        caster = MagicMock(spec=Character)
        caster.name = "TestWizard"
        caster.level = 1
        caster.get_available_spell_slots.return_value = 2
        caster.use_spell_slot.return_value = True
        return caster

    def test_cast_spell_combat_routes_to_hp_pool(self, mock_game_state, sleep_spell_data, caster):
        """cast_spell_combat should route hp_pool spells correctly."""
        # Setup mock enemy
        enemy = MagicMock()
        enemy.name = "Goblin"
        enemy.current_hp = 7
        enemy.is_alive = True
        mock_game_state.active_enemies = [enemy]

        # Setup combat engine response
        mock_game_state.combat_engine.resolve_spell_hp_pool.return_value = {
            "spell_name": "Sleep",
            "caster": "TestWizard",
            "hp_pool_rolled": 25,
            "hp_pool_remaining": 18,
            "affected_targets": [{"name": "Goblin", "hp": 7, "condition": "unconscious"}],
            "unaffected_targets": [],
        }

        result = mock_game_state.cast_spell_combat(
            caster=caster,
            spell_data=sleep_spell_data,
            target=None,  # Area spell
            spellcasting_ability="int",
        )

        # Verify routing
        mock_game_state.combat_engine.resolve_spell_hp_pool.assert_called_once()
        assert result.spell_type == "hp_pool"
        assert result.hp_pool_rolled == 25
        assert len(result.affected_targets) == 1

    def test_hp_pool_spell_result_fields(self, mock_game_state, sleep_spell_data, caster):
        """CombatSpellResult should have correct hp_pool fields."""
        enemy = MagicMock()
        enemy.name = "Goblin"
        enemy.is_alive = True
        mock_game_state.active_enemies = [enemy]

        mock_game_state.combat_engine.resolve_spell_hp_pool.return_value = {
            "spell_name": "Sleep",
            "caster": "TestWizard",
            "hp_pool_rolled": 30,
            "hp_pool_remaining": 5,
            "affected_targets": [{"name": "Goblin", "hp": 7, "condition": "unconscious"}],
            "unaffected_targets": [
                {"name": "Ogre", "hp": 50, "reason": "not enough HP pool remaining"}
            ],
        }

        result = mock_game_state.cast_spell_combat(
            caster=caster, spell_data=sleep_spell_data, target=None, spellcasting_ability="int"
        )

        assert result.success is True
        assert result.spell_name == "Sleep"
        assert result.spell_type == "hp_pool"
        assert result.hp_pool_rolled == 30
        assert result.hp_pool_remaining == 5
        assert result.affected_targets is not None
        assert result.unaffected_targets is not None
