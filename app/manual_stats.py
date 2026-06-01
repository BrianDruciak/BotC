"""
Authoritative player win rates from the committed manual stats file.

Player stats are served from data/manual_player_stats.json instead of aggregating
OCR game_seat rows (which include hallucinated names/seats).
"""

from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_JSON = os.path.join(ROOT, "data", "manual_player_stats.json")


def manual_stats_path() -> str:
    return os.environ.get("MANUAL_STATS_JSON", DEFAULT_JSON)


def load_manual_players(min_games: int = 0) -> list[dict] | None:
    path = manual_stats_path()
    if not os.path.exists(path):
        return None

    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)

    out: list[dict] = []
    for row_idx, row in enumerate(payload.get("players", []), start=1):
        games = int(row["games"])
        if games < min_games:
            continue
        out.append(
            {
                "id": row_idx,
                "name": row["name"],
                "games": games,
                "wins": int(row["wins"]),
                "losses": int(row["losses"]),
                "win_pct": float(row["win_pct"]),
                "good_games": int(row["good_games"]),
                "good_win_pct": row.get("good_win_pct"),
                "evil_games": int(row["evil_games"]),
                "evil_win_pct": row.get("evil_win_pct"),
                "source": "manual",
            }
        )

    out.sort(key=lambda d: (-d["win_pct"], -d["games"], d["name"]))
    return out


def manual_player_names() -> set[str] | None:
    players = load_manual_players(min_games=0)
    if players is None:
        return None
    return {p["name"] for p in players}


def get_manual_player(player_id: int) -> dict | None:
    players = load_manual_players(min_games=0)
    if not players:
        return None
    for p in players:
        if p["id"] == player_id:
            return p
    return None
