# ABOUTME: Tests for the quest state system that tracks quest progression.
# ABOUTME: Verifies quest states (locked/available/active/completed) and transitions.

import pytest
from pathlib import Path
import tempfile
import json

from dnd_engine.core.quest import BonusReward, Quest, QuestState, QuestManager


class TestQuestState:
    """Test the QuestState enum."""

    def test_quest_states_exist(self):
        """All four quest states should be defined."""
        assert QuestState.LOCKED.value == "locked"
        assert QuestState.AVAILABLE.value == "available"
        assert QuestState.ACTIVE.value == "active"
        assert QuestState.COMPLETED.value == "completed"


class TestQuest:
    """Test the Quest dataclass."""

    def test_quest_creation_with_required_fields(self):
        """Quest should be creatable with required fields."""
        quest = Quest(
            id="test_quest",
            name="Test Quest",
            description="A test quest"
        )
        assert quest.id == "test_quest"
        assert quest.name == "Test Quest"
        assert quest.description == "A test quest"
        assert quest.unlocked_by_default is False
        assert quest.unlock_requirements is None
        assert quest.target_dungeon is None
        assert quest.completion_criteria == {}
        assert quest.unlocks_quests == []

    def test_quest_creation_with_all_fields(self):
        """Quest should support all optional fields."""
        quest = Quest(
            id="investigate_crypt",
            name="The Crypt Problem",
            description="Investigate the disturbances at the old cemetery",
            unlocked_by_default=True,
            unlock_requirements=None,
            target_dungeon="the_unquiet_dead_crypt",
            completion_criteria={"dungeon_completed": "the_unquiet_dead_crypt"},
            unlocks_quests=["cult_conspiracy"]
        )
        assert quest.unlocked_by_default is True
        assert quest.target_dungeon == "the_unquiet_dead_crypt"
        assert quest.completion_criteria == {"dungeon_completed": "the_unquiet_dead_crypt"}
        assert quest.unlocks_quests == ["cult_conspiracy"]

    def test_quest_from_dict(self):
        """Quest should be loadable from dictionary."""
        data = {
            "id": "test_quest",
            "name": "Test Quest",
            "description": "A test quest",
            "unlocked_by_default": True,
            "target_dungeon": "test_dungeon"
        }
        quest = Quest.from_dict(data)
        assert quest.id == "test_quest"
        assert quest.unlocked_by_default is True
        assert quest.target_dungeon == "test_dungeon"

    def test_quest_to_dict(self):
        """Quest should be serializable to dictionary."""
        quest = Quest(
            id="test_quest",
            name="Test Quest",
            description="A test quest",
            unlocked_by_default=True
        )
        data = quest.to_dict()
        assert data["id"] == "test_quest"
        assert data["unlocked_by_default"] is True


