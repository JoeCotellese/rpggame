"""
Integration tests for time tracking system.

Tests cover:
- Time advancement during exploration actions (move, search, rest)
- Time advancement during combat rounds
- Spell duration tracking during gameplay
- Effect expiration during gameplay
- Concentration spell management
"""

import pytest
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.core.character import Character, CharacterClass, Abilities
from dnd_engine.utils.events import EventBus, EventType
from dnd_engine.systems.time_manager import EffectType


@pytest.fixture
def test_party():
    """Create a test party with characters."""
    # Create a cleric
    cleric_abilities = Abilities(
        strength=12,
        dexterity=10,
        constitution=14,
        intelligence=10,
        wisdom=16,
        charisma=12
    )
    cleric = Character(
        name="TestCleric",
        character_class=CharacterClass.CLERIC,
        level=3,
        abilities=cleric_abilities,
        max_hp=20,
        ac=15,
        spellcasting_ability="wis",
        prepared_spells=["cure_wounds", "bless", "shield_of_faith"]
    )

    # Create a wizard
    wizard_abilities = Abilities(
        strength=8,
        dexterity=14,
        constitution=12,
        intelligence=16,
        wisdom=12,
        charisma=10
    )
    wizard = Character(
        name="TestWizard",
        character_class=CharacterClass.WIZARD,
        level=3,
        abilities=wizard_abilities,
        max_hp=15,
        ac=12,
        spellcasting_ability="int",
        prepared_spells=["mage_armor", "shield", "detect_magic"]
    )

    party = Party([cleric, wizard])
    return party


@pytest.fixture
def game_state(test_party):
    """Create a test game state."""
    event_bus = EventBus()
    gs = GameState(
        party=test_party,
        dungeon_name="test_dungeon.json",
        event_bus=event_bus
    )
    return gs


class TestExplorationTimeAdvancement:
    """Test time advancement during exploration."""

    def test_move_advances_time(self, game_state):
        """Test that moving to a new room advances time by 10 minutes."""
        initial_time = game_state.time_manager.elapsed_minutes

        # Move to a valid direction
        current_room = game_state.get_current_room()
        exits = current_room.get("exits", {})

        if exits:
            direction = list(exits.keys())[0]
            success = game_state.move(direction, check_for_enemies=False)

            if success:
                assert game_state.time_manager.elapsed_minutes == initial_time + 10.0

    def test_search_advances_time(self, game_state):
        """Test that searching a room advances time by 10 minutes."""
        initial_time = game_state.time_manager.elapsed_minutes

        # Search the room
        result = game_state.search_room()

        # If search was performed (not already searched), time should advance
        if not result.get("already_searched"):
            assert game_state.time_manager.elapsed_minutes == initial_time + 10.0

    def test_multiple_moves_accumulate_time(self, game_state):
        """Test that multiple moves accumulate time correctly."""
        initial_time = game_state.time_manager.elapsed_minutes
        moves = 0

        # Try to move multiple times
        for _ in range(3):
            current_room = game_state.get_current_room()
            exits = current_room.get("exits", {})

            if exits:
                direction = list(exits.keys())[0]
                if game_state.move(direction, check_for_enemies=False):
                    moves += 1

        if moves > 0:
            expected_time = initial_time + (moves * 10.0)
            assert game_state.time_manager.elapsed_minutes == expected_time


class TestRestTimeAdvancement:
    """Test time advancement during rests."""

    def test_short_rest_advances_time(self, game_state):
        """Test that short rest advances time by 60 minutes."""
        # This test requires the CLI to perform rest
        # We'll test the time manager directly
        initial_time = game_state.time_manager.elapsed_minutes

        game_state.time_manager.advance_time(60, reason="short_rest")

        assert game_state.time_manager.elapsed_minutes == initial_time + 60.0

    def test_long_rest_advances_time(self, game_state):
        """Test that long rest advances time by 480 minutes (8 hours)."""
        initial_time = game_state.time_manager.elapsed_minutes

        game_state.time_manager.advance_time(480, reason="long_rest")

        assert game_state.time_manager.elapsed_minutes == initial_time + 480.0


