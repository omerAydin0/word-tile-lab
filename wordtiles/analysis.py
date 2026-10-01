"""Evidence about *why* a level plays the way it does, for the analyst agent to reason over.

Everything here is measured, not guessed: features read off the level, and what
the bots actually did. The agent interprets; it never has to invent a number.
"""
from __future__ import annotations

import random
from collections import Counter

from .bots import CASUAL_MAX_LEN, CASUAL_MIN_ZIPF, CasualPlayer, ExpertPlayer, OpponentBot, play_duel
from .generator import Level
from .measure import measure
from .vocab import zipf

RARE = set("JQXZKV")


def features(level: Level) -> dict:
    board = level.board()
    words = [w for w, _ in level.solution]
    letters = Counter(level.tiles.values())
    return {
        "tiles": len(level.tiles),
        "layers": 1 + max(z for _, _, z in level.tiles),
        "free_at_start": len(board.free_tiles()),
        "answer_words": [{"word": w, "zipf": round(zipf(w), 2),
                          "casual_knows": zipf(w) >= CASUAL_MIN_ZIPF and len(w) <= CASUAL_MAX_LEN}
                         for w in words],
        "answer_words_casual_knows": sum(zipf(w) >= CASUAL_MIN_ZIPF and len(w) <= CASUAL_MAX_LEN for w in words),
        "rare_letter_tiles": sum(n for ch, n in letters.items() if ch in RARE),
        "deck": "".join(level.deck),
        "bot_strength": level.bot_strength,
        "bot_vocabulary_size": len(OpponentBot(level.bot_strength).lexicon),
    }


EXPLAIN_TRIALS = 300  # at 100, one fixed seed read 0.63 for a level whose real rate is 0.49 (relaxed-04 L5)


def explain(level: Level, trials: int = EXPLAIN_TRIALS, seed: int = 0, expert_trials: int = 10) -> dict:
    casual = CasualPlayer()
    m = measure(level, casual, seed, trials)
    expert = measure(level, ExpertPlayer(), seed + 1, expert_trials) if expert_trials else None

    # One lost duel, move by move, as a concrete story of how the level beats a player.
    sample_loss = None
    rng = random.Random(seed + 2)
    opponent = OpponentBot(level.bot_strength)
    for _ in range(50):
        duel = play_duel(level, casual, opponent, rng)
        if not duel.won:
            sample_loss = {"moves": [("player" if who == 0 else "bot", what) for who, what in duel.moves],
                           "final_score": {"player": duel.scores[0], "bot": duel.scores[1]},
                           "board_cleared": duel.board_cleared,
                           "player_stuck_with": duel.stuck_letters or None}
            break

    lo, hi = m.interval
    return {
        "features": features(level),
        "casual_vs_bot": {"win_rate": round(m.rate, 3), "ci95": [round(lo, 3), round(hi, 3)],
                          "trials": m.trials, "ties": m.ties,
                          "mean_score_margin": round(m.mean_margin, 1),
                          "passes_with_a_valid_word_available": m.vocabulary_walls,
                          "most_common_stuck_letters": m.stuck_on.most_common(5)},
        "expert_vs_bot": None if expert is None else {"win_rate": round(expert.rate, 3), "trials": expert.trials},
        "sample_casual_loss": sample_loss,
    }
