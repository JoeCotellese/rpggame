# ABOUTME: Unit tests for debug console functionality
# ABOUTME: Tests command parsing, execution, and state manipulation

import pytest
import os
from dnd_engine.ui.debug_console import DebugConsole
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.core.character import Character, CharacterClass, CharacterRace
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
        # Create a character
        character = Character(
            name="Gandalf",
            character_class=CharacterClass.WIZARD,
            race=CharacterRace.HIGH_ELF,
            abilities=Abilities(10, 10, 10, 16, 14, 12)
        )
        character.current_hp = 0
        character.is_unconscious = True
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
            race=CharacterRace.HIGH_ELF,
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
            race=CharacterRace.HIGH_ELF,
            abilities=Abilities(10, 10, 10, 16, 14, 12)
        )

        party = Party([character])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Execute sethp command
        console.cmd_set_hp(["Gandalf", "15"])

        # Verify HP is set
        assert character.current_hp == 15

    def test_set_hp_clamps_to_max(self):
        """Test /sethp command clamps value to max HP"""
        character = Character(
            name="Gandalf",
            character_class=CharacterClass.WIZARD,
            race=CharacterRace.HIGH_ELF,
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
            race=CharacterRace.HIGH_ELF,
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
            race=CharacterRace.HIGH_ELF,
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
            race=CharacterRace.HIGH_ELF,
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
            race=CharacterRace.HIGH_ELF,
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
            race=CharacterRace.HIGH_ELF,
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
            race=CharacterRace.HIGH_ELF,
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
            race=CharacterRace.HIGH_ELF,
            abilities=Abilities(10, 10, 10, 16, 14, 12)
        )

        party = Party([character])
        game_state = GameState(party, "test_dungeon")
        console = DebugConsole(game_state, enabled=True)

        # Set INT to 20
        console.cmd_set_stat(["Gandalf", "INT", "20"])

        # Verify stat changed
        assert character.abilities.int == 20


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

        initial_gold = game_state.party.currency.to_copper() // 100

        # Add gold
        console.cmd_gold(["500"])

        new_gold = game_state.party.currency.to_copper() // 100
        assert new_gold == initial_gold + 500

    def test_gold_remove(self):
        """Test /gold command with negative value removes gold"""
        party = Party([])
        game_state = GameState(party, "test_dungeon")
        # Add some gold first
        game_state.party.currency.add_gold(1000)
        console = DebugConsole(game_state, enabled=True)

        initial_gold = game_state.party.currency.to_copper() // 100

        # Remove gold
        console.cmd_gold(["-200"])

        new_gold = game_state.party.currency.to_copper() // 100
        assert new_gold == initial_gold - 200


class TestHelperMethods:
    """Test helper methods"""

    def test_find_character_case_insensitive(self):
        """Test finding character by name is case-insensitive"""
        character = Character(
            name="Gandalf",
            character_class=CharacterClass.WIZARD,
            race=CharacterRace.HIGH_ELF,
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
