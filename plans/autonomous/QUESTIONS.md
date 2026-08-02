# Questions for Joe

Read this first. Items here blocked the loop or need human judgement.
Empty is good news.

---

## Open

### Q-001 — Real LLM provider path cannot be verified here
**Raised:** 2026-08-02 setup
**Issue:** P2-05
**Context:** Neither `ANTHROPIC_API_KEY` nor `OPENAI_API_KEY` is set in this
container and there is no `.env`. DM adjudication will be built against the
`LLMProvider` interface and verified with `llm/debug_provider.py`, which is
deterministic and proves the *wiring* and the engine-authoritative invariants —
but it cannot prove that a real model returns usable rulings.
**Needs from you:** run the adjudication flow once with a real key and judge
whether the proposed rulings feel like a competent DM. That is a taste
judgement the loop cannot make.
**Blocking:** no — P2-05 proceeds against the debug provider.

### Q-002 — The engine has no determinism seam, which breaks P1-04 as originally specified
**Raised:** 2026-08-02, P1-01 PLAYTEST
**Issue:** P1-04 (redesigned in `ROADMAP.md`, not blocked)
**Context:** P1-04 was specified as "drive the same seeded scenario twice and
assert identical outcomes". That cannot work today. Measured on a real crypt
playthrough:

| Seeding | Events | Distinct types |
|---|---|---|
| `DiceRoller(seed=…)` only | stable 9 | **5–6, varies** |
| + `random.seed(…)` | **9 to 46, varies** | 5–7 |
| + `PYTHONHASHSEED=0` | stable 9 | **5–6, varies** |

Cause: enemy AI target selection calls the global `random` module directly
(`systems/ai/targeting.py:80,156,162` and `core/game_state.py:5969`), bypassing
the seedable `DiceRoller`. Some variance survives even with that seeded and hash
randomisation pinned, so there is at least one more source.

**What the loop did:** redesigned P1-04 in `ROADMAP.md` to a *same-run*
comparison — drive one scenario through the facade and assert the facade's
reported `ActionResult` agrees with that same `GameState`'s actual internal
state. One run, no RNG dependence, and it tests the thing that actually matters.
Proceeding on that basis rather than blocking.

**Needs from you:** a call on whether the engine should gain a real determinism
seam (thread the `DiceRoller` through AI targeting instead of using global
`random`). That would make reproducible playtests and scripted scenarios possible
and is probably worth doing — but it changes existing behaviour, so it is
non-additive and outside tonight's strangler constraint.
**Blocking:** no.
