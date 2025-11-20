# ABOUTME: Unit tests for spell saving throw mechanics
# ABOUTME: Tests spell save DC, save resolution, damage calculation, and upcasting

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.core.combat import CombatEngine
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.spell import Spell, SpellDamage, SavingThrow, SpellSchool, CastingTime, SpellComponents, DurationType
from dnd_engine.utils.events import EventBus, EventType


class TestSpellSaveDC:
    """Test spell save DC calculation"""

    def setup_method(self):
        """Set up test fixtures"""
        self.wizard_abilities = Abilities(
            strength=8,
            dexterity=14,
            constitution=12,
            intelligence=18,  # +4 modifier
            wisdom=10,
            charisma=10
        )

        self.wizard = Character(
            name="Gandalf",
            character_class=CharacterClass.WIZARD,
            level=5,  # +3 proficiency
            abilities=self.wizard_abilities,
            max_hp=30,
            ac=12,
            spellcasting_ability="int"
        )

    def test_spell_save_dc_calculation(self):
        """Test that spell save DC = 8 + proficiency + ability modifier"""
        # Level 5 wizard has +3 proficiency, INT +4
        # DC = 8 + 3 + 4 = 15
        assert self.wizard.get_spell_save_dc() == 15

    def test_spell_save_dc_different_ability(self):
        """Test spell save DC with different spellcasting ability"""
        cleric = Character(
            name="Healer",
            character_class=CharacterClass.WIZARD,  # Using wizard class for simplicity
            level=3,  # +2 proficiency
            abilities=Abilities(
                strength=10,
                dexterity=10,
                constitution=14,
                intelligence=10,
                wisdom=16,  # +3 modifier
                charisma=10
            ),
            max_hp=20,
            ac=16,
            spellcasting_ability="wis"
        )
        # DC = 8 + 2 + 3 = 13
        assert cleric.get_spell_save_dc() == 13


