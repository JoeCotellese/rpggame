# Autonomous Build Loop — Operating Manual

This directory is the durable state for an unattended overnight build loop. The
agent running the loop has no reliable memory across wake-ups: **every wake-up
begins by reading this directory, never by recalling prior context.**

## Prime directives

1. **Read state before acting.** Start each wake-up with `ROADMAP.md` (what is
   next) and `PROGRESS.md` (what just happened). Trust the files over memory.
2. **Never block.** There is nobody to answer a question. A genuine fork goes in
   `QUESTIONS.md`, the issue is marked `blocked`, and the loop moves to the next
   issue.
3. **One stage per wake-up.** A context reset then costs at most one stage.
4. **Additive only.** See "Strangler constraint" below. No existing caller may
   change behaviour.
5. **Push after every issue.** The container is ephemeral; unpushed work is lost
   work.
6. **Never `--no-verify`.** Never weaken, skip, or delete a test to make a gate
   pass.

## Strangler constraint (non-negotiable)

All new work is **purely additive**. The new session API is built *alongside*
`GameState`, not in place of it.

- `client-terminal` and `client-2d` must remain byte-for-byte unmodified in
  behaviour. Both must still boot and play at the end of every issue.
- No existing public method may change signature or semantics.
- No existing test may be modified to accommodate new code.

If an issue cannot be completed additively, it is `blocked`, not forced.

## Issue lifecycle

Each issue advances through five stages. One stage per wake-up.

| Stage | Work | Gate to exit |
|---|---|---|
| `SPEC` | Write `issues/<id>.md`: user story, acceptance criteria, technical design, UI design | Definition of Ready fully satisfied |
| `BUILD` | TDD implementation | New tests pass; failures ≤ pinned baseline; both clients still boot |
| `PLAYTEST` | Execute every AC against real gameplay; record evidence | Every AC verified with recorded evidence |
| `REVIEW` | Adversarial pass against the spec | Zero unresolved **critical** findings |
| `SHIP` | Commit, push, update `ROADMAP.md` | Pushed to the working branch |

## Definition of Ready

An issue may not enter `BUILD` until all are true:

- [ ] User story: *As a &lt;role&gt;, I want &lt;capability&gt;, so that &lt;value&gt;.*
- [ ] Acceptance criteria written as numbered `AC-n` in Given/When/Then form
- [ ] Every `AC-n` names its verification method (unit test, integration test,
      facade playtest script, or `GameSession` regression playtest)
- [ ] Technical design: files touched, new types, exact API signatures
- [ ] UI design: what the player sees and does — or an explicit statement that
      the issue has no player-visible surface, plus the client-facing contract
- [ ] Dependencies listed and satisfied
- [ ] Rollback plan: exactly how to revert this issue cleanly

## Definition of Done

An issue may not be marked `done` until all are true:

- [ ] Every `AC-n` verified by its named method, with evidence recorded in the
      issue file (command run + observed output)
- [ ] New tests pass; total failure count ≤ the baseline in `BASELINE.md`
- [ ] Regression playtest passes: game boots and plays the smoke scenario
- [ ] Both clients still start
- [ ] Adversarial review complete, zero unresolved critical findings
- [ ] Non-critical findings recorded in `FOLLOWUPS.md`
- [ ] Committed and pushed
- [ ] `ROADMAP.md` status updated

## Definition of Critical

Only **critical** findings from adversarial review get fixed. Everything else is
logged to `FOLLOWUPS.md` and left alone.

**Critical** — fix before shipping the issue:

- Crash or unhandled exception on a normal player path
- Incorrect D&D rules adjudication (wrong arithmetic, wrong DC, wrong action
  economy, wrong advantage/disadvantage)
- Data loss or corruption (save files, character vault)
- Regression: a previously passing test or previously verified AC now fails
- The issue's own acceptance criteria are not actually met
- A strangler violation: existing caller behaviour changed

**Not critical** — log to `FOLLOWUPS.md`, do not fix:

- Naming, style, formatting, comment wording
- Performance that is not user-perceptible
- Refactoring opportunities, duplication
- Missing tests for edge cases outside the issue's acceptance criteria
- Pre-existing problems the issue did not introduce

## Failure policy

When adversarial review finds a critical issue that cannot be safely fixed:

1. Revert that issue's commits so the branch stays green.
2. Write it up in `QUESTIONS.md` with full context and what was tried.
3. Mark the issue `reverted` in `ROADMAP.md`.
4. Move to the next issue. Do not stop the loop.

## Verification approach

Because the work is additive, the new API is not yet wired into either client.
Verification therefore has two halves, and **both** are required:

1. **Forward verification** — a playtest script drives the *new session API*
   through a real seeded scenario (load dungeon, move, trigger combat, take a
   turn) and asserts on real engine outcomes. This is genuine gameplay, just
   entered through the new door.
2. **Regression verification** — a playtest drives `GameSession` exactly as the
   2D client does, proving the existing game is untouched.

Playtests use a fixed seed via the dev `set_seed()` surface so runs are
reproducible.

## Environment recovery

If the container was recreated, restore the toolchain before any other work:

```bash
uv sync --all-extras
uv run python scripts/seed_test_vault.py     # headless client needs a non-empty vault
```

Tests must be run **per package, from that package's directory** — running from
the repo root produces 57 collection errors because each package sets its own
`pythonpath`.

```bash
cd dnd-engine      && uv run pytest -q --no-cov
cd client-2d       && uv run pytest -q --no-cov
cd client-terminal && uv run pytest -q --no-cov
```

## Files

| File | Purpose |
|---|---|
| `ROADMAP.md` | Ordered backlog with per-issue status. The loop's work queue. |
| `BASELINE.md` | Pinned environment facts and test baseline. |
| `issues/<id>.md` | Full spec and recorded verification evidence per issue. |
| `PROGRESS.md` | Append-only log, one entry per wake-up. |
| `QUESTIONS.md` | Blocked items needing Joe. Read this first in the morning. |
| `FOLLOWUPS.md` | Non-critical findings deliberately not fixed. |
