# ABOUTME: Integration test — monster Opportunity Attacks fire through the real
# ABOUTME: _start_combat bootstrap + attempt_combat_step path (plan-10 W1).

from __future__ import annotations

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.game_state import GameState
from dnd_engine.core.map import Map, TileType
from dnd_engine.core.party import Party
from dnd_engine.core.position import Position
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import Event, EventBus, EventType


def _floor_map(size: int = 7) -> Map:
    """An all-floor square map so movement geometry is the only variable."""
    tiles = {(x, y): TileType.FLOOR for x in range(size) for y in range(size)}
    return Map(width=size, height=size, tiles=tiles)


def _pc_id(name: str) -> str:
    """Mirror the EngineAdapter / GameState PC entity-id convention."""
    return f"pc_{name.lower().replace(' ', '_')}"


def _make_game_state() -> tuple[GameState, str, str]:
    """Build a combat-ready GameState with one PC and one goblin, both
    placed in the spatial index BEFORE ``_start_combat`` so the OA
    registration walk subscribes them. The PC starts 5 ft south of the
    goblin (within its reach) and is forced to be the current combatant.

    The PC's AC is set to 1 so the goblin's Opportunity Attack reliably
    connects — but the load-bearing assertions key off Reaction-slot
    consumption, which is roll-independent.
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
        ac=1,
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
    goblin_id = "goblin_0"  # index 0 in active_enemies
    # Place both BEFORE combat starts: _register_default_opportunity_attacks
    # walks the spatial index at _start_combat time and only subscribes
    # entities already placed.
    gs.set_position(goblin_id, 3, 3)
    gs.set_position(pc_id, 3, 4)  # 5 ft south of the goblin — within reach.

    gs._start_combat()

    # attempt_combat_step consults the *current* turn state, not the mover's
    # id — force the PC's turn so its movement budget is the one consumed.
    fighter_idx = next(
        i
        for i, entry in enumerate(gs.initiative_tracker.combatants)
        if entry.creature is fighter
    )
    gs.initiative_tracker.current_turn_index = fighter_idx
    gs.initiative_tracker.turn_states[fighter].reset(speed=fighter.speed)
    return gs, pc_id, goblin_id


class TestMonsterOpportunityAttackFiresOnMovement:
    def test_moving_out_of_reach_consumes_reactor_reaction(self) -> None:
        """SRD: leaving a hostile creature's reach provokes an Opportunity
        Attack, spending the reactor's Reaction."""
        gs, pc_id, _goblin_id = _make_game_state()
        goblin = gs.active_enemies[0]
        assert gs.initiative_tracker.turn_states[goblin].reaction_available is True

        # PC steps south (3,4) -> (3,5): now 10 ft from the goblin, leaving
        # its 5 ft reach.
        result = gs.attempt_combat_step(pc_id, 0, 1)

        assert result.ok is True
        assert result.position == Position(3, 5)
        assert gs.initiative_tracker.turn_states[goblin].reaction_available is False

    def test_moving_within_reach_does_not_provoke(self) -> None:
        """Moving while staying inside the reactor's reach must NOT provoke,
        so the reaction slot survives for a genuine departure."""
        gs, pc_id, _goblin_id = _make_game_state()
        goblin = gs.active_enemies[0]

        # PC steps east (3,4) -> (4,4): still 5 ft (diagonal) from the goblin.
        result = gs.attempt_combat_step(pc_id, 1, 0)

        assert result.ok is True
        assert result.position == Position(4, 4)
        assert gs.initiative_tracker.turn_states[goblin].reaction_available is True

    def test_oa_hit_emits_damage_dealt_with_flag(self) -> None:
        """The full resolution path: a connecting OA emits DAMAGE_DEALT
        tagged ``opportunity_attack`` so clients can surface it."""
        gs, pc_id, _goblin_id = _make_game_state()
        captured: list[Event] = []
        gs.event_bus.subscribe(EventType.DAMAGE_DEALT, captured.append)

        gs.attempt_combat_step(pc_id, 0, 1)  # provoking move

        oa_events = [e for e in captured if e.data.get("opportunity_attack")]
        assert len(oa_events) == 1
        assert oa_events[0].data["attacker"] == "Goblin"
        assert oa_events[0].data["defender"] == "Fighter 1"


def _make_late_bootstrap_state() -> tuple[GameState, str, str]:
    """Build a combat-ready GameState the way the scenario loader does:
    ``_start_combat`` runs *before* the SpatialIndex exists, so the
    registration walk inside it subscribes nobody. The caller is expected
    to bootstrap spatial, place the combatants, and then invoke
    ``register_opportunity_attacks`` to wire the handlers.
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
        ac=1,
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
    goblin = gs.data_loader.create_monster("goblin")
    gs.active_enemies.append(goblin)

    # Combat starts with spatial still None — mirrors ScenarioLoader.load.
    gs._start_combat()

    # Only now does the client-side bootstrap happen: install the index,
    # place the combatants, then re-register OA handlers.
    gs.bootstrap_spatial(_floor_map())
    pc_id = _pc_id(fighter.name)
    goblin_id = "goblin_0"
    gs.set_position(goblin_id, 3, 3)
    gs.set_position(pc_id, 3, 4)

    fighter_idx = next(
        i
        for i, entry in enumerate(gs.initiative_tracker.combatants)
        if entry.creature is fighter
    )
    gs.initiative_tracker.current_turn_index = fighter_idx
    gs.initiative_tracker.turn_states[fighter].reset(speed=fighter.speed)
    return gs, pc_id, goblin_id


class TestRegisterAfterLateBootstrap:
    """The scenario-loader ordering: combat starts before spatial exists.
    ``register_opportunity_attacks`` is the public entry that wires the
    handlers once the index is populated."""

    def test_register_after_bootstrap_arms_opportunity_attacks(self) -> None:
        """After a late bootstrap, calling the public registration entry
        makes a provoking move spend the reactor's Reaction."""
        gs, pc_id, _goblin_id = _make_late_bootstrap_state()
        goblin = gs.active_enemies[0]

        gs.register_opportunity_attacks()

        result = gs.attempt_combat_step(pc_id, 0, 1)  # leaves 5 ft reach

        assert result.ok is True
        assert gs.initiative_tracker.turn_states[goblin].reaction_available is False

    def test_without_registration_no_opportunity_attack_fires(self) -> None:
        """Negative control: skipping the public registration after a late
        bootstrap leaves the handlers unwired, so the same move provokes
        nothing — proving the call is load-bearing."""
        gs, pc_id, _goblin_id = _make_late_bootstrap_state()
        goblin = gs.active_enemies[0]

        # Deliberately do NOT call register_opportunity_attacks().
        result = gs.attempt_combat_step(pc_id, 0, 1)

        assert result.ok is True
        assert gs.initiative_tracker.turn_states[goblin].reaction_available is True