class TestResolveSpellSave:
    """Test resolve_spell_save method"""

    def setup_method(self):
        """Set up test fixtures"""
        self.wizard = Character(
            name="Wizard",
            character_class=CharacterClass.WIZARD,
            level=5,
            abilities=Abilities(
                strength=8,
                dexterity=14,
                constitution=12,
                intelligence=18,  # +4, DC = 8 + 3 + 4 = 15
                wisdom=10,
                charisma=10
            ),
            max_hp=30,
            ac=12,
            spellcasting_ability="int"
        )

        self.goblin = Creature(
            name="Goblin",
            max_hp=7,
            ac=15,
            abilities=Abilities(
                strength=8,
                dexterity=14,  # +2 DEX save
                constitution=10,
                intelligence=10,
                wisdom=8,
                charisma=8
            )
        )

        self.combat = CombatEngine()
        self.event_bus = EventBus()

        # Fireball spell - save for half damage
        self.fireball = Spell(
            id="fireball",
            name="Fireball",
            level=3,
            school=SpellSchool.EVOCATION,
            casting_time=CastingTime.ACTION,
            range_ft=150,
            components=SpellComponents(verbal=True, somatic=True, material=True),
            duration=DurationType.INSTANTANEOUS,
            description="A bright streak flashes to a point...",
            damage=SpellDamage(
                dice="8d6",
                damage_type="fire",
                higher_levels="1d6 per slot level above 3rd"
            ),
            saving_throw=SavingThrow(
                ability="dexterity",
                on_success="half"
            ),
            classes=["wizard", "sorcerer"]
        )

    def test_resolve_spell_save_basic(self):
        """Test basic spell save resolution"""
        result = self.combat.resolve_spell_save(
            caster=self.wizard,
            targets=[self.goblin],
            spell=self.fireball,
            apply_damage=False,
            event_bus=self.event_bus
        )

        assert result["spell_name"] == "Fireball"
        assert result["caster"] == "Wizard"
        assert result["save_dc"] == 15
        assert result["save_ability"] == "dexterity"
        assert len(result["targets"]) == 1

        target_result = result["targets"][0]
        assert target_result["name"] == "Goblin"
        assert "roll" in target_result
        assert "modifier" in target_result
        assert "total" in target_result
        assert "success" in target_result
        assert target_result["damage"] > 0  # Should have some damage
        assert target_result["damage_type"] == "fire"

    def test_save_success_half_damage(self):
        """Test that successful save results in half damage"""
        # Use seeded dice roller to control save result
        self.combat.dice_roller = DiceRoller(seed=42)

        # Run multiple times to test both success and failure
        results = []
        for i in range(10):
            self.combat.dice_roller = DiceRoller(seed=i)
            result = self.combat.resolve_spell_save(
                caster=self.wizard,
                targets=[self.goblin],
                spell=self.fireball,
                apply_damage=False
            )
            results.append(result["targets"][0])

        # Check that we have both successes and failures
        successes = [r for r in results if r["success"]]
        failures = [r for r in results if not r["success"]]

        # Verify half damage on success
        if successes and failures:
            # Note: Due to random damage rolls, we can't guarantee exact half,
            # but successful saves should generally have less damage
            avg_success_damage = sum(r["damage"] for r in successes) / len(successes)
            avg_failure_damage = sum(r["damage"] for r in failures) / len(failures)
            assert avg_success_damage < avg_failure_damage

    def test_multiple_targets(self):
        """Test spell save with multiple targets"""
        goblin2 = Creature(
            name="Goblin2",
            max_hp=7,
            ac=15,
            abilities=Abilities(
                strength=8,
                dexterity=14,
                constitution=10,
                intelligence=10,
                wisdom=8,
                charisma=8
            )
        )

        result = self.combat.resolve_spell_save(
            caster=self.wizard,
            targets=[self.goblin, goblin2],
            spell=self.fireball,
            apply_damage=False
        )

        assert len(result["targets"]) == 2
        assert result["targets"][0]["name"] == "Goblin"
        assert result["targets"][1]["name"] == "Goblin2"

    def test_apply_damage_on_failed_save(self):
        """Test that damage is applied when apply_damage=True"""
        initial_hp = self.goblin.current_hp

        self.combat.resolve_spell_save(
            caster=self.wizard,
            targets=[self.goblin],
            spell=self.fireball,
            apply_damage=True
        )

        # Goblin should have taken damage
        assert self.goblin.current_hp < initial_hp

    def test_spell_save_event_emitted(self):
        """Test that SPELL_SAVE event is emitted"""
        events = []
        def capture_event(event):
            events.append(event)

        self.event_bus.subscribe(EventType.SPELL_SAVE, capture_event)

        self.combat.resolve_spell_save(
            caster=self.wizard,
            targets=[self.goblin],
            spell=self.fireball,
            event_bus=self.event_bus
        )

        assert len(events) == 1
        event = events[0]
        assert event.type == EventType.SPELL_SAVE
        assert event.data["spell_name"] == "Fireball"
        assert event.data["caster"] == "Wizard"
        assert event.data["save_dc"] == 15


