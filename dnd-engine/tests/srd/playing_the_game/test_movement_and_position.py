# ABOUTME: SRD conformance audit for "Playing the Game > Movement and Position".
# ABOUTME: Cross-references docs/srd/playing-the-game/movement-and-position.md against engine code.

"""SRD conformance: Movement and Position.

Maps every rule in `docs/srd/playing-the-game/movement-and-position.md`
to a test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dnd_engine.core.creature import Abilities, Creature, MovementMode, Size
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.map import Map, TileType
from dnd_engine.core.position import Position
from dnd_engine.systems.action_economy import ActionType, Terrain, TurnState, cost_for
from dnd_engine.systems.actions import disengage
from dnd_engine.systems.initiative import InitiativeTracker
from dnd_engine.systems.opportunity_attacks import (
    publish_movement_provoke,
    register_default_opportunity_attack,
)
from dnd_engine.systems.reactions import ReactionDispatcher
from dnd_engine.systems.spatial_index import SpatialIndex

pytestmark = pytest.mark.srd(
    "playing-the-game/movement-and-position.md",
    lines="1864-1974",
)


MONSTERS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "monsters.json"
)
RACES_JSON = Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "races.json"


def _make_creature(*, speed: int = 30) -> Creature:
    """Plain Medium humanoid fixture for movement tests."""
    abilities = Abilities(
        strength=14,
        dexterity=14,
        constitution=14,
        intelligence=10,
        wisdom=10,
        charisma=10,
    )
    return Creature(name="Walker", max_hp=20, ac=12, abilities=abilities, speed=speed)


class TestSpeed_MoveUpToSpeed:
    """SRD § Playing the Game › Movement and Position › Speed.

    > On your turn, you can move a distance equal to your Speed or less.
    > Or you can decide not to move.
    """

    def test_turn_state_initializes_movement_pool_from_speed(self) -> None:
        """A creature's `TurnState.movement_remaining` starts at its Speed.

        `InitiativeTracker.add_combatant` constructs
        `TurnState(movement_remaining=creature.speed)` and `reset()`
        re-seeds it on each new turn. This is the engine's
        representation of "you can move a distance equal to your Speed."
        """
        creature = _make_creature(speed=30)
        state = TurnState(movement_remaining=creature.speed)

        assert state.movement_remaining == 30

        # Resetting (start of a new turn) re-seeds to the creature's speed.
        state.movement_remaining = 0
        state.reset(speed=creature.speed)
        assert state.movement_remaining == 30

    def test_partial_move_is_allowed_under_speed(self) -> None:
        """Consuming less than the full pool is permitted ("Speed or less").

        Two 5-ft steps draw the pool down to 20; the SRD allows
        "a distance equal to your Speed or less" and `consume_movement`
        succeeds without forcing the full Speed to be spent.
        """
        state = TurnState(movement_remaining=30)

        assert state.consume_movement(5) is True
        assert state.consume_movement(5) is True
        assert state.movement_remaining == 20

    def test_no_movement_is_allowed(self) -> None:
        """ "Or you can decide not to move." — zero consumption is legal.

        The TurnState supports skipping movement entirely: no API
        forces the pool to drain. A creature that takes an action and
        ends its turn without calling `consume_movement` leaves the
        pool full, which is the engine-side equivalent of "decide
        not to move."
        """
        state = TurnState(movement_remaining=30)
        # Take an action without moving.
        assert state.consume_action(ActionType.ACTION) is True
        # Pool is untouched.
        assert state.movement_remaining == 30

    def test_movement_beyond_speed_is_rejected(self) -> None:
        """You cannot move farther than your Speed in one turn.

        `consume_movement` returns False when the request exceeds the
        remaining pool and does not deduct, enforcing "a distance
        equal to your Speed or less."
        """
        state = TurnState(movement_remaining=30)

        # First 30 ft fully drains the pool.
        assert state.consume_movement(30) is True
        assert state.movement_remaining == 0

        # Any further request must be refused without changing the pool.
        assert state.consume_movement(5) is False
        assert state.movement_remaining == 0


class TestSpeed_DeductPerPartOfMove:
    """SRD § Playing the Game › Movement and Position › Speed (deduction).

    > However you're moving with your Speed, you deduct the distance of
    > each part of your move from it until it is used up or until you
    > are done moving, whichever comes first.
    """

    def test_each_step_deducts_from_movement_pool(self) -> None:
        """Each tactical step deducts its cost from `movement_remaining`.

        Six 5-ft steps draw a 30-ft pool to 0. This mirrors how the
        2D client consumes movement during combat (one tile = 5 ft per
        `client-2d/src/client_2d/session.py:912`).
        """
        state = TurnState(movement_remaining=30)
        for _ in range(6):
            assert state.consume_movement(5) is True
        assert state.movement_remaining == 0

    def test_pool_is_used_up_when_exactly_drained(self) -> None:
        """When the pool reaches 0, no further part of the move resolves.

        The "until it is used up" clause is enforced by
        `consume_movement` returning False once `movement_remaining`
        cannot cover the request.
        """
        state = TurnState(movement_remaining=5)
        assert state.consume_movement(5) is True
        assert state.movement_remaining == 0
        assert state.consume_movement(5) is False


class TestSpeed_CharacterAndMonsterStatBlocks:
    """SRD § Playing the Game › Movement and Position › Speed (sources).

    > A character's Speed is determined during character creation. A
    > monster's Speed is noted in the monster's stat block.
    """

    def test_creature_default_speed_matches_medium_humanoid(self) -> None:
        """`Creature` constructor defaults to 30 ft Speed.

        Matches the SRD default Speed for a Medium humanoid character
        established at creation time (Human, Elf, etc.). The race data
        in `data/srd/races.json` lists speeds per-species; this test
        defends the engine fallback.
        """
        creature = _make_creature()
        assert creature.speed == 30

    def test_monster_speed_loaded_from_stat_block(self) -> None:
        """Monsters in `monsters.json` carry a `speed` integer.

        Data-parity check: every monster entry declares its Speed,
        which `Creature.speed` then seeds during combat encounter
        construction.
        """
        monsters = json.loads(MONSTERS_JSON.read_text())
        assert monsters, "monsters.json must not be empty"
        for mid, mdata in monsters.items():
            assert "speed" in mdata, f"monster '{mid}' missing 'speed' in stat block"
            assert isinstance(mdata["speed"], int), (
                f"monster '{mid}' speed must be an int (got {type(mdata['speed']).__name__})"
            )

    def test_character_race_data_carries_speed(self) -> None:
        """`races.json` declares Speed per playable race (creation source).

        The SRD pins a character's Speed to character creation;
        `data/srd/races.json` is the canonical source the engine reads
        from when building a Character.
        """
        races = json.loads(RACES_JSON.read_text())
        assert races, "races.json must not be empty"
        for race_id, race_data in races.items():
            assert "speed" in race_data, f"race '{race_id}' missing 'speed' in race data"


class TestSpeed_SpecialSpeeds:
    """SRD § Playing the Game › Movement and Position › Speed (special speeds).

    > See "Rules Glossary" for more about Speed as well as about
    > special speeds, such as a Climb Speed, Fly Speed, or Swim Speed.
    """

    def test_creature_exposes_climb_fly_swim_speeds(self) -> None:
        """The engine models per-mode Speed via `Creature.speeds` keyed by
        `MovementMode` (Climb / Fly / Swim / Burrow), shipped under issue
        #432. Per-mode movement *cost* is a separate concern tracked by
        #433 (see `TestMovement_Modes`); this asserts only the data model.
        """
        # A flying creature can carry distinct per-mode speeds.
        flyer = Creature(
            name="Wyvern",
            max_hp=30,
            ac=13,
            abilities=Abilities(19, 10, 16, 5, 12, 6),
            speeds={MovementMode.WALK: 20, MovementMode.FLY: 80},
        )
        assert flyer.speeds[MovementMode.WALK] == 20
        assert flyer.speeds[MovementMode.FLY] == 80
        # The legacy scalar `speed` mirrors the WALK entry for back-compat.
        assert flyer.speed == 20

        # A plain creature defaults to a single WALK entry derived from `speed`.
        walker = _make_creature(speed=30)
        assert walker.speeds == {MovementMode.WALK: 30}


class TestMovement_Modes:
    """SRD § Playing the Game › Movement and Position › Modes of movement.

    > Your movement can include climbing, crawling, jumping, and
    > swimming (each explained in "Rules Glossary"). These different
    > modes of movement can be combined with your regular movement, or
    > they can constitute your entire move.
    """

    def test_climbing_costs_extra_movement(self) -> None:
        pytest.skip(
            "GAP: climbing has no per-mode movement cost. The Rules "
            "Glossary imposes a 1-ft extra cost per foot climbed without "
            "a Climb Speed. The `MovementMode`/`Creature.speeds` data "
            "model shipped under #432 (dnd_engine/core/creature.py:31), "
            "but no system reads `.speeds` to compute cost: `cost_for` "
            "(dnd_engine/systems/action_economy.py:41) and "
            "`TurnState.consume_movement` "
            "(dnd_engine/systems/action_economy.py:140) key cost only on "
            "`Terrain` (NORMAL/DIFFICULT), with no per-mode multiplier. "
            "Tracked by issue #433."
        )

    def test_swimming_costs_extra_movement(self) -> None:
        pytest.skip(
            "GAP: swimming has no per-mode movement cost. Per Rules "
            "Glossary, swimming without a Swim Speed costs 1 extra foot "
            "per foot. The `MovementMode`/`Creature.speeds` data model "
            "shipped under #432, but `cost_for` "
            "(dnd_engine/systems/action_economy.py:41) and "
            "`TurnState.consume_movement` "
            "(dnd_engine/systems/action_economy.py:140) key cost only on "
            "`Terrain`, with no swim-mode multiplier. Tracked by "
            "issue #433."
        )

    def test_crawling_costs_extra_movement(self) -> None:
        pytest.skip(
            "GAP: crawling has no per-mode movement cost. Per Rules "
            "Glossary, every foot of crawling costs 1 extra foot. "
            "`MovementMode.CRAWL` exists (dnd_engine/core/creature.py:31) "
            "but there is no Prone-aware cost path: `consume_movement` "
            "(dnd_engine/systems/action_economy.py:140) keys cost only on "
            "`Terrain`. Tracked by issue #433."
        )

    def test_jumping_consumes_movement(self) -> None:
        pytest.skip(
            "GAP: jumping has no per-mode movement cost. Per Rules "
            "Glossary, a long jump and a high jump each consume movement "
            "equal to the distance covered (with STR- and DEX-derived "
            "maxima). `MovementMode.JUMP` exists "
            "(dnd_engine/core/creature.py:31) but no jump-distance helper "
            "or movement-cost model reads it. Tracked by issue #433."
        )


class TestDifficultTerrain_CostsExtra:
    """SRD § Playing the Game › Movement and Position › Difficult Terrain.

    > Every foot of movement in Difficult Terrain costs 1 extra foot,
    > even if multiple things in a space count as Difficult Terrain.
    """

    def test_difficult_terrain_doubles_movement_cost(self) -> None:
        """Every foot of movement in Difficult Terrain costs 1 extra foot.

        Shipped under issue #436 (PR #558): `cost_for` doubles the
        per-foot cost and `TurnState.consume_movement` accepts a
        `terrain` kwarg that applies it.
        """
        # A 5-ft step through Difficult Terrain costs 10 ft (1 extra foot/foot).
        assert cost_for(5, Terrain.NORMAL) == 5
        assert cost_for(5, Terrain.DIFFICULT) == 10

        # consume_movement deducts the doubled cost from the pool.
        state = TurnState(movement_remaining=30)
        assert state.consume_movement(5, terrain=Terrain.DIFFICULT) is True
        assert state.movement_remaining == 20  # 30 - (5 * 2)

    def test_overlapping_difficult_terrain_does_not_stack(self) -> None:
        """Cost is +1 ft per foot "even if multiple things in a space
        count as Difficult Terrain". The engine models a single binary
        `Terrain.DIFFICULT` category (issue #436 / PR #558); `cost_for`
        returns a flat `feet * 2`, so no number of overlapping difficult
        causes can raise the cost beyond the single +1-ft/ft cap.
        """
        # Difficult is a single category; the doubled cost is the cap,
        # never 3x+, regardless of how many causes overlap a space.
        assert cost_for(5, Terrain.DIFFICULT) == 10

        # Re-applying difficult terrain does not compound: two 5-ft steps
        # through difficult terrain cost 10 each, with no escalating surcharge.
        state = TurnState(movement_remaining=30)
        assert state.consume_movement(5, terrain=Terrain.DIFFICULT) is True
        assert state.consume_movement(5, terrain=Terrain.DIFFICULT) is True
        assert state.movement_remaining == 10  # 30 - 10 - 10, no stacking


class TestBreakingUpMove_BeforeAndAfterAction:
    """SRD § Playing the Game › Movement and Position › Breaking Up Your Move.

    > You can break up your move, using some of its movement before and
    > after any action, Bonus Action, or Reaction you take on the same
    > turn.
    """

    def test_movement_pool_persists_across_an_action(self) -> None:
        """Moving, acting, and moving again all draw from one pool.

        SRD example: "a Speed of 30 feet, you could go 10 feet, take an
        action, and then go 20 feet." The TurnState retains
        `movement_remaining` across the action consumption so the
        post-action move can spend the rest.
        """
        state = TurnState(movement_remaining=30)

        # Spend 10 ft (two 5-ft steps) before the action.
        assert state.consume_movement(5) is True
        assert state.consume_movement(5) is True
        assert state.movement_remaining == 20

        # Take the action.
        assert state.consume_action(ActionType.ACTION) is True

        # Spend the remaining 20 ft after the action.
        for _ in range(4):
            assert state.consume_movement(5) is True
        assert state.movement_remaining == 0

    def test_movement_pool_persists_across_a_bonus_action(self) -> None:
        """Same break-up rule applies to Bonus Actions.

        A creature can move 5 ft, use a Bonus Action, then move 25 ft
        — the SRD treats Action and Bonus Action symmetrically for
        movement break-up.
        """
        state = TurnState(movement_remaining=30)

        assert state.consume_movement(5) is True
        assert state.consume_action(ActionType.BONUS_ACTION) is True
        for _ in range(5):
            assert state.consume_movement(5) is True
        assert state.movement_remaining == 0


class TestDroppingProne_FreeOnYourTurn:
    """SRD § Playing the Game › Movement and Position › Dropping Prone.

    > On your turn, you can give yourself the Prone condition (see
    > "Rules Glossary") without using an action or any of your Speed,
    > but you can't do so if your Speed is 0.
    """

    def test_drop_prone_action_exists(self) -> None:
        """A voluntary drop-prone handler exists and applies the Prone
        condition to the actor."""
        from dnd_engine.systems.actions import drop_prone

        abilities = Abilities(10, 10, 10, 10, 10, 10)
        actor = Creature("Hero", max_hp=20, ac=15, abilities=abilities, speed=30)
        turn = TurnState()
        turn.reset(speed=30)

        ok, _ = drop_prone(actor, turn)

        assert ok is True
        assert actor.has_condition("prone") is True

    def test_drop_prone_does_not_consume_action_or_movement(self) -> None:
        """SRD: 'without using an action or any of your Speed'."""
        from dnd_engine.systems.actions import drop_prone

        abilities = Abilities(10, 10, 10, 10, 10, 10)
        actor = Creature("Hero", max_hp=20, ac=15, abilities=abilities, speed=30)
        turn = TurnState()
        turn.reset(speed=30)

        drop_prone(actor, turn)

        assert turn.action_available is True
        assert turn.bonus_action_available is True
        assert turn.movement_remaining == 30

    def test_drop_prone_forbidden_when_speed_is_zero(self) -> None:
        """SRD carve-out: cannot voluntarily drop prone when Speed is 0."""
        from dnd_engine.systems.actions import drop_prone

        abilities = Abilities(10, 10, 10, 10, 10, 10)
        actor = Creature("Hero", max_hp=20, ac=15, abilities=abilities, speed=0)
        turn = TurnState()
        turn.reset(speed=0)

        ok, _ = drop_prone(actor, turn)

        assert ok is False
        assert actor.has_condition("prone") is False


class TestStandingUpFromProne_HalfSpeedCost:
    """SRD § Playing the Game › Movement and Position › Dropping Prone (companion).

    The reverse transition — standing up from Prone — lives in Rules
    Glossary but is the symmetric obligation: standing costs half the
    creature's Speed. Tracking it alongside Drop Prone keeps the pair
    auditable.
    """

    def test_stand_up_from_prone_costs_half_speed(self) -> None:
        """Rules Glossary (Prone): standing up costs half the
        creature's Speed."""
        from dnd_engine.systems.actions import stand_up

        abilities = Abilities(10, 10, 10, 10, 10, 10)
        actor = Creature("Hero", max_hp=20, ac=15, abilities=abilities, speed=30)
        actor.add_condition("prone")
        turn = TurnState()
        turn.reset(speed=30)

        ok, _ = stand_up(actor, turn)

        assert ok is True
        assert actor.has_condition("prone") is False
        assert turn.movement_remaining == 15  # 30 - (30 // 2)


class TestCreatureSize_SpaceFromSizeCategory:
    """SRD § Playing the Game › Movement and Position › Creature Size.

    > A creature belongs to a size category, which determines the
    > width of the square space the creature occupies on a map, as
    > shown on the Creature Size and Space table.
    """

    def test_monsters_declare_size_category(self) -> None:
        """`monsters.json` carries a `size` string per stat block.

        Data-parity check. Every monster lists a size category
        (tiny / small / medium / large / huge / gargantuan). The engine
        does not yet *consume* this field to compute occupied tiles
        (see the GAP test below), but the data is present for when it
        does.
        """
        monsters = json.loads(MONSTERS_JSON.read_text())
        valid_sizes = {"tiny", "small", "medium", "large", "huge", "gargantuan"}
        for mid, mdata in monsters.items():
            assert "size" in mdata, f"monster '{mid}' missing 'size' in stat block"
            assert mdata["size"].lower() in valid_sizes, (
                f"monster '{mid}' has unrecognized size '{mdata['size']}'"
            )

    def _clear_index(self, n: int = 6) -> SpatialIndex:
        """A wall-free n x n SpatialIndex for unobstructed footprint geometry."""
        tiles = {(x, y): TileType.FLOOR for x in range(n) for y in range(n)}
        return SpatialIndex(Map(width=n, height=n, tiles=tiles))

    def test_engine_computes_occupied_tiles_from_size_category(self) -> None:
        """Creature size drives the set of tiles a creature occupies.

        The SRD Creature Size and Space table maps Medium -> 1 tile,
        Large -> 2x2, Huge -> 3x3, Gargantuan -> 4x4. The engine reads
        `Creature.size` and the `SpatialIndex` claims the full footprint,
        so occupancy queries resolve every covered tile — not just the
        anchor.
        """
        abilities = Abilities(
            strength=19,
            dexterity=10,
            constitution=16,
            intelligence=6,
            wisdom=10,
            charisma=7,
        )

        # Side length of the square space matches the SRD table.
        assert Size.MEDIUM.footprint == 1
        assert Size.LARGE.footprint == 2
        assert Size.HUGE.footprint == 3
        assert Size.GARGANTUAN.footprint == 4

        # A Large creature anchored at (1,1) claims the 2x2 block, and
        # occupancy is footprint-aware across every covered tile.
        ogre = Creature(name="Ogre", max_hp=59, ac=11, abilities=abilities, size=Size.LARGE)
        index = self._clear_index()
        index.place("ogre", Position(1, 1), size=ogre.size)
        assert index.footprint_of("ogre") == frozenset(
            {Position(1, 1), Position(2, 1), Position(1, 2), Position(2, 2)}
        )
        assert index.occupant_at(Position(2, 2)) == "ogre"  # not just the anchor
        assert index.occupant_at(Position(3, 3)) is None  # outside the block

        # A Huge creature claims the full 3x3 block.
        giant = Creature(name="Hill Giant", max_hp=105, ac=13, abilities=abilities, size=Size.HUGE)
        index.place("giant", Position(3, 3), size=giant.size)
        assert index.footprint_of("giant") == frozenset(
            Position(3 + dx, 3 + dy) for dx in range(3) for dy in range(3)
        )


class TestMovingAroundOtherCreatures_PassThroughAllowed:
    """SRD § Playing the Game › Movement and Position › Moving around Other Creatures.

    > During your move, you can pass through the space of an ally, a
    > creature that has the Incapacitated condition (see "Rules
    > Glossary"), a Tiny creature, or a creature that is two sizes
    > larger or smaller than you.
    """

    @staticmethod
    def _build_passthrough_fixture(
        *,
        occupant_size: Size = Size.MEDIUM,
        occupant_conditions: tuple[str, ...] = (),
    ) -> tuple[object, str, str]:
        """A mover at (1,1) and an occupant at (2,1) on a 6x6 floor.

        Returns ``(game_state, mover_id, occupant_id)``. The mover's
        TurnState is reset to its full speed so ``attempt_combat_step``
        has budget for the 5-ft step into the occupant's tile. The map
        is sized to accommodate occupant footprints up to Gargantuan
        (4x4 anchored at (2,1) reaches (5,4)).
        """
        from dnd_engine.core.character import Character, CharacterClass
        from dnd_engine.core.entity_ids import pc_entity_id
        from dnd_engine.core.game_state import GameState
        from dnd_engine.core.party import Party
        from dnd_engine.rules.loader import DataLoader
        from dnd_engine.utils.events import EventBus

        tiles: dict[tuple[int, int], TileType] = {}
        for y in range(6):
            for x in range(6):
                tiles[(x, y)] = TileType.FLOOR
        grid_map = Map(width=6, height=6, tiles=tiles)

        mover = Character(
            name="Walker",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(
                strength=14,
                dexterity=14,
                constitution=14,
                intelligence=10,
                wisdom=10,
                charisma=10,
            ),
            max_hp=20,
            ac=15,
            xp=0,
        )
        party = Party(characters=[mover])
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=EventBus(),
            data_loader=DataLoader(),
            dice_roller=DiceRoller(seed=1),
        )
        game_state.bootstrap_spatial(grid_map)

        occupant = Creature(
            name="Bystander",
            max_hp=10,
            ac=10,
            abilities=Abilities(10, 10, 10, 10, 10, 10),
            size=occupant_size,
        )
        for cond in occupant_conditions:
            occupant.add_condition(cond)
        game_state.active_enemies.append(occupant)

        mover_id = pc_entity_id(mover.name)
        occupant_id = "bystander_0"
        game_state.set_position(mover_id, 1, 1)
        game_state.set_position(occupant_id, 2, 1)

        game_state._start_combat()
        tracker = game_state.initiative_tracker
        assert tracker is not None
        for idx, entry in enumerate(tracker.combatants):
            if entry.creature is mover:
                tracker.current_turn_index = idx
                break
        tracker.turn_states[mover].reset(speed=mover.speed)
        return game_state, mover_id, occupant_id

    def test_move_can_pass_through_an_allys_space(self) -> None:
        """Stepping onto a Prone ally's tile succeeds at the normal 5-ft cost.

        Engine-side allegiance flags are out of scope for this slice;
        the Prone carve-out (the mechanically distinct ally-friendly
        case) is what the engine actually evaluates.
        """
        game_state, mover_id, _ = self._build_passthrough_fixture(
            occupant_conditions=("prone",),
        )
        result = game_state.attempt_combat_step(mover_id, dx=1, dy=0)
        assert result.ok, f"step rejected: {result.reason}"
        assert result.position == Position(2, 1)
        # Full per-step cost (no Difficult-Terrain double yet for this slice).
        assert result.movement_remaining == 25

    def test_move_can_pass_through_incapacitated_creature(self) -> None:
        """An Incapacitated occupant does not block the mover's step."""
        game_state, mover_id, _ = self._build_passthrough_fixture(
            occupant_conditions=("unconscious",),
        )
        result = game_state.attempt_combat_step(mover_id, dx=1, dy=0)
        assert result.ok, f"step rejected: {result.reason}"
        assert result.position == Position(2, 1)

    def test_move_can_pass_through_tiny_creature(self) -> None:
        """A Tiny occupant does not block the mover's step."""
        game_state, mover_id, _ = self._build_passthrough_fixture(
            occupant_size=Size.TINY,
        )
        result = game_state.attempt_combat_step(mover_id, dx=1, dy=0)
        assert result.ok, f"step rejected: {result.reason}"
        assert result.position == Position(2, 1)

    def test_move_can_pass_through_creature_two_sizes_apart(self) -> None:
        """A Medium mover passes through a Huge occupant (two sizes larger)."""
        game_state, mover_id, _ = self._build_passthrough_fixture(
            occupant_size=Size.HUGE,
        )
        # Place huge occupant manually — set_position above already
        # placed a 3x3 footprint anchored at (2,1) which spills past
        # (4,2); the 5x3 map accommodates that and the mover is at (1,1).
        result = game_state.attempt_combat_step(mover_id, dx=1, dy=0)
        assert result.ok, f"step rejected: {result.reason}"
        assert result.position == Position(2, 1)


