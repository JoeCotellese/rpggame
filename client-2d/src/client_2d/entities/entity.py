# ABOUTME: Entity classes representing game objects with live engine references.
# ABOUTME: Enables visual state sync from engine Creatures for rendering and animation.

"""Entity classes for the 2D client with engine references.

This module provides Entity classes that maintain references to engine
Creature objects, enabling live synchronization between engine state
and visual representation.

Architecture:
    Engine Creature <--reference--> Entity <--managed by--> EntityManager
         │                            │
         ├── current_hp               ├── hp (cached)
         ├── is_alive                 ├── is_alive (cached)
         └── active_conditions        └── visual (VisualState)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

import arcade

if TYPE_CHECKING:
    from dnd_engine.core.creature import Creature


class EntityType(Enum):
    """Types of entities that can exist on the map."""

    MONSTER = auto()
    PARTY_MEMBER = auto()
    ITEM = auto()
    DECORATION = auto()


@dataclass
class VisualState:
    """Visual state for rendering and animation.

    Tracks the visual representation of an entity, including
    position offsets for smooth movement animations.

    Attributes:
        offset_x: Pixel offset from grid position (for animation).
        offset_y: Pixel offset from grid position (for animation).
        alpha: Transparency (0-255) for fade effects.
        scale: Scale multiplier for size effects.
        tint: RGB tint color for effects like damage flash.
        is_animating: Whether entity is currently animating.
    """

    offset_x: float = 0.0
    offset_y: float = 0.0
    alpha: int = 255
    scale: float = 1.0
    tint: tuple[int, int, int] = (255, 255, 255)
    is_animating: bool = False


@dataclass
class Entity:
    """Base entity class with engine creature reference.

    Represents any entity on the game map that may be linked to
    an engine Creature object. Caches frequently-accessed state
    for rendering and provides sync methods to update from engine.

    Attributes:
        entity_id: Unique identifier for this entity.
        grid_x: X position in grid coordinates.
        grid_y: Y position in grid coordinates.
        entity_type: Type of entity (monster, party_member, item, etc.).
        sub_type: Specific subtype (e.g., "giant_rat", "longsword").
        visual: Visual state for rendering/animation.
        texture: Loaded arcade texture for rendering.
        hp: Cached current HP from engine creature.
        max_hp: Cached max HP from engine creature.
        is_alive: Cached alive status from engine creature.
        conditions: Cached active conditions from engine creature.
    """

    entity_id: str
    grid_x: int
    grid_y: int
    entity_type: EntityType
    sub_type: str = ""
    visual: VisualState = field(default_factory=VisualState)
    texture: arcade.Texture | None = None
    _creature_ref: Creature | None = field(default=None, repr=False)
    hp: int = 0
    max_hp: int = 0
    is_alive: bool = True
    conditions: set[str] = field(default_factory=set)

    def sync_from_creature(self) -> bool:
        """Sync cached state from the engine creature reference.

        Updates cached HP, is_alive, and conditions from the referenced
        engine Creature. This allows efficient rendering without
        constantly querying the engine.

        Position is **not** synced here. The engine drives position via
        explicit CREATURE_MOVED / CREATURE_PLACED events; the
        EngineBridge subscribes to those events (#647) and writes
        grid_x / grid_y directly so the visual layer sees per-step
        movement without overwriting client-owned writes from legacy
        combat (update_current_turn_position) or MCP tests that set
        grid coordinates by hand.

        Returns:
            True if any state changed, False if unchanged.
            Use this to trigger animations on state changes.
        """
        if self._creature_ref is None:
            return False

        changed = False
        creature = self._creature_ref

        if self.hp != creature.current_hp:
            self.hp = creature.current_hp
            changed = True

        if self.max_hp != creature.max_hp:
            self.max_hp = creature.max_hp
            changed = True

        if self.is_alive != creature.is_alive:
            self.is_alive = creature.is_alive
            changed = True

        new_conditions = set(creature.active_conditions.keys())
        if self.conditions != new_conditions:
            self.conditions = new_conditions
            changed = True

        return changed

    @property
    def creature(self) -> Creature | None:
        """Access the referenced engine Creature."""
        return self._creature_ref

    @creature.setter
    def creature(self, value: Creature | None) -> None:
        """Set the engine Creature reference and sync state."""
        self._creature_ref = value
        if value is not None:
            self.sync_from_creature()


@dataclass
class MonsterEntity(Entity):
    """Entity representing an enemy monster.

    Extends Entity with enemy-specific attributes for combat
    targeting and turn order tracking.

    Attributes:
        enemy_index: Index into GameState.active_enemies for attack targeting.
    """

    enemy_index: int = -1

    def __post_init__(self) -> None:
        """Ensure entity_type is set to MONSTER."""
        self.entity_type = EntityType.MONSTER


@dataclass
class PartyMemberEntity(Entity):
    """Entity representing a party member character.

    Extends Entity with party-specific attributes for combat
    formation and turn highlighting.

    Attributes:
        party_index: Index into Party.characters (0-3 for 4-member party).
        is_current_turn: Whether this character is taking their turn.
        character_class: Character's class (fighter, wizard, etc.) for sprite.
    """

    party_index: int = -1
    is_current_turn: bool = False
    character_class: str = ""

    def __post_init__(self) -> None:
        """Ensure entity_type is set to PARTY_MEMBER."""
        self.entity_type = EntityType.PARTY_MEMBER


@dataclass
class ItemEntity(Entity):
    """Entity representing an item on the ground.

    Extends Entity with item-specific attributes for
    collection tracking.

    Attributes:
        collected: Whether the item has been picked up.
        item_category: Category like "weapons", "potions", "misc".
    """

    collected: bool = False
    item_category: str = ""

    def __post_init__(self) -> None:
        """Ensure entity_type is set to ITEM."""
        self.entity_type = EntityType.ITEM