class TestQuestManager:
    """Test the QuestManager class."""

    @pytest.fixture
    def quest_data(self):
        """Sample quest definitions for testing."""
        return {
            "quests": [
                {
                    "id": "investigate_crypt",
                    "name": "The Crypt Problem",
                    "description": "Investigate the disturbances at the old cemetery",
                    "unlocked_by_default": True,
                    "target_dungeon": "the_unquiet_dead_crypt",
                    "completion_criteria": {
                        "dungeon_completed": "the_unquiet_dead_crypt"
                    },
                    "unlocks_quests": ["cult_conspiracy"]
                },
                {
                    "id": "cult_conspiracy",
                    "name": "The Cult Conspiracy",
                    "description": "Follow the trail to the cult hideout",
                    "unlocked_by_default": False,
                    "unlock_requirements": {
                        "quest_completed": "investigate_crypt"
                    },
                    "target_dungeon": "cult_hideout",
                    "completion_criteria": {
                        "dungeon_completed": "cult_hideout"
                    },
                    "unlocks_quests": ["temple_assault"]
                },
                {
                    "id": "temple_assault",
                    "name": "Temple of Durgon",
                    "description": "Assault the temple and stop the ritual",
                    "unlocked_by_default": False,
                    "unlock_requirements": {
                        "quest_completed": "cult_conspiracy"
                    },
                    "target_dungeon": "temple_of_durgon",
                    "completion_criteria": {
                        "dungeon_completed": "temple_of_durgon"
                    },
                    "unlocks_quests": []
                }
            ]
        }

    @pytest.fixture
    def quest_manager(self, quest_data):
        """Create a QuestManager with test data."""
        manager = QuestManager()
        manager.load_quests_from_dict(quest_data)
        return manager

    def test_load_quests(self, quest_manager):
        """QuestManager should load quest definitions."""
        assert len(quest_manager.quests) == 3
        assert "investigate_crypt" in quest_manager.quests
        assert "cult_conspiracy" in quest_manager.quests
        assert "temple_assault" in quest_manager.quests

    def test_initial_quest_states(self, quest_manager):
        """Default-unlocked quests should be available, others locked."""
        assert quest_manager.get_quest_state("investigate_crypt") == QuestState.AVAILABLE
        assert quest_manager.get_quest_state("cult_conspiracy") == QuestState.LOCKED
        assert quest_manager.get_quest_state("temple_assault") == QuestState.LOCKED

    def test_get_quest_state_unknown_quest(self, quest_manager):
        """Getting state of unknown quest should raise error."""
        with pytest.raises(KeyError):
            quest_manager.get_quest_state("nonexistent_quest")

    def test_activate_quest(self, quest_manager):
        """Activating an available quest should move it to active."""
        result = quest_manager.activate_quest("investigate_crypt")
        assert result is True
        assert quest_manager.get_quest_state("investigate_crypt") == QuestState.ACTIVE

    def test_activate_locked_quest_fails(self, quest_manager):
        """Cannot activate a locked quest."""
        result = quest_manager.activate_quest("cult_conspiracy")
        assert result is False
        assert quest_manager.get_quest_state("cult_conspiracy") == QuestState.LOCKED

    def test_activate_already_active_quest(self, quest_manager):
        """Activating an already active quest should return True but no state change."""
        quest_manager.activate_quest("investigate_crypt")
        result = quest_manager.activate_quest("investigate_crypt")
        assert result is True
        assert quest_manager.get_quest_state("investigate_crypt") == QuestState.ACTIVE

    def test_activate_completed_quest_fails(self, quest_manager):
        """Cannot re-activate a completed quest."""
        quest_manager.activate_quest("investigate_crypt")
        quest_manager.complete_quest("investigate_crypt")
        result = quest_manager.activate_quest("investigate_crypt")
        assert result is False
        assert quest_manager.get_quest_state("investigate_crypt") == QuestState.COMPLETED

    def test_complete_quest(self, quest_manager):
        """Completing an active quest should move it to completed."""
        quest_manager.activate_quest("investigate_crypt")
        unlocked = quest_manager.complete_quest("investigate_crypt")
        assert quest_manager.get_quest_state("investigate_crypt") == QuestState.COMPLETED
        assert "cult_conspiracy" in unlocked

    def test_complete_quest_unlocks_dependent_quests(self, quest_manager):
        """Completing a quest should unlock quests that depend on it."""
        quest_manager.activate_quest("investigate_crypt")
        quest_manager.complete_quest("investigate_crypt")

        # cult_conspiracy should now be available
        assert quest_manager.get_quest_state("cult_conspiracy") == QuestState.AVAILABLE
        # temple_assault still locked (needs cult_conspiracy)
        assert quest_manager.get_quest_state("temple_assault") == QuestState.LOCKED

    def test_complete_inactive_quest_fails(self, quest_manager):
        """Cannot complete a quest that isn't active."""
        unlocked = quest_manager.complete_quest("investigate_crypt")
        assert unlocked == []
        assert quest_manager.get_quest_state("investigate_crypt") == QuestState.AVAILABLE

    def test_get_available_quests(self, quest_manager):
        """Should return only available quests."""
        available = quest_manager.get_available_quests()
        assert len(available) == 1
        assert available[0].id == "investigate_crypt"

    def test_get_active_quests(self, quest_manager):
        """Should return only active quests."""
        quest_manager.activate_quest("investigate_crypt")
        active = quest_manager.get_active_quests()
        assert len(active) == 1
        assert active[0].id == "investigate_crypt"

    def test_get_completed_quests(self, quest_manager):
        """Should return only completed quests."""
        quest_manager.activate_quest("investigate_crypt")
        quest_manager.complete_quest("investigate_crypt")
        completed = quest_manager.get_completed_quests()
        assert len(completed) == 1
        assert completed[0].id == "investigate_crypt"

    def test_full_campaign_progression(self, quest_manager):
        """Test full progression through all three quests."""
        # Start: only first quest available
        assert quest_manager.get_quest_state("investigate_crypt") == QuestState.AVAILABLE
        assert quest_manager.get_quest_state("cult_conspiracy") == QuestState.LOCKED
        assert quest_manager.get_quest_state("temple_assault") == QuestState.LOCKED

        # Activate and complete first quest
        quest_manager.activate_quest("investigate_crypt")
        quest_manager.complete_quest("investigate_crypt")
        assert quest_manager.get_quest_state("investigate_crypt") == QuestState.COMPLETED
        assert quest_manager.get_quest_state("cult_conspiracy") == QuestState.AVAILABLE

        # Activate and complete second quest
        quest_manager.activate_quest("cult_conspiracy")
        quest_manager.complete_quest("cult_conspiracy")
        assert quest_manager.get_quest_state("cult_conspiracy") == QuestState.COMPLETED
        assert quest_manager.get_quest_state("temple_assault") == QuestState.AVAILABLE

        # Activate and complete third quest
        quest_manager.activate_quest("temple_assault")
        quest_manager.complete_quest("temple_assault")
        assert quest_manager.get_quest_state("temple_assault") == QuestState.COMPLETED

        # All quests completed
        assert len(quest_manager.get_completed_quests()) == 3


