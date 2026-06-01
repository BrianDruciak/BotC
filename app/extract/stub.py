"""
Deterministic offline extractor.

Generates a plausible grimoire from the canonical character pool so the whole
pipeline (import -> resolve -> commit -> stats -> UI) can be exercised without a
vision API key or real screenshots. Output is seeded by the image bytes so the same
"image" always yields the same game.
"""

from __future__ import annotations

import hashlib
import random

from ..reference import get_reference
from .base import Extractor, GameExtraction, SeatExtraction

_PLAYER_POOL = [
    "Alex", "Sam", "Jordan", "Taylor", "Casey", "Riley", "Morgan", "Jamie",
    "Drew", "Quinn", "Avery", "Parker", "Reese", "Skyler", "Charlie",
]


class StubExtractor(Extractor):
    def extract(self, image_bytes_list, winner_hint=None) -> GameExtraction:
        ref = get_reference()
        seed_src = b"".join(image_bytes_list) or b"empty"
        seed = int(hashlib.sha256(seed_src).hexdigest(), 16)
        rng = random.Random(seed)

        n = rng.choice([7, 8, 9, 10, 12])
        townsfolk = [c for c in ref.characters if c.type == "townsfolk"]
        outsiders = [c for c in ref.characters if c.type == "outsider"]
        minions = [c for c in ref.characters if c.type == "minion"]
        demons = [c for c in ref.characters if c.type == "demon"]

        n_minion = 1 if n < 9 else (2 if n < 12 else 3)
        n_outsider = rng.choice([0, 1, 1, 2])
        n_townsfolk = n - n_minion - 1 - n_outsider

        picks = (
            rng.sample(townsfolk, min(n_townsfolk, len(townsfolk)))
            + rng.sample(outsiders, min(n_outsider, len(outsiders)))
            + rng.sample(minions, min(n_minion, len(minions)))
            + rng.sample(demons, 1)
        )
        rng.shuffle(picks)

        names = rng.sample(_PLAYER_POOL, len(picks))
        seats = []
        for i, (c, nm) in enumerate(zip(picks, names)):
            seats.append(
                SeatExtraction(
                    player_name=nm,
                    character_text=c.name,
                    alignment_hint=c.alignment if c.alignment in ("good", "evil") else None,
                    is_alive=rng.random() > 0.4,
                    reminder_tokens=["DEAD"] if rng.random() > 0.6 else [],
                    confidence=round(rng.uniform(0.82, 0.99), 2),
                    seat_index=i,
                )
            )

        winner = winner_hint or rng.choice(["good", "evil"])
        return GameExtraction(winner=winner, script=None, seats=seats, raw={"stub": True})
