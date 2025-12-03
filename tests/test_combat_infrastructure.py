"""
Tests for combat infrastructure (Issue #174 Phase 1).

Tests the new combat infrastructure systems added to the game engine:
- Combat history tracking (CombatEvent)
- Battlefield state queries (BattlefieldState)
- Enemy numbering system (InitiativeTracker)
- Target lookup by reference
"""

import time

import pytest

from dnd_engine.core.character import Abilities, Character, CharacterClass
from dnd_engine.core.creature import Creature
from dnd_engine.core.game_state import CombatEvent, GameState
from dnd_engine.core.party import Party
from dnd_engine.systems.initiative import InitiativeTracker


def create_test_character(name: str, char_class: str = "fighter", level: int = 1) -> Character:
    """Helper to create a test character with minimal setup."""
    char_class_enum = CharacterClass.FIGHTER if char_class == "fighter" else CharacterClass.CLERIC
    return Character(
        name=name,
        character_class=char_class_enum,
        level=level,
        abilities=Abilities(15, 14, 13, 10, 12, 8),
        max_hp=10,
        ac=15,
        race="human",
    )


def create_test_creature(name: str, max_hp: int = 7, ac: int = 15) -> Creature:
    """Helper to create a test creature (enemy) with minimal setup."""
    return Creature(name=name, max_hp=max_hp, ac=ac, abilities=Abilities(10, 10, 10, 10, 10, 10))


class TestCombatEventTracking:
    """Test combat event recording and retrieval."""

    def test_record_combat_event(self):
        """Test recording a single combat event."""
        party = Party([])
        game_state = GameState(party, "test_dungeon")

        event = CombatEvent(
            timestamp=time.time(),
            event_type="attack",
            attacker="Frodo",
            defender="Goblin 1",
            damage=5,
            critical=False,
            description="Frodo hit Goblin 1 for 5 damage",
        )

        game_state.record_combat_event(event)

        assert len(game_state.combat_history) == 1
        assert game_state.combat_history[0] == event

    def test_record_multiple_events(self):
        """Test recording multiple combat events."""
        party = Party([])
        game_state = GameState(party, "test_dungeon")

        for i in range(5):
            event = CombatEvent(
                timestamp=time.time(),
                event_type="attack",
                attacker=f"Attacker{i}",
                defender=f"Defender{i}",
                damage=i,
                description=f"Action {i}",
            )
            game_state.record_combat_event(event)

        assert len(game_state.combat_history) == 5

    def test_combat_history_auto_trimming(self):
        """Test that combat history auto-trims to max size."""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        game_state.max_combat_history_size = 10

        # Record 15 events (more than max)
        for i in range(15):
            event = CombatEvent(
                timestamp=time.time(),
                event_type="attack",
                attacker=f"Attacker{i}",
                defender="Target",
                damage=i,
                description=f"Action {i}",
            )
            game_state.record_combat_event(event)

        # Should only keep last 10
        assert len(game_state.combat_history) == 10
        # Should have the most recent events (5-14)
        assert game_state.combat_history[0].attacker == "Attacker5"
        assert game_state.combat_history[-1].attacker == "Attacker14"

    def test_get_recent_combat_history(self):
        """Test retrieving recent combat events."""
        party = Party([])
        game_state = GameState(party, "test_dungeon")

        # Record 20 events
        for i in range(20):
            event = CombatEvent(
                timestamp=time.time(),
                event_type="attack",
                attacker=f"Attacker{i}",
                defender="Target",
                damage=i,
                description=f"Action {i}",
            )
            game_state.record_combat_event(event)

        # Get last 5
        recent = game_state.get_recent_combat_history(5)
        assert len(recent) == 5
        assert recent[0].attacker == "Attacker15"
        assert recent[-1].attacker == "Attacker19"

    def test_get_recent_combat_history_less_than_count(self):
        """Test get_recent when fewer events exist than requested."""
        party = Party([])
        game_state = GameState(party, "test_dungeon")

        # Record only 3 events
        for i in range(3):
            event = CombatEvent(
                timestamp=time.time(),
                event_type="attack",
                attacker=f"Attacker{i}",
                defender="Target",
                damage=i,
                description=f"Action {i}",
            )
            game_state.record_combat_event(event)

        # Request 10 (more than available)
        recent = game_state.get_recent_combat_history(10)
        assert len(recent) == 3

    def test_clear_combat_history(self):
        """Test clearing combat history."""
        party = Party([])
        game_state = GameState(party, "test_dungeon")

        # Record some events
        for i in range(5):
            event = CombatEvent(
                timestamp=time.time(),
                event_type="attack",
                attacker=f"Attacker{i}",
                defender="Target",
                damage=i,
                description=f"Action {i}",
            )
            game_state.record_combat_event(event)

        assert len(game_state.combat_history) == 5

        game_state.clear_combat_history()

        assert len(game_state.combat_history) == 0

    def test_combat_event_with_details(self):
        """Test combat event with additional details dict."""
        party = Party([])
        game_state = GameState(party, "test_dungeon")

        event = CombatEvent(
            timestamp=time.time(),
            event_type="spell",
            attacker="Wizard",
            defender="Enemy",
            damage=20,
            critical=False,
            description="Wizard cast Fireball",
            details={
                "spell_name": "Fireball",
                "spell_level": 3,
                "save_dc": 15,
                "area": "20ft radius",
            },
        )

        game_state.record_combat_event(event)

        retrieved = game_state.combat_history[0]
        assert retrieved.details["spell_name"] == "Fireball"
        assert retrieved.details["spell_level"] == 3


