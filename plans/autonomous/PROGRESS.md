# Progress Log

Append-only. One entry per wake-up. Newest at the bottom.

Format:
```
## <UTC timestamp> — <issue id> — <stage>
Did: <what happened>
Gate: <pass/fail + evidence>
Next: <the single next stage>
```

---

## 2026-08-02 03:1x UTC — setup — bootstrap
Did: Verified environment end to end before planning. Synced deps; confirmed the
headless client boots and `GameSession` is drivable in-process; confirmed MCP
serves; confirmed git push reachable. Found and fixed the empty-vault blocker
(added `scripts/seed_test_vault.py`). Captured the test baseline (3 pre-existing
failures) and five landmines into `BASELINE.md`. Wrote the loop protocol,
roadmap, and this log.
Gate: pass — playtest harness proven runnable, baseline pinned.
Next: P1-01 SPEC.

## 2026-08-02 03:3x UTC — P1-01 — SPEC
Did: Wrote `issues/P1-01.md` — session protocol types. 6 acceptance criteria, each
with a named verification method; exact type signatures; client-facing UI contract
for terminal / 2D / MCP; rollback plan. Read the existing surfaces first so the
design composes rather than guesses: `core/move_result.py` sets the house style
(frozen + slots + per-field edge-case docs), and `GameEvent` reuses the existing
`EventType` enum rather than introducing a parallel taxonomy.
Notable find: `InitiativeTracker` already has `pause_for_reaction()`,
`resume_paused_turn()`, and `is_paused_for_reaction` (`systems/initiative.py:285-338`).
The engine can already pause mid-turn — P1-03 only needs to add the channel that
routes the question to a human, which de-risks it substantially.
Gate: pass — Definition of Ready fully satisfied.
Next: P1-01 BUILD.

## 2026-08-02 03:4x UTC — P1-01 — BUILD
Did: TDD. Wrote `tests/session/test_protocol.py` (31 tests, one class per AC),
confirmed it failed on `ModuleNotFoundError`, then implemented
`dnd_engine/session/protocol.py` and `__init__.py`. Matched the `core/move_result.py`
house style: frozen + slots, per-field docs covering `None` semantics.
Design note worth keeping: intent `from_dict` dispatch uses an explicit registry
built after the class definitions rather than `__init_subclass__`, because
`slots=True` makes the dataclass decorator return a *replacement* class object —
a subclass hook would have registered the pre-slots class and silently broken
deserialisation.
Gate: PASS.
  - new tests: 31 passed
  - engine suite: 3686 passed, 0 failed
  - client-2d: 576 passed, 2 failed (both pre-existing baseline)
  - client-terminal: 506 passed
  - total failures 2, at or under the pinned baseline
  - ruff clean, mypy clean on new code
  - strangler gate: 2D client boots and renders; terminal client imports clean
Finding: the engine's "1 pre-existing failure" is **flaky, not stable**.
`test_party_defeats_enemy` failed 2 of 12 isolated runs (~17%) — it asserts a kill
against an unseeded 1d8+10 roll. `BASELINE.md` updated to treat the engine count as
0–1 and to require an isolated re-run before calling anything a regression.
Next: P1-01 PLAYTEST.

## 2026-08-02 03:5x UTC — P1-01 — PLAYTEST
Did: Forward verification by driving a **real crypt playthrough** (walk, fight
skeletons, 16 resolved weapon attacks) and asserting the protocol carries what the
engine actually emits — added as a permanent test,
`tests/session/test_protocol_integration.py`, with an explicit non-vacuity guard so
it cannot pass on an empty run. Regression verification via `GameSession`: 5/5 moves
accepted, party 44/44, explored 255→270/300.
Gate: PASS — all 6 ACs verified with evidence recorded in `issues/P1-01.md`.
  - session tests: 36 passed (31 unit + 5 integration)
  - engine 3686 / client-2d 576 (2 pre-existing) / client-terminal 506
  - ruff clean
