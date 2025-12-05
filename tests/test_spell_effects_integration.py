# ABOUTME: Integration tests for spell effects with GameState.
# ABOUTME: Tests that spell effect handlers integrate correctly with cast_spell_exploration.

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.resources import ResourcePool
from dnd_engine.systems.time_manager import EffectType
from dnd_engine.utils.events import EventBus


class TestSpellEffectsIntegration:
    """Integration tests for spell effects with GameState."""

    @pytest.fixture
    def event_bus(self):
        """Create event bus for testing."""
        return EventBus()

    @pytest.fixture
    def data_loader(self):
        """Create data loader."""
        return DataLoader()

    @pytest.fixture
    def dice_roller(self):
        """Create seeded dice roller for predictable results."""
        return DiceRoller(seed=42)

    @pytest.fixture
    def wizard_abilities(self):
        """Create abilities for a wizard."""
        return Abilities(
            strength=8,
            dexterity=14,
            constitution=12,
            intelligence=16,  # +3 modifier
            wisdom=10,
            charisma=10,
        )

    @pytest.fixture
    def wizard_with_utility_spells(self, wizard_abilities):
        """Create a wizard with utility spells."""
        wizard = Character(
            name="Elara",
            character_class=CharacterClass.WIZARD,
            level=3,
            abilities=wizard_abilities,
            max_hp=15,
            ac=12,
            spellcasting_ability="int",
            known_spells=[
                "fire_bolt",
                "light",
                "mage_hand",
                "prestidigitation",
                "detect_magic",
            ],
            prepared_spells=[
                "fire_bolt",
                "light",
                "mage_hand",
                "prestidigitation",
                "detect_magic",
            ],
        )
        # Set up spell slots
        wizard.add_resource_pool(
            ResourcePool(
                name="spell_slots_level_1", current=4, maximum=4, recovery_type="long_rest"
            )
        )
        wizard.add_resource_pool(
            ResourcePool(
                name="spell_slots_level_2", current=2, maximum=2, recovery_type="long_rest"
            )
        )
        return wizard

    @pytest.fixture
    def game_state(self, wizard_with_utility_spells, event_bus, data_loader, dice_roller):
        """Create game state with a wizard."""
        party = Party([wizard_with_utility_spells])
        return GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller,
        )


class TestLightSpellIntegration(TestSpellEffectsIntegration):
    """Integration tests for Light cantrip."""

    def test_light_spell_returns_illumination_message(self, game_state):
        """Casting Light should return a message about illumination."""
        result = game_state.cast_spell_exploration("Elara", "light")

        assert result["success"] is True
        assert "bright" in result["description"].lower()

    def test_light_spell_creates_active_effect(self, game_state):
        """Casting Light should create an active effect."""
        game_state.cast_spell_exploration("Elara", "light")

        effects = game_state.time_manager.get_all_effects()
        light_effects = [e for e in effects if e.source == "Light"]

        assert len(light_effects) == 1
        effect = light_effects[0]
        assert effect.effect_type == EffectType.SPELL
        assert effect.effect_data.get("light_level") == "bright"

    def test_light_spell_does_not_consume_slot(self, game_state, wizard_with_utility_spells):
        """Light is a cantrip and should not consume spell slots."""
        initial_slots = wizard_with_utility_spells.get_available_spell_slots(1)

        game_state.cast_spell_exploration("Elara", "light")

        assert wizard_with_utility_spells.get_available_spell_slots(1) == initial_slots

    def test_light_spell_affects_effective_lighting(self, game_state, wizard_with_utility_spells):
        """Light spell should affect the effective lighting in the area."""
        # First check lighting without spell
        game_state.cast_spell_exploration("Elara", "light")

        # The get_effective_lighting method should detect the Light spell
        lighting = game_state.get_effective_lighting(wizard_with_utility_spells)
        assert lighting == "bright"


class TestMageHandIntegration(TestSpellEffectsIntegration):
    """Integration tests for Mage Hand cantrip."""

    def test_mage_hand_returns_manipulation_message(self, game_state):
        """Casting Mage Hand should return a message about the spectral hand."""
        result = game_state.cast_spell_exploration("Elara", "mage_hand")

        assert result["success"] is True
        assert "spectral" in result["description"].lower() or "hand" in result["description"].lower()

    def test_mage_hand_creates_active_effect_with_capabilities(self, game_state):
        """Casting Mage Hand should create an effect with manipulation capabilities."""
        game_state.cast_spell_exploration("Elara", "mage_hand")

        effects = game_state.time_manager.get_all_effects()
        mage_hand_effects = [e for e in effects if e.source == "Mage Hand"]

        assert len(mage_hand_effects) == 1
        effect = mage_hand_effects[0]
        assert "interact_at_range" in effect.effect_data.get("capabilities", [])
        assert effect.effect_data.get("weight_limit_lb") == 10

    def test_mage_hand_is_concentration(self, game_state):
        """Mage Hand should be a concentration spell."""
        game_state.cast_spell_exploration("Elara", "mage_hand")

        effects = game_state.time_manager.get_all_effects()
        mage_hand_effects = [e for e in effects if e.source == "Mage Hand"]

        assert len(mage_hand_effects) == 1
        assert mage_hand_effects[0].concentration is True

    def test_casting_mage_hand_again_breaks_concentration(self, game_state):
        """Casting Mage Hand again should break concentration on the first one."""
        game_state.cast_spell_exploration("Elara", "mage_hand")

        # Cast again
        game_state.cast_spell_exploration("Elara", "mage_hand")

        # Should only have one active Mage Hand effect
        effects = game_state.time_manager.get_all_effects()
        mage_hand_effects = [e for e in effects if e.source == "Mage Hand"]

        assert len(mage_hand_effects) == 1


