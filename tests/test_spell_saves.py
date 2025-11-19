# ABOUTME: Unit tests for spell saving throw mechanics
# ABOUTME: Tests spell save DC calculation, spell casting, damage resolution, and upcasting

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.combat import CombatEngine
from dnd_engine.systems.resources import ResourcePool
from dnd_engine.utils.events import EventBus, Event, EventType


class TestCharacterSpellcasting:
    """Test Character spell casting methods and spell save DC"""

    def setup_method(self):
        """Set up test fixtures"""
        # Create a wizard character with INT 16 (modifier +3)
        self.wizard = Character(
            name="Gandalf",
            character_class=CharacterClass.FIGHTER,  # Using fighter class but with spellcasting
            level=5,
            abilities=Abilities(
                strength=10,
                dexterity=12,
                constitution=14,
                intelligence=16,  # +3 modifier
                wisdom=10,
                charisma=8
            ),
            max_hp=30,
            ac=12,
            spellcasting_ability="int",
            known_spells=["fireball", "burning_hands", "sacred_flame"]
        )

        # Add spell slots
        self.wizard.add_resource_pool(
            ResourcePool(name="1st level slots", current=4, maximum=4, recovery_type="long_rest")
        )
        self.wizard.add_resource_pool(
            ResourcePool(name="2nd level slots", current=3, maximum=3, recovery_type="long_rest")
        )
        self.wizard.add_resource_pool(
            ResourcePool(name="3rd level slots", current=2, maximum=2, recovery_type="long_rest")
        )

    def test_spell_save_dc_calculation(self):
        """Test spell save DC = 8 + proficiency + spellcasting modifier"""
        # Level 5 wizard: proficiency +3, INT modifier +3
        # DC = 8 + 3 + 3 = 14
        assert self.wizard.spell_save_dc == 14

    def test_spell_attack_bonus_calculation(self):
        """Test spell attack bonus = proficiency + spellcasting modifier"""
        # Level 5 wizard: proficiency +3, INT modifier +3
        # Attack bonus = 3 + 3 = 6
        assert self.wizard.spell_attack_bonus == 6

    def test_get_spellcasting_modifier(self):
        """Test getting the spellcasting ability modifier"""
        assert self.wizard.get_spellcasting_modifier() == 3  # INT +3

    def test_get_spellcasting_modifier_no_ability(self):
        """Test error when character has no spellcasting ability"""
        fighter = Character(
            name="Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(14, 12, 16, 10, 10, 8),
            max_hp=12,
            ac=16
        )

        with pytest.raises(ValueError, match="has no spellcasting ability"):
            fighter.get_spellcasting_modifier()

    def test_knows_spell(self):
        """Test checking if character knows a spell"""
        assert self.wizard.knows_spell("fireball") is True
        assert self.wizard.knows_spell("magic_missile") is False

    def test_can_cast_spell_cantrip(self):
        """Test cantrip casting (always available if known)"""
        assert self.wizard.can_cast_spell(0, "sacred_flame") is True

    def test_can_cast_spell_with_slot(self):
        """Test casting spell with available slot"""
        assert self.wizard.can_cast_spell(3, "fireball") is True

    def test_can_cast_spell_unknown(self):
        """Test cannot cast unknown spell"""
        assert self.wizard.can_cast_spell(1, "magic_missile") is False

    def test_can_cast_spell_no_slot(self):
        """Test cannot cast spell without slot"""
        # Use all 3rd level slots
        self.wizard.use_resource("3rd level slots", 2)
        assert self.wizard.can_cast_spell(3, "fireball") is False

    def test_cast_spell_cantrip(self):
        """Test casting cantrip doesn't consume slots"""
        result = self.wizard.cast_spell(0)
        assert result is True
        # Cantrips don't have slots, so this always succeeds

    def test_cast_spell_consume_slot(self):
        """Test casting spell consumes slot"""
        pool = self.wizard.get_resource_pool("3rd level slots")
        assert pool.current == 2

        result = self.wizard.cast_spell(3)
        assert result is True
        assert pool.current == 1

    def test_cast_spell_upcast(self):
        """Test upcasting spell consumes higher level slot"""
        pool_3rd = self.wizard.get_resource_pool("3rd level slots")

        # Cast burning hands (1st level) using 3rd level slot
        result = self.wizard.cast_spell(1, upcast_level=3)
        assert result is True
        assert pool_3rd.current == 1  # Used a 3rd level slot

    def test_get_spell_slot_name(self):
        """Test spell slot name formatting"""
        assert self.wizard._get_spell_slot_name(1) == "1st level slots"
        assert self.wizard._get_spell_slot_name(2) == "2nd level slots"
        assert self.wizard._get_spell_slot_name(3) == "3rd level slots"
        assert self.wizard._get_spell_slot_name(4) == "4th level slots"


