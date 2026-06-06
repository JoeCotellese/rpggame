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
from dnd_engine.utils.events import Event, EventBus, EventType


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
    enemy_speed_override: int | None = None,
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
        if enemy_speed_override is not None:
            # Set speed BEFORE _start_combat() so TurnState init at
            # initiative.py:102 picks up the override
            # (TurnState(movement_remaining=creature.speed)).
            enemy.speed = enemy_speed_override
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

    def test_speed_20_enemy_stops_10_ft_short_and_emits_moved(self):
        """Speed=20 enemy 30 ft from a PC moves 4 squares and stops.

        Issue #641 acceptance criterion 2: a monster whose speed
        budget doesn't reach the nearest PC takes what movement it
        has, ends the turn with a MOVED action, and does NOT attempt
        an attack (the engine reach gate would reject it anyway).

        Geometry: enemy at (5, 5), PC at (5, 11) → 30 ft. With
        speed=20, the enemy takes 4 steps (4 × 5 ft = 20 ft) and
        lands at (5, 9), still 10 ft from the PC.
        """
        gs, _eids = _build_movement_fixture(
            party_positions={"Bob": (5, 11)},
            enemy_positions=(5, 5),
            enemy_speed_override=20,
        )

        result = gs.process_enemy_turn()

        assert result is not None
        assert result.action_taken == EnemyTurnAction.MOVED, (
            f"speed=20 enemy should have emitted MOVED; got {result.action_taken}"
        )
        assert result.moved_squares == 4, (
            f"speed=20 = 4 steps of 5 ft; got {result.moved_squares}"
        )
        assert result.movement_end_position == (5, 9), (
            "enemy should have stopped at (5, 9), 10 ft from PC; "
            f"ended at {result.movement_end_position}"
        )
        assert result.attack_result is None
        assert result.target_killed is False
        assert result.turn_advanced is True
        # PC took no damage — confirming attack truly didn't run.
        for character in gs.party.characters:
            assert character.current_hp == character.max_hp


class TestMonsterMovementProvokesOpportunityAttacks:
    """The OA dispatch already publishes OPPORTUNITY_PROVOKED for any
    mover (PC or monster) via ``attempt_combat_step``. Layer 3 just has
    to plumb monster movement through that primitive — this test
    verifies the integration.
    """

    def test_monster_leaving_reach_to_chase_distant_pc_provokes_oa(self):
        """Issue #641 acceptance criterion 3: enemy 1 walks south past
        enemy 2's 5-ft reach to reach a distant PC; enemy 2's reaction
        slot is consumed by the OA.

        Why two enemies (not two PCs)? Our greedy "nearest target"
        strategy will always pick an adjacent PC first and attack it
        instead of moving — there's no scenario where a monster
        rationally walks past a PC it could bite. ``_register_default_
        opportunity_attacks`` walks every placed combatant, though, so
        enemy 2 IS a registered reactor and its OA handler fires on
        any mover (including another monster) leaving its 5-ft reach.

        Geometry:
          enemy 1 (mover) at (5, 5), enemy 2 (reactor) at (4, 5).
          PC at (5, 12) — 35 ft south.
          Step 1: (5,5)->(5,6). Enemy 1 still 5 ft from enemy 2 → no OA.
          Step 2: (5,6)->(5,7). Enemy 1 now 10 ft from enemy 2 — leaves
          reach → enemy 2's reaction fires, slot consumed.
        """
        gs, _eids = _build_movement_fixture(
            party_positions={"Alice": (5, 12)},
            enemy_positions=[(5, 5), (4, 5)],
        )
        mover = gs.active_enemies[0]

        captured: list[Event] = []
        gs.event_bus.subscribe(EventType.DAMAGE_DEALT, captured.append)

        result = gs.process_enemy_turn()
        assert result is not None

        # The OA fires when the mover leaves the reactor's reach on
        # step 2. Reaction-slot consumption can't be asserted directly
        # here — ``process_enemy_turn`` calls ``next_turn`` before
        # returning, and per SRD the reactor's slot resets at the
        # start of its own turn (initiative.py:208). The roll-
        # independent signal we DO get is the ``DAMAGE_DEALT`` event
        # tagged ``opportunity_attack`` emitted by
        # ``_resolve_opportunity_attack_outcome`` when an OA connects.
        # Matches the canonical observation in
        # tests/test_oa_combat_step_integration.py:115-127.
        oa_events = [e for e in captured if e.data.get("opportunity_attack")]
        assert len(oa_events) >= 1, (
            f"expected at least one OA DAMAGE_DEALT event; got {len(oa_events)}"
        )
        # The mover (enemy 1) is the defender of the OA. The reactor
        # (enemy 2) is the attacker — both happen to be "Giant Rat",
        # which is correct: the OA system makes no friend/foe check
        # (a known limitation, not introduced by this change).
        assert oa_events[0].data["defender"] == mover.name


