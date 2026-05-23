# ABOUTME: Executes a scenario script (list of action dicts) against a LoadedScenario.
# ABOUTME: Records each action's effect on a ScriptContext for assertion runners to inspect.

"""Script execution for YAML scenarios (issue #363).

A scenario YAML may carry a ``script:`` block — a sequence of action
dicts that drive the game forward from the loaded state. The executor
applies them in order against the underlying ``GameState`` and records
side-effects (last attack result, last rejection reason, turn count) on
:class:`ScriptContext` so assertion runners can inspect what happened.

The vocabulary is intentionally narrow: ``attack`` and ``wait``. Those
two cover every scenario the issue lists. Adding more is the next
ticket's job.

Range checking lives here because the pure engine doesn't validate
weapon ranges — that's a client-layer concern (``client-2d`` does the
same check in ``session.get_attack_range``). Duplicating ten lines of
parsing here keeps the engine layer free of any cross-package import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from dnd_engine.core.distance import distance_in_feet
from dnd_engine.systems.ranged_attacks import is_close_combat_ranged_disadvantage

if TYPE_CHECKING:
    from dnd_engine.scenarios.loader import LoadedScenario


class ScriptExecutionError(RuntimeError):
    """Raised when a script action references an unknown entity, an
    unknown action type, or runs in a state where it cannot proceed
    (e.g. trying to attack while it's not a player's turn).
    """


@dataclass
class ScriptContext:
    """State carried through script execution and read by assertion runners.

    ``game_state`` is the engine state from the loader. The position
    dicts mirror what ``LoadedScenario`` returns and are required for
    distance/range calculations on attacks. ``party_entity_ids`` and
    ``enemy_entity_ids`` preserve the entity-id ↔ list-index mapping so
    a YAML can address creatures by stable id (e.g. ``goblin_0``)
    rather than positional index.
    """

    game_state: Any
    party_positions: dict[str, tuple[int, int]] = field(default_factory=dict)
    enemy_positions: dict[str, tuple[int, int]] = field(default_factory=dict)
    party_entity_ids: list[str] = field(default_factory=list)
    enemy_entity_ids: list[str] = field(default_factory=list)

    last_attack: Any | None = None
    last_attack_error: str | None = None
    last_attack_disadvantage: bool = False
    turn_count: int = 0

    def resolve_entity(self, entity_id: str) -> Any | None:
        """Return the creature with the given entity_id, or None.

        The lookup walks the engine state (party + active_enemies). Dead
        enemies remain in ``active_enemies`` with ``is_alive=False``, so
        callers asking about a defeated entity still get the creature
        back and can inspect its state.
        """
        if entity_id in self.party_entity_ids:
            i = self.party_entity_ids.index(entity_id)
            party = getattr(self.game_state, "party", None)
            chars = getattr(party, "characters", None) if party else None
            if chars is not None and i < len(chars):
                return chars[i]
        if entity_id in self.enemy_entity_ids:
            i = self.enemy_entity_ids.index(entity_id)
            enemies = getattr(self.game_state, "active_enemies", None) or []
            if i < len(enemies):
                return enemies[i]
        return None

    def position_of(self, entity_id: str) -> tuple[int, int] | None:
        if entity_id in self.party_positions:
            return self.party_positions[entity_id]
        if entity_id in self.enemy_positions:
            return self.enemy_positions[entity_id]
        return None


def _parse_weapon_range(range_str: str | None) -> tuple[int, int]:
    """Parse a weapon ``range`` string from items.json into (normal, max) feet.

    items.json stores ranges as ``"80/320"`` (ranged) or ``"20/60"``
    (thrown). A single value means normal == max. A missing value falls
    back to melee reach (5 ft for both bounds).
    """
    if not range_str:
        return (5, 5)
    parts = str(range_str).split("/")
    if len(parts) == 2:
        return (int(parts[0]), int(parts[1]))
    return (int(parts[0]), int(parts[0]))


def _attack_range_for(weapon_data: dict[str, Any] | None) -> tuple[int, int]:
    """Compute the effective attack range for the equipped weapon.

    Ranged weapons always honor their range tuple. A melee weapon with
    the ``thrown`` property keeps its range tuple too. Anything else is
    melee reach (5 ft).
    """
    if not weapon_data:
        return (5, 5)
    range_str = weapon_data.get("range")
    properties = weapon_data.get("properties", []) or []
    category = weapon_data.get("category", "melee")
    if category == "ranged":
        return _parse_weapon_range(range_str)
    if "thrown" in properties and range_str:
        return _parse_weapon_range(range_str)
    return (5, 5)


def _attack_reach_for(monster_action: dict[str, Any] | None) -> int:
    """Parse a monster action's ``reach`` string into feet.

    monsters.json encodes reach per attack action as ``"5 ft."`` or
    ``"10 ft."``. Per SRD § Playing the Game › Melee Attacks, a creature
    has a 5-foot reach by default; creatures with greater reach declare
    it on the action. This helper returns the integer feet so the
    executor can gate attack resolution on distance.

    Missing or unparseable values fall back to the SRD default (5 ft) so
    a malformed catalog row degrades to vanilla melee rather than
    silently widening reach.
    """
    if not monster_action:
        return 5
    raw = monster_action.get("reach")
    if not raw:
        return 5
    # "10 ft." → "10"; tolerate stray whitespace too.
    head = str(raw).strip().split()[0]
    try:
        return int(head)
    except ValueError:
        return 5


def _is_ranged_attack(weapon_data: dict[str, Any] | None) -> bool:
    """Return True when an attack with this weapon is a ranged attack roll.

    Per SRD: a thrown weapon attack is a ranged attack even when the
    weapon itself is categorized as melee. Mirrors the precedent in
    ``_attack_range_for`` so the close-combat rule lines up with the
    range tuple it produces.
    """
    if not weapon_data:
        return False
    if weapon_data.get("category") == "ranged":
        return True
    properties = weapon_data.get("properties", []) or []
    return "thrown" in properties


class ScriptExecutor:
    """Runs a script of action dicts against a ``LoadedScenario``.

    Construction primes a :class:`ScriptContext` with the scenario's
    positions and entity-id ordering. ``run(script)`` then drives the
    actions in sequence and returns the final context for assertion
    runners.
    """

    def __init__(self, loaded: LoadedScenario) -> None:
        self.loaded = loaded
        self.ctx = ScriptContext(
            game_state=loaded.game_state,
            party_positions=dict(loaded.party_positions),
            enemy_positions=dict(loaded.enemy_positions),
            party_entity_ids=list(loaded.party_positions.keys()),
            enemy_entity_ids=list(loaded.enemy_positions.keys()),
        )

    def run(self, script: list[dict[str, Any]]) -> ScriptContext:
        for i, action in enumerate(script):
            try:
                self._run_action(action)
            except ScriptExecutionError:
                raise
            except Exception as exc:
                raise ScriptExecutionError(
                    f"script[{i}] ({action!r}) failed: {exc}"
                ) from exc
        return self.ctx

    def _run_action(self, action: dict[str, Any]) -> None:
        a_type = action.get("action")
        if a_type == "wait":
            self._action_wait()
        elif a_type == "attack":
            target = action.get("target")
            if target is None:
                raise ScriptExecutionError("attack action missing 'target'")
            self._action_attack(str(target))
        elif a_type == "monster_attack":
            attacker = action.get("attacker")
            target = action.get("target")
            monster_action_name = action.get("monster_action")
            if attacker is None or target is None or monster_action_name is None:
                raise ScriptExecutionError(
                    "monster_attack action requires 'attacker', 'target', "
                    "and 'monster_action'"
                )
            self._action_monster_attack(
                str(attacker), str(target), str(monster_action_name)
            )
        else:
            raise ScriptExecutionError(
                f"unknown script action: {a_type!r}"
            )

    # --- actions ----------------------------------------------------------

    def _action_wait(self) -> None:
        tracker = self.ctx.game_state.initiative_tracker
        if tracker is None:
            raise ScriptExecutionError(
                "wait: combat is not active (no initiative tracker)"
            )
        tracker.next_turn()
        self.ctx.turn_count += 1

    def _action_attack(self, target_id: str) -> None:
        target = self.ctx.resolve_entity(target_id)
        if target is None or target_id not in self.ctx.enemy_entity_ids:
            raise ScriptExecutionError(
                f"attack: unknown target '{target_id}'"
            )

        attacker, attacker_id = self._current_player_attacker()
        attacker_pos = self.ctx.position_of(attacker_id)
        target_pos = self.ctx.position_of(target_id)
        if attacker_pos is None or target_pos is None:
            raise ScriptExecutionError(
                f"attack: missing position for "
                f"{attacker_id!r} or {target_id!r}"
            )

        distance = distance_in_feet(
            attacker_pos[0], attacker_pos[1], target_pos[0], target_pos[1]
        )

        # Look up the equipped weapon's range data via the engine's own
        # data loader so the executor stays inside the engine layer.
        weapon_data = self._equipped_weapon_data(attacker)
        normal_range, max_range = _attack_range_for(weapon_data)

        if distance > max_range:
            self.ctx.last_attack_error = (
                f"out of range: {distance} ft > max {max_range} ft "
                f"({weapon_data.get('name') if weapon_data else 'unarmed'})"
            )
            self.ctx.last_attack = None
            return

        in_long_range = distance > normal_range
        # SRD § Ranged Attacks in Close Combat (#400): applies to any
        # ranged attack roll — bow shots and thrown melee weapons alike.
        # Mirrors _attack_range_for's treatment of "thrown" as ranged.
        is_ranged_attack = _is_ranged_attack(weapon_data)
        in_close_combat = is_ranged_attack and is_close_combat_ranged_disadvantage(
            attacker_pos=attacker_pos,
            enemies=self._living_enemies_with_positions(),
        )
        disadvantage = in_long_range or in_close_combat
        self.ctx.last_attack_disadvantage = disadvantage

        result = self.ctx.game_state.execute_player_attack(
            attacker, target, disadvantage=disadvantage
        )
        # ``execute_player_attack`` returns ``PlayerAttackResult``; the
        # nested ``AttackResult`` carries the fields the assertion
        # vocabulary actually inspects (hit, damage, attack_roll).
        self.ctx.last_attack = getattr(result, "attack_result", result)

        tracker = self.ctx.game_state.initiative_tracker
        if tracker is not None:
            tracker.next_turn()
        self.ctx.turn_count += 1

    def _action_monster_attack(
        self,
        attacker_id: str,
        target_id: str,
        monster_action_name: str,
    ) -> None:
        """Resolve a monster's melee attack, gated on the action's reach.

        Mirrors ``_action_attack`` for the inverse direction (enemy →
        party member). Reads the monster's action definition from
        ``monsters.json`` via the engine's own data loader, parses the
        action's ``reach`` field (SRD § Melee Attacks › Reach), and
        rejects the attack if the target sits beyond it. A bearded
        devil's Glaive (10 ft.) can hit a target two tiles away; a
        goblin's Scimitar (5 ft.) cannot.
        """
        if attacker_id not in self.ctx.enemy_entity_ids:
            raise ScriptExecutionError(
                f"monster_attack: unknown attacker '{attacker_id}'"
            )
        if target_id not in self.ctx.party_entity_ids:
            raise ScriptExecutionError(
                f"monster_attack: unknown target '{target_id}'"
            )

        attacker = self.ctx.resolve_entity(attacker_id)
        target = self.ctx.resolve_entity(target_id)
        if attacker is None or target is None:
            raise ScriptExecutionError(
                f"monster_attack: could not resolve "
                f"{attacker_id!r} or {target_id!r}"
            )

        attacker_pos = self.ctx.position_of(attacker_id)
        target_pos = self.ctx.position_of(target_id)
        if attacker_pos is None or target_pos is None:
            raise ScriptExecutionError(
                f"monster_attack: missing position for "
                f"{attacker_id!r} or {target_id!r}"
            )

        action_data = self._monster_action_data(attacker_id, monster_action_name)
        if action_data is None:
            raise ScriptExecutionError(
                f"monster_attack: no action {monster_action_name!r} on "
                f"monster {attacker_id!r}"
            )

        reach_ft = _attack_reach_for(action_data)
        distance = distance_in_feet(
            attacker_pos[0], attacker_pos[1], target_pos[0], target_pos[1]
        )
        if distance > reach_ft:
            self.ctx.last_attack_error = (
                f"out of reach: {distance} ft > reach {reach_ft} ft "
                f"({monster_action_name})"
            )
            self.ctx.last_attack = None
            return

        attack_bonus = action_data.get("attack_bonus")
        damage_dice = action_data.get("damage")
        if attack_bonus is None or damage_dice is None:
            raise ScriptExecutionError(
                f"monster_attack: action {monster_action_name!r} on "
                f"{attacker_id!r} is missing attack_bonus/damage"
            )

        result = self.ctx.game_state.combat_engine.resolve_attack(
            attacker=attacker,
            defender=target,
            attack_bonus=int(attack_bonus),
            damage_dice=str(damage_dice),
            apply_damage=True,
            event_bus=getattr(self.ctx.game_state, "event_bus", None),
            action=action_data,
            game_state=self.ctx.game_state,
        )
        self.ctx.last_attack = result

        tracker = self.ctx.game_state.initiative_tracker
        if tracker is not None:
            tracker.next_turn()
        self.ctx.turn_count += 1

    # --- helpers ----------------------------------------------------------

    def _current_player_attacker(self) -> tuple[Any, str]:
        tracker = self.ctx.game_state.initiative_tracker
        if tracker is None:
            raise ScriptExecutionError(
                "attack: combat is not active (no initiative tracker)"
            )
        current = tracker.get_current_combatant()
        if current is None:
            raise ScriptExecutionError("attack: no current combatant")
        creature = current.creature
        party = getattr(self.ctx.game_state, "party", None)
        chars = list(getattr(party, "characters", []) or [])
        for i, character in enumerate(chars):
            if character is creature:
                if i < len(self.ctx.party_entity_ids):
                    return character, self.ctx.party_entity_ids[i]
                raise ScriptExecutionError(
                    "attack: party_entity_ids out of sync with party"
                )
        raise ScriptExecutionError(
            f"attack: current combatant {creature.name!r} is not a "
            f"party member (enemy turn?)"
        )

    def _living_enemies_with_positions(
        self,
    ) -> list[tuple[tuple[int, int], Any]]:
        """Pair each known enemy with its (x, y) position for rule helpers.

        Skips entries missing either a tracked position or a live creature
        reference. Dead enemies are still yielded; the rule helper filters
        them itself so the data flow remains uniform.
        """
        enemies: list[tuple[tuple[int, int], Any]] = []
        for entity_id in self.ctx.enemy_entity_ids:
            pos = self.ctx.enemy_positions.get(entity_id)
            if pos is None:
                continue
            creature = self.ctx.resolve_entity(entity_id)
            if creature is None:
                continue
            enemies.append((pos, creature))
        return enemies

    def _equipped_weapon_data(self, attacker: Any) -> dict[str, Any] | None:
        # Lazy-import to avoid pulling EquipmentSlot at module load — the
        # inventory subsystem is heavyweight and the executor is imported
        # by every scenario fixture.
        from dnd_engine.systems.inventory import EquipmentSlot

        inventory = getattr(attacker, "inventory", None)
        if inventory is None:
            return None
        weapon_id = inventory.get_equipped_item(EquipmentSlot.WEAPON)
        if not weapon_id:
            return None
        data_loader = getattr(self.ctx.game_state, "data_loader", None)
        campaign_id = getattr(self.ctx.game_state, "campaign_id", None)
        if data_loader is None or campaign_id is None:
            return None
        items = data_loader.load_items(campaign_id)
        return items.get("weapons", {}).get(weapon_id)

    def _monster_action_data(
        self, enemy_entity_id: str, action_name: str
    ) -> dict[str, Any] | None:
        """Look up a named action on the given enemy's monster catalog row.

        The entity_id encodes the monster id as ``{monster_id}_{index}``
        (see ``ScenarioLoader``). Splits on the trailing index, loads
        ``monsters.json`` through the engine's data loader, and returns
        the first action whose ``name`` matches. Returns ``None`` when
        the catalog row, action, or loader is unavailable so callers can
        surface a precise script-level error.
        """
        # entity_id is "{monster_id}_{i}"; rstrip the index segment.
        monster_id = enemy_entity_id.rsplit("_", 1)[0]
        data_loader = getattr(self.ctx.game_state, "data_loader", None)
        if data_loader is None:
            return None
        monsters = data_loader.load_monsters()
        mdata = monsters.get(monster_id)
        if not mdata:
            return None
        for act in mdata.get("actions") or []:
            if act.get("name") == action_name:
                return act
        return None
