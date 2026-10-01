# relaxed-04 — PASS (second gate attempt)

The first run with stored, versioned reports and the audit hook. Same brief as relaxed-03
(10 levels, relaxed adult players); orchestrator on Sonnet. Everything the run produced is
in `relaxed-04/`: the campaign and its levels, all five report versions, the hardest
level's render, and the audit summary.

## What happened

| step | result |
|---|---|
| design | curve `[0.92, 0.85, 0.78, 0.70, 0.50, 0.82, 0.70, 0.60, 0.48, 0.40]`; designer report v1 |
| word review | blocked CRAP (vulgar), MICK (ethnic slur), STUD (sexual slang), LIN and PARKER (obscure / proper noun) |
| regenerations | levels 4, 8, 9, 10 for blocked words (by the orchestrator, `reason: blocked_word`); levels 1, 8, 9, 10 for difficulty (by the designer, `reason: difficulty`) - recorded separately in the campaign |
| gate 1 | **FAIL**: the designer's report predated the regenerations and contradicted `campaign_report` on levels 4, 8, 9, 10 |
| fix | the orchestrator **sent the report back to its author** instead of editing it; the designer submitted v2 |
| gate 2 | **PASS**, 10/10 in band; the reviewer re-measured levels 1, 7, 10 (300 trials) within 0.03 |

The PASS names exactly what it covers: designer v2 `d0dd14543cd8ef85`, curator v2
`32719135dec2d5f3`, analyst v1 `c5e6a1838dfb396e`.

## The audit trail

62 wordtiles tool calls, each tagged with the agent that made it (`audit-summary.txt`). The
reviewer read the stored reports 6 times, re-ran the analyst's `explain_level` figures 6
times and measured 8 times on its own - the gate checking, not trusting.

## Two findings this run surfaced

**1. The designer's report goes stale by design.** The designer reports in step 1; blocked-word
regenerations happen in step 3. Any blocked word makes the first gate fail on a stale report.
The skill should have the designer refresh its report after step 3.

**2. Reproducible is not the same as right.** Level 5: fresh rate 0.48, `explain_level` 0.63.
The analyst called it noise; re-measuring settled it:

| measurement | casual win rate |
|---|---|
| seed 0, 100 trials (what `explain_level` always uses) | 0.63 |
| seeds 1 / 2 / 3, 100 trials each | 0.54 / 0.46 / 0.45 |
| one 1,000-trial run | 0.49 (95% CI 0.46-0.52) |
| ten 300-trial runs, seeds 0-9 | 0.47-0.58, mean **0.52** |
| all 4,000 trials pooled | **≈ 0.51** |

The analyst was right that it was noise. But the reviewer "verified" 0.63 by reproducing it
exactly - it re-ran the same lucky sample. `explain_level` is deterministic so its figures can
be checked; with 100 trials that also means one fixed, noisy sample.

A correction while checking the fix: I first wrote the "true" rate as 0.49 from the single
1,000-trial run - itself a sample, low by chance. Ten 300-trial runs spread across seeds about as
much as independent trials should (sd 0.033 vs 0.029 expected), so the measurement is sound and
the pooled ≈ 0.51 is the better estimate. Seed 0 still reads 0.58 at 300 trials: more trials
halve the noise but don't remove unlucky samples. The real fix is reading rates with their
intervals and comparing intervals, not point values.

## Hardest level

Level 10 (`t0.504_s2190008`): fresh 0.31 in a 0.30-0.50 band, bot strength 0.453, expert 30/30.
The analyst traced most losses to a Z tile the casual player is left holding. Sample duel in
`relaxed-04/level-10.html`: bot 25, player 17.
