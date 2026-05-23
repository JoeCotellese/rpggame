# ABOUTME: Unit tests for the combat engine
# ABOUTME: Tests attack resolution, damage calculation, critical hits, and combat outcomes

from dnd_engine.core.combat import AttackResult, CombatEngine
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller


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
            charisma=8,
        )
        self.fighter = Creature(name="Fighter", max_hp=20, ac=16, abilities=fighter_abilities)

        # Create a goblin enemy
        goblin_abilities = Abilities(
            strength=8, dexterity=14, constitution=10, intelligence=10, wisdom=8, charisma=8
        )
        self.goblin = Creature(name="Goblin", max_hp=7, ac=15, abilities=goblin_abilities)

    def test_attack_hit(self):
        """Test a successful attack"""
        # Use a seeded roller to get predictable results
        result = self.engine.resolve_attack(
            attacker=self.fighter, defender=self.goblin, attack_bonus=5, damage_dice="1d8+3"
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
            attacker=self.fighter, defender=self.goblin, attack_bonus=5, damage_dice="1d8+3"
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
                attacker=self.fighter, defender=self.goblin, attack_bonus=5, damage_dice="1d8+3"
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
                attacker=self.fighter, defender=self.goblin, attack_bonus=5, damage_dice="1d8+3"
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
                attacker=self.fighter, defender=self.goblin, attack_bonus=5, damage_dice="1d8+3"
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
                attacker=self.fighter, defender=self.goblin, attack_bonus=5, damage_dice="1d8+3"
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
                attacker=self.fighter, defender=self.goblin, attack_bonus=5, damage_dice="1d8+3"
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
            apply_damage=True,
        )

        if result.hit:
            # Goblin should have taken damage
            assert self.goblin.current_hp < goblin_initial_hp
            assert self.goblin.current_hp == goblin_initial_hp - result.damage

    def test_attack_without_applying_damage(self):
        """Test that attacks can be simulated without applying damage"""
        goblin_initial_hp = self.goblin.current_hp

        self.engine.resolve_attack(
            attacker=self.fighter,
            defender=self.goblin,
            attack_bonus=20,
            damage_dice="1d8+3",
            apply_damage=False,  # Don't actually apply damage
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
            apply_damage=True,
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
            advantage=True,
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
            disadvantage=True,
        )

        assert result.disadvantage is True
        assert 1 <= result.attack_roll <= 20

    def test_attack_result_string_representation(self):
        """Test that AttackResult has a useful string representation"""
        result = self.engine.resolve_attack(
            attacker=self.fighter, defender=self.goblin, attack_bonus=5, damage_dice="1d8+3"
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
                    damage_dice=damage_dice,
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
            disadvantage=False,
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
            disadvantage=False,
        )

        assert result.total_attack == 17  # 12 + 5


