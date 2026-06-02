"""
Manual character-stat corrections (bonuses for unlogged appearances).

Legion is NOT deduplicated here — multiple evil seats can all be Legion in one game.
See stats._PER_GAME_CHARACTER_STATS for per-game win-rate counting.
"""

from __future__ import annotations

from .reference import get_reference

# Extra games/wins missing from OCR import (character_id -> bonus counts).
CHARACTER_BONUSES: dict[str, dict[str, int]] = {
    "vortox": {"games": 1, "wins": 1, "survived": 1},
    "scapegoat": {"wins": 3},
    "apprentice": {"wins": 1},
    "gunslinger": {"wins": 1},
}


def apply_character_bonuses(char_stats: list[dict]) -> list[dict]:
    """Apply manual corrections for unlogged character appearances."""
    by_id = {c["id"]: dict(c) for c in char_stats}

    for cid, bonus in CHARACTER_BONUSES.items():
        games = bonus.get("games", 0)
        wins = bonus.get("wins", 0)
        survived = bonus.get("survived", wins)
        if cid in by_id:
            c = by_id[cid]
            c["games"] += games
            c["wins"] += wins
            c["losses"] = c["games"] - c["wins"]
            old_g = c["games"] - games
            old_surv = round(c.get("survival_pct", 0) * old_g / 100.0) if old_g else 0
            c["survival_pct"] = (
                round(100.0 * (old_surv + survived) / c["games"], 1) if c["games"] else 0.0
            )
            c["win_pct"] = round(100.0 * c["wins"] / c["games"], 1) if c["games"] else 0.0
        elif games:
            c = get_reference().get(cid)
            if c:
                by_id[cid] = {
                    "id": cid,
                    "name": c.name,
                    "type": c.type,
                    "alignment": c.alignment,
                    "editions": c.editions,
                    "icon_path": c.icon_path,
                    "games": games,
                    "wins": wins,
                    "losses": games - wins,
                    "win_pct": round(100.0 * wins / games, 1) if games else 0.0,
                    "survival_pct": round(100.0 * survived / games, 1) if games else 0.0,
                }

    out = list(by_id.values())
    out.sort(key=lambda d: (-d["win_pct"], -d["games"], d["name"]))
    return out
