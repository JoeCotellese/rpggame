# ABOUTME: Unit tests for NPC data model classes
# ABOUTME: Tests NPC, NPCPersonality, NPCKnowledge, NPCShop creation and serialization

import pytest

from dnd_engine.core.npc import NPC, NPCKnowledge, NPCPersonality, NPCShop, ShopItem


class TestNPCPersonality:
    """Tests for NPCPersonality dataclass."""

    def test_from_dict_complete(self):
        """Test creating personality from complete dict."""
        data = {
            "traits": ["warm", "friendly"],
            "speech_style": "casual",
            "attitude_default": "friendly",
            "suspicion_of_strangers": "mild",
        }
        personality = NPCPersonality.from_dict(data)

        assert personality.traits == ["warm", "friendly"]
        assert personality.speech_style == "casual"
        assert personality.attitude_default == "friendly"
        assert personality.suspicion_of_strangers == "mild"

    def test_from_dict_minimal(self):
        """Test creating personality with defaults."""
        data = {}
        personality = NPCPersonality.from_dict(data)

        assert personality.traits == []
        assert personality.speech_style == ""
        assert personality.attitude_default == "neutral"
        assert personality.suspicion_of_strangers == "none"

    def test_to_prompt_text(self):
        """Test generating prompt text from personality."""
        personality = NPCPersonality(
            traits=["gruff", "honest"],
            speech_style="military",
            attitude_default="hostile",
            suspicion_of_strangers="high",
        )
        text = personality.to_prompt_text()

        assert "gruff" in text
        assert "honest" in text
        assert "military" in text
        assert "hostile" in text


class TestNPCKnowledge:
    """Tests for NPCKnowledge dataclass."""

    def test_from_dict_complete(self):
        """Test creating knowledge from complete dict."""
        data = {
            "general": ["knows local history"],
            "quest_hooks": ["quest_a", "quest_b"],
            "local_lore": ["old legends"],
        }
        knowledge = NPCKnowledge.from_dict(data)

        assert knowledge.general == ["knows local history"]
        assert knowledge.quest_hooks == ["quest_a", "quest_b"]
        assert knowledge.local_lore == ["old legends"]

    def test_from_dict_empty(self):
        """Test creating knowledge with defaults."""
        knowledge = NPCKnowledge.from_dict({})

        assert knowledge.general == []
        assert knowledge.quest_hooks == []
        assert knowledge.local_lore == []

    def test_to_prompt_text(self):
        """Test generating prompt text from knowledge."""
        knowledge = NPCKnowledge(
            general=["fact1", "fact2"],
            quest_hooks=["quest1"],
            local_lore=["lore1"],
        )
        text = knowledge.to_prompt_text()

        assert "fact1" in text
        assert "fact2" in text
        assert "lore1" in text


class TestNPCShop:
    """Tests for NPCShop dataclass."""

    def test_from_dict_enabled_shop(self):
        """Test creating an enabled shop from dict."""
        data = {
            "enabled": True,
            "shop_type": "tavern",
            "inventory": [{"item_id": "ale", "price": 2, "stock": -1}],
            "buy_rate": 0.5,
            "sell_dialogue": "What'll ya have?",
            "insufficient_funds_dialogue": "Not enough gold!",
        }
        shop = NPCShop.from_dict(data)

        assert shop.enabled is True
        assert shop.shop_type == "tavern"
        assert len(shop.inventory) == 1
        assert isinstance(shop.inventory[0], ShopItem)
        assert shop.inventory[0].item_id == "ale"
        assert shop.inventory[0].price == 2
        assert shop.buy_rate == 0.5
        assert shop.sell_dialogue == "What'll ya have?"

    def test_from_dict_disabled_shop(self):
        """Test creating a disabled shop from dict."""
        data = {"enabled": False}
        shop = NPCShop.from_dict(data)

        assert shop.enabled is False
        assert shop.inventory == []

    def test_from_dict_defaults(self):
        """Test creating shop with defaults."""
        shop = NPCShop.from_dict({})

        assert shop.enabled is False
        assert shop.shop_type == "general"  # Default is "general"
        assert shop.inventory == []
        assert shop.buy_rate == 0.5


