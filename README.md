# D&D 5E SRD Terminal Game

A Python-based terminal game for running D&D 5E SRD adventures with LLM-enhanced narrative. Play classic dungeon-crawling adventures with tactical combat and dynamic storytelling powered by Claude AI.

## Overview

This project delivers a command-line interface (CLI) D&D gaming experience built on an extensible engine architecture. The game separates deterministic mechanics (dice rolls, combat rules, HP tracking) from creative narrative generation (room descriptions, combat flavor, NPC dialogue), creating an immersive tabletop RPG experience in your terminal.

## Key Features

- **Tactical Turn-Based Combat**: Full D&D 5E combat rules including initiative, attack rolls, damage calculation, and critical hits
- **LLM-Enhanced Narrative**: Dynamic descriptions and storytelling powered by Claude AI
- **Event-Driven Architecture**: Modular design with clean separation between game engine, narrative layer, and UI
- **Data-Driven Content**: All monsters, dungeons, and items defined in JSON for easy customization
- **Extensible Plugin System**: Add new content, rule systems, or LLM providers without modifying core engine

## MVP Features

- Single character class (Fighter, levels 1-3)
- Basic combat system with initiative, attacks, and damage
- Simple dungeon with 5-7 connected rooms
- 3-4 enemy types with varying difficulty
- Basic inventory system (weapons, armor, potions, gold)
- LLM-enhanced room descriptions and combat narration
- Core actions: movement, combat, searching, item usage

## Architecture

```
┌─────────────────────────────────────┐
│           UI Layer (CLI)            │
└─────────────────────────────────────┘
                 ↓↑
┌─────────────────────────────────────┐
│      LLM Enhancement Layer          │
│  (Narrative, Dialogue, Descriptions)│
└─────────────────────────────────────┘
                 ↓↑
┌─────────────────────────────────────┐
│         Event Bus                   │
│  (Pub/Sub for game events)          │
└─────────────────────────────────────┘
                 ↓↑
┌─────────────────────────────────────┐
│       Game Engine Core              │
│  (Rules, Combat, State Management)  │
└─────────────────────────────────────┘
                 ↓↑
┌─────────────────────────────────────┐
│         Data Layer                  │
│  (JSON: Monsters, Spells, Dungeons) │
└─────────────────────────────────────┘
```

## Core Design Principles

- **Separation of Concerns**: Game rules, content, narrative enhancement, and UI are completely separated
- **Data-Driven**: All content (monsters, items, spells, dungeons) stored in JSON, not hardcoded
- **Event-Driven**: Components communicate via event bus, enabling loose coupling
- **Extensible**: Plugin architecture allows adding new rule systems, content, or LLM providers
- **Testable**: Each component can be unit tested independently

## Requirements

- Python 3.11+
- OpenAI API key or Anthropic API key (optional - game works without LLM)

## Installation

### From Source (Development)

```bash
# Clone the repository
git clone https://github.com/yourusername/rpggame.git
cd rpggame

# Create virtual environment with uv
uv venv

# Activate virtual environment
source .venv/bin/activate  # On Linux/Mac
# .venv\Scripts\activate   # On Windows

# Install in editable mode with dev dependencies
uv pip install -e ".[dev]"
```

### User Installation

```bash
# Install from source
uv pip install .

# Or install in editable mode for development
uv pip install -e .
```

### Configuration

Create a `.env` file in the project root (optional):

```bash
# LLM Provider (optional - game works without LLM)
LLM_PROVIDER=openai

# OpenAI Configuration
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini

# OR Anthropic Configuration
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-ant-your-key-here
# ANTHROPIC_MODEL=claude-3-5-haiku-20241022

# LLM Settings
LLM_TIMEOUT=10
LLM_MAX_TOKENS=150
```

See `.env.example` for all configuration options.

## Quick Start

```bash
# Start the game (default settings)
dnd-game

# Or run as Python module
python -m dnd_engine.main
```

The game will:
1. Display a banner
2. Check configuration
3. Guide you through character creation
4. Start your adventure!

## Command-Line Options

```bash
# Get help
dnd-game --help

# Show version
dnd-game --version

# Disable LLM narrative enhancement
dnd-game --no-llm

# Use specific LLM provider
dnd-game --llm-provider openai      # Use OpenAI (default)
dnd-game --llm-provider anthropic   # Use Anthropic Claude
dnd-game --llm-provider none        # Disable LLM

# Choose starting dungeon
dnd-game --dungeon goblin_warren    # Default dungeon
dnd-game --dungeon crypt            # Alternative dungeon

# Enable debug mode with file logging
dnd-game --debug
```

