# D&D 5E Terminal Game - Development TODO

This document tracks remaining implementation tasks and completed work.

**Last Updated:** 2025-11-17
**Current Status:** MVP COMPLETE! Core systems operational, spellcasting in progress

---

## 🎉 MVP Status: COMPLETE

The MVP is **complete** and playable! All core requirements met:

1. ✅ Create characters (Fighter, Rogue) with rolled abilities and race selection
2. ✅ Explore dungeons with multiple rooms
3. ✅ Combat system with initiative, attacks, damage, and death
4. ✅ Find and use items (weapons, armor, potions)
5. ✅ LLM enhances room descriptions and combat narration
6. ✅ Victory condition (defeat all enemies)
7. ✅ Defeat condition (party wipe)
8. ✅ Comprehensive test coverage (>80%)
9. ✅ Save/load game state
10. ✅ Party system (1-4 characters)
11. ✅ Leveling system with XP and feature granting
12. ✅ Rest system (short/long rest)

---

## ✅ Completed Systems

### Core Gameplay
- ✅ **Character Creation** (#7) - Roll abilities, choose race/class, starting equipment
- ✅ **Party System** (#4) - 1-4 character parties with shared resources
- ✅ **Combat Engine** - Initiative, attacks, damage, critical hits
- ✅ **Inventory System** - Equipment slots, weapons, armor, consumables
- ✅ **Currency System** (#6) - All 5 D&D currencies (cp, sp, ep, gp, pp) with auto-conversion
- ✅ **Save/Load System** (#18) - Persistent game state between sessions
- ✅ **Leveling System** (#40) - XP thresholds, HP increases, feature granting
- ✅ **Rest System** (#35) - Short rest (heal, use hit dice) and long rest (full restore)

### Combat & Mechanics
- ✅ **Attack System** (#30) - STR-based, DEX-based, ranged, finesse weapons
- ✅ **Skills System** (#32) - All 18 D&D skills with proficiency bonuses
- ✅ **Saving Throws** (#31) - Ability-based saves with class proficiencies
- ✅ **Equipment Proficiency** (#33) - Penalties for non-proficient armor
- ✅ **Resource Pools** (#34) - Generic system for tracking limited-use abilities
- ✅ **Weapon Switching** (#10) - Change weapons during combat
- ✅ **Flee Mechanic** - Escape from combat with opportunity attacks

### Character Classes
- ✅ **Fighter** - STR-based melee combatant, Second Wind, Action Surge
- ✅ **Rogue** (#41) - DEX-based, Sneak Attack, Cunning Action, Expertise

### Data & Content
- ✅ **Monsters** - Goblin, Goblin Boss, Wolf (with SRD stats)
- ✅ **Items** - 30+ weapons, armor, consumables from SRD
- ✅ **Classes** - Fighter, Rogue with full progression
- ✅ **Races** - Human, Elf, Dwarf, Halfling with racial traits
- ✅ **Dungeon** - Goblin Warren (6 rooms with encounters)

### LLM Integration
- ✅ **Multi-Provider Support** (#8) - OpenAI and Anthropic
- ✅ **Narrative Enhancement** - Room descriptions, combat actions, deaths, victories
- ✅ **Synchronous Generation** - Blocking LLM calls with timeout for proper sequencing
- ✅ **Graceful Degradation** - Game works without LLM

### Developer Experience
- ✅ **Debug Mode** (#17) - File logging for troubleshooting
- ✅ **Campaign Reset** (#29) - Reset dungeon progress, keep characters
- ✅ **Multi-Player Commands** (#21) - Target specific party members for inventory
- ✅ **Comprehensive Testing** - Unit, integration, and e2e tests

---

## 🚧 Active Development

### Spellcasting System (In Progress)
Related issues: #36, #37, #38, #39, #42

**Remaining Tasks:**
- [ ] **#36** - Create spell data structures and spells.json
  - [ ] Define spell schema (name, level, school, components, etc.)
  - [ ] Add SRD spells with full properties
  - [ ] Damage, healing, buff, debuff, utility spells
- [ ] **#37** - Implement spell slot tracking and management
  - [ ] Track slots per spell level (1-9)
  - [ ] Expend slots when casting
  - [ ] Recover slots on long rest
  - [ ] Display available slots in UI
- [ ] **#38** - Implement spell attack roll mechanics
  - [ ] Calculate spell attack bonus (proficiency + casting ability)
  - [ ] Resolve spell attacks against AC
  - [ ] Handle spell critical hits
- [ ] **#39** - Implement spell saving throw mechanics
  - [ ] Calculate spell save DC (8 + proficiency + casting ability)
  - [ ] Target makes saving throw
  - [ ] Apply effects (damage, conditions, etc.)
  - [ ] Half damage on successful save
- [ ] **#42** - Add Wizard character class
  - [ ] INT-based spellcaster
  - [ ] Spellbook and spell preparation
  - [ ] Arcane Recovery feature
  - [ ] School of magic specialization

**Dependencies:**
- Spell data (#36) must be complete before other tasks
- Spell slot tracking (#37) needed for casting
- Attack/save mechanics (#38, #39) needed for resolution
- Wizard (#42) requires all spell systems

---

## 📝 Planned Features

### High Priority

#### Death Saving Throws (#52)
When characters drop to 0 HP:
- [ ] Track death save successes/failures (3 each)
- [ ] Roll d20 at start of turn (10+ success, 9- failure)
- [ ] Natural 20 = regain 1 HP and consciousness
- [ ] Natural 1 = 2 failures
- [ ] Damage while unconscious = automatic failure
- [ ] Massive damage (damage ≥ max HP) = instant death
- [ ] Medicine skill checks to stabilize
- [ ] Stabilized characters stop making death saves
- [ ] LLM narratives for death saves and stabilization

**Impact:** Prevents instant death, adds tactical depth, enables ally rescue mechanics

---

### Content Expansion

#### Location System Extension (#28)
- [ ] Settlements (towns, cities with NPCs and merchants)
- [ ] Regions (multiple locations connected by travel)
- [ ] World map navigation
- [ ] Fast travel between discovered locations
- [ ] Encounter tables for wilderness travel
- [ ] Time tracking (day/night cycles)

#### Multiple Dungeons
- [ ] Create 3-5 additional dungeons
  - [ ] Varying difficulty (CR 1-5)
  - [ ] Different themes (crypt, bandit camp, ruins, mine)
  - [ ] 5-10 rooms each
- [ ] Dungeon selection system
- [ ] Campaign mode (linked dungeons with story)

#### Quest System
- [ ] Create quest tracking system
- [ ] Define quests in JSON
- [ ] Objectives with completion tracking
- [ ] Branching quest outcomes
- [ ] Quest rewards (XP, gold, items)
- [ ] Main quest line and side quests

#### More Content
- [ ] 20+ additional monsters (CR 1-5)
  - [ ] Flying creatures
  - [ ] Undead
  - [ ] Beasts
  - [ ] Constructs
- [ ] 30+ more items
  - [ ] Magic weapons (+1, +2, flaming, frost)
  - [ ] Magic armor
  - [ ] Wondrous items (rings, cloaks, boots)
  - [ ] Scrolls and wands

---

### Advanced Combat Mechanics

#### Combat Reactions
- [ ] Opportunity attacks when enemies move
- [ ] Reaction spells (Shield, Counterspell, Feather Fall)
- [ ] Ready action mechanic
- [ ] UI for triggering reactions mid-turn

#### Positioning & Tactics
- [ ] Simple grid/range system
- [ ] Cover mechanics (half/three-quarters)
- [ ] Area of effect spells (cone, sphere, line)
- [ ] Difficult terrain
- [ ] Flying/climbing

#### Conditions & Status Effects
- [ ] Implement all 5E conditions:
  - [ ] Blinded, Charmed, Deafened, Frightened
  - [ ] Grappled, Incapacitated, Invisible, Paralyzed
  - [ ] Petrified, Poisoned, Prone, Restrained
  - [ ] Stunned, Unconscious
- [ ] Condition effects on combat
- [ ] Condition duration tracking
- [ ] Saving throws to end conditions

#### Advanced Actions
- [ ] Grappling
- [ ] Shoving
- [ ] Disarm
- [ ] Help action (advantage for ally)

---

### NPC & Social Systems

#### NPC Interactions
- [ ] Merchants (buy/sell items with pricing)
- [ ] Quest givers with dialogue trees
- [ ] Reputation/faction system
- [ ] Persuasion/intimidation/deception checks
- [ ] LLM-powered dynamic dialogue
- [ ] NPC personalities and backgrounds

#### Shops & Economy
- [ ] Item shops with inventory
- [ ] Dynamic pricing based on charisma
- [ ] Selling found loot
- [ ] Special/rare item availability
- [ ] Black market for illicit goods

---

### UX Improvements (#26)

#### CLI Enhancements
- [x] Rich library integration (partially done)
- [ ] Combat status tables (show HP bars)
- [ ] Skill check result formatting
- [ ] Better error messages with suggestions
- [ ] Command history and autocomplete
- [ ] Help system improvements
- [ ] Color-coded damage types
- [ ] ASCII art for special encounters

#### Quality of Life
- [ ] Auto-save on important events
- [ ] Multiple save slots with names
- [ ] Undo last command (limited)
- [ ] Command aliases (shortcuts)
- [ ] Macro system for common actions
- [ ] Session summary on exit

---

### Future Phases

#### Web UI (Phase 6.2)
- [ ] FastAPI backend exposing game API
- [ ] React/Vue frontend
- [ ] WebSocket for real-time updates
- [ ] Visual character sheet
- [ ] Interactive map display
- [ ] Click-based combat
- [ ] Multiplayer support

#### Mobile/Native Apps (Phase 6.3)
- [ ] iOS app
- [ ] Android app
- [ ] Touch-optimized UI
- [ ] Offline play with cloud sync
- [ ] Push notifications for turn-based multiplayer

---

## 🐛 Known Issues

*No critical bugs currently tracked*

Minor issues:
- Dead combatants briefly show turn indicator before being skipped (fixed 2025-11-17)
- Combat mechanics text color was too dim on dark terminals (fixed 2025-11-17)

---

## 📋 Development Workflow

### Before Starting Each Task
1. ✅ Read related GitHub issue for context
2. ✅ Read SPEC.md section if applicable
3. ✅ Check project CLAUDE.md for standards
4. ✅ Write tests first (TDD)
5. ✅ Implement minimal code to pass tests
6. ✅ Refactor for clarity

### After Completing Each Task
1. ✅ Run all tests: `pytest`
2. ✅ Check coverage: `pytest --cov=dnd_engine tests/`
3. ✅ Update this TODO.md if milestone reached
4. ✅ Commit with descriptive message
5. ✅ Close related GitHub issue
6. ✅ Update documentation if needed

### Testing Requirements
- **Unit tests**: Test individual components in isolation
- **Integration tests**: Test multiple components working together
- **End-to-end tests**: Test complete game flows
- **NO EXCEPTIONS POLICY**: All test types required for new features
- **Coverage goal**: >80%
- **Test output must be pristine** - no errors in logs unless explicitly tested

### Code Standards
- ✅ ABOUTME comments at top of every file
- ✅ Type hints for all function signatures
- ✅ Docstrings for all public methods
- ✅ Match existing code style in file
- ✅ NEVER use --no-verify when committing
- ✅ NEVER remove comments unless provably false
- ✅ Comments should be evergreen (no temporal references)

---

## 💡 Design Decisions

### Character Creation
- ✅ 4d6 drop lowest for ability scores
- ✅ Auto-assign abilities optimally for chosen class
- ✅ Allow manual swaps before confirming
- ✅ Re-roll if all scores < 10 (too weak)

### Combat
- ✅ Monster AI targets lowest HP party member
- ✅ No special critical miss effects (keep it simple)
- ✅ Combat narratives appear before mechanics for drama

### LLM Integration
- ✅ Synchronous blocking calls with 3-second timeout
- ✅ Graceful degradation when LLM unavailable
- ✅ --no-llm flag for testing/faster play
- ✅ Support both OpenAI and Anthropic providers

### Inventory
- ✅ Individual inventory per character
- ✅ Shared party gold pool
- ✅ Equipment slots (weapon, armor, etc.)
- ✅ Stack consumables

---

## 🎯 Project Metrics

**Lines of Code:**
- Production: ~3,100 lines
- Tests: ~1,500+ lines
- Test Coverage: >80%

**Features Implemented:**
- 2 Character Classes (Fighter, Rogue)
- 4 Races (Human, Elf, Dwarf, Halfling)
- 18 Skills
- 30+ Items
- 3 Monster types
- 1 Complete dungeon
- Full combat system
- Save/load system
- Party management
- Leveling system
- Rest system

**GitHub Stats:**
- Issues Created: 52
- Issues Closed: 44
- Open Issues: 8
- Active Development: Spellcasting system

---

**Notes:**
- This TODO is a living document - update as major milestones are reached
- Day-to-day tasks tracked in GitHub issues
- Mark completed sections with ✅
- Add new discoveries to appropriate sections
