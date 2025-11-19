# ABOUTME: Main entry point for D&D 5E terminal game with new save slot system
# ABOUTME: Orchestrates new main menu, save slots, character vault, and game loop

import argparse
import sys
from typing import Optional
from datetime import datetime

from dotenv import load_dotenv

from dnd_engine.core.game_state import GameState
from dnd_engine.llm.enhancer import LLMEnhancer
from dnd_engine.llm.factory import create_llm_provider
from dnd_engine.ui.main_menu_v2 import MainMenuV2
from dnd_engine.ui.cli import CLI
from dnd_engine.core.save_slot_manager import SaveSlotManager
from dnd_engine.ui.rich_ui import (
    print_banner,
    print_status_message,
    print_error,
    console,
    init_console
)
from dnd_engine.utils.logging_config import get_logging_config


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="D&D 5E Terminal Adventure Game (Save Slot System)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  dnd-game                          # Start with new menu system
  dnd-game --no-llm                 # Disable LLM enhancement
  dnd-game --llm-provider openai    # Use OpenAI (default)
  dnd-game --llm-provider anthropic # Use Anthropic Claude
  dnd-game --llm-provider debug     # Debug mode
  dnd-game --debug                  # Enable debug logging
        """
    )

    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM narrative enhancement"
    )

    parser.add_argument(
        "--llm-provider",
        choices=["openai", "anthropic", "debug", "none"],
        help="Override LLM provider (default: from LLM_PROVIDER env var)"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode with file logging and detailed error traces"
    )

    parser.add_argument(
        "--version",
        action="version",
        version="D&D 5E Terminal Game v0.2.0 (Save Slot System)"
    )

    return parser.parse_args()


def initialize_llm(args: argparse.Namespace) -> Optional:
    """Initialize LLM provider based on arguments."""
    if args.no_llm:
        print_status_message("LLM disabled (--no-llm flag)", "warning")
        return None

    provider_name = args.llm_provider
    if provider_name == "none":
        print_status_message("LLM disabled (--llm-provider none)", "warning")
        return None

    try:
        provider = create_llm_provider(provider_name)
        if provider:
            print_status_message(f"LLM provider: {provider.get_provider_name()}", "success")
        else:
            print_status_message("LLM disabled (no API key configured)", "warning")
            print_status_message("Set OPENAI_API_KEY or ANTHROPIC_API_KEY in environment", "info")
        return provider
    except Exception as e:
        print_status_message(f"LLM initialization failed: {e}", "warning")
        print_status_message("Continuing with basic descriptions...", "info")
        return None


class SaveSlotCLIAdapter:
    """
    Adapter to make CLI work with SaveSlotManager.

    This provides a compatible interface for CLI while using the new save slot system.
    """

    def __init__(self, slot_manager: SaveSlotManager, slot_number: int, session_start: datetime):
        """
        Initialize the adapter.

        Args:
            slot_manager: SaveSlotManager instance
            slot_number: Current slot number (1-10)
            session_start: When the game session started (for playtime tracking)
        """
        self.slot_manager = slot_manager
        self.slot_number = slot_number
        self.session_start = session_start

    def save_campaign_state(
        self,
        campaign_name: str,  # Ignored (kept for compatibility)
        game_state: GameState,
        slot_name: str,  # "auto", "quick", or custom name
        save_type: str  # "auto", "quick", or "manual"
    ) -> None:
        """
        Save game state to current slot (adapter method).

        Args:
            campaign_name: Ignored (kept for CLI compatibility)
            game_state: Game state to save
            slot_name: Save slot name (ignored, we use current slot)
            save_type: Type of save (ignored for now)
        """
        # Calculate session playtime
        playtime_delta = int((datetime.now() - self.session_start).total_seconds())

        # Save to current slot
        self.slot_manager.save_game(
            slot_number=self.slot_number,
            game_state=game_state,
            playtime_delta=playtime_delta
        )


def main() -> None:
    """
    Main entry point for the game with new save slot system.

    Flow:
        1. Load environment variables
        2. Parse command-line arguments
        3. Initialize debug logging (if enabled)
        4. Initialize LLM provider (if enabled)
        5. Show new main menu (handles migration automatically)
        6. Load or create game
        7. Initialize UI with save slot adapter
        8. Start game loop
    """
    # Load environment variables from .env file
    load_dotenv()

    # Parse arguments
    args = parse_arguments()

    # Initialize console with debug logging
    init_console(debug_mode=args.debug)

    # Display debug mode message if enabled
    if args.debug:
        logging_config = get_logging_config()
        if logging_config and logging_config.get_log_file_path():
            log_path = logging_config.get_log_file_path()
            print_status_message(
                f"Debug mode enabled. Logging to: {log_path}",
                "info"
            )

    # Initialize LLM provider
    llm_provider = initialize_llm(args)

    # Initialize LLM enhancer if provider available
    llm_enhancer = None
    if llm_provider:
        from dnd_engine.utils.events import EventBus
        event_bus = EventBus()
        llm_enhancer = LLMEnhancer(llm_provider, event_bus)

    try:
        # Show new main menu (handles migration automatically)
        menu = MainMenuV2()

        result = menu.run()

        if result is None:
            # User chose to exit
            return

        # Unpack result
        game_state, slot_number = result

        # Create save slot adapter for CLI compatibility
        session_start = datetime.now()
        slot_manager = SaveSlotManager()
        save_adapter = SaveSlotCLIAdapter(slot_manager, slot_number, session_start)

        # Initialize CLI with adapter (compatible with old interface)
        # Note: CLI expects campaign_manager and campaign_name, we provide adapter and slot number
        cli = CLI(
            game_state=game_state,
            campaign_manager=save_adapter,
            campaign_name=f"slot_{slot_number}",  # Dummy name for compatibility
            auto_save_enabled=True,
            llm_enhancer=llm_enhancer
        )

        # Start game loop
        cli.run()

    except KeyboardInterrupt:
        console.print("\n")
        print_status_message("Game interrupted. Thanks for playing!", "info")
        sys.exit(0)
    except Exception as e:
        if args.debug:
            raise
        print_error(str(e))
        print_status_message("Use --debug flag for detailed error information.", "info")
        sys.exit(1)


if __name__ == "__main__":
    main()
