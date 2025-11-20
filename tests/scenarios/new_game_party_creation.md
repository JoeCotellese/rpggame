# Test Scenario: New Game and Party Creation

## Objective

Verify that a new campaign can be started and a party can be created with multiple characters, selecting a dungeon, and entering the first room without errors.

## Prerequisites

- **Game state:** clean (no existing saves required, but test should work with or without)
- **Required data:** none
- **Special setup:** none

## Setup Steps

1. Start the game from project directory
   - **Command:** `python -m dnd_engine.main_v2`
   - **Expected:** Main menu appears with options for New Campaign, Load Game, Character Vault, Exit

## Test Actions

1. Select "New Campaign" from main menu
   - **Command:** `1`
   - **Expected:** Prompted to create party or select characters

2. Create first character (Fighter)
   - **Command:** Follow prompts to create a Fighter
   - **Expected:** Character creation wizard guides through name, class selection, stats

3. Create second character (Wizard)
   - **Command:** Follow prompts to create a Wizard
   - **Expected:** Character added to party

4. Create third character (Rogue)
   - **Command:** Follow prompts to create a Rogue
   - **Expected:** Character added to party, party now has 3 members

5. Complete party creation
   - **Command:** Confirm party is complete (exact command depends on UI)
   - **Expected:** Prompted to select a dungeon

6. Select starting dungeon
   - **Command:** Choose "Goblin Warren" or first available dungeon
   - **Expected:** Dungeon selected, game begins

7. Verify first room entry
   - **Command:** (May be automatic, or may need to confirm)
   - **Expected:** First room description appears, party status visible

8. Check party status
   - **Command:** `status`
   - **Expected:** All three characters shown with correct names, classes, HP, and stats

9. Verify game state is saved
   - **Command:** `quit` or check for auto-save message
   - **Expected:** Game saved to a slot

## Expected Outcomes

- ✓ Main menu displays correctly with all options
- ✓ New campaign workflow initiates properly
- ✓ Character creation wizard completes for all three characters
- ✓ All characters appear in party with correct classes (Fighter, Wizard, Rogue)
- ✓ Character stats are initialized correctly (positive HP, valid ability scores)
- ✓ Dungeon selection presents available options
- ✓ First room loads and displays description
- ✓ Party status command shows all three characters
- ✓ Game auto-saves or allows manual save
- ✓ No exceptions or error messages appear

## Failure Conditions

- ✗ Main menu doesn't display or has missing options
- ✗ Character creation wizard crashes or loops
- ✗ Characters not added to party correctly
- ✗ Invalid stats generated (negative HP, out-of-range ability scores)
- ✗ Dungeon selection fails or doesn't present options
- ✗ First room fails to load
- ✗ Party status shows incorrect or missing characters
- ✗ Python exceptions or tracebacks appear
- ✗ Game crashes or exits unexpectedly
- ✗ Save functionality doesn't work

## Notes

- **Estimated duration:** 3-5 minutes
- **Edge cases:**
  - What happens with duplicate character names?
  - Can you create a party with only 1 character? Or more than 3?
  - What if you try to select an invalid dungeon option?
- **Future extensions:**
  - Test creating party from character vault instead of new characters
  - Test all available dungeons
  - Test party size limits (min/max characters)
  - Test invalid inputs during character creation
- **Related scenarios:**
  - `basic_combat.md` - Next logical test after party creation
  - `character_creation.md` - More detailed character vault testing