## Debug Mode

The `--debug` flag enables comprehensive file logging for troubleshooting and analysis:

### Features

- **Dual Output**: All console output is written to both the terminal and a log file
- **Structured Logging**: Events, dice rolls, LLM calls, combat actions, and player inputs are logged with timestamps
- **Log Rotation**: Automatically keeps the last 10 log files, deleting older ones
- **Plain Text Format**: Log files are human-readable plain text (ANSI codes stripped)
- **UTF-8 Encoding**: Full support for unicode characters and special symbols

### Log File Location

When debug mode is enabled, log files are created in the `logs/` directory with the pattern:
```
logs/dnd_game_YYYYMMDD_HHMMSS.log
```

Example: `logs/dnd_game_20250117_143052.log`

### What Gets Logged

Debug mode captures:

- **[EVENT]** All game events (combat start/end, damage dealt, items acquired, etc.) with event counter and metadata
- **[DICE]** Every dice roll with notation, individual rolls, modifiers, and totals (e.g., `1d20+5 → [15] + 5 = 20`)
- **[LLM]** LLM API calls with prompt type, latency, response length, and success/failure status
- **[COMBAT]** Combat events including initiative order, round transitions, and victory/defeat
- **[PLAYER]** Player actions and inputs (movement, attacks, item usage)

### Example Log Output

```
[2025-01-17 14:30:45] [INFO] dnd_engine.events: [EVENT #001] COMBAT_START: {enemies=['Goblin', 'Orc']}
[2025-01-17 14:30:45] [INFO] dnd_engine.combat: [COMBAT] Combat started - Initiative order: Aragorn(18), Goblin(12), Orc(8)
[2025-01-17 14:30:52] [INFO] dnd_engine.player: [PLAYER] Aragorn: attack (target=Goblin)
[2025-01-17 14:30:52] [INFO] dnd_engine.dice: [DICE] 1d20+5 → [15] + 5 = 20
[2025-01-17 14:30:52] [INFO] dnd_engine.dice: [DICE] 1d8+3 → [6] + 3 = 9
[2025-01-17 14:30:52] [INFO] dnd_engine.events: [EVENT #002] DAMAGE_DEALT: {attacker=Aragorn, defender=Goblin, damage=9}
[2025-01-17 14:30:53] [INFO] dnd_engine.llm: [LLM] combat_action - SUCCESS - 245ms - 87 chars
```

### Troubleshooting with Debug Logs

When reporting issues:

1. Run the game with `--debug` flag
2. Reproduce the issue
3. Locate the log file in the `logs/` directory
4. Attach the log file to your bug report

### Performance

Debug mode uses buffered file I/O and should not noticeably impact game performance. If file writes fail, the game continues without crashing.

## Usage Examples

```bash
# Standard game start with LLM
dnd-game

# Quick start without LLM
dnd-game --no-llm

# Use Claude for narrative
dnd-game --llm-provider anthropic

# Start in a specific dungeon
dnd-game --dungeon dragon_lair

# Debug mode for troubleshooting
dnd-game --debug
```

## Debug Console

The debug console provides slash commands for rapid game state manipulation during development and QA testing. Debug mode must be enabled via the `DEBUG_MODE` environment variable.

### Enabling Debug Mode

```bash
# Enable debug console
export DEBUG_MODE=true

# Run the game
dnd-game

# Or combine with other flags
DEBUG_MODE=true dnd-game --no-llm
```

### Available Commands

The debug console provides 34+ slash commands organized into 7 categories:

#### Character Manipulation
```bash
/revive <character>              # Revive dead/unconscious character
/kill <target>                   # Kill character or monster
/sethp <character> <amount>      # Set exact HP value
/damage <character> <amount>     # Deal damage for testing
/heal <character> <amount>       # Direct healing
/godmode <character>             # Toggle invulnerability
/setlevel <character> <level>    # Jump to specific level (1-20)
/addxp <character> <amount>      # Grant XP without combat
/setstat <character> <ability> <value>  # Modify STR/DEX/CON/INT/WIS/CHA
```

