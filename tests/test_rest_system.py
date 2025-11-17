# ABOUTME: Unit tests for rest system (short rest and long rest)
# ABOUTME: Tests HP recovery, resource pool recovery, and rest mechanics

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.systems.resources import ResourcePool


class TestRecoverHP:
    """Test HP recovery functionality"""

    @pytest.fixture
    def sample_character(self):
        """Create a sample character for testing"""
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        return Character(
            name="Test Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16,
            current_hp=5  # Start damaged
        )

    def test_recover_hp_partial(self, sample_character):
        """Test recovering a specific amount of HP"""
        healed = sample_character.recover_hp(3)
        assert healed == 3
        assert sample_character.current_hp == 8

    def test_recover_hp_full(self, sample_character):
        """Test full HP recovery (None parameter)"""
        healed = sample_character.recover_hp()
        assert healed == 7  # Was at 5/12, should heal 7
        assert sample_character.current_hp == 12
        assert sample_character.current_hp == sample_character.max_hp

    def test_recover_hp_already_full(self):
        """Test recovering HP when already at max"""
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        character = Character(
            name="Healthy Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16,
            current_hp=12  # Already at max
        )
        healed = character.recover_hp()
        assert healed == 0
        assert character.current_hp == 12

    def test_recover_hp_cannot_exceed_max(self, sample_character):
        """Test that HP cannot exceed max_hp"""
        healed = sample_character.recover_hp(100)  # Try to heal way more than needed
        assert healed == 7  # Only heals to max
        assert sample_character.current_hp == 12
        assert sample_character.current_hp == sample_character.max_hp

    def test_recover_hp_zero_amount(self, sample_character):
        """Test recovering 0 HP"""
        healed = sample_character.recover_hp(0)
        assert healed == 0
        assert sample_character.current_hp == 5  # Unchanged


class TestRecoverResources:
    """Test resource pool recovery based on rest type"""

    @pytest.fixture
    def character_with_resources(self):
        """Create a character with various resource pools"""
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        character = Character(
            name="Test Fighter",
            character_class=CharacterClass.FIGHTER,
            level=2,
            abilities=abilities,
            max_hp=20,
            ac=16
        )

        # Add short rest recovery pool
        second_wind = ResourcePool(
            name="second_wind",
            current=0,  # Used up
            maximum=1,
            recovery_type="short_rest"
        )
        character.add_resource_pool(second_wind)

        # Add another short rest recovery pool
        action_surge = ResourcePool(
            name="action_surge",
            current=0,  # Used up
            maximum=1,
            recovery_type="short_rest"
        )
        character.add_resource_pool(action_surge)

        # Add long rest recovery pool
        spell_slots = ResourcePool(
            name="spell_slots",
            current=0,  # Used up
            maximum=2,
            recovery_type="long_rest"
        )
        character.add_resource_pool(spell_slots)

        # Add permanent pool (should never recover)
        permanent_ability = ResourcePool(
            name="permanent_ability",
            current=0,  # Used up
            maximum=1,
            recovery_type="permanent"
        )
        character.add_resource_pool(permanent_ability)

        return character

    def test_short_rest_recovers_short_rest_resources(self, character_with_resources):
        """Test that short rest only recovers short_rest resources"""
        recovered = character_with_resources.recover_resources("short_rest")

        assert "second_wind" in recovered
        assert "action_surge" in recovered
        assert "spell_slots" not in recovered
        assert "permanent_ability" not in recovered

        # Verify resources are actually recovered
        assert character_with_resources.resource_pools["second_wind"].current == 1
        assert character_with_resources.resource_pools["action_surge"].current == 1
        assert character_with_resources.resource_pools["spell_slots"].current == 0
        assert character_with_resources.resource_pools["permanent_ability"].current == 0

    def test_long_rest_recovers_short_and_long_rest_resources(self, character_with_resources):
        """Test that long rest recovers both short_rest and long_rest resources"""
        recovered = character_with_resources.recover_resources("long_rest")

        assert "second_wind" in recovered
        assert "action_surge" in recovered
        assert "spell_slots" in recovered
        assert "permanent_ability" not in recovered

        # Verify resources are actually recovered
        assert character_with_resources.resource_pools["second_wind"].current == 1
        assert character_with_resources.resource_pools["action_surge"].current == 1
        assert character_with_resources.resource_pools["spell_slots"].current == 2
        assert character_with_resources.resource_pools["permanent_ability"].current == 0

    def test_recover_resources_empty_pools(self):
        """Test recovering resources when character has no pools"""
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        character = Character(
            name="No Resources",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16
        )

        recovered = character.recover_resources("short_rest")
        assert recovered == []

        recovered = character.recover_resources("long_rest")
        assert recovered == []

    def test_recover_resources_already_full(self):
        """Test recovering resources when pools are already full"""
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        character = Character(
            name="Full Resources",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16
        )

        # Add pool that's already full
        second_wind = ResourcePool(
            name="second_wind",
            current=1,  # Already full
            maximum=1,
            recovery_type="short_rest"
        )
        character.add_resource_pool(second_wind)

        recovered = character.recover_resources("short_rest")
        assert "second_wind" in recovered  # Still in list
        assert character.resource_pools["second_wind"].current == 1


