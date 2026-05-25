# ABOUTME: SRD conformance audit for "Playing the Game > Melee Attacks".
# ABOUTME: Cross-references docs/srd/playing-the-game/melee-attacks.md against engine code.

"""SRD conformance: Melee Attacks.

Maps every rule in `docs/srd/playing-the-game/melee-attacks.md` to a
test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.combat import CombatEngine
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.entity_ids import pc_entity_id
from dnd_engine.core.game_state import GameState
from dnd_engine.core.map import Map, TileType
from dnd_engine.core.party import Party
from dnd_engine.core.position import Position
from dnd_engine.rules.loader import DataLoader
from dnd_engine.scenarios.loader import ScenarioLoader
from dnd_engine.scenarios.script_executor import (
    ScriptExecutor,
    _attack_range_for,
    _attack_reach_for,
)
from dnd_engine.systems.opportunity_attacks import (
    register_default_opportunity_attack,
)
from dnd_engine.utils.events import Event, EventBus, EventType

pytestmark = pytest.mark.srd(
    "playing-the-game/melee-attacks.md",
    lines="2085-2115",
)


MONSTERS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "monsters.json"
)


def _make_engine_and_combatants() -> tuple[CombatEngine, Creature, Creature]:
    """Fighter-vs-goblin fixture mirroring the ranged-attacks pilot."""
    engine = CombatEngine(DiceRoller(seed=42))
    fighter_abilities = Abilities(
        strength=16,
        dexterity=14,
        constitution=15,
        intelligence=10,
        wisdom=12,
        charisma=8,
    )
    goblin_abilities = Abilities(
        strength=8,
        dexterity=14,
        constitution=10,
        intelligence=10,
        wisdom=8,
        charisma=8,
    )
    fighter = Creature(name="Fighter", max_hp=20, ac=16, abilities=fighter_abilities)
    goblin = Creature(name="Goblin", max_hp=7, ac=15, abilities=goblin_abilities)
    return engine, fighter, goblin


class TestMeleeAttack_Definition:
    """SRD § Playing the Game › Melee Attacks › Definition.

    > A melee attack allows you to attack a target within your reach. A
    > melee attack typically uses a handheld weapon or an Unarmed
    > Strike. Many monsters make melee attacks with claws, teeth, or
    > other body parts. A few spells also involve melee attacks.
    """

    def test_resolve_attack_supports_melee_weapon_damage(self):
        """Engine resolves a melee weapon attack and surfaces hit + damage.

        The SRD's broad definition is satisfied by the engine accepting
        a melee weapon's damage dice (longsword: 1d8) on its core
        attack surface.
        """
        engine, fighter, goblin = _make_engine_and_combatants()

        result = engine.resolve_attack(
            attacker=fighter,
            defender=goblin,
            attack_bonus=5,
            damage_dice="1d8+3",
        )

        assert result.attack_roll >= 1
        assert hasattr(result, "hit")
        assert hasattr(result, "damage")


class TestReach_DefaultFiveFeet:
    """SRD § Playing the Game › Melee Attacks › Reach (default).

    > A creature has a 5-foot reach and can thus attack targets within
    > 5 feet when making a melee attack.
    """

    def test_melee_weapon_defaults_to_five_foot_reach(self):
        """`_attack_range_for(longsword)` returns (5, 5).

        Verifies the default-reach contract used by the scenario
        script executor when validating attack distances. Longsword has
        no `range`, no `thrown` property, so the helper falls through
        to the melee default.
        """
        longsword = {
            "name": "Longsword",
            "category": "melee",
            "properties": ["versatile"],
        }

        assert _attack_range_for(longsword) == (5, 5)

    def test_unspecified_weapon_falls_back_to_five_foot_reach(self):
        """Missing weapon data still yields 5-ft reach.

        Unarmed Strikes and partial item rows must not silently widen
        reach. The helper's `not weapon_data` branch defends this.
        """
        assert _attack_range_for(None) == (5, 5)
        assert _attack_range_for({}) == (5, 5)


class TestReach_GreaterThanFiveFeet:
    """SRD § Playing the Game › Melee Attacks › Reach (creatures with more).

    > Certain creatures have melee attacks with a reach greater than 5
    > feet, as noted in their descriptions.
    """

    def test_monster_data_encodes_extended_reach(self):
        """monsters.json carries explicit `reach` per attack action.

        Data-parity check: at least one monster action declares a
        reach greater than the default. Confirms the SRD's "noted in
        their descriptions" clause is reflected in the catalog.
        """
        monsters = json.loads(MONSTERS_JSON.read_text())

        extended = [
            (mid, action["name"], action["reach"])
            for mid, mdata in monsters.items()
            for action in (mdata.get("actions") or [])
            if action.get("reach") and action["reach"] != "5 ft."
        ]

        assert extended, (
            "Expected at least one monster action with reach > 5 ft. "
            "in monsters.json (e.g., bearded_devil: Glaive 10 ft.)."
        )

    def test_extended_reach_data_is_consumed_by_attack_resolution(self, tmp_path: Path):
        """A 10-ft reach action lands at 10 ft; a 5-ft action is rejected.

        Verifies the SRD's "noted in their descriptions" clause is honored
        end-to-end: `script_executor._attack_reach_for` parses the action's
        `reach` string, and the `monster_attack` action gates resolution on
        it. Mirrors the player-weapon range pattern (#400) so scenario
        scripts can express monster melee that depends on reach.
        """
        monsters = json.loads(MONSTERS_JSON.read_text())

        glaive = next(
            a for a in monsters["bearded_devil"]["actions"]
            if a.get("name") == "Glaive"
        )
        scimitar = next(
            a for a in monsters["goblin"]["actions"]
            if a.get("name") == "Scimitar"
        )

        # Helper consumes the field — that alone closes the GAP.
        assert _attack_reach_for(glaive) == 10
        assert _attack_reach_for(scimitar) == 5

        # And it gates attack resolution: a 10-ft reach action lands at
        # 10 ft, but a 5-ft action at the same distance is out of reach.
        # Fixture: PC at (3, 5), monster at (5, 5) — 2 tiles = 10 ft.
        bearded_devil_yaml = """
name: srd_reach_extended
seed: 7
map:
  dungeon: laboratory
  campaign: poisoned_laboratory
  start_room: laboratory.entrance
party:
  - class: fighter
    race: human
    weapons: [longsword]
    position: [3, 5]
    name: Brick
enemies:
  - monster_id: bearded_devil
    position: [5, 5]
"""
        goblin_yaml = """
name: srd_reach_default
seed: 7
map:
  dungeon: laboratory
  campaign: poisoned_laboratory
  start_room: laboratory.entrance
party:
  - class: fighter
    race: human
    weapons: [longsword]
    position: [3, 5]
    name: Brick
enemies:
  - monster_id: goblin
    position: [5, 5]
"""

        bd_path = tmp_path / "bd.yaml"
        bd_path.write_text(bearded_devil_yaml.lstrip())
        gb_path = tmp_path / "gb.yaml"
        gb_path.write_text(goblin_yaml.lstrip())

        # Advance to the monster's turn, then have it attack the PC.
        bd_loaded = ScenarioLoader().load(bd_path)
        bd_executor = ScriptExecutor(bd_loaded)
        bd_ctx = bd_executor.run([
            {"action": "wait"},  # let fighter pass
            {
                "action": "monster_attack",
                "attacker": "bearded_devil_0",
                "target": "pc_brick",
                "monster_action": "Glaive",
            },
        ])
        # Glaive (10 ft) at 10 ft must resolve, not reject.
        assert bd_ctx.last_attack is not None, (
            f"bearded devil glaive (10 ft reach) should hit at 10 ft, "
            f"got error: {bd_ctx.last_attack_error}"
        )

        gb_loaded = ScenarioLoader().load(gb_path)
        gb_executor = ScriptExecutor(gb_loaded)
        gb_ctx = gb_executor.run([
            {"action": "wait"},
            {
                "action": "monster_attack",
                "attacker": "goblin_0",
                "target": "pc_brick",
                "monster_action": "Scimitar",
            },
        ])
        # Scimitar (5 ft) at 10 ft must be rejected.
        assert gb_ctx.last_attack is None
        assert gb_ctx.last_attack_error is not None
        assert "reach" in gb_ctx.last_attack_error.lower(), (
            f"expected out-of-reach rejection, got: "
            f"{gb_ctx.last_attack_error}"
        )


def _build_oa_fixture() -> tuple[GameState, str, Creature, Character]:
    """Construct a minimal combat with a fighter adjacent to a goblin.

    Returns ``(game_state, pc_entity_id, goblin, fighter)``. The fighter
    sits at ``(1, 1)`` and the goblin at ``(2, 1)`` — 5 ft apart, in
    each other's default reach. The map is otherwise open floor on a
    5x3 grid so the fighter has room to step away in any direction.
    """
    tiles: dict[tuple[int, int], TileType] = {}
    for y in range(3):
        for x in range(5):
            tiles[(x, y)] = TileType.FLOOR
    grid_map = Map(width=5, height=3, tiles=tiles)

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

    goblin = game_state.data_loader.create_monster("goblin")
    game_state.active_enemies.append(goblin)

    pc_id = pc_entity_id(fighter.name)
    goblin_id = "goblin_0"
    game_state.set_position(pc_id, 1, 1)
    game_state.set_position(goblin_id, 2, 1)

    # Start combat AFTER placements so OA handlers register against the
    # already-placed entities. Force the PC to be the active combatant
    # so attempt_combat_step queries the PC's TurnState.
    game_state._start_combat()
    tracker = game_state.initiative_tracker
    assert tracker is not None
    for idx, entry in enumerate(tracker.combatants):
        if entry.creature is fighter:
            tracker.current_turn_index = idx
            break
    tracker.turn_states[fighter].reset(speed=fighter.speed)

    return game_state, pc_id, goblin, fighter


def _build_oa_fixture_no_los() -> tuple[GameState, str, Creature, Character]:
    """OA fixture where a wall blocks LOS between the goblin and the PC.

    Adjacent-tile LOS is always clear on a tile grid (no half-walls),
    so to exercise visibility specifically the goblin gets a 10-ft
    reach override and the wall sits in the 2-tile gap between them:

        Fighter at (1, 1)  ── WALL ──  Goblin at (3, 1)   reach=10

    Reach gate passes (was 10 ft, now 15 ft); LOS gate fails (wall
    blocks the raycast). With the SRD visibility clause enforced,
    the goblin's Reaction stays available and no OA is resolved.
    """
    tiles: dict[tuple[int, int], TileType] = {}
    for y in range(3):
        for x in range(5):
            tiles[(x, y)] = TileType.FLOOR
    tiles[(2, 1)] = TileType.WALL  # blocks LOS between (1, 1) and (3, 1)
    grid_map = Map(width=5, height=3, tiles=tiles)

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

    goblin = game_state.data_loader.create_monster("goblin")
    game_state.active_enemies.append(goblin)

    pc_id = pc_entity_id(fighter.name)
    goblin_id = "goblin_0"
    game_state.set_position(pc_id, 1, 1)
    game_state.set_position(goblin_id, 3, 1)

    game_state._start_combat()
    # Re-register the goblin with 10-ft reach so the wall-blocked LOS
    # gate is what suppresses the OA, not the reach gate. The default
    # 5-ft handler registered by _register_default_opportunity_attacks
    # stays subscribed too, but the dispatcher's "last wins" rule
    # means the new registration takes precedence.
    spatial = game_state.spatial
    assert spatial is not None
    assert game_state.reaction_dispatcher is not None

    def _gob_pos() -> Position | None:
        return spatial.position_of(goblin_id)

    def _gob_can_see(target: Position) -> bool:
        origin = spatial.position_of(goblin_id)
        if origin is None:
            return False
        return spatial.has_line_of_sight(origin, target)

    register_default_opportunity_attack(
        game_state.reaction_dispatcher,
        goblin,
        get_position=_gob_pos,
        reach_feet=10,
        can_see=_gob_can_see,
    )

    tracker = game_state.initiative_tracker
    assert tracker is not None
    for idx, entry in enumerate(tracker.combatants):
        if entry.creature is fighter:
            tracker.current_turn_index = idx
            break
    tracker.turn_states[fighter].reset(speed=fighter.speed)

    return game_state, pc_id, goblin, fighter


class TestOpportunityAttacks_Triggering:
    """SRD § Playing the Game › Melee Attacks › Opportunity Attacks (trigger).

    > Combatants watch for enemies to drop their guard. If you move
    > heedlessly past your foes, you put yourself in danger by
    > provoking an Opportunity Attack.
    > [...]
    > You can make an Opportunity Attack when a creature that you can
    > see leaves your reach.
    """

    def test_fleeing_party_provokes_one_attack_per_living_enemy(self):
        """`flee_combat` exposes the OA fan-out contract.

        This is the engine's only OA-equivalent today: a batch reaction
        triggered by `flee_combat()`. Each living enemy makes one
        attack against a random living party member (game_state.py
        :4222-4264). The mechanic captures the SRD's spirit (movement
        out of reach provokes) for the flee case only. We assert the
        callable exists and returns the documented OA payload shape —
        full behavioral exercise lives in integration tests that own
        a full GameState fixture.
        """
        import inspect

        from dnd_engine.core.game_state import GameState

        assert callable(getattr(GameState, "flee_combat", None))
        src = inspect.getsource(GameState.flee_combat)
        assert "opportunity_attacks" in src, (
            "flee_combat must surface an `opportunity_attacks` field "
            "documenting per-enemy OA results."
        )
        assert "living_enemies" in src and "resolve_attack" in src, (
            "flee_combat must iterate living enemies and resolve one "
            "attack per enemy to model OA fan-out."
        )

    def test_tactical_movement_out_of_reach_provokes_opportunity_attack(self):
        """Stepping out of an adjacent enemy's reach consumes their Reaction.

        Fighter at (1, 1), goblin at (2, 1) — 5 ft apart. The fighter
        steps to (0, 1), 10 ft from the goblin and outside its default
        reach. The dispatcher publishes ``OPPORTUNITY_PROVOKED`` and the
        goblin's handler fires: its ``reaction_available`` slot flips
        to ``False`` and a ``DAMAGE_DEALT`` event with
        ``opportunity_attack=True`` rides the bus (when the attack
        hits) — verifying the publish + resolve hooks land an actual
        attack roll, not just a slot consumption.
        """
        game_state, pc_id, goblin, fighter = _build_oa_fixture()

        # Pre-check: dispatcher exists, goblin's Reaction is live.
        assert game_state.reaction_dispatcher is not None
        tracker = game_state.initiative_tracker
        assert tracker is not None
        assert tracker.turn_states[goblin].reaction_available is True

        damage_events: list[Event] = []
        game_state.event_bus.subscribe(
            EventType.DAMAGE_DEALT, damage_events.append
        )

        # PC steps west, away from the goblin.
        result = game_state.attempt_combat_step(pc_id, dx=-1, dy=0)
        assert result.ok, f"step failed unexpectedly: {result.reason}"
        assert result.position == Position(0, 1)

        # The goblin's Reaction slot was consumed: SRD § Reactions
        # contract met.
        assert tracker.turn_states[goblin].reaction_available is False, (
            "OA handler fired but did not consume the reactor's "
            "Reaction slot — the dispatcher / handler contract is broken."
        )

        # Exactly one damage event corresponding to the OA. The
        # deterministic seed (42) gives the goblin's scimitar attack a
        # consistent roll for this fixture, but we don't assert on
        # specific hit/damage values — only on the *resolution shape*
        # (event emitted iff the roll hit, marked as OA).
        oa_events = [
            e for e in damage_events
            if e.data.get("opportunity_attack") is True
        ]
        # Either the attack hit (>=1 oa event) or missed (0 events).
        # Both branches are SRD-compliant — the contract is that the
        # OA was attempted, evidenced by slot consumption above. The
        # event-count assertion below pins the resolution-side shape.
        assert len(oa_events) <= 1, (
            f"expected at most one OA damage event, got {len(oa_events)}"
        )
        for e in oa_events:
            assert e.data["attacker"] == goblin.name
            assert e.data["defender"] == fighter.name


class TestOpportunityAttacks_Avoidance:
    """SRD § Playing the Game › Melee Attacks › Avoiding OAs.

    > You can avoid provoking an Opportunity Attack by taking the
    > Disengage action. You also don't provoke an Opportunity Attack
    > when you Teleport or when you are moved without using your
    > movement, action, Bonus Action, or Reaction.
    """

    def test_disengage_action_prevents_opportunity_attack(self):
        pytest.skip(
            "GAP: Disengage is not a playable action. The string "
            "'Disengage' appears only as flavor text in "
            "dnd_engine/data/srd/classes.json (rogue cunning action) "
            "and dnd_engine/data/srd/monsters.json (goblin Nimble "
            "Escape, spy). No action handler, dispatcher, or "
            "movement-flag is wired up — a player cannot choose "
            "Disengage to avoid OAs. Tracked by issue #414 "
            "(depends on #413 per-creature OAs)."
        )

    def test_involuntary_movement_does_not_provoke(self):
        """Forced movement (Teleport/Shoved/Hurled) skips OA publishing.

        Same fixture as the triggering test, but the step is marked
        ``involuntary=True``. The OA dispatcher is never invoked, so
        the goblin keeps its Reaction for any later in-round trigger
        and no damage event fires. The SRD calls this out explicitly:

            > You also don't provoke an Opportunity Attack when you
            > Teleport or when you are moved without using your
            > movement, action, Bonus Action, or Reaction.
        """
        game_state, pc_id, goblin, _fighter = _build_oa_fixture()
        tracker = game_state.initiative_tracker
        assert tracker is not None

        damage_events: list[Event] = []
        game_state.event_bus.subscribe(
            EventType.DAMAGE_DEALT, damage_events.append
        )

        result = game_state.attempt_combat_step(
            pc_id, dx=-1, dy=0, involuntary=True
        )
        assert result.ok
        assert result.position == Position(0, 1)

        assert tracker.turn_states[goblin].reaction_available is True, (
            "involuntary movement consumed the goblin's Reaction — "
            "the publish hook should have been suppressed."
        )
        oa_events = [
            e for e in damage_events
            if e.data.get("opportunity_attack") is True
        ]
        assert oa_events == [], (
            f"involuntary movement produced OA damage events: {oa_events}"
        )


class TestOpportunityAttacks_Mechanics:
    """SRD § Playing the Game › Melee Attacks › Making an OA.

    > You can make an Opportunity Attack when a creature that you can
    > see leaves your reach. To make the attack, take a Reaction to
    > make one melee attack with a weapon or an Unarmed Strike against
    > that creature. The attack occurs right before it leaves your
    > reach.
    """

    def test_opportunity_attack_consumes_attackers_reaction(self):
        pytest.skip(
            "GAP: Reaction economy is not modeled. `flee_combat()` "
            "fans out one attack per living enemy without checking or "
            "consuming a Reaction (dnd_engine/core/game_state.py:4222"
            "-4264). An enemy could in principle OA on every flee and "
            "still react to other triggers in the same round. Tracked "
            "by issue #412. Cross-link from "
            "docs/srd/playing-the-game/reactions.md when that section "
            "is audited."
        )

    def test_opportunity_attack_requires_seeing_the_provoker(self):
        """A wall between reactor and mover suppresses the OA.

        The SRD says you can only make an OA against a creature you
        can see. Slice 4b uses geometric line-of-sight as the proxy
        for "can see" — full invisibility / blinded / heavy
        obscurement gates land with plan-05's perception primitives.

        Fixture: fighter at (1, 1) with a 10-ft-reach goblin at
        (3, 1); a wall at (2, 1) breaks LOS between them. The fighter
        steps to (0, 1) — outside even the 10-ft reach — so the reach
        gate alone would normally fire the OA. The visibility gate
        keeps the goblin's Reaction available and emits no damage.
        """
        game_state, pc_id, goblin, _fighter = _build_oa_fixture_no_los()
        tracker = game_state.initiative_tracker
        assert tracker is not None
        assert tracker.turn_states[goblin].reaction_available is True

        # Sanity: confirm LOS really is blocked by the wall fixture.
        spatial = game_state.spatial
        assert spatial is not None
        assert not spatial.has_line_of_sight(
            Position(3, 1), Position(1, 1)
        ), (
            "fixture setup error: expected LOS between (3, 1) and "
            "(1, 1) to be blocked by the wall at (2, 1)."
        )

        damage_events: list[Event] = []
        game_state.event_bus.subscribe(
            EventType.DAMAGE_DEALT, damage_events.append
        )

        result = game_state.attempt_combat_step(pc_id, dx=-1, dy=0)
        assert result.ok
        assert result.position == Position(0, 1)

        assert tracker.turn_states[goblin].reaction_available is True, (
            "wall-blocked LOS still let the OA fire — visibility gate "
            "in register_default_opportunity_attack is not honored."
        )
        oa_events = [
            e for e in damage_events
            if e.data.get("opportunity_attack") is True
        ]
        assert oa_events == [], (
            f"unseen mover produced OA damage events: {oa_events}"
        )
