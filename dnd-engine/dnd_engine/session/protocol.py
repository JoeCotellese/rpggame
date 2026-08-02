# ABOUTME: Serialisable vocabulary describing what a player wants and what happened.
# ABOUTME: Pure data types with no engine coupling, consumed by any client.

"""Session protocol types.

A client needs three things to play a turn: a way to say what the player wants
(:class:`Intent`), a record of what happened (:class:`GameEvent`), and a way to
be asked a question mid-resolution (:class:`PendingDecision`). All three are
bundled into the single value returned by a session action
(:class:`ActionResult`).

Everything here is plain data. This module deliberately imports nothing from
``dnd_engine.core`` — a client that can render from :class:`ActionResult` never
has to reach into engine internals. The one shared import is
:class:`~dnd_engine.utils.events.EventType`, reused rather than duplicated so a
second event taxonomy cannot drift from the one the engine already emits.

Every type round-trips through ``to_dict()`` / ``from_dict()`` so the same
vocabulary serves an in-process client, an MCP tool response, and a save file.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from enum import Enum
from typing import Any, ClassVar

from dnd_engine.utils.events import EventType


def to_jsonable(value: Any) -> Any:
    """Coerce an arbitrary engine value into JSON-native form.

    Engine event payloads are free-form dicts assembled by whichever system
    emits them, and they routinely contain values JSON knows nothing about —
    ``CREATURE_MOVED`` carries :class:`~dnd_engine.core.position.Position`
    objects, other payloads carry enums and tuples. Passing those straight to
    ``json.dumps`` either raises (``Position``) or silently changes type on the
    way back (a tuple returns as a list, so the value no longer compares equal).

    Normalising once, at construction, means the in-memory payload is already
    identical to its wire form, which is what makes round-tripping lossless
    rather than approximately lossless.

    Conversions, in order:

    - ``None``/``str``/``bool``/``int``/``float`` — returned unchanged
    - :class:`Enum` — replaced by its ``value``
    - ``list``/``tuple``/``set`` — a list of normalised members
    - ``dict`` — keys coerced to ``str``, values normalised
    - objects exposing ``to_dict()`` — the normalised result of that call
    - dataclass instances — normalised ``asdict()``, so ``Position(1, 2)``
      becomes ``{"x": 1, "y": 2}`` and stays useful to a client
    - anything else — ``str(value)``, so an unexpected object degrades to
      something renderable instead of breaking the turn

    Args:
        value: Any value found in an engine event payload.

    Returns:
        A structure containing only JSON-native types.
    """
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Enum):
        return to_jsonable(value.value)
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_jsonable(to_dict())
    if is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(asdict(value))

    return str(value)


class IntentKind(str, Enum):
    """Discriminator for the intent subclasses.

    Inherits ``str`` so the value serialises directly and compares equal to its
    wire form without an explicit conversion.
    """

    MOVE = "move"
    ATTACK = "attack"
    WAIT = "wait"
    FREEFORM = "freeform"


@dataclass(frozen=True, slots=True)
class Intent:
    """What an actor wants to do, expressed without engine types.

    Subclasses add their own parameters and set :attr:`kind`. The base class is
    not meant to be instantiated directly; it exists so callers can accept "any
    intent" in a signature and so :meth:`from_dict` has one dispatch point.

    Fields:
        actor_id: Stable id of the creature acting. A string rather than a
            ``Creature`` so a client never needs an engine object to express a
            want.

    Class attributes:
        kind: The discriminator, set by each subclass. Declared as a
            ``ClassVar`` so it stays off the instance and out of the generated
            ``__init__``, keeping the wire form flat.
    """

    actor_id: str

    kind: ClassVar[IntentKind]

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a flat JSON-compatible dict including the discriminator."""
        payload: dict[str, Any] = {"kind": self.kind.value}
        for f in fields(self):
            payload[f.name] = getattr(self, f.name)
        return payload

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Intent:
        """Rebuild the correct subclass from its wire form.

        Args:
            data: A dict as produced by :meth:`to_dict`.

        Returns:
            An instance of the subclass named by ``data["kind"]``.

        Raises:
            ValueError: If ``kind`` is missing or names no known intent.
        """
        raw_kind = data.get("kind")
        if raw_kind is None:
            raise ValueError("intent payload is missing the 'kind' discriminator")

        intent_cls = _INTENT_BY_KIND.get(raw_kind)
        if intent_cls is None:
            known = ", ".join(sorted(_INTENT_BY_KIND))
            raise ValueError(f"unknown intent kind {raw_kind!r}; known kinds: {known}")

        payload = {k: v for k, v in data.items() if k != "kind"}
        return intent_cls(**payload)


