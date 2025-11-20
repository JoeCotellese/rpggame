# Test Scenario: Inventory Management

## Objective

Verify that inventory viewing, item usage, and party item management work correctly across multiple characters.

## Prerequisites

- **Game state:** existing save with party
- **Required data:** Party with multiple characters (recommend slot 1: Shadow, Bob, Tim with tripled HP)
- **Special setup:** Characters should have various items (potions, equipment)

## Setup Steps

1. Start the game
   - **Command:** `python -m dnd_engine.main_v2`
   - **Expected:** Main menu appears

2. Load existing save
   - **Command:** `2` (Load Game)
   - **Expected:** Save slot selection appears

3. Select slot with party
   - **Command:** `1` (or appropriate slot number)
   - **Expected:** Game loads, party enters dungeon

## Test Actions

### 1. View Party Inventory
1. Check overall inventory
   - **Command:** `inventory`
   - **Expected:** Display shows all items across party members

2. Check status to see who has what
   - **Command:** `status`
   - **Expected:** Party status table shows all characters

### 2. Use Consumable Item (Potion)
1. Use potion without specifying target (should prompt)
   - **Command:** `use`
   - **Expected:** Interactive menu shows available consumables and targets

2. Use potion with explicit command
   - **Command:** `use potion_of_healing on Bob`
   - **Expected:** Bob heals, potion removed from inventory, HP increases

3. Verify potion was consumed
   - **Command:** `inventory`
   - **Expected:** Potion count decreased by 1

### 3. Check Inventory After Use
1. View inventory again
   - **Command:** `inventory`
   - **Expected:** Updated item counts, potion quantity reduced

2. Check character status
   - **Command:** `status`
   - **Expected:** Bob's HP should be increased

### 4. Edge Cases

1. Try to use non-existent item
   - **Command:** `use magical_banana`
   - **Expected:** Error message: "Item not found" or similar

2. Try to use item on invalid target
   - **Command:** `use potion_of_healing on gandalf` (if Gandalf not in party)
   - **Expected:** Error message about invalid target

3. View inventory with filter (if supported)
   - **Command:** `inventory consumables`
   - **Expected:** Shows only consumable items

## Expected Outcomes

- ✓ Inventory command displays all party items
- ✓ Status command shows current party state
- ✓ Use command works with interactive prompts
- ✓ Use command works with explicit syntax (item + target)
- ✓ Items are consumed and removed from inventory
- ✓ HP changes are reflected immediately
- ✓ Invalid item names show error messages
- ✓ Invalid targets show error messages
- ✓ Inventory updates after item usage
- ✓ No exceptions or error messages for valid operations

## Failure Conditions

- ✗ Inventory not showing items
- ✗ Items not being consumed after use
- ✗ HP not changing after using healing items
- ✗ Inventory showing incorrect counts
- ✗ Python exceptions or tracebacks appear
- ✗ Game crashes or exits unexpectedly
- ✗ Items affecting wrong character
- ✗ Duplicate items appearing in inventory

## Notes

- **Estimated duration:** 3-4 minutes
- **Edge cases:**
  - What happens if you try to use a potion on a character at full HP?
  - Can you use items from one character's inventory on another character?
  - What happens when you run out of a consumable?
- **Future extensions:**
  - Test inventory during combat vs exploration
  - Test multi-item usage in succession
  - Test inventory limits (if any)
- **Related scenarios:**
  - `equipment_system.md` - For equippable items
  - `search_and_loot.md` - For acquiring items
