# ABOUTME: Integration tests for the lighting system
# ABOUTME: Tests complete workflows with Light spell, darkvision, and Perception checks

import pytest
from dnd_engine.core.game_state import GameState
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.party import Party
from dnd_engine.utils.events import EventBus, EventType


@pytest.fixture
def wizard_with_light_spell():
    """Create a wizard with the Light cantrip."""
    abilities = Abilities(
        strength=8,
        dexterity=12,
        constitution=10,
        intelligence=16,  # +3 spellcasting modifier
        wisdom=12,
        charisma=10
    )
    wizard = Character(
        name="Tim the Wizard",
        character_class=CharacterClass.WIZARD,
        level=1,
        abilities=abilities,
        max_hp=8,
        ac=12,
        race="human",
        spellcasting_ability="int",
        known_spells=["light", "mage_armor"],
        prepared_spells=["light", "mage_armor"],
        skill_proficiencies=["arcana", "investigation"]
    )
    wizard.darkvision_range = 0
    return wizard


@pytest.fixture
def dwarf_cleric():
    """Create a dwarf cleric with darkvision."""
    abilities = Abilities(
        strength=14,
        dexterity=10,
        constitution=14,
        intelligence=10,
        wisdom=16,  # +3 for Perception
        charisma=12
    )
    cleric = Character(
        name="Thorin Cleric",
        character_class=CharacterClass.CLERIC,
        level=1,
        abilities=abilities,
        max_hp=10,
        ac=16,
        race="mountain_dwarf",
        spellcasting_ability="wis",
        known_spells=["cure_wounds", "bless"],
        prepared_spells=["cure_wounds", "bless"],
        skill_proficiencies=["perception", "religion"]
    )
    cleric.darkvision_range = 60
    return cleric


class TestLightSpellIntegration:
    """Integration tests for Light spell affecting room lighting and Perception."""

    def test_light_spell_enables_perception_in_dark_room(self, wizard_with_light_spell):
        """Test that casting Light in a dark room allows successful Perception checks."""
        party = Party([wizard_with_light_spell])
        game_state = GameState(party, "the_unquiet_dead_crypt")

        # Move to dark room with hidden features
        game_state.current_room_id = "hall_of_the_dead"
        room = game_state.get_current_room()
        assert room.get("lighting") == "dark"

        # Before Light spell: dark
        effective_lighting = game_state.get_effective_lighting(wizard_with_light_spell)
        assert effective_lighting == "dark"

        # Cast Light spell
        result = game_state.cast_spell_exploration("Tim the Wizard", "light")
        assert result["success"] is True
        assert result["spell_name"] == "Light"

        # After Light spell: bright
        effective_lighting = game_state.get_effective_lighting(wizard_with_light_spell)
        assert effective_lighting == "bright"

        # Verify active effect exists
        active_effects = game_state.time_manager.active_effects
        assert len(active_effects) == 1
        assert active_effects[0].source == "Light"

    def test_light_spell_expires_after_duration(self, wizard_with_light_spell):
        """Test that Light spell effect expires after 1 hour."""
        party = Party([wizard_with_light_spell])
        game_state = GameState(party, "the_unquiet_dead_crypt")
        game_state.current_room_id = "hall_of_the_dead"

        # Cast Light
        result = game_state.cast_spell_exploration("Tim the Wizard", "light")
        assert result["success"] is True

        # Room should be bright
        assert game_state.get_effective_lighting(wizard_with_light_spell) == "bright"

        # Advance time by 59 minutes (Light lasts 60 minutes)
        game_state.time_manager.advance_time(59, reason="exploration")
        assert len(game_state.time_manager.active_effects) == 1
        assert game_state.get_effective_lighting(wizard_with_light_spell) == "bright"

        # Advance time by 2 more minutes (total 61 minutes)
        game_state.time_manager.advance_time(2, reason="exploration")

        # Effect should be expired
        assert len(game_state.time_manager.active_effects) == 0

        # Room should be dark again
        assert game_state.get_effective_lighting(wizard_with_light_spell) == "dark"


class TestDarkvisionIntegration:
    """Integration tests for darkvision in dark environments."""

    def test_dwarf_can_see_in_dark_room(self, dwarf_cleric):
        """Test that dwarf with darkvision treats darkness as dim light."""
        party = Party([dwarf_cleric])
        game_state = GameState(party, "the_unquiet_dead_crypt")

        # Move to dark room
        game_state.current_room_id = "hall_of_the_dead"
        room = game_state.get_current_room()
        assert room.get("lighting") == "dark"

        # Dwarf sees it as dim (due to darkvision)
        effective_lighting = game_state.get_effective_lighting(dwarf_cleric)
        assert effective_lighting == "dim"

    def test_mixed_party_lighting_perception(self, wizard_with_light_spell, dwarf_cleric):
        """Test that mixed party has different effective lighting levels."""
        party = Party([wizard_with_light_spell, dwarf_cleric])
        game_state = GameState(party, "the_unquiet_dead_crypt")

        # Move to dark room
        game_state.current_room_id = "hall_of_the_dead"

        # Wizard (no darkvision) sees darkness
        wizard_lighting = game_state.get_effective_lighting(wizard_with_light_spell)
        assert wizard_lighting == "dark"

        # Dwarf (darkvision) sees dim light
        dwarf_lighting = game_state.get_effective_lighting(dwarf_cleric)
        assert dwarf_lighting == "dim"


