# ABOUTME: E2E driver that boots the real CLI on the lab settlement (no LLM, no menus).
# ABOUTME: Run under pexpect by test_node_surface_e2e.py; only game setup is scripted.

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus
from terminal_client.ui.cli import CLI


class NoopCampaignManager:
    """Save-less campaign manager so the e2e run never touches real save slots."""

    def save_game(self, *args, **kwargs):
        return None


def main() -> None:
    character = Character(
        name="Test Hero",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=Abilities(
            strength=14,
            dexterity=12,
            constitution=13,
            intelligence=10,
            wisdom=11,
            charisma=8,
        ),
        max_hp=12,
        ac=16,
    )
    game_state = GameState(
        party=Party([character]),
        dungeon_name="lab_settlement",
        event_bus=EventBus(),
        data_loader=DataLoader(),
    )
    cli = CLI(
        game_state,
        NoopCampaignManager(),
        "lab",
        auto_save_enabled=False,
        llm_enhancer=None,
    )
    cli.run()


if __name__ == "__main__":
    main()
