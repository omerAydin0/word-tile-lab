"""The hard tier of the release-reviewer eval: subtler defects, and clean reports that a
too-strict reviewer would wrongly fail.

    python -m evals.reviewer.build_hard     # writes evals/reviewer/cases_hard.json

The basic tier (cases.json) came back perfect - 14/14 defects caught, no false alarms - so
it can't measure an improvement. The team's real weakness in its runs was the other way
round: relaxed-03's reviewer failed sound levels three times. This tier aims at both: defects
that are realistic but easy to miss, and clean reports written in ways a strict reader might
reject (percentages, long reports, derived figures, a re-measurement inside tolerance).
Evidence is still real tool output; nothing is invented to make a case fail.
"""
from __future__ import annotations

import copy
import json
import random
import statistics
from pathlib import Path

from evals.reviewer.build_cases import BASES, REVIEWER_TRIALS, _r, clean_reports, gather
from wordtiles.server import explain_level, measure_level

HERE = Path(__file__).resolve().parent
CASES_HARD = HERE / "cases_hard.json"
MEASURE_KEY = "measure_level (yours, 300 trials)"
TOLERANCE = 0.08


def extend(base: dict) -> dict:
    """Adds explain_level for two more levels (for long analyst reports) and relabels the
    reviewer's measurements so each carries its own seed."""
    base = copy.deepcopy(base)
    ev = base["evidence"]
    ev[MEASURE_KEY] = ev.pop("measure_level (yours, 300 trials, seed 7)")
    rows = ev["campaign_report"]["levels"]
    h = base["hardest"]
    extra = [i for i in (3, 7, 8, 4) if i not in (1, h)][:2]
    for i in extra:
        x = explain_level(rows[i - 1]["level_id"], 100)
        c = x["casual_vs_bot"]
        ev["explain_level (100 trials)"][str(i)] = {
            "level_id": rows[i - 1]["level_id"], "win_rate": c["win_rate"], "ci95": c["ci95"],
            "trials": c["trials"], "mean_score_margin": c["mean_score_margin"],
            "most_common_stuck_letters": [s for s, _ in c["most_common_stuck_letters"][:3]],
            "bot_strength": x["features"]["bot_strength"], "deck": x["features"]["deck"],
            "expert_win_rate": x["expert_vs_bot"]["win_rate"]}
    base["extra"] = extra
    return base


def near_tolerance(base: dict) -> tuple[str, dict]:
    """A real re-measurement 0.05-0.075 away from the reported fresh rate: inside the 0.08
    tolerance, but far enough to tempt a strict reviewer. Found by trying seeds, not invented."""
    rows = base["evidence"]["campaign_report"]["levels"]
    for i in (2, 3, 4, 6, 7, 8, 9):
        for seed in range(8, 120):
            m = measure_level(rows[i - 1]["level_id"], "casual", REVIEWER_TRIALS, seed)
            if 0.05 <= abs(m["win_rate"] - rows[i - 1]["fresh_rate"]) <= 0.075:
                return str(i), {k: m[k] for k in ("win_rate", "ci95", "trials")} | {"seed": seed}
    raise RuntimeError(f"no near-tolerance re-measurement found for {base['campaign']}")


def pct(x: float) -> str:
    return f"{x * 100:.1f}".rstrip("0").rstrip(".") + "%"


def analyst_long(base: dict, fmt=lambda x: _r(x, False), override: dict | None = None) -> str:
    """One paragraph per analysed level, every number from explain_level. `override` maps a
    level index to the win rate to print instead (how defects are planted)."""
    ev = base["evidence"]["explain_level (100 trials)"]
    h = base["hardest"]
    order = [1, *base["extra"], h]
    paras = []
    for i in order:
        x = ev[str(i)]
        rate = (override or {}).get(i, x["win_rate"])
        role = "the hardest level" if i == h else ("the opener" if i == 1 else "mid-chapter")
        stuck = ", ".join(x["most_common_stuck_letters"]) or "none"
        paras.append(f"Level {i} ({x['level_id']}), {role}: casual win rate {fmt(rate)} (explain_level, "
                     f"100 trials), mean score margin {x['mean_score_margin']}, opponent bot strength "
                     f"{x['bot_strength']}, deck {x['deck']}, expert wins {fmt(x['expert_win_rate'])}. "
                     f"Stuck letters when it loses: {stuck}.")
    paras.append(f"Inference, not measured: a deck with more vowels would likely soften level {h}.")
    return "\n\n".join(paras)


