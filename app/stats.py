"""
Win-rate aggregations.

Character win rates are keyed on the STARTING role (game_seat.character_id) per the
attribution decision. Fabled/Loric seats are excluded (storyteller pieces).
"""

from __future__ import annotations

from . import db
from .character_fix import apply_character_bonuses
from .manual_stats import get_manual_player, load_manual_players, manual_player_names
from .reference import get_reference
from .scripts import OFFICIAL_ORDER, normalize_script

# Demo games (stub extractor) use external_id "demo-N" and fake player names.
_REAL_GAMES = "(g.external_id IS NULL OR g.external_id NOT LIKE 'demo-%')"

# Legion: every evil player can be Legion in the same game — count games, not seats.
_PER_GAME_CHARACTER_STATS = {"legion"}


def _eligible_char_ids() -> set[str]:
    ref = get_reference()
    return {c.id for c in ref.characters if ref.stats_eligible(c.id)}


def _legion_character_stat(conn, ref, min_games: int) -> dict | None:
    row = conn.execute(
        f"""
        SELECT COUNT(DISTINCT g.id) AS games,
               COUNT(DISTINCT CASE WHEN g.winner = 'evil' THEN g.id END) AS wins,
               SUM(s.is_alive_at_end) AS survived,
               COUNT(s.id) AS seats
        FROM game_seat s
        JOIN game g ON g.id = s.game_id
        WHERE s.character_id = 'legion' AND {_REAL_GAMES}
        """
    ).fetchone()
    games = row["games"] or 0
    if games < min_games:
        return None
    wins = row["wins"] or 0
    seats = row["seats"] or 0
    c = ref.get("legion")
    return {
        "id": "legion",
        "name": c.name if c else "Legion",
        "type": c.type if c else "demon",
        "alignment": c.alignment if c else "evil",
        "editions": c.editions if c else [],
        "icon_path": c.icon_path if c else "",
        "games": games,
        "wins": wins,
        "losses": games - wins,
        "win_pct": round(100.0 * wins / games, 1) if games else 0.0,
        "survival_pct": round(100.0 * (row["survived"] or 0) / seats, 1) if seats else 0.0,
    }


