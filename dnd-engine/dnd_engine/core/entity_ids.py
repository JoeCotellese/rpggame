# ABOUTME: Canonical engine-side entity-id derivation helpers for spatial routing.
# ABOUTME: Centralizes the f"pc_{name.lower().replace(' ', '_')}" convention used across engine + client.

from __future__ import annotations


def pc_entity_id(name: str) -> str:
    """Derive the canonical spatial entity_id for a player character.

    Every consumer of the plan-03 spatial index that addresses a PC must
    route through this helper. Inlining the lowercase/underscore
    transformation at call sites drifts (one site lowercases without
    underscoring; another forgets to lowercase) and silently mis-routes
    spatial lookups when a name contains spaces or mixed case.

    Two PC names that fold to the same id (e.g. "Hero" and "HERO" both
    yield ``"pc_hero"``) cannot be distinguished by the spatial index.
    Uniqueness enforcement at character-creation time is filed
    separately — this helper does not validate.
    """
    return f"pc_{name.lower().replace(' ', '_')}"
