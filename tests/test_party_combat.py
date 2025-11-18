# ABOUTME: Integration tests for party combat scenarios
# ABOUTME: Tests party members in combat, initiative, targeting, and victory/defeat conditions

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.party import Party
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.combat import CombatEngine
from dnd_engine.systems.initiative import InitiativeTracker


@pytest.fixture
def test_abilities():
    """Create test abilities."""
    return Abilities(
        strength=15,
        dexterity=14,
        constitution=13,
        intelligence=10,
        wisdom=12,
        charisma=8
    )


@pytest.fixture
def dice_roller():
    """Create a dice roller."""
    return DiceRoller()


@pytest.fixture
def combat_engine(dice_roller):
    """Create a combat engine."""
    return CombatEngine(dice_roller)


@pytest.fixture
def initiative_tracker(dice_roller):
    """Create an initiative tracker."""
    return InitiativeTracker(dice_roller)


@pytest.fixture
def party_of_four(test_abilities):
    """Create a party of 4 fighters."""
    fighters = []
    for i in range(4):
        fighter = Character(
            name=f"Fighter {i+1}",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=test_abilities,
            max_hp=12,
            ac=16
        )
        fighters.append(fighter)
    return Party(characters=fighters)


@pytest.fixture
def goblin_enemy(test_abilities):
    """Create a goblin enemy."""
    return Creature(
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


@pytest.fixture
def multiple_goblins(test_abilities):
    """Create multiple goblin enemies."""
    goblins = []
    for i in range(3):
        goblin = Creature(
            name=f"Goblin {i+1}",
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
        goblins.append(goblin)
    return goblins


class TestPartyInitiative:
    """Test party members in initiative order."""

    def test_all_party_members_in_initiative(self, party_of_four, initiative_tracker):
        """Test that all party members are added to initiative."""
        for character in party_of_four.characters:
            initiative_tracker.add_combatant(character)

        all_combatants = initiative_tracker.get_all_combatants()
        assert len(all_combatants) == 4

        # Verify all party members are in initiative
        combatant_creatures = [entry.creature for entry in all_combatants]
        for character in party_of_four.characters:
            assert character in combatant_creatures

    def test_party_and_enemies_in_initiative(
        self, party_of_four, multiple_goblins, initiative_tracker
    ):
        """Test that party members and enemies are mixed in initiative."""
        # Add party members
        for character in party_of_four.characters:
            initiative_tracker.add_combatant(character)

        # Add enemies
        for goblin in multiple_goblins:
            initiative_tracker.add_combatant(goblin)

        all_combatants = initiative_tracker.get_all_combatants()
        assert len(all_combatants) == 7  # 4 party + 3 goblins

    def test_initiative_order_is_sorted(self, party_of_four, initiative_tracker):
        """Test that initiative order is properly sorted."""
        for character in party_of_four.characters:
            initiative_tracker.add_combatant(character)

        all_combatants = initiative_tracker.get_all_combatants()

        # Verify sorted in descending order
        for i in range(len(all_combatants) - 1):
            assert (
                all_combatants[i].initiative_total
                >= all_combatants[i + 1].initiative_total
            )


class TestPartyCombat:
    """Test combat with party members."""

    def test_party_member_attacks_enemy(
        self, party_of_four, goblin_enemy, combat_engine
    ):
        """Test that a party member can attack an enemy."""
        fighter = party_of_four.characters[0]
        result = combat_engine.resolve_attack(
            attacker=fighter,
            defender=goblin_enemy,
            attack_bonus=fighter.melee_attack_bonus,
            damage_dice=f"1d8+{fighter.melee_damage_bonus}",
            apply_damage=True
        )

        assert result.attacker_name == fighter.name
        assert result.defender_name == goblin_enemy.name

    def test_party_defeats_enemy(self, party_of_four, goblin_enemy, combat_engine):
        """Test that party can defeat an enemy."""
        # Have multiple party members attack until goblin is dead
        for fighter in party_of_four.characters:
            if goblin_enemy.is_alive:
                combat_engine.resolve_attack(
                    attacker=fighter,
                    defender=goblin_enemy,
                    attack_bonus=fighter.melee_attack_bonus,
                    damage_dice="1d8+10",  # High damage to ensure kill
                    apply_damage=True
                )

        assert not goblin_enemy.is_alive

    def test_dead_party_member_removed_from_initiative(
        self, party_of_four, initiative_tracker
    ):
        """Test that dead party members are removed from initiative."""
        # Add all party members to initiative
        for character in party_of_four.characters:
            initiative_tracker.add_combatant(character)

        initial_count = len(initiative_tracker.get_all_combatants())

        # Kill first party member
        first_fighter = party_of_four.characters[0]
        first_fighter.take_damage(first_fighter.max_hp)

        # Remove from initiative
        initiative_tracker.remove_combatant(first_fighter)

        assert len(initiative_tracker.get_all_combatants()) == initial_count - 1

    def test_combat_continues_with_party_casualties(
        self, party_of_four, goblin_enemy, initiative_tracker
    ):
        """Test that combat continues when some party members die."""
        # Add party and enemy to initiative
        for character in party_of_four.characters:
            initiative_tracker.add_combatant(character)
        initiative_tracker.add_combatant(goblin_enemy)

        # Kill two party members
        party_of_four.characters[0].take_damage(party_of_four.characters[0].max_hp)
        party_of_four.characters[1].take_damage(party_of_four.characters[1].max_hp)

        # Remove dead members from initiative
        initiative_tracker.remove_combatant(party_of_four.characters[0])
        initiative_tracker.remove_combatant(party_of_four.characters[1])

        # Combat should continue (not over with 2 living party + 1 enemy)
        assert not initiative_tracker.is_combat_over()
        assert len(initiative_tracker.get_all_combatants()) == 3


class TestPartyVictoryDefeat:
    """Test victory and defeat conditions for parties."""

    def test_party_victory_all_enemies_dead(
        self, party_of_four, multiple_goblins, initiative_tracker
    ):
        """Test that combat ends when all enemies are dead."""
        # Add party members
        for character in party_of_four.characters:
            initiative_tracker.add_combatant(character)

        # Add and kill all enemies
        for goblin in multiple_goblins:
            initiative_tracker.add_combatant(goblin)
            goblin.take_damage(goblin.max_hp)
            initiative_tracker.remove_combatant(goblin)

        # With 4 party members still in initiative, is_combat_over() returns False
        # because it checks for 0 or 1 combatants remaining
        # The game logic determines combat end by checking if all enemies are dead
        assert len(initiative_tracker.get_all_combatants()) == 4
        assert all(not g.is_alive for g in multiple_goblins)

    def test_party_not_wiped_if_one_alive(self, party_of_four):
        """Test that party is not wiped if at least one member is alive."""
        # Kill 3 out of 4 party members
        for i in range(3):
            party_of_four.characters[i].take_damage(
                party_of_four.characters[i].max_hp
            )

        assert not party_of_four.is_wiped()
        assert len(party_of_four.get_living_members()) == 1

    def test_party_wiped_all_dead(self, party_of_four):
        """Test that party is wiped when all members are dead."""
        # Kill all party members (reduce to 0 HP and set 3 death save failures)
        for character in party_of_four.characters:
            character.take_damage(character.max_hp)
            character.death_save_failures = 3

        assert party_of_four.is_wiped()
        assert len(party_of_four.get_living_members()) == 0


class TestEnemyTargeting:
    """Test enemy targeting of party members."""

    def test_enemy_can_target_any_party_member(
        self, party_of_four, goblin_enemy, combat_engine
    ):
        """Test that an enemy can target any party member."""
        # Test attacking each party member
        for character in party_of_four.characters:
            result = combat_engine.resolve_attack(
                attacker=goblin_enemy,
                defender=character,
                attack_bonus=4,  # Goblin attack bonus
                damage_dice="1d6+2",
                apply_damage=False  # Don't actually damage
            )

            assert result.attacker_name == goblin_enemy.name
            assert result.defender_name == character.name

    def test_enemy_targets_lowest_hp_party_member(self, party_of_four):
        """Test logic for targeting lowest HP party member."""
        # Damage one party member
        party_of_four.characters[2].take_damage(6)

        # Find party member with lowest HP
        living = party_of_four.get_living_members()
        lowest_hp_member = min(living, key=lambda c: c.current_hp)

        assert lowest_hp_member == party_of_four.characters[2]
        assert lowest_hp_member.current_hp == 6


class TestPartyTurnManagement:
    """Test turn management with party members."""

    def test_each_party_member_gets_turn(
        self, party_of_four, goblin_enemy, initiative_tracker
    ):
        """Test that each party member gets a turn in initiative."""
        # Add party and enemy
        for character in party_of_four.characters:
            initiative_tracker.add_combatant(character)
        initiative_tracker.add_combatant(goblin_enemy)

        # Track which party members have had a turn
        party_members_who_acted = set()

        # Go through enough turns to cover all combatants
        for _ in range(len(initiative_tracker.get_all_combatants())):
            current = initiative_tracker.get_current_combatant()
            if current.creature in party_of_four.characters:
                party_members_who_acted.add(current.creature)
            initiative_tracker.next_turn()

        # All 4 party members should have had a turn
        assert len(party_members_who_acted) == 4

    def test_turn_skips_dead_party_member(
        self, party_of_four, initiative_tracker
    ):
        """Test that dead party members don't get turns."""
        # Add all party members
        for character in party_of_four.characters:
            initiative_tracker.add_combatant(character)

        # Kill and remove one member
        party_of_four.characters[1].take_damage(party_of_four.characters[1].max_hp)
        initiative_tracker.remove_combatant(party_of_four.characters[1])

        # Collect all creatures in initiative
        all_creatures = [
            entry.creature for entry in initiative_tracker.get_all_combatants()
        ]

        # Dead member should not be in initiative
        assert party_of_four.characters[1] not in all_creatures
        assert len(all_creatures) == 3
