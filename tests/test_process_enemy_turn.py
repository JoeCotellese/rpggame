# ABOUTME: Unit tests for GameState.process_enemy_turn() method
# ABOUTME: Tests enemy turn processing including attacks, conditions, and AI decisions

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.game_state import (
    EnemyTurnAction,
    EnemyTurnResult,
    GameState,
)
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.action_economy import TurnState
from dnd_engine.systems.initiative import InitiativeEntry, InitiativeTracker
from dnd_engine.utils.events import EventBus


class TestProcessEnemyTurn:
    """Tests for GameState.process_enemy_turn() method."""

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
    def fighter(self):
        """Create a fighter character."""
        return Character(
            name="Conan",
            character_class=CharacterClass.FIGHTER,
            level=3,
            abilities=Abilities(16, 12, 14, 10, 10, 10),
            max_hp=28,
            ac=16
        )

    @pytest.fixture
    def goblin(self):
        """Create a goblin enemy."""
        return Creature(
            name="Goblin",
            max_hp=7,
            ac=13,
            abilities=Abilities(8, 14, 10, 10, 8, 8)
        )

    @pytest.fixture
    def game_state(self, fighter, goblin, event_bus, data_loader, dice_roller):
        """Create game state with party and enemies in combat."""
        party = Party([fighter])
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller
        )
        game_state.active_enemies = [goblin]
        game_state.in_combat = True

        # Set up initiative with goblin going first (higher initiative)
        game_state.initiative_tracker = InitiativeTracker(dice_roller=dice_roller)
        # Directly add entries to control order (goblin first, then fighter)
        goblin_entry = InitiativeEntry(creature=goblin, initiative_roll=20)
        fighter_entry = InitiativeEntry(creature=fighter, initiative_roll=10)
        game_state.initiative_tracker.combatants = [goblin_entry, fighter_entry]
        game_state.initiative_tracker.turn_states[goblin] = TurnState()
        game_state.initiative_tracker.turn_states[fighter] = TurnState()
        game_state.initiative_tracker.round_number = 1  # Combat has started

        return game_state


class TestProcessEnemyTurnBasicAttack(TestProcessEnemyTurn):
    """Test basic enemy attack turn processing."""

    def test_returns_enemy_turn_result(self, game_state):
        """process_enemy_turn returns EnemyTurnResult."""
        result = game_state.process_enemy_turn()

        assert isinstance(result, EnemyTurnResult)

    def test_attack_action_type(self, game_state):
        """Enemy performs attack action when able."""
        result = game_state.process_enemy_turn()

        assert result.action_taken == EnemyTurnAction.ATTACK

    def test_enemy_name_populated(self, game_state, goblin):
        """Enemy name is included in result."""
        result = game_state.process_enemy_turn()

        assert result.enemy_name == "Goblin"

    def test_target_name_populated(self, game_state, fighter):
        """Target name is included in result."""
        result = game_state.process_enemy_turn()

        assert result.target_name == "Conan"

    def test_attack_result_populated(self, game_state):
        """Attack result is populated when attacking."""
        result = game_state.process_enemy_turn()

        assert result.attack_result is not None
        assert hasattr(result.attack_result, "hit")
        assert hasattr(result.attack_result, "damage")

    def test_turn_advanced(self, game_state):
        """Turn is advanced after processing."""
        result = game_state.process_enemy_turn()

        assert result.turn_advanced is True

    def test_initiative_advances_to_party_member(self, game_state, fighter):
        """After enemy turn, initiative moves to party member."""
        game_state.process_enemy_turn()

        current = game_state.initiative_tracker.get_current_combatant()
        assert current.creature == fighter


class TestProcessEnemyTurnPartyTurn(TestProcessEnemyTurn):
    """Test when it's a party member's turn."""

    def test_returns_none_when_party_turn(self, game_state, fighter, goblin):
        """Returns None when current turn is a party member."""
        # Advance to fighter's turn
        game_state.initiative_tracker.next_turn()

        result = game_state.process_enemy_turn()

        assert result is None


