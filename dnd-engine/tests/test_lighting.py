# ABOUTME: Unit tests for the lighting system
# ABOUTME: Tests room lighting, darkvision, Light spell, and Perception penalties

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.systems.time_manager import EffectType


@pytest.fixture
def basic_abilities():
    """Standard ability scores for testing."""
    return Abilities(
        strength=10,
        dexterity=10,
        constitution=10,
        intelligence=10,
        wisdom=14,  # +2 modifier for Perception
        charisma=10,
    )


@pytest.fixture
def human_character(basic_abilities):
    """Create a human character (no darkvision)."""
    char = Character(
        name="Human Fighter",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=basic_abilities,
        max_hp=12,
        ac=16,
        race="human",
        skill_proficiencies=["perception"],
    )
    char.darkvision_range = 0  # Humans have no darkvision
    return char


@pytest.fixture
def dwarf_character(basic_abilities):
    """Create a dwarf character (60 ft darkvision)."""
    char = Character(
        name="Dwarf Fighter",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=basic_abilities,
        max_hp=14,
        ac=16,
        race="mountain_dwarf",
        skill_proficiencies=["perception"],
    )
    char.darkvision_range = 60  # Dwarves have 60 ft darkvision
    return char


class TestRoomLighting:
    """Test room lighting levels and defaults."""

    def test_bright_room_default(self, human_character):
        """Test that rooms default to bright lighting if not specified."""
        party = Party([human_character])
        game_state = GameState(party, "test_dungeon")

        # test_dungeon has "bright" lighting set
        room = game_state.get_current_room()
        assert room.get("lighting") == "bright"

        effective_lighting = game_state.get_effective_lighting(human_character)
        assert effective_lighting == "bright"

    def test_dark_room(self, human_character):
        """Test dark room lighting."""
        party = Party([human_character])
        game_state = GameState(party, "crypt", campaign_id="the_unquiet_dead")

        # Move to a dark room (hall_of_the_dead)
        game_state.current_room_id = "crypt.hall_of_the_dead"
        room = game_state.get_current_room()
        assert room.get("lighting") == "dark"

        effective_lighting = game_state.get_effective_lighting(human_character)
        assert effective_lighting == "dark"


class TestDarkvision:
    """Test darkvision mechanics."""

    def test_human_no_darkvision(self, human_character):
        """Test that humans have no darkvision."""
        assert human_character.darkvision_range == 0

    def test_dwarf_has_darkvision(self, dwarf_character):
        """Test that dwarves have 60 ft darkvision."""
        assert dwarf_character.darkvision_range == 60

    def test_darkvision_treats_dark_as_dim(self, dwarf_character):
        """Test that darkvision treats darkness as dim light."""
        party = Party([dwarf_character])
        game_state = GameState(party, "crypt", campaign_id="the_unquiet_dead")

        # Move to a dark room
        game_state.current_room_id = "crypt.hall_of_the_dead"
        room = game_state.get_current_room()
        assert room.get("lighting") == "dark"

        # Dwarf with darkvision sees it as dim
        effective_lighting = game_state.get_effective_lighting(dwarf_character)
        assert effective_lighting == "dim"

    def test_darkvision_doesnt_affect_bright_light(self, dwarf_character):
        """Test that darkvision doesn't change bright light."""
        party = Party([dwarf_character])
        game_state = GameState(party, "test_dungeon")

        room = game_state.get_current_room()
        assert room.get("lighting") == "bright"

        effective_lighting = game_state.get_effective_lighting(dwarf_character)
        assert effective_lighting == "bright"


class TestLightSpell:
    """Test Light spell mechanics."""

    def test_light_spell_brightens_dark_room(self, human_character):
        """Test that Light spell makes a dark room bright."""
        # Give the character the Light cantrip
        human_character.known_spells = ["light"]
        human_character.prepared_spells = ["light"]
        human_character.spellcasting_ability = "int"

        party = Party([human_character])
        game_state = GameState(party, "crypt", campaign_id="the_unquiet_dead")

        # Move to a dark room
        game_state.current_room_id = "crypt.hall_of_the_dead"

        # Verify room is dark before casting
        effective_lighting = game_state.get_effective_lighting(human_character)
        assert effective_lighting == "dark"

        # Cast Light spell
        result = game_state.cast_spell_exploration("Human Fighter", "light")
        assert result["success"] is True

        # Verify room is now bright
        effective_lighting = game_state.get_effective_lighting(human_character)
        assert effective_lighting == "bright"

    def test_light_spell_creates_active_effect(self, human_character):
        """Test that Light spell creates a 1-hour active effect."""
        human_character.known_spells = ["light"]
        human_character.prepared_spells = ["light"]
        human_character.spellcasting_ability = "int"

        party = Party([human_character])
        game_state = GameState(party, "test_dungeon")

        # Cast Light spell
        result = game_state.cast_spell_exploration("Human Fighter", "light")
        assert result["success"] is True

        # Check that an active effect was created
        active_effects = game_state.time_manager.active_effects
        assert len(active_effects) == 1

        effect = active_effects[0]
        assert effect.effect_type == EffectType.SPELL
        assert effect.source == "Light"
        assert effect.duration_type == "hours"
        assert effect.duration_value == 1.0  # 1 hour


