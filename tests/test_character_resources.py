# ABOUTME: Unit tests for Character resource pool integration
# ABOUTME: Tests adding, using, and retrieving resource pools from characters

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.systems.resources import ResourcePool


class TestCharacterResourcePoolIntegration:
    """Test Character class resource pool functionality"""

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
            ac=16
        )

    def test_character_has_empty_resource_pools_on_creation(self, sample_character):
        """Test that character starts with empty resource pools"""
        assert sample_character.resource_pools == {}

    def test_add_single_resource_pool(self, sample_character):
        """Test adding a single resource pool to character"""
        pool = ResourcePool(
            name="second_wind",
            current=1,
            maximum=1,
            recovery_type="short_rest"
        )
        sample_character.add_resource_pool(pool)

        assert "second_wind" in sample_character.resource_pools
        assert sample_character.resource_pools["second_wind"] == pool

    def test_add_multiple_resource_pools(self, sample_character):
        """Test adding multiple resource pools to character"""
        pool1 = ResourcePool(
            name="second_wind",
            current=1,
            maximum=1,
            recovery_type="short_rest"
        )
        pool2 = ResourcePool(
            name="action_surge",
            current=1,
            maximum=1,
            recovery_type="short_rest"
        )

        sample_character.add_resource_pool(pool1)
        sample_character.add_resource_pool(pool2)

        assert len(sample_character.resource_pools) == 2
        assert "second_wind" in sample_character.resource_pools
        assert "action_surge" in sample_character.resource_pools

    def test_add_resource_pool_overwrites_existing(self, sample_character):
        """Test that adding a pool with same name overwrites the old one"""
        pool1 = ResourcePool(
            name="action_surge",
            current=1,
            maximum=1,
            recovery_type="short_rest"
        )
        pool2 = ResourcePool(
            name="action_surge",
            current=2,
            maximum=2,
            recovery_type="short_rest"
        )

        sample_character.add_resource_pool(pool1)
        sample_character.add_resource_pool(pool2)

        assert len(sample_character.resource_pools) == 1
        assert sample_character.resource_pools["action_surge"].maximum == 2

    def test_get_resource_pool_existing(self, sample_character):
        """Test getting an existing resource pool"""
        pool = ResourcePool(
            name="second_wind",
            current=1,
            maximum=1,
            recovery_type="short_rest"
        )
        sample_character.add_resource_pool(pool)

        retrieved = sample_character.get_resource_pool("second_wind")
        assert retrieved is pool
        assert retrieved.name == "second_wind"

    def test_get_resource_pool_nonexistent(self, sample_character):
        """Test getting a non-existent resource pool"""
        retrieved = sample_character.get_resource_pool("nonexistent")
        assert retrieved is None

    def test_use_resource_successful(self, sample_character):
        """Test using a resource that exists and has available uses"""
        pool = ResourcePool(
            name="second_wind",
            current=1,
            maximum=1,
            recovery_type="short_rest"
        )
        sample_character.add_resource_pool(pool)

        result = sample_character.use_resource("second_wind")
        assert result is True
        assert sample_character.resource_pools["second_wind"].current == 0

    def test_use_resource_insufficient(self, sample_character):
        """Test using a resource that doesn't have enough uses"""
        pool = ResourcePool(
            name="second_wind",
            current=0,
            maximum=1,
            recovery_type="short_rest"
        )
        sample_character.add_resource_pool(pool)

        result = sample_character.use_resource("second_wind")
        assert result is False
        assert sample_character.resource_pools["second_wind"].current == 0

    def test_use_resource_nonexistent(self, sample_character):
        """Test using a resource that doesn't exist"""
        result = sample_character.use_resource("nonexistent")
        assert result is False

    def test_use_resource_multiple_amounts(self, sample_character):
        """Test using multiple amounts from a resource"""
        pool = ResourcePool(
            name="ki_points",
            current=5,
            maximum=5,
            recovery_type="short_rest"
        )
        sample_character.add_resource_pool(pool)

        result = sample_character.use_resource("ki_points", 3)
        assert result is True
        assert sample_character.resource_pools["ki_points"].current == 2

    def test_character_with_multiple_pools_use_different_pools(self, sample_character):
        """Test using resources from different pools doesn't affect others"""
        pool1 = ResourcePool(
            name="second_wind",
            current=1,
            maximum=1,
            recovery_type="short_rest"
        )
        pool2 = ResourcePool(
            name="action_surge",
            current=1,
            maximum=1,
            recovery_type="short_rest"
        )

        sample_character.add_resource_pool(pool1)
        sample_character.add_resource_pool(pool2)

        # Use one pool
        sample_character.use_resource("second_wind")

        # Verify only that pool was affected
        assert sample_character.resource_pools["second_wind"].current == 0
        assert sample_character.resource_pools["action_surge"].current == 1


