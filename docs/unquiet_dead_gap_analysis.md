# "The Unquiet Dead" Adventure - Gap Analysis

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

#### Character Mechanics
- ✅ Ability scores and modifiers
- ✅ Skill checks (Athletics, Perception, Insight, Medicine, Investigation, Religion, Stealth)
- ✅ Proficiency bonus
- ✅ Class features
- ✅ Spellcasting for clerics/wizards
- ✅ Level progression and XP

#### Monster Mechanics
- ✅ Skeletons
- ✅ Basic undead creatures
- ✅ Multiple monster types with different stat blocks

#### Items & Equipment
- ✅ Weapons (shortsword, longsword, dagger, mace, glaive)
- ✅ Armor and AC calculation
- ✅ Currency (gp, sp)
- ✅ Inventory management
- ✅ Magic items (+1 weapons)

### ⚠️ PARTIALLY IMPLEMENTED

#### Lighting System (#124 - CRITICAL)
**Required by adventure**:
- Crypt is "pitch black"
- Temple is "pitch black"
- Cult hideout has "dim light" from candles
- Characters need to see in darkness or bring light sources

**Current state**: NO lighting system
- No darkvision implementation
- No light sources (torches, lanterns, candles)
- No dim light / bright light / darkness mechanics
- No disadvantage on Perception in darkness

**Blocking**: YES - Entire adventure assumes lighting matters

#### Stealth & Perception (#101 - HIGH)
**Required by adventure**:
- DC 12 Perception to notice skeletons lurking (Room 1)
- DC 14 Perception to hear skeletons dragging swords (Room 3)
- DC 14 Perception to overhear cultist conversations (Rooms 1, 4)
- DC 12 Stealth to avoid alerting guards on broken glass (Room 11)
- DC 16 Perception to see into adjacent rooms

**Current state**: Skill checks implemented but not integrated into exploration
- Can roll skill checks
- No "listening at doors" mechanic
- No "spotting enemies before engagement" mechanic
- No surprise/stealth system

**Blocking**: PARTIAL - Can complete adventure but missing key mechanics

