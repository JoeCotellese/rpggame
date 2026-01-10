# Test Scenario: Rest and Healing

## Objective

Verify that the rest system works correctly, healing party members and restoring resources (spell slots, HP, etc.).

## Prerequisites

- **Game state:** existing save with party
- **Required data:** Party with damaged characters (HP below max)
- **Special setup:** Ideally party should be injured from combat, wizard should have expended spell slots

## Setup Steps

1. Start the game and load save
   - **Command:** `python -m dnd_engine.main_v2`
   - **Expected:** Main menu appears

2. Load game
   - **Command:** `2` → select slot with party
   - **Expected:** Game loads with party

3. Ensure party is damaged (if not, engage in combat first)
   - **Command:** Navigate to room with enemies if needed
   - **Expected:** Party takes some damage

## Test Actions

### 1. Check Party Status Before Rest
1. View current party status
   - **Command:** `status`
   - **Expected:** Shows current HP (should be below max for at least one character)

2. Check wizard's spell slots (if wizard in party)
   - **Command:** `inventory` or check status
   - **Expected:** Shows available/expended spell slots

### 2. Attempt Short Rest
1. Try to rest
   - **Command:** `rest`
   - **Expected:** Rest system initiates (may prompt for rest type: short or long)

2. If prompted, select rest type
   - **Command:** Follow prompts
   - **Expected:** Rest completes successfully

### 3. Verify Healing After Rest
1. Check party status after rest
   - **Command:** `status`
   - **Expected:** HP restored to maximum (for long rest) or partially healed (for short rest with hit dice)

2. Check wizard spell slots (if applicable)
   - **Expected:** Long rest should restore all spell slots

3. Verify all party members healed
   - **Expected:** All characters show restored HP

### 4. Test Rest Edge Cases

1. Try to rest at full HP
   - **Command:** `rest` (when party is at full HP)
   - **Expected:** Either allows rest anyway or shows message that rest isn't needed

2. Try to rest during combat (if possible to test)
   - **Expected:** Should not allow rest during active combat

3. Check for random encounters during rest
   - **Expected:** May trigger random encounter depending on game mechanics

## Expected Outcomes

- ✓ Rest command is recognized and executes
- ✓ Party HP is restored after rest
- ✓ Spell slots are restored after long rest (for spellcasters)
- ✓ All party members benefit from rest
- ✓ Status command shows updated HP values
- ✓ Cannot rest during combat
- ✓ Rest completes without crashes
- ✓ No exceptions or error messages appear
- ✓ Game state is properly updated after rest
- ✓ Auto-save occurs after rest (if auto-save enabled)

## Failure Conditions

- ✗ Rest command not recognized
- ✗ HP not restored after rest
- ✗ Spell slots not restored after long rest
- ✗ Some party members not healed
- ✗ Can rest during combat
- ✗ Rest causes game to crash
- ✗ Python exceptions or tracebacks appear
- ✗ HP values become invalid (over max, negative)
- ✗ Game state corrupted after rest

## Notes

- **Estimated duration:** 2-3 minutes
- **Edge cases:**
  - What happens if party rests multiple times in a row?
  - Can you rest in certain rooms but not others?
  - Are there limits on how often you can rest?
  - Do certain dungeon types have rest restrictions?
- **Future extensions:**
  - Test short rest vs long rest mechanics
  - Test hit dice usage during short rest
  - Test random encounters during rest
  - Test resting in different dungeon environments
- **Related scenarios:**
  - `inventory_management.md` - Alternative healing with potions
  - `basic_combat.md` - Getting injured before testing rest
  - `death_and_unconsciousness.md` - Healing unconscious allies
