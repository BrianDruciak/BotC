"""
Win-rate aggregations.

Character win rates are keyed on the STARTING role (game_seat.character_id) per the
attribution decision. Fabled/Loric seats are excluded (storyteller pieces).
"""

from __future__ import annotations

from . import db
from .reference import get_reference


def _eligible_char_ids() -> set[str]:
    ref = get_reference()
    return {c.id for c in ref.characters if ref.stats_eligible(c.id)}


def character_stats(db_path: str = db.DEFAULT_DB, min_games: int = 0) -> list[dict]:
    ref = get_reference()
    eligible = _eligible_char_ids()
    with db.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT character_id,
                   COUNT(*)              AS games,
                   SUM(won)              AS wins,
                   SUM(1 - won)          AS losses,
                   SUM(is_alive_at_end)  AS survived
            FROM game_seat
            GROUP BY character_id
            """
        ).fetchall()

    out = []
    for r in rows:
        cid = r["character_id"]
        if cid not in eligible:
            continue
        c = ref.get(cid)
        games = r["games"] or 0
        wins = r["wins"] or 0
        if games < min_games:
            continue
        out.append(
            {
                "id": cid,
                "name": c.name if c else cid,
                "type": c.type if c else "unknown",
                "alignment": c.alignment if c else "?",
                "editions": c.editions if c else [],
                "icon_path": c.icon_path if c else "",
                "games": games,
                "wins": wins,
                "losses": r["losses"] or 0,
                "win_pct": round(100.0 * wins / games, 1) if games else 0.0,
                "survival_pct": round(100.0 * (r["survived"] or 0) / games, 1) if games else 0.0,
            }
        )
    out.sort(key=lambda d: (-d["win_pct"], -d["games"], d["name"]))
    return out


def player_stats(db_path: str = db.DEFAULT_DB, min_games: int = 0) -> list[dict]:
    with db.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT p.id, p.canonical_name AS name,
                   COUNT(*)                                   AS games,
                   SUM(s.won)                                 AS wins,
                   SUM(CASE WHEN s.final_alignment='good' THEN 1 ELSE 0 END)         AS good_games,
                   SUM(CASE WHEN s.final_alignment='good' THEN s.won ELSE 0 END)     AS good_wins,
                   SUM(CASE WHEN s.final_alignment='evil' THEN 1 ELSE 0 END)         AS evil_games,
                   SUM(CASE WHEN s.final_alignment='evil' THEN s.won ELSE 0 END)     AS evil_wins
            FROM game_seat s
            JOIN player p ON p.id = s.player_id
            GROUP BY p.id
            """
        ).fetchall()

    out = []
    for r in rows:
        games = r["games"] or 0
        if games < min_games:
            continue
        wins = r["wins"] or 0
        out.append(
            {
                "id": r["id"],
                "name": r["name"],
                "games": games,
                "wins": wins,
                "losses": games - wins,
                "win_pct": round(100.0 * wins / games, 1) if games else 0.0,
                "good_games": r["good_games"] or 0,
                "good_win_pct": round(100.0 * (r["good_wins"] or 0) / r["good_games"], 1) if r["good_games"] else None,
                "evil_games": r["evil_games"] or 0,
                "evil_win_pct": round(100.0 * (r["evil_wins"] or 0) / r["evil_games"], 1) if r["evil_games"] else None,
            }
        )
    out.sort(key=lambda d: (-d["win_pct"], -d["games"], d["name"]))
    return out


def overview(db_path: str = db.DEFAULT_DB) -> dict:
    with db.connect(db_path) as conn:
        g = conn.execute(
            """
            SELECT COUNT(*) AS games,
                   SUM(CASE WHEN winner='good' THEN 1 ELSE 0 END) AS good_wins,
                   SUM(CASE WHEN winner='evil' THEN 1 ELSE 0 END) AS evil_wins,
                   SUM(needs_review) AS games_need_review
            FROM game
            """
        ).fetchone()
        seats = conn.execute("SELECT COUNT(*) AS n FROM game_seat").fetchone()["n"]
        players = conn.execute("SELECT COUNT(*) AS n FROM player").fetchone()["n"]
    games = g["games"] or 0
    return {
        "games": games,
        "seats": seats,
        "players": players,
        "good_wins": g["good_wins"] or 0,
        "evil_wins": g["evil_wins"] or 0,
        "good_win_pct": round(100.0 * (g["good_wins"] or 0) / games, 1) if games else 0.0,
        "games_need_review": g["games_need_review"] or 0,
    }


def games_for_character(char_id: str, db_path: str = db.DEFAULT_DB) -> list[dict]:
    with db.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT g.id AS game_id, g.played_at, g.script, g.winner, g.player_count,
                   s.player_name, s.won, s.is_alive_at_end, s.final_alignment
            FROM game_seat s JOIN game g ON g.id = s.game_id
            WHERE s.character_id = ?
            ORDER BY g.id DESC
            """,
            (char_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def games_for_player(player_id: int, db_path: str = db.DEFAULT_DB) -> list[dict]:
    ref = get_reference()
    with db.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT g.id AS game_id, g.played_at, g.script, g.winner,
                   s.character_id, s.final_alignment, s.won, s.is_alive_at_end
            FROM game_seat s JOIN game g ON g.id = s.game_id
            WHERE s.player_id = ?
            ORDER BY g.id DESC
            """,
            (player_id,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        c = ref.get(d["character_id"])
        d["character_name"] = c.name if c else d["character_id"]
        out.append(d)
    return out
