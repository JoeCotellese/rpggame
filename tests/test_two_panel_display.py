# ABOUTME: Tests for the two-panel display system (mechanics + narrative panels)
# ABOUTME: Verifies proper separation of game mechanics from LLM-enhanced narrative

import pytest
from unittest.mock import MagicMock, patch, call
from dnd_engine.utils.events import Event, EventType, EventBus
from dnd_engine.ui.cli import CLI
from dnd_engine.core.game_state import GameState
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature


class TestTwoPanelDisplay:
    """Test the two-panel display system for combat."""

    def test_enhancement_started_event_type_exists(self):
        """Verify ENHANCEMENT_STARTED event type is defined."""
        assert hasattr(EventType, 'ENHANCEMENT_STARTED')
        assert EventType.ENHANCEMENT_STARTED.value == "enhancement_started"

    @patch('dnd_engine.ui.cli.print_narrative_loading')
    def test_loading_panel_on_enhancement_started(self, mock_loading):
        """Verify loading panel is displayed when LLM enhancement starts."""
        # Create minimal CLI for testing event handlers
        game_state = MagicMock()
        game_state.event_bus = EventBus()
        cli = CLI(game_state)

        # Emit ENHANCEMENT_STARTED event
        event = Event(
            type=EventType.ENHANCEMENT_STARTED,
            data={"type": "combat"}
        )
        cli._on_enhancement_started(event)

        # Verify loading panel was shown
        assert mock_loading.called
        assert cli.narrative_pending is True

    @patch('dnd_engine.ui.cli.print_narrative_panel')
    def test_narrative_panel_on_combat_description(self, mock_narrative):
        """Verify narrative panel is displayed for combat descriptions."""
        game_state = MagicMock()
        game_state.event_bus = EventBus()
        cli = CLI(game_state)

        # Emit DESCRIPTION_ENHANCED event
        event = Event(
            type=EventType.DESCRIPTION_ENHANCED,
            data={
                "type": "combat",
                "text": "The sword gleams in the torchlight as it strikes true!"
            }
        )
        cli._on_description_enhanced(event)

        # Verify narrative panel was shown
        assert mock_narrative.called
        assert mock_narrative.call_args[0][0] == "The sword gleams in the torchlight as it strikes true!"
        assert cli.narrative_pending is False

    @patch('dnd_engine.ui.cli.print_narrative_panel')
    def test_narrative_panel_on_death_description(self, mock_narrative):
        """Verify narrative panel is displayed for death descriptions."""
        game_state = MagicMock()
        game_state.event_bus = EventBus()
        cli = CLI(game_state)

        event = Event(
            type=EventType.DESCRIPTION_ENHANCED,
            data={
                "type": "death",
                "text": "The hero falls with a final breath..."
            }
        )
        cli._on_description_enhanced(event)

        assert mock_narrative.called
        assert "hero falls" in mock_narrative.call_args[0][0]

    @patch('dnd_engine.ui.cli.print_narrative_loading')
    def test_loading_not_shown_for_non_combat(self, mock_loading):
        """Verify loading panel is NOT shown for room descriptions."""
        game_state = MagicMock()
        game_state.event_bus = EventBus()
        cli = CLI(game_state)

        event = Event(
            type=EventType.ENHANCEMENT_STARTED,
            data={"type": "room"}
        )
        cli._on_enhancement_started(event)

        # Loading should NOT be called for room type
        assert not mock_loading.called

    def test_event_bus_subscription(self):
        """Verify CLI subscribes to ENHANCEMENT_STARTED event."""
        game_state = MagicMock()
        game_state.event_bus = EventBus()
        cli = CLI(game_state)

        # Check that the handler is subscribed
        assert cli.game_state.event_bus.subscriber_count(EventType.ENHANCEMENT_STARTED) >= 1


class TestPanelFunctions:
    """Test the individual panel display functions."""

    @patch('dnd_engine.ui.rich_ui.console')
    def test_print_mechanics_panel(self, mock_console):
        """Test mechanics panel formatting."""
        from dnd_engine.ui.rich_ui import print_mechanics_panel

        print_mechanics_panel("TestWarrior attacks Goblin: 17 vs AC 15 - HIT")

        # Verify console.print was called
        assert mock_console.print.called

        # Get the Panel object that was printed
        panel = mock_console.print.call_args[0][0]
        assert panel.title == "⚔️  Mechanics"
        assert panel.border_style == "dim blue"

    @patch('dnd_engine.ui.rich_ui.console')
    def test_print_narrative_loading(self, mock_console):
        """Test narrative loading panel formatting."""
        from dnd_engine.ui.rich_ui import print_narrative_loading

        print_narrative_loading()

        assert mock_console.print.called
        panel = mock_console.print.call_args[0][0]
        assert panel.title == "✨ Narrative"
        assert panel.border_style == "yellow"

    @patch('dnd_engine.ui.rich_ui.console')
    def test_print_narrative_panel(self, mock_console):
        """Test narrative panel formatting."""
        from dnd_engine.ui.rich_ui import print_narrative_panel

        print_narrative_panel("The blade gleams in the moonlight!")

        assert mock_console.print.called
        panel = mock_console.print.call_args[0][0]
        assert panel.title == "✨ Narrative"
        assert panel.border_style == "gold1"
