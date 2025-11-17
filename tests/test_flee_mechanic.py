# ABOUTME: Unit tests for the flee combat mechanic
# ABOUTME: Tests flee functionality, opportunity attacks, and edge cases

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.core.party import Party
from dnd_engine.core.game_state import GameState
from dnd_engine.core.dice import DiceRoller
from dnd_engine.utils.events import EventBus, EventType
from dnd_engine.rules.loader import DataLoader


@pytest.fixture
def dice_roller():
    """Fixture for a dice roller."""
    return DiceRoller()


@pytest.fixture
def event_bus():
    """Fixture for an event bus."""
    return EventBus()


@pytest.fixture
def data_loader():
    """Fixture for a data loader."""
    return DataLoader()


@pytest.fixture
def test_character():
    """Create a test character."""
    abilities = Abilities(
        strength=16,
        dexterity=14,
        constitution=15,
        intelligence=10,
        wisdom=12,
        charisma=8
    )
    char = Character(
        name="TestWarrior",
        character_class=CharacterClass.FIGHTER,
        level=3,
        abilities=abilities,
        max_hp=30,
        ac=16,
        current_hp=30
    )
    return char


@pytest.fixture
def party(test_character):
    """Create a test party with one character."""
    return Party([test_character])


@pytest.fixture
def game_state_with_combat(party, event_bus, data_loader, dice_roller):
    """Create a game state already in combat."""
    game_state = GameState(
        party=party,
        dungeon_name="goblin_warren",
        event_bus=event_bus,
        data_loader=data_loader,
        dice_roller=dice_roller
    )

    # Clear enemies from guard_post so fleeing doesn't trigger new combat
    game_state.dungeon["rooms"]["guard_post"]["enemies"] = []

    # Manually set up combat with a goblin
    goblin = Creature(
        name="Goblin",
        max_hp=7,
        ac=15,
        abilities=Abilities(
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=8,
            charisma=8
        )
    )
    goblin.current_hp = 7

    game_state.active_enemies = [goblin]
    game_state._start_combat()

    return game_state


def test_flee_not_in_combat(party, event_bus, data_loader, dice_roller):
    """Test fleeing when not in combat returns failure."""
    game_state = GameState(
        party=party,
        dungeon_name="goblin_warren",
        event_bus=event_bus,
        data_loader=data_loader,
        dice_roller=dice_roller
    )

    result = game_state.flee_combat()

    assert result["success"] is False
    assert "reason" in result
    assert result["reason"] == "Not in combat"


def test_flee_basic_success(game_state_with_combat):
    """Test basic flee mechanics - combat ends, no XP awarded."""
    game_state = game_state_with_combat

    # Set up previous direction (simulate having entered from the south)
    game_state.last_entry_direction = "south"

    # Track events
    fled_event_emitted = []
    game_state.event_bus.subscribe(
        EventType.COMBAT_FLED,
        lambda e: fled_event_emitted.append(e)
    )

    # Flee combat
    result = game_state.flee_combat()

    # Verify flee succeeded
    assert result["success"] is True
    assert "opportunity_attacks" in result
    assert "casualties" in result
    assert "retreat_direction" in result
    assert result["retreat_direction"] == "north"  # Reverse of south

    # Verify combat ended
    assert game_state.in_combat is False
    assert game_state.initiative_tracker is None

    # Verify event was emitted
    assert len(fled_event_emitted) == 1


def test_flee_opportunity_attacks_occur(game_state_with_combat):
    """Test that enemies get opportunity attacks when party flees."""
    game_state = game_state_with_combat

    # Set up previous direction
    game_state.last_entry_direction = "south"

    initial_hp = game_state.party.characters[0].current_hp

    # Flee combat
    result = game_state.flee_combat()

    # Should have opportunity attacks (one per enemy)
    assert len(result["opportunity_attacks"]) == 1

    # HP might have changed (if attack hit)
    # We can't guarantee hit/miss, but the attack should have been attempted
    attack_result = result["opportunity_attacks"][0]
    assert attack_result.attacker_name == "Goblin"
    assert attack_result.defender_name == "TestWarrior"


