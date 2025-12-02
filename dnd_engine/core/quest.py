# ABOUTME: Quest state system for tracking quest progression through the campaign.
# ABOUTME: Handles quest states (locked/available/active/completed) and objective tracking.

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dnd_engine.utils.events import Event, EventBus

logger = logging.getLogger(__name__)


class QuestState(Enum):
    """Possible states for a quest."""

    LOCKED = "locked"
    AVAILABLE = "available"
    ACTIVE = "active"
    COMPLETED = "completed"
    REWARDED = "rewarded"  # Quest completed AND reward claimed


class ObjectiveType(Enum):
    """Types of quest objectives."""

    KILL = "kill"  # Defeat a specific enemy/boss
    FETCH = "fetch"  # Acquire a specific item
    USE = "use"  # Use/read a specific item
    DELIVER = "deliver"  # Bring item to an NPC
    DISCOVER = "discover"  # Visit a location/room
    CLEAR = "clear"  # Defeat all enemies in an area


@dataclass
class QuestObjective:
    """A single objective within a quest."""

    id: str
    type: ObjectiveType
    target: str  # monster_id, item_id, room_id, or npc_id depending on type
    description: str
    required: bool = True
    count_required: int = 1
    count_current: int = 0
    completed: bool = False

    # For deliver objectives, the item to deliver
    deliver_item: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuestObjective":
        """Create a QuestObjective from a dictionary."""
        obj_type = data.get("type", "fetch")
        if isinstance(obj_type, str):
            obj_type = ObjectiveType(obj_type)

        return cls(
            id=data["id"],
            type=obj_type,
            target=data["target"],
            description=data.get("description", ""),
            required=data.get("required", True),
            count_required=data.get("count_required", 1),
            count_current=data.get("count_current", 0),
            completed=data.get("completed", False),
            deliver_item=data.get("deliver_item"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert QuestObjective to a dictionary."""
        result = {
            "id": self.id,
            "type": self.type.value,
            "target": self.target,
            "description": self.description,
            "required": self.required,
            "count_required": self.count_required,
            "count_current": self.count_current,
            "completed": self.completed,
        }
        if self.deliver_item:
            result["deliver_item"] = self.deliver_item
        return result


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
    progression through the campaign's storyline. Each quest has objectives
    that must be completed before rewards can be claimed.
    """

    id: str
    name: str
    description: str
    objectives: list[QuestObjective] = field(default_factory=list)
    unlocked_by_default: bool = False
    unlock_requirements: dict[str, Any] | None = None
    target_dungeon: str | None = None
    unlocks_quests: list[str] = field(default_factory=list)
    unlocks_dungeons: list[str] = field(default_factory=list)
    quest_giver: str | None = None  # NPC who gives the quest
    turn_in_npc: str | None = None  # NPC to return to (defaults to quest_giver)
    reward_gold: int = 0  # Gold reward for completing quest
    reward_items: list[str] = field(default_factory=list)
    bonus_rewards: list[BonusReward] = field(default_factory=list)
    final_quest: bool = False
    npc_hints: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Set turn_in_npc to quest_giver if not specified."""
        if self.turn_in_npc is None and self.quest_giver is not None:
            self.turn_in_npc = self.quest_giver

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Quest":
        """
        Create a Quest from a dictionary.

        Args:
            data: Dictionary with quest data

        Returns:
            Quest instance
        """
        objectives = [
            QuestObjective.from_dict(obj) for obj in data.get("objectives", [])
        ]
        bonus_rewards = [
            BonusReward.from_dict(br) for br in data.get("bonus_rewards", [])
        ]
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            objectives=objectives,
            unlocked_by_default=data.get("unlocked_by_default", False),
            unlock_requirements=data.get("unlock_requirements"),
            target_dungeon=data.get("target_dungeon"),
            unlocks_quests=data.get("unlocks_quests", []),
            unlocks_dungeons=data.get("unlocks_dungeons", []),
            quest_giver=data.get("quest_giver"),
            turn_in_npc=data.get("turn_in_npc"),
            reward_gold=data.get("reward_gold", 0),
            reward_items=data.get("reward_items", []),
            bonus_rewards=bonus_rewards,
            final_quest=data.get("final_quest", False),
            npc_hints=data.get("npc_hints", {}),
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
            "objectives": [obj.to_dict() for obj in self.objectives],
            "unlocked_by_default": self.unlocked_by_default,
            "unlock_requirements": self.unlock_requirements,
            "target_dungeon": self.target_dungeon,
            "unlocks_quests": self.unlocks_quests,
            "unlocks_dungeons": self.unlocks_dungeons,
            "quest_giver": self.quest_giver,
            "turn_in_npc": self.turn_in_npc,
            "reward_gold": self.reward_gold,
            "reward_items": self.reward_items,
            "bonus_rewards": [br.to_dict() for br in self.bonus_rewards],
            "final_quest": self.final_quest,
            "npc_hints": self.npc_hints,
        }

    def all_required_objectives_complete(self) -> bool:
        """Check if all required objectives are completed."""
        return all(
            obj.completed for obj in self.objectives if obj.required
        )


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
            List of Quest objects that are completed and have this NPC as turn_in_npc
        """
        return [
            self.quests[qid]
            for qid, state in self._quest_states.items()
            if state == QuestState.COMPLETED
            and self.quests[qid].turn_in_npc == npc_id
            and self.quests[qid].reward_gold > 0
        ]

    def claim_quest_reward(self, quest_id: str, npc_id: str) -> dict[str, Any]:
        """
        Claim the reward for a completed quest from the turn-in NPC.

        Args:
            quest_id: ID of the quest to claim reward for
            npc_id: ID of the NPC claiming from (must match turn_in_npc)

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

        if quest.turn_in_npc != npc_id:
            return {
                "success": False,
                "error": f"Wrong NPC - turn in to {quest.turn_in_npc}",
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

    # -------------------------------------------------------------------------
    # Event-driven objective tracking
    # -------------------------------------------------------------------------

    def set_event_bus(self, event_bus: "EventBus") -> None:
        """
        Connect this QuestManager to an EventBus for event-driven tracking.

        Args:
            event_bus: The EventBus to subscribe to
        """
        from dnd_engine.utils.events import EventType

        self._event_bus = event_bus

        # Subscribe to relevant game events
        event_bus.subscribe(EventType.BOSS_DEFEATED, self._on_boss_defeated)
        event_bus.subscribe(EventType.ITEM_ACQUIRED, self._on_item_acquired)
        event_bus.subscribe(EventType.ITEM_USED, self._on_item_used)
        event_bus.subscribe(EventType.ROOM_ENTER, self._on_room_enter)
        event_bus.subscribe(EventType.CHARACTER_DEATH, self._on_character_death)
        event_bus.subscribe(EventType.COMBAT_END, self._on_combat_end)

    def _on_boss_defeated(self, event: "Event") -> None:
        """Handle boss defeated event - check kill objectives."""
        monster_id = event.data.get("monster_id")
        if monster_id:
            self._check_objectives(ObjectiveType.KILL, monster_id)

    def _on_item_acquired(self, event: "Event") -> None:
        """Handle item acquired event - check fetch objectives."""
        item_id = event.data.get("item_id")
        if item_id:
            self._check_objectives(ObjectiveType.FETCH, item_id)

    def _on_item_used(self, event: "Event") -> None:
        """Handle item used event - check use objectives."""
        item_id = event.data.get("item_id")
        if item_id:
            # Auto-activate available quests that have a USE objective for this item
            self._auto_activate_quests_for_use_objective(item_id)
            self._check_objectives(ObjectiveType.USE, item_id)

    def _auto_activate_quests_for_use_objective(self, item_id: str) -> None:
        """Auto-activate available quests when using an item that matches a USE objective."""
        from dnd_engine.utils.events import Event, EventType

        for quest in self.get_available_quests():
            for objective in quest.objectives:
                if objective.type == ObjectiveType.USE and objective.target == item_id:
                    self._quest_states[quest.id] = QuestState.ACTIVE
                    logger.info(
                        f"Quest '{quest.name}' auto-activated upon using {item_id}"
                    )

                    # Emit quest activated event
                    if hasattr(self, "_event_bus"):
                        self._event_bus.emit(
                            Event(
                                EventType.QUEST_ACTIVATED,
                                {
                                    "quest_id": quest.id,
                                    "quest_name": quest.name,
                                    "item_id": item_id,
                                },
                            )
                        )
                    break  # Only activate once per quest

    def _on_room_enter(self, event: "Event") -> None:
        """Handle room enter event - check discover objectives and auto-activate quests."""
        room_id = event.data.get("room_id")
        dungeon_id = event.data.get("dungeon_id")

        # Auto-activate available quests when entering their target dungeon
        if dungeon_id:
            self._auto_activate_quests_for_dungeon(dungeon_id)

        # Check discover objectives for active quests
        if room_id:
            self._check_objectives(ObjectiveType.DISCOVER, room_id)

    def _on_character_death(self, event: "Event") -> None:
        """Handle character death event - check kill objectives for non-boss enemies."""
        # Only process enemy deaths, not player deaths
        if event.data.get("is_enemy", False):
            monster_id = event.data.get("monster_id")
            if monster_id:
                self._check_objectives(ObjectiveType.KILL, monster_id)

    def _on_combat_end(self, event: "Event") -> None:
        """Handle combat end event - check clear objectives."""
        # Only check on victory (all enemies in room defeated)
        if event.data.get("victory", False):
            room_id = event.data.get("room_id")
            if room_id:
                # Auto-activate available quests that have a CLEAR objective for this room
                self._auto_activate_quests_for_clear_objective(room_id)
                self._check_objectives(ObjectiveType.CLEAR, room_id)

    def _auto_activate_quests_for_clear_objective(self, room_id: str) -> None:
        """Auto-activate available quests when clearing a room that matches a CLEAR objective."""
        from dnd_engine.utils.events import Event, EventType

        for quest in self.get_available_quests():
            for objective in quest.objectives:
                if objective.type == ObjectiveType.CLEAR and objective.target == room_id:
                    self._quest_states[quest.id] = QuestState.ACTIVE
                    logger.info(
                        f"Quest '{quest.name}' auto-activated upon clearing {room_id}"
                    )
                    # Emit quest activated event
                    if hasattr(self, "_event_bus"):
                        self._event_bus.emit(
                            Event(
                                EventType.QUEST_ACTIVATED,
                                {
                                    "quest_id": quest.id,
                                    "quest_name": quest.name,
                                    "room_id": room_id,
                                },
                            )
                        )
                    break  # Only activate once per quest

    def _auto_activate_quests_for_dungeon(self, dungeon_id: str) -> None:
        """
        Auto-activate available quests when entering their target dungeon.

        Args:
            dungeon_id: The ID of the dungeon being entered
        """
        from dnd_engine.utils.events import Event, EventType

        for quest in self.get_available_quests():
            if quest.target_dungeon == dungeon_id:
                self._quest_states[quest.id] = QuestState.ACTIVE
                logger.info(
                    f"Quest '{quest.name}' auto-activated upon entering {dungeon_id}"
                )

                # Emit quest activated event
                if hasattr(self, "_event_bus"):
                    self._event_bus.emit(
                        Event(
                            EventType.QUEST_ACTIVATED,
                            {
                                "quest_id": quest.id,
                                "quest_name": quest.name,
                                "dungeon_id": dungeon_id,
                            },
                        )
                    )

    def _check_objectives(self, obj_type: ObjectiveType, target: str) -> None:
        """
        Check all active quests for objectives matching the type and target.

        Args:
            obj_type: The type of objective to check
            target: The target ID (item_id, monster_id, room_id, etc.)
        """
        from dnd_engine.utils.events import Event, EventType

        for quest in self.get_active_quests():
            for objective in quest.objectives:
                if objective.type == obj_type and objective.target == target:
                    if not objective.completed:
                        objective.count_current += 1
                        logger.info(
                            f"Quest '{quest.name}' objective '{objective.id}' "
                            f"progress: {objective.count_current}/{objective.count_required}"
                        )

                        if objective.count_current >= objective.count_required:
                            objective.completed = True
                            logger.info(
                                f"Quest '{quest.name}' objective "
                                f"'{objective.id}' completed!"
                            )

                            # Emit objective complete event
                            if hasattr(self, "_event_bus"):
                                self._event_bus.emit(
                                    Event(
                                        EventType.QUEST_OBJECTIVE_COMPLETE,
                                        {
                                            "quest_id": quest.id,
                                            "quest_name": quest.name,
                                            "objective_id": objective.id,
                                            "objective_description": objective.description,
                                        },
                                    )
                                )

            # Check if quest is now complete
            if quest.all_required_objectives_complete():
                if self._quest_states[quest.id] == QuestState.ACTIVE:
                    self._complete_quest_from_objectives(quest)

    def _complete_quest_from_objectives(self, quest: Quest) -> None:
        """
        Complete a quest when all required objectives are done.

        Args:
            quest: The quest to complete
        """
        from dnd_engine.utils.events import Event, EventType

        self._quest_states[quest.id] = QuestState.COMPLETED
        logger.info(f"Quest '{quest.name}' completed!")

        # Unlock dependent quests
        unlocked_quests = []
        for unlock_id in quest.unlocks_quests:
            if unlock_id in self.quests:
                if self._check_unlock_conditions(unlock_id):
                    if self._quest_states[unlock_id] == QuestState.LOCKED:
                        self._quest_states[unlock_id] = QuestState.AVAILABLE
                        unlocked_quests.append(unlock_id)
                        logger.info(f"Quest '{unlock_id}' is now available!")

        # Emit quest completed event
        if hasattr(self, "_event_bus"):
            self._event_bus.emit(
                Event(
                    EventType.QUEST_COMPLETED,
                    {
                        "quest_id": quest.id,
                        "quest_name": quest.name,
                        "unlocked_quests": unlocked_quests,
                        "unlocked_dungeons": quest.unlocks_dungeons,
                        "turn_in_npc": quest.turn_in_npc,
                        "reward_gold": quest.reward_gold,
                    },
                )
            )

    def complete_deliver_objective(
        self, npc_id: str, item_id: str
    ) -> dict[str, Any]:
        """
        Complete a deliver objective when a player gives an item to an NPC.

        Args:
            npc_id: ID of the NPC receiving the item
            item_id: ID of the item being delivered

        Returns:
            Dictionary with success status and quest info
        """
        for quest in self.get_active_quests():
            for objective in quest.objectives:
                if (
                    objective.type == ObjectiveType.DELIVER
                    and objective.target == npc_id
                    and objective.deliver_item == item_id
                    and not objective.completed
                ):
                    objective.completed = True
                    logger.info(
                        f"Quest '{quest.name}' deliver objective "
                        f"'{objective.id}' completed!"
                    )

                    # Check if quest is now complete
                    if quest.all_required_objectives_complete():
                        self._complete_quest_from_objectives(quest)

                    return {
                        "success": True,
                        "quest_id": quest.id,
                        "quest_name": quest.name,
                        "objective_id": objective.id,
                    }

        return {"success": False, "error": "No matching deliver objective found"}

    def serialize_objective_states(self) -> dict[str, list[dict[str, Any]]]:
        """
        Serialize objective states for saving.

        Returns:
            Dictionary mapping quest IDs to lists of objective state dicts
        """
        result = {}
        for quest_id, quest in self.quests.items():
            if quest.objectives:
                result[quest_id] = [
                    {
                        "id": obj.id,
                        "count_current": obj.count_current,
                        "completed": obj.completed,
                    }
                    for obj in quest.objectives
                ]
        return result

    def deserialize_objective_states(
        self, saved_objectives: dict[str, list[dict[str, Any]]]
    ) -> None:
        """
        Restore objective states from saved data.

        Args:
            saved_objectives: Dictionary mapping quest IDs to objective states
        """
        for quest_id, objectives_data in saved_objectives.items():
            if quest_id in self.quests:
                quest = self.quests[quest_id]
                obj_map = {obj.id: obj for obj in quest.objectives}
                for obj_data in objectives_data:
                    obj_id = obj_data.get("id")
                    if obj_id in obj_map:
                        obj_map[obj_id].count_current = obj_data.get(
                            "count_current", 0
                        )
                        obj_map[obj_id].completed = obj_data.get(
                            "completed", False
                        )
