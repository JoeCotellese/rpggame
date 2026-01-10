# Test Scenario: Search and Loot

## Objective

Verify that searching rooms, finding loot, and taking items works correctly.

## Prerequisites

- **Game state:** existing save with party OR new game
- **Required data:** Party in dungeon with searchable rooms
- **Special setup:** Rooms should contain loot (gold, items)

## Setup Steps

1. Start game and load/create campaign
   - **Command:** `python -m dnd_engine.main_v2`
   - **Expected:** Main menu appears

2. Load or start game with party in dungeon
   - **Command:** Load existing save or create new campaign
   - **Expected:** Party in dungeon ready to explore

3. Navigate to unexplored room
   - **Command:** `n`, `s`, `e`, or `w` as needed
   - **Expected:** Enter new room

## Test Actions

### 1. Search Room
1. Examine current room
   - **Command:** `look`
   - **Expected:** Room description displayed

2. Search the room
   - **Command:** `search`
   - **Expected:** Either "You found items!" or "You found nothing" message

3. Check what was found (if anything)
   - **Expected:** Display shows gold, items, or "nothing found"

### 2. Take Gold
1. If gold was found, take it
   - **Command:** `take currency` or `take gold` or interactive prompt
   - **Expected:** Gold added to party inventory

2. Verify gold added
   - **Command:** `inventory`
   - **Expected:** Party gold count increased

3. Try to take gold again from same room
   - **Command:** `take currency`
   - **Expected:** "No gold here" or "Already taken" message

### 3. Take Items
1. If items were found, take one
   - **Command:** `take dagger` (or whatever item was found) or use interactive prompt
   - **Expected:** Item added to character's inventory

2. Verify item added
   - **Command:** `inventory`
   - **Expected:** Item appears in party inventory

3. Try to take item again
   - **Command:** `take dagger`
   - **Expected:** "Item not found" or "Already taken" message

### 4. Take Multiple Items
1. Search room with multiple items (find another room if needed)
   - **Command:** Navigate and `search`
   - **Expected:** Multiple items displayed

2. Take first item
   - **Command:** `take <item_name>`
   - **Expected:** First item taken

3. Take second item
   - **Command:** `take <item_name>`
   - **Expected:** Second item taken

4. Verify both items in inventory
   - **Command:** `inventory`
   - **Expected:** Both items present

### 5. Edge Cases

1. Search empty room
   - **Command:** Navigate to room, then `search`
   - **Expected:** "You found nothing" or similar message

2. Search room multiple times
   - **Command:** `search` → `search` again
   - **Expected:** Should not find duplicate items

3. Try to take non-existent item
   - **Command:** `take legendary_sword`
   - **Expected:** Error message: "Item not found"

4. Search during combat (if possible)
   - **Command:** Engage enemy, then try `search`
   - **Expected:** Should not allow searching during combat

5. Check room loot respawn
   - **Command:** Leave room and return, then `search`
   - **Expected:** Loot should not respawn (unless intentional game mechanic)

### 6. Interactive Item Selection
1. If multiple items in room, test interactive selection
   - **Command:** `take` (without specifying item)
   - **Expected:** Interactive menu shows available items

2. Select item from menu
   - **Expected:** Selected item added to inventory

3. Cancel item selection
   - **Expected:** Returns to game without taking item

## Expected Outcomes

- ✓ Search command works in all rooms
- ✓ Found items and gold are displayed clearly
- ✓ Take command adds items to inventory
- ✓ Gold is tracked correctly
- ✓ Items cannot be taken twice from same location
- ✓ Empty rooms show appropriate "nothing found" message
- ✓ Invalid item names show error messages
- ✓ Inventory updates immediately after taking items
- ✓ Cannot search during combat
- ✓ Interactive item selection works (if implemented)
- ✓ No exceptions or crashes occur

## Failure Conditions

- ✗ Search command not recognized
- ✗ Found items not displayed
- ✗ Take command doesn't work
- ✗ Items or gold not added to inventory
- ✗ Can take same item multiple times
- ✗ Items disappear after taking
- ✗ Gold count incorrect
- ✗ Can search during combat
- ✗ Loot respawns when it shouldn't
- ✗ Python exceptions or tracebacks appear
- ✗ Game crashes during search/loot operations

## Notes

- **Estimated duration:** 4-5 minutes
- **Edge cases:**
  - Do different rooms have different loot tables?
  - Are there hidden items requiring skill checks?
  - Can you search the same room after defeating enemies?
  - Do searched rooms get marked/remembered?
  - Is there inventory weight/limit?
- **Future extensions:**
  - Test skill checks for hidden items (perception, investigation)
  - Test container/chest searching
  - Test trapped loot
  - Test cursed items
  - Test sharing loot among party members
  - Test searching after combat (dead enemies drop loot)
- **Related scenarios:**
  - `inventory_management.md` - Managing acquired items
  - `equipment_system.md` - Equipping found items
  - `basic_combat.md` - Looting after defeating enemies
  - `dungeon_exploration.md` - Finding rooms to search
