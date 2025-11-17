# D&D 5E Terminal Game - Development TODO

This document tracks remaining implementation tasks to complete the MVP and future enhancements based on the SPEC.md.

**Last Updated:** 2025-11-16
**Current Status:** Core systems implemented, LLM integration and character creation pending

---

## Current Implementation Status

### ✅ Completed Components

- **Core Systems**
  - ✅ Dice roller with advantage/disadvantage (`dnd_engine/core/dice.py`)
  - ✅ Creature base class with abilities and HP tracking (`dnd_engine/core/creature.py`)
  - ✅ Character class extending Creature (`dnd_engine/core/character.py`)
  - ✅ Combat engine with attack resolution (`dnd_engine/core/combat.py`)
  - ✅ Initiative tracker (`dnd_engine/systems/initiative.py`)
  - ✅ Inventory system with equipment slots (`dnd_engine/systems/inventory.py`)
  - ✅ Game state manager (`dnd_engine/core/game_state.py`)
  - ✅ Event bus for pub/sub (`dnd_engine/utils/events.py`)
  - ✅ Party system for 4-character gameplay (`dnd_engine/core/party.py`)

- **Data Layer**
  - ✅ JSON data loader (`dnd_engine/rules/loader.py`)
  - ✅ Monster definitions (`dnd_engine/data/srd/monsters.json`)
  - ✅ Items definitions (`dnd_engine/data/srd/items.json`)
  - ✅ Class definitions (`dnd_engine/data/srd/classes.json`)
  - ✅ Goblin Warren dungeon (`dnd_engine/data/content/dungeons/goblin_warren.json`)

- **User Interface**
  - ✅ CLI implementation (`dnd_engine/ui/cli.py`)
  - ✅ Combat loop
  - ✅ Exploration commands
  - ✅ Inventory management commands

- **Testing**
  - ✅ Unit tests for dice, combat, creatures
  - ✅ Integration tests for inventory
  - ✅ End-to-end tests for inventory

---

## 🚧 MVP Phase - Remaining Tasks

### Priority 1: Critical for Playable Game

#### 1.1 Character Creation System ✅ COMPLETED
**Location:** `dnd_engine/core/character_factory.py`
**Dependencies:** Dice roller, Character class, CLI
**Estimated Effort:** Medium (6.5 hours)
**GitHub Issue:** #7
**Completed:** 2025-11-16

**Tasks:**
- [x] Create `CharacterFactory` class
  - [x] `roll_abilities()` - Roll 4d6 drop lowest, six times
  - [x] `auto_assign_abilities(scores, class_name)` - Assign scores based on class priorities from JSON
  - [x] `swap_abilities(abilities, ability1, ability2)` - Allow player swaps
  - [x] `calculate_derived_stats(class, abilities)` - Calculate HP, AC, attack bonus
  - [x] `apply_starting_equipment(character, class)` - Add starting gear from class JSON
  - [x] `create_character_interactive(ui)` - Full creation flow
- [x] Add unit tests for `CharacterFactory`
  - [x] Test ability rolling (4d6 drop lowest)
  - [x] Test auto-assignment follows class priorities correctly
  - [x] Test ability swapping
  - [x] Test derived stat calculation (HP from d10+CON, AC from armor, etc.)
  - [x] Test starting equipment application
- [x] Integrate into main.py entry point
  - [x] Prompt player to create character before starting game
  - [x] Display rolled abilities with drop-lowest detail
  - [x] Show optimized character sheet
  - [x] Allow swaps before accepting
  - [x] Prompt for character name

**Acceptance Criteria:**
- ✅ Player can roll abilities and see each 4d6 result with dropped die
- ✅ System auto-assigns scores optimally for Fighter class
- ✅ Player can swap any two abilities
- ✅ Character sheet displays with accurate HP, AC, attack/damage bonuses
- ✅ Starting equipment (chain mail, longsword, etc.) is equipped correctly

