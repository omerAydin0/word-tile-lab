"""A level as a self-contained HTML page: the board in its layers, the deck, the opponent, the answers."""
from __future__ import annotations

import html
from pathlib import Path

from .bots import Duel
from .generator import Level
from .rules import POINTS

TILE_W, TILE_H, LAYER_SHIFT = 46, 58, 6


def duel_html(duel: Duel, caption: str) -> str:
    """A duel move by move, with the running score, so the page shows the game being played."""
    rows, score = [], [0, 0]
    turn = 0
    for who, move in duel.moves:
        name = "Player" if who == 0 else "Bot"
        if move == "pass":
            what, pts = "passes", ""
        elif move.startswith("draw "):
            what, pts = f"draws <b>{html.escape(move[5:])}</b> from the deck", ""
        else:
            turn += 1
            gained = POINTS[len(move)]
            score[who] += gained
            what, pts = f"<b>{html.escape(move)}</b>", f"+{gained}"
        rows.append(f'<tr class="{"p" if who == 0 else "b"}"><td>{name}</td><td>{what}</td>'
                    f'<td class="num">{pts}</td><td class="num">{score[0]} &ndash; {score[1]}</td></tr>')
    p, b = duel.scores
    verdict = "Player wins" if p > b else ("Bot wins" if b > p else "Tie")
    ending = "board cleared" if duel.board_cleared else "both players passed with tiles left"
    return (f'<h3>{html.escape(caption)}</h3>'
            f'<table class="duel"><thead><tr><th>who</th><th>move</th><th class="num">points</th>'
            f'<th class="num">score (player &ndash; bot)</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'
            f'<p><b>{verdict} {p}&ndash;{b}</b> &middot; {ending}</p>')


def to_html(level: Level, title: str = "", reveal_answers: bool = True,
            duel: Duel | None = None, duel_caption: str = "Sample duel") -> str:
    board = level.board()
    free = set(board.free_tiles())
    visible = set(board.visible_tiles())
    xs = [x for x, _, _ in level.tiles]
    ys = [y for _, y, _ in level.tiles]
    width = (max(xs) + 1) * TILE_W + 40
    height = (max(ys) + 1) * TILE_H + 40

    tiles = []
    for (x, y, z), ch in sorted(level.tiles.items(), key=lambda kv: (kv[0][2], kv[0][1], kv[0][0])):
        left = 10 + x * TILE_W - z * LAYER_SHIFT
        top = 20 + y * TILE_H - z * LAYER_SHIFT
        pos = (x, y, z)
        if pos in free:
            cls, label = "tile free", html.escape(ch)
        elif pos in visible:
            cls, label = "tile blocked", html.escape(ch)
        else:
            cls, label = "tile covered", ""   # a player can't read a covered tile, so neither can the page
        tiles.append(f'<div class="{cls}" style="left:{left}px;top:{top}px;z-index:{z * 100 + y}" '
                     f'title="({x},{y},{z})">{label}</div>')

    deck = "".join(f'<span class="chip">{html.escape(ch)}</span>' for ch in level.deck)
    answers = ", ".join(html.escape(w) for w, _ in level.solution)
    heading = html.escape(title or f"t={level.t:.2f} seed={level.seed}")
    answers_block = f"<p><b>Answer words (in a solving order):</b> {answers}</p>" if reveal_answers else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{heading}</title>
<style>
:root {{ --bg:#f6f1e7; --tile:#fffdf8; --edge:#b9a98a; --free:#2f6f4f; --ink:#2b2620; --muted:#a39886; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#1d1b18; --tile:#2c2925; --edge:#5b5246; --free:#7fd1a5; --ink:#eee6d8; --muted:#7d7466; }} }}
body {{ background:var(--bg); color:var(--ink); font:15px system-ui,sans-serif; margin:24px; }}
.board {{ position:relative; width:{width}px; height:{height}px; max-width:100%; overflow:auto; }}
.tile {{ position:absolute; width:{TILE_W - 6}px; height:{TILE_H - 6}px; background:var(--tile);
  border:1px solid var(--edge); border-radius:7px; box-shadow:2px 3px 0 var(--edge);
  display:flex; align-items:center; justify-content:center; font-weight:700; font-size:22px; }}
.tile.free {{ border-color:var(--free); box-shadow:2px 3px 0 var(--free); }}
.tile.blocked {{ color:var(--muted); }}
.tile.covered {{ background:var(--edge); }}
.chip {{ display:inline-block; min-width:26px; padding:4px; margin:2px; text-align:center;
  border:1px solid var(--edge); border-radius:5px; font-weight:700; background:var(--tile); }}
.duel {{ border-collapse:collapse; min-width:min(520px,100%); }}
.duel th, .duel td {{ padding:4px 10px; border-bottom:1px solid var(--edge); text-align:left; }}
.duel .num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.duel tr.b td:first-child {{ color:var(--muted); }}
.duel tr.p td:first-child {{ color:var(--free); font-weight:700; }}
</style></head><body>
<h2>{heading}</h2>
<p>{len(level.tiles)} tiles &middot; opponent bot strength {level.bot_strength:.2f} &middot;
green edge = free now &middot; grey letter = visible but blocked &middot; blank = covered</p>
<div class="board">{''.join(tiles)}</div>
<p><b>Deck</b> (face down in the game; next draw first): {deck or '(empty)'}</p>
{answers_block}
{duel_html(duel, duel_caption) if duel else ""}
</body></html>"""


def write(level: Level, path: Path, title: str = "", reveal_answers: bool = True,
          duel: Duel | None = None, duel_caption: str = "Sample duel") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_html(level, title, reveal_answers, duel, duel_caption), encoding="utf-8")
    return path
