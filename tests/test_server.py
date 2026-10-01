"""The MCP server, exercised the way an agent uses it: launched over stdio, called by tool name."""
import json
import shutil
import sys
import uuid
from pathlib import Path

import anyio
from mcp import Client, StdioServerParameters

from wordtiles import store

ROOT = Path(__file__).resolve().parent.parent


def _payload(result) -> dict:
    if getattr(result, "structured_content", None):
        return result.structured_content
    return json.loads(result.content[0].text)


async def _session_checks() -> None:
    params = StdioServerParameters(command=sys.executable, args=["-m", "wordtiles.server"], cwd=str(ROOT))
    async with Client(params) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
        assert {"generate_level", "measure_level", "explain_level", "calibrate_campaign",
                "release_check", "record_word_decisions"} <= set(tools)
        assert tools["measure_level"].annotations.read_only_hint is True
        assert tools["record_word_decisions"].annotations.read_only_hint is False

        made = _payload(await client.call_tool("generate_level", {"t": 0.3, "seed": 5}))
        assert made["verified_clearable"] is True and made["bot_strength"] >= 0

        measured = _payload(await client.call_tool("measure_level", {"level_id": made["level_id"], "trials": 30}))
        lo, hi = measured["ci95"]
        assert measured["trials"] == 30 and lo <= measured["win_rate"] <= hi

        bad = await client.call_tool("generate_level", {"t": 2.0, "seed": 1})
        assert bad.is_error

        traversal = await client.call_tool("get_level", {"level_id": "../../etc/passwd"})
        assert traversal.is_error


async def _reports_and_regeneration_checks() -> None:
    campaign = f"test-{uuid.uuid4().hex[:8]}"
    params = StdioServerParameters(command=sys.executable, args=["-m", "wordtiles.server"], cwd=str(ROOT))
    try:
        async with Client(params) as client:
            first = _payload(await client.call_tool(
                "submit_report", {"campaign": campaign, "author": "analyst", "text": "level 1: 0.80"}))
            second = _payload(await client.call_tool(
                "submit_report", {"campaign": campaign, "author": "analyst", "text": "level 1: 0.82"}))
            assert (first["version"], second["version"]) == (1, 2) and first["sha256"] != second["sha256"]

            latest = _payload(await client.call_tool("read_report", {"campaign": campaign, "author": "analyst"}))
            assert latest["text"] == "level 1: 0.82" and latest["versions"] == 2
            assert latest["sha256"] == second["sha256"]
            old = _payload(await client.call_tool(
                "read_report", {"campaign": campaign, "author": "analyst", "version": 1}))
            assert old["text"] == "level 1: 0.80"           # earlier versions are kept, not overwritten

            assert (await client.call_tool(
                "submit_report", {"campaign": campaign, "author": "orchestrator", "text": "x"})).is_error
            assert (await client.call_tool("read_report", {"campaign": campaign, "author": "designer"})).is_error

            await client.call_tool("calibrate_campaign", {"name": campaign, "n_levels": 1})
            assert (await client.call_tool(
                "regenerate_level", {"name": campaign, "index": 1, "reason": "because"})).is_error
            r1 = _payload(await client.call_tool(
                "regenerate_level", {"name": campaign, "index": 1, "reason": "blocked_word"}))
            r2 = _payload(await client.call_tool(
                "regenerate_level", {"name": campaign, "index": 1, "reason": "difficulty"}))
            assert r1["regenerations"] == {"blocked_word": 1}
            assert r2["regenerations"] == {"blocked_word": 1, "difficulty": 1}
            assert r1["level_id"] != r2["level_id"]          # each attempt uses a new seed
    finally:
        shutil.rmtree(store.REPORTS_DIR / campaign, ignore_errors=True)
        (store.CAMPAIGNS_DIR / f"{campaign}.json").unlink(missing_ok=True)


def test_server_over_stdio():
    anyio.run(_session_checks)


def test_reports_are_versioned_and_regenerations_count_by_reason():
    anyio.run(_reports_and_regeneration_checks)


async def _staleness_checks() -> None:
    campaign = f"test-{uuid.uuid4().hex[:8]}"
    params = StdioServerParameters(command=sys.executable, args=["-m", "wordtiles.server"], cwd=str(ROOT))
    try:
        async with Client(params) as client:
            await client.call_tool("calibrate_campaign", {"name": campaign, "n_levels": 1})
            await client.call_tool("submit_report", {"campaign": campaign, "author": "designer", "text": "L1 ok"})
            fresh = _payload(await client.call_tool("read_report", {"campaign": campaign, "author": "designer"}))
            assert fresh["campaign_changed_after_report"] is False and fresh["submitted_at"]

            await client.call_tool("regenerate_level", {"name": campaign, "index": 1, "reason": "blocked_word"})
            stale = _payload(await client.call_tool("read_report", {"campaign": campaign, "author": "designer"}))
            assert stale["campaign_changed_after_report"] is True

            await client.call_tool("submit_report", {"campaign": campaign, "author": "designer", "text": "L1 redone"})
            redone = _payload(await client.call_tool("read_report", {"campaign": campaign, "author": "designer"}))
            assert redone["version"] == 2 and redone["campaign_changed_after_report"] is False
    finally:
        shutil.rmtree(store.REPORTS_DIR / campaign, ignore_errors=True)
        (store.CAMPAIGNS_DIR / f"{campaign}.json").unlink(missing_ok=True)


def test_a_report_goes_stale_when_a_level_is_regenerated_after_it():
    anyio.run(_staleness_checks)


def test_explain_level_measures_300_trials_by_default():
    from wordtiles.analysis import EXPLAIN_TRIALS
    from wordtiles.server import explain_level
    import inspect
    assert EXPLAIN_TRIALS == 300 and inspect.signature(explain_level).parameters["trials"].default == 300
