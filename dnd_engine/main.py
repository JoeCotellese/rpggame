# ABOUTME: Main entry point for the D&D 5E terminal game
# ABOUTME: Sets up the character, game state, and starts the CLI

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.ui.cli import CLI
from dnd_engine.utils.events import EventBus


def create_default_character() -> Character:
    """
    Create a default level 1 fighter character.

    Returns:
        Pre-configured fighter character
    """
    # Fighter with standard array stats
    abilities = Abilities(
        strength=16,     # Primary stat for fighter
        dexterity=14,    # Good for AC and initiative
        constitution=15, # Good HP
        intelligence=10,
        wisdom=12,
        charisma=8
    )

    # Level 1 fighter with 1d10 + CON mod HP (12 HP avg)
    character = Character(
        name="Thorin Ironshield",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=12,  # 10 (avg d10) + 2 (CON mod)
        ac=16,      # Chain mail
        xp=0
    )

    return character


def main():
    """Main entry point for the game."""
    # Create the player character
    player = create_default_character()

    # Create event bus
    event_bus = EventBus()

    # Create game state
    game_state = GameState(
        player=player,
        dungeon_name="goblin_warren",
        event_bus=event_bus
    )

    # Create and run CLI
    cli = CLI(game_state)
    cli.run()


if __name__ == "__main__":
    main()
