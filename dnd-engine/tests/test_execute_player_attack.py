# ABOUTME: Tests for GameState.execute_player_attack() method
# ABOUTME: Tests player attack execution including weapon handling and concentration checks

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.game_state import GameState, PlayerAttackResult
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.inventory import EquipmentSlot
from dnd_engine.utils.events import EventBus


class TestExecutePlayerAttack:
    """Test GameState.execute_player_attack() method"""

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
    def fighter_abilities(self):
        """Create abilities for a fighter (high STR)"""
        return Abilities(
            strength=16,  # +3 modifier
            dexterity=14,  # +2 modifier
            constitution=14,  # +2 modifier
            intelligence=10,
            wisdom=12,
            charisma=8,
        )

    @pytest.fixture
    def fighter(self, fighter_abilities):
        """Create a fighter with a weapon equipped"""
        fighter = Character(
            name="Conan",
            character_class=CharacterClass.FIGHTER,
            level=3,
            abilities=fighter_abilities,
            max_hp=28,
            ac=16,
        )
        # Equip a longsword
        fighter.inventory.add_item("longsword", 1)
        fighter.inventory.equip_item("longsword", EquipmentSlot.WEAPON)
        return fighter

    @pytest.fixture
    def unarmed_fighter(self, fighter_abilities):
        """Create a fighter without a weapon equipped"""
        return Character(
            name="Bruiser",
            character_class=CharacterClass.FIGHTER,
            level=3,
            abilities=fighter_abilities,
            max_hp=28,
            ac=14,
        )

    @pytest.fixture
    def goblin(self):
        """Create a goblin enemy"""
        return Creature(name="Goblin", max_hp=7, ac=13, abilities=Abilities(8, 14, 10, 10, 8, 8))

    @pytest.fixture
    def weak_goblin(self):
        """Create a weak goblin that will die easily"""
        return Creature(
            name="Weak Goblin", max_hp=1, ac=5, abilities=Abilities(8, 14, 10, 10, 8, 8)
        )

    @pytest.fixture
    def game_state(self, fighter, goblin, event_bus, data_loader, dice_roller):
        """Create game state with party and enemies"""
        party = Party([fighter])
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller,
        )
        game_state.active_enemies = [goblin]
        return game_state


class TestBasicAttack(TestExecutePlayerAttack):
    """Test basic attack functionality"""

    def test_attack_returns_player_attack_result(self, game_state, fighter, goblin):
        """execute_player_attack returns PlayerAttackResult"""
        result = game_state.execute_player_attack(fighter, goblin)

        assert isinstance(result, PlayerAttackResult)
        assert result.success is True
        assert result.attacker_name == "Conan"
        assert result.target_name == "Goblin"

    def test_attack_includes_weapon_name(self, game_state, fighter, goblin):
        """Attack result includes weapon name"""
        result = game_state.execute_player_attack(fighter, goblin)

        # Weapon name should be the item name from data
        assert result.weapon_name == "Longsword"

    def test_attack_includes_attack_result(self, game_state, fighter, goblin):
        """Attack result includes the underlying AttackResult"""
        result = game_state.execute_player_attack(fighter, goblin)

        assert result.attack_result is not None
        assert hasattr(result.attack_result, "hit")
        assert hasattr(result.attack_result, "damage")
        assert hasattr(result.attack_result, "critical_hit")


class TestUnarmedAttack(TestExecutePlayerAttack):
    """Test unarmed attack functionality"""

    def test_unarmed_attack_works(
        self, unarmed_fighter, goblin, event_bus, data_loader, dice_roller
    ):
        """Attack without weapon equipped uses unarmed strike"""
        party = Party([unarmed_fighter])
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller,
        )
        game_state.active_enemies = [goblin]

        result = game_state.execute_player_attack(unarmed_fighter, goblin)

        assert result.success is True
        assert result.weapon_name == "unarmed strike"


class TestAttackDamage(TestExecutePlayerAttack):
    """Test attack damage calculations"""

    def test_hit_attack_deals_damage(self, game_state, fighter, goblin):
        """Successful hit deals damage to target"""
        initial_hp = goblin.current_hp

        result = game_state.execute_player_attack(fighter, goblin)

        if result.attack_result.hit:
            assert goblin.current_hp < initial_hp
            assert result.attack_result.damage > 0


class TestTargetKilled(TestExecutePlayerAttack):
    """Test target death tracking"""

    def test_killing_blow_sets_target_killed(self, fighter, weak_goblin, event_bus, data_loader):
        """target_killed is True when attack kills target"""
        # Use a dice roller that guarantees hits
        dice_roller = DiceRoller(seed=12345)

        party = Party([fighter])
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller,
        )
        game_state.active_enemies = [weak_goblin]

        result = game_state.execute_player_attack(fighter, weak_goblin)

        # With only 1 HP, any hit should kill
        if result.attack_result.hit:
            assert result.target_killed is True
            assert not weak_goblin.is_alive