class TestShortRest:
    """Test short rest functionality"""

    @pytest.fixture
    def character_with_short_rest_resources(self):
        """Create a character with short rest resources"""
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        character = Character(
            name="Test Fighter",
            character_class=CharacterClass.FIGHTER,
            level=2,
            abilities=abilities,
            max_hp=20,
            ac=16,
            current_hp=10  # Damaged
        )

        # Add short rest resources
        second_wind = ResourcePool(
            name="second_wind",
            current=0,
            maximum=1,
            recovery_type="short_rest"
        )
        character.add_resource_pool(second_wind)

        action_surge = ResourcePool(
            name="action_surge",
            current=0,
            maximum=1,
            recovery_type="short_rest"
        )
        character.add_resource_pool(action_surge)

        # Add long rest resource (should NOT recover)
        spell_slots = ResourcePool(
            name="spell_slots",
            current=0,
            maximum=2,
            recovery_type="long_rest"
        )
        character.add_resource_pool(spell_slots)

        return character

    def test_take_short_rest_returns_correct_data(self, character_with_short_rest_resources):
        """Test that take_short_rest returns expected result dictionary"""
        result = character_with_short_rest_resources.take_short_rest()

        assert result["character"] == "Test Fighter"
        assert result["rest_type"] == "short"
        assert "second_wind" in result["resources_recovered"]
        assert "action_surge" in result["resources_recovered"]
        assert "spell_slots" not in result["resources_recovered"]
        assert result["hp_recovered"] == 0  # No Hit Dice healing in MVP

    def test_short_rest_recovers_short_rest_resources_only(self, character_with_short_rest_resources):
        """Test that short rest only recovers short_rest type resources"""
        character_with_short_rest_resources.take_short_rest()

        # Short rest resources should be recovered
        assert character_with_short_rest_resources.resource_pools["second_wind"].current == 1
        assert character_with_short_rest_resources.resource_pools["action_surge"].current == 1

        # Long rest resources should NOT be recovered
        assert character_with_short_rest_resources.resource_pools["spell_slots"].current == 0

    def test_short_rest_does_not_heal_hp(self, character_with_short_rest_resources):
        """Test that short rest does not heal HP (Hit Dice not implemented)"""
        initial_hp = character_with_short_rest_resources.current_hp
        result = character_with_short_rest_resources.take_short_rest()

        assert character_with_short_rest_resources.current_hp == initial_hp
        assert result["hp_recovered"] == 0


class TestLongRest:
    """Test long rest functionality"""

    @pytest.fixture
    def character_for_long_rest(self):
        """Create a character for long rest testing"""
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        character = Character(
            name="Test Fighter",
            character_class=CharacterClass.FIGHTER,
            level=2,
            abilities=abilities,
            max_hp=20,
            ac=16,
            current_hp=5  # Heavily damaged
        )

        # Add short rest resources
        second_wind = ResourcePool(
            name="second_wind",
            current=0,
            maximum=1,
            recovery_type="short_rest"
        )
        character.add_resource_pool(second_wind)

        # Add long rest resource
        spell_slots = ResourcePool(
            name="spell_slots",
            current=0,
            maximum=3,
            recovery_type="long_rest"
        )
        character.add_resource_pool(spell_slots)

        # Add permanent resource (should never recover)
        permanent = ResourcePool(
            name="permanent_ability",
            current=0,
            maximum=1,
            recovery_type="permanent"
        )
        character.add_resource_pool(permanent)

        return character

    def test_take_long_rest_returns_correct_data(self, character_for_long_rest):
        """Test that take_long_rest returns expected result dictionary"""
        result = character_for_long_rest.take_long_rest()

        assert result["character"] == "Test Fighter"
        assert result["rest_type"] == "long"
        assert result["hp_recovered"] == 15  # From 5 to 20
        assert "second_wind" in result["resources_recovered"]
        assert "spell_slots" in result["resources_recovered"]
        assert "permanent_ability" not in result["resources_recovered"]
        assert result["conditions_removed"] == []  # Future feature

    def test_long_rest_recovers_all_hp(self, character_for_long_rest):
        """Test that long rest fully recovers HP"""
        character_for_long_rest.take_long_rest()

        assert character_for_long_rest.current_hp == character_for_long_rest.max_hp
        assert character_for_long_rest.current_hp == 20

    def test_long_rest_recovers_short_and_long_rest_resources(self, character_for_long_rest):
        """Test that long rest recovers both short_rest and long_rest resources"""
        character_for_long_rest.take_long_rest()

        # Both short rest and long rest resources should be recovered
        assert character_for_long_rest.resource_pools["second_wind"].current == 1
        assert character_for_long_rest.resource_pools["spell_slots"].current == 3

        # Permanent resources should NOT be recovered
        assert character_for_long_rest.resource_pools["permanent_ability"].current == 0

    def test_long_rest_when_already_full_health(self):
        """Test long rest when character is already at full HP"""
        abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        character = Character(
            name="Healthy Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16,
            current_hp=12  # Already full
        )

        result = character.take_long_rest()

        assert result["hp_recovered"] == 0
        assert character.current_hp == 12

    def test_long_rest_multiple_times(self, character_for_long_rest):
        """Test taking multiple long rests (resources stay at max)"""
        # First long rest
        character_for_long_rest.take_long_rest()
        assert character_for_long_rest.current_hp == 20
        assert character_for_long_rest.resource_pools["spell_slots"].current == 3

        # Use some resources
        character_for_long_rest.current_hp = 10
        character_for_long_rest.resource_pools["spell_slots"].use(2)
        assert character_for_long_rest.resource_pools["spell_slots"].current == 1

        # Second long rest
        result = character_for_long_rest.take_long_rest()
        assert character_for_long_rest.current_hp == 20
        assert character_for_long_rest.resource_pools["spell_slots"].current == 3
        assert result["hp_recovered"] == 10
