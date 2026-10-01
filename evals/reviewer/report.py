"""Renders the release-reviewer eval as one readable page: every dev case, what was planted
(as a diff against the clean report), and what the reviewer said in each run.

    python -m evals.reviewer.report      # writes evals/reviewer/report.html
"""
from __future__ import annotations

import difflib
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from evals.reviewer.harness import RUNS, judge, load_cases, opaque, run_glob, split

HERE = Path(__file__).resolve().parent
OUT = HERE / "report.html"

KIND_TEXT = {
    "designer_wrong_rate": "Designer quotes a wrong win rate for one level (off by 0.07-0.12).",
    "designer_hides_out_of_band": "A level is out of band in the evidence; the designer still claims 10/10 and release_check passes at 80%.",
    "analyst_wrong_rate": "Analyst quotes a wrong explain_level win rate (off by 0.08-0.15).",
    "analyst_stale_level": "Analyst analyses a level id the campaign no longer holds.",
    "analyst_unsupported_number": "Analyst adds a figure no tool returned (\"attempts on average\").",
    "curator_count_mismatch": "Curator says it blocked one more word than it lists.",
    "curator_decision_misreported": "Curator reports blocking a word the data shows approved.",
    "clean_exact": "Clean reports, numbers exactly as the tools returned them.",
    "clean_rounded": "Clean reports, numbers rounded to two decimals.",
    "subtle_wrong_rate": "Designer's rate for one level drifts by only 0.03-0.05.",
    "buried_wrong_rate": "One wrong rate in the third paragraph of a four-level analyst report.",
    "consistent_wrong_pair": "Designer and analyst agree on the same wrong number.",
    "misattributed_number": "A real explain_level figure, attributed to the wrong level.",
    "percent_format": "Clean reports with every rate written as a percentage.",
    "long_correct": "A long analyst report, every number correct.",
    "derived_numbers": "Clean, plus a derived figure (a mean) that is not in the evidence but can be computed.",
    "tolerance_edge": "Clean; the reviewer's own re-measurement is 0.05-0.075 off - inside the 0.08 tolerance.",
}
OUTCOME_TEXT = {"caught": "caught", "wrong_reason": "failed for the wrong reason", "missed": "missed",
                "passed": "passed", "false_alarm": "false alarm", "no_answer": "no answer"}
GOOD = {"caught", "passed"}


def flatten(obj, prefix: str = "") -> dict[str, object]:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else str(k)))
        return out
    if isinstance(obj, list) and obj and all(isinstance(x, dict) and "index" in x for x in obj):
        out = {}
        for x in obj:
            out.update(flatten(x, f"{prefix}[level {x['index']}]"))
        return out
    return {prefix: obj}


def baselines(cases: list[dict], tier: str) -> dict[str, dict]:
    """The clean case to diff against, per campaign."""
    kind = "clean_exact" if tier == "basic" else "long_correct"
    return {c["campaign"]: c for c in cases if c["kind"] == kind}


def report_diff(clean: str, planted: str) -> str:
    rows = []
    for line in difflib.ndiff(clean.splitlines(), planted.splitlines()):
        tag, text = line[:1], line[2:]
        if not text.strip():
            continue
        if tag == "-":
            rows.append(f'<div class="del">&minus; {html.escape(text)}</div>')
        elif tag == "+":
            rows.append(f'<div class="add">+ {html.escape(text)}</div>')
    return "".join(rows)


def case_html(case: dict, base: dict, base_basic: dict | None, answers: list[dict | None]) -> str:
    parts = []
    for who in ("designer", "curator", "analyst"):
        clean = base["reports"][who]
        if who == "analyst" and "mid-chapter" not in case["reports"][who] and base_basic:
            clean = base_basic["reports"][who]
        if case["reports"][who] != clean:
            parts.append(f'<div class="diff"><div class="who">{who} report</div>{report_diff(clean, case["reports"][who])}</div>')
    before, after = flatten(base["evidence"]), flatten(case["evidence"])
    changed = [k for k in sorted(set(before) | set(after)) if before.get(k) != after.get(k)]
    if changed:
        rows = "".join(f"<tr><td>{html.escape(k)}</td><td>{html.escape(json.dumps(before.get(k)))}</td>"
                       f"<td>{html.escape(json.dumps(after.get(k)))}</td></tr>" for k in changed)
        parts.append(f'<div class="diff"><div class="who">evidence</div><table class="ev"><tr><th>field</th>'
                     f'<th>clean</th><th>this case</th></tr>{rows}</table></div>')
    if not parts:
        parts.append('<p class="muted">No difference: this is the plain clean report.</p>')

    exp = case["expected"]
    target = ("PASS" if exp["verdict"] == "PASS" else
              f"FAIL, naming {' or '.join(exp['report'])}" + (f", level {exp['level']}" if exp.get("level") else ""))
    runs = []
    for i, a in enumerate(answers, 1):
        outcome = judge(case, a)
        cls = "good" if outcome in GOOD else "bad"
        problems = "".join(
            f'<li><span class="tag">{html.escape(str(p.get("report")))}'
            f'{", level " + str(p.get("level")) if p.get("level") is not None else ""}</span> '
            f'{html.escape(str(p.get("issue", "")))}</li>' for p in (a or {}).get("problems", []))
        runs.append(f'<div class="run"><span class="badge {cls}">run {i}: {(a or {}).get("verdict", "-")} '
                    f'&middot; {OUTCOME_TEXT[outcome]}</span>{"<ul>" + problems + "</ul>" if problems else ""}</div>')
    good = sum(judge(case, a) in GOOD for a in answers)
    summary_cls = "good" if good == len(answers) else "bad"
    is_defect = exp["verdict"] == "FAIL"
    return (f'<details class="case" id="{opaque(case["id"])}" data-tier="{case.get("tier", "basic")}" '
            f'data-type="{"defect" if is_defect else "clean"}">'
            f'<summary><span class="badge {summary_cls}">{good}/{len(answers)}</span> '
            f'<b>{html.escape(case["kind"].replace("_", " "))}</b> <span class="muted">&middot; '
            f'{html.escape(case["campaign"])} &middot; {case.get("tier", "basic")}</span></summary>'
            f'<p>{html.escape(KIND_TEXT.get(case["kind"], ""))}</p>'
            f'<p><b>A correct reviewer says:</b> {html.escape(target)}</p>'
            f'<h4>{"What was planted" if is_defect else "How it differs from the plain clean report"}</h4>{"".join(parts)}'
            f'<h4>What the reviewer said</h4>{"".join(runs)}</details>')


