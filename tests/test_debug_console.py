# ABOUTME: Unit tests for debug console functionality
# ABOUTME: Tests command parsing, execution, and state manipulation

import pytest
import os
from dnd_engine.ui.debug_console import DebugConsole
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller


class TestDebugConsoleInit:
    """Test DebugConsole initialization"""

    def test_init_with_enabled_flag(self):
        """Test initialization with enabled=True"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        assert console.enabled is True
        assert console.game_state == game_state

    def test_init_with_disabled_flag(self):
        """Test initialization with enabled=False"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=False)

        assert console.enabled is False

    def test_init_with_env_var_true(self, monkeypatch):
        """Test initialization with DEBUG_MODE=true env var"""
        monkeypatch.setenv("DEBUG_MODE", "true")
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state)

        assert console.enabled is True

    def test_init_with_env_var_false(self, monkeypatch):
        """Test initialization with DEBUG_MODE=false env var"""
        monkeypatch.setenv("DEBUG_MODE", "false")
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state)

        assert console.enabled is False

    def test_command_registry_has_critical_commands(self):
        """Test that command registry includes all critical commands"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Character manipulation
        assert "revive" in console.commands
        assert "kill" in console.commands
        assert "sethp" in console.commands
        assert "damage" in console.commands
        assert "heal" in console.commands
        assert "godmode" in console.commands
        assert "setlevel" in console.commands
        assert "addxp" in console.commands
        assert "setstat" in console.commands

        # Combat testing
        assert "spawn" in console.commands
        assert "despawn" in console.commands
        assert "nextturn" in console.commands
        assert "endcombat" in console.commands

        # Inventory
        assert "give" in console.commands
        assert "remove" in console.commands
        assert "gold" in console.commands
        assert "clearinventory" in console.commands

        # System
        assert "help" in console.commands
        assert "reset" in console.commands


class TestCommandParsing:
    """Test command parsing functionality"""

    def test_is_debug_command_with_slash(self):
        """Test that commands starting with / are identified as debug commands"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        assert console.is_debug_command("/revive") is True
        assert console.is_debug_command("/help") is True
        assert console.is_debug_command("/sethp Gandalf 50") is True

    def test_is_debug_command_without_slash(self):
        """Test that commands without / are not debug commands"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        assert console.is_debug_command("revive") is False
        assert console.is_debug_command("help") is False
        assert console.is_debug_command("attack goblin") is False

    def test_parse_command_simple(self):
        """Test parsing simple command"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        cmd_name, args = console.parse_command("/help")

        assert cmd_name == "help"
        assert args == []

    def test_parse_command_with_args(self):
        """Test parsing command with arguments"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        cmd_name, args = console.parse_command("/revive Gandalf")

        assert cmd_name == "revive"
        assert args == ["Gandalf"]

    def test_parse_command_with_multiple_args(self):
        """Test parsing command with multiple arguments"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        cmd_name, args = console.parse_command("/sethp Gandalf 50")

        assert cmd_name == "sethp"
        assert args == ["Gandalf", "50"]

    def test_parse_command_with_multi_word_name(self):
        """Test parsing command with multi-word character name"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        cmd_name, args = console.parse_command("/revive Gandalf the Grey")

        assert cmd_name == "revive"
        assert args == ["Gandalf", "the", "Grey"]


class TestCharacterManipulation:
    """Test character manipulation commands"""

    def test_revive_character(self):
        """Test /revive command restores character to full HP"""
        # Create a character and set it to near death using proper methods
        character = Character(
            name="Gandalf",
            character_class=CharacterClass.WIZARD,
            race="high_elf",
            level=1,
            max_hp=10,
            ac=10,
            abilities=Abilities(10, 10, 10, 16, 14, 12)
        )
        # Reduce HP to 0 and add death save failures
        character.take_damage(character.current_hp)
        character.death_save_failures = 2

        party = Party([character])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Execute revive command
        console.cmd_revive(["Gandalf"])

        # Verify character is revived
        assert character.current_hp == character.max_hp
        assert character.is_unconscious is False
        assert character.death_save_failures == 0
        assert character.death_save_successes == 0

    def test_kill_character(self):
        """Test /kill command sets character to dead"""
        character = Character(
            name="Gandalf",
            character_class=CharacterClass.WIZARD,
            race="high_elf",
            level=1,
            max_hp=10,
            ac=10,
            abilities=Abilities(10, 10, 10, 16, 14, 12)
        )

        party = Party([character])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Execute kill command
        console.cmd_kill(["Gandalf"])

        # Verify character is dead
        assert character.current_hp == 0
        assert character.death_save_failures == 3

    def test_set_hp_valid_value(self):
        """Test /sethp command with valid HP value"""
        character = Character(
            name="Gandalf",
            character_class=CharacterClass.WIZARD,
            race="high_elf",
            level=1,
            max_hp=10,
            ac=10,
            abilities=Abilities(10, 10, 10, 16, 14, 12)
        )

        party = Party([character])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Execute sethp command with valid value within max
        console.cmd_set_hp(["Gandalf", "7"])

        # Verify HP is set
        assert character.current_hp == 7

    def test_set_hp_clamps_to_max(self):
        """Test /sethp command clamps value to max HP"""
        character = Character(
            name="Gandalf",
            character_class=CharacterClass.WIZARD,
            race="high_elf",
            level=1,
            max_hp=10,
            ac=10,
            abilities=Abilities(10, 10, 10, 16, 14, 12)
        )
        max_hp = character.max_hp

        party = Party([character])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Execute sethp command with value > max
        console.cmd_set_hp(["Gandalf", "999"])

        # Verify HP is clamped to max
        assert character.current_hp == max_hp

    def test_set_hp_clamps_to_zero(self):
        """Test /sethp command clamps value to 0"""
        character = Character(
            name="Gandalf",
            character_class=CharacterClass.WIZARD,
            race="high_elf",
            level=1,
            max_hp=10,
            ac=10,
            abilities=Abilities(10, 10, 10, 16, 14, 12)
        )

        party = Party([character])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Execute sethp command with negative value
        console.cmd_set_hp(["Gandalf", "-50"])

        # Verify HP is clamped to 0
        assert character.current_hp == 0

    def test_damage_character(self):
        """Test /damage command reduces HP"""
        character = Character(
            name="Gandalf",
            character_class=CharacterClass.WIZARD,
            race="high_elf",
            level=1,
            max_hp=10,
            ac=10,
            abilities=Abilities(10, 10, 10, 16, 14, 12)
        )
        initial_hp = character.current_hp

        party = Party([character])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Execute damage command
        console.cmd_damage(["Gandalf", "10"])

        # Verify damage was dealt
        assert character.current_hp == initial_hp - 10

    def test_heal_character(self):
        """Test /heal command restores HP"""
        character = Character(
            name="Gandalf",
            character_class=CharacterClass.WIZARD,
            race="high_elf",
            level=1,
            max_hp=10,
            ac=10,
            abilities=Abilities(10, 10, 10, 16, 14, 12)
        )
        character.current_hp = character.max_hp // 2

        party = Party([character])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Execute heal command
        console.cmd_heal(["Gandalf", "10"])

        # Verify HP was restored (but not exceeding max)
        assert character.current_hp <= character.max_hp

    def test_godmode_toggle(self):
        """Test /godmode command toggles invulnerability"""
        character = Character(
            name="Gandalf",
            character_class=CharacterClass.WIZARD,
            race="high_elf",
            level=1,
            max_hp=10,
            ac=10,
            abilities=Abilities(10, 10, 10, 16, 14, 12)
        )

        party = Party([character])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Enable god mode
        console.cmd_godmode(["Gandalf"])
        assert console.is_god_mode(character) is True

        # Disable god mode
        console.cmd_godmode(["Gandalf"])
        assert console.is_god_mode(character) is False

    def test_set_level(self):
        """Test /setlevel command changes character level"""
        character = Character(
            name="Gandalf",
            character_class=CharacterClass.WIZARD,
            race="high_elf",
            level=1,
            max_hp=10,
            ac=10,
            abilities=Abilities(10, 10, 10, 16, 14, 12)
        )

        party = Party([character])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Set to level 5
        console.cmd_set_level(["Gandalf", "5"])

        # Verify level changed
        assert character.level == 5

    def test_add_xp(self):
        """Test /addxp command grants XP"""
        character = Character(
            name="Gandalf",
            character_class=CharacterClass.WIZARD,
            race="high_elf",
            level=1,
            max_hp=10,
            ac=10,
            abilities=Abilities(10, 10, 10, 16, 14, 12)
        )
        initial_xp = character.xp

        party = Party([character])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Grant XP
        console.cmd_add_xp(["Gandalf", "500"])

        # Verify XP was granted
        assert character.xp == initial_xp + 500

    def test_set_stat(self):
        """Test /setstat command changes ability score"""
        character = Character(
            name="Gandalf",
            character_class=CharacterClass.WIZARD,
            race="high_elf",
            level=1,
            max_hp=10,
            ac=10,
            abilities=Abilities(10, 10, 10, 16, 14, 12)
        )

        party = Party([character])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Set INT to 20
        console.cmd_set_stat(["Gandalf", "INT", "20"])

        # Verify stat changed
        assert character.abilities.intelligence == 20


class TestCombatManipulation:
    """Test combat manipulation commands"""

    def test_next_turn_not_in_combat(self, capsys):
        """Test /nextturn command when not in combat shows error"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Execute nextturn command when not in combat
        console.cmd_next_turn([])

        # Should show error message (captured output will contain error)
        # This is a basic test - in real scenario we'd check error handling

    def test_end_combat_not_in_combat(self, capsys):
        """Test /endcombat command when not in combat shows error"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Execute endcombat command when not in combat
        console.cmd_end_combat([])

        # Should show error message


class TestInventoryManipulation:
    """Test inventory manipulation commands"""

    def test_gold_add(self):
        """Test /gold command adds gold to party"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        initial_gold = game_state.party.currency.gold

        # Add gold
        console.cmd_gold(["500"])

        new_gold = game_state.party.currency.gold
        assert new_gold == initial_gold + 500

    def test_gold_remove(self):
        """Test /gold command with negative value removes gold"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        # Add some gold first
        game_state.party.currency.gold = 1000
        console = DebugConsole(game_state, enabled=True)

        initial_gold = game_state.party.currency.gold

        # Remove gold
        console.cmd_gold(["-200"])

        new_gold = game_state.party.currency.gold
        assert new_gold == initial_gold - 200


class TestHelperMethods:
    """Test helper methods"""

    def test_find_character_case_insensitive(self):
        """Test finding character by name is case-insensitive"""
        character = Character(
            name="Gandalf",
            character_class=CharacterClass.WIZARD,
            race="high_elf",
            level=1,
            max_hp=10,
            ac=10,
            abilities=Abilities(10, 10, 10, 16, 14, 12)
        )

        party = Party([character])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Find with different cases
        assert console._find_character("gandalf", silent=True) == character
        assert console._find_character("GANDALF", silent=True) == character
        assert console._find_character("Gandalf", silent=True) == character

    def test_find_character_not_found(self):
        """Test finding character that doesn't exist returns None"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        result = console._find_character("NonExistent", silent=True)
        assert result is None


