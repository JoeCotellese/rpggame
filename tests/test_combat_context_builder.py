# ABOUTME: Unit tests for CombatContextBuilder class
# ABOUTME: Tests context assembly with mocked dependencies

from unittest.mock import Mock

from dnd_engine.core.character import Character
from dnd_engine.core.combat import AttackResult
from dnd_engine.core.creature import Creature
from dnd_engine.systems.combat_context.builder import CombatContextBuilder
from dnd_engine.systems.inventory import EquipmentSlot


class TestCombatContextBuilder:
    """Test the CombatContextBuilder class."""

    def setup_method(self):
        """Create test fixtures."""
        self.data_loader = Mock()
        self.game_state = Mock()

        # Setup default mock returns
        self.data_loader.load_items.return_value = {
            "weapons": {
                "longsword": {
                    "name": "Longsword",
                    "damage": "1d8",
                    "damage_type": "slashing",
                },
                "shortbow": {
                    "name": "Shortbow",
                    "damage": "1d6",
                    "damage_type": "piercing",
                },
            },
            "armor": {
                "chainmail": {"name": "Chainmail", "armor_type": "heavy"},
                "leather_armor": {"name": "Leather Armor", "armor_type": "light"},
            },
        }

        self.data_loader.load_races.return_value = {
            "human": {"name": "Human"},
            "elf": {"name": "Elf"},
        }

        self.data_loader.load_monsters.return_value = {
            "skeleton": {
                "name": "Skeleton",
                "type": "undead",
                "ac_source": "armor scraps",
                "actions": [
                    {"name": "Shortsword", "damage_type": "piercing"},
                    {"name": "Shortbow", "damage_type": "piercing"},
                ],
            },
            "zombie": {
                "name": "Zombie",
                "type": "undead",
                "ac_source": "",
                "actions": [{"name": "Slam", "damage_type": "bludgeoning"}],
            },
        }

        self.game_state.get_current_room.return_value = {"name": "Dark Crypt"}
        self.game_state.get_recent_combat_history.return_value = [
            "Fighter attacked Skeleton for 8 damage",
            "Skeleton attacked Fighter for 5 damage",
        ]
        self.game_state.get_battlefield_state.return_value = {
            "party_hp": [("Fighter", 25, 30)],
            "enemy_hp": [("Skeleton", 8, 13)],
        }

        self.builder = CombatContextBuilder(self.data_loader, self.game_state)

    def test_build_player_attack_context_with_weapon(self):
        """Test building context for player attack with equipped weapon."""
        # Create player character
        player = Mock(spec=Character)
        player.name = "Fighter"
        player.race = "human"
        player.inventory = Mock()
        player.inventory.get_equipped_item.side_effect = (
            lambda slot: "longsword" if slot == EquipmentSlot.WEAPON else None
        )

        # Create enemy
        enemy = Mock(spec=Creature)
        enemy.name = "Skeleton"

        # Create attack result
        result = AttackResult(
            attacker_name="Fighter",
            defender_name="Skeleton",
            attack_roll=18,
            attack_bonus=5,
            target_ac=13,
            hit=True,
            critical_hit=False,
            damage=10,
            advantage=False,
            disadvantage=False,
        )

        # Build context
        context = self.builder.build_attack_context(player, enemy, result)

        # Verify structure
        assert context["attacker"] == "Fighter"
        assert context["defender"] == "Skeleton"
        assert context["damage"] == 10
        assert context["critical"] is False
        assert context["hit"] is True
        assert context["location"] == "Dark Crypt"
        assert context["weapon"] == "Longsword"
        assert context["damage_type"] == "slashing"
        assert context["attacker_race"] == "Human"
        assert context["defender_armor"] == "armor scraps"
        assert len(context["combat_history"]) == 2
        assert context["battlefield_state"] == {
            "party_hp": [("Fighter", 25, 30)],
            "enemy_hp": [("Skeleton", 8, 13)],
        }

    def test_build_player_attack_context_unarmed(self):
        """Test building context for player unarmed attack."""
        player = Mock(spec=Character)
        player.name = "Monk"
        player.race = "elf"
        player.inventory = Mock()
        player.inventory.get_equipped_item.return_value = None

        enemy = Mock(spec=Creature)
        enemy.name = "Zombie"

        result = AttackResult(
            attacker_name="Monk",
            defender_name="Zombie",
            attack_roll=15,
            attack_bonus=3,
            target_ac=8,
            hit=True,
            critical_hit=False,
            damage=6,
            advantage=False,
            disadvantage=False,
        )

        context = self.builder.build_attack_context(player, enemy, result)

        assert context["weapon"] == "unarmed strike"
        assert context["damage_type"] == "bludgeoning"
        assert context["attacker_race"] == "Elf"
        assert context["defender_armor"] == ""  # Zombie has no ac_source

    def test_build_enemy_attack_context(self):
        """Test building context for enemy attack against player."""
        enemy = Mock(spec=Creature)
        enemy.name = "Skeleton"

        player = Mock(spec=Character)
        player.name = "Fighter"
        player.race = "human"
        player.inventory = Mock()
        player.inventory.get_equipped_item.side_effect = (
            lambda slot: "chainmail" if slot == EquipmentSlot.ARMOR else None
        )

        result = AttackResult(
            attacker_name="Skeleton",
            defender_name="Fighter",
            attack_roll=12,
            attack_bonus=4,
            target_ac=16,
            hit=False,
            critical_hit=False,
            damage=0,
            advantage=False,
            disadvantage=False,
        )

        action_data = {"name": "Shortsword", "damage_type": "piercing"}

        context = self.builder.build_attack_context(
            enemy, player, result, action_data=action_data
        )

        assert context["attacker"] == "Skeleton"
        assert context["defender"] == "Fighter"
        assert context["weapon"] == "Shortsword"
        assert context["damage_type"] == "piercing"
        assert context["attacker_race"] == "undead"
        assert context["defender_armor"] == "heavy armor"
        assert context["hit"] is False

    def test_build_spell_attack_context(self):
        """Test building context for spell attack."""
        player = Mock(spec=Character)
        player.name = "Wizard"
        player.race = "elf"
        player.inventory = Mock()
        player.inventory.get_equipped_item.return_value = None

        enemy = Mock(spec=Creature)
        enemy.name = "Skeleton"

        result = AttackResult(
            attacker_name="Wizard",
            defender_name="Skeleton",
            attack_roll=20,
            attack_bonus=7,
            target_ac=13,
            hit=True,
            critical_hit=True,
            damage=16,
            advantage=False,
            disadvantage=False,
        )

        spell_data = {"name": "Fire Bolt", "damage_type": "fire"}

        context = self.builder.build_attack_context(
            player, enemy, result, action_data=spell_data, is_spell=True
        )

        assert context["weapon"] == "Fire Bolt"
        assert context["damage_type"] == "fire"
        assert context["is_spell"] is True
        assert context["critical"] is True

    def test_build_context_with_unknown_race(self):
        """Test building context when race is not in data."""
        player = Mock(spec=Character)
        player.name = "Dragonborn"
        player.race = "dragonborn"  # Not in mock data
        player.inventory = Mock()
        player.inventory.get_equipped_item.return_value = None

        enemy = Mock(spec=Creature)
        enemy.name = "Skeleton"

        result = AttackResult(
            attacker_name="Dragonborn",
            defender_name="Skeleton",
            attack_roll=15,
            attack_bonus=4,
            target_ac=13,
            hit=True,
            critical_hit=False,
            damage=8,
            advantage=False,
            disadvantage=False,
        )

        context = self.builder.build_attack_context(player, enemy, result)

        assert context["attacker_race"] == ""  # Fallback to empty string

    def test_build_context_with_unknown_monster(self):
        """Test building context when monster is not in data."""
        player = Mock(spec=Character)
        player.name = "Fighter"
        player.race = "human"
        player.inventory = Mock()
        player.inventory.get_equipped_item.return_value = None

        enemy = Mock(spec=Creature)
        enemy.name = "Beholder"  # Not in mock data

        result = AttackResult(
            attacker_name="Fighter",
            defender_name="Beholder",
            attack_roll=15,
            attack_bonus=5,
            target_ac=18,
            hit=False,
            critical_hit=False,
            damage=0,
            advantage=False,
            disadvantage=False,
        )

        context = self.builder.build_attack_context(player, enemy, result)

        assert context["defender_armor"] == ""  # Fallback to empty string

    def test_build_context_with_no_armor(self):
        """Test building context when defender has no equipped armor."""
        enemy = Mock(spec=Creature)
        enemy.name = "Skeleton"

        player = Mock(spec=Character)
        player.name = "Rogue"
        player.race = "elf"
        player.inventory = Mock()
        player.inventory.get_equipped_item.return_value = None  # No armor

        result = AttackResult(
            attacker_name="Skeleton",
            defender_name="Rogue",
            attack_roll=15,
            attack_bonus=4,
            target_ac=14,
            hit=True,
            critical_hit=False,
            damage=5,
            advantage=False,
            disadvantage=False,
        )

        action_data = {"name": "Shortsword", "damage_type": "piercing"}

        context = self.builder.build_attack_context(
            enemy, player, result, action_data=action_data
        )

        assert context["defender_armor"] == ""  # No armor equipped

    def test_build_context_with_empty_combat_history(self):
        """Test building context when combat has just started."""
        self.game_state.get_recent_combat_history.return_value = []

        player = Mock(spec=Character)
        player.name = "Fighter"
        player.race = "human"
        player.inventory = Mock()
        player.inventory.get_equipped_item.return_value = None

        enemy = Mock(spec=Creature)
        enemy.name = "Skeleton"

        result = AttackResult(
            attacker_name="Fighter",
            defender_name="Skeleton",
            attack_roll=15,
            attack_bonus=5,
            target_ac=13,
            hit=True,
            critical_hit=False,
            damage=8,
            advantage=False,
            disadvantage=False,
        )

        context = self.builder.build_attack_context(player, enemy, result)

        assert context["combat_history"] == []

    def test_build_context_without_action_data(self):
        """Test building context for enemy attack without action data."""
        enemy = Mock(spec=Creature)
        enemy.name = "Skeleton"

        player = Mock(spec=Character)
        player.name = "Fighter"
        player.race = "human"
        player.inventory = Mock()
        player.inventory.get_equipped_item.return_value = None

        result = AttackResult(
            attacker_name="Skeleton",
            defender_name="Fighter",
            attack_roll=10,
            attack_bonus=4,
            target_ac=14,
            hit=False,
            critical_hit=False,
            damage=0,
            advantage=False,
            disadvantage=False,
        )

        # No action_data provided
        context = self.builder.build_attack_context(enemy, player, result)

        assert context["weapon"] == "attack"  # Default fallback
        assert context["damage_type"] == ""
