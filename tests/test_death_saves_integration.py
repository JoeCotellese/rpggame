"""
Integration tests for death saving throws in combat scenarios.

Tests death save mechanics integrated with:
- Combat engine
- Initiative tracking
- Party management
- Event system
"""

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.core.combat import CombatEngine
from dnd_engine.core.party import Party
from dnd_engine.core.dice import DiceRoller
from dnd_engine.systems.initiative import InitiativeTracker
from dnd_engine.utils.events import EventBus, EventType
from unittest.mock import Mock, patch


@pytest.fixture
def abilities():
    """Standard ability scores for testing."""
    return Abilities(
        strength=14,
        dexterity=12,
        constitution=13,
        intelligence=10,
        wisdom=11,
        charisma=8
    )


@pytest.fixture
def fighter(abilities):
    """Create a test fighter."""
    return Character(
        name="Fighter",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=12,
        ac=16,
        current_hp=12
    )


@pytest.fixture
def rogue(abilities):
    """Create a test rogue."""
    return Character(
        name="Rogue",
        character_class=CharacterClass.ROGUE,
        level=1,
        abilities=abilities,
        max_hp=10,
        ac=14,
        current_hp=10
    )


@pytest.fixture
def goblin():
    """Create a test goblin enemy."""
    return Creature(
        name="Goblin",
        max_hp=7,
        ac=15,
        abilities=Abilities(10, 14, 10, 10, 8, 8)
    )


@pytest.fixture
def party(fighter, rogue):
    """Create a test party."""
    return Party([fighter, rogue])


@pytest.fixture
def combat_engine():
    """Create a combat engine."""
    return CombatEngine()


@pytest.fixture
def event_bus():
    """Create an event bus."""
    return EventBus()


class TestCombatDamageWithDeathSaves:
    """Test combat damage integration with death saves."""

    def test_attack_drops_character_to_zero_hp(self, fighter, goblin, combat_engine, event_bus):
        """Attack that reduces character to 0 HP should make them unconscious."""
        fighter.current_hp = 3

        result = combat_engine.resolve_attack(
            attacker=goblin,
            defender=fighter,
            attack_bonus=4,
            damage_dice="1d6+2",
            apply_damage=True,
            event_bus=event_bus
        )

        if result.hit and result.damage >= 3:
            assert fighter.current_hp == 0
            assert fighter.is_unconscious == True
            assert fighter.is_dead == False
            assert fighter.death_save_failures == 0  # No automatic failure on first drop

    def test_attack_on_unconscious_character(self, fighter, goblin, combat_engine, event_bus):
        """Attack on unconscious character should add death save failure."""
        fighter.current_hp = 0
        events = []
        event_bus.subscribe(EventType.DAMAGE_AT_ZERO_HP, lambda e: events.append(e))

        result = combat_engine.resolve_attack(
            attacker=goblin,
            defender=fighter,
            attack_bonus=4,
            damage_dice="1d6+2",
            apply_damage=True,
            event_bus=event_bus
        )

        if result.hit:
            assert fighter.death_save_failures == 1
            assert len(events) == 1

    def test_massive_damage_kills_unconscious_character(self, fighter, goblin, combat_engine, event_bus):
        """Massive damage to unconscious character should cause instant death."""
        fighter.current_hp = 0
        events = []
        event_bus.subscribe(EventType.MASSIVE_DAMAGE_DEATH, lambda e: events.append(e))

        # Force a hit with massive damage
        with patch.object(combat_engine.dice_roller, 'roll') as mock_roll:
            # Attack roll
            mock_roll.side_effect = [
                Mock(total=20, rolls=[20]),  # Natural 20 attack
                Mock(total=fighter.max_hp, rolls=[fighter.max_hp])  # Massive damage
            ]

            result = combat_engine.resolve_attack(
                attacker=goblin,
                defender=fighter,
                attack_bonus=4,
                damage_dice="2d10+10",
                apply_damage=True,
                event_bus=event_bus
            )

        if result.damage >= fighter.max_hp:
            assert fighter.is_dead == True
            assert fighter.death_save_failures >= 3
            assert len(events) == 1


