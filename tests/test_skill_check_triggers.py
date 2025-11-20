# ABOUTME: Tests for skill check triggers during dungeon exploration
# ABOUTME: Covers passive Perception, examinable objects, examinable exits, and enhanced search

import pytest
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.utils.events import EventBus, EventType
from dnd_engine.rules.loader import DataLoader


@pytest.fixture
def high_perception_character():
    """Create a character with high Perception (Passive Perception 17)."""
    # STR, DEX, CON, INT, WIS, CHA
    abilities = Abilities(10, 14, 12, 10, 20, 10)  # +5 WIS mod
    char = Character(
        name="Keen Observer",
        character_class=CharacterClass.CLERIC,
        level=3,  # +2 proficiency
        abilities=abilities,
        max_hp=20,
        ac=14,
        skill_proficiencies=["perception"]  # +2 prof + 5 WIS = +7, Passive = 17
    )
    return char


@pytest.fixture
def low_perception_character():
    """Create a character with low Perception (Passive Perception 9)."""
    # STR, DEX, CON, INT, WIS, CHA
    abilities = Abilities(14, 10, 14, 10, 8, 10)  # -1 WIS mod
    char = Character(
        name="Oblivious Fighter",
        character_class=CharacterClass.FIGHTER,
        level=2,
        abilities=abilities,
        max_hp=22,
        ac=16
        # No perception proficiency
    )
    return char


@pytest.fixture
def medicine_proficient_character():
    """Create a character proficient in Medicine."""
    # STR, DEX, CON, INT, WIS, CHA
    abilities = Abilities(10, 14, 12, 10, 16, 10)
    char = Character(
        name="Healer",
        character_class=CharacterClass.CLERIC,
        level=3,
        abilities=abilities,
        max_hp=20,
        ac=14,
        skill_proficiencies=["medicine", "perception"]
    )
    return char


@pytest.fixture
def mock_dungeon_with_skill_checks():
    """Create a test dungeon with passive perception, examinable objects, and exits."""
    return {
        "name": "Test Crypt",
        "start_room": "entrance",
        "rooms": {
            "entrance": {
                "name": "Entrance Hall",
                "description": "A dusty entrance hall",
                "hidden_features": [
                    {
                        "type": "passive_perception",
                        "dc": 16,
                        "on_success": "You notice skeletal figures in the eastern chamber.",
                        "on_failure": None,
                        "trigger": "on_enter",
                        "once_per_room": True
                    }
                ],
                "examinable_objects": [
                    {
                        "id": "cultist_corpse",
                        "name": "fresh corpse",
                        "description": "A fresh corpse lies in the corner.",
                        "examine_checks": [
                            {
                                "skill": "medicine",
                                "dc": 12,
                                "on_success": "The victim's skull was surgically removed with precision.",
                                "on_failure": "You see signs of violence but cannot determine specifics."
                            }
                        ]
                    }
                ],
                "exits": {
                    "north": {
                        "destination": "chamber",
                        "examine_checks": [
                            {
                                "skill": "perception",
                                "dc": 14,
                                "action": "listen at the door",
                                "on_success": "You hear scraping sounds - bone dragging on stone.",
                                "on_failure": "You hear nothing unusual through the thick wood."
                            }
                        ]
                    },
                    "south": "hallway"  # Simple exit for testing
                },
                "enemies": [],
                "items": [],
                "searchable": True,
                "search_checks": [
                    {
                        "skill": "investigation",
                        "dc": 12,
                        "on_success": "You find a hidden compartment!",
                        "on_failure": "You find nothing beyond the obvious."
                    }
                ]
            },
            "chamber": {
                "name": "Northern Chamber",
                "description": "A dark chamber",
                "exits": {"south": "entrance"},
                "enemies": [],
                "items": [],
                "searchable": False
            },
            "hallway": {
                "name": "Southern Hallway",
                "description": "A long hallway",
                "exits": {"north": "entrance"},
                "enemies": [],
                "items": [],
                "searchable": False
            }
        }
    }


