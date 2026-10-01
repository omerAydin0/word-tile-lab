"""MCP server: the deterministic half of the level team, as tools agents can call.

Agents decide and explain; these tools generate, measure and verify. Nothing an
agent says about a level is trusted unless a tool here produced it.
"""
from __future__ import annotations

import random
import time

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from . import store, wordlists
from .analysis import explain
from .bots import CasualPlayer, ExpertPlayer, OpponentBot, play_duel
from .calibrate import calibrate_level
from .generator import generate, verify
from .measure import measure
from .render import write as write_html
from .vocab import full_lexicon, zipf

READ = ToolAnnotations(read_only_hint=True, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False)

MAX_CAMPAIGN = 50
FRESH_TRIALS = 200

server = MCPServer(
    "wordtiles",
    instructions=(
        "Word-tile level lab. A level is a Mahjong-style board of letter tiles that the player and "
        "an opponent bot share, taking turns (player first), plus a face-down deck; longer words "
        "score more and the higher score wins when the board is empty. Difficulty is how often a "
        "casual-player bot beats the level's opponent bot. Typical flow: calibrate_campaign -> "
        "campaign_report -> review_queue / record_word_decisions -> regenerate_level for any level "
        "using a blocked word -> release_check. explain_level gives measured evidence for why a level "
        "is hard. Never state a win rate or solvability you did not get from a tool."
    ),
)


def _summary(level, lid: str) -> dict:
    return {"level_id": lid, "t": round(level.t, 3), "tiles": len(level.tiles),
            "answer_words": [w for w, _ in level.solution], "deck": "".join(level.deck),
            "bot_strength": level.bot_strength, "verified_clearable": verify(level)}


@server.tool(annotations=WRITE)
def generate_level(t: float, seed: int) -> dict:
    """Generate one level at difficulty knob t (0 easiest .. 1 hardest) and save it.
    The board can be cleared by construction; `verified_clearable` replays the certificate.
    t also sets the opponent bot's strength and how helpful the deck is."""
    if not 0.0 <= t <= 1.0:
        raise ValueError("t must be between 0 and 1")
    level = generate(t, seed)
    return _summary(level, store.save_level(level))


@server.tool(annotations=READ)
def get_level(level_id: str) -> dict:
    """Full level data: tiles [x,y,z,letter], deck (next draw first), opponent bot strength,
    and answer words in a clearing order."""
    return store.load_level(level_id).to_json()


@server.tool(annotations=READ)
def measure_level(level_id: str, player: str = "casual", trials: int = 100, seed: int = 0) -> dict:
    """How often a player beats the level's opponent bot over `trials` duels, with a 95%
    interval. player: 'casual' (the difficulty signal) or 'expert' (fairness check, max 30)."""
    level = store.load_level(level_id)
    if player == "casual":
        bot, cap = CasualPlayer(), 1000
    elif player == "expert":
        bot, cap = ExpertPlayer(), 30
    else:
        raise ValueError("player must be 'casual' or 'expert'")
    m = measure(level, bot, seed, max(1, min(trials, cap)))
    lo, hi = m.interval
    return {"level_id": level_id, "player": player, "win_rate": round(m.rate, 3),
            "ci95": [round(lo, 3), round(hi, 3)], "trials": m.trials, "ties": m.ties,
            "mean_score_margin": round(m.mean_margin, 1),
            "passes_with_a_valid_word_available": m.vocabulary_walls,
            "most_common_stuck_letters": m.stuck_on.most_common(5)}


@server.tool(annotations=READ)
def explain_level(level_id: str, trials: int = 300) -> dict:
    """Measured evidence for why a level plays as it does: features, casual and expert win
    rates against the opponent bot (with 95% intervals), score margins, where casual players
    get stuck, and one lost duel move by move. Deterministic for a given level and `trials`,
    so others can re-run it - which also means it is one fixed sample: read rates with
    their interval, not as exact values."""
    return explain(store.load_level(level_id), trials=max(20, min(trials, 500)))


@server.tool(annotations=WRITE)
def calibrate_campaign(name: str, n_levels: int = 10, base_seed: int = 90_000,
                       chapter_targets: list[float] | None = None) -> dict:
    """Build a campaign of n_levels (max 50), each level calibrated so the casual player's win
    rate against the opponent bot lands within +/-0.10 of its target, then re-measured on
    fresh seeds the calibration never saw. Takes several seconds per level.

    chapter_targets: optional 10 casual win rates vs the bot (0-1), one per position in each 10-level
    chapter; every later chapter is 0.07 harder. Omit for the default curve
    [0.90, 0.75, 0.65, 0.55, 0.30, 0.65, 0.50, 0.35, 0.15, 0.06]."""
    store.safe_name(name)
    if chapter_targets is not None:
        if len(chapter_targets) != 10 or not all(0.0 <= x <= 1.0 for x in chapter_targets):
            raise ValueError("chapter_targets must be 10 numbers between 0 and 1")
    n_levels = max(1, min(n_levels, MAX_CAMPAIGN))
    started = time.time()
    player = CasualPlayer()
    entries = []
    for i in range(1, n_levels + 1):
        c = calibrate_level(i, base_seed, "adaptive", player, FRESH_TRIALS, chapter_targets)
        entries.append(_entry(c, store.save_level(c.level)))
    store.save_campaign(name, {"name": name, "base_seed": base_seed,
                               "chapter_targets": chapter_targets, "levels": entries})
    return {"name": name, "levels": n_levels, "seconds": round(time.time() - started, 1),
            "in_band_on_fresh_trials": sum(e["fresh_in_band"] for e in entries)}


def _entry(c, lid: str) -> dict:
    lo, hi = c.target
    return {"index": c.index, "level_id": lid, "target": [round(lo, 3), round(hi, 3)],
            "calibration_rate": round(c.selection.rate, 3), "calibration_trials": c.selection.trials,
            "fresh_rate": round(c.fresh.rate, 3), "fresh_trials": c.fresh.trials,
            "fresh_in_band": c.truly_in_band}


@server.tool(annotations=READ)
def campaign_report(name: str) -> dict:
    """The campaign's chapter_targets, and per level: target band, calibrated and fresh win
    rates, regenerations, and each answer word's review status."""
    campaign = store.load_campaign(name)
    rows = []
    for e in campaign["levels"]:
        level = store.load_level(e["level_id"])
        rows.append({**e, "tiles": len(level.tiles),
                     "answer_words": {w: wordlists.status(w) for w, _ in level.solution}})
    return {"name": name, "chapter_targets": campaign.get("chapter_targets"), "levels": rows}


@server.tool(annotations=READ)
def review_queue(name: str) -> dict:
    """Answer words in a campaign that nobody has reviewed yet - the words players would see."""
    campaign = store.load_campaign(name)
    pending: dict[str, list[int]] = {}
    for e in campaign["levels"]:
        for w, _ in store.load_level(e["level_id"]).solution:
            if wordlists.status(w) == "unreviewed":
                pending.setdefault(w, []).append(e["index"])
    return {"name": name, "unreviewed": [{"word": w, "zipf": round(zipf(w), 2), "levels": lv}
                                         for w, lv in sorted(pending.items())]}


@server.tool(annotations=WRITE)
def record_word_decisions(words: list[str], decision: str, reason: str) -> dict:
    """Record an editorial decision for answer words: decision 'approve' or 'block', with a
    short reason. Blocked words are never used as answers by the generator again."""
    return wordlists.record(words, decision, reason)


@server.tool(annotations=READ)
def check_words(words: list[str]) -> dict:
    """For each word: accepted by the game's dictionary?, frequency (zipf), review status."""
    lex = full_lexicon()
    return {"words": [{"word": w.upper(), "accepted": w.upper() in lex, "zipf": round(zipf(w), 2),
                       "status": wordlists.status(w)} for w in words]}


REGENERATION_REASONS = ("blocked_word", "difficulty")


def _regenerations(entry: dict) -> dict[str, int]:
    counts = entry.get("regenerations", {})
    if isinstance(counts, int):              # campaigns built before reasons were recorded
        return {"unspecified": counts}
    return dict(counts)


