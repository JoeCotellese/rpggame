# ABOUTME: Unit tests for item assignment service.
# ABOUTME: Verifies class-item suitability matching and auto-assignment logic.

from enum import Enum

import pytest

from dnd_engine.systems.item_assignment import ItemAssignmentService, ItemRecommendation


class MockCharacterClass(Enum):
    """Mock character class enum for testing."""

    FIGHTER = "fighter"
    ROGUE = "rogue"
    WIZARD = "wizard"
    CLERIC = "cleric"


class MockCharacter:
    """Mock character for testing item assignment."""

    def __init__(
        self, name: str, character_class: MockCharacterClass, current_hp: int = 20, max_hp: int = 20
    ):
        self.name = name
        self.character_class = character_class
        self.current_hp = current_hp
        self.max_hp = max_hp


class TestItemAssignmentServiceWeapons:
    """Test cases for weapon item assignment recommendations."""

    @pytest.fixture
    def service(self):
        """Create service with mock items data."""
        items_data = {
            "weapons": {
                "longsword": {"name": "Longsword", "type": "weapon"},
                "dagger": {"name": "Dagger", "type": "weapon"},
            }
        }
        return ItemAssignmentService(items_data=items_data)

    def test_fighter_gets_high_score_for_weapons(self, service):
        """Test that fighter gets highest score for weapons."""
        party = [
            MockCharacter("Conan", MockCharacterClass.FIGHTER),
            MockCharacter("Gandalf", MockCharacterClass.WIZARD),
        ]

        recommendations = service.get_recommended_recipients("longsword", party)

        # Fighter should be first with score 1.0
        assert recommendations[0].character.name == "Conan"
        assert recommendations[0].score == 1.0
        # Wizard should have lower score
        assert recommendations[1].character.name == "Gandalf"
        assert recommendations[1].score == 0.5

    def test_all_non_martial_classes_get_equal_weapon_score(self, service):
        """Test that non-martial classes all get same weapon score."""
        party = [
            MockCharacter("Gandalf", MockCharacterClass.WIZARD),
            MockCharacter("Frodo", MockCharacterClass.ROGUE),
            MockCharacter("Brother Marcus", MockCharacterClass.CLERIC),
        ]

        recommendations = service.get_recommended_recipients("longsword", party)

        # All should have score 0.5
        for rec in recommendations:
            assert rec.score == 0.5


class TestItemAssignmentServiceArmor:
    """Test cases for armor item assignment recommendations."""

    @pytest.fixture
    def service(self):
        """Create service with mock items data."""
        items_data = {
            "armor": {
                "chainmail": {"name": "Chainmail", "type": "armor"},
                "plate": {"name": "Plate", "type": "armor"},
            }
        }
        return ItemAssignmentService(items_data=items_data)

    def test_fighter_gets_high_score_for_armor(self, service):
        """Test that fighter gets highest score for armor."""
        party = [
            MockCharacter("Conan", MockCharacterClass.FIGHTER),
            MockCharacter("Gandalf", MockCharacterClass.WIZARD),
        ]

        recommendations = service.get_recommended_recipients("chainmail", party)

        assert recommendations[0].character.name == "Conan"
        assert recommendations[0].score == 1.0

    def test_cleric_gets_high_score_for_armor(self, service):
        """Test that cleric gets highest score for armor."""
        party = [
            MockCharacter("Brother Marcus", MockCharacterClass.CLERIC),
            MockCharacter("Gandalf", MockCharacterClass.WIZARD),
        ]

        recommendations = service.get_recommended_recipients("chainmail", party)

        assert recommendations[0].character.name == "Brother Marcus"
        assert recommendations[0].score == 1.0

    def test_rogue_wizard_get_lower_armor_score(self, service):
        """Test that rogue and wizard get lower armor scores."""
        party = [
            MockCharacter("Shadow", MockCharacterClass.ROGUE),
            MockCharacter("Gandalf", MockCharacterClass.WIZARD),
        ]

        recommendations = service.get_recommended_recipients("chainmail", party)

        for rec in recommendations:
            assert rec.score == 0.5


