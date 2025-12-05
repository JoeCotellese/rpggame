# ABOUTME: Unit tests for the capability system.
# ABOUTME: Tests CapabilityResolver and room interaction capability requirements.

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from dnd_engine.systems.capabilities import (
    Capability,
    CapabilitySource,
    CapabilityResolver,
)


class TestCapabilityEnum:
    """Tests for the Capability enum."""

    def test_capability_values_are_strings(self):
        """Capability enum values should be strings."""
        assert Capability.LIGHT_SOURCE == "light_source"
        assert Capability.DARKVISION == "darkvision"
        assert Capability.REACH_30FT == "reach_30ft"
        assert Capability.REACH_60FT == "reach_60ft"

    def test_capability_from_string(self):
        """Should be able to create Capability from string value."""
        assert Capability("light_source") == Capability.LIGHT_SOURCE
        assert Capability("reach_30ft") == Capability.REACH_30FT

    def test_capability_invalid_string_raises(self):
        """Invalid string should raise ValueError."""
        with pytest.raises(ValueError):
            Capability("invalid_capability")


class TestCapabilitySource:
    """Tests for the CapabilitySource dataclass."""

    def test_create_spell_source(self):
        """Should create a spell-based capability source."""
        source = CapabilitySource(
            capability=Capability.LIGHT_SOURCE,
            source_type="spell",
            source_name="Light",
            character_name="Gandalf",
            duration="1 hour",
        )

        assert source.capability == Capability.LIGHT_SOURCE
        assert source.source_type == "spell"
        assert source.source_name == "Light"
        assert source.character_name == "Gandalf"
        assert source.duration == "1 hour"

    def test_create_item_source(self):
        """Should create an item-based capability source."""
        source = CapabilitySource(
            capability=Capability.LIGHT_SOURCE,
            source_type="item",
            source_name="torch",
            character_name="Frodo",
            duration="while held",
        )

        assert source.capability == Capability.LIGHT_SOURCE
        assert source.source_type == "item"
        assert source.source_name == "torch"

    def test_create_racial_source(self):
        """Should create a racial trait capability source."""
        source = CapabilitySource(
            capability=Capability.DARKVISION,
            source_type="racial",
            source_name="Darkvision (Elf)",
            character_name="Legolas",
            duration="permanent",
        )

        assert source.capability == Capability.DARKVISION
        assert source.source_type == "racial"


class TestCapabilityResolverBasic:
    """Basic tests for CapabilityResolver."""

    @pytest.fixture
    def mock_game_state(self):
        """Create a mock game state with empty party."""
        game_state = MagicMock()
        game_state.party = MagicMock()
        game_state.party.characters = []
        game_state.time_manager = MagicMock()
        game_state.time_manager.get_all_effects.return_value = []
        return game_state

    def test_no_capabilities_with_empty_party(self, mock_game_state):
        """Empty party should have no capabilities."""
        resolver = CapabilityResolver(mock_game_state)
        capabilities = resolver.get_party_capabilities()

        assert capabilities == []

    def test_has_capability_returns_false_for_missing(self, mock_game_state):
        """has_capability should return False for missing capability."""
        resolver = CapabilityResolver(mock_game_state)

        assert resolver.has_capability(Capability.LIGHT_SOURCE) is False
        assert resolver.has_capability("light_source") is False

    def test_has_capability_with_invalid_string(self, mock_game_state):
        """has_capability should return False for invalid string."""
        resolver = CapabilityResolver(mock_game_state)

        assert resolver.has_capability("nonexistent") is False

    def test_get_capability_source_returns_none_for_missing(self, mock_game_state):
        """get_capability_source should return None for missing capability."""
        resolver = CapabilityResolver(mock_game_state)

        assert resolver.get_capability_source(Capability.LIGHT_SOURCE) is None


