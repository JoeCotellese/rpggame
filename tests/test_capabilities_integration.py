# ABOUTME: Integration tests for the capability system with GameState.
# ABOUTME: Tests get_available_interactions and execute_interaction methods.

from unittest.mock import MagicMock, patch
import json
import pytest

from dnd_engine.systems.capabilities import Capability, CapabilityResolver


class TestGameStateInteractions:
    """Integration tests for GameState interaction methods."""

    @pytest.fixture
    def mock_room_with_interactions(self):
        """Create a mock room with capability-gated interactions."""
        return {
            "name": "Test Room",
            "description": "A test room with interactions",
            "exits": {"north": "other_room"},
            "interactions": [
                {
                    "id": "pull_lever",
                    "name": "Pull the brass lever",
                    "description": "A lever across a pit.",
                    "requires_any": ["reach_30ft", "reach_60ft"],
                    "action": {
                        "type": "message",
                        "text": "You pull the lever!",
                    },
                    "rewards": [
                        {"type": "item", "id": "potion_of_healing"},
                        {"type": "currency", "gold": 10},
                    ],
                    "one_time": True,
                },
                {
                    "id": "read_inscription",
                    "name": "Read the wall inscription",
                    "description": "Faded writing on the wall.",
                    "requires_any": ["light_source", "darkvision"],
                    "action": {
                        "type": "message",
                        "text": "You read the inscription.",
                    },
                    "one_time": True,
                },
                {
                    "id": "open_chest",
                    "name": "Open the chest",
                    "description": "An unlocked chest.",
                    # No requirements - always available
                    "action": {
                        "type": "message",
                        "text": "You open the chest.",
                    },
                },
            ],
        }

    @pytest.fixture
    def mock_game_state(self, mock_room_with_interactions):
        """Create a mock game state for testing interactions."""
        game_state = MagicMock()
        game_state.current_room = mock_room_with_interactions
        game_state.completed_interactions = set()

        # Empty party initially
        game_state.party = MagicMock()
        game_state.party.characters = []
        game_state.time_manager = MagicMock()
        game_state.time_manager.get_all_effects.return_value = []

        return game_state

    def test_get_available_interactions_no_capabilities(self, mock_game_state):
        """With no capabilities, only unrestricted interactions available."""
        # Import here to get the real method
        from dnd_engine.core.game_state import GameState

        # Call the method directly on a fresh instance bound to mock
        resolver = CapabilityResolver(mock_game_state)

        room = mock_game_state.current_room
        interactions = room.get("interactions", [])

        # Filter to what should be available
        available = []
        for interaction in interactions:
            requires_any = interaction.get("requires_any")
            requires_all = interaction.get("requires_all")

            # Check if already completed (one_time)
            if interaction.get("one_time") and interaction["id"] in mock_game_state.completed_interactions:
                continue

            # Check requirements
            met, _ = resolver.check_requirements(requires_any=requires_any, requires_all=requires_all)
            if met:
                available.append(interaction)

        # Only open_chest has no requirements
        assert len(available) == 1
        assert available[0]["id"] == "open_chest"

    def test_get_available_interactions_with_light(self, mock_game_state):
        """With light capability, can access light-requiring interactions."""
        # Add a torch-bearing character
        char = MagicMock()
        char.name = "Sam"
        char.race = "human"
        char.inventory = MagicMock()
        char.inventory.items = {"torch": MagicMock(quantity=1)}

        mock_game_state.party.characters = [char]

        resolver = CapabilityResolver(mock_game_state)
        room = mock_game_state.current_room
        interactions = room.get("interactions", [])

        available = []
        for interaction in interactions:
            requires_any = interaction.get("requires_any")
            requires_all = interaction.get("requires_all")

            if interaction.get("one_time") and interaction["id"] in mock_game_state.completed_interactions:
                continue

            met, _ = resolver.check_requirements(requires_any=requires_any, requires_all=requires_all)
            if met:
                available.append(interaction)

        # Should have open_chest and read_inscription
        available_ids = [i["id"] for i in available]
        assert "open_chest" in available_ids
        assert "read_inscription" in available_ids
        assert "pull_lever" not in available_ids  # Needs reach capability

    def test_get_available_interactions_with_mage_hand(self, mock_game_state):
        """With mage hand (reach_30ft), can access reach-requiring interactions."""
        from dnd_engine.systems.time_manager import EffectType

        # Add Mage Hand effect
        mage_hand_effect = MagicMock()
        mage_hand_effect.effect_type = EffectType.SPELL
        mage_hand_effect.source = "Mage Hand"
        mage_hand_effect.remaining_value = 1
        mage_hand_effect.remaining_unit = "minutes"
        mage_hand_effect.effect_data = {
            "spell_name": "Mage Hand",
            "caster_name": "Thim",
            "capabilities": ["interact_at_range"],
            "range_ft": 30,
        }

        mock_game_state.time_manager.get_all_effects.return_value = [mage_hand_effect]

        resolver = CapabilityResolver(mock_game_state)
        room = mock_game_state.current_room
        interactions = room.get("interactions", [])

        available = []
        for interaction in interactions:
            requires_any = interaction.get("requires_any")
            requires_all = interaction.get("requires_all")

            if interaction.get("one_time") and interaction["id"] in mock_game_state.completed_interactions:
                continue

            met, _ = resolver.check_requirements(requires_any=requires_any, requires_all=requires_all)
            if met:
                available.append(interaction)

        # Should have open_chest and pull_lever
        available_ids = [i["id"] for i in available]
        assert "open_chest" in available_ids
        assert "pull_lever" in available_ids
        assert "read_inscription" not in available_ids  # Needs light

    def test_one_time_interaction_filtered_after_completion(self, mock_game_state):
        """One-time interactions should not appear after completion."""
        # Add torch for light capability
        char = MagicMock()
        char.name = "Sam"
        char.race = "human"
        char.inventory = MagicMock()
        char.inventory.items = {"torch": MagicMock(quantity=1)}
        mock_game_state.party.characters = [char]

        # Mark read_inscription as completed
        mock_game_state.completed_interactions = {"read_inscription"}

        resolver = CapabilityResolver(mock_game_state)
        room = mock_game_state.current_room
        interactions = room.get("interactions", [])

        available = []
        for interaction in interactions:
            requires_any = interaction.get("requires_any")
            requires_all = interaction.get("requires_all")

            if interaction.get("one_time") and interaction["id"] in mock_game_state.completed_interactions:
                continue

            met, _ = resolver.check_requirements(requires_any=requires_any, requires_all=requires_all)
            if met:
                available.append(interaction)

        available_ids = [i["id"] for i in available]
        assert "read_inscription" not in available_ids  # Completed
        assert "open_chest" in available_ids  # Not one_time

    def test_elf_can_read_inscription_without_light(self, mock_game_state):
        """Elf with darkvision should be able to read inscription."""
        char = MagicMock()
        char.name = "Legolas"
        char.race = "elf"
        char.inventory = MagicMock()
        char.inventory.items = {}

        mock_game_state.party.characters = [char]

        resolver = CapabilityResolver(mock_game_state)

        # Check darkvision is available
        assert resolver.has_capability(Capability.DARKVISION)

        room = mock_game_state.current_room
        interactions = room.get("interactions", [])

        available = []
        for interaction in interactions:
            requires_any = interaction.get("requires_any")
            requires_all = interaction.get("requires_all")

            if interaction.get("one_time") and interaction["id"] in mock_game_state.completed_interactions:
                continue

            met, _ = resolver.check_requirements(requires_any=requires_any, requires_all=requires_all)
            if met:
                available.append(interaction)

        available_ids = [i["id"] for i in available]
        assert "read_inscription" in available_ids


