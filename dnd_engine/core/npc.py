# ABOUTME: NPC class for non-player characters with LLM-powered conversations
# ABOUTME: Handles personality, knowledge, shops, and tool-calling for game interactions

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NPCDisposition(Enum):
    """NPC attitude toward the player party."""

    HOSTILE = "hostile"
    UNFRIENDLY = "unfriendly"
    NEUTRAL = "neutral"
    FRIENDLY = "friendly"
    ALLIED = "allied"


@dataclass
class ShopItem:
    """Item available for purchase from an NPC shop."""

    item_id: str
    price: int  # Price in gold
    stock: int = -1  # -1 for unlimited


@dataclass
class NPCShop:
    """Shop configuration for merchant NPCs."""

    enabled: bool
    shop_type: str  # "tavern", "temple", "blacksmith", "general", etc.
    inventory: list[ShopItem]
    buy_rate: float  # Multiplier for buying items from player (0.5 = 50%)
    sell_dialogue: str = "What would you like?"
    insufficient_funds_dialogue: str = "You don't have enough gold."

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NPCShop":
        """Create NPCShop from dictionary data."""
        items = [
            ShopItem(
                item_id=item["item_id"],
                price=item["price"],
                stock=item.get("stock", -1),
            )
            for item in data.get("inventory", [])
        ]
        return cls(
            enabled=data.get("enabled", False),
            shop_type=data.get("shop_type", "general"),
            inventory=items,
            buy_rate=data.get("buy_rate", 0.5),
            sell_dialogue=data.get("sell_dialogue", "What would you like?"),
            insufficient_funds_dialogue=data.get(
                "insufficient_funds_dialogue", "You don't have enough gold."
            ),
        )


@dataclass
class NPCPersonality:
    """Personality configuration for LLM prompt generation."""

    traits: list[str]
    speech_style: str
    attitude_default: str
    suspicion_of_strangers: str = "none"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NPCPersonality":
        """Create NPCPersonality from dictionary data."""
        return cls(
            traits=data.get("traits", []),
            speech_style=data.get("speech_style", ""),
            attitude_default=data.get("attitude_default", "neutral"),
            suspicion_of_strangers=data.get("suspicion_of_strangers", "none"),
        )

    def to_prompt_text(self) -> str:
        """Generate personality description for LLM system prompt."""
        traits_text = ", ".join(self.traits) if self.traits else "unremarkable"
        return (
            f"PERSONALITY: {traits_text}\n"
            f"SPEECH STYLE: {self.speech_style}\n"
            f"DEFAULT ATTITUDE: {self.attitude_default}"
        )


@dataclass
class NPCKnowledge:
    """Knowledge the NPC possesses for conversation context."""

    general: list[str]  # General facts the NPC knows
    quest_hooks: list[str]  # Quest IDs this NPC can provide hints about
    local_lore: list[str]  # World-building information

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NPCKnowledge":
        """Create NPCKnowledge from dictionary data."""
        return cls(
            general=data.get("general", []),
            quest_hooks=data.get("quest_hooks", []),
            local_lore=data.get("local_lore", []),
        )

    def to_prompt_text(self) -> str:
        """Generate knowledge section for LLM system prompt."""
        lines = ["KNOWLEDGE:"]
        for fact in self.general:
            lines.append(f"- {fact}")
        if self.local_lore:
            lines.append("\nLOCAL LORE:")
            for lore in self.local_lore:
                lines.append(f"- {lore}")
        return "\n".join(lines)


