"""Shared test helpers. All data here is synthetic: no real queries, shops or people."""
from __future__ import annotations

import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "google-trends" / "scripts"
sys.path.insert(0, str(SCRIPTS))

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def weekly_dates(weeks: int = 260, end: date = date(2026, 10, 18)) -> list[str]:
    """Sundays, oldest first, ending at `end`."""
    return [(end - timedelta(weeks=weeks - 1 - i)).isoformat() for i in range(weeks)]


def make_series(shape: str, weeks: int = 260, seed: int = 7) -> tuple[list[str], list[int]]:
    rnd = random.Random(seed)
    dates = weekly_dates(weeks)
    vals: list[float] = []
    for i, d in enumerate(dates):
        month = int(d[5:7])
        t = i / (weeks - 1)
        noise = rnd.uniform(-3, 3)
        if shape == "growing":
            v = 20 + 70 * t + noise
        elif shape == "stable":
            v = 50 + noise
        elif shape == "declining":
            v = 90 - 65 * t + noise
        elif shape == "seasonal":  # winter heater: peak in December
            v = 12 + 70 * max(0.0, math.cos((month - 12) / 12 * 2 * math.pi)) ** 2 + noise
        elif shape == "seasonal_growing":
            v = (10 + 30 * t) * (1 + 2.2 * max(0.0, math.cos((month - 12) / 12 * 2 * math.pi)) ** 2) + noise
        elif shape == "fad":
            peak_i = int(weeks * 0.35)
            v = 4 + 95 * math.exp(-((i - peak_i) ** 2) / (2 * 6 ** 2)) + abs(noise) * 0.3
        elif shape == "sparse":
            v = 40 if rnd.random() < 0.3 else 0
        elif shape == "growing_exp":
            v = 8 * math.exp(2.4 * t) + noise
        else:
            raise ValueError(shape)
        vals.append(max(0, min(100, round(v))))
    peak = max(vals) or 1
    return dates, [round(v * 100 / peak) for v in vals]
