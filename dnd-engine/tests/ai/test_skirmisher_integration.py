# ABOUTME: Integration test — goblin tagged "skirmisher" closes, attacks, then retreats.
# ABOUTME: Verifies the full process_enemy_turn → pipeline → attempt_combat_step flow.

from __future__ import annotations

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.game_state import EnemyTurnAction, GameState
from dnd_engine.core.map import Map, TileType
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus


def _floor_map(size: int = 12) -> Map:
    tiles = {(x, y): TileType.FLOOR for x in range(size) for y in range(size)}
    return Map(width=size, height=size, tiles=tiles)


def _pc_id(name: str) -> str:
    return f"pc_{name.lower().replace(' ', '_')}"


def _make_skirmish_state() -> tuple[GameState, Character, Creature, str]:
    """A 12×12 floor, one PC at (3,9), one goblin at (3,3).

    The goblin's speed is 30 ft (6 tiles). From (3,3) to (3,9) is six
    tiles → the goblin can close to (3,8) (5 ft from the PC, in reach),
    spend 5 tiles of budget on the close, and retain 5 ft for one
    retreat step back to (3,7). All assertions key off engine state
    rather than dice rolls.
    """
    abilities = Abilities(
        strength=15, dexterity=14, constitution=13,
        intelligence=10, wisdom=12, charisma=8,
    )
    fighter = Character(
        name="Fighter 1",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=30,
        ac=30,  # high AC so the goblin's attack misses, keeping the PC alive
        xp=0,
    )
    party = Party(characters=[fighter])
    gs = GameState(
        party=party,
        dungeon_name="test_dungeon",
        event_bus=EventBus(),
        data_loader=DataLoader(),
        dice_roller=DiceRoller(seed=1),
    )
    gs.bootstrap_spatial(_floor_map())

    goblin = gs.data_loader.create_monster("goblin")
    gs.active_enemies.append(goblin)

    pc_id = _pc_id(fighter.name)
    goblin_id = "goblin_0"
    gs.set_position(goblin_id, 3, 3)
    gs.set_position(pc_id, 3, 9)

    gs._start_combat()

    goblin_idx = next(
        i for i, entry in enumerate(gs.initiative_tracker.combatants)
        if entry.creature is goblin
    )
    gs.initiative_tracker.current_turn_index = goblin_idx
    gs.initiative_tracker.turn_states[goblin].reset(speed=goblin.speed)
    # _start_combat surprises monsters on round 1; clear it so the
    # goblin can act on its forced turn.
    if "surprised" in goblin.conditions:
        goblin.remove_condition("surprised")
    return gs, fighter, goblin, goblin_id


class TestGoblinSkirmishesEndToEnd:
    def test_goblin_closes_attacks_then_retreats(self):
        gs, _fighter, goblin, goblin_id = _make_skirmish_state()

        result = gs.process_enemy_turn()
        assert result is not None
        assert result.action_taken == EnemyTurnAction.ATTACK
        # Close was 5 tiles, retreat was 1 tile.
        assert result.moved_squares == 6
        # Goblin ended at (3, 7) — one tile back from the attack position.
        end_position = gs.spatial.position_of(goblin_id)
        assert end_position is not None
        assert (end_position.x, end_position.y) == (3, 7)
        assert result.movement_end_position == (3, 7)
        # The actual goblin object's position mirrors the spatial index.
        assert goblin.position == end_position

