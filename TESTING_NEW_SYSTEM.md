# Testing the New Save Slot System

This guide walks through testing the newly implemented save slot system for Issue #92.

## Quick Start

```bash
# Run the new system
python run_new_system.py

# Or with uv
uv run python run_new_system.py

# With debug logging
python run_new_system.py --debug

# Without LLM
python run_new_system.py --no-llm
```

## Test Scenarios

### 1. First-Time User Experience

**Goal:** Verify new users can start playing within 60 seconds

**Steps:**
1. Run `python run_new_system.py`
2. Select **[1] New Game**
3. Create 1-2 characters (or use test characters if vault has them)
4. Select an adventure
5. Choose a save slot (e.g., Slot 1)
6. Start playing

**Expected Result:**
- Should reach gameplay within 60 seconds
- Save slot should show auto-generated name
- Characters should be added to vault

### 2. Migration from Old System

**Goal:** Verify existing campaigns are migrated correctly

**Prerequisites:**
- Have old campaigns in `~/.dnd_terminal/campaigns/`

**Steps:**
1. Run `python run_new_system.py`
2. Should see "MIGRATION DETECTED" screen
3. Review migration info (campaigns, characters)
4. Confirm migration by typing "yes"
5. Wait for migration to complete
6. Verify success message

**Expected Result:**
- Backup created at `~/.dnd_terminal/backup_pre_migration/`
- Up to 10 most recent campaigns migrated to slots
- Unique characters extracted to vault
- No errors in migration

**Verification:**
```bash
# Check new save slots
ls -la ~/.dnd_game/saves/

# Check character vault
cat ~/.dnd_game/character_vault.json | jq .

# Verify backup
ls -la ~/.dnd_terminal/backup_pre_migration/
```

### 3. Save and Load Game

**Goal:** Verify save/load functionality works correctly

**Steps:**
1. Start a new game
2. Play for a few minutes (move rooms, fight enemies)
3. Note the auto-save messages after combat/room changes
4. Exit game (Ctrl+C or quit command)
5. Run game again
6. Select **[2] Load Game**
7. Choose the slot you saved to
8. Verify game state is restored

**Expected Result:**
- Auto-saves appear after key events
- Slot shows accurate progress and playtime
- Party HP, location, and inventory restored correctly

### 4. Character Vault Usage

**Goal:** Verify character vault tracks usage correctly

**Steps:**
1. Run game
2. Select **[3] Character Vault**
3. Create a new character
4. Exit vault
5. Start new game using that character
6. Save and quit
7. Return to vault
8. Verify character shows:
   - Times used: 1
   - Slots: [slot_number]

**Expected Result:**
- Usage statistics update correctly
- Characters sort by last used

### 5. Slot Management

**Goal:** Verify slot renaming and clearing works

**Steps:**
1. Run game
2. Select **[4] Manage Save Slots**
3. Test renaming:
   - Select **[R] Rename slot**
   - Choose a used slot
   - Enter custom name
   - Verify name updates
4. Test clearing:
   - Select **[C] Clear slot**
   - Choose a slot
   - Confirm clearing
   - Verify slot becomes empty

**Expected Result:**
- Custom names override auto-generated names
- Cleared slots show as EMPTY
- Changes persist across restarts

### 6. Multiple Party Members

**Goal:** Verify parties with 2-6 characters work correctly

**Steps:**
1. Start new game
2. Create/select 3-4 characters
3. Play through combat
4. Save and reload
5. Verify all characters present

**Expected Result:**
- All party members show in save slot preview
- Party composition displays correctly (e.g., "Alice, Bob +2")
- All characters load correctly

### 7. Playtime Tracking

**Goal:** Verify playtime accumulates correctly

**Steps:**
1. Start new game
2. Play for exactly 5 minutes (use timer)
3. Save and quit
4. Note playtime in slot
5. Load same slot
6. Play for another 5 minutes
7. Save and quit
8. Verify playtime increased by 10 minutes

**Expected Result:**
- Playtime formats correctly (e.g., "10m")
- Playtime accumulates across sessions
- Playtime persists in save slot

### 8. Empty Slot Handling

**Goal:** Verify empty slots are handled correctly

**Steps:**
1. Try to load from empty slot
2. Verify appropriate error message
3. Create game in empty slot
4. Verify slot is no longer empty

**Expected Result:**
- Cannot load from empty slot
- Clear error message
- Slots initialize properly

### 9. Save Slot Display Names

**Goal:** Verify auto-generated names are descriptive

**Format:** `{Adventure} - {Party} - {Progress} - {Playtime}`

**Examples to Test:**
- Solo character: "Goblin Warren - Alice - Room 3 - 15m"
- Small party: "Lost Mine - Alice, Bob - Level 2 - 1h 23m"
- Large party: "Tomb - Alice, Bob +3 - Room 12 - 2h 15m"

**Expected Result:**
- Names are descriptive and helpful
- Format is consistent
- Custom names override auto-names

### 10. Corrupted Save Handling

**Goal:** Verify graceful handling of corrupted saves