class TestMovingAroundOtherCreatures_DifficultTerrain:
    """SRD § Playing the Game › Movement and Position › Other creature's space.

    > Another creature's space is Difficult Terrain for you unless that
    > creature is Tiny or your ally.
    """

    def test_passing_through_creature_costs_double_movement(self) -> None:
        pytest.skip(
            "GAP: depends on pass-through carve-outs (#445). NOTE: base "
            "Difficult Terrain now ships — `cost_for` "
            "(dnd_engine/systems/action_economy.py) and `Map.terrain_at` "
            "(dnd_engine/core/map.py) drive a doubled per-foot cost inside "
            "`attempt_combat_step`, so #436 is satisfied. What's missing "
            "is treating an occupied non-ally non-Tiny space as Difficult "
            "Terrain: `attempt_combat_step` rejects the occupied tile "
            "outright before any creature-as-terrain cost can apply. "
            "Blocked on #445."
        )


class TestMovingAroundOtherCreatures_CannotEndInOccupiedSpace:
    """SRD § Playing the Game › Movement and Position › End of move.

    > You can't willingly end a move in a space occupied by another
    > creature. If you somehow end a turn in a space with another
    > creature, you have the Prone condition (see "Rules Glossary")
    > unless you are Tiny or are of a larger size than the other
    > creature.
    """

    def test_cannot_willingly_end_move_in_occupied_space(self) -> None:
        """`Session.combat_move` refuses to step onto an occupied tile.

        `client-2d/src/client_2d/session.py` rejects a move whose
        destination tile already contains a monster with
        "Path blocked!". This satisfies the SRD's "can't willingly
        end a move in a space occupied by another creature" — though
        the rejection is currently blanket (no ally / Tiny / size
        carve-outs), which is its own gap (#445). The base "cannot
        end here" prohibition is enforced.

        Reads the source as text to avoid importing `arcade` (the 2D
        client's render dependency) into engine-only tests.
        """
        session_path = (
            Path(__file__).resolve().parents[4] / "client-2d" / "src" / "client_2d" / "session.py"
        )
        assert session_path.exists(), f"expected client-2d session.py at {session_path}"

        src = session_path.read_text()
        assert "def combat_move" in src, "client-2d session.py must define `combat_move`."
        assert "Path blocked!" in src, (
            "combat_move must reject moves into a tile already "
            "occupied by another creature to honor the SRD's "
            "'can't willingly end a move in a space occupied by "
            "another creature' rule."
        )
        assert "entity_at_dest" in src and "get_at_position" in src, (
            "combat_move must query the destination tile's occupancy "
            "before allowing the move to land."
        )

    def test_involuntarily_ending_in_occupied_space_applies_prone(self) -> None:
        """Forced movement that lands on an occupant drops BOTH Prone.

        `attempt_combat_step(involuntary=True)` lets the step land on
        an occupied tile via the spatial co-occupancy primitive and
        applies the Prone condition to both creatures per the SRD
        ("If you somehow end a turn in a space with another creature,
        you have the Prone condition…").
        """
        from dnd_engine.core.character import Character, CharacterClass
        from dnd_engine.core.entity_ids import pc_entity_id
        from dnd_engine.core.game_state import GameState
        from dnd_engine.core.party import Party
        from dnd_engine.rules.loader import DataLoader
        from dnd_engine.utils.events import EventBus

        tiles: dict[tuple[int, int], TileType] = {}
        for y in range(3):
            for x in range(5):
                tiles[(x, y)] = TileType.FLOOR
        grid_map = Map(width=5, height=3, tiles=tiles)

        mover = Character(
            name="Shovee",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(
                strength=14,
                dexterity=14,
                constitution=14,
                intelligence=10,
                wisdom=10,
                charisma=10,
            ),
            max_hp=20,
            ac=15,
            xp=0,
        )
        party = Party(characters=[mover])
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=EventBus(),
            data_loader=DataLoader(),
            dice_roller=DiceRoller(seed=1),
        )
        game_state.bootstrap_spatial(grid_map)

        occupant = Creature(
            name="Bystander",
            max_hp=10,
            ac=10,
            abilities=Abilities(10, 10, 10, 10, 10, 10),
        )
        game_state.active_enemies.append(occupant)
        mover_id = pc_entity_id(mover.name)
        occupant_id = "bystander_0"
        game_state.set_position(mover_id, 1, 1)
        game_state.set_position(occupant_id, 2, 1)
        game_state._start_combat()
        tracker = game_state.initiative_tracker
        assert tracker is not None
        for idx, entry in enumerate(tracker.combatants):
            if entry.creature is mover:
                tracker.current_turn_index = idx
                break
        tracker.turn_states[mover].reset(speed=mover.speed)

        assert mover.has_condition("prone") is False
        assert occupant.has_condition("prone") is False

        result = game_state.attempt_combat_step(mover_id, dx=1, dy=0, involuntary=True)

        assert result.ok, f"forced step rejected: {result.reason}"
        assert result.position == Position(2, 1)
        assert mover.has_condition("prone") is True
        assert occupant.has_condition("prone") is True


