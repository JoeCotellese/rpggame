# ABOUTME: Runnable demonstration of the session facade, reactions, and DM adjudication.
# ABOUTME: The new engine API is additive and not yet wired into either client, so this shows it.

"""Demonstrate what the session layer can do.

The session API is purely additive — neither `dnd-game` nor `dnd-2d` uses it
yet — so launching either client shows none of it. This script drives it
directly.

Usage::

    uv run python scripts/demo_session.py            # all three demos
    uv run python scripts/demo_session.py combat     # just one

With ``ANTHROPIC_API_KEY`` set, the adjudication demo uses a real model. Without
it, a scripted stand-in stands in so the demo still runs.
"""

from __future__ import annotations

import json
import os
import sys

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.entity_ids import pc_entity_id
from dnd_engine.core.game_state import GameState
from dnd_engine.core.map import Map, TileType
from dnd_engine.core.party import Party
from dnd_engine.core.position import Position
from dnd_engine.rules.loader import DataLoader
from dnd_engine.session import (
    AttackIntent,
    FreeformIntent,
    LLMRulingSource,
    Session,
    WaitIntent,
)
from dnd_engine.systems.opportunity_attacks import publish_movement_provoke
from dnd_engine.utils.events import EventBus, EventType


def _fighter(name: str, **overrides) -> Character:
    """A serviceable level-3 fighter."""
    defaults = {
        "character_class": CharacterClass.FIGHTER,
        "level": 3,
        "abilities": Abilities(
            strength=16,
            dexterity=12,
            constitution=14,
            intelligence=12,
            wisdom=13,
            charisma=8,
        ),
        "max_hp": 30,
        "ac": 16,
    }
    defaults.update(overrides)
    return Character(name=name, **defaults)


def _game(party: Party, seed: int) -> GameState:
    """A started game in the crypt, where the entrance encounter waits."""
    game = GameState(
        party=party,
        dungeon_name="crypt",
        campaign_id="the_unquiet_dead",
        event_bus=EventBus(),
        data_loader=DataLoader(),
        dice_roller=DiceRoller(seed=seed),
    )
    game.start()
    return game


def demo_combat() -> None:
    """A whole fight driven through `perform()`, with no client-side turn logic."""
    print("=" * 68)
    print("1. A FULL FIGHT THROUGH THE FACADE")
    print("=" * 68)
    print("The caller submits intents. The engine advances initiative, runs death")
    print("saves, drains enemy turns, and decides when combat is over.\n")

    game = _game(Party([_fighter("Thorin"), _fighter("Garrick")]), seed=5)
    session = Session(game)
    session.advance()  # an enemy may hold the first initiative slot

    turns = 0
    while session.in_combat and not session.is_over and turns < 40:
        actor = session.awaiting_actor_id
        if actor is None:
            result = session.advance()
        else:
            living = [e for e in session.snapshot()["enemies"] if e["is_alive"]]
            result = session.perform(
                AttackIntent(actor_id=actor, target_ref=living[0]["display_name"])
                if living
                else WaitIntent(actor_id=actor)
            )
            turns += 1

        for event in result.events:
            if event.message:
                print(f"   {event.message}")
            elif event.type is EventType.COMBAT_END:
                print(f"   [COMBAT END] {event.data}")

        # A withdrawing enemy can leave a reaction unanswered, and the session
        # refuses to advance until it is. A demo has nobody to ask, so it takes
        # the decision's own default — which is the automatic attack the engine
        # always used to make. Without this the loop spins: `advance()` keeps
        # returning nothing and `turns` never grows past the bound.
        while session.pending_decision is not None:
            decision = session.pending_decision
            answer = decision.default_option_id or decision.options[0].option_id
            print(f"   [DECISION] {decision.prompt} -> {answer}")
            for event in session.resolve(decision.decision_id, answer).events:
                if event.message:
                    print(f"   {event.message}")

    print(f"\n   Resolved in {turns} player turns.")
    print("   Note the enemies are 'Skeleton 1' and 'Skeleton 2' — every client")
    print("   now gets that disambiguation, not just the terminal one.\n")


