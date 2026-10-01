---
name: build-campaign
description: Builds a release-ready word-tile level campaign end to end with the level team - design, word review, regeneration, playtest analysis and a release gate. Use when asked to make, build or ship a campaign or a set of levels for the word-tile game.
when_to_use: "make me 30 levels", "build a campaign for older players", "ship a new chapter", "generate levels and check them"
---

# Build a campaign

Runs the four agents in order. The designer, curator and analyst store their reports
with `submit_report`; the reviewer reads them itself with `read_report`. You route work
between agents, but you never carry a report to the gate and never edit one: whoever
relays a report controls what the gate sees.

## Steps

1. **Design.** Delegate to `level-designer` with the user's brief, a campaign name
   (letters, digits, `-`, `_`) and the level count (default 10). Keep its chosen
   `chapter_targets` and its fresh in-band count.

2. **Word review.** Delegate to `word-curator` with the campaign name.

3. **Regenerate blocked levels.** Call `campaign_report`. For every level with an answer
   word whose status is `blocked`, call `regenerate_level` with `reason` "blocked_word".
   These don't count against the designer's difficulty limit. Then send `word-curator` back
   to review the new words. Repeat until no answer word is blocked or unreviewed, at most
   three rounds; if it still isn't clean, stop and report which levels are stuck.

4. **Playtest analysis.** Delegate to `playtest-analyst` with the campaign name.

5. **Refresh stale reports.** Call `read_report` for the designer, the curator and the
   analyst. A report with `campaign_changed_after_report: true` was written before a level
   was regenerated, so its numbers may describe levels the campaign no longer holds (the
   designer's always is after a blocked word: it reports in step 1, step 3 regenerates).
   Send each stale one back to its author to re-issue from the current `campaign_report`
   with `submit_report`, then check again. Go to the gate only when none is stale.

6. **Release gate.** Delegate to `release-reviewer` with the campaign name only - not
   the reports, not a summary of them. It reads the stored reports itself.
   - FAIL with fixable problems (an out-of-band level, an unreviewed word): fix it with
     the step that owns it, repeat step 5 (a fix that regenerates a level makes reports
     stale again), then run the reviewer again. At most two gate runs.
   - FAIL because a report is wrong or unverifiable: send it back to its author to fix and
     `submit_report` again. Don't rewrite another agent's report yourself.
   - FAIL that you cannot fix: stop and report it. Never present a failed campaign as done.

7. **Report** to the user, in this order:
   - verdict (PASS/FAIL), the fresh in-band count, and the report versions and sha256
     fingerprints the reviewer passed
   - the chapter targets and why (from the designer)
   - words blocked, with reasons
   - the analyst's notes on the hardest and out-of-band levels
   - a rendered example: call `render_level` on the hardest level and give the path

## Ground rules
- Numbers come from tools, never from an agent's memory. If two reports disagree, the
  reviewer's measurement wins.
- Don't skip the word review or the gate, even for a "quick test" campaign: an unreviewed
  answer word is exactly how a slur reaches a player.
