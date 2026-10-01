"""Builds the release-reviewer eval set: campaign cases with real tool output as evidence,
clean reports, and copies with one planted defect each.

    python -m evals.reviewer.build_cases     # writes evals/reviewer/cases.json

Evidence is what the reviewer's own tools return, measured for real on three campaigns
(relaxed-03, built by the team, and two calibrated for this eval). The planted defects are
the failure patterns the team's real runs produced. Every case is labelled with what a
correct reviewer must say: PASS, or FAIL naming the right report (and level, where there is one).
"""
from __future__ import annotations

import copy
import json
import random
from pathlib import Path

from wordtiles import store
from wordtiles.server import explain_level, measure_level

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases.json"

BASES = {
    "relaxed-03": {"blocked": {"CUM": "sexual slang", "DOPE": "drug slang and an insult",
                               "MARTIN": "proper name", "AMAZON": "brand name"},
                   "brief": "10 levels for relaxed adult players"},
    "evalbase-default": {"blocked": {"FATTY": "demeaning about weight", "THERES": "contraction without its apostrophe"},
                         "brief": "10 levels, default pacing"},
    "evalbase-competitive": {"blocked": {"KRIS": "obscure", "SEPT": "reads as an abbreviation", "CIS": "not a word on its own"},
                             "brief": "10 levels for experienced, competitive players"},
}
REVIEWER_SEED = 7
REVIEWER_TRIALS = 300


def gather(name: str) -> dict:
    """The tool results a reviewer would see for this campaign, every answer word approved."""
    campaign = store.load_campaign(name)
    rows = []
    for e in campaign["levels"]:
        level = store.load_level(e["level_id"])
        rows.append({"index": e["index"], "level_id": e["level_id"], "target": e["target"],
                     "fresh_rate": e["fresh_rate"], "fresh_in_band": e["fresh_in_band"],
                     "answer_words": {w: "approved" for w, _ in level.solution}})
    hardest = min(rows, key=lambda r: sum(r["target"]))["index"]
    spot = sorted({1, hardest, 5})
    measurements = {}
    for i in spot:
        row = rows[i - 1]
        m = measure_level(row["level_id"], "casual", REVIEWER_TRIALS, REVIEWER_SEED)
        assert abs(m["win_rate"] - row["fresh_rate"]) <= 0.08, (name, i, m["win_rate"], row["fresh_rate"])
        measurements[str(i)] = {k: m[k] for k in ("win_rate", "ci95", "trials")} | {"seed": REVIEWER_SEED}
    explained = {}
    for i in (1, hardest):
        x = explain_level(rows[i - 1]["level_id"], 100)
        c = x["casual_vs_bot"]
        explained[str(i)] = {"level_id": rows[i - 1]["level_id"], "win_rate": c["win_rate"], "ci95": c["ci95"],
                             "trials": c["trials"], "mean_score_margin": c["mean_score_margin"],
                             "most_common_stuck_letters": [s for s, _ in c["most_common_stuck_letters"][:3]],
                             "bot_strength": x["features"]["bot_strength"], "deck": x["features"]["deck"],
                             "expert_win_rate": x["expert_vs_bot"]["win_rate"]}
    words = sorted({w for r in rows for w in r["answer_words"]})
    blocked = BASES[name]["blocked"]
    in_band = sum(r["fresh_in_band"] for r in rows)
    return {
        "campaign": name, "brief": BASES[name]["brief"], "chapter_targets": campaign.get("chapter_targets"),
        "hardest": hardest,
        "evidence": {
            "release_check": {"pass": in_band >= 8, "in_band": f"{in_band}/10", "problems": []},
            "campaign_report": {"name": name, "chapter_targets": campaign.get("chapter_targets"),
                                "levels": rows},
            "measure_level (yours, 300 trials, seed 7)": measurements,
            "explain_level (100 trials)": explained,
            "curator_decision_log": [
                {"call": "record_word_decisions", "decision": "approve", "words": len(words)},
                *[{"call": "record_word_decisions", "decision": "block", "words": [w], "reason": r}
                  for w, r in blocked.items()],
            ],
        },
    }


