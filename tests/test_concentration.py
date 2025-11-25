# ABOUTME: Unit tests for spell concentration mechanics
# ABOUTME: Tests concentration tracking, damage-triggered checks, and concentration breaking

from unittest.mock import Mock, patch

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.systems.time_manager import ActiveEffect, EffectType
from dnd_engine.utils.events import EventBus


@pytest.fixture
def sample_character():
    """Create a sample character for testing"""
    return Character(
        name="Test Wizard",
        character_class=CharacterClass.WIZARD,
        level=5,
        abilities=Abilities(
            strength=8,
            dexterity=14,
            constitution=14,  # +2 modifier
            intelligence=16,
            wisdom=12,
            charisma=10
        ),
        max_hp=30,
        ac=12
    )


@pytest.fixture
def game_state_with_character(sample_character):
    """Create game state with a character"""
    party = Party([sample_character])
    event_bus = EventBus()

    with patch('dnd_engine.core.game_state.DataLoader') as mock_loader_class:
        mock_loader = Mock()
        mock_loader.load_dungeon.return_value = {
            "name": "Test Dungeon",
            "start_room": "test_room",
            "rooms": {
                "test_room": {
                    "name": "Test Room",
                    "description": "A test room",
                    "exits": {},
                    "items": []
                }
            }
        }
        mock_loader.load_skills.return_value = {}
        mock_loader.load_items.return_value = {
            "weapons": {},
            "consumables": {},
            "armor": {}
        }
        mock_loader.load_spells.return_value = {
            "bless": {
                "name": "Bless",
                "level": 1,
                "concentration": True,
                "duration": 60
            },
            "mage_hand": {
                "name": "Mage Hand",
                "level": 0,
                "concentration": True,
                "duration": 60
            },
            "magic_missile": {
                "name": "Magic Missile",
                "level": 1,
                "concentration": False
            }
        }
        mock_loader_class.return_value = mock_loader

        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus
        )

    game_state.current_room_id = "test_room"
    return game_state


class TestGetConcentrationSpell:
    """Test getting active concentration spell"""

    def test_no_concentration_returns_none(self, game_state_with_character, sample_character):
        """Test that None is returned when not concentrating"""
        result = game_state_with_character.get_concentration_spell(sample_character.name)
        assert result is None

    def test_returns_concentration_spell_name(self, game_state_with_character, sample_character):
        """Test that spell name is returned when concentrating"""
        # Add a concentration effect
        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="bless",
            duration_type="minutes",
            duration_value=60.0,
            remaining_value=60.0,
            target_name=sample_character.name,
            caster_name=sample_character.name,
            concentration=True
        )
        game_state_with_character.time_manager.add_effect(effect)

        result = game_state_with_character.get_concentration_spell(sample_character.name)
        assert result == "bless"

    def test_different_character_concentration(self, game_state_with_character):
        """Test that concentration is character-specific"""
        # Add concentration for a different character
        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="bless",
            duration_type="minutes",
            duration_value=60.0,
            remaining_value=60.0,
            target_name="Other Character",
            caster_name="Other Character",
            concentration=True
        )
        game_state_with_character.time_manager.add_effect(effect)

        # Should not return concentration for our test character
        result = game_state_with_character.get_concentration_spell("Test Wizard")
        assert result is None