---

#### 1.2 LLM Integration Layer ✅ COMPLETED
**Location:** `dnd_engine/llm/` directory
**Dependencies:** Event bus, OpenAI/Anthropic API
**Estimated Effort:** Large (8 hours)
**GitHub Issue:** #8
**Completed:** 2025-11-16

**Tasks:**

**1.2.1 LLM Provider Interface**
- [x] Create `dnd_engine/llm/base.py`
  - [ ] Define `LLMProvider` abstract base class
  - [ ] Method: `enhance_description(context: Dict) -> str`
  - [ ] Method: `generate_dialogue(npc: Dict, player_input: str) -> str`
- [ ] Create `dnd_engine/llm/claude.py`
  - [ ] Implement `ClaudeProvider` extending `LLMProvider`
  - [ ] Add async support using `anthropic` library
  - [ ] Add timeout handling (10 seconds)
  - [ ] Add error handling with graceful degradation
  - [ ] Add caching for common descriptions (monster appearances, room types)

**1.2.2 Prompt Templates**
- [ ] Create `dnd_engine/llm/prompts.py`
  - [ ] `COMBAT_ACTION_PROMPT` - Template for combat narration
  - [ ] `ROOM_DESCRIPTION_PROMPT` - Template for room atmosphere
  - [ ] `NPC_DIALOGUE_PROMPT` - Template for NPC responses
  - [ ] `DEATH_PROMPT` - Template for death narration
  - [ ] `VICTORY_PROMPT` - Template for combat victory
  - [ ] Helper function to build prompts with context

**1.2.3 LLM Enhancer**
- [ ] Create `dnd_engine/llm/enhancer.py`
  - [ ] `LLMEnhancer` class that subscribes to events
  - [ ] Subscribe to `ROOM_ENTER` - enhance room descriptions
  - [ ] Subscribe to `DAMAGE_DEALT` - enhance combat narration
  - [ ] Subscribe to `COMBAT_END` - enhance victory/defeat narration
  - [ ] Subscribe to `CHARACTER_DEATH` - enhance death narration
  - [ ] Fallback to basic descriptions if LLM fails/times out
  - [ ] Cache frequently used descriptions

**1.2.4 Environment Setup**
- [ ] Add `ANTHROPIC_API_KEY` to .env.example
- [ ] Update README with LLM setup instructions
- [ ] Add --no-llm flag to disable LLM for faster play