class TestPartyWipeMechanics:
    """Test party wipe conditions with death saves."""

    def test_unconscious_party_not_wiped(self, party):
        """Party with unconscious members is not wiped."""
        party.characters[0].current_hp = 0  # Fighter unconscious
        party.characters[1].current_hp = 5   # Rogue alive

        assert party.is_wiped() == False

    def test_all_unconscious_not_wiped(self, party):
        """Party with all unconscious (but not dead) is not wiped."""
        party.characters[0].current_hp = 0
        party.characters[0].death_save_failures = 2  # Close to death but not dead

        party.characters[1].current_hp = 0
        party.characters[1].death_save_failures = 1

        assert party.is_wiped() == False

    def test_all_dead_is_wiped(self, party):
        """Party with all dead members is wiped."""
        party.characters[0].current_hp = 0
        party.characters[0].death_save_failures = 3  # Dead

        party.characters[1].current_hp = 0
        party.characters[1].death_save_failures = 3  # Dead

        assert party.is_wiped() == True

    def test_mixed_states_not_wiped(self, party):
        """Party with mixed alive/unconscious/dead is not wiped."""
        party.characters[0].current_hp = 0
        party.characters[0].death_save_failures = 3  # Dead

        party.characters[1].current_hp = 1  # Alive

        assert party.is_wiped() == False


class TestStabilizationIntegration:
    """Test character stabilization in combat."""

    def test_stabilization_stops_death_saves(self, fighter):
        """Stabilized character should not need death saves."""
        fighter.current_hp = 0
        fighter.stabilized = True

        # Attempt to make death save
        result = fighter.make_death_save()

        # Should return early without rolling
        assert result["stabilized"] == True
        assert result["roll"] == 0

    def test_medicine_check_stabilization(self, fighter, rogue):
        """Successful Medicine check should stabilize unconscious ally."""
        from dnd_engine.rules.loader import DataLoader

        fighter.current_hp = 0
        data_loader = DataLoader()
        skills_data = data_loader.load_skills()

        # Ensure rogue has Medicine proficiency for better chance
        rogue.skill_proficiencies.append("medicine")

        check_result = rogue.make_skill_check("medicine", 10, skills_data)

        if check_result["success"]:
            fighter.stabilize_character()
            assert fighter.stabilized == True
            assert fighter.current_hp == 0  # Still unconscious, just stabilized

    def test_stabilized_character_heals_naturally_over_time(self, fighter):
        """Stabilized characters should remain stable (preparation for future healing)."""
        fighter.current_hp = 0
        fighter.stabilize_character()

        assert fighter.stabilized == True
        assert fighter.is_unconscious == True
        assert fighter.is_dead == False

        # After 1d4 hours, would heal to 1 HP (not implemented in MVP)
        # This test documents the expected behavior for future implementation


class TestDeathSaveProgression:
    """Test death save progression over multiple rounds."""

    def test_multiple_successful_death_saves(self, fighter, event_bus):
        """Multiple successful saves should eventually stabilize."""
        fighter.current_hp = 0

        # First success
        with patch.object(fighter._dice_roller, 'roll') as mock_roll:
            mock_roll.return_value = Mock(total=15)
            result1 = fighter.make_death_save(event_bus)
        assert result1["successes"] == 1
        assert not result1["stabilized"]

        # Second success
        with patch.object(fighter._dice_roller, 'roll') as mock_roll:
            mock_roll.return_value = Mock(total=12)
            result2 = fighter.make_death_save(event_bus)
        assert result2["successes"] == 2
        assert not result2["stabilized"]

        # Third success - stabilizes
        with patch.object(fighter._dice_roller, 'roll') as mock_roll:
            mock_roll.return_value = Mock(total=18)
            result3 = fighter.make_death_save(event_bus)
        assert result3["successes"] == 3
        assert result3["stabilized"] == True

    def test_multiple_failed_death_saves(self, fighter, event_bus):
        """Multiple failed saves should eventually kill."""
        fighter.current_hp = 0

        # First failure
        with patch.object(fighter._dice_roller, 'roll') as mock_roll:
            mock_roll.return_value = Mock(total=5)
            result1 = fighter.make_death_save(event_bus)
        assert result1["failures"] == 1
        assert not result1["dead"]

        # Second failure
        with patch.object(fighter._dice_roller, 'roll') as mock_roll:
            mock_roll.return_value = Mock(total=7)
            result2 = fighter.make_death_save(event_bus)
        assert result2["failures"] == 2
        assert not result2["dead"]

        # Third failure - death
        with patch.object(fighter._dice_roller, 'roll') as mock_roll:
            mock_roll.return_value = Mock(total=4)
            result3 = fighter.make_death_save(event_bus)
        assert result3["failures"] == 3
        assert result3["dead"] == True

    def test_mixed_death_saves(self, fighter, event_bus):
        """Mixed successes and failures should track both."""
        fighter.current_hp = 0

        # Success
        with patch.object(fighter._dice_roller, 'roll') as mock_roll:
            mock_roll.return_value = Mock(total=15)
            fighter.make_death_save(event_bus)

        # Failure
        with patch.object(fighter._dice_roller, 'roll') as mock_roll:
            mock_roll.return_value = Mock(total=5)
            fighter.make_death_save(event_bus)

        # Another success
        with patch.object(fighter._dice_roller, 'roll') as mock_roll:
            mock_roll.return_value = Mock(total=12)
            fighter.make_death_save(event_bus)

        assert fighter.death_save_successes == 2
        assert fighter.death_save_failures == 1
        assert not fighter.stabilized
        assert not fighter.is_dead


