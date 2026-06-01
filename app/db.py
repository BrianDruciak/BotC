"""
SQLite storage for recorded games.

Schema notes:
- `game_seat.character_id` holds the STARTING role (the attribution target for stats).
- `game_seat.final_character_id` holds the end-of-game token if the role changed.
- `game_seat.won` is derived: final_alignment == game.winner (BOTC win rule, alive or dead).
- Fabled/Loric seats are stored but excluded from win-rate stats (see reference.stats_eligible).
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_DB = os.path.join(ROOT, "data", "games.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS player (
    id              INTEGER PRIMARY KEY,
    canonical_name  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS player_alias (
    player_id  INTEGER NOT NULL REFERENCES player(id),
    alias      TEXT NOT NULL,
    UNIQUE(alias)
);

CREATE TABLE IF NOT EXISTS game (
    id            INTEGER PRIMARY KEY,
    external_id   TEXT,                 -- id/row from the source sheet, if any
    played_at     TEXT,
    script        TEXT,                 -- trouble_brewing | bad_moon_rising | ... | mixed
    player_count  INTEGER,
    winner        TEXT NOT NULL CHECK (winner IN ('good','evil')),
    source_images TEXT,                 -- JSON list of image links/paths
    notes         TEXT,
    needs_review  INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS game_seat (
    id                  INTEGER PRIMARY KEY,
    game_id             INTEGER NOT NULL REFERENCES game(id) ON DELETE CASCADE,
    seat_index          INTEGER,
    player_id           INTEGER REFERENCES player(id),
    player_name         TEXT,
    character_id        TEXT NOT NULL,         -- STARTING role (stats key)
    final_character_id  TEXT,                  -- final token if changed
    final_alignment     TEXT NOT NULL CHECK (final_alignment IN ('good','evil')),
    is_alive_at_end     INTEGER,
    reminder_tokens     TEXT,                  -- JSON list (audit trail)
    won                 INTEGER NOT NULL,      -- derived
    confidence          REAL,
    needs_review        INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_seat_game     ON game_seat(game_id);
CREATE INDEX IF NOT EXISTS ix_seat_char     ON game_seat(character_id);
CREATE INDEX IF NOT EXISTS ix_seat_player   ON game_seat(player_id);
"""


@contextmanager
def connect(path: str = DEFAULT_DB):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(path: str = DEFAULT_DB) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)


def get_or_create_player(conn: sqlite3.Connection, name: str) -> int:
    name = (name or "").strip()
    if not name:
        name = "(unknown)"
    row = conn.execute(
        "SELECT player_id FROM player_alias WHERE alias = ?", (name,)
    ).fetchone()
    if row:
        return row["player_id"]
    row = conn.execute(
        "SELECT id FROM player WHERE canonical_name = ?", (name,)
    ).fetchone()
    if row:
        pid = row["id"]
    else:
        cur = conn.execute(
            "INSERT INTO player(canonical_name) VALUES (?)", (name,)
        )
        pid = cur.lastrowid
    conn.execute(
        "INSERT OR IGNORE INTO player_alias(player_id, alias) VALUES (?, ?)",
        (pid, name),
    )
    return pid


def insert_game(conn: sqlite3.Connection, game: dict) -> int:
    cur = conn.execute(
        """
        INSERT INTO game(external_id, played_at, script, player_count, winner,
                         source_images, notes, needs_review)
        VALUES (:external_id, :played_at, :script, :player_count, :winner,
                :source_images, :notes, :needs_review)
        """,
        {
            "external_id": game.get("external_id"),
            "played_at": game.get("played_at"),
            "script": game.get("script"),
            "player_count": game.get("player_count"),
            "winner": game["winner"],
            "source_images": json.dumps(game.get("source_images", [])),
            "notes": game.get("notes"),
            "needs_review": int(bool(game.get("needs_review", False))),
        },
    )
    return cur.lastrowid


def insert_seat(conn: sqlite3.Connection, game_id: int, seat: dict) -> int:
    pid = get_or_create_player(conn, seat.get("player_name", ""))
    cur = conn.execute(
        """
        INSERT INTO game_seat(
            game_id, seat_index, player_id, player_name, character_id,
            final_character_id, final_alignment, is_alive_at_end,
            reminder_tokens, won, confidence, needs_review)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            game_id,
            seat.get("seat_index"),
            pid,
            seat.get("player_name"),
            seat["character_id"],
            seat.get("final_character_id"),
            seat["final_alignment"],
            int(bool(seat.get("is_alive_at_end", True))),
            json.dumps(seat.get("reminder_tokens", [])),
            int(bool(seat["won"])),
            seat.get("confidence"),
            int(bool(seat.get("needs_review", False))),
        ),
    )
    return cur.lastrowid


if __name__ == "__main__":
    init_db()
    print(f"Initialized DB at {DEFAULT_DB}")
