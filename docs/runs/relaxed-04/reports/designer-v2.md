DESIGNER REPORT (revised) - campaign relaxed-04. All numbers below come from campaign_report output; nothing was regenerated or recalibrated for this revision.

STATUS CHANGE: Levels 4, 8, 9 and 10 were regenerated after my original build (blocked-word fixes on all four, plus a difficulty retry on level 9 per the task note). This report replaces v1, which described the earlier level_ids and rates. Note: the current report also shows regenerations on levels 8 and 10 that include difficulty 1, and level 1 shows difficulty 1; those counts are quoted exactly below.

CHAPTER TARGETS (10 casual win rates): 0.92, 0.85, 0.78, 0.70, 0.50, 0.82, 0.70, 0.60, 0.48, 0.40.
Reasoning (unchanged): relaxed brief, so the curve starts high (0.92) and the hardest level stays above 0.35 (0.40 finale). Build-up 0.92 -> 0.70 over levels 1-4; spike at level 5 (0.50); breather at level 6 (0.82); second build 0.70 -> 0.48 over levels 7-9; chapter's hardest level last at 0.40.

PER LEVEL (current level_id | target band | fresh_rate over fresh_trials | regenerations):
1 | t0.000_s1100003 | 0.82-1.00 | 0.885 / 200 | blocked_word 0, difficulty 1
2 | t0.000_s110002 | 0.75-0.95 | 0.905 / 200 | none
3 | t0.067_s120000 | 0.68-0.88 | 0.79 / 200 | none
4 | t0.143_s1130003 | 0.60-0.80 | 0.73 / 200 | blocked_word 1, difficulty 0
5 | t0.333_s140000 | 0.40-0.60 | 0.48 / 200 | none
6 | t0.000_s150001 | 0.72-0.92 | 0.825 / 200 | none
7 | t0.143_s160000 | 0.60-0.80 | 0.72 / 200 | none
8 | t0.238_s2170006 | 0.50-0.70 | 0.70 / 200 | blocked_word 1, difficulty 1
9 | t0.352_s2180006 | 0.38-0.58 | 0.475 / 200 | blocked_word 1, difficulty 1
10 | t0.504_s2190008 | 0.30-0.50 | 0.31 / 200 | blocked_word 1, difficulty 1

Regeneration totals: blocked_word 4 (levels 4, 8, 9, 10); difficulty 4 (levels 1, 8, 9, 10). No level exceeds the two-difficulty-retry limit; each has used at most 1.

FRESH IN-BAND: 10 of 10 levels report fresh_in_band true.

EDGE FLAGS (as measured, not smoothed):
- Level 10: fresh 0.31 vs floor 0.30, only 0.01 above the lower edge. With 200 trials this is a thin margin and could fall out of band on re-measurement.
- Level 8: fresh 0.70 equals the band ceiling 0.70 exactly (calibration 0.66). It is in band as reported, but at the very edge.
- Level 5 (0.48) and level 9 (0.475) sit mid-band. Level 2 (0.905 vs ceiling 0.95), level 3 (0.79 vs ceiling 0.88) and level 1 (0.885 vs floor 0.82) have comfortable margins. Levels 4 (0.73), 6 (0.825) and 7 (0.72) are well inside their bands.
- Calibration vs fresh differences worth noting: level 1 fresh 0.885 vs calibration 0.933; level 5 fresh 0.48 vs calibration 0.555; level 10 fresh 0.31 vs calibration 0.392.

Levels still out of band: none.