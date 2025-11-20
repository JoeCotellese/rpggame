# Debug Console Feature

**Title:** Implement Debug Console with Slash Commands for QA and Development

**Labels:** enhancement, developer-experience, qa-tools, testing

---

## Problem Statement
Currently, testing and QA workflows require playing through the game naturally to reach specific game states. This is time-consuming for developers and QA testers who need to:
- Test specific combat scenarios
- Verify level progression mechanics
- Test edge cases (character death, resource exhaustion, etc.)
- Demo features to stakeholders quickly
- Reproduce bug reports at specific game states

## Proposed Solution
Implement a debug console with slash commands (e.g., `/revive`, `/kill`, `/teleport`) that allow rapid manipulation of game state for testing purposes.

---

## 🎯 CRITICAL PRIORITY - Core Testing Commands

### Character State Manipulation
- [x] `/revive [character]` - Revive dead/unconscious character
- [x] `/kill [target]` - Kill character or monster
- [x] `/sethp [character] [amount]` - Set exact HP value
- [x] `/damage [character] [amount]` - Deal damage for testing healing/death
- [x] `/heal [character] [amount]` - Direct healing (bypass spell mechanics)
- [x] `/godmode [character]` - Toggle invulnerability for testing
- [x] `/setlevel [character] [level]` - Jump to specific level (1-20)
- [x] `/addxp [character] [amount]` - Grant XP without combat
- [x] `/setstat [character] [ability] [value]` - Modify STR/DEX/CON/INT/WIS/CHA

### Combat Testing
- [x] `/spawn [monster] [count]` - Spawn enemies in current room
- [x] `/despawn [target]` - Remove monster from combat
- [x] `/nextturn` - Skip to next turn in initiative
- [x] `/endcombat` - Force end combat encounter
- [ ] `/initiative [target] [value]` - Set initiative order
- [ ] `/advantage [character]` - Force advantage on next roll
- [ ] `/crit` - Force next attack to crit (testing crit mechanics)

### Inventory & Currency
- [x] `/give [item] [quantity]` - Spawn any item from items.json
- [x] `/remove [item] [quantity]` - Remove items from inventory
- [x] `/gold [amount]` - Add/remove gold (negative values subtract)
- [x] `/clearinventory [character]` - Empty inventory for clean testing

---

## 🔥 HIGH PRIORITY - QA Workflows

### Condition Testing
- [x] `/addcondition [character] [condition]` - Apply status effect (poisoned, stunned, etc.)
- [x] `/removecondition [character] [condition]` - Clear specific condition
- [x] `/clearconditions [character]` - Remove all conditions
- [x] `/listconditions` - Show available condition types

### Resource Management
- [x] `/setslots [character] [level] [count]` - Set spell slot counts
- [x] `/restoreslots [character]` - Fully restore spell slots
- [x] `/setresource [character] [resource] [amount]` - Set ki/rage/etc.
- [x] `/shortrest` - Instant short rest (no time passage)
- [x] `/longrest` - Instant long rest (no time passage)

### Navigation & Exploration
- [x] `/teleport [room_id]` - Jump to any room instantly
- [x] `/listrooms` - Show all room IDs in dungeon
- [x] `/unlock [direction]` - Unlock door without checks
- [x] `/reveal` - Show all hidden features in room
- [ ] `/fog` - Toggle fog of war (show entire map)

### Spellcasting
- [x] `/learnspell [character] [spell]` - Add spell to spellbook
- [x] `/forgetspell [character] [spell]` - Remove spell
- [x] `/listspells [class] [level]` - Browse available spells
- [ ] `/cast [spell] [target]` - Force cast without slot consumption

---

## ⚡ MEDIUM PRIORITY - Development Speed

### Party Management
- [ ] `/addcharacter [class] [race] [level]` - Create new party member
- [ ] `/removecharacter [name]` - Remove from party
- [ ] `/switchparty [preset]` - Load pre-configured party setups
- [ ] `/cloneparty` - Duplicate party to another save slot

### Save State Tools
- [ ] `/saveslots` - List all save slots with metadata
- [ ] `/backup [slot]` - Create backup of save
- [ ] `/restore [slot] [backup]` - Restore from backup
- [ ] `/compareslots [slot1] [slot2]` - Diff two saves
- [ ] `/exportsave [slot] [filename]` - Export save as JSON

### Dungeon Manipulation
- [ ] `/resetsearch` - Mark all rooms as unsearched
- [ ] `/respawn` - Respawn all defeated enemies
- [ ] `/loottable [room_id]` - Preview loot before searching
- [ ] `/setdungeon [dungeon_name]` - Load different dungeon instantly

