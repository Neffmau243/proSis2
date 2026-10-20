"""Offline WHO 2007 LMS calculation; no network access at runtime."""

import json
from functools import lru_cache
from math import ceil, floor, log
from pathlib import Path


@lru_cache(maxsize=1)
def tables():
    return json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "who2007_lms.json").read_text(
            encoding="utf-8"
        )
    )["tables"]


def lms_z(value: float, power: float, m: float, s: float, *, restricted: bool = True) -> float:
    """WHO computation.pdf: LMS with linear tails beyond ±3 for weight/BMI."""
    z = ((value / m) ** power - 1) / (power * s) if power else log(value / m) / s
    if not restricted or -3 <= z <= 3:
        return z

    def centile(sd):
        return m * (1 + power * s * sd) ** (1 / power)

    if z > 3:
        return 3 + (value - centile(3)) / (centile(3) - centile(2))
    return -3 + (value - centile(-3)) / (centile(-2) - centile(-3))


def score(kind: str, sex: str, months: float, value: float) -> float | None:
    table = tables().get(f"{kind}_{sex}")
    if not table or not 61 <= months <= (120 if kind == "weight" else 228):
        return None
    low, high = floor(months), ceil(months)
    fraction = months - low
    coefficients = [
        a + (b - a) * fraction for a, b in zip(table[str(low)], table[str(high)], strict=True)
    ]
    return lms_z(value, *coefficients, restricted=kind != "height")