class TestCapabilityResolverRacialTraits:
    """Tests for racial trait capabilities."""

    @pytest.fixture
    def mock_elf_character(self):
        """Create a mock elf character."""
        char = MagicMock()
        char.name = "Legolas"
        char.race = "elf"
        char.inventory = MagicMock()
        char.inventory.items = {}
        return char

    @pytest.fixture
    def mock_game_state_with_elf(self, mock_elf_character):
        """Create game state with an elf character."""
        game_state = MagicMock()
        game_state.party = MagicMock()
        game_state.party.characters = [mock_elf_character]
        game_state.time_manager = MagicMock()
        game_state.time_manager.get_all_effects.return_value = []
        return game_state

    def test_elf_has_darkvision(self, mock_game_state_with_elf):
        """Elf character should have darkvision capability."""
        resolver = CapabilityResolver(mock_game_state_with_elf)

        assert resolver.has_capability(Capability.DARKVISION) is True

    def test_elf_darkvision_source(self, mock_game_state_with_elf):
        """Elf darkvision should have correct source info."""
        resolver = CapabilityResolver(mock_game_state_with_elf)
        source = resolver.get_capability_source(Capability.DARKVISION)

        assert source is not None
        assert source.capability == Capability.DARKVISION
        assert source.source_type == "racial"
        assert source.character_name == "Legolas"
        assert source.duration == "permanent"

    def test_dwarf_has_darkvision(self):
        """Dwarf character should have darkvision capability."""
        char = MagicMock()
        char.name = "Gimli"
        char.race = "dwarf"
        char.inventory = MagicMock()
        char.inventory.items = {}

        game_state = MagicMock()
        game_state.party.characters = [char]
        game_state.time_manager.get_all_effects.return_value = []

        resolver = CapabilityResolver(game_state)
        assert resolver.has_capability(Capability.DARKVISION) is True

    def test_human_no_darkvision(self):
        """Human character should not have darkvision capability."""
        char = MagicMock()
        char.name = "Aragorn"
        char.race = "human"
        char.inventory = MagicMock()
        char.inventory.items = {}

        game_state = MagicMock()
        game_state.party.characters = [char]
        game_state.time_manager.get_all_effects.return_value = []

        resolver = CapabilityResolver(game_state)
        assert resolver.has_capability(Capability.DARKVISION) is False


class TestCapabilityResolverItems:
    """Tests for item-based capabilities."""

    @pytest.fixture
    def mock_character_with_torch(self):
        """Create a character with a torch."""
        char = MagicMock()
        char.name = "Sam"
        char.race = "human"
        char.inventory = MagicMock()
        char.inventory.items = {
            "torch": MagicMock(quantity=1),
        }
        return char

    @pytest.fixture
    def mock_game_state_with_torch(self, mock_character_with_torch):
        """Create game state with a torch-bearing character."""
        game_state = MagicMock()
        game_state.party.characters = [mock_character_with_torch]
        game_state.time_manager.get_all_effects.return_value = []
        return game_state

    def test_torch_grants_light_source(self, mock_game_state_with_torch):
        """Character with torch should have light_source capability."""
        resolver = CapabilityResolver(mock_game_state_with_torch)

        assert resolver.has_capability(Capability.LIGHT_SOURCE) is True

    def test_torch_light_source_details(self, mock_game_state_with_torch):
        """Torch light source should have correct details."""
        resolver = CapabilityResolver(mock_game_state_with_torch)
        source = resolver.get_capability_source(Capability.LIGHT_SOURCE)

        assert source is not None
        assert source.source_type == "item"
        assert "torch" in source.source_name.lower()
        assert source.character_name == "Sam"
        assert source.duration == "while held"

    def test_lantern_grants_light_source(self):
        """Character with lantern should have light_source capability."""
        char = MagicMock()
        char.name = "Bilbo"
        char.race = "halfling"
        char.inventory = MagicMock()
        char.inventory.items = {"lantern": MagicMock(quantity=1)}

        game_state = MagicMock()
        game_state.party.characters = [char]
        game_state.time_manager.get_all_effects.return_value = []

        resolver = CapabilityResolver(game_state)
        assert resolver.has_capability(Capability.LIGHT_SOURCE) is True