@dataclass
class NPC:
    """
    Non-player character with LLM-powered conversation capabilities.

    NPCs have personalities, knowledge, optional shops, and can interact
    with the game through tool calling (quest activation, transactions, etc.).
    """

    id: str
    name: str
    display_name: str
    home_location: str  # Room GUID
    current_location: str  # Room GUID
    can_move: bool

    personality: NPCPersonality
    knowledge: NPCKnowledge
    shop: NPCShop | None
    dialogue: dict[str, str]  # greeting, farewell, busy, etc.
    schedule: dict[str, str] | None  # time_of_day -> room_guid
    reputation_modifiers: dict[str, Any] | None
    services: dict[str, Any] | None  # Temple healing, etc.

    # Runtime state (not persisted in JSON definition)
    player_reputation: int = 0
    conversation_history: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NPC":
        """Create NPC from dictionary data."""
        # Build shop if present
        shop = None
        if data.get("shop"):
            shop = NPCShop.from_dict(data["shop"])

        return cls(
            id=data["id"],
            name=data["name"],
            display_name=data.get("display_name", data["name"]),
            home_location=data["home_location"],
            current_location=data.get("current_location", data["home_location"]),
            can_move=data.get("can_move", False),
            personality=NPCPersonality.from_dict(data.get("personality", {})),
            knowledge=NPCKnowledge.from_dict(data.get("knowledge", {})),
            shop=shop,
            dialogue=data.get("dialogue", {}),
            schedule=data.get("schedule"),
            reputation_modifiers=data.get("reputation_modifiers"),
            services=data.get("services"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize NPC runtime state for saving."""
        result = {
            "id": self.id,
            "current_location": self.current_location,
            "player_reputation": self.player_reputation,
        }
        # Include shop stock changes if shop exists
        if self.shop:
            result["shop_stock"] = {
                item.item_id: item.stock for item in self.shop.inventory
            }
        return result

    def get_disposition(self) -> NPCDisposition:
        """Get current disposition based on reputation."""
        if not self.reputation_modifiers:
            return NPCDisposition.NEUTRAL

        friendly_threshold = self.reputation_modifiers.get("friendly_threshold", 10)
        hostile_threshold = self.reputation_modifiers.get("hostile_threshold", -20)

        if self.player_reputation >= friendly_threshold:
            return NPCDisposition.FRIENDLY
        elif self.player_reputation <= hostile_threshold:
            return NPCDisposition.HOSTILE
        return NPCDisposition.NEUTRAL

    def build_system_prompt(self, game_context: dict[str, Any] | None = None) -> str:
        """
        Build the LLM system prompt for this NPC.

        Args:
            game_context: Optional current game state info (quests, player party, etc.)

        Returns:
            Complete system prompt for LLM conversation
        """
        lines = [
            f"You are {self.display_name}.",
            "",
            self.personality.to_prompt_text(),
            "",
            self.knowledge.to_prompt_text(),
            "",
            "BEHAVIOR:",
            "- Stay in character at all times",
            "- Don't break character or mention being an AI",
            "- ALWAYS call get_available_quests before sharing any rumors - don't invent content",
            "- Only activate quests when the player clearly commits to helping",
            "- Never narrate tool usage - just do it and respond to the result",
            "",
            "CRITICAL - PURCHASES:",
            "- You MUST call buy_item for ANY purchase - never just roleplay accepting money",
            "- When player orders food/drink/items, IMMEDIATELY call buy_item with item_name and price",
            "- If buy_item fails (not enough gold), respond naturally explaining the problem",
            "- Do not say 'I'll bring your order' without first calling buy_item to process payment",
        ]

        if self.shop and self.shop.enabled:
            lines.extend(
                [
                    "",
                    f"SHOP ({self.shop.shop_type}):",
                    f"- {self.shop.sell_dialogue}",
                    "- Process purchases through buy_item tool",
                ]
            )

        lines.extend(
            [
                "",
                "IMPORTANT - QUEST DIALOGUE:",
                "- NEVER say 'there's a quest called X' - quests don't have names in-world",
                "- Describe PROBLEMS and SITUATIONS naturally (e.g., 'strange sounds from the crypt')",
                "- Let players infer it's an opportunity to help - don't label it a 'quest'",
                "- Use the 'hint' field for how YOUR CHARACTER would describe the situation",
                "- Keep responses conversational and in-character",
                "",
                "QUEST REWARDS AND ITEM EXCHANGE:",
                "- Call get_pending_rewards to check if player has quests to turn in to you",
                "- When player reports completing a task, call turn_in_quest to give them gold",
                "- When player offers to give/return an item, call receive_item_from_player",
                "- If receive_item_from_player returns bonus_reward=true, describe giving them the reward",
                "- React naturally to receiving items - express gratitude for important returns",
            ]
        )

        return "\n".join(lines)

    def get_greeting(self) -> str:
        """Get appropriate greeting based on disposition."""
        disposition = self.get_disposition()
        if disposition == NPCDisposition.HOSTILE:
            return self.dialogue.get("hostile_greeting", "What do you want?")
        return self.dialogue.get("greeting", f"Hello, I'm {self.name}.")

    def get_farewell(self) -> str:
        """Get farewell dialogue."""
        return self.dialogue.get("farewell", "Goodbye.")

    def move_to(self, room_guid: str) -> None:
        """Move NPC to a new location."""
        if self.can_move:
            self.current_location = room_guid

    def return_home(self) -> None:
        """Return NPC to their home location."""
        self.current_location = self.home_location