class TestExecuteCommand:
    """Test command execution"""

    def test_execute_when_disabled(self, capsys):
        """Test that commands fail when debug mode is disabled"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=False)

        result = console.execute("/help")

        # Should return False and show error
        assert result is False

    def test_execute_valid_command(self):
        """Test executing a valid command"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        result = console.execute("/help")

        # Should return True for successful execution
        assert result is True

    def test_execute_invalid_command(self, capsys):
        """Test executing an invalid command"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        result = console.execute("/nonexistent")

        # Should return False for unknown command
        assert result is False

    def test_execute_non_debug_command(self):
        """Test executing a non-debug command (no /)"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        result = console.execute("help")

        # Should return False for non-debug commands
        assert result is False


class TestPartyManagementCommands:
    """Test party management commands (/addcharacter, /removecharacter)"""

    def test_addcharacter_with_all_args(self):
        """Test /addcharacter with class, race, and level specified"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        initial_count = len(party.characters)

        # Add a wizard (use actual race ID from races.json)
        console.cmd_add_character(["wizard", "high_elf", "3"])

        # Should have one more character
        assert len(party.characters) == initial_count + 1

        # Check character properties
        new_char = party.characters[-1]
        assert new_char.character_class == CharacterClass.WIZARD
        assert new_char.level == 3
        assert new_char.race == "high_elf"
        assert new_char.max_hp > 0
        assert new_char.ac > 0

    def test_addcharacter_with_class_and_race(self):
        """Test /addcharacter with class and race (level defaults to 1)"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        console.cmd_add_character(["fighter", "mountain_dwarf"])

        # Check character has level 1
        new_char = party.characters[-1]
        assert new_char.character_class == CharacterClass.FIGHTER
        assert new_char.level == 1
        assert new_char.race == "mountain_dwarf"

    def test_addcharacter_with_class_only(self):
        """Test /addcharacter with only class (race is random, level is 1)"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        console.cmd_add_character(["rogue"])

        # Check character was created with level 1 and some race
        new_char = party.characters[-1]
        assert new_char.character_class == CharacterClass.ROGUE
        assert new_char.level == 1
        assert new_char.race is not None
        assert len(new_char.race) > 0

    def test_addcharacter_with_class_and_level(self):
        """Test /addcharacter with class and level (race is random)"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # When second arg is a number, it's the level (use valid class)
        console.cmd_add_character(["fighter", "5"])

        # Check character has correct level and random race
        new_char = party.characters[-1]
        assert new_char.character_class == CharacterClass.FIGHTER
        assert new_char.level == 5
        assert new_char.race is not None

    def test_addcharacter_invalid_class(self, capsys):
        """Test /addcharacter with invalid class"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        initial_count = len(party.characters)

        # Try invalid class
        console.cmd_add_character(["invalidclass", "elf"])

        # Should not add character
        assert len(party.characters) == initial_count

    def test_addcharacter_invalid_race(self, capsys):
        """Test /addcharacter with invalid race"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        initial_count = len(party.characters)

        # Try invalid race
        console.cmd_add_character(["wizard", "invalidrace"])

        # Should not add character
        assert len(party.characters) == initial_count

    def test_addcharacter_invalid_level(self, capsys):
        """Test /addcharacter with invalid level"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        initial_count = len(party.characters)

        # Try level > 20 (use valid race so it tests level validation)
        console.cmd_add_character(["wizard", "high_elf", "25"])

        # Should not add character
        assert len(party.characters) == initial_count

    def test_addcharacter_no_args(self, capsys):
        """Test /addcharacter with no arguments"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        initial_count = len(party.characters)

        # Try with no args
        console.cmd_add_character([])

        # Should not add character
        assert len(party.characters) == initial_count

    def test_removecharacter(self, monkeypatch):
        """Test /removecharacter command"""
        # Create a character
        abilities = Abilities(10, 10, 10, 10, 10, 10)
        char = Character(
            name="TestChar",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=10
        )
        party = Party([char])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Mock user confirmation
        monkeypatch.setattr('builtins.input', lambda _: 'y')

        # Remove the character
        console.cmd_remove_character(["TestChar"])

        # Should be removed
        assert len(party.characters) == 0

    def test_removecharacter_cancel(self, monkeypatch):
        """Test /removecharacter command with cancellation"""
        # Create a character
        abilities = Abilities(10, 10, 10, 10, 10, 10)
        char = Character(
            name="TestChar",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=10
        )
        party = Party([char])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Mock user cancellation
        monkeypatch.setattr('builtins.input', lambda _: 'n')

        # Try to remove the character
        console.cmd_remove_character(["TestChar"])

        # Should NOT be removed
        assert len(party.characters) == 1

    def test_removecharacter_not_found(self, capsys):
        """Test /removecharacter with character that doesn't exist"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Try to remove non-existent character
        console.cmd_remove_character(["NonExistent"])

        # Should do nothing (still 0 characters)
        assert len(party.characters) == 0

    def test_removecharacter_no_args(self, capsys):
        """Test /removecharacter with no arguments"""
        abilities = Abilities(10, 10, 10, 10, 10, 10)
        char = Character(
            name="TestChar",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=10
        )
        party = Party([char])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        initial_count = len(party.characters)

        # Try with no args
        console.cmd_remove_character([])

        # Should not remove anything
        assert len(party.characters) == initial_count

    def test_addcharacter_initializes_spellcasting(self):
        """Test that /addcharacter properly initializes spellcasting for spellcasters"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Add a wizard
        console.cmd_add_character(["wizard", "human", "1"])

        new_char = party.characters[-1]

        # Wizard should have spellcasting ability set (uses "int" not "intelligence")
        assert new_char.spellcasting_ability is not None
        assert new_char.spellcasting_ability == "int"

        # Should have known spells
        assert len(new_char.known_spells) > 0

    def test_addcharacter_has_equipment(self):
        """Test that /addcharacter gives starting equipment"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Add a fighter
        console.cmd_add_character(["fighter", "human", "1"])

        new_char = party.characters[-1]

        # Should have some inventory items
        assert len(new_char.inventory.items) > 0

    def test_command_registry_has_party_commands(self):
        """Test that command registry includes party management commands"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Party management commands
        assert "addcharacter" in console.commands
        assert "removecharacter" in console.commands

        # /create should NOT exist (we removed it)
        assert "create" not in console.commands