class TestQuestManagerSerialization:
    """Test QuestManager serialization for save/load."""

    @pytest.fixture
    def quest_data(self):
        """Sample quest definitions for testing."""
        return {
            "quests": [
                {
                    "id": "quest_a",
                    "name": "Quest A",
                    "description": "First quest",
                    "unlocked_by_default": True,
                    "unlocks_quests": ["quest_b"]
                },
                {
                    "id": "quest_b",
                    "name": "Quest B",
                    "description": "Second quest",
                    "unlocked_by_default": False,
                    "unlock_requirements": {"quest_completed": "quest_a"},
                    "unlocks_quests": []
                }
            ]
        }

    def test_serialize_quest_states(self, quest_data):
        """Should serialize current quest states."""
        manager = QuestManager()
        manager.load_quests_from_dict(quest_data)
        manager.activate_quest("quest_a")

        serialized = manager.serialize_states()
        assert serialized["quest_a"] == "active"
        assert serialized["quest_b"] == "locked"

    def test_deserialize_quest_states(self, quest_data):
        """Should restore quest states from serialized data."""
        manager = QuestManager()
        manager.load_quests_from_dict(quest_data)

        saved_states = {
            "quest_a": "completed",
            "quest_b": "active"
        }
        manager.deserialize_states(saved_states)

        assert manager.get_quest_state("quest_a") == QuestState.COMPLETED
        assert manager.get_quest_state("quest_b") == QuestState.ACTIVE

    def test_deserialize_partial_states(self, quest_data):
        """Should handle partial state data (missing quests use defaults)."""
        manager = QuestManager()
        manager.load_quests_from_dict(quest_data)

        # Only quest_a state saved
        saved_states = {"quest_a": "active"}
        manager.deserialize_states(saved_states)

        assert manager.get_quest_state("quest_a") == QuestState.ACTIVE
        # quest_b should use default (locked since unlocked_by_default=False)
        assert manager.get_quest_state("quest_b") == QuestState.LOCKED


