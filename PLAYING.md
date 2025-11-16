# How to Play

## Starting the Game

```bash
# Make sure you're in the virtual environment
source .venv/bin/activate

# Run the game
python -m dnd_engine.main
```

## Your Character

You play as **Thorin Ironshield**, a Level 1 Fighter:
- **HP**: 12
- **AC**: 16 (chain mail)
- **Attack Bonus**: +5 (1d20+5)
- **Damage**: 1d8+3 (longsword + STR bonus)

## Game Objective

Explore the Goblin Warren dungeon, defeat all enemies, and claim the treasure!

## Commands

### Exploration Mode

- `move <direction>` or `go <direction>` - Move to another room (e.g., `move north`)
- `look` or `l` - Look around the current room
- `search` - Search the current room for hidden items (only works in some rooms)
- `status` or `stats` - View your character stats
- `help` or `?` - Show available commands
- `quit` or `exit` - Exit the game

### Combat Mode

When you enter a room with enemies, combat begins automatically!

- `attack <enemy>` - Attack an enemy (e.g., `attack goblin`)
- `status` or `stats` - View combat status and initiative order
- `help` or `?` - Show available commands

**Combat Tips:**
- Combat follows D&D 5E initiative rules (everyone rolls 1d20 + DEX modifier)
- Turns proceed in initiative order (highest first)
- You attack by rolling 1d20+5 vs the enemy's AC
- Natural 20 is always a critical hit (double damage dice)
- Natural 1 is always a miss
- Combat ends when all enemies are defeated
- You gain XP for each enemy defeated

## The Dungeon: Goblin Warren

The dungeon has 6 connected rooms:

1. **Cave Entrance** - Starting point (no enemies)
2. **Guard Post** - 2 Goblins, some gold
3. **Storage Room** - No enemies, loot (searchable!)
4. **Main Hall** - Goblin and Wolf, connected to prison and throne room
5. **Prison** - No enemies, hidden dagger (searchable!)
6. **Throne Room** - BOSS FIGHT: Goblin Boss + Goblin, best treasure!

## Enemy Types

- **Goblin**: AC 15, HP 2d6, Attack +4 for 1d6+2 damage, Worth 50 XP
- **Bandit**: AC 12, HP 2d8+2, Attack +3 for 1d6+1 damage, Worth 25 XP
- **Wolf**: AC 13, HP 2d8+2, Attack +4 for 2d4+2 damage, Worth 50 XP
- **Goblin Boss**: AC 17, HP 6d6+12, Attack +4 for 1d6+2 damage, Worth 200 XP

## Tips for Success

1. **Search rooms** - Some rooms have hidden items or extra loot
2. **Watch your HP** - If you get low, consider retreating (future: use potions!)
3. **Know your enemy** - Higher AC enemies are harder to hit
4. **Critical hits matter** - A lucky nat 20 can turn the tide of battle
5. **Initiative counts** - Going first can make a big difference

## Example Gameplay

```
> move north
You move north.

------------------------------------------------------------
Guard Post

A small chamber with crude wooden spikes pointing outward...

Exits: south, east, north
------------------------------------------------------------

⚔️  Combat begins! Enemies: Goblin, Goblin

--- Your turn ---

> attack goblin
Goblin attacks Goblin: 15+5=20 vs AC 15 - HIT for 9 damage

Goblin is defeated!

Goblin's turn...
Goblin attacks Thorin Ironshield: 12+4=16 vs AC 16 - HIT for 5 damage

--- Your turn ---

> attack goblin
Thorin Ironshield attacks Goblin: 18+5=23 vs AC 15 - HIT for 7 damage

Goblin is defeated!

✓ Victory! You gained 100 XP.
```

## Known Limitations (MVP)

This is a minimal viable product with the following limitations:
- No inventory system yet (items are found but not usable)
- No potion usage
- No save/load functionality
- No character creation (fixed character)
- No LLM-enhanced descriptions yet
- Limited combat options (attack only, no spells/abilities)

## Future Enhancements

Coming soon:
- LLM-powered narrative descriptions
- Inventory and item usage
- Multiple character classes
- More dungeons and quests
- Save/load system
- Character creation

Enjoy the game!
