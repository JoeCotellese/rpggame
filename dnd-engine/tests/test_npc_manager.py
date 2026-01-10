# ABOUTME: Unit tests for NPCManager class
# ABOUTME: Tests NPC loading, lookup, room queries, and state serialization

from unittest.mock import Mock

import pytest

from dnd_engine.core.npc import NPC
from dnd_engine.core.npc_manager import NPCManager


class TestNPCManager:
    """Tests for NPCManager class."""

    @pytest.fixture
    def mock_loader(self):
        """Create a mock data loader with sample NPC data."""
        mock = Mock()
        # load_npcs returns a dict with "npcs" key
        mock.load_npcs.return_value = {
            "npcs": {
                "marta_innkeeper": {
                    "id": "marta_innkeeper",
                    "name": "Marta",
                    "display_name": "Marta, the Innkeeper",
                    "home_location": "arden.inn_common_room",
                    "current_location": "arden.inn_common_room",
                    "can_move": False,
                    "personality": {
                        "traits": ["warm"],
                        "speech_style": "folksy",
                        "attitude_default": "friendly",
                        "suspicion_of_strangers": "mild",
                    },
                    "knowledge": {
                        "general": ["Runs the inn"],
                        "quest_hooks": ["investigate_crypt"],
                        "local_lore": [],
                    },
                    "dialogue": {
                        "greeting": "Welcome!",
                        "farewell": "Safe travels!",
                    },
                },
                "father_aldric": {
                    "id": "father_aldric",
                    "name": "Father Aldric",
                    "display_name": "Father Aldric",
                    "home_location": "arden.chapel_interior",
                    "current_location": "arden.chapel_interior",
                    "can_move": True,
                    "personality": {
                        "traits": ["devout"],
                        "speech_style": "formal",
                        "attitude_default": "welcoming",
                        "suspicion_of_strangers": "none",
                    },
                    "knowledge": {
                        "general": ["Serves as priest"],
                        "quest_hooks": ["investigate_crypt"],
                        "local_lore": [],
                    },
                    "dialogue": {
                        "greeting": "Blessings upon you.",
                        "farewell": "May the Light guide you.",
                    },
                },
            }
        }
        return mock

    @pytest.fixture
    def manager(self, mock_loader):
        """Create NPCManager with mock loader."""
        return NPCManager("test_campaign", mock_loader)

    def test_init_loads_npcs(self, manager, mock_loader):
        """Test that NPCManager loads NPCs on initialization."""
        mock_loader.load_npcs.assert_called_once_with("test_campaign")
        assert len(manager.npcs) == 2

    def test_init_no_npcs_logs_warning(self):
        """Test NPCManager logs warning when NPC file not found."""
        mock_loader = Mock()
        mock_loader.load_npcs.side_effect = FileNotFoundError("No NPCs")

        # Should not raise, just log warning
        manager = NPCManager("missing_campaign", mock_loader)
        assert len(manager.npcs) == 0

    def test_get_npc_by_id(self, manager):
        """Test getting NPC by ID."""
        npc = manager.get_npc("marta_innkeeper")

        assert npc is not None
        assert npc.id == "marta_innkeeper"
        assert npc.name == "Marta"

    def test_get_npc_not_found(self, manager):
        """Test getting non-existent NPC returns None."""
        npc = manager.get_npc("nonexistent")
        assert npc is None

    def test_get_npc_by_name(self, manager):
        """Test getting NPC by name (case-insensitive)."""
        npc = manager.get_npc_by_name("marta")

        assert npc is not None
        assert npc.id == "marta_innkeeper"

    def test_get_npc_by_name_partial(self, manager):
        """Test getting NPC by partial name."""
        npc = manager.get_npc_by_name("Aldric")

        assert npc is not None
        assert npc.id == "father_aldric"

    def test_get_npc_by_name_not_found(self, manager):
        """Test getting NPC by non-existent name returns None."""
        npc = manager.get_npc_by_name("nobody")
        assert npc is None

    def test_get_npcs_in_room(self, manager):
        """Test getting all NPCs in a specific room."""
        npcs = manager.get_npcs_in_room("arden.inn_common_room")

        assert len(npcs) == 1
        assert npcs[0].id == "marta_innkeeper"

    def test_get_npcs_in_room_empty(self, manager):
        """Test getting NPCs in room with none."""
        npcs = manager.get_npcs_in_room("arden.empty_room")

        assert len(npcs) == 0

    def test_get_npcs_in_room_multiple(self, mock_loader):
        """Test getting multiple NPCs in same room."""
        # Add another NPC to the inn
        mock_loader.load_npcs.return_value["npcs"]["bar_patron"] = {
            "id": "bar_patron",
            "name": "Drunk Patron",
            "home_location": "arden.inn_common_room",
            "current_location": "arden.inn_common_room",
        }
        manager = NPCManager("test_campaign", mock_loader)

        npcs = manager.get_npcs_in_room("arden.inn_common_room")

        assert len(npcs) == 2

    def test_get_all_npcs(self, manager):
        """Test getting all NPCs."""
        all_npcs = manager.get_all_npcs()

        assert len(all_npcs) == 2
        npc_ids = [npc.id for npc in all_npcs]
        assert "marta_innkeeper" in npc_ids
        assert "father_aldric" in npc_ids

    def test_serialize_state_preserves_location(self, manager):
        """Test that serialization preserves NPC locations."""
        # Move Aldric to a different location
        aldric = manager.get_npc("father_aldric")
        aldric.current_location = "arden.town_square"
        aldric.player_reputation = 10

        state = manager.serialize_state()

        assert "father_aldric" in state
        assert state["father_aldric"]["current_location"] == "arden.town_square"
        assert state["father_aldric"]["player_reputation"] == 10

    def test_deserialize_state_restores_location(self, manager):
        """Test that deserialization restores NPC state."""
        saved_state = {
            "father_aldric": {
                "current_location": "arden.market_square",
                "player_reputation": 5,
            },
            "marta_innkeeper": {
                "current_location": "arden.inn_common_room",
                "player_reputation": -3,
            },
        }

        manager.deserialize_state(saved_state)

        aldric = manager.get_npc("father_aldric")
        assert aldric.current_location == "arden.market_square"
        assert aldric.player_reputation == 5

        marta = manager.get_npc("marta_innkeeper")
        assert marta.player_reputation == -3

    def test_deserialize_state_handles_missing_npcs(self, manager):
        """Test deserialization ignores unknown NPCs in saved state."""
        saved_state = {
            "unknown_npc": {
                "current_location": "somewhere",
                "player_reputation": 100,
            },
        }

        # Should not raise an error
        manager.deserialize_state(saved_state)

    def test_npcs_created_as_npc_objects(self, manager):
        """Test that NPCs are proper NPC instances."""
        npc = manager.get_npc("marta_innkeeper")

        assert isinstance(npc, NPC)
        assert hasattr(npc, "personality")
        assert hasattr(npc, "knowledge")
        assert callable(getattr(npc, "get_greeting", None))

    def test_update_npc_locations_based_on_schedule(self, manager):
        """Test NPC location updates based on schedule."""
        # Father Aldric has can_move=True, give him a schedule
        aldric = manager.get_npc("father_aldric")
        aldric.schedule = {
            "morning": "arden.chapel_interior",
            "afternoon": "arden.outside_chapel",
            "evening": "arden.chapel_interior",
        }

        # Update to afternoon
        movements = manager.update_npc_locations("afternoon")

        assert len(movements) == 1
        npc, old_loc, new_loc = movements[0]
        assert npc.id == "father_aldric"
        assert old_loc == "arden.chapel_interior"
        assert new_loc == "arden.outside_chapel"
        assert aldric.current_location == "arden.outside_chapel"

    def test_update_npc_locations_no_movement(self, manager):
        """Test NPC locations don't change without schedules."""
        movements = manager.update_npc_locations("afternoon")

        # Neither NPC has a schedule set by default in mock
        assert len(movements) == 0
