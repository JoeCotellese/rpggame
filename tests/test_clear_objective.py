# ABOUTME: Tests for the CLEAR objective type that completes when all enemies in a room are defeated.
# ABOUTME: Verifies the COMBAT_END event handler and room-based objective completion.

import pytest

from dnd_engine.core.quest import (
    ObjectiveType,
    Quest,
    QuestManager,
    QuestObjective,
    QuestState,
)
from dnd_engine.utils.events import Event, EventBus, EventType


class TestClearObjectiveHandler:
    """Test the CLEAR objective event handler."""

    @pytest.fixture
    def event_bus(self):
        """Create a fresh event bus for testing."""
        return EventBus()

    @pytest.fixture
    def quest_manager(self, event_bus):
        """Create a QuestManager connected to the event bus."""
        manager = QuestManager()
        manager.set_event_bus(event_bus)
        return manager

    @pytest.fixture
    def clear_quest(self):
        """Create a quest with a CLEAR objective."""
        return Quest(
            id="clear_cellar",
            name="Rat Problem",
            description="Clear out the rats in the cellar",
            objectives=[
                QuestObjective(
                    id="clear_rats",
                    type=ObjectiveType.CLEAR,
                    target="cellar.storage",
                    description="Clear out the rats in the cellar",
                )
            ],
            unlocked_by_default=True,
        )

    def test_clear_handler_triggers_on_victory(
        self, quest_manager, event_bus, clear_quest
    ):
        """CLEAR handler should check objectives when combat ends in victory."""
        quest_manager.quests[clear_quest.id] = clear_quest
        quest_manager._quest_states[clear_quest.id] = QuestState.AVAILABLE
        quest_manager.activate_quest("clear_cellar")

        # Emit COMBAT_END with victory and matching room_id
        event_bus.emit(
            Event(
                type=EventType.COMBAT_END,
                data={"victory": True, "room_id": "cellar.storage", "xp_gained": 50},
            )
        )

        # The objective should be completed
        quest = quest_manager.quests["clear_cellar"]
        assert quest.objectives[0].completed is True

    def test_clear_handler_ignores_defeat(
        self, quest_manager, event_bus, clear_quest
    ):
        """CLEAR handler should not complete objective on defeat."""
        quest_manager.quests[clear_quest.id] = clear_quest
        quest_manager._quest_states[clear_quest.id] = QuestState.AVAILABLE
        quest_manager.activate_quest("clear_cellar")

        # Emit COMBAT_END with defeat
        event_bus.emit(
            Event(
                type=EventType.COMBAT_END,
                data={"victory": False, "room_id": "cellar.storage", "xp_gained": 0},
            )
        )

        # The objective should NOT be completed
        quest = quest_manager.quests["clear_cellar"]
        assert quest.objectives[0].completed is False

    def test_clear_handler_requires_matching_room(
        self, quest_manager, event_bus, clear_quest
    ):
        """CLEAR handler should only complete objective for matching room."""
        quest_manager.quests[clear_quest.id] = clear_quest
        quest_manager._quest_states[clear_quest.id] = QuestState.AVAILABLE
        quest_manager.activate_quest("clear_cellar")

        # Emit COMBAT_END with victory but different room
        event_bus.emit(
            Event(
                type=EventType.COMBAT_END,
                data={"victory": True, "room_id": "laboratory.entrance", "xp_gained": 50},
            )
        )

        # The objective should NOT be completed (wrong room)
        quest = quest_manager.quests["clear_cellar"]
        assert quest.objectives[0].completed is False

    def test_clear_completes_quest(self, quest_manager, event_bus, clear_quest):
        """Quest should complete when all CLEAR objectives are done."""
        quest_manager.quests[clear_quest.id] = clear_quest
        quest_manager._quest_states[clear_quest.id] = QuestState.AVAILABLE
        quest_manager.activate_quest("clear_cellar")

        # Emit COMBAT_END to complete the objective
        event_bus.emit(
            Event(
                type=EventType.COMBAT_END,
                data={"victory": True, "room_id": "cellar.storage", "xp_gained": 50},
            )
        )

        # The quest should be completed
        assert quest_manager.get_quest_state("clear_cellar") == QuestState.COMPLETED

    def test_clear_unlocks_dungeons(self, quest_manager, event_bus):
        """Quest completion via CLEAR should unlock dungeons."""
        quest = Quest(
            id="clear_cellar",
            name="Rat Problem",
            description="Clear out the rats",
            objectives=[
                QuestObjective(
                    id="clear_rats",
                    type=ObjectiveType.CLEAR,
                    target="cellar.storage",
                    description="Clear the cellar",
                )
            ],
            unlocked_by_default=True,
            unlocks_dungeons=["laboratory"],
        )
        quest_manager.quests[quest.id] = quest
        quest_manager._quest_states[quest.id] = QuestState.AVAILABLE
        quest_manager.activate_quest("clear_cellar")

        # Complete the objective
        event_bus.emit(
            Event(
                type=EventType.COMBAT_END,
                data={"victory": True, "room_id": "cellar.storage", "xp_gained": 50},
            )
        )

        # Verify quest completed and dungeons would be unlocked
        assert quest_manager.get_quest_state("clear_cellar") == QuestState.COMPLETED
        assert quest_manager.quests["clear_cellar"].unlocks_dungeons == ["laboratory"]

    def test_clear_only_checks_active_quests(
        self, quest_manager, event_bus, clear_quest
    ):
        """CLEAR handler should only check active quests."""
        quest_manager.quests[clear_quest.id] = clear_quest
        quest_manager._quest_states[clear_quest.id] = QuestState.AVAILABLE
        # Quest is AVAILABLE but not ACTIVE

        # Emit COMBAT_END
        event_bus.emit(
            Event(
                type=EventType.COMBAT_END,
                data={"victory": True, "room_id": "cellar.storage", "xp_gained": 50},
            )
        )

        # Objective should NOT be completed (quest not active)
        quest = quest_manager.quests["clear_cellar"]
        assert quest.objectives[0].completed is False


