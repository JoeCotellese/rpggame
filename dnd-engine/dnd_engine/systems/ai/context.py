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
    ) -> TurnContext:
        """Construct a TurnContext from a game state + enemy.

        Looks up the enemy's first non-Multiattack action from the
        monsters catalog (preserving the current `process_enemy_turn`
        action-selection contract). Falls back to None when the
        catalog or the action list is missing — callers handle that
        as "no valid attack".

        Args:
            state: The active game state.
            enemy: The enemy whose turn is starting.
            target_pool: Optional pre-resolved list of living party
                members. When None, falls back to an empty list —
                the pipeline resolves the pool separately.
            monster_data: Optional pre-resolved monster data dict.
                When None, looks up `enemy.name.lower()` in the
                catalog and returns an empty dict on miss.

        Returns:
            A frozen `TurnContext` ready to thread through `decide`.
        """
        pool = target_pool if target_pool is not None else []
        m_data = monster_data if monster_data is not None else _lookup_monster_data(state, enemy)

        action_data = _first_weapon_action(m_data)
        reach_ft: int | None = None
        is_ranged = False
        if action_data is not None:
            reach_ft = attack_reach_for(action_data)
            is_ranged = is_ranged_action(action_data)

        return cls(
            state=state,
            actor=enemy,
            target_pool=pool,
            monster_data=m_data,
            action_data=action_data,
            reach_ft=reach_ft,
            is_ranged=is_ranged,
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
