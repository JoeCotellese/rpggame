# D&D 5E SRD Terminal Game

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

A Python-based terminal game for running D&D 5E SRD adventures with LLM-enhanced narrative. Play classic dungeon-crawling adventures with tactical combat and dynamic storytelling powered by Claude AI.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Command-Line Options](#command-line-options)
- [Debug Mode](#debug-mode)
- [Debug Console](#debug-console)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

## Overview

This project delivers a command-line interface (CLI) D&D gaming experience built on an extensible engine architecture. The game separates deterministic mechanics (dice rolls, combat rules, HP tracking) from creative narrative generation (room descriptions, combat flavor, NPC dialogue), creating an immersive tabletop RPG experience in your terminal.

## Features

### Core Gameplay
- **Tactical Turn-Based Combat**: Full D&D 5E combat rules including initiative, attack rolls, damage calculation, and critical hits
- **Multiple Character Classes**: Fighter, Cleric, and Wizard with class-specific abilities
- **Party System**: Control multiple characters in your adventuring party
- **Save/Load System**: Save your progress and continue later

### Technical Features
- **LLM-Enhanced Narrative**: Dynamic descriptions and storytelling powered by Claude AI (optional)
- **Event-Driven Architecture**: Modular design with clean separation between game engine, narrative layer, and UI
- **Data-Driven Content**: All monsters, dungeons, and items defined in JSON for easy customization
- **Extensible Design**: Add new content, rule systems, or LLM providers without modifying core engine

## Requirements

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip for package management
- Anthropic API key or OpenAI API key (optional - game works without LLM)

## Installation

### Prerequisites

Install `uv` if you haven't already:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with Homebrew
brew install uv
```

### From Source

```bash
# Clone the repository
git clone https://github.com/JoeCotellese/rpggame.git
cd rpggame

# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install in editable mode with dev dependencies
uv pip install -e ".[dev]"
```

### User Installation

```bash
# Install from source
uv pip install .
```

## Quick Start

```bash
# Start the game
dnd-game

# Or run as Python module
python -m dnd_engine.main
```

The game will guide you through:
1. Character creation or selection
2. Party formation
3. Dungeon selection
4. Your adventure begins!

## Configuration

Create a `.env` file in the project root (optional):

```bash
# LLM Provider (optional - game works without LLM)
LLM_PROVIDER=anthropic

# Anthropic Configuration
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL=claude-3-5-haiku-20241022

# OR OpenAI Configuration
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-your-key-here
# OPENAI_MODEL=gpt-4o-mini

# LLM Settings
LLM_TIMEOUT=10
LLM_MAX_TOKENS=150
```

See `.env.example` for all configuration options.

## Command-Line Options

```bash
dnd-game --help              # Show help
dnd-game --version           # Show version
dnd-game --no-llm            # Disable LLM narrative enhancement
dnd-game --llm-provider anthropic  # Use specific LLM provider
dnd-game --dungeon crypt     # Choose starting dungeon
dnd-game --debug             # Enable debug mode with file logging
```

## Debug Mode

The `--debug` flag enables comprehensive file logging:

- **Log Location**: `logs/dnd_game_YYYYMMDD_HHMMSS.log`
- **Log Rotation**: Keeps the last 10 log files
- **Captures**: Events, dice rolls, LLM calls, combat actions, player inputs

Example log output:
```
[2025-01-17 14:30:45] [EVENT #001] COMBAT_START: {enemies=['Goblin', 'Orc']}
[2025-01-17 14:30:52] [DICE] 1d20+5 → [15] + 5 = 20
[2025-01-17 14:30:52] [DICE] 1d8+3 → [6] + 3 = 9
```

## Debug Console

Enable the debug console for development and testing:

```bash
DEBUG_MODE=true dnd-game
```

Available command categories:
- **Character**: `/revive`, `/kill`, `/sethp`, `/damage`, `/heal`, `/godmode`, `/setlevel`, `/addxp`
- **Combat**: `/spawn`, `/despawn`, `/nextturn`, `/endcombat`
- **Inventory**: `/give`, `/remove`, `/gold`, `/clearinventory`
- **Conditions**: `/addcondition`, `/removecondition`, `/clearconditions`
- **Resources**: `/setslots`, `/restoreslots`, `/shortrest`, `/longrest`
- **Navigation**: `/teleport`, `/listrooms`, `/unlock`, `/reveal`
- **Spells**: `/learnspell`, `/forgetspell`, `/listspells`

Use `/help` in-game for the complete command reference.

## Testing

```bash
# Run all tests with coverage
pytest

# Run specific test categories
pytest tests/test_main.py              # Unit tests
pytest tests/test_main_integration.py  # Integration tests
pytest tests/test_main_e2e.py          # End-to-end tests

# Run tests without coverage
pytest --no-cov
```

## Project Structure

```
rpggame/
├── dnd_engine/
│   ├── core/           # Core game mechanics
│   ├── systems/        # Game subsystems (initiative, inventory, conditions)
│   ├── rules/          # Rule loading and validation
│   ├── data/           # Game content (JSON)
│   │   ├── srd/        # D&D 5E SRD content
│   │   └── content/    # Dungeons and encounters
│   ├── llm/            # LLM integration layer
│   ├── ui/             # User interfaces
│   └── utils/          # Utilities (events, logging)
├── tests/              # Test suite
├── docs/               # Documentation
├── logs/               # Debug logs (generated)
└── saves/              # Save files (generated)
```

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

### Design Principles

- **Separation of Concerns**: Game rules, content, narrative enhancement, and UI are completely separated
- **Data-Driven**: All content stored in JSON, not hardcoded
- **Event-Driven**: Components communicate via event bus for loose coupling
- **Extensible**: Plugin architecture for new rule systems, content, or LLM providers
- **Testable**: Each component can be unit tested independently

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture and implementation details |
| [ROADMAP.md](docs/ROADMAP.md) | Development roadmap and planned features |
| [DEBUG_LLM.md](docs/DEBUG_LLM.md) | Debug LLM provider documentation |
| [CLAUDE.md](CLAUDE.md) | Development standards and coding practices |

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run the test suite (`pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Guidelines

- Follow PEP 8 and use type hints
- Write tests for new functionality
- Keep commits focused and atomic
- Update documentation as needed

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built on the [D&D 5E System Reference Document (SRD)](https://dnd.wizards.com/resources/systems-reference-document)
- Narrative enhancement powered by [Anthropic's Claude](https://www.anthropic.com/)
- Terminal UI built with [Rich](https://github.com/Textualize/rich) and [Questionary](https://github.com/tmbo/questionary)
