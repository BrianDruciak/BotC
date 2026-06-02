"""Regenerate data/manual_player_stats.json from the games database.

WARNING: The manual sheet is the authoritative source for player stats.
Only run this if you intentionally want to overwrite the sheet from the DB.
Prefer scripts/apply_three_to_manual.py-style deltas instead.
"""

from __future__ import annotations

import json
import os

from app import db
from app.manual_stats import DEFAULT_JSON, manual_player_names
from app.players import stats_real_games_sql


def _pct(wins: int, games: int) -> float | None:
    return round(100.0 * wins / games, 1) if games else None


def aggregate_from_db(db_path: str = db.DEFAULT_DB) -> dict[str, dict]:
    real = stats_real_games_sql()
    with db.connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT p.canonical_name AS name,
                   COUNT(*) AS games,
                   SUM(s.won) AS wins,
                   SUM(CASE WHEN s.final_alignment='good' THEN 1 ELSE 0 END) AS good_games,
                   SUM(CASE WHEN s.final_alignment='good' THEN s.won ELSE 0 END) AS good_wins,
                   SUM(CASE WHEN s.final_alignment='evil' THEN 1 ELSE 0 END) AS evil_games,
                   SUM(CASE WHEN s.final_alignment='evil' THEN s.won ELSE 0 END) AS evil_wins
            FROM game_seat s
            JOIN game g ON g.id = s.game_id
            JOIN player p ON p.id = s.player_id
            WHERE {real}
            GROUP BY p.id
            """
        ).fetchall()

    out: dict[str, dict] = {}
    for r in rows:
        games = int(r["games"] or 0)
        wins = int(r["wins"] or 0)
        good_g = int(r["good_games"] or 0)
        evil_g = int(r["evil_games"] or 0)
        good_w = int(r["good_wins"] or 0)
        evil_w = int(r["evil_wins"] or 0)
        out[r["name"]] = {
            "name": r["name"],
            "games": games,
            "wins": wins,
            "losses": games - wins,
            "win_pct": _pct(wins, games) or 0.0,
            "good_games": good_g,
            "good_win_pct": _pct(good_w, good_g),
            "evil_games": evil_g,
            "evil_win_pct": _pct(evil_w, evil_g),
        }
    return out


def export_manual_stats(
    db_path: str = db.DEFAULT_DB,
    out_path: str = DEFAULT_JSON,
    *,
    keep_zero_players: bool = True,
) -> dict:
    """Write manual_player_stats.json from DB; preserve manual roster + add new DB players."""
    db_stats = aggregate_from_db(db_path)
    allowed = manual_player_names() or set()

    # Preserve manual roster order from existing file; append new DB names at end.
    existing_order: list[str] = []
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as fh:
            existing_order = [p["name"] for p in json.load(fh).get("players", [])]

    new_in_db = sorted(set(db_stats) - set(existing_order) - allowed)
    names = existing_order + [n for n in new_in_db if n not in existing_order]

    if keep_zero_players:
        for n in allowed:
            if n not in names:
                names.append(n)

    players: list[dict] = []
    for name in names:
        if name in db_stats:
            players.append(db_stats[name])
        elif keep_zero_players and name in allowed:
            players.append(
                {
                    "name": name,
                    "games": 0,
                    "wins": 0,
                    "losses": 0,
                    "win_pct": 0.0,
                    "good_games": 0,
                    "good_win_pct": None,
                    "evil_games": 0,
                    "evil_win_pct": None,
                }
            )

    # Any DB player not yet included (e.g. new guest like 4b)
    for name in sorted(db_stats):
        if name not in {p["name"] for p in players}:
            players.append(db_stats[name])

    players.sort(key=lambda p: (-p["win_pct"], -p["games"], p["name"].lower()))

    payload = {"players": players}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    return {
        "players": len(players),
        "seats": sum(p["games"] for p in players),
        "added": new_in_db,
        "path": out_path,
    }


def main() -> None:
    info = export_manual_stats()
    print(f"Wrote {info['path']}: {info['players']} players, {info['seats']} seat appearances")
    if info["added"]:
        print("New players added:", ", ".join(info["added"]))


if __name__ == "__main__":
    main()