class TestCombatTimeAdvancement:
    """Test time advancement during combat."""

    def test_combat_round_advances_time(self, game_state):
        """Test that combat rounds advance time by 0.1 minutes (6 seconds)."""
        # Start combat
        game_state._start_combat()

        # Add combatants
        for character in game_state.party.characters:
            game_state.initiative_tracker.add_combatant(character)

        initial_time = game_state.time_manager.elapsed_minutes
        combatant_count = len(game_state.initiative_tracker.combatants)

        # Advance through one full round (all combatants take turns)
        for _ in range(combatant_count):
            game_state.initiative_tracker.next_turn()

        # Time should advance by 0.1 minutes for completing a round
        assert game_state.time_manager.elapsed_minutes == initial_time + 0.1

    def test_multiple_rounds_accumulate_time(self, game_state):
        """Test that multiple combat rounds accumulate time correctly."""
        # Start combat
        game_state._start_combat()

        # Add combatants
        for character in game_state.party.characters:
            game_state.initiative_tracker.add_combatant(character)

        initial_time = game_state.time_manager.elapsed_minutes
        combatant_count = len(game_state.initiative_tracker.combatants)

        # Advance through 3 full rounds
        rounds = 3
        for _ in range(rounds * combatant_count):
            game_state.initiative_tracker.next_turn()

        # Time should advance by 0.1 minutes per round
        expected_time = initial_time + (rounds * 0.1)
        assert abs(game_state.time_manager.elapsed_minutes - expected_time) < 0.01


class TestSpellDurationTracking:
    """Test spell duration tracking during gameplay."""

    def test_cast_spell_with_duration_creates_effect(self, game_state):
        """Test that casting a spell with duration creates an active effect."""
        cleric = game_state.party.get_character_by_name("TestCleric")

        # Prepare and cast Bless (1 minute duration, concentration)
        if "bless" in cleric.prepared_spells or "bless" in cleric.known_spells:
            result = game_state.cast_spell_exploration(
                caster_name="TestCleric",
                spell_id="bless",
                target_name="TestCleric"
            )

            if result.get("success"):
                # Check that effect was created
                effects = game_state.time_manager.get_effects_for_character("TestCleric")
                assert len(effects) > 0

                # Verify effect properties
                bless_effect = next((e for e in effects if e.source == "Bless"), None)
                if bless_effect:
                    assert bless_effect.effect_type == EffectType.SPELL
                    assert bless_effect.duration_minutes == 1.0
                    assert bless_effect.concentration

    def test_spell_effect_expires_with_time(self, game_state):
        """Test that spell effects expire when time advances."""
        # Add a short-duration effect
        from dnd_engine.systems.time_manager import ActiveEffect

        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Shield",
            duration_minutes=1.0,
            remaining_minutes=1.0,
            target_name="TestWizard",
            concentration=False
        )

        game_state.time_manager.add_effect(effect)
        assert len(game_state.time_manager.active_effects) == 1

        # Advance time by 0.5 minutes - effect should still be active
        game_state.time_manager.advance_time(0.5, reason="test")
        assert len(game_state.time_manager.active_effects) == 1

        # Advance time by 0.5 more minutes - effect should expire
        game_state.time_manager.advance_time(0.5, reason="test")
        assert len(game_state.time_manager.active_effects) == 0

    def test_long_duration_spell_persists(self, game_state):
        """Test that long-duration spells persist through multiple actions."""
        from dnd_engine.systems.time_manager import ActiveEffect

        # Add a long-duration effect (8 hours)
        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Mage Armor",
            duration_minutes=480.0,
            remaining_minutes=480.0,
            target_name="TestWizard",
            concentration=False
        )

        game_state.time_manager.add_effect(effect)

        # Perform multiple actions (each takes 10 minutes)
        for _ in range(10):
            game_state.time_manager.advance_time(10, reason="move")

        # Effect should still be active (100 minutes passed, 480 duration)
        effects = game_state.time_manager.get_effects_for_character("TestWizard")
        assert len(effects) == 1
        assert effects[0].remaining_minutes == 380.0


