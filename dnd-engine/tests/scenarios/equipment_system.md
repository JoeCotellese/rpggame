# Test Scenario: Equipment System

## Objective

Verify that equipping and unequipping items works correctly, affects character stats (AC, attack bonus), and handles edge cases properly.

## Prerequisites

- **Game state:** existing save with party
- **Required data:** Party with multiple characters having equipment options
- **Special setup:** Characters should have weapons, armor, or other equippable items in inventory

## Setup Steps

1. Start game and load save
   - **Command:** `python -m dnd_engine.main_v2`
   - **Expected:** Main menu appears

2. Load existing game
   - **Command:** `2` → select slot
   - **Expected:** Game loads with party

3. Check starting equipment
   - **Command:** `inventory`
   - **Expected:** Shows equipped items and available equipment

## Test Actions

### 1. View Current Equipment
1. Check party status to see equipped items
   - **Command:** `status`
   - **Expected:** Shows AC and attack bonuses for all characters

2. View inventory with equipment details
   - **Command:** `inventory`
   - **Expected:** Shows equipped items marked/highlighted

3. Examine specific character (if command exists)
   - **Command:** `examine Bob` or similar
   - **Expected:** Shows detailed equipment loadout

### 2. Equip Weapon
1. Note current attack bonus
   - **Command:** `status`
   - **Expected:** Record current attack bonus

2. Equip a weapon
   - **Command:** `equip longsword on Bob`
   - **Expected:** Weapon equipped successfully message

3. Verify stat changes
   - **Command:** `status`
   - **Expected:** Attack bonus and damage updated to reflect new weapon

### 3. Unequip Item
1. Unequip weapon
   - **Command:** `unequip weapon on Bob`
   - **Expected:** Weapon removed, goes back to inventory

2. Verify stats changed back
   - **Command:** `status`
   - **Expected:** Attack bonus reflects unarmed or default weapon

3. Check inventory for unequipped item
   - **Command:** `inventory`
   - **Expected:** Previously equipped weapon now in inventory

### 4. Equip Armor
1. Note current AC
   - **Command:** `status`
   - **Expected:** Record current AC

2. Equip armor
   - **Command:** `equip chain_mail on Bob`
   - **Expected:** Armor equipped successfully

3. Verify AC changed
   - **Command:** `status`
   - **Expected:** AC increased based on armor type

### 5. Test Equipment Edge Cases

1. Try to equip item character can't use (if applicable)
   - **Command:** `equip heavy_armor on Wizard` (if wizard can't use heavy armor)
   - **Expected:** Error message about proficiency or class restrictions

2. Try to equip item to non-existent character
   - **Command:** `equip sword on Gandalf` (if Gandalf not in party)
   - **Expected:** Error message about invalid target

3. Try to equip item not in inventory
   - **Command:** `equip excalibur on Bob`
   - **Expected:** Error message: "Item not found"

4. Try to unequip empty slot
   - **Command:** `unequip shield on Bob` (if no shield equipped)
   - **Expected:** Error message or "Nothing equipped in that slot"

### 6. Multiple Equipment Slots
1. Equip items in different slots
   - **Command:** `equip longsword on Bob` → `equip shield on Bob`
   - **Expected:** Both items equipped simultaneously

2. Verify cumulative bonuses
   - **Command:** `status`
   - **Expected:** Stats reflect all equipped items

## Expected Outcomes

- ✓ Equipment commands (equip/unequip) are recognized
- ✓ Equipping weapons changes attack bonus and damage
- ✓ Equipping armor changes AC
- ✓ Unequipping items returns them to inventory
- ✓ Stats update immediately after equipment changes
- ✓ Status command reflects current equipment
- ✓ Cannot equip items character isn't proficient with (or shows warning)
- ✓ Cannot equip non-existent items
- ✓ Cannot target non-existent characters
- ✓ Multiple items can be equipped in different slots
- ✓ No exceptions or crashes occur

## Failure Conditions

- ✗ Equipment commands not recognized
- ✗ Stats don't update after equipping items
- ✗ Items disappear after equipping
- ✗ Cannot unequip items
- ✗ Equipment affects wrong character
- ✗ AC or attack calculations are incorrect
- ✗ Can equip multiple items in same slot (unless intentional)
- ✗ Equipment persists after character death
- ✗ Python exceptions or tracebacks appear
- ✗ Game crashes during equipment changes

## Notes

- **Estimated duration:** 4-5 minutes
- **Edge cases:**
  - Can rogues equip heavy armor?
  - Can wizards use martial weapons?
  - What happens if you equip weapon while holding another?
  - Do magical items have special restrictions?
  - Can you equip items during combat?
- **Future extensions:**
  - Test two-handed weapons
  - Test dual-wielding mechanics
  - Test shield + weapon combinations
  - Test armor weight/class restrictions
  - Test magical item attunement (if implemented)
  - Test equipment during combat
- **Related scenarios:**
  - `inventory_management.md` - Viewing and managing items
  - `basic_combat.md` - Equipment effects in combat
  - `new_game_party_creation.md` - Starting equipment
