# ABOUTME: Integration tests for NPCChatManager class
# ABOUTME: Tests NPC chat workflow with mocked LLM provider

from unittest.mock import AsyncMock, Mock

import pytest

from dnd_engine.core.npc import NPC
from dnd_engine.llm.npc_chat import NPC_TOOLS, ConversationState, NPCChatManager


class TestConversationState:
    """Tests for ConversationState dataclass."""

    def test_initial_state(self):
        """Test conversation state initialization."""
        npc = NPC.from_dict(
            {
                "id": "test",
                "name": "Test NPC",
                "home_location": "test.room",
            }
        )
        state = ConversationState(npc=npc)

        assert state.npc == npc
        assert state.messages == []
        assert state.ended is False
        assert state.end_reason is None


class TestNPCTools:
    """Tests for NPC tool definitions."""

    def test_tools_have_required_fields(self):
        """Test that all tools have required OpenAI format fields."""
        for tool in NPC_TOOLS:
            assert "type" in tool
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]

    def test_expected_tools_present(self):
        """Test that expected tools are defined."""
        tool_names = [t["function"]["name"] for t in NPC_TOOLS]

        assert "activate_quest" in tool_names
        assert "get_available_quests" in tool_names
        assert "open_shop" in tool_names
        assert "get_player_gold" in tool_names
        assert "charge_gold" in tool_names
        assert "give_item" in tool_names
        assert "check_reputation" in tool_names


class TestNPCChatManagerWithoutProvider:
    """Tests for NPCChatManager fallback behavior (no LLM)."""

    @pytest.fixture
    def sample_npc(self):
        """Create a sample NPC for testing."""
        return NPC.from_dict(
            {
                "id": "marta_innkeeper",
                "name": "Marta",
                "display_name": "Marta, the Innkeeper",
                "home_location": "arden.inn_common_room",
                "dialogue": {
                    "greeting": "Welcome to my inn!",
                    "farewell": "Safe travels!",
                },
            }
        )

    @pytest.fixture
    def mock_game_state(self):
        """Create mock game state."""
        mock = Mock()
        mock.quest_manager = None
        mock.party.characters = []
        return mock

    @pytest.fixture
    def manager_no_llm(self, mock_game_state):
        """Create NPCChatManager without LLM provider."""
        return NPCChatManager(provider=None, game_state=mock_game_state)

    def test_start_conversation_returns_greeting(self, manager_no_llm, sample_npc):
        """Test starting conversation returns NPC greeting without LLM."""
        greeting = manager_no_llm.start_conversation_sync(sample_npc)

        assert greeting == "Welcome to my inn!"

    def test_send_message_returns_fallback(self, manager_no_llm, sample_npc):
        """Test sending message returns fallback without LLM."""
        manager_no_llm.start_conversation_sync(sample_npc)
        response, ended = manager_no_llm.send_message_sync("hello")

        assert response == "Hmm, I'm not sure what to say to that."
        assert ended is False

    def test_farewell_words_end_conversation(self, manager_no_llm, sample_npc):
        """Test farewell words trigger conversation end."""
        manager_no_llm.start_conversation_sync(sample_npc)
        response, ended = manager_no_llm.send_message_sync("goodbye")

        assert response == "Safe travels!"
        assert ended is True

    def test_get_current_npc(self, manager_no_llm, sample_npc):
        """Test getting current conversation NPC."""
        assert manager_no_llm.get_current_npc() is None

        manager_no_llm.start_conversation_sync(sample_npc)
        assert manager_no_llm.get_current_npc() == sample_npc

    def test_end_conversation_clears_state(self, manager_no_llm, sample_npc):
        """Test ending conversation clears current NPC."""
        manager_no_llm.start_conversation_sync(sample_npc)
        manager_no_llm.end_conversation()

        assert manager_no_llm.get_current_npc() is None


