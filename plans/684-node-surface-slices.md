# [#684] Node/social surface for settlements — slice plan

## Status

Drafted 2026-07-18. Supersedes the flat acceptance-criteria checklist in #684 with
an ordered slice roster for **autonomous** implementation: every slice gates on a
check that runs without a human (pytest, pexpect, or headless MCP playtest), and
each slice is one PR.

Progress: slice 1 merged (PR #686), slice 2 merged (PR #687), slice 3 merged
(PR #689). Next: slice 4 (transition seam). Standing review policy: deep
multi-agent review offered to Joe only at slices 4 and 6; `/code-review` high on
those two, medium elsewhere; architecture-guardian on 2/4/7. Merges are done by
Joe (permission classifier blocks `gh pr merge`). Related: #688 tracks the
pre-existing `load_skills()` caching gap found in slice-3 review.

Parent design: `docs/PARTIAL_TOTM_DESIGN.md` (town node surface).
Related epics: plan-07 #536 (pillars — NOT built here), plan-10 #539 (engine owns
rules, clients thin — governing constraint).

## Goal

Settlements present as theater-of-the-mind: a flat list of **nodes** (pick a
place), prose descriptions, and contextual actions — no walked `@`. The Arden
opening beat of The Unquiet Dead (quest hook → shop → rest → rumors → depart to
the crypt) is playable end-to-end in the terminal client.

## Decisions on record

- **Input model: hybrid (v1).** The prompt accepts **a number or prose**. The
  numbered action list stays on screen as the DM's offered affordances; typed
  prose ("ask marta about the lights", "head to the chapel") is the intended
  primary mode. Prose routes through the existing **rule-based** `CommandParser`
  (rapidfuzz — deterministic, no LLM), extended with node vocabulary. Deep
  conversation remains the existing LLM chat loop inside `talk`. LLM-routed
  freeform intent classification is **deferred** (slots in later as a
  low-confidence parser fallback; pairs with plan-07's GM loop).
- **NL lives in the client input layer only.** The engine API is typed intents
  (`enter_node`, `talk`, `shop`, …). Plan-10 boundary: deepening NL later
  requires zero engine churn.
- **Main never breaks.** Slices 1–5 build against a **lab settlement fixture**
  (`lab_settlement.json`, alongside the laboratory dungeon). Arden stays a tile
  town until slice 6 cuts it over.
- **Pillar dependency scoped down.** This plan adds a lightweight
  surface-discrimination concept (grid vs node), NOT #536's full
  explore/social/combat state machine.
- **Save compatibility at cutover:** one-shot id remap (tile room → nearest
  node) applied at load; old Arden tile-room ids resolve rather than invalidate
  saves.
- **Autonomy protocol per slice:** branch `feature/684-s<N>-<desc>` → TDD →
  package suite green → review checkpoints (below) → PR → CI green → merge →
  next slice.

## Review protocol (lean — no multi-agent fan-out, per token-budget decision 2026-07-18)

| Checkpoint | When | Mechanism |
|---|---|---|
| Design pass | Before slice 1; re-run if slice 2 changes the API shape | Inline single-pass review of the API shape against `PARTIAL_TOTM_DESIGN.md` + plan-10 boundaries (main context, no agents) |
| Architecture check | Slices 2, 4, 7 | `architecture-guardian` skill before the PR |
| Code review | Every slice | `/code-review` medium; **high** on slices 4 and 6 (seam + cutover). Confirmed findings fixed before PR |
| QA gate | Slice 8 | `/playtester` free-form run of the Arden beat |

Merge policy: CI green + clean review at the slice's checkpoint level = merge.

## Slices

Each slice is a single PR with its gating tests named up front. Sub-issues
created per slice at slice start (plan-03 convention).

### Slice 1 — Node schema, loader validation, lab fixture

**Surface:** `dnd_engine/rules/loader.py` (+ a validation module);
`data/content/dungeons/lab_settlement.json` (new fixture).

Locations may declare `surface: "node"` with a `nodes` collection and
`start_node` (grid `rooms` + `start_room` path untouched). Validation:
`start_node` exists; nodes carry `name`/`blurb`/`description`; `actions` drawn
from the fixed vocabulary (`talk`, `shop`, `rest`, `gather_rumors`,
`read_job_board`, `examine_*`, `transition`); every skill-gated action authors
`on_success` AND `on_failure` prose; `transition` targets declare a destination.

**Gating tests:** new `tests/test_node_schema.py` — valid fixture loads; each
validation rule has a failing-fixture case.

### Slice 2 — Engine node-surface state + navigation API

**Surface:** `dnd_engine/core/game_state.py` (+ new `core/node_surface.py` if
warranted).

`GameState` recognizes a node-surface location: `is_node_surface()`,
`current_node()`, `list_nodes()` → (id, name, blurb), `enter_node(id)` → prose +
present NPCs (existing `NPCManager.get_npcs_in_room` keyed by node id) +
available actions. Tile machinery never instantiated on a node surface;
grid-only methods (`move`, exits, search) degrade cleanly.

**Gating tests:** integration vs lab fixture — enter settlement, list nodes,
enter node, NPC presence, grid-method degradation.

**Checkpoint:** architecture-guardian.

### Slice 3 — Node actions: social routing + skill gates

**Surface:** engine node action dispatch.

`interactions()` merges node `actions` + present NPCs. `talk`/`shop`/`rest`
route into existing NPC dialogue/shop/reputation systems; `gather_rumors` and
`read_job_board` return prose gated by disposition; `examine_*` runs the skill
check (seeded dice in tests) and returns authored success/failure prose.
Disposition surfaces as a one-word text tag — never a number, never color.

**Gating tests:** integration, seeded RNG; both branches of every skill gate
asserted; disposition tag correctness at friendly/neutral/hostile thresholds.

### Slice 4 — Transition seam, both directions

**Surface:** `game_state.py` cross-dungeon move path, `room_registry`.

Node `transition` action → loads the target grid dungeon at its start room
(extends the existing cross-dungeon mechanism). Reverse: a grid exit whose
destination is a node id re-enters the settlement's node surface at that node.
This is the crypt ↔ town seam.

**Gating tests:** round-trip integration — lab settlement → laboratory dungeon
→ back to originating node; state preserved across the seam.

**Checkpoints:** architecture-guardian + deep adversarial panel.

### Slice 5 — Terminal three-zone rendering + hybrid input

**Surface:** `client-terminal` — `ui/cli.py` node-surface branch in the run
loop; `nlp/command_parser.py` + `GameContextProvider` node extensions.

Three zones rendered as text: status strip (location · time · gold), scrolling
prose log (DM voice, 2–4 short paragraphs per beat), numbered contextual action
list. Node list hides behind `Go elsewhere ▸`. Prompt accepts **number or
prose**: new `ACTION_PATTERNS` for node intents (`go/visit/head to <node>` →
`enter_node`, etc.), context provider feeds node names + present NPCs.
Mechanics bracketed (`[Religion DC 12]`); gated/locked cues are text/symbol,
never color-only.

**Gating tests:** parser unit tests (prose → intent mapping, fuzzy node names);
pexpect e2e on the lab settlement — full keyboard playthrough via numbers AND
via typed prose.

**Carried findings from slice 2 review:** `CLI.display_room` →
`get_room_display_context` → `get_current_room` raises on node surfaces — the
node render branch this slice builds must be reached first; the CLI `reset`
handler renders the room after reset and would mis-report "reset failed" when
resetting into a settlement; if an event consumer ever needs to distinguish
surfaces, add a `surface` field to ROOM_ENTER data rather than a new event
type.

### Slice 6 — Arden cutover + full-beat e2e

**Surface:** campaign data + save-load remap.

`town_of_arden.json` re-authored: 11 tile rooms → ~6 nodes (town_square,
rusty_tankard, chapel, davos_manor, general_store, warrens_alley) with authored
blurbs/descriptions. `npcs.json`: 5 `current_location`/`home_location` values →
node ids (content otherwise untouched). `campaign.json` `starting_room` →
node-aware. Return exits in `crypt.json` (`arden.town_road`) and
`cult_hideout.json` (`arden.warrens_alley`) repointed at nodes. Save-load
tile-room → node remap.

**Gating tests:** data validation; save-migration unit tests; scripted pexpect
run of the acceptance beat — quest hook, shop, rest, gather rumors, depart to
crypt, return to town.

**Carried findings from slice 3 review (authoring lints for this slice):**
`disposition_effects` keys other than friendly/neutral/hostile are unreachable
(the 3-state disposition model never yields "unfriendly"/"allied") — don't
author them for Arden NPCs, or add an NPC-data lint; gate skills are not
validated against skills.json at load (a typo fails at play time as
NodeActionError) — lint authored gate skills when writing Arden content.

**Checkpoint:** deep adversarial panel. Candidate for `/code-review ultra`
(user-triggered).

### Slice 7 — 2D client parity

**Surface:** `client-2d` — `GameSession`, MCP tools.

Render the same node model; MCP `game_state` exposes node list/actions so
headless playtest can drive it. 2D adds decoration only — zero information the
terminal lacks.

**Risk flag:** scope-check at slice start — current campaign/town support in
client-2d is unverified; slice may shrink (MCP-only) or split.

**Carried finding from slice 2 review:** `EngineAdapter.new_game` sets
`_initialized = True` before calling `get_current_room()`, so a node-surface
dungeon leaves the adapter claiming initialized while every room-based call
raises. Settlements never worked in client-2d (previously failed fast on
`start_room`); make the adapter surface-aware or fail before flagging
initialized.

**Gating tests:** client-2d unit tests + headless MCP playtest of the lab
settlement and Arden.

**Checkpoint:** architecture-guardian.

### Slice 8 — Autonomous QA pass

`/playtester` runs the Arden opening beat free-form (headless MCP + terminal
pexpect), files issues for findings; blocking bugs fixed in-slice, non-blocking
logged.

## Deferred (new issues, out of #684)

- Combat erupting *from* a node (tavern brawl) — needs plan-07 encounter
  machinery; the seam built in slice 4 is the funnel it will use.
- LLM intent-classification parser fallback.
- Visual/clickable town map (TotM doc: later enhancement).
- Travel montage / region map (plan-09).

## Risks

- **Slice 2 API shape is load-bearing** — errors propagate through 3–7; hence
  the upfront adversarial design review re-runs if it shifts.
- **client-2d campaign support unknown** (slice 7 flag).
- **`campaign.json` starting_room semantics** change at cutover; campaign
  start/save/load paths all touch it (slice 6 panel lens).