class TestSpellSaveMechanics:
    """Test CombatEngine spell save resolution"""

    def setup_method(self):
        """Set up test fixtures"""
        self.combat_engine = CombatEngine()
        self.event_bus = EventBus()

        # Create caster (wizard with INT 16, level 5)
        self.caster = Character(
            name="Wizard",
            character_class=CharacterClass.FIGHTER,
            level=5,
            abilities=Abilities(10, 12, 14, 16, 10, 8),  # INT +3
            max_hp=30,
            ac=12,
            spellcasting_ability="int",
            known_spells=["fireball", "burning_hands", "hold_person", "sacred_flame"]
        )

        # Create targets
        self.goblin = Character(
            name="Goblin",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(8, 14, 10, 10, 8, 8),  # DEX +2
            max_hp=7,
            ac=15,
            saving_throw_proficiencies=[]
        )

        self.orc = Character(
            name="Orc",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(16, 12, 16, 7, 11, 10),  # DEX +1
            max_hp=15,
            ac=13,
            saving_throw_proficiencies=[]
        )

        # Spell data (mock from spells.json)
        self.fireball_data = {
            "id": "fireball",
            "name": "Fireball",
            "level": 3,
            "damage": {
                "dice": "8d6",
                "damage_type": "fire",
                "higher_levels": "When you cast this spell using a spell slot of 4th level or higher, the damage increases by 1d6 for each slot level above 3rd."
            },
            "saving_throw": {
                "ability": "dexterity",
                "on_success": "half"
            },
            "area_of_effect": "20-foot radius sphere"
        }

        self.sacred_flame_data = {
            "id": "sacred_flame",
            "name": "Sacred Flame",
            "level": 0,
            "damage": {
                "dice": "1d8",
                "damage_type": "radiant",
                "higher_levels": "The spell's damage increases by 1d8 when you reach 5th level (2d8), 11th level (3d8), and 17th level (4d8)."
            },
            "saving_throw": {
                "ability": "dexterity",
                "on_success": "none"
            }
        }

        self.hold_person_data = {
            "id": "hold_person",
            "name": "Hold Person",
            "level": 2,
            "saving_throw": {
                "ability": "wisdom",
                "on_success": "negates"
            }
        }

    def test_resolve_spell_save_basic(self):
        """Test basic spell save resolution"""
        result = self.combat_engine.resolve_spell_save(
            caster=self.caster,
            targets=[self.goblin],
            spell_data=self.fireball_data,
            apply_damage=False,
            event_bus=self.event_bus
        )

        assert result["spell_id"] == "fireball"
        assert result["spell_name"] == "Fireball"
        assert result["caster"] == "Wizard"
        assert result["save_dc"] == 14  # 8 + 3 (prof) + 3 (INT)
        assert result["save_ability"] == "dexterity"
        assert len(result["targets"]) == 1
        assert result["targets"][0]["name"] == "Goblin"

    def test_resolve_spell_save_damage_calculation(self):
        """Test damage is rolled correctly"""
        result = self.combat_engine.resolve_spell_save(
            caster=self.caster,
            targets=[self.goblin],
            spell_data=self.fireball_data,
            apply_damage=False
        )

        target_result = result["targets"][0]
        # Damage should be in range 8-48 (8d6)
        assert 8 <= target_result["damage_rolled"] <= 48

    def test_resolve_spell_save_half_damage_on_success(self):
        """Test half damage on successful save"""
        # Run multiple times to get both success and failure cases
        successes = 0
        failures = 0

        for _ in range(20):
            result = self.combat_engine.resolve_spell_save(
                caster=self.caster,
                targets=[self.goblin],
                spell_data=self.fireball_data,
                apply_damage=False
            )

            target_result = result["targets"][0]
            if target_result["save_result"]["success"]:
                successes += 1
                # Should take half damage
                assert target_result["damage_taken"] == target_result["damage_rolled"] // 2
            else:
                failures += 1
                # Should take full damage
                assert target_result["damage_taken"] == target_result["damage_rolled"]

        # Should have some successes and failures (not 100% either way)
        assert successes > 0
        assert failures > 0

    def test_resolve_spell_save_negates_on_success(self):
        """Test 'none' or 'negates' prevents all damage on success"""
        # Run multiple times
        for _ in range(20):
            result = self.combat_engine.resolve_spell_save(
                caster=self.caster,
                targets=[self.goblin],
                spell_data=self.sacred_flame_data,
                apply_damage=False
            )

            target_result = result["targets"][0]
            if target_result["save_result"]["success"]:
                # Should take no damage
                assert target_result["damage_taken"] == 0
            else:
                # Should take full damage
                assert target_result["damage_taken"] == target_result["damage_rolled"]

    def test_resolve_spell_save_multi_target(self):
        """Test spell affecting multiple targets"""
        result = self.combat_engine.resolve_spell_save(
            caster=self.caster,
            targets=[self.goblin, self.orc],
            spell_data=self.fireball_data,
            apply_damage=False
        )

        assert len(result["targets"]) == 2
        assert result["targets"][0]["name"] == "Goblin"
        assert result["targets"][1]["name"] == "Orc"
        # Both should get the same damage roll
        assert result["targets"][0]["damage_rolled"] == result["targets"][1]["damage_rolled"]

    def test_resolve_spell_save_apply_damage(self):
        """Test applying damage to targets"""
        goblin_hp = self.goblin.current_hp

        result = self.combat_engine.resolve_spell_save(
            caster=self.caster,
            targets=[self.goblin],
            spell_data=self.fireball_data,
            apply_damage=True
        )

        target_result = result["targets"][0]
        # Goblin should have taken damage (HP can't go below 0)
        expected_hp = max(0, goblin_hp - target_result["damage_taken"])
        assert self.goblin.current_hp == expected_hp

    def test_resolve_spell_save_emits_event(self):
        """Test spell cast event is emitted"""
        events_captured = []

        def capture_event(event: Event):
            events_captured.append(event)

        self.event_bus.subscribe(EventType.SPELL_CAST, capture_event)

        self.combat_engine.resolve_spell_save(
            caster=self.caster,
            targets=[self.goblin],
            spell_data=self.fireball_data,
            event_bus=self.event_bus
        )

        assert len(events_captured) == 1
        event_data = events_captured[0].data
        assert event_data["caster"] == "Wizard"
        assert event_data["spell_id"] == "fireball"
        assert event_data["save_dc"] == 14

    def test_resolve_spell_save_no_saving_throw(self):
        """Test error when spell doesn't have saving throw"""
        bad_spell = {
            "id": "test",
            "name": "Test",
            "level": 1
        }

        with pytest.raises(ValueError, match="does not require a saving throw"):
            self.combat_engine.resolve_spell_save(
                caster=self.caster,
                targets=[self.goblin],
                spell_data=bad_spell
            )

    def test_resolve_spell_save_caster_not_spellcaster(self):
        """Test error when caster doesn't have spell_save_dc"""
        fighter = Character(
            name="Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(16, 12, 14, 10, 10, 8),
            max_hp=12,
            ac=16
        )

        with pytest.raises(ValueError, match="has no spellcasting ability"):
            self.combat_engine.resolve_spell_save(
                caster=fighter,
                targets=[self.goblin],
                spell_data=self.fireball_data
            )


