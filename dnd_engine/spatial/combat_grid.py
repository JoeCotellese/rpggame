# ABOUTME: Combat grid manager for integrating spatial positioning with combat
# ABOUTME: Provides range checking, distance calculations, and combat movement

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from dnd_engine.spatial.grid import TileMap, EntityInfo
from dnd_engine.spatial.movement import MovementController, MovementMode, MovementState
from dnd_engine.spatial.position import Position, Direction
from dnd_engine.spatial.fov import FieldOfView, FOVConfig

if TYPE_CHECKING:
    from dnd_engine.core.creature import Creature
    from dnd_engine.utils.events import EventBus


# D&D 5E standard: 1 tile = 5 feet
FEET_PER_TILE = 5


class AttackType(Enum):
    """Types of attacks for range checking."""
    MELEE = "melee"
    RANGED = "ranged"
    REACH = "reach"  # Weapons with reach (10ft instead of 5ft)
    SPELL = "spell"


@dataclass
class RangeCheckResult:
    """Result of a range check."""
    in_range: bool
    distance_tiles: int
    distance_feet: int
    requires_movement: int = 0  # Tiles needed to close distance
    message: str = ""


@dataclass
class CombatantInfo:
    """Information about a combatant in grid combat."""
    creature_id: str
    position: Position
    movement_state: MovementState
    is_player: bool = False
    has_moved: bool = False
    has_acted: bool = False


