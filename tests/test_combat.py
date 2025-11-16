# ABOUTME: Unit tests for the combat engine
# ABOUTME: Tests attack resolution, damage calculation, critical hits, and combat outcomes

import pytest
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.core.combat import CombatEngine, AttackResult


class TestCombatEngine:
    """Test the CombatEngine class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.roller = DiceRoller(seed=42)
        self.engine = CombatEngine(self.roller)

        # Create a standard fighter
        fighter_abilities = Abilities(
            strength=16,  # +3
            dexterity=14,
            constitution=15,
            intelligence=10,
            wisdom=12,
            charisma=8
        )
        self.fighter = Creature(
            name="Fighter",
            max_hp=20,
            ac=16,
            abilities=fighter_abilities
        )

        # Create a goblin enemy
        goblin_abilities = Abilities(
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=8,
            charisma=8
        )
        self.goblin = Creature(
            name="Goblin",
            max_hp=7,
            ac=15,
            abilities=goblin_abilities
        )

    def test_attack_hit(self):
        """Test a successful attack"""
        # Use a seeded roller to get predictable results
        result = self.engine.resolve_attack(
            attacker=self.fighter,
            defender=self.goblin,
            attack_bonus=5,
            damage_dice="1d8+3"
        )

        assert isinstance(result, AttackResult)
        assert result.attacker_name == "Fighter"
        assert result.defender_name == "Goblin"
        assert result.hit is not None  # Should be True or False
        assert result.attack_roll >= 1
        assert result.attack_roll <= 20

    def test_attack_against_ac(self):
        """Test that attacks are compared against AC correctly"""
        # Attack roll + bonus >= AC means hit
        # Create a deterministic test by checking the result fields
        result = self.engine.resolve_attack(
            attacker=self.fighter,
            defender=self.goblin,
            attack_bonus=5,
            damage_dice="1d8+3"
        )

        expected_hit = (result.attack_roll + 5) >= self.goblin.ac

        assert result.hit == expected_hit
        if result.hit:
            assert result.damage > 0
        else:
            assert result.damage == 0

    def test_critical_hit_on_natural_20(self):
        """Test that rolling a 20 is always a critical hit"""
        # Run multiple attacks to eventually get a nat 20
        found_crit = False
        for _ in range(100):
            result = self.engine.resolve_attack(
                attacker=self.fighter,
                defender=self.goblin,
                attack_bonus=5,
                damage_dice="1d8+3"
            )

            if result.attack_roll == 20:
                assert result.critical_hit is True
                assert result.hit is True
                # Critical damage should be higher (doubled dice, not modifier)
                found_crit = True
                break

        assert found_crit, "Should eventually roll a natural 20"

    def test_critical_miss_on_natural_1(self):
        """Test that rolling a 1 is always a miss"""
        # Run multiple attacks to eventually get a nat 1
        found_miss = False
        for _ in range(100):
            result = self.engine.resolve_attack(
                attacker=self.fighter,
                defender=self.goblin,
                attack_bonus=5,
                damage_dice="1d8+3"
            )

            if result.attack_roll == 1:
                assert result.hit is False
                assert result.damage == 0
                found_miss = True
                break

        assert found_miss, "Should eventually roll a natural 1"

    def test_damage_calculation_normal_hit(self):
        """Test damage calculation for normal hits"""
        # Keep attacking until we get a normal hit (not crit, not miss)
        for _ in range(100):
            result = self.engine.resolve_attack(
                attacker=self.fighter,
                defender=self.goblin,
                attack_bonus=5,
                damage_dice="1d8+3"
            )

            if result.hit and not result.critical_hit:
                # Damage should be 1d8+3, so between 4 and 11
                assert 4 <= result.damage <= 11
                break

    def test_damage_calculation_critical_hit(self):
        """Test that critical hits double the damage dice"""
        # Keep attacking until we get a crit
        for _ in range(100):
            result = self.engine.resolve_attack(
                attacker=self.fighter,
                defender=self.goblin,
                attack_bonus=5,
                damage_dice="1d8+3"
            )

            if result.critical_hit:
                # Critical: 2d8+3, so between 5 and 19
                assert 5 <= result.damage <= 19
                break

    def test_miss_deals_no_damage(self):
        """Test that misses deal no damage"""
        # Keep attacking until we miss
        for _ in range(100):
            result = self.engine.resolve_attack(
                attacker=self.fighter,
                defender=self.goblin,
                attack_bonus=5,
                damage_dice="1d8+3"
            )

            if not result.hit:
                assert result.damage == 0
                break

    def test_apply_attack_damage(self):
        """Test applying attack damage to a creature"""
        goblin_initial_hp = self.goblin.current_hp

        # Force a hit by making attack bonus very high
        result = self.engine.resolve_attack(
            attacker=self.fighter,
            defender=self.goblin,
            attack_bonus=20,  # Almost guaranteed hit
            damage_dice="1d8+3",
            apply_damage=True
        )

        if result.hit:
            # Goblin should have taken damage
            assert self.goblin.current_hp < goblin_initial_hp
            assert self.goblin.current_hp == goblin_initial_hp - result.damage

    def test_attack_without_applying_damage(self):
        """Test that attacks can be simulated without applying damage"""
        goblin_initial_hp = self.goblin.current_hp

        result = self.engine.resolve_attack(
            attacker=self.fighter,
            defender=self.goblin,
            attack_bonus=20,
            damage_dice="1d8+3",
            apply_damage=False  # Don't actually apply damage
        )

        # HP should be unchanged
        assert self.goblin.current_hp == goblin_initial_hp

    def test_attack_can_kill_target(self):
        """Test that attacks can reduce target to 0 HP"""
        # Damage the goblin first
        self.goblin.current_hp = 3

        # Attack with high bonus to ensure hit
        result = self.engine.resolve_attack(
            attacker=self.fighter,
            defender=self.goblin,
            attack_bonus=20,
            damage_dice="1d8+3",
            apply_damage=True
        )

        if result.hit and result.damage >= 3:
            assert self.goblin.current_hp == 0
            assert not self.goblin.is_alive

    def test_attack_with_advantage(self):
        """Test attacks with advantage"""
        result = self.engine.resolve_attack(
            attacker=self.fighter,
            defender=self.goblin,
            attack_bonus=5,
            damage_dice="1d8+3",
            advantage=True
        )

        assert result.advantage is True
        # Attack roll should still be in valid range
        assert 1 <= result.attack_roll <= 20

    def test_attack_with_disadvantage(self):
        """Test attacks with disadvantage"""
        result = self.engine.resolve_attack(
            attacker=self.fighter,
            defender=self.goblin,
            attack_bonus=5,
            damage_dice="1d8+3",
            disadvantage=True
        )

        assert result.disadvantage is True
        assert 1 <= result.attack_roll <= 20

    def test_attack_result_string_representation(self):
        """Test that AttackResult has a useful string representation"""
        result = self.engine.resolve_attack(
            attacker=self.fighter,
            defender=self.goblin,
            attack_bonus=5,
            damage_dice="1d8+3"
        )

        result_str = str(result)
        assert "Fighter" in result_str
        assert "Goblin" in result_str

    def test_different_damage_dice(self):
        """Test attacks with different damage dice"""
        test_cases = [
            ("1d4+2", 3, 6),  # min, max damage
            ("1d6+3", 4, 9),
            ("2d6+3", 5, 15),
            ("1d12+3", 4, 15),
        ]

        for damage_dice, min_dmg, max_dmg in test_cases:
            # Try multiple times to hit
            for _ in range(50):
                result = self.engine.resolve_attack(
                    attacker=self.fighter,
                    defender=self.goblin,
                    attack_bonus=20,  # Ensure hit
                    damage_dice=damage_dice
                )

                if result.hit and not result.critical_hit:
                    assert min_dmg <= result.damage <= max_dmg
                    break


class TestAttackResult:
    """Test the AttackResult class"""

    def test_attack_result_creation(self):
        """Test creating an AttackResult"""
        result = AttackResult(
            attacker_name="Fighter",
            defender_name="Goblin",
            attack_roll=15,
            attack_bonus=5,
            target_ac=15,
            hit=True,
            damage=8,
            critical_hit=False,
            advantage=False,
            disadvantage=False
        )

        assert result.attacker_name == "Fighter"
        assert result.defender_name == "Goblin"
        assert result.attack_roll == 15
        assert result.hit is True
        assert result.damage == 8

    def test_attack_result_total(self):
        """Test that total attack is calculated correctly"""
        result = AttackResult(
            attacker_name="Fighter",
            defender_name="Goblin",
            attack_roll=12,
            attack_bonus=5,
            target_ac=15,
            hit=True,
            damage=8,
            critical_hit=False,
            advantage=False,
            disadvantage=False
        )

        assert result.total_attack == 17  # 12 + 5
