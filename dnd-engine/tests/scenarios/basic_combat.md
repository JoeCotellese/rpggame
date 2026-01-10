# Test Scenario: Basic Combat Flow

## Objective
Verify that a newly created party can enter a dungeon, engage in combat, and complete a fight without crashes or errors.

## Setup Steps
1. Start the game (assume clean state, no existing saves)
2. Select "New Campaign" from main menu
3. Create a party with default characters:
   - Fighter (any name)
   - Wizard (any name)
   - Rogue (any name)
4. Select "Goblin Warren" as the starting dungeon

## Test Actions
1. Enter the first room
2. If enemies are present:
   - Initiate combat (or wait for automatic combat)
   - Have Fighter attack enemies
   - Have Wizard use offensive spells if available
   - Have Rogue attack enemies
   - Continue until combat resolves (victory, defeat, or flee)
3. If no enemies, search the room and move to next room

## Expected Outcomes
- ✓ Game starts without errors
- ✓ Party creation completes successfully
- ✓ Dungeon loads and displays room description
- ✓ Combat system engages properly
- ✓ All characters can take actions
- ✓ Combat resolves (no infinite loops or hangs)
- ✓ Character HP updates correctly
- ✓ No exceptions or error messages in output

## Failure Conditions
- ✗ Game crashes or exits unexpectedly
- ✗ Combat hangs or loops infinitely
- ✗ Character actions don't register
- ✗ HP values become negative or invalid
- ✗ Python exceptions or tracebacks appear
- ✗ Unhandled input prompts (game waiting for input we can't provide)

## Notes
- This is a basic smoke test for core game loop
- Should complete in under 2 minutes
- Can be extended to test multiple rooms/encounters