@dataclass(frozen=True, slots=True)
class MoveIntent(Intent):
    """Move the actor one step in a compass direction.

    Fields:
        direction: One of ``"north"``, ``"south"``, ``"east"``, ``"west"``.
            Validated by the session that consumes the intent, not here — this
            module stays free of rules.
    """

    direction: str

    kind: ClassVar[IntentKind] = IntentKind.MOVE


@dataclass(frozen=True, slots=True)
class AttackIntent(Intent):
    """Attack a target with the actor's equipped weapon.

    Fields:
        target_ref: Either a stable entity id or a display name. The consuming
            session resolves it, so a client can pass through whatever the
            player typed or clicked without doing lookups itself.
    """

    target_ref: str

    kind: ClassVar[IntentKind] = IntentKind.ATTACK


@dataclass(frozen=True, slots=True)
class WaitIntent(Intent):
    """Take no action and end the actor's turn."""

    kind: ClassVar[IntentKind] = IntentKind.WAIT


@dataclass(frozen=True, slots=True)
class FreeformIntent(Intent):
    """Raw player prose describing something the action menu does not cover.

    Fields:
        text: Verbatim player input, e.g. "I shove the brazier into the webs".
            Carries no interpretation; adjudication happens downstream.
    """

    text: str

    kind: ClassVar[IntentKind] = IntentKind.FREEFORM


# Explicit registry rather than ``__init_subclass__``: ``slots=True`` makes the
# dataclass decorator build a replacement class object, so a hook that fired at
# original class creation would register the pre-slots class and break
# ``from_dict``.
_INTENT_BY_KIND: dict[str, type[Intent]] = {
    cls.kind.value: cls for cls in (MoveIntent, AttackIntent, WaitIntent, FreeformIntent)
}


@dataclass(frozen=True, slots=True)
class GameEvent:
    """One thing that happened, in a form a client can render directly.

    Fields:
        type: Reuses the engine's existing :class:`EventType`. Not a parallel
            enum — a second taxonomy would immediately drift from the event
            types the engine already emits.
        data: Structured payload; the schema is owned by whatever emits the
            event. Normalised through :func:`to_jsonable` at construction, so
            whatever the engine hands over — ``Position`` objects, enums,
            tuples — is stored already in JSON-native form. That normalisation
            is what makes round-tripping lossless: without it a tuple would
            return as a list and no longer compare equal, and a ``Position``
            would not serialise at all. Held as a plain dict, so ``frozen``
            prevents rebinding but not mutation, and a ``GameEvent`` is not
            hashable.
        sequence: Position within one :class:`ActionResult`, counting from 0.
            Lets a client replay or animate events in order without relying on
            list ordering surviving serialisation.
        message: Optional pre-rendered human-readable line. A client may show it
            verbatim or ignore it and render from ``data``. This is what lets a
            thin client stay thin without pushing presentation into the engine.
    """

    type: EventType
    data: dict[str, Any]
    sequence: int
    message: str | None = None

    def __post_init__(self) -> None:
        """Normalise the payload so the in-memory form matches the wire form."""
        object.__setattr__(self, "data", to_jsonable(self.data))

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "type": self.type.value,
            "data": self.data,
            "sequence": self.sequence,
            "message": self.message,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> GameEvent:
        """Rebuild from the wire form produced by :meth:`to_dict`."""
        return GameEvent(
            type=EventType(data["type"]),
            data=data.get("data") or {},
            sequence=data["sequence"],
            message=data.get("message"),
        )


class DecisionKind(str, Enum):
    """What sort of question the engine is asking."""

    REACTION = "reaction"
    TARGET = "target"
    CONFIRM = "confirm"


@dataclass(frozen=True, slots=True)
class DecisionOption:
    """One answer a player may give to a :class:`PendingDecision`.

    Fields:
        option_id: Stable identifier passed back when resolving. Must be unique
            within one decision.
        label: Short text for a menu row or button.
        description: Optional longer explanation, shown as a hint where the UI
            has room for one.
    """

    option_id: str
    label: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "option_id": self.option_id,
            "label": self.label,
            "description": self.description,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> DecisionOption:
        """Rebuild from the wire form produced by :meth:`to_dict`."""
        return DecisionOption(
            option_id=data["option_id"],
            label=data["label"],
            description=data.get("description", ""),
        )