class TestCapabilityResolverSpells:
    """Tests for spell-based capabilities."""

    @pytest.fixture
    def mock_light_spell_effect(self):
        """Create a mock Light spell effect."""
        effect = MagicMock()
        effect.effect_type = MagicMock()
        effect.effect_type.value = "spell"
        effect.effect_type.name = "SPELL"
        effect.source = "Light"
        effect.remaining_value = 60
        effect.remaining_unit = "minutes"
        effect.effect_data = {
            "spell_name": "Light",
            "caster_name": "Gandalf",
            "light_level": "bright",
            "radius_ft": 20,
        }
        return effect

    @pytest.fixture
    def mock_mage_hand_effect(self):
        """Create a mock Mage Hand spell effect."""
        effect = MagicMock()
        effect.effect_type = MagicMock()
        effect.effect_type.value = "spell"
        effect.effect_type.name = "SPELL"
        effect.source = "Mage Hand"
        effect.remaining_value = 1
        effect.remaining_unit = "minutes"
        effect.effect_data = {
            "spell_name": "Mage Hand",
            "caster_name": "Thim",
            "capabilities": ["interact_at_range", "trigger_pressure_plates"],
            "range_ft": 30,
        }
        return effect

    def test_light_spell_grants_light_source(self, mock_light_spell_effect):
        """Light spell should grant light_source capability."""
        from dnd_engine.systems.time_manager import EffectType

        # Set the effect_type correctly
        mock_light_spell_effect.effect_type = EffectType.SPELL

        game_state = MagicMock()
        game_state.party.characters = []
        game_state.time_manager.get_all_effects.return_value = [mock_light_spell_effect]

        resolver = CapabilityResolver(game_state)
        assert resolver.has_capability(Capability.LIGHT_SOURCE) is True

    def test_light_spell_source_details(self, mock_light_spell_effect):
        """Light spell capability should have correct details."""
        from dnd_engine.systems.time_manager import EffectType

        mock_light_spell_effect.effect_type = EffectType.SPELL

        game_state = MagicMock()
        game_state.party.characters = []
        game_state.time_manager.get_all_effects.return_value = [mock_light_spell_effect]

        resolver = CapabilityResolver(game_state)
        source = resolver.get_capability_source(Capability.LIGHT_SOURCE)

        assert source is not None
        assert source.source_type == "spell"
        assert source.source_name == "Light"
        assert source.character_name == "Gandalf"
        assert "60" in source.duration

    def test_mage_hand_grants_reach_30ft(self, mock_mage_hand_effect):
        """Mage Hand spell should grant reach_30ft capability."""
        from dnd_engine.systems.time_manager import EffectType

        mock_mage_hand_effect.effect_type = EffectType.SPELL

        game_state = MagicMock()
        game_state.party.characters = []
        game_state.time_manager.get_all_effects.return_value = [mock_mage_hand_effect]

        resolver = CapabilityResolver(game_state)
        assert resolver.has_capability(Capability.REACH_30FT) is True

    def test_telekinesis_grants_reach_60ft(self):
        """Telekinesis spell with 60ft range should grant reach_60ft."""
        from dnd_engine.systems.time_manager import EffectType

        effect = MagicMock()
        effect.effect_type = EffectType.SPELL
        effect.source = "Telekinesis"
        effect.remaining_value = 10
        effect.remaining_unit = "minutes"
        effect.effect_data = {
            "spell_name": "Telekinesis",
            "caster_name": "Elminster",
            "capabilities": ["interact_at_range"],
            "range_ft": 60,
        }

        game_state = MagicMock()
        game_state.party.characters = []
        game_state.time_manager.get_all_effects.return_value = [effect]

        resolver = CapabilityResolver(game_state)
        assert resolver.has_capability(Capability.REACH_60FT) is True


