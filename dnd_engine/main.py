# ABOUTME: Main entry point for the D&D 5E terminal game
# ABOUTME: Sets up the party, game state, and starts the CLI

import argparse

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.party import Party
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.llm.enhancer import LLMEnhancer
from dnd_engine.llm.factory import create_llm_provider
from dnd_engine.ui.cli import CLI
from dnd_engine.utils.events import EventBus


def create_default_party() -> Party:
    """
    Create a default party of 4 level 1 fighters.

    Returns:
        Party with 4 pre-configured fighter characters
    """
    # Fighter 1: Thorin Ironshield - STR-focused tank
    thorin = Character(
        name="Thorin Ironshield",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=Abilities(
            strength=16,     # Primary stat - high STR for attacks
            dexterity=12,    # Moderate DEX
            constitution=15, # Good HP
            intelligence=10,
            wisdom=12,
            charisma=8
        ),
        max_hp=12,  # 10 (avg d10) + 2 (CON mod)
        ac=16,      # Chain mail
        xp=0
    )

    # Fighter 2: Bjorn Axebearer - Balanced melee
    bjorn = Character(
        name="Bjorn Axebearer",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=Abilities(
            strength=15,     # Good STR
            dexterity=14,    # Good DEX
            constitution=14, # Good CON
            intelligence=10,
            wisdom=10,
            charisma=10
        ),
        max_hp=12,  # 10 (avg d10) + 2 (CON mod)
        ac=16,      # Chain mail
        xp=0
    )

    # Fighter 3: Eldric Swiftblade - DEX-focused fighter
    eldric = Character(
        name="Eldric Swiftblade",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=Abilities(
            strength=14,     # Good STR
            dexterity=16,    # Primary stat - high DEX for initiative and AC
            constitution=13, # Moderate CON
            intelligence=10,
            wisdom=12,
            charisma=8
        ),
        max_hp=11,  # 10 (avg d10) + 1 (CON mod)
        ac=16,      # Chain mail
        xp=0
    )

    # Fighter 4: Gareth Stormwind - CON-focused, high HP
    gareth = Character(
        name="Gareth Stormwind",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=Abilities(
            strength=15,     # Good STR
            dexterity=12,    # Moderate DEX
            constitution=16, # Primary stat - high CON for HP
            intelligence=10,
            wisdom=10,
            charisma=10
        ),
        max_hp=13,  # 10 (avg d10) + 3 (CON mod)
        ac=16,      # Chain mail
        xp=0
    )

    # Create party with all 4 fighters
    party = Party(characters=[thorin, bjorn, eldric, gareth])

    return party


def main() -> None:
    """Main entry point for the game."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="D&D 5E Terminal Game with LLM Enhancement"
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM narrative enhancement"
    )
    parser.add_argument(
        "--llm-provider",
        choices=["openai", "anthropic", "none"],
        help="Override LLM provider (openai/anthropic/none)"
    )
    parser.add_argument(
        "--llm-debug",
        action="store_true",
        help="Enable verbose LLM logging"
    )
    args = parser.parse_args()

    # Create the party
    party = create_default_party()

    # Create event bus
    event_bus = EventBus()

    # Initialize LLM provider
    llm_provider = None
    if not args.no_llm:
        llm_provider = create_llm_provider(args.llm_provider)
        if llm_provider:
            provider_name = llm_provider.get_provider_name()
            print(f"LLM enabled: {provider_name}")
            if args.llm_debug:
                print(f"  Model: {llm_provider.model}")
                print(f"  Timeout: {llm_provider.timeout}s")
                print(f"  Max tokens: {llm_provider.max_tokens}")
        else:
            print("LLM disabled (no API key or --no-llm flag)")

    # Initialize LLM enhancer
    if llm_provider:
        llm_enhancer = LLMEnhancer(llm_provider, event_bus)

    # Create game state
    game_state = GameState(
        party=party,
        dungeon_name="goblin_warren",
        event_bus=event_bus
    )

    # Create and run CLI
    cli = CLI(game_state)
    cli.run()


if __name__ == "__main__":
    main()
