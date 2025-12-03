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
                "Only call this when they explicitly agree, not just when asking questions. "
                "IMPORTANT: You MUST use the exact quest ID returned by get_available_quests - "
                "do NOT invent or modify quest IDs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "quest_id": {
                        "type": "string",
                        "description": (
                            "The EXACT quest ID from get_available_quests response. "
                            "Must match exactly (e.g., 'investigate_crypt', not 'investigate_family_crypt')."
                        ),
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
            "name": "open_shop",
            "description": (
                "Call this when the player wants to shop, browse, buy, sell, "
                "see your inventory, or do any commerce. This opens a visual shop "
                "interface for the player to interact with."
            ),
            "parameters": {"type": "object", "properties": {}},
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
        self.shop_requested: bool = False  # Flag to signal shop UI should open

        # Background event loop (same pattern as LLMEnhancer)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        if provider:
            self._start_event_loop()

        # Register tool handlers
        self._tool_handlers: dict[str, Callable[..., dict[str, Any]]] = {
            "activate_quest": self._handle_activate_quest,
            "get_available_quests": self._handle_get_available_quests,
            "open_shop": self._handle_open_shop,
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

        # Gather context about quest items the player is visibly carrying
        game_context = self._gather_visible_quest_context(npc)

        # Build system prompt with context
        system_prompt = npc.build_system_prompt(game_context)
        self._current_conversation.messages.append(
            {"role": "system", "content": system_prompt}
        )

        # Build initial message describing what the NPC sees
        initial_message = self._build_initial_approach_message(game_context)
        self._current_conversation.messages.append(
            {"role": "user", "content": initial_message}
        )

        # Get initial greeting from LLM
        response = self._run_sync(self._get_npc_response(), timeout=timeout)
        return response

    def _gather_visible_quest_context(self, npc: NPC) -> dict[str, Any]:
        """
        Gather context about quest items the party is carrying that this NPC
        would recognize or be interested in.

        Args:
            npc: The NPC to check relevance for

        Returns:
            Dictionary with visible_quest_items list
        """
        visible_items: list[dict[str, Any]] = []

        if not self.game_state.quest_manager:
            return {"visible_quest_items": visible_items}

        # Get quest items relevant to this NPC
        relevant_items = self.game_state.quest_manager.get_relevant_quest_items(npc.id)

        # Check which of these items the party actually has
        for item_info in relevant_items:
            item_id = item_info["item_id"]
            for char in self.game_state.party.characters:
                if char.inventory.has_item(item_id):
                    # Get item description from content registry
                    item_data = self._get_item_data(item_id)
                    visible_items.append({
                        "item_id": item_id,
                        "item_name": item_data.get("name", item_id) if item_data else item_id,
                        "item_description": item_data.get("description", "") if item_data else "",
                        "quest_state": item_info["quest_state"],
                        "relevance_type": item_info["relevance_type"],
                    })
                    break  # Only count once per item type

        return {"visible_quest_items": visible_items}

    def _get_item_data(self, item_id: str) -> dict[str, Any] | None:
        """Get item data from game state's content registry."""
        if hasattr(self.game_state, "content_registry") and self.game_state.content_registry:
            return self.game_state.content_registry.get_item(item_id)
        return None

    def _build_initial_approach_message(
        self, game_context: dict[str, Any]
    ) -> str:
        """
        Build the initial approach message describing what the NPC sees.

        Args:
            game_context: Context with visible_quest_items

        Returns:
            String describing the player's approach
        """
        visible_items = game_context.get("visible_quest_items", [])

        if not visible_items:
            return "*enters and approaches*"

        # Describe what the NPC can see
        item_descriptions = []
        for item in visible_items:
            name = item.get("item_name", item["item_id"])
            item_descriptions.append(name.lower())

        if len(item_descriptions) == 1:
            items_text = item_descriptions[0]
        else:
            items_text = ", ".join(item_descriptions[:-1]) + f" and {item_descriptions[-1]}"

        return f"*enters and approaches, visibly carrying a {items_text}*"

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
        if tool_name == "activate_quest":
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
        # Note: turn_in_quest feedback is handled in _handle_turn_in_quest directly
        # Note: get_pending_rewards has no user feedback - NPC describes rewards naturally

    # === Tool Handlers ===

    def _handle_activate_quest(self, quest_id: str) -> dict[str, Any]:
        """Activate a quest for the player."""
        if not self.game_state.quest_manager:
            return {"success": False, "error": "Quest system not available"}

        quest = self.game_state.quest_manager.quests.get(quest_id)
        if not quest:
            return {"success": False, "error": f"Unknown quest: {quest_id}"}

        # If quest is locked and this NPC is the quest_giver, unlock it first
        qm = self.game_state.quest_manager
        state = qm.get_quest_state(quest_id)
        if state.value == "locked" and self._current_conversation:
            npc_id = self._current_conversation.npc.id
            if quest.quest_giver == npc_id:
                from dnd_engine.core.quest import QuestState
                qm._quest_states[quest_id] = QuestState.AVAILABLE

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
                # Include locked quests if this NPC is the quest_giver (they can offer it)
                is_quest_giver = quest.quest_giver == npc.id
                if state.value in ["available", "active"] or (
                    state.value == "locked" and is_quest_giver
                ):
                    # Get NPC-specific hint from quest data
                    hint = self._get_quest_hint(quest_id, npc.id)
                    available.append(
                        {
                            "id": quest.id,
                            "state": state.value,
                            "can_offer": is_quest_giver and state.value in ["locked", "available"],
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
            if quest and quest.npc_hints:
                state = self.game_state.quest_manager.get_quest_state(quest_id)
                state_hints = quest.npc_hints.get(state.value, {})

                # state_hints can be a string (same for all NPCs) or dict (NPC-specific)
                if isinstance(state_hints, str):
                    return state_hints

                if isinstance(state_hints, dict):
                    if npc_id in state_hints:
                        return state_hints[npc_id]
                    # Try by NPC role
                    npc = self._current_conversation.npc if self._current_conversation else None
                    if npc:
                        role = npc.id.split("_")[-1]  # e.g., "innkeeper" from "marta_innkeeper"
                        if role in state_hints:
                            return state_hints[role]

        return ""

    def _handle_open_shop(self) -> dict[str, Any]:
        """Signal that the shop UI should be opened."""
        if not self._current_conversation:
            return {"success": False, "error": "No active conversation"}

        npc = self._current_conversation.npc
        if not npc.shop or not npc.shop.enabled:
            return {"success": False, "error": "This NPC doesn't have a shop"}

        # Set flag to signal CLI should open shop UI
        self.shop_requested = True

        return {
            "success": True,
            "message": "Opening shop interface",
            "shop_type": npc.shop.shop_type,
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
        """Accept an item from the player, checking for deliver objectives and bonus rewards."""
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

        # Check if this completes a deliver objective
        deliver_result = quest_manager.complete_deliver_objective(npc.id, item_id)
        if deliver_result.get("success"):
            # Remove item from player inventory
            item_holder.inventory.remove_item(item_id)
            print_status_message(
                f"🎁 Gave {item_id} to {npc.display_name}", "success"
            )
            return {
                "success": True,
                "item_received": item_id,
                "deliver_objective_completed": True,
                "quest_id": deliver_result.get("quest_id"),
                "quest_name": deliver_result.get("quest_name"),
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

        # Block transfer of quest items that don't have a matching objective
        inv_item = item_holder.inventory.items.get(item_id)
        if inv_item and inv_item.quest_item:
            return {
                "success": False,
                "error": (
                    f"Cannot give away {item_id} - it is a quest item needed "
                    "for progression. Quest items can only be given to NPCs "
                    "when a quest objective specifically requires it."
                ),
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
