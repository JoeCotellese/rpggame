"""Unit tests for LLM prompt template functions."""

from dnd_engine.core.game_state import BattlefieldState, CombatantStatus
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
        # Should include length instruction for standard rooms
        assert "LENGTH:" in prompt
        assert "2-3 sentences" in prompt or "50 words" in prompt

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

    def test_build_room_description_pov_constraints(self) -> None:
        """Test that room description enforces third-person POV and no arrival language."""
        room_data = {
            "name": "Town Square",
            "description": "A bustling market square with a fountain."
        }

        prompt = build_room_description_prompt(room_data)

        # Should enforce third-person POV
        assert "third-person" in prompt.lower() or 'never "you"' in prompt.lower()
        # Should prohibit arrival/transition language
        assert "never describe arrival" in prompt.lower() or "stepping into" in prompt.lower()

    def test_build_room_description_significance_levels(self) -> None:
        """Test that room significance affects description length instruction."""
        base_room = {
            "name": "Test Room",
            "description": "A test room."
        }

        # Minor rooms get shortest descriptions
        minor_room = {**base_room, "significance": "minor"}
        prompt = build_room_description_prompt(minor_room)
        assert "1 sentence" in prompt
        assert "20 words" in prompt

        # Standard rooms (default) get medium descriptions
        standard_room = {**base_room, "significance": "standard"}
        prompt = build_room_description_prompt(standard_room)
        assert "2-3 sentences" in prompt
        assert "50 words" in prompt

        # Major rooms get longest descriptions
        major_room = {**base_room, "significance": "major"}
        prompt = build_room_description_prompt(major_room)
        assert "3-4 sentences" in prompt
        assert "80 words" in prompt

    def test_build_room_description_combat_overrides_significance(self) -> None:
        """Test that combat starting overrides significance to short description."""
        room_data = {
            "name": "Boss Chamber",
            "description": "The dragon's lair.",
            "significance": "major",  # Would normally be long
            "monsters": ["Dragon"]
        }

        prompt = build_room_description_prompt(room_data, combat_starting=True)

        # Combat should override to short, even for major rooms
        assert "1-2 sentences" in prompt
        assert "40 words" in prompt
        assert "Combat is imminent" in prompt