class TestQuestManagerFileLoading:
    """Test loading quests from JSON files."""

    def test_load_quests_from_file(self):
        """Should load quests from a JSON file."""
        quest_data = {
            "quests": [
                {
                    "id": "file_quest",
                    "name": "File Quest",
                    "description": "Loaded from file",
                    "unlocked_by_default": True
                }
            ]
        }

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            json.dump(quest_data, f)
            temp_path = Path(f.name)

        try:
            manager = QuestManager()
            manager.load_quests_from_file(temp_path)
            assert "file_quest" in manager.quests
            assert manager.get_quest_state("file_quest") == QuestState.AVAILABLE
        finally:
            temp_path.unlink()


class TestQuestManagerGameStateIntegration:
    """Test QuestManager integration with GameState."""

    def test_game_state_loads_quests_with_campaign_id(self):
        """GameState should load quest manager when campaign_id is provided."""
        from dnd_engine.core.character import Character, CharacterClass
        from dnd_engine.core.creature import Abilities
        from dnd_engine.core.game_state import GameState
        from dnd_engine.core.party import Party
        from dnd_engine.rules.loader import DataLoader
        from dnd_engine.utils.events import EventBus

        abilities = Abilities(
            strength=10, dexterity=14, constitution=14,
            intelligence=10, wisdom=12, charisma=10
        )
        character = Character(
            name="Test Hero",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16
        )
        party = Party([character])
        event_bus = EventBus()
        data_loader = DataLoader()

        game_state = GameState(
            party=party,
            dungeon_name="town_of_arden",
            event_bus=event_bus,
            data_loader=data_loader,
            campaign_id="the_unquiet_dead"
        )

        assert game_state.quest_manager is not None
        assert len(game_state.quest_manager.quests) == 3
        assert game_state.quest_manager.get_quest_state("investigate_crypt") == QuestState.AVAILABLE

    def test_game_state_without_campaign_has_no_quest_manager(self):
        """GameState should have no quest manager without campaign_id."""
        from dnd_engine.core.character import Character, CharacterClass
        from dnd_engine.core.creature import Abilities
        from dnd_engine.core.game_state import GameState
        from dnd_engine.core.party import Party
        from dnd_engine.rules.loader import DataLoader
        from dnd_engine.utils.events import EventBus

        abilities = Abilities(
            strength=10, dexterity=14, constitution=14,
            intelligence=10, wisdom=12, charisma=10
        )
        character = Character(
            name="Test Hero",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16
        )
        party = Party([character])
        event_bus = EventBus()
        data_loader = DataLoader()

        # Use test_dungeon which doesn't have a campaign_id in its data
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus,
            data_loader=data_loader
        )

        assert game_state.quest_manager is None


class TestTheUnquietDeadCampaign:
    """Test loading the actual The Unquiet Dead campaign quests."""

    def test_load_the_unquiet_dead_quests(self):
        """Should load The Unquiet Dead campaign quests from data file."""
        from dnd_engine.rules.loader import DataLoader

        data_loader = DataLoader()
        quest_data = data_loader.load_quests("the_unquiet_dead")

        manager = QuestManager()
        manager.load_quests_from_dict(quest_data)

        # Should have 3 quests
        assert len(manager.quests) == 3
        assert "investigate_crypt" in manager.quests
        assert "cult_conspiracy" in manager.quests
        assert "temple_assault" in manager.quests

        # First quest available, others locked
        assert manager.get_quest_state("investigate_crypt") == QuestState.AVAILABLE
        assert manager.get_quest_state("cult_conspiracy") == QuestState.LOCKED
        assert manager.get_quest_state("temple_assault") == QuestState.LOCKED

    def test_the_unquiet_dead_full_progression(self):
        """Should be able to progress through all The Unquiet Dead quests."""
        from dnd_engine.rules.loader import DataLoader

        data_loader = DataLoader()
        quest_data = data_loader.load_quests("the_unquiet_dead")

        manager = QuestManager()
        manager.load_quests_from_dict(quest_data)

        # Complete first quest
        manager.activate_quest("investigate_crypt")
        unlocked = manager.complete_quest("investigate_crypt")
        assert "cult_conspiracy" in unlocked
        assert manager.get_quest_state("cult_conspiracy") == QuestState.AVAILABLE

        # Complete second quest
        manager.activate_quest("cult_conspiracy")
        unlocked = manager.complete_quest("cult_conspiracy")
        assert "temple_assault" in unlocked
        assert manager.get_quest_state("temple_assault") == QuestState.AVAILABLE

        # Complete final quest
        manager.activate_quest("temple_assault")
        unlocked = manager.complete_quest("temple_assault")
        assert unlocked == []  # No more quests to unlock

        # All completed
        assert len(manager.get_completed_quests()) == 3


