# Test Scenario: Save and Load Game

## Objective

Verify that manual saving, auto-saving, and loading game state works correctly and preserves all game data.

## Prerequisites

- **Game state:** clean OR existing save
- **Required data:** none (will create during test)
- **Special setup:** none

## Setup Steps

1. Start game
   - **Command:** `python -m dnd_engine.main_v2`
   - **Expected:** Main menu appears

2. Either load existing game or create new campaign
   - **Command:** `1` (New Game) or `2` (Load Game)
   - **Expected:** Party in dungeon

## Test Actions

### 1. Manual Save
1. Check current game state
   - **Command:** `status`
   - **Expected:** Note current HP, XP, location for comparison

2. Perform manual save
   - **Command:** `save`
   - **Expected:** "Game saved successfully" message or save confirmation

3. Make a change to game state
   - **Command:** Take damage in combat or use item
   - **Expected:** Game state changes (HP decreases, item used)

4. Verify unsaved changes
   - **Command:** `status`
   - **Expected:** State different from saved state

### 2. Quick Save (if implemented)
1. Test quick save
   - **Command:** `qs` or `quicksave`
   - **Expected:** Quick save confirmation

2. Note quick save timestamp/slot
   - **Expected:** Display shows when/where quick save occurred

### 3. Auto-Save Verification
1. Navigate to new room
   - **Command:** `n`, `s`, `e`, or `w`
   - **Expected:** Auto-save message appears (or silent auto-save)

2. Check for auto-save indicator
   - **Expected:** Some indication that auto-save occurred

### 4. Exit and Reload
1. Exit game
   - **Command:** `quit`
   - **Expected:** Returns to main menu or exits program

2. Restart game
   - **Command:** `python -m dnd_engine.main_v2`
   - **Expected:** Main menu appears

3. Load saved game
   - **Command:** `2` (Load Game) → select appropriate slot
   - **Expected:** Game loads from save point

4. Verify game state preserved
   - **Command:** `status`, `inventory`, `look`
   - **Expected:** HP, XP, location, inventory match saved state

### 5. Multiple Save Slots
1. Create/load game in slot 1
   - **Expected:** Game running in slot 1

2. Exit and create new game in different slot
   - **Command:** New campaign → slot 2
   - **Expected:** Separate game in slot 2

3. Verify both saves are independent
   - **Command:** Load slot 1, then load slot 2
   - **Expected:** Different parties, progress, locations

### 6. Save Slot Management
1. View all save slots
   - **Command:** From main menu: `4` (Manage Save Slots) if available
   - **Expected:** Display shows all slots with metadata

2. Check save slot information
   - **Expected:** Shows party names, location, timestamp, playtime

3. Overwrite existing save
   - **Command:** Save to same slot again
   - **Expected:** Confirmation prompt, then overwrites

### 7. Edge Cases

1. Try to save during combat (if restricted)
   - **Expected:** Either allows save or shows "Cannot save during combat"

2. Load corrupted save (if testable)
   - **Expected:** Error handling, doesn't crash game

3. Save with full slots (if there's a limit)
   - **Expected:** Prompt to overwrite or error message

4. Load non-existent slot
   - **Expected:** Error message or shows "Empty slot"

## Expected Outcomes

- ✓ Save command works and persists data
- ✓ Quick save works (if implemented)
- ✓ Auto-save triggers on room transitions
- ✓ Load command restores exact game state
- ✓ HP, XP, location, inventory all preserved
- ✓ Multiple save slots work independently
- ✓ Save slot metadata (timestamp, playtime) correct
- ✓ Can overwrite existing saves with confirmation
- ✓ Game doesn't crash on save/load operations
- ✓ No data loss or corruption
- ✓ No exceptions or error messages for valid operations

## Failure Conditions

- ✗ Save command doesn't work
- ✗ Game state not preserved after save/load
- ✗ HP, XP, or inventory incorrect after loading
- ✗ Wrong location after loading
- ✗ Auto-save doesn't trigger
- ✗ Save slots overwrite each other
- ✗ Save metadata incorrect (wrong timestamp, playtime)
- ✗ Cannot overwrite existing saves
- ✗ Python exceptions or tracebacks appear
- ✗ Game crashes during save/load
- ✗ Save file corruption
- ✗ Data loss on save/load

## Notes

- **Estimated duration:** 5-7 minutes
- **Edge cases:**
  - What happens if save file is manually deleted?
  - Can you load saves from different game versions?
  - What's the maximum number of save slots?
  - Are saves portable between machines?
  - How large can save files get?
- **Future extensions:**
  - Test save file format/structure
  - Test cloud save integration (if planned)
  - Test save file migration across versions
  - Test concurrent saves (multiple game instances)
  - Test save file integrity checks
  - Test backup/restore functionality
- **Related scenarios:**
  - All scenarios depend on save/load working
  - `new_game_party_creation.md` - Initial save creation
  - `dungeon_exploration.md` - Auto-save during exploration
