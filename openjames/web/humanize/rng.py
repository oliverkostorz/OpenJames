"""One seeded RNG + a "persona" per session.

Consistent behaviour within a session (same person: same speed, precision, typing rate),
varied across sessions. `speed` scales every delay; the selftest uses a fast persona.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field


@dataclass
class Persona:
    seed: int
    rng: random.Random = field(repr=False)
    speed: float = 1.0            # multiplies all delays (<1 = faster)
    precision: float = 0.22       # click spread as a fraction of the element's half-size
    wpm: float = 55.0             # typing speed
    typo_rate: float = 0.015      # chance per letter of a typo that is then corrected
    overshoot_rate: float = 0.3   # chance a long move overshoots and corrects
    curvature: float = 1.0        # personal bias of path bending (sign + size)
    hz: float = 90.0              # mouse event rate

    @classmethod
    def new(cls, seed: int | None = None, speed: float | None = None) -> "Persona":
        seed = seed if seed is not None else random.SystemRandom().randrange(1 << 31)
        r = random.Random(seed)
        if speed is None:
            speed = float(os.environ.get("OJ_WEB_SPEED", "1.0"))
        return cls(seed=seed, rng=r, speed=speed,
                   precision=r.uniform(0.15, 0.3), wpm=r.uniform(40, 75),
                   typo_rate=r.uniform(0.0, 0.03), overshoot_rate=r.uniform(0.15, 0.4),
                   curvature=r.choice((-1, 1)) * r.uniform(0.6, 1.4), hz=r.uniform(60, 120))

    # helpers -------------------------------------------------------------------------
    def lognormal(self, median: float, sigma: float = 0.4) -> float:
        """Seconds, log-normally distributed around `median`, scaled by speed."""
        import math
        return self.rng.lognormvariate(math.log(max(median, 1e-4)), sigma) * self.speed

    def gauss_clip(self, mu: float, sd: float, lo: float, hi: float) -> float:
        return min(hi, max(lo, self.rng.gauss(mu, sd)))