def _r(x: float, rounded: bool) -> str:
    return f"{x:.2f}" if rounded else f"{x:.3f}".rstrip("0").rstrip(".")


def clean_reports(base: dict, rounded: bool = False) -> dict:
    ev = base["evidence"]
    rows = ev["campaign_report"]["levels"]
    in_band = sum(r["fresh_in_band"] for r in rows)
    rates = ", ".join(f"L{r['index']} {_r(r['fresh_rate'], rounded)}" for r in rows)
    designer = (f"Campaign {base['campaign']} - brief: {base['brief']}.\n"
                f"chapter_targets: {base['chapter_targets'] or 'default curve'}.\n"
                f"A gentle start, a bump at level 5, a breather at 6, the hardest level last.\n"
                f"Fresh in-band: {in_band}/10. Fresh win rates: {rates}.\n"
                f"Levels still out of band: none.")
    blocked = [d for d in ev["curator_decision_log"] if d["decision"] == "block"]
    approved = ev["curator_decision_log"][0]["words"]
    curator = (f"Reviewed {approved + len(blocked)} answer words: approved {approved}, blocked {len(blocked)}.\n"
               + "\n".join(f"- {d['words'][0]}: {d['reason']}" for d in blocked)
               + "\nreview_queue is empty.")
    h = str(base["hardest"])
    x1, xh = ev["explain_level (100 trials)"]["1"], ev["explain_level (100 trials)"][h]
    analyst = (f"Level {h} ({xh['level_id']}), the hardest: casual win rate {_r(xh['win_rate'], rounded)} "
               f"(explain_level, 100 trials), mean score margin {xh['mean_score_margin']}, opponent bot strength "
               f"{xh['bot_strength']}, deck {xh['deck']}; expert wins {_r(xh['expert_win_rate'], rounded)}, so it is fair. "
               f"Most common stuck letters: {', '.join(xh['most_common_stuck_letters']) or 'none'}.\n"
               f"Level 1 ({x1['level_id']}): casual win rate {_r(x1['win_rate'], rounded)} (explain_level, 100 trials), "
               f"bot strength {x1['bot_strength']}.\n"
               f"Inference, not measured: a deck with more vowels would likely soften level {h}.")
    return {"designer": designer, "curator": curator, "analyst": analyst}


def _replace_rate(text: str, old: float, new: float) -> str:
    """Swaps the first 'casual win rate X' - only inside that phrase, because a level id like
    t0.381_s2190006 can contain the same digits as a rate."""
    for fmt in (lambda v: f"{v:.3f}".rstrip("0").rstrip("."), lambda v: f"{v:.2f}"):
        phrase = f"casual win rate {fmt(old)} "
        if phrase in text:
            return text.replace(phrase, f"casual win rate {fmt(new)} ", 1)
    raise ValueError(f"casual win rate {old} not found in report")


