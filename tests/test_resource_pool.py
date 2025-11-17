# ABOUTME: Unit tests for ResourcePool class
# ABOUTME: Tests resource usage, recovery, and state checking mechanics

import pytest
from dnd_engine.systems.resources import ResourcePool


class TestResourcePoolBasics:
    """Test basic ResourcePool initialization and properties"""

    def test_resource_pool_creation(self):
        """Test creating a resource pool"""
        pool = ResourcePool(
            name="action_surge",
            current=1,
            maximum=1,
            recovery_type="short_rest"
        )
        assert pool.name == "action_surge"
        assert pool.current == 1
        assert pool.maximum == 1
        assert pool.recovery_type == "short_rest"

    def test_resource_pool_string_representation(self):
        """Test string representation of resource pool"""
        pool = ResourcePool(
            name="second_wind",
            current=1,
            maximum=1,
            recovery_type="short_rest"
        )
        assert str(pool) == "second_wind: 1/1"

    def test_resource_pool_with_different_current_and_max(self):
        """Test resource pool with current less than maximum"""
        pool = ResourcePool(
            name="ki_points",
            current=2,
            maximum=5,
            recovery_type="long_rest"
        )
        assert pool.current == 2
        assert pool.maximum == 5
        assert str(pool) == "ki_points: 2/5"


class TestResourcePoolUsage:
    """Test resource usage mechanics"""

    def test_use_single_resource(self):
        """Test using a single resource"""
        pool = ResourcePool(
            name="spell_slots",
            current=2,
            maximum=2,
            recovery_type="long_rest"
        )
        assert pool.use() is True
        assert pool.current == 1

    def test_use_multiple_resources(self):
        """Test using multiple resources at once"""
        pool = ResourcePool(
            name="ki_points",
            current=5,
            maximum=5,
            recovery_type="short_rest"
        )
        assert pool.use(3) is True
        assert pool.current == 2

    def test_use_exact_remaining(self):
        """Test using exactly the remaining resources"""
        pool = ResourcePool(
            name="resources",
            current=3,
            maximum=5,
            recovery_type="daily"
        )
        assert pool.use(3) is True
        assert pool.current == 0

    def test_use_insufficient_resources_returns_false(self):
        """Test that use returns False when insufficient resources"""
        pool = ResourcePool(
            name="resources",
            current=2,
            maximum=5,
            recovery_type="short_rest"
        )
        assert pool.use(3) is False
        assert pool.current == 2  # Current should not change

    def test_use_from_empty_pool(self):
        """Test using resources from empty pool"""
        pool = ResourcePool(
            name="empty_pool",
            current=0,
            maximum=3,
            recovery_type="short_rest"
        )
        assert pool.use() is False
        assert pool.current == 0

    def test_use_zero_amount(self):
        """Test using zero resources"""
        pool = ResourcePool(
            name="resources",
            current=5,
            maximum=5,
            recovery_type="short_rest"
        )
        assert pool.use(0) is False  # Using 0 should fail
        assert pool.current == 5

    def test_use_negative_amount(self):
        """Test using negative resources (should fail)"""
        pool = ResourcePool(
            name="resources",
            current=5,
            maximum=5,
            recovery_type="short_rest"
        )
        assert pool.use(-1) is False
        assert pool.current == 5


class TestResourcePoolRecovery:
    """Test resource recovery mechanics"""

    def test_recover_partial_amount(self):
        """Test recovering a partial amount"""
        pool = ResourcePool(
            name="second_wind",
            current=0,
            maximum=1,
            recovery_type="short_rest"
        )
        recovered = pool.recover(1)
        assert recovered == 1
        assert pool.current == 1

    def test_recover_all_resources(self):
        """Test recovering all resources with None"""
        pool = ResourcePool(
            name="action_surge",
            current=0,
            maximum=1,
            recovery_type="short_rest"
        )
        recovered = pool.recover(None)
        assert recovered == 1
        assert pool.current == 1

    def test_recover_more_than_max(self):
        """Test recovering more resources than maximum"""
        pool = ResourcePool(
            name="resources",
            current=1,
            maximum=5,
            recovery_type="long_rest"
        )
        recovered = pool.recover(10)
        assert recovered == 4  # Should only recover up to max
        assert pool.current == 5

    def test_recover_when_full(self):
        """Test recovering when already at maximum"""
        pool = ResourcePool(
            name="resources",
            current=5,
            maximum=5,
            recovery_type="short_rest"
        )
        recovered = pool.recover(3)
        assert recovered == 0  # Can't recover any
        assert pool.current == 5

    def test_recover_zero_amount(self):
        """Test recovering zero resources"""
        pool = ResourcePool(
            name="resources",
            current=2,
            maximum=5,
            recovery_type="short_rest"
        )
        recovered = pool.recover(0)
        assert recovered == 0
        assert pool.current == 2

    def test_recover_all_from_depleted(self):
        """Test recovering all from depleted pool"""
        pool = ResourcePool(
            name="spell_slots",
            current=0,
            maximum=3,
            recovery_type="long_rest"
        )
        recovered = pool.recover()
        assert recovered == 3
        assert pool.current == 3

    def test_recover_partial_from_depleted(self):
        """Test recovering partial amount from depleted pool"""
        pool = ResourcePool(
            name="resources",
            current=0,
            maximum=5,
            recovery_type="short_rest"
        )
        recovered = pool.recover(2)
        assert recovered == 2
        assert pool.current == 2