class TestSavingThrowEffects:
    """Test saving throw processing in combat"""

    def setup_method(self):
        """Set up test fixtures"""
        self.roller = DiceRoller(seed=42)
        self.engine = CombatEngine(self.roller)

        # Create test creatures
        fighter_abilities = Abilities(
            strength=16,
            dexterity=14,
            constitution=15,  # +2 CON modifier
            intelligence=10,
            wisdom=12,
            charisma=8,
        )
        self.fighter = Creature(name="Fighter", max_hp=20, ac=16, abilities=fighter_abilities)

        ghoul_abilities = Abilities(
            strength=13, dexterity=15, constitution=10, intelligence=7, wisdom=10, charisma=6
        )
        self.ghoul = Creature(name="Ghoul", max_hp=22, ac=12, abilities=ghoul_abilities)

    def test_saving_throw_triggers_on_hit(self):
        """Test that saving throw is processed when attack hits"""
        # Ghoul claws action with saving throw
        action = {
            "name": "Claws",
            "attack_bonus": 4,
            "damage": "2d4+2",
            "saving_throw": {
                "trigger": "on_hit",
                "ability": "constitution",
                "dc": 10,
                "on_fail": {
                    "condition": "paralyzed",
                    "duration_type": "rounds",
                    "duration": 10,
                    "allow_repeat_save": True,
                    "repeat_timing": "end_of_turn",
                },
            },
        }

        # Attack with high bonus to ensure hit
        result = self.engine.resolve_attack(
            attacker=self.ghoul,
            defender=self.fighter,
            attack_bonus=20,
            damage_dice=action["damage"],
            apply_damage=True,
            action=action,
        )

        # Should hit
        assert result.hit is True

        # Fighter should either be paralyzed (failed save) or not (passed save)
        # We can't predict the exact outcome due to randomness, but we can check structure
        if self.fighter.has_condition("paralyzed"):
            # Failed save - should have condition with metadata
            assert "paralyzed" in self.fighter.active_conditions
            metadata = self.fighter.active_conditions["paralyzed"]
            assert metadata["duration_type"] == "rounds"
            assert metadata["duration_remaining"] == 10
            assert metadata["dc"] == 10
            assert metadata["ability"] == "constitution"
            assert metadata["allow_repeat_save"] is True
        else:
            # Passed save - should not have condition
            assert "paralyzed" not in self.fighter.active_conditions

    def test_saving_throw_not_triggered_on_miss(self):
        """Test that saving throw doesn't trigger when attack misses"""
        action = {
            "name": "Claws",
            "attack_bonus": 4,
            "damage": "2d4+2",
            "saving_throw": {
                "trigger": "on_hit",
                "ability": "constitution",
                "dc": 10,
                "on_fail": {
                    "condition": "paralyzed",
                    "duration_type": "rounds",
                    "duration": 10,
                    "allow_repeat_save": True,
                },
            },
        }

        # Attack with very low bonus to likely miss
        result = self.engine.resolve_attack(
            attacker=self.ghoul,
            defender=self.fighter,
            attack_bonus=-10,
            damage_dice=action["damage"],
            apply_damage=True,
            action=action,
        )

        # If missed, should not have paralysis regardless
        if not result.hit:
            assert not self.fighter.has_condition("paralyzed")

    def test_process_saving_throw_effect_directly(self):
        """Test _process_saving_throw_effect method directly"""
        saving_throw_data = {
            "trigger": "on_hit",
            "ability": "constitution",
            "dc": 10,
            "on_fail": {
                "condition": "paralyzed",
                "duration_type": "rounds",
                "duration": 10,
                "allow_repeat_save": True,
                "repeat_timing": "end_of_turn",
            },
        }

        # Process the saving throw effect
        result = self.engine._process_saving_throw_effect(
            saving_throw_data, self.ghoul, self.fighter, event_bus=None
        )

        # Should return a result dict with save_result and condition_applied
        assert result is not None
        assert "save_result" in result
        assert "condition_applied" in result
        assert "success" in result["save_result"]
        assert "ability" in result["save_result"]
        assert result["save_result"]["ability"] == "con"
        assert result["save_result"]["dc"] == 10

        # Check if condition was applied based on save result
        if not result["save_result"]["success"]:
            assert self.fighter.has_condition("paralyzed")
            assert result["condition_applied"] == "paralyzed"
        else:
            assert not self.fighter.has_condition("paralyzed")
            assert result["condition_applied"] is None


