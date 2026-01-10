# Epic: 2D Dungeon Crawler Mode

Transform the text-based D&D 5E terminal game into a visual 2D dungeon crawler while preserving all existing game mechanics.

## Overview

This epic adds grid-based spatial positioning, ASCII/terminal rendering, and real-time movement to create an immersive dungeon crawling experience. The existing event-driven architecture makes this feasible without major refactoring.

## Goals

- **Visual exploration**: See the dungeon as a 2D map with player position
- **Grid-based movement**: WASD/arrow key movement on tile grid
- **Fog of war**: Discover the dungeon as you explore
- **Preserve mechanics**: All D&D 5E rules, combat, LLM enhancement unchanged
- **Backward compatible**: Text mode still available

## Architecture

```
┌─────────────────────────────────────────┐
│  NEW: Spatial Layer (dnd_engine/spatial)│
│  - TileMap, Position, Grid management   │
│  - Field of View (shadowcasting)        │
│  - Pathfinding (A* for AI)              │
└──────────────────┬──────────────────────┘
                   ↓ Events
┌─────────────────────────────────────────┐
│  NEW: 2D Renderer (dnd_engine/ui)       │
│  - ASCII grid rendering via Rich        │
│  - Entity display (@, G, etc.)          │
│  - Fog of war visualization             │
└──────────────────┬──────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│  EXISTING: Game Engine (unchanged)      │
│  - Combat, dice, HP, damage, spells     │
│  - Event bus, LLM enhancement           │
└─────────────────────────────────────────┘
```

## Implementation Plan

### Phase 1: Spatial Foundation
**Goal**: Core grid data structures and positioning

- [ ] Create `dnd_engine/spatial/` module
- [ ] Implement `Position` dataclass (x, y coordinates)
- [ ] Implement `Tile` dataclass (type, walkable, blocks_sight, contents)
- [ ] Implement `TileMap` class (2D grid, entity tracking)
- [ ] Add spatial event types (ENTITY_MOVED, TILE_REVEALED, MAP_LOADED)
- [ ] Unit tests for spatial primitives

### Phase 2: Map Data Format
**Goal**: JSON-based map definitions

- [ ] Design map JSON schema (tiles, legend, spawns, connections)
- [ ] Implement `MapLoader` to parse map JSON
- [ ] Convert `poisoned_laboratory` dungeon to grid format
- [ ] Create map validation utilities
- [ ] Unit tests for map loading

### Phase 3: ASCII Renderer
**Goal**: Visual grid display in terminal

- [ ] Implement `GridRenderer` class using Rich
- [ ] Tile-to-character mapping (walls=#, floor=., door=+)
- [ ] Entity rendering (@=player, G=goblin, etc.)
- [ ] Color coding (walls=gray, player=green, enemies=red)
- [ ] Status panel (HP, location, etc.)
- [ ] Subscribe to spatial events for re-rendering

### Phase 4: Movement System
**Goal**: Real-time grid movement

- [ ] Implement movement input handler (WASD/arrows)
- [ ] Collision detection (walls, entities)
- [ ] Movement cost tracking (for 5E movement rules)
- [ ] Door interaction (open/close)
- [ ] Emit ENTITY_MOVED events
- [ ] Integration tests for movement

### Phase 5: Field of View
**Goal**: Fog of war and visibility

- [ ] Implement shadowcasting FOV algorithm
- [ ] Track tile states: unexplored, explored, visible
- [ ] Update visibility on player movement
- [ ] Render fog of war (dim explored, hide unexplored)
- [ ] Light source integration (torches affect FOV radius)

### Phase 6: Combat Integration
**Goal**: Grid-aware combat

- [ ] Calculate range from grid distance
- [ ] Melee range = adjacent tiles (5ft)
- [ ] Ranged attacks use actual distance
- [ ] Movement during combat turns
- [ ] Enemy AI pathfinding to targets
- [ ] Opportunity attacks on movement (optional)

### Phase 7: Game Mode Integration
**Goal**: Seamless mode switching

- [ ] Add `--mode 2d` CLI flag
- [ ] GameState tracks spatial data when in 2D mode
- [ ] Save/load includes grid positions
- [ ] Room transitions update grid map
- [ ] Existing text commands still work alongside movement

## Map JSON Format

```json
{
  "id": "crypt_level_1",
  "name": "The Crypt - Level 1",
  "width": 50,
  "height": 30,
  "tiles": [
    "##################################################",
    "#................................................#",
    "#..###..........@..........G.....###.............#",
    "#..#.#.........................../..#.............#"
  ],
  "legend": {
    "#": {"type": "wall", "walkable": false, "blocks_sight": true},
    ".": {"type": "floor", "walkable": true, "blocks_sight": false},
    "/": {"type": "door", "walkable": true, "blocks_sight": true, "interactive": true},
    "@": {"type": "floor", "spawn": "player"},
    "G": {"type": "floor", "spawn": {"monster": "goblin"}}
  },
  "regions": {
    "entrance": {"x1": 0, "y1": 0, "x2": 15, "y2": 10},
    "main_hall": {"x1": 16, "y1": 0, "x2": 35, "y2": 15}
  },
  "connections": [
    {"type": "stairs_down", "x": 45, "y": 25, "target_map": "crypt_level_2", "target_x": 5, "target_y": 5}
  ]
}
```

## Rendering Example

```
╔══════════════════════════════════════════════════════╗
║  The Crypt - Level 1                    HP: 15/15    ║
╠══════════════════════════════════════════════════════╣
║  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  ║
║  ░░████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  ║
║  ░░█......█░░░░░░░░░░████████░░░░░░░░░░░░░░░░░░░░░░  ║
║  ░░█..@...+........../......█░░░░░░░░░░░░░░░░░░░░░░  ║
║  ░░█......█...........█.G...█░░░░░░░░░░░░░░░░░░░░░░  ║
║  ░░████████░░░░░░░░░░████████░░░░░░░░░░░░░░░░░░░░░░  ║
║  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  ║
╠══════════════════════════════════════════════════════╣
║  [G]oblin spotted to the east!                       ║
║  > _                                                 ║
╚══════════════════════════════════════════════════════╝

Legend: @ = You  G = Goblin  █ = Wall  . = Floor  + = Door  ░ = Unexplored
```

## Technical Notes

### Event Integration
New event types for spatial layer:
- `ENTITY_MOVED`: When any entity changes position
- `TILE_REVEALED`: When fog of war is lifted
- `MAP_LOADED`: When a new map is loaded
- `DOOR_OPENED/CLOSED`: Interactive tile state changes

### Backward Compatibility
- Text-only mode remains default
- 2D mode activated via `--mode 2d` flag
- All existing commands work in both modes
- Dungeon JSON can include both room descriptions AND grid data

### Performance Considerations
- FOV recalculated only on player movement
- Render only visible portion (viewport) for large maps
- Entity positions cached, not recalculated

## Success Criteria

- [ ] Player can move through dungeon with arrow keys
- [ ] Fog of war reveals map as player explores
- [ ] Enemies visible when in line of sight
- [ ] Combat triggers when adjacent to enemies
- [ ] All existing D&D mechanics work unchanged
- [ ] Maps load from JSON format
- [ ] Save/load preserves grid position

## Dependencies

- Rich (existing) - terminal rendering
- No new external dependencies required

## Estimated Scope

- Phase 1-2: Foundation (~500 lines)
- Phase 3-4: Rendering & Movement (~400 lines)
- Phase 5: FOV (~200 lines)
- Phase 6-7: Integration (~300 lines)
- Tests: (~400 lines)

Total: ~1800 lines of new code