def build(only: str | None = None) -> str:
    """The full report, or - with `only`, a case id from the page - just that case, open
    (a page small enough to screenshot)."""
    tiers = {}
    cards = []
    kind_rows = []
    basic_clean = baselines(load_cases("basic"), "basic")
    for tier in ("basic", "hard"):
        cases = split(load_cases(tier), "dev")
        base = baselines(load_cases(tier), tier)
        runs = [json.loads(p.read_text(encoding="utf-8"))["answers"] for p in sorted(RUNS.glob(run_glob("v1", "dev", tier)))]
        tally = Counter()
        per_kind = defaultdict(Counter)
        for c in cases:
            answers = [r.get(opaque(c["id"])) for r in runs]
            for a in answers:
                o = judge(c, a)
                tally[o] += 1
                per_kind[c["kind"]][o] += 1
            card = case_html(c, base[c["campaign"]], basic_clean.get(c["campaign"]) if tier == "hard" else None, answers)
            if only is None:
                cards.append(card)
            elif opaque(c["id"]) == only:
                cards.append(card.replace('<details class="case"', '<details open class="case"', 1))
        defects = tally["caught"] + tally["wrong_reason"] + tally["missed"]
        clean = tally["passed"] + tally["false_alarm"]
        tiers[tier] = (tally["caught"], defects, tally["passed"], clean, len(runs))
        for kind, counts in per_kind.items():
            n = sum(counts.values())
            good = counts["caught"] + counts["passed"]
            kind_rows.append(f'<tr><td>{tier}</td><td>{html.escape(kind.replace("_", " "))}</td>'
                             f'<td>{html.escape(KIND_TEXT.get(kind, ""))}</td><td class="num {"good" if good == n else "bad"}">'
                             f'{good}/{n}</td></tr>')

    summary = "".join(
        f'<tr><td>{t}</td><td class="num">{c}/{d}</td><td class="num">{d - c}</td><td class="num">{p}/{n}</td>'
        f'<td class="num">{n - p}</td><td class="num">{r}</td></tr>' for t, (c, d, p, n, r) in tiers.items())

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reviewer eval</title>
<style>
:root {{ --bg:#f7f5f0; --card:#fffdf9; --ink:#24221e; --muted:#6f6a60; --line:#e2ddd2;
  --good:#2f7a4f; --good-bg:#e3f2e8; --bad:#a33a2a; --bad-bg:#f7e2de; --add:#e3f2e8; --del:#f7e2de; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#1b1a17; --card:#24221e; --ink:#ece7dc;
  --muted:#a29b8e; --line:#3a3731; --good:#7fd1a0; --good-bg:#1f3a2a; --bad:#f0a091; --bad-bg:#43251f; --add:#1f3a2a; --del:#43251f; }} }}
:root[data-theme="dark"] {{ --bg:#1b1a17; --card:#24221e; --ink:#ece7dc; --muted:#a29b8e; --line:#3a3731;
  --good:#7fd1a0; --good-bg:#1f3a2a; --bad:#f0a091; --bad-bg:#43251f; --add:#1f3a2a; --del:#43251f; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:980px; margin:0 auto; padding:28px 16px 60px; }}
h1 {{ font-size:26px; margin:0 0 6px; }} h2 {{ font-size:19px; margin:32px 0 10px; }} h4 {{ margin:16px 0 6px; font-size:14px; }}
p {{ margin:6px 0; }} .muted {{ color:var(--muted); }}
.wrap {{ overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; background:var(--card); border:1px solid var(--line); border-radius:8px; }}
th, td {{ text-align:left; padding:7px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
th {{ font-size:13px; color:var(--muted); font-weight:600; }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
td.good {{ color:var(--good); font-weight:600; }} td.bad {{ color:var(--bad); font-weight:600; }}
.filters {{ display:flex; flex-wrap:wrap; gap:8px; margin:12px 0; }}
.filters button {{ font:inherit; padding:6px 12px; border-radius:999px; border:1px solid var(--line);
  background:var(--card); color:var(--ink); cursor:pointer; }}
.filters button[aria-pressed="true"] {{ background:var(--ink); color:var(--bg); border-color:var(--ink); }}
.case {{ background:var(--card); border:1px solid var(--line); border-radius:8px; margin:8px 0; padding:0 14px; }}
.case summary {{ cursor:pointer; padding:11px 0; list-style-position:outside; }}
.case[open] {{ padding-bottom:12px; }}
.badge {{ display:inline-block; font-size:12.5px; font-weight:600; padding:2px 8px; border-radius:6px; }}
.badge.good {{ background:var(--good-bg); color:var(--good); }} .badge.bad {{ background:var(--bad-bg); color:var(--bad); }}
.diff {{ border:1px solid var(--line); border-radius:6px; margin:6px 0; overflow:hidden; }}
.diff .who {{ font-size:12.5px; color:var(--muted); padding:4px 10px; border-bottom:1px solid var(--line); }}
.diff .add, .diff .del {{ font:12.5px/1.45 ui-monospace,Consolas,monospace; padding:4px 10px; white-space:pre-wrap; overflow-wrap:anywhere; }}
.diff .add {{ background:var(--add); }} .diff .del {{ background:var(--del); }}
table.ev {{ border:0; font:12.5px ui-monospace,Consolas,monospace; }} table.ev td {{ overflow-wrap:anywhere; }}
.run {{ margin:6px 0; }} .run ul {{ margin:6px 0 0; padding-left:20px; }} .run li {{ margin:3px 0; }}
.tag {{ font-size:12px; font-weight:600; color:var(--muted); }}
</style></head><body><main>
<h1>Release-reviewer eval{": one case" if only else ""}</h1>
<p class="muted">word-tile-lab &middot; the reviewer is the level team's last gate</p>
<p>The reviewer reads the designer's, curator's and analyst's reports and checks every number against
tool output. Each case below gives it real tool output for a campaign and reports with one planted
defect - or none. A defect only counts as caught when the reviewer fails the campaign <i>and</i> names
the right report (and level). Clean cases test the opposite failure: rejecting sound work.
Model: Sonnet, the production model &middot; dev split &middot; 3 runs per case.</p>

{"" if only else f"""<h2>Summary</h2>
<div class="wrap"><table><tr><th>tier</th><th class="num">defects caught</th><th class="num">missed / wrong reason</th>
<th class="num">clean passed</th><th class="num">false alarms</th><th class="num">runs</th></tr>{summary}</table></div>
<p>Given complete evidence, the reviewer caught every planted defect and never failed a clean report.
In the team's real run relaxed-03 it failed sound levels three times - this eval is how we know that
was the plumbing (what it could reach), not its judgement.</p>

<h2>By defect type</h2>
<div class="wrap"><table><tr><th>tier</th><th>kind</th><th>what was planted</th><th class="num">right answers</th></tr>
{''.join(kind_rows)}</table></div>

<h2>Every case</h2>
<p class="muted">Open a case to see the planted change (red: the clean report, green: what the reviewer got) and
each run's verdict in the reviewer's own words.</p>
<div class="filters" role="group" aria-label="Filter cases">
<button data-f="all" aria-pressed="true">All</button><button data-f="defect" aria-pressed="false">Defects</button>
<button data-f="clean" aria-pressed="false">Clean</button><button data-f="basic" aria-pressed="false">Basic tier</button>
<button data-f="hard" aria-pressed="false">Hard tier</button></div>"""}
<div id="cases">{''.join(cards)}</div>
</main>
<script>
// A link to report.html#case-xxxxxxxx opens that case.
const linked = location.hash && document.getElementById(location.hash.slice(1));
if (linked) {{ linked.open = true; linked.scrollIntoView(); }}
document.querySelectorAll('.filters button').forEach(b => b.addEventListener('click', () => {{
  document.querySelectorAll('.filters button').forEach(x => x.setAttribute('aria-pressed', x === b));
  const f = b.dataset.f;
  document.querySelectorAll('.case').forEach(c => {{
    c.hidden = !(f === 'all' || c.dataset.type === f || c.dataset.tier === f);
  }});
}}));
</script>
</body></html>"""


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3:                      # report.py <case id> <out.html>
        Path(sys.argv[2]).write_text(build(only=sys.argv[1]), encoding="utf-8")
    else:
        OUT.write_text(build(), encoding="utf-8")
        print(f"wrote {OUT}")
