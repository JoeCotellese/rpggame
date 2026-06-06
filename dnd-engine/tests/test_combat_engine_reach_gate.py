# ABOUTME: Tests for the engine-level melee reach gate added to CombatEngine.resolve_attack (#634).
# ABOUTME: Mirrors the ranged-range pattern (#401) — reject melee attacks when distance > action.reach.

from __future__ import annotations

import json
from pathlib import Path

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.combat import CombatEngine
from dnd_engine.core.combat_geometry import attack_reach_for, is_ranged_action
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.entity_ids import pc_entity_id
from dnd_engine.core.game_state import GameState
from dnd_engine.core.map import Map, TileType
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus

MONSTERS_JSON = (
    Path(__file__).resolve().parents[1]
    / "dnd_engine"
    / "data"
    / "srd"
    / "monsters.json"
)


def _build_engine_fixture(
    attacker_pos: tuple[int, int],
    defender_pos: tuple[int, int],
    *,
    enemy_id: str = "giant_rat",
) -> tuple[GameState, Creature, Character]:
    """Construct a GameState with an enemy and a PC placed at given tiles.

    The map is a 20x20 open floor — enough room for any small-grid
    reach test (5/10/15/30 ft). The PC is a fighter (high AC so the
    test doesn't depend on the attack roll happening to miss). The
    enemy is loaded from the SRD catalog so its actions carry the
    real `reach`/`range` fields the gate will read.
    """
    tiles: dict[tuple[int, int], TileType] = {}
    for y in range(20):
        for x in range(20):
            tiles[(x, y)] = TileType.FLOOR
    grid_map = Map(width=20, height=20, tiles=tiles)

    fighter = Character(
        name="Brick",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=Abilities(
            strength=16, dexterity=14, constitution=15,
            intelligence=10, wisdom=12, charisma=8,
        ),
        max_hp=20,
        ac=16,
        xp=0,
    )
    party = Party(characters=[fighter])

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

    pc_id = pc_entity_id(fighter.name)
    enemy_eid = f"{enemy_id}_0"
    game_state.set_position(pc_id, defender_pos[0], defender_pos[1])
    game_state.set_position(enemy_eid, attacker_pos[0], attacker_pos[1])

    return game_state, enemy, fighter


class TestAttackReachForHelper:
    """The promoted attack_reach_for(action) helper parses monster reach.

    Behavioral parity with the original `_attack_reach_for` in
    `script_executor.py` (which now re-exports this implementation).
    """

    def test_parses_5_ft_reach(self):
        assert attack_reach_for({"reach": "5 ft."}) == 5

    def test_parses_10_ft_reach(self):
        assert attack_reach_for({"reach": "10 ft."}) == 10

    def test_missing_action_defaults_to_5(self):
        assert attack_reach_for(None) == 5

    def test_missing_reach_field_defaults_to_5(self):
        assert attack_reach_for({"name": "Bite"}) == 5

    def test_unparseable_reach_defaults_to_5(self):
        assert attack_reach_for({"reach": "garbage"}) == 5


class TestIsRangedAction:
    """is_ranged_action(action) distinguishes ranged from melee."""

    def test_melee_action_with_reach_is_not_ranged(self):
        assert is_ranged_action({"name": "Bite", "reach": "5 ft."}) is False

    def test_ranged_action_with_range_is_ranged(self):
        assert is_ranged_action({"name": "Longbow", "range": "150/600"}) is True

    def test_missing_action_is_not_ranged(self):
        assert is_ranged_action(None) is False


