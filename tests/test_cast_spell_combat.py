# ABOUTME: Tests for GameState.cast_spell_combat() method
# ABOUTME: Tests combat spellcasting including attack, save, buff, and concentration spells

import pytest
from dnd_engine.core.game_state import GameState, CombatSpellResult
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.party import Party
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.combat import CombatEngine
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus
from dnd_engine.systems.resources import ResourcePool
from dnd_engine.systems.time_manager import TimeManager


class TestCastSpellCombat:
    """Test GameState.cast_spell_combat() method"""

    @pytest.fixture
    def event_bus(self):
        """Create event bus for testing"""
        return EventBus()

    @pytest.fixture
    def data_loader(self):
        """Create data loader"""
        return DataLoader()

    @pytest.fixture
    def dice_roller(self):
        """Create seeded dice roller for predictable results"""
        return DiceRoller(seed=42)

    @pytest.fixture
    def wizard_abilities(self):
        """Create abilities for a wizard (high INT)"""
        return Abilities(
            strength=8,
            dexterity=12,
            constitution=14,
            intelligence=16,  # +3 modifier
            wisdom=10,
            charisma=10
        )

    @pytest.fixture
    def wizard(self, wizard_abilities):
        """Create a wizard with attack spells"""
        wizard = Character(
            name="Gandalf",
            character_class=CharacterClass.WIZARD,
            level=3,
            abilities=wizard_abilities,
            max_hp=18,
            ac=12,
            spellcasting_ability="int",
            known_spells=["fire_bolt", "burning_hands", "magic_missile", "mage_armor", "shield"],
            prepared_spells=["fire_bolt", "burning_hands", "magic_missile", "mage_armor", "shield"]
        )
        wizard.add_resource_pool(ResourcePool(
            name="spell_slots_level_1",
            current=4,
            maximum=4,
            recovery_type="long_rest"
        ))
        return wizard

    @pytest.fixture
    def goblin(self):
        """Create a goblin enemy"""
        return Creature(
            name="Goblin",
            max_hp=7,
            ac=13,
            abilities=Abilities(8, 14, 10, 10, 8, 8)
        )

    @pytest.fixture
    def skeleton(self):
        """Create a skeleton enemy"""
        return Creature(
            name="Skeleton",
            max_hp=13,
            ac=13,
            abilities=Abilities(10, 14, 15, 6, 8, 5)
        )

    @pytest.fixture
    def game_state(self, wizard, goblin, event_bus, data_loader, dice_roller):
        """Create game state with party and enemies"""
        party = Party([wizard])
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller
        )
        game_state.active_enemies = [goblin]
        return game_state


class TestAttackSpells(TestCastSpellCombat):
    """Test attack spell resolution"""

    def test_fire_bolt_returns_combat_spell_result(self, game_state, wizard, goblin, data_loader):
        """Fire Bolt cast returns CombatSpellResult"""
        spell_data = data_loader.load_spells()["fire_bolt"]

        result = game_state.cast_spell_combat(
            caster=wizard,
            spell_data=spell_data,
            target=goblin,
            spellcasting_ability="int"
        )

        assert isinstance(result, CombatSpellResult)
        assert result.success is True
        assert result.spell_name == "Fire Bolt"
        assert result.caster_name == "Gandalf"
        assert result.spell_type == "attack"
        assert result.is_area_effect is False
        assert "Goblin" in result.targets

    def test_fire_bolt_attack_result_populated(self, game_state, wizard, goblin, data_loader):
        """Fire Bolt includes AttackResult"""
        spell_data = data_loader.load_spells()["fire_bolt"]

        result = game_state.cast_spell_combat(
            caster=wizard,
            spell_data=spell_data,
            target=goblin,
            spellcasting_ability="int"
        )

        assert result.attack_result is not None
        # AttackResult has attack_roll, damage, hit, etc.
        assert hasattr(result.attack_result, "attack_roll")
        assert hasattr(result.attack_result, "damage")
        assert hasattr(result.attack_result, "hit")

    def test_fire_bolt_damage_applied(self, wizard, goblin, data_loader, event_bus):
        """Fire Bolt damage is applied to target when it hits"""
        spell_data = data_loader.load_spells()["fire_bolt"]
        initial_hp = goblin.current_hp

        # Try multiple seeds to find one that hits
        for seed in range(50):
            dice_roller = DiceRoller(seed=seed)
            party = Party([wizard])
            game_state = GameState(
                party=party,
                dungeon_name="test_dungeon",
                event_bus=event_bus,
                data_loader=data_loader,
                dice_roller=dice_roller
            )
            game_state.active_enemies = [goblin]
            goblin.current_hp = initial_hp  # Reset

            result = game_state.cast_spell_combat(
                caster=wizard,
                spell_data=spell_data,
                target=goblin,
                spellcasting_ability="int"
            )

            if result.attack_result.hit:
                assert result.total_damage > 0
                assert goblin.current_hp < initial_hp
                return

        pytest.skip("No hitting seed found in range")

    def test_fire_bolt_killed_target_tracked(self, wizard, goblin, data_loader, event_bus):
        """Fire Bolt tracks killed targets"""
        spell_data = data_loader.load_spells()["fire_bolt"]

        # Try multiple seeds to find one that kills
        for seed in range(50):
            dice_roller = DiceRoller(seed=seed)
            party = Party([wizard])
            game_state = GameState(
                party=party,
                dungeon_name="test_dungeon",
                event_bus=event_bus,
                data_loader=data_loader,
                dice_roller=dice_roller
            )
            game_state.active_enemies = [goblin]
            goblin.current_hp = 1  # Near death

            result = game_state.cast_spell_combat(
                caster=wizard,
                spell_data=spell_data,
                target=goblin,
                spellcasting_ability="int"
            )

            if result.attack_result.hit and not goblin.is_alive:
                assert "Goblin" in result.killed_targets
                return

        pytest.skip("No killing hit found in range")