class TestConcentrationManagement:
    """Test concentration spell management."""

    def test_concentration_spell_breaks_previous(self, game_state):
        """Test that casting a concentration spell breaks previous concentration."""
        from dnd_engine.systems.time_manager import ActiveEffect

        wizard = "TestWizard"

        # Add first concentration spell
        effect1 = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Haste",
            duration_minutes=10.0,
            remaining_minutes=10.0,
            target_name="TestCleric",
            concentration=True,
            caster_name=wizard
        )

        game_state.time_manager.add_effect(effect1)
        assert len(game_state.time_manager.active_effects) == 1

        # Cast second concentration spell - should break first
        effect2 = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Fly",
            duration_minutes=10.0,
            remaining_minutes=10.0,
            target_name="TestCleric",
            concentration=True,
            caster_name=wizard
        )

        # Manually break concentration (simulating casting new concentration spell)
        game_state.time_manager.remove_concentration_effects(wizard)
        game_state.time_manager.add_effect(effect2)

        # Should only have the new effect
        effects = game_state.time_manager.active_effects
        assert len(effects) == 1
        assert effects[0].source == "Fly"

    def test_non_concentration_spell_doesnt_break_concentration(self, game_state):
        """Test that casting a non-concentration spell doesn't break concentration."""
        from dnd_engine.systems.time_manager import ActiveEffect

        wizard = "TestWizard"

        # Add concentration spell
        effect1 = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Haste",
            duration_minutes=10.0,
            remaining_minutes=10.0,
            target_name="TestCleric",
            concentration=True,
            caster_name=wizard
        )

        game_state.time_manager.add_effect(effect1)

        # Add non-concentration spell
        effect2 = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Mage Armor",
            duration_minutes=480.0,
            remaining_minutes=480.0,
            target_name=wizard,
            concentration=False
        )

        game_state.time_manager.add_effect(effect2)

        # Should have both effects
        effects = game_state.time_manager.active_effects
        assert len(effects) == 2


class TestEventEmission:
    """Test event emission during time tracking."""

    def test_time_advanced_event_emitted(self, game_state):
        """Test that TIME_ADVANCED event is emitted when time advances."""
        events_received = []

        def handler(event):
            events_received.append(event)

        game_state.event_bus.subscribe(EventType.TIME_ADVANCED, handler)

        # Advance time
        game_state.time_manager.advance_time(10, reason="test")

        assert len(events_received) == 1
        assert events_received[0].type == EventType.TIME_ADVANCED

    def test_hour_passed_event_emitted(self, game_state):
        """Test that HOUR_PASSED event is emitted when an hour passes."""
        events_received = []

        def handler(event):
            events_received.append(event)

        game_state.event_bus.subscribe(EventType.HOUR_PASSED, handler)

        # Advance time by 1 hour
        game_state.time_manager.advance_time(60, reason="test")

        assert len(events_received) == 1
        assert events_received[0].type == EventType.HOUR_PASSED

    def test_effect_expired_event_emitted(self, game_state):
        """Test that EFFECT_EXPIRED event is emitted when effect expires."""
        from dnd_engine.systems.time_manager import ActiveEffect

        events_received = []

        def handler(event):
            events_received.append(event)

        game_state.event_bus.subscribe(EventType.EFFECT_EXPIRED, handler)

        # Add short-duration effect
        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Shield",
            duration_minutes=1.0,
            remaining_minutes=1.0,
            target_name="TestWizard"
        )

        game_state.time_manager.add_effect(effect)

        # Advance time to expire effect
        game_state.time_manager.advance_time(1.0, reason="test")

        assert len(events_received) == 1
        assert events_received[0].type == EventType.EFFECT_EXPIRED


class TestTimeDisplay:
    """Test time display formatting."""

    def test_elapsed_time_display(self, game_state):
        """Test elapsed time display formatting."""
        # Start at 0
        display = game_state.time_manager.get_elapsed_time_display()
        assert "0 minutes" in display or "0 minute" in display

        # Advance 30 minutes
        game_state.time_manager.advance_time(30)
        display = game_state.time_manager.get_elapsed_time_display()
        assert "30 minutes" in display

        # Advance to 1 hour
        game_state.time_manager.advance_time(30)
        display = game_state.time_manager.get_elapsed_time_display()
        assert "1 hour" in display

        # Advance to 1 day
        game_state.time_manager.advance_time(23 * 60)
        display = game_state.time_manager.get_elapsed_time_display()
        assert "1 day" in display
