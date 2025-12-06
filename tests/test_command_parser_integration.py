# ABOUTME: Integration tests for fuzzy command parser with CLI.
# ABOUTME: Tests that natural language commands are correctly routed through the CLI.

from unittest.mock import MagicMock

import pytest

from dnd_engine.nlp import CLIContextAdapter, CommandParser


def create_mock_game_state():
    """Create a mock game state for testing."""
    game_state = MagicMock()

    # Mock party
    char1 = MagicMock()
    char1.name = "Gandalf"
    char1.is_alive = True
    char1.spells.cantrips = ["fire_bolt", "light"]
    char1.spells.prepared_spells = ["magic_missile", "shield"]
    char1.spells.known_spells = []
    char1.inventory.get_items_by_category.return_value = []
    char1.inventory.equipment = {}

    char2 = MagicMock()
    char2.name = "Aragorn"
    char2.is_alive = True
    char2.spells.cantrips = []
    char2.spells.prepared_spells = []
    char2.spells.known_spells = []
    char2.inventory.get_items_by_category.return_value = []
    char2.inventory.equipment = {}

    game_state.party.characters = [char1, char2]

    # Mock combat state
    game_state.in_combat = False
    game_state.initiative_tracker = None
    game_state.active_enemies = []

    # Mock room items
    game_state.get_room_items.return_value = [
        {"id": "longsword", "name": "Longsword", "type": "weapon"},
        {"id": "healing_potion", "name": "Healing Potion", "type": "consumable"},
    ]

    # Mock NPCs
    npc1 = MagicMock()
    npc1.name = "Marta the Innkeeper"
    game_state.npc_manager.get_npcs_in_room.return_value = [npc1]
    game_state.current_room = "inn"

    # Mock data loader
    game_state.data_loader.load_spells.return_value = {
        "fire_bolt": {"name": "Fire Bolt"},
        "light": {"name": "Light"},
        "magic_missile": {"name": "Magic Missile"},
        "shield": {"name": "Shield"},
    }
    game_state.data_loader.load_items.return_value = {
        "longsword": {"name": "Longsword"},
        "healing_potion": {"name": "Healing Potion"},
    }
    game_state.campaign_id = "test_campaign"

    return game_state


class TestCLIContextAdapter:
    """Tests for CLIContextAdapter with mocked game state."""

    @pytest.fixture
    def mock_game_state(self):
        """Create a mock game state for testing."""
        return create_mock_game_state()

    def test_get_party_member_names(self, mock_game_state):
        adapter = CLIContextAdapter(mock_game_state)
        names = adapter.get_party_member_names()
        assert "Gandalf" in names
        assert "Aragorn" in names

    def test_get_available_items_from_room(self, mock_game_state):
        adapter = CLIContextAdapter(mock_game_state)
        items = adapter.get_available_items()
        assert "Longsword" in items
        assert "Healing Potion" in items

    def test_get_available_npcs(self, mock_game_state):
        adapter = CLIContextAdapter(mock_game_state)
        npcs = adapter.get_available_npcs()
        assert "Marta the Innkeeper" in npcs

    def test_get_available_spells_exploration_mode(self, mock_game_state):
        adapter = CLIContextAdapter(mock_game_state)
        spells = adapter.get_available_spells()
        # Should get first living character's spells
        assert "Fire Bolt" in spells
        assert "Light" in spells
        assert "Magic Missile" in spells
        assert "Shield" in spells

    def test_is_in_combat_false_by_default(self, mock_game_state):
        adapter = CLIContextAdapter(mock_game_state)
        assert adapter.is_in_combat() is False

    def test_get_available_enemies_empty_outside_combat(self, mock_game_state):
        adapter = CLIContextAdapter(mock_game_state)
        enemies = adapter.get_available_enemies()
        assert enemies == []


def create_combat_game_state():
    """Create a mock game state in combat."""
    game_state = MagicMock()

    # Mock party
    char1 = MagicMock()
    char1.name = "Gandalf"
    char1.is_alive = True
    char1.current_hp = 20
    char1.spells.cantrips = ["fire_bolt"]
    char1.spells.prepared_spells = ["magic_missile"]
    char1.spells.known_spells = []

    game_state.party.characters = [char1]

    # Mock enemies
    enemy1 = MagicMock()
    enemy1.name = "Goblin"
    enemy1.current_hp = 5

    enemy2 = MagicMock()
    enemy2.name = "Skeleton"
    enemy2.current_hp = 10

    # Mock combat state
    game_state.in_combat = True

    # Mock initiative tracker
    entry1 = MagicMock()
    entry1.creature = enemy1
    entry2 = MagicMock()
    entry2.creature = enemy2
    entry3 = MagicMock()
    entry3.creature = char1

    game_state.initiative_tracker.order = [entry1, entry2, entry3]
    game_state.initiative_tracker.get_combatant_display_name.side_effect = lambda c: (
        "Goblin 1" if c == enemy1 else "Skeleton 1"
    )
    game_state.initiative_tracker.get_current_combatant.return_value = entry3

    # Mock other required attributes
    game_state.get_room_items.return_value = []
    game_state.npc_manager = None
    game_state.data_loader.load_spells.return_value = {
        "fire_bolt": {"name": "Fire Bolt"},
        "magic_missile": {"name": "Magic Missile"},
    }
    game_state.campaign_id = "test_campaign"

    return game_state


