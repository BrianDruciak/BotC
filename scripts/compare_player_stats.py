"""Compare manual_player_stats.json vs DB-aggregated player stats."""

from __future__ import annotations

import sqlite3

from app import db, stats
from app.manual_stats import load_manual_players
from app.players import stats_real_games_sql


def db_player_stats() -> dict[str, dict]:
    real = stats_real_games_sql()
    with db.connect() as conn:
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
    out = {}
    for r in rows:
        g = int(r["games"])
        w = int(r["wins"] or 0)
        gg = int(r["good_games"] or 0)
        eg = int(r["evil_games"] or 0)
        out[r["name"]] = {
            "games": g,
            "wins": w,
            "losses": g - w,
            "win_pct": round(100.0 * w / g, 1) if g else 0.0,
            "good_games": gg,
            "good_wins": int(r["good_wins"] or 0),
            "evil_games": eg,
            "evil_wins": int(r["evil_wins"] or 0),
        }
    return out


def main() -> None:
    manual = {p["name"]: p for p in (load_manual_players(0) or [])}
    db_stats = db_player_stats()
    api = {p["name"]: p for p in stats.player_stats(min_games=0)}

    all_names = sorted(set(manual) | set(db_stats), key=str.lower)
    mismatches = []

    print(f"{'Player':<16} {'Manual G/W':>12} {'DB G/W':>12} {'API G/W':>12}  Note")
    print("-" * 70)

    for name in all_names:
        m = manual.get(name)
        d = db_stats.get(name)
        a = api.get(name)

        mg, mw = (m["games"], m["wins"]) if m else ("—", "—")
        dg, dw = (d["games"], d["wins"]) if d else (0, 0)
        ag, aw = (a["games"], a["wins"]) if a else ("—", "—")

        note = ""
        if m and d and (m["games"] != d["games"] or m["wins"] != d["wins"]):
            note = "MISMATCH manual vs DB"
            mismatches.append((name, m, d))
        elif not m and d:
            note = "DB only"
        elif m and not d:
            note = "manual only (0 in DB)"

        if note or name.lower() == "ununoctium":
            print(f"{name:<16} {str(mg)+'/'+str(mw):>12} {str(dg)+'/'+str(dw):>12} {str(ag)+'/'+str(aw):>12}  {note}")

    print()
    print(f"Total mismatches (manual vs DB): {len(mismatches)}")
    for name, m, d in mismatches:
        print(f"\n=== {name} ===")
        print(f"  manual: {m['games']}G {m['wins']}W ({m['win_pct']}%)")
        print(f"  DB:     {d['games']}G {d['wins']}W")
        diff_g = m["games"] - d["games"]
        diff_w = m["wins"] - d["wins"]
        print(f"  delta:  {diff_g:+d} games, {diff_w:+d} wins")

    # Ununoctium game list from DB
    print("\n=== Ununoctium DB seats ===")
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT g.id, g.script, g.winner, s.character_id, s.final_alignment, s.won
            FROM game_seat s
            JOIN game g ON g.id = s.game_id
            JOIN player p ON p.id = s.player_id
            WHERE p.canonical_name = 'Ununoctium'
              AND (g.external_id IS NULL OR g.external_id NOT LIKE 'demo-%')
            ORDER BY g.id
            """
        ).fetchall()
        for r in rows:
            print(f"  game #{r['id']} {r['script']} {r['character_id']} {r['final_alignment']} {'W' if r['won'] else 'L'}")


if __name__ == "__main__":
    main()
