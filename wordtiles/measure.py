from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass, field

from .bots import OpponentBot, Player, play_duel
from .generator import Level


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


@dataclass
class Measurement:
    """How often a player beats the level's opponent bot. Ties count as not winning."""
    successes: int
    trials: int
    vocabulary_walls: int = 0
    stuck_on: Counter = field(default_factory=Counter)
    ties: int = 0
    margin_total: int = 0      # sum of (player score - bot score)

    @property
    def rate(self) -> float:
        return self.successes / self.trials if self.trials else 0.0

    @property
    def interval(self) -> tuple[float, float]:
        return wilson(self.successes, self.trials)

    @property
    def mean_margin(self) -> float:
        return self.margin_total / self.trials if self.trials else 0.0

    def __add__(self, other: Measurement) -> Measurement:
        return Measurement(self.successes + other.successes, self.trials + other.trials,
                           self.vocabulary_walls + other.vocabulary_walls, self.stuck_on + other.stuck_on,
                           self.ties + other.ties, self.margin_total + other.margin_total)


def measure(level: Level, player: Player, seed: int, trials: int) -> Measurement:
    rng = random.Random(seed)
    opponent = OpponentBot(level.bot_strength)
    m = Measurement(0, 0)
    for _ in range(trials):
        duel = play_duel(level, player, opponent, rng)
        m.trials += 1
        m.successes += duel.won
        m.ties += duel.tie
        m.margin_total += duel.scores[0] - duel.scores[1]
        m.vocabulary_walls += duel.vocabulary_walls
        if not duel.won and duel.stuck_letters:
            m.stuck_on[duel.stuck_letters] += 1
    return m


def measure_until_decided(level: Level, player: Player, seed: int, band: tuple[float, float],
                          batch: int = 20, max_trials: int = 200) -> Measurement:
    """Keeps sampling until the 95% interval sits clearly inside or clearly outside `band`.

    A fixed 60 trials leaves roughly +/-13 points of noise around 50%, more than a +/-10
    band, so a fixed sample size decides in-band/out-of-band by luck near the edges.
    """
    lo, hi = band
    total = Measurement(0, 0)
    while total.trials < max_trials:
        total = total + measure(level, player, seed + total.trials, batch)
        a, b = total.interval
        if (lo <= a and b <= hi) or b < lo or a > hi:
            break
    return total
