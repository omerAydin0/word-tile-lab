"""Audit trail for the level team: every wordtiles tool call, which agent made it, and how long it took.

Wired as a Claude Code PreToolUse/PostToolUse hook (see .claude/settings.json); the hook
pipes its JSON on stdin and this appends one line per event to out/audit/audit.jsonl.

    python -m wordtiles.audit              # hook mode: read one event from stdin
    python -m wordtiles.audit summary      # per session: calls by agent and tool, durations

An audit hook must never stop the work it records, so hook mode always exits 0; a write
failure is reported on stderr instead.
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

LOG = Path(os.environ.get("WORDTILES_AUDIT_LOG",
                          Path(__file__).resolve().parent.parent / "out" / "audit" / "audit.jsonl"))
INPUT_CHARS = 2000
RESULT_CHARS = 300


def _clip(value, limit: int) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + f"... [{len(text)} chars]"


def record(event: dict) -> dict:
    entry = {
        "ts": round(time.time(), 3),
        "event": event.get("hook_event_name"),
        "session_id": event.get("session_id"),
        "agent_type": event.get("agent_type") or "main",
        "agent_id": event.get("agent_id"),
        "tool": event.get("tool_name"),
        "tool_use_id": event.get("tool_use_id"),
        "input": _clip(event.get("tool_input", {}), INPUT_CHARS),
    }
    result = event.get("tool_result", event.get("tool_response"))
    if result is not None:
        entry["result_preview"] = _clip(result, RESULT_CHARS)
        if isinstance(result, dict) and ("is_error" in result or "isError" in result):
            entry["is_error"] = bool(result.get("is_error", result.get("isError")))
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def summary(path: Path = LOG) -> str:
    if not path.exists():
        return f"no audit log at {path}"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    sessions: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        sessions[r.get("session_id") or "?"].append(r)

    out = []
    for sid, events in sessions.items():
        started = {e["tool_use_id"]: e["ts"] for e in events
                   if e.get("event") == "PreToolUse" and e.get("tool_use_id")}
        calls = Counter()
        seconds: dict[tuple[str, str], float] = defaultdict(float)
        errors = Counter()
        for e in events:
            if e.get("event") != "PostToolUse":
                continue
            key = (e["agent_type"], e["tool"])
            calls[key] += 1
            if e.get("tool_use_id") in started:
                seconds[key] += e["ts"] - started[e["tool_use_id"]]
            if e.get("is_error"):
                errors[key] += 1
        out.append(f"session {sid}: {sum(calls.values())} tool calls")
        for (agent, tool), n in sorted(calls.items()):
            err = f", {errors[(agent, tool)]} errors" if errors[(agent, tool)] else ""
            out.append(f"  {agent:18s} {tool:42s} x{n:<3d} {seconds[(agent, tool)]:7.1f}s{err}")
    return "\n".join(out)


def main() -> None:
    if sys.argv[1:] == ["summary"]:
        sys.stdout.reconfigure(encoding="utf-8")
        print(summary())
        return
    try:
        record(json.loads(sys.stdin.read() or "{}"))
    except Exception as exc:  # never block the agent over a logging failure
        print(f"wordtiles audit: could not record event: {exc}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
