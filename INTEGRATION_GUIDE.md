# Save Slot System Integration Guide (Issue #92)

This guide explains how to integrate the new save slot system into the existing D&D terminal game.

## Overview

The new save slot system has been implemented with the following components:

### ✅ Completed Components

1. **SaveSlot** (`dnd_engine/core/save_slot.py`)
   - Data model for individual save slots
   - Auto-generated names: "{Adventure} - {Party} - {Progress} - {Playtime}"
   - Custom name support
   - Playtime tracking

2. **SaveSlotManager** (`dnd_engine/core/save_slot_manager.py`)
   - Manages 10 fixed save slots (slot_01.json through slot_10.json)
   - Save/load game state
   - Slot clearing and renaming
   - Stored in `~/.dnd_game/saves/`

3. **CharacterVaultV2** (`dnd_engine/core/character_vault_v2.py`)
   - Single-file character storage (`~/.dnd_game/character_vault.json`)
   - Usage tracking (times_used, last_used, save_slots_used)
   - Character CRUD operations

4. **MigrationManager** (`dnd_engine/core/migration.py`)
   - Migrates old campaigns from `~/.dnd_terminal/` to new system
   - Backs up old data automatically
   - Deduplicates characters (keeps highest level)

5. **Unit Tests** (`tests/test_save_slot*.py`, `tests/test_character_vault_v2.py`)
   - 43 passing tests covering all core functionality

## Integration Steps

### 1. Update Main Menu

The main menu (`dnd_engine/ui/main_menu.py`) currently uses `CampaignManager`. Update it to use `SaveSlotManager`:

```python
from dnd_engine.core.save_slot_manager import SaveSlotManager
from dnd_engine.core.migration import MigrationManager

class MainMenu:
    def __init__(self):
        # Check for migration first
        migration_manager = MigrationManager()
        if migration_manager.should_migrate():
            self._handle_migration(migration_manager)

        # Use new save slot manager
        self.slot_manager = SaveSlotManager()

    def _handle_migration(self, migration_manager):
        """Display migration UI and perform migration."""
        info = migration_manager.get_migration_info()

        # Show migration info to user
        print(f"\n{'='*60}")
        print("MIGRATION DETECTED")
        print(f"{'='*60}")
        print(f"Found {info['total_campaigns']} old campaigns")
        print(f"Will migrate {info['migratable_campaigns']} most recent")
        print(f"Will extract {info['total_characters']} unique characters")
        print(f"\nBackup will be created at: ~/.dnd_terminal/backup_pre_migration/")

        # Confirm migration
        confirm = input("\nProceed with migration? (yes/no): ")

        if confirm.lower() == 'yes':
            success, message, stats = migration_manager.migrate()
            print(f"\n{message}")
            if stats.get('errors'):
                print("\nWarnings:")
                for error in stats['errors']:
                    print(f"  - {error}")
        else:
            print("Migration cancelled.")
            print("Note: You can migrate later by deleting ~/.dnd_game/")
```

### 2. Update Load Game Flow

Replace the campaign/save selection flow with slot selection:

```python
def show_load_game_menu(self):
    """Show load game menu with save slots."""
    slots = self.slot_manager.list_slots()

    # Filter out empty slots
    used_slots = [slot for slot in slots if not slot.is_empty()]

    if not used_slots:
        print("No saved games found.")
        return None

    # Display slots
    print("\n" + "="*60)
    print("LOAD GAME")
    print("="*60)

    for slot in used_slots:
        print(f"\n[{slot.slot_number}] {slot.get_display_name()}")
        print(f"    Last played: {slot.get_last_played_display()}")
        print(f"    Playtime: {slot._format_playtime()}")
        if slot.party_composition:
            print(f"    Party: {', '.join(slot.party_composition)}")

    print(f"\n[0] Back")

    # Get user choice
    choice = input("\nSelect slot number: ")

    try:
        slot_num = int(choice)
        if slot_num == 0:
            return None

        if 1 <= slot_num <= 10:
            # Load game state
            game_state = self.slot_manager.load_game(slot_num)
            return game_state
        else:
            print("Invalid slot number.")
            return None

    except ValueError:
        print("Invalid input.")
        return None
```