class TestItemAssignmentServiceMagicItems:
    """Test cases for magical item (scrolls, wands, staves) recommendations."""

    @pytest.fixture
    def service(self):
        """Create service with mock items data."""
        items_data = {
            "consumables": {
                "scroll_of_fireball": {"name": "Scroll of Fireball", "type": "scroll"},
                "wand_of_magic_missiles": {"name": "Wand of Magic Missiles", "type": "wand"},
            }
        }
        return ItemAssignmentService(items_data=items_data)

    def test_wizard_gets_high_score_for_scroll(self, service):
        """Test that wizard gets highest score for scrolls."""
        party = [
            MockCharacter("Conan", MockCharacterClass.FIGHTER),
            MockCharacter("Gandalf", MockCharacterClass.WIZARD),
        ]

        recommendations = service.get_recommended_recipients("scroll_of_fireball", party)

        assert recommendations[0].character.name == "Gandalf"
        assert recommendations[0].score == 1.0

    def test_cleric_gets_high_score_for_scroll(self, service):
        """Test that cleric gets highest score for scrolls."""
        party = [
            MockCharacter("Conan", MockCharacterClass.FIGHTER),
            MockCharacter("Brother Marcus", MockCharacterClass.CLERIC),
        ]

        recommendations = service.get_recommended_recipients("scroll_of_fireball", party)

        assert recommendations[0].character.name == "Brother Marcus"
        assert recommendations[0].score == 1.0

    def test_wand_detected_by_item_id(self, service):
        """Test that wands are detected by item_id keyword."""
        party = [
            MockCharacter("Conan", MockCharacterClass.FIGHTER),
            MockCharacter("Gandalf", MockCharacterClass.WIZARD),
        ]

        recommendations = service.get_recommended_recipients("wand_of_magic_missiles", party)

        assert recommendations[0].character.name == "Gandalf"
        assert recommendations[0].score == 1.0

    def test_staff_detected_by_item_id(self, service):
        """Test that staves are detected by item_id keyword."""
        service_with_staff = ItemAssignmentService(items_data={"weapons": {}})
        party = [
            MockCharacter("Conan", MockCharacterClass.FIGHTER),
            MockCharacter("Gandalf", MockCharacterClass.WIZARD),
        ]

        recommendations = service_with_staff.get_recommended_recipients("staff_of_power", party)

        assert recommendations[0].character.name == "Gandalf"
        assert recommendations[0].score == 1.0

    def test_non_caster_gets_low_score_for_magic_items(self, service):
        """Test that non-casters get low score for magic items."""
        party = [
            MockCharacter("Conan", MockCharacterClass.FIGHTER),
            MockCharacter("Shadow", MockCharacterClass.ROGUE),
        ]

        recommendations = service.get_recommended_recipients("scroll_of_fireball", party)

        # Both should have low score (0.3)
        for rec in recommendations:
            assert rec.score == 0.3


class TestItemAssignmentServicePotions:
    """Test cases for potion/consumable assignment based on HP."""

    @pytest.fixture
    def service(self):
        """Create service with mock items data."""
        items_data = {
            "consumables": {
                "potion_of_healing": {"name": "Potion of Healing", "type": "potion"},
            }
        }
        return ItemAssignmentService(items_data=items_data)

    def test_lower_hp_character_gets_higher_potion_score(self, service):
        """Test that character with lower HP gets higher potion score."""
        party = [
            MockCharacter("Healthy", MockCharacterClass.FIGHTER, current_hp=20, max_hp=20),
            MockCharacter("Injured", MockCharacterClass.WIZARD, current_hp=5, max_hp=20),
        ]

        recommendations = service.get_recommended_recipients("potion_of_healing", party)

        # Injured character should be first
        assert recommendations[0].character.name == "Injured"
        assert recommendations[0].score > recommendations[1].score

    def test_full_hp_character_gets_baseline_potion_score(self, service):
        """Test that full HP character gets baseline score of 0.5."""
        party = [
            MockCharacter("Healthy", MockCharacterClass.FIGHTER, current_hp=20, max_hp=20),
        ]

        recommendations = service.get_recommended_recipients("potion_of_healing", party)

        assert recommendations[0].score == 0.5

    def test_zero_hp_character_gets_max_potion_score(self, service):
        """Test that 0 HP character gets maximum score of 1.0."""
        party = [
            MockCharacter("Down", MockCharacterClass.FIGHTER, current_hp=0, max_hp=20),
        ]

        recommendations = service.get_recommended_recipients("potion_of_healing", party)

        assert recommendations[0].score == 1.0

    def test_half_hp_character_gets_intermediate_score(self, service):
        """Test that half HP character gets score of 0.75."""
        party = [
            MockCharacter("HalfHP", MockCharacterClass.FIGHTER, current_hp=10, max_hp=20),
        ]

        recommendations = service.get_recommended_recipients("potion_of_healing", party)

        assert recommendations[0].score == 0.75


class TestItemAssignmentServiceUnknownItems:
    """Test cases for unknown or generic items."""

    @pytest.fixture
    def service(self):
        """Create service with minimal items data."""
        return ItemAssignmentService(items_data={})

    def test_unknown_item_gives_equal_scores(self, service):
        """Test that unknown items give equal scores to all characters."""
        party = [
            MockCharacter("Conan", MockCharacterClass.FIGHTER),
            MockCharacter("Gandalf", MockCharacterClass.WIZARD),
            MockCharacter("Shadow", MockCharacterClass.ROGUE),
        ]

        recommendations = service.get_recommended_recipients("mystery_item", party)

        # All should have equal score of 0.5
        for rec in recommendations:
            assert rec.score == 0.5