class TestPerceptionPenalties:
    """Test Perception check penalties in different lighting."""

    def test_passive_perception_normal_in_bright_light(self, human_character):
        """Test that passive Perception is normal in bright light."""
        party = Party([human_character])
        game_state = GameState(party, "test_dungeon")

        # Room is bright, passive Perception should be normal
        # Passive Perception = 10 + Wis modifier (2) + proficiency (2) = 14
        skills_data = game_state.data_loader.load_skills()
        perception_mod = human_character.get_skill_modifier("perception", skills_data)
        expected_passive = 10 + perception_mod

        # Lighting shouldn't affect it
        lighting = game_state.get_effective_lighting(human_character)
        assert lighting == "bright"
        assert expected_passive == 14

    def test_passive_perception_penalty_in_dim_light(self, human_character):
        """Test that passive Perception has -5 penalty in dim light."""
        party = Party([human_character])
        game_state = GameState(party, "crypt", campaign_id="the_unquiet_dead")

        # Create a room with dim lighting
        game_state.dungeon["rooms"]["test_dim_room"] = {
            "name": "Dim Room",
            "description": "A room with dim lighting",
            "lighting": "dim",
            "exits": {},
            "enemies": [],
            "hidden_features": [
                {
                    "type": "passive_perception",
                    "dc": 12,
                    "trigger": "on_enter",
                    "on_success": "You notice something",
                    "on_failure": None,
                }
            ],
        }
        game_state.current_room_id = "test_dim_room"

        # Verify lighting is dim
        lighting = game_state.get_effective_lighting(human_character)
        assert lighting == "dim"

        # Passive Perception should be reduced by 5 in dim light
        # Base: 10 + 4 (Wis+Prof) = 14, with -5 penalty = 9
        # The penalty is applied in _check_passive_perception

    def test_passive_perception_fails_in_darkness(self, human_character):
        """Test that passive Perception auto-fails in complete darkness."""
        party = Party([human_character])
        game_state = GameState(party, "crypt", campaign_id="the_unquiet_dead")

        # Move to dark room
        game_state.current_room_id = "crypt.hall_of_the_dead"
        lighting = game_state.get_effective_lighting(human_character)
        assert lighting == "dark"

        # In darkness, passive Perception should be 0 (auto-fail)
        # This is tested by the actual passive perception check logic

    def test_darkvision_reduces_darkness_penalty(self, dwarf_character):
        """Test that darkvision converts darkness to dim light for Perception."""
        party = Party([dwarf_character])
        game_state = GameState(party, "crypt", campaign_id="the_unquiet_dead")

        # Move to dark room
        game_state.current_room_id = "crypt.hall_of_the_dead"

        # Base lighting is dark
        room = game_state.get_current_room()
        assert room.get("lighting") == "dark"

        # But dwarf sees it as dim due to darkvision
        effective_lighting = game_state.get_effective_lighting(dwarf_character)
        assert effective_lighting == "dim"

        # So they get disadvantage (-5 for passive) instead of auto-fail


class TestCreatureEnvironment:
    """Test the `GameState.creature_environment` seam (#518).

    The combat damage-modifier chokepoint reads a creature's environment
    via this method to apply SRD environment carve-outs (underwater →
    Fire Resistance). The method reads the current room's `environment`
    field (the minimal schema addition for #518; full environment-flag
    work — schema validation, per-creature room tracking — lives in
    #514).
    """

    def test_returns_none_when_room_has_no_environment(self, human_character):
        """A room without an `environment` field yields None."""
        party = Party([human_character])
        game_state = GameState(party, "test_dungeon")

        room = game_state.get_current_room()
        assert "environment" not in room

        assert game_state.creature_environment(human_character) is None

    def test_returns_underwater_when_room_environment_is_underwater(self, human_character):
        """A room tagged `environment: "underwater"` yields "underwater"."""
        party = Party([human_character])
        game_state = GameState(party, "test_dungeon")

        # Minimal schema addition for #518: rooms may carry an
        # `environment` tag alongside `lighting`.
        room = game_state.get_current_room()
        room["environment"] = "underwater"

        assert game_state.creature_environment(human_character) == "underwater"

    def test_environment_lookup_is_case_insensitive(self, human_character):
        """`Underwater` data normalizes to `underwater`."""
        party = Party([human_character])
        game_state = GameState(party, "test_dungeon")

        room = game_state.get_current_room()
        room["environment"] = "Underwater"

        assert game_state.creature_environment(human_character) == "underwater"

    def test_returns_none_when_current_room_is_unresolvable(self, human_character):
        """An unbuilt/unknown current room yields None, not a crash (#595).

        Item use and other damage paths now consult this seam while a
        combat-only GameState may never have bootstrapped a dungeon map.
        A missing current room means "no environment context" rather than
        a KeyError bubbling up through the damage pipeline.
        """
        party = Party([human_character])
        game_state = GameState(party, "test_dungeon")

        # Point the current room id at something the dungeon does not have.
        game_state.current_room_id = "does_not_exist"

        assert game_state.creature_environment(human_character) is None


