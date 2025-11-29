# ABOUTME: Quest state system for tracking quest progression through the campaign.
# ABOUTME: Handles quest states (locked/available/active/completed) and transitions.

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class QuestState(Enum):
    """Possible states for a quest."""

    LOCKED = "locked"
    AVAILABLE = "available"
    ACTIVE = "active"
    COMPLETED = "completed"
    REWARDED = "rewarded"  # Quest completed AND reward claimed


@dataclass
class BonusReward:
    """A bonus reward that can be claimed by returning an item to an NPC."""

    condition: str  # e.g., "return_item"
    item_id: str  # Item that must be given to NPC
    turn_in_npc: str  # NPC who accepts the item
    reward_item: str  # Item received as reward
    description: str  # Human-readable description

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BonusReward":
        """Create a BonusReward from a dictionary."""
        return cls(
            condition=data.get("condition", "return_item"),
            item_id=data["item_id"],
            turn_in_npc=data["turn_in_npc"],
            reward_item=data["reward_item"],
            description=data.get("description", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert BonusReward to a dictionary."""
        return {
            "condition": self.condition,
            "item_id": self.item_id,
            "turn_in_npc": self.turn_in_npc,
            "reward_item": self.reward_item,
            "description": self.description,
        }


@dataclass
class Quest:
    """
    Definition of a quest in the campaign.

    Quests are discovered through NPC conversations and track player
    progression through the campaign's storyline.
    """

    id: str
    name: str
    description: str
    unlocked_by_default: bool = False
    unlock_requirements: dict[str, Any] | None = None
    target_dungeon: str | None = None
    completion_criteria: dict[str, Any] = field(default_factory=dict)
    unlocks_quests: list[str] = field(default_factory=list)
    quest_giver: str | None = None  # NPC who gives quest and receives turn-in
    reward_gold: int = 0  # Gold reward for completing quest
    bonus_rewards: list[BonusReward] = field(default_factory=list)
    final_quest: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Quest":
        """
        Create a Quest from a dictionary.

        Args:
            data: Dictionary with quest data

        Returns:
            Quest instance
        """
        bonus_rewards = [
            BonusReward.from_dict(br) for br in data.get("bonus_rewards", [])
        ]
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            unlocked_by_default=data.get("unlocked_by_default", False),
            unlock_requirements=data.get("unlock_requirements"),
            target_dungeon=data.get("target_dungeon"),
            completion_criteria=data.get("completion_criteria", {}),
            unlocks_quests=data.get("unlocks_quests", []),
            quest_giver=data.get("quest_giver"),
            reward_gold=data.get("reward_gold", 0),
            bonus_rewards=bonus_rewards,
            final_quest=data.get("final_quest", False),
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert Quest to a dictionary.

        Returns:
            Dictionary representation of the quest
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "unlocked_by_default": self.unlocked_by_default,
            "unlock_requirements": self.unlock_requirements,
            "target_dungeon": self.target_dungeon,
            "completion_criteria": self.completion_criteria,
            "unlocks_quests": self.unlocks_quests,
            "quest_giver": self.quest_giver,
            "reward_gold": self.reward_gold,
            "bonus_rewards": [br.to_dict() for br in self.bonus_rewards],
            "final_quest": self.final_quest,
        }


class QuestManager:
    """
    Manages quest state for a campaign.

    Tracks which quests are locked, available, active, or completed.
    Handles state transitions and unlock logic when quests are completed.
    """

    def __init__(self):
        """Initialize an empty QuestManager."""
        self.quests: dict[str, Quest] = {}
        self._quest_states: dict[str, QuestState] = {}

    def load_quests_from_dict(self, data: dict[str, Any]) -> None:
        """
        Load quest definitions from a dictionary.

        Args:
            data: Dictionary with 'quests' key containing list of quest data
        """
        self.quests.clear()
        self._quest_states.clear()

        for quest_data in data.get("quests", []):
            quest = Quest.from_dict(quest_data)
            self.quests[quest.id] = quest

            # Set initial state based on unlocked_by_default
            if quest.unlocked_by_default:
                self._quest_states[quest.id] = QuestState.AVAILABLE
            else:
                self._quest_states[quest.id] = QuestState.LOCKED

    def load_quests_from_file(self, path: Path) -> None:
        """
        Load quest definitions from a JSON file.

        Args:
            path: Path to the JSON file containing quest definitions
        """
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.load_quests_from_dict(data)

    def get_quest_state(self, quest_id: str) -> QuestState:
        """
        Get the current state of a quest.

        Args:
            quest_id: ID of the quest

        Returns:
            Current QuestState

        Raises:
            KeyError: If quest_id is not found
        """
        if quest_id not in self.quests:
            raise KeyError(f"Unknown quest: {quest_id}")
        return self._quest_states[quest_id]

    def activate_quest(self, quest_id: str) -> bool:
        """
        Activate a quest (move from available to active).

        Args:
            quest_id: ID of the quest to activate

        Returns:
            True if quest was activated or already active, False if cannot activate
        """
        if quest_id not in self.quests:
            return False

        current_state = self._quest_states[quest_id]

        if current_state == QuestState.ACTIVE:
            return True

        if current_state == QuestState.AVAILABLE:
            self._quest_states[quest_id] = QuestState.ACTIVE
            return True

        # Cannot activate locked or completed quests
        return False

    def complete_quest(self, quest_id: str) -> list[str]:
        """
        Complete a quest and unlock dependent quests.

        Args:
            quest_id: ID of the quest to complete

        Returns:
            List of quest IDs that were unlocked by completing this quest
        """
        if quest_id not in self.quests:
            return []

        current_state = self._quest_states[quest_id]

        if current_state != QuestState.ACTIVE:
            return []

        self._quest_states[quest_id] = QuestState.COMPLETED

        # Unlock dependent quests
        unlocked = []
        quest = self.quests[quest_id]
        for unlock_id in quest.unlocks_quests:
            if unlock_id in self.quests:
                if self._check_unlock_conditions(unlock_id):
                    if self._quest_states[unlock_id] == QuestState.LOCKED:
                        self._quest_states[unlock_id] = QuestState.AVAILABLE
                        unlocked.append(unlock_id)

        return unlocked

    def _check_unlock_conditions(self, quest_id: str) -> bool:
        """
        Check if a quest's unlock conditions are met.

        Args:
            quest_id: ID of the quest to check

        Returns:
            True if all unlock conditions are met
        """
        quest = self.quests.get(quest_id)
        if not quest:
            return False

        if quest.unlocked_by_default:
            return True

        requirements = quest.unlock_requirements
        if not requirements:
            return True

        # Check quest_completed requirement (COMPLETED or REWARDED both count)
        if "quest_completed" in requirements:
            required_quest = requirements["quest_completed"]
            required_state = self._quest_states.get(required_quest)
            if required_state not in (QuestState.COMPLETED, QuestState.REWARDED):
                return False

        return True

    def get_available_quests(self) -> list[Quest]:
        """
        Get all quests in the available state.

        Returns:
            List of available Quest objects
        """
        return [
            self.quests[qid]
            for qid, state in self._quest_states.items()
            if state == QuestState.AVAILABLE
        ]

    def get_active_quests(self) -> list[Quest]:
        """
        Get all quests in the active state.

        Returns:
            List of active Quest objects
        """
        return [
            self.quests[qid]
            for qid, state in self._quest_states.items()
            if state == QuestState.ACTIVE
        ]

    def get_completed_quests(self) -> list[Quest]:
        """
        Get all quests in the completed state (not yet rewarded).

        Returns:
            List of completed Quest objects
        """
        return [
            self.quests[qid]
            for qid, state in self._quest_states.items()
            if state == QuestState.COMPLETED
        ]

    def get_quests_awaiting_reward(self, npc_id: str) -> list[Quest]:
        """
        Get completed quests that can be turned in to a specific NPC.

        Args:
            npc_id: ID of the NPC to check for turn-ins

        Returns:
            List of Quest objects that are completed and have this NPC as quest_giver
        """
        return [
            self.quests[qid]
            for qid, state in self._quest_states.items()
            if state == QuestState.COMPLETED
            and self.quests[qid].quest_giver == npc_id
            and self.quests[qid].reward_gold > 0
        ]

    def claim_quest_reward(self, quest_id: str, npc_id: str) -> dict[str, Any]:
        """
        Claim the reward for a completed quest from the quest giver.

        Args:
            quest_id: ID of the quest to claim reward for
            npc_id: ID of the NPC claiming from (must match quest_giver)

        Returns:
            Dictionary with success status and reward details
        """
        if quest_id not in self.quests:
            return {"success": False, "error": "Unknown quest"}

        quest = self.quests[quest_id]
        current_state = self._quest_states[quest_id]

        if current_state != QuestState.COMPLETED:
            if current_state == QuestState.REWARDED:
                return {"success": False, "error": "Reward already claimed"}
            return {"success": False, "error": "Quest not completed"}

        if quest.quest_giver != npc_id:
            return {
                "success": False,
                "error": f"Wrong NPC - quest giver is {quest.quest_giver}",
            }

        # Mark as rewarded
        self._quest_states[quest_id] = QuestState.REWARDED

        return {
            "success": True,
            "quest_id": quest_id,
            "quest_name": quest.name,
            "reward_gold": quest.reward_gold,
        }

    def check_bonus_reward(
        self, npc_id: str, item_id: str
    ) -> tuple[Quest | None, BonusReward | None]:
        """
        Check if an NPC accepts an item for a bonus reward.

        Args:
            npc_id: ID of the NPC receiving the item
            item_id: ID of the item being offered

        Returns:
            Tuple of (Quest, BonusReward) if valid, (None, None) otherwise
        """
        for quest in self.quests.values():
            for bonus in quest.bonus_rewards:
                if bonus.turn_in_npc == npc_id and bonus.item_id == item_id:
                    return quest, bonus
        return None, None

    def serialize_states(self) -> dict[str, str]:
        """
        Serialize quest states for saving.

        Returns:
            Dictionary mapping quest IDs to state strings
        """
        return {
            quest_id: state.value
            for quest_id, state in self._quest_states.items()
        }

    def deserialize_states(self, saved_states: dict[str, str]) -> None:
        """
        Restore quest states from saved data.

        Args:
            saved_states: Dictionary mapping quest IDs to state strings
        """
        for quest_id, state_str in saved_states.items():
            if quest_id in self.quests:
                self._quest_states[quest_id] = QuestState(state_str)
