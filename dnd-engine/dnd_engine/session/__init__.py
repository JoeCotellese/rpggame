# ABOUTME: Public exports for the session protocol - the client-facing engine vocabulary.
# ABOUTME: Import from here rather than from submodules so internals stay free to move.

"""Session layer for the D&D 5E engine.

The vocabulary a client uses to drive the game: express an intent, receive the
events it produced, and answer any question the engine raises mid-resolution.

    from dnd_engine.session import ActionResult, MoveIntent

`Session` owns the turn loop: submit an intent, receive everything that
happened, up to the next point a player must decide.
"""

from dnd_engine.session.protocol import (
    ActionResult,
    AttackIntent,
    DecisionKind,
    DecisionOption,
    ErrorKind,
    FreeformIntent,
    GameEvent,
    Intent,
    IntentKind,
    MoveIntent,
    PendingDecision,
    WaitIntent,
    to_jsonable,
)
from dnd_engine.session.session import Session

__all__ = [
    "ActionResult",
    "ErrorKind",
    "Session",
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
    "to_jsonable",
]
