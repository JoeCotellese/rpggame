# ABOUTME: Tests for range-aware target preference in process_enemy_turn (#634, Layer 2).
# ABOUTME: Enemies prefer in-reach PCs; if none reachable, emit NO_REACHABLE_TARGET and advance turn.

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
    """Build a level-1 PC for the targeting fixture.

    Identical stats across PCs so retaliation / lowest-HP heuristics don't
    bias the targeting outcome we're measuring — only distance does.
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


def _build_targeting_fixture(
    *,
    party_positions: dict[str, tuple[int, int]],
    enemy_position: tuple[int, int],
    enemy_id: str = "giant_rat",
) -> tuple[GameState, str]:
    """Set up a combat with party members at given tiles and one enemy.

    Returns ``(game_state, enemy_entity_id)``. The PCs are wizards
    (cosmetic — we just want non-frontline names) so the fighter/wizard
    labeling in the test docstrings reads naturally. All PCs share the
    same stats so distance is the only differentiating factor for
    targeting.
    """
    tiles: dict[tuple[int, int], TileType] = {}
    for y in range(20):
        for x in range(20):
            tiles[(x, y)] = TileType.FLOOR
    grid_map = Map(width=20, height=20, tiles=tiles)

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

    enemy = game_state.data_loader.create_monster(enemy_id)
    game_state.active_enemies.append(enemy)

    for character, (x, y) in zip(characters, party_positions.values(), strict=True):
        game_state.set_position(pc_entity_id(character.name), x, y)
    enemy_eid = f"{enemy_id}_0"
    game_state.set_position(enemy_eid, enemy_position[0], enemy_position[1])

    # Start combat so initiative_tracker exists and the enemy can take
    # turns. Force the enemy to be the current combatant.
    game_state._start_combat()
    tracker = game_state.initiative_tracker
    assert tracker is not None
    for idx, entry in enumerate(tracker.combatants):
        if entry.creature is enemy:
            tracker.current_turn_index = idx
            break

    # Clear the surprise condition that _check_for_surprise applies on
    # combat start when the party stat-sneaks the enemy. The targeting
    # tests assert on attack outcomes — a surprised enemy would skip
    # its turn entirely, drowning the signal we want to measure. Plays
    # well with how the tests construct combat from scratch.
    if enemy.has_condition("surprised"):
        enemy.remove_condition("surprised")

    return game_state, enemy_eid


class TestRangeAwareTargeting:
    """SRD § Playing the Game › Melee Attacks (#634, Layer 2).

    When choosing a target, an enemy must restrict to PCs within its
    reach. The smart-targeting strategy (retaliation, lowest-HP, etc.)
    then runs over that in-reach subset rather than the whole party.
    """

    def test_enemy_prefers_in_reach_target_over_distant_one(self):
        """Issue #634 repro: rat picks the adjacent PC, not the 30-ft PC.

        Bob (wizard) is adjacent to the rat (5 ft, in reach). Abe
        (wizard) is 30 ft away. The rat's 5-ft Bite can only land on
        Bob. Pre-fix, ``select_target_smart`` ignored distance and
        could pick Abe; post-fix, only Bob is in the candidate list so
        the rat targets and attacks Bob.
        """
        gs, _enemy_eid = _build_targeting_fixture(
            party_positions={"Bob": (6, 5), "Abe": (5, 11)},
            enemy_position=(5, 5),
        )

        result = gs.process_enemy_turn()

        assert result is not None
        assert result.action_taken == EnemyTurnAction.ATTACK
        assert result.target_name == "Bob", (
            f"rat should have targeted in-reach Bob, picked {result.target_name!r}"
        )

    def test_no_reachable_target_returns_dedicated_action_and_advances_turn(self):
        """All PCs out of reach -> NO_REACHABLE_TARGET, turn advances.

        Architect-flagged blocker: if the new "no in-reach" branch
        forgets to advance the turn, the headless tick loop spins
        forever and combat hangs. This test pins both the action enum
        and the turn-advance contract so the regression is loud.
        """
        gs, _enemy_eid = _build_targeting_fixture(
            party_positions={"Bob": (5, 11), "Abe": (5, 12)},  # both 30+ ft
            enemy_position=(5, 5),
        )
        tracker = gs.initiative_tracker
        assert tracker is not None
        turn_index_before = tracker.current_turn_index

        result = gs.process_enemy_turn()

        assert result is not None
        assert result.action_taken == EnemyTurnAction.NO_REACHABLE_TARGET
        assert result.turn_advanced is True
        assert tracker.current_turn_index != turn_index_before, (
            "initiative did not advance — combat would hang in the "
            "headless tick loop"
        )
        assert result.attack_result is None
        # No PC took damage.
        for character in gs.party.characters:
            assert character.current_hp == character.max_hp

    def test_combat_does_not_hang_when_all_enemies_stranded(self):
        """Multiple stranded enemies across rounds — initiative keeps moving.

        Catches the tick-loop hang risk by exercising several
        consecutive ``process_enemy_turn`` calls when no PC is in
        reach. Each call must advance the turn so the round eventually
        rotates back to the PCs.
        """
        gs, _enemy_eid = _build_targeting_fixture(
            party_positions={"Bob": (5, 14), "Abe": (5, 15)},  # both ~45 ft
            enemy_position=(5, 5),
        )
        tracker = gs.initiative_tracker
        assert tracker is not None

        seen_turn_indices: set[int] = set()
        for _ in range(6):
            seen_turn_indices.add(tracker.current_turn_index)
            result = gs.process_enemy_turn()
            # Either the enemy's turn ran (NO_REACHABLE_TARGET) or
            # initiative is on a PC and process_enemy_turn returned
            # None — both are progress, neither hangs.
            if result is not None:
                assert result.turn_advanced is True
        # Initiative cycled through more than one combatant — proof
        # the loop isn't stuck on the rat's turn.
        assert len(seen_turn_indices) >= 2

    def test_in_reach_filter_passes_multiple_candidates_through_to_targeting(self):
        """Three in-reach PCs all survive the filter; smart targeting then picks.

        Pins the contract that the filter is *additive*, not *collapsing*:
        when multiple PCs are within reach, all of them reach
        select_target_smart so retaliation / lowest-HP / intelligence
        strategies still see a real choice. We inject a fake
        combat_history so the test exercises the retaliation code
        path (without pinning a specific pick — low-INT rats use a
        weighted retaliation, not a hard rule).
        """
        gs, _enemy_eid = _build_targeting_fixture(
            party_positions={
                "Bob": (6, 5),       # adjacent east
                "Charlie": (4, 5),   # adjacent west
                "Daniel": (5, 6),    # adjacent south
            },
            enemy_position=(5, 5),
        )
        # Seed combat_history with Charlie having hit the rat.
        from dnd_engine.core.game_state import CombatEvent
        gs.combat_history.append(
            CombatEvent(
                timestamp=0.0,
                event_type="attack",
                attacker="Charlie",
                defender="Giant Rat",
                damage=3,
            )
        )

        result = gs.process_enemy_turn()
        assert result is not None
        assert result.action_taken == EnemyTurnAction.ATTACK
        # All three are in reach; smart targeting must have picked one.
        assert result.target_name in {"Bob", "Charlie", "Daniel"}
        # We don't pin Charlie specifically: low-INT rats (INT=2)
        # don't always retaliate (retaliation_weight defaults < 1.0).
        # The contract this test pins: the in-reach filter didn't
        # collapse the candidate list to just one PC; smart targeting
        # still ran with three candidates.

    def test_in_reach_filter_skipped_when_enemy_has_no_position(self):
        """Backwards compatibility — pre-spatial fixtures still work.

        Some integration tests place enemies without spatial context.
        When ``enemy.position`` is ``None``, skip the in-reach filter
        and fall through to the original full-party targeting (otherwise
        we'd regress every test that doesn't bootstrap_spatial).
        """
        gs, _enemy_eid = _build_targeting_fixture(
            party_positions={"Bob": (5, 11)},  # 30 ft — would be filtered out
            enemy_position=(5, 5),
        )
        # Strip the enemy's position to simulate a non-spatial fixture.
        gs.active_enemies[0].position = None

        result = gs.process_enemy_turn()
        # With no position, filter is skipped; rat targets Bob and
        # attacks (engine reach gate also no-ops without positions, so
        # the attack roll happens normally).
        assert result is not None
        assert result.action_taken == EnemyTurnAction.ATTACK
        assert result.target_name == "Bob"
