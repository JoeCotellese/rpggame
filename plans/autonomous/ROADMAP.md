# Roadmap — Session Facade + DM Adjudication

**Working branch:** `claude/dnd-engine-game-integration-kwrd0j`
**Mode:** strangler / additive only — see `README.md`
**Scope for this run:** P1-01 → P1-04, then P2-05.

## Why this order

The engine is already a package with no UI dependencies, but it is not
consumable as a library: `GameState` is 6,539 lines mixing rules, spatial,
exploration, campaign progression and presentation, and there is no command API.
The consequence is measurable — `client-terminal/.../cli.py` calls
`initiative_tracker.next_turn()` at **10 separate sites** and the private
`game_state._check_combat_end()` **7 times**; `client-2d/.../session.py` carries
its own independent combat state machine and also calls `_check_combat_end()`.
The turn loop lives in the clients, so every new client re-implements D&D's turn
structure.

P1-01 → P1-04 move the turn loop into the engine behind a single facade.
P1-03 is the fidelity unlock: reactions require the engine to *pause and ask a
human*, which is impossible today. P2-05 is the experience unlock: open-ended
player intent adjudicated by rules rather than a fixed action menu.

## Status legend

`todo` → `spec` → `build` → `playtest` → `review` → `done`
Terminal states: `blocked`, `reverted`

## Queue

| ID | Title | Status | Stage | Depends on |
|---|---|---|---|---|
| P1-01 | Session protocol types: `Intent`, `GameEvent`, `PendingDecision`, `ActionResult` | spec | BUILD next | — |
| P1-02 | `Session` facade owning the turn loop (move + attack) | todo | — | P1-01 |
| P1-03 | `PendingDecision` for opportunity attacks (pause-and-ask) | todo | — | P1-02 |
| P1-04 | Conformance suite: facade vs. legacy path produce identical outcomes | todo | — | P1-02 |
| P2-05 | LLM DM adjudication: freeform intent → proposed ruling → engine adjudicates | todo | — | P1-02 |

## Issue sketches

Full specs are written during each issue's `SPEC` stage into `issues/<id>.md`.
These sketches are the input to that stage, not a substitute for it.

### P1-01 — Session protocol types

New package `dnd_engine/session/`. Pure data types, no behaviour, no imports
from either client. `Intent` (what a player wants to do), `GameEvent` (what
happened, serialisable), `PendingDecision` (engine is asking a question and
cannot proceed), `ActionResult` (events + optional pending decision).

No player-visible surface. The contract is the client-facing one: a client
should be able to render everything it needs from `ActionResult` alone, without
reaching into `GameState`.

### P1-02 — `Session` facade owning the turn loop

`Session.perform(intent) -> ActionResult`. Wraps an existing `GameState`.
Movement and attack intents only. Critically, the facade — not the caller —
calls `initiative_tracker.next_turn()` and checks combat end. `GameState` is not
modified; the facade composes it.

Success looks like: a scenario playable end to end through `perform()` without
the caller ever touching `initiative_tracker`, `_check_combat_end`, or any
private member.

### P1-03 — `PendingDecision` for opportunity attacks

The acid test for the whole design. When a creature leaves a threatened square,
`perform()` returns an `ActionResult` carrying a `PendingDecision` instead of
resolving automatically. The caller answers with
`Session.resolve(decision_id, choice)`.

`ReactionDispatcher.publish()` (`systems/reactions.py:146`) already returns
outcomes but has no channel to route a question to a human — that is the gap
this closes. Existing automatic behaviour must remain available and unchanged
for existing callers.

### P1-04 — Conformance suite

Drive the same seeded scenario twice — once through the facade, once through the
legacy `GameState` path — and assert identical final state (positions, HP,
initiative order, combat status). This is what keeps the strangler honest: if
the facade ever drifts from the engine's real behaviour, this fails.

### P2-05 — LLM DM adjudication

The pipeline, with the engine authoritative at every step:

```
freeform player text
  → LLM proposes a ruling (ability, skill, DC, success and failure consequence)
  → ENGINE rolls and adjudicates          ← authoritative
  → LLM narrates the adjudicated outcome
```

Hard invariants, each of which needs its own test: the LLM never rolls dice,
never sets HP, never decides success or failure, and never mutates game state. A
malformed or hostile LLM response must degrade safely, not corrupt play.
`core/constants/dc_ladder.py` supplies the DC vocabulary.

**Constraint:** no API key in this environment. Build against the `LLMProvider`
interface, verify with `llm/debug_provider.py`, and flag the real-provider path
in `QUESTIONS.md` for Joe's manual validation.

## Explicitly out of scope tonight

- Migrating either client onto the facade (strangler: additive only)
- Splitting presentation out of `GameState`
- The content-module system and `module.json` manifests
- Fixing the 3 pre-existing test failures
- Fixing the two-vault split or the missing Cleric class (logged in
  `BASELINE.md`, belongs in `FOLLOWUPS.md` if touched)