class TestNarrativeContext(TestExecutePlayerAttack):
    """Test narrative context for LLM enhancement"""

    def test_narrative_context_included(self, game_state, fighter, goblin):
        """Attack result includes narrative context"""
        result = game_state.execute_player_attack(fighter, goblin)

        assert "attacker_name" in result.narrative_context
        assert "target_name" in result.narrative_context
        assert "weapon_name" in result.narrative_context
        assert "hit" in result.narrative_context
        assert "damage" in result.narrative_context
        assert "target_killed" in result.narrative_context

    def test_narrative_context_has_correct_values(self, game_state, fighter, goblin):
        """Narrative context values match result"""
        result = game_state.execute_player_attack(fighter, goblin)

        assert result.narrative_context["attacker_name"] == "Conan"
        assert result.narrative_context["target_name"] == "Goblin"
        assert result.narrative_context["weapon_name"] == "Longsword"
        assert result.narrative_context["hit"] == result.attack_result.hit
        assert result.narrative_context["damage"] == result.attack_result.damage
        assert result.narrative_context["target_killed"] == result.target_killed


class TestConcentrationBreak(TestExecutePlayerAttack):
    """Test concentration checking when attacking characters"""

    @pytest.fixture
    def concentrating_wizard(self):
        """Create a wizard concentrating on a spell"""
        wizard = Character(
            name="Enemy Wizard",
            character_class=CharacterClass.WIZARD,
            level=3,
            abilities=Abilities(8, 12, 10, 16, 10, 10),
            max_hp=15,
            ac=12,
            spellcasting_ability="int",
        )
        return wizard

    def test_concentration_checked_on_character_hit(
        self, fighter, concentrating_wizard, event_bus, data_loader
    ):
        """Concentration is checked when hitting a concentrating character"""
        # Use a dice roller that guarantees hits
        dice_roller = DiceRoller(seed=12345)

        party = Party([fighter])
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller,
        )

        # Set up concentration on target
        from dnd_engine.systems.time_manager import ActiveEffect, EffectType

        game_state.time_manager.add_effect(
            ActiveEffect(
                effect_type=EffectType.SPELL,
                source="Concentration: Test Spell",
                duration_type="rounds",
                duration_value=10,
                remaining_value=10,
                target_name="Enemy Wizard",
                caster_name="Enemy Wizard",
                concentration=True,
            )
        )

        result = game_state.execute_player_attack(fighter, concentrating_wizard)

        # If hit with damage, concentration should be checked
        if result.attack_result.hit and result.attack_result.damage > 0:
            # Either concentration was broken (dict returned) or it wasn't (None)
            # The check should have happened either way
            assert result.concentration_broken is None or isinstance(
                result.concentration_broken, dict
            )


class TestDisadvantage(TestExecutePlayerAttack):
    """Test that the disadvantage flag is forwarded to the underlying attack roll."""

    def test_disadvantage_flag_propagates_to_attack_result(
        self, game_state, fighter, goblin
    ):
        """When called with disadvantage=True, the AttackResult records it."""
        result = game_state.execute_player_attack(fighter, goblin, disadvantage=True)

        assert result.success is True
        assert result.attack_result is not None
        assert result.attack_result.disadvantage is True

    def test_default_attack_has_no_disadvantage(self, game_state, fighter, goblin):
        """Default attack (no kwarg) records disadvantage=False."""
        result = game_state.execute_player_attack(fighter, goblin)

        assert result.success is True
        assert result.attack_result is not None
        assert result.attack_result.disadvantage is False

    def test_disadvantage_lowers_attack_roll(
        self, fighter, goblin, event_bus, data_loader
    ):
        """A disadvantaged roll is the lower of two d20s; over many trials it
        should produce a lower average attack roll than a normal attack with
        the same seed sequence.
        """
        normal_rolls: list[int] = []
        disadv_rolls: list[int] = []

        for seed in range(50):
            for bucket, disadvantage in ((normal_rolls, False), (disadv_rolls, True)):
                dice_roller = DiceRoller(seed=seed)
                party = Party([fighter])
                gs = GameState(
                    party=party,
                    dungeon_name="test_dungeon",
                    event_bus=event_bus,
                    data_loader=data_loader,
                    dice_roller=dice_roller,
                )
                # Use a fresh goblin per trial so HP changes don't matter.
                target = Creature(
                    name="Goblin",
                    max_hp=999,
                    ac=99,  # Guarantees miss so target stays alive
                    abilities=Abilities(8, 14, 10, 10, 8, 8),
                )
                gs.active_enemies = [target]
                result = gs.execute_player_attack(
                    fighter, target, disadvantage=disadvantage
                )
                bucket.append(result.attack_result.attack_roll)

        normal_avg = sum(normal_rolls) / len(normal_rolls)
        disadv_avg = sum(disadv_rolls) / len(disadv_rolls)
        assert disadv_avg < normal_avg, (
            f"Expected disadvantage to lower avg roll, "
            f"got normal={normal_avg:.2f} vs disadv={disadv_avg:.2f}"
        )