@dataclass(frozen=True, slots=True)
class PendingDecision:
    """The engine is asking a question and cannot proceed until it is answered.

    This is what makes reactions possible for a human player: opportunity
    attacks, Shield, and Counterspell all require resolution to stop mid-flight
    and ask. Without a type like this an engine can only ever resolve reactions
    automatically.

    Fields:
        decision_id: Identifies this question when resolving it. Unique for the
            lifetime of the asking session.
        kind: What sort of question this is, for UI routing.
        actor_id: Whose decision it is — not necessarily whoever acted. An
            opportunity attack asks the *threatening* creature, not the mover.
        prompt: Player-facing question text.
        options: The available answers. Never empty.
        default_option_id: Option to use when nobody can be asked — a headless
            run, an MCP call, or a UI timer expiring. ``None`` means the
            decision has no safe default and must be answered explicitly. When
            set, it must name a member of ``options``.
        context: Free-form structured detail for clients that want to render
            more than the prompt (e.g. which creature provoked, the attack roll
            being reacted to). Must be JSON-serialisable.

    Raises:
        ValueError: If ``options`` is empty, contains duplicate ``option_id``
            values, or ``default_option_id`` names an option that is not present.
    """

    decision_id: str
    kind: DecisionKind
    actor_id: str
    prompt: str
    options: tuple[DecisionOption, ...]
    default_option_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalise the context, then reject decisions a client could not use."""
        object.__setattr__(self, "context", to_jsonable(self.context))

        if not self.options:
            raise ValueError(
                f"PendingDecision {self.decision_id!r} has no options; "
                "a decision with nothing to choose is not answerable"
            )

        option_ids = [option.option_id for option in self.options]
        duplicates = {oid for oid in option_ids if option_ids.count(oid) > 1}
        if duplicates:
            raise ValueError(
                f"PendingDecision {self.decision_id!r} has duplicate option ids: "
                f"{sorted(duplicates)}"
            )

        if self.default_option_id is not None and self.default_option_id not in option_ids:
            raise ValueError(
                f"default_option_id {self.default_option_id!r} is not among the options "
                f"of PendingDecision {self.decision_id!r}: {option_ids}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "decision_id": self.decision_id,
            "kind": self.kind.value,
            "actor_id": self.actor_id,
            "prompt": self.prompt,
            "options": [option.to_dict() for option in self.options],
            "default_option_id": self.default_option_id,
            "context": self.context,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> PendingDecision:
        """Rebuild from the wire form produced by :meth:`to_dict`."""
        return PendingDecision(
            decision_id=data["decision_id"],
            kind=DecisionKind(data["kind"]),
            actor_id=data["actor_id"],
            prompt=data["prompt"],
            options=tuple(DecisionOption.from_dict(o) for o in data.get("options", ())),
            default_option_id=data.get("default_option_id"),
            context=data.get("context") or {},
        )


@dataclass(frozen=True, slots=True)
class ActionResult:
    """Everything that came of one attempted action.

    A client should be able to render a complete turn from this value alone. If
    it needs to reach into engine state to render, the protocol has failed.

    Four outcomes are distinguishable from ``ok`` / :attr:`is_awaiting_decision`
    / ``error`` without inspecting ``events``:

    ===================================  ======  ===================  =======
    Outcome                              ``ok``  awaiting a decision  error
    ===================================  ======  ===================  =======
    Succeeded, play continues            True    False                None
    Succeeded, engine is asking          True    True                 None
    Rejected for a game reason           False   False                set
    ===================================  ======  ===================  =======

    Fields:
        ok: Whether the action was accepted. ``False`` always carries an
            ``error`` explaining why.
        events: What happened, in ``sequence`` order. A tuple because a frozen
            value object should not hand out a mutable collection.
        pending: A question that must be answered before play continues, or
            ``None``.
        error: Human-readable reason the action was rejected. ``None`` on
            success.

    Raises:
        ValueError: If ``ok`` is ``False`` without an ``error``.
    """

    ok: bool
    events: tuple[GameEvent, ...] = ()
    pending: PendingDecision | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        """Guarantee a rejection always explains itself."""
        if not self.ok and self.error is None:
            raise ValueError("ActionResult(ok=False) requires an error explaining the rejection")

    @property
    def is_awaiting_decision(self) -> bool:
        """Whether the engine is blocked on a player decision."""
        return self.pending is not None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "ok": self.ok,
            "events": [event.to_dict() for event in self.events],
            "pending": self.pending.to_dict() if self.pending is not None else None,
            "error": self.error,
        }

    def to_json(self) -> str:
        """Serialise directly to a JSON string, for MCP and other wire callers."""
        return json.dumps(self.to_dict())

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ActionResult:
        """Rebuild from the wire form produced by :meth:`to_dict`."""
        pending = data.get("pending")
        return ActionResult(
            ok=data["ok"],
            events=tuple(GameEvent.from_dict(e) for e in data.get("events", ())),
            pending=PendingDecision.from_dict(pending) if pending is not None else None,
            error=data.get("error"),
        )