class TestBattlefieldState:
    """Test battlefield state queries."""

    @pytest.fixture
    def game_with_combat(self):
        """Create a game state with active combat."""
        # Create party with two characters
        char1 = create_test_character("Frodo", "fighter", 1)
        char1.current_hp = 10

        char2 = create_test_character("Sam", "cleric", 1)
        char2.current_hp = 12

        party = Party([char1, char2])
        game_state = GameState(party, "test_dungeon")

        # Create enemies
        goblin1 = create_test_creature("Goblin", max_hp=7)
        goblin1.current_hp = 5
        goblin1.ac = 15

        goblin2 = create_test_creature("Goblin", max_hp=7)
        goblin2.current_hp = 7
        goblin2.ac = 15

        # Start combat
        game_state.in_combat = True
        game_state.active_enemies = [goblin1, goblin2]
        game_state.initiative_tracker = InitiativeTracker()

        # Add combatants to initiative
        game_state.initiative_tracker.add_combatant(char1)
        game_state.initiative_tracker.add_combatant(char2)
        game_state.initiative_tracker.add_combatant(goblin1)
        game_state.initiative_tracker.add_combatant(goblin2)

        # Assign combat numbers
        game_state.initiative_tracker.assign_combat_numbers([char1, char2])

        return game_state

    def test_get_battlefield_state_in_combat(self, game_with_combat):
        """Test getting battlefield state during combat."""
        state = game_with_combat.get_battlefield_state()

        assert state.in_combat is True
        assert len(state.party_combatants) == 2
        assert len(state.enemy_combatants) == 2
        assert state.round_number == 0

    def test_battlefield_state_party_info(self, game_with_combat):
        """Test that party combatant info is correct."""
        state = game_with_combat.get_battlefield_state()

        # Find Frodo in the party combatants
        frodo = next(c for c in state.party_combatants if c.name == "Frodo")

        assert frodo.display_name == "Frodo"
        assert frodo.current_hp == 10
        assert frodo.is_alive is True
        assert frodo.is_player is True
        assert frodo.ac > 0  # Has some AC

    def test_battlefield_state_enemy_info(self, game_with_combat):
        """Test that enemy combatant info includes combat numbers."""
        state = game_with_combat.get_battlefield_state()

        # Enemies should have display names with numbers
        display_names = [c.display_name for c in state.enemy_combatants]
        assert "Goblin 1" in display_names
        assert "Goblin 2" in display_names

        # Check one enemy's details
        goblin = state.enemy_combatants[0]
        assert goblin.name == "Goblin"
        assert goblin.is_player is False
        assert goblin.ac == 15

    def test_get_battlefield_state_not_in_combat(self):
        """Test getting battlefield state when not in combat."""
        party = Party([])
        game_state = GameState(party, "test_dungeon")

        state = game_state.get_battlefield_state()

        assert state.in_combat is False
        assert len(state.party_combatants) == 0
        assert len(state.enemy_combatants) == 0
        assert state.round_number == 0
        assert state.current_turn == ""