class TestSpellDamageUpcasting:
    """Test spell damage scaling with upcasting"""

    def setup_method(self):
        """Set up test fixtures"""
        self.combat_engine = CombatEngine()

        self.burning_hands_data = {
            "id": "burning_hands",
            "name": "Burning Hands",
            "level": 1,
            "damage": {
                "dice": "3d6",
                "damage_type": "fire",
                "higher_levels": "When you cast this spell using a spell slot of 2nd level or higher, the damage increases by 1d6 for each slot level above 1st."
            },
            "saving_throw": {
                "ability": "dexterity",
                "on_success": "half"
            }
        }

        self.fireball_data = {
            "id": "fireball",
            "name": "Fireball",
            "level": 3,
            "damage": {
                "dice": "8d6",
                "damage_type": "fire",
                "higher_levels": "When you cast this spell using a spell slot of 4th level or higher, the damage increases by 1d6 for each slot level above 3rd."
            },
            "saving_throw": {
                "ability": "dexterity",
                "on_success": "half"
            }
        }

    def test_roll_spell_damage_base_level(self):
        """Test rolling damage at base spell level"""
        damage = self.combat_engine._roll_spell_save_damage(
            self.burning_hands_data,
            base_level=1,
            upcast_level=None
        )
        # 3d6 = 3-18 damage
        assert 3 <= damage <= 18

    def test_roll_spell_damage_upcast(self):
        """Test rolling damage when upcasting"""
        # Burning Hands at 1st level: 3d6
        # Burning Hands at 2nd level: 4d6
        # Burning Hands at 3rd level: 5d6

        # Run multiple times to get statistics
        damages_1st = []
        damages_3rd = []

        for _ in range(100):
            damage_1st = self.combat_engine._roll_spell_save_damage(
                self.burning_hands_data,
                base_level=1,
                upcast_level=1
            )
            damage_3rd = self.combat_engine._roll_spell_save_damage(
                self.burning_hands_data,
                base_level=1,
                upcast_level=3
            )
            damages_1st.append(damage_1st)
            damages_3rd.append(damage_3rd)

        # 3rd level should on average deal more damage than 1st level
        avg_1st = sum(damages_1st) / len(damages_1st)
        avg_3rd = sum(damages_3rd) / len(damages_3rd)
        assert avg_3rd > avg_1st

    def test_roll_spell_damage_fireball_upcast(self):
        """Test Fireball damage upcasting"""
        # Fireball at 3rd level: 8d6 (8-48)
        # Fireball at 4th level: 9d6 (9-54)
        # Fireball at 5th level: 10d6 (10-60)

        damage_3rd = self.combat_engine._roll_spell_save_damage(
            self.fireball_data,
            base_level=3,
            upcast_level=3
        )
        damage_5th = self.combat_engine._roll_spell_save_damage(
            self.fireball_data,
            base_level=3,
            upcast_level=5
        )

        # 3rd level should be 8-48
        assert 8 <= damage_3rd <= 48
        # 5th level should be 10-60
        assert 10 <= damage_5th <= 60

    def test_roll_spell_damage_no_damage(self):
        """Test error when spell has no damage"""
        no_damage_spell = {
            "id": "test",
            "name": "Test",
            "level": 1
        }

        with pytest.raises(ValueError, match="has no damage"):
            self.combat_engine._roll_spell_save_damage(
                no_damage_spell,
                base_level=1
            )