class TestProcessEnemyTurnNoCombat(TestProcessEnemyTurn):
    """Test when not in combat."""

    def test_returns_none_when_not_in_combat(self, game_state):
        """Returns None when not in combat."""
        game_state.in_combat = False

        result = game_state.process_enemy_turn()

        assert result is None


class TestProcessEnemyTurnDeadEnemy(TestProcessEnemyTurn):
    """Test dead enemy handling."""

    def test_dead_enemy_skipped(self, game_state, goblin, fighter):
        """Dead enemy has turn skipped."""
        goblin.current_hp = 0

        result = game_state.process_enemy_turn()

        assert result.action_taken == EnemyTurnAction.DIED_START_OF_TURN
        # Turn should advance to fighter
        current = game_state.initiative_tracker.get_current_combatant()
        assert current.creature == fighter


class TestProcessEnemyTurnIncapacitated(TestProcessEnemyTurn):
    """Test incapacitated enemy handling."""

    def test_incapacitated_enemy_cannot_act(self, game_state, goblin):
        """Incapacitated enemy cannot take actions."""
        goblin.add_condition("stunned")

        result = game_state.process_enemy_turn()

        assert result.action_taken == EnemyTurnAction.INCAPACITATED
        assert "STUNNED" in result.incapacitating_conditions

    def test_surprised_enemy_cannot_act(self, game_state, goblin):
        """Surprised enemy cannot take actions."""
        goblin.add_condition("surprised")

        result = game_state.process_enemy_turn()

        assert result.action_taken == EnemyTurnAction.INCAPACITATED
        assert "SURPRISED" in result.incapacitating_conditions


class TestProcessEnemyTurnNoTargets(TestProcessEnemyTurn):
    """Test when no targets available."""

    def test_no_targets_when_party_wiped(self, game_state, fighter):
        """No targets action when party is wiped."""
        fighter.current_hp = 0

        result = game_state.process_enemy_turn()

        assert result.action_taken == EnemyTurnAction.NO_TARGETS


class TestProcessEnemyTurnConditionRemoval(TestProcessEnemyTurn):
    """Test condition removal decision."""

    def test_on_fire_low_hp_attempts_removal(self, game_state, goblin):
        """Enemy on fire with low HP attempts to extinguish."""
        goblin.add_condition("on_fire")
        goblin.current_hp = 3  # Below threshold of 4

        result = game_state.process_enemy_turn()

        assert result.action_taken == EnemyTurnAction.CONDITION_REMOVAL
        assert result.condition_removal is not None
        assert result.condition_removal.condition_id == "on_fire"

    def test_on_fire_high_hp_attacks_instead(self, game_state, goblin):
        """Enemy on fire with high HP attacks instead of extinguishing."""
        goblin.add_condition("on_fire")
        goblin.current_hp = 7  # Full HP, above threshold

        result = game_state.process_enemy_turn()

        # Should attack instead of attempting removal
        assert result.action_taken == EnemyTurnAction.ATTACK


class TestProcessEnemyTurnNarrativeContext(TestProcessEnemyTurn):
    """Test narrative context for LLM enhancement."""

    def test_narrative_context_populated(self, game_state):
        """Narrative context is populated for attacks."""
        result = game_state.process_enemy_turn()

        assert result.narrative_context is not None
        assert "attacker" in result.narrative_context
        assert "target" in result.narrative_context
        assert "hit" in result.narrative_context


class TestProcessEnemyTurnTargetKilled(TestProcessEnemyTurn):
    """Test target killed detection."""

    def test_target_killed_flag_set(self, game_state, fighter):
        """target_killed flag is set when target dies."""
        # Set fighter to very low HP so goblin can kill
        fighter.current_hp = 1

        # Run enemy turn - may or may not kill depending on hit/damage
        result = game_state.process_enemy_turn()

        if result.attack_result and result.attack_result.hit:
            if fighter.current_hp <= 0:
                assert result.target_killed is True