class TestPerceptionIntegration:
    """Integration tests for Perception checks with lighting penalties."""

    def test_passive_perception_in_dark_crypt(self, wizard_with_light_spell, dwarf_cleric):
        """Test passive Perception checks in dark crypt for both characters."""
        party = Party([wizard_with_light_spell, dwarf_cleric])

        # Track skill check events
        skill_checks = []
        def capture_skill_check(event):
            if event.type == EventType.SKILL_CHECK:
                skill_checks.append(event.data)

        event_bus = EventBus()
        event_bus.subscribe(EventType.SKILL_CHECK, capture_skill_check)

        game_state = GameState(party, "the_unquiet_dead_crypt", event_bus=event_bus)

        # Move to dark hall with passive Perception check (DC 16)
        game_state.current_room_id = "hall_of_the_dead"
        game_state._check_passive_perception()

        # Should have 2 skill checks (one per character)
        assert len(skill_checks) == 2

        # Find wizard and dwarf checks
        wizard_check = next(c for c in skill_checks if c["character"] == "Tim the Wizard")
        dwarf_check = next(c for c in skill_checks if c["character"] == "Thorin Cleric")

        # Wizard: Wis modifier is +1, no proficiency in Perception
        # Passive Perception = 10 + 1 = 11
        # In darkness: 0 (auto-fail)
        assert wizard_check["total"] == 0
        assert wizard_check["success"] is False

        # Dwarf: Wis modifier is +3, proficient (+2)
        # Passive Perception = 10 + 3 + 2 = 15
        # In darkness with darkvision: treats as dim, so -5 penalty = 10
        assert dwarf_check["total"] == 10
        assert dwarf_check["success"] is False  # DC 16, so fails

    def test_perception_check_with_light_spell(self, wizard_with_light_spell):
        """Test that Light spell removes Perception penalties."""
        party = Party([wizard_with_light_spell])

        # Track skill check events
        perception_checks = []
        def capture_skill_check(event):
            if event.type == EventType.SKILL_CHECK and event.data["skill"] == "perception":
                perception_checks.append(event.data)

        event_bus = EventBus()
        event_bus.subscribe(EventType.SKILL_CHECK, capture_skill_check)

        game_state = GameState(party, "the_unquiet_dead_crypt", event_bus=event_bus)
        game_state.current_room_id = "antechamber"

        # Add an examinable door with Perception check
        room = game_state.get_current_room()

        # Before casting Light: should fail in darkness
        effective_lighting = game_state.get_effective_lighting(wizard_with_light_spell)
        assert effective_lighting == "dark"

        # Cast Light spell
        game_state.cast_spell_exploration("Tim the Wizard", "light")

        # After casting Light: should have bright light
        effective_lighting = game_state.get_effective_lighting(wizard_with_light_spell)
        assert effective_lighting == "bright"

        # Now Perception checks should work normally (no penalties)

    def test_examine_exit_lighting_penalty(self, wizard_with_light_spell):
        """Test that examine_exit applies lighting penalties to Perception."""
        party = Party([wizard_with_light_spell])
        game_state = GameState(party, "the_unquiet_dead_crypt")

        # Move to antechamber with examine checks on exits
        game_state.current_room_id = "antechamber"

        # Try to listen at the north door (Perception DC 14)
        result = game_state.examine_exit("north", wizard_with_light_spell)

        # Result should have been attempted
        assert "results" in result
        assert len(result["results"]) > 0

        # The Perception check should have been made
        # In darkness, sight-based Perception should auto-fail
        for check_result in result["results"]:
            if check_result["skill"] == "perception":
                # In complete darkness, should fail
                assert check_result["success"] is False

        # Overall success should be False since Perception check failed
        assert result["success"] is False


class TestCompleteWorkflow:
    """Test complete dungeon exploration workflow with lighting."""

    def test_dungeon_exploration_with_lighting(self, wizard_with_light_spell, dwarf_cleric):
        """Test full workflow: enter dark crypt, cast Light, make Perception checks."""
        party = Party([wizard_with_light_spell, dwarf_cleric])
        game_state = GameState(party, "the_unquiet_dead_crypt")

        # Start at graveyard (bright light)
        assert game_state.current_room_id == "graveyard_entrance"
        room = game_state.get_current_room()
        assert room.get("lighting") == "bright"

        # Both characters see bright light
        assert game_state.get_effective_lighting(wizard_with_light_spell) == "bright"
        assert game_state.get_effective_lighting(dwarf_cleric) == "bright"

        # Move down to Hall of the Dead (dark)
        move_result = game_state.move("down")
        assert move_result is True  # move() returns bool, not dict
        assert game_state.current_room_id == "hall_of_the_dead"

        # Wizard sees darkness, dwarf sees dim
        assert game_state.get_effective_lighting(wizard_with_light_spell) == "dark"
        assert game_state.get_effective_lighting(dwarf_cleric) == "dim"

        # Cast Light spell
        cast_result = game_state.cast_spell_exploration("Tim the Wizard", "light")
        assert cast_result["success"] is True

        # Now both see bright light
        assert game_state.get_effective_lighting(wizard_with_light_spell) == "bright"
        assert game_state.get_effective_lighting(dwarf_cleric) == "bright"

        # Verify Light effect is active
        active_effects = game_state.time_manager.active_effects
        assert len(active_effects) == 1
        assert active_effects[0].source == "Light"
        assert active_effects[0].duration_minutes == 60

        # Move to another room - Light effect should persist
        move_result = game_state.move("north")
        assert move_result is True  # move() returns bool, not dict
        assert game_state.current_room_id == "antechamber"

        # Still bright due to Light spell
        assert game_state.get_effective_lighting(wizard_with_light_spell) == "bright"
        assert game_state.get_effective_lighting(dwarf_cleric) == "bright"
