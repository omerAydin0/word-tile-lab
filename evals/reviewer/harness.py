"""Eval for the release-reviewer agent: does it catch planted defects in the team's reports,
and does it pass clean ones?

    python -m evals.reviewer.harness prompt --version v1 --split dev      # the exact prompt
    python -m evals.reviewer.harness run    --version v1 --split dev -k 3 # via `claude -p`
    python -m evals.reviewer.harness score  --version v1 --split dev      # every saved run

As with the curator eval, the agent's own instruction file is under test; the dry run
replaces its tool calls with the real tool results stored in cases.json. A defect counts
as caught only when the verdict is FAIL *and* a listed problem names the right report (and
level, where the defect has one): failing a campaign for the wrong reason isn't catching it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases.json"
CASES_HARD = HERE / "cases_hard.json"
VERSIONS = HERE / "versions"
RUNS = HERE / "runs"

DRY_RUN = """

## Dry run (evaluation)
This is a dry run: do not call any tools. Below are independent campaign cases. For each,
`evidence` holds exactly what your tools return for that campaign: `release_check`,
`campaign_report`, your own `measure_level` runs (300 trials, seed 7), `explain_level` for the
levels the analyst discusses (100 trials, as the analyst ran it), and the curator's
`record_word_decisions` log. `reports` holds what `read_report` returns for the designer,
curator and analyst. Judge every case on its own, exactly as you would in production.

Output ONLY a JSON array - no prose before or after - with one object per case:
{"case": "<case id>", "verdict": "PASS" or "FAIL",
 "problems": [{"report": "designer" | "curator" | "analyst" | "release_check",
               "level": <level index or null>, "issue": "<one sentence with the evidence>"}]}
Use an empty problems list for PASS.