class TestResourcePoolStateChecking:
    """Test resource state checking methods"""

    def test_is_available_sufficient_resources(self):
        """Test is_available with sufficient resources"""
        pool = ResourcePool(
            name="action_surge",
            current=2,
            maximum=2,
            recovery_type="short_rest"
        )
        assert pool.is_available(1) is True
        assert pool.is_available(2) is True

    def test_is_available_insufficient_resources(self):
        """Test is_available with insufficient resources"""
        pool = ResourcePool(
            name="resources",
            current=1,
            maximum=3,
            recovery_type="short_rest"
        )
        assert pool.is_available(2) is False

    def test_is_available_default_amount(self):
        """Test is_available with default amount (1)"""
        pool = ResourcePool(
            name="resources",
            current=1,
            maximum=1,
            recovery_type="short_rest"
        )
        assert pool.is_available() is True

    def test_is_empty_when_depleted(self):
        """Test is_empty when pool is depleted"""
        pool = ResourcePool(
            name="empty_pool",
            current=0,
            maximum=3,
            recovery_type="short_rest"
        )
        assert pool.is_empty() is True

    def test_is_empty_when_has_resources(self):
        """Test is_empty when pool has resources"""
        pool = ResourcePool(
            name="resources",
            current=1,
            maximum=3,
            recovery_type="short_rest"
        )
        assert pool.is_empty() is False

    def test_is_full_when_at_maximum(self):
        """Test is_full when at maximum"""
        pool = ResourcePool(
            name="action_surge",
            current=1,
            maximum=1,
            recovery_type="short_rest"
        )
        assert pool.is_full() is True

    def test_is_full_when_below_maximum(self):
        """Test is_full when below maximum"""
        pool = ResourcePool(
            name="resources",
            current=2,
            maximum=5,
            recovery_type="short_rest"
        )
        assert pool.is_full() is False


class TestResourcePoolBoundaryConditions:
    """Test boundary conditions and edge cases"""

    def test_zero_maximum_pool(self):
        """Test pool with zero maximum"""
        pool = ResourcePool(
            name="zero_pool",
            current=0,
            maximum=0,
            recovery_type="permanent"
        )
        assert pool.is_empty() is True
        assert pool.is_full() is True
        assert pool.use() is False
        assert pool.recover() == 0

    def test_large_resource_values(self):
        """Test pool with large resource values"""
        pool = ResourcePool(
            name="large_pool",
            current=1000,
            maximum=1000,
            recovery_type="permanent"
        )
        assert pool.use(500) is True
        assert pool.current == 500
        assert pool.recover(500) == 500
        assert pool.current == 1000

    def test_use_and_recover_cycle(self):
        """Test cycling through use and recover"""
        pool = ResourcePool(
            name="action_surge",
            current=1,
            maximum=1,
            recovery_type="short_rest"
        )

        # Use the resource
        assert pool.use() is True
        assert pool.is_empty() is True

        # Recover it
        pool.recover()
        assert pool.is_full() is True

        # Use again
        assert pool.use() is True
        assert pool.is_empty() is True


class TestResourcePoolDifferentRecoveryTypes:
    """Test different recovery types"""

    def test_short_rest_recovery_type(self):
        """Test short_rest recovery type"""
        pool = ResourcePool(
            name="second_wind",
            current=0,
            maximum=1,
            recovery_type="short_rest"
        )
        assert pool.recovery_type == "short_rest"

    def test_long_rest_recovery_type(self):
        """Test long_rest recovery type"""
        pool = ResourcePool(
            name="spell_slots",
            current=0,
            maximum=2,
            recovery_type="long_rest"
        )
        assert pool.recovery_type == "long_rest"

    def test_daily_recovery_type(self):
        """Test daily recovery type"""
        pool = ResourcePool(
            name="daily_ability",
            current=0,
            maximum=3,
            recovery_type="daily"
        )
        assert pool.recovery_type == "daily"

    def test_permanent_recovery_type(self):
        """Test permanent recovery type (never recovers)"""
        pool = ResourcePool(
            name="permanent_resource",
            current=5,
            maximum=5,
            recovery_type="permanent"
        )
        assert pool.recovery_type == "permanent"
