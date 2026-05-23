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

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.systems.action_economy import ActionType, TurnState

pytestmark = pytest.mark.srd(
    "playing-the-game/movement-and-position.md",
    lines="1864-1974",
)


MONSTERS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "monsters.json"
)
RACES_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "races.json"
)


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
        """"Or you can decide not to move." — zero consumption is legal.

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
        pytest.skip(
            "GAP: special speeds (Climb / Fly / Swim / Burrow) are not "
            "modeled. `Creature` exposes a single scalar `speed` "
            "(dnd_engine/core/creature.py:89) and `monsters.json` only "
            "declares a single integer `speed` per stat block. The "
            "client-2d combat-move path treats one tile as 5 ft of the "
            "creature's only speed (client-2d/src/client_2d/session.py:912), "
            "so a flying or aquatic creature has no engine-tracked way to "
            "spend a Fly Speed or Swim Speed. Tracked by issue #432."
        )


class TestMovement_Modes:
    """SRD § Playing the Game › Movement and Position › Modes of movement.

    > Your movement can include climbing, crawling, jumping, and
    > swimming (each explained in "Rules Glossary"). These different
    > modes of movement can be combined with your regular movement, or
    > they can constitute your entire move.
    """

    def test_climbing_costs_extra_movement(self) -> None:
        pytest.skip(
            "GAP: climbing is not a tracked movement mode. The Rules "
            "Glossary entry for Climbing imposes a 1-ft extra cost per "
            "foot climbed without a Climb Speed. The engine has no "
            "concept of climbable terrain or per-mode cost; "
            "`TurnState.consume_movement` (dnd_engine/systems/action_economy.py:83) "
            "takes a flat feet argument and the client-2d combat-move "
            "always charges 5 ft per tile. Tracked by issue #433."
        )

    def test_swimming_costs_extra_movement(self) -> None:
        pytest.skip(
            "GAP: swimming is not a tracked movement mode. Per Rules "
            "Glossary, swimming without a Swim Speed costs 1 extra foot "
            "per foot. The engine has no aquatic terrain model and no "
            "per-mode cost in `TurnState.consume_movement`. Tracked by "
            "issue #433."
        )

    def test_crawling_costs_extra_movement(self) -> None:
        pytest.skip(
            "GAP: crawling is not a tracked movement mode. Per Rules "
            "Glossary, every foot of crawling costs 1 extra foot. The "
            "engine has no Prone-aware movement cost; `consume_movement` "
            "takes a flat feet argument. Tracked by issue #433."
        )

    def test_jumping_consumes_movement(self) -> None:
        pytest.skip(
            "GAP: jumping is not a tracked movement mode. Per Rules "
            "Glossary, a long jump and a high jump each consume movement "
            "equal to the distance covered (with STR- and DEX-derived "
            "maxima). No jump action, helper, or movement-cost model "
            "exists in the engine. Tracked by issue #433."
        )


class TestDifficultTerrain_CostsExtra:
    """SRD § Playing the Game › Movement and Position › Difficult Terrain.

    > Every foot of movement in Difficult Terrain costs 1 extra foot,
    > even if multiple things in a space count as Difficult Terrain.
    """

    def test_difficult_terrain_doubles_movement_cost(self) -> None:
        pytest.skip(
            "GAP: Difficult Terrain is not modeled. `TurnState."
            "consume_movement` (dnd_engine/systems/action_economy.py:83) "
            "accepts a flat feet argument; the 2D client charges a fixed "
            "5 ft per tile in combat-move "
            "(client-2d/src/client_2d/session.py:912) with no terrain "
            "query. `RoomLayout` (client-2d/src/client_2d/integration/"
            "layout_schema.py) declares WALL and PIT tile types but has "
            "no Difficult Terrain tile type or `is_difficult_terrain` "
            "predicate. Tracked by issue #436."
        )

    def test_overlapping_difficult_terrain_does_not_stack(self) -> None:
        pytest.skip(
            "GAP: dependent on Difficult Terrain existing first. The "
            "SRD caps the cost at +1 ft per foot regardless of how many "
            "Difficult-Terrain causes overlap in a space. Until the "
            "base mechanic ships (#436), this cap has nothing to guard."
        )


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
        pytest.skip(
            "GAP: no `drop_prone` action handler. `Creature.add_condition('prone')` "
            "(dnd_engine/core/creature.py:242) is the only way to apply "
            "the Prone condition, and it's used by spell/trap effects "
            "(e.g., the `caltrops` item rolls a DC 10 DEX save to "
            "knock the target prone). There is no scenario script "
            "action, MCP tool, or client UI for a creature to "
            "voluntarily drop prone on its own turn. Tracked by "
            "issue #439."
        )

    def test_drop_prone_does_not_consume_action_or_movement(self) -> None:
        pytest.skip(
            "GAP: dependent on a drop-prone action existing (#439). "
            "Per SRD it must not consume the actor's action, bonus "
            "action, or any of its Speed pool. Once the action handler "
            "lands, it must call neither `consume_action` nor "
            "`consume_movement`."
        )

    def test_drop_prone_forbidden_when_speed_is_zero(self) -> None:
        pytest.skip(
            "GAP: dependent on a drop-prone action existing (#439). "
            "SRD carve-out: a creature with Speed 0 (e.g., grappled, "
            "restrained, or zero-Speed condition) cannot voluntarily "
            "drop prone. The handler must read the creature's current "
            "effective Speed before allowing the transition."
        )


class TestStandingUpFromProne_HalfSpeedCost:
    """SRD § Playing the Game › Movement and Position › Dropping Prone (companion).

    The reverse transition — standing up from Prone — lives in Rules
    Glossary but is the symmetric obligation: standing costs half the
    creature's Speed. Tracking it alongside Drop Prone keeps the pair
    auditable.
    """

    def test_stand_up_from_prone_costs_half_speed(self) -> None:
        pytest.skip(
            "GAP: no `stand_up` action handler. Per Rules Glossary "
            "(Prone): standing up costs half the creature's Speed. No "
            "engine code consumes half of `TurnState.movement_remaining` "
            "to clear the Prone condition. Tracked by issue #439."
        )


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

    def test_engine_computes_occupied_tiles_from_size_category(self) -> None:
        pytest.skip(
            "GAP: creature size does not drive map footprint. The SRD "
            "Size table maps Large -> 2x2 tiles, Huge -> 3x3, "
            "Gargantuan -> 4x4. The `Creature` class does not store a "
            "size category; `monsters.json` records `size` as a string "
            "but no code (engine or client-2d) reads it to size the "
            "creature's footprint. `EntityManager.get_at_position` "
            "(client-2d/src/client_2d/entities/entity_manager.py) "
            "treats every entity as a single-tile occupant. Tracked by "
            "issue #442."
        )


class TestMovingAroundOtherCreatures_PassThroughAllowed:
    """SRD § Playing the Game › Movement and Position › Moving around Other Creatures.

    > During your move, you can pass through the space of an ally, a
    > creature that has the Incapacitated condition (see "Rules
    > Glossary"), a Tiny creature, or a creature that is two sizes
    > larger or smaller than you.
    """

    def test_move_can_pass_through_an_allys_space(self) -> None:
        pytest.skip(
            "GAP: the combat-move path treats any occupied destination "
            "tile as blocked. `Session.combat_move` "
            "(client-2d/src/client_2d/session.py:902-908) rejects any "
            "monster at the destination with 'Path blocked!'; no "
            "ally / incapacitated / size-relative carve-out is wired "
            "up. Engine-side movement has no per-creature OAs or "
            "pass-through query either. Tracked by issue #445."
        )

    def test_move_can_pass_through_incapacitated_creature(self) -> None:
        pytest.skip(
            "GAP: dependent on pass-through carve-outs existing (#445). "
            "Per SRD, an Incapacitated creature does not block "
            "movement. The combat-move path consults neither "
            "`Creature.has_condition('incapacitated')` nor any size "
            "comparison when rejecting a destination tile."
        )

    def test_move_can_pass_through_tiny_creature(self) -> None:
        pytest.skip(
            "GAP: dependent on pass-through carve-outs existing (#445). "
            "Per SRD, a Tiny creature does not block movement. Until "
            "creature size is read by the movement path (#442 / #445), "
            "this carve-out cannot be honored."
        )

    def test_move_can_pass_through_creature_two_sizes_apart(self) -> None:
        pytest.skip(
            "GAP: dependent on pass-through carve-outs existing (#445) "
            "and creature size being modeled (#442). Per SRD, a "
            "creature can pass through one that is two sizes larger or "
            "smaller (e.g., a Medium PC can move through a Huge "
            "monster's space)."
        )


class TestMovingAroundOtherCreatures_DifficultTerrain:
    """SRD § Playing the Game › Movement and Position › Other creature's space.

    > Another creature's space is Difficult Terrain for you unless that
    > creature is Tiny or your ally.
    """

    def test_passing_through_creature_costs_double_movement(self) -> None:
        pytest.skip(
            "GAP: depends on Difficult Terrain (#436) and the pass-"
            "through carve-outs (#445). Even when pass-through is "
            "allowed, the SRD imposes Difficult Terrain cost on the "
            "space of a non-Tiny non-ally creature. Neither the cost "
            "rule nor the carve-out exists today, so the combined "
            "behavior has no enforcement path."
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
            Path(__file__).resolve().parents[4]
            / "client-2d"
            / "src"
            / "client_2d"
            / "session.py"
        )
        assert session_path.exists(), (
            f"expected client-2d session.py at {session_path}"
        )

        src = session_path.read_text()
        assert "def combat_move" in src, (
            "client-2d session.py must define `combat_move`."
        )
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
        pytest.skip(
            "GAP: the carve-out for involuntary co-occupancy is not "
            "modeled. Per SRD, if a creature 'somehow' ends a turn in "
            "a space with another (e.g., shoved, pulled by an effect), "
            "it gains the Prone condition unless it is Tiny or larger "
            "than the other creature. No engine path applies Prone on "
            "involuntary co-occupancy. Tracked by issue #445."
        )


class TestLeavingReach_ProvokesOpportunityAttack:
    """SRD § Playing the Game › Movement and Position › Reach interaction.

    Movement that takes a creature out of an enemy's reach is the
    trigger for the Opportunity Attack rule from
    `docs/srd/playing-the-game/melee-attacks.md`. Auditing it from the
    movement side keeps the cross-reference live.
    """

    def test_moving_out_of_reach_during_own_turn_provokes(self) -> None:
        pytest.skip(
            "GAP: OAs do not fire on tactical movement out of reach. "
            "The engine's only OA path is `flee_combat()` "
            "(dnd_engine/core/game_state.py:4194), which is a "
            "party-wide retreat trigger and does not introspect "
            "per-creature reach against a moving creature's path. "
            "`Session.combat_move` (client-2d/src/client_2d/session.py:871) "
            "applies no OA hook when a creature steps off a tile "
            "adjacent to an enemy. Tracked by issue #413 (depends on "
            "#412 Reaction economy)."
        )

    def test_disengage_action_suppresses_movement_oa_provocation(self) -> None:
        pytest.skip(
            "GAP: Disengage is not a playable action. The string "
            "'Disengage' appears only as flavor text in "
            "dnd_engine/data/srd/classes.json (rogue cunning action) "
            "and dnd_engine/data/srd/monsters.json (goblin Nimble "
            "Escape, spy). No action handler, dispatcher, or "
            "movement-flag is wired up. Tracked by issue #414 "
            "(depends on #413 per-creature OAs)."
        )