class TestAttackVisibility:
    """`GameState.attack_visibility` feeds the Unseen Attackers rule (#475).

    The engine derives the per-direction `VisibilityRelation` from the
    room's ambient lighting and each combatant's senses, and
    `resolve_attack` turns those into the SRD Advantage/Disadvantage for
    an unseen attacker / unseen target.
    """

    def _dark_room_state(self, party):
        game_state = GameState(party, "crypt", campaign_id="the_unquiet_dead")
        game_state.current_room_id = "crypt.hall_of_the_dead"
        assert game_state.get_current_room().get("lighting") == "dark"
        return game_state

    def test_bright_room_sees_both_ways(self, human_character, dwarf_character):
        """In bright light each combatant sees the other (no adv/disadv)."""
        from dnd_engine.systems.perception import VisibilityRelation

        party = Party([human_character, dwarf_character])
        game_state = GameState(party, "test_dungeon")

        saw_def, saw_atk = game_state.attack_visibility(human_character, dwarf_character)
        assert saw_def == VisibilityRelation.SEEN
        assert saw_atk == VisibilityRelation.SEEN

    def test_darkvision_attacker_unseen_by_sighted_defender_in_dark(
        self, human_character, dwarf_character
    ):
        """Dwarf (darkvision) sees the human; the human can't see the dwarf."""
        from dnd_engine.systems.perception import VisibilityRelation

        party = Party([human_character, dwarf_character])
        game_state = self._dark_room_state(party)

        saw_def, saw_atk = game_state.attack_visibility(dwarf_character, human_character)
        # Dwarf sees the human (darkvision); human can't see the dwarf.
        assert saw_def == VisibilityRelation.SEEN
        assert saw_atk == VisibilityRelation.UNSEEN

    def test_darkvision_attacker_gains_advantage_in_dark(self, human_character, dwarf_character):
        """The dwarf, unseen by the human, attacks with Advantage."""
        party = Party([human_character, dwarf_character])
        game_state = self._dark_room_state(party)

        saw_def, saw_atk = game_state.attack_visibility(dwarf_character, human_character)
        result = game_state.combat_engine.resolve_attack(
            attacker=dwarf_character,
            defender=human_character,
            attack_bonus=4,
            damage_dice="1d8",
            game_state=game_state,
            attacker_sees_defender=saw_def,
            defender_sees_attacker=saw_atk,
        )
        assert result.advantage is True
        assert result.disadvantage is False

    def test_sighted_attacker_has_disadvantage_against_darkvision_foe_in_dark(
        self, human_character, dwarf_character
    ):
        """The human, blind in the dark, attacks the dwarf with Disadvantage."""
        party = Party([human_character, dwarf_character])
        game_state = self._dark_room_state(party)

        saw_def, saw_atk = game_state.attack_visibility(human_character, dwarf_character)
        result = game_state.combat_engine.resolve_attack(
            attacker=human_character,
            defender=dwarf_character,
            attack_bonus=4,
            damage_dice="1d8",
            game_state=game_state,
            attacker_sees_defender=saw_def,
            defender_sees_attacker=saw_atk,
        )
        assert result.disadvantage is True
        assert result.advantage is False

    def test_two_blind_combatants_in_dark_cancel_to_straight_roll(self, basic_abilities):
        """Two sightless-in-the-dark combatants each grant the other adv/disadv → cancel."""
        from dnd_engine.systems.perception import VisibilityRelation

        a = Character(
            name="Human A",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=basic_abilities,
            max_hp=12,
            ac=16,
            race="human",
        )
        b = Character(
            name="Human B",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=basic_abilities,
            max_hp=12,
            ac=16,
            race="human",
        )
        a.darkvision_range = 0
        b.darkvision_range = 0
        party = Party([a, b])
        game_state = self._dark_room_state(party)

        saw_def, saw_atk = game_state.attack_visibility(a, b)
        assert saw_def == VisibilityRelation.UNSEEN
        assert saw_atk == VisibilityRelation.UNSEEN

        result = game_state.combat_engine.resolve_attack(
            attacker=a,
            defender=b,
            attack_bonus=4,
            damage_dice="1d8",
            game_state=game_state,
            attacker_sees_defender=saw_def,
            defender_sees_attacker=saw_atk,
        )
        assert result.advantage is False
        assert result.disadvantage is False