Two findings the unit tests could never have caught, both folded into the
roadmap sketches of the issues they affect:
  1. **Weapon attacks emit nothing to the event bus.** `ATTACK_ROLL` fires only
     from the spell path, and `CombatEngine` is constructed without a bus at all.
     16 real attacks produced zero attack/damage events. P1-02 therefore cannot
     build its event stream from bus subscriptions — it must synthesize events
     from returned result objects and merge them with bus events.
  2. **The engine has no determinism seam.** Enemy AI targeting calls global
     `random`, bypassing the injected `DiceRoller`. Seeding the dice leaves the
     type set varying 5-6; adding `random.seed()` made it worse (9 to 46 events);
     pinning `PYTHONHASHSEED` stabilised the count but not the types. This makes
     P1-04's "run twice, assert identical" premise unsound, so P1-04 was
     redesigned in `ROADMAP.md` to a same-run comparison that has no RNG
     dependence. Logged as Q-002 for Joe.
Next: P1-01 REVIEW.

## 2026-08-02 04:0x UTC — P1-01 — REVIEW
Did: Adversarial pass framed as "which AC can I prove is NOT met" rather than a
diff read. Found one critical defect and one spec/implementation mismatch.
**CRITICAL (fixed): `GameEvent` could not carry real movement payloads.**
`CREATURE_MOVED` carries `Position` objects, which are not JSON-serialisable, so
`ActionResult.to_json()` raised `TypeError` on any grid movement — and P1-02's
facade will emit exactly those. Tuples were separately lossy (returned as lists,
compared unequal). PLAYTEST missed it because crypt navigation is room-based and
never touches the grid path. Fixed by normalising payloads through a new
`to_jsonable()` at construction, so in-memory form == wire form; `Position(1,2)`
now renders as `{"x":1,"y":2}` and unknown objects degrade to `str()` rather than
breaking a turn. 8 regression tests added.
**Spec corrected: AC-3 claimed four outcome states, the design has three.**
Amended the AC rather than leaving a spec the code doesn't meet; logged the
rejected-vs-error distinction to FOLLOWUPS for P1-02.
Attacked and found sound: no transitive `core` import (AC-1 holds beyond its
static check), malformed wire input rejected cleanly, no strangler violation.
Gate: PASS — zero unresolved critical findings.
  - session tests 44 passed; engine 3699 passed; client-2d 576 (2 pre-existing);
    client-terminal 506; ruff + mypy clean; both clients boot and play
Baseline correction: a new engine failure appeared that was NOT mine. Applied the
isolation procedure — 10/10 passes isolated, and 4 of 5 full runs fully green with
identical code. The engine suite is flaky in at least two independent places, so a
raw failure count is not a usable gate. `BASELINE.md` now carries an explicit
3-step procedure to follow before ever declaring a regression.
Next: P1-01 SHIP.

## 2026-08-02 04:1x UTC — P1-01 — SHIP ✅ ISSUE COMPLETE
Did: Verified the full Definition of Done rather than rubber-stamping it, then
marked P1-01 done and queued P1-02.
Gate: PASS — every DoD item confirmed fresh:
  - session tests 44 passed (31 unit + 5 integration + 8 normalisation regression)
  - engine 3699 passed, 0 failed
  - client-2d 576 passed, 2 failed (both pre-existing baseline)
  - client-terminal 506 passed
  - regression playtest PASS (5/5 moves, party 44/44, explored 255→270/300)
  - terminal client boots: "D&D 5E Terminal Game v0.2.0"
  - zero unresolved critical findings; non-critical logged to FOLLOWUPS.md
  - working tree clean, all 4 commits pushed
Corrected the AC-2 evidence row to record that its first PASS was wrong — the
playtest never carried a `Position` because crypt navigation is room-based, so
the gap only surfaced under adversarial review. The evidence table should show
what actually happened, not a tidied version.
**P1-01 delivered:** `dnd_engine/session/` — `Intent` (+4 subclasses),
`GameEvent`, `PendingDecision`, `ActionResult`, `to_jsonable`. Purely additive;
nothing outside its own tests imports it yet. P1-02 gives it a producer.
Next: P1-02 SPEC — with two design inputs already captured in the roadmap sketch
(weapon attacks emit nothing to the bus; the rejected-vs-error split).

