# ABOUTME: Tests for locked door system with multiple unlock methods
# ABOUTME: Covers skill checks, key-based unlocking, and backwards compatibility

import pytest
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.utils.events import EventBus
from dnd_engine.rules.loader import DataLoader


@pytest.fixture
def mock_dungeon_with_locked_door():
    """Create a test dungeon with locked and unlocked doors."""
    return {
        "name": "Test Dungeon",
        "start_room": "entrance",
        "rooms": {
            "entrance": {
                "name": "Entrance Hall",
                "description": "A simple entrance",
                "exits": {
                    "north": "simple_room",  # Simple string exit (unlocked)
                    "west": {  # Locked door with skill checks
                        "destination": "locked_room",
                        "locked": True,
                        "unlock_methods": [
                            {
                                "skill": "sleight_of_hand",
                                "tool_proficiency": "thieves_tools",
                                "dc": 12,
                                "description": "pick the lock",
                                "silent": True
                            },
                            {
                                "skill": "athletics",
                                "dc": 12,
                                "description": "break down the door",
                                "silent": False
                            }
                        ]
                    },
                    "east": {  # Door requiring a key
                        "destination": "key_room",
                        "locked": True,
                        "unlock_methods": [
                            {
                                "requires_item": "rusty_key",
                                "description": "unlock with the rusty key"
                            }
                        ]
                    }
                },
                "enemies": [],
                "items": [],
                "searchable": False
            },
            "simple_room": {
                "name": "Simple Room",
                "description": "An unlocked room",
                "exits": {"south": "entrance"},
                "enemies": [],
                "items": [],
                "searchable": False
            },
            "locked_room": {
                "name": "Locked Room",
                "description": "A previously locked room",
                "exits": {"east": "entrance"},
                "enemies": [],
                "items": [],
                "searchable": False
            },
            "key_room": {
                "name": "Key Room",
                "description": "A room that requires a key",
                "exits": {"west": "entrance"},
                "enemies": [],
                "items": [],
                "searchable": False
            }
        }
    }


@pytest.fixture
def test_party():
    """Create a test party with characters of varying skills."""
    # Rogue with high DEX and thieves' tools
    rogue = Character(
        name="Sneaky",
        character_class=CharacterClass.ROGUE,
        level=3,
        abilities=Abilities(
            strength=10,
            dexterity=18,  # +4 DEX
            constitution=12,
            intelligence=12,
            wisdom=12,
            charisma=10
        ),
        max_hp=20,
        ac=15
    )
    rogue.tool_proficiencies = ["thieves_tools"]
    rogue.skill_proficiencies.append("sleight_of_hand")  # Rogues are proficient in lockpicking skills

    # Fighter with high STR, low DEX
    fighter = Character(
        name="Bruiser",
        character_class=CharacterClass.FIGHTER,
        level=3,
        abilities=Abilities(
            strength=18,  # +4 STR
            dexterity=10,  # +0 DEX
            constitution=16,
            intelligence=8,
            wisdom=10,
            charisma=8
        ),
        max_hp=30,
        ac=18
    )
    fighter.skill_proficiencies.append("athletics")  # Fighters are proficient in physical skills

    return Party([rogue, fighter])


@pytest.fixture
def game_state_with_locked_doors(mock_dungeon_with_locked_door, test_party, monkeypatch):
    """Create a game state with locked doors for testing."""
    event_bus = EventBus()
    data_loader = DataLoader()

    # Mock the dungeon loading
    monkeypatch.setattr(data_loader, 'load_dungeon', lambda name: mock_dungeon_with_locked_door)

    game_state = GameState(
        party=test_party,
        dungeon_name="test_dungeon",
        event_bus=event_bus,
        data_loader=data_loader
    )

    return game_state


