# relaxed-05 — PASS on the first gate run

The run that checks relaxed-04's two fixes in a real session: stale reports are now caught
by a fact the tools report (`campaign_changed_after_report`) and refreshed before the gate,
and the analyst reads rates with their intervals (`explain_level` now 300 trials). Same brief
(10 levels, relaxed adults), orchestrator on Sonnet. Files in `relaxed-05/`.

## What happened

| time | who | what |
|---|---|---|
| 13:31:36 | designer | calibrated the campaign, regenerated level 1 for difficulty, stored report **v1** |
| 13:32:05 | curator | blocked BOOTY ("slang sense players would snigger at"), approved the rest |
| 13:32:19 | orchestrator | regenerated level 10 for the blocked word (`reason: blocked_word`) |
| 13:32:34 | curator | approved level 10's five new words, report v2 |
| 13:33:07 | analyst | report v1, every rate with its 95% interval |
| 13:33:19 | orchestrator | **step 5:** read all three reports - the designer's was written before level 10 changed |
| 13:33:34 | designer | re-issued its report from the current `campaign_report` (**v2**) |
| 13:33:48 | reviewer | **PASS**: 10/10 in band, levels 1, 6, 10 re-measured within 0.05, the analyst's four `explain_level` figures reproduced |

The file times are the proof: designer v1 13:31:36, campaign last saved 13:32:19, curator v2
13:32:34, analyst 13:33:07 - only the designer's report predated the change, and only it was
refreshed. In relaxed-04 the same situation cost a failed gate run; here it never reached
the gate.

PASS covers designer v2 `76671b1d6bad4b1e`, curator v2 `9f8d1fcf0d1d3b91`, analyst v1
`c986eb752e3b1748`.

## The analyst, reading intervals

It quoted every rate with its interval (e.g. level 10: 95% CI 0.395-0.507, 300 trials) and
declined to rank levels 5, 8, 9 and 10 against each other because their intervals overlap -
the behaviour relaxed-04's "reproducible is not right" finding asked for. It also flagged its
own weak spot: the expert's 10/10 is a thin fairness check.

## Open, from this run

- The audit log's 300-character result preview is too short to show `read_report`'s staleness
  field; the file times above had to be read instead.
- `explain_level` runs the expert only 10 times - enough to spot an unfair level, not to measure one.
