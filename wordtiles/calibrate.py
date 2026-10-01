"""Closed-loop campaign calibration, ported from AlchemyMatch's CampaignLevels.

Generate a candidate at difficulty knob t, measure how often a casual
player beats the level's opponent bot, nudge t toward the target band, repeat.
The target curve is the original's, so the two systems aim at the same shape;
its t-space starting points are not, because t means something else here.
"""
from __future__ import annotations

from dataclasses import dataclass

from .bots import CasualPlayer, Player
from .generator import Level, generate, verify
from .measure import Measurement, measure, measure_until_decided

CHAPTER = 10
TARGET_SUCCESS = [0.90, 0.75, 0.65, 0.55, 0.30, 0.65, 0.50, 0.35, 0.15, 0.06]
TARGET_BAND = 0.10
CHAPTER_DROP = 0.07
TARGET_FLOOR = 0.02
ITERATIONS = 10

FIXED_TRIALS = 60       # the original's sample size
FRESH_TRIALS = 300      # independent re-measurement used to grade the result


@dataclass
class CalibratedLevel:
    index: int
    level: Level
    target: tuple[float, float]
    selection: Measurement      # the measurement the loop decided on
    fresh: Measurement | None   # an independent one, on seeds the loop never saw

    @property
    def claimed_in_band(self) -> bool:
        lo, hi = self.target
        return lo <= self.selection.rate <= hi

    @property
    def truly_in_band(self) -> bool:
        lo, hi = self.target
        return self.fresh is not None and lo <= self.fresh.rate <= hi


def position(index: int) -> tuple[int, int]:
    return (index - 1) % CHAPTER, (index - 1) // CHAPTER


def target_range(index: int, targets: list[float] | None = None) -> tuple[float, float]:
    """Band around this level's target casual win rate. `targets` is one rate per chapter
    position (10 values); each later chapter is CHAPTER_DROP harder."""
    pos, chapter = position(index)
    centre = max(TARGET_FLOOR, (targets or TARGET_SUCCESS)[pos] - chapter * CHAPTER_DROP)
    return max(0.0, centre - TARGET_BAND), min(1.0, centre + TARGET_BAND)


def initial_t(index: int, targets: list[float] | None = None) -> float:
    """Where the search starts: a rough inverse of how the casual win rate falls with t,
    read off a sweep (about 0.85 at t=0, about zero by t=0.8). Only a starting guess."""
    lo, hi = target_range(index, targets)
    return max(0.0, min(1.0, (0.85 - (lo + hi) / 2) / 1.05))


def _distance(rate: float, band: tuple[float, float]) -> float:
    lo, hi = band
    return lo - rate if rate < lo else (rate - hi if rate > hi else 0.0)


def calibrate_level(index: int, base_seed: int, method: str = "adaptive",
                    player: Player | None = None, fresh_trials: int = FRESH_TRIALS,
                    targets: list[float] | None = None) -> CalibratedLevel:
    """`method="fixed"` reproduces the original (60 trials, stop at the first in-band
    reading); `method="adaptive"` samples until the interval decides in or out."""
    player = player or CasualPlayer()
    band = target_range(index, targets)
    t, step = initial_t(index, targets), 0.25
    best: tuple[float, Level, Measurement] | None = None

    for it in range(ITERATIONS):
        seed = base_seed + index * 10_000 + it
        candidate = generate(t, seed)
        if not verify(candidate):          # cannot happen by construction; kept as the hard gate
            t, step = max(0.0, t - step), step * 0.7
            continue

        mseed = base_seed + index * 31_337 + it * 1_000
        if method == "fixed":
            m = measure(candidate, player, mseed, FIXED_TRIALS)
        else:
            m = measure_until_decided(candidate, player, mseed, band)

        d = _distance(m.rate, band)
        if best is None or d < best[0]:
            best = (d, candidate, m)
        if d <= 0.0:
            break
        t = min(1.0, t + step) if m.rate > band[1] else max(0.0, t - step)
        step *= 0.7

    _, level, selection = best
    fresh = None
    if fresh_trials:
        fresh = measure(level, player, base_seed + index * 7_777_777 + 999, fresh_trials)
    return CalibratedLevel(index, level, band, selection, fresh)


def build_campaign(n_levels: int, base_seed: int = 90_000, method: str = "adaptive",
                   fresh_trials: int = FRESH_TRIALS) -> list[CalibratedLevel]:
    player = CasualPlayer()
    return [calibrate_level(i, base_seed, method, player, fresh_trials) for i in range(1, n_levels + 1)]