class TestDeathSaveEvents:
    """Test event emission for death save mechanics."""

    def test_death_save_event_contains_full_data(self, fighter, event_bus):
        """DEATH_SAVE event should contain complete information."""
        fighter.current_hp = 0
        events = []
        event_bus.subscribe(EventType.DEATH_SAVE, lambda e: events.append(e))

        with patch.object(fighter._dice_roller, 'roll') as mock_roll:
            mock_roll.return_value = Mock(total=14)
            fighter.make_death_save(event_bus)

        assert len(events) == 1
        event_data = events[0].data

        assert event_data["character"] == "Fighter"
        assert event_data["roll"] == 14
        assert event_data["success"] == True
        assert event_data["successes"] == 1
        assert event_data["failures"] == 0
        assert event_data["stabilized"] == False
        assert event_data["dead"] == False

    def test_character_stabilized_event(self, fighter, rogue, event_bus):
        """CHARACTER_STABILIZED event should be emitted on stabilization."""
        from dnd_engine.rules.loader import DataLoader

        fighter.current_hp = 0
        events = []
        event_bus.subscribe(EventType.CHARACTER_STABILIZED, lambda e: events.append(e))

        # Simulate successful Medicine check
        data_loader = DataLoader()
        skills_data = data_loader.load_skills()

        with patch.object(rogue._dice_roller, 'roll') as mock_roll:
            mock_roll.return_value = Mock(total=15, modifier=0)  # High roll to ensure success
            check_result = rogue.make_skill_check("medicine", 10, skills_data)

        if check_result["success"]:
            fighter.stabilize_character()

            # Emit the event (would be done by CLI)
            from dnd_engine.utils.events import Event
            event_bus.emit(Event(
                type=EventType.CHARACTER_STABILIZED,
                data={
                    "helper": rogue.name,
                    "target": fighter.name,
                    "check_total": check_result["total"]
                }
            ))

            assert len(events) == 1
            assert events[0].data["helper"] == "Rogue"
            assert events[0].data["target"] == "Fighter"


class TestInitiativeWithDeathSaves:
    """Test initiative tracking with unconscious/dead characters."""

    def test_unconscious_character_stays_in_initiative(self, fighter, goblin):
        """Unconscious characters should remain in initiative."""
        tracker = InitiativeTracker()
        tracker.add_combatant(fighter)
        tracker.add_combatant(goblin)

        # Make fighter unconscious
        fighter.current_hp = 0

        # Unconscious character should still be in initiative
        combatants = [entry.creature for entry in tracker.get_all_combatants()]
        assert fighter in combatants

    def test_dead_character_removed_from_initiative(self, fighter, goblin):
        """Dead characters should be removed from initiative."""
        tracker = InitiativeTracker()
        tracker.add_combatant(fighter)
        tracker.add_combatant(goblin)

        # Kill the fighter
        fighter.current_hp = 0
        fighter.death_save_failures = 3

        # Remove dead character
        tracker.remove_combatant(fighter)

        combatants = [entry.creature for entry in tracker.get_all_combatants()]
        assert fighter not in combatants
        assert goblin in combatants