class TestMeleeReachGate:
    """SRD § Playing the Game › Melee Attacks › Reach.

    A melee attack rejects when distance > action.reach. Mirrors the
    ranged-range pattern in `CombatEngine.resolve_attack` (#401's
    successor — #401 left this for melee as future work).
    """

    def test_melee_attack_rejected_beyond_reach(self):
        """Issue #634 repro: 5-ft Bite at 30 ft must NOT land.

        Giant rat at (5, 5), fighter at (5, 11) — Chebyshev distance
        6 tiles = 30 ft. Rat's Bite has 5-ft reach. The gate's
        sentinel is ``attack_roll == 0`` — no d20 was rolled because
        the attack was rejected before resolution. We also pin
        ``hit=False`` and ``damage=0`` to guarantee no HP changed.

        Using ``attack_bonus=99`` makes the test independent of dice
        luck: without the gate, the attack would auto-hit
        (99 + 1 = 100 vs AC 16), so any ``hit=False`` here proves
        the gate fired rather than the roll happening to miss.
        """
        gs, rat, fighter = _build_engine_fixture(
            attacker_pos=(5, 5), defender_pos=(5, 11),
        )
        bite = next(
            a for a in gs.data_loader.load_monsters()["giant_rat"]["actions"]
            if a["name"] == "Bite"
        )

        starting_hp = fighter.current_hp
        result = gs.combat_engine.resolve_attack(
            attacker=rat,
            defender=fighter,
            attack_bonus=99,  # auto-hit if the roll happens
            damage_dice=bite["damage"],
            apply_damage=True,
            action=bite,
            game_state=gs,
        )

        assert result.attack_roll == 0, (
            "Reach gate did not fire: an attack_roll happened despite "
            "the target being out of reach. Gate must short-circuit "
            "before rolling."
        )
        assert result.hit is False
        assert result.damage == 0
        assert fighter.current_hp == starting_hp

    def test_melee_attack_within_reach_resolves_normally(self):
        """Adjacent rat (5 ft) — gate must NOT interfere.

        Distance 5 ft equals reach 5 ft: the gate's condition is
        `distance > reach`, so a 5/5 case passes through to a normal
        attack roll. We can't assert hit/miss deterministically (the
        roll varies even with seed=42 once the gate path is added),
        but we can assert the gate didn't short-circuit: an attack roll
        actually happened.
        """
        gs, rat, fighter = _build_engine_fixture(
            attacker_pos=(5, 5), defender_pos=(6, 5),  # 5 ft east
        )
        bite = next(
            a for a in gs.data_loader.load_monsters()["giant_rat"]["actions"]
            if a["name"] == "Bite"
        )

        result = gs.combat_engine.resolve_attack(
            attacker=rat,
            defender=fighter,
            attack_bonus=bite["attack_bonus"],
            damage_dice=bite["damage"],
            apply_damage=True,
            action=bite,
            game_state=gs,
        )

        # An attack roll happened (1..20). The reach gate returns a
        # sentinel attack_roll=0 when it short-circuits.
        assert 1 <= result.attack_roll <= 20

    def test_reach_gate_skipped_when_game_state_is_none(self):
        """Unit tests that call resolve_attack(game_state=None) keep working.

        Backwards-compatibility guarantee: callers without spatial
        context (the existing combat unit-test suite) see the legacy
        no-gate behavior. Otherwise we'd break ~dozens of tests.
        """
        engine = CombatEngine(DiceRoller(seed=42))
        attacker = Creature(
            name="A", max_hp=10, ac=10,
            abilities=Abilities(
                strength=10, dexterity=10, constitution=10,
                intelligence=10, wisdom=10, charisma=10,
            ),
        )
        defender = Creature(
            name="D", max_hp=10, ac=10,
            abilities=Abilities(
                strength=10, dexterity=10, constitution=10,
                intelligence=10, wisdom=10, charisma=10,
            ),
        )
        # action has reach=5 but no game_state means no positions to
        # check — gate must no-op and the attack must roll.
        result = engine.resolve_attack(
            attacker=attacker,
            defender=defender,
            attack_bonus=2,
            damage_dice="1d4",
            action={"reach": "5 ft.", "name": "Bite"},
            game_state=None,
        )
        assert 1 <= result.attack_roll <= 20

    def test_reach_gate_skipped_when_action_is_none(self):
        """Callers that don't pass action= also bypass the gate.

        PC weapon attacks (`game_state.py:3204`), OA attacks
        (`game_state.py:1246`, `:5397`), and improvised item-throws
        (`game_state.py:5676`) all call resolve_attack without an
        `action=` parameter. Their range/reach is enforced upstream
        (UI gate, OA system's `reach_feet`). The engine gate is the
        catch-all for the monster-turn path that DOES pass action;
        all other call sites are unaffected.
        """
        gs, rat, fighter = _build_engine_fixture(
            attacker_pos=(5, 5), defender_pos=(5, 11),  # 30 ft
        )
        result = gs.combat_engine.resolve_attack(
            attacker=rat,
            defender=fighter,
            attack_bonus=4,
            damage_dice="1d4",
            apply_damage=False,
            action=None,
            game_state=gs,
        )
        # Without action, gate can't read reach — roll proceeds.
        assert 1 <= result.attack_roll <= 20

    def test_reach_gate_skipped_for_ranged_action(self):
        """Ranged actions are governed by `range`, not `reach`.

        A monster's Longbow action with range "150/600" must not be
        rejected as "out of reach" — the reach gate only applies to
        melee actions. Range enforcement for ranged monster attacks
        is a separate concern (still a GAP per #401's audit).
        """
        gs, rat, fighter = _build_engine_fixture(
            attacker_pos=(5, 5), defender_pos=(5, 11),  # 30 ft
        )
        fake_longbow = {
            "name": "Longbow",
            "attack_bonus": 4,
            "damage": "1d8",
            "range": "150/600",
        }
        result = gs.combat_engine.resolve_attack(
            attacker=rat,
            defender=fighter,
            attack_bonus=4,
            damage_dice="1d8",
            apply_damage=False,
            action=fake_longbow,
            game_state=gs,
        )
        # Ranged: gate skipped; roll proceeds.
        assert 1 <= result.attack_roll <= 20

    def test_reach_10ft_action_lands_at_10ft_misses_at_15ft(self):
        """10-ft reach action hits at 10 ft, rejects at 15 ft.

        Covers the Large-creature / reach-weapon case. Uses an inline
        action dict so the test doesn't depend on a specific catalog
        monster carrying a reach-10 action.
        """
        gs, rat, fighter = _build_engine_fixture(
            attacker_pos=(5, 5), defender_pos=(5, 7),  # 10 ft
        )
        action_reach_10 = {
            "name": "TestGlaive",
            "reach": "10 ft.",
            "attack_bonus": 4,
            "damage": "1d8",
        }

        result_at_10ft = gs.combat_engine.resolve_attack(
            attacker=rat, defender=fighter,
            attack_bonus=4, damage_dice="1d8",
            apply_damage=False,
            action=action_reach_10, game_state=gs,
        )
        # 10 ft <= 10 ft reach: gate passes, roll happens.
        assert 1 <= result_at_10ft.attack_roll <= 20

        # Now move defender to 15 ft; same gate, same action, rejects.
        gs.set_position(pc_entity_id(fighter.name), 5, 8)  # 15 ft south
        result_at_15ft = gs.combat_engine.resolve_attack(
            attacker=rat, defender=fighter,
            attack_bonus=99,  # auto-hit if not gated
            damage_dice="1d8",
            apply_damage=False,
            action=action_reach_10, game_state=gs,
        )
        assert result_at_15ft.attack_roll == 0  # gate fired
        assert result_at_15ft.hit is False
        assert result_at_15ft.damage == 0