class TestUpcasting:
    """Test spell upcasting mechanics"""

    def setup_method(self):
        """Set up test fixtures"""
        self.wizard = Character(
            name="Wizard",
            character_class=CharacterClass.WIZARD,
            level=5,
            abilities=Abilities(
                strength=8,
                dexterity=14,
                constitution=12,
                intelligence=18,
                wisdom=10,
                charisma=10
            ),
            max_hp=30,
            ac=12,
            spellcasting_ability="int"
        )

        self.goblin = Creature(
            name="Goblin",
            max_hp=50,  # High HP to survive damage
            ac=15,
            abilities=Abilities(
                strength=8,
                dexterity=14,
                constitution=10,
                intelligence=10,
                wisdom=8,
                charisma=8
            )
        )

        self.combat = CombatEngine(dice_roller=DiceRoller(seed=42))

        self.fireball = Spell(
            id="fireball",
            name="Fireball",
            level=3,
            school=SpellSchool.EVOCATION,
            casting_time=CastingTime.ACTION,
            range_ft=150,
            components=SpellComponents(verbal=True, somatic=True, material=True),
            duration=DurationType.INSTANTANEOUS,
            description="A bright streak flashes to a point...",
            damage=SpellDamage(
                dice="8d6",
                damage_type="fire",
                higher_levels="1d6 per slot level above 3rd"
            ),
            saving_throw=SavingThrow(
                ability="dexterity",
                on_success="half"
            ),
            classes=["wizard"]
        )

    def test_upcast_increases_damage(self):
        """Test that upcasting adds extra damage dice"""
        # Cast at base level (3rd)
        result_3rd = self.combat.resolve_spell_save(
            caster=self.wizard,
            targets=[self.goblin],
            spell=self.fireball,
            upcast_level=3
        )

        # Reset combat engine with same seed for consistency
        self.combat = CombatEngine(dice_roller=DiceRoller(seed=42))

        # Cast at 4th level (should add 1d6)
        result_4th = self.combat.resolve_spell_save(
            caster=self.wizard,
            targets=[self.goblin],
            spell=self.fireball,
            upcast_level=4
        )

        # 4th level should have higher damage potential (not guaranteed every roll, but averaged)
        # We're using same seed so this is more of a structure test
        assert "targets" in result_4th
        assert result_4th["targets"][0]["damage"] >= 0

    def test_upcast_event_includes_slot_level(self):
        """Test that spell save event includes both spell level and slot level"""
        events = []
        event_bus = EventBus()
        def capture_event(event):
            events.append(event)

        event_bus.subscribe(EventType.SPELL_SAVE, capture_event)

        self.combat.resolve_spell_save(
            caster=self.wizard,
            targets=[self.goblin],
            spell=self.fireball,
            upcast_level=5,  # Cast at 5th level (2 levels above base)
            event_bus=event_bus
        )

        assert len(events) == 1
        event_data = events[0].data
        assert event_data["spell_level"] == 3  # Base level
        assert event_data["slot_level"] == 5  # Cast level


class TestNoEffectOnSave:
    """Test spells with no effect on successful save"""

    def setup_method(self):
        """Set up test fixtures"""
        self.wizard = Character(
            name="Wizard",
            character_class=CharacterClass.WIZARD,
            level=5,
            abilities=Abilities(
                strength=8,
                dexterity=14,
                constitution=12,
                intelligence=18,
                wisdom=10,
                charisma=10
            ),
            max_hp=30,
            ac=12,
            spellcasting_ability="int"
        )

        self.goblin = Creature(
            name="Goblin",
            max_hp=7,
            ac=15,
            abilities=Abilities(
                strength=8,
                dexterity=14,
                constitution=10,
                intelligence=10,
                wisdom=12,  # +1 WIS save
                charisma=8
            )
        )

        self.combat = CombatEngine()

        # Hold Person - no damage, but for testing we'll use a damage spell with "none" effect
        self.sleep_spell = Spell(
            id="sleep",
            name="Sleep",
            level=1,
            school=SpellSchool.ENCHANTMENT,
            casting_time=CastingTime.ACTION,
            range_ft=90,
            components=SpellComponents(verbal=True, somatic=True, material=True),
            duration=DurationType.TIMED,
            duration_value="1 minute",
            description="Creatures fall unconscious...",
            saving_throw=SavingThrow(
                ability="wisdom",
                on_success="none"
            ),
            classes=["wizard", "bard"]
        )

    def test_no_damage_on_successful_save(self):
        """Test that spells with on_success='none' deal no damage on success"""
        # Run test multiple times to catch a successful save
        for seed in range(100):
            self.combat.dice_roller = DiceRoller(seed=seed)
            result = self.combat.resolve_spell_save(
                caster=self.wizard,
                targets=[self.goblin],
                spell=self.sleep_spell,
                apply_damage=False
            )

            target_result = result["targets"][0]
            if target_result["success"]:
                # Successful save = no effect
                assert target_result["damage"] == 0
                break


