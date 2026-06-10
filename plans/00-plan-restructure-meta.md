# [meta] Plan Audit & Restructure — 2026-06-09

Cross-plan audit of epics #530–#539 after observing that several "closed" plan-08 children had no shipping code. Eight epics audited (plan-01 through plan-10, excluding plan-04 and plan-08 which were verified shipped in the same session). Triggered by Mr. Cotellese's recollection of premature ticket closures.

## Audit verdicts

| Plan | Epic | Verdict | Children shipped / total | Notes |
|---|---|---|---|---|
| plan-01 Action Economy | #530 | **PREMATURE** | 5 / 19 | 14 `NOT_PLANNED` batch-close in 52s window (2026-05-23 18:05:23 → 18:06:15). Dash / Dodge / Help / Knockout / Drop Prone / Search-as-action / Study / outside-combat one-action gate all dormant. |
| plan-02 Damage-Type Pipeline | #531 | **REAL** | 11 / 11 + #595 | Genuinely shipped end-to-end. Canonical `apply_damage_modifiers` pipeline + AST regression lint (`test_take_damage_pipeline_guard.py`). Metadata hygiene completed 2026-06-09: 7 children (#461 #462 #464 #466 #468 #470 #490) re-closed `COMPLETED`. |
| plan-03 Movement / Terrain | #532 | **PARTIAL** | 5 / 8 | OAs / difficult terrain / size + footprint / special speeds shipped. Dormant: cover (#473 — surfaced by orphan #619), per-mode movement costs (#433), pass-through + involuntary Prone (#445), diagonal corner-cutting (#476 unconfirmed). |
| plan-04 0-HP / Death Saves | #533 | **REAL** | 11 / 11 | Shipped this session. |
| plan-05 Vision / Stealth | #534 | **PARTIAL** | ~5 / 6 | Real `perception.py` module + `VisibilityRelation` + Hide action shipped. 5 GAP skips in `test_vision_and_light.py` still cite closed #494 and #495 (per-creature lighting, magical Darkness vs Truesight). |
| plan-06 Environment / Hazards / Objects | #535 | **PREMATURE** | <1 / 11 | Only narrow `creature_environment()` string-tag shipped. ~35 GAP skips across `test_hazards.py`, `test_interacting_with_objects.py`, `test_underwater_combat.py` cite closed children. |
| plan-07 Three-Pillar Mode / Social / GM | #536 | **PREMATURE** | 0 / 8 | `in_combat: bool` still intact at `game_state.py:118`. No `GameMode` / `narration_loop` / `gm_roll` / `influence` symbols. Every gating skip still names its closed issue. |
| plan-08 D20 / Proficiency | — | **REAL** | 12 / 12 | Shipped this session (slices 4–10). |
| plan-09 Travel / Mounts / World Nav | #538 | **PREMATURE** | <1 / 6 | No `TravelPace` / `Mount` / `Vehicle` / `systems/travel.py`. 37+ GAP skips across `test_travel.py` and `test_mounted_combat.py`. |
| plan-10 2D Client / MCP Convergence | #539 | **PREMATURE** | partial / 15 | 15 children batch-closed in a 37s window. Range check still in 3 sites (`session.py:1592`, `script_executor.py:263`, `game.py:1306`) — was supposed to be 1. 4 of 6 promised MCP tools missing (`game_cast` / `game_use_item` / `game_stabilize` / `game_flee`). Open flake #615 is a symptom. |

## Root cause of premature closures

SRD-audit PRs (#525, #498, others in the 2026-05-23 batch) **documented** the gaps by adding `pytest.skip("GAP: ... Tracked by #N")` markers, then closed the referenced issues as if landing the audit *resolved* them. The "Consolidating into #epic" boilerplate comment was used both for genuine plan-02 closures (where the work landed under the epic's PR umbrella) and for the 4 fully-dormant plans (where no work followed). The two are indistinguishable by close-reason metadata, which is how the bookkeeping drifted.

## Tally

- **Genuinely done (3):** plan-02, plan-04, plan-08
- **Partially done (3):** plan-01, plan-03, plan-05
- **Largely or fully premature (4):** plan-06, plan-07, plan-09, plan-10

## Restructure strategy (option C — fresh slices)

For each non-real plan:

1. **Reopen** the dormant children, OR file `plan-XX: implement <X> (supersedes #YYY)` tickets — preference is supersede so closed-ticket view stays clean and the audit trail lives in the body.
2. **Rewrite the plan doc** in the slice-based format proven by plan-08 / plan-04:
   - Numbered slices, each sized to one PR.
   - Each slice names its gating test (`tests/srd/.../test_<X>.py::Test_<Y>::test_<z>`).
   - Each slice declares its skip-count delta (how many GAP skips it lights up).
   - Slices ordered by dependency / by smallest-blast-radius first.
3. **File fresh child issues** — one per slice — referenced from the plan doc.

Do **one plan at a time** end-to-end (restructure → ship slices → close epic) rather than rewriting all 7 docs up front. Prevents stale docs and decision fatigue.

## Recommended order (smallest leverage to largest)

| Order | Plan | Why this order | Rough size |
|---|---|---|---|
| 0 | plan-02 metadata cleanup | Fast hygiene; not a real restructure. Re-close 8 children as `COMPLETED` so future audits aren't misled. | 1 admin task |
| 1 | **plan-03** | Smallest real gap. 3 known dormant children (#473 cover, #433 per-mode costs, #445 pass-through). Cover is already surfaced by live ticket #619. | ~3 slice PRs |
| 2 | plan-05 | Narrow closeout. Per-creature lighting + magical Darkness/Truesight. Mostly fixing skip-message references + small data-model work. | ~2 slice PRs |
| 3 | plan-01 | Moderate. ~8 missing core actions; each is its own small handler + gating test. | ~6–8 slice PRs |
| 4 | plan-06 | Large. Hazards + first-class Object + underwater combat + carrying capacity + marching order. | ~10+ slices |
| 5 | plan-07 | Large + architectural. Replacing `in_combat: bool` with `GameMode` enum is load-bearing. | ~10+ slices |
| 6 | plan-09 | Large. Travel pace + Mount + Vehicle + cross-area continuity. Mostly net-new systems. | ~10+ slices |
| 7 | plan-10 | Large + cross-layer (engine + MCP + client-2d). Touches the 2026-05-23 batch-close fallout most heavily. | ~10+ slices |

## How to recognize the smell going forward

The premature-close pattern leaves consistent fingerprints:

- Children closed within a single short window (15–60s) on `2026-05-23` — strong batch-close signal.
- `stateReason: NOT_PLANNED` rather than `COMPLETED`.
- Closing comment is the boilerplate "Consolidating into #epic …" with no linked PR.
- The gating test referenced in the issue body still has a `pytest.skip("GAP: ... Tracked by #<that-issue>")` block.

Verify by running, per epic:
```bash
gh issue view <epic> --json title,body
# For each listed child:
gh issue view <child> --json state,stateReason,closedAt,timelineItems
rg "Tracked by #<child>" dnd-engine/tests/srd/
```

If the skip still cites the closed issue and no commit references the child, treat as premature.

## Status of this meta plan

Living doc. Update verdicts as restructures land. Each finished plan moves to **REAL** in the table above.
