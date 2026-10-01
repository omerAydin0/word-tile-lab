"""The audit hook, run exactly as Claude Code runs it: a subprocess fed one JSON event on stdin."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _hook(event, log: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "WORDTILES_AUDIT_LOG": str(log)}
    payload = event if isinstance(event, str) else json.dumps(event)
    return subprocess.run([sys.executable, "-m", "wordtiles.audit"], input=payload, text=True,
                          capture_output=True, cwd=ROOT, env=env, timeout=60)


def test_pre_and_post_events_are_logged_with_the_calling_agent(tmp_path):
    log = tmp_path / "audit.jsonl"
    base = {"session_id": "s1", "tool_name": "mcp__wordtiles__measure_level",
            "tool_input": {"level_id": "t0.300_s5", "trials": 30}, "tool_use_id": "toolu_1",
            "agent_id": "a1", "agent_type": "release-reviewer"}
    assert _hook({**base, "hook_event_name": "PreToolUse"}, log).returncode == 0
    assert _hook({**base, "hook_event_name": "PostToolUse",
                  "tool_result": {"type": "text", "text": '{"win_rate": 0.43}'}}, log).returncode == 0

    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [r["event"] for r in rows] == ["PreToolUse", "PostToolUse"]
    assert all(r["agent_type"] == "release-reviewer" and r["tool"] == base["tool_name"] for r in rows)
    assert "0.43" in rows[1]["result_preview"]


def test_main_session_calls_are_labelled_main(tmp_path):
    log = tmp_path / "audit.jsonl"
    _hook({"hook_event_name": "PostToolUse", "session_id": "s1",
           "tool_name": "mcp__wordtiles__release_check", "tool_input": {"name": "c"}}, log)
    assert json.loads(log.read_text(encoding="utf-8"))["agent_type"] == "main"


def test_a_broken_event_never_blocks_the_tool_call(tmp_path):
    result = _hook("this is not json", tmp_path / "audit.jsonl")
    assert result.returncode == 0 and "could not record" in result.stderr


def test_huge_inputs_are_clipped(tmp_path):
    log = tmp_path / "audit.jsonl"
    _hook({"hook_event_name": "PreToolUse", "tool_name": "mcp__wordtiles__submit_report",
           "tool_input": {"text": "x" * 50_000}}, log)
    assert len(json.loads(log.read_text(encoding="utf-8"))["input"]) < 2200


def test_summary_counts_calls_per_agent_and_tool(tmp_path):
    log = tmp_path / "audit.jsonl"
    for i, agent in enumerate(["level-designer", "release-reviewer", "release-reviewer"]):
        ev = {"session_id": "s1", "tool_name": "mcp__wordtiles__campaign_report",
              "tool_input": {}, "tool_use_id": f"t{i}", "agent_type": agent}
        _hook({**ev, "hook_event_name": "PreToolUse"}, log)
        _hook({**ev, "hook_event_name": "PostToolUse", "tool_result": {"type": "text", "text": "{}"}}, log)
    env = {**os.environ, "WORDTILES_AUDIT_LOG": str(log)}
    out = subprocess.run([sys.executable, "-m", "wordtiles.audit", "summary"], text=True,
                         capture_output=True, cwd=ROOT, env=env, timeout=60).stdout
    assert "session s1: 3 tool calls" in out
    assert "release-reviewer" in out and "x2" in out


def test_project_settings_are_valid_and_gate_the_word_decisions():
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    allowed = set(settings["permissions"]["allow"])
    # The one tool that changes what players can see always asks a human.
    assert "mcp__wordtiles__record_word_decisions" not in allowed
    for event in ("PreToolUse", "PostToolUse"):
        (entry,) = settings["hooks"][event]
        assert entry["matcher"] == "mcp__wordtiles__.*"
        assert entry["hooks"][0]["command"] == "python -m wordtiles.audit"
