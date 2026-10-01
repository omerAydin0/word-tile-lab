import json

import pytest

from evals.reviewer.harness import (
    build_prompt, compact_json, judge, load_cases, opaque, parse, score_run, split,
)

TIERS = ["basic", "hard"]


@pytest.mark.parametrize("tier", TIERS)
def test_dev_and_test_partition_every_kind(tier):
    cases = load_cases(tier)
    dev = {c["id"] for c in split(cases, "dev")}
    test = {c["id"] for c in split(cases, "test")}
    assert not dev & test and dev | test == {c["id"] for c in cases}
    kinds = {c["kind"] for c in cases}
    assert kinds == {c["kind"] for c in split(cases, "dev")} == {c["kind"] for c in split(cases, "test")}


@pytest.mark.parametrize("tier", TIERS)
def test_the_prompt_never_reveals_ids_kinds_or_answers(tier):
    cases = load_cases(tier)
    prompt = build_prompt("v1", "dev", tier)
    body = prompt.split("Cases:\n", 1)[1]
    for c in cases:
        assert c["id"] not in body
        assert f'"{c["kind"]}"' not in body
    assert '"expected"' not in body and '"kind"' not in body


@pytest.mark.parametrize("tier", TIERS)
def test_compact_prompt_round_trips_exactly(tier):
    prompt = build_prompt("v1", "dev", tier)
    shown = json.loads(prompt.split("Cases:\n", 1)[1])
    by_id = {opaque(c["id"]): c for c in split(load_cases(tier), "dev")}
    assert len(shown) == len(by_id)
    for s in shown:
        assert s["evidence"] == by_id[s["case"]]["evidence"] and s["reports"] == by_id[s["case"]]["reports"]


@pytest.mark.parametrize("tier", TIERS)
def test_every_defect_case_names_the_report_and_level_it_expects(tier):
    for c in load_cases(tier):
        exp = c["expected"]
        if exp["verdict"] == "FAIL":
            assert exp["report"] and ("level" in exp)


def test_compact_json_keeps_lines_short_and_content_identical():
    obj = {"a": [{"x": i, "words": {f"W{j}": "approved" for j in range(6)}} for i in range(30)]}
    text = compact_json(obj)
    assert json.loads(text) == obj and len(text.splitlines()) < 40


CASE_FAIL = {"id": "x", "expected": {"verdict": "FAIL", "report": ["analyst"], "level": 7}}
CASE_PASS = {"id": "y", "expected": {"verdict": "PASS"}}


@pytest.mark.parametrize("answer, outcome", [
    ({"verdict": "FAIL", "problems": [{"report": "analyst", "level": 7}]}, "caught"),
    ({"verdict": "FAIL", "problems": [{"report": "Analyst", "level": 7}]}, "caught"),
    ({"verdict": "FAIL", "problems": [{"report": "designer", "level": 7}]}, "wrong_reason"),
    ({"verdict": "FAIL", "problems": [{"report": "analyst", "level": 3}]}, "wrong_reason"),
    ({"verdict": "PASS", "problems": []}, "missed"),
    (None, "no_answer"),
])
def test_a_defect_is_caught_only_for_the_right_report_and_level(answer, outcome):
    assert judge(CASE_FAIL, answer) == outcome


def test_clean_cases_score_pass_or_false_alarm():
    assert judge(CASE_PASS, {"verdict": "PASS", "problems": []}) == "passed"
    assert judge(CASE_PASS, {"verdict": "FAIL", "problems": [{"report": "designer"}]}) == "false_alarm"


def test_parse_ignores_prose_and_bad_verdicts():
    raw = 'note\n[{"case": "c1", "verdict": "FAIL", "problems": []}, {"case": "c2", "verdict": "MAYBE"}]\nend'
    assert parse(raw) == {"c1": {"verdict": "FAIL", "problems": []}}


def test_saved_v1_runs_score_as_reported():
    for tier in TIERS:
        cases = split(load_cases(tier), "dev")
        from evals.reviewer.harness import RUNS, run_glob
        runs = sorted(RUNS.glob(run_glob("v1", "dev", tier)))
        assert len(runs) == 3
        for p in runs:
            r = score_run(json.loads(p.read_text(encoding="utf-8"))["answers"], cases)
            assert r["detection"] == 1.0 and r["false_alarm"] == 0.0


def test_report_page_shows_every_dev_case_with_its_runs():
    from evals.reviewer.report import build
    page = build()
    dev = sum(len(split(load_cases(t), "dev")) for t in TIERS)
    assert page.count('<details class="case"') == dev
    assert page.count('class="run"') == dev * 3
    assert "<script>" in page and "prefers-color-scheme: dark" in page