@pytest.fixture
def event_bus():
    """Create an event bus for testing."""
    return EventBus()


@pytest.fixture
def data_loader(mock_dungeon_with_skill_checks, monkeypatch):
    """Create a data loader with mocked dungeon."""
    loader = DataLoader()

    # Mock load_dungeon to return our test dungeon
    monkeypatch.setattr(
        loader,
        'load_dungeon',
        lambda name: mock_dungeon_with_skill_checks
    )

    return loader


class TestPassivePerception:
    """Test passive Perception checks on room entry."""

    def test_high_perception_notices_feature(
        self,
        high_perception_character,
        data_loader,
        event_bus
    ):
        """Character with Passive Perception 17 should notice DC 16 feature."""
        party = Party([high_perception_character])
        game_state = GameState(
            party=party,
            dungeon_name="test_crypt",
            event_bus=event_bus,
            data_loader=data_loader
        )

        # Track events
        skill_check_events = []

        def capture_event(event):
            if event.type == EventType.SKILL_CHECK:
                skill_check_events.append(event)

        event_bus.subscribe(EventType.SKILL_CHECK, capture_event)

        # Start the game (which enters the first room and triggers passive check)
        game_state.start()

        # Should have one skill check event
        assert len(skill_check_events) == 1

        event_data = skill_check_events[0].data
        assert event_data["character"] == "Keen Observer"
        assert event_data["skill"] == "perception"
        assert event_data["passive"] is True
        assert event_data["dc"] == 16
        assert event_data["total"] == 17
        assert event_data["success"] is True
        assert "skeletal figures" in event_data["success_text"]

    def test_low_perception_misses_feature(
        self,
        low_perception_character,
        data_loader,
        event_bus
    ):
        """Character with Passive Perception 9 should miss DC 16 feature."""
        party = Party([low_perception_character])
        game_state = GameState(
            party=party,
            dungeon_name="test_crypt",
            event_bus=event_bus,
            data_loader=data_loader
        )

        skill_check_events = []

        def capture_event(event):
            if event.type == EventType.SKILL_CHECK:
                skill_check_events.append(event)

        event_bus.subscribe(EventType.SKILL_CHECK, capture_event)

        game_state.start()

        assert len(skill_check_events) == 1
        event_data = skill_check_events[0].data
        assert event_data["character"] == "Oblivious Fighter"
        assert event_data["success"] is False
        assert event_data["success_text"] is None

    def test_passive_check_only_once_per_room(
        self,
        high_perception_character,
        data_loader,
        event_bus
    ):
        """Passive checks should only trigger once per room."""
        party = Party([high_perception_character])
        game_state = GameState(
            party=party,
            dungeon_name="test_crypt",
            event_bus=event_bus,
            data_loader=data_loader
        )

        skill_check_events = []

        def capture_event(event):
            if event.type == EventType.SKILL_CHECK:
                skill_check_events.append(event)

        event_bus.subscribe(EventType.SKILL_CHECK, capture_event)

        # Start game (first entry)
        game_state.start()
        assert len(skill_check_events) == 1

        # Leave and re-enter the room
        game_state.move("south")  # Move to hallway
        game_state.move("north")  # Return to entrance

        # Should still be only 1 skill check (not triggered again)
        assert len(skill_check_events) == 1

    def test_multiple_characters_checked(
        self,
        high_perception_character,
        low_perception_character,
        data_loader,
        event_bus
    ):
        """All party members should be checked for passive Perception."""
        party = Party([high_perception_character, low_perception_character])
        game_state = GameState(
            party=party,
            dungeon_name="test_crypt",
            event_bus=event_bus,
            data_loader=data_loader
        )

        skill_check_events = []

        def capture_event(event):
            if event.type == EventType.SKILL_CHECK:
                skill_check_events.append(event)

        event_bus.subscribe(EventType.SKILL_CHECK, capture_event)

        game_state.start()

        # Should have two events (one per character)
        assert len(skill_check_events) == 2

        # One succeeds, one fails
        successes = [e.data["success"] for e in skill_check_events]
        assert True in successes
        assert False in successes