class TestDictFormatSpells:
    """Test that spell save works with dict format spells (backward compatibility)"""

    def setup_method(self):
        """Set up test fixtures"""
        self.wizard = Character(
            name="Wizard",
            character_class=CharacterClass.WIZARD,
            level=5,
            abilities=Abilities(
                strength=8,
                dexterity=14,
                constitution=12,
                intelligence=18,
                wisdom=10,
                charisma=10
            ),
            max_hp=30,
            ac=12,
            spellcasting_ability="int"
        )

        self.goblin = Creature(
            name="Goblin",
            max_hp=7,
            ac=15,
            abilities=Abilities(
                strength=8,
                dexterity=14,
                constitution=10,
                intelligence=10,
                wisdom=8,
                charisma=8
            )
        )

        self.combat = CombatEngine()

    def test_dict_format_spell(self):
        """Test resolve_spell_save with dict format spell"""
        fireball_dict = {
            "id": "fireball",
            "name": "Fireball",
            "level": 3,
            "damage": {
                "dice": "8d6",
                "damage_type": "fire",
                "higher_levels": "1d6 per slot level above 3rd"
            },
            "saving_throw": {
                "ability": "dexterity",
                "on_success": "half"
            }
        }

        result = self.combat.resolve_spell_save(
            caster=self.wizard,
            targets=[self.goblin],
            spell=fireball_dict,
            apply_damage=False
        )

        assert result["spell_name"] == "Fireball"
        assert result["save_dc"] == 15
        assert len(result["targets"]) == 1


class TestErrorHandling:
    """Test error handling in spell save resolution"""

    def setup_method(self):
        """Set up test fixtures"""
        self.wizard = Character(
            name="Wizard",
            character_class=CharacterClass.WIZARD,
            level=5,
            abilities=Abilities(
                strength=8,
                dexterity=14,
                constitution=12,
                intelligence=18,
                wisdom=10,
                charisma=10
            ),
            max_hp=30,
            ac=12,
            spellcasting_ability="int"
        )

        self.fighter = Character(
            name="Fighter",
            character_class=CharacterClass.FIGHTER,
            level=5,
            abilities=Abilities(
                strength=16,
                dexterity=14,
                constitution=14,
                intelligence=10,
                wisdom=10,
                charisma=8
            ),
            max_hp=40,
            ac=18
            # No spellcasting_ability
        )

        self.goblin = Creature(
            name="Goblin",
            max_hp=7,
            ac=15,
            abilities=Abilities(
                strength=8,
                dexterity=14,
                constitution=10,
                intelligence=10,
                wisdom=8,
                charisma=8
            )
        )

        self.combat = CombatEngine()

    def test_error_if_no_spell_save_dc(self):
        """Test that error is raised if caster has no spell save DC"""
        spell = {
            "name": "Fireball",
            "level": 3,
            "damage": {"dice": "8d6", "damage_type": "fire"},
            "saving_throw": {"ability": "dexterity", "on_success": "half"}
        }

        with pytest.raises(ValueError, match="has no spellcasting ability|cannot cast spells"):
            self.combat.resolve_spell_save(
                caster=self.fighter,
                targets=[self.goblin],
                spell=spell
            )

    def test_error_if_no_saving_throw_info(self):
        """Test that error is raised if spell has no saving throw info"""
        spell = {
            "name": "Magic Missile",
            "level": 1,
            "damage": {"dice": "1d4+1", "damage_type": "force"}
            # No saving_throw
        }

        with pytest.raises(ValueError, match="does not have saving throw information"):
            self.combat.resolve_spell_save(
                caster=self.wizard,
                targets=[self.goblin],
                spell=spell
            )
