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
            return

        self.ctx.last_attack_disadvantage = distance > normal_range

        result = self.ctx.game_state.execute_player_attack(attacker, target)
        # ``execute_player_attack`` returns ``PlayerAttackResult``; the
        # nested ``AttackResult`` carries the fields the assertion
        # vocabulary actually inspects (hit, damage, attack_roll).
        self.ctx.last_attack = getattr(result, "attack_result", result)

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
