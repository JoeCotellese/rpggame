# ABOUTME: Tests for quest item functionality including display markers and behavior.
# ABOUTME: Verifies quest items show star marker in inventory and conditional exits work.

from io import StringIO

import pytest
from rich.console import Console

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus
from terminal_client.ui.rich_ui import create_inventory_table


class TestQuestItemDisplay:
    """Test that quest items display with the star marker."""

    def test_quest_item_shows_star_marker(self):
        """Quest items should display with a cyan star prefix."""
        items = {
            "consumables": [
                {"name": "Cultist's Journal", "quantity": 1, "equipped": False, "quest_item": True}
            ]
        }
        table = create_inventory_table(items)
        # Render the table to string to check contents
        console = Console(file=StringIO(), force_terminal=True)
        console.print(table)
        output = console.file.getvalue()

        # Should contain the star marker
        assert "★" in output
        assert "Cultist's Journal" in output

    def test_regular_item_no_star_marker(self):
        """Regular items should not have the star marker."""
        items = {
            "consumables": [
                {"name": "Potion of Healing", "quantity": 1, "equipped": False, "quest_item": False}
            ]
        }
        table = create_inventory_table(items)
        console = Console(file=StringIO(), force_terminal=True)
        console.print(table)
        output = console.file.getvalue()

        # Should NOT contain the star marker
        assert "★" not in output
        assert "Potion of Healing" in output

    def test_mixed_items_only_quest_has_star(self):
        """Only quest items should have the star marker in mixed inventory."""
        items = {
            "consumables": [
                {
                    "name": "Potion of Healing",
                    "quantity": 2,
                    "equipped": False,
                    "quest_item": False,
                },
                {"name": "Cultist's Journal", "quantity": 1, "equipped": False, "quest_item": True},
            ],
            "weapons": [
                {"name": "Longsword", "quantity": 1, "equipped": True, "quest_item": False}
            ],
        }
        table = create_inventory_table(items)
        console = Console(file=StringIO(), force_terminal=True)
        console.print(table)
        output = console.file.getvalue()

        # Star should appear only once (for the journal)
        assert output.count("★") == 1
        assert "Cultist's Journal" in output
        assert "Potion of Healing" in output
        assert "Longsword" in output

    def test_quest_item_without_flag_defaults_to_no_star(self):
        """Items without quest_item field should default to no star."""
        items = {
            "consumables": [
                {
                    "name": "Mystery Item",
                    "quantity": 1,
                    "equipped": False,
                    # No quest_item field
                }
            ]
        }
        table = create_inventory_table(items)
        console = Console(file=StringIO(), force_terminal=True)
        console.print(table)
        output = console.file.getvalue()

        assert "★" not in output
        assert "Mystery Item" in output


@pytest.fixture
def test_party():
    """Create a simple test party."""
    abilities = Abilities(
        strength=10, dexterity=14, constitution=14, intelligence=10, wisdom=12, charisma=10
    )
    character = Character(
        name="Test Hero",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=12,
        ac=16,
    )
    return Party([character])