class CombatGridManager:
    """
    Manages grid-based combat positioning and movement.

    Integrates with the existing combat system by providing:
    - Range checking for attacks and spells
    - Distance calculations between combatants
    - Combat movement tracking (D&D 5E: 30ft = 6 tiles per turn)
    - Line of sight for ranged attacks

    Usage:
        # Initialize with a tile map when combat starts
        combat_grid = CombatGridManager(tile_map)

        # Add combatants at their positions
        combat_grid.add_combatant("player", player_creature, Position(5, 5))
        combat_grid.add_combatant("goblin_1", goblin, Position(8, 5))

        # Check if attack is in range
        result = combat_grid.check_melee_range("player", "goblin_1")
        if not result.in_range:
            print(f"Target is {result.distance_feet}ft away, need to move closer")

        # Move combatant during combat
        combat_grid.move_combatant("player", Direction.EAST)
    """

    def __init__(
        self,
        tile_map: TileMap,
        event_bus: EventBus | None = None,
    ):
        """
        Initialize combat grid manager.

        Args:
            tile_map: The map where combat takes place
            event_bus: Optional event bus for movement events
        """
        self.tile_map = tile_map
        self.event_bus = event_bus

        # Movement controller for combat movement
        self.movement_controller = MovementController(
            tile_map=tile_map,
            mode=MovementMode.COMBAT,
            event_bus=event_bus,
        )

        # FOV calculator for line of sight
        self.fov = FieldOfView(tile_map, FOVConfig(max_radius=20, walls_block=True))

        # Track combatants (creature_id -> CombatantInfo)
        self._combatants: dict[str, CombatantInfo] = {}

        # Track creatures for reference
        self._creatures: dict[str, Creature] = {}

    def add_combatant(
        self,
        creature_id: str,
        creature: Creature,
        position: Position,
        is_player: bool = False,
        speed: int = 30,
    ) -> bool:
        """
        Add a combatant to the grid.

        Args:
            creature_id: Unique identifier for this combatant
            creature: The Creature object
            position: Starting position on the grid
            is_player: Whether this is a player character
            speed: Movement speed in feet (default 30)

        Returns:
            True if combatant was added successfully
        """
        # Determine display character
        if is_player:
            display_char = "@"
        elif hasattr(creature, "monster_type"):
            # Use first letter of name for monsters
            display_char = creature.name[0].upper() if creature.name else "M"
        else:
            display_char = "?"

        # Add to tile map
        success = self.tile_map.add_entity(
            entity_id=creature_id,
            position=position,
            display_char=display_char,
            display_name=creature.name,
            is_player=is_player,
            blocks_movement=True,
        )

        if not success:
            return False

        # Set up movement state for combat
        self.movement_controller.set_speed(creature_id, speed)

        # Track combatant info
        self._combatants[creature_id] = CombatantInfo(
            creature_id=creature_id,
            position=position,
            movement_state=self.movement_controller.get_movement_state(creature_id),
            is_player=is_player,
        )

        # Store creature reference
        self._creatures[creature_id] = creature

        return True

    def remove_combatant(self, creature_id: str) -> bool:
        """Remove a combatant from the grid (when defeated)."""
        if creature_id not in self._combatants:
            return False

        self.tile_map.remove_entity(creature_id)
        del self._combatants[creature_id]
        if creature_id in self._creatures:
            del self._creatures[creature_id]

        return True

    def get_position(self, creature_id: str) -> Position | None:
        """Get a combatant's current position."""
        if creature_id in self._combatants:
            return self._combatants[creature_id].position
        return self.tile_map.get_entity_position(creature_id)

    def get_distance(self, creature_id1: str, creature_id2: str) -> int | None:
        """
        Get distance in tiles between two combatants.

        Uses Chebyshev distance (D&D 5E standard where diagonal = 1 tile).

        Returns:
            Distance in tiles, or None if either combatant not found
        """
        pos1 = self.get_position(creature_id1)
        pos2 = self.get_position(creature_id2)

        if pos1 is None or pos2 is None:
            return None

        return pos1.chebyshev_distance(pos2)

    def get_distance_feet(self, creature_id1: str, creature_id2: str) -> int | None:
        """Get distance in feet between two combatants."""
        dist = self.get_distance(creature_id1, creature_id2)
        return dist * FEET_PER_TILE if dist is not None else None

    def check_melee_range(
        self,
        attacker_id: str,
        target_id: str,
        reach: bool = False,
    ) -> RangeCheckResult:
        """
        Check if target is in melee range.

        Args:
            attacker_id: The attacking combatant
            target_id: The target combatant
            reach: If True, use 10ft reach instead of 5ft

        Returns:
            RangeCheckResult with in_range status and distance info
        """
        distance = self.get_distance(attacker_id, target_id)

        if distance is None:
            return RangeCheckResult(
                in_range=False,
                distance_tiles=0,
                distance_feet=0,
                message="Combatant not found",
            )

        distance_feet = distance * FEET_PER_TILE
        melee_range = 2 if reach else 1  # 10ft or 5ft
        melee_range_feet = melee_range * FEET_PER_TILE

        in_range = distance <= melee_range
        requires_movement = max(0, distance - melee_range)

        if in_range:
            message = "Target is in melee range"
        else:
            message = f"Target is {distance_feet}ft away, {requires_movement * FEET_PER_TILE}ft movement needed"

        return RangeCheckResult(
            in_range=in_range,
            distance_tiles=distance,
            distance_feet=distance_feet,
            requires_movement=requires_movement,
            message=message,
        )

    def check_ranged_range(
        self,
        attacker_id: str,
        target_id: str,
        normal_range: int,
        long_range: int | None = None,
    ) -> RangeCheckResult:
        """
        Check if target is in ranged attack range.

        Args:
            attacker_id: The attacking combatant
            target_id: The target combatant
            normal_range: Normal range in feet
            long_range: Long range in feet (attacks have disadvantage)

        Returns:
            RangeCheckResult with in_range status
        """
        distance = self.get_distance(attacker_id, target_id)

        if distance is None:
            return RangeCheckResult(
                in_range=False,
                distance_tiles=0,
                distance_feet=0,
                message="Combatant not found",
            )

        distance_feet = distance * FEET_PER_TILE
        effective_long_range = long_range or normal_range

        # Check range first - if out of range, report that before LOS
        if distance_feet > effective_long_range:
            return RangeCheckResult(
                in_range=False,
                distance_tiles=distance,
                distance_feet=distance_feet,
                message=f"Target is out of range ({distance_feet}ft, max {effective_long_range}ft)",
            )

        # Check line of sight (only for targets within range)
        attacker_pos = self.get_position(attacker_id)
        target_pos = self.get_position(target_id)

        # Compute FOV from attacker to check if target is visible
        self.fov.compute(attacker_pos, radius=effective_long_range // FEET_PER_TILE)
        has_los = self.fov.is_visible(target_pos)

        if not has_los:
            return RangeCheckResult(
                in_range=False,
                distance_tiles=distance,
                distance_feet=distance_feet,
                message="No line of sight to target",
            )

        if distance_feet <= normal_range:
            return RangeCheckResult(
                in_range=True,
                distance_tiles=distance,
                distance_feet=distance_feet,
                message="Target is in normal range",
            )
        else:
            # Must be in long range (we already checked for out of range above)
            return RangeCheckResult(
                in_range=True,
                distance_tiles=distance,
                distance_feet=distance_feet,
                message="Target is at long range (disadvantage)",
            )

    def check_spell_range(
        self,
        caster_id: str,
        target_id: str,
        spell_range: int,
    ) -> RangeCheckResult:
        """
        Check if target is in spell range.

        Args:
            caster_id: The casting combatant
            target_id: The target combatant
            spell_range: Spell range in feet (0 for self, -1 for touch)

        Returns:
            RangeCheckResult with in_range status
        """
        if spell_range == 0:
            # Self-targeting spell
            return RangeCheckResult(
                in_range=(caster_id == target_id),
                distance_tiles=0,
                distance_feet=0,
                message="Self-targeting spell" if caster_id == target_id else "Cannot target others",
            )

        if spell_range == -1:
            # Touch spell - use melee range
            return self.check_melee_range(caster_id, target_id)

        # Regular ranged spell
        distance = self.get_distance(caster_id, target_id)

        if distance is None:
            return RangeCheckResult(
                in_range=False,
                distance_tiles=0,
                distance_feet=0,
                message="Combatant not found",
            )

        distance_feet = distance * FEET_PER_TILE
        in_range = distance_feet <= spell_range

        # Check line of sight for non-self spells
        caster_pos = self.get_position(caster_id)
        target_pos = self.get_position(target_id)

        self.fov.compute(caster_pos, radius=spell_range // FEET_PER_TILE)
        has_los = self.fov.is_visible(target_pos)

        if not has_los:
            return RangeCheckResult(
                in_range=False,
                distance_tiles=distance,
                distance_feet=distance_feet,
                message="No line of sight to target",
            )

        if in_range:
            message = f"Target is within spell range ({distance_feet}ft)"
        else:
            message = f"Target is out of spell range ({distance_feet}ft, max {spell_range}ft)"

        return RangeCheckResult(
            in_range=in_range,
            distance_tiles=distance,
            distance_feet=distance_feet,
            message=message,
        )

    def move_combatant(
        self,
        creature_id: str,
        direction: Direction,
    ) -> bool:
        """
        Move a combatant in combat (consumes movement).

        Args:
            creature_id: The combatant to move
            direction: Direction to move

        Returns:
            True if movement succeeded
        """
        result = self.movement_controller.move(creature_id, direction)

        if result.success and creature_id in self._combatants:
            self._combatants[creature_id].position = result.new_position
            self._combatants[creature_id].has_moved = True

        return result.success

    def get_movement_remaining(self, creature_id: str) -> int:
        """Get remaining movement in feet for a combatant."""
        state = self.movement_controller.get_movement_state(creature_id)
        return state.movement_remaining

    def can_move(self, creature_id: str, tiles: int = 1) -> bool:
        """Check if combatant has enough movement remaining."""
        state = self.movement_controller.get_movement_state(creature_id)
        return state.can_move(tiles)

    def reset_turn(self, creature_id: str) -> None:
        """Reset movement for a combatant's new turn."""
        self.movement_controller.reset_movement(creature_id)
        if creature_id in self._combatants:
            self._combatants[creature_id].has_moved = False
            self._combatants[creature_id].has_acted = False

    def reset_all_turns(self) -> None:
        """Reset movement for all combatants (new round)."""
        for creature_id in self._combatants:
            self.reset_turn(creature_id)

    def get_adjacent_enemies(self, creature_id: str) -> list[str]:
        """Get IDs of all enemies adjacent to a combatant."""
        pos = self.get_position(creature_id)
        if pos is None:
            return []

        combatant = self._combatants.get(creature_id)
        if combatant is None:
            return []

        adjacent = self.tile_map.get_adjacent_entities(pos)

        # Return enemies (opposite team)
        enemies = []
        for entity in adjacent:
            if entity.entity_id in self._combatants:
                other = self._combatants[entity.entity_id]
                if other.is_player != combatant.is_player:
                    enemies.append(entity.entity_id)

        return enemies

    def get_enemies_in_range(
        self,
        creature_id: str,
        range_feet: int,
    ) -> list[tuple[str, int]]:
        """
        Get all enemies within a certain range.

        Args:
            creature_id: The combatant to check from
            range_feet: Maximum range in feet

        Returns:
            List of (enemy_id, distance_feet) tuples, sorted by distance
        """
        combatant = self._combatants.get(creature_id)
        if combatant is None:
            return []

        enemies = []
        for other_id, other in self._combatants.items():
            if other.is_player != combatant.is_player:
                dist = self.get_distance_feet(creature_id, other_id)
                if dist is not None and dist <= range_feet:
                    enemies.append((other_id, dist))

        return sorted(enemies, key=lambda x: x[1])

    def get_closest_enemy(self, creature_id: str) -> tuple[str, int] | None:
        """Get the closest enemy to a combatant."""
        combatant = self._combatants.get(creature_id)
        if combatant is None:
            return None

        closest = None
        closest_dist = float("inf")

        for other_id, other in self._combatants.items():
            if other.is_player != combatant.is_player:
                dist = self.get_distance(creature_id, other_id)
                if dist is not None and dist < closest_dist:
                    closest = other_id
                    closest_dist = dist

        if closest is None:
            return None

        return (closest, int(closest_dist * FEET_PER_TILE))

    def get_all_combatants(self) -> list[CombatantInfo]:
        """Get information about all combatants."""
        return list(self._combatants.values())

    def get_player_combatants(self) -> list[str]:
        """Get IDs of all player combatants."""
        return [c.creature_id for c in self._combatants.values() if c.is_player]

    def get_enemy_combatants(self) -> list[str]:
        """Get IDs of all enemy combatants."""
        return [c.creature_id for c in self._combatants.values() if not c.is_player]