def demo_reaction() -> None:
    """An opportunity attack presented as a choice rather than resolved for you."""
    print("=" * 68)
    print("2. OPPORTUNITY ATTACKS ARE A DECISION")
    print("=" * 68)
    print("The engine used to take these automatically. Now it asks.\n")

    for choice in ("decline", "attack"):
        game = _game(Party([_fighter("Thorin")]), seed=3)
        game.bootstrap_spatial(
            Map(
                width=20,
                height=20,
                tiles={(x, y): TileType.FLOOR for y in range(20) for x in range(20)},
            ),
            replace=True,
        )
        game.set_position(pc_entity_id("Thorin"), 10, 10)
        game.set_position("skeleton_0", 11, 10)

        session = Session(game)
        # Arms the deferring handlers, which is also what a client does at
        # combat start when an enemy holds the first initiative slot.
        session.advance()

        mover = game._find_creature_by_id("skeleton_0")
        publish_movement_provoke(
            game.reaction_dispatcher, mover, Position(11, 10), Position(14, 10)
        )

        decision = session.pending_decision
        if decision is None:
            print("   (no reaction provoked this run)")
            continue

        turn_state = game.initiative_tracker.turn_states[game.party.characters[0]]
        print(f'   "{decision.prompt}"')
        print(f"   asked of: {decision.actor_id}")
        print(f"   options:  {[o.option_id for o in decision.options]}")
        print(f"   -> player chooses: {choice.upper()}")

        result = session.resolve(decision.decision_id, choice)
        for event in result.events[:2]:
            if event.message:
                print(f"      {event.message}")
        print(f"      reaction still available: {turn_state.reaction_available}\n")

    print("   Declining keeps the reaction, exactly as the SRD requires.\n")


class _ScriptedDM:
    """Stands in for a real model when no API key is present."""

    RULINGS = {
        "brazier": {
            "ability": "strength",
            "skill": "athletics",
            "dc": 15,
            "success_text": "The brazier crashes over and the webs catch, roaring alight.",
            "failure_text": "It grinds across the flagstones but refuses to tip.",
        },
        "carvings": {
            "ability": "intelligence",
            "skill": "history",
            "dc": 12,
            "success_text": "The carvings name the Davos dead — one name scratched out.",
            "failure_text": "The script is too worn to read.",
        },
        "listen": {
            "ability": "wisdom",
            "skill": "perception",
            "dc": 10,
            "success_text": "Beyond the wall, something drags itself in a slow circle.",
            "failure_text": "You hear only your own breathing.",
        },
    }

    def __init__(self) -> None:
        self.key = "brazier"

    async def generate(self, prompt: str, temperature: float = 0.7) -> str:
        return f"```json\n{json.dumps(self.RULINGS[self.key])}\n```"


def demo_adjudication() -> None:
    """Freeform player text turned into a ruled check."""
    print("=" * 68)
    print("3. SAY WHAT YOU ACTUALLY WANT TO DO")
    print("=" * 68)

    use_real_model = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if use_real_model:
        from dnd_engine.llm.factory import create_llm_provider

        provider = create_llm_provider()
        print("Using a REAL model — judge whether these rulings feel like a DM.\n")
    else:
        provider = _ScriptedDM()
        print("No ANTHROPIC_API_KEY set, so a scripted stand-in is supplying the")
        print("rulings. Set the key and re-run to see a real model decide.\n")

    party = Party(
        [
            _fighter(
                "Nyx",
                character_class=CharacterClass.ROGUE,
                max_hp=24,
                ac=14,
                skill_proficiencies=["athletics", "perception", "history"],
            )
        ]
    )
    game = _game(party, seed=8)
    session = Session(game, ruling_source=LLMRulingSource(provider))
    session.advance()

    attempts = [
        ("brazier", "I shove the brazier into the webs"),
        ("carvings", "I study the carvings on the wall"),
        ("listen", "I press my ear to the wall and listen"),
    ]
    for key, said in attempts:
        if isinstance(provider, _ScriptedDM):
            provider.key = key

        actor = session.awaiting_actor_id or pc_entity_id("Nyx")
        result = session.perform(FreeformIntent(actor_id=actor, text=said))

        print(f'   > "{said}"')
        if not result.ok:
            print(f"     (the DM declines: {result.error})\n")
            continue
        for event in result.events:
            if event.type in (
                EventType.SKILL_CHECK,
                EventType.ABILITY_CHECK,
                EventType.DESCRIPTION_ENHANCED,
            ):
                print(f"     {event.message}")
        print()

        if session.awaiting_actor_id is None and session.in_combat:
            session.advance()

    print("   The model proposed the ability and the DC. The ENGINE rolled and")
    print("   decided — which is why the arithmetic is shown.\n")


DEMOS = {
    "combat": demo_combat,
    "reaction": demo_reaction,
    "adjudication": demo_adjudication,
}


def main() -> int:
    """Run one demo, or all of them."""
    requested = sys.argv[1:] or list(DEMOS)
    unknown = [name for name in requested if name not in DEMOS]
    if unknown:
        print(f"unknown demo(s): {', '.join(unknown)}")
        print(f"available: {', '.join(DEMOS)}")
        return 1

    for name in requested:
        DEMOS[name]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
