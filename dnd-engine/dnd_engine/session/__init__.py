# ABOUTME: Public exports for the session protocol - the client-facing engine vocabulary.
# ABOUTME: Import from here rather than from submodules so internals stay free to move.

"""Session layer for the D&D 5E engine.

The vocabulary a client uses to drive the game: express an intent, receive the
events it produced, and answer any question the engine raises mid-resolution.

    from dnd_engine.session import ActionResult, MoveIntent

Currently protocol types only; the session that consumes them lands in P1-02.
"""

from dnd_engine.session.protocol import (
    ActionResult,
    AttackIntent,
    DecisionKind,
    DecisionOption,
    FreeformIntent,
    GameEvent,
    Intent,
    IntentKind,
    MoveIntent,
    PendingDecision,
    WaitIntent,
)

__all__ = [
    "ActionResult",
    "AttackIntent",
    "DecisionKind",
    "DecisionOption",
    "FreeformIntent",
    "GameEvent",
    "Intent",
    "IntentKind",
    "MoveIntent",
    "PendingDecision",
    "WaitIntent",
]
