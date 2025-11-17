# ABOUTME: Main entry point for D&D 5E terminal game
# ABOUTME: Orchestrates character creation, LLM setup, and game loop

import argparse
import sys
from typing import Optional

from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.llm.enhancer import LLMEnhancer
from dnd_engine.llm.factory import create_llm_provider
from dnd_engine.rules.loader import DataLoader
from dnd_engine.ui.cli import CLI
from dnd_engine.utils.events import EventBus


def print_banner() -> None:
    """Display game banner."""
    print("""
╔════════════════════════════════════╗
║   D&D 5E Terminal Adventure        ║
║   Version 0.1.0                    ║
╚════════════════════════════════════╝
    """)


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="D&D 5E Terminal Adventure Game",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  dnd-game                          # Start with default settings
  dnd-game --no-llm                 # Disable LLM enhancement
  dnd-game --llm-provider openai    # Use OpenAI (default)
  dnd-game --llm-provider anthropic # Use Anthropic Claude
  dnd-game --dungeon crypt          # Start in specific dungeon
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
        choices=["openai", "anthropic", "none"],
        help="Override LLM provider (default: from LLM_PROVIDER env var)"
    )

    parser.add_argument(
        "--dungeon",
        default="goblin_warren",
        help="Dungeon to explore (default: goblin_warren)"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    parser.add_argument(
        "--version",
        action="version",
        version="D&D 5E Terminal Game v0.1.0"
    )

    return parser.parse_args()


def initialize_data_loader() -> DataLoader:
    """
    Initialize and validate data loader.

    Returns:
        DataLoader instance

    Raises:
        FileNotFoundError: If data files are missing
    """
    try:
        loader = DataLoader()
        print("✓ Data files loaded")
        return loader
    except FileNotFoundError as e:
        print("✗ Error: Data files not found")
        print(f"  {e}")
        print("\nPlease ensure the game is installed correctly.")
        sys.exit(1)


def initialize_llm(args: argparse.Namespace) -> Optional:
    """
    Initialize LLM provider based on arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        LLMProvider instance or None if disabled
    """
    if args.no_llm:
        print("⚠ LLM disabled (--no-llm flag)")
        return None

    provider_name = args.llm_provider
    if provider_name == "none":
        print("⚠ LLM disabled (--llm-provider none)")
        return None

    try:
        provider = create_llm_provider(provider_name)
        if provider:
            print(f"✓ LLM provider: {provider.get_provider_name()}")
        else:
            print("⚠ LLM disabled (no API key configured)")
            print("  Set OPENAI_API_KEY or ANTHROPIC_API_KEY in environment")
        return provider
    except Exception as e:
        print(f"⚠ LLM initialization failed: {e}")
        print("  Continuing with basic descriptions...")
        return None


def main() -> None:
    """
    Main entry point for the game.

    Flow:
        1. Parse command-line arguments
        2. Display banner
        3. Initialize data loader
        4. Initialize LLM provider (if enabled)
        5. Create event bus
        6. Run character creation
        7. Initialize game state
        8. Initialize LLM enhancer (if LLM enabled)
        9. Initialize UI
        10. Start game loop
    """
    # Parse arguments
    args = parse_arguments()

    # Display banner
    print_banner()
    print("Checking configuration...")

    # Initialize data loader
    data_loader = initialize_data_loader()

    # Initialize LLM provider
    llm_provider = initialize_llm(args)

    # Create event bus
    event_bus = EventBus()

    # Initialize LLM enhancer if provider available
    llm_enhancer = None
    if llm_provider:
        llm_enhancer = LLMEnhancer(llm_provider, event_bus)

    print("\nLet's create your character!\n")

    try:
        # Create character factory
        factory = CharacterFactory()

        # Run character creation (CharacterFactory handles all UI)
        character = factory.create_character_interactive(
            ui=None,
            data_loader=data_loader
        )

        # Get race and class info for display
        races_data = data_loader.load_races()
        classes_data = data_loader.load_classes()

        race_name = races_data.get(character.race, {}).get("name", character.race)
        class_name = classes_data.get("fighter", {}).get("name", "Fighter")

        print(f"\nCharacter created: {character.name} ({race_name} {class_name})")
        print("\nPress Enter to begin your adventure...")
        input()

        # Create party with the character
        party = Party(characters=[character])

        # Initialize game state
        game_state = GameState(
            party=party,
            dungeon_name=args.dungeon,
            event_bus=event_bus,
            data_loader=data_loader
        )

        # Initialize UI
        cli = CLI(game_state)

        # Start game loop
        cli.run()

    except KeyboardInterrupt:
        print("\n\nGame interrupted. Thanks for playing!")
        sys.exit(0)
    except Exception as e:
        if args.debug:
            raise
        print(f"\n✗ Error: {e}")
        print("\nUse --debug flag for detailed error information.")
        sys.exit(1)


if __name__ == "__main__":
    main()
