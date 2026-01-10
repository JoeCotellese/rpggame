# Test Scenario: Death and Unconsciousness

## Objective

Verify that character death, unconsciousness, death saves, and stabilization mechanics work correctly according to D&D 5E rules.

## Prerequisites

- **Game state:** existing save with party
- **Required data:** Party with characters (recommend using party with normal HP, not tripled)
- **Special setup:** Party should be able to engage enemies that can reduce character to 0 HP

## Setup Steps

1. Start game and load save
   - **Command:** `python -m dnd_engine.main_v2`
   - **Expected:** Main menu appears

2. Load game with party
   - **Command:** `2` → select slot
   - **Expected:** Party loaded in dungeon

3. Navigate to room with enemies
   - **Command:** Navigate as needed
   - **Expected:** Encounter enemies

## Test Actions

### 1. Character Reaches 0 HP
1. Engage in combat
   - **Expected:** Combat begins

2. Allow character to be reduced to 0 HP
   - **Command:** Continue combat, let enemy attack until character reaches 0 HP
   - **Expected:** Character becomes unconscious

3. Check character status
   - **Command:** `status` during combat
   - **Expected:** Character shows as unconscious or at 0 HP

4. Verify unconscious character cannot act
   - **Expected:** Cannot select unconscious character for actions

### 2. Death Saves
1. Continue combat rounds
   - **Expected:** Unconscious character makes death saves automatically each round

2. Observe death save results
   - **Expected:** Display shows death save rolls (success/failure)

3. Track death save successes and failures
   - **Expected:** Game tracks 3 successes = stabilized, 3 failures = death

4. Let character stabilize OR die (depending on rolls)
   - **Expected:** Either "Character stabilized!" or "Character died!"

### 3. Stabilize Command
1. Get different character to 0 HP
   - **Command:** Continue combat or start new encounter
   - **Expected:** Another character unconscious

2. Attempt to stabilize with ally
   - **Command:** `stabilize <character_name>` on ally's turn
   - **Expected:** Medicine check performed

3. Check stabilization result
   - **Expected:** If check succeeds: character stabilized, if fails: character still dying

4. Verify stabilized character stops making death saves
   - **Expected:** No more death saves, remains at 0 HP but stable

### 4. Healing Unconscious Character
1. Have character at 0 HP
   - **Expected:** Unconscious character

2. Attempt to heal with potion or spell
   - **Command:** `use potion_of_healing on <unconscious_character>`
   - **Expected:** Character regains HP and consciousness

3. Verify character can act again
   - **Expected:** Character back in initiative, can take turns

4. Check HP after revival
   - **Command:** `status`
   - **Expected:** HP matches healing received (e.g., potion restored 2d4+2 HP)

### 5. Character Death
1. Get character to 0 HP
   - **Expected:** Unconscious

2. Allow 3 failed death saves (or take massive damage)
   - **Expected:** Character dies permanently

3. Verify dead character status
   - **Command:** `status`
   - **Expected:** Character shown as dead

4. Attempt to heal dead character
   - **Command:** `use potion_of_healing on <dead_character>`
   - **Expected:** Either not allowed or doesn't revive (potions don't revive in 5E)

5. Check if dead character affects party
   - **Expected:** Party continues with remaining members

### 6. Total Party Kill (TPK)
1. (Optional/Dangerous) Allow entire party to die
   - **Expected:** All characters at 0 HP or dead

2. Check game over condition
   - **Expected:** Game over message, return to main menu, or other TPK handling

### 7. Edge Cases

1. Massive damage (instant death)
   - **Command:** If possible, take damage >= current HP + max HP
   - **Expected:** Instant death without death saves (5E rule)

2. Stabilize at exactly 3 successes
   - **Expected:** Character stabilizes automatically

3. Critical hit while unconscious
   - **Expected:** Counts as 2 failed death saves (5E rule)

4. Healing word / in-combat healing
   - **Command:** Cast healing spell on unconscious ally
   - **Expected:** Ally revives immediately, can act same round

## Expected Outcomes

- ✓ Characters become unconscious at 0 HP
- ✓ Death saves are rolled automatically each round
- ✓ 3 successes = stabilized, 3 failures = death
- ✓ Stabilize command works with Medicine check
- ✓ Healing unconscious character revives them
- ✓ Dead characters cannot be healed with potions
- ✓ Unconscious characters cannot take actions
- ✓ Death saves are tracked correctly
- ✓ TPK triggers game over condition
- ✓ Massive damage causes instant death
- ✓ No exceptions or crashes during death mechanics

## Failure Conditions

- ✗ Characters don't become unconscious at 0 HP
- ✗ Death saves don't occur
- ✗ Death save tracking is incorrect
- ✗ Cannot stabilize allies
- ✗ Healing doesn't revive unconscious characters
- ✗ Dead characters can still act
- ✗ Potions revive dead characters (shouldn't in 5E)
- ✗ TPK doesn't end game
- ✗ Massive damage doesn't cause instant death
- ✗ Python exceptions or tracebacks appear
- ✗ Game crashes during death mechanics

## Notes

- **Estimated duration:** 6-8 minutes (depends on combat)
- **Edge cases:**
  - What happens if healer is unconscious?
  - Can you flee combat with unconscious allies?
  - Do unconscious allies get experience?
  - What happens to unconscious character's equipment?
  - Is there resurrection magic available?
- **Future extensions:**
  - Test spare the dying cantrip
  - Test resurrection spells (if implemented)
  - Test death ward spell
  - Test temporary HP preventing unconsciousness
  - Test different damage types affecting death saves
  - Test conditions affecting death saves (poisoned, etc.)
- **Related scenarios:**
  - `basic_combat.md` - Getting into combat
  - `rest_and_healing.md` - Alternative to combat healing
  - `inventory_management.md` - Using healing potions