class TestCharacterFactoryResourceInitialization:
    """Test CharacterFactory resource initialization"""

    @pytest.fixture
    def class_data(self):
        """Sample Fighter class data with resources"""
        return {
            "name": "Fighter",
            "hit_die": "1d10",
            "features_by_level": {
                "1": [
                    {
                        "name": "Second Wind",
                        "description": "Once per short rest...",
                        "resource": {
                            "pool": "second_wind",
                            "max_uses": 1,
                            "recovery": "short_rest"
                        }
                    }
                ],
                "2": [
                    {
                        "name": "Action Surge",
                        "description": "Once per short rest...",
                        "resource": {
                            "pool": "action_surge",
                            "max_uses": 1,
                            "recovery": "short_rest"
                        }
                    }
                ]
            }
        }

    @pytest.fixture
    def sample_character(self):
        """Create a character for factory testing"""
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
            ac=16
        )

    def test_initialize_resources_level_1_fighter(self, sample_character, class_data):
        """Test initializing resources for level 1 Fighter"""
        from dnd_engine.core.character_factory import CharacterFactory

        CharacterFactory.initialize_class_resources(sample_character, class_data, 1)

        assert len(sample_character.resource_pools) == 1
        assert "second_wind" in sample_character.resource_pools
        assert sample_character.resource_pools["second_wind"].current == 1
        assert sample_character.resource_pools["second_wind"].maximum == 1
        assert sample_character.resource_pools["second_wind"].recovery_type == "short_rest"

    def test_initialize_resources_level_2_fighter(self, sample_character, class_data):
        """Test initializing resources for level 2 Fighter"""
        from dnd_engine.core.character_factory import CharacterFactory

        CharacterFactory.initialize_class_resources(sample_character, class_data, 2)

        assert len(sample_character.resource_pools) == 2
        assert "second_wind" in sample_character.resource_pools
        assert "action_surge" in sample_character.resource_pools
        assert sample_character.resource_pools["action_surge"].current == 1

    def test_initialize_resources_with_duplicate_pools(self, sample_character):
        """Test that duplicate pool names don't create multiple pools"""
        class_data = {
            "features_by_level": {
                "1": [
                    {
                        "name": "Feature 1",
                        "resource": {
                            "pool": "shared_pool",
                            "max_uses": 1,
                            "recovery": "short_rest"
                        }
                    },
                    {
                        "name": "Feature 2",
                        "resource": {
                            "pool": "shared_pool",
                            "max_uses": 1,
                            "recovery": "short_rest"
                        }
                    }
                ]
            }
        }

        from dnd_engine.core.character_factory import CharacterFactory

        CharacterFactory.initialize_class_resources(sample_character, class_data, 1)

        # Should only have one pool despite two features
        assert len(sample_character.resource_pools) == 1
        assert "shared_pool" in sample_character.resource_pools

    def test_initialize_resources_no_resources_defined(self, sample_character):
        """Test initializing when class has no resources defined"""
        class_data = {
            "features_by_level": {
                "1": [
                    {
                        "name": "Feature without resource",
                        "description": "No resource pool"
                    }
                ]
            }
        }

        from dnd_engine.core.character_factory import CharacterFactory

        CharacterFactory.initialize_class_resources(sample_character, class_data, 1)

        assert len(sample_character.resource_pools) == 0

    def test_initialize_resources_empty_class_data(self, sample_character):
        """Test initializing with empty class data"""
        class_data = {}

        from dnd_engine.core.character_factory import CharacterFactory

        CharacterFactory.initialize_class_resources(sample_character, class_data, 1)

        assert len(sample_character.resource_pools) == 0

    def test_fighter_gets_second_wind_at_level_1(self, sample_character, class_data):
        """Test that Fighter gets Second Wind resource at level 1"""
        from dnd_engine.core.character_factory import CharacterFactory

        CharacterFactory.initialize_class_resources(sample_character, class_data, 1)

        second_wind = sample_character.get_resource_pool("second_wind")
        assert second_wind is not None
        assert second_wind.name == "second_wind"
        assert second_wind.current == 1
        assert second_wind.maximum == 1
        assert second_wind.recovery_type == "short_rest"

    def test_fighter_gets_action_surge_at_level_2(self, sample_character, class_data):
        """Test that Fighter gets Action Surge resource at level 2"""
        from dnd_engine.core.character_factory import CharacterFactory

        CharacterFactory.initialize_class_resources(sample_character, class_data, 2)

        action_surge = sample_character.get_resource_pool("action_surge")
        assert action_surge is not None
        assert action_surge.name == "action_surge"
        assert action_surge.current == 1
        assert action_surge.maximum == 1
        assert action_surge.recovery_type == "short_rest"