class TestGetTargetsInArea:
    """Test area of effect targeting"""

    def setup_method(self):
        """Set up test fixtures"""
        self.combat_engine = CombatEngine()

        self.goblin1 = Character(
            name="Goblin1",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(8, 14, 10, 10, 8, 8),
            max_hp=7,
            ac=15
        )

        self.goblin2 = Character(
            name="Goblin2",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(8, 14, 10, 10, 8, 8),
            max_hp=7,
            ac=15
        )

        self.orc = Character(
            name="Orc",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=Abilities(16, 12, 16, 7, 11, 10),
            max_hp=15,
            ac=13
        )

    def test_get_targets_in_area_selected(self):
        """Test getting selected targets from area"""
        all_targets = [self.goblin1, self.goblin2, self.orc]
        selected = [self.goblin1, self.goblin2]

        targets = self.combat_engine._get_targets_in_area(
            all_targets,
            "20-foot radius sphere",
            selected
        )

        assert len(targets) == 2
        assert self.goblin1 in targets
        assert self.goblin2 in targets
        assert self.orc not in targets

    def test_get_targets_in_area_all(self):
        """Test getting all targets when none selected"""
        all_targets = [self.goblin1, self.goblin2, self.orc]

        targets = self.combat_engine._get_targets_in_area(
            all_targets,
            "20-foot radius sphere",
            None
        )

        assert len(targets) == 3
        assert targets == all_targets