class TestMonsterCatalogReachInvariant:
    """Catch-future-author-drift: Large+ monsters must declare reach.

    Per SRD, a Large creature's natural reach is 10 ft. The codebase
    encodes reach on each action in monsters.json (not on the monster
    size). This test fails-loud when someone adds a Large+ monster
    without declaring `reach: "10 ft."` on its melee actions, so the
    engine's reach gate doesn't silently apply the 5-ft default.
    """

    def test_large_and_bigger_creatures_declare_reach_on_melee_actions(self):
        monsters = json.loads(MONSTERS_JSON.read_text())
        LARGE_OR_BIGGER = {"Large", "Huge", "Gargantuan"}

        offenders = []
        for mid, mdata in monsters.items():
            size = mdata.get("size", "")
            if size not in LARGE_OR_BIGGER:
                continue
            for action in mdata.get("actions") or []:
                # Melee action with an attack roll but no reach declared.
                if "attack_bonus" not in action:
                    continue
                if action.get("range") is not None:
                    # Ranged action — uses range, not reach.
                    continue
                if not action.get("reach"):
                    offenders.append(
                        f"{mid} [{size}] action {action.get('name')!r} "
                        f"has attack_bonus but no reach"
                    )

        assert offenders == [], (
            "Large+ monsters with melee actions must declare reach "
            "explicitly (default 5 ft is wrong for them). Offenders: "
            f"{offenders}"
        )