class TestConcentrationFromDamage:
    """Test damage-triggered concentration checks"""

    def test_no_concentration_no_check(self, game_state_with_character, sample_character):
        """Test that no check occurs when not concentrating"""
        result = game_state_with_character.check_concentration_from_damage(
            sample_character.name,
            10
        )

        assert result["was_concentrating"] is False
        assert result["concentration_broken"] is False
        assert result["spell_name"] is None

    def test_low_damage_dc_10(self, game_state_with_character, sample_character):
        """Test that low damage (< 20) uses DC 10"""
        # Add concentration
        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="bless",
            duration_type="minutes",
            duration_value=60.0,
            remaining_value=60.0,
            target_name=sample_character.name,
            caster_name=sample_character.name,
            concentration=True
        )
        game_state_with_character.time_manager.add_effect(effect)

        # Mock saving throw to succeed
        with patch.object(sample_character, 'make_saving_throw') as mock_save:
            mock_save.return_value = {
                "success": True,
                "roll": 12,
                "modifier": 2,
                "total": 14
            }

            result = game_state_with_character.check_concentration_from_damage(
                sample_character.name,
                5  # Low damage
            )

            # DC should be max(10, 5//2) = max(10, 2) = 10
            assert result["dc"] == 10
            assert result["was_concentrating"] is True
            assert result["concentration_broken"] is False
            mock_save.assert_called_once_with("constitution", 10)

    def test_high_damage_dc_half_damage(self, game_state_with_character, sample_character):
        """Test that high damage uses DC = damage // 2"""
        # Add concentration
        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="bless",
            duration_type="minutes",
            duration_value=60.0,
            remaining_value=60.0,
            target_name=sample_character.name,
            caster_name=sample_character.name,
            concentration=True
        )
        game_state_with_character.time_manager.add_effect(effect)

        # Mock saving throw
        with patch.object(sample_character, 'make_saving_throw') as mock_save:
            mock_save.return_value = {
                "success": True,
                "roll": 18,
                "modifier": 2,
                "total": 20
            }

            result = game_state_with_character.check_concentration_from_damage(
                sample_character.name,
                30  # High damage
            )

            # DC should be max(10, 30//2) = max(10, 15) = 15
            assert result["dc"] == 15
            mock_save.assert_called_once_with("constitution", 15)

    def test_failed_save_breaks_concentration(self, game_state_with_character, sample_character):
        """Test that failed save breaks concentration"""
        # Add concentration
        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="bless",
            duration_type="minutes",
            duration_value=60.0,
            remaining_value=60.0,
            target_name=sample_character.name,
            caster_name=sample_character.name,
            concentration=True
        )
        game_state_with_character.time_manager.add_effect(effect)

        # Mock saving throw to fail
        with patch.object(sample_character, 'make_saving_throw') as mock_save:
            mock_save.return_value = {
                "success": False,
                "roll": 5,
                "modifier": 2,
                "total": 7
            }

            result = game_state_with_character.check_concentration_from_damage(
                sample_character.name,
                10
            )

            assert result["was_concentrating"] is True
            assert result["concentration_broken"] is True
            assert result["spell_name"] == "bless"

            # Verify concentration was actually removed
            remaining_spell = game_state_with_character.get_concentration_spell(sample_character.name)
            assert remaining_spell is None

    def test_successful_save_maintains_concentration(self, game_state_with_character, sample_character):
        """Test that successful save maintains concentration"""
        # Add concentration
        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="bless",
            duration_type="minutes",
            duration_value=60.0,
            remaining_value=60.0,
            target_name=sample_character.name,
            caster_name=sample_character.name,
            concentration=True
        )
        game_state_with_character.time_manager.add_effect(effect)

        # Mock saving throw to succeed
        with patch.object(sample_character, 'make_saving_throw') as mock_save:
            mock_save.return_value = {
                "success": True,
                "roll": 15,
                "modifier": 2,
                "total": 17
            }

            result = game_state_with_character.check_concentration_from_damage(
                sample_character.name,
                10
            )

            assert result["was_concentrating"] is True
            assert result["concentration_broken"] is False

            # Verify concentration is still active
            remaining_spell = game_state_with_character.get_concentration_spell(sample_character.name)
            assert remaining_spell == "bless"

    def test_multiple_damage_instances(self, game_state_with_character, sample_character):
        """Test multiple damage checks in sequence"""
        # Add concentration
        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="bless",
            duration_type="minutes",
            duration_value=60.0,
            remaining_value=60.0,
            target_name=sample_character.name,
            caster_name=sample_character.name,
            concentration=True
        )
        game_state_with_character.time_manager.add_effect(effect)

        # First hit - succeed
        with patch.object(sample_character, 'make_saving_throw') as mock_save:
            mock_save.return_value = {"success": True, "roll": 15, "modifier": 2, "total": 17}
            result1 = game_state_with_character.check_concentration_from_damage(sample_character.name, 10)
            assert result1["concentration_broken"] is False

        # Second hit - fail
        with patch.object(sample_character, 'make_saving_throw') as mock_save:
            mock_save.return_value = {"success": False, "roll": 3, "modifier": 2, "total": 5}
            result2 = game_state_with_character.check_concentration_from_damage(sample_character.name, 10)
            assert result2["concentration_broken"] is True

        # Verify concentration is gone
        assert game_state_with_character.get_concentration_spell(sample_character.name) is None