class TestNPCChatManagerToolHandlers:
    """Tests for NPCChatManager tool handlers."""

    @pytest.fixture
    def sample_npc(self):
        """Create a sample NPC for testing."""
        return NPC.from_dict(
            {
                "id": "marta_innkeeper",
                "name": "Marta",
                "display_name": "Marta, the Innkeeper",
                "home_location": "arden.inn_common_room",
                "knowledge": {
                    "quest_hooks": ["investigate_crypt"],
                },
            }
        )

    @pytest.fixture
    def mock_character(self):
        """Create mock character with inventory."""
        char = Mock()
        char.name = "Hero"
        char.inventory = Mock()
        char.inventory.gold = 100
        return char

    @pytest.fixture
    def mock_game_state(self, mock_character):
        """Create mock game state with quest manager."""
        mock = Mock()

        # Quest manager
        mock_quest = Mock()
        mock_quest.id = "investigate_crypt"
        mock_quest.name = "Investigate the Crypt"
        mock_quest.description = "Something evil stirs..."
        # Return empty dict for completion_criteria.get() to avoid Mock iteration
        mock_quest.completion_criteria = {"npc_hints": {}}

        mock.quest_manager = Mock()
        mock.quest_manager.quests = {"investigate_crypt": mock_quest}
        mock.quest_manager.get_quest_state.return_value = Mock(value="available")
        mock.quest_manager.activate_quest.return_value = True

        # Party
        mock.party = Mock()
        mock.party.characters = [mock_character]

        return mock

    @pytest.fixture
    def manager(self, mock_game_state):
        """Create NPCChatManager with mock game state."""
        return NPCChatManager(provider=None, game_state=mock_game_state)

    def test_handle_activate_quest_success(self, manager, sample_npc):
        """Test successful quest activation."""
        manager._current_conversation = ConversationState(npc=sample_npc)

        result = manager._handle_activate_quest("investigate_crypt")

        assert result["success"] is True
        assert result["quest_name"] == "Investigate the Crypt"

    def test_handle_activate_quest_unknown(self, manager, sample_npc):
        """Test activating unknown quest."""
        manager._current_conversation = ConversationState(npc=sample_npc)

        result = manager._handle_activate_quest("unknown_quest")

        assert result["success"] is False
        assert "Unknown quest" in result["error"]

    def test_handle_get_available_quests(self, manager, sample_npc):
        """Test getting available quests."""
        manager._current_conversation = ConversationState(npc=sample_npc)

        result = manager._handle_get_available_quests()

        assert "quests" in result
        assert len(result["quests"]) == 1
        assert result["quests"][0]["id"] == "investigate_crypt"

    def test_handle_get_player_gold(self, manager):
        """Test getting player gold total."""
        result = manager._handle_get_player_gold()

        assert result["gold"] == 100

    def test_handle_charge_gold_success(self, manager):
        """Test charging gold successfully."""
        result = manager._handle_charge_gold(amount=25, reason="room for the night")

        assert result["success"] is True
        assert result["charged"] == 25
        assert result["reason"] == "room for the night"
        assert result["remaining_gold"] == 75

    def test_handle_charge_gold_insufficient(self, manager):
        """Test charging gold when party doesn't have enough."""
        result = manager._handle_charge_gold(amount=200, reason="expensive item")

        assert result["success"] is False
        assert result["error"] == "Insufficient gold"
        assert result["party_gold"] == 100
        assert result["amount_needed"] == 200

    def test_handle_charge_gold_invalid_amount(self, manager):
        """Test charging zero or negative gold."""
        result = manager._handle_charge_gold(amount=0, reason="free")

        assert result["success"] is False
        assert "positive" in result["error"]

    def test_handle_open_shop_no_conversation(self, manager, mock_character):
        """Test open_shop fails without active conversation."""
        result = manager._handle_open_shop()

        assert result["success"] is False
        assert "No active conversation" in result["error"]

    def test_handle_open_shop_npc_has_no_shop(self, manager, sample_npc):
        """Test open_shop fails if NPC has no shop."""
        from dnd_engine.llm.npc_chat import ConversationState

        manager._current_conversation = ConversationState(npc=sample_npc)

        result = manager._handle_open_shop()

        assert result["success"] is False
        assert "doesn't have a shop" in result["error"]

    def test_handle_check_reputation(self, manager, sample_npc):
        """Test checking reputation."""
        manager._current_conversation = ConversationState(npc=sample_npc)
        sample_npc.player_reputation = 5

        result = manager._handle_check_reputation()

        assert result["reputation"] == 5
        assert result["disposition"] == "neutral"

    def test_dispatch_unknown_tool(self, manager):
        """Test dispatching unknown tool returns error."""
        result = manager._dispatch_tool("unknown_tool", {})

        assert result["success"] is False
        assert "Unknown tool" in result["error"]

    # === Quest Reward Tool Handler Tests ===

    def test_handle_turn_in_quest_success(self, manager, sample_npc, mock_character):
        """Test successful quest turn-in awards gold."""
        manager._current_conversation = ConversationState(npc=sample_npc)

        # Configure mock to return successful claim
        manager.game_state.quest_manager.claim_quest_reward.return_value = {
            "success": True,
            "quest_name": "Investigate the Crypt",
            "reward_gold": 50,
        }

        result = manager._handle_turn_in_quest("investigate_crypt")

        assert result["success"] is True
        assert result["quest_name"] == "Investigate the Crypt"
        assert result["reward_gold"] == 50
        # Gold should be added to party leader
        assert mock_character.inventory.gold == 150

    def test_handle_turn_in_quest_wrong_npc(self, manager, sample_npc):
        """Test turn-in fails when talking to wrong NPC."""
        manager._current_conversation = ConversationState(npc=sample_npc)

        # Configure mock to return failure (wrong NPC)
        manager.game_state.quest_manager.claim_quest_reward.return_value = {
            "success": False,
            "error": "This quest must be turned in to Father Aldric",
        }

        result = manager._handle_turn_in_quest("investigate_crypt")

        assert result["success"] is False
        assert "Father Aldric" in result["error"]

    def test_handle_turn_in_quest_not_completed(self, manager, sample_npc):
        """Test turn-in fails when quest not completed."""
        manager._current_conversation = ConversationState(npc=sample_npc)

        manager.game_state.quest_manager.claim_quest_reward.return_value = {
            "success": False,
            "error": "Quest 'investigate_crypt' is not completed",
        }

        result = manager._handle_turn_in_quest("investigate_crypt")

        assert result["success"] is False
        assert "not completed" in result["error"]

    def test_handle_turn_in_quest_no_conversation(self, manager):
        """Test turn-in fails without active conversation."""
        result = manager._handle_turn_in_quest("investigate_crypt")

        assert result["success"] is False
        assert "No active conversation" in result["error"]

    def test_handle_get_pending_rewards_with_quests(self, manager, sample_npc):
        """Test getting pending rewards returns completed quests."""
        manager._current_conversation = ConversationState(npc=sample_npc)

        # Create mock completed quests
        mock_quest1 = Mock()
        mock_quest1.id = "investigate_crypt"
        mock_quest1.name = "Investigate the Crypt"
        mock_quest1.reward_gold = 50

        mock_quest2 = Mock()
        mock_quest2.id = "clear_cellar"
        mock_quest2.name = "Rat Problem"
        mock_quest2.reward_gold = 25

        manager.game_state.quest_manager.get_quests_awaiting_reward.return_value = [
            mock_quest1,
            mock_quest2,
        ]

        result = manager._handle_get_pending_rewards()

        assert len(result["pending_rewards"]) == 2
        assert result["pending_rewards"][0]["quest_id"] == "investigate_crypt"
        assert result["pending_rewards"][0]["reward_gold"] == 50
        assert result["pending_rewards"][1]["quest_id"] == "clear_cellar"

    def test_handle_get_pending_rewards_empty(self, manager, sample_npc):
        """Test getting pending rewards when none available."""
        manager._current_conversation = ConversationState(npc=sample_npc)

        manager.game_state.quest_manager.get_quests_awaiting_reward.return_value = []

        result = manager._handle_get_pending_rewards()

        assert result["pending_rewards"] == []

    def test_handle_get_pending_rewards_no_conversation(self, manager):
        """Test getting pending rewards without conversation."""
        result = manager._handle_get_pending_rewards()

        assert result["pending_rewards"] == []

    def test_handle_receive_item_delivers_objective(self, manager, sample_npc, mock_character):
        """Test receiving item completes deliver objective."""
        manager._current_conversation = ConversationState(npc=sample_npc)

        # Character has the item
        mock_character.inventory.has_item.return_value = True

        # Deliver objective succeeds
        manager.game_state.quest_manager.complete_deliver_objective.return_value = {
            "success": True,
            "quest_id": "analyze_research",
            "quest_name": "Dangerous Knowledge",
        }

        result = manager._handle_receive_item_from_player("volatile_compound")

        assert result["success"] is True
        assert result["deliver_objective_completed"] is True
        assert result["quest_id"] == "analyze_research"
        # Item should be removed from inventory
        mock_character.inventory.remove_item.assert_called_with("volatile_compound")

    def test_handle_receive_item_bonus_reward(self, manager, sample_npc, mock_character):
        """Test receiving item triggers bonus reward."""
        manager._current_conversation = ConversationState(npc=sample_npc)

        # Character has the item
        mock_character.inventory.has_item.return_value = True

        # Deliver objective fails (not a deliver item)
        manager.game_state.quest_manager.complete_deliver_objective.return_value = {
            "success": False,
        }

        # But it's a bonus reward item
        mock_quest = Mock()
        mock_quest.id = "stop_the_alchemist"
        mock_bonus = Mock()
        mock_bonus.reward_item = "potion_of_healing"
        mock_bonus.description = "Thanks for the specimen!"

        manager.game_state.quest_manager.check_bonus_reward.return_value = (
            mock_quest,
            mock_bonus,
        )

        # Mock item category lookup
        manager.game_state._get_item_category.return_value = "consumables"

        result = manager._handle_receive_item_from_player("preserved_specimen")

        assert result["success"] is True
        assert result["bonus_reward"] is True
        assert result["reward_item"] == "potion_of_healing"
        # Item removed from giver, reward added to recipient
        mock_character.inventory.remove_item.assert_called_with("preserved_specimen")
        mock_character.inventory.add_item.assert_called_with("potion_of_healing", "consumables")

    def test_handle_receive_item_no_special_reward(self, manager, sample_npc, mock_character):
        """Test receiving item with no quest reward."""
        manager._current_conversation = ConversationState(npc=sample_npc)

        mock_character.inventory.has_item.return_value = True

        # Not a deliver objective
        manager.game_state.quest_manager.complete_deliver_objective.return_value = {
            "success": False,
        }
        # Not a bonus reward either
        manager.game_state.quest_manager.check_bonus_reward.return_value = (None, None)

        # Mock inventory items dict - item is NOT a quest item
        mock_inv_item = Mock()
        mock_inv_item.quest_item = False
        mock_character.inventory.items = {"random_item": mock_inv_item}

        result = manager._handle_receive_item_from_player("random_item")

        assert result["success"] is True
        assert result["bonus_reward"] is False
        mock_character.inventory.remove_item.assert_called_with("random_item")

    def test_handle_receive_item_blocks_quest_items(self, manager, sample_npc, mock_character):
        """Test that quest items cannot be given away without a matching objective."""
        manager._current_conversation = ConversationState(npc=sample_npc)

        mock_character.inventory.has_item.return_value = True

        # Not a deliver objective
        manager.game_state.quest_manager.complete_deliver_objective.return_value = {
            "success": False,
        }
        # Not a bonus reward either
        manager.game_state.quest_manager.check_bonus_reward.return_value = (None, None)

        # Mock inventory items dict - item IS a quest item
        mock_inv_item = Mock()
        mock_inv_item.quest_item = True
        mock_character.inventory.items = {"gorgus_journal": mock_inv_item}

        result = manager._handle_receive_item_from_player("gorgus_journal")

        assert result["success"] is False
        assert "quest item" in result["error"]
        # Item should NOT be removed
        mock_character.inventory.remove_item.assert_not_called()

    def test_handle_receive_item_not_in_inventory(self, manager, sample_npc, mock_character):
        """Test receiving item fails if party doesn't have it."""
        manager._current_conversation = ConversationState(npc=sample_npc)

        mock_character.inventory.has_item.return_value = False

        result = manager._handle_receive_item_from_player("missing_item")

        assert result["success"] is False
        assert "does not have item" in result["error"]

    def test_handle_receive_item_no_conversation(self, manager):
        """Test receiving item fails without conversation."""
        result = manager._handle_receive_item_from_player("some_item")

        assert result["success"] is False
        assert "No active conversation" in result["error"]