**Steps:**
1. Create a save in Slot 5
2. Exit game
3. Corrupt the save file:
   ```bash
   echo "{ invalid json }" > ~/.dnd_game/saves/slot_05.json
   ```
4. Run game
5. Try to load Slot 5

**Expected Result:**
- Slot shows as EMPTY or error
- Game doesn't crash
- Can still use other slots

## Performance Metrics

Track these metrics during testing (from Issue #92):

### Time to First Game
**Target:** < 60 seconds

**Measure:**
1. Start timer when running `python run_new_system.py`
2. Stop timer when entering first room
3. Record time

**Acceptable:** 30-60 seconds
**Needs Work:** > 60 seconds

### Save/Load Success Rate
**Target:** > 95%

**Measure:**
- Successful loads / Total load attempts
- Track any load failures

### Migration Success
**Target:** 100%

**Measure:**
- Successful migrations / Total migrations attempted
- Check for any data loss

## Manual Testing Checklist

Use this checklist for comprehensive manual testing:

- [ ] First-time user can start game quickly
- [ ] Migration detects old campaigns correctly
- [ ] Migration completes without errors
- [ ] Backup is created during migration
- [ ] Character vault stores characters correctly
- [ ] Usage tracking updates properly
- [ ] New game flow works smoothly
- [ ] Load game shows correct slot information
- [ ] Auto-save triggers after combat
- [ ] Auto-save triggers after room change
- [ ] Auto-save triggers after level-up
- [ ] Playtime accumulates correctly
- [ ] Slot renaming works
- [ ] Slot clearing works
- [ ] Multiple characters in party work
- [ ] Empty slots handled correctly
- [ ] Corrupted saves handled gracefully
- [ ] Auto-generated names are descriptive
- [ ] Custom names override auto-names
- [ ] Can have up to 6 characters in party
- [ ] All 10 slots are usable

## Known Issues / Limitations

### Current Limitations

1. **Character Matching:** The vault matches characters by name when recording usage, which could cause issues if you have duplicate character names.

2. **CLI Compatibility:** The old CLI code is still used with an adapter. Some features might not work perfectly.

3. **Save Management:** Manual save and quick-save commands in-game are not yet updated to work with slot system.

## Debugging

### View Save Slot Contents

```bash
# Pretty print a save slot
cat ~/.dnd_game/saves/slot_01.json | jq .

# Check slot metadata
cat ~/.dnd_game/saves/slot_01.json | jq .metadata
```

### View Character Vault

```bash
# Pretty print entire vault
cat ~/.dnd_game/character_vault.json | jq .

# List all characters
cat ~/.dnd_game/character_vault.json | jq '.characters | keys'

# View character usage
cat ~/.dnd_game/character_vault.json | jq '.characters[] | {name: .character.name, times_used, save_slots_used}'
```

### Check Migration Backup

```bash
# List backed up campaigns
ls -la ~/.dnd_terminal/backup_pre_migration/campaigns/

# Compare old vs new
diff -r ~/.dnd_terminal/backup_pre_migration ~/.dnd_terminal/campaigns
```

### Enable Debug Logging

```bash
# Run with debug flag
python run_new_system.py --debug

# Check log file (location shown in startup message)
tail -f ~/.local/share/dnd_game/debug.log
```

## Troubleshooting

### Migration doesn't start
- Check if `~/.dnd_game/` already exists
- Delete `~/.dnd_game/` to trigger migration again
- Ensure `~/.dnd_terminal/campaigns/` has valid campaigns

### Save slot is empty after playing
- Check auto-save is enabled in CLI
- Verify slot number is correct
- Check `~/.dnd_game/saves/` for slot files

### Character not in vault
- Verify character was created successfully
- Check `~/.dnd_game/character_vault.json`
- Try creating character again

### Playtime not updating
- Verify auto-save is working
- Check if SaveSlotCLIAdapter is being used
- Review session start time logic

## Test Results Template

Use this template to document your testing:

```
## Test Session: [Date]
Tester: [Name]
Branch: claude/implement-new-menu-system-01SDhKCq4NBm2Tj224oMY1mw
Commit: [commit hash]

### Scenarios Tested
- [ ] First-time user
- [ ] Migration
- [ ] Save/Load
- [ ] Character Vault
- [ ] Slot Management
- [ ] Multiple characters
- [ ] Playtime tracking

### Issues Found
1. [Issue description]
   - Steps to reproduce
   - Expected vs Actual
   - Severity: High/Medium/Low

### Performance Metrics
- Time to first game: [XX seconds]
- Save/load success rate: [XX%]
- Migration success: [Yes/No]

### Notes
[Any additional observations]
```

## Next Steps After Testing

Once testing is complete:

1. **Document Issues:** Create GitHub issues for any bugs found
2. **Update Documentation:** Update user-facing docs if needed
3. **Performance Tuning:** Optimize any slow areas
4. **Polish UI:** Improve error messages and user feedback
5. **Final Review:** Review code for any improvements

## Contact

For questions or issues during testing:
- Create a GitHub issue
- Reference commit hash and test scenario
- Include debug logs if available