class TestMonsterCannotMove:
    """SRD: a creature with speed 0 (Grappled, Restrained, etc.) can't
    move. Layer 3 must surface this cleanly as NO_REACHABLE_TARGET so
    the headless tick loop doesn't hang, and must not infinite-loop on
    a step that always fails.
    """

    def test_speed_0_enemy_stays_put_and_advances_turn(self):
        """Issue #641 acceptance criterion 4: a speed=0 enemy (e.g.,
        grappled) returns NO_REACHABLE_TARGET with moved_squares=0.

        ``attempt_combat_step`` fails the first step with
        ``"no movement remaining"`` because TurnState was initialized
        from ``enemy.speed = 0``. The movement loop's exhausted-budget
        branch breaks out without spinning, the turn advances, and no
        attack happens.
        """
        gs, _eids = _build_movement_fixture(
            party_positions={"Alice": (5, 11)},  # 30 ft away
            enemy_positions=(5, 5),
            enemy_speed_override=0,
        )
        tracker = gs.initiative_tracker
        assert tracker is not None
        turn_index_before = tracker.current_turn_index

        result = gs.process_enemy_turn()

        assert result is not None
        assert result.action_taken == EnemyTurnAction.NO_REACHABLE_TARGET
        assert result.moved_squares == 0
        assert result.turn_advanced is True
        assert tracker.current_turn_index != turn_index_before, (
            "initiative did not advance — combat would hang"
        )
        # Enemy position unchanged.
        assert gs.active_enemies[0].position.x == 5
        assert gs.active_enemies[0].position.y == 5


class TestMonsterMovementDoesNotDeadlock:
    """The anti-loop guard (two consecutive step failures) protects
    against monster-vs-monster collisions and walls. Without it, a
    monster blocked by another monster on every step would spin until
    the hard step ceiling tripped.
    """

    def test_two_enemies_blocking_each_other_terminate_cleanly(self):
        """Issue #641 acceptance criterion 5: enemy 1's path to the PC
        is blocked by enemy 2; enemy 1's movement loop must exit
        cleanly via the anti-loop guard rather than spin.

        Layout (single shared south-bound axis):
          enemy 1 at (5, 5), enemy 2 at (5, 6) directly blocking south.
          PC at (5, 11) — south of both.

        Enemy 1's greedy sign-step is always (0, +1). attempt_combat_step
        rejects each step with reason ``"occupied by giant_rat_1"``.
        After two consecutive failures the loop breaks; result is
        NO_REACHABLE_TARGET with moved_squares=0 and the turn
        advances.

        We then call ``process_enemy_turn`` again for enemy 2's turn
        as a smoke check: it should NOT hang and should make
        meaningful progress (its south path is clear).
        """
        gs, _eids = _build_movement_fixture(
            party_positions={"Alice": (5, 11)},
            enemy_positions=[(5, 5), (5, 6)],
        )
        tracker = gs.initiative_tracker
        assert tracker is not None
        enemy_1 = gs.active_enemies[0]
        enemy_2 = gs.active_enemies[1]

        result_1 = gs.process_enemy_turn()

        assert result_1 is not None
        assert result_1.action_taken == EnemyTurnAction.NO_REACHABLE_TARGET
        assert result_1.moved_squares == 0
        assert result_1.turn_advanced is True
        # Enemy 1 stayed at (5, 5).
        assert (enemy_1.position.x, enemy_1.position.y) == (5, 5)

        # Drive forward until enemy 2 acts (a PC may go between them
        # depending on initiative). Cap the loop to prove no hang.
        seen_enemy_2_turn = False
        for _ in range(10):
            current = tracker.get_current_combatant()
            if current is not None and current.creature is enemy_2:
                result_2 = gs.process_enemy_turn()
                assert result_2 is not None
                seen_enemy_2_turn = True
                break
            # Skip PC turns by advancing initiative manually.
            tracker.next_turn()

        assert seen_enemy_2_turn, (
            "enemy 2 never got a turn within 10 initiative steps — "
            "something is hanging combat"
        )


class TestTickLoopClosesAndAttacks:
    """Integration: drive the headless tick loop forward; the only path
    to victory is monsters closing distance. Mirrors the hang-detector
    pattern from
    tests/test_enemy_turn_reach_targeting.py::TestRangeAwareTargeting
    ::test_combat_does_not_hang_when_all_enemies_stranded.
    """

    def test_monster_closes_distance_and_lands_an_attack_within_one_round(self):
        """Issue #641 acceptance criterion 6: when the enemy is 30 ft
        from the PC, ``process_enemy_turn`` should — within a single
        call — move into reach and attack.

        Speed=30 = 6 squares of movement; the gap closes in 5 steps
        (the 6th step is unnecessary, the loop must recognize the
        in-reach pool became non-empty and break to attack). We loop
        ``process_enemy_turn`` to be resilient to initiative ordering
        (the enemy may or may not be the first combatant), with a
        belt-and-braces step ceiling.
        """
        gs, _eids = _build_movement_fixture(
            party_positions={"Alice": (5, 11)},  # 30 ft south
            enemy_positions=(5, 5),
        )
        tracker = gs.initiative_tracker
        assert tracker is not None
        enemy = gs.active_enemies[0]

        attack_seen = False
        moved_before_attacking = 0
        # Hard cap on initiative iterations: enough for a few rounds
        # in a 2-combatant fight, well short of an infinite loop.
        for _ in range(20):
            current = tracker.get_current_combatant()
            if current is not None and current.creature is enemy:
                result = gs.process_enemy_turn()
                assert result is not None
                if result.action_taken == EnemyTurnAction.ATTACK:
                    attack_seen = True
                    moved_before_attacking = result.moved_squares
                    break
                # MOVED or NO_REACHABLE_TARGET: keep cycling
                continue
            # PC turn — skip past it.
            tracker.next_turn()

        assert attack_seen, (
            "enemy never reached attack range — closing-distance "
            "combat would never complete"
        )
        assert moved_before_attacking >= 5, (
            f"enemy needed at least 5 steps to close 30 ft; "
            f"got {moved_before_attacking}"
        )