Cases:
"""


def opaque(case_id: str) -> str:
    return "case-" + hashlib.sha256(case_id.encode()).hexdigest()[:8]


def load_cases(tier: str = "basic") -> list[dict]:
    return json.loads((CASES if tier == "basic" else CASES_HARD).read_text(encoding="utf-8"))


def run_glob(version: str, which: str, tier: str) -> str:
    # basic runs predate tiers and are named v1_dev_1.json; hard runs carry the tier.
    return f"{version}_{which}_[0-9]*.json" if tier == "basic" else f"{version}_{which}_{tier}_[0-9]*.json"


def split(cases: list[dict], which: str) -> list[dict]:
    """Stratified 50/50 by defect kind, ordered by a hash of the case id."""
    by_kind = defaultdict(list)
    for c in cases:
        by_kind[c["kind"]].append(c)
    chosen = []
    for kind_cases in by_kind.values():
        ordered = sorted(kind_cases, key=lambda c: hashlib.sha256(c["id"].encode()).hexdigest())
        chosen += ordered[0::2] if which == "dev" else ordered[1::2]
    return chosen


def instructions(version: str) -> str:
    text = (VERSIONS / f"{version}.md").read_text(encoding="utf-8")
    return re.sub(r"\A---\n.*?\n---\n", "", text, count=1, flags=re.S).strip()


def build_prompt(version: str, which: str, tier: str = "basic") -> str:
    cases = split(load_cases(tier), which)
    random.Random(f"{which}-order").shuffle(cases)  # never grouped by defect kind
    shown = [{"case": opaque(c["id"]), "campaign": c["campaign"],
              "evidence": c["evidence"], "reports": c["reports"]} for c in cases]
    return instructions(version) + DRY_RUN + compact_json(shown)


def compact_json(obj, width: int = 400, indent: int = 0) -> str:
    """JSON where any list or object that fits in `width` characters sits on one line and
    larger ones are indented: same content, a fraction of the lines (the agent reads the
    prompt from a file in chunks)."""
    one = json.dumps(obj, ensure_ascii=False)
    if len(one) <= width or not isinstance(obj, (dict, list)) or not obj:
        return one
    pad, inner = " " * indent, " " * (indent + 1)
    if isinstance(obj, dict):
        items = [f"{inner}{json.dumps(k, ensure_ascii=False)}: {compact_json(v, width, indent + 1)}"
                 for k, v in obj.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    items = [inner + compact_json(v, width, indent + 1) for v in obj]
    return "[\n" + ",\n".join(items) + "\n" + pad + "]"


def parse(raw: str) -> dict[str, dict]:
    start, end = raw.find("["), raw.rfind("]")
    if start < 0 or end < start:
        return {}
    try:
        items = json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return {}
    out = {}
    for item in items:
        if isinstance(item, dict) and item.get("verdict") in ("PASS", "FAIL"):
            out[str(item.get("case"))] = {"verdict": item["verdict"], "problems": item.get("problems") or []}
    return out


def judge(case: dict, answer: dict | None) -> str:
    """'caught' | 'wrong_reason' | 'missed' for defects; 'passed' | 'false_alarm' for clean;
    'no_answer' if the case is missing."""
    if answer is None:
        return "no_answer"
    exp = case["expected"]
    if exp["verdict"] == "PASS":
        return "passed" if answer["verdict"] == "PASS" else "false_alarm"
    if answer["verdict"] != "FAIL":
        return "missed"
    for p in answer["problems"]:
        report_ok = str(p.get("report", "")).lower() in exp["report"]
        level_ok = exp["level"] is None or p.get("level") == exp["level"]
        if report_ok and level_ok:
            return "caught"
    return "wrong_reason"


def score_run(answers: dict[str, dict], cases: list[dict]) -> dict:
    outcomes = {c["id"]: judge(c, answers.get(opaque(c["id"]))) for c in cases}
    defects = [c for c in cases if c["expected"]["verdict"] == "FAIL"]
    clean = [c for c in cases if c["expected"]["verdict"] == "PASS"]
    return {
        "detection": sum(outcomes[c["id"]] == "caught" for c in defects) / len(defects),
        "false_alarm": sum(outcomes[c["id"]] == "false_alarm" for c in clean) / len(clean) if clean else None,
        "outcomes": outcomes,
    }


def save_run(version: str, which: str, raw: str, produced_by: str, model: str, tier: str = "basic") -> Path:
    RUNS.mkdir(parents=True, exist_ok=True)
    n = len(list(RUNS.glob(run_glob(version, which, tier)))) + 1
    stem = f"{version}_{which}_{n}" if tier == "basic" else f"{version}_{which}_{tier}_{n}"
    path = RUNS / f"{stem}.json"
    path.write_text(json.dumps({"version": version, "split": which, "tier": tier, "run": n, "produced_by": produced_by,
                                "model": model, "answers": parse(raw), "raw": raw}, indent=1),
                    encoding="utf-8")
    return path


def run_cli(version: str, which: str, k: int, claude: str, model: str, tier: str) -> None:
    prompt = build_prompt(version, which, tier)
    for _ in range(k):
        started = time.time()
        out = subprocess.run([claude, "-p", "--model", model], input=prompt, text=True,
                             capture_output=True, encoding="utf-8", timeout=900)
        if out.returncode != 0:
            sys.exit(f"claude failed: {out.stderr.strip() or out.stdout.strip()}")
        print(f"saved {save_run(version, which, out.stdout, 'claude -p', model, tier).name} "
              f"({time.time() - started:.0f}s)")


def score_all(version: str, which: str, tier: str = "basic") -> None:
    cases = split(load_cases(tier), which)
    runs = sorted(RUNS.glob(run_glob(version, which, tier)))
    if not runs:
        sys.exit(f"no runs for {version}/{which}/{tier}")
    results = [score_run(json.loads(p.read_text(encoding="utf-8"))["answers"], cases) for p in runs]
    det = [r["detection"] for r in results]
    fa = [r["false_alarm"] for r in results if r["false_alarm"] is not None]
    print(f"{version} / {which} / {tier}: {len(runs)} runs, {len(cases)} cases")
    print(f"  defects caught (right report/level)  {statistics.mean(det):.3f}  (min {min(det):.3f}, max {max(det):.3f})")
    if fa:
        print(f"  false alarms on clean cases         {statistics.mean(fa):.3f}  (min {min(fa):.3f}, max {max(fa):.3f})")
    by_kind = defaultdict(lambda: defaultdict(int))
    for r in results:
        for c in cases:
            by_kind[c["kind"]][r["outcomes"][c["id"]]] += 1
    for kind, counts in sorted(by_kind.items()):
        print(f"    {kind:30s} " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["prompt", "run", "score"])
    ap.add_argument("--version", default="v1")
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("-k", type=int, default=3)
    ap.add_argument("--claude", default="claude")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--tier", default="basic", choices=["basic", "hard"])
    a = ap.parse_args()
    if a.command == "prompt":
        sys.stdout.reconfigure(encoding="utf-8")
        print(build_prompt(a.version, a.split, a.tier))
    elif a.command == "run":
        run_cli(a.version, a.split, a.k, a.claude, a.model, a.tier)
    else:
        score_all(a.version, a.split, a.tier)


if __name__ == "__main__":
    main()