class TestEnemyNumbering:
    """Test enemy combat number assignment."""

    def test_assign_combat_numbers_to_duplicates(self):
        """Test that duplicate enemy names get sequential numbers."""
        tracker = InitiativeTracker()

        # Create characters (won't get numbers)
        char = create_test_character("Frodo", "fighter", 1)

        # Create duplicate enemies
        goblin1 = create_test_creature("Goblin", max_hp=7)
        goblin2 = create_test_creature("Goblin", max_hp=7)
        goblin3 = create_test_creature("Goblin", max_hp=7)

        tracker.add_combatant(char)
        tracker.add_combatant(goblin1)
        tracker.add_combatant(goblin2)
        tracker.add_combatant(goblin3)

        tracker.assign_combat_numbers([char])

        # Check that goblins got numbers 1, 2, 3
        goblin_entries = [e for e in tracker.combatants if e.creature.name == "Goblin"]
        numbers = sorted([e.combat_number for e in goblin_entries])
        assert numbers == [1, 2, 3]

        # Check display names
        display_names = sorted([e.display_name for e in goblin_entries])
        assert display_names == ["Goblin 1", "Goblin 2", "Goblin 3"]

    def test_players_dont_get_numbers(self):
        """Test that player characters don't get combat numbers."""
        tracker = InitiativeTracker()

        char1 = create_test_character("Frodo", "fighter", 1)
        char2 = create_test_character("Sam", "cleric", 1)
        goblin = create_test_creature("Goblin", max_hp=7)

        tracker.add_combatant(char1)
        tracker.add_combatant(char2)
        tracker.add_combatant(goblin)

        tracker.assign_combat_numbers([char1, char2])

        # Characters should have no numbers
        frodo_entry = next(e for e in tracker.combatants if e.creature == char1)
        sam_entry = next(e for e in tracker.combatants if e.creature == char2)

        assert frodo_entry.combat_number is None
        assert frodo_entry.display_name == "Frodo"
        assert sam_entry.combat_number is None
        assert sam_entry.display_name == "Sam"

        # Goblin should have number
        goblin_entry = next(e for e in tracker.combatants if e.creature == goblin)
        assert goblin_entry.combat_number == 1
        assert goblin_entry.display_name == "Goblin 1"

    def test_single_enemy_gets_number(self):
        """Test that even a single enemy gets a number for consistency."""
        tracker = InitiativeTracker()

        char = create_test_character("Frodo", "fighter", 1)
        goblin = create_test_creature("Goblin", max_hp=7)

        tracker.add_combatant(char)
        tracker.add_combatant(goblin)

        tracker.assign_combat_numbers([char])

        goblin_entry = next(e for e in tracker.combatants if e.creature == goblin)
        assert goblin_entry.combat_number == 1
        assert goblin_entry.display_name == "Goblin 1"

    def test_mixed_enemy_types(self):
        """Test numbering with multiple different enemy types."""
        tracker = InitiativeTracker()

        char = create_test_character("Frodo", "fighter", 1)
        goblin1 = create_test_creature("Goblin", max_hp=7)
        goblin2 = create_test_creature("Goblin", max_hp=7)
        orc1 = create_test_creature("Orc", max_hp=15)
        orc2 = create_test_creature("Orc", max_hp=15)
        wolf = create_test_creature("Wolf", max_hp=11)

        tracker.add_combatant(char)
        tracker.add_combatant(goblin1)
        tracker.add_combatant(goblin2)
        tracker.add_combatant(orc1)
        tracker.add_combatant(orc2)
        tracker.add_combatant(wolf)

        tracker.assign_combat_numbers([char])

        # Check goblins
        goblin_entries = [e for e in tracker.combatants if e.creature.name == "Goblin"]
        goblin_numbers = sorted([e.combat_number for e in goblin_entries])
        assert goblin_numbers == [1, 2]

        # Check orcs
        orc_entries = [e for e in tracker.combatants if e.creature.name == "Orc"]
        orc_numbers = sorted([e.combat_number for e in orc_entries])
        assert orc_numbers == [1, 2]

        # Check wolf
        wolf_entry = next(e for e in tracker.combatants if e.creature.name == "Wolf")
        assert wolf_entry.combat_number == 1


