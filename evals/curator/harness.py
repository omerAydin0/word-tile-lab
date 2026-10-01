"""Eval for the word-curator agent: does it block what the policy says to block, and only that?

    python -m evals.curator.harness prompt --version v1 --split dev      # the exact prompt
    python -m evals.curator.harness run    --version v1 --split dev -k 3 # via `claude -p`
    python -m evals.curator.harness score  --version v1 --split dev      # every saved run

The agent's own instruction file is the thing under test; the eval only swaps its tool
workflow for a dry run (queue in, JSON decisions out), so the judgement policy is
identical to production. Words are split dev/test per category: improve the prompt by
reading dev failures only, and report test.
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from wordtiles.vocab import zipf  # noqa: E402

HERE = Path(__file__).resolve().parent
WORDS = HERE / "words.tsv"
VERSIONS = HERE / "versions"
RUNS = HERE / "runs"

DRY_RUN = """

## Dry run (evaluation)
This is a dry run: do not call any tools. The review queue is below as JSON, in the same
shape `review_queue` returns. Judge every word exactly as you would in production, then
output ONLY a JSON array - no prose before or after - with one object per word:
{"word": "...", "decision": "approve" or "block", "reason": "..."}

Review queue:
"""


def load_set() -> list[dict]:
    rows = []
    for line in WORDS.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or line.startswith("word\t") or not line.strip():
            continue
        word, label, category, stratum, *rest = line.split("\t")
        rows.append({"word": word, "label": label, "category": category, "stratum": stratum,
                     "note": rest[0] if rest else ""})
    return rows


def split(rows: list[dict], which: str) -> list[dict]:
    """Stratified 50/50 by stratum (a word's first category, never edited), ordered by a hash
    so it depends on neither file order nor later relabelling."""
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["stratum"]].append(r)
    chosen = []
    for cat_rows in by_cat.values():
        ordered = sorted(cat_rows, key=lambda r: hashlib.sha256(r["word"].encode()).hexdigest())
        chosen += ordered[0::2] if which == "dev" else ordered[1::2]
    return chosen


def instructions(version: str) -> str:
    text = (VERSIONS / f"{version}.md").read_text(encoding="utf-8")
    return re.sub(r"\A---\n.*?\n---\n", "", text, count=1, flags=re.S).strip()


def build_prompt(version: str, which: str) -> str:
    rows = split(load_set(), which)
    rng = random.Random(f"{which}-order")
    rng.shuffle(rows)   # never grouped by category: the order must not hint at the label
    queue = {"name": f"eval-{which}",
             "unreviewed": [{"word": r["word"], "zipf": round(zipf(r["word"]), 2)} for r in rows]}
    return instructions(version) + DRY_RUN + json.dumps(queue, indent=1)


def parse_decisions(raw: str) -> dict[str, str]:
    start, end = raw.find("["), raw.rfind("]")
    if start < 0 or end < start:
        return {}
    try:
        items = json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return {}
    out = {}
    for item in items:
        if isinstance(item, dict) and item.get("decision") in ("approve", "block"):
            out[str(item.get("word", "")).upper()] = item["decision"]
    return out


def score_run(decisions: dict[str, str], rows: list[dict]) -> dict:
    per_cat = defaultdict(lambda: {"n": 0, "wrong": 0, "missing": 0, "blocked": 0})
    for r in rows:
        d = decisions.get(r["word"])
        c = per_cat[r["category"]]
        c["n"] += 1
        c["label"] = r["label"]
        if d is None:
            c["missing"] += 1
        elif d == "block":
            c["blocked"] += 1
        if r["label"] == "block" and d != "block":
            c["wrong"] += 1
        if r["label"] == "approve" and d != "approve":
            c["wrong"] += 1

    def tally(label):
        n = sum(c["n"] for c in per_cat.values() if c["label"] == label)
        wrong = sum(c["wrong"] for c in per_cat.values() if c["label"] == label)
        return n, wrong

    nb, missed = tally("block")
    na, over = tally("approve")
    border = [c for c in per_cat.values() if c["label"] == "borderline"]
    return {
        "block_recall": (nb - missed) / nb if nb else None,
        "false_block_rate": over / na if na else None,
        "missing": sum(c["missing"] for c in per_cat.values()),
        "borderline_blocked": (sum(c["blocked"] for c in border), sum(c["n"] for c in border)),
        "categories": {k: dict(v) for k, v in per_cat.items()},
        "errors": sorted(
            f"{r['word']} ({r['category']}): expected {r['label']}, got {decisions.get(r['word'], 'nothing')}"
            for r in rows
            if r["label"] != "borderline" and decisions.get(r["word"]) != r["label"]),
    }


def save_run(version: str, which: str, raw: str, produced_by: str, model: str) -> Path:
    RUNS.mkdir(parents=True, exist_ok=True)
    n = len(list(RUNS.glob(f"{version}_{which}_*.json"))) + 1
    path = RUNS / f"{version}_{which}_{n}.json"
    path.write_text(json.dumps({"version": version, "split": which, "run": n,
                                "produced_by": produced_by, "model": model,
                                "decisions": parse_decisions(raw), "raw": raw}, indent=1),
                    encoding="utf-8")
    return path


def run_cli(version: str, which: str, k: int, claude: str, model: str) -> None:
    prompt = build_prompt(version, which)
    for _ in range(k):
        started = time.time()
        out = subprocess.run([claude, "-p", "--model", model], input=prompt, text=True,
                             capture_output=True, encoding="utf-8", timeout=600)
        if out.returncode != 0:
            sys.exit(f"claude failed: {out.stderr.strip() or out.stdout.strip()}")
        path = save_run(version, which, out.stdout, "claude -p", model)
        print(f"saved {path.name} ({time.time() - started:.0f}s)")


def score_all(version: str, which: str) -> dict:
    rows = split(load_set(), which)
    runs = sorted(RUNS.glob(f"{version}_{which}_*.json"))
    if not runs:
        sys.exit(f"no runs for {version}/{which}")
    results = [score_run(json.loads(p.read_text(encoding="utf-8"))["decisions"], rows) for p in runs]

    def spread(key):
        vals = [r[key] for r in results]
        return statistics.mean(vals), min(vals), max(vals)

    rec, fb = spread("block_recall"), spread("false_block_rate")
    cats = defaultdict(list)
    for r in results:
        for name, c in r["categories"].items():
            cats[name].append(c)
    summary = {
        "version": version, "split": which, "runs": len(runs), "words": len(rows),
        "block_recall": rec, "false_block_rate": fb,
        "missing_per_run": [r["missing"] for r in results],
        "by_category": {name: {"label": cs[0]["label"], "n": cs[0]["n"],
                               "mean_wrong": statistics.mean(c["wrong"] for c in cs),
                               "mean_blocked": statistics.mean(c["blocked"] for c in cs)}
                        for name, cs in sorted(cats.items())},
        "errors_by_run": [r["errors"] for r in results],
    }
    return summary


def print_summary(s: dict) -> None:
    rec, fb = s["block_recall"], s["false_block_rate"]
    print(f"{s['version']} / {s['split']}: {s['runs']} runs, {s['words']} words")
    print(f"  block recall      {rec[0]:.3f}  (min {rec[1]:.3f}, max {rec[2]:.3f})")
    print(f"  false-block rate  {fb[0]:.3f}  (min {fb[1]:.3f}, max {fb[2]:.3f})")
    print(f"  missing decisions per run: {s['missing_per_run']}")
    for name, c in s["by_category"].items():
        what = "blocked" if c["label"] == "borderline" else "wrong"
        val = c["mean_blocked"] if c["label"] == "borderline" else c["mean_wrong"]
        print(f"    {name:22s} {c['label']:10s} n={c['n']:3d}  mean {what}: {val:.2f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["prompt", "run", "score"])
    ap.add_argument("--version", default="v1")
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("-k", type=int, default=3)
    ap.add_argument("--claude", default="claude")
    ap.add_argument("--model", default="sonnet")
    a = ap.parse_args()
    if a.command == "prompt":
        sys.stdout.reconfigure(encoding="utf-8")
        print(build_prompt(a.version, a.split))
    elif a.command == "run":
        run_cli(a.version, a.split, a.k, a.claude, a.model)
    else:
        s = score_all(a.version, a.split)
        print_summary(s)
        for i, errs in enumerate(s["errors_by_run"], 1):
            print(f"  run {i} errors: {errs}")


if __name__ == "__main__":
    main()
