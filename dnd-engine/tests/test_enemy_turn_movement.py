# ABOUTME: Tests for monster movement AI in process_enemy_turn (#641, Layer 3).
# ABOUTME: When no PC is in reach, the enemy closes distance via attempt_combat_step.

from __future__ import annotations

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.entity_ids import pc_entity_id
from dnd_engine.core.game_state import EnemyTurnAction, GameState
from dnd_engine.core.map import Map, TileType
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus


def _make_character(
    name: str, cls: CharacterClass, position: tuple[int, int]
) -> Character:
    """Level-1 wizard PC. Stats identical across PCs so distance is the
    only differentiating factor for targeting / movement decisions.
    """
    return Character(
        name=name,
        character_class=cls,
        level=1,
        abilities=Abilities(
            strength=12, dexterity=12, constitution=12,
            intelligence=10, wisdom=10, charisma=10,
        ),
        max_hp=15,
        ac=12,
        xp=0,
    )


def _build_movement_fixture(
    *,
    party_positions: dict[str, tuple[int, int]],
    enemy_positions: list[tuple[int, int]] | tuple[int, int],
    enemy_id: str = "giant_rat",
    map_size: int = 20,
) -> tuple[GameState, list[str]]:
    """Build a flat-floor combat with PCs and one or more enemies.

    Returns ``(game_state, enemy_entity_ids)``. Initiative is forced to
    the first enemy so ``process_enemy_turn`` can be called directly.

    Mirrors ``test_enemy_turn_reach_targeting._build_targeting_fixture``
    so we share the same regression-tested wiring (bootstrap_spatial,
    _start_combat, surprise scrub).
    """
    tiles: dict[tuple[int, int], TileType] = {}
    for y in range(map_size):
        for x in range(map_size):
            tiles[(x, y)] = TileType.FLOOR
    grid_map = Map(width=map_size, height=map_size, tiles=tiles)

    characters = [
        _make_character(name, CharacterClass.WIZARD, pos)
        for name, pos in party_positions.items()
    ]
    party = Party(characters=characters)

    game_state = GameState(
        party=party,
        dungeon_name="test_dungeon",
        event_bus=EventBus(),
        data_loader=DataLoader(),
        dice_roller=DiceRoller(seed=42),
    )
    game_state.bootstrap_spatial(grid_map)

    if isinstance(enemy_positions, tuple):
        enemy_positions = [enemy_positions]

    enemy_eids: list[str] = []
    for idx, pos in enumerate(enemy_positions):
        enemy = game_state.data_loader.create_monster(enemy_id)
        game_state.active_enemies.append(enemy)
        eid = f"{enemy_id}_{idx}"
        game_state.set_position(eid, pos[0], pos[1])
        enemy_eids.append(eid)

    for character, (x, y) in zip(characters, party_positions.values(), strict=True):
        game_state.set_position(pc_entity_id(character.name), x, y)

    game_state._start_combat()
    tracker = game_state.initiative_tracker
    assert tracker is not None
    # Force the first enemy to act first.
    for idx, entry in enumerate(tracker.combatants):
        if entry.creature is game_state.active_enemies[0]:
            tracker.current_turn_index = idx
            break

    # Strip surprise so the movement test isn't sidetracked by a skipped
    # turn — same scrub used by the reach-targeting suite.
    for enemy in game_state.active_enemies:
        if enemy.has_condition("surprised"):
            enemy.remove_condition("surprised")

    return game_state, enemy_eids


class TestMonsterClosesAndAttacks:
    """SRD § Movement: a monster with no in-reach target moves toward
    the nearest PC, then attacks if it lands inside reach.
    """

    def test_speed_30_enemy_closes_30_ft_and_attacks_in_one_turn(self):
        """Giant rat (speed 30, 5-ft bite) 30 ft from a PC closes and bites.

        Issue #641 acceptance criterion 1: ``process_enemy_turn`` must
        consume movement to reach an out-of-reach PC and then resolve
        the attack in the same turn.

        Geometry: enemy at (5, 5), PC at (5, 11) → 6 squares = 30 ft.
        After 5 steps the enemy lands at (5, 10), 5 ft from the PC and
        in bite reach. The 6th step is unnecessary; the loop must
        notice the in-reach pool became non-empty and break to attack.
        """
        gs, _eids = _build_movement_fixture(
            party_positions={"Bob": (5, 11)},
            enemy_positions=(5, 5),
        )

        result = gs.process_enemy_turn()

        assert result is not None
        assert result.action_taken == EnemyTurnAction.ATTACK
        assert result.target_name == "Bob"
        assert result.moved_squares >= 5, (
            "enemy needed at least 5 steps to reach bite range — "
            f"got {result.moved_squares}"
        )
        # Attack happened (hit or miss — seeded roll, but the contract
        # is that the attack code ran, not that it landed).
        assert result.attack_result is not None
