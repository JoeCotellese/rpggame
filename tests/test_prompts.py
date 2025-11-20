"""Unit tests for LLM prompt template functions."""

from dnd_engine.llm.prompts import (
    build_combat_action_prompt,
    build_death_prompt,
    build_room_description_prompt,
    build_victory_prompt,
)


class TestRoomDescriptionPrompt:
    """Test room description prompt building."""

    def test_build_room_description_with_full_data(self) -> None:
        """Test building room description prompt with complete data."""
        room_data = {
            "name": "Torture Chamber",
            "description": "A dark room with rusty chains hanging from the ceiling.",
            "exits": ["north", "south"],
            "contents": ["chest", "skeleton"]
        }

        prompt = build_room_description_prompt(room_data)

        assert "Torture Chamber" in prompt
        assert "dark room with rusty chains" in prompt
        assert "D&D" in prompt
        assert "atmospheric" in prompt or "vivid" in prompt

    def test_build_room_description_minimal_data(self) -> None:
        """Test building room description with minimal data."""
        room_data = {
            "name": "Chamber"
        }

        prompt = build_room_description_prompt(room_data)

        assert "Chamber" in prompt
        assert prompt is not None
        assert len(prompt) > 0

    def test_build_room_description_no_name(self) -> None:
        """Test building room description without name."""
        room_data = {
            "description": "A mysterious chamber"
        }

        prompt = build_room_description_prompt(room_data)

        assert "mysterious chamber" in prompt or "chamber" in prompt

    def test_build_room_description_with_single_monster(self) -> None:
        """Test building room description with a single monster."""
        room_data = {
            "name": "Guard Post",
            "description": "A narrow corridor with weapon racks on the walls.",
            "monsters": ["Goblin"]
        }

        prompt = build_room_description_prompt(room_data)

        assert "Guard Post" in prompt
        assert "narrow corridor" in prompt
        assert "Goblin" in prompt
        assert "hostile" in prompt
        assert "threatening" in prompt or "stance" in prompt or "readiness" in prompt

    def test_build_room_description_with_two_monsters(self) -> None:
        """Test building room description with two monsters."""
        room_data = {
            "name": "Barracks",
            "description": "A messy chamber with scattered bedrolls.",
            "monsters": ["Goblin", "Wolf"]
        }

        prompt = build_room_description_prompt(room_data)

        assert "Barracks" in prompt
        assert "Goblin" in prompt
        assert "Wolf" in prompt
        assert "hostile" in prompt
        assert " and " in prompt  # Natural language conjunction

    def test_build_room_description_with_multiple_same_monsters(self) -> None:
        """Test building room description with multiple monsters of the same type."""
        room_data = {
            "name": "Throne Room",
            "description": "A grand chamber with a bone throne.",
            "monsters": ["Goblin", "Goblin", "Goblin"]
        }

        prompt = build_room_description_prompt(room_data)

        assert "Throne Room" in prompt
        assert "3 Goblins" in prompt or "3 goblins" in prompt
        assert "hostile" in prompt

    def test_build_room_description_with_mixed_monsters(self) -> None:
        """Test building room description with mixed monster types."""
        room_data = {
            "name": "Kennel",
            "description": "A dirty room filled with cages.",
            "monsters": ["Goblin", "Goblin", "Wolf", "Wolf", "Wolf"]
        }

        prompt = build_room_description_prompt(room_data)

        assert "Kennel" in prompt
        assert "2 Goblins" in prompt or "2 goblins" in prompt
        # Note: Simple pluralization adds 's', so "Wolf" becomes "Wolfs"
        assert "3 Wolf" in prompt  # Matches "3 Wolfs" or "3 wolves"
        assert "hostile" in prompt

    def test_build_room_description_without_monsters(self) -> None:
        """Test building room description explicitly with no monsters."""
        room_data = {
            "name": "Safe Room",
            "description": "A quiet chamber with no threats.",
            "monsters": []
        }

        prompt = build_room_description_prompt(room_data)

        assert "Safe Room" in prompt
        assert "quiet chamber" in prompt
        assert "hostile" not in prompt
        assert "threatening" not in prompt

    def test_build_room_description_combat_starting_false(self) -> None:
        """Test building room description with combat_starting=False (default behavior)."""
        room_data = {
            "name": "Guard Post",
            "description": "A narrow corridor with weapon racks.",
            "monsters": ["Goblin", "Wolf"]
        }

        prompt = build_room_description_prompt(room_data, combat_starting=False)

        assert "Guard Post" in prompt
        assert "Goblin" in prompt
        assert "Wolf" in prompt
        assert "hostile" in prompt
        # Should have standard monster acknowledgment instructions
        assert "stance" in prompt or "readiness" in prompt or "threatening" in prompt
        # Should NOT have combat initiation instructions
        assert "combat begins" not in prompt.lower()
        assert "battle is about to erupt" not in prompt.lower()

    def test_build_room_description_combat_starting_true(self) -> None:
        """Test building room description with combat_starting=True (combat initiation)."""
        room_data = {
            "name": "Throne Room",
            "description": "A grand chamber with a bone throne.",
            "monsters": ["Goblin Boss", "Goblin", "Goblin"]
        }

        prompt = build_room_description_prompt(room_data, combat_starting=True)

        assert "Throne Room" in prompt
        assert "Goblin Boss" in prompt
        assert "2 Goblin" in prompt
        assert "hostile" in prompt
        # Should have combat initiation instructions
        assert "combat begins" in prompt.lower() or "battle" in prompt.lower()
        assert "enemies react" in prompt.lower() or "threatening stance" in prompt.lower() or "aggressive" in prompt.lower()
        # Should tell LLM to transition into combat
        assert "transition" in prompt.lower() or "escalation" in prompt.lower()

    def test_build_room_description_combat_starting_without_monsters(self) -> None:
        """Test building room description with combat_starting=True but no monsters (edge case)."""
        room_data = {
            "name": "Empty Room",
            "description": "A quiet chamber.",
            "monsters": []
        }

        prompt = build_room_description_prompt(room_data, combat_starting=True)

        assert "Empty Room" in prompt
        assert "quiet chamber" in prompt
        # No monsters, so should not have combat instructions even if flag is True
        assert "hostile" not in prompt
        assert "combat begins" not in prompt.lower()

    def test_build_room_description_combat_starting_default_false(self) -> None:
        """Test that combat_starting defaults to False when not specified."""
        room_data = {
            "name": "Barracks",
            "description": "A messy chamber with bedrolls.",
            "monsters": ["Goblin"]
        }

        # Call without combat_starting parameter (should default to False)
        prompt = build_room_description_prompt(room_data)

        assert "Barracks" in prompt
        assert "Goblin" in prompt
        assert "hostile" in prompt
        # Should NOT have combat initiation instructions with default
        assert "combat begins" not in prompt.lower()
        assert "battle is about to erupt" not in prompt.lower()