class TestItemAssignmentServiceAutoAssign:
    """Test cases for auto-assignment decision logic."""

    @pytest.fixture
    def service(self):
        """Create service with mock items data."""
        items_data = {
            "weapons": {
                "longsword": {"name": "Longsword", "type": "weapon"},
            }
        }
        return ItemAssignmentService(items_data=items_data)

    def test_auto_assign_single_party_member(self, service):
        """Test auto-assign when only one party member."""
        party = [MockCharacter("Solo", MockCharacterClass.FIGHTER)]
        recommendations = service.get_recommended_recipients("longsword", party)

        result = service.should_auto_assign(recommendations)

        assert result is not None
        assert result.name == "Solo"

    def test_auto_assign_single_high_scorer(self, service):
        """Test auto-assign when one character has score >= threshold."""
        party = [
            MockCharacter("Conan", MockCharacterClass.FIGHTER),
            MockCharacter("Gandalf", MockCharacterClass.WIZARD),
        ]
        recommendations = service.get_recommended_recipients("longsword", party)

        result = service.should_auto_assign(recommendations)

        # Fighter has 1.0, Wizard has 0.5 - should auto-assign to Fighter
        assert result is not None
        assert result.name == "Conan"

    def test_no_auto_assign_multiple_high_scorers(self, service):
        """Test no auto-assign when multiple characters have high scores."""
        party = [
            MockCharacter("Conan", MockCharacterClass.FIGHTER),
            MockCharacter("Roland", MockCharacterClass.FIGHTER),
        ]
        recommendations = service.get_recommended_recipients("longsword", party)

        result = service.should_auto_assign(recommendations)

        # Both fighters have 1.0, should prompt user
        assert result is None

    def test_no_auto_assign_empty_recommendations(self, service):
        """Test no auto-assign when no recommendations."""
        result = service.should_auto_assign([])

        assert result is None

    def test_auto_assign_custom_threshold(self, service):
        """Test auto-assign with custom threshold."""
        party = [
            MockCharacter("Gandalf", MockCharacterClass.WIZARD),
            MockCharacter("Shadow", MockCharacterClass.ROGUE),
        ]
        recommendations = service.get_recommended_recipients("longsword", party)

        # With default threshold 0.8, neither scores high enough
        # Both have 0.5, so no auto-assign
        result = service.should_auto_assign(recommendations)
        assert result is None

        # With threshold 0.4, first one qualifies
        result_low_threshold = service.should_auto_assign(recommendations, threshold=0.4)
        assert result_low_threshold is None  # Still None because BOTH are >= 0.4


class TestItemAssignmentServiceEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def service(self):
        """Create service with mock items data."""
        return ItemAssignmentService(items_data={"weapons": {}})

    def test_empty_party_returns_empty_list(self, service):
        """Test that empty party returns empty recommendations."""
        recommendations = service.get_recommended_recipients("longsword", [])

        assert recommendations == []

    def test_recommendations_sorted_by_score_descending(self, service):
        """Test that recommendations are sorted by score (highest first)."""
        items_data = {
            "consumables": {
                "potion_of_healing": {"name": "Potion", "type": "potion"},
            }
        }
        service = ItemAssignmentService(items_data=items_data)

        party = [
            MockCharacter("Full", MockCharacterClass.FIGHTER, current_hp=20, max_hp=20),
            MockCharacter("Half", MockCharacterClass.WIZARD, current_hp=10, max_hp=20),
            MockCharacter("Low", MockCharacterClass.ROGUE, current_hp=2, max_hp=20),
        ]

        recommendations = service.get_recommended_recipients("potion_of_healing", party)

        # Should be sorted: Low (highest score) -> Half -> Full (lowest score)
        assert recommendations[0].character.name == "Low"
        assert recommendations[1].character.name == "Half"
        assert recommendations[2].character.name == "Full"

    def test_character_with_zero_max_hp_gets_default_potion_score(self):
        """Test that character with 0 max_hp doesn't cause division by zero."""
        items_data = {
            "consumables": {
                "potion_of_healing": {"name": "Potion", "type": "potion"},
            }
        }
        service = ItemAssignmentService(items_data=items_data)

        party = [
            MockCharacter("ZeroMax", MockCharacterClass.FIGHTER, current_hp=0, max_hp=0),
        ]

        recommendations = service.get_recommended_recipients("potion_of_healing", party)

        # Should not raise, should return default score
        assert len(recommendations) == 1
        assert recommendations[0].score == 0.5


class TestItemRecommendationDataclass:
    """Test ItemRecommendation dataclass."""

    def test_item_recommendation_creation(self):
        """Test creating an ItemRecommendation."""
        char = MockCharacter("Test", MockCharacterClass.FIGHTER)
        rec = ItemRecommendation(character=char, score=0.8)

        assert rec.character == char
        assert rec.score == 0.8

    def test_item_recommendation_equality(self):
        """Test ItemRecommendation equality based on content."""
        char = MockCharacter("Test", MockCharacterClass.FIGHTER)
        rec1 = ItemRecommendation(character=char, score=0.8)
        rec2 = ItemRecommendation(character=char, score=0.8)

        assert rec1 == rec2
