# ABOUTME: Tests for GameState.cast_spell_combat() method
# ABOUTME: Tests combat spellcasting including attack, save, buff, and concentration spells

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.game_state import CombatSpellResult, GameState
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.resources import ResourcePool
from dnd_engine.utils.events import EventBus


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


class TestSpellSlotManagement(TestCastSpellCombat):
    """Test spell slot validation and consumption in cast_spell_combat()"""

    def test_leveled_spell_consumes_slot(self, game_state, wizard, goblin, data_loader):
        """Casting a leveled spell consumes a spell slot"""
        spell_data = data_loader.load_spells()["burning_hands"]
        initial_slots = wizard.get_available_spell_slots(1)
        assert initial_slots > 0, "Test requires available spell slots"

        result = game_state.cast_spell_combat(
            caster=wizard,
            spell_data=spell_data,
            target=goblin,
            spellcasting_ability="int"
        )

        assert result.success is True
        assert wizard.get_available_spell_slots(1) == initial_slots - 1

    def test_leveled_spell_tracks_resources_consumed(self, game_state, wizard, goblin, data_loader):
        """Casting a leveled spell populates resources_consumed for refund tracking"""
        spell_data = data_loader.load_spells()["burning_hands"]

        result = game_state.cast_spell_combat(
            caster=wizard,
            spell_data=spell_data,
            target=goblin,
            spellcasting_ability="int"
        )

        assert result.success is True
        assert len(result.resources_consumed) == 1
        assert result.resources_consumed[0] == ("spell_slots_level_1", 1)

    def test_no_spell_slots_returns_error(self, game_state, wizard, goblin, data_loader):
        """Casting a leveled spell with no slots returns clear error"""
        spell_data = data_loader.load_spells()["burning_hands"]
        # Exhaust all level 1 slots
        pool = wizard.resource_pools.get("spell_slots_level_1")
        pool.current = 0

        result = game_state.cast_spell_combat(
            caster=wizard,
            spell_data=spell_data,
            target=goblin,
            spellcasting_ability="int"
        )

        assert result.success is False
        assert result.error is not None
        assert "1st-level spell slots" in result.error

    def test_no_spell_slots_does_not_consume(self, game_state, wizard, goblin, data_loader):
        """Failed spell cast due to no slots doesn't consume resources"""
        spell_data = data_loader.load_spells()["burning_hands"]
        pool = wizard.resource_pools.get("spell_slots_level_1")
        pool.current = 0

        result = game_state.cast_spell_combat(
            caster=wizard,
            spell_data=spell_data,
            target=goblin,
            spellcasting_ability="int"
        )

        assert result.success is False
        # No resources should be consumed when validation fails
        assert len(result.resources_consumed) == 0
        assert pool.current == 0

    def test_cantrip_does_not_consume_slots(self, game_state, wizard, goblin, data_loader):
        """Cantrips (level 0) don't consume spell slots"""
        spell_data = data_loader.load_spells()["fire_bolt"]
        initial_slots = wizard.get_available_spell_slots(1)

        result = game_state.cast_spell_combat(
            caster=wizard,
            spell_data=spell_data,
            target=goblin,
            spellcasting_ability="int"
        )

        assert result.success is True
        # Spell slots unchanged
        assert wizard.get_available_spell_slots(1) == initial_slots
        # No resources consumed for cantrips
        assert len(result.resources_consumed) == 0

    def test_area_spell_no_enemies_still_tracks_consumed_resources(
        self, game_state, wizard, data_loader
    ):
        """Area spell that fails due to no targets still tracks consumed resources"""
        spell_data = data_loader.load_spells()["burning_hands"]
        game_state.active_enemies = []  # No enemies
        initial_slots = wizard.get_available_spell_slots(1)

        result = game_state.cast_spell_combat(
            caster=wizard,
            spell_data=spell_data,
            target=None,
            spellcasting_ability="int"
        )

        assert result.success is False
        # Slot was consumed before we knew there were no enemies
        assert wizard.get_available_spell_slots(1) == initial_slots - 1
        # resources_consumed should be populated for middleware refund
        assert len(result.resources_consumed) == 1
        assert result.resources_consumed[0] == ("spell_slots_level_1", 1)

    def test_higher_level_spell_slot_tracking(self, wizard_abilities, event_bus, data_loader, dice_roller, goblin):
        """Higher level spells track correct slot level in resources_consumed"""
        # Create wizard with level 2 slots and hold_person spell
        wizard = Character(
            name="Gandalf",
            character_class=CharacterClass.WIZARD,
            level=5,
            abilities=wizard_abilities,
            max_hp=28,
            ac=12,
            spellcasting_ability="int",
            known_spells=["hold_person"],
            prepared_spells=["hold_person"]
        )
        wizard.add_resource_pool(ResourcePool(
            name="spell_slots_level_2",
            current=3,
            maximum=3,
            recovery_type="long_rest"
        ))
        party = Party([wizard])
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller
        )
        game_state.active_enemies = [goblin]

        spell_data = data_loader.load_spells().get("hold_person")
        if not spell_data:
            pytest.skip("hold_person spell not in data")

        result = game_state.cast_spell_combat(
            caster=wizard,
            spell_data=spell_data,
            target=goblin,
            spellcasting_ability="int"
        )

        assert wizard.get_available_spell_slots(2) == 2
        assert len(result.resources_consumed) == 1
        assert result.resources_consumed[0] == ("spell_slots_level_2", 1)


