"""Does the calibration loop's own measurement overstate how many levels hit their band?

Builds the same campaign twice - the original method (60 trials, stop at the first
in-band reading) and the adaptive one - then re-measures every accepted level with
trials the loop never saw. "Claimed" is what the loop believed; "true" is the
independent re-measurement.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wordtiles.calibrate import build_campaign  # noqa: E402

N_LEVELS = int(sys.argv[1]) if len(sys.argv) > 1 else 30
OUT = Path(__file__).resolve().parent.parent / "out"


def summarise(name: str, campaign, seconds: float) -> dict:
    claimed = sum(c.claimed_in_band for c in campaign)
    true = sum(c.truly_in_band for c in campaign)
    overstated = sum(c.claimed_in_band and not c.truly_in_band for c in campaign)
    miss = [abs(c.fresh.rate - min(max(c.fresh.rate, c.target[0]), c.target[1])) for c in campaign]
    return {
        "method": name,
        "levels": len(campaign),
        "claimed_in_band": claimed,
        "true_in_band": true,
        "claimed_but_not_true": overstated,
        "mean_true_miss": round(sum(miss) / len(miss), 4),
        "selection_trials": sum(c.selection.trials for c in campaign),
        "seconds": round(seconds, 1),
        "per_level": [
            {"index": c.index, "t": round(c.level.t, 3), "target": [round(x, 3) for x in c.target],
             "selection_rate": round(c.selection.rate, 3), "selection_trials": c.selection.trials,
             "fresh_rate": round(c.fresh.rate, 3)}
            for c in campaign
        ],
    }


def main() -> None:
    OUT.mkdir(exist_ok=True)
    results = []
    for method in ("fixed", "adaptive"):
        start = time.time()
        campaign = build_campaign(N_LEVELS, method=method)
        results.append(summarise(method, campaign, time.time() - start))
        r = results[-1]
        print(f"{method:9s} claimed {r['claimed_in_band']}/{r['levels']}  true {r['true_in_band']}/{r['levels']}  "
              f"overstated {r['claimed_but_not_true']}  mean miss {r['mean_true_miss']:.3f}  "
              f"trials {r['selection_trials']}  {r['seconds']}s", flush=True)
    (OUT / "calibration_honesty.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
