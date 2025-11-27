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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Quest":
        """
        Create a Quest from a dictionary.

        Args:
            data: Dictionary with quest data

        Returns:
            Quest instance
        """
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            unlocked_by_default=data.get("unlocked_by_default", False),
            unlock_requirements=data.get("unlock_requirements"),
            target_dungeon=data.get("target_dungeon"),
            completion_criteria=data.get("completion_criteria", {}),
            unlocks_quests=data.get("unlocks_quests", [])
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
            "unlocks_quests": self.unlocks_quests
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

        # Check quest_completed requirement
        if "quest_completed" in requirements:
            required_quest = requirements["quest_completed"]
            if self._quest_states.get(required_quest) != QuestState.COMPLETED:
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
        Get all quests in the completed state.

        Returns:
            List of completed Quest objects
        """
        return [
            self.quests[qid]
            for qid, state in self._quest_states.items()
            if state == QuestState.COMPLETED
        ]

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
