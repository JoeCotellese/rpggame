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
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
