#!/usr/bin/env python3
"""
Create a test party for Phase 5 testing with new consumable items.

This script creates a 4-member party optimized for testing Phase 5 features:
- Thief Rogue with Fast Hands capability
- Mixed inventory with all new consumable types
- Level 3 characters with subclasses
"""

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.party import Party
from dnd_engine.core.game_state import GameState
from dnd_engine.core.save_manager import SaveManager


def create_test_party() -> Party:
    """Create a test party with diverse characters and Phase 5 consumables."""
    party = Party()

    # 1. Tank/Leader - Human Fighter (Champion)
    tank = Character(
        name="Bjorn",
        race="human",
        character_class=CharacterClass.FIGHTER,
        level=3,
        abilities=Abilities(
            strength=16,
            dexterity=12,
            constitution=16,
            intelligence=10,
            wisdom=12,
            charisma=8
        ),
        max_hp=28,
        ac=18,
        subclass="champion"
    )
    # Tank gets defensive items
    tank.inventory.add_item("potion_of_healing", "consumables", 2)
    tank.inventory.add_item("alchemists_fire", "consumables", 2)
    tank.inventory.add_item("potion_of_fire_resistance", "consumables", 1)
    tank.inventory.add_item("longsword", "weapons", 1)
    tank.inventory.add_item("chain_mail", "armor", 1)
    tank.inventory.equip_item("longsword", "weapon")
    tank.inventory.equip_item("chain_mail", "armor")
    tank.inventory.currency.gold = 15
    party.add_character(tank)

    # 2. DPS/Scout - Halfling Rogue (Thief) - FAST HANDS!
    thief = Character(
        name="Pip",
        race="halfling",
        character_class=CharacterClass.ROGUE,
        level=3,
        abilities=Abilities(
            strength=10,
            dexterity=18,
            constitution=14,
            intelligence=12,
            wisdom=14,
            charisma=10
        ),
        max_hp=21,
        ac=15,
        subclass="thief"  # Has Fast Hands at level 3!
    )
    # Thief gets lots of consumables (Fast Hands makes them better)
    thief.inventory.add_item("potion_of_healing", "consumables", 3)
    thief.inventory.add_item("acid_vial", "consumables", 2)
    thief.inventory.add_item("antitoxin", "consumables", 2)
    thief.inventory.add_item("shortsword", "weapons", 1)
    thief.inventory.add_item("leather_armor", "armor", 1)
    thief.inventory.equip_item("shortsword", "weapon")
    thief.inventory.equip_item("leather_armor", "armor")
    thief.inventory.currency.gold = 25
    party.add_character(thief)

    # 3. Support - Human Fighter (no subclass yet at level 3)
    support = Character(
        name="Elena",
        race="human",
        character_class=CharacterClass.FIGHTER,
        level=3,
        abilities=Abilities(
            strength=14,
            dexterity=14,
            constitution=15,
            intelligence=10,
            wisdom=13,
            charisma=12
        ),
        max_hp=26,
        ac=17,
        subclass=None
    )
    # Support gets healing and curative items
    support.inventory.add_item("potion_of_healing", "consumables", 4)
    support.inventory.add_item("elixir_of_health", "consumables", 1)
    support.inventory.add_item("antitoxin", "consumables", 1)
    support.inventory.add_item("longsword", "weapons", 1)
    support.inventory.add_item("chain_mail", "armor", 1)
    support.inventory.equip_item("longsword", "weapon")
    support.inventory.equip_item("chain_mail", "armor")
    support.inventory.currency.gold = 20
    party.add_character(support)

    # 4. Ranged - High Elf Fighter (Archer build)
    archer = Character(
        name="Aelar",
        race="high_elf",
        character_class=CharacterClass.FIGHTER,
        level=3,
        abilities=Abilities(
            strength=12,
            dexterity=17,
            constitution=14,
            intelligence=14,
            wisdom=12,
            charisma=10
        ),
        max_hp=24,
        ac=16,
        subclass=None
    )
    # Archer gets ranged utility items
    archer.inventory.add_item("potion_of_healing", "consumables", 2)
    archer.inventory.add_item("alchemists_fire", "consumables", 2)
    archer.inventory.add_item("acid_vial", "consumables", 1)
    archer.inventory.add_item("longbow", "weapons", 1)
    archer.inventory.add_item("studded_leather", "armor", 1)
    archer.inventory.equip_item("longbow", "weapon")
    archer.inventory.equip_item("studded_leather", "armor")
    archer.inventory.currency.gold = 18
    party.add_character(archer)

    return party


def main():
    """Create party and save to new game."""
    print("Creating Phase 5 test party...")

    party = create_test_party()

    print(f"\nCreated party with {len(party.characters)} members:")
    for char in party.characters:
        subclass_str = f" ({char.subclass})" if char.subclass else ""
        print(f"  - {char.name}: Level {char.level} {char.race.title()} {char.character_class.value.title()}{subclass_str}")
        print(f"    HP: {char.current_hp}/{char.max_hp}, AC: {char.ac}")
        consumables = char.inventory.get_items_by_category("consumables")
        if consumables:
            print(f"    Consumables: {', '.join(f'{item.item_id} x{item.quantity}' for item in consumables)}")

    # Create game state with new party
    print("\nCreating game state with poisoned_laboratory dungeon...")
    game_state = GameState(party=party, dungeon_name="poisoned_laboratory")

    # Save the game
    print("Saving game as 'phase5-test'...")
    save_manager = SaveManager()
    save_path = save_manager.save_game(game_state, "phase5-test")

    print(f"\n✅ Test party saved to: {save_path}")
    print("\nTo load: python -m dnd_engine.main --load phase5-test")


if __name__ == "__main__":
    main()