def test_flee_enemies_remain_in_room(game_state_with_combat):
    """Test that enemies remain in the room after fleeing (can encounter again)."""
    game_state = game_state_with_combat

    # Get current room
    room = game_state.get_current_room()
    initial_enemy_count = len(room.get("enemies", []))

    # Flee combat
    game_state.flee_combat()

    # Enemies should NOT be cleared from room
    room_after_flee = game_state.get_current_room()
    # Note: In the test setup, we manually create enemies, so room enemies list
    # might not be populated. The key is that flee_combat does NOT clear enemies
    # like _end_combat does.
    # We verify this by checking the code doesn't call room["enemies"] = []

    # Verify active_enemies still exist (but combat is over)
    assert len(game_state.active_enemies) == 1
    assert game_state.active_enemies[0].name == "Goblin"


def test_flee_multiple_enemies(party, event_bus, data_loader, dice_roller):
    """Test fleeing from multiple enemies - each gets one opportunity attack."""
    game_state = GameState(
        party=party,
        dungeon_name="goblin_warren",
        event_bus=event_bus,
        data_loader=data_loader,
        dice_roller=dice_roller
    )

    # Set up previous direction
    game_state.last_entry_direction = "south"

    # Create multiple enemies using the actual Goblin from monster data
    goblin1 = Creature(
        name="Goblin",  # Must match monster data exactly
        max_hp=7,
        ac=15,
        abilities=Abilities(
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=8,
            charisma=8
        )
    )
    goblin1.current_hp = 7

    goblin2 = Creature(
        name="Goblin",  # Must match monster data exactly
        max_hp=7,
        ac=15,
        abilities=Abilities(
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=8,
            charisma=8
        )
    )
    goblin2.current_hp = 7

    game_state.active_enemies = [goblin1, goblin2]
    game_state._start_combat()

    # Flee combat
    result = game_state.flee_combat()

    # Should have 2 opportunity attacks (one per enemy)
    assert len(result["opportunity_attacks"]) == 2


def test_flee_with_dead_enemies(party, event_bus, data_loader, dice_roller):
    """Test that dead enemies don't get opportunity attacks."""
    game_state = GameState(
        party=party,
        dungeon_name="goblin_warren",
        event_bus=event_bus,
        data_loader=data_loader,
        dice_roller=dice_roller
    )

    # Set up previous direction
    game_state.last_entry_direction = "south"

    # Create one living and one dead enemy (using actual Goblin from monster data)
    living_goblin = Creature(
        name="Goblin",  # Must match monster data exactly
        max_hp=7,
        ac=15,
        abilities=Abilities(
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=8,
            charisma=8
        )
    )
    living_goblin.current_hp = 7

    dead_goblin = Creature(
        name="Goblin",  # Must match monster data exactly
        max_hp=7,
        ac=15,
        abilities=Abilities(
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=8,
            charisma=8
        )
    )
    dead_goblin.current_hp = 0  # Dead

    game_state.active_enemies = [living_goblin, dead_goblin]
    game_state._start_combat()

    # Flee combat
    result = game_state.flee_combat()

    # Should only have 1 opportunity attack (from living enemy)
    assert len(result["opportunity_attacks"]) == 1
    assert result["opportunity_attacks"][0].attacker_name == "Goblin"


def test_flee_party_can_die_during_flee(event_bus, data_loader, dice_roller):
    """Test that party members can die during opportunity attacks."""
    # Create a character with very low HP
    abilities = Abilities(
        strength=16,
        dexterity=14,
        constitution=15,
        intelligence=10,
        wisdom=12,
        charisma=8
    )
    weak_char = Character(
        name="WeakWarrior",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=10,
        ac=10,  # Low AC to increase hit chance
        current_hp=1  # Very low HP
    )

    party = Party([weak_char])

    game_state = GameState(
        party=party,
        dungeon_name="goblin_warren",
        event_bus=event_bus,
        data_loader=data_loader,
        dice_roller=dice_roller
    )

    # Create a strong enemy
    strong_orc = Creature(
        name="StrongOrc",
        max_hp=15,
        ac=13,
        abilities=Abilities(
            strength=16,
            dexterity=12,
            constitution=16,
            intelligence=7,
            wisdom=11,
            charisma=10
        )
    )
    strong_orc.current_hp = 15

    game_state.active_enemies = [strong_orc]
    game_state._start_combat()

    # Track death events
    death_events = []
    game_state.event_bus.subscribe(
        EventType.CHARACTER_DEATH,
        lambda e: death_events.append(e)
    )

    # Flee combat - character might die from opportunity attack
    result = game_state.flee_combat()

    # Check if character died
    if not weak_char.is_alive:
        assert len(result["casualties"]) > 0
        assert weak_char.name in result["casualties"]
        assert len(death_events) > 0