class TestBonusReward:
    """Test the BonusReward dataclass."""

    def test_bonus_reward_creation(self):
        """BonusReward should be creatable with all fields."""
        bonus = BonusReward(
            condition="return_item",
            item_id="skull_of_davos",
            turn_in_npc="lord_davos",
            reward_item="jar_of_ointment",
            description="Return the skull to Lord Davos",
        )
        assert bonus.condition == "return_item"
        assert bonus.item_id == "skull_of_davos"
        assert bonus.turn_in_npc == "lord_davos"
        assert bonus.reward_item == "jar_of_ointment"
        assert bonus.description == "Return the skull to Lord Davos"

    def test_bonus_reward_from_dict(self):
        """BonusReward should be creatable from dictionary."""
        data = {
            "condition": "return_item",
            "item_id": "skull_of_davos",
            "turn_in_npc": "lord_davos",
            "reward_item": "jar_of_ointment",
            "description": "Return the skull to Lord Davos",
        }
        bonus = BonusReward.from_dict(data)
        assert bonus.condition == "return_item"
        assert bonus.item_id == "skull_of_davos"
        assert bonus.turn_in_npc == "lord_davos"

    def test_bonus_reward_from_dict_default_condition(self):
        """BonusReward should use default condition when not provided."""
        data = {
            "item_id": "skull",
            "turn_in_npc": "npc",
            "reward_item": "reward",
        }
        bonus = BonusReward.from_dict(data)
        assert bonus.condition == "return_item"
        assert bonus.description == ""

    def test_bonus_reward_to_dict(self):
        """BonusReward should be serializable to dictionary."""
        bonus = BonusReward(
            condition="return_item",
            item_id="skull_of_davos",
            turn_in_npc="lord_davos",
            reward_item="jar_of_ointment",
            description="Return the skull to Lord Davos",
        )
        data = bonus.to_dict()
        assert data["condition"] == "return_item"
        assert data["item_id"] == "skull_of_davos"
        assert data["turn_in_npc"] == "lord_davos"
        assert data["reward_item"] == "jar_of_ointment"
        assert data["description"] == "Return the skull to Lord Davos"

    def test_bonus_reward_roundtrip(self):
        """BonusReward should survive roundtrip serialization."""
        original = BonusReward(
            condition="return_item",
            item_id="skull_of_davos",
            turn_in_npc="lord_davos",
            reward_item="jar_of_ointment",
            description="Return the skull to Lord Davos",
        )
        data = original.to_dict()
        restored = BonusReward.from_dict(data)
        assert restored.condition == original.condition
        assert restored.item_id == original.item_id
        assert restored.turn_in_npc == original.turn_in_npc
        assert restored.reward_item == original.reward_item
        assert restored.description == original.description