class TestExaminableObjects:
    """Test examinable objects with skill checks."""

    def test_get_examinable_objects(self, medicine_proficient_character, data_loader, event_bus):
        """Should be able to list examinable objects in room."""
        party = Party([medicine_proficient_character])
        game_state = GameState(
            party=party,
            dungeon_name="test_crypt",
            event_bus=event_bus,
            data_loader=data_loader
        )

        game_state.start()

        objects = game_state.get_examinable_objects()
        assert len(objects) == 1
        assert objects[0]["id"] == "cultist_corpse"
        assert objects[0]["name"] == "fresh corpse"

    def test_examine_object_success(
        self,
        medicine_proficient_character,
        data_loader,
        event_bus
    ):
        """Examining object with successful skill check should reveal information."""
        party = Party([medicine_proficient_character])
        game_state = GameState(
            party=party,
            dungeon_name="test_crypt",
            event_bus=event_bus,
            data_loader=data_loader
        )

        game_state.start()

        skill_check_events = []

        def capture_event(event):
            if event.type == EventType.SKILL_CHECK and event.data.get("action", "").startswith("examine"):
                skill_check_events.append(event)

        event_bus.subscribe(EventType.SKILL_CHECK, capture_event)

        # Examine the corpse
        result = game_state.examine_object("cultist_corpse", medicine_proficient_character)

        assert result["success"] in [True, False]  # Depends on dice roll
        assert result["object_name"] == "fresh corpse"
        assert result["already_checked"] is False
        assert len(result["results"]) == 1

        # Event should be emitted
        assert len(skill_check_events) == 1
        event_data = skill_check_events[0].data
        assert event_data["skill"] == "medicine"
        assert event_data["dc"] == 12

    def test_examine_already_checked_object(
        self,
        medicine_proficient_character,
        data_loader,
        event_bus
    ):
        """Re-examining an object should show already checked message."""
        party = Party([medicine_proficient_character])
        game_state = GameState(
            party=party,
            dungeon_name="test_crypt",
            event_bus=event_bus,
            data_loader=data_loader
        )

        game_state.start()

        # Examine once
        game_state.examine_object("cultist_corpse", medicine_proficient_character)

        # Examine again
        result = game_state.examine_object("cultist_corpse", medicine_proficient_character)

        assert result["success"] is False
        assert result["already_checked"] is True
        assert len(result["results"]) == 0

    def test_examine_nonexistent_object(
        self,
        medicine_proficient_character,
        data_loader,
        event_bus
    ):
        """Examining non-existent object should return error."""
        party = Party([medicine_proficient_character])
        game_state = GameState(
            party=party,
            dungeon_name="test_crypt",
            event_bus=event_bus,
            data_loader=data_loader
        )

        game_state.start()

        result = game_state.examine_object("nonexistent", medicine_proficient_character)

        assert result["success"] is False
        assert "error" in result