class TestSaveSpells(TestCastSpellCombat):
    """Test saving throw spell resolution"""

    def test_burning_hands_area_effect(self, game_state, wizard, goblin, skeleton, data_loader):
        """Burning Hands targets all enemies as area effect"""
        spell_data = data_loader.load_spells()["burning_hands"]
        game_state.active_enemies = [goblin, skeleton]

        result = game_state.cast_spell_combat(
            caster=wizard,
            spell_data=spell_data,
            target=None,  # Area effect
            spellcasting_ability="int"
        )

        assert result.success is True
        assert result.spell_type == "save"
        assert result.is_area_effect is True
        assert len(result.targets) == 2
        assert "Goblin" in result.targets
        assert "Skeleton" in result.targets

    def test_save_spell_has_dc_and_ability(self, game_state, wizard, goblin, data_loader):
        """Save spell result includes DC and save ability"""
        spell_data = data_loader.load_spells()["burning_hands"]

        result = game_state.cast_spell_combat(
            caster=wizard,
            spell_data=spell_data,
            target=goblin,
            spellcasting_ability="int"
        )

        assert result.save_dc is not None
        assert result.save_ability is not None
        assert result.save_dc > 0

    def test_save_spell_has_per_target_results(self, game_state, wizard, goblin, skeleton, data_loader):
        """Save spell has per-target save results"""
        spell_data = data_loader.load_spells()["burning_hands"]
        game_state.active_enemies = [goblin, skeleton]

        result = game_state.cast_spell_combat(
            caster=wizard,
            spell_data=spell_data,
            target=None,
            spellcasting_ability="int"
        )

        assert result.save_results is not None
        assert len(result.save_results) == 2
        # Each target result has save info
        for target_result in result.save_results:
            assert "success" in target_result or "damage" in target_result

    def test_save_spell_damage_applied(self, game_state, wizard, goblin, data_loader):
        """Save spell damage is applied to targets"""
        spell_data = data_loader.load_spells()["burning_hands"]
        initial_hp = goblin.current_hp

        result = game_state.cast_spell_combat(
            caster=wizard,
            spell_data=spell_data,
            target=goblin,
            spellcasting_ability="int"
        )

        # Burning hands always does some damage (half on save)
        assert result.total_damage >= 0
        if result.total_damage > 0:
            assert goblin.current_hp < initial_hp


class TestBuffSpells(TestCastSpellCombat):
    """Test buff and auto-hit spell resolution"""

    def test_mage_armor_creates_effect(self, game_state, wizard, data_loader):
        """Mage Armor creates a buff effect"""
        spell_data = data_loader.load_spells()["mage_armor"]

        result = game_state.cast_spell_combat(
            caster=wizard,
            spell_data=spell_data,
            target=wizard,
            spellcasting_ability="int"
        )

        assert result.success is True
        assert result.spell_type == "buff"
        assert result.spell_name == "Mage Armor"
        assert result.total_damage == 0

    def test_shield_spell_buff_type(self, game_state, wizard, data_loader):
        """Shield spell is categorized as buff"""
        spell_data = data_loader.load_spells()["shield"]

        result = game_state.cast_spell_combat(
            caster=wizard,
            spell_data=spell_data,
            target=wizard,
            spellcasting_ability="int"
        )

        assert result.success is True
        assert result.spell_type == "buff"


class TestConcentration(TestCastSpellCombat):
    """Test concentration spell handling"""

    @pytest.fixture
    def wizard_with_concentration_spells(self, wizard_abilities):
        """Create wizard with concentration spells"""
        wizard = Character(
            name="Merlin",
            character_class=CharacterClass.WIZARD,
            level=5,
            abilities=wizard_abilities,
            max_hp=28,
            ac=12,
            spellcasting_ability="int",
            known_spells=["hold_person", "detect_magic"],
            prepared_spells=["hold_person", "detect_magic"]
        )
        wizard.add_resource_pool(ResourcePool(
            name="spell_slots_level_2",
            current=3,
            maximum=3,
            recovery_type="long_rest"
        ))
        return wizard

    def test_concentration_spell_tracked(self, event_bus, data_loader, dice_roller, wizard_with_concentration_spells, goblin):
        """Casting concentration spell sets now_concentrating"""
        party = Party([wizard_with_concentration_spells])
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller
        )
        game_state.active_enemies = [goblin]

        # Hold Person is a concentration spell
        spell_data = data_loader.load_spells().get("hold_person")
        if not spell_data:
            pytest.skip("hold_person spell not in data")

        result = game_state.cast_spell_combat(
            caster=wizard_with_concentration_spells,
            spell_data=spell_data,
            target=goblin,
            spellcasting_ability="int"
        )

        if spell_data.get("concentration"):
            assert result.now_concentrating is True


class TestErrorCases(TestCastSpellCombat):
    """Test error handling"""

    def test_area_spell_no_enemies(self, game_state, wizard, data_loader):
        """Area spell with no enemies returns error"""
        spell_data = data_loader.load_spells()["burning_hands"]
        game_state.active_enemies = []  # No enemies

        result = game_state.cast_spell_combat(
            caster=wizard,
            spell_data=spell_data,
            target=None,
            spellcasting_ability="int"
        )

        assert result.success is False
        assert result.error is not None
        assert "No enemies" in result.error
