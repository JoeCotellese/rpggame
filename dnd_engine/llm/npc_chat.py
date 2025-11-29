# ABOUTME: Manages LLM-powered NPC conversations with tool calling capabilities
# ABOUTME: Handles conversation state, tool dispatch, and sync-over-async for CLI

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from dnd_engine.core.npc import NPC
from dnd_engine.ui.rich_ui import print_status_message

if TYPE_CHECKING:
    from dnd_engine.core.game_state import GameState
    from dnd_engine.llm.base import LLMProvider

logger = logging.getLogger(__name__)


# Tool definitions for NPC conversations
NPC_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "activate_quest",
            "description": (
                "Activate a quest when the player shows clear commitment to helping. "
                "Only call this when they explicitly agree, not just when asking questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "quest_id": {
                        "type": "string",
                        "description": "The quest identifier",
                    }
                },
                "required": ["quest_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_quests",
            "description": (
                "Get quests/rumors the NPC knows about. "
                "ALWAYS call this before sharing any rumors or quest information - never invent content."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buy_item",
            "description": (
                "Process a purchase when the player wants to buy something. "
                "The game validates gold. Common prices: ale 2gp, meal 5gp, room 8gp."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string", "description": "Item being purchased"},
                    "price": {"type": "integer", "description": "Price in gold"},
                },
                "required": ["item_name", "price"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_player_gold",
            "description": "Check how much gold the player party has.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "give_item",
            "description": "Give an item from NPC to player (gift, quest reward, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string", "description": "Item to give"},
                },
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_reputation",
            "description": "Check the player's reputation with this NPC or their faction.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "receive_item_from_player",
            "description": (
                "Accept an item from the player. Use when player offers to give "
                "or return an item. Check if this triggers a quest bonus reward."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "ID of the item being offered",
                    },
                },
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn_in_quest",
            "description": (
                "Complete a quest turn-in and give the player their gold reward. "
                "Use when the player reports completing a task you asked them to do."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "quest_id": {
                        "type": "string",
                        "description": "ID of the quest being turned in",
                    },
                },
                "required": ["quest_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_rewards",
            "description": (
                "Check if the player has any completed quests they can turn in "
                "to this NPC for rewards."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


@dataclass
class ConversationState:
    """Tracks state of an active NPC conversation."""

    npc: NPC
    messages: list[dict[str, Any]] = field(default_factory=list)
    ended: bool = False
    end_reason: str | None = None


class NPCChatManager:
    """
    Manages NPC conversations using LLM with tool calling.

    Coordinates between the LLM provider and game state,
    dispatching tool calls to modify game state.
    """

    def __init__(
        self,
        provider: "LLMProvider | None",
        game_state: "GameState",
    ):
        """
        Initialize NPC chat manager.

        Args:
            provider: LLM provider for generating responses (None for fallback mode)
            game_state: Game state for tool dispatch
        """
        self.provider = provider
        self.game_state = game_state
        self._current_conversation: ConversationState | None = None

        # Background event loop (same pattern as LLMEnhancer)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        if provider:
            self._start_event_loop()

        # Register tool handlers
        self._tool_handlers: dict[str, Callable[..., dict[str, Any]]] = {
            "activate_quest": self._handle_activate_quest,
            "get_available_quests": self._handle_get_available_quests,
            "buy_item": self._handle_buy_item,
            "get_player_gold": self._handle_get_player_gold,
            "give_item": self._handle_give_item,
            "check_reputation": self._handle_check_reputation,
            "receive_item_from_player": self._handle_receive_item_from_player,
            "turn_in_quest": self._handle_turn_in_quest,
            "get_pending_rewards": self._handle_get_pending_rewards,
        }

    def _start_event_loop(self) -> None:
        """Start background thread with event loop for async tasks."""

        def run_loop() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()

        # Wait for loop to be ready
        while self._loop is None:
            pass

    def _run_sync(self, coro: Any, timeout: float = 30.0) -> Any:
        """Run a coroutine synchronously with timeout."""
        if not self._loop or self._loop.is_closed():
            return None

        try:
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
            return future.result(timeout=timeout)
        except TimeoutError:
            logger.warning(f"NPC chat timed out after {timeout}s")
            return None
        except Exception as e:
            logger.error(f"NPC chat error: {e}")
            return None

    def start_conversation_sync(
        self, npc: NPC, timeout: float = 30.0
    ) -> str | None:
        """
        Start a conversation with an NPC (synchronous).

        Args:
            npc: The NPC to talk to
            timeout: Request timeout

        Returns:
            The NPC's greeting or None if unavailable
        """
        self._current_conversation = ConversationState(npc=npc)

        if not self.provider:
            return npc.get_greeting()

        # Build system prompt
        system_prompt = npc.build_system_prompt()
        self._current_conversation.messages.append(
            {"role": "system", "content": system_prompt}
        )

        # Add initial user message to trigger greeting
        self._current_conversation.messages.append(
            {"role": "user", "content": "*enters and approaches*"}
        )

        # Get initial greeting from LLM
        response = self._run_sync(self._get_npc_response(), timeout=timeout)
        return response

    def send_message_sync(
        self, player_message: str, timeout: float = 30.0
    ) -> tuple[str | None, bool]:
        """
        Send a player message and get NPC response.

        Args:
            player_message: What the player says
            timeout: Request timeout

        Returns:
            Tuple of (npc_response, conversation_ended)
        """
        if not self._current_conversation:
            return None, True

        if not self.provider:
            ended = self._check_conversation_ended(player_message)
            return self._get_fallback_response(player_message), ended

        # Add player message
        self._current_conversation.messages.append(
            {"role": "user", "content": player_message}
        )

        # Get response (may involve multiple tool calls)
        response = self._run_sync(self._get_npc_response(), timeout=timeout)

        # Check if conversation ended naturally
        ended = self._check_conversation_ended(player_message)

        return response, ended

    def end_conversation(self) -> None:
        """End the current conversation."""
        self._current_conversation = None

    def get_current_npc(self) -> NPC | None:
        """Get the NPC in the current conversation."""
        if self._current_conversation:
            return self._current_conversation.npc
        return None

    async def _get_npc_response(self) -> str | None:
        """Get NPC response, processing any tool calls."""
        if not self._current_conversation or not self.provider:
            return None

        while True:
            response = await self.provider.chat_with_tools(
                messages=self._current_conversation.messages,
                tools=NPC_TOOLS,
                temperature=0.7,
            )

            if not response:
                return None

            # Process tool calls if any
            if response.get("tool_calls"):
                # Add assistant message with tool calls
                assistant_msg: dict[str, Any] = {"role": "assistant"}
                if response.get("content"):
                    assistant_msg["content"] = response["content"]

                # Build tool_calls in OpenAI format for message history
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"]),
                        },
                    }
                    for tc in response["tool_calls"]
                ]
                self._current_conversation.messages.append(assistant_msg)

                # Execute tools and add results
                for tool_call in response["tool_calls"]:
                    result = self._dispatch_tool(
                        tool_call["name"], tool_call["arguments"]
                    )
                    logger.info(
                        f"[TOOL] {tool_call['name']}({tool_call['arguments']}) -> {result}"
                    )

                    # Show visible feedback to user (like dice rolls)
                    self._show_tool_feedback(
                        tool_call["name"], tool_call["arguments"], result
                    )

                    self._current_conversation.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": json.dumps(result),
                        }
                    )

                # Continue loop for final response
                continue

            # No tool calls - final response
            if response.get("content"):
                self._current_conversation.messages.append(
                    {"role": "assistant", "content": response["content"]}
                )
                return response["content"]

            return None

    def _dispatch_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Dispatch a tool call to its handler."""
        handler = self._tool_handlers.get(tool_name)
        if not handler:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}

        try:
            return handler(**arguments)
        except Exception as e:
            logger.error(f"Tool handler error: {e}")
            return {"success": False, "error": str(e)}

    def _show_tool_feedback(
        self, tool_name: str, arguments: dict[str, Any], result: dict[str, Any]
    ) -> None:
        """Show visible feedback to user when tools execute (like dice rolls)."""
        if tool_name == "buy_item":
            item = arguments.get("item_name", "item")
            price = arguments.get("price", 0)
            if result.get("success"):
                remaining = result.get("remaining_gold", 0)
                print_status_message(
                    f"💰 Purchased {item} for {price} gold ({remaining} gold remaining)",
                    "success",
                )
            else:
                error = result.get("error", "Transaction failed")
                print_status_message(f"💰 Purchase failed: {error}", "error")

        elif tool_name == "activate_quest":
            quest_id = arguments.get("quest_id", "quest")
            if result.get("success"):
                quest_name = result.get("quest_name", quest_id)
                print_status_message(f"📜 Quest activated: {quest_name}", "success")
            else:
                print_status_message(
                    f"📜 Quest activation failed: {result.get('error')}", "error"
                )

        elif tool_name == "give_item":
            item_id = arguments.get("item_id", "item")
            if result.get("success"):
                print_status_message(f"🎁 Received: {item_id}", "success")
            else:
                print_status_message(
                    f"🎁 Failed to receive item: {result.get('error')}", "error"
                )

        elif tool_name == "get_player_gold":
            gold = result.get("gold", 0)
            print_status_message(f"💰 Party gold: {gold}", "info")

        # Note: get_available_quests has no user feedback - NPC describes quests naturally

    # === Tool Handlers ===

    def _handle_activate_quest(self, quest_id: str) -> dict[str, Any]:
        """Activate a quest for the player."""
        if not self.game_state.quest_manager:
            return {"success": False, "error": "Quest system not available"}

        quest = self.game_state.quest_manager.quests.get(quest_id)
        if not quest:
            return {"success": False, "error": f"Unknown quest: {quest_id}"}

        success = self.game_state.quest_manager.activate_quest(quest_id)
        if success:
            return {
                "success": True,
                "quest_name": quest.name,
                "quest_description": quest.description,
            }
        return {"success": False, "error": "Quest cannot be activated"}

    def _handle_get_available_quests(self) -> dict[str, Any]:
        """Get quests the NPC can share."""
        if not self.game_state.quest_manager or not self._current_conversation:
            return {"quests": []}

        npc = self._current_conversation.npc
        quest_hooks = npc.knowledge.quest_hooks

        # Get available quests that this NPC knows about
        available = []
        for quest_id in quest_hooks:
            quest = self.game_state.quest_manager.quests.get(quest_id)
            if quest:
                state = self.game_state.quest_manager.get_quest_state(quest_id)
                if state.value in ["available", "active"]:
                    # Get NPC-specific hint from quest data
                    hint = self._get_quest_hint(quest_id, npc.id)
                    available.append(
                        {
                            "id": quest.id,
                            "state": state.value,
                            # 'hint' is how the NPC would describe this situation
                            "hint": hint,
                        }
                    )

        return {"quests": available}

    def _get_quest_hint(self, quest_id: str, npc_id: str) -> str:
        """Get NPC-specific hint for a quest."""
        # Try to get hint from quest data
        if self.game_state.quest_manager:
            quest = self.game_state.quest_manager.quests.get(quest_id)
            if quest and hasattr(quest, "npc_hints"):
                # Check if npc_hints exists in completion_criteria (where we store it)
                hints = quest.completion_criteria.get("npc_hints", {})
                state = self.game_state.quest_manager.get_quest_state(quest_id)
                state_hints = hints.get(state.value, {})
                if npc_id in state_hints:
                    return state_hints[npc_id]
                # Try by NPC role
                npc = self._current_conversation.npc if self._current_conversation else None
                if npc:
                    role = npc.id.split("_")[-1]  # e.g., "innkeeper" from "marta_innkeeper"
                    if role in state_hints:
                        return state_hints[role]

        return ""

    def _handle_buy_item(self, item_name: str, price: int) -> dict[str, Any]:
        """Process item purchase."""
        # Get party gold total
        total_gold = sum(
            char.inventory.gold for char in self.game_state.party.characters
        )

        if total_gold < price:
            return {
                "success": False,
                "error": "Not enough gold",
                "player_gold": total_gold,
            }

        # Deduct from first character with enough gold
        for char in self.game_state.party.characters:
            if char.inventory.gold >= price:
                char.inventory.gold -= price
                break
        else:
            # Spread across characters if needed
            remaining = price
            for char in self.game_state.party.characters:
                if remaining <= 0:
                    break
                deduct = min(char.inventory.gold, remaining)
                char.inventory.gold -= deduct
                remaining -= deduct

        # For consumables like food/drink, we don't add to inventory
        # For actual items, would add here

        return {
            "success": True,
            "item": item_name,
            "remaining_gold": sum(
                c.inventory.gold for c in self.game_state.party.characters
            ),
        }

    def _handle_get_player_gold(self) -> dict[str, Any]:
        """Get party's total gold."""
        total = sum(char.inventory.gold for char in self.game_state.party.characters)
        return {"gold": total}

    def _handle_give_item(self, item_id: str) -> dict[str, Any]:
        """Give an item from NPC to player."""
        if not self._current_conversation:
            return {"success": False, "error": "No active conversation"}

        # Check if NPC has the item in personal inventory or shop
        # For now, just acknowledge the gift
        # TODO: Integrate with full inventory system

        # Give to first party member
        if self.game_state.party.characters:
            char = self.game_state.party.characters[0]
            # Would add item to inventory here
            return {
                "success": True,
                "item_id": item_id,
                "recipient": char.name,
            }

        return {"success": False, "error": "No party members to receive item"}

    def _handle_check_reputation(self) -> dict[str, Any]:
        """Check player's reputation with this NPC."""
        if not self._current_conversation:
            return {"reputation": 0, "disposition": "neutral"}

        npc = self._current_conversation.npc
        disposition = npc.get_disposition()

        return {
            "reputation": npc.player_reputation,
            "disposition": disposition.value,
        }

    def _handle_receive_item_from_player(self, item_id: str) -> dict[str, Any]:
        """Accept an item from the player, checking for bonus rewards."""
        if not self._current_conversation:
            return {"success": False, "error": "No active conversation"}

        npc = self._current_conversation.npc
        quest_manager = self.game_state.quest_manager

        # Check if any character in party has this item
        item_holder = next(
            (char for char in self.game_state.party.characters
             if char.inventory.has_item(item_id)),
            None
        )

        if not item_holder:
            return {
                "success": False,
                "error": f"Party does not have item: {item_id}",
            }

        # Check if this triggers a bonus reward
        quest, bonus = quest_manager.check_bonus_reward(npc.id, item_id)

        if quest and bonus:
            # Remove item from player inventory
            item_holder.inventory.remove_item(item_id)

            # Give reward item to player
            reward_recipient = self.game_state.party.characters[0]
            reward_category = self.game_state._get_item_category(bonus.reward_item)
            if reward_category:
                reward_recipient.inventory.add_item(bonus.reward_item, reward_category)

            print_status_message(
                f"🎁 Gave {item_id} to {npc.display_name}", "success"
            )
            print_status_message(
                f"🎁 Received: {bonus.reward_item}", "success"
            )

            return {
                "success": True,
                "item_received": item_id,
                "bonus_reward": True,
                "reward_item": bonus.reward_item,
                "reward_recipient": reward_recipient.name,
                "npc_dialogue_hint": bonus.description,
            }

        # NPC accepts the item but no special reward
        item_holder.inventory.remove_item(item_id)
        print_status_message(
            f"🎁 Gave {item_id} to {npc.display_name}", "success"
        )

        return {
            "success": True,
            "item_received": item_id,
            "bonus_reward": False,
        }

    def _handle_turn_in_quest(self, quest_id: str) -> dict[str, Any]:
        """Turn in a completed quest and claim the gold reward."""
        if not self._current_conversation:
            return {"success": False, "error": "No active conversation"}

        npc = self._current_conversation.npc
        quest_manager = self.game_state.quest_manager

        # Attempt to claim reward
        result = quest_manager.claim_quest_reward(quest_id, npc.id)

        if result["success"]:
            # Award gold to party
            reward_gold = result["reward_gold"]
            if reward_gold > 0 and self.game_state.party.characters:
                # Add gold to first character (party leader)
                leader = self.game_state.party.characters[0]
                leader.inventory.gold += reward_gold

                print_status_message(
                    f"💰 Received {reward_gold} gold for completing "
                    f"'{result['quest_name']}'",
                    "success",
                )

            return {
                "success": True,
                "quest_id": quest_id,
                "quest_name": result["quest_name"],
                "reward_gold": reward_gold,
            }

        return result

    def _handle_get_pending_rewards(self) -> dict[str, Any]:
        """Get quests that can be turned in to this NPC."""
        if not self._current_conversation:
            return {"pending_rewards": []}

        npc = self._current_conversation.npc
        quest_manager = self.game_state.quest_manager

        pending = quest_manager.get_quests_awaiting_reward(npc.id)

        return {
            "pending_rewards": [
                {
                    "quest_id": q.id,
                    "quest_name": q.name,
                    "reward_gold": q.reward_gold,
                }
                for q in pending
            ]
        }

    # === Fallback Methods ===

    def _get_fallback_response(self, message: str) -> str:
        """Return static response when LLM unavailable."""
        lower = message.lower()
        if any(word in lower for word in ["bye", "goodbye", "leave", "farewell"]):
            if self._current_conversation:
                return self._current_conversation.npc.get_farewell()
            return "Farewell."
        return "Hmm, I'm not sure what to say to that."

    def _check_conversation_ended(self, player_message: str) -> bool:
        """Check if conversation should end based on player message."""
        farewell_words = ["bye", "goodbye", "leave", "farewell", "exit"]
        return any(word in player_message.lower() for word in farewell_words)