class TestCapabilityResolverRequirements:
    """Tests for requirement checking."""

    @pytest.fixture
    def mock_game_state_with_light(self):
        """Create game state with light_source capability."""
        char = MagicMock()
        char.name = "Sam"
        char.race = "human"
        char.inventory = MagicMock()
        char.inventory.items = {"torch": MagicMock(quantity=1)}

        game_state = MagicMock()
        game_state.party.characters = [char]
        game_state.time_manager.get_all_effects.return_value = []
        return game_state

    def test_check_requirements_requires_any_met(self, mock_game_state_with_light):
        """check_requirements with requires_any should pass when one is met."""
        resolver = CapabilityResolver(mock_game_state_with_light)

        met, missing = resolver.check_requirements(
            requires_any=["light_source", "darkvision"]
        )

        assert met is True
        assert missing == []

    def test_check_requirements_requires_any_not_met(self, mock_game_state_with_light):
        """check_requirements with requires_any should fail when none met."""
        resolver = CapabilityResolver(mock_game_state_with_light)

        met, missing = resolver.check_requirements(
            requires_any=["reach_30ft", "reach_60ft"]
        )

        assert met is False
        assert "reach_30ft" in missing
        assert "reach_60ft" in missing

    def test_check_requirements_requires_all_met(self):
        """check_requirements with requires_all should pass when all met."""
        char = MagicMock()
        char.name = "Legolas"
        char.race = "elf"  # Has darkvision
        char.inventory = MagicMock()
        char.inventory.items = {"torch": MagicMock(quantity=1)}  # Has light

        game_state = MagicMock()
        game_state.party.characters = [char]
        game_state.time_manager.get_all_effects.return_value = []

        resolver = CapabilityResolver(game_state)
        met, missing = resolver.check_requirements(
            requires_all=["light_source", "darkvision"]
        )

        assert met is True
        assert missing == []

    def test_check_requirements_requires_all_partial(self, mock_game_state_with_light):
        """check_requirements with requires_all should fail when some missing."""
        resolver = CapabilityResolver(mock_game_state_with_light)

        met, missing = resolver.check_requirements(
            requires_all=["light_source", "darkvision"]
        )

        assert met is False
        assert "darkvision" in missing
        assert "light_source" not in missing

    def test_check_requirements_empty_passes(self, mock_game_state_with_light):
        """check_requirements with no requirements should pass."""
        resolver = CapabilityResolver(mock_game_state_with_light)

        met, missing = resolver.check_requirements()

        assert met is True
        assert missing == []


class TestCapabilityResolverMultipleSources:
    """Tests for capabilities from multiple sources."""

    def test_multiple_characters_pool_capabilities(self):
        """Party should pool capabilities from all characters."""
        elf = MagicMock()
        elf.name = "Legolas"
        elf.race = "elf"  # Has darkvision
        elf.inventory = MagicMock()
        elf.inventory.items = {}

        human = MagicMock()
        human.name = "Sam"
        human.race = "human"
        human.inventory = MagicMock()
        human.inventory.items = {"torch": MagicMock(quantity=1)}  # Has light

        game_state = MagicMock()
        game_state.party.characters = [elf, human]
        game_state.time_manager.get_all_effects.return_value = []

        resolver = CapabilityResolver(game_state)

        # Party should have both capabilities
        assert resolver.has_capability(Capability.DARKVISION) is True
        assert resolver.has_capability(Capability.LIGHT_SOURCE) is True

    def test_capability_from_any_source_counts(self):
        """light_source from either item or spell should count."""
        from dnd_engine.systems.time_manager import EffectType

        # Character with no items
        char = MagicMock()
        char.name = "Wizard"
        char.race = "human"
        char.inventory = MagicMock()
        char.inventory.items = {}

        # But has Light spell active
        light_effect = MagicMock()
        light_effect.effect_type = EffectType.SPELL
        light_effect.source = "Light"
        light_effect.remaining_value = 60
        light_effect.remaining_unit = "minutes"
        light_effect.effect_data = {
            "spell_name": "Light",
            "caster_name": "Wizard",
            "light_level": "bright",
        }

        game_state = MagicMock()
        game_state.party.characters = [char]
        game_state.time_manager.get_all_effects.return_value = [light_effect]

        resolver = CapabilityResolver(game_state)
        assert resolver.has_capability(Capability.LIGHT_SOURCE) is True