class TestLockedDoors:
    """Test locked door functionality."""

    def test_simple_unlocked_door_works(self, game_state_with_locked_doors):
        """Test backwards compatibility - simple string exits work as before."""
        game_state = game_state_with_locked_doors

        # Move north through unlocked door
        success = game_state.move("north", check_for_enemies=False)

        assert success is True
        assert game_state.current_room_id == "simple_room"

    def test_locked_door_blocks_movement(self, game_state_with_locked_doors):
        """Test that locked doors block movement."""
        game_state = game_state_with_locked_doors

        # Try to move west through locked door
        success = game_state.move("west", check_for_enemies=False)

        assert success is False
        assert game_state.current_room_id == "entrance"  # Still in entrance

    def test_is_exit_locked_detection(self, game_state_with_locked_doors):
        """Test detection of locked vs unlocked exits."""
        game_state = game_state_with_locked_doors

        # North is unlocked (simple string exit)
        assert game_state.is_exit_locked("north") is False

        # West is locked
        assert game_state.is_exit_locked("west") is True

        # East is locked (key required)
        assert game_state.is_exit_locked("east") is True

    def test_get_unlock_methods(self, game_state_with_locked_doors):
        """Test retrieving unlock methods for a locked door."""
        game_state = game_state_with_locked_doors

        # Get unlock methods for west door
        methods = game_state.get_unlock_methods("west")

        assert len(methods) == 2
        assert methods[0]["skill"] == "sleight_of_hand"
        assert methods[0]["tool_proficiency"] == "thieves_tools"
        assert methods[0]["dc"] == 12
        assert methods[0]["silent"] is True

        assert methods[1]["skill"] == "athletics"
        assert methods[1]["dc"] == 12
        assert methods[1]["silent"] is False

    def test_skill_check_success_unlocks_door(self, game_state_with_locked_doors, monkeypatch):
        """Test successful skill check unlocks the door."""
        from dnd_engine.core.dice import DiceRoll
        game_state = game_state_with_locked_doors
        rogue = game_state.party.characters[0]  # Sneaky the Rogue

        # Mock dice roll to always succeed (roll 20)
        def mock_roll(notation, advantage=False, disadvantage=False):
            return DiceRoll(notation="1d20", rolls=[20], modifier=0, advantage=advantage, disadvantage=disadvantage)
        monkeypatch.setattr(rogue._dice_roller, 'roll', mock_roll)

        # Attempt to pick the lock (method index 0)
        result = game_state.attempt_unlock("west", 0, rogue)

        assert result["success"] is True
        assert result["skill_check_result"]["success"] is True
        assert game_state.is_exit_locked("west") is False

        # Now movement should work
        success = game_state.move("west", check_for_enemies=False)
        assert success is True
        assert game_state.current_room_id == "locked_room"

    def test_skill_check_failure_keeps_door_locked(self, game_state_with_locked_doors, monkeypatch):
        """Test failed skill check keeps door locked but allows retry."""
        from dnd_engine.core.dice import DiceRoll
        game_state = game_state_with_locked_doors
        fighter = game_state.party.characters[1]  # Bruiser the Fighter

        # Mock dice roll to always fail (roll 1)
        def mock_roll(notation, advantage=False, disadvantage=False):
            return DiceRoll(notation="1d20", rolls=[1], modifier=0, advantage=advantage, disadvantage=disadvantage)
        monkeypatch.setattr(fighter._dice_roller, 'roll', mock_roll)

        # Attempt to pick the lock (fighter has no thieves tools, low DEX)
        result = game_state.attempt_unlock("west", 0, fighter)

        assert result["success"] is False
        assert result["skill_check_result"]["success"] is False
        assert game_state.is_exit_locked("west") is True

        # Door still locked, cannot move
        success = game_state.move("west", check_for_enemies=False)
        assert success is False

    def test_retry_after_failed_unlock(self, game_state_with_locked_doors, monkeypatch):
        """Test that player can retry after failing an unlock attempt."""
        from dnd_engine.core.dice import DiceRoll
        game_state = game_state_with_locked_doors
        rogue = game_state.party.characters[0]

        # First attempt: fail
        def mock_roll_fail(notation, advantage=False, disadvantage=False):
            return DiceRoll(notation="1d20", rolls=[1], modifier=0, advantage=advantage, disadvantage=disadvantage)
        monkeypatch.setattr(rogue._dice_roller, 'roll', mock_roll_fail)

        result1 = game_state.attempt_unlock("west", 0, rogue)
        assert result1["success"] is False
        assert game_state.is_exit_locked("west") is True

        # Second attempt: succeed
        def mock_roll_success(notation, advantage=False, disadvantage=False):
            return DiceRoll(notation="1d20", rolls=[20], modifier=0, advantage=advantage, disadvantage=disadvantage)
        monkeypatch.setattr(rogue._dice_roller, 'roll', mock_roll_success)

        result2 = game_state.attempt_unlock("west", 0, rogue)
        assert result2["success"] is True
        assert game_state.is_exit_locked("west") is False

    def test_multiple_unlock_methods(self, game_state_with_locked_doors, monkeypatch):
        """Test that multiple unlock methods all work."""
        from dnd_engine.core.dice import DiceRoll
        game_state = game_state_with_locked_doors
        fighter = game_state.party.characters[1]

        # Mock dice roll to succeed
        def mock_roll(notation, advantage=False, disadvantage=False):
            return DiceRoll(notation="1d20", rolls=[20], modifier=0, advantage=advantage, disadvantage=disadvantage)
        monkeypatch.setattr(fighter._dice_roller, 'roll', mock_roll)

        # Try second method (Athletics check) instead of lockpicking
        result = game_state.attempt_unlock("west", 1, fighter)

        assert result["success"] is True
        assert result["method"]["skill"] == "athletics"
        assert game_state.is_exit_locked("west") is False

    def test_key_based_unlock_with_item(self, game_state_with_locked_doors):
        """Test key-based unlocking succeeds when party has the item."""
        game_state = game_state_with_locked_doors
        rogue = game_state.party.characters[0]

        # Add the key to rogue's inventory
        rogue.inventory.add_item("rusty_key", "consumables")

        # Attempt unlock with key
        result = game_state.attempt_unlock("east", 0, rogue)

        assert result["success"] is True
        assert result.get("automatic") is True
        assert game_state.is_exit_locked("east") is False

    def test_key_based_unlock_without_item(self, game_state_with_locked_doors):
        """Test key-based unlocking fails when party doesn't have the item."""
        game_state = game_state_with_locked_doors
        rogue = game_state.party.characters[0]

        # Don't add the key - party doesn't have it

        # Attempt unlock without key
        result = game_state.attempt_unlock("east", 0, rogue)

        assert result["success"] is False
        assert "does not have" in result["reason"]
        assert game_state.is_exit_locked("east") is True

    def test_door_stays_unlocked(self, game_state_with_locked_doors, monkeypatch):
        """Test that once unlocked, a door remains unlocked."""
        from dnd_engine.core.dice import DiceRoll
        game_state = game_state_with_locked_doors
        rogue = game_state.party.characters[0]

        # Mock successful dice roll
        def mock_roll(notation, advantage=False, disadvantage=False):
            return DiceRoll(notation="1d20", rolls=[20], modifier=0, advantage=advantage, disadvantage=disadvantage)
        monkeypatch.setattr(rogue._dice_roller, 'roll', mock_roll)

        # Unlock the door
        result = game_state.attempt_unlock("west", 0, rogue)
        assert result["success"] is True

        # Move through
        game_state.move("west", check_for_enemies=False)
        assert game_state.current_room_id == "locked_room"

        # Move back
        game_state.move("east", check_for_enemies=False)
        assert game_state.current_room_id == "entrance"

        # Door should still be unlocked
        assert game_state.is_exit_locked("west") is False

        # Can move through again without unlocking
        success = game_state.move("west", check_for_enemies=False)
        assert success is True

    def test_tool_proficiency_affects_skill_check(self, game_state_with_locked_doors, monkeypatch):
        """Test that tool proficiency is considered in skill checks."""
        from dnd_engine.core.dice import DiceRoll
        game_state = game_state_with_locked_doors
        rogue = game_state.party.characters[0]  # Has thieves_tools proficiency
        fighter = game_state.party.characters[1]  # Does not have thieves_tools

        # Mock a medium roll that would succeed with proficiency but fail without
        def mock_roll_medium(notation, advantage=False, disadvantage=False):
            return DiceRoll(notation="1d20", rolls=[10], modifier=0, advantage=advantage, disadvantage=disadvantage)
        monkeypatch.setattr(rogue._dice_roller, 'roll', mock_roll_medium)

        # Rogue: DEX +4, proficiency +2, roll 10 = 16 total (vs DC 12) -> SUCCESS
        rogue_result = game_state.attempt_unlock("west", 0, rogue)
        assert rogue_result["success"] is True

        # Reset door to locked for next test
        exit_info = game_state.get_exit_info("west")
        exit_info["locked"] = True

        # Mock fighter's dice roller
        monkeypatch.setattr(fighter._dice_roller, 'roll', mock_roll_medium)

        # Fighter: DEX +0, no proficiency, roll 10 = 10 total (vs DC 12) -> FAIL
        fighter_result = game_state.attempt_unlock("west", 0, fighter)
        assert fighter_result["success"] is False

    def test_invalid_direction(self, game_state_with_locked_doors):
        """Test attempting to unlock a non-existent exit."""
        game_state = game_state_with_locked_doors
        rogue = game_state.party.characters[0]

        result = game_state.attempt_unlock("south", 0, rogue)

        assert result["success"] is False
        assert "No exit" in result["reason"]

    def test_invalid_method_index(self, game_state_with_locked_doors):
        """Test attempting to use an invalid unlock method index."""
        game_state = game_state_with_locked_doors
        rogue = game_state.party.characters[0]

        # West door only has 2 methods (index 0 and 1)
        result = game_state.attempt_unlock("west", 99, rogue)

        assert result["success"] is False
        assert "Invalid unlock method" in result["reason"]

    def test_get_exit_info_backwards_compatibility(self, game_state_with_locked_doors):
        """Test get_exit_info handles both string and dict exits."""
        game_state = game_state_with_locked_doors

        # String exit (simple)
        north_info = game_state.get_exit_info("north")
        assert north_info["destination"] == "simple_room"
        assert north_info["locked"] is False
        assert north_info["unlock_methods"] == []

        # Dict exit (locked)
        west_info = game_state.get_exit_info("west")
        assert west_info["destination"] == "locked_room"
        assert west_info["locked"] is True
        assert len(west_info["unlock_methods"]) == 2

    def test_skill_check_event_emitted(self, game_state_with_locked_doors, monkeypatch):
        """Test that skill check events are emitted for unlock attempts."""
        from dnd_engine.core.dice import DiceRoll
        game_state = game_state_with_locked_doors
        rogue = game_state.party.characters[0]

        # Track emitted events
        emitted_events = []
        def track_event(event):
            emitted_events.append(event)
        from dnd_engine.utils.events import EventType
        game_state.event_bus.subscribe(EventType.SKILL_CHECK, track_event)

        # Mock dice roll
        def mock_roll(notation, advantage=False, disadvantage=False):
            return DiceRoll(notation="1d20", rolls=[15], modifier=0, advantage=advantage, disadvantage=disadvantage)
        monkeypatch.setattr(rogue._dice_roller, 'roll', mock_roll)

        # Attempt unlock
        game_state.attempt_unlock("west", 0, rogue)

        # Check that skill check event was emitted
        assert len(emitted_events) > 0
        event_data = emitted_events[0].data
        assert event_data["character"] == "Sneaky"
        assert event_data["skill"] == "sleight_of_hand"
        assert event_data["dc"] == 12
        assert "action" in event_data