class TestConditionalExits:
    """Test conditional exit requirements based on quest items."""

    def test_party_has_quest_item_when_present(self, test_party):
        """Party should report having an item when a character has it."""
        event_bus = EventBus()
        data_loader = DataLoader()

        game_state = GameState(
            party=test_party,
            dungeon_name="town_of_arden",
            campaign_id="the_unquiet_dead",
            event_bus=event_bus,
            data_loader=data_loader,
        )

        # Add quest item to character's inventory
        test_party.characters[0].inventory.add_item("gorgus_journal", "consumables")

        assert game_state.party_has_quest_item("gorgus_journal") is True

    def test_party_has_quest_item_when_absent(self, test_party):
        """Party should report not having an item when no one has it."""
        event_bus = EventBus()
        data_loader = DataLoader()

        game_state = GameState(
            party=test_party,
            dungeon_name="town_of_arden",
            campaign_id="the_unquiet_dead",
            event_bus=event_bus,
            data_loader=data_loader,
        )

        assert game_state.party_has_quest_item("gorgus_journal") is False

    def test_exit_requirements_met_with_quest_item(self, test_party):
        """Exit requirements should be met when party has required item."""
        event_bus = EventBus()
        data_loader = DataLoader()

        game_state = GameState(
            party=test_party,
            dungeon_name="town_of_arden",
            campaign_id="the_unquiet_dead",
            event_bus=event_bus,
            data_loader=data_loader,
        )

        # Manually set up a room with conditional exit for testing
        game_state.dungeon["rooms"]["test_room"] = {
            "id": "test_room",
            "name": "Test Room",
            "description": "A test room",
            "exits": {
                "north": {"destination": "other_room", "requires": {"quest_item": "gorgus_journal"}}
            },
        }
        game_state.current_room_id = "test_room"

        # Without the item, requirements not met
        req_check = game_state.check_exit_requirements("north")
        assert req_check["met"] is False
        assert len(req_check["missing"]) > 0

        # Add the item
        test_party.characters[0].inventory.add_item("gorgus_journal", "consumables")

        # With the item, requirements met
        req_check = game_state.check_exit_requirements("north")
        assert req_check["met"] is True
        assert len(req_check["missing"]) == 0

    def test_exit_hidden_until_unlocked(self, test_party):
        """Exits marked hidden_until_unlocked should not appear without item."""
        event_bus = EventBus()
        data_loader = DataLoader()

        game_state = GameState(
            party=test_party,
            dungeon_name="town_of_arden",
            campaign_id="the_unquiet_dead",
            event_bus=event_bus,
            data_loader=data_loader,
        )

        # Set up room with hidden conditional exit
        game_state.dungeon["rooms"]["test_room"] = {
            "id": "test_room",
            "name": "Test Room",
            "description": "A test room",
            "exits": {
                "west": "normal_room",
                "down": {
                    "destination": "secret_room",
                    "requires": {"quest_item": "gorgus_journal"},
                    "hidden_until_unlocked": True,
                },
            },
        }
        game_state.current_room_id = "test_room"

        # Without item, hidden exit should not be in available exits
        available = game_state.get_available_exits()
        assert "west" in available
        assert "down" not in available

        # Add the item
        test_party.characters[0].inventory.add_item("gorgus_journal", "consumables")

        # With item, hidden exit should now be visible
        available = game_state.get_available_exits()
        assert "west" in available
        assert "down" in available

    def test_exit_without_requirements_always_available(self, test_party):
        """Exits without requires field should always be available."""
        event_bus = EventBus()
        data_loader = DataLoader()

        game_state = GameState(
            party=test_party,
            dungeon_name="town_of_arden",
            campaign_id="the_unquiet_dead",
            event_bus=event_bus,
            data_loader=data_loader,
        )

        # Check a normal exit (town square has multiple exits without requirements)
        game_state.current_room_id = "arden.town_square"
        req_check = game_state.check_exit_requirements("north")
        assert req_check["met"] is True

    def test_move_blocked_without_required_item(self, test_party):
        """Movement should fail when exit requirements not met."""
        event_bus = EventBus()
        data_loader = DataLoader()

        game_state = GameState(
            party=test_party,
            dungeon_name="town_of_arden",
            campaign_id="the_unquiet_dead",
            event_bus=event_bus,
            data_loader=data_loader,
        )

        # Set up room with conditional exit
        game_state.dungeon["rooms"]["test_room"] = {
            "id": "test_room",
            "name": "Test Room",
            "description": "A test room",
            "exits": {
                "north": {
                    "destination": "arden.town_square",
                    "requires": {"quest_item": "gorgus_journal"},
                }
            },
        }
        game_state.dungeon["rooms"]["arden.town_square"] = game_state.dungeon["rooms"].get(
            "arden.town_square", {"id": "arden.town_square", "name": "Town Square"}
        )
        game_state.current_room_id = "test_room"

        # Without item, move should fail
        success = game_state.move("north", check_for_enemies=False)
        assert success is False
        assert game_state.current_room_id == "test_room"

        # Add the item
        test_party.characters[0].inventory.add_item("gorgus_journal", "consumables")

        # With item, move should succeed
        success = game_state.move("north", check_for_enemies=False)
        assert success is True
        assert game_state.current_room_id == "arden.town_square"