class TestQuestWithBonusRewards:
    """Test Quest with bonus_rewards functionality."""

    def test_quest_with_bonus_rewards(self):
        """Quest should support bonus_rewards field."""
        bonus = BonusReward(
            condition="return_item",
            item_id="skull",
            turn_in_npc="npc",
            reward_item="reward",
            description="Test",
        )
        quest = Quest(
            id="test_quest",
            name="Test Quest",
            description="A test quest",
            bonus_rewards=[bonus],
        )
        assert len(quest.bonus_rewards) == 1
        assert quest.bonus_rewards[0].item_id == "skull"

    def test_quest_to_dict_includes_bonus_rewards(self):
        """Quest.to_dict() should serialize bonus_rewards."""
        bonus = BonusReward(
            condition="return_item",
            item_id="skull",
            turn_in_npc="npc",
            reward_item="reward",
            description="Test bonus",
        )
        quest = Quest(
            id="test_quest",
            name="Test Quest",
            description="A test quest",
            bonus_rewards=[bonus],
        )
        data = quest.to_dict()
        assert "bonus_rewards" in data
        assert len(data["bonus_rewards"]) == 1
        assert data["bonus_rewards"][0]["item_id"] == "skull"

    def test_quest_roundtrip_with_bonus_rewards(self):
        """Quest should survive roundtrip with bonus_rewards."""
        bonus = BonusReward(
            condition="return_item",
            item_id="skull",
            turn_in_npc="npc",
            reward_item="reward",
            description="Test",
        )
        original = Quest(
            id="test_quest",
            name="Test Quest",
            description="A test quest",
            bonus_rewards=[bonus],
        )
        data = original.to_dict()
        restored = Quest.from_dict(data)
        assert len(restored.bonus_rewards) == 1
        assert restored.bonus_rewards[0].item_id == "skull"