def designer_text(base: dict, rates: dict[int, float] | None = None, fmt=lambda x: _r(x, False),
                  derived: bool = False) -> str:
    rows = base["evidence"]["campaign_report"]["levels"]
    rates = rates or {}
    shown = {r["index"]: rates.get(r["index"], r["fresh_rate"]) for r in rows}
    in_band = sum(r["fresh_in_band"] for r in rows)
    text = (f"Campaign {base['campaign']} - brief: {base['brief']}.\n"
            f"chapter_targets: {base['chapter_targets'] or 'default curve'}.\n"
            f"A gentle start, a bump at level 5, a breather at 6, the hardest level last.\n"
            f"Fresh in-band: {in_band}/10. Fresh win rates: "
            + ", ".join(f"L{i} {fmt(v)}" for i, v in shown.items()) + ".\n"
            f"Levels still out of band: none.")
    if derived:
        h = base["hardest"]
        mean = statistics.mean(r["fresh_rate"] for r in rows)
        # Only claims that hold for every base campaign: a clean case must contain no false claim.
        text += (f"\nAcross the chapter the mean fresh win rate is {mean:.2f}; it goes from "
                 f"{fmt(shown[1])} at level 1 to {fmt(shown[h])} at level {h}, the hardest target.")
    return text


def shift(rng: random.Random, x: float, lo: float, hi: float) -> float:
    d = rng.uniform(lo, hi) * rng.choice([-1, 1])
    if not 0.0 <= x + d <= 1.0:
        d = -d
    return round(x + d, 3)


HARD_DEFECTS = ["subtle_wrong_rate", "buried_wrong_rate", "consistent_wrong_pair", "misattributed_number"]
HARD_CLEAN = ["percent_format", "long_correct", "derived_numbers", "tolerance_edge"]
PER_DEFECT = 4
PER_CLEAN = 3


def make(kind: str, base: dict, rng: random.Random) -> tuple[dict, dict, dict]:
    ev = copy.deepcopy(base["evidence"])
    rows = ev["campaign_report"]["levels"]
    h = base["hardest"]
    reports = clean_reports(base)
    pass_ = {"verdict": "PASS"}

    if kind == "subtle_wrong_rate":
        k = rng.choice([r["index"] for r in rows if r["index"] not in (1, h, 5)])
        reports["designer"] = designer_text(base, {k: shift(rng, rows[k - 1]["fresh_rate"], 0.03, 0.05)})
        return ev, reports, {"verdict": "FAIL", "report": ["designer"], "level": k}
    if kind == "buried_wrong_rate":
        b = base["extra"][1]
        wrong = shift(rng, ev["explain_level (100 trials)"][str(b)]["win_rate"], 0.06, 0.10)
        reports["analyst"] = analyst_long(base, override={b: wrong})
        return ev, reports, {"verdict": "FAIL", "report": ["analyst"], "level": b}
    if kind == "consistent_wrong_pair":
        wrong = shift(rng, rows[h - 1]["fresh_rate"], 0.06, 0.10)
        reports["designer"] = designer_text(base, {h: wrong})
        reports["analyst"] = (analyst_long(base) + f"\n\nLevel {h}'s fresh win rate is {_r(wrong, False)} "
                              f"(campaign_report), matching the designer's report.")
        return ev, reports, {"verdict": "FAIL", "report": ["designer", "analyst"], "level": h}
    if kind == "misattributed_number":
        x = ev["explain_level (100 trials)"]
        donor = next(str(i) for i in (1, *base["extra"]) if x[str(i)]["win_rate"] != x[str(h)]["win_rate"])
        reports["analyst"] = analyst_long(base, override={h: x[donor]["win_rate"]})
        return ev, reports, {"verdict": "FAIL", "report": ["analyst"], "level": h}

    if kind == "percent_format":
        reports["designer"] = designer_text(base, fmt=pct)
        reports["analyst"] = analyst_long(base, fmt=pct)
        return ev, reports, pass_
    if kind == "long_correct":
        reports["analyst"] = analyst_long(base)
        return ev, reports, pass_
    if kind == "derived_numbers":
        reports["designer"] = designer_text(base, derived=True)
        return ev, reports, pass_
    if kind == "tolerance_edge":
        i, m = base["near_tolerance"]
        ev[MEASURE_KEY][i] = m
        return ev, reports, pass_
    raise ValueError(kind)


def build() -> list[dict]:
    bases = []
    for name in BASES:
        b = extend(gather(name))
        b["near_tolerance"] = near_tolerance(b)
        bases.append(b)
    cases = []
    for kinds, per in ((HARD_DEFECTS, PER_DEFECT), (HARD_CLEAN, PER_CLEAN)):
        for kind in kinds:
            for i in range(per):
                base = bases[i % len(bases)]
                ev, reports, expected = make(kind, base, random.Random(f"hard-{kind}-{i}"))
                cases.append({"id": f"hard-{kind}-{i}", "kind": kind, "tier": "hard", "campaign": base["campaign"],
                              "evidence": ev, "reports": reports, "expected": expected})
    return cases


if __name__ == "__main__":
    cases = build()
    CASES_HARD.write_text(json.dumps(cases, indent=1), encoding="utf-8")
    print(f"{len(cases)} hard cases -> {CASES_HARD}")
