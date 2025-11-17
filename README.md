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

# Enable debug logging
dnd-game --debug
```

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

🚧 **Currently in development** - This is an MVP implementation focused on core gameplay mechanics.

See [MVP.md](MVP.md) for detailed architecture and implementation plans.

## Future Enhancements

- Additional character classes (Rogue, Cleric)
- Spellcasting system
- Character creation and leveling
- Multiple dungeons and campaigns
- Quest system with branching outcomes
- Web-based UI
- Save/load functionality

## Contributing

Contributions welcome! This project prioritizes clean, testable, maintainable code architecture.

## License

MIT License - see [LICENSE](LICENSE) file for details

## Acknowledgments

- Built on D&D 5E System Reference Document (SRD)
- Narrative enhancement powered by Anthropic's Claude