**1.2.5 Testing**
- [ ] Unit tests for prompt template generation
- [ ] Mock tests for LLM provider (don't call real API)
- [ ] Integration tests with event bus
- [ ] Test graceful degradation when API unavailable
- [ ] Test timeout handling
- [ ] Test caching behavior

**Acceptance Criteria:**
- Room descriptions are enhanced with atmospheric details
- Combat actions have vivid, 2-3 sentence narrations
- Game continues working even if LLM API fails
- No mechanical changes from LLM (only narrative enhancement)
- Descriptions are cached to reduce API calls
- --no-llm flag works for testing

---

#### 1.3 Main Entry Point & Game Loop ✅ COMPLETED
**Location:** `dnd_engine/main.py`
**Dependencies:** CharacterFactory, GameState, CLI, LLMEnhancer
**Estimated Effort:** Small (6 hours)
**GitHub Issue:** #9
**Completed:** 2025-11-16

**Tasks:**
- [x] Update `main.py` with complete game flow
  - [x] Parse command-line arguments (--no-llm, --dungeon-name)
  - [x] Check for ANTHROPIC_API_KEY (if LLM enabled)
  - [x] Run character creation via CharacterFactory
  - [x] Initialize GameState with created character
  - [x] Initialize LLMEnhancer and subscribe to events (if enabled)
  - [x] Initialize CLI with game state
  - [x] Start game loop via CLI.run()
  - [x] Handle exceptions and display user-friendly errors
- [x] Add entry point configuration
  - [x] Update pyproject.toml with console_scripts entry point
  - [x] Test running via `python -m dnd_engine.main`
  - [x] Test running via installed command `dnd-game`
- [x] Comprehensive test coverage
  - [x] Unit tests (tests/test_main.py)
  - [x] Integration tests (tests/test_main_integration.py)
  - [x] End-to-end tests (tests/test_main_e2e.py)

**Acceptance Criteria:**
- ✅ Game can be started with `python -m dnd_engine.main`
- ✅ Character creation runs before game starts
- ✅ LLM integration works when API key is present
- ✅ --no-llm flag disables LLM layer
- ✅ Clear error messages for missing dependencies
- ✅ 1,117 lines of tests added

---

#### 1.4 Combat & Exploration Polish
**Location:** `dnd_engine/core/game_state.py`, `dnd_engine/ui/cli.py`
**Dependencies:** Existing systems
**Estimated Effort:** Small (8.5 hours)
**GitHub Issue:** #10

**Tasks:**
- [ ] Fix combat turn flow in CLI
  - [ ] Ensure player can't act on enemy turns
  - [ ] Process all enemy turns automatically until player turn
  - [ ] Display clear turn indicators
- [ ] Add missing combat actions
  - [ ] Use item during combat (healing potions)
  - [ ] Display available actions based on inventory
- [ ] Improve exploration
  - [ ] Add "exits" command to show available directions
  - [ ] Better error messages for invalid commands
  - [ ] Show searchable rooms with hint
- [ ] Victory conditions
  - [ ] Detect when boss (goblin_boss) is defeated
  - [ ] Display victory message
  - [ ] Show final stats (XP, gold, items collected)

**Acceptance Criteria:**
- Combat flows smoothly with clear turn order
- Player can use healing potions during combat
- Victory is detected when boss is defeated
- Game shows meaningful ending

---

### Priority 2: Data & Content Completion

#### 2.1 Complete Monster Definitions ✅ COMPLETED
**Location:** `dnd_engine/data/srd/monsters.json`
**Dependencies:** None
**Estimated Effort:** Small
**Completed:** 2025-11-16

**Tasks:**
- [x] Verify all monsters in Goblin Warren are defined:
  - [x] Goblin (basic enemy)
  - [x] Wolf (companion creature)
  - [x] Goblin Boss (final boss)
- [x] Ensure all monster data is complete:
  - [x] Name, AC, HP formula, speed
  - [x] Ability scores (STR, DEX, CON, INT, WIS, CHA)
  - [x] Attack actions (name, to_hit, damage)
  - [x] XP value for each monster
  - [x] Special traits (Nimble Escape, Pack Tactics, etc.)
  - [x] Skills, senses, languages from official SRD
  - [x] CR ratings and source attribution

**Acceptance Criteria:**
- ✅ All monsters spawn correctly in dungeon
- ✅ Combat resolves properly with correct attack bonuses
- ✅ XP is awarded after defeating enemies
- ✅ Using official D&D 5E SRD (CC BY 4.0) stats

---

#### 2.2 Complete Item Definitions ✅ COMPLETED
**Location:** `dnd_engine/data/srd/items.json`
**Dependencies:** None
**Estimated Effort:** Small
**Completed:** 2025-11-16

**Tasks:**
- [x] Verify all items in Goblin Warren are defined:
  - [x] Weapons: longsword, shortsword, dagger, light_crossbow
  - [x] Armor: chain_mail, leather_armor
  - [x] Consumables: potion_of_healing, potion_of_greater_healing
- [x] Ensure item data is complete:
  - [x] Name, description, type
  - [x] Weapon: damage dice, damage type, properties, range
  - [x] Armor: AC value, armor type, stealth disadvantage, STR requirements
  - [x] Consumable: effect type, amount (healing dice), rarity
- [x] Add interesting variety from SRD:
  - [x] 10 additional weapons (crossbows, bows, axes, hammers, etc.)
  - [x] 9 additional armor types (padded through plate)
  - [x] 2 additional healing potions (superior, supreme)

**Acceptance Criteria:**
- ✅ All items can be found in dungeon
- ✅ Items can be equipped/used correctly
- ✅ Equipment affects character stats properly (AC, damage)
- ✅ Using official D&D 5E SRD (CC BY 4.0) stats
- ✅ light_crossbow added for weapon switching (Issue #10)

---

#### 2.3 Implement D&D 5E Currency System
**Location:** `dnd_engine/systems/currency.py` (NEW FILE)
**Dependencies:** Inventory system
**Estimated Effort:** Medium (2-3 hours)
**GitHub Issue:** #6

**Tasks:**
- [ ] Create `Currency` dataclass
  - [ ] Track all five currency types: cp, sp, ep, gp, pp
  - [ ] `to_copper()` method for total wealth calculation
  - [ ] `add()` method with optional auto-consolidation
  - [ ] `subtract()` method with automatic change-making
  - [ ] `can_afford()` method for affordability checks
  - [ ] `consolidate()` method to convert to larger denominations
  - [ ] `__str__()` method for display (only non-zero denominations)
- [ ] Update Inventory class
  - [ ] Replace `self.gold: int` with `self.currency: Currency`
  - [ ] Add `gold` property for backward compatibility
  - [ ] Update `add_gold()`, `remove_gold()`, `has_gold()` methods
  - [ ] Update `__str__()` to display full currency
- [ ] Write unit tests (`tests/test_currency.py`)
  - [ ] Test conversion rates (cp, sp, ep, gp, pp)
  - [ ] Test adding currency with consolidation
  - [ ] Test subtracting with change-making
  - [ ] Test affordability checks
  - [ ] Test edge cases (negative amounts, insufficient funds)
  - [ ] Test display formatting
- [ ] Write integration tests
  - [ ] Test inventory with currency operations
  - [ ] Test backward compatibility with existing code
- [ ] Update data files
  - [ ] Add currency to dungeon treasures
  - [ ] Add currency to monster loot

**Acceptance Criteria:**
- Currency class tracks all five D&D 5E currency types
- Automatic change-making works when paying
- Currency displays in readable format (e.g., "5 gp, 7 sp, 3 cp")
- All unit tests pass with >80% coverage
- Backward compatible via `inventory.gold` property
- No breaking changes to existing functionality

---

#### 2.4 Validate Class Definitions
**Location:** `dnd_engine/data/srd/classes.json`
**Dependencies:** None
**Estimated Effort:** Small

**Tasks:**
- [ ] Verify Fighter class definition:
  - [ ] Name, hit_die (1d10)
  - [ ] Ability priorities: [strength, constitution, dexterity, wisdom, intelligence, charisma]
  - [ ] Primary ability: strength
  - [ ] Saving throw proficiencies
  - [ ] Armor/weapon proficiencies
  - [ ] Starting equipment with IDs that match items.json

**Acceptance Criteria:**
- Character creation uses correct ability priorities
- Starting equipment matches items.json IDs
- Fighter gets correct proficiencies

---

### Priority 3: Testing & Quality

#### 3.1 Unit Test Coverage
**Location:** `tests/`
**Dependencies:** Implemented features
**Estimated Effort:** Medium

**Tasks:**
- [ ] Test CharacterFactory
  - [ ] `test_character_factory.py` - All factory methods
- [ ] Test LLM Layer
  - [ ] `test_llm_provider.py` - Mock tests for providers
  - [ ] `test_llm_enhancer.py` - Event subscription and enhancement
  - [ ] `test_prompts.py` - Template generation
- [ ] Test GameState
  - [ ] Extend `test_game_state.py` with combat scenarios
  - [ ] Test victory detection
  - [ ] Test XP awarding
- [ ] Test CLI
  - [ ] `test_cli.py` - Command parsing and execution
  - [ ] Test equipment commands
  - [ ] Test item usage

**Acceptance Criteria:**
- Test coverage > 80%
- All edge cases covered
- Mock tests don't require API keys

---

#### 3.2 Integration Testing
**Location:** `tests/`
**Dependencies:** All systems implemented
**Estimated Effort:** Medium

**Tasks:**
- [ ] Create `test_full_game_flow.py`
  - [ ] Test character creation → dungeon exploration → combat → victory
  - [ ] Test finding items → equipping → using in combat
  - [ ] Test death scenario (player HP reaches 0)
- [ ] Create `test_combat_integration.py`
  - [ ] Full combat from start to victory
  - [ ] Multiple enemies with initiative
  - [ ] Player uses healing potion mid-combat
- [ ] Create `test_llm_integration.py`
  - [ ] Events trigger LLM enhancement (with mocks)
  - [ ] Fallback works when LLM fails

**Acceptance Criteria:**
- Complete game can be played from start to finish programmatically
- All integration points work together
- Tests pass consistently

---

#### 3.3 End-to-End Testing
**Location:** `tests/`
**Dependencies:** Complete game
**Estimated Effort:** Small

**Tasks:**
- [ ] Create `test_e2e.py`
  - [ ] Simulate full playthrough with scripted commands
  - [ ] Test winning scenario
  - [ ] Test losing scenario
  - [ ] Test inventory management throughout game
- [ ] Manual playtesting
  - [ ] Play through Goblin Warren completely
  - [ ] Test all commands in exploration mode
  - [ ] Test all commands in combat mode
  - [ ] Find and report bugs

**Acceptance Criteria:**
- Game is beatable
- No crashes or game-breaking bugs
- All features work as expected

---

### Priority 4: Documentation & Polish

#### 4.1 Code Documentation
**Location:** Throughout codebase
**Dependencies:** None
**Estimated Effort:** Small

**Tasks:**
- [ ] Ensure all new files have ABOUTME comments
- [ ] Add/update docstrings for all public methods
- [ ] Add inline comments for complex logic
- [ ] Update type hints everywhere

**Acceptance Criteria:**
- Every file has 2-line ABOUTME header
- All public methods have docstrings
- Complex algorithms are explained

---

#### 4.2 User Documentation
**Location:** Root directory
**Dependencies:** Complete game
**Estimated Effort:** Small

**Tasks:**
- [ ] Update README.md
  - [ ] Add screenshots/example gameplay
  - [ ] Update installation instructions
  - [ ] Add troubleshooting section
  - [ ] List all commands
- [ ] Create QUICKSTART.md
  - [ ] 5-minute getting started guide
  - [ ] Example playthrough
  - [ ] Common commands reference
- [ ] Create ARCHITECTURE.md (simplified SPEC.md)
  - [ ] High-level architecture diagram
  - [ ] Component responsibilities
  - [ ] Extension points

**Acceptance Criteria:**
- New users can get started in < 5 minutes
- All features are documented
- Architecture is clear for contributors

---

## 🔮 Future Enhancements (Post-MVP)

### Phase 2: Core Expansion

#### 2.1 Additional Character Classes
- [ ] Rogue class
  - [ ] Ability priorities: [dexterity, intelligence, constitution, charisma, wisdom, strength]
  - [ ] Sneak Attack feature
  - [ ] Starting equipment
- [ ] Cleric class
  - [ ] Ability priorities: [wisdom, constitution, strength, charisma, dexterity, intelligence]
  - [ ] Spellcasting (requires Phase 2.2)
  - [ ] Channel Divinity feature
- [ ] Update CharacterFactory to support class selection

#### 2.2 Spellcasting System
- [ ] Create `dnd_engine/systems/spellcasting.py`
  - [ ] Spell slot tracking per level
  - [ ] Spell preparation mechanics
  - [ ] Spell targeting and resolution
  - [ ] Concentration tracking
- [ ] Create `dnd_engine/data/srd/spells.json`
  - [ ] Define SRD spells with properties
  - [ ] Level, components, duration, range
  - [ ] Effect descriptions
- [ ] Integrate into combat system
  - [ ] "Cast spell" action
  - [ ] Spell attack rolls vs. saving throws
  - [ ] Spell damage and healing

#### 2.3 Character Leveling
- [ ] XP thresholds for leveling up
- [ ] HP increase (roll hit die + CON)
- [ ] Proficiency bonus increase
- [ ] New abilities/features per class
- [ ] Level-up UI flow

#### 2.4 Death Saves
- [ ] Track 0 HP as "unconscious" not "dead"
- [ ] Death save mechanics (3 successes/failures)
- [ ] Stabilization
- [ ] Healing unconscious characters
- [ ] Damage at 0 HP = automatic failure

---

### Phase 3: Party Support

#### 3.1 Party Management
- [ ] Create `dnd_engine/core/party.py`
  - [ ] Party class to hold multiple Characters
  - [ ] `get_living_members()`
  - [ ] `is_wiped()`
  - [ ] Shared vs individual inventory decision
- [ ] Update GameState to use Party instead of single Character
- [ ] Character creation for multiple party members
- [ ] Combat with party initiative

#### 3.2 Party Dynamics
- [ ] Simultaneous exploration (all move together)
- [ ] Individual combat turns
- [ ] Party death conditions (all dead = game over)
- [ ] Party inventory management
- [ ] Shared gold pool

---

### Phase 4: Content Expansion

#### 4.1 Multiple Dungeons
- [ ] Create 3-5 additional dungeons
  - [ ] Varying difficulty levels
  - [ ] Different themes (crypt, bandit camp, ruins)
  - [ ] 5-10 rooms each
- [ ] Dungeon selection at game start
- [ ] Campaign mode (linked dungeons)

#### 4.2 Quest System
- [ ] Create `dnd_engine/systems/quests.py`
  - [ ] Quest tracking
  - [ ] Objectives with completion states
  - [ ] Branching outcomes
  - [ ] Quest rewards
- [ ] Define quests in JSON
- [ ] Integrate with dungeon content

#### 4.3 More Monsters & Items
- [ ] Add 15+ more monsters
  - [ ] Varying CR (Challenge Rating)
  - [ ] Different abilities and tactics
  - [ ] Special traits (flying, regeneration, etc.)
- [ ] Add 20+ more items
  - [ ] Magic weapons (+1, +2)
  - [ ] Magic armor
  - [ ] Wondrous items (rings, cloaks)
- [ ] More consumables (scrolls, potions)

---

### Phase 5: Advanced Features

#### 5.1 Save/Load System
- [ ] Create `dnd_engine/systems/persistence.py`
  - [ ] Serialize game state to JSON
  - [ ] Load game state from JSON
  - [ ] Multiple save slots
  - [ ] Auto-save on important events
- [ ] UI commands: save, load, list saves

#### 5.2 Combat Reactions
- [ ] Opportunity attacks when enemies move
- [ ] Reaction spells (Shield, Counterspell)
- [ ] Ready action mechanic
- [ ] UI for triggering reactions

#### 5.3 Advanced Combat Mechanics
- [ ] Positioning/grid system
- [ ] Cover (half cover, three-quarters cover)
- [ ] Area of effect spells
- [ ] All 5E conditions (blinded, charmed, etc.)
- [ ] Grappling and shoving

#### 5.4 NPC Interactions
- [ ] Merchants (buy/sell items)
- [ ] Quest givers with dialogue trees
- [ ] Reputation system
- [ ] Persuasion/intimidation checks
- [ ] LLM-powered dynamic dialogue

---

### Phase 6: UI/UX Improvements

#### 6.1 Enhanced CLI
- [ ] Use `rich` library for better formatting
- [ ] Colored output
- [ ] Tables for inventory/stats
- [ ] Progress bars for HP
- [ ] ASCII art for rooms/monsters

#### 6.2 Web UI
- [ ] Create web-based interface
  - [ ] FastAPI backend
  - [ ] React/Vue frontend
  - [ ] WebSocket for real-time updates
- [ ] Visual character sheet
- [ ] Map display
- [ ] Better combat visualization
- [ ] Click-based commands

#### 6.3 Mobile/Native Apps
- [ ] iOS app
- [ ] Android app
- [ ] Touch-optimized UI
- [ ] Offline play with local save

---

## 📋 Development Workflow Notes

### Before Starting Each Task
1. ✅ Read SPEC.md section related to task
2. ✅ Read project CLAUDE.md for standards
3. ✅ Read global ~/.claude/CLAUDE.md for workflow
4. ✅ Write tests first (TDD)
5. ✅ Implement minimal code to pass tests
6. ✅ Refactor for clarity

### After Completing Each Task
1. ✅ Run all tests: `pytest`
2. ✅ Check coverage: `pytest --cov=dnd_engine tests/`
3. ✅ Update this TODO.md
4. ✅ Commit with descriptive message
5. ✅ Update documentation if needed

### Testing Requirements
- **Unit tests**: Test individual components in isolation
- **Integration tests**: Test multiple components working together
- **End-to-end tests**: Test complete game flows
- **NO EXCEPTIONS POLICY**: All test types required
- **Coverage goal**: >80%
- **Test output must be pristine** - no errors in logs unless explicitly tested

### Code Standards
- ✅ ABOUTME comments at top of every file
- ✅ Type hints for all function signatures
- ✅ Docstrings for all public methods
- ✅ Match existing code style in file
- ✅ NEVER use --no-verify when committing
- ✅ NEVER remove comments unless provably false

---

## 🎯 MVP Definition of Done

The MVP is **complete** when:

1. ✅ Player can create a Fighter character with rolled abilities
2. ✅ Player can explore the Goblin Warren dungeon (5-7 rooms)
3. ✅ Combat system works with initiative, attacks, and damage
4. ✅ Player can find and use items (weapons, armor, potions)
5. ✅ LLM enhances room descriptions and combat narration
6. ✅ Game has clear victory condition (defeat goblin boss)
7. ✅ Game has clear defeat condition (player dies)
8. ✅ All unit tests pass with >80% coverage
9. ✅ Integration tests cover main game flows
10. ✅ Documentation is complete and accurate
11. ✅ No game-breaking bugs
12. ✅ Game is fun to play through once

---

## 🐛 Known Issues & Bugs

*Track bugs here as they're discovered*

- None currently tracked

---

## 💡 Open Questions

*Decisions needed from SPEC.md "Open Questions" section:*

1. **Character Creation:**
   - [ ] Allow re-roll once if all scores < 12? (Recommendation: Yes)
   - [ ] Allow manual assignment instead of auto? (Recommendation: Post-MVP)

2. **Combat:**
   - [ ] Monster AI focus fire or spread damage? (Recommendation: Focus lowest HP)
   - [ ] Critical misses have special effects? (Recommendation: No for MVP)

3. **LLM:**
   - [ ] Cache descriptions or generate fresh? (Recommendation: Cache templates, generate combat fresh)
   - [ ] Allow --no-llm flag? (Recommendation: Yes)

4. **Content:**
   - [ ] How many rooms in MVP dungeon? (Recommendation: 6 rooms as per current goblin_warren.json)
   - [ ] Include merchant NPC? (Recommendation: Post-MVP)
   - [ ] Include puzzles/traps? (Recommendation: Post-MVP)

---

**Notes:**
- This TODO is a living document - update as tasks are completed
- Mark completed items with ✅
- Move blocked items to "Known Issues"
- Add new discoveries to appropriate sections