class TestQuestManagerRewards:
    """Test QuestManager reward functionality."""

    @pytest.fixture
    def quest_data_with_rewards(self):
        """Sample quest definitions with rewards."""
        return {
            "quests": [
                {
                    "id": "crypt_quest",
                    "name": "The Crypt Problem",
                    "description": "Investigate the crypt",
                    "unlocked_by_default": True,
                    "quest_giver": "father_aldric",
                    "reward_gold": 50,
                    "unlocks_quests": ["cult_quest"],
                    "bonus_rewards": [
                        {
                            "condition": "return_item",
                            "item_id": "skull_of_davos",
                            "turn_in_npc": "lord_davos",
                            "reward_item": "jar_of_ointment",
                            "description": "Return skull to Lord Davos",
                        }
                    ],
                },
                {
                    "id": "cult_quest",
                    "name": "The Cult Conspiracy",
                    "description": "Stop the cult",
                    "unlocked_by_default": False,
                    "unlock_requirements": {"quest_completed": "crypt_quest"},
                    "quest_giver": "sister_maeve",
                    "reward_gold": 0,
                    "unlocks_quests": ["temple_quest"],
                },
                {
                    "id": "temple_quest",
                    "name": "Temple of Doom",
                    "description": "Final assault",
                    "unlocked_by_default": False,
                    "unlock_requirements": {"quest_completed": "cult_quest"},
                    "quest_giver": "father_aldric",
                    "reward_gold": 250,
                },
            ]
        }

    @pytest.fixture
    def quest_manager(self, quest_data_with_rewards):
        """Create a QuestManager with reward test data."""
        manager = QuestManager()
        manager.load_quests_from_dict(quest_data_with_rewards)
        return manager

    def test_rewarded_state_exists(self):
        """REWARDED quest state should be defined."""
        assert QuestState.REWARDED.value == "rewarded"

    def test_claim_quest_reward_success(self, quest_manager):
        """Should claim reward from correct quest giver."""
        quest_manager.activate_quest("crypt_quest")
        quest_manager.complete_quest("crypt_quest")

        result = quest_manager.claim_quest_reward("crypt_quest", "father_aldric")

        assert result["success"] is True
        assert result["quest_id"] == "crypt_quest"
        assert result["quest_name"] == "The Crypt Problem"
        assert result["reward_gold"] == 50
        assert quest_manager.get_quest_state("crypt_quest") == QuestState.REWARDED

    def test_claim_quest_reward_wrong_npc(self, quest_manager):
        """Should fail when claiming from wrong NPC."""
        quest_manager.activate_quest("crypt_quest")
        quest_manager.complete_quest("crypt_quest")

        result = quest_manager.claim_quest_reward("crypt_quest", "wrong_npc")

        assert result["success"] is False
        assert "Wrong NPC" in result["error"]
        assert quest_manager.get_quest_state("crypt_quest") == QuestState.COMPLETED

    def test_claim_quest_reward_not_completed(self, quest_manager):
        """Should fail when quest not completed."""
        quest_manager.activate_quest("crypt_quest")

        result = quest_manager.claim_quest_reward("crypt_quest", "father_aldric")

        assert result["success"] is False
        assert "not completed" in result["error"]

    def test_claim_quest_reward_already_rewarded(self, quest_manager):
        """Should fail when reward already claimed."""
        quest_manager.activate_quest("crypt_quest")
        quest_manager.complete_quest("crypt_quest")
        quest_manager.claim_quest_reward("crypt_quest", "father_aldric")

        result = quest_manager.claim_quest_reward("crypt_quest", "father_aldric")

        assert result["success"] is False
        assert "already claimed" in result["error"]

    def test_claim_quest_reward_unknown_quest(self, quest_manager):
        """Should fail for unknown quest ID."""
        result = quest_manager.claim_quest_reward("unknown_quest", "father_aldric")

        assert result["success"] is False
        assert "Unknown quest" in result["error"]

    def test_get_quests_awaiting_reward(self, quest_manager):
        """Should return quests completed but not yet rewarded for an NPC."""
        quest_manager.activate_quest("crypt_quest")
        quest_manager.complete_quest("crypt_quest")

        awaiting = quest_manager.get_quests_awaiting_reward("father_aldric")

        assert len(awaiting) == 1
        assert awaiting[0].id == "crypt_quest"

    def test_get_quests_awaiting_reward_empty_after_claim(self, quest_manager):
        """Should return empty after reward is claimed."""
        quest_manager.activate_quest("crypt_quest")
        quest_manager.complete_quest("crypt_quest")
        quest_manager.claim_quest_reward("crypt_quest", "father_aldric")

        awaiting = quest_manager.get_quests_awaiting_reward("father_aldric")

        assert len(awaiting) == 0

    def test_get_quests_awaiting_reward_wrong_npc(self, quest_manager):
        """Should return empty for NPC who isn't the quest giver."""
        quest_manager.activate_quest("crypt_quest")
        quest_manager.complete_quest("crypt_quest")

        awaiting = quest_manager.get_quests_awaiting_reward("wrong_npc")

        assert len(awaiting) == 0

    def test_get_quests_awaiting_reward_excludes_zero_gold(self, quest_manager):
        """Should exclude quests with zero gold reward."""
        quest_manager.activate_quest("crypt_quest")
        quest_manager.complete_quest("crypt_quest")
        quest_manager.activate_quest("cult_quest")
        quest_manager.complete_quest("cult_quest")

        awaiting = quest_manager.get_quests_awaiting_reward("sister_maeve")

        assert len(awaiting) == 0

    def test_check_bonus_reward_found(self, quest_manager):
        """Should find bonus reward for matching NPC and item."""
        quest, bonus = quest_manager.check_bonus_reward("lord_davos", "skull_of_davos")

        assert quest is not None
        assert bonus is not None
        assert quest.id == "crypt_quest"
        assert bonus.reward_item == "jar_of_ointment"

    def test_check_bonus_reward_wrong_npc(self, quest_manager):
        """Should return None for wrong NPC."""
        quest, bonus = quest_manager.check_bonus_reward("wrong_npc", "skull_of_davos")

        assert quest is None
        assert bonus is None

    def test_check_bonus_reward_wrong_item(self, quest_manager):
        """Should return None for wrong item."""
        quest, bonus = quest_manager.check_bonus_reward("lord_davos", "wrong_item")

        assert quest is None
        assert bonus is None

    def test_rewarded_state_still_unlocks_quests(self, quest_manager):
        """REWARDED state should count as completed for unlock conditions."""
        quest_manager.activate_quest("crypt_quest")
        quest_manager.complete_quest("crypt_quest")
        quest_manager.claim_quest_reward("crypt_quest", "father_aldric")

        # Verify crypt_quest is REWARDED
        assert quest_manager.get_quest_state("crypt_quest") == QuestState.REWARDED

        # cult_quest should still be available (REWARDED counts as completed)
        assert quest_manager.get_quest_state("cult_quest") == QuestState.AVAILABLE