def character_stats(db_path: str = db.DEFAULT_DB, min_games: int = 0) -> list[dict]:
    ref = get_reference()
    eligible = _eligible_char_ids()
    with db.connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT s.character_id,
                   COUNT(*)              AS games,
                   SUM(s.won)              AS wins,
                   SUM(1 - s.won)          AS losses,
                   SUM(s.is_alive_at_end)  AS survived
            FROM game_seat s
            JOIN game g ON g.id = s.game_id
            WHERE {_REAL_GAMES}
              AND s.character_id NOT IN ({",".join("?" * len(_PER_GAME_CHARACTER_STATS))})
            GROUP BY s.character_id
            """,
            tuple(_PER_GAME_CHARACTER_STATS),
        ).fetchall()
        legion = _legion_character_stat(conn, ref, min_games)

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
    if legion and "legion" in eligible:
        out.append(legion)
    out.sort(key=lambda d: (-d["win_pct"], -d["games"], d["name"]))
    return apply_character_bonuses(out)


def player_stats(db_path: str = db.DEFAULT_DB, min_games: int = 0) -> list[dict]:
    manual = load_manual_players(min_games=min_games)
    if manual is not None:
        return manual

    with db.connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT p.id, p.canonical_name AS name,
                   COUNT(*)                                   AS games,
                   SUM(s.won)                                 AS wins,
                   SUM(CASE WHEN s.final_alignment='good' THEN 1 ELSE 0 END)         AS good_games,
                   SUM(CASE WHEN s.final_alignment='good' THEN s.won ELSE 0 END)     AS good_wins,
                   SUM(CASE WHEN s.final_alignment='evil' THEN 1 ELSE 0 END)         AS evil_games,
                   SUM(CASE WHEN s.final_alignment='evil' THEN s.won ELSE 0 END)     AS evil_wins
            FROM game_seat s
            JOIN game g ON g.id = s.game_id
            JOIN player p ON p.id = s.player_id
            WHERE {_REAL_GAMES}
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
    manual = load_manual_players(min_games=0)
    with db.connect(db_path) as conn:
        g = conn.execute(
            f"""
            SELECT COUNT(*) AS games,
                   SUM(CASE WHEN winner='good' THEN 1 ELSE 0 END) AS good_wins,
                   SUM(CASE WHEN winner='evil' THEN 1 ELSE 0 END) AS evil_wins,
                   SUM(needs_review) AS games_need_review
            FROM game g
            WHERE {_REAL_GAMES}
            """
        ).fetchone()
        if manual is not None:
            seats = sum(p["games"] for p in manual)
            players = len(manual)
        else:
            seats = conn.execute(
                f"""
                SELECT COUNT(*) AS n
                FROM game_seat s JOIN game g ON g.id = s.game_id
                WHERE {_REAL_GAMES}
                """
            ).fetchone()["n"]
            players = conn.execute(
                f"""
                SELECT COUNT(DISTINCT s.player_id) AS n
                FROM game_seat s JOIN game g ON g.id = s.game_id
                WHERE {_REAL_GAMES}
                """
            ).fetchone()["n"]
    games = g["games"] or 0
    return {
        "games": games,
        "seats": seats,
        "players": players,
        "good_wins": g["good_wins"] or 0,
        "evil_wins": g["evil_wins"] or 0,
        "good_win_pct": round(100.0 * (g["good_wins"] or 0) / games, 1) if games else 0.0,
        "games_need_review": g["games_need_review"] or 0,
        "player_source": "manual" if manual is not None else "database",
    }


def script_stats(db_path: str = db.DEFAULT_DB) -> list[dict]:
    """Good/evil team win rates grouped by script / edition set."""
    with db.connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT script, winner
            FROM game g
            WHERE {_REAL_GAMES}
            """
        ).fetchall()

    buckets: dict[str, dict] = {}
    for r in rows:
        name = normalize_script(r["script"])
        b = buckets.setdefault(
            name,
            {"name": name, "games": 0, "good_wins": 0, "evil_wins": 0},
        )
        b["games"] += 1
        if r["winner"] == "good":
            b["good_wins"] += 1
        else:
            b["evil_wins"] += 1

    out: list[dict] = []
    for b in buckets.values():
        g = b["games"]
        gw = b["good_wins"]
        ew = b["evil_wins"]
        out.append(
            {
                "name": b["name"],
                "games": g,
                "good_wins": gw,
                "evil_wins": ew,
                "good_win_pct": round(100.0 * gw / g, 1) if g else 0.0,
                "evil_win_pct": round(100.0 * ew / g, 1) if g else 0.0,
                "official": b["name"] in OFFICIAL_ORDER,
            }
        )

    order = {n: i for i, n in enumerate(OFFICIAL_ORDER)}

    def sort_key(d: dict) -> tuple:
        if d["name"] in order:
            return (0, order[d["name"]], d["name"].lower())
        return (1, -d["games"], d["name"].lower())

    out.sort(key=sort_key)
    return out


def games_for_character(char_id: str, db_path: str = db.DEFAULT_DB) -> list[dict]:
    with db.connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT g.id AS game_id, g.played_at, g.script, g.winner, g.player_count,
                   s.player_name, s.won, s.is_alive_at_end, s.final_alignment
            FROM game_seat s JOIN game g ON g.id = s.game_id
            WHERE s.character_id = ? AND {_REAL_GAMES}
            ORDER BY g.id DESC
            """,
            (char_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def games_for_player(player_id: int, db_path: str = db.DEFAULT_DB) -> list[dict]:
    if get_manual_player(player_id):
        return []

    ref = get_reference()
    with db.connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT g.id AS game_id, g.played_at, g.script, g.winner,
                   s.character_id, s.final_alignment, s.won, s.is_alive_at_end
            FROM game_seat s JOIN game g ON g.id = s.game_id
            WHERE s.player_id = ? AND {_REAL_GAMES}
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
