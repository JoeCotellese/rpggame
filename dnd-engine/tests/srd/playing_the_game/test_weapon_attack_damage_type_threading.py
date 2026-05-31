# ABOUTME: Verifies weapon/enemy/OA/item attacks thread damage_type into the resistance pipeline (#617, #598).
# ABOUTME: Guards that physical-damage Resistance/Vulnerability/Immunity actually apply in normal combat, not just spells.

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.action_economy import TurnState
from dnd_engine.systems.initiative import InitiativeEntry, InitiativeTracker
from dnd_engine.systems.inventory import EquipmentSlot
from dnd_engine.utils.events import EventBus


@pytest.fixture
def data_loader():
    return DataLoader()


@pytest.fixture
def fighter_abilities():
    # STR 16 (+3): longsword (slashing) and unarmed strike both swing off STR.
    return Abilities(strength=16, dexterity=14, constitution=14, intelligence=10, wisdom=12, charisma=8)


def _make_fighter(abilities, *, with_weapon=True):
    fighter = Character(
        name="Conan",
        character_class=CharacterClass.FIGHTER,
        level=3,
        abilities=abilities,
        max_hp=28,
        ac=16,
    )
    if with_weapon:
        fighter.inventory.add_item("longsword", 1)
        fighter.inventory.equip_item("longsword", EquipmentSlot.WEAPON)
    return fighter


def _run_player_attack(data_loader, fighter, *, seed, resistances=None, vulnerabilities=None):
    """Run one player weapon attack with a fixed seed against an always-hit dummy.

    Returns the underlying AttackResult. Same seed -> identical attack and
    damage rolls, so the only variable across runs is the target's per-type
    modifiers.
    """
    dice_roller = DiceRoller(seed=seed)
    party = Party([fighter])
    gs = GameState(
        party=party,
        dungeon_name="test_dungeon",
        event_bus=EventBus(),
        data_loader=data_loader,
        dice_roller=dice_roller,
    )
    target = Creature(
        name="Dummy",
        max_hp=999,  # never dies, so damage is never HP-capped
        ac=1,  # guarantees the attack lands
        abilities=Abilities(8, 14, 10, 10, 8, 8),
    )
    if resistances:
        target.damage_resistances = resistances
    if vulnerabilities:
        target.damage_vulnerabilities = vulnerabilities
    gs.active_enemies = [target]
    return gs.execute_player_attack(fighter, target).attack_result


class TestPlayerWeaponDamageType:
    def test_slashing_resistance_halves_longsword_damage(self, data_loader, fighter_abilities):
        """A target resistant to slashing takes half from a longsword (slashing)."""
        fighter = _make_fighter(fighter_abilities)
        normal = _run_player_attack(data_loader, fighter, seed=7)
        resisted = _run_player_attack(data_loader, fighter, seed=7, resistances=["slashing"])

        assert normal.hit and resisted.hit
        assert normal.damage > 1, "need a non-trivial hit to observe halving"
        assert resisted.damage == normal.damage // 2

    def test_slashing_vulnerability_doubles_longsword_damage(self, data_loader, fighter_abilities):
        """A target vulnerable to slashing takes double from a longsword."""
        fighter = _make_fighter(fighter_abilities)
        normal = _run_player_attack(data_loader, fighter, seed=7)
        vulnerable = _run_player_attack(
            data_loader, fighter, seed=7, vulnerabilities=["slashing"]
        )

        assert normal.hit and vulnerable.hit
        assert vulnerable.damage == normal.damage * 2

    def test_unarmed_strike_deals_bludgeoning(self, data_loader, fighter_abilities):
        """An unarmed strike is bludgeoning, so bludgeoning resistance halves it."""
        fighter = _make_fighter(fighter_abilities, with_weapon=False)
        normal = _run_player_attack(data_loader, fighter, seed=7)
        resisted = _run_player_attack(
            data_loader, fighter, seed=7, resistances=["bludgeoning"]
        )

        assert normal.hit and resisted.hit
        assert normal.damage > 1
        assert resisted.damage == normal.damage // 2


def _run_enemy_turn(data_loader, *, seed, resistances=None):
    """Run one goblin enemy turn (Scimitar → slashing) against a PC that always
    gets hit. Returns the AttackResult. Same seed -> identical rolls.
    """
    dice_roller = DiceRoller(seed=seed)
    fighter = Character(
        name="Conan",
        character_class=CharacterClass.FIGHTER,
        level=3,
        abilities=Abilities(16, 12, 14, 10, 10, 10),
        max_hp=999,  # survives, so damage is never HP-capped
        ac=1,  # guarantees the goblin lands its attack
    )
    if resistances:
        fighter.damage_resistances = resistances
    goblin = Creature(name="Goblin", max_hp=7, ac=13, abilities=Abilities(8, 14, 10, 10, 8, 8))
    gs = GameState(
        party=Party([fighter]),
        dungeon_name="test_dungeon",
        event_bus=EventBus(),
        data_loader=data_loader,
        dice_roller=dice_roller,
    )
    gs.active_enemies = [goblin]
    gs.in_combat = True
    gs.initiative_tracker = InitiativeTracker(dice_roller=dice_roller)
    gs.initiative_tracker.combatants = [
        InitiativeEntry(creature=goblin, initiative_roll=20),
        InitiativeEntry(creature=fighter, initiative_roll=10),
    ]
    gs.initiative_tracker.turn_states[goblin] = TurnState()
    gs.initiative_tracker.turn_states[fighter] = TurnState()
    gs.initiative_tracker.round_number = 1
    return gs.process_enemy_turn().attack_result


class TestEnemyTurnDamageType:
    def test_enemy_attack_respects_target_resistance(self, data_loader):
        """A PC resistant to slashing takes half from the goblin's Scimitar."""
        normal = _run_enemy_turn(data_loader, seed=7)
        resisted = _run_enemy_turn(data_loader, seed=7, resistances=["slashing"])

        assert normal.hit and resisted.hit
        assert normal.damage > 1
        assert resisted.damage == normal.damage // 2
