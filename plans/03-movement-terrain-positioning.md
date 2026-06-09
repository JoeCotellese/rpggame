# [plan-03] Movement, Terrain & Positioning — costs, modes, OAs, footprint, cover

## Status

Restructured 2026-06-09 under the [meta plan audit](./00-plan-restructure-meta.md). Original ticket roster was a mix of shipped work and 2026-05-23 batch-closed `NOT_PLANNED` issues with no implementation. Slices below replace the dormant tickets.

### Already shipped

| Original child | Notes |
|---|---|
| #413 Opportunity Attacks | Emits `OPPORTUNITY_PROVOKED` on movement out of reach. Consumed by Reaction dispatcher in plan-01. |
| #432 Special speeds | `MovementMode` enum + `Creature.speeds` data model landed (`dnd_engine/core/creature.py:31`). Cost integration deferred → see slice 1. |
| #436 Difficult Terrain | `cost_for` (`dnd_engine/systems/action_economy.py`) + `Map.terrain_at` (`dnd_engine/core/map.py`) drive doubled per-foot cost. |
| #442 Creature size / footprint | Large+ creatures occupy NxN block; pathing accounts for footprint. |

### Dormant (superseded by slices below)

| Original | Superseded by | Slice |
|---|---|---|
| #433 per-mode movement costs | #670 | 1 |
| #445 pass-through carve-outs | #671 | 2 |
| #473 Cover system | #672 | 3 |
| #476 diagonal corner-cutting | #673 | 4 |

## Defect

The movement layer treats every step as one foot regardless of mode or geometry. The `MovementMode` enum exists but `cost_for` ignores it — climbing/swimming/crawling/jumping without the matching speed should cost double. `attempt_combat_step` blanket-rejects any occupied tile, so Prone allies, Incapacitated creatures, Tiny creatures, and two-sizes-different creatures can't be passed through. **Cover** — the headline Step-2 attack modifier — is not modeled anywhere: `resolve_attack` has no `cover` parameter, `get_effective_ac` has no cover bump, `make_saving_throw` has no cover kwarg. Diagonal movement allows cuts across wall corners. These are one defect: **the engine has a sparse spatial-geometry layer; movement and attack resolution are missing the cheap typed-traversal hooks that bring SRD geometry to life.**

## Slices

Each slice is a single PR. Each cites its gating tests and declares its skip-count delta. Ordered by smallest blast radius / least dependency first — Cover lands last because it threads through both attack and save paths.

### Slice 1 — Per-mode movement costs

**Issue:** #670 (supersedes #433)

**Surface:** Extend `cost_for` in `dnd_engine/systems/action_economy.py` to consult the moving creature's `speeds` and current `MovementMode`. Mode without matching speed → cost doubles. Jumping → cost equals distance covered, capped by STR (long) / DEX (high).

**Gating tests:** `tests/srd/playing_the_game/test_movement_and_position.py`
- climbing without Climb Speed → 2 ft/ft
- swimming without Swim Speed → 2 ft/ft
- crawling → 2 ft/ft
- jumping → distance-as-cost

**Skip-count delta:** +4

---

### Slice 2 — Pass-through carve-outs and involuntary co-occupancy Prone

**Issue:** #671 (supersedes #445)

**Surface:** `GameState.attempt_combat_step` (`dnd_engine/core/game_state.py`) consults occupant `Conditions` and `size` before rejecting. Carve-outs:

1. Prone occupant — pass through at full cost.
2. Incapacitated occupant — pass through.
3. Tiny occupant — pass through.
4. Two-sizes-larger / smaller occupant — pass through.
5. Voluntary stop in occupied square — still disallowed.
6. Involuntary co-occupancy (e.g., shoved into enemy's square) — both creatures gain Prone.

**Gating tests:** `tests/srd/playing_the_game/test_movement_and_position.py`
- Move through Prone ally
- Move through Incapacitated creature
- Move through Tiny creature
- Move through two-sizes-different creature
- Involuntary co-occupancy → both Prone

**Skip-count delta:** +5

---

### Slice 3 — Cover system at attack-resolution layer

**Issue:** #672 (supersedes #473)

**Surface:**

- New `Cover` enum: NONE / HALF / THREE_QUARTERS / TOTAL.
- `CombatEngine.resolve_attack(..., cover: Cover = Cover.NONE)` at `dnd_engine/core/combat.py:91`.
- `Creature.make_saving_throw(..., cover: Cover = Cover.NONE)` — DEX-save side.
- Total cover short-circuits to rejected-target.
- `GameState.get_effective_ac` layers cover bonus alongside existing AC modifiers.
- Most-protective-applies (no stacking). Cover from creatures only when occupant ≥ "one size smaller is no cover" rule.

| Degree | AC bump | DEX-save bump | Targetable? |
|---|---|---|---|
| Half | +2 | +2 | yes |
| Three-Quarters | +5 | +5 | yes |
| Total | n/a | n/a | no |

**Gating tests:** `tests/srd/playing_the_game/test_making_an_attack.py`
- Half cover: +2 AC / +2 Dex
- Three-quarters cover: +5 AC / +5 Dex
- Total cover: no target
- Most-protective-applies (no stacking)
- Two-sizes-smaller carve-out (no cover granted)
- Plus follow-on tests in `test_ranged_attacks.py`

**Skip-count delta:** +7

---

### Slice 4 — Diagonal movement cannot cross wall corners

**Issue:** #673 (supersedes #476)

**Surface:** Same predicate that powers `attempt_combat_step`'s adjacency check. For each diagonal step `(dx, dy) ∈ {-1,1}²`, reject if either `(x+dx, y)` or `(x, y+dy)` is a wall / space-filling feature.

**Gating tests:** `tests/srd/playing_the_game/test_the_order_of_combat.py`
- `test_diagonal_move_cannot_cross_a_wall_corner`
- Shortest-route count with wall-corner block

**Skip-count delta:** +2

## Out of scope

- Reaction mechanics consuming `OPPORTUNITY_PROVOKED` — plan-01.
- Travel pace and overland mounted movement — plan-09.
- Visibility / Stealth-driven adv/disadv — plan-05 (Cover here is geometric; visibility there is sensory).
- Engine-vs-client ownership of ranged-range checks — plan-10 (#401).
- 5E diagonal variant "every other diagonal counts as 10 ft" — explicit non-goal.