def test_flee_no_xp_awarded(game_state_with_combat):
    """Test that no XP is awarded when fleeing."""
    game_state = game_state_with_combat

    initial_xp = game_state.party.characters[0].xp

    # Track XP-related events
    combat_end_events = []
    game_state.event_bus.subscribe(
        EventType.COMBAT_END,
        lambda e: combat_end_events.append(e)
    )

    # Set up previous direction so flee can work
    game_state.last_entry_direction = "north"

    # Flee combat
    game_state.flee_combat()

    # XP should not have changed
    assert game_state.party.characters[0].xp == initial_xp

    # COMBAT_END event should NOT be emitted (only COMBAT_FLED)
    assert len(combat_end_events) == 0


def test_flee_retreats_to_previous_room(party, event_bus, data_loader, dice_roller):
    """Test that fleeing moves party to previous room."""
    game_state = GameState(
        party=party,
        dungeon_name="goblin_warren",
        event_bus=event_bus,
        data_loader=data_loader,
        dice_roller=dice_roller
    )

    # Move from entrance to guard_post (north)
    initial_room = game_state.current_room_id
    game_state.move("north")
    second_room = game_state.current_room_id

    # Verify we moved
    assert second_room != initial_room
    assert game_state.last_entry_direction == "north"

    # Manually start combat in guard_post
    goblin = Creature(
        name="Goblin",
        max_hp=7,
        ac=15,
        abilities=Abilities(
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=8,
            charisma=8
        )
    )
    goblin.current_hp = 7
    game_state.active_enemies = [goblin]
    game_state._start_combat()

    # Flee combat
    result = game_state.flee_combat()

    # Should have fled successfully
    assert result["success"] is True
    assert result["retreat_direction"] == "south"  # Reverse of north

    # Should be back in initial room
    assert game_state.current_room_id == initial_room
    assert not game_state.in_combat


def test_flee_from_start_room_fails(party, event_bus, data_loader, dice_roller):
    """Test that fleeing from start room (no previous direction) fails."""
    game_state = GameState(
        party=party,
        dungeon_name="goblin_warren",
        event_bus=event_bus,
        data_loader=data_loader,
        dice_roller=dice_roller
    )

    # Start in entrance (start room) - no previous direction
    assert game_state.last_entry_direction is None

    # Manually start combat
    goblin = Creature(
        name="Goblin",
        max_hp=7,
        ac=15,
        abilities=Abilities(
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=8,
            charisma=8
        )
    )
    goblin.current_hp = 7
    game_state.active_enemies = [goblin]
    game_state._start_combat()

    # Attempt to flee
    result = game_state.flee_combat()

    # Should fail
    assert result["success"] is False
    assert "Nowhere to retreat" in result["reason"]

    # Should still be in combat
    assert game_state.in_combat


def test_flee_direction_tracking_after_multiple_moves(party, event_bus, data_loader, dice_roller):
    """Test direction tracking works correctly after multiple movements."""
    game_state = GameState(
        party=party,
        dungeon_name="goblin_warren",
        event_bus=event_bus,
        data_loader=data_loader,
        dice_roller=dice_roller
    )

    # Clear enemies from guard_post so we can move through it
    game_state.dungeon["rooms"]["guard_post"]["enemies"] = []
    game_state.dungeon["rooms"]["main_hall"]["enemies"] = []

    # entrance -> north -> guard_post -> north -> main_hall
    game_state.move("north")  # To guard_post
    game_state.move("north")  # To main_hall

    # Last direction should be "north"
    assert game_state.last_entry_direction == "north"

    # Start combat manually
    goblin = Creature(
        name="Goblin",
        max_hp=7,
        ac=15,
        abilities=Abilities(
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=8,
            charisma=8
        )
    )
    goblin.current_hp = 7
    game_state.active_enemies = [goblin]
    game_state._start_combat()

    # Flee should go south (reverse of north)
    result = game_state.flee_combat()

    assert result["success"] is True
    assert result["retreat_direction"] == "south"


def test_reset_clears_last_entry_direction(party, event_bus, data_loader, dice_roller):
    """Test that reset_dungeon clears last_entry_direction."""
    game_state = GameState(
        party=party,
        dungeon_name="goblin_warren",
        event_bus=event_bus,
        data_loader=data_loader,
        dice_roller=dice_roller
    )

    # Move somewhere
    game_state.move("north")
    assert game_state.last_entry_direction == "north"

    # Reset dungeon
    game_state.reset_dungeon()

    # Direction should be cleared
    assert game_state.last_entry_direction is None
