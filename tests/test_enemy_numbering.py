# ABOUTME: Tests for enemy numbering system in combat
# ABOUTME: Verifies enemies are numbered sequentially and can be targeted by number

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.core.party import Party
from dnd_engine.core.game_state import GameState
from dnd_engine.ui.cli import CLI
from dnd_engine.utils.events import EventBus
from dnd_engine.rules.loader import DataLoader


@pytest.fixture
def test_character():
    """Create a test character."""
    abilities = Abilities(
        strength=16,
        dexterity=14,
        constitution=13,
        intelligence=10,
        wisdom=12,
        charisma=8
    )
    character = Character(
        name="TestWarrior",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=12,
        ac=16
    )
    return character


@pytest.fixture
def test_party(test_character):
    """Create a test party."""
    return Party([test_character])


@pytest.fixture
def game_state_with_enemies(test_party):
    """Create a game state with enemies for testing."""
    event_bus = EventBus()
    data_loader = DataLoader()

    # Create game state
    game_state = GameState(
        party=test_party,
        dungeon_name="goblin_warren",
        event_bus=event_bus,
        data_loader=data_loader
    )

    # Manually create enemies for testing
    goblin1 = Creature(
        name="Goblin",
        ac=13,
        max_hp=7,
        abilities=Abilities(
            strength=8, dexterity=14, constitution=10,
            intelligence=10, wisdom=8, charisma=8
        )
    )
    goblin2 = Creature(
        name="Goblin",
        ac=13,
        max_hp=7,
        abilities=Abilities(
            strength=8, dexterity=14, constitution=10,
            intelligence=10, wisdom=8, charisma=8
        )
    )
    wolf = Creature(
        name="Wolf",
        ac=13,
        max_hp=11,
        abilities=Abilities(
            strength=12, dexterity=15, constitution=12,
            intelligence=3, wisdom=12, charisma=6
        )
    )
    goblin_boss = Creature(
        name="Goblin Boss",
        ac=17,
        max_hp=21,
        abilities=Abilities(
            strength=10, dexterity=14, constitution=10,
            intelligence=10, wisdom=8, charisma=10
        )
    )

    game_state.active_enemies = [goblin1, goblin2, wolf, goblin_boss]

    # Start combat to initialize initiative tracker
    game_state._start_combat()

    return game_state


@pytest.fixture
def cli_with_enemies(game_state_with_enemies):
    """Create a CLI instance with enemies in combat."""
    return CLI(game_state_with_enemies, auto_save_enabled=False)


