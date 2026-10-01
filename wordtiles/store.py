"""Levels and campaigns on disk, so agents can hand work to each other by id."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .generator import Level

OUT_DIR = Path(__file__).resolve().parent.parent / "out"
LEVELS_DIR = OUT_DIR / "levels"
CAMPAIGNS_DIR = OUT_DIR / "campaigns"
_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def safe_name(name: str) -> str:
    if not _NAME.match(name):
        raise ValueError("names may only use letters, digits, '_', '-' and '.' (max 64)")
    return name


def level_id(level: Level) -> str:
    return f"t{level.t:.3f}_s{level.seed}"


def save_level(level: Level) -> str:
    LEVELS_DIR.mkdir(parents=True, exist_ok=True)
    lid = level_id(level)
    (LEVELS_DIR / f"{lid}.json").write_text(json.dumps(level.to_json()), encoding="utf-8")
    return lid


def load_level(lid: str) -> Level:
    path = LEVELS_DIR / f"{safe_name(lid)}.json"
    if not path.exists():
        raise KeyError(f"no level {lid!r}; generate it or check list_levels")
    return Level.from_json(json.loads(path.read_text(encoding="utf-8")))


def save_campaign(name: str, data: dict) -> Path:
    CAMPAIGNS_DIR.mkdir(parents=True, exist_ok=True)
    path = CAMPAIGNS_DIR / f"{safe_name(name)}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def load_campaign(name: str) -> dict:
    path = CAMPAIGNS_DIR / f"{safe_name(name)}.json"
    if not path.exists():
        raise KeyError(f"no campaign {name!r}")
    return json.loads(path.read_text(encoding="utf-8"))


REPORTS_DIR = OUT_DIR / "reports"
REPORT_AUTHORS = ("designer", "curator", "analyst")


def _report_versions(campaign: str, author: str) -> list[Path]:
    folder = REPORTS_DIR / safe_name(campaign)
    if author not in REPORT_AUTHORS:
        raise ValueError(f"author must be one of {REPORT_AUTHORS}")
    return sorted(folder.glob(f"{author}-v*.md"), key=lambda p: int(p.stem.rsplit("-v", 1)[1]))


def save_report(campaign: str, author: str, text: str) -> dict:
    """Stores a report as a new version - never over an earlier one - and fingerprints it,
    so the gate reviews the report itself rather than whatever someone relays about it."""
    if not text.strip():
        raise ValueError("report is empty")
    versions = _report_versions(campaign, author)
    version = len(versions) + 1
    path = REPORTS_DIR / campaign / f"{author}-v{version}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return {"campaign": campaign, "author": author, "version": version,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]}


def load_report(campaign: str, author: str, version: int | None = None) -> dict:
    versions = _report_versions(campaign, author)
    if not versions:
        raise KeyError(f"no {author} report for campaign {campaign!r}")
    if version is None:
        version = len(versions)
    if not 1 <= version <= len(versions):
        raise KeyError(f"{author} report for {campaign!r} has versions 1..{len(versions)}")
    path = versions[version - 1]
    text = path.read_text(encoding="utf-8")
    return {"campaign": campaign, "author": author, "version": version, "versions": len(versions),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
            "submitted_at": _iso(path.stat().st_mtime),
            "campaign_changed_after_report": campaign_changed_after(campaign, path),
            "text": text}


def campaign_changed_after(campaign: str, report_path: Path) -> bool:
    """True when the campaign was saved (e.g. a level regenerated) after the report was
    written: the report may describe levels the campaign no longer holds. A fact read off
    the files, so nobody has to remember to say a report went stale."""
    campaign_path = CAMPAIGNS_DIR / f"{safe_name(campaign)}.json"
    return campaign_path.exists() and campaign_path.stat().st_mtime_ns > report_path.stat().st_mtime_ns


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


def list_campaigns() -> list[str]:
    return sorted(p.stem for p in CAMPAIGNS_DIR.glob("*.json")) if CAMPAIGNS_DIR.exists() else []
