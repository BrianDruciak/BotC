"""Compare original committed manual_player_stats.json vs DB aggregation."""

from __future__ import annotations

import json
import subprocess
import sys

from app import db
from app.players import stats_real_games_sql


def load_original_manual() -> dict[str, dict]:
    raw = subprocess.check_output(
        ["git", "show", "HEAD:data/manual_player_stats.json"],
        text=True,
        encoding="utf-8",
    )
    return {p["name"]: p for p in json.loads(raw)["players"]}


def load_db_stats() -> dict[str, dict]:
    real = stats_real_games_sql()
    with db.connect() as conn:
        rows = conn.execute(
            f"""
            SELECT p.canonical_name AS name,
                   COUNT(*) AS games,
                   SUM(s.won) AS wins,
                   SUM(CASE WHEN s.final_alignment='good' THEN 1 ELSE 0 END) AS good_games,
                   SUM(CASE WHEN s.final_alignment='evil' THEN 1 ELSE 0 END) AS evil_games
            FROM game_seat s
            JOIN game g ON g.id = s.game_id
            JOIN player p ON p.id = s.player_id
            WHERE {real}
            GROUP BY p.id
            """
        ).fetchall()
    return {
        r["name"]: {
            "games": r["games"],
            "wins": int(r["wins"] or 0),
            "good_games": int(r["good_games"] or 0),
            "evil_games": int(r["evil_games"] or 0),
        }
        for r in rows
    }


def main() -> None:
    orig = load_original_manual()
    db_stats = load_db_stats()

    print(f"{'Player':<18} {'Manual G/W':>12} {'DB G/W':>12} {'dG':>4} {'dW':>4}")
    print("-" * 54)

    diffs: list[tuple] = []
    for name in sorted(set(orig) | set(db_stats), key=str.lower):
        o = orig.get(name)
        d = db_stats.get(name)
        if not o:
            print(f"{name:<18} {'—':>12} {d['games']:>4}/{d['wins']:<4}  DB only")
            continue
        if not d:
            print(f"{name:<18} {o['games']:>4}/{o['wins']:<4} {'—':>12}  manual only")
            continue
        dg, dw = d["games"] - o["games"], d["wins"] - o["wins"]
        if dg or dw:
            diffs.append((name, o, d, dg, dw))
            print(
                f"{name:<18} {o['games']:>4}/{o['wins']:<4} "
                f"{d['games']:>4}/{d['wins']:<4} {dg:>+4} {dw:>+4}"
            )

    print(f"\n{len(diffs)} player(s) differ between original manual sheet and DB.")

    # Current file on disk (may have been overwritten by export)
    from app.manual_stats import load_manual_players

    current = {p["name"]: p for p in (load_manual_players(0) or [])}
    if current.get("Ununoctium", {}).get("games") != orig.get("Ununoctium", {}).get("games"):
        u = current.get("Ununoctium", {})
        o = orig.get("Ununoctium", {})
        print(
            f"\nWebsite manual JSON now shows Ununoctium {u.get('games')}G "
            f"(original sheet had {o.get('games')}G) — export overwrote the sheet."
        )


if __name__ == "__main__":
    main()