class TestEnemyNumbering:
    """Test enemy numbering system."""

    def test_assign_enemy_numbers(self, cli_with_enemies):
        """Test that enemies are assigned sequential numbers."""
        cli = cli_with_enemies

        # Assign numbers
        cli._assign_enemy_numbers()

        # Check that all enemies have numbers
        assert len(cli.enemy_numbers) == 4

        # Check that numbers are sequential starting from 1
        numbers = sorted(cli.enemy_numbers.values())
        assert numbers == [1, 2, 3, 4]

    def test_get_enemy_number(self, cli_with_enemies):
        """Test retrieving enemy numbers."""
        cli = cli_with_enemies
        cli._assign_enemy_numbers()

        goblin1 = cli.game_state.active_enemies[0]
        goblin2 = cli.game_state.active_enemies[1]
        wolf = cli.game_state.active_enemies[2]
        goblin_boss = cli.game_state.active_enemies[3]

        assert cli._get_enemy_number(goblin1) == 1
        assert cli._get_enemy_number(goblin2) == 2
        assert cli._get_enemy_number(wolf) == 3
        assert cli._get_enemy_number(goblin_boss) == 4

    def test_find_enemy_by_pure_number(self, cli_with_enemies):
        """Test finding enemy by pure number (e.g., '1', '2', '3')."""
        cli = cli_with_enemies
        cli._assign_enemy_numbers()

        # Test finding by number
        enemy1 = cli._find_enemy_by_target("1")
        enemy2 = cli._find_enemy_by_target("2")
        enemy3 = cli._find_enemy_by_target("3")
        enemy4 = cli._find_enemy_by_target("4")

        assert enemy1 == cli.game_state.active_enemies[0]
        assert enemy2 == cli.game_state.active_enemies[1]
        assert enemy3 == cli.game_state.active_enemies[2]
        assert enemy4 == cli.game_state.active_enemies[3]

    def test_find_enemy_by_name_and_number(self, cli_with_enemies):
        """Test finding enemy by name and number (e.g., 'goblin 1', 'wolf 3')."""
        cli = cli_with_enemies
        cli._assign_enemy_numbers()

        # Test finding by name and number
        goblin1 = cli._find_enemy_by_target("goblin 1")
        goblin2 = cli._find_enemy_by_target("goblin 2")
        wolf = cli._find_enemy_by_target("wolf 3")
        goblin_boss = cli._find_enemy_by_target("goblin boss 4")

        assert goblin1 == cli.game_state.active_enemies[0]
        assert goblin2 == cli.game_state.active_enemies[1]
        assert wolf == cli.game_state.active_enemies[2]
        assert goblin_boss == cli.game_state.active_enemies[3]

    def test_find_enemy_by_name_only_unambiguous(self, cli_with_enemies):
        """Test finding enemy by name when there's only one match."""
        cli = cli_with_enemies
        cli._assign_enemy_numbers()

        # Wolf is unambiguous (only one wolf)
        wolf = cli._find_enemy_by_target("wolf")
        assert wolf == cli.game_state.active_enemies[2]

        # Goblin Boss is unambiguous
        goblin_boss = cli._find_enemy_by_target("goblin boss")
        assert goblin_boss == cli.game_state.active_enemies[3]

    def test_find_enemy_by_name_only_ambiguous(self, cli_with_enemies):
        """Test finding enemy by name when there are multiple matches."""
        cli = cli_with_enemies
        cli._assign_enemy_numbers()

        # "Goblin" is ambiguous (two goblins)
        result = cli._find_enemy_by_target("goblin")
        assert result is None  # Should return None for ambiguous matches

    def test_find_enemy_invalid_number(self, cli_with_enemies):
        """Test finding enemy with invalid number."""
        cli = cli_with_enemies
        cli._assign_enemy_numbers()

        # Test invalid numbers
        assert cli._find_enemy_by_target("0") is None
        assert cli._find_enemy_by_target("5") is None
        assert cli._find_enemy_by_target("999") is None

    def test_find_enemy_wrong_name_with_number(self, cli_with_enemies):
        """Test finding enemy with wrong name but valid number."""
        cli = cli_with_enemies
        cli._assign_enemy_numbers()

        # "dragon 1" doesn't exist (no dragon)
        assert cli._find_enemy_by_target("dragon 1") is None

        # "goblin 3" doesn't exist (3 is wolf, not goblin)
        assert cli._find_enemy_by_target("goblin 3") is None

    def test_find_enemy_case_insensitive(self, cli_with_enemies):
        """Test that enemy targeting is case-insensitive."""
        cli = cli_with_enemies
        cli._assign_enemy_numbers()

        # Test various case combinations
        assert cli._find_enemy_by_target("GOBLIN 1") == cli.game_state.active_enemies[0]
        assert cli._find_enemy_by_target("Goblin 1") == cli.game_state.active_enemies[0]
        assert cli._find_enemy_by_target("goblin 1") == cli.game_state.active_enemies[0]
        assert cli._find_enemy_by_target("WOLF") == cli.game_state.active_enemies[2]
        assert cli._find_enemy_by_target("Wolf") == cli.game_state.active_enemies[2]

    def test_find_enemy_ignores_dead_enemies(self, cli_with_enemies):
        """Test that dead enemies cannot be targeted."""
        cli = cli_with_enemies
        cli._assign_enemy_numbers()

        # Kill the first goblin
        goblin1 = cli.game_state.active_enemies[0]
        goblin1.take_damage(100)
        assert not goblin1.is_alive

        # Should not be able to target dead enemy by number
        assert cli._find_enemy_by_target("1") is None

        # Should not be able to target dead enemy by name+number
        assert cli._find_enemy_by_target("goblin 1") is None

        # But can still target the living goblin
        assert cli._find_enemy_by_target("goblin 2") == cli.game_state.active_enemies[1]

    def test_enemy_numbers_cleared_on_combat_end(self, cli_with_enemies):
        """Test that enemy numbers are cleared when combat ends."""
        cli = cli_with_enemies
        cli._assign_enemy_numbers()

        # Check numbers are assigned
        assert len(cli.enemy_numbers) == 4

        # Simulate combat end event
        from dnd_engine.utils.events import Event, EventType
        event = Event(
            type=EventType.COMBAT_END,
            data={"xp_gained": 100, "xp_per_character": 100}
        )
        cli._on_combat_end(event)

        # Numbers should be cleared
        assert len(cli.enemy_numbers) == 0

    def test_enemy_numbers_cleared_on_flee(self, cli_with_enemies):
        """Test that enemy numbers are cleared when fleeing combat."""
        cli = cli_with_enemies
        cli._assign_enemy_numbers()

        # Check numbers are assigned
        assert len(cli.enemy_numbers) == 4

        # Simulate combat fled event
        from dnd_engine.utils.events import Event, EventType
        event = Event(
            type=EventType.COMBAT_FLED,
            data={
                "success": True,
                "opportunity_attacks": 0,
                "casualties": [],
                "surviving_party": []
            }
        )
        cli._on_combat_fled(event)

        # Numbers should be cleared
        assert len(cli.enemy_numbers) == 0

    def test_enemy_numbers_assigned_on_combat_start(self, cli_with_enemies):
        """Test that enemy numbers are automatically assigned when combat starts."""
        cli = cli_with_enemies

        # Numbers should not be assigned yet
        assert len(cli.enemy_numbers) == 0

        # Simulate combat start event (which should happen automatically)
        from dnd_engine.utils.events import Event, EventType
        event = Event(
            type=EventType.COMBAT_START,
            data={
                "enemies": ["Goblin", "Goblin", "Wolf", "Goblin Boss"],
                "party": ["TestWarrior"]
            }
        )
        cli._on_combat_start(event)

        # Numbers should now be assigned
        assert len(cli.enemy_numbers) == 4
        assert sorted(cli.enemy_numbers.values()) == [1, 2, 3, 4]
