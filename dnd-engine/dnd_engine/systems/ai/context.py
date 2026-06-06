# ABOUTME: TurnContext snapshot passed to pipeline.decide and MovementStrategy.plan.
# ABOUTME: Issue #647 — captures actor + action data + target pool for one enemy turn.

"""Per-turn context bundle for the enemy-turn pipeline.

`TurnContext` is the immutable read-side snapshot of everything
`pipeline.decide` and any `MovementStrategy` needs to choose an
`Intent`. It is built once at the start of an enemy turn and threaded
through the strategy seam. State mutation happens later in
`pipeline.execute`; strategies must not mutate `ctx`.

The classmethod `build(state, enemy)` is the canonical constructor.
It resolves the actor's first viable weapon action from the monster
catalog (the existing `process_enemy_turn` behavior), reads `reach_ft`
via `attack_reach_for`, and snapshots the living party.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from dnd_engine.core.combat_geometry import attack_reach_for, is_ranged_action

if TYPE_CHECKING:
    from dnd_engine.core.creature import Creature
    from dnd_engine.core.game_state import GameState


@dataclass(frozen=True)
class TurnContext:
    """Read-only snapshot of one enemy's turn-start situation.

    Attributes:
        state: The game state — passed through so strategies that
            need to peek at terrain or spatial neighbors can, while
            staying read-only by convention.
        actor: The creature whose turn this is.
        target_pool: Living party members (and any allied creatures
            that count as targets). Caller filters dead targets.
        monster_data: The actor's entry in the monsters catalog. May
            be empty if the actor was not loaded from the catalog.
        action_data: The chosen weapon action dict (e.g. the scimitar
            entry). None if no viable action.
        reach_ft: Effective reach in feet for `action_data`. None if
            `action_data` is None.
        is_ranged: True if `action_data` is a ranged attack.
    """

    state: GameState
    actor: Creature
    target_pool: list[Creature]
    monster_data: dict[str, Any] = field(default_factory=dict)
    action_data: dict[str, Any] | None = None
    reach_ft: int | None = None
    is_ranged: bool = False

    @classmethod
    def build(
        cls,
        state: GameState,
        enemy: Creature,
        *,
        target_pool: list[Creature] | None = None,
        monster_data: dict[str, Any] | None = None,
        action_data: dict[str, Any] | None = None,
        reach_ft: int | None = None,
        is_ranged: bool | None = None,
    ) -> TurnContext:
        """Construct a TurnContext from a game state + enemy.

        Looks up the enemy's first non-Multiattack action from the
        monsters catalog (preserving the current `process_enemy_turn`
        action-selection contract). Falls back to None when the
        catalog or the action list is missing — callers handle that
        as "no valid attack".

        Callers that already resolved the chosen attack action (e.g.
        `process_enemy_turn`, which picks the first action carrying
        both `attack_bonus` and `damage`) can pass `action_data` /
        `reach_ft` / `is_ranged` explicitly so the context aligns
        with the call site's action-selection rules.

        Args:
            state: The active game state.
            enemy: The enemy whose turn is starting.
            target_pool: Optional pre-resolved list of living party
                members. When None, falls back to an empty list —
                the pipeline resolves the pool separately.
            monster_data: Optional pre-resolved monster data dict.
                When None, looks up `enemy.name.lower()` in the
                catalog and returns an empty dict on miss.
            action_data: Optional explicit override for the chosen
                attack action. Skips the local lookup when provided.
            reach_ft: Optional explicit override for reach.
            is_ranged: Optional explicit override for ranged-ness.

        Returns:
            A frozen `TurnContext` ready to thread through `decide`.
        """
        pool = target_pool if target_pool is not None else []
        m_data = monster_data if monster_data is not None else _lookup_monster_data(state, enemy)

        if action_data is not None:
            resolved_action = action_data
            resolved_reach = reach_ft if reach_ft is not None else attack_reach_for(action_data)
            resolved_is_ranged = is_ranged if is_ranged is not None else is_ranged_action(action_data)
        else:
            resolved_action = _first_weapon_action(m_data)
            if resolved_action is None:
                resolved_reach = None
                resolved_is_ranged = False
            else:
                resolved_reach = attack_reach_for(resolved_action)
                resolved_is_ranged = is_ranged_action(resolved_action)

        return cls(
            state=state,
            actor=enemy,
            target_pool=pool,
            monster_data=m_data,
            action_data=resolved_action,
            reach_ft=resolved_reach,
            is_ranged=resolved_is_ranged,
        )


def _lookup_monster_data(state: GameState, enemy: Creature) -> dict[str, Any]:
    """Look up an enemy's monsters.json entry on the data loader."""
    loader = getattr(state, "data_loader", None)
    if loader is None:
        return {}
    try:
        monsters = loader.load_monsters()
    except Exception:
        return {}
    key = enemy.name.lower().replace(" ", "_")
    return monsters.get(key, {}) or {}


def _first_weapon_action(monster_data: dict[str, Any]) -> dict[str, Any] | None:
    """Return the first non-Multiattack action from a monster entry.

    Mirrors the current selection in `process_enemy_turn`: skip
    Multiattack entries and take the first concrete weapon attack.
    """
    actions = monster_data.get("actions") or []
    for action in actions:
        name = (action.get("name") or "").lower()
        if "multiattack" in name:
            continue
        return action
    return None
