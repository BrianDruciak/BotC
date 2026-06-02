"""Apply user-confirmed role corrections and clear review flags."""

from __future__ import annotations

import sqlite3

from app import db

FIXES: list[tuple[int, str, str, str | None, bool]] = [
    # game_id, player_name, character_id, alignment (None=keep), clear_review
    (5, "Paul", "lunatic", "good", True),
    (5, "Erika", "po", "evil", True),
    (14, "Script", "no_dashii", "evil", True),
    (32, "Ichika", "soldier", "good", True),
    (32, "Snail", "empath", "good", True),
    (40, "Paul", "unknown:unknown", "good", True),
]


def recalc_won(conn: sqlite3.Connection, game_id: int, player_name: str) -> None:
    winner = conn.execute("SELECT winner FROM game WHERE id=?", (game_id,)).fetchone()[
        "winner"
    ]
    row = conn.execute(
        """
        SELECT id, final_alignment FROM game_seat
        WHERE game_id=? AND player_name=?
        """,
        (game_id, player_name),
    ).fetchone()
    if not row:
        raise ValueError(f"Seat not found: game {game_id} {player_name!r}")
    won = 1 if row["final_alignment"] == winner else 0
    conn.execute("UPDATE game_seat SET won=? WHERE id=?", (won, row["id"]))


def clear_game_review_if_clean(conn: sqlite3.Connection, game_id: int) -> None:
    pending = conn.execute(
        "SELECT COUNT(*) AS n FROM game_seat WHERE game_id=? AND needs_review=1",
        (game_id,),
    ).fetchone()["n"]
    if pending == 0:
        conn.execute("UPDATE game SET needs_review=0 WHERE id=?", (game_id,))


def main() -> None:
    with db.connect() as conn:
        for game_id, player, char_id, alignment, clear_review in FIXES:
            row = conn.execute(
                """
                SELECT id FROM game_seat
                WHERE game_id=? AND player_name=?
                """,
                (game_id, player),
            ).fetchone()
            if not row:
                print(f"SKIP missing seat: game {game_id} {player!r}")
                continue
            sets = ["character_id=?"]
            params: list = [char_id]
            if alignment:
                sets.append("final_alignment=?")
                params.append(alignment)
            if clear_review:
                sets.append("needs_review=0")
            params.extend([game_id, player])
            conn.execute(
                f"UPDATE game_seat SET {', '.join(sets)} WHERE game_id=? AND player_name=?",
                params,
            )
            recalc_won(conn, game_id, player)
            print(f"Fixed game {game_id}: {player} -> {char_id} ({alignment or 'unchanged'})")

        for gid in {f[0] for f in FIXES}:
            clear_game_review_if_clean(conn, gid)
            print(f"Checked game {gid} review flag")


if __name__ == "__main__":
    main()