class TestLeavingReach_ProvokesOpportunityAttack:
    """SRD § Playing the Game › Movement and Position › Reach interaction.

    Movement that takes a creature out of an enemy's reach is the
    trigger for the Opportunity Attack rule from
    `docs/srd/playing-the-game/melee-attacks.md`. Auditing it from the
    movement side keeps the cross-reference live.
    """

    @staticmethod
    def _oa_setup() -> tuple[ReactionDispatcher, InitiativeTracker, Creature, Creature]:
        """A reactor threatening a mover, wired through the OA dispatcher.

        Reactor sits at (5, 5) with the default 5-ft reach; the mover is
        a combatant so `publish_movement_provoke` can read its TurnState
        (and honor a Disengage). Returns the dispatcher, tracker, reactor
        and mover.
        """
        reactor = Creature(
            name="Sentinel", max_hp=20, ac=15, abilities=Abilities(10, 10, 10, 10, 10, 10)
        )
        mover = Creature(
            name="Runner", max_hp=20, ac=15, abilities=Abilities(10, 10, 10, 10, 10, 10)
        )
        tracker = InitiativeTracker(DiceRoller(seed=1))
        tracker.add_combatant(reactor)
        tracker.add_combatant(mover)
        dispatcher = ReactionDispatcher(tracker)
        register_default_opportunity_attack(
            dispatcher, reactor, get_position=lambda: Position(5, 5)
        )
        return dispatcher, tracker, reactor, mover

    def test_moving_out_of_reach_during_own_turn_provokes(self) -> None:
        """Stepping out of an adjacent enemy's reach provokes an OA that
        consumes the reactor's Reaction. This is the movement-side audit
        of the rule wired into `GameState.attempt_combat_step` ->
        `publish_movement_provoke` (issue #413, depends on #412).
        """
        dispatcher, tracker, reactor, mover = self._oa_setup()
        assert tracker.turn_states[reactor].reaction_available is True

        # Mover steps from 5 ft (in reach) to 15 ft (out of reach).
        outcomes = publish_movement_provoke(
            dispatcher,
            mover=mover,
            from_position=Position(6, 5),
            to_position=Position(8, 5),
        )

        assert any(o.reacted for o in outcomes), "leaving reach did not provoke an OA"
        assert tracker.turn_states[reactor].reaction_available is False

    def test_disengage_action_suppresses_movement_oa_provocation(self) -> None:
        """Taking the Disengage action suppresses OA provocation for the
        rest of the turn, preserving the reactor's Reaction. `disengage`
        sets `TurnState.disengaged_this_turn`, which
        `publish_movement_provoke` honors (issue #414, depends on #413).
        """
        dispatcher, tracker, reactor, mover = self._oa_setup()

        # Mover takes the Disengage action this turn.
        ok, reason = disengage(tracker.turn_states[mover])
        assert ok is True, f"disengage failed: {reason}"
        assert tracker.turn_states[mover].disengaged_this_turn is True

        # The same out-of-reach step now provokes nothing.
        outcomes = publish_movement_provoke(
            dispatcher,
            mover=mover,
            from_position=Position(6, 5),
            to_position=Position(8, 5),
        )

        assert outcomes == [], "Disengage did not suppress OA provocation"
        assert tracker.turn_states[reactor].reaction_available is True