### Event System
- [ ] `/events` - Show recent event history
- [ ] `/trigger [event_type]` - Manually fire event
- [ ] `/subscribe [event_type]` - Watch specific events (verbose logging)
- [ ] `/eventlog [on|off]` - Toggle event logging overlay

---

## 🛠️ LOW PRIORITY - Edge Cases

### Proficiency & Features
- [ ] `/addskill [character] [skill]` - Grant skill proficiency
- [ ] `/addexpertise [character] [skill]` - Grant expertise (Rogue feature)
- [ ] `/addfeature [character] [feature]` - Grant class feature early
- [ ] `/resetfeatures [character]` - Clear and reapply features for level

### Dice & RNG Testing
- [ ] `/fixeddice [value]` - All dice roll this value until reset
- [ ] `/randomseed [seed]` - Set RNG seed for reproducible tests
- [ ] `/lastroll` - Show last dice roll details (useful for bug reports)
- [ ] `/rollstats` - Show dice distribution statistics

### UI & Display
- [ ] `/togglellm` - Disable/enable LLM narration
- [ ] `/slowmode [seconds]` - Add delay between messages (demo mode)
- [ ] `/clearscreen` - Clear terminal output
- [ ] `/status [verbose]` - Detailed system state dump
- [ ] `/screenshot [filename]` - Save current UI state to file

### Performance & Testing
- [ ] `/benchmark` - Run performance test suite
- [ ] `/loadtest` - Stress test save/load system
- [ ] `/memstats` - Show memory usage statistics
- [ ] `/validate` - Check game state integrity

---

## 💡 Example Use Cases

### QA Testing Death Mechanics
```bash
/sethp Gandalf 1
/damage Gandalf 10
# Test death saves, stabilize mechanics, party death detection
```

### Testing Level Progression
```bash
/setlevel Aragorn 5
/addxp Aragorn 6500  # Just enough to hit level 6
# Verify level-up grants correct features, HP, spell slots
```

### Testing Sneak Attack
```bash
/spawn Goblin 1
/advantage Rogue
attack Goblin
# Verify sneak attack damage calculation
```

### Testing Spell Slot Management
```bash
/setslots Wizard 3 0  # Exhaust 3rd level slots
/cast Fireball Goblin
# Should fail gracefully
/restoreslots Wizard
# Should work now
```

### Testing Locked Doors
```bash
/remove Thieves_Tools 1  # Remove lockpicks
/unlock north  # Bypass to test post-unlock behavior
```

### Testing Save System
```bash
/backup 1
/kill Gandalf
/damage Aragorn 50
/gold -500
/restore 1 latest
# Verify rollback works correctly
```

### Demo New Content
```bash
/teleport boss_room
/setlevel party 10
/longrest
# Jump straight to showcase boss fight
```

### Showcase Class Features
```bash
/addcharacter Rogue Halfling 3  # Thief archetype
/give Potion_of_Healing 5
/spawn Bandit 3
# Demo sneak attack mechanics immediately
```

### Test Balance Changes
```bash
/spawn Ancient_Red_Dragon 1
/godmode party
# Test new monster without risk of party wipe
```

---

## Implementation Considerations

### Architecture
- **Location**: New module `dnd_engine/ui/debug_console.py`
- **Parser**: Command parser to extract command + arguments
- **Dispatcher**: Route commands to appropriate handlers
- **Integration**: Hook into existing CLI command loop

### Safety Features
1. **Confirmation Prompts**: Destructive commands require confirmation
2. **Undo Buffer**: Store last 5 game states for `/undo` command
3. **Production Flag**: Environment variable to disable debug console
4. **Audit Log**: Track all debug commands used in session

### Discoverability
- `/help debug` - List all debug commands with descriptions
- `/help [command]` - Show detailed usage for specific command
- Tab completion for command names
- Typo suggestions ("Did you mean `/revive`?")

### Testing Requirements
- Unit tests for command parser
- Integration tests for each command category
- Test that debug commands don't break save/load
- Test that debug mode can be disabled

---

## Acceptance Criteria

- [x] Debug console can be enabled/disabled via environment variable or CLI flag
- [x] All CRITICAL priority commands implemented and tested
- [x] Commands work correctly without breaking game state
- [x] Help system (`/help`, `/help [command]`) implemented
- [ ] Debug commands logged to audit file
- [x] Existing `reset` command converted to `/reset` slash command
- [x] Documentation added to project README
- [x] Unit and integration tests added for debug console

---

## Migration Note

Current command to migrate:
- `reset` → `/reset` (reset dungeon state while keeping party)
