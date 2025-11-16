# ABOUTME: Central game state manager coordinating all game systems
# ABOUTME: Manages dungeon exploration, combat state, player actions, and game flow

from typing import Dict, List, Any, Optional
from dnd_engine.core.character import Character
from dnd_engine.core.party import Party
from dnd_engine.core.creature import Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.combat import CombatEngine
from dnd_engine.systems.initiative import InitiativeTracker
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus, Event, EventType


class GameState:
    """
    Central game state manager.

    Coordinates all game systems and maintains the complete game state:
    - Party of player characters
    - Current dungeon and room
    - Combat state and active enemies
    - Game events

    Serves as the single source of truth for the entire game.
    """

    def __init__(
        self,
        party: Party,
        dungeon_name: str,
        event_bus: Optional[EventBus] = None,
        data_loader: Optional[DataLoader] = None,
        dice_roller: Optional[DiceRoller] = None
    ):
        """
        Initialize the game state.

        Args:
            party: The party of player characters
            dungeon_name: Name of the dungeon to load
            event_bus: Event bus for game events (creates new if not provided)
            data_loader: Data loader for loading content (creates new if not provided)
            dice_roller: Dice roller (creates new if not provided)
        """
        self.party = party
        self.event_bus = event_bus or EventBus()
        self.data_loader = data_loader or DataLoader()
        self.dice_roller = dice_roller or DiceRoller()

        # Load dungeon
        self.dungeon = self.data_loader.load_dungeon(dungeon_name)
        self.current_room_id = self.dungeon["start_room"]

        # Combat state
        self.in_combat = False
        self.initiative_tracker: Optional[InitiativeTracker] = None
        self.active_enemies: List[Creature] = []
        self.combat_engine = CombatEngine(self.dice_roller)

        # Action history for narrative context
        self.action_history: List[str] = []

    def get_current_room(self) -> Dict[str, Any]:
        """
        Get the current room data.

        Returns:
            Dictionary containing room information
        """
        return self.dungeon["rooms"][self.current_room_id]

    def get_available_actions(self) -> List[str]:
        """
        Get list of available actions in the current state.

        Returns:
            List of action names (e.g., ["move", "attack", "search"])
        """
        if self.in_combat:
            return ["attack", "use_item"]
        else:
            actions = ["move"]
            room = self.get_current_room()
            if room.get("searchable") and not room.get("searched"):
                actions.append("search")
            return actions

    def move(self, direction: str) -> bool:
        """
        Move the player in a direction.

        Args:
            direction: Direction to move (must match an exit in current room)

        Returns:
            True if move was successful, False otherwise
        """
        if self.in_combat:
            return False  # Cannot move during combat

        current_room = self.get_current_room()
        exits = current_room.get("exits", {})

        if direction not in exits:
            return False  # Invalid direction

        # Move to new room
        new_room_id = exits[direction]
        self.current_room_id = new_room_id

        # Emit room enter event
        self.event_bus.emit(Event(
            type=EventType.ROOM_ENTER,
            data={
                "room_id": new_room_id,
                "room_name": self.get_current_room()["name"]
            }
        ))

        # Check for enemies and start combat if needed
        self._check_for_enemies()

        return True

    def search_room(self) -> List[Dict[str, Any]]:
        """
        Search the current room for hidden items.

        Adds items to party members' inventories and emits events.
        Gold is split evenly among all party members.
        Items go to the first living party member.

        Returns:
            List of items found
        """
        room = self.get_current_room()

        if room.get("searched"):
            return []  # Already searched

        if not room.get("searchable"):
            return []  # Not searchable

        # Mark as searched
        room["searched"] = True

        # Get items and add to inventory
        items = room.get("items", [])
        living_members = self.party.get_living_members()

        if not living_members:
            return items  # No one alive to pick up items

        for item in items:
            if item["type"] == "gold":
                amount = item["amount"]
                # Split gold evenly among all party members (living and dead)
                split_amount = amount // len(self.party.characters)
                for character in self.party.characters:
                    character.inventory.add_gold(split_amount)
                # Emit gold acquired event
                self.event_bus.emit(Event(
                    type=EventType.GOLD_ACQUIRED,
                    data={"amount": amount}
                ))
            elif item["type"] == "item":
                item_id = item["id"]
                category = self._get_item_category(item_id)
                if category:
                    # Add item to first living party member's inventory
                    living_members[0].inventory.add_item(item_id, category)
                    # Emit item acquired event
                    self.event_bus.emit(Event(
                        type=EventType.ITEM_ACQUIRED,
                        data={"item_id": item_id, "category": category, "character": living_members[0].name}
                    ))

        return items

    def _get_item_category(self, item_id: str) -> Optional[str]:
        """
        Determine the category of an item by ID.

        Args:
            item_id: ID of the item

        Returns:
            Category name ("weapons", "armor", "consumables") or None if not found
        """
        items_data = self.data_loader.load_items()
        for category in ["weapons", "armor", "consumables"]:
            if item_id in items_data.get(category, {}):
                return category
        return None

    def get_room_description(self) -> str:
        """
        Get a description of the current room.

        Returns:
            Room description string
        """
        room = self.get_current_room()
        desc = f"{room['name']}\n\n{room['description']}\n"

        # Add exits
        exits = room.get("exits", {})
        if exits:
            exit_str = ", ".join(exits.keys())
            desc += f"\nExits: {exit_str}"

        # Add enemy info if in combat
        if self.in_combat and self.active_enemies:
            enemy_names = [e.name for e in self.active_enemies if e.is_alive]
            if enemy_names:
                desc += f"\n\nEnemies: {', '.join(enemy_names)}"

        return desc

    def get_player_status(self) -> List[Dict[str, Any]]:
        """
        Get status for all party members.

        Returns:
            List of dictionaries with character stats for each party member
        """
        return [
            {
                "name": char.name,
                "hp": char.current_hp,
                "max_hp": char.max_hp,
                "ac": char.ac,
                "level": char.level,
                "xp": char.xp,
                "alive": char.is_alive
            }
            for char in self.party.characters
        ]

    def is_game_over(self) -> bool:
        """
        Check if the game is over.

        Returns:
            True if game should end (entire party is dead)
        """
        return self.party.is_wiped()

    def _check_for_enemies(self) -> None:
        """Check current room for enemies and start combat if found."""
        room = self.get_current_room()
        enemy_ids = room.get("enemies", [])

        if not enemy_ids:
            return  # No enemies

        # Create enemy creatures
        self.active_enemies = []
        for enemy_id in enemy_ids:
            enemy = self.data_loader.create_monster(enemy_id)
            self.active_enemies.append(enemy)

        # Start combat
        self._start_combat()

    def _start_combat(self) -> None:
        """Initialize combat with current enemies."""
        self.in_combat = True
        self.initiative_tracker = InitiativeTracker(self.dice_roller)

        # Add all living party members to initiative
        for character in self.party.get_living_members():
            self.initiative_tracker.add_combatant(character)

        # Add enemies to initiative
        for enemy in self.active_enemies:
            self.initiative_tracker.add_combatant(enemy)

        # Emit combat start event
        self.event_bus.emit(Event(
            type=EventType.COMBAT_START,
            data={
                "enemies": [e.name for e in self.active_enemies],
                "party": [c.name for c in self.party.get_living_members()]
            }
        ))

    def _check_combat_end(self) -> None:
        """Check if combat should end and handle cleanup."""
        # Remove dead enemies from tracker
        for enemy in self.active_enemies:
            if not enemy.is_alive and self.initiative_tracker:
                self.initiative_tracker.remove_combatant(enemy)

        # Check if combat is over (all enemies dead OR party wiped)
        if self.initiative_tracker:
            all_enemies_dead = all(not enemy.is_alive for enemy in self.active_enemies)
            party_wiped = self.party.is_wiped()

            if all_enemies_dead or party_wiped:
                self._end_combat()

    def _end_combat(self) -> None:
        """End combat and perform cleanup."""
        # Calculate XP from defeated enemies
        total_xp = 0
        monsters = self.data_loader.load_monsters()

        for enemy in self.active_enemies:
            if not enemy.is_alive:
                # Find enemy XP value
                for monster_id, monster_data in monsters.items():
                    if monster_data["name"] == enemy.name:
                        total_xp += monster_data.get("xp", 0)
                        break

        # Award XP to all party members (split evenly)
        if total_xp > 0 and len(self.party.characters) > 0:
            xp_per_character = total_xp // len(self.party.characters)
            for character in self.party.characters:
                character.gain_xp(xp_per_character)

        # Clear combat state
        self.in_combat = False
        self.initiative_tracker = None

        # Remove defeated enemies from room
        room = self.get_current_room()
        room["enemies"] = []

        # Emit combat end event
        self.event_bus.emit(Event(
            type=EventType.COMBAT_END,
            data={
                "victory": True,
                "xp_gained": total_xp,
                "xp_per_character": total_xp // len(self.party.characters) if len(self.party.characters) > 0 else 0
            }
        ))