class TestApplyDamageModifiers:
    """Tests for the per-type damage modifier chokepoint.

    `CombatEngine._apply_damage_modifiers` is the single seam that
    scales raw damage by the target's per-type Resistance / Immunity.
    It must consult BOTH creature-condition flags (the legacy item-
    effects path) AND the monster catalog fields (`damage_resistances`,
    `damage_immunities`) attached to the Creature instance.

    This slice (#461) wires Resistance + Immunity only. Vulnerability,
    No-Stacking, Order-of-Application, and clamp-at-zero are tracked
    by follow-up slices (#463, #468, #490).
    """

    def setup_method(self):
        self.engine = CombatEngine(DiceRoller(seed=1))
        abilities = Abilities(
            strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10
        )
        self.target = Creature(name="Target", max_hp=100, ac=10, abilities=abilities)

    def test_no_modifiers_returns_raw_damage(self):
        """A target with no per-type modifiers takes the raw amount."""
        result = self.engine._apply_damage_modifiers(self.target, raw_damage=10, damage_type="fire")
        assert result == 10

    def test_no_damage_type_returns_raw_damage(self):
        """When damage_type is None, modifiers cannot apply."""
        self.target.add_condition("has_resistance_fire")
        result = self.engine._apply_damage_modifiers(self.target, raw_damage=10, damage_type=None)
        assert result == 10

    def test_condition_flag_resistance_halves_damage(self):
        """`has_resistance_{type}` condition halves matching damage."""
        self.target.add_condition("has_resistance_fire")
        result = self.engine._apply_damage_modifiers(self.target, raw_damage=10, damage_type="fire")
        assert result == 5

    def test_condition_flag_resistance_floors_odd_damage(self):
        """Resistance halves with floor rounding (SRD: 'round down')."""
        self.target.add_condition("has_resistance_fire")
        result = self.engine._apply_damage_modifiers(self.target, raw_damage=5, damage_type="fire")
        assert result == 2

    def test_condition_flag_resistance_is_per_type(self):
        """Fire resistance does not reduce poison damage."""
        self.target.add_condition("has_resistance_fire")
        result = self.engine._apply_damage_modifiers(
            self.target, raw_damage=10, damage_type="poison"
        )
        assert result == 10

    def test_monster_catalog_resistance_halves_damage(self):
        """`damage_resistances` list attribute halves matching damage."""
        self.target.damage_resistances = ["cold"]
        result = self.engine._apply_damage_modifiers(self.target, raw_damage=10, damage_type="cold")
        assert result == 5

    def test_monster_catalog_immunity_zeroes_damage(self):
        """`damage_immunities` list attribute zeroes matching damage."""
        self.target.damage_immunities = ["fire", "poison"]
        result = self.engine._apply_damage_modifiers(self.target, raw_damage=20, damage_type="fire")
        assert result == 0

    def test_monster_catalog_immunity_is_per_type(self):
        """A fire-immune creature still takes other damage types."""
        self.target.damage_immunities = ["fire"]
        result = self.engine._apply_damage_modifiers(
            self.target, raw_damage=20, damage_type="slashing"
        )
        assert result == 20

    def test_immunity_takes_precedence_over_resistance(self):
        """If both immunity and resistance match the type, damage is 0."""
        self.target.damage_immunities = ["fire"]
        self.target.add_condition("has_resistance_fire")
        result = self.engine._apply_damage_modifiers(self.target, raw_damage=10, damage_type="fire")
        assert result == 0

    def test_damage_type_is_normalized_case_insensitively(self):
        """Mixed-case damage types match the modifier list (SRD types
        are lowercased in the catalog)."""
        self.target.damage_immunities = ["fire"]
        result = self.engine._apply_damage_modifiers(self.target, raw_damage=10, damage_type="Fire")
        assert result == 0


