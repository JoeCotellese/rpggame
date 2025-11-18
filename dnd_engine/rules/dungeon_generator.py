# ABOUTME: This module generates random dungeons for D&D 5E adventures.
# ABOUTME: It creates room layouts, populates them with monsters and loot based on difficulty level.

import random
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime


class DungeonGenerator:
    """Generates random dungeons with rooms, monsters, and loot."""

    # Dungeon themes with associated monsters and room name templates
    THEMES = {
        "goblinoid": {
            "name": "Goblinoid Lair",
            "monsters": ["goblin"],
            "boss_monsters": ["goblin_boss"],
            "room_templates": [
                "Guard Post", "Sleeping Quarters", "Main Hall", "Storage Room",
                "Crude Kitchen", "Weapon Cache", "Trophy Room", "Chieftain's Chamber",
                "Prison Cell", "Scout Outpost"
            ],
            "description_templates": [
                "Crude drawings cover the {wall_feature}. The smell of unwashed goblinoids is overwhelming.",
                "Makeshift furniture and stolen goods are scattered about. {light_source} provides dim illumination.",
                "The {floor_feature} is littered with bones and debris. Goblin tracks are everywhere.",
                "Rough wooden supports hold up the {ceiling_feature}. You hear skittering sounds in the shadows.",
                "{wall_feature} show signs of crude carving. The air is thick with smoke and grease."
            ]
        },
        "bandit": {
            "name": "Bandit Hideout",
            "monsters": ["bandit"],
            "boss_monsters": ["bandit"],  # For now, use bandit as boss
            "room_templates": [
                "Guard Station", "Sleeping Area", "Common Room", "Supply Cache",
                "Mess Hall", "Armory", "Treasure Vault", "Captain's Quarters",
                "Holding Cell", "Lookout Post"
            ],
            "description_templates": [
                "Crude bedrolls and personal effects suggest bandits rest here. {light_source} flickers nearby.",
                "The {floor_feature} shows signs of heavy traffic. Stolen goods are piled in corners.",
                "Well-worn paths cross the {floor_feature}. {wall_feature} bear scratched tallies and crude maps.",
                "The {ceiling_feature} is low and oppressive. You hear muffled voices from nearby.",
                "Weapon racks line {wall_feature}. The smell of cheap ale and smoke fills the air."
            ]
        },
        "beast": {
            "name": "Beast Den",
            "monsters": ["wolf"],
            "boss_monsters": ["wolf", "wolf"],  # Multiple wolves for boss room
            "room_templates": [
                "Den Entrance", "Hunting Grounds", "Main Lair", "Food Cache",
                "Sleeping Hollow", "Bone Pit", "Alpha's Territory", "Feeding Area",
                "Deep Cave", "Hidden Grotto"
            ],
            "description_templates": [
                "The {floor_feature} is covered in fur and claw marks. {light_source} barely penetrates the gloom.",
                "Bones and remains are scattered across the {floor_feature}. The stench of predators is strong.",
                "Fresh kills hang from {wall_feature}. The sound of growling echoes through the chamber.",
                "The {ceiling_feature} drips with moisture. Territorial markings cover every surface.",
                "Animal tracks crisscross the {floor_feature}. You sense you're being watched."
            ]
        }
    }

    # Room feature variations
    WALL_FEATURES = ["stone walls", "earthen walls", "rough-hewn walls", "damp walls", "ancient walls"]
    FLOOR_FEATURES = ["dirt floor", "stone floor", "uneven ground", "rocky floor", "packed earth"]
    CEILING_FEATURES = ["low ceiling", "arched ceiling", "rough stone ceiling", "dripping ceiling", "shadowed ceiling"]
    LIGHT_SOURCES = ["torches", "a guttering candle", "dim phosphorescence", "scattered coals", "a single lantern"]

    def __init__(self, data_loader):
        """
        Initialize the dungeon generator.

        Args:
            data_loader: DataLoader instance for accessing monsters and items
        """
        self.data_loader = data_loader
        self.monsters = data_loader.load_monsters()
        self.items = data_loader.load_items()

    def generate(self, level: int = 1, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Generate a random dungeon appropriate for the given character level.

        Args:
            level: Character level for difficulty scaling (default: 1)
            output_path: Optional path to save the dungeon JSON

        Returns:
            Dictionary containing the complete dungeon data
        """
        # Select random theme
        theme_key = random.choice(list(self.THEMES.keys()))
        theme = self.THEMES[theme_key]

        # Generate random number of rooms (5-10)
        num_rooms = random.randint(5, 10)

        # Generate room graph
        rooms = self._generate_room_graph(num_rooms, theme)

        # Populate rooms with enemies and items
        self._populate_rooms(rooms, theme, level)

        # Create dungeon data structure
        dungeon_name = f"{theme['name']} - {datetime.now().strftime('%Y%m%d_%H%M%S')}"
        dungeon = {
            "name": dungeon_name,
            "description": self._generate_dungeon_description(theme),
            "start_room": "room_0",
            "rooms": rooms
        }

        # Save to file if path provided
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(dungeon, f, indent=2)

        return dungeon

    def _generate_room_graph(self, num_rooms: int, theme: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Generate a connected graph of rooms.

        Creates a dungeon layout with:
        - Linear main path with some branches
        - Dead ends with treasure
        - All rooms reachable from start

        Args:
            num_rooms: Number of rooms to generate
            theme: Theme dictionary containing room templates

        Returns:
            Dictionary of room_id -> room_data
        """
        rooms = {}
        room_names = theme["room_templates"].copy()
        random.shuffle(room_names)

        # Ensure we have enough room names
        while len(room_names) < num_rooms:
            room_names.extend(theme["room_templates"])

        # Create rooms
        for i in range(num_rooms):
            room_id = f"room_{i}"
            rooms[room_id] = {
                "name": room_names[i],
                "description": self._generate_room_description(theme),
                "exits": {},
                "enemies": [],
                "items": [],
                "searched": False
            }

        # Connect rooms in a path with branches
        # Start with linear path through most rooms
        main_path_length = max(3, num_rooms - 2)  # Leave some rooms for branches

        for i in range(main_path_length - 1):
            # Connect forward
            rooms[f"room_{i}"]["exits"]["north"] = f"room_{i+1}"
            rooms[f"room_{i+1}"]["exits"]["south"] = f"room_{i}"

        # Add side branches for remaining rooms
        remaining_rooms = list(range(main_path_length, num_rooms))
        random.shuffle(remaining_rooms)

        for room_idx in remaining_rooms:
            # Pick a random room on main path to branch from
            branch_point = random.randint(1, main_path_length - 2)

            # Use east/west for branches
            direction = random.choice(["east", "west"])
            opposite = "west" if direction == "east" else "east"

            # If this direction is already taken, try the other
            if direction in rooms[f"room_{branch_point}"]["exits"]:
                direction, opposite = opposite, direction

            # Only connect if the direction is free
            if direction not in rooms[f"room_{branch_point}"]["exits"]:
                rooms[f"room_{branch_point}"]["exits"][direction] = f"room_{room_idx}"
                rooms[f"room_{room_idx}"]["exits"][opposite] = f"room_{branch_point}"

        return rooms

    def _populate_rooms(self, rooms: Dict[str, Dict[str, Any]], theme: Dict[str, Any], level: int) -> None:
        """
        Populate rooms with enemies and items.

        Args:
            rooms: Dictionary of room data to populate
            theme: Theme dictionary with monster types
            level: Character level for difficulty scaling
        """
        room_ids = list(rooms.keys())
        num_rooms = len(room_ids)

        # Determine boss room (last room in main path or dead end)
        boss_room_id = self._find_boss_room(rooms)

        # Determine safe room (early side branch or dead end)
        safe_room_id = self._find_safe_room(rooms, boss_room_id)

        # Get appropriate monsters for this level
        available_monsters = self._get_monsters_for_level(theme["monsters"], level)
        boss_monsters = theme["boss_monsters"]

        for room_id, room in rooms.items():
            if room_id == "room_0":
                # Start room: no enemies, minimal loot
                continue
            elif room_id == boss_room_id:
                # Boss room: boss enemy, best loot
                room["enemies"] = boss_monsters.copy()
                room["items"] = self._generate_loot(level, is_boss=True)
            elif room_id == safe_room_id:
                # Safe room: no enemies, medium loot, can rest
                room["items"] = self._generate_loot(level, is_treasure=True)
                room["searchable"] = True
                room["safe_rest"] = True
            else:
                # Normal room: 30% empty, 40% single enemy, 30% multiple enemies
                roll = random.random()
                if roll < 0.3:
                    # Empty room
                    if random.random() < 0.5:
                        # Half of empty rooms have searchable loot
                        room["items"] = self._generate_loot(level, is_minor=True)
                        room["searchable"] = True
                elif roll < 0.7:
                    # Single enemy
                    room["enemies"] = [random.choice(available_monsters)]
                    room["items"] = self._generate_loot(level, is_minor=True)
                else:
                    # Multiple enemies (2-3)
                    num_enemies = random.randint(2, 3)
                    room["enemies"] = [random.choice(available_monsters) for _ in range(num_enemies)]
                    room["items"] = self._generate_loot(level)

    def _find_boss_room(self, rooms: Dict[str, Dict[str, Any]]) -> str:
        """Find the best room for the boss (furthest from start or dead end)."""
        # Prefer dead ends (rooms with only one exit) or rooms far from start
        dead_ends = [room_id for room_id, room in rooms.items()
                     if len(room["exits"]) == 1 and room_id != "room_0"]

        if dead_ends:
            return random.choice(dead_ends)

        # Otherwise, use the last room in the main path
        max_room_id = max(rooms.keys(), key=lambda x: int(x.split('_')[1]))
        return max_room_id

    def _find_safe_room(self, rooms: Dict[str, Dict[str, Any]], boss_room_id: str) -> str:
        """Find a good room for safe rest (not start, not boss, preferably dead end)."""
        candidates = [room_id for room_id, room in rooms.items()
                     if room_id not in ["room_0", boss_room_id] and len(room["exits"]) == 1]

        if candidates:
            return random.choice(candidates)

        # Otherwise, pick a random side room
        candidates = [room_id for room_id in rooms.keys()
                     if room_id not in ["room_0", boss_room_id]]
        return random.choice(candidates) if candidates else "room_1"

    def _get_monsters_for_level(self, theme_monsters: List[str], level: int) -> List[str]:
        """
        Get monsters appropriate for the character level.

        For level 1, use CR 0 to CR 1 monsters.

        Args:
            theme_monsters: List of monster IDs from theme
            level: Character level

        Returns:
            List of monster IDs appropriate for the level
        """
        # For level 1, we want CR 0 - 1
        max_cr = min(level, 1)  # For now, cap at CR 1

        appropriate_monsters = []
        for monster_id in theme_monsters:
            if monster_id in self.monsters:
                monster_cr = self.monsters[monster_id].get("cr", "0")
                # Convert CR to float (handle fractions like "1/4")
                if isinstance(monster_cr, str) and "/" in monster_cr:
                    cr_value = eval(monster_cr)  # "1/4" -> 0.25
                else:
                    cr_value = float(monster_cr)

                if cr_value <= max_cr:
                    appropriate_monsters.append(monster_id)

        return appropriate_monsters if appropriate_monsters else theme_monsters

    def _generate_loot(self, level: int, is_boss: bool = False,
                      is_treasure: bool = False, is_minor: bool = False) -> List[Dict[str, Any]]:
        """
        Generate loot appropriate for the level and room type.

        Args:
            level: Character level
            is_boss: Whether this is a boss room (better loot)
            is_treasure: Whether this is a treasure room (medium loot, no combat)
            is_minor: Whether this is minor loot (small amounts)

        Returns:
            List of item dictionaries
        """
        items = []

        if is_boss:
            # Boss room: guaranteed good gold + chance for items
            items.append({
                "type": "currency",
                "gold": random.randint(10, 25),
                "silver": random.randint(10, 30),
                "copper": random.randint(50, 100)
            })
            # 80% chance for healing potion
            if random.random() < 0.8:
                items.append({"type": "item", "id": "potion_of_healing"})
            # 50% chance for a weapon or armor
            if random.random() < 0.5:
                item_id = random.choice(["shortsword", "longsword", "dagger", "chain_shirt", "leather_armor"])
                items.append({"type": "item", "id": item_id})

        elif is_treasure:
            # Treasure room: decent loot
            items.append({
                "type": "currency",
                "gold": random.randint(5, 15),
                "silver": random.randint(10, 20),
                "copper": random.randint(20, 50)
            })
            # 60% chance for healing potion
            if random.random() < 0.6:
                items.append({"type": "item", "id": "potion_of_healing"})
            # 30% chance for equipment
            if random.random() < 0.3:
                item_id = random.choice(["dagger", "shortsword", "leather_armor"])
                items.append({"type": "item", "id": item_id})

        elif is_minor:
            # Minor loot: just currency or small item
            if random.random() < 0.7:
                items.append({
                    "type": "currency",
                    "gold": random.randint(0, 3),
                    "silver": random.randint(2, 8),
                    "copper": random.randint(5, 20)
                })
            else:
                items.append({"type": "item", "id": "potion_of_healing"})

        else:
            # Normal loot: moderate currency
            items.append({
                "type": "currency",
                "gold": random.randint(1, 8),
                "silver": random.randint(3, 12),
                "copper": random.randint(10, 40)
            })
            # 40% chance for healing potion
            if random.random() < 0.4:
                items.append({"type": "item", "id": "potion_of_healing"})

        return items

    def _generate_dungeon_description(self, theme: Dict[str, Any]) -> str:
        """Generate a description for the entire dungeon."""
        descriptions = {
            "goblinoid": "A warren of caves and tunnels inhabited by goblinoids. The air reeks of filth and violence.",
            "bandit": "A hidden stronghold used by bandits to store their ill-gotten gains and plan their raids.",
            "beast": "A natural cave system that has become the hunting grounds and den of dangerous predators."
        }

        for key, theme_data in self.THEMES.items():
            if theme_data == theme:
                return descriptions.get(key, "A dangerous dungeon filled with threats.")

        return "A dangerous dungeon filled with threats."

    def _generate_room_description(self, theme: Dict[str, Any]) -> str:
        """Generate a random description for a room based on theme."""
        template = random.choice(theme["description_templates"])

        # Fill in the template with random features
        description = template.format(
            wall_feature=random.choice(self.WALL_FEATURES),
            floor_feature=random.choice(self.FLOOR_FEATURES),
            ceiling_feature=random.choice(self.CEILING_FEATURES),
            light_source=random.choice(self.LIGHT_SOURCES)
        )

        return description
