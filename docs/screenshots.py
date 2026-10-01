"""Regenerates the README's screenshots from the project's own pages, with headless Edge/Chrome.

    python docs/screenshots.py          # writes docs/images/*.png

`CHROME` can point at any Chromium; otherwise Edge (which ships with Windows) or Chrome is used.
"""
from __future__ import annotations

import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals.reviewer.report import build as eval_report  # noqa: E402
from wordtiles.bots import CasualPlayer, OpponentBot, play_duel  # noqa: E402
from wordtiles.generator import Level  # noqa: E402
from wordtiles.render import to_html  # noqa: E402

IMAGES = ROOT / "docs" / "images"
LEVEL = ROOT / "docs/runs/relaxed-05/levels/t0.429_s1190003.json"
EVAL_CASE = "case-65ee744c"      # designer and analyst agree on the same wrong number


def level_page() -> str:
    import json
    level = Level.from_json(json.loads(LEVEL.read_text(encoding="utf-8")))
    duel = play_duel(level, CasualPlayer(), OpponentBot(level.bot_strength), random.Random(0))
    return to_html(level, "relaxed-05, level 10 (the hardest)", True, duel,
                   "Sample game: casual player vs the level's bot")


SHOTS = [
    # (output, page html, width, height)
    ("level-duel.png", level_page, 820, 1010),
    ("reviewer-eval-summary.png", lambda: (ROOT / "evals/reviewer/report.html").read_text(encoding="utf-8"), 1100, 880),
    ("reviewer-eval-case.png", lambda: eval_report(only=EVAL_CASE), 1100, 760),
]


def browser() -> str:
    named = os.environ.get("CHROME")
    if named:
        return named
    for candidate in (r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
                      r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"):
        path = os.path.expandvars(candidate)
        if os.path.exists(path):
            return path
    for name in ("msedge", "chrome", "chromium", "google-chrome"):
        if shutil.which(name):
            return shutil.which(name)
    sys.exit("no Chromium found; set CHROME to one")


def shoot(exe: str, out: Path, page: Path, width: int, height: int) -> None:
    out.unlink(missing_ok=True)
    for _ in range(3):  # back-to-back headless launches occasionally exit 0 without writing
        # A throwaway profile: without one, a headless launch hands off to an Edge that is
        # already open, exits 0, and writes nothing.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile:
            subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                            f"--user-data-dir={profile}", "--force-device-scale-factor=1",
                            f"--window-size={width},{height}", "--virtual-time-budget=3000",
                            f"--screenshot={out}", page.as_uri()],
                           check=True, capture_output=True, timeout=120)
        for _ in range(20):
            if out.exists() and out.stat().st_size > 0:
                return
            time.sleep(0.25)
    sys.exit(f"screenshot failed: {out}")


def main() -> None:
    exe = browser()
    IMAGES.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, make_page, width, height in SHOTS:
            page = Path(tmp) / f"{Path(name).stem}.html"
            page.write_text(make_page(), encoding="utf-8")
            shoot(exe, IMAGES / name, page, width, height)
            print(f"docs/images/{name}  {width}x{height}")


if __name__ == "__main__":
    main()
