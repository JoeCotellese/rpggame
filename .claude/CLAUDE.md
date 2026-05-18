# D&D 5E Terminal Game - Development Standards

## Python Development Standards

### Package Management
- Always use `uv` for package management (not pip, poetry, or conda)
- Create virtual environments local to the project directory using `uv`
- Never use global Python installations for project dependencies

### Project Setup
```bash
# Create virtual environment in project directory
uv venv

# Install dependencies
uv pip install -r requirements.txt

# Add new dependencies
uv pip install package_name
```

### Code Style and Standards
- Follow PEP 8 for code style
- Use type hints for all function signatures
- Prefer f-strings over .format() or % formatting
- Use pathlib for file operations instead of os.path
- Use dataclasses or Pydantic for data structures
- Use implicit string concatenation for long strings (ruff/black don't auto-break strings):
  ```python
  # Good: Break long strings with implicit concatenation
  message = (
      f"This is a long message with {variable} that "
      f"continues on the next line for readability."
  )
  ```

### Import Organization
```python
# Standard library imports
import os
import sys
from pathlib import Path

# Third-party imports
import pandas as pd
import numpy as np

# Local application imports
from dnd_engine.core import dice
from dnd_engine.utils import helpers
```

### Testing Philosophy
- Use pytest for testing framework
- Place tests in a `tests/` directory
- Name test files with `test_` prefix
- Use fixtures for common test setup
- Aim for high test coverage (>80%)
- Tests MUST cover the functionality being implemented
- NEVER ignore the output of the system or the tests - Logs and messages often contain CRITICAL information
- TEST OUTPUT MUST BE PRISTINE TO PASS
- If the logs are supposed to contain errors, capture and test it

### Test Types and When to Use Each

#### Unit Tests (test_*.py)
- Test individual functions and classes in isolation
- Mock external dependencies
- Fast execution (milliseconds per test)
- Use for: business logic, data transformations, utility functions
- Example: test_dice.py, test_character.py

#### Integration Tests (test_*_integration.py)
- Test how multiple components work together
- Mock only external I/O (network, filesystem, user input)
- Medium execution time (seconds per test)
- Use for: testing interactions between systems, event flows, state management
- Example: test_inventory_integration.py, test_llm_enhancer_integration.py

#### End-to-End Tests (test_*_e2e.py)
- ONLY write true e2e tests - DO NOT mock the application behavior
- If you find yourself mocking core application logic, write a unit or integration test instead
- E2E tests should test actual user workflows with minimal mocking
- Use tools like `pexpect` for interactive CLI testing, not mocked subprocesses
- Slow execution (seconds to minutes per test)
- Use for: complete user workflows, actual CLI interaction, real file I/O
- **CRITICAL**: Do not write "fake" e2e tests that heavily mock everything - those are just slow unit tests
- If an e2e test mocks CharacterFactory, CLI, input(), etc., delete it and write proper unit tests instead

#### NO EXCEPTIONS POLICY
- Every feature MUST have unit tests
- Features that integrate multiple systems MUST have integration tests
- Only write e2e tests for true end-to-end workflows worth the overhead
- Never mark any required test type as "not applicable"

### TDD Practice
- Write failing test → write minimal code to pass → refactor → repeat
- Only write enough code to make the test pass

### Async Programming
- Use asyncio for concurrent operations
- Prefer async/await over threading for I/O operations
- Use aiohttp for async HTTP requests
- LLM calls should be async and non-blocking

### Error Handling
- Use specific exception types, not bare except
- Log errors appropriately
- Provide user-friendly error messages
- Use context managers for resource management

### Documentation
- Use docstrings for all public functions and classes
- Follow Google or NumPy docstring style consistently
- Include type hints in function signatures
- Document complex algorithms and business logic
- All code files should start with a brief 2 line comment explaining what the file does
- Each line of the comment should start with the string "ABOUTME: " to make it easy to grep for
- When writing comments, avoid referring to temporal context about refactors or recent changes
- Comments should be evergreen and describe the code as it is, not how it evolved

### Common Libraries for This Project
- **Testing**: pytest with pytest-asyncio for async tests
- **LLM**: anthropic (Claude API)
- **Data Validation**: pydantic
- **Linting**: ruff (preferred) or flake8 + black
- **Type Checking**: mypy or pyright

### Security
- Never hardcode secrets or API keys
- Use environment variables for configuration (ANTHROPIC_API_KEY)
- Validate all user inputs
- Keep dependencies updated

## General Code Standards

### Code Quality
- CRITICAL: NEVER USE --no-verify WHEN COMMITTING CODE
- Prefer simple, clean, maintainable solutions over clever or complex ones
- Readability and maintainability are primary concerns
- MUST ask permission before reimplementing features from scratch instead of updating existing implementation
- Match the style and formatting of surrounding code
- Consistency within a file is more important than strict adherence to external standards

### Code Changes
- NEVER make code changes that aren't directly related to the current task
- If you notice something unrelated that should be fixed, document it in a new issue instead
- NEVER remove code comments unless you can prove that they are actively false
- Comments are important documentation and should be preserved
- NEVER throw away old implementation and rewrite without explicit permission
- NEVER name things as 'improved' or 'new' or 'enhanced' - code naming should be evergreen

## Development Workflow

### Tooling for shell interactions
- Is it about finding FILES? use 'fd'
- Is it about finding TEXT/strings? use 'rg'
- Is it about finding CODE STRUCTURE? use 'ast-grep'
- Is it about SELECTING from multiple results? pipe to 'fzf'
- Is it about interacting with JSON? use 'jq'
- Is it about interacting with YAML or XML? use 'yq'
- Use `tldr` tool when trying to figure out the syntax of a 3rd party tool

### Small, Iterative Changes
- Work in small, testable increments - implement, test with human in the loop, then continue
- Make the smallest reasonable changes to achieve the desired outcome
- Break down work into small, iterable, testable chunks
- Always discuss plans before implementation unless explicitly told otherwise

## Project-Specific Architecture Principles

### Separation of Concerns
- Game rules, content, narrative enhancement, and UI are completely separated
- Game engine handles deterministic mechanics only
- LLM layer handles narrative enhancement only
- Event bus coordinates communication between layers

### Data-Driven Design
- All content (monsters, items, spells, dungeons) stored in JSON, not hardcoded
- Content should be easily modifiable without code changes

### Event-Driven Architecture
- Components communicate via event bus
- Loose coupling enables extensibility and testability
- Each component can be unit tested independently

### Extensibility
- Plugin architecture allows adding new rule systems, content, or LLM providers
- Clear interfaces for extending core systems

## 2D Graphical Client (client-2d)

The project includes a 2D graphical client built with **Python Arcade**.

### Framework & Documentation
- Uses Python Arcade (arcade library) for rendering
- For up-to-date Arcade documentation, use the `docs-server` MCP with library 'arcade'
- Entry point: `dnd-2d` command (or `uv run dnd-2d`)

### Architecture
```
client-2d/
├── src/client_2d/
│   ├── core/          # Constants, game mode enums
│   ├── rendering/     # Map, entity, fog rendering
│   ├── systems/       # Fog of war, lighting, animation
│   ├── input/         # Keyboard handling
│   ├── assets/        # Sprite/asset loading with fallbacks
│   ├── ui/            # UI overlays (HP bars, menus)
│   └── integration/   # Event bridge to dnd-engine
├── assets/            # Sprites, tilesets, maps
├── tests/             # Test suite
└── scripts/           # visual_test.py demo
```

### Key Systems
- **InputHandler**: Maps keyboard events to game actions (WASD/arrows for movement)
- **FogOfWarSystem**: D&D 5E compliant visibility (unexplored/dark/dim/bright)
- **LightingSystem**: Calculates illumination from light sources (torch, lantern, darkvision)
- **AssetManager**: Loads sprites with hierarchical fallback system
- **SpriteResolver**: Resolves sprite paths (exact match → category → generic fallback)

### Running the Visual Demo
```bash
cd client-2d
uv run python scripts/visual_test.py
```
- WASD/Arrows: Move
- L: Cycle light modes
- ESC: Quit

### Testing the 2D Client
```bash
cd client-2d
uv run pytest tests/
```

### Claude-Driven Playtesting (MCP Server)

The project includes an MCP server that allows Claude to playtest the game directly via tool calls, acting as a human player interacting with the client.

**Architecture:**
```
Claude Code ◄──MCP──► Game MCP Server ◄──► client-2d (player view) ◄──► dnd-engine
```

**Enabling the MCP Server:**
```bash
# Add to project scope (already configured in .mcp.json)
claude mcp add -s project dnd-game /path/to/client-2d/scripts/run_mcp_server.sh
```

**Available Tools:**
| Tool | Description |
|------|-------------|
| `game_new()` | Start a new game session |
| `game_state()` | Get current state (ASCII map + JSON) |
| `game_move(direction)` | Move north/south/east/west |
| `game_attack(target)` | Attack adjacent enemy |
| `game_interact(target)` | Interact with adjacent object |
| `game_wait()` | Wait one turn |

**ASCII Map Legend:**
- `@` = Player
- `A-Z` = Entities (see legend in output)
- `#` = Wall
- `.` = Floor (bright light)
- `,` = Floor (dim light)
- `:` = Floor (dark/remembered)
- ` ` = Unexplored

**State Output Includes:**
- ASCII map with fog of war
- Player position, HP, light source
- Visible entities with distance and direction
- Available actions for current position

**Example Session:**
```
> game_new()
Turn: 0, Player: [20, 14], HP: 30/30
Map shows @ surrounded by fog of war...

> game_move("east")
Moved east. Turn: 1, Player: [21, 14]
New areas revealed, entities come into view...

> game_attack("goblin_1")
Attacked goblin_1! Enemy defeated.
```

### Headless Mode (issue #362)

The 2D client can run **without an arcade window** — engine + entity manager + MCP HTTP server only. Faster to launch, lower resource use, no window stealing focus, CI-friendly.

```bash
# Headless + dev tools + MCP (preferred for automated playtesting)
uv run dnd-2d --headless --dev --mcp [--mcp-port 8765]
```

`--headless` implies `--mcp`. SIGINT / SIGTERM exit the tick loop cleanly. Combat state machine ticks at ~30 Hz so MCP commands drain promptly.

**Architecture:** A `GameSession` class (`client-2d/src/client_2d/session.py`) owns the non-graphical state — engine adapter, entity manager, MCP plumbing, combat state machine, fog/lighting, room layout. Both `GameWindow` (windowed mode) and `run_headless()` instantiate one; the windowed mode adds rendering on top. All MCP tools behave identically in both modes because they route through `GameSession`.

### Playtester Skill

Use the `/playtester` skill (or say "let's playtest", "test our fix", "qa the game") to have Claude QA the game through the embedded MCP server.

**What it does:**
- Starts game with `uv run dnd-2d --headless --dev --mcp` (or `--mcp` only when visual inspection is needed)
- Plays the game using MCP tools as a human would
- If working on a ticket, focuses testing on that functionality
- Creates GitHub issues for bugs found
- Stops on blocking bugs, continues logging non-blocking issues

**When to use headless vs windowed:**
- **Headless (default):** scripted scenario runs, regression checks, anything driven by MCP only. Faster, doesn't steal focus.
- **Windowed:** when you need to see fog-of-war, sprites, or any visual rendering to diagnose a bug.