class TestPrestidigitationIntegration(TestSpellEffectsIntegration):
    """Integration tests for Prestidigitation cantrip."""

    def test_prestidigitation_returns_utility_message(self, game_state):
        """Casting Prestidigitation should return a message about minor magic."""
        result = game_state.cast_spell_exploration("Elara", "prestidigitation")

        assert result["success"] is True
        assert "Elara" in result["description"]

    def test_prestidigitation_creates_effect_with_capabilities(self, game_state):
        """Casting Prestidigitation should create an effect with utility capabilities."""
        game_state.cast_spell_exploration("Elara", "prestidigitation")

        effects = game_state.time_manager.get_all_effects()
        presti_effects = [e for e in effects if e.source == "Prestidigitation"]

        assert len(presti_effects) == 1
        effect = presti_effects[0]
        capabilities = effect.effect_data.get("capabilities", [])
        assert "create_sensory_effect" in capabilities
        assert "clean_or_soil" in capabilities


class TestDetectMagicIntegration(TestSpellEffectsIntegration):
    """Integration tests for Detect Magic spell."""

    def test_detect_magic_returns_detection_message(self, game_state):
        """Casting Detect Magic should return a message about magical senses."""
        result = game_state.cast_spell_exploration("Elara", "detect_magic")

        assert result["success"] is True
        assert "Elara" in result["description"]
        assert "senses" in result["description"].lower() or "magic" in result["description"].lower()

    def test_detect_magic_consumes_spell_slot(self, game_state, wizard_with_utility_spells):
        """Detect Magic (level 1) should consume a spell slot."""
        initial_slots = wizard_with_utility_spells.get_available_spell_slots(1)

        game_state.cast_spell_exploration("Elara", "detect_magic")

        assert wizard_with_utility_spells.get_available_spell_slots(1) == initial_slots - 1

    def test_detect_magic_creates_active_effect(self, game_state):
        """Casting Detect Magic should create an active effect with reveals list."""
        game_state.cast_spell_exploration("Elara", "detect_magic")

        effects = game_state.time_manager.get_all_effects()
        detect_effects = [e for e in effects if e.source == "Detect Magic"]

        assert len(detect_effects) == 1
        effect = detect_effects[0]
        assert effect.concentration is True
        reveals = effect.effect_data.get("reveals", [])
        assert "magical_items" in reveals

    def test_detect_magic_is_concentration(self, game_state):
        """Detect Magic should be a concentration spell."""
        game_state.cast_spell_exploration("Elara", "detect_magic")

        effects = game_state.time_manager.get_all_effects()
        detect_effects = [e for e in effects if e.source == "Detect Magic"]

        assert len(detect_effects) == 1
        assert detect_effects[0].concentration is True

    def test_casting_detect_magic_breaks_mage_hand_concentration(self, game_state):
        """Casting Detect Magic should break concentration on Mage Hand."""
        game_state.cast_spell_exploration("Elara", "mage_hand")

        # Verify Mage Hand is active
        effects_before = game_state.time_manager.get_all_effects()
        mage_hand_before = [e for e in effects_before if e.source == "Mage Hand"]
        assert len(mage_hand_before) == 1

        # Cast Detect Magic (also concentration)
        game_state.cast_spell_exploration("Elara", "detect_magic")

        # Mage Hand should be gone, Detect Magic should be active
        effects_after = game_state.time_manager.get_all_effects()
        mage_hand_after = [e for e in effects_after if e.source == "Mage Hand"]
        detect_after = [e for e in effects_after if e.source == "Detect Magic"]

        assert len(mage_hand_after) == 0
        assert len(detect_after) == 1


class TestSpellEffectQueries(TestSpellEffectsIntegration):
    """Tests for querying spell effects through handlers."""

    def test_illumination_query_returns_light_level(self, game_state):
        """Illumination handler query should return active light level."""
        from dnd_engine.spells.effects import get_effect_handler

        game_state.cast_spell_exploration("Elara", "light")

        handler = get_effect_handler("illumination")
        light_level = handler.query(game_state, "get_light_level")

        assert light_level == "bright"

    def test_manipulation_query_has_capability(self, game_state):
        """Manipulation handler query should detect active capabilities."""
        from dnd_engine.spells.effects import get_effect_handler

        game_state.cast_spell_exploration("Elara", "mage_hand")

        handler = get_effect_handler("manipulation")
        has_capability = handler.query(
            game_state, "has_capability", capability="interact_at_range"
        )

        assert has_capability is True

    def test_manipulation_query_no_capability_when_not_cast(self, game_state):
        """Manipulation handler query should return False when no effect active."""
        from dnd_engine.spells.effects import get_effect_handler

        # Don't cast mage hand
        handler = get_effect_handler("manipulation")
        has_capability = handler.query(
            game_state, "has_capability", capability="interact_at_range"
        )

        assert has_capability is False
