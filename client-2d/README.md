# D&D 5E 2D Graphical Client

A sprite-based, top-down dungeon crawler interface for the D&D 5E game engine.

## Features

- **Sprite-Based Rendering**: Categorized entity types with visual fallback hierarchies
- **D&D-Compliant Lighting**: Tile-based vision states (bright/dim/dark/unexplored)
- **Fog of War**: Exploration-based tile revelation with memory of visited areas
- **Keyboard Navigation**: Arrow keys or WASD for movement

## Installation

```bash
# From the repository root
cd client-2d
uv pip install -e ".[dev]"
```

## Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_fog_of_war.py -v
```

## Architecture

See [docs/CLIENT_2D_ARCHITECTURE.md](../docs/CLIENT_2D_ARCHITECTURE.md) for detailed architecture documentation.

## Development Status

Currently implementing Phase 1:
- [x] Fog of war system
- [x] D&D-compliant lighting (torch, lantern)
- [x] Keyboard input handling
- [x] Asset manager with sprite fallbacks
- [ ] Basic Arcade rendering (requires `[graphics]` extra)

## Phase Roadmap

1. **Phase 1**: Single-room navigation with fog of war and torch mechanics
2. **Phase 2**: GameState integration, entity rendering, movement animations
3. **Phase 3**: Combat UI with grid overlays and action menus
4. **Phase 4**: Essential overlays (HP bars, combat log, inventory)
5. **Phase 5**: Enhanced visuals (raycast lighting, audio, particles)
