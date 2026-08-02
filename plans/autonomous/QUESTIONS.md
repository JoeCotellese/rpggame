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