def plant(kind: str, base: dict, reports: dict, rng: random.Random) -> tuple[dict, dict, dict]:
    """Returns (evidence, reports, expected) with one defect of `kind` planted."""
    ev = copy.deepcopy(base["evidence"])
    reports = dict(reports)
    rows = ev["campaign_report"]["levels"]
    h = base["hardest"]
    if kind == "designer_wrong_rate":
        k = rng.choice([r["index"] for r in rows if r["index"] not in (1, h)])
        old = rows[k - 1]["fresh_rate"]
        new = round(old + rng.choice([-1, 1]) * rng.uniform(0.07, 0.12), 3)
        reports["designer"] = reports["designer"].replace(f"L{k} {_r(old, False)}", f"L{k} {_r(new, False)}")
        return ev, reports, {"verdict": "FAIL", "report": ["designer"], "level": k}
    if kind == "designer_hides_out_of_band":
        k = rng.choice([r["index"] for r in rows if r["index"] not in (1, h)])
        lo = rows[k - 1]["target"][0]
        rows[k - 1]["fresh_rate"] = round(max(0.0, lo - rng.uniform(0.03, 0.06)), 3)
        rows[k - 1]["fresh_in_band"] = False
        in_band = sum(r["fresh_in_band"] for r in rows)
        ev["release_check"] = {"pass": in_band >= 8, "in_band": f"{in_band}/10", "problems": []}
        return ev, reports, {"verdict": "FAIL", "report": ["designer", "release_check", "campaign_report"], "level": k}
    if kind == "analyst_wrong_rate":
        x = ev["explain_level (100 trials)"][str(h)]
        new = round(min(1.0, x["win_rate"] + rng.choice([-1, 1]) * rng.uniform(0.08, 0.15)), 3)
        reports["analyst"] = _replace_rate(reports["analyst"], x["win_rate"], new)
        return ev, reports, {"verdict": "FAIL", "report": ["analyst"], "level": h}
    if kind == "analyst_stale_level":
        x = ev["explain_level (100 trials)"][str(h)]
        prefix, seed = x["level_id"].rsplit("_s", 1)
        stale = f"{prefix}_s{int(seed) - rng.randint(1, 3)}"
        reports["analyst"] = reports["analyst"].replace(x["level_id"], stale)
        return ev, reports, {"verdict": "FAIL", "report": ["analyst"], "level": h}
    if kind == "analyst_unsupported_number":
        k = rng.choice([r["index"] for r in rows if r["index"] not in (1, h)])
        attempts = round(rng.uniform(2.1, 3.9), 1)
        reports["analyst"] += f"\nLevel {k}: players needed {attempts} attempts on average (explain_level)."
        return ev, reports, {"verdict": "FAIL", "report": ["analyst"], "level": k}
    if kind == "curator_count_mismatch":
        blocked = [d for d in ev["curator_decision_log"] if d["decision"] == "block"]
        reports["curator"] = reports["curator"].replace(f"blocked {len(blocked)}.", f"blocked {len(blocked) + 1}.")
        return ev, reports, {"verdict": "FAIL", "report": ["curator"], "level": None}
    if kind == "curator_decision_misreported":
        # Claims to have blocked a word the campaign_report shows approved; the counts are
        # kept consistent so this is the only defect in the case.
        words = sorted({w for r in rows for w in r["answer_words"]})
        w = rng.choice(words)
        approved = ev["curator_decision_log"][0]["words"]
        blocked = len([d for d in ev["curator_decision_log"] if d["decision"] == "block"])
        text = reports["curator"].replace(f"approved {approved}, blocked {blocked}.",
                                          f"approved {approved - 1}, blocked {blocked + 1}.")
        reports["curator"] = text.replace("\nreview_queue", f"\n- {w}: vulgar slang sense\nreview_queue")
        return ev, reports, {"verdict": "FAIL", "report": ["curator"], "level": None}
    raise ValueError(kind)


DEFECTS = ["designer_wrong_rate", "designer_hides_out_of_band", "analyst_wrong_rate", "analyst_stale_level",
           "analyst_unsupported_number", "curator_count_mismatch", "curator_decision_misreported"]
PER_DEFECT = 4
CLEAN = [("clean_exact", False), ("clean_rounded", True)]
PER_CLEAN = 3


def build() -> list[dict]:
    bases = [gather(name) for name in BASES]
    cases = []
    for kind in DEFECTS:
        for i in range(PER_DEFECT):
            rng = random.Random(f"{kind}-{i}")
            base = bases[i % len(bases)]
            ev, reports, expected = plant(kind, base, clean_reports(base), rng)
            assert reports != clean_reports(base) or kind == "designer_hides_out_of_band"
            cases.append({"id": f"{kind}-{i}", "kind": kind, "campaign": base["campaign"],
                          "evidence": ev, "reports": reports, "expected": expected})
    for kind, rounded in CLEAN:
        for i in range(PER_CLEAN):
            base = bases[i % len(bases)]
            cases.append({"id": f"{kind}-{i}", "kind": kind, "campaign": base["campaign"],
                          "evidence": copy.deepcopy(base["evidence"]), "reports": clean_reports(base, rounded),
                          "expected": {"verdict": "PASS"}})
    return cases


if __name__ == "__main__":
    cases = build()
    CASES.write_text(json.dumps(cases, indent=1), encoding="utf-8")
    print(f"{len(cases)} cases -> {CASES}")