class TestCLIContextAdapterInCombat:
    """Tests for CLIContextAdapter during combat."""

    @pytest.fixture
    def combat_game_state(self):
        """Create a mock game state in combat."""
        return create_combat_game_state()

    def test_is_in_combat_true(self, combat_game_state):
        adapter = CLIContextAdapter(combat_game_state)
        assert adapter.is_in_combat() is True

    def test_get_available_enemies_returns_enemy_names(self, combat_game_state):
        adapter = CLIContextAdapter(combat_game_state)
        enemies = adapter.get_available_enemies()
        assert "Goblin 1" in enemies
        assert "Skeleton 1" in enemies

    def test_get_available_spells_current_combatant(self, combat_game_state):
        adapter = CLIContextAdapter(combat_game_state)
        spells = adapter.get_available_spells()
        assert "Fire Bolt" in spells
        assert "Magic Missile" in spells


def create_simple_combat_parser():
    """Create parser with combat context."""
    game_state = MagicMock()

    # Mock party
    char1 = MagicMock()
    char1.name = "Gandalf"
    char1.is_alive = True
    char1.current_hp = 20

    game_state.party.characters = [char1]

    # Mock enemies
    enemy1 = MagicMock()
    enemy1.name = "Goblin"
    enemy1.current_hp = 5

    game_state.in_combat = True

    entry1 = MagicMock()
    entry1.creature = enemy1
    entry2 = MagicMock()
    entry2.creature = char1

    game_state.initiative_tracker.order = [entry1, entry2]
    game_state.initiative_tracker.get_combatant_display_name.return_value = "Goblin 1"
    game_state.initiative_tracker.get_current_combatant.return_value = entry2

    game_state.get_room_items.return_value = []
    game_state.npc_manager = None
    game_state.data_loader.load_spells.return_value = {
        "magic_missile": {"name": "Magic Missile"},
    }
    game_state.campaign_id = "test"
    char1.spells.cantrips = []
    char1.spells.prepared_spells = ["magic_missile"]
    char1.spells.known_spells = []

    adapter = CLIContextAdapter(game_state)
    return CommandParser(context_provider=adapter)


class TestCommandParserWithCLIContext:
    """Tests for CommandParser using CLIContextAdapter."""

    @pytest.fixture
    def combat_parser(self):
        """Create parser with combat context."""
        return create_simple_combat_parser()

    def test_attack_with_fuzzy_target(self, combat_parser):
        """Test that fuzzy target matching works with real context."""
        result = combat_parser.parse("hit the goblin")
        assert result.success
        assert result.action == "attack"
        assert result.params.get("target") == "Goblin 1"

    def test_attack_with_typo(self, combat_parser):
        """Test fuzzy matching handles typos."""
        result = combat_parser.parse("attack gobln 1")  # Typo in goblin
        assert result.success
        assert result.action == "attack"
        assert result.params.get("target") == "Goblin 1"

    def test_cast_spell_with_target(self, combat_parser):
        """Test spell casting with target resolution."""
        result = combat_parser.parse("cast magic missile at goblin")
        assert result.success
        assert result.action == "cast"
        assert result.params.get("spell") == "Magic Missile"
        assert result.params.get("target") == "Goblin 1"

    def test_cast_spell_with_typo(self, combat_parser):
        """Test spell fuzzy matching."""
        result = combat_parser.parse("cast magic missle at goblin")  # Typo
        assert result.success
        assert result.params.get("spell") == "Magic Missile"


class TestParserBackwardCompatibility:
    """Tests ensuring backward compatibility with existing commands."""

    @pytest.fixture
    def parser(self):
        """Create parser without context (simulating legacy behavior)."""
        return CommandParser()

    @pytest.mark.parametrize(
        "legacy_command,expected_action",
        [
            # Existing exact commands should still work
            ("go north", "move"),
            ("move south", "move"),
            ("attack goblin", "attack"),
            ("cast fireball", "cast"),
            ("take sword", "take"),
            ("use potion", "use"),
            ("equip armor", "equip"),
            ("search", "search"),
            ("look", "look"),
            ("inventory", "inventory"),
            ("status", "status"),
            ("help", "help"),
            ("rest", "rest"),
            ("flee", "flee"),
            ("save", "save"),
        ],
    )
    def test_legacy_commands_work(self, parser, legacy_command, expected_action):
        """Verify all existing command formats are recognized."""
        result = parser.parse(legacy_command)
        assert result.action == expected_action

    def test_short_direction_aliases(self, parser):
        """Test that direction aliases work."""
        for alias, direction in [("n", "north"), ("s", "south"), ("e", "east"), ("w", "west")]:
            result = parser.parse(f"go {alias}")
            assert result.action == "move"
            assert result.params.get("direction") == direction