class TestNPCChatManagerWithMockedProvider:
    """Tests for NPCChatManager with mocked LLM provider."""

    @pytest.fixture
    def sample_npc(self):
        """Create a sample NPC for testing."""
        return NPC.from_dict(
            {
                "id": "marta_innkeeper",
                "name": "Marta",
                "display_name": "Marta, the Innkeeper",
                "home_location": "arden.inn_common_room",
                "personality": {
                    "traits": ["warm"],
                    "speech_style": "folksy",
                },
                "dialogue": {
                    "greeting": "Welcome!",
                    "farewell": "Goodbye!",
                },
            }
        )

    @pytest.fixture
    def mock_provider(self):
        """Create mock LLM provider."""
        mock = Mock()
        # Mock the async chat_with_tools method
        mock.chat_with_tools = AsyncMock(
            return_value={
                "content": "Hello, welcome to my inn!",
                "tool_calls": [],
                "finish_reason": "stop",
            }
        )
        return mock

    @pytest.fixture
    def mock_game_state(self):
        """Create mock game state."""
        mock = Mock()
        mock.quest_manager = None
        mock.party = Mock()
        mock.party.characters = []
        return mock

    @pytest.fixture
    def manager(self, mock_provider, mock_game_state):
        """Create NPCChatManager with mocked provider."""
        return NPCChatManager(provider=mock_provider, game_state=mock_game_state)

    def test_start_conversation_calls_provider(self, manager, sample_npc, mock_provider):
        """Test that starting conversation calls LLM provider."""
        greeting = manager.start_conversation_sync(sample_npc, timeout=5.0)

        # Should have called chat_with_tools
        assert mock_provider.chat_with_tools.called
        assert greeting == "Hello, welcome to my inn!"

    def test_conversation_builds_messages(self, manager, sample_npc, mock_provider):
        """Test that conversation builds message history."""
        manager.start_conversation_sync(sample_npc, timeout=5.0)

        # Check that messages were built
        assert manager._current_conversation is not None
        messages = manager._current_conversation.messages

        # Should have system message, user message, and assistant response
        assert len(messages) >= 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_send_message_adds_to_history(self, manager, sample_npc, mock_provider):
        """Test that sending message adds to conversation history."""
        manager.start_conversation_sync(sample_npc, timeout=5.0)

        # Reset mock for second call
        mock_provider.chat_with_tools.reset_mock()
        mock_provider.chat_with_tools.return_value = {
            "content": "Of course, dearie!",
            "tool_calls": [],
            "finish_reason": "stop",
        }

        response, ended = manager.send_message_sync("Can I have some ale?", timeout=5.0)

        assert response == "Of course, dearie!"
        assert ended is False
        # Message history should have grown
        assert len(manager._current_conversation.messages) > 3
