# [plan-04] 0 HP, Death Saves & Hit-Point Model — finish the dying state machine

**Status: COMPLETE.** All 11 children merged; epic #533 closed. The HP/dying state machine is now authoritative: 0-HP applies Unconscious, death-save counters reset on Stable, Stable→damage resumes saves, 1d4-hour rest grants 1 HP, crit-at-0 adds two failures, massive-damage overflow triggers instant death, Bloodied flag surfaced, Temp HP buffers/no-stacks/expires on long rest and is not healing, CON-mod increases retroactively bump HP max, fixed-HP level-up is selectable.

## Defect

The hit-point model and dying state machine are partially implemented and inconsistent. When a character drops to 0 HP, Unconscious is not applied automatically (so a 0-HP character can still appear "healthy" in status displays). Death-save counters do not reset when a character becomes Stable; damage to a Stable creature does not clear stabilized and resume saves; a Stable creature does not regain 1 HP after 1d4 hours. Critical hits at 0 HP add only one death-save failure (SRD requires two). Massive damage instant-death (damage overflow from positive HP exceeding HP max) is not applied. The Bloodied state (≤ ½ HP, data-surfacable) does not exist. Temporary Hit Points have no buffer model — current code stacks rather than no-stacks, no long-rest expiry, and Temp HP is incorrectly counted as healing in places. CON modifier increases do not retroactively recalculate HP max. Fixed HP per class on level-up is not an option (only roll). These are one defect: **HP state and dying-state transitions are not authoritative — the engine treats them as derived display rather than a state machine.**

## Children

- #334 — Bug: Character at 0 HP still shows 'healthy' status
- #404 — Level-up: support fixed HP per class as alternative to rolling
- #407 — Constitution modifier increase does not retroactively recalculate HP maximum
- #448 — Apply massive-damage instant death on damage overflow from positive HP
- #452 — Apply Unconscious condition when a character drops to 0 HP
- #454 — Reset death-save counters to zero when a character becomes Stable
- #457 — Critical-hit damage at 0 HP must add two death-save failures, not one
- #458 — Damage to a Stable creature must clear stabilized flag and resume death saves
- #460 — Stable creature regains 1 HP after 1d4 hours of rest
- #482 — Implement Temporary Hit Points (buffer, no-stack, long-rest expiry, not-healing)
- #488 — Implement Bloodied state (≤ ½ HP; data-surfacable flag, no inherent effect)

## Fix sequence

1. **HP state machine.** `DyingState` enum (Alive / Dying / Stable / Dead). Transitions are pure functions of `current_hp`, death-save counters, and damage events.
2. **Drop-to-0 transition (#452).** When `current_hp` reaches 0 from positive, set `DyingState.Dying` and apply Unconscious. Status displays must read this state, fixing #334.
3. **Massive damage (#448).** If `damage_overflow >= max_hp` while transitioning from positive HP, set `DyingState.Dead` directly. Skip Dying.
4. **Stable transitions (#454, #458, #460).** Becoming Stable resets death-save counters. Damage clears Stable, returns to Dying, applies one death-save failure (or two if crit), resumes the cycle. After 1d4 hours of rest, Stable → 1 HP, Conscious.
5. **Crit-at-0 (#457).** Critical-hit damage while at 0 HP adds **two** failures (not one). Routed via plan-02's damage pipeline — the consumer is here.
6. **Temporary Hit Points (#482).** New `Creature.temp_hp` field. Incoming damage consumes temp HP first; no-stacking rule (the larger value wins on overlap); cleared on long rest; never counted by `heal()`.
7. **CON mod recalc (#407).** Listening to ability-score change events, recompute `max_hp = sum(level_hp) + CON_mod * level`. Apply to current HP only as a delta (don't fully heal).
8. **Bloodied flag (#488).** Pure derived property: `is_bloodied = current_hp <= max_hp // 2`. Surfaced for UI / triggers but applies no mechanical effect by itself.
9. **Fixed HP per class on level-up (#404).** Add player choice at level-up: roll or take the SRD's fixed value (e.g., 5 for d8). New `LevelUpHpPolicy` enum.

## Test matrix

| Scenario | Pre-HP | Damage | Post-HP | Dying state | Failures added | Notes |
|---|---|---|---|---|---|---|
| Healthy hit | 20 | 5 | 15 | Alive | 0 | — |
| Drop to 0 | 5 | 5 | 0 | Dying + Unconscious | 0 | #452, #334 |
| Drop to 0 with massive damage | 5 | 100 (overflow ≥ max) | 0 | Dead | n/a | #448 |
| Death save crit (attacker rolls 20 in melee within 5 ft) | 0 | crit damage | 0 | Dying | 2 | #457 |
| Stabilize (DC 10 Medicine or natural 20) | 0 | 0 | 0 | Stable | resets to 0 | #454 |
| Damage to Stable | 0 | 1 | 0 | Dying | 1 (or 2 if crit) | #458 |
| 1d4-hour rest while Stable | 0 | 0 | 1 | Alive | n/a | #460 |
| Temp HP intercepts | 10 + 5 temp | 8 | 7 + 0 temp | Alive | n/a | #482 |
| Temp HP no-stack | 10 + 5 temp, gain 3 temp | unchanged | 10 + 5 temp | Alive | n/a | #482 |
| Long rest expires temp HP | 10 + 5 temp | rest | 10 + 0 temp | Alive | n/a | #482 |
| CON mod +1 at level-up | 24 max / 24 cur (lvl 4) | bump | 28 max / 28 cur | Alive | n/a | #407 |
| Bloodied flag | 8 / 20 max | n/a | n/a | Alive + Bloodied | n/a | #488 |
| Fixed-HP level-up | n/a | n/a | +5 + CON | n/a | n/a | #404 |

Parametrized pytest in `tests/srd/playing_the_game/test_dying_state.py` and `test_temp_hp.py`.

## Out of scope

- The damage-type pipeline that produces the damage events consumed here — see plan-02 (the consumer-side row for `#457` and `#448` is here; the producer is there).
- Knockout-as-action (a melee attacker chooses non-lethal damage → 1 HP + Unconscious) — see plan-01 (#485).
- Healing primitives and per-spell healing math (already audited and largely conforming) — out of scope; only the Temp-HP-isn't-healing invariant lives here.
- Long-rest and short-rest scheduling at the campaign/world layer — see plan-09.
