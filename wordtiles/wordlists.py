"""Editorial word decisions: which answer words may be shown to players.

The game *accepts* every ENABLE word a player types. What it *shows* - the
answer words a level is built from - must be reviewed: ENABLE contains slurs
and vulgarities. Two committed lists record the review, one word per line
with the reason after a tab:

    data/blocked_words.tsv    never used as an answer
    data/approved_words.tsv   reviewed and fine to show

A word in neither list is unreviewed; a campaign containing one can't ship.
"""
from __future__ import annotations

from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BLOCKED_PATH = DATA_DIR / "blocked_words.tsv"
APPROVED_PATH = DATA_DIR / "approved_words.tsv"


def _load(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    entries = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        word, _, reason = line.partition("\t")
        entries[word.strip().upper()] = reason.strip()
    return entries


def _save(path: Path, entries: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{w}\t{r}\n" for w, r in sorted(entries.items())), encoding="utf-8")


def blocked() -> dict[str, str]:
    return _load(BLOCKED_PATH)


def approved() -> dict[str, str]:
    return _load(APPROVED_PATH)


def record(words: list[str], decision: str, reason: str) -> dict[str, int]:
    """Moves each word into the blocked or approved list (a later decision overrides)."""
    if decision not in ("block", "approve"):
        raise ValueError("decision must be 'block' or 'approve'")
    blk, ok = blocked(), approved()
    target, other = (blk, ok) if decision == "block" else (ok, blk)
    for w in words:
        w = w.strip().upper()
        target[w] = reason
        other.pop(w, None)
    _save(BLOCKED_PATH, blk)
    _save(APPROVED_PATH, ok)
    return {"blocked": len(blk), "approved": len(ok)}


def status(word: str) -> str:
    w = word.upper()
    if w in blocked():
        return "blocked"
    if w in approved():
        return "approved"
    return "unreviewed"
