# ABOUTME: Registry of class features (Second Wind, Action Surge, etc.) as callable, action-costed handlers
# ABOUTME: Prerequisite for the Magic action (#446); catalogs features so they can be dispatched on a turn

"""Class-feature registry for the SRD "use a magical feature" surface.

Class features used to live as descriptive strings in
``dnd_engine/data/srd/classes.json`` with no callable surface. This
module turns each into a :class:`ClassFeature`: a stable id, the action
it costs, the resource pool it spends, and a handler that applies the
effect and returns a structured :class:`FeatureResult`.

The Magic action dispatcher (#446) consumes this registry; the
:func:`use_feature` dispatcher here owns the action-economy and
resource gating so callers do not repeat it.

How to add a class feature
---------------------------
1. Add a stable ``"feature_id"`` to the feature's entry in
   ``classes.json`` ``features_by_level`` (e.g. ``"fighter.second_wind"``).
   If the feature spends a per-rest resource, keep its existing
   ``"resource"`` block — pools are granted at level-up by
   ``Character._grant_class_features``.
2. Register a handler here keyed by that same ``feature_id`` using the
   :func:`register` decorator, declaring the action cost and (for
   dispatcher-managed spend) the resource pool name.

``tests/test_class_features.py`` walks ``classes.json`` and fails CI if a
declared ``feature_id`` has no handler here — so a forgotten handler is
caught and points right back at this module.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from dnd_engine.core.dice import DiceRoller
from dnd_engine.systems.action_economy import ActionType, TurnState

if TYPE_CHECKING:
    from dnd_engine.core.creature import Creature


@dataclass
class FeatureResult:
    """Structured outcome of attempting to use a class feature.

    Attributes:
        success: Whether the feature was used.
        message: Short human-readable reason or label (failure reason on
            ``success=False``; the feature name on success).
        data: Feature-specific payload (e.g. ``{"healed": 7}``).
    """

    success: bool
    message: str | None = None
    data: dict = field(default_factory=dict)


# A handler applies the feature's effect. Action-economy and resource
# spend are already settled by use_feature() before it is called.
FeatureHandler = Callable[["Creature", TurnState, Any, Any], FeatureResult]


@dataclass
class ClassFeature:
    """A class feature catalogued for combat-turn dispatch.

    Attributes:
        feature_id: Stable id, e.g. ``"fighter.second_wind"``.
        name: Display name.
        action_cost: The action economy slot the feature costs
            (``ActionType.NO_ACTION`` for features that cost nothing).
        resource_pool: Name of the :class:`ResourcePool` the dispatcher
            spends, or ``None`` when the handler manages its own
            resource accounting (e.g. Arcane Recovery).
        handler: Callable applying the effect.
        uses: Resource units spent per activation (default 1).
    """

    feature_id: str
    name: str
    action_cost: ActionType
    resource_pool: str | None
    handler: FeatureHandler
    uses: int = 1


# The one place every dispatchable class feature is registered.
FEATURE_REGISTRY: dict[str, ClassFeature] = {}


def register(
    feature_id: str,
    name: str,
    action_cost: ActionType,
    resource_pool: str | None,
    uses: int = 1,
    registry: dict[str, ClassFeature] | None = None,
) -> Callable[[FeatureHandler], FeatureHandler]:
    """Decorator that registers a handler as a :class:`ClassFeature`.

    Args:
        feature_id: Stable id keying the registry.
        name: Display name.
        action_cost: Action-economy slot the feature costs.
        resource_pool: Dispatcher-managed pool name, or ``None`` for
            handler-managed accounting.
        uses: Resource units per activation.
        registry: Target registry (defaults to the global
            ``FEATURE_REGISTRY``; overridable for test isolation).

    Returns:
        The handler unchanged, after registering it.
    """
    target = FEATURE_REGISTRY if registry is None else registry

    def decorator(handler: FeatureHandler) -> FeatureHandler:
        target[feature_id] = ClassFeature(
            feature_id=feature_id,
            name=name,
            action_cost=action_cost,
            resource_pool=resource_pool,
            handler=handler,
            uses=uses,
        )
        return handler

    return decorator


def get_feature(
    feature_id: str, registry: dict[str, ClassFeature] | None = None
) -> ClassFeature | None:
    """Return the registered feature, or ``None`` if unknown."""
    target = FEATURE_REGISTRY if registry is None else registry
    return target.get(feature_id)


def list_features(
    registry: dict[str, ClassFeature] | None = None,
) -> list[ClassFeature]:
    """Return all registered features."""
    target = FEATURE_REGISTRY if registry is None else registry
    return list(target.values())


def use_feature(
    actor: Creature,
    turn_state: TurnState,
    feature_id: str,
    *,
    target: Any = None,
    payload: Any = None,
    registry: dict[str, ClassFeature] | None = None,
) -> FeatureResult:
    """Dispatch a class feature, settling action economy and resources.

    Gating runs *before* any consumption: if either the action slot or
    the resource pool is unavailable, nothing is consumed and a failure
    result is returned. Only when both gates pass are the action slot
    and (for dispatcher-managed features) the resource spent, and the
    handler invoked.

    Args:
        actor: The creature using the feature.
        turn_state: The actor's :class:`TurnState`.
        feature_id: Id of the feature to use.
        target: Optional target creature/object for the handler.
        payload: Optional feature-specific input for the handler
            (e.g. ``{"spell_slot_levels": {1: 1}}`` for Arcane Recovery,
            or ``{"dice_roller": DiceRoller(seed=...)}`` for determinism).
        registry: Registry to dispatch against (defaults to the global).

    Returns:
        The handler's :class:`FeatureResult`, or a failure result when
        the feature is unknown or a gate refuses.
    """
    feature = get_feature(feature_id, registry=registry)
    if feature is None:
        return FeatureResult(False, f"unknown feature: {feature_id}")

    if not turn_state.is_action_available(feature.action_cost):
        return FeatureResult(False, "action unavailable")

    if feature.resource_pool is not None:
        get_pool = getattr(actor, "get_resource_pool", None)
        pool = get_pool(feature.resource_pool) if get_pool else None
        if pool is None or not pool.is_available(feature.uses):
            return FeatureResult(False, "resource unavailable")

    turn_state.consume_action(feature.action_cost)
    if feature.resource_pool is not None:
        actor.use_resource(feature.resource_pool, feature.uses)

    return feature.handler(actor, turn_state, target, payload)


# --------------------------------------------------------------------------
# Cohort handlers — existing-class proof of concept (Fighter, Wizard).
# Each id below mirrors a "feature_id" in classes.json (see guardrail test).
# --------------------------------------------------------------------------


@register(
    "fighter.second_wind",
    "Second Wind",
    ActionType.BONUS_ACTION,
    "second_wind",
)
def _second_wind(
    actor: Creature, turn_state: TurnState, target: Any, payload: Any
) -> FeatureResult:
    """Regain 1d10 + fighter level HP as a Bonus Action (once per short rest)."""
    payload = payload or {}
    roller = payload.get("dice_roller") or DiceRoller()
    roll = roller.roll(f"1d10+{actor.level}")
    healed = actor.recover_hp(roll.total)
    return FeatureResult(True, "Second Wind", {"healed": healed, "roll": roll.total})


@register(
    "fighter.action_surge",
    "Action Surge",
    ActionType.NO_ACTION,
    "action_surge",
)
def _action_surge(
    actor: Creature, turn_state: TurnState, target: Any, payload: Any
) -> FeatureResult:
    """Take one additional action this turn (once per short rest)."""
    turn_state.action_available = True
    return FeatureResult(True, "Action Surge", {"extra_action": True})


@register(
    "wizard.arcane_recovery",
    "Arcane Recovery",
    ActionType.NO_ACTION,
    # resource_pool=None: Character.use_arcane_recovery consumes the
    # "arcane_recovery" pool itself, so the dispatcher must not also
    # spend it (that would double-consume).
    None,
)
def _arcane_recovery(
    actor: Creature, turn_state: TurnState, target: Any, payload: Any
) -> FeatureResult:
    """Recover spell slots (once per long rest); delegates to the Character.

    The slots to recover are passed via ``payload["spell_slot_levels"]``
    (e.g. ``{1: 1}`` for one 1st-level slot).
    """
    payload = payload or {}
    slot_levels = payload.get("spell_slot_levels", {})
    recovered = actor.use_arcane_recovery(slot_levels)
    if not recovered:
        return FeatureResult(False, "arcane recovery unavailable")
    return FeatureResult(True, "Arcane Recovery", {"recovered": slot_levels})
