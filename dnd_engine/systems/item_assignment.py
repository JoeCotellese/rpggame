# ABOUTME: Item assignment service for recommending which character should receive items.
# ABOUTME: Encapsulates game rules for class-item suitability matching.

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dnd_engine.core.character import Character


@dataclass
class ItemRecommendation:
    """
    Recommendation for assigning an item to a character.

    Attributes:
        character: The recommended character
        score: Suitability score from 0.0 to 1.0
               1.0 = perfect match, 0.5 = acceptable, 0.0 = unsuitable
    """
    character: "Character"
    score: float


class ItemAssignmentService:
    """
    Handles intelligent item assignment recommendations for party members.

    Encapsulates game rules for determining which character class should
    receive which item types. The CLI calls this service to get recommendations
    and handles user interaction separately.

    Class-item suitability rules:
    - Weapons: prefer martial classes (Fighter)
    - Armor: prefer tank classes (Fighter, Cleric)
    - Scrolls/wands/staves: prefer casters (Wizard, Cleric)
    - Potions: prefer characters with lower HP percentage
    """

    # Classes that prefer martial weapons
    MARTIAL_CLASSES = frozenset(["fighter"])

    # Classes that prefer heavy armor
    TANK_CLASSES = frozenset(["fighter", "cleric"])

    # Classes that prefer magical items (scrolls, wands, staves)
    CASTER_CLASSES = frozenset(["wizard", "cleric"])

    def __init__(self, items_data: dict[str, Any] | None = None):
        """
        Initialize the item assignment service.

        Args:
            items_data: Full items data from items.json. If not provided,
                       will be loaded on first use.
        """
        self._items_data = items_data

    @property
    def items_data(self) -> dict[str, Any]:
        """Lazy-load items data if not provided."""
        if self._items_data is None:
            from dnd_engine.rules.loader import DataLoader
            data_loader = DataLoader()
            self._items_data = data_loader.load_items()
        return self._items_data

    def get_recommended_recipients(
        self,
        item_id: str,
        party_members: list["Character"]
    ) -> list[ItemRecommendation]:
        """
        Get recommended recipients for an item with suitability scores.

        Args:
            item_id: ID of the item to assign
            party_members: List of living party members to consider

        Returns:
            List of ItemRecommendation objects sorted by score (highest first).
            Empty list if no party members provided.
        """
        if not party_members:
            return []

        # Find item details and category
        item_details, category = self._find_item_details(item_id)

        recommendations = []
        for character in party_members:
            score = self._calculate_suitability_score(
                character, item_id, item_details, category
            )
            recommendations.append(ItemRecommendation(character=character, score=score))

        # Sort by score descending
        recommendations.sort(key=lambda r: r.score, reverse=True)
        return recommendations

    def _find_item_details(
        self,
        item_id: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        Find item details and category from items data.

        Args:
            item_id: ID of the item to look up

        Returns:
            Tuple of (item_details dict, category string) or (None, None) if not found
        """
        for category, category_items in self.items_data.items():
            if isinstance(category_items, dict) and item_id in category_items:
                return category_items[item_id], category
        return None, None

    def _calculate_suitability_score(
        self,
        character: "Character",
        item_id: str,
        item_details: dict[str, Any] | None,
        category: str | None
    ) -> float:
        """
        Calculate how suitable a character is for an item.

        Args:
            character: The character to evaluate
            item_id: ID of the item
            item_details: Item details from items.json (may be None)
            category: Item category (weapons, armor, consumables)

        Returns:
            Suitability score from 0.0 to 1.0
        """
        char_class = character.character_class.value.lower()

        # If we have item details, use type-based scoring
        if item_details:
            item_type = item_details.get("type", "").lower()

            # Weapons: prefer martial classes
            if "weapon" in item_type or category == "weapons":
                if char_class in self.MARTIAL_CLASSES:
                    return 1.0
                return 0.5

            # Armor: prefer tank classes
            if "armor" in item_type or category == "armor":
                if char_class in self.TANK_CLASSES:
                    return 1.0
                return 0.5

        # Scrolls/wands/staves: prefer casters (check item_id for keywords)
        if any(keyword in item_id.lower() for keyword in ["scroll", "wand", "staff"]):
            if char_class in self.CASTER_CLASSES:
                return 1.0
            return 0.3

        # Potions/consumables: score based on HP percentage (lower HP = higher score)
        if "potion" in item_id.lower() or category == "consumables":
            if character.max_hp > 0:
                hp_percentage = character.current_hp / character.max_hp
                # Invert so lower HP = higher score, scale to 0.5-1.0 range
                return 0.5 + (0.5 * (1.0 - hp_percentage))
            return 0.5

        # Default: all characters equally suitable
        return 0.5

    def should_auto_assign(
        self,
        recommendations: list[ItemRecommendation],
        threshold: float = 0.8
    ) -> "Character | None":
        """
        Determine if an item should be auto-assigned without user prompt.

        Auto-assigns when:
        - Only one party member exists
        - Exactly one character has a score >= threshold and others are below

        Args:
            recommendations: List of recommendations from get_recommended_recipients
            threshold: Minimum score for auto-assignment (default 0.8)

        Returns:
            Character to auto-assign to, or None if user should be prompted
        """
        if not recommendations:
            return None

        # Single party member: auto-assign
        if len(recommendations) == 1:
            return recommendations[0].character

        # Check for single high-confidence match
        high_scorers = [r for r in recommendations if r.score >= threshold]
        if len(high_scorers) == 1:
            return high_scorers[0].character

        # Multiple matches or no clear winner: prompt user
        return None
