# ABOUTME: Manages Entity lifecycle and synchronization with engine state.
# ABOUTME: Creates entities from engine state and handles sync, death removal, combat formation.

"""EntityManager for managing game entities.

This module provides the EntityManager class that handles:
- Creating entities from engine state during room load
- Synchronizing entity state from engine creatures
- Removing dead entities after combat
- Spreading party members into combat formation
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import arcade

from client_2d.entities.entity import (
    Entity,
    EntityType,
    ItemEntity,
    MonsterEntity,
    PartyMemberEntity,
)

if TYPE_CHECKING:

    from client_2d.integration.engine_adapter import EngineAdapter
    from client_2d.integration.layout_loader import RoomLayout


class EntityManager:
    """Manages entity lifecycle and synchronization with engine state.

    The EntityManager is responsible for:
    - Creating entities when loading a room (monsters from active_enemies, items from room data)
    - Syncing entity state from engine creatures (HP, conditions, alive status)
    - Removing dead entities and returning them for death animations
    - Creating party member entities for combat spread formation

    Usage:
        manager = EntityManager()
        manager.load_from_room(engine, layout, room_data, textures)

        # After combat actions:
        changed = manager.sync_from_engine(engine)
        dead = manager.remove_dead_entities()

        # Get entities for rendering:
        for entity in manager.get_all():
            draw(entity)
    """

    def __init__(self) -> None:
        """Initialize an empty EntityManager."""
        self._entities: dict[str, Entity] = {}
        self._monsters: dict[str, MonsterEntity] = {}
        self._party_members: dict[str, PartyMemberEntity] = {}
        self._items: dict[str, ItemEntity] = {}

    def clear(self) -> None:
        """Remove all entities. Call on room transitions."""
        self._entities.clear()
        self._monsters.clear()
        self._party_members.clear()
        self._items.clear()

    def load_from_room(
        self,
        engine: EngineAdapter,
        layout: RoomLayout,
        room_data: dict[str, Any] | None,
        monster_textures: dict[str, arcade.Texture | None],
        item_textures: dict[str, arcade.Texture | None],
    ) -> None:
        """Create entities from engine state and room layout.

        Creates MonsterEntity objects for each active enemy in engine state,
        and ItemEntity objects for visible items in room_data.

        Args:
            engine: EngineAdapter providing access to game state.
            layout: RoomLayout with entity spawn positions.
            room_data: Room JSON data with items and decoration info.
            monster_textures: Dict mapping monster IDs to loaded textures.
            item_textures: Dict mapping item IDs to loaded textures.
        """
        self.clear()

        game_state = engine.game_state
        if game_state is None:
            return

        # Create entities for active enemies from engine
        enemy_positions = layout.entity_positions.enemies
        for i, enemy in enumerate(game_state.active_enemies):
            if i < len(enemy_positions):
                ex, ey = enemy_positions[i]
            else:
                ex = layout.width // 2 + i
                ey = layout.height // 2

            # Extract monster type from name (e.g., "Giant Rat 1" -> "giant_rat")
            monster_type = enemy.name.lower().replace(" ", "_")
            # Strip trailing numbers for texture lookup
            base_type = monster_type.rstrip("0123456789").rstrip("_")

            entity_id = f"monster_{i}"
            monster = MonsterEntity(
                entity_id=entity_id,
                grid_x=ex,
                grid_y=ey,
                entity_type=EntityType.MONSTER,
                sub_type=base_type,
                enemy_index=i,
                texture=monster_textures.get(base_type),
            )
            monster.creature = enemy  # Sets reference and syncs state
            self._add_entity(monster)

        # Create entities for items from room data
        if room_data:
            room_items = room_data.get("items", [])
            item_positions = layout.entity_positions.items
            visible_idx = 0
            for item_data in room_items:
                if not item_data.get("visible", True):
                    continue

                item_id = item_data.get("id", f"item_{visible_idx}")
                if visible_idx < len(item_positions):
                    ix, iy = item_positions[visible_idx]
                else:
                    ix = 3 + (visible_idx * 2) % (layout.width - 6)
                    iy = 3 + (visible_idx * 3) % (layout.height - 6)

                entity = ItemEntity(
                    entity_id=f"item_{item_id}",
                    grid_x=ix,
                    grid_y=iy,
                    entity_type=EntityType.ITEM,
                    sub_type=item_id,
                    item_category=item_data.get("category", "misc"),
                    texture=item_textures.get(item_id),
                )
                self._add_entity(entity)
                visible_idx += 1

    def sync_from_engine(self, engine: EngineAdapter) -> list[Entity]:
        """Sync all entities with engine creature state.

        Updates cached state (HP, conditions, alive) for all entities
        that have creature references.

        Args:
            engine: EngineAdapter (currently unused, entities have direct refs).

        Returns:
            List of entities whose state changed (for animation triggers).
        """
        changed: list[Entity] = []

        for monster in self._monsters.values():
            if monster.sync_from_creature():
                changed.append(monster)

        for party_member in self._party_members.values():
            if party_member.sync_from_creature():
                changed.append(party_member)

        return changed

    def remove_dead_entities(self) -> list[Entity]:
        """Remove dead entities from the manager.

        Checks all monster entities and removes those that are no longer alive.
        Party members are NOT removed when dead (they remain for resurrection).

        Returns:
            List of removed entities (for death animation triggers).
        """
        removed: list[Entity] = []

        # Find dead monsters
        dead_monster_ids = [
            entity_id
            for entity_id, monster in self._monsters.items()
            if not monster.is_alive
        ]

        # Remove them
        for entity_id in dead_monster_ids:
            monster = self._monsters.pop(entity_id)
            self._entities.pop(entity_id, None)
            removed.append(monster)

        return removed

    def spread_party_for_combat(
        self,
        engine: EngineAdapter,
        center_x: int,
        center_y: int,
        layout: RoomLayout,
        character_textures: dict[str, arcade.Texture | None],
    ) -> list[tuple[int, int]]:
        """Create party member entities in combat formation.

        Spreads the party into a 2x2 formation around the center point,
        with front-row fighters and back-row casters.

        Formation (assuming enemies to the north):
            Back row:  [2] [3]  (wizard, rogue)
            Front row: [0] [1]  (fighters)

        Args:
            engine: EngineAdapter providing party data.
            center_x: Center X position for formation.
            center_y: Center Y position for formation.
            layout: RoomLayout to check for blocking tiles.
            character_textures: Dict mapping class names to textures.

        Returns:
            List of (x, y) positions for each party member, in formation order.
        """
        # Clear any existing party member entities
        for entity_id in list(self._party_members.keys()):
            self._entities.pop(entity_id, None)
        self._party_members.clear()

        party_data = engine.get_party_for_rendering()
        if not party_data:
            return []

        # Formation offsets: front row closer to enemies (north = lower y)
        offsets = [
            (-1, 0),   # Front-left
            (1, 0),    # Front-right
            (-1, 1),   # Back-left
            (1, 1),    # Back-right
        ]

        positions: list[tuple[int, int]] = []

        for i, char_data in enumerate(party_data[:4]):  # Max 4 party members
            if i < len(offsets):
                dx, dy = offsets[i]
            else:
                dx, dy = 0, i

            px, py = center_x + dx, center_y + dy

            # Clamp to room bounds and avoid walls
            px = max(1, min(px, layout.width - 2))
            py = max(1, min(py, layout.height - 2))

            # If blocked, try the center position
            if layout.is_blocking(px, py):
                px, py = center_x, center_y

            positions.append((px, py))

            # Get creature reference from engine
            creature_ref = None
            party = engine.party
            if party and i < len(party.characters):
                creature_ref = party.characters[i]

            char_class = char_data["class"].lower()
            entity = PartyMemberEntity(
                entity_id=f"party_{i}",
                grid_x=px,
                grid_y=py,
                entity_type=EntityType.PARTY_MEMBER,
                sub_type=char_class,
                party_index=i,
                is_current_turn=char_data.get("is_current_turn", False),
                character_class=char_class,
                texture=character_textures.get(char_class),
            )
            if creature_ref is not None:
                entity.creature = creature_ref
            self._add_entity(entity)

        return positions

    def collapse_party(self) -> None:
        """Remove party member entities after combat ends.

        Called when combat ends to remove the spread party members.
        The player returns to single-unit representation.
        """
        for entity_id in list(self._party_members.keys()):
            self._entities.pop(entity_id, None)
        self._party_members.clear()

    def update_party_turn_status(self, engine: EngineAdapter) -> None:
        """Update is_current_turn for all party member entities.

        Args:
            engine: EngineAdapter to get current combatant info.
        """
        current = engine.get_current_combatant()
        current_creature = current.get("creature") if current else None

        for party_member in self._party_members.values():
            party_member.is_current_turn = (
                party_member._creature_ref is not None
                and party_member._creature_ref is current_creature
            )

    def _add_entity(self, entity: Entity) -> None:
        """Add an entity to the appropriate collections."""
        self._entities[entity.entity_id] = entity

        if isinstance(entity, MonsterEntity):
            self._monsters[entity.entity_id] = entity
        elif isinstance(entity, PartyMemberEntity):
            self._party_members[entity.entity_id] = entity
        elif isinstance(entity, ItemEntity):
            self._items[entity.entity_id] = entity

    def get_all(self) -> list[Entity]:
        """Get all entities for rendering."""
        return list(self._entities.values())

    def get_monsters(self) -> list[MonsterEntity]:
        """Get all monster entities."""
        return list(self._monsters.values())

    def get_party_members(self) -> list[PartyMemberEntity]:
        """Get all party member entities."""
        return list(self._party_members.values())

    def get_items(self) -> list[ItemEntity]:
        """Get all item entities."""
        return list(self._items.values())

    def get_at_position(self, x: int, y: int) -> Entity | None:
        """Get entity at a specific grid position.

        Args:
            x: Grid X coordinate.
            y: Grid Y coordinate.

        Returns:
            Entity at that position, or None if empty.
        """
        for entity in self._entities.values():
            if entity.grid_x == x and entity.grid_y == y:
                return entity
        return None

    def get_by_id(self, entity_id: str) -> Entity | None:
        """Get an entity by its ID.

        Args:
            entity_id: The entity's unique identifier.

        Returns:
            The entity, or None if not found.
        """
        return self._entities.get(entity_id)