class TestCombatActionPrompt:
    """Test combat action prompt building."""

    def test_build_combat_action_hit(self) -> None:
        """Test building combat action prompt for a hit."""
        action_data = {
            "attacker": "Thorin",
            "defender": "Goblin",
            "weapon": "longsword",
            "damage": 8,
            "hit": True
        }

        prompt = build_combat_action_prompt(action_data)

        assert "Thorin" in prompt
        assert "Goblin" in prompt
        assert "longsword" in prompt
        assert "8" in prompt
        assert "hit" in prompt or "damage" in prompt

    def test_build_combat_action_miss(self) -> None:
        """Test building combat action prompt for a miss."""
        action_data = {
            "attacker": "Bjorn",
            "defender": "Orc",
            "weapon": "battleaxe",
            "damage": 0,
            "hit": False
        }

        prompt = build_combat_action_prompt(action_data)

        assert "Bjorn" in prompt
        assert "Orc" in prompt
        assert "battleaxe" in prompt
        assert "miss" in prompt

    def test_build_combat_action_minimal_data(self) -> None:
        """Test building combat action with minimal data."""
        action_data = {"hit": True}

        prompt = build_combat_action_prompt(action_data)

        assert prompt is not None
        assert len(prompt) > 0

    def test_build_combat_action_with_location(self) -> None:
        """Test building combat action prompt with location context."""
        action_data = {
            "attacker": "Gandalf",
            "defender": "Balrog",
            "weapon": "staff",
            "damage": 12,
            "hit": True,
            "location": "Bridge of Khazad-dûm"
        }

        prompt = build_combat_action_prompt(action_data)

        assert "Gandalf" in prompt
        assert "Balrog" in prompt
        assert "Bridge of Khazad-dûm" in prompt
        assert "Location:" in prompt
        assert "environmental" in prompt.lower() or "location" in prompt.lower()

    def test_build_combat_action_with_full_context(self) -> None:
        """Test building combat action prompt with full context (weapon, armor, race, damage type)."""
        action_data = {
            "attacker": "Thorin",
            "defender": "Goblin",
            "weapon": "Longsword",
            "damage": 9,
            "hit": True,
            "location": "Goblin Warren",
            "attacker_race": "mountain dwarf",
            "defender_armor": "leather armor",
            "damage_type": "slashing"
        }

        prompt = build_combat_action_prompt(action_data)

        assert "Thorin" in prompt
        assert "mountain dwarf" in prompt
        assert "Goblin" in prompt
        assert "leather armor" in prompt
        assert "Longsword" in prompt
        assert "slashing" in prompt
        assert "Goblin Warren" in prompt
        assert "9" in prompt

    def test_build_combat_action_round_zero_or_one(self) -> None:
        """Test combat action prompt shows opening exchange for round 0-1."""
        # Test round 0 (first round of combat)
        action_data = {
            "attacker": "Legolas",
            "defender": "Orc",
            "weapon": "Longbow",
            "damage": 7,
            "hit": True,
            "round_number": 0
        }

        prompt = build_combat_action_prompt(action_data)
        assert "opening exchange" in prompt.lower()
        assert "Legolas" in prompt

        # Test round 1 (still early combat)
        action_data["round_number"] = 1
        prompt = build_combat_action_prompt(action_data)
        assert "opening exchange" in prompt.lower()

    def test_build_combat_action_ongoing_battle(self) -> None:
        """Test combat action prompt shows ongoing battle for round 2+."""
        action_data = {
            "attacker": "Gimli",
            "defender": "Uruk-hai",
            "weapon": "Battleaxe",
            "damage": 10,
            "hit": True,
            "round_number": 3
        }

        prompt = build_combat_action_prompt(action_data)

        assert "round 3" in prompt.lower()
        assert "ongoing battle" in prompt.lower()
        assert "Gimli" in prompt