class TestNPC:
    """Tests for NPC dataclass."""

    @pytest.fixture
    def sample_npc_data(self):
        """Sample NPC data for tests."""
        return {
            "id": "marta_innkeeper",
            "name": "Marta",
            "display_name": "Marta, the Innkeeper",
            "home_location": "arden.inn_common_room",
            "current_location": "arden.inn_common_room",
            "can_move": False,
            "personality": {
                "traits": ["warm", "maternal"],
                "speech_style": "folksy",
                "attitude_default": "friendly",
                "suspicion_of_strangers": "mild",
            },
            "knowledge": {
                "general": ["Runs the inn for 20 years"],
                "quest_hooks": ["investigate_crypt"],
                "local_lore": ["The Davos family history"],
            },
            "shop": {
                "enabled": True,
                "shop_type": "tavern",
                "inventory": [{"item_id": "ale", "price": 2, "stock": -1}],
                "buy_rate": 0.5,
                "sell_dialogue": "What can I get you, dearie?",
                "insufficient_funds_dialogue": "Oh dearie, you're a bit short.",
            },
            "dialogue": {
                "greeting": "Welcome to the Rusty Tankard!",
                "farewell": "Safe travels, dearie!",
            },
        }

    @pytest.fixture
    def minimal_npc_data(self):
        """Minimal NPC data with required fields."""
        return {
            "id": "test_npc",
            "name": "Test",
            "home_location": "test.room",
        }

    def test_from_dict_complete(self, sample_npc_data):
        """Test creating NPC from complete dict."""
        npc = NPC.from_dict(sample_npc_data)

        assert npc.id == "marta_innkeeper"
        assert npc.name == "Marta"
        assert npc.display_name == "Marta, the Innkeeper"
        assert npc.home_location == "arden.inn_common_room"
        assert npc.current_location == "arden.inn_common_room"
        assert npc.can_move is False
        assert "warm" in npc.personality.traits
        assert "investigate_crypt" in npc.knowledge.quest_hooks
        assert npc.shop.enabled is True
        assert npc.player_reputation == 0

    def test_from_dict_minimal(self, minimal_npc_data):
        """Test creating NPC with minimal data."""
        npc = NPC.from_dict(minimal_npc_data)

        assert npc.id == "test_npc"
        assert npc.name == "Test"
        assert npc.display_name == "Test"  # Defaults to name
        assert npc.home_location == "test.room"
        assert npc.current_location == "test.room"  # Defaults to home_location
        assert npc.can_move is False
        assert npc.shop is None

    def test_to_dict_saves_runtime_state(self, sample_npc_data):
        """Test serializing NPC saves runtime state only."""
        npc = NPC.from_dict(sample_npc_data)
        npc.current_location = "arden.town_square"
        npc.player_reputation = 15

        result = npc.to_dict()

        # Runtime state fields
        assert result["id"] == "marta_innkeeper"
        assert result["current_location"] == "arden.town_square"
        assert result["player_reputation"] == 15
        # Shop stock should be included
        assert "shop_stock" in result

    def test_get_greeting(self, sample_npc_data):
        """Test getting NPC greeting."""
        npc = NPC.from_dict(sample_npc_data)

        greeting = npc.get_greeting()
        assert greeting == "Welcome to the Rusty Tankard!"

    def test_get_greeting_default(self, minimal_npc_data):
        """Test default greeting when not specified."""
        npc = NPC.from_dict(minimal_npc_data)

        greeting = npc.get_greeting()
        assert "Test" in greeting

    def test_get_farewell(self, sample_npc_data):
        """Test getting NPC farewell."""
        npc = NPC.from_dict(sample_npc_data)

        farewell = npc.get_farewell()
        assert farewell == "Safe travels, dearie!"

    def test_get_farewell_default(self, minimal_npc_data):
        """Test default farewell when not specified."""
        npc = NPC.from_dict(minimal_npc_data)

        farewell = npc.get_farewell()
        assert farewell == "Goodbye."

    def test_get_disposition_friendly(self, sample_npc_data):
        """Test disposition calculation for friendly NPC."""
        sample_npc_data["reputation_modifiers"] = {
            "friendly_threshold": 10,
            "hostile_threshold": -20,
        }
        npc = NPC.from_dict(sample_npc_data)

        # Default reputation is 0, disposition is neutral
        assert npc.get_disposition().value == "neutral"

        # Increase reputation above friendly threshold
        npc.player_reputation = 15
        assert npc.get_disposition().value == "friendly"

    def test_get_disposition_hostile(self, sample_npc_data):
        """Test disposition calculation for hostile NPC."""
        sample_npc_data["reputation_modifiers"] = {
            "friendly_threshold": 10,
            "hostile_threshold": -10,
        }
        npc = NPC.from_dict(sample_npc_data)

        # Decrease reputation below hostile threshold
        npc.player_reputation = -15
        assert npc.get_disposition().value == "hostile"

    def test_build_system_prompt(self, sample_npc_data):
        """Test building system prompt for LLM."""
        npc = NPC.from_dict(sample_npc_data)

        prompt = npc.build_system_prompt()

        # Check key elements are in the prompt
        assert "Marta" in prompt
        assert "warm" in prompt
        assert "folksy" in prompt

    def test_build_system_prompt_with_shop(self, sample_npc_data):
        """Test system prompt includes shop info when enabled."""
        npc = NPC.from_dict(sample_npc_data)

        prompt = npc.build_system_prompt()

        assert "tavern" in prompt.lower() or "shop" in prompt.lower()

    def test_move_to(self, sample_npc_data):
        """Test NPC movement when allowed."""
        sample_npc_data["can_move"] = True
        npc = NPC.from_dict(sample_npc_data)

        npc.move_to("arden.town_square")
        assert npc.current_location == "arden.town_square"

    def test_move_to_blocked_when_cannot_move(self, sample_npc_data):
        """Test NPC movement is blocked when can_move is False."""
        sample_npc_data["can_move"] = False
        npc = NPC.from_dict(sample_npc_data)
        original = npc.current_location

        npc.move_to("arden.town_square")
        assert npc.current_location == original

    def test_return_home(self, sample_npc_data):
        """Test NPC returning home."""
        sample_npc_data["can_move"] = True
        npc = NPC.from_dict(sample_npc_data)
        npc.move_to("arden.town_square")

        npc.return_home()
        assert npc.current_location == "arden.inn_common_room"