class TestSpellSlotRefundIntegration(TestCastSpellCombat):
    """
    Integration tests for spell slot refund through middleware chain.

    These tests verify that when a spell fails after slot consumption,
    the middleware correctly refunds the consumed slot.
    """

    def test_area_spell_no_enemies_slot_refunded_through_middleware(
        self, wizard, data_loader, event_bus, dice_roller
    ):
        """
        Test that spell slot is refunded when area spell fails due to no enemies.

        Flow:
        1. Spell slot is consumed in cast_spell_combat()
        2. Spell fails ("No enemies to target")
        3. CLI sets context.result = FAILED and propagates resources_consumed
        4. ResourceCleanupMiddleware refunds the slot
        """
        from unittest.mock import Mock, patch
        from dnd_engine.systems.combat_middleware import (
            ActionResult,
            CombatActionContext,
            CombatActionExecutor,
        )
        from dnd_engine.systems.action_economy import ActionType

        # Setup game state with combat active
        party = Party([wizard])
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller
        )
        game_state.active_enemies = []  # No enemies - will cause spell to fail

        # Start combat to enable turn tracking
        game_state.in_combat = True
        from dnd_engine.systems.initiative import InitiativeTracker
        tracker = InitiativeTracker()
        tracker.add_combatant(wizard)
        game_state.initiative_tracker = tracker

        # Record initial spell slots
        initial_slots = wizard.get_available_spell_slots(1)
        assert initial_slots > 0, "Test requires available spell slots"

        spell_data = data_loader.load_spells()["burning_hands"]

        # Create the action executor
        executor = CombatActionExecutor(game_state)

        # Simulate what CLI._execute_spell does
        def execute_spell_action(ctx):
            result = game_state.cast_spell_combat(
                caster=wizard,
                spell_data=spell_data,
                target=None,  # Area effect
                spellcasting_ability="int"
            )

            # Propagate consumed resources for middleware refund
            ctx.resources_consumed = result.resources_consumed

            if not result.success:
                ctx.result = ActionResult.FAILED
                ctx.error_message = result.error or "Spell failed"
                return False

            return True

        # Execute through middleware chain (patching logging to avoid side effects)
        with patch('dnd_engine.utils.logging_config.get_logging_config', return_value=None):
            context = executor.execute(
                actor=wizard,
                action_type=ActionType.ACTION,
                action_name="cast_spell",
                action_handler=execute_spell_action,
                spell="Burning Hands",
                target="area"
            )

        # Verify the spell failed
        assert context.result == ActionResult.FAILED
        assert "No enemies" in context.error_message

        # Verify the spell slot was REFUNDED by middleware
        final_slots = wizard.get_available_spell_slots(1)
        assert final_slots == initial_slots, (
            f"Spell slot should have been refunded. "
            f"Expected {initial_slots}, got {final_slots}"
        )

    def test_no_slots_error_no_refund_needed(self, wizard, data_loader, event_bus, dice_roller):
        """
        Test that when spell fails due to no slots, nothing is consumed or refunded.

        This is a validation failure - slot consumption should never happen.
        """
        from unittest.mock import Mock, patch
        from dnd_engine.systems.combat_middleware import (
            ActionResult,
            CombatActionContext,
            CombatActionExecutor,
        )
        from dnd_engine.systems.action_economy import ActionType

        # Exhaust all level 1 slots
        pool = wizard.resource_pools.get("spell_slots_level_1")
        pool.current = 0

        # Setup game state with combat active
        party = Party([wizard])
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller
        )
        game_state.active_enemies = [Creature(
            name="Goblin", max_hp=7, ac=13,
            abilities=Abilities(8, 14, 10, 10, 8, 8)
        )]

        # Start combat
        game_state.in_combat = True
        from dnd_engine.systems.initiative import InitiativeTracker
        tracker = InitiativeTracker()
        tracker.add_combatant(wizard)
        game_state.initiative_tracker = tracker

        spell_data = data_loader.load_spells()["burning_hands"]
        executor = CombatActionExecutor(game_state)

        def execute_spell_action(ctx):
            result = game_state.cast_spell_combat(
                caster=wizard,
                spell_data=spell_data,
                target=game_state.active_enemies[0],
                spellcasting_ability="int"
            )

            ctx.resources_consumed = result.resources_consumed

            if not result.success:
                ctx.result = ActionResult.FAILED
                ctx.error_message = result.error or "Spell failed"
                return False

            return True

        with patch('dnd_engine.utils.logging_config.get_logging_config', return_value=None):
            context = executor.execute(
                actor=wizard,
                action_type=ActionType.ACTION,
                action_name="cast_spell",
                action_handler=execute_spell_action,
                spell="Burning Hands",
                target="Goblin"
            )

        # Verify the spell failed due to no slots
        assert context.result == ActionResult.FAILED
        assert "spell slots" in context.error_message.lower()

        # Verify no resources were consumed (validation failure, not execution failure)
        assert len(context.resources_consumed) == 0
        assert pool.current == 0  # Still zero, nothing to refund


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
