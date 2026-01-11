# Option 5: Self-Contained Campaign Layouts

## Overview

Add optional `layout` field to dungeon room definitions, allowing campaign authors to define tile-based layouts for 2D client rendering while keeping campaigns self-contained.

## Architecture

```
Campaign Package (self-contained)
├── dungeons/
│   └── laboratory.json     # Rooms with optional layout field
├── npcs/
├── quests/
└── ...

Terminal Client                    2D Client
     │                                │
     │                                │
     └──── dnd-engine ────────────────┘
              │
              ├── Reads room graph (exits, enemies, items)
              ├── Terminal: ignores layout field
              └── 2D Client: uses layout if present, generates if missing
```

## JSON Schema

### Room with Layout

```json
{
  "laboratory.entrance": {
    "name": "Collapsed Entrance Hall",
    "description": "The entrance to the laboratory...",
    "exits": {
      "north": "laboratory.storage"
    },
    "enemies": ["goblin", "goblin"],
    "items": [{"type": "item", "id": "potion_of_healing"}],

    "layout": {
      "width": 20,
      "height": 15,
      "tiles": [
        [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
        [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
        "... (0=floor, 1=wall, 2=door, etc.)"
      ],
      "spawn_points": {
        "player": [10, 13],
        "exits": {
          "north": [10, 1]
        }
      },
      "entity_positions": {
        "enemies": [[5, 5], [15, 8]],
        "items": [[8, 10]]
      },
      "light_sources": [
        {"x": 10, "y": 7, "type": "torch", "radius": 20}
      ]
    }
  }
}
```

### Tile Types

| Value | Meaning |
|-------|---------|
| 0 | Floor (walkable) |
| 1 | Wall (blocked, blocks light) |
| 2 | Door (walkable, may be locked) |
| 3 | Water (walkable, difficult terrain) |
| 4 | Pit (blocked unless flying) |

### Layout Field Spec

| Field | Required | Description |
|-------|----------|-------------|
| `width` | Yes | Room width in tiles |
| `height` | Yes | Room height in tiles |
| `tiles` | Yes | 2D array of tile values |
| `spawn_points.player` | Yes | [x, y] where player starts |
| `spawn_points.exits` | Yes | Map of exit direction to [x, y] |
| `entity_positions.enemies` | No | List of [x, y] for enemy spawns |
| `entity_positions.items` | No | List of [x, y] for item positions |
| `light_sources` | No | List of static light sources |

## Implementation Phases

### Phase 1: Layout Schema & Loader

1. Create `client_2d/integration/layout_loader.py`
   - Load room data from engine
   - Parse layout field
   - Generate fallback layout if missing

2. Create `client_2d/integration/layout_schema.py`
   - Pydantic models for layout validation
   - RoomLayout, SpawnPoints, EntityPositions

3. Tests: `tests/test_layout_loader.py`

### Phase 2: Engine Bridge Integration

1. Update `engine_bridge.py`
   - Load room layout when room entered
   - Sync entity positions from layout
   - Emit layout_loaded event

2. Connect bridge to existing GameState in test harness

3. Tests: Update `test_engine_bridge.py`

### Phase 3: Demo Dungeon Layout

1. Add layout to `poisoned_laboratory/dungeons/laboratory.json`
   - Start with entrance room only
   - Design tactical layout with walls, cover

2. Update `create_demo_game_state()` to optionally load from engine

3. Manual testing via MCP server

### Phase 4: Procedural Fallback

1. Create `client_2d/integration/layout_generator.py`
   - Generate basic room from width/height
   - Place walls at borders
   - Add doorways for exits
   - Random obstacles

2. Tests: `tests/test_layout_generator.py`

## File Changes

### New Files
- `client-2d/src/client_2d/integration/layout_loader.py`
- `client-2d/src/client_2d/integration/layout_schema.py`
- `client-2d/src/client_2d/integration/layout_generator.py`
- `client-2d/tests/test_layout_loader.py`
- `client-2d/tests/test_layout_generator.py`

### Modified Files
- `client-2d/src/client_2d/integration/__init__.py` - exports
- `client-2d/src/client_2d/integration/engine_bridge.py` - layout loading
- `dnd-engine/data/campaigns/poisoned_laboratory/dungeons/laboratory.json` - add layout

## Acceptance Criteria

- [ ] Room layout JSON schema defined and validated
- [ ] Layout loader parses layouts from dungeon JSON
- [ ] Fallback generator creates basic rooms when no layout
- [ ] Engine bridge loads layout on room enter
- [ ] At least one dungeon room has a hand-crafted layout
- [ ] MCP playtesting works with real dungeon layout
- [ ] All tests pass

## Out of Scope (Future)

- Visual layout editor tool
- Multiple floors/elevation
- Dynamic room changes (cave-ins, etc.)
- Tiled/TMX format import