#### Conditions & Status Effects (#122 - MEDIUM)
**Required by adventure**:
- **Poisoned condition** (DC 10 CON save in Room 8, lasts 1 hour)
- **Paralysis** from ghoul attacks
- **Bless** spell (acolyte casts on self + 2 cultists)
- **Disadvantage** (Durgon's first round attacks)

**Current state**: Some conditions implemented
- ✅ Basic conditions exist (prone, etc.)
- ❌ Poisoned condition with duration
- ❌ Paralysis from ghoul
- ❌ Bless spell effects
- ❌ Disadvantage tracking

**Blocking**: PARTIAL - Core ghoul mechanic missing

### ❌ NOT IMPLEMENTED - Critical Gaps

#### 1. Lighting & Vision System (#124) - CRITICAL
**Impact**: Blocks entire adventure playthrough
- Crypt & temple are pitch black
- No way to handle darkvision
- No light sources or torches
- No dim light penalties

**Maps to issue**: #124 (Add lighting system to dungeon rooms)

#### 2. Time Tracking (#123) - CRITICAL
**Impact**: Breaks adventure timing mechanics
- Poisoned condition lasts "1 hour"
- Durgon takes "approximately 12 hours" to reform
- Long rest mechanics (8 hours)
- No way to track passage of time

**Adventure quote**: *"Read the following if the characters enter the chamber after twelve hours have elapsed"*

**Maps to issue**: #123 (Implement time tracking and timed spell effects)

#### 3. Ghoul Paralysis Attack - CRITICAL
**Impact**: Core monster mechanic missing
- Ghouls can paralyze on hit
- This is their signature ability
- Without it, encounter is much easier

**Current state**: Ghoul likely doesn't have paralysis
**Maps to issue**: #103 (Verify monster special attack saving throws)

#### 4. Secret Doors & Hidden Rooms - MEDIUM
**Impact**: Missing optional content
- DC 14 Investigation check to find mechanism (Room 1)
- Secret door with draft (Room 1)
- Hidden room behind tapestry (Room 11)

**Current state**: No secret door mechanics
**Maps to issue**: #101 (Skill check triggers during exploration)

#### 5. Locked Doors & Lock Picking - MEDIUM
**Impact**: Blocks some paths (but alternatives exist)
- DC 12 Dexterity + Thieves' Tools to pick locks (Rooms 3, 8)
- DC 12 Strength to break doors (Rooms 3, 8)
- Can brute force doors as alternative

**Current state**: Unknown if Thieves' Tools checks work
**Maps to issue**: #101 (Skill check triggers)

#### 6. Listening at Doors - MEDIUM
**Impact**: Tactical information loss
- Characters can hear chanting through door (Room 5)
- Hear skeletons dragging swords (Room 3)

**Current state**: No "listen at door" action
**Maps to issue**: #101 (Skill check triggers)

#### 7. Social Encounter with Durgon - MEDIUM
**Impact**: Missed non-combat resolution
- DC 18 Charisma checks to avoid final fight
- Deception, Intimidation, or Persuasion
- Roleplay opportunity

**Current state**: Unknown if social checks work in combat situations
**Maps to issue**: Possibly new issue needed

#### 8. Surprise Mechanics (#104) - LOW
**Impact**: Enhanced tactical play
- Surprise round if characters attack Durgon after convincing him
- Cultists "need a round to get weapons ready" (surprised)

**Current state**: Unknown if surprise rounds implemented
**Maps to issue**: #104 (Alert State and Surprise Round Mechanics)

#### 9. Advantage/Disadvantage Tracking - LOW
**Impact**: Durgon's disadvantage on first turn
- "His first round of attacks are made at disadvantage"

**Current state**: Unknown if advantage/disadvantage implemented
**Maps to issue**: Possibly covered by #122 or needs new issue

### 🔄 NICE TO HAVE - Enhancement Opportunities

#### 1. Spell Slot Display (#105)
**Impact**: Quality of life for spellcasters
- Acolytes cast bless and sacred flame
- Mage has 1st-level slots remaining
- Players need to track their own slots

**Maps to issue**: #105 (Display spell slot availability)

#### 2. Item Usage in Combat (#56)
**Impact**: Using potions, holy water, etc.
- Characters might want to use items during fight

**Maps to issue**: #56 (Implement item usage during combat)

#### 3. Quest/Journal System (#102)
**Impact**: Track adventure progress
- Journal found on cultist corpse
- Map to cult hideout
- Map to temple

**Maps to issue**: #102 (Quest item system and campaign progression)

## Critical Path to Playability

### BLOCKER Issues (Must Fix)
1. **#124** - Lighting system (CRITICAL)
   - Entire adventure happens in darkness
   - Without this, adventure doesn't make sense

2. **#123** - Time tracking (CRITICAL)
   - Poisoned condition (1 hour)
   - Durgon reform timer (12 hours)
   - Long rest mechanics

3. **#103** - Ghoul/Ghast paralysis (CRITICAL)
   - Core monster mechanic
   - Makes encounters trivial without it

### HIGH Priority Issues (Should Fix)
4. **#101** - Skill check triggers (HIGH)
   - Listening at doors
   - Finding secret doors
   - Lock picking
   - Spotting enemies before combat

5. **#104** - Surprise mechanics (MEDIUM)
   - Cultists getting weapons ready
   - Surprise rounds

6. **#122** - Conditions (MEDIUM)
   - Poisoned condition
   - Bless spell
   - Disadvantage tracking

### MEDIUM Priority (Enhancement)
7. **#105** - Spell slot display
8. **#56** - Item usage in combat
9. **#102** - Quest journal

## Recommendation

**To play "The Unquiet Dead" adventure**, you MUST implement:
1. #124 (Lighting) - CRITICAL BLOCKER
2. #123 (Time tracking) - CRITICAL BLOCKER
3. #103 (Ghoul paralysis) - CRITICAL BLOCKER

**For a good experience**, also implement:
4. #101 (Exploration skill checks) - HIGH
5. #104 (Surprise rounds) - MEDIUM
6. #122 (Condition tracking for poisoned/bless) - MEDIUM

**Current Backlog Priority** should be:
1. #124 Lighting (blocks adventure)
2. #123 Time tracking (blocks adventure)
3. #103 Monster special attacks (blocks adventure)
4. #101 Skill check triggers (enhances adventure)
5. #104 Surprise mechanics (enhances adventure)
6. #122 Spell concentration/conditions (enhances adventure)

This maps perfectly to the top 6 issues in your backlog!