#### Combat Testing
```bash
/spawn <monster> [count]         # Spawn enemies in current room
/despawn <target>                # Remove monster from combat
/nextturn                        # Skip to next turn in initiative
/endcombat                       # Force end combat encounter
```

#### Inventory & Currency
```bash
/give <item> <quantity>          # Spawn any item from items.json
/remove <item> <quantity>        # Remove items from inventory
/gold <amount>                   # Add/remove gold (negative to remove)
/clearinventory <character>      # Empty inventory (with confirmation)
```

#### Condition Testing
```bash
/addcondition <character> <condition>    # Apply status effects
/removecondition <character> <condition> # Clear specific condition
/clearconditions <character>             # Remove all conditions
/listconditions                          # Show available conditions
```

#### Resource Management
```bash
/setslots <character> <level> <count>    # Set spell slot counts
/restoreslots <character>                # Restore all spell slots
/setresource <character> <resource> <amount>  # Modify resource pools
/shortrest                               # Instant short rest (party)
/longrest                                # Instant long rest (party)
```

#### Navigation & Exploration
```bash
/teleport <room_id>              # Jump to any room instantly
/listrooms                       # Display all rooms in dungeon
/unlock <direction>              # Bypass locked doors
/reveal                          # Show all hidden features
```

#### Spellcasting
```bash
/learnspell <character> <spell>  # Add spell to known/prepared
/forgetspell <character> <spell> # Remove spell from character
/listspells [class] [level]      # Browse spells with filters
```

#### System
```bash
/help                            # Show all debug commands
/help <command>                  # Show help for specific command
/reset                           # Reset dungeon, keep party
```

### Usage Examples

#### Test Death Mechanics
```bash
/sethp Gandalf 1
/damage Gandalf 10
# Test death saves, stabilize mechanics
```

#### Test Level Progression
```bash
/setlevel Aragorn 5
/addxp Aragorn 6500
# Verify level-up grants correct features
```

#### Demo Boss Fight
```bash
/teleport boss_room
/setlevel party 10
/longrest
# Jump straight to showcase
```

#### Test Spell Slot Management
```bash
/setslots Wizard 3 0
cast Fireball
# Should fail gracefully
/restoreslots Wizard
# Should work now
```

#### Test Conditions
```bash
/addcondition Rogue on_fire
/listconditions
# Test turn-start effects
/removecondition Rogue on_fire
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=dnd_engine tests/

# Run specific test categories
pytest tests/test_main.py              # Unit tests
pytest tests/test_main_integration.py  # Integration tests
pytest tests/test_main_e2e.py          # End-to-end tests

# Verbose output
pytest -v
```

## Project Structure

```
/dnd_engine
  /core                    # Core game mechanics
  /systems                 # Game subsystems (initiative, inventory, conditions)
  /rules                   # Rule loading and validation
  /data                    # Game content (all JSON)
    /srd                   # D&D 5E SRD content
    /content               # Dungeons and encounters
  /llm                     # LLM integration layer
  /ui                      # User interfaces
  /utils                   # Utilities (events, logging)
  tests/                   # Unit tests
  main.py                  # Entry point
```

## Development Status

✅ **MVP Complete - Beyond Initial Release**

The project has successfully completed its MVP and several post-MVP features including party support, save/load system, multiple dungeons, and enhanced terminal UI.

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Current system architecture and implementation details ⭐ **START HERE**
- **[ROADMAP.md](ROADMAP.md)** - Development roadmap and planned features
- **[CLAUDE.md](CLAUDE.md)** - Development standards and coding practices
- **[docs/SPEC_HISTORICAL_2025-11.md](docs/SPEC_HISTORICAL_2025-11.md)** - Original design specification (historical reference)
- **[MVP.md](MVP.md)** - Original MVP architecture overview (historical reference)

## Future Enhancements

See [ROADMAP.md](ROADMAP.md) for the complete development roadmap. Upcoming features include:

- Spellcasting system with spell slots and targeting
- Character leveling and XP progression
- Death saves (5E-accurate mechanics)
- Quest system with branching outcomes
- Campaign system with connected dungeons
- Web-based UI (FastAPI + React)
- Multiplayer/co-op support

## Contributing

Contributions welcome! This project prioritizes clean, testable, maintainable code architecture.

## License

MIT License - see [LICENSE](LICENSE) file for details

## Acknowledgments

- Built on D&D 5E System Reference Document (SRD)
- Narrative enhancement powered by Anthropic's Claude