@server.tool(annotations=WRITE)
def regenerate_level(name: str, index: int, reason: str) -> dict:
    """Recalibrate one campaign level with a new seed. reason: 'blocked_word' (an answer
    word was blocked - a content fix) or 'difficulty' (another try at the target band).
    The result counts each reason separately, so a limit on difficulty retries isn't used
    up by word fixes."""
    if reason not in REGENERATION_REASONS:
        raise ValueError(f"reason must be one of {REGENERATION_REASONS}")
    campaign = store.load_campaign(name)
    entry = next((e for e in campaign["levels"] if e["index"] == index), None)
    if entry is None:
        raise KeyError(f"campaign {name!r} has no level {index}")
    counts = _regenerations(entry)
    attempt = sum(counts.values()) + 1
    c = calibrate_level(index, campaign["base_seed"] + attempt * 1_000_003, "adaptive",
                        CasualPlayer(), FRESH_TRIALS, campaign.get("chapter_targets"))
    new = _entry(c, store.save_level(c.level))
    counts[reason] = counts.get(reason, 0) + 1
    new["regenerations"] = counts
    campaign["levels"] = [new if e["index"] == index else e for e in campaign["levels"]]
    store.save_campaign(name, campaign)
    return new


@server.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False,
                                         idempotent_hint=False, open_world_hint=False))
def submit_report(campaign: str, author: str, text: str) -> dict:
    """Store your full report for a campaign as a new version (earlier versions are kept,
    never overwritten). author: 'designer', 'curator' or 'analyst'. Returns the version and
    a sha256 fingerprint; the release reviewer reads the stored report itself."""
    return store.save_report(campaign, author, text)


@server.tool(annotations=READ)
def read_report(campaign: str, author: str, version: int | None = None) -> dict:
    """Read a stored report: the latest version unless `version` is given. Returns the text,
    its version, how many versions exist, its sha256 fingerprint, when it was submitted, and
    `campaign_changed_after_report` - true when a level was regenerated (or the campaign
    otherwise saved) after the report was written, so its numbers may describe old levels."""
    return store.load_report(campaign, author, version)


@server.tool(annotations=READ)
def release_check(name: str) -> dict:
    """The ship gate. Fails if any board cannot be cleared, any answer word is blocked
    or unreviewed, or fewer than 80% of levels land in band on fresh trials."""
    campaign = store.load_campaign(name)
    problems = []
    in_band = 0
    for e in campaign["levels"]:
        level = store.load_level(e["level_id"])
        if not verify(level):
            problems.append(f"level {e['index']}: certificate does not replay")
        for w, _ in level.solution:
            s = wordlists.status(w)
            if s != "approved":
                problems.append(f"level {e['index']}: answer word {w} is {s}")
        in_band += bool(e["fresh_in_band"])
    share = in_band / len(campaign["levels"])
    if share < 0.8:
        problems.append(f"only {in_band}/{len(campaign['levels'])} levels in band on fresh trials")
    return {"name": name, "pass": not problems, "in_band": f"{in_band}/{len(campaign['levels'])}",
            "problems": problems}


@server.tool(annotations=WRITE)
def render_level(level_id: str, reveal_answers: bool = True, sample_duel_seed: int | None = 0) -> dict:
    """Write the level as an HTML page: the board by layer (free tiles highlighted), the deck,
    and one casual-player-vs-bot duel move by move with the running score. Pass
    sample_duel_seed=None to leave the duel out; other seeds show other games."""
    level = store.load_level(level_id)
    duel = caption = None
    if sample_duel_seed is not None:
        duel = play_duel(level, CasualPlayer(), OpponentBot(level.bot_strength), random.Random(sample_duel_seed))
        caption = f"Sample duel: casual player vs the level's bot (seed {sample_duel_seed})"
    path = write_html(level, store.OUT_DIR / "render" / f"{level_id}.html", level_id, reveal_answers,
                      duel, caption or "")
    return {"path": str(path), "sample_duel": None if duel is None else
            {"player": duel.scores[0], "bot": duel.scores[1], "moves": len(duel.moves)}}


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
