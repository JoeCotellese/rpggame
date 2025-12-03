# ABOUTME: Unit tests for Character.prepare_for_new_campaign() method
# ABOUTME: Tests HP restoration, resource pool recovery, condition clearing, and quest item removal

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.systems.resources import ResourcePool


class TestPrepareForNewCampaign:
    """Test Character.prepare_for_new_campaign() functionality."""

    @pytest.fixture
    def sample_character(self):
        """Create a sample character for testing."""
        abilities = Abilities(
            strength=16, dexterity=14, constitution=15, intelligence=8, wisdom=10, charisma=12
        )

        return Character(
            name="Test Warrior",
            character_class=CharacterClass.FIGHTER,
            level=5,
            abilities=abilities,
            max_hp=45,
            ac=18,
            current_hp=45,
            xp=6500,
            race="Dwarf",
        )

    def test_restores_hp_to_max(self, sample_character):
        """Test that prepare_for_new_campaign restores HP to max."""
        sample_character.current_hp = 10  # Damaged

        sample_character.prepare_for_new_campaign()

        assert sample_character.current_hp == sample_character.max_hp
        assert sample_character.current_hp == 45

    def test_restores_resource_pools(self, sample_character):
        """Test that prepare_for_new_campaign restores all resource pools."""
        # Add some resource pools
        second_wind = ResourcePool(
            name="second_wind",
            current=0,  # Used
            maximum=1,
            recovery_type="short_rest",
        )
        action_surge = ResourcePool(
            name="action_surge",
            current=0,  # Used
            maximum=2,
            recovery_type="short_rest",
        )

        sample_character.add_resource_pool(second_wind)
        sample_character.add_resource_pool(action_surge)

        sample_character.prepare_for_new_campaign()

        assert sample_character.resource_pools["second_wind"].current == 1
        assert sample_character.resource_pools["action_surge"].current == 2

    def test_clears_conditions(self, sample_character):
        """Test that prepare_for_new_campaign clears all conditions."""
        sample_character.add_condition("poisoned")
        sample_character.add_condition("frightened")
        sample_character.add_condition("exhaustion")

        removed = sample_character.prepare_for_new_campaign()

        assert len(sample_character.conditions) == 0
        assert "poisoned" in removed["conditions"]
        assert "frightened" in removed["conditions"]
        assert "exhaustion" in removed["conditions"]

    def test_resets_death_saves(self, sample_character):
        """Test that prepare_for_new_campaign resets death saving throws."""
        sample_character.death_save_successes = 2
        sample_character.death_save_failures = 1
        sample_character.stabilized = True

        sample_character.prepare_for_new_campaign()

        assert sample_character.death_save_successes == 0
        assert sample_character.death_save_failures == 0
        assert sample_character.stabilized is False

    def test_removes_quest_items(self, sample_character):
        """Test that prepare_for_new_campaign removes quest items."""
        # Add regular item and quest item
        sample_character.inventory.add_item("longsword", "weapons", 1)
        sample_character.inventory.add_item("ancient_key", "consumables", 1, quest_item=True)
        sample_character.inventory.add_item("magic_orb", "consumables", 1, quest_item=True)

        removed = sample_character.prepare_for_new_campaign()

        # Regular item should remain
        assert sample_character.inventory.has_item("longsword")

        # Quest items should be gone
        assert not sample_character.inventory.has_item("ancient_key")
        assert not sample_character.inventory.has_item("magic_orb")

        # Check return value
        assert "ancient_key" in removed["quest_items"]
        assert "magic_orb" in removed["quest_items"]

    def test_preserves_xp_and_level(self, sample_character):
        """Test that XP and level are preserved."""
        original_xp = sample_character.xp
        original_level = sample_character.level

        sample_character.prepare_for_new_campaign()

        assert sample_character.xp == original_xp
        assert sample_character.level == original_level

    def test_preserves_gold(self, sample_character):
        """Test that gold is preserved."""
        sample_character.inventory.add_gold(500)

        sample_character.prepare_for_new_campaign()

        assert sample_character.inventory.gold == 500

    def test_preserves_permanent_items(self, sample_character):
        """Test that non-quest items are preserved."""
        sample_character.inventory.add_item("longsword", "weapons", 1)
        sample_character.inventory.add_item("chain_mail", "armor", 1)
        sample_character.inventory.add_item("potion_of_healing", "consumables", 3)

        sample_character.prepare_for_new_campaign()

        assert sample_character.inventory.has_item("longsword")
        assert sample_character.inventory.has_item("chain_mail")
        assert sample_character.inventory.has_item("potion_of_healing")
        assert sample_character.inventory.get_item_quantity("potion_of_healing") == 3

    def test_returns_removed_items_report(self, sample_character):
        """Test that method returns dictionary with removed items."""
        sample_character.add_condition("poisoned")
        sample_character.inventory.add_item("quest_gem", "consumables", 1, quest_item=True)

        removed = sample_character.prepare_for_new_campaign()

        assert isinstance(removed, dict)
        assert "quest_items" in removed
        assert "conditions" in removed
        assert "quest_gem" in removed["quest_items"]
        assert "poisoned" in removed["conditions"]

    def test_returns_empty_report_when_nothing_to_remove(self, sample_character):
        """Test return value when character has no conditions or quest items."""
        removed = sample_character.prepare_for_new_campaign()

        assert removed["quest_items"] == []
        assert removed["conditions"] == []

    def test_handles_equipped_quest_item_removal(self, sample_character):
        """Test that equipped quest items are properly unequipped and removed."""
        from dnd_engine.systems.inventory import EquipmentSlot

        # Add and equip a quest weapon
        sample_character.inventory.add_item("cursed_blade", "weapons", 1, quest_item=True)
        sample_character.inventory.equip_item("cursed_blade", EquipmentSlot.WEAPON)

        # Verify it's equipped
        assert sample_character.inventory.get_equipped_item(EquipmentSlot.WEAPON) == "cursed_blade"

        sample_character.prepare_for_new_campaign()

        # Quest item should be gone and slot empty
        assert not sample_character.inventory.has_item("cursed_blade")
        assert sample_character.inventory.get_equipped_item(EquipmentSlot.WEAPON) is None

    def test_full_scenario_damaged_exhausted_character(self, sample_character):
        """Test complete scenario with damaged, exhausted character with quest items."""
        # Damage character
        sample_character.current_hp = 5

        # Add conditions
        sample_character.add_condition("exhaustion")
        sample_character.add_condition("poisoned")

        # Use resources
        sample_character.add_resource_pool(
            ResourcePool("second_wind", current=0, maximum=1, recovery_type="short_rest")
        )

        # Add inventory
        sample_character.inventory.add_gold(1000)
        sample_character.inventory.add_item("longsword", "weapons", 1)
        sample_character.inventory.add_item("macguffin", "consumables", 1, quest_item=True)

        # Set death saves (from a close call)
        sample_character.death_save_successes = 3
        sample_character.stabilized = True

        # Prepare for new campaign
        removed = sample_character.prepare_for_new_campaign()

        # Verify full restoration
        assert sample_character.current_hp == 45
        assert len(sample_character.conditions) == 0
        assert sample_character.resource_pools["second_wind"].current == 1
        assert sample_character.death_save_successes == 0
        assert sample_character.stabilized is False

        # Verify items
        assert sample_character.inventory.gold == 1000
        assert sample_character.inventory.has_item("longsword")
        assert not sample_character.inventory.has_item("macguffin")

        # Verify report
        assert "macguffin" in removed["quest_items"]
        assert "exhaustion" in removed["conditions"]
        assert "poisoned" in removed["conditions"]
