# D&D 5E Terminal Game - Test Suite Overview

This directory contains end-to-end test scenarios for the D&D 5E terminal game. Each scenario is written in natural language and can be executed by either humans or AI using the e2e-tester skill.

## Available Test Scenarios

### Core Gameplay

#### 1. **new_game_party_creation.md** ✅ TESTED
- **Status:** PASS (10/10 outcomes achieved)
- **Duration:** ~7 minutes
- **Coverage:** New campaign creation, character creation wizard, party selection, dungeon selection, first room entry
- **Last Run:** 2025-11-20
- **Key Findings:** Zero bugs, flawless character creation flow

#### 2. **basic_combat.md** ✅ TESTED
- **Status:** PARTIAL (bugs found)
- **Duration:** ~5 minutes
- **Coverage:** Combat initiation, attack commands, initiative, turn order, enemy defeat
- **Last Run:** 2025-11-20
- **Key Findings:**
  - Bug: Enemy re-indexing after defeat (attack 1 fails after Goblin 1 dies)
  - Bug: Spell casting syntax unclear

#### 3. **dungeon_exploration.md** (Navigation mechanics)
- **Status:** Manual testing completed (not documented)
- **Coverage:** Room navigation (n/s/e/w), look, flee, room connections, auto-save
- **Notes:** Tested during previous session, needs formal RESULTS file

### Item Systems

#### 4. **inventory_management.md** 📝 NEW
- **Status:** Not yet tested
- **Duration:** 3-4 minutes (estimated)
- **Coverage:**
  - View inventory across party
  - Use consumables (potions)
  - Item targeting
  - Inventory updates
  - Edge cases (invalid items, invalid targets)

#### 5. **equipment_system.md** 📝 NEW
- **Status:** Not yet tested
- **Duration:** 4-5 minutes (estimated)
- **Coverage:**
  - Equip weapons and armor
  - Unequip items
  - Stat changes (AC, attack bonus)
  - Multiple equipment slots
  - Class/proficiency restrictions
  - Edge cases

#### 6. **search_and_loot.md** 📝 NEW
- **Status:** Not yet tested
- **Duration:** 4-5 minutes (estimated)
- **Coverage:**
  - Search rooms
  - Find gold and items
  - Take items
  - Multiple item handling
  - Loot persistence
  - Edge cases

### Character Management

#### 7. **rest_and_healing.md** 📝 NEW
- **Status:** Not yet tested
- **Duration:** 2-3 minutes (estimated)
- **Coverage:**
  - Short and long rest
  - HP restoration
  - Spell slot restoration
  - Rest restrictions (combat, etc.)
  - Edge cases

#### 8. **death_and_unconsciousness.md** 📝 NEW
- **Status:** Not yet tested
- **Duration:** 6-8 minutes (estimated)
- **Coverage:**
  - Character reaches 0 HP
  - Death saves (automatic)
  - Stabilize command
  - Healing unconscious characters
  - Character death (permanent)
  - Total party kill (TPK)
  - Massive damage instant death
  - Edge cases

### System Features

#### 9. **save_load_game.md** 📝 NEW
- **Status:** Not yet tested
- **Duration:** 5-7 minutes (estimated)
- **Coverage:**
  - Manual save
  - Quick save
  - Auto-save
  - Load game
  - Multiple save slots
  - Save slot management
  - Data persistence
  - Edge cases

## Test Execution

### Using the e2e-tester Skill

```bash
# From Claude Code, invoke the skill:
/e2e-tester

# Then request:
"Run the inventory_management test"
# or
"Create a test for spell casting"
```

### Manual Testing

1. Read the scenario markdown file
2. Follow each step sequentially
3. Verify expected outcomes
4. Document any issues in a RESULTS file
5. Note edge cases or unexpected behavior

## Test Coverage Matrix

| Feature Area | Scenarios | Coverage |
|--------------|-----------|----------|
| Party Creation | 1 | ✅ Complete |
| Combat | 1 | ⚠️ Bugs found |
| Navigation | 1 | ✅ Manual test |
| Inventory | 1 | 📝 Not tested |
| Equipment | 1 | 📝 Not tested |
| Loot/Search | 1 | 📝 Not tested |
| Rest/Healing | 1 | 📝 Not tested |
| Death Mechanics | 1 | 📝 Not tested |
| Save/Load | 1 | 📝 Not tested |

## Known Issues

From executed tests:

### High Priority
1. **Enemy Re-indexing** (`basic_combat.md`)
   - After defeating Goblin 1, `attack 1` fails
   - Must use `attack 2` to target remaining goblin
   - Expected: Remaining enemies re-index to start at 1

2. **Spell Casting Syntax** (`basic_combat.md`)
   - Command `cast fire_bolt 1` returns "Unknown spell"
   - Syntax unclear from game
   - Need to document correct spell casting syntax

### Previously Identified
3. **Cannot heal unconscious allies** (Navigation test)
   - `use potion on Bob` when Bob at 0 HP returns "No living player found"
   - Prevents reviving downed party members outside combat
   - May be intended behavior (5E rules: potions require action)

## Test Priorities

### Immediate (Next Session)
1. **inventory_management.md** - Critical gameplay feature
2. **equipment_system.md** - Affects combat effectiveness
3. **save_load_game.md** - Essential for game persistence

### Soon
4. **rest_and_healing.md** - Important recovery mechanic
5. **search_and_loot.md** - Core exploration loop
6. **death_and_unconsciousness.md** - Critical edge case handling

## Adding New Scenarios

To create a new test scenario:

1. Use the template in `.claude/skills/e2e-tester/references/test_scenario_template.md`
2. Follow the structure:
   - Objective (what you're testing)
   - Prerequisites (game state needed)
   - Setup Steps (how to get ready)
   - Test Actions (what to do)
   - Expected Outcomes (success criteria)
   - Failure Conditions (what indicates failure)
   - Notes (edge cases, extensions)
3. Save as `tests/scenarios/<scenario_name>.md`
4. Execute immediately to validate
5. Document results in `RESULTS_<scenario_name>.md`
6. Update this overview with findings

## Test Automation

Currently using **terminal-control MCP** for automated test execution:
- Open terminal session
- Send commands programmatically
- Read game output
- Verify expected outcomes
- Document results

Future possibilities:
- Pytest integration for automated runs
- CI/CD pipeline integration
- Regression test suite
- Performance benchmarking

## Success Metrics

### Test Quality
- ✓ Human-readable scenarios
- ✓ AI-executable scenarios
- ✓ Clear success/failure criteria
- ✓ Comprehensive edge case coverage
- ✓ Reproducible results

### Coverage Goals
- [ ] 100% of core features tested
- [ ] All major game systems verified
- [ ] Edge cases documented
- [ ] Performance benchmarks established
- [ ] Regression suite automated

## Contributing

When adding or running tests:
1. Follow the scenario template structure
2. Document all findings (bugs, UX issues, suggestions)
3. Update this overview with test status
4. Create GitHub issues for discovered bugs
5. Link RESULTS files to relevant issues
