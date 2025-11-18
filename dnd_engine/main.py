# ABOUTME: Main entry point for D&D 5E terminal game
# ABOUTME: Orchestrates character creation, LLM setup, and game loop

import argparse
import sys
from typing import Optional

from dotenv import load_dotenv

from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.core.save_manager import SaveManager
from dnd_engine.llm.enhancer import LLMEnhancer
from dnd_engine.llm.factory import create_llm_provider
from dnd_engine.rules.loader import DataLoader
from dnd_engine.ui.cli import CLI
from dnd_engine.ui.rich_ui import (
    print_banner,
    print_status_message,
    print_error,
    print_title,
    print_message,
    print_section,
    print_input_prompt,
    console,
    init_console
)
from dnd_engine.utils.events import EventBus
from dnd_engine.utils.logging_config import get_logging_config




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
  dnd-game --llm-provider debug     # Debug mode - shows prompts instead of API calls
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
        choices=["openai", "anthropic", "debug", "none"],
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
        help="Enable debug mode with file logging and detailed error traces"
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
        print_status_message("Data files loaded", "success")
        return loader
    except FileNotFoundError as e:
        print_error("Data files not found", e)
        print_error("Please ensure the game is installed correctly.")
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


def show_save_load_menu(save_manager: SaveManager) -> Optional[str]:
    """
    Show save/load menu and get user choice.

    Args:
        save_manager: SaveManager instance

    Returns:
        Save name to load, or None to create new party
    """
    print_section("Welcome Adventurer!", "What would you like to do?")

    # List available saves
    saves = save_manager.list_saves()

    if saves:
        print_title("\nAvailable Saved Games:")
        for i, save in enumerate(saves, 1):
            party_info = ", ".join(save["party_names"])
            avg_level = int(save["average_level"])
            last_played = save["last_played"][:10] if len(save["last_played"]) >= 10 else save["last_played"]
            print_message(
                f"{i}. {save['name']} - {party_info} "
                f"(Lvl {avg_level}, {save['dungeon']}) - Last played: {last_played}"
            )
        print_message(f"{len(saves) + 1}. Start a new adventure")
    else:
        print_status_message("No saved games found. Starting a new adventure!", "info")
        return None

    # Get user choice
    while True:
        try:
            choice_input = print_input_prompt(
                f"Enter your choice (1-{len(saves) + 1})"
            ).strip()
            choice = int(choice_input)

            if 1 <= choice <= len(saves):
                return saves[choice - 1]["name"]
            elif choice == len(saves) + 1:
                return None
            else:
                print_status_message(
                    f"Please enter a number between 1 and {len(saves) + 1}.",
                    "warning"
                )
        except ValueError:
            print_status_message("Please enter a valid number.", "warning")
        except KeyboardInterrupt:
            raise


def create_new_party(
    args: argparse.Namespace,
    data_loader: DataLoader
) -> Party:
    """
    Create a new party through character creation.

    Args:
        args: Command-line arguments
        data_loader: Data loader instance

    Returns:
        Created Party
    """
    # Get party size
    print_section("Party Creation", "How many characters in your party?")
    party_size = None
    while party_size is None:
        try:
            size_input = print_input_prompt("Enter number (1-4)").strip()
            size = int(size_input)
            if 1 <= size <= 4:
                party_size = size
            else:
                print_status_message("Please enter a number between 1 and 4.", "warning")
        except ValueError:
            print_status_message("Please enter a valid number.", "warning")
        except KeyboardInterrupt:
            raise

    if party_size == 1:
        print_title("\nLet's create your character!\n")
    else:
        print_title(f"\nLet's create your party of {party_size}!\n")

    # Create character factory
    factory = CharacterFactory()

    # Get race and class info for display
    races_data = data_loader.load_races()
    classes_data = data_loader.load_classes()

    # Create all characters
    characters = []
    for i in range(party_size):
        if party_size > 1:
            print_section(f"Character {i + 1} of {party_size}")

        # Run character creation
        character = factory.create_character_interactive(
            ui=None,
            data_loader=data_loader
        )

        race_name = races_data.get(character.race, {}).get("name", character.race)
        class_name = classes_data.get("fighter", {}).get("name", "Fighter")

        print_status_message(
            f"Character created: {character.name} ({race_name} {class_name})",
            "success"
        )
        characters.append(character)

    # Display party roster
    if party_size > 1:
        roster_lines = []
        for char in characters:
            race_name = races_data.get(char.race, {}).get("name", char.race)
            class_name = classes_data.get("fighter", {}).get("name", "Fighter")
            roster_lines.append(
                f"  • {char.name} ({race_name} {class_name}) - "
                f"HP: {char.max_hp}, AC: {char.ac}"
            )
        print_section("PARTY ROSTER", "\n".join(roster_lines))

    return Party(characters=characters)


def main() -> None:
    """
    Main entry point for the game.

    Flow:
        1. Load environment variables
        2. Parse command-line arguments
        3. Initialize debug logging (if enabled)
        4. Display banner
        5. Initialize data loader
        6. Initialize LLM provider (if enabled)
        7. Create event bus
        8. Show save/load menu
        9. Load existing game OR create new party
        10. Initialize game state
        11. Initialize LLM enhancer (if LLM enabled)
        12. Initialize UI
        13. Start game loop
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

    # Display banner
    print_banner("D&D 5E Terminal Adventure", version="0.1.0", color="cyan")
    print_status_message("Checking configuration...", "info")

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

    # Initialize save manager
    save_manager = SaveManager()

    try:
        # Show save/load menu
        save_to_load = show_save_load_menu(save_manager)

        if save_to_load:
            # Load existing game
            print_status_message(f"Loading saved game: {save_to_load}", "info")
            try:
                game_state = save_manager.load_game(
                    save_to_load,
                    event_bus=event_bus,
                    data_loader=data_loader
                )
                print_status_message("Game loaded successfully!", "success")
            except Exception as e:
                print_error(f"Failed to load save: {e}")
                print_status_message("Starting new game instead...", "info")
                party = create_new_party(args, data_loader)
                print_input_prompt("Press Enter to begin your adventure")
                game_state = GameState(
                    party=party,
                    dungeon_name=args.dungeon,
                    event_bus=event_bus,
                    data_loader=data_loader
                )
        else:
            # Create new party
            party = create_new_party(args, data_loader)
            print_input_prompt("Press Enter to begin your adventure")

            # Initialize game state
            game_state = GameState(
                party=party,
                dungeon_name=args.dungeon,
                event_bus=event_bus,
                data_loader=data_loader
            )

        # Store save manager in game state for later use
        game_state.save_manager = save_manager

        # Initialize UI with LLM enhancer
        cli = CLI(game_state, llm_enhancer=llm_enhancer)

        # Start game loop
        cli.run()

    except KeyboardInterrupt:
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