class TestTargetLookup:
    """Test finding combatants by reference string."""

    @pytest.fixture
    def tracker_with_combatants(self):
        """Create an initiative tracker with various combatants."""
        tracker = InitiativeTracker()

        # Characters
        frodo = create_test_character("Frodo", "fighter", 1)
        sam = create_test_character("Sam", "cleric", 1)

        # Enemies
        goblin1 = create_test_creature("Goblin", max_hp=7)
        goblin2 = create_test_creature("Goblin", max_hp=7)
        goblin3 = create_test_creature("Goblin", max_hp=7)
        orc = create_test_creature("Orc", max_hp=15)

        tracker.add_combatant(frodo)
        tracker.add_combatant(sam)
        tracker.add_combatant(goblin1)
        tracker.add_combatant(goblin2)
        tracker.add_combatant(goblin3)
        tracker.add_combatant(orc)

        tracker.assign_combat_numbers([frodo, sam])

        return tracker

    def test_find_by_pure_number(self, tracker_with_combatants):
        """Test finding enemy by just number."""
        result = tracker_with_combatants.find_combatant_by_reference("2")

        assert result is not None
        assert result.combat_number == 2
        assert result.creature.name == "Goblin"

    def test_find_by_name_and_number(self, tracker_with_combatants):
        """Test finding enemy by 'name number' format."""
        result = tracker_with_combatants.find_combatant_by_reference("goblin 3")

        assert result is not None
        assert result.combat_number == 3
        assert result.creature.name == "Goblin"

    def test_find_by_name_case_insensitive(self, tracker_with_combatants):
        """Test that name matching is case-insensitive."""
        result = tracker_with_combatants.find_combatant_by_reference("GOBLIN 2")

        assert result is not None
        assert result.combat_number == 2

    def test_find_player_by_name(self, tracker_with_combatants):
        """Test finding player character by name."""
        result = tracker_with_combatants.find_combatant_by_reference("frodo")

        assert result is not None
        assert result.creature.name == "Frodo"
        assert result.combat_number is None

    def test_find_single_enemy_by_name(self, tracker_with_combatants):
        """Test finding single enemy type by just name."""
        result = tracker_with_combatants.find_combatant_by_reference("orc")

        assert result is not None
        assert result.creature.name == "Orc"
        assert result.combat_number == 1

    def test_find_nonexistent_returns_none(self, tracker_with_combatants):
        """Test that searching for nonexistent combatant returns None."""
        result = tracker_with_combatants.find_combatant_by_reference("dragon")

        assert result is None

    def test_find_invalid_number_returns_none(self, tracker_with_combatants):
        """Test that invalid number returns None."""
        result = tracker_with_combatants.find_combatant_by_reference("99")

        assert result is None

    def test_find_dead_enemy_returns_none(self, tracker_with_combatants):
        """Test that dead enemies are not returned."""
        # Kill goblin 1 (be specific with name to avoid ambiguity)
        goblin_entry = tracker_with_combatants.find_combatant_by_reference("goblin 1")
        goblin_entry.creature.current_hp = 0

        result = tracker_with_combatants.find_combatant_by_reference("goblin 1")

        assert result is None

    def test_find_with_extra_whitespace(self, tracker_with_combatants):
        """Test that extra whitespace is handled gracefully."""
        result = tracker_with_combatants.find_combatant_by_reference("  goblin 2  ")

        assert result is not None
        assert result.combat_number == 2
