# "The Unquiet Dead" Adventure - Gap Analysis

**Last Updated**: 2025-11-23
**Adventure Playability**: 75% Complete 🎯

## Adventure Overview
- **Level**: 1st level (4 characters, APL 1)
- **Progression**: Characters reach 3rd level by completion
- **Duration**: ~3-4 hour session
- **Locations**: Graveyard, Family Crypt, Cult Hideout, Abandoned Temple

## Feature Requirements vs Current Implementation

### ✅ IMPLEMENTED - Core Mechanics

#### Combat System
- ✅ Turn-based combat with initiative
- ✅ Attack rolls, damage, HP tracking
- ✅ Death saves and character death
- ✅ Multiple enemies in encounters
- ✅ AC and saving throws
- ✅ Spell concentration with damage interruption (PR #149)
- ✅ Surprise rounds with stealth checks (PR #150)

#### Character Mechanics
- ✅ Ability scores and modifiers
- ✅ Skill checks (Athletics, Perception, Insight, Medicine, Investigation, Religion, Stealth)
- ✅ Proficiency bonus
- ✅ Class features
- ✅ Spellcasting for clerics/wizards
- ✅ Level progression and XP
- ✅ Spell slot management
- ✅ Proper spell routing (attack/save/buff types) (PR #151)

#### Monster Mechanics
- ✅ Skeletons
- ✅ Basic undead creatures
- ✅ Multiple monster types with different stat blocks
- ✅ Passive Perception for surprise checks

#### Items & Equipment
- ✅ Weapons (shortsword, longsword, dagger, mace, glaive)
- ✅ Armor and AC calculation
- ✅ Currency (gp, sp)
- ✅ Inventory management
- ✅ Magic items (+1 weapons)
- ✅ Light sources (torches, lanterns, candles)

### ✅ RECENTLY COMPLETED - Critical Systems

#### Lighting System (#124) - ✅ COMPLETED
**Required by adventure**:
- Crypt is "pitch black"
- Temple is "pitch black"
- Cult hideout has "dim light" from candles
- Characters need to see in darkness or bring light sources

**Implemented**:
- ✅ Darkness, dim light, bright light levels
- ✅ Darkvision for characters/monsters
- ✅ Light sources (torches, lanterns, candles)
- ✅ Vision penalties in darkness
- ✅ Light source management and duration tracking

**Impact**: Entire adventure now playable with proper lighting mechanics! 🎉

#### Time Tracking (#123) - ✅ COMPLETED
**Required by adventure**:
- Poisoned condition lasts "1 hour"
- Durgon takes "approximately 12 hours" to reform
- Long rest mechanics (8 hours)

**Implemented**:
- ✅ In-game time tracking (hours, minutes, rounds)
- ✅ Timed conditions (poisoned for 1 hour)
- ✅ Timed events (Durgon reform timer)
- ✅ Long rest time passage
- ✅ Display current time to players

**Adventure quote**: *"Read the following if the characters enter the chamber after twelve hours have elapsed"* - NOW WORKS!

#### Spell Concentration (#122) - ✅ COMPLETED
**Required by adventure**:
- **Bless spell** (acolyte casts on self + 2 cultists)
- **Poisoned condition** with duration (1 hour)
- Concentration breaks on damage

**Implemented**:
- ✅ Concentration mechanic for spells
- ✅ CON save on damage to maintain concentration
- ✅ Automatic spell effect cleanup when broken
- ✅ Timed condition tracking
- ✅ Status effect display

**Impact**: Core spellcasting mechanics now D&D 5E compliant! 🎉

#### Surprise Mechanics (#104) - ✅ COMPLETED
**Required by adventure**:
- Surprise round if characters attack Durgon after convincing him
- Cultists "need a round to get weapons ready" (surprised)
- Failed stealth alerts enemies

**Implemented**:
- ✅ Group stealth checks vs enemy passive Perception
- ✅ Surprised condition prevents actions on first turn
- ✅ Room alert state tracking
- ✅ Loud unlock methods alert destination rooms
- ✅ Silent approaches enable surprise rounds
- ✅ Proper game logic separation (not in UI)

**Impact**: Tactical gameplay now rewards careful play. Silent approaches vs loud door breaking has real consequences! 🎉

#### Spell Mechanics Fix (#146) - ✅ COMPLETED
**Required by adventure**:
- Shield spell for defensive play
- Proper spell routing for all spell types

**Implemented**:
- ✅ Attack spells route to attack roll system
- ✅ Save spells route to saving throw system
- ✅ Buff spells (Shield, Mage Armor) apply directly without bogus attack rolls
- ✅ Proper display for each spell category

**Impact**: Spellcasters can now use all spell types correctly! 🎉

### ❌ NOT IMPLEMENTED - Remaining Gaps

#### 1. Ghoul Paralysis Attack (#103) - CRITICAL 🚨
**Impact**: Core monster mechanic missing - LAST CRITICAL BLOCKER!
- Ghouls can paralyze on hit (signature ability)
- This makes encounters significantly more challenging
- Without it, Room 8 ghast encounter is too easy

**Adventure Requirements**:
- Ghoul claw attack: DC 10 CON save or paralyzed until end of next turn
- Ghast stench: DC 10 CON save or poisoned for 1 hour
- Paralysis is their defining mechanic

**Current state**: Ghoul likely doesn't have paralysis attack
**Maps to issue**: #103 (Verify monster special attack saving throws)

**BLOCKING**: YES - This is now the ONLY critical blocker remaining!

#### 2. Secret Doors & Hidden Rooms (#101) - HIGH
**Impact**: Missing optional content and tactical information
- DC 14 Investigation check to find mechanism (Room 1)
- Secret door with draft (Room 1)
- Hidden room behind tapestry (Room 11)
- DC 14 Perception to hear chanting through door (Room 5)
- DC 14 Perception to hear skeletons dragging swords (Room 3)

**Current state**: No secret door mechanics or "listen at door" action
**Maps to issue**: #101 (Skill check triggers during exploration)

**BLOCKING**: PARTIAL - Can complete adventure but missing exploration depth

#### 3. Locked Doors & Lock Picking (#101) - MEDIUM
**Impact**: Alternative paths blocked (but brute force alternatives exist)
- DC 12 Dexterity + Thieves' Tools to pick locks (Rooms 3, 8)
- DC 12 Strength to break doors (Rooms 3, 8)
- Can brute force doors as alternative (alerts enemies)

**Current state**: Unknown if Thieves' Tools checks work properly
**Maps to issue**: #101 (Skill check triggers)

**BLOCKING**: NO - Can brute force doors

#### 4. Social Encounter with Durgon - MEDIUM
**Impact**: Missed non-combat resolution opportunity
- DC 18 Charisma checks to avoid final fight
- Deception, Intimidation, or Persuasion options
- Roleplay opportunity for clever parties

**Current state**: Unknown if social checks work in combat-like situations
**Maps to issue**: Possibly new issue needed

**BLOCKING**: NO - Combat is always an option

### 🔄 NICE TO HAVE - Enhancement Opportunities

#### 1. Spell Slot Display (#105)
**Impact**: Quality of life for spellcasters
- Acolytes cast bless and sacred flame
- Mage has 1st-level slots remaining
- Players need to see remaining slots easily

**Maps to issue**: #105 (Display spell slot availability)

#### 2. Item Usage in Combat (#56)
**Impact**: Using potions, holy water, etc.
- Characters might want to use items during fight
- Action economy for item usage

**Maps to issue**: #56 (Implement item usage during combat)

#### 3. Quest/Journal System (#102)
**Impact**: Track adventure progress
- Journal found on cultist corpse
- Map to cult hideout
- Map to temple

**Maps to issue**: #102 (Quest item system and campaign progression)

## Critical Path to Playability

### ✅ BLOCKER Issues - MOSTLY COMPLETE!
1. ✅ **#124** - Lighting system (COMPLETED)
   - Entire adventure happens in darkness ✅

2. ✅ **#123** - Time tracking (COMPLETED)
   - Poisoned condition (1 hour) ✅
   - Durgon reform timer (12 hours) ✅
   - Long rest mechanics ✅

3. ❌ **#103** - Ghoul/Ghast paralysis (IN PROGRESS) 🚨
   - Core monster mechanic
   - **LAST CRITICAL BLOCKER**
   - Makes encounters trivial without it

### HIGH Priority Issues (Should Fix for Full Experience)
4. ❌ **#101** - Skill check triggers (HIGH)
   - Listening at doors
   - Finding secret doors
   - Lock picking
   - Spotting enemies before combat
   - **Needed for exploration depth**

### ✅ MEDIUM Priority - COMPLETE!
5. ✅ **#104** - Surprise mechanics (COMPLETED)
   - Cultists getting weapons ready ✅
   - Surprise rounds ✅
   - Stealth vs alert state ✅

6. ✅ **#122** - Conditions & Concentration (COMPLETED)
   - Poisoned condition ✅
   - Bless spell ✅
   - Concentration mechanics ✅

7. ✅ **#146** - Spell mechanics fixes (COMPLETED)
   - Proper spell routing ✅
   - Buff spells work correctly ✅

### MEDIUM Priority (Enhancement)
8. **#105** - Spell slot display
9. **#56** - Item usage in combat
10. **#102** - Quest journal

## Progress Summary

### Playability Checklist (8/10 Complete) ✅
- [x] Can navigate dark crypt with torches/darkvision (#124)
- [x] Time-based mechanics work (poisoned duration, Durgon timer) (#123)
- [ ] Ghoul paralysis attack functions correctly (#103) 🚨
- [x] Surprise rounds work when catching enemies off-guard (#104)
- [x] Bless spell and poisoned condition track properly (#122)
- [x] Spell concentration breaks on damage (#122)
- [x] Shield and buff spells work correctly (#146)
- [ ] Can find secret doors with Investigation (#101)
- [x] Alert state prevents surprise in alerted rooms (#104)
- [x] Spell effects tracked with proper duration (#123)

### Recent Wins (Last 7 Days) 🎉
- ✅ PR #149: Spell concentration tracking with damage checks
- ✅ PR #150: Surprise mechanics with proper architecture
- ✅ PR #151: Shield spell and buff spell routing fix
- ✅ Closed issues #104, #122, #146

## Recommendation

### **To play "The Unquiet Dead" adventure at 75% fidelity:**

**YOU MUST FIX** (1 remaining):
1. ❌ #103 (Ghoul paralysis) - LAST CRITICAL BLOCKER 🚨

**FOR FULL EXPERIENCE**, also implement:
2. ❌ #101 (Exploration skill checks) - HIGH

### **Current Status**
- **Critical blockers**: 1 remaining (#103)
- **Core systems**: 6/7 complete (85%)
- **Playability**: Adventure is ~75% playable
- **Exploration depth**: Needs #101 for full experience

### **Backlog Priority Order**
1. 🚨 **#103** - Monster special attacks (BLOCKS ADVENTURE)
2. **#101** - Skill check triggers (ENHANCES ADVENTURE)
3. **#105** - Spell slot display (QUALITY OF LIFE)
4. **#56** - Item usage in combat (ENHANCEMENT)
5. **#102** - Quest journal (ENHANCEMENT)

## Conclusion

**Massive progress!** We've gone from 3 critical blockers to just 1:
- ✅ Lighting system - DONE
- ✅ Time tracking - DONE
- ✅ Surprise mechanics - DONE
- ✅ Spell concentration - DONE
- ✅ Spell routing fixes - DONE
- ❌ Ghoul paralysis - **LAST BLOCKER**

Once #103 is complete, the adventure will be playable end-to-end at ~75% fidelity. Adding #101 (exploration mechanics) would bring it to ~90% fidelity.

**Next steps**: Fix ghoul/ghast special attacks (#103), then implement exploration skill checks (#101) for the full adventure experience! 🎯