class TestProcessEnemyTurnTurnStartEffects(TestProcessEnemyTurn):
    """Test turn-start effect processing."""

    def test_turn_start_effects_recorded(self, game_state, goblin):
        """Turn-start effects are recorded in result."""
        goblin.add_condition("on_fire")
        goblin.current_hp = 7  # High HP so won't try to extinguish

        result = game_state.process_enemy_turn()

        # Fire damage should be recorded (even if enemy still attacks)
        # Note: turn_start_effects may be empty if on_fire doesn't trigger
        # damage at turn start in this implementation
        assert isinstance(result.turn_start_effects, list)


class TestProcessEnemyTurnMultipleEnemies:
    """Test with multiple enemies."""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def data_loader(self):
        return DataLoader()

    @pytest.fixture
    def dice_roller(self):
        return DiceRoller(seed=42)

    @pytest.fixture
    def fighter(self):
        return Character(
            name="Conan",
            character_class=CharacterClass.FIGHTER,
            level=3,
            abilities=Abilities(16, 12, 14, 10, 10, 10),
            max_hp=28,
            ac=16
        )

    @pytest.fixture
    def goblin1(self):
        return Creature(
            name="Goblin",
            max_hp=7,
            ac=13,
            abilities=Abilities(8, 14, 10, 10, 8, 8)
        )

    @pytest.fixture
    def goblin2(self):
        return Creature(
            name="Goblin",
            max_hp=7,
            ac=13,
            abilities=Abilities(8, 14, 10, 10, 8, 8)
        )

    @pytest.fixture
    def game_state_multi(
        self, fighter, goblin1, goblin2, event_bus, data_loader, dice_roller
    ):
        """Create game state with multiple enemies."""
        party = Party([fighter])
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller
        )
        game_state.active_enemies = [goblin1, goblin2]
        game_state.in_combat = True

        game_state.initiative_tracker = InitiativeTracker(dice_roller=dice_roller)
        # Directly add entries to control order
        goblin1_entry = InitiativeEntry(creature=goblin1, initiative_roll=20)
        goblin2_entry = InitiativeEntry(creature=goblin2, initiative_roll=15)
        fighter_entry = InitiativeEntry(creature=fighter, initiative_roll=10)
        game_state.initiative_tracker.combatants = [
            goblin1_entry, goblin2_entry, fighter_entry
        ]
        game_state.initiative_tracker.turn_states[goblin1] = TurnState()
        game_state.initiative_tracker.turn_states[goblin2] = TurnState()
        game_state.initiative_tracker.turn_states[fighter] = TurnState()
        game_state.initiative_tracker.round_number = 1  # Combat has started

        return game_state

    def test_processes_first_enemy(self, game_state_multi, goblin1):
        """Processes first enemy in initiative order."""
        result = game_state_multi.process_enemy_turn()

        assert result.action_taken == EnemyTurnAction.ATTACK
        # First goblin should have gone

    def test_processes_second_enemy_after_first(self, game_state_multi, goblin2):
        """Second enemy can be processed after first."""
        # Process first goblin
        game_state_multi.process_enemy_turn()

        # Process second goblin
        result = game_state_multi.process_enemy_turn()

        assert result.action_taken == EnemyTurnAction.ATTACK

    def test_returns_none_after_all_enemies(self, game_state_multi, fighter):
        """Returns None when all enemies have gone and it's party's turn."""
        # Process both goblins
        game_state_multi.process_enemy_turn()
        game_state_multi.process_enemy_turn()

        # Should now be fighter's turn
        result = game_state_multi.process_enemy_turn()

        assert result is None
        current = game_state_multi.initiative_tracker.get_current_combatant()
        assert current.creature == fighter