class TestResolveAttackDamageType:
    """Tests for `damage_type` plumbing through `resolve_attack`."""

    def setup_method(self):
        self.engine = CombatEngine(DiceRoller(seed=42))
        attacker_abilities = Abilities(
            strength=16, dexterity=14, constitution=15, intelligence=10, wisdom=12, charisma=8
        )
        self.attacker = Creature(
            name="Attacker", max_hp=20, ac=16, abilities=attacker_abilities
        )
        defender_abilities = Abilities(
            strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10
        )
        self.defender = Creature(name="Defender", max_hp=100, ac=10, abilities=defender_abilities)

    def test_resolve_attack_accepts_damage_type_parameter(self):
        """`resolve_attack` accepts an optional `damage_type` kwarg
        without behavior change when target has no modifiers."""
        result = self.engine.resolve_attack(
            attacker=self.attacker,
            defender=self.defender,
            attack_bonus=20,  # always hits
            damage_dice="0d4+10",
            damage_type="fire",
        )
        assert result.hit is True
        assert result.damage == 10  # No modifiers, full damage

    def test_resolve_attack_immunity_zeroes_damage(self):
        """A fire-immune monster takes 0 damage from a fire-typed attack."""
        self.defender.damage_immunities = ["fire"]
        result = self.engine.resolve_attack(
            attacker=self.attacker,
            defender=self.defender,
            attack_bonus=20,
            damage_dice="0d4+10",
            damage_type="fire",
            apply_damage=True,
        )
        assert result.hit is True
        assert result.damage == 0
        assert self.defender.current_hp == 100  # No HP lost

    def test_resolve_attack_resistance_halves_damage(self):
        """A cold-resistant target takes half damage from cold attacks."""
        self.defender.damage_resistances = ["cold"]
        result = self.engine.resolve_attack(
            attacker=self.attacker,
            defender=self.defender,
            attack_bonus=20,
            damage_dice="0d4+10",
            damage_type="cold",
            apply_damage=True,
        )
        assert result.hit is True
        assert result.damage == 5
        assert self.defender.current_hp == 95

    def test_resolve_attack_without_damage_type_is_backward_compatible(self):
        """Existing callers that don't pass `damage_type` see no change."""
        # Even if the defender has fire immunity, it shouldn't apply when
        # the attack has no damage_type tag.
        self.defender.damage_immunities = ["fire"]
        result = self.engine.resolve_attack(
            attacker=self.attacker,
            defender=self.defender,
            attack_bonus=20,
            damage_dice="0d4+10",
            apply_damage=True,
        )
        assert result.hit is True
        assert result.damage == 10
        assert self.defender.current_hp == 90


class TestResolveSpellSaveDamageType:
    """Tests for damage_type wiring in `resolve_spell_save`."""

    def setup_method(self):
        self.engine = CombatEngine(DiceRoller(seed=42))

    def _make_caster(self, dc: int = 15) -> Creature:
        """Build a minimal caster that exposes `get_spell_save_dc`."""
        abilities = Abilities(
            strength=10, dexterity=10, constitution=10, intelligence=16, wisdom=10, charisma=10
        )
        caster = Creature(name="Caster", max_hp=20, ac=12, abilities=abilities)
        caster.get_spell_save_dc = lambda: dc  # type: ignore[attr-defined]
        return caster

    def _make_target(self, name: str = "Target") -> Creature:
        abilities = Abilities(
            strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10
        )
        return Creature(name=name, max_hp=100, ac=10, abilities=abilities)

    def test_spell_save_immunity_zeroes_damage(self):
        """A fire-immune target takes 0 damage from a Fireball-style
        save spell, even on a failed save."""
        caster = self._make_caster(dc=99)  # impossible DC → always fails
        target = self._make_target()
        target.damage_immunities = ["fire"]

        spell = {
            "name": "Fireball",
            "level": 3,
            "id": "fireball",
            "damage": {"dice": "0d6+30", "damage_type": "fire"},
            "saving_throw": {"ability": "dex", "on_success": "half"},
        }

        result = self.engine.resolve_spell_save(
            caster=caster, targets=[target], spell=spell, apply_damage=True
        )
        # Find the result row for our target
        target_row = next(r for r in result["targets"] if r["name"] == target.name)
        assert target_row["success"] is False  # failed the impossible save
        assert target_row["damage"] == 0
        assert target.current_hp == 100

    def test_spell_save_resistance_halves_damage(self):
        """A cold-resistant target takes half damage from a cold spell
        on a failed save."""
        caster = self._make_caster(dc=99)  # always fail
        target = self._make_target()
        target.damage_resistances = ["cold"]

        spell = {
            "name": "Ray of Frost (save variant)",
            "level": 1,
            "id": "rof_save",
            "damage": {"dice": "0d6+10", "damage_type": "cold"},
            "saving_throw": {"ability": "con", "on_success": "half"},
        }

        result = self.engine.resolve_spell_save(
            caster=caster, targets=[target], spell=spell, apply_damage=True
        )
        target_row = next(r for r in result["targets"] if r["name"] == target.name)
        assert target_row["success"] is False
        assert target_row["damage"] == 5
        assert target.current_hp == 95
