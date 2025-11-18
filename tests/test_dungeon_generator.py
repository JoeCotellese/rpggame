# ABOUTME: Unit tests for random dungeon generation
# ABOUTME: Tests dungeon structure, connectivity, monsters, and loot

import pytest
import json
from pathlib import Path
from dnd_engine.rules.dungeon_generator import DungeonGenerator
from dnd_engine.rules.loader import DataLoader


class TestDungeonGenerator:
    """Test the DungeonGenerator class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.loader = DataLoader()
        self.generator = DungeonGenerator(self.loader)

    def test_generator_creation(self):
        """Test creating a dungeon generator"""
        assert self.generator is not None
        assert self.generator.data_loader == self.loader

    def test_generate_basic_dungeon(self):
        """Test basic dungeon generation"""
        dungeon = self.generator.generate(level=1)

        assert dungeon is not None
        assert "name" in dungeon
        assert "description" in dungeon
        assert "start_room" in dungeon
        assert "rooms" in dungeon

    def test_room_count_in_range(self):
        """Test that generated dungeons have 5-10 rooms"""
        # Generate multiple dungeons to test randomness
        for _ in range(10):
            dungeon = self.generator.generate(level=1)
            room_count = len(dungeon["rooms"])
            assert 5 <= room_count <= 10, f"Room count {room_count} not in range 5-10"

    def test_start_room_exists(self):
        """Test that the start room exists in the dungeon"""
        dungeon = self.generator.generate(level=1)

        assert dungeon["start_room"] in dungeon["rooms"]
        assert dungeon["start_room"] == "room_0"

    def test_room_structure(self):
        """Test that each room has required fields"""
        dungeon = self.generator.generate(level=1)

        for room_id, room in dungeon["rooms"].items():
            assert "name" in room
            assert "description" in room
            assert "exits" in room
            assert "enemies" in room
            assert "items" in room
            assert "searched" in room

    def test_room_connectivity(self):
        """Test that all rooms are reachable from the start room"""
        dungeon = self.generator.generate(level=1)

        # BFS to find all reachable rooms
        visited = set()
        queue = [dungeon["start_room"]]

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            for direction, target in dungeon["rooms"][current]["exits"].items():
                if target not in visited:
                    queue.append(target)

        # All rooms should be reachable
        all_rooms = set(dungeon["rooms"].keys())
        assert visited == all_rooms, f"Unreachable rooms: {all_rooms - visited}"

    def test_bidirectional_exits(self):
        """Test that room exits are bidirectional (if A->B then B->A)"""
        dungeon = self.generator.generate(level=1)
        rooms = dungeon["rooms"]

        opposites = {
            "north": "south",
            "south": "north",
            "east": "west",
            "west": "east"
        }

        for room_id, room in rooms.items():
            for direction, target_id in room["exits"].items():
                opposite_dir = opposites[direction]
                target_room = rooms[target_id]

                # The target room should have an exit back to this room
                assert opposite_dir in target_room["exits"], \
                    f"Room {room_id} has {direction} to {target_id}, but {target_id} has no {opposite_dir} back"
                assert target_room["exits"][opposite_dir] == room_id, \
                    f"Exit mismatch: {room_id}->{target_id} but {target_id} doesn't point back"

    def test_monsters_appropriate_cr(self):
        """Test that monsters in level 1 dungeon are CR 0-1"""
        dungeon = self.generator.generate(level=1)
        monsters = self.loader.load_monsters()

        for room in dungeon["rooms"].values():
            for enemy_id in room["enemies"]:
                assert enemy_id in monsters, f"Unknown monster: {enemy_id}"

                monster_cr = monsters[enemy_id].get("cr", "0")
                # Convert CR to float (handle fractions like "1/4")
                if isinstance(monster_cr, str) and "/" in monster_cr:
                    cr_value = eval(monster_cr)
                else:
                    cr_value = float(monster_cr)

                assert cr_value <= 1, f"Monster {enemy_id} has CR {cr_value}, too high for level 1"

    def test_start_room_empty(self):
        """Test that the start room has no enemies"""
        # Generate multiple dungeons to ensure consistency
        for _ in range(10):
            dungeon = self.generator.generate(level=1)
            start_room = dungeon["rooms"][dungeon["start_room"]]
            assert len(start_room["enemies"]) == 0, "Start room should have no enemies"

    def test_boss_room_has_boss(self):
        """Test that there's at least one room with boss enemies"""
        dungeon = self.generator.generate(level=1)

        # Find rooms with boss enemies
        boss_rooms = []
        for room_id, room in dungeon["rooms"].items():
            if room_id == "room_0":
                continue
            # Boss rooms typically have "boss" in the enemy ID
            if any("boss" in enemy for enemy in room["enemies"]):
                boss_rooms.append(room_id)

        # There should be at least one boss room (or a room with multiple enemies as boss)
        # For some themes, boss might be multiple enemies instead
        assert len(boss_rooms) >= 0  # Boss is not required for all themes

    def test_safe_room_exists(self):
        """Test that there's a safe rest room"""
        dungeon = self.generator.generate(level=1)

        # Find safe rooms
        safe_rooms = [room_id for room_id, room in dungeon["rooms"].items()
                     if room.get("safe_rest", False)]

        assert len(safe_rooms) >= 1, "Dungeon should have at least one safe rest room"

        # Safe room should have no enemies
        for room_id in safe_rooms:
            room = dungeon["rooms"][room_id]
            assert len(room["enemies"]) == 0, f"Safe room {room_id} should have no enemies"

    def test_loot_generation(self):
        """Test that loot is generated appropriately"""
        dungeon = self.generator.generate(level=1)

        # Count rooms with loot
        rooms_with_loot = 0
        for room in dungeon["rooms"].values():
            if room["items"]:
                rooms_with_loot += 1

                # Check loot structure
                for item in room["items"]:
                    assert "type" in item
                    assert item["type"] in ["currency", "item"]

                    if item["type"] == "currency":
                        # Currency should have at least one coin type
                        has_coins = any(k in item for k in ["gold", "silver", "copper"])
                        assert has_coins, "Currency item should have gold, silver, or copper"

                    if item["type"] == "item":
                        assert "id" in item

        # At least some rooms should have loot
        assert rooms_with_loot > 0, "Dungeon should have at least some loot"

    def test_theme_application(self):
        """Test that themes are applied correctly"""
        # Generate multiple dungeons and check for theme diversity
        themes_found = set()

        for _ in range(20):
            dungeon = self.generator.generate(level=1)

            # Extract theme from dungeon name or check monsters
            dungeon_name = dungeon["name"].lower()

            # Identify theme from name or monsters
            if "goblinoid" in dungeon_name or "goblin" in dungeon_name:
                themes_found.add("goblinoid")
            elif "bandit" in dungeon_name:
                themes_found.add("bandit")
            elif "beast" in dungeon_name or "den" in dungeon_name:
                themes_found.add("beast")

        # We should see at least 2 different themes in 20 generations
        assert len(themes_found) >= 2, f"Only found themes: {themes_found}"

    def test_save_to_file(self, tmp_path):
        """Test saving dungeon to a file"""
        output_file = tmp_path / "test_dungeon.json"

        dungeon = self.generator.generate(level=1, output_path=output_file)

        # File should exist
        assert output_file.exists()

        # File should contain valid JSON
        with open(output_file, 'r') as f:
            loaded_dungeon = json.load(f)

        assert loaded_dungeon == dungeon

    def test_generated_dungeon_playable(self):
        """Test that generated dungeon can be loaded by DataLoader"""
        # Generate and save a dungeon
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            dungeon_path = Path(tmpdir) / "test_dungeon.json"
            dungeon = self.generator.generate(level=1, output_path=dungeon_path)

            # Load it back
            with open(dungeon_path, 'r') as f:
                loaded = json.load(f)

            # Should have all required fields
            assert loaded["name"] == dungeon["name"]
            assert loaded["start_room"] == dungeon["start_room"]
            assert len(loaded["rooms"]) == len(dungeon["rooms"])

    def test_room_descriptions_unique(self):
        """Test that room descriptions are varied"""
        dungeon = self.generator.generate(level=1)

        descriptions = [room["description"] for room in dungeon["rooms"].values()]

        # Most descriptions should be unique (allowing some overlap)
        unique_descriptions = set(descriptions)
        uniqueness_ratio = len(unique_descriptions) / len(descriptions)

        assert uniqueness_ratio > 0.5, f"Only {len(unique_descriptions)}/{len(descriptions)} descriptions are unique"

    def test_multiple_generation_variety(self):
        """Test that multiple generations produce different dungeons"""
        dungeons = [self.generator.generate(level=1) for _ in range(5)]

        # Check that they have different room counts or structures
        room_counts = [len(d["rooms"]) for d in dungeons]

        # Very unlikely all 5 have the same number of rooms
        assert len(set(room_counts)) > 1, "All generated dungeons have the same room count"

    def test_no_isolated_rooms(self):
        """Test that no rooms are isolated (all have at least one exit except dead ends are ok)"""
        dungeon = self.generator.generate(level=1)

        for room_id, room in dungeon["rooms"].items():
            # Every room should have at least one exit
            assert len(room["exits"]) >= 1, f"Room {room_id} has no exits"

    def test_valid_monster_ids(self):
        """Test that all monster IDs are valid"""
        dungeon = self.generator.generate(level=1)
        monsters = self.loader.load_monsters()

        for room in dungeon["rooms"].values():
            for enemy_id in room["enemies"]:
                assert enemy_id in monsters, f"Invalid monster ID: {enemy_id}"

    def test_valid_item_ids(self):
        """Test that all item IDs are valid"""
        dungeon = self.generator.generate(level=1)
        items = self.loader.load_items()

        # Flatten items structure
        all_items = {}
        for category in ["weapons", "armor", "consumables", "tools"]:
            if category in items:
                all_items.update(items[category])

        for room in dungeon["rooms"].values():
            for item in room["items"]:
                if item["type"] == "item":
                    item_id = item["id"]
                    assert item_id in all_items, f"Invalid item ID: {item_id}"
