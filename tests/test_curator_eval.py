import re

from evals.curator.harness import (
    build_prompt, instructions, load_set, parse_decisions, score_run, split,
)
from wordtiles.vocab import ENABLE_PATH


def test_every_word_is_valid_and_labelled_once():
    rows = load_set()
    words = [r["word"] for r in rows]
    assert len(words) == len(set(words))
    # Valid in ENABLE; length doesn't matter here - the eval tests judgement, not playability.
    enable = {w.upper() for w in ENABLE_PATH.read_text(encoding="ascii").split()}
    assert all(w in enable for w in words)
    assert {r["label"] for r in rows} == {"block", "approve", "borderline"}


def test_dev_and_test_partition_the_set():
    rows = load_set()
    dev = {r["word"] for r in split(rows, "dev")}
    test = {r["word"] for r in split(rows, "test")}
    assert not dev & test and dev | test == {r["word"] for r in rows}


def test_relabelling_a_word_never_moves_it_between_splits():
    rows = load_set()
    before = {r["word"] for r in split(rows, "dev")}
    relabelled = [{**r, "category": "something_else", "label": "borderline"} for r in rows]
    assert {r["word"] for r in split(relabelled, "dev")} == before


def test_no_prompt_names_a_word_it_is_scored_on():
    scored = {r["word"] for r in load_set()}
    for version in ("v1", "v2"):
        named = set(re.findall(r"\b[A-Z]{3,}\b", instructions(version)))
        assert not named & scored, (version, named & scored)


def test_prompt_never_lists_words_grouped_by_category():
    prompt = build_prompt("v2", "test")
    rows = {r["word"]: r["category"] for r in load_set()}
    order = [rows[w] for w in re.findall(r'"word": "([A-Z]+)"', prompt)]
    longest = run = 1
    for prev, cur in zip(order, order[1:]):
        run = run + 1 if cur == prev else 1
        longest = max(longest, run)
    assert len(order) == len(split(load_set(), "test")) and longest < 6


def test_parse_ignores_prose_and_bad_decisions():
    raw = 'Here you go:\n[{"word": "cat", "decision": "approve"}, {"word": "x", "decision": "maybe"}]\nthanks'
    assert parse_decisions(raw) == {"CAT": "approve"}
    assert parse_decisions("no json here") == {}


def test_scoring_counts_misses_and_false_blocks_but_not_borderline():
    rows = [{"word": "BAD", "label": "block", "category": "slur"},
            {"word": "OK", "label": "approve", "category": "common"},
            {"word": "HMM", "label": "borderline", "category": "x"}]
    s = score_run({"BAD": "approve", "OK": "block", "HMM": "block"}, rows)
    assert s["block_recall"] == 0.0 and s["false_block_rate"] == 1.0
    assert s["borderline_blocked"] == (1, 1)
    perfect = score_run({"BAD": "block", "OK": "approve"}, rows)
    assert perfect["block_recall"] == 1.0 and perfect["false_block_rate"] == 0.0 and perfect["missing"] == 1