class TestExaminableExits:
    """Test examinable exits (listening at doors)."""

    def test_get_examinable_exits(
        self,
        high_perception_character,
        data_loader,
        event_bus
    ):
        """Should be able to list examinable exits."""
        party = Party([high_perception_character])
        game_state = GameState(
            party=party,
            dungeon_name="test_crypt",
            event_bus=event_bus,
            data_loader=data_loader
        )

        game_state.start()

        exits = game_state.get_examinable_exits()
        assert "north" in exits
        assert "south" not in exits  # Simple exit, not examinable

    def test_examine_exit(
        self,
        high_perception_character,
        data_loader,
        event_bus
    ):
        """Examining an exit should perform skill check."""
        party = Party([high_perception_character])
        game_state = GameState(
            party=party,
            dungeon_name="test_crypt",
            event_bus=event_bus,
            data_loader=data_loader
        )

        game_state.start()

        skill_check_events = []

        def capture_event(event):
            if event.type == EventType.SKILL_CHECK and "listen" in event.data.get("action", ""):
                skill_check_events.append(event)

        event_bus.subscribe(EventType.SKILL_CHECK, capture_event)

        result = game_state.examine_exit("north", high_perception_character)

        assert result["success"] in [True, False]
        assert result["direction"] == "north"
        assert len(result["results"]) == 1

        # Event should be emitted
        assert len(skill_check_events) == 1
        event_data = skill_check_events[0].data
        assert event_data["skill"] == "perception"
        assert event_data["dc"] == 14
        assert "listen at the door" in event_data["action"]

    def test_examine_non_examinable_exit(
        self,
        high_perception_character,
        data_loader,
        event_bus
    ):
        """Examining a non-examinable exit should return error."""
        party = Party([high_perception_character])
        game_state = GameState(
            party=party,
            dungeon_name="test_crypt",
            event_bus=event_bus,
            data_loader=data_loader
        )

        game_state.start()

        result = game_state.examine_exit("south", high_perception_character)

        assert result["success"] is False
        assert "error" in result


class TestEnhancedSearch:
    """Test enhanced search with skill checks."""

    def test_search_with_skill_check(
        self,
        high_perception_character,
        data_loader,
        event_bus
    ):
        """Searching room with search_checks should require skill check."""
        party = Party([high_perception_character])
        game_state = GameState(
            party=party,
            dungeon_name="test_crypt",
            event_bus=event_bus,
            data_loader=data_loader
        )

        game_state.start()

        skill_check_events = []

        def capture_event(event):
            if event.type == EventType.SKILL_CHECK and event.data.get("action") == "search room":
                skill_check_events.append(event)

        event_bus.subscribe(EventType.SKILL_CHECK, capture_event)

        # Add items to the room for successful search
        room = game_state.get_current_room()
        room["items"] = [{"type": "item", "id": "test_item"}]

        result = game_state.search_room(high_perception_character)

        # Event should be emitted
        assert len(skill_check_events) == 1
        event_data = skill_check_events[0].data
        assert event_data["skill"] == "investigation"
        assert event_data["dc"] == 12

        # Result depends on dice roll
        assert "success" in result
        assert "already_searched" in result
        assert result["already_searched"] is False

    def test_search_already_searched_room(
        self,
        high_perception_character,
        data_loader,
        event_bus
    ):
        """Re-searching a room should not require another check."""
        party = Party([high_perception_character])
        game_state = GameState(
            party=party,
            dungeon_name="test_crypt",
            event_bus=event_bus,
            data_loader=data_loader
        )

        game_state.start()

        room = game_state.get_current_room()
        room["items"] = [{"type": "item", "id": "test_item"}]

        # Search once
        game_state.search_room(high_perception_character)

        # Search again
        result = game_state.search_room(high_perception_character)

        assert result["success"] is True
        assert result["already_searched"] is True

    def test_search_failed_check_marks_searched(
        self,
        low_perception_character,
        data_loader,
        event_bus
    ):
        """Failed search check should still mark room as searched."""
        party = Party([low_perception_character])
        game_state = GameState(
            party=party,
            dungeon_name="test_crypt",
            event_bus=event_bus,
            data_loader=data_loader
        )

        game_state.start()

        room = game_state.get_current_room()
        room["items"] = [{"type": "item", "id": "test_item"}]

        # Search (likely to fail with low investigation)
        result = game_state.search_room(low_perception_character)

        # Room should be marked as searched
        assert room["searched"] is True

        # Second search should show already_searched
        result2 = game_state.search_room(low_perception_character)
        assert result2["already_searched"] is True