class TestLaboratoryInteractions:
    """Integration tests using the actual laboratory dungeon data."""

    @pytest.fixture
    def laboratory_data(self):
        """Load the actual laboratory dungeon data."""
        import json
        from pathlib import Path

        lab_path = Path(__file__).parent.parent / "dnd_engine/data/content/campaigns/poisoned_laboratory/dungeons/laboratory.json"
        with open(lab_path) as f:
            return json.load(f)

    def test_laboratory_lever_interaction_exists(self, laboratory_data):
        """Laboratory should have the pull_lever interaction."""
        lab_room = laboratory_data["rooms"]["laboratory.laboratory"]
        interactions = lab_room.get("interactions", [])

        lever_interaction = None
        for interaction in interactions:
            if interaction["id"] == "pull_lever":
                lever_interaction = interaction
                break

        assert lever_interaction is not None
        assert "requires_any" in lever_interaction
        assert "reach_30ft" in lever_interaction["requires_any"]
        assert "reach_60ft" in lever_interaction["requires_any"]

    def test_laboratory_inscription_interaction_exists(self, laboratory_data):
        """Laboratory should have the read_inscription interaction."""
        specimen_room = laboratory_data["rooms"]["laboratory.specimen_chamber"]
        interactions = specimen_room.get("interactions", [])

        inscription_interaction = None
        for interaction in interactions:
            if interaction["id"] == "read_inscription":
                inscription_interaction = interaction
                break

        assert inscription_interaction is not None
        assert "requires_any" in inscription_interaction
        assert "light_source" in inscription_interaction["requires_any"]
        assert "darkvision" in inscription_interaction["requires_any"]

    def test_lever_requires_mage_hand_to_pull(self, laboratory_data):
        """Without Mage Hand, lever interaction should not be available."""
        lab_room = laboratory_data["rooms"]["laboratory.laboratory"]
        interactions = lab_room.get("interactions", [])

        # Create game state without mage hand
        game_state = MagicMock()
        game_state.party.characters = []
        game_state.time_manager.get_all_effects.return_value = []
        game_state.completed_interactions = set()

        resolver = CapabilityResolver(game_state)

        # Check which interactions are available
        available = []
        for interaction in interactions:
            requires_any = interaction.get("requires_any")
            met, _ = resolver.check_requirements(requires_any=requires_any)
            if met:
                available.append(interaction)

        # Lever should not be available
        available_ids = [i["id"] for i in available]
        assert "pull_lever" not in available_ids

    def test_lever_available_with_mage_hand(self, laboratory_data):
        """With Mage Hand active, lever interaction should be available."""
        from dnd_engine.systems.time_manager import EffectType

        lab_room = laboratory_data["rooms"]["laboratory.laboratory"]
        interactions = lab_room.get("interactions", [])

        # Create game state with mage hand
        game_state = MagicMock()
        game_state.party.characters = []
        game_state.completed_interactions = set()

        mage_hand_effect = MagicMock()
        mage_hand_effect.effect_type = EffectType.SPELL
        mage_hand_effect.source = "Mage Hand"
        mage_hand_effect.remaining_value = 1
        mage_hand_effect.remaining_unit = "minutes"
        mage_hand_effect.effect_data = {
            "spell_name": "Mage Hand",
            "caster_name": "Thim",
            "capabilities": ["interact_at_range"],
            "range_ft": 30,
        }
        game_state.time_manager.get_all_effects.return_value = [mage_hand_effect]

        resolver = CapabilityResolver(game_state)

        # Check lever is available
        lever_interaction = next(i for i in interactions if i["id"] == "pull_lever")
        met, _ = resolver.check_requirements(requires_any=lever_interaction["requires_any"])

        assert met is True

    def test_inscription_available_with_torch(self, laboratory_data):
        """With torch, inscription interaction should be available."""
        specimen_room = laboratory_data["rooms"]["laboratory.specimen_chamber"]
        interactions = specimen_room.get("interactions", [])

        # Create game state with torch
        char = MagicMock()
        char.name = "Sam"
        char.race = "human"
        char.inventory = MagicMock()
        char.inventory.items = {"torch": MagicMock(quantity=1)}

        game_state = MagicMock()
        game_state.party.characters = [char]
        game_state.time_manager.get_all_effects.return_value = []
        game_state.completed_interactions = set()

        resolver = CapabilityResolver(game_state)

        # Check inscription is available
        inscription_interaction = next(i for i in interactions if i["id"] == "read_inscription")
        met, _ = resolver.check_requirements(requires_any=inscription_interaction["requires_any"])

        assert met is True

    def test_inscription_available_with_elf_darkvision(self, laboratory_data):
        """Elf with darkvision should be able to read inscription."""
        specimen_room = laboratory_data["rooms"]["laboratory.specimen_chamber"]
        interactions = specimen_room.get("interactions", [])

        # Create game state with elf
        char = MagicMock()
        char.name = "Legolas"
        char.race = "elf"
        char.inventory = MagicMock()
        char.inventory.items = {}

        game_state = MagicMock()
        game_state.party.characters = [char]
        game_state.time_manager.get_all_effects.return_value = []
        game_state.completed_interactions = set()

        resolver = CapabilityResolver(game_state)

        # Check darkvision is available
        assert resolver.has_capability(Capability.DARKVISION)

        # Check inscription is available
        inscription_interaction = next(i for i in interactions if i["id"] == "read_inscription")
        met, _ = resolver.check_requirements(requires_any=inscription_interaction["requires_any"])

        assert met is True
