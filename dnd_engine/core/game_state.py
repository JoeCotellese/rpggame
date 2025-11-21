# ABOUTME: Central game state manager coordinating all game systems
# ABOUTME: Manages dungeon exploration, combat state, player actions, and game flow

from typing import Dict, List, Any, Optional
from dnd_engine.core.character import Character
from dnd_engine.core.party import Party
from dnd_engine.core.creature import Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.combat import CombatEngine, AttackResult
from dnd_engine.systems.initiative import InitiativeTracker
from dnd_engine.systems.action_economy import ActionType
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus, Event, EventType


# Direction reversal mapping for fleeing combat
REVERSE_DIRECTIONS = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
    "up": "down",
    "down": "up"
}


class CombatItemResult:
    """Result of using a combat attack item (thrown weapon)."""
    def __init__(
        self,
        success: bool,
        attack_result: Optional[AttackResult],
        item_name: str,
        action_type: ActionType,
        special_effects: Optional[List[str]] = None,
        error_message: Optional[str] = None
    ):
        self.success = success
        self.attack_result = attack_result
        self.item_name = item_name
        self.action_type = action_type
        self.special_effects = special_effects or []
        self.error_message = error_message


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
        self.dungeon_name = dungeon_name  # Store filename for saving
        self.dungeon = self.data_loader.load_dungeon(dungeon_name)
        self.current_room_id = self.dungeon["start_room"]

        # Combat state
        self.in_combat = False
        self.initiative_tracker: Optional[InitiativeTracker] = None
        self.active_enemies: List[Creature] = []
        self.combat_engine = CombatEngine(self.dice_roller)

        # Navigation tracking for flee mechanic
        self.last_entry_direction: Optional[str] = None

        # Action history for narrative context
        self.action_history: List[str] = []

    def start(self) -> None:
        """
        Begin the game.

        Called once after initialization to check the starting room
        for enemies and perform any other game start logic.
        """
        # Check for passive perception features
        self._check_passive_perception()

        # Check for enemies
        self._check_for_enemies()

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

    def move(self, direction: str, check_for_enemies: bool = True) -> bool:
        """
        Move the player in a direction.

        Args:
            direction: Direction to move (must match an exit in current room)
            check_for_enemies: Whether to check for enemies after moving (default True)

        Returns:
            True if move was successful, False otherwise
        """
        if self.in_combat:
            return False  # Cannot move during combat

        current_room = self.get_current_room()
        exits = current_room.get("exits", {})

        if direction not in exits:
            return False  # Invalid direction

        # Check if exit is locked
        if self.is_exit_locked(direction):
            return False  # Door is locked

        # Track direction for flee mechanic (before moving)
        self.last_entry_direction = direction

        # Get destination (handle both string and dict formats)
        exit_info = exits[direction]
        if isinstance(exit_info, str):
            new_room_id = exit_info
        else:
            new_room_id = exit_info["destination"]

        # Move to new room
        self.current_room_id = new_room_id

        # Emit room enter event
        self.event_bus.emit(Event(
            type=EventType.ROOM_ENTER,
            data={
                "room_id": new_room_id,
                "room_name": self.get_current_room()["name"]
            }
        ))

        # Check for passive perception features on room entry
        self._check_passive_perception()

        # Check for enemies and start combat if needed (unless explicitly disabled)
        if check_for_enemies:
            self._check_for_enemies()

        return True

    def get_exit_info(self, direction: str) -> Optional[Dict[str, Any]]:
        """
        Get exit information for a direction.

        Args:
            direction: Direction to check

        Returns:
            Exit info dict or None if exit doesn't exist
        """
        current_room = self.get_current_room()
        exits = current_room.get("exits", {})

        if direction not in exits:
            return None

        exit_data = exits[direction]

        # Handle backwards compatibility (string exits)
        if isinstance(exit_data, str):
            return {
                "destination": exit_data,
                "locked": False,
                "unlock_methods": []
            }

        # Return dict exit as-is
        return exit_data

    def is_exit_locked(self, direction: str) -> bool:
        """
        Check if an exit is locked.

        Args:
            direction: Direction to check

        Returns:
            True if exit is locked, False otherwise
        """
        exit_info = self.get_exit_info(direction)
        if not exit_info:
            return False

        return exit_info.get("locked", False)

    def get_unlock_methods(self, direction: str) -> List[Dict[str, Any]]:
        """
        Get available unlock methods for a locked exit.

        Args:
            direction: Direction to check

        Returns:
            List of unlock method dicts, empty list if not locked or no methods
        """
        exit_info = self.get_exit_info(direction)
        if not exit_info:
            return []

        return exit_info.get("unlock_methods", [])

    def attempt_unlock(
        self,
        direction: str,
        method_index: int,
        character: Character
    ) -> Dict[str, Any]:
        """
        Attempt to unlock a door using a specific method.

        Args:
            direction: Direction of the locked door
            method_index: Index of the unlock method to use
            character: Character attempting the unlock

        Returns:
            Dict with unlock result:
            - success: bool - Whether unlock succeeded
            - method: dict - The unlock method used
            - skill_check_result: dict - Skill check details (if applicable)
            - reason: str - Failure reason (if failed)
        """
        # Validate exit exists and is locked
        exit_info = self.get_exit_info(direction)
        if not exit_info:
            return {
                "success": False,
                "reason": f"No exit in direction '{direction}'"
            }

        if not exit_info.get("locked", False):
            return {
                "success": False,
                "reason": "Door is not locked"
            }

        # Get unlock methods
        unlock_methods = exit_info.get("unlock_methods", [])
        if method_index < 0 or method_index >= len(unlock_methods):
            return {
                "success": False,
                "reason": "Invalid unlock method"
            }

        method = unlock_methods[method_index]

        # Handle item-based unlocking
        if "requires_item" in method:
            item_id = method["requires_item"]
            # Check if any party member has the item
            for char in self.party.characters:
                if char.inventory.has_item(item_id):
                    # Unlock the door
                    exit_info["locked"] = False
                    # Emit event
                    self.event_bus.emit(Event(
                        type=EventType.SKILL_CHECK,
                        data={
                            "character": character.name,
                            "action": f"unlock door with {item_id}",
                            "success": True,
                            "automatic": True
                        }
                    ))
                    return {
                        "success": True,
                        "method": method,
                        "automatic": True
                    }

            return {
                "success": False,
                "method": method,
                "reason": f"Party does not have {item_id}"
            }

        # Handle skill-based unlocking
        if "skill" in method:
            skill = method["skill"]
            dc = method["dc"]

            # Check tool proficiency requirement
            tool_proficiency = method.get("tool_proficiency")
            if tool_proficiency:
                # Load proficiencies data to check if character has the tool
                if not hasattr(character, 'tool_proficiencies') or tool_proficiency not in character.tool_proficiencies:
                    # Character lacks required tool proficiency - they can still attempt but without proficiency bonus
                    pass

            # Load skills data
            skills_data = self.data_loader.load_skills()

            # Make skill check
            check_result = character.make_skill_check(skill, dc, skills_data)

            # Emit skill check event
            self.event_bus.emit(Event(
                type=EventType.SKILL_CHECK,
                data={
                    "character": character.name,
                    "skill": skill,
                    "dc": dc,
                    "roll": check_result["roll"],
                    "modifier": check_result["modifier"],
                    "total": check_result["total"],
                    "success": check_result["success"],
                    "action": method["description"]
                }
            ))

            if check_result["success"]:
                # Unlock the door
                exit_info["locked"] = False

            return {
                "success": check_result["success"],
                "method": method,
                "skill_check_result": check_result
            }

        return {
            "success": False,
            "reason": "Invalid unlock method configuration"
        }

    def get_examinable_objects(self) -> List[Dict[str, Any]]:
        """
        Get list of examinable objects in the current room.

        Returns:
            List of examinable object dicts with id, name, description
        """
        room = self.get_current_room()
        return room.get("examinable_objects", [])

    def get_examinable_exits(self) -> List[str]:
        """
        Get list of exits that can be examined in the current room.

        Returns:
            List of direction names that have examine_checks or are locked
        """
        room = self.get_current_room()
        exits = room.get("exits", {})
        examinable = []

        for direction, exit_data in exits.items():
            # Include exits with examine_checks or locked doors
            if isinstance(exit_data, dict):
                has_examine_checks = exit_data.get("examine_checks")
                is_locked = exit_data.get("locked", False)
                if has_examine_checks or is_locked:
                    examinable.append(direction)

        return examinable

    def examine_exit(
        self,
        direction: str,
        character: Character
    ) -> Dict[str, Any]:
        """
        Examine an exit (e.g., listen at a door) with a skill check.

        Args:
            direction: Direction of the exit to examine
            character: Character attempting the examination

        Returns:
            Dict with examination result:
            - success: bool - Whether any check succeeded
            - direction: str - Direction examined
            - results: List[Dict] - Results from each examine check
        """
        # Get exit info
        exit_info = self.get_exit_info(direction)
        if not exit_info:
            return {
                "success": False,
                "error": f"No exit in direction '{direction}'"
            }

        # Check if exit has examine_checks
        examine_checks = exit_info.get("examine_checks", [])

        # If no examine_checks but door is locked, provide locked door info
        if not examine_checks:
            is_locked = exit_info.get("locked", False)
            if is_locked:
                unlock_methods = exit_info.get("unlock_methods", [])
                return {
                    "success": True,
                    "direction": direction,
                    "is_locked": True,
                    "unlock_methods": unlock_methods,
                    "description": f"The door to the {direction} is locked. You notice a sturdy lock mechanism."
                }
            else:
                return {
                    "success": False,
                    "error": f"Exit '{direction}' cannot be examined"
                }

        # Load skills data
        skills_data = self.data_loader.load_skills()

        # Perform all examine checks for this exit
        results = []
        any_success = False

        for check in examine_checks:
            skill = check["skill"]
            dc = check["dc"]
            action = check.get("action", f"examine {direction} exit")

            # Make skill check
            check_result = character.make_skill_check(skill, dc, skills_data)

            # Emit skill check event
            self.event_bus.emit(Event(
                type=EventType.SKILL_CHECK,
                data={
                    "character": character.name,
                    "skill": skill,
                    "dc": dc,
                    "roll": check_result["roll"],
                    "modifier": check_result["modifier"],
                    "total": check_result["total"],
                    "success": check_result["success"],
                    "action": action,
                    "success_text": check.get("on_success") if check_result["success"] else None,
                    "failure_text": check.get("on_failure") if not check_result["success"] else None
                }
            ))

            results.append({
                "skill": skill,
                "dc": dc,
                "action": action,
                "check_result": check_result,
                "success_text": check.get("on_success") if check_result["success"] else None,
                "failure_text": check.get("on_failure") if not check_result["success"] else None
            })

            if check_result["success"]:
                any_success = True

        return {
            "success": any_success,
            "direction": direction,
            "results": results
        }

    def examine_object(
        self,
        object_id: str,
        character: Character
    ) -> Dict[str, Any]:
        """
        Examine an object in the current room with a skill check.

        Args:
            object_id: ID of the object to examine
            character: Character attempting the examination

        Returns:
            Dict with examination result:
            - success: bool - Whether any check succeeded
            - object_name: str - Name of the examined object
            - results: List[Dict] - Results from each examine check
            - already_checked: bool - Whether this object was already examined
        """
        room = self.get_current_room()

        # Initialize checked_objects set if not present
        if "checked_objects" not in room:
            room["checked_objects"] = set()

        # Find the object
        examinable_objects = room.get("examinable_objects", [])
        obj = None
        for o in examinable_objects:
            if o["id"] == object_id:
                obj = o
                break

        if not obj:
            return {
                "success": False,
                "error": f"Object '{object_id}' not found in room"
            }

        object_name = obj.get("name", object_id)

        # Check if already examined
        if object_id in room["checked_objects"]:
            return {
                "success": False,
                "object_name": object_name,
                "already_checked": True,
                "results": []
            }

        # Mark as examined
        room["checked_objects"].add(object_id)

        # Load skills data
        skills_data = self.data_loader.load_skills()

        # Perform all examine checks for this object
        results = []
        any_success = False

        for check in obj.get("examine_checks", []):
            skill = check["skill"]
            dc = check["dc"]

            # Make skill check
            check_result = character.make_skill_check(skill, dc, skills_data)

            # Emit skill check event
            self.event_bus.emit(Event(
                type=EventType.SKILL_CHECK,
                data={
                    "character": character.name,
                    "skill": skill,
                    "dc": dc,
                    "roll": check_result["roll"],
                    "modifier": check_result["modifier"],
                    "total": check_result["total"],
                    "success": check_result["success"],
                    "action": f"examine {object_name}",
                    "success_text": check.get("on_success") if check_result["success"] else None,
                    "failure_text": check.get("on_failure") if not check_result["success"] else None
                }
            ))

            results.append({
                "skill": skill,
                "dc": dc,
                "check_result": check_result,
                "success_text": check.get("on_success") if check_result["success"] else None,
                "failure_text": check.get("on_failure") if not check_result["success"] else None
            })

            if check_result["success"]:
                any_success = True

        return {
            "success": any_success,
            "object_name": object_name,
            "already_checked": False,
            "results": results
        }

    def search_room(
        self,
        character: Optional[Character] = None
    ) -> Dict[str, Any]:
        """
        Search the current room for items, optionally with skill checks.

        If the room has search_checks defined, a skill check is required.
        Otherwise, searching automatically succeeds (backwards compatibility).

        Only reveals items without picking them up.
        Use take_item() to actually pick up items.

        Args:
            character: Character performing the search (required if room has search_checks)

        Returns:
            Dict with search result:
            - success: bool - Whether search succeeded
            - items: List[Dict] - Items found (if successful or already searched)
            - already_searched: bool - Whether room was already searched
            - check_result: Dict - Skill check result (if applicable)
        """
        room = self.get_current_room()

        # Not searchable rooms return failure
        if not room.get("searchable"):
            return {
                "success": False,
                "items": [],
                "error": "This room cannot be searched"
            }

        # Check if already searched
        already_searched = room.get("searched", False)

        # If already searched, return current items without requiring another check
        if already_searched:
            return {
                "success": True,
                "items": room.get("items", []),
                "already_searched": True
            }

        # Check if room has search_checks
        search_checks = room.get("search_checks", [])

        if search_checks:
            # Skill check required
            if character is None:
                return {
                    "success": False,
                    "items": [],
                    "error": "Character required for search with skill check"
                }

            # Load skills data
            skills_data = self.data_loader.load_skills()

            # Perform search check (use first check - typically Investigation or Perception)
            check = search_checks[0]
            skill = check["skill"]
            dc = check["dc"]

            # Make skill check
            check_result = character.make_skill_check(skill, dc, skills_data)

            # Mark room as searched regardless of result
            room["searched"] = True

            # Emit skill check event
            self.event_bus.emit(Event(
                type=EventType.SKILL_CHECK,
                data={
                    "character": character.name,
                    "skill": skill,
                    "dc": dc,
                    "roll": check_result["roll"],
                    "modifier": check_result["modifier"],
                    "total": check_result["total"],
                    "success": check_result["success"],
                    "action": "search room",
                    "success_text": check.get("on_success") if check_result["success"] else None,
                    "failure_text": check.get("on_failure") if not check_result["success"] else None
                }
            ))

            # Return items only if check succeeded
            if check_result["success"]:
                return {
                    "success": True,
                    "items": room.get("items", []),
                    "already_searched": False,
                    "check_result": check_result,
                    "success_text": check.get("on_success"),
                    "failure_text": None
                }
            else:
                return {
                    "success": False,
                    "items": [],
                    "already_searched": False,
                    "check_result": check_result,
                    "success_text": None,
                    "failure_text": check.get("on_failure")
                }
        else:
            # No skill check required - automatic success (backwards compatibility)
            room["searched"] = True
            return {
                "success": True,
                "items": room.get("items", []),
                "already_searched": False
            }

    def get_available_items_in_room(self) -> List[Dict[str, Any]]:
        """
        Get list of items available to pick up in the current room.

        Returns items if:
        - Room has been searched and has items, OR
        - Room is not searchable but has items (visible items)

        Returns:
            List of available items
        """
        room = self.get_current_room()
        items = room.get("items", [])

        # Items are available if room is searched or not searchable
        if room.get("searched") or not room.get("searchable"):
            return items
        return []

    def take_item(self, item_id: str, character: Character) -> bool:
        """
        Pick up an item from the current room and add it to a character's inventory.

        Args:
            item_id: ID of the item to pick up (or "gold" for currency)
            character: Character who should receive the item

        Returns:
            True if item was successfully taken, False otherwise
        """
        room = self.get_current_room()
        items = room.get("items", [])

        # Find the item in the room
        item_to_take = None
        for item in items:
            if item["type"] == "gold" and item_id.lower() == "gold":
                item_to_take = item
                break
            elif item["type"] == "currency" and item_id.lower() in ["gold", "silver", "copper", "currency"]:
                item_to_take = item
                break
            elif item["type"] == "item" and item.get("id") == item_id:
                item_to_take = item
                break

        if not item_to_take:
            return False  # Item not found in room

        # Handle different item types
        if item_to_take["type"] == "currency":
            # Handle currency with gold, silver, and copper
            from dnd_engine.systems.currency import Currency
            gold = item_to_take.get("gold", 0)
            silver = item_to_take.get("silver", 0)
            copper = item_to_take.get("copper", 0)

            currency = Currency(gold=gold, silver=silver, copper=copper)
            # Split total value evenly among all party members
            total_cp = currency.to_copper()
            split_cp = total_cp // len(self.party.characters)

            for char in self.party.characters:
                split_currency = Currency()
                split_currency._from_copper(split_cp)
                char.inventory.currency.add(split_currency)

            # Emit gold acquired event
            self.event_bus.emit(Event(
                type=EventType.GOLD_ACQUIRED,
                data={"amount": gold, "silver": silver, "copper": copper}
            ))

        elif item_to_take["type"] == "gold":
            amount = item_to_take["amount"]
            # Split gold evenly among all party members
            split_amount = amount // len(self.party.characters)
            for char in self.party.characters:
                char.inventory.add_gold(split_amount)

            # Emit gold acquired event
            self.event_bus.emit(Event(
                type=EventType.GOLD_ACQUIRED,
                data={"amount": amount}
            ))

        elif item_to_take["type"] == "item":
            category = self._get_item_category(item_id)
            if not category:
                return False  # Unknown item category

            # Add item to the specified character's inventory
            character.inventory.add_item(item_id, category)

            # Emit item acquired event
            self.event_bus.emit(Event(
                type=EventType.ITEM_ACQUIRED,
                data={"item_id": item_id, "category": category, "character": character.name}
            ))

        # Remove item from room
        items.remove(item_to_take)
        return True

    def prepare_spells(self, character_name: str, spell_ids: List[str]) -> bool:
        """
        Prepare spells for a character (orchestration for player action).

        This method coordinates spell preparation after a long rest. The Character
        class handles validation and state updates.

        Args:
            character_name: Name of character preparing spells
            spell_ids: List of spell IDs to prepare (cantrips will be auto-included by Character)

        Returns:
            True if preparation successful, False if validation failed or character not found
        """
        character = self.party.get_character_by_name(character_name)
        if not character:
            return False

        # Character validates and updates prepared spell list
        success = character.set_prepared_spells(spell_ids)

        if success:
            # Emit event for logging/tracking
            self.event_bus.emit(Event(
                type=EventType.SPELLS_PREPARED,
                data={
                    "character": character_name,
                    "spell_count": len(spell_ids)
                }
            ))

        return success

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

    def _check_passive_perception(self) -> None:
        """
        Check party members' passive Perception against hidden features on room entry.

        Passive Perception = 10 + Perception modifier

        Only triggers once per room per party. Results are emitted as events.
        """
        room = self.get_current_room()

        # Skip if no hidden features or already checked
        hidden_features = room.get("hidden_features", [])
        if not hidden_features:
            return

        # Initialize passive_checks_done flag if not present
        if "passive_checks_done" not in room:
            room["passive_checks_done"] = False

        # Only check once per room
        if room["passive_checks_done"]:
            return

        # Mark as checked
        room["passive_checks_done"] = True

        # Load skills data for Perception
        skills_data = self.data_loader.load_skills()

        # Check each hidden feature with trigger "on_enter"
        for feature in hidden_features:
            if feature.get("trigger") != "on_enter":
                continue

            if feature.get("type") != "passive_perception":
                continue

            dc = feature.get("dc", 10)

            # Check each party member's passive Perception
            for character in self.party.characters:
                # Calculate passive Perception: 10 + Perception modifier
                perception_mod = character.get_skill_modifier("perception", skills_data)
                passive_perception = 10 + perception_mod

                success = passive_perception >= dc

                # Emit event for this check
                self.event_bus.emit(Event(
                    type=EventType.SKILL_CHECK,
                    data={
                        "character": character.name,
                        "skill": "perception",
                        "dc": dc,
                        "modifier": perception_mod,
                        "total": passive_perception,
                        "success": success,
                        "passive": True,
                        "action": f"passive perception (DC {dc})",
                        "success_text": feature.get("on_success") if success else None,
                        "failure_text": feature.get("on_failure") if not success else None
                    }
                ))

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

                # Check for level-up (can level up multiple times if enough XP)
                while character.check_for_level_up(self.data_loader, self.event_bus):
                    pass  # Level-up event already emitted by check_for_level_up

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

    def flee_combat(self) -> Dict[str, Any]:
        """
        Attempt to flee from combat.

        Party flees together, but each living enemy gets one opportunity attack
        against random living party members. No XP is awarded. Party automatically
        retreats to the previous room (reverse of last_entry_direction).

        Returns:
            Dictionary with flee results including:
            - success: True if fled successfully, False if failed
            - reason: Failure reason (if failed)
            - opportunity_attacks: List of attack results
            - casualties: List of party members who died during flee
            - retreat_direction: Direction party fled (if successful)
            - retreat_room: Room name party fled to (if successful)
        """
        if not self.in_combat:
            return {"success": False, "reason": "Not in combat"}

        # Check if we can retreat (need previous direction)
        if not self.last_entry_direction:
            return {
                "success": False,
                "reason": "Nowhere to retreat! You're trapped in this room."
            }

        # Calculate retreat direction
        retreat_direction = REVERSE_DIRECTIONS.get(self.last_entry_direction)
        if not retreat_direction:
            return {
                "success": False,
                "reason": f"Cannot determine retreat direction from '{self.last_entry_direction}'"
            }

        # Track flee results
        opportunity_attacks = []
        casualties = []

        # Each living enemy gets one opportunity attack
        living_enemies = [e for e in self.active_enemies if e.is_alive]
        living_party = self.party.get_living_members()

        if living_party and living_enemies:
            # Load monster data for attack stats
            monsters = self.data_loader.load_monsters()

            for enemy in living_enemies:
                # Pick a random living party member to attack
                import random
                target = random.choice(living_party)

                # Find enemy's attack data
                monster_data = None
                for monster_id, mdata in monsters.items():
                    if mdata["name"] == enemy.name:
                        monster_data = mdata
                        break

                if monster_data and monster_data.get("actions"):
                    # Find first action with attack_bonus (skip Multiattack, etc.)
                    action = None
                    for act in monster_data["actions"]:
                        if "attack_bonus" in act:
                            action = act
                            break

                    if action:
                        result = self.combat_engine.resolve_attack(
                            attacker=enemy,
                            defender=target,
                            attack_bonus=action["attack_bonus"],
                            damage_dice=action["damage"],
                            apply_damage=True
                        )
                        opportunity_attacks.append(result)

                        # Emit damage event if hit
                        if result.hit:
                            self.event_bus.emit(Event(
                                type=EventType.DAMAGE_DEALT,
                                data={
                                    "attacker": enemy.name,
                                    "defender": target.name,
                                    "damage": result.damage,
                                    "opportunity_attack": True
                                }
                            ))

                        # Track casualties
                        if not target.is_alive:
                            casualties.append(target.name)
                            self.event_bus.emit(Event(
                                type=EventType.CHARACTER_DEATH,
                                data={"name": target.name}
                            ))

                # Update living party list if someone died
                living_party = self.party.get_living_members()
                if not living_party:
                    break  # No one left to attack

        # Clear combat state (no XP awarded for fleeing)
        self.in_combat = False
        self.initiative_tracker = None

        # Enemies remain in room (can encounter them again)
        # Do NOT clear enemies from room like in _end_combat

        # Retreat to previous room
        move_success = self.move(retreat_direction)

        if not move_success:
            # This shouldn't happen if direction tracking is correct, but handle gracefully
            return {
                "success": False,
                "reason": f"Failed to retreat {retreat_direction} - exit may not exist"
            }

        # Get new room info for return data
        new_room = self.get_current_room()
        retreat_room_name = new_room.get("name", "Unknown")

        # Emit flee event
        self.event_bus.emit(Event(
            type=EventType.COMBAT_FLED,
            data={
                "opportunity_attacks": len(opportunity_attacks),
                "casualties": casualties,
                "surviving_party": [c.name for c in self.party.get_living_members()],
                "retreat_direction": retreat_direction,
                "retreat_room": retreat_room_name
            }
        ))

        return {
            "success": True,
            "opportunity_attacks": opportunity_attacks,
            "casualties": casualties,
            "retreat_direction": retreat_direction,
            "retreat_room": retreat_room_name
        }

    def reset_dungeon(self, new_dungeon_name: Optional[str] = None) -> None:
        """
        Reset the dungeon to its initial state.

        Keeps party data intact while resetting:
        - Current room to dungeon entrance
        - All room states (searched flags, enemies)
        - Combat state
        - Action history

        Args:
            new_dungeon_name: If provided, switch to a different dungeon
        """
        # Emit reset started event
        self.event_bus.emit(Event(
            type=EventType.RESET_STARTED,
            data={
                "old_dungeon": self.dungeon_name,
                "new_dungeon": new_dungeon_name or self.dungeon_name
            }
        ))

        # Load new dungeon if specified, otherwise reload current one
        if new_dungeon_name:
            self.dungeon_name = new_dungeon_name
            self.dungeon = self.data_loader.load_dungeon(new_dungeon_name)
        else:
            # Reload current dungeon from disk to reset state
            self.dungeon = self.data_loader.load_dungeon(self.dungeon_name)

        # Reset to start room
        self.current_room_id = self.dungeon["start_room"]

        # Reset combat state
        self.in_combat = False
        self.initiative_tracker = None
        self.active_enemies = []

        # Reset navigation tracking
        self.last_entry_direction = None

        # Clear action history
        self.action_history = []

        # Emit reset complete event
        self.event_bus.emit(Event(
            type=EventType.RESET_COMPLETE,
            data={
                "dungeon": self.dungeon_name,
                "current_room": self.current_room_id
            }
        ))

    def reset_party_hp(self) -> None:
        """
        Restore all party members to full health.

        Heals all living and dead characters to their maximum HP.
        """
        for character in self.party.characters:
            character.current_hp = character.max_hp

    def reset_party_conditions(self) -> None:
        """
        Clear all conditions from all party members.

        Removes conditions like poisoned, paralyzed, stunned, etc.
        """
        for character in self.party.characters:
            character.conditions.clear()

    def use_combat_attack_item(
        self,
        user: Character,
        item_id: str,
        target: Creature
    ) -> CombatItemResult:
        """
        Use a combat attack item (thrown weapon) on a target during combat.

        Handles the complete flow of using attack items like Alchemist's Fire, Acid Vials:
        1. Validates action economy
        2. Consumes item from inventory
        3. Makes ranged attack roll (DEX-based)
        4. Applies damage on hit
        5. Applies special effects (e.g., ongoing fire damage)
        6. Emits appropriate events

        Args:
            user: Character using the item
            item_id: ID of the item to use
            target: Target creature for the attack

        Returns:
            CombatItemResult with attack outcome and display information
        """
        # Load item data (structure: {"weapons": {...}, "armor": {...}, "consumables": {...}})
        items_data = self.data_loader.load_items()

        # Find item in categories
        item_data = None
        for category, category_items in items_data.items():
            if item_id in category_items:
                item_data = category_items[item_id]
                break

        if item_data is None:
            return CombatItemResult(
                success=False,
                attack_result=None,
                item_name=item_id,
                action_type=ActionType.ACTION,
                error_message=f"Item '{item_id}' not found"
            )

        item_name = item_data.get("name", item_id)

        # Parse action required
        action_required_str = item_data.get("action_required", "action")
        action_type_map = {
            "action": ActionType.ACTION,
            "bonus_action": ActionType.BONUS_ACTION,
            "free_object": ActionType.FREE_OBJECT,
            "no_action": ActionType.NO_ACTION
        }
        action_required = action_type_map.get(action_required_str, ActionType.ACTION)

        # Validate action economy
        turn_state = self.initiative_tracker.get_current_turn_state() if self.initiative_tracker else None
        if not turn_state:
            return CombatItemResult(
                success=False,
                attack_result=None,
                item_name=item_name,
                action_type=action_required,
                error_message="Unable to get current turn state"
            )

        if not turn_state.is_action_available(action_required):
            action_name = action_required_str.replace("_", " ").title()
            return CombatItemResult(
                success=False,
                attack_result=None,
                item_name=item_name,
                action_type=action_required,
                error_message=f"No {action_name} available this turn"
            )

        # Consume the action
        if not turn_state.consume_action(action_required):
            return CombatItemResult(
                success=False,
                attack_result=None,
                item_name=item_name,
                action_type=action_required,
                error_message=f"Failed to consume {action_required_str}"
            )

        # Use the item from inventory (removes it)
        inventory = user.inventory
        success, used_item_data = inventory.use_item(item_id, items_data)

        if not success:
            # Restore the action since item use failed
            turn_state.reset()
            turn_state.consume_action(action_required)
            return CombatItemResult(
                success=False,
                attack_result=None,
                item_name=item_name,
                action_type=action_required,
                error_message=f"Failed to use {item_name} from inventory"
            )

        # Calculate attack bonus (DEX-based improvised ranged weapon)
        attack_bonus = user.abilities.dex_mod
        if hasattr(user, 'proficiency_bonus'):
            attack_bonus += user.proficiency_bonus

        # Get damage from item
        damage_dice = used_item_data.get("damage", "1d4")
        damage_type = used_item_data.get("damage_type", "damage")

        # Resolve the attack
        attack_result = self.combat_engine.resolve_attack(
            attacker=user,
            defender=target,
            attack_bonus=attack_bonus,
            damage_dice=damage_dice,
            apply_damage=True,
            event_bus=self.event_bus
        )

        # Apply special effects on hit
        special_effects = []
        if attack_result.hit:
            # Alchemist's Fire: ongoing fire damage
            if "alchemist" in item_id.lower() or "alchemist" in item_name.lower():
                target.add_condition("on_fire")
                special_effects.append("on_fire")

        # Emit item used event
        self.event_bus.emit(Event(
            type=EventType.ITEM_USED,
            data={
                "character": user.name,
                "target": target.name,
                "item_id": item_id,
                "item_name": item_name,
                "effect_type": "attack",
                "action_cost": action_required_str,
                "success": attack_result.hit,
                "damage": attack_result.damage if attack_result.hit else 0
            }
        ))

        return CombatItemResult(
            success=True,
            attack_result=attack_result,
            item_name=item_name,
            action_type=action_required,
            special_effects=special_effects
        )