## 2026-08-02 04:2x UTC — P1-02 — SPEC
Did: Wrote `issues/P1-02.md` — the `Session` facade that owns the turn loop.
9 acceptance criteria, each with a named verification method; exact signatures; a
turn-advancement table mapping every branch to the `cli.py` line it absorbs; UI
contract for terminal / 2D / MCP; rollback plan.
Studied the real turn loops first rather than designing in the abstract. The
terminal client's `run()` (`cli.py:6100-6230`) carries ~100 lines of turn-structure
*rules* in the UI: skip-dead using an `is_dead` vs `is_alive` distinction, death
saves, stabilized skip, incapacitation handling, turn-start effects, five separate
`next_turn()` calls, and the private `_check_combat_end()`. That whole block is
what the facade absorbs, and each branch is now a row in the design table with its
source line.
Worth noting the engine is not uniformly leaky: the *enemy* side is already clean —
`process_enemy_turn()` advances initiative itself and `EnemyTurnResult` is
explicitly documented as needing no game logic from the UI. The gap is an owner for
the loop and a unified event stream, not missing engine capability.
Two design decisions recorded for scrutiny at REVIEW:
  1. AC-5 exists because weapon attacks emit nothing to the bus (P1-01 finding), so
     the facade must synthesize attack/damage events from `PlayerAttackResult` and
     merge them with real bus events in true chronological order (AC-6). This is
     why the facade cannot be a thin passthrough.
  2. AC-7 adds `ErrorKind` to split "the rules said no" from "something broke",
     honouring the P1-01 AC-3 amendment. Doing so requires relaxing my own P1-01
     test that allows only two enums in `protocol.py`. That test's purpose was to
     block a parallel *event* taxonomy, which `ErrorKind` is not — but relaxing a
     gate I wrote needs calling out, so it is flagged in the AC and must be
     re-examined at REVIEW.
Also logged: the CLI builds its own `ConditionManager` despite `GameState` already
owning one. The facade will use the engine's.
Gate: pass — Definition of Ready fully satisfied.
Next: P1-02 BUILD.

## 2026-08-02 04:3x UTC — P1-02 — BUILD
Did: Implemented `dnd_engine/session/session.py` — the facade that owns the turn
loop — plus `ErrorKind` on the protocol, and 32 new tests (76 in the session suite).
The turn advancer absorbs the branch structure the terminal client carries today:
skip-dead (via `is_dead`, not `is_alive`, because an unconscious character is not
alive but still takes a turn), death saves, stabilized skip, incapacitation,
turn-start effects, enemy draining, and combat-end checks — with an iteration cap
so a malformed initiative order cannot hang a client.
`_EventRecorder` merges bus events and synthesized events into one stream in true
arrival order, which is what makes weapon attacks visible at all (AC-5/AC-6).
Gate: PASS.
  - session suite 76 passed (39 protocol + 5 protocol-integration + 17 session-unit
    + 15 session-combat-integration)
  - engine 3731 passed, 0 failed
  - client-2d at pre-existing baseline; client-terminal 506 passed
  - ruff clean, mypy clean, strangler playtest PASS
**A full crypt combat is now playable end to end through `perform()` alone**, with
an AST assertion in the integration test proving the caller never touches
`initiative_tracker`, `_check_combat_end`, or `process_enemy_turn`.
Two things worth recording:
  1. **mypy caught a real latent crash.** `GameState.initiative_tracker` is
     `Optional`, and I had six unguarded `.next_turn()` accesses. Routed them
     through `_require_tracker()`, which raises a clear error that `perform()`'s
     boundary converts to `ErrorKind.INTERNAL` rather than crashing the client.
     Worth noting the type checker found this, not the 76 tests.
  2. **My own AST guard test initially failed on itself** — it grepped raw source
     for forbidden names and matched its own docstring. Rewritten to walk the AST
     for actual attribute access, which is what it should have been.