class TestLLMToggleCommand:
    """Test /disablellm command"""

    def test_disablellm_without_cli(self, capsys):
        """Test /disablellm when CLI is not provided"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Execute without CLI
        console.cmd_disable_llm([])

        # Should show error (check captured output would contain error)
        # Since we don't have CLI, it should error

    def test_disablellm_toggle_on(self):
        """Test /disablellm switches to debug provider"""
        from dnd_engine.llm.base import LLMProvider
        from dnd_engine.llm.debug_provider import DebugProvider
        from dnd_engine.llm.enhancer import LLMEnhancer
        from dnd_engine.utils.events import EventBus

        # Create a mock provider
        class MockProvider(LLMProvider):
            def __init__(self):
                super().__init__("test", "test", 10.0, 150)

            async def generate(self, prompt, temperature=0.7):
                return "test response"

            def get_provider_name(self):
                return "Mock Provider"

        # Create mock CLI with LLM enhancer
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        event_bus = EventBus()

        original_provider = MockProvider()
        llm_enhancer = LLMEnhancer(original_provider, event_bus)

        # Add some cached data
        llm_enhancer.cache["test_key"] = "test_value"
        assert len(llm_enhancer.cache) == 1

        # Create a minimal CLI mock
        class MockCLI:
            def __init__(self, llm_enhancer):
                self.llm_enhancer = llm_enhancer

        cli = MockCLI(llm_enhancer)
        console = DebugConsole(game_state, enabled=True, cli=cli)

        # Execute command to enable debug mode
        console.cmd_disable_llm([])

        # Should switch to DebugProvider
        assert isinstance(cli.llm_enhancer.provider, DebugProvider)
        assert console._llm_debug_mode is True
        assert console._original_llm_provider == original_provider
        # Cache should be cleared
        assert len(llm_enhancer.cache) == 0

    def test_disablellm_toggle_off(self):
        """Test /disablellm restores original provider"""
        from dnd_engine.llm.base import LLMProvider
        from dnd_engine.llm.debug_provider import DebugProvider
        from dnd_engine.llm.enhancer import LLMEnhancer
        from dnd_engine.utils.events import EventBus

        # Create a mock provider
        class MockProvider(LLMProvider):
            def __init__(self):
                super().__init__("test", "test", 10.0, 150)

            async def generate(self, prompt, temperature=0.7):
                return "test response"

            def get_provider_name(self):
                return "Mock Provider"

        # Create mock CLI with LLM enhancer
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        event_bus = EventBus()

        original_provider = MockProvider()
        llm_enhancer = LLMEnhancer(original_provider, event_bus)

        # Create a minimal CLI mock
        class MockCLI:
            def __init__(self, llm_enhancer):
                self.llm_enhancer = llm_enhancer

        cli = MockCLI(llm_enhancer)
        console = DebugConsole(game_state, enabled=True, cli=cli)

        # Enable debug mode first
        console.cmd_disable_llm([])
        assert isinstance(cli.llm_enhancer.provider, DebugProvider)

        # Add some cached debug data
        llm_enhancer.cache["debug_key"] = "debug_value"
        assert len(llm_enhancer.cache) == 1

        # Toggle back to original
        console.cmd_disable_llm([])

        # Should restore original provider
        assert cli.llm_enhancer.provider == original_provider
        assert console._llm_debug_mode is False
        # Cache should be cleared
        assert len(llm_enhancer.cache) == 0

    def test_disablellm_without_llm_enhancer(self, capsys):
        """Test /disablellm when llm_enhancer is None"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")

        # Create a minimal CLI mock without llm_enhancer
        class MockCLI:
            def __init__(self):
                self.llm_enhancer = None

        cli = MockCLI()
        console = DebugConsole(game_state, enabled=True, cli=cli)

        # Execute command
        console.cmd_disable_llm([])

        # Should handle gracefully (no crash)

    def test_command_registry_has_disablellm(self):
        """Test that command registry includes disablellm"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        assert "disablellm" in console.commands