### 3. Update New Game Flow

Replace campaign creation wizard with character vault selection + slot selection:

```python
from dnd_engine.core.character_vault_v2 import CharacterVaultV2

def show_new_game_menu(self):
    """Show new game menu with character vault and slot selection."""
    vault = CharacterVaultV2()

    # Step 1: Select characters from vault or create new
    print("\n" + "="*60)
    print("NEW GAME - SELECT PARTY")
    print("="*60)

    party_characters = self._select_party_from_vault(vault)

    if not party_characters:
        print("No party selected. Returning to menu.")
        return None

    # Step 2: Select adventure
    adventure = self._select_adventure()

    if not adventure:
        print("No adventure selected. Returning to menu.")
        return None

    # Step 3: Select save slot
    print("\n" + "="*60)
    print("SELECT SAVE SLOT")
    print("="*60)

    slots = self.slot_manager.list_slots()

    # Show all 10 slots
    for slot in slots:
        status = "EMPTY" if slot.is_empty() else slot.get_display_name()
        print(f"[{slot.slot_number}] {status}")

    choice = input("\nSelect slot number (1-10): ")

    try:
        slot_num = int(choice)
        if not 1 <= slot_num <= 10:
            print("Invalid slot number.")
            return None

        # Confirm overwrite if slot is not empty
        if not slots[slot_num - 1].is_empty():
            confirm = input(f"Slot {slot_num} is not empty. Overwrite? (yes/no): ")
            if confirm.lower() != 'yes':
                print("Cancelled.")
                return None

        # Create game state
        from dnd_engine.core.party import Party
        from dnd_engine.core.game_state import GameState

        party = Party(party_characters)
        game_state = GameState(
            party=party,
            dungeon_name=adventure
        )

        # Save to slot
        self.slot_manager.save_game(
            slot_number=slot_num,
            game_state=game_state,
            playtime_delta=0
        )

        # Record character usage
        for character in party_characters:
            char_id = self._get_character_id_from_vault(vault, character.name)
            if char_id:
                vault.record_usage(char_id, slot_num)

        return game_state

    except ValueError:
        print("Invalid input.")
        return None

def _select_party_from_vault(self, vault):
    """Select party members from character vault."""
    characters_info = vault.list_characters()

    print("\nAvailable characters:")
    for i, char_info in enumerate(characters_info, 1):
        print(f"[{i}] {char_info['name']} - Level {char_info['level']} {char_info['class']}")
        if char_info['times_used'] > 0:
            print(f"    Used {char_info['times_used']} times")

    print(f"\n[0] Create new character(s)")

    # Allow user to select 1-6 characters
    selected = []

    while len(selected) < 6:
        choice = input(f"\nSelect character #{len(selected)+1} (or press Enter to finish): ")

        if not choice:
            break

        try:
            idx = int(choice)

            if idx == 0:
                # Create new character
                new_char = self._create_character_wizard()
                if new_char:
                    char_id = vault.add_character(new_char)
                    selected.append(new_char)
            elif 1 <= idx <= len(characters_info):
                char_info = characters_info[idx - 1]
                character = vault.get_character(char_info['id'])
                selected.append(character)
            else:
                print("Invalid selection.")

        except ValueError:
            print("Invalid input.")

    return selected
```

### 4. Update Game Loop Auto-Save

Update the game loop (`dnd_engine/cli.py`) to use new save system:

```python
from dnd_engine.core.save_slot_manager import SaveSlotManager

class GameCLI:
    def __init__(self, game_state, slot_number):
        self.game_state = game_state
        self.slot_number = slot_number
        self.slot_manager = SaveSlotManager()
        self.session_start = datetime.now()

    def auto_save(self):
        """Auto-save game to current slot."""
        # Calculate session playtime
        playtime_delta = int((datetime.now() - self.session_start).total_seconds())

        # Save to slot
        self.slot_manager.save_game(
            slot_number=self.slot_number,
            game_state=self.game_state,
            playtime_delta=playtime_delta
        )

        print("[Auto-saved]")
```

### 5. Add Save Slot Management Menu

Add a new menu option for managing save slots:

```python
def show_save_slot_management_menu(self):
    """Show menu for managing save slots (rename, clear, etc.)."""
    while True:
        slots = self.slot_manager.list_slots()

        print("\n" + "="*60)
        print("SAVE SLOT MANAGEMENT")
        print("="*60)

        for slot in slots:
            status = "EMPTY" if slot.is_empty() else slot.get_display_name()
            print(f"[{slot.slot_number}] {status}")

        print("\nActions:")
        print("[R] Rename slot")
        print("[C] Clear slot")
        print("[0] Back")

        choice = input("\nSelect action: ").upper()

        if choice == '0':
            break
        elif choice == 'R':
            slot_num = int(input("Slot number to rename: "))
            new_name = input("Enter custom name (or leave empty to use auto-name): ")
            self.slot_manager.rename_slot(slot_num, new_name)
            print(f"Slot {slot_num} renamed.")
        elif choice == 'C':
            slot_num = int(input("Slot number to clear: "))
            confirm = input(f"Clear slot {slot_num}? This cannot be undone! (yes/no): ")
            if confirm.lower() == 'yes':
                self.slot_manager.clear_slot(slot_num)
                print(f"Slot {slot_num} cleared.")
```

## Testing the Integration

1. **Test Migration**:
   ```bash
   # If you have old campaigns, test migration
   python -m dnd_engine.main
   # Should detect old campaigns and prompt for migration
   ```

2. **Test New Game Flow**:
   - Create new game
   - Select/create characters
   - Choose adventure
   - Select save slot
   - Start game

3. **Test Load Game**:
   - Load from save slot
   - Verify party and progress are correct

4. **Test Auto-Save**:
   - Play game
   - Verify auto-saves update the correct slot
   - Check playtime is accumulating

5. **Test Slot Management**:
   - Rename slots
   - Clear slots
   - Verify changes persist

## File Structure After Integration

```
~/.dnd_game/
├── saves/
│   ├── slot_01.json
│   ├── slot_02.json
│   ├── ... (up to slot_10.json)
└── character_vault.json

~/.dnd_terminal/  (old system)
└── backup_pre_migration/  (created during migration)
    └── campaigns/
        └── [old campaign data]
```

## Rollback Plan

If issues occur, users can:

1. Delete `~/.dnd_game/` directory
2. Restore from `~/.dnd_terminal/backup_pre_migration/`
3. Copy back to `~/.dnd_terminal/campaigns/`

## Success Metrics (from Issue #92)

Monitor these metrics post-launch:

- **Time to first game**: < 60 seconds (Goal: under 60s)
- **Vault adoption**: Track % of users who use character vault
- **Load success rate**: > 95% on first try
- **Migration success**: 100%
- **Save corruption**: < 0.1%

## Next Steps

1. Implement the integration points above in the actual UI files
2. Test thoroughly with manual play testing
3. Update documentation for users
4. Consider adding additional features from "Out of Scope" list as future enhancements

## References

- Original Issue: #92
- Implementation Files:
  - `dnd_engine/core/save_slot.py`
  - `dnd_engine/core/save_slot_manager.py`
  - `dnd_engine/core/character_vault_v2.py`
  - `dnd_engine/core/migration.py`
- Test Files:
  - `tests/test_save_slot.py`
  - `tests/test_save_slot_manager.py`
  - `tests/test_character_vault_v2.py`
