"""
Fix OCR hallucinations where multiple seats in one game share a single-slot demon.
"""

from __future__ import annotations

import sqlite3

from . import db

# Demons that can only appear on one seat per game.
_SINGLE_SLOT_DEMONS = {"legion"}

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
            # Recompute survival from prior rate + bonus survived
            old_g = c["games"] - games
            old_surv = round(c.get("survival_pct", 0) * old_g / 100.0) if old_g else 0
            c["survival_pct"] = (
                round(100.0 * (old_surv + survived) / c["games"], 1) if c["games"] else 0.0
            )
            c["win_pct"] = round(100.0 * c["wins"] / c["games"], 1) if c["games"] else 0.0
        elif games:
            from .reference import get_reference

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


def fix_singleton_demon_duplicates(db_path: str = db.DEFAULT_DB) -> list[dict]:
    """Keep one demon tag per game; demote duplicate seats."""
    fixes: list[dict] = []
    with db.connect(db_path) as conn:
        for demon in _SINGLE_SLOT_DEMONS:
            games = conn.execute(
                """
                SELECT game_id, COUNT(*) AS n
                FROM game_seat
                WHERE character_id = ?
                GROUP BY game_id
                HAVING n > 1
                """,
                (demon,),
            ).fetchall()
            for g in games:
                gid = g["game_id"]
                winner = conn.execute(
                    "SELECT winner FROM game WHERE id = ?", (gid,)
                ).fetchone()["winner"]
                seats = conn.execute(
                    """
                    SELECT id, player_name FROM game_seat
                    WHERE game_id = ? AND character_id = ?
                    ORDER BY id
                    """,
                    (gid, demon),
                ).fetchall()
                keep = seats[0]
                demoted = []
                for s in seats[1:]:
                    won = 1 if winner == "good" else 0
                    conn.execute(
                        """
                        UPDATE game_seat
                        SET character_id = ?,
                            final_alignment = 'good',
                            won = ?,
                            needs_review = 1
                        WHERE id = ?
                        """,
                        (f"unknown:ocr-{demon}-dup", won, s["id"]),
                    )
                    demoted.append(s["player_name"])
                fixes.append(
                    {
                        "game_id": gid,
                        "demon": demon,
                        "kept": keep["player_name"],
                        "demoted": demoted,
                    }
                )
    return fixes