class TestDeathPrompt:
    """Test character death prompt building."""

    def test_build_death_prompt_full_data(self) -> None:
        """Test building death prompt with full character data."""
        character_data = {
            "name": "Thorin Ironshield",
            "race": "Dwarf",
            "class": "Fighter",
            "cause": "was slain by a dragon's fiery breath"
        }

        prompt = build_death_prompt(character_data)

        assert "Thorin Ironshield" in prompt
        assert "slain by a dragon's fiery breath" in prompt
        assert "death" in prompt or "final" in prompt

    def test_build_death_prompt_minimal_data(self) -> None:
        """Test building death prompt with minimal data."""
        character_data = {
            "name": "Hero"
        }

        prompt = build_death_prompt(character_data)

        assert "Hero" in prompt
        assert prompt is not None

    def test_build_death_prompt_player_death(self) -> None:
        """Test building death prompt for player character."""
        character_data = {
            "name": "Gandalf",
            "is_player": True,
            "cause": "fell defending the party"
        }

        prompt = build_death_prompt(character_data)

        assert "Gandalf" in prompt
        assert "heroic" in prompt.lower()
        assert "fell defending the party" in prompt

    def test_build_death_prompt_enemy_death(self) -> None:
        """Test building death prompt for enemy creature."""
        character_data = {
            "name": "Goblin",
            "is_player": False,
            "cause": "was struck down"
        }

        prompt = build_death_prompt(character_data)

        assert "Goblin" in prompt
        assert "defeat" in prompt.lower()
        assert "was struck down" in prompt


class TestVictoryPrompt:
    """Test combat victory prompt building."""

    def test_build_victory_prompt_full_data(self) -> None:
        """Test building victory prompt with full combat data."""
        combat_data = {
            "enemies": ["Goblin Warrior", "Goblin Shaman"],
            "final_blow": "Thorin cleaved through the last goblin with his axe"
        }

        prompt = build_victory_prompt(combat_data)

        assert "Goblin Warrior" in prompt or "Goblin" in prompt
        assert "Thorin cleaved" in prompt
        assert "victory" in prompt or "defeat" in prompt

    def test_build_victory_prompt_minimal_data(self) -> None:
        """Test building victory prompt with minimal data."""
        combat_data = {}

        prompt = build_victory_prompt(combat_data)

        assert prompt is not None
        assert len(prompt) > 0
