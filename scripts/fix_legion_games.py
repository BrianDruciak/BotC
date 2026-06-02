"""Fix Legion games and Game 10 Evoker per user confirmation."""

from __future__ import annotations

import sqlite3

from app import db

# (game_id, player_name, character_id, alignment)
SEAT_FIXES = [
    # Game 10 — Evoker is Snake Charmer (good); evil won
    (10, "Evoker", "snake_charmer", "good"),
    # Game 29 — Legion: multiple evil players share the demon
    (29, "Mango", "legion", "evil"),
    (29, "Solomon", "legion", "evil"),
    (29, "Socrates", "legion", "evil"),
    (29, "Pingu", "legion", "evil"),
    (29, "Grave", "legion", "evil"),
    (29, "Relic", "lycanthrope", "good"),
    (29, "Cercheo", "empath", "good"),
    (29, "Rice", "pixie", "good"),
    # Game 31 — Legion: eight evil Legion seats
    (31, "Ununoctium", "legion", "evil"),
    (31, "Lin", "legion", "evil"),
    (31, "Socrates", "legion", "evil"),
    (31, "Solomon", "legion", "evil"),
    (31, "Komodo", "legion", "evil"),
    (31, "PMA", "legion", "evil"),
    (31, "Pingu", "legion", "evil"),
    (31, "Radio", "legion", "evil"),
    (31, "Cercheo", "noble", "good"),
    (31, "Tomato", "empath", "good"),
    (31, "Mango", "plague_doctor", "good"),
    (31, "Prince", "alchemist", "good"),
]


def apply(conn: sqlite3.Connection) -> None:
    for game_id, player, char_id, alignment in SEAT_FIXES:
        winner = conn.execute(
            "SELECT winner FROM game WHERE id=?", (game_id,)
        ).fetchone()["winner"]
        won = 1 if alignment == winner else 0
        cur = conn.execute(
            """
            UPDATE game_seat
            SET character_id=?, final_alignment=?, won=?, needs_review=0
            WHERE game_id=? AND player_name=?
            """,
            (char_id, alignment, won, game_id, player),
        )
        if cur.rowcount == 0:
            raise ValueError(f"Missing seat: game {game_id} {player!r}")

    for gid in {10, 29, 31}:
        conn.execute("UPDATE game SET needs_review=0 WHERE id=?", (gid,))


def main() -> None:
    with db.connect() as conn:
        apply(conn)
    print("Fixed games 10, 29, 31")


if __name__ == "__main__":
    main()
