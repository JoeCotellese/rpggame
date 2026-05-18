---
name: playtester
description: Execute end-to-end playtesting of the D&D 5E game using the embedded MCP server. Use this skill when the user says "let's playtest", "test our fix", "qa the game", "playtest this", "test the game", or wants to verify game functionality through actual gameplay. When working on a ticket, focuses testing on the specific functionality being addressed.
---

# Playtester

QA the D&D 5E game by playing it as a human player would, using the embedded MCP server.

## Setup

**Prefer headless mode by default** (issue #362) — faster to launch, no window stealing focus, identical MCP behavior:
```bash
uv run dnd-2d --headless --dev --mcp
```

`--headless` implies `--mcp`. Add `--dev` so the `spawn_monster`, `spawn_character`, `set_position`, `clear_enemies`, `set_seed`, and `load_scenario` tools are available for reproducible setup. SIGINT / SIGTERM stops it cleanly.

**Use windowed mode only when you genuinely need to see the rendering:**
```bash
uv run dnd-2d --mcp --dev   # visual inspection of fog of war, sprites, layout
```

Both modes route MCP commands through the same `GameSession` so behavior is identical.

## MCP Tools

Core play tools (always available):

| Tool | Usage |
|------|-------|
| `game_state()` | Get ASCII map + JSON state |
| `game_move(direction)` | Move "north"/"south"/"east"/"west" |
| `game_attack(target)` | Attack enemy by index or entity ID (e.g., `"goblin_0"`) |
| `game_wait()` | Wait/pass turn in combat |

Dev tools (only available with `--dev`):

| Tool | Usage |
|------|-------|
| `spawn_monster(monster_id, x, y)` | Place a monster on the map and start combat |
| `spawn_character(class, race, weapons, x, y, ...)` | Add a PC to the party |
| `set_position(entity_id, x, y)` | Move any entity to a tile |
| `clear_enemies()` | Wipe enemies, end combat |
| `set_seed(seed)` | Reseed the dice roller for reproducible rolls |
| `load_scenario(path)` | Load a YAML scenario (party + enemies + seed + map) |

## Playtest Workflow

### 1. Context Check

If working on a ticket/issue, identify the specific functionality to test. Read the ticket to understand:
- What was changed
- Expected behavior
- Edge cases to verify

### 2. Start Session

```
game_state() → Observe initial state
```

### 3. Navigate to Test Area

Move systematically to reach the area/feature being tested. For ticket work, navigate to where the bug/feature manifests.

### 4. Execute Test Actions

Perform actions to exercise the functionality:
- Movement sequences
- Combat encounters
- Object interactions
- Edge cases from the ticket

### 5. Observe and Document

After each action, check game_state() for:
- Expected state changes occurred
- No unexpected errors in output
- Visual/map state is correct
- Entity positions are sensible

### 6. Bug Handling

**When a bug is found:**

Create a GitHub issue immediately:
```bash
gh issue create --title "Bug: [brief description]" --body "[details]"
```

Include in the issue:
- Steps to reproduce (the exact MCP calls made)
- Expected behavior
- Actual behavior
- Game state at time of bug (paste relevant JSON)

**Severity decision:**
- **Blocking**: Game crashes, cannot continue, core mechanic broken → End testing, report to user
- **Non-blocking**: Visual glitch, minor calculation error, cosmetic → Log issue, continue testing

### 7. Continue or Report

- If non-blocking bugs: continue exploring other functionality
- If blocking bug: stop and inform user immediately
- When testing complete: summarize findings (issues created, areas tested, pass/fail)

## Test Strategies

**Exploration test**: Move in all directions, reveal full map, check fog of war

**Combat test**: Find enemy, attack until resolved, verify HP changes and death

**Boundary test**: Try invalid moves (into walls), verify rejection

**State persistence**: Check that position/HP persist across turns
