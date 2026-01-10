# ABOUTME: Spell effect registry and handler exports.
# ABOUTME: Auto-registers effect handlers on import for the plugin architecture.

from typing import TYPE_CHECKING

from .base import SpellEffect, SpellEffectResult

if TYPE_CHECKING:
    pass

# Registry mapping effect_type strings to handler instances
_REGISTRY: dict[str, SpellEffect] = {}


def register(effect: SpellEffect) -> None:
    """
    Register a spell effect handler.

    Args:
        effect: SpellEffect instance to register
    """
    _REGISTRY[effect.effect_type] = effect


def get_effect_handler(effect_type: str) -> SpellEffect | None:
    """
    Get the handler for a spell effect type.

    Args:
        effect_type: The effect_type from spell JSON data

    Returns:
        SpellEffect handler instance, or None if not found
    """
    return _REGISTRY.get(effect_type)


def list_effect_types() -> list[str]:
    """
    List all registered effect types.

    Returns:
        List of registered effect_type strings
    """
    return list(_REGISTRY.keys())


# Import and register effect handlers
# Each module registers its handler(s) when imported
from .illumination import IlluminationEffect  # noqa: E402

register(IlluminationEffect())

from .manipulation import ManipulationEffect  # noqa: E402

register(ManipulationEffect())

from .detection import DetectionEffect  # noqa: E402

register(DetectionEffect())

from .utility import UtilityEffect  # noqa: E402

register(UtilityEffect())


__all__ = [
    "SpellEffect",
    "SpellEffectResult",
    "register",
    "get_effect_handler",
    "list_effect_types",
    "IlluminationEffect",
    "ManipulationEffect",
    "DetectionEffect",
    "UtilityEffect",
]
