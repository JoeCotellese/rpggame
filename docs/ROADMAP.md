# D&D 5E Terminal Game - Development Roadmap

**Last Updated:** 2025-11-20
**Current Version:** 0.2.0 (Beyond MVP)

> **Note on Task Tracking:**
> This roadmap provides strategic planning and high-level feature priorities.
> Day-to-day task tracking is managed through [GitHub Issues](https://github.com/JoeCotellese/rpggame/issues).
> See [CLAUDE.md](../CLAUDE.md) for development standards and [ARCHITECTURE.md](ARCHITECTURE.md) for system design.

---

## Overview

This roadmap outlines planned features and enhancements for the D&D 5E terminal game. The project has successfully completed its MVP and several post-MVP features. This document tracks remaining work and future vision.

---

## ✅ Completed Features

### MVP (Phase 1) - ✅ COMPLETE
- ✅ Single character gameplay (Fighter)
- ✅ Basic combat system (attack rolls, damage, initiative)
- ✅ Simple dungeon (5-7 rooms)
- ✅ 3-4 enemy types
- ✅ Basic inventory system
- ✅ LLM-enhanced narrative

### Post-MVP Completed - ✅
- ✅ **Party System** - Multiple character support, party management
- ✅ **Save/Load System** - Persistent game state to JSON
- ✅ **Multiple Dungeons** - Multiple dungeon files and procedural generation
- ✅ **Rich Terminal UI** - Color-coded output, formatted tables, progress bars
- ✅ **Multiple LLM Providers** - OpenAI, Anthropic, Debug mode
- ✅ **Character Classes** - Fighter, Rogue (partial), Cleric (partial) in data
- ✅ **Advanced Inventory** - Equipment slots, consumables, gold tracking
- ✅ **Debug Mode** - File logging with structured events

---

## 🚧 In Progress (Phase 2: Core Expansion)

### Priority: High

#### 1. **Complete Class Implementations**
- **Status**: Rogue and Cleric in data files but features not fully implemented
- **Remaining Work**:
  - Implement Sneak Attack mechanics for Rogue
  - Implement spellcasting for Cleric
  - Class-specific abilities and features
  - Balance testing

#### 2. **Spellcasting System**
- **Status**: In Progress - Combat spells implemented, out-of-combat casting needed
- **Completed**:
  - ✅ Spell slots (per level) - #37
  - ✅ Spell save DCs and attack rolls - #38, #39
  - ✅ Combat spell casting with targeting
  - ✅ Cantrip damage scaling
- **Remaining**:
  - Out-of-combat spellcasting (#116)
  - Spell preparation system
  - Concentration mechanics
  - Ritual casting
  - Reaction spells
- **Dependencies**: None
- **Estimated Effort**: 2 weeks remaining

#### 3. **Character Leveling**
- **Status**: ✅ COMPLETE (#40)
- **Implemented**:
  - ✅ XP tracking system
  - ✅ Level-up mechanics
  - ✅ Ability score improvements
  - ✅ New feature grants per level
  - ✅ HP increase calculations

#### 4. **Death Saves (5E Mechanics)**
- **Status**: ✅ COMPLETE
- **Implemented**:
  - ✅ 3 success / 3 failure tracking
  - ✅ Stabilization mechanics
  - ✅ Healing unconscious characters
  - ✅ Automatic death saves on each turn at 0 HP
  - ✅ Character revival with healing items/spells

---

## 📋 Planned Features

### Phase 3: Content & Polish

#### 5. **Campaign System**
- **Status**: Not started
- **Description**:
  - Multi-dungeon storylines
  - Overworld map navigation
  - Story progression tracking
  - Connected narrative across dungeons
- **Dependencies**: Multiple dungeons ✅ (complete)
- **Estimated Effort**: 3 weeks

#### 6. **Quest System**
- **Status**: Not started
- **Description**:
  - Track quest objectives
  - Branching quest outcomes
  - Quest rewards (XP, items, reputation)
  - Quest log UI
  - Multiple active quests
- **Dependencies**: Campaign system
- **Estimated Effort**: 2-3 weeks

#### 7. **More Content**
- **Status**: Ongoing
- **Goals**:
  - 20+ unique monsters (currently: ~6)
  - 10+ dungeons (currently: 2)
  - 50+ items/weapons/armor (currently: ~15)
  - Additional character classes/subclasses
  - More character races beyond human
- **Dependencies**: None (can add incrementally)
- **Estimated Effort**: Ongoing

---

### Phase 4: Advanced Features

#### 8. **Enhanced Save/Load**
- **Status**: Basic save/load exists ✅, enhancements needed
- **Enhancements**:
  - Multiple save slots (currently: single save)
  - Auto-save on important events
  - Save file versioning and migration
  - Cloud save support (optional)
  - Save file compression
- **Dependencies**: None
- **Estimated Effort**: 1 week

#### 9. **Reactions System**
- **Status**: Action economy exists, reactions not implemented
- **Description**:
  - Opportunity attacks
  - Shield spell (requires spellcasting)
  - Counterspell (requires spellcasting)
  - Reaction UI and timing
- **Dependencies**: Spellcasting system (for spell reactions)
- **Estimated Effort**: 2 weeks

#### 10. **Advanced Combat Mechanics**
- **Status**: Not started
- **Description**:
  - Positioning/grid system (currently abstract)
  - Cover mechanics (half/three-quarters/full)
  - Area of effect spells
  - All 5E conditions (currently: partial)
  - Flanking rules (optional)
- **Dependencies**: Spellcasting system
- **Estimated Effort**: 4 weeks

#### 11. **NPC Interactions**
- **Status**: Basic NPC support exists, enhancements needed
- **Description**:
  - Merchant system (buy/sell items)
  - Quest giver NPCs
  - Reputation system
  - Persuasion/intimidation skill checks
  - Dynamic dialogue trees
  - NPC memory of player actions
- **Dependencies**: Quest system (for quest givers)
- **Estimated Effort**: 3 weeks

---

### Phase 5: UI/UX Expansion

#### 12. **Web UI**
- **Status**: Not started
- **Description**:
  - Browser-based interface using FastAPI + React/Vue
  - Visual character sheet
  - Interactive map display
  - Better combat visualization
  - Multiplayer support (co-op parties)
  - Real-time updates via WebSockets
- **Dependencies**: None (parallel implementation)
- **Estimated Effort**: 6-8 weeks
- **Note**: Major architectural addition

#### 13. **Mobile/Native Apps**
- **Status**: Not started
- **Description**:
  - iOS/Android native apps
  - Touch-optimized UI
  - Offline play support
  - Cross-platform save sync
- **Dependencies**: Web UI (share backend API)
- **Estimated Effort**: 8-10 weeks
- **Note**: Requires mobile development expertise

---

## 🔮 Future Vision (Phase 6+)

### Long-Term Goals

#### 14. **Multiplayer/Co-op**
- **Description**: Multiple players control party members in same game
- **Requirements**: Web UI with WebSocket server, synchronized state
- **Estimated Effort**: 6 weeks

#### 15. **Modding Support**
- **Description**: Community-created content
- **Requirements**:
  - Plugin system
  - Content validation and sandboxing
  - Mod marketplace/repository
  - Visual content creation tools
- **Estimated Effort**: 4-6 weeks

#### 16. **Advanced AI**
- **Description**: Smarter monster tactics, dynamic difficulty
- **Requirements**:
  - Tactical AI (positioning, focus fire, retreat)
  - Difficulty scaling based on player performance
  - Monster personality traits
- **Estimated Effort**: 3 weeks

#### 17. **Character Builder**
- **Description**: Standalone character creation tool
- **Requirements**:
  - Web/desktop app for character creation
  - Export to game-compatible format
  - Share characters with other players
- **Estimated Effort**: 4 weeks

---

## 📊 Implementation Priority

### Next 3 Months (High Priority)
1. ✅ **Character leveling** - COMPLETE (#40)
2. ✅ **Death saves** - COMPLETE
3. ✅ **Rogue class** - COMPLETE (#41)
4. **Out-of-combat spellcasting** (#116) - 1-2 weeks
5. **Complete Cleric class implementation** (2 weeks)
6. **More content** (ongoing - monsters, dungeons, items)

### Next 6 Months (Medium Priority)
6. **Quest system** (3 weeks)
7. **Campaign system** (3 weeks)
8. **Reactions system** (2 weeks)
9. **NPC interactions** (3 weeks)
10. **Advanced combat mechanics** (4 weeks)

### Next 12 Months (Lower Priority / Exploratory)
11. **Web UI** (8 weeks)
12. **Enhanced save/load** (1 week)
13. **Multiplayer support** (6 weeks)
14. **Mobile apps** (10 weeks)

---

## 🎯 Success Metrics

### Technical Goals
- Maintain >80% test coverage
- Keep response times <100ms for game actions
- LLM enhancement <3 seconds
- Support 4+ character parties
- Support 50+ room dungeons

### User Experience Goals
- Complete dungeon playthrough in 60-90 minutes
- Clear tutorial for new players
- Accessible to screen readers
- Intuitive command syntax
- Rich narrative experience

### Content Goals
- 20+ monsters with varied tactics
- 10+ unique dungeons
- 5+ character classes fully implemented
- 100+ items/equipment options
- Campaign spanning 10+ hours

---

## 🤝 Contributing

Interested in contributing to these features? See [CLAUDE.md](../CLAUDE.md) for development standards and [ARCHITECTURE.md](ARCHITECTURE.md) for system architecture.

Priority areas for contribution:
- **Content Creation**: New monsters, dungeons, items (no coding required - JSON files)
- **Class Implementation**: Complete Rogue and Cleric features
- **Spellcasting**: Design and implement spell system
- **Testing**: Increase test coverage, write integration tests

---

## 📝 Notes

- **Data-Driven Design**: Most content can be added via JSON without code changes
- **Event-Driven Architecture**: New systems integrate by subscribing to events
- **Extensibility**: Plugin system designed for easy feature additions
- **Backward Compatibility**: Save files use versioning for migration

---

*For detailed architecture and current implementation status, see [ARCHITECTURE.md](ARCHITECTURE.md)*

*For historical design decisions, see [SPEC_HISTORICAL_2025-11.md](SPEC_HISTORICAL_2025-11.md)*