class TestCombatActionPrompt:
    """Test combat action prompt building."""

    def test_build_combat_action_hit(self) -> None:
        """Test building combat action prompt for a regular hit."""
        action_data = {
            "attacker": "Thorin",
            "defender": "Goblin",
            "weapon": "longsword",
            "hit": True
        }

        prompt = build_combat_action_prompt(action_data)

        assert "Thorin" in prompt
        assert "Goblin" in prompt
        assert "longsword" in prompt
        assert "hit" in prompt.lower()
        # Regular hits should request brief output (max 12 words, punchy sentence)
        assert "max 12 words" in prompt or "punchy sentence" in prompt.lower()
        # Should enforce third-person POV (player controls multiple characters)
        assert "third-person" in prompt.lower() or 'never "you"' in prompt.lower()

    def test_build_combat_action_miss(self) -> None:
        """Test building combat action prompt for a miss."""
        action_data = {
            "attacker": "Bjorn",
            "defender": "Orc",
            "weapon": "battleaxe",
            "hit": False
        }

        prompt = build_combat_action_prompt(action_data)

        assert "Bjorn" in prompt
        assert "Orc" in prompt
        assert "battleaxe" in prompt
        assert "miss" in prompt.lower()
        # Misses should be extra brief (max 10 words)
        assert "max 10 words" in prompt

    def test_build_combat_action_minimal_data(self) -> None:
        """Test building combat action with minimal data."""
        action_data = {"hit": True}

        prompt = build_combat_action_prompt(action_data)

        assert prompt is not None
        assert len(prompt) > 0

    def test_build_combat_action_with_location(self) -> None:
        """Test building combat action prompt with location context.

        Location is only included for killing blows (tiered verbosity).
        """
        action_data = {
            "attacker": "Gandalf",
            "defender": "Balrog",
            "weapon": "staff",
            "hit": True,
            "is_killing_blow": True,
            "location": "Bridge of Khazad-dûm"
        }

        prompt = build_combat_action_prompt(action_data)

        assert "Gandalf" in prompt
        assert "Balrog" in prompt
        # Location is included for killing blows
        assert "Bridge of Khazad-dûm" in prompt
        assert "Location:" in prompt

    def test_build_combat_action_critical_hit(self) -> None:
        """Test building combat action prompt for a critical hit.

        Critical hits (non-killing) are more concise - no location or history
        context. They request visceral but brief output (15-20 words).
        """
        action_data = {
            "attacker": "Thorin",
            "defender": "Goblin",
            "weapon": "Longsword",
            "hit": True,
            "is_critical": True,
            "location": "Goblin Warren",
            "damage_type": "slashing",
            "combat_history": ["Goblin attacked Thorin", "Thorin missed Goblin"]
        }

        prompt = build_combat_action_prompt(action_data)

        assert "Thorin" in prompt
        assert "Goblin" in prompt
        assert "Longsword" in prompt
        assert "slashing" in prompt
        # Critical hits should request visceral output (15-20 words)
        assert "visceral" in prompt.lower() or "15-20 words" in prompt
        # Critical hits emphasize enemy survives
        assert "survives" in prompt.lower() or "staggers" in prompt.lower()

    def test_build_combat_action_killing_blow(self) -> None:
        """Test building combat action prompt for a killing blow."""
        action_data = {
            "attacker": "Legolas",
            "defender": "Orc",
            "weapon": "Longbow",
            "hit": True,
            "is_killing_blow": True,
            "combat_history": [
                "Orc attacked Legolas",
                "Legolas shot Orc",
                "Orc attacked Gimli",
                "Gimli hit Orc"
            ]
        }

        prompt = build_combat_action_prompt(action_data)

        assert "Legolas" in prompt
        assert "killing blow" in prompt.lower() or "strikes down" in prompt.lower()
        # Killing blows get more history
        assert "Recent Actions:" in prompt
        # Killing blows should request 2-3 sentences
        assert "2-3" in prompt

    def test_build_combat_action_regular_hit_excludes_history(self) -> None:
        """Test that regular hits don't include combat history."""
        action_data = {
            "attacker": "Gimli",
            "defender": "Uruk-hai",
            "weapon": "Battleaxe",
            "hit": True,
            "combat_history": ["Uruk-hai attacked Gimli", "Gimli attacked Uruk-hai"]
        }

        prompt = build_combat_action_prompt(action_data)

        assert "Gimli" in prompt
        # Regular hits should NOT include history
        assert "Recent Actions:" not in prompt

    def test_build_combat_action_killing_blow_with_battlefield_state(self) -> None:
        """Test combat action prompt includes battlefield state for killing blows."""
        # Create a BattlefieldState with party and enemy combatants
        party_combatants = [
            CombatantStatus(
                name="Thorin",
                display_name="Thorin",
                current_hp=25,
                max_hp=30,
                is_alive=True,
                conditions=[],
                is_player=True,
                ac=16
            ),
            CombatantStatus(
                name="Bjorn",
                display_name="Bjorn",
                current_hp=15,
                max_hp=28,
                is_alive=True,
                conditions=[],
                is_player=True,
                ac=14
            )
        ]

        enemy_combatants = [
            CombatantStatus(
                name="Skeleton",
                display_name="Skeleton 1",
                current_hp=10,
                max_hp=13,
                is_alive=True,
                conditions=[],
                is_player=False,
                ac=13
            ),
            CombatantStatus(
                name="Skeleton",
                display_name="Skeleton 2",
                current_hp=8,
                max_hp=13,
                is_alive=True,
                conditions=[],
                is_player=False,
                ac=13
            )
        ]

        battlefield_state = BattlefieldState(
            party_combatants=party_combatants,
            enemy_combatants=enemy_combatants,
            round_number=2,
            current_turn="Thorin",
            in_combat=True
        )

        action_data = {
            "attacker": "Thorin",
            "defender": "Skeleton 1",
            "weapon": "battleaxe",
            "hit": True,
            "is_killing_blow": True,
            "battlefield_state": battlefield_state
        }

        prompt = build_combat_action_prompt(action_data)

        # Verify the prompt was built successfully
        assert "Thorin" in prompt
        assert "Skeleton 1" in prompt or "Skeleton" in prompt
        assert prompt is not None
        assert len(prompt) > 0

        # Verify battlefield context is included for killing blows
        assert "Battlefield:" in prompt
        assert "25/30" in prompt or "Thorin" in prompt

    def test_build_combat_action_regular_hit_excludes_battlefield_state(self) -> None:
        """Test that regular hits don't include battlefield state."""
        party_combatants = [
            CombatantStatus(
                name="Thorin",
                display_name="Thorin",
                current_hp=25,
                max_hp=30,
                is_alive=True,
                conditions=[],
                is_player=True,
                ac=16
            )
        ]

        enemy_combatants = [
            CombatantStatus(
                name="Skeleton",
                display_name="Skeleton 1",
                current_hp=10,
                max_hp=13,
                is_alive=True,
                conditions=[],
                is_player=False,
                ac=13
            )
        ]

        battlefield_state = BattlefieldState(
            party_combatants=party_combatants,
            enemy_combatants=enemy_combatants,
            round_number=2,
            current_turn="Thorin",
            in_combat=True
        )

        action_data = {
            "attacker": "Thorin",
            "defender": "Skeleton 1",
            "weapon": "battleaxe",
            "hit": True,
            "battlefield_state": battlefield_state
        }

        prompt = build_combat_action_prompt(action_data)

        # Regular hits should NOT include battlefield state
        assert "Battlefield:" not in prompt
        assert "25/30" not in prompt
        assert "10/13" not in prompt


class TestDeathPrompt:
    """Test character death prompt building."""

    def test_build_death_prompt_enemy(self) -> None:
        """Test building death prompt for enemy (brief, focused)."""
        character_data = {
            "name": "Skeleton",
            "cause": "was shattered by a mighty blow"
        }

        prompt = build_death_prompt(character_data)

        assert "Skeleton" in prompt
        assert "shattered" in prompt
        # Enemy deaths should be brief
        assert "brief sentence" in prompt.lower() or "falls" in prompt.lower()
        # Should enforce third-person POV
        assert "third-person" in prompt.lower() or 'never "you"' in prompt.lower()

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