Baseline correction: one client-2d run showed 3 failures instead of 2; six
consecutive runs after it showed exactly 2. client-2d is flaky as well —
`BASELINE.md` updated to treat its count as 2–3.
Next: P1-02 PLAYTEST.

## 2026-08-02 04:4x UTC — P1-02 — PLAYTEST
Did: Played real games through the facade instead of only asserting — a healthy
party through a full fight, four fragile-party runs to force characters down, and
exploration after combat. All 9 ACs now verified with evidence in `issues/P1-02.md`.
Confirmed working under real play: death saves fire for real (seed 11 produced 4,
with a character going unconscious then dying), combat ends with XP, exploration
moves are accepted and illegal ones rejected as `RULE`, and the event stream reads
like a D&D log rather than a state dump.
**Two defects found, both fixed — neither reachable by the unit tests:**
  1. **CRITICAL — deadlock at combat start.** When an enemy held the first
     initiative slot, `awaiting_actor_id` was `None` while `in_combat` was True.
     Enemy turns drain only inside a session call, so a client following the
     documented contract had no legal move — roughly a coin flip on every fight.
     AC-2 was not met. Fixed by adding `Session.advance()`, which drains until a
     player is up or combat ends, with `_advance_to_next_actionable_turn` taking a
     `skip_current` flag so entering the loop cold does not skip whoever is up.
  2. **Every death save was reported twice.** The bus already emits `DEATH_SAVE`
     with a richer payload (roll, success, natural_20, stabilized, dead), and I was
     synthesizing a thinner one alongside it. Rather than guess at the general
     case, I measured: across 5 seeded fights, `ATTACK_ROLL` was 0 bus / 33 synth,
     `DAMAGE_DEALT` 0/20, `CHARACTER_DEATH` 0/12, and `DEATH_SAVE` 7/7 — exactly
     one duplicate. Dropped the synthesized version and added a guard test that
     fails if any type ever arrives from both sources again.
Also fixed a test that was **passing for the wrong reason**: AC-3's check counted
distinct actor names, and the second name came from the duplicate death-save event
I removed. Seeing only the enemy actually proves draining worked, so the assertion
was rewritten to say what AC-3 means — a waiting player still sees enemy activity.
Gate: PASS — 80 session tests; engine 3735 passed / 0 failed; clients at baseline;
ruff + mypy clean; strangler playtest PASS.
Next: P1-02 REVIEW.

## 2026-08-02 04:5x UTC — P1-02 — REVIEW
Did: Adversarial pass against the ACs. Found two critical defects, both fixed.
**C-1 (critical): a client could not target one of two identical enemies.** Both
crypt skeletons reported as "Skeleton" with different HP; `_resolve_target`
silently attacked whichever came first, so aiming at the wounded one hit the
healthy one — incorrect adjudication, not cosmetics. Root cause is precisely the
pattern this issue exists to remove: `assign_combat_numbers()` exists to produce
"Skeleton 1"/"Skeleton 2" but **nothing in the engine calls it — only
`client-terminal` does** (`cli.py:6243`), so terminal players could distinguish
enemies and every other client could not. The facade now assigns numbers itself
and resolves targets by display name. Verified: attacks on "Skeleton 2" took it
12→0 while "Skeleton 1" stayed at 13.
**C-2 (critical): the combat log named targets ambiguously**, using the raw name
while the snapshot used the display name. Now consistent.
Also completed the P1-02 PLAYTEST deadlock fix: the rejection message now names
the remedy rather than just stating the problem.
Re-examined the enum-gate relaxation I flagged at SPEC. Verdict: legitimate — the
assertion is exact set equality, so any new enum still fails it, and `ErrorKind`
classifies failures rather than events. The guard's purpose is intact.
One honest note: adding numbering broke 11 unit tests because my stub tracker
lacked the methods. That was the test double being incomplete, not a product
defect — but it did reveal the call was undefended, so it now degrades via
`getattr` instead of assuming the method exists.
Gate: PASS — zero unresolved critical findings.
  - session 83 passed; engine 3738 passed / 0 failed; clients at baseline
  - ruff + mypy clean; strangler playtest PASS
Next: P1-02 SHIP.