class TestClearObjectiveIntegration:
    """Integration tests for CLEAR objectives with the full quest system."""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def quest_manager(self, event_bus):
        manager = QuestManager()
        manager.set_event_bus(event_bus)
        return manager

    def test_multiple_clear_objectives(self, quest_manager, event_bus):
        """Quest with multiple CLEAR objectives should track each separately."""
        quest = Quest(
            id="clear_dungeon",
            name="Clear the Dungeon",
            description="Clear all rooms",
            objectives=[
                QuestObjective(
                    id="clear_room1",
                    type=ObjectiveType.CLEAR,
                    target="dungeon.room1",
                    description="Clear room 1",
                ),
                QuestObjective(
                    id="clear_room2",
                    type=ObjectiveType.CLEAR,
                    target="dungeon.room2",
                    description="Clear room 2",
                ),
            ],
            unlocked_by_default=True,
        )
        quest_manager.quests[quest.id] = quest
        quest_manager._quest_states[quest.id] = QuestState.AVAILABLE
        quest_manager.activate_quest("clear_dungeon")

        # Clear first room
        event_bus.emit(
            Event(
                type=EventType.COMBAT_END,
                data={"victory": True, "room_id": "dungeon.room1", "xp_gained": 25},
            )
        )

        # First objective done, second not
        assert quest.objectives[0].completed is True
        assert quest.objectives[1].completed is False
        assert quest_manager.get_quest_state("clear_dungeon") == QuestState.ACTIVE

        # Clear second room
        event_bus.emit(
            Event(
                type=EventType.COMBAT_END,
                data={"victory": True, "room_id": "dungeon.room2", "xp_gained": 25},
            )
        )

        # Both objectives done, quest complete
        assert quest.objectives[0].completed is True
        assert quest.objectives[1].completed is True
        assert quest_manager.get_quest_state("clear_dungeon") == QuestState.COMPLETED

    def test_clear_with_mixed_objectives(self, quest_manager, event_bus):
        """Quest with CLEAR and other objective types should work correctly."""
        quest = Quest(
            id="investigate",
            name="Investigate",
            description="Clear enemies and find item",
            objectives=[
                QuestObjective(
                    id="clear_room",
                    type=ObjectiveType.CLEAR,
                    target="dungeon.main",
                    description="Clear the main room",
                ),
                QuestObjective(
                    id="find_note",
                    type=ObjectiveType.FETCH,
                    target="mysterious_note",
                    description="Find the note",
                ),
            ],
            unlocked_by_default=True,
        )
        quest_manager.quests[quest.id] = quest
        quest_manager._quest_states[quest.id] = QuestState.AVAILABLE
        quest_manager.activate_quest("investigate")

        # Complete CLEAR objective
        event_bus.emit(
            Event(
                type=EventType.COMBAT_END,
                data={"victory": True, "room_id": "dungeon.main", "xp_gained": 50},
            )
        )

        # CLEAR done, FETCH not done
        assert quest.objectives[0].completed is True
        assert quest.objectives[1].completed is False
        assert quest_manager.get_quest_state("investigate") == QuestState.ACTIVE

        # Complete FETCH objective
        event_bus.emit(
            Event(
                type=EventType.ITEM_ACQUIRED,
                data={"item_id": "mysterious_note"},
            )
        )

        # Both done, quest complete
        assert quest.objectives[0].completed is True
        assert quest.objectives[1].completed is True
        assert quest_manager.get_quest_state("investigate") == QuestState.COMPLETED