## 2026-08-02 05:0x UTC — P1-02 — SHIP ✅ ISSUE COMPLETE
Did: Verified the full Definition of Done fresh, then marked P1-02 done and queued
P1-03.
Gate: PASS — every item confirmed:
  - session suite 83 passed (39 protocol + 5 protocol-integration + 17 unit + 22
    combat-integration)
  - engine 3738 passed, 0 failed
  - client-2d 576 passed, 2 failed (pre-existing baseline)
  - client-terminal 506 passed
  - 2D client boots and renders; terminal client boots at v0.2.0
  - zero unresolved critical findings; non-critical in FOLLOWUPS.md
  - working tree clean, all commits pushed
End-to-end proof — a complete crypt fight rendered from `ActionResult` alone, with
no client-side turn logic at all:
```
Thorin misses Skeleton 1 with unarmed strike.
Skeleton 1 hits Thorin with Shortsword.
Thorin takes 4 damage.
Skeleton 2 misses Thorin with Shortsword.
Garrick hits Skeleton 1 with unarmed strike.
Skeleton 1 takes 10 damage.
Thorin hits Skeleton 1 with unarmed strike.
Skeleton 1 falls.
Thorin hits Skeleton 2 with unarmed strike.
Skeleton 2 falls.
[COMBAT_END] victory, 100 xp, 50 per character
```
Resolved in 7 player turns. Enemies correctly disambiguated, damage tracked,
initiative order visible — the log reads as D&D rather than as a state dump.
**P1-02 delivered:** `Session.perform()` / `Session.advance()` / `snapshot()`, with
the engine owning turn advancement, death saves, enemy draining, combat-end
detection, and enemy disambiguation. Purely additive — both clients untouched.
Next: P1-03 SPEC — `PendingDecision` for opportunity attacks. Note from P1-01:
`InitiativeTracker` already has `pause_for_reaction()` / `resume_paused_turn()` /
`is_paused_for_reaction`, and `EventType` has **no** opportunity-attack or reaction
member yet, so one will need adding (additive, safe).

## 2026-08-02 05:1x UTC — P1-03 — SPEC
Did: Wrote `issues/P1-03.md` — opportunity attacks as `PendingDecision`. 8 ACs,
each with a named verification method; interception flow; per-file risk table; UI
contract; rollback plan.
Read the whole reaction stack before designing, and it is in better shape than the
roadmap assumed. Three things make this small and cleanly additive:
  1. `ReactionDispatcher.publish()` **already** wraps each handler in
     `pause_for_reaction()` / `resume_paused_turn()`, so the engine can already
     halt mid-turn and report the reactor as current.
  2. `register()` is documented **"last wins"** (`reactions.py:120`), so the
     session can register its own OA handler after the engine's default and take
     precedence — interception with no engine change.
  3. `publish()` consumes the reaction slot **only** on `reacted=True`, so a
     handler that defers the decision returns False and leaves the slot intact,
     which is exactly the SRD rule for a declined reaction.
So the missing piece really is only the channel to a human — which is what
`PendingDecision` was built for in P1-01. Good sign the P1-01 design was right.
Two decisions flagged for REVIEW:
  1. **AC-4 pins `default_option_id` to "attack".** The engine currently always
     takes the OA, so any other default would silently change the game for every
     existing caller. Preserving current behaviour matters more than picking the
     tactically "better" default.
  2. **One engine file gets touched.** `opportunity_attacks.py` gains a
     `build_default_opportunity_handler()` and the existing registrar becomes a
     thin wrapper over it. Behaviour-identical, and the alternative was
     duplicating ~20 lines of reach/visibility geometry into the session — two
     copies of a rule that must agree. Existing OA tests must pass unmodified.
Also recorded a real fidelity limitation rather than letting it pass unnoticed:
the engine steps the mover *then* publishes the provoke, so the OA resolves after
the move rather than interrupting it. Same outcome except when the attack would
have stopped the movement. Logged to FOLLOWUPS.
Gate: pass — Definition of Ready fully satisfied.
Next: P1-03 BUILD.
