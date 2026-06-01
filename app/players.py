"""
Player identity helpers: merge OCR duplicates into one canonical player.

The player_alias table records every raw name seen; merge_players consolidates
duplicate player rows and re-points game_seat rows at the survivor.
"""

from __future__ import annotations

import sqlite3

from . import db
from .manual_stats import manual_player_names

# Known OCR / casing duplicates from grimoire extraction. Keep name -> merge these in.
# Canonical names aligned with stats (1).xlsx manual sheet where noted.
OCR_MERGE_GROUPS: list[tuple[str, list[str]]] = [
    ("Solomon", ["solomon"]),
    ("Paul", ["paul"]),
    ("Cercheo", ["CERCHEO"]),
    ("Grave", ["grave", "Graveboi"]),
    ("Miku", ["miku"]),
    ("Relic", ["RELIC", "lost_relic", "relic_lost"]),
    ("Cube", ["CUBE"]),
    ("Marishi", ["marishi", "Mariishi", "Sukeyu", "Sukeiyu", "Sukeyu93"]),
    ("Evoker", ["evoker"]),
    ("Sybil", ["sybil"]),
    ("Snail", ["King Snail", "Kingsnail", "KingSnail", "Kings"]),
    ("Ichika", ["ichika"]),
    ("Socrates", ["Socra...", "Soc"]),
    ("Ununoctium", ["Ununocti...", "ununocti...", "Ununoctiu...", "ununocitium", "Ununo"]),
    ("Icelily", ["Icielily"]),
    ("meiji", ["meijii", "meijji"]),
    ("Rendro", ["Rerdro"]),
    ("Tomato", ["Tomato L", "Tomato Lover"]),
    ("Cactus", ["Noble Cactus"]),
]

# Rename canonical display name after merges (old canonical -> new).
RENAME_CANONICAL: dict[str, str] = {
    "Nigerian Tea Bag Enthusiast": "Nigerian",
    "Rendro": "Rendroken",
    "Haupt": "Hautp",
    "Raidio": "Radio",
}


def resolve_player_id(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute(
        "SELECT player_id FROM player_alias WHERE alias = ?", (name,)
    ).fetchone()
    if row:
        return row["player_id"]
    row = conn.execute(
        "SELECT id FROM player WHERE canonical_name = ?", (name,)
    ).fetchone()
    if row:
        return row["id"]
    raise ValueError(f"Unknown player: {name!r}")


def merge_players(
    conn: sqlite3.Connection,
    keep_id: int,
    merge_ids: list[int],
) -> dict:
    """Merge duplicate players into keep_id."""
    merge_ids = [mid for mid in merge_ids if mid != keep_id]
    if not merge_ids:
        return {"keep_id": keep_id, "merged": [], "seats_moved": 0}

    keep = conn.execute(
        "SELECT id, canonical_name FROM player WHERE id = ?", (keep_id,)
    ).fetchone()
    if not keep:
        raise ValueError(f"Keep player id {keep_id} not found")

    canonical = keep["canonical_name"]
    merged: list[dict] = []
    seats_moved = 0

    for mid in merge_ids:
        row = conn.execute(
            "SELECT id, canonical_name FROM player WHERE id = ?", (mid,)
        ).fetchone()
        if not row:
            continue

        alias = row["canonical_name"]
        cur = conn.execute(
            "UPDATE game_seat SET player_id = ? WHERE player_id = ?",
            (keep_id, mid),
        )
        seats_moved += cur.rowcount
        conn.execute(
            "UPDATE game_seat SET player_name = ? WHERE player_id = ? AND player_name = ?",
            (canonical, keep_id, alias),
        )
        conn.execute(
            "INSERT OR IGNORE INTO player_alias(player_id, alias) VALUES (?, ?)",
            (keep_id, alias),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO player_alias(player_id, alias)
            SELECT ?, alias FROM player_alias WHERE player_id = ?
            """,
            (keep_id, mid),
        )
        conn.execute("DELETE FROM player_alias WHERE player_id = ?", (mid,))
        conn.execute("DELETE FROM player WHERE id = ?", (mid,))
        merged.append({"id": mid, "name": alias, "seats": cur.rowcount})

    conn.execute(
        "INSERT OR IGNORE INTO player_alias(player_id, alias) VALUES (?, ?)",
        (keep_id, canonical),
    )
    return {
        "keep_id": keep_id,
        "keep_name": canonical,
        "merged": merged,
        "seats_moved": seats_moved,
    }


def rename_player(conn: sqlite3.Connection, old_name: str, new_name: str) -> bool:
    """Rename a player's canonical name (records old name as alias)."""
    row = conn.execute(
        "SELECT id, canonical_name FROM player WHERE canonical_name = ?", (old_name,)
    ).fetchone()
    if not row:
        return False
    pid = row["id"]
    conn.execute("UPDATE player SET canonical_name = ? WHERE id = ?", (new_name, pid))
    conn.execute(
        "INSERT OR IGNORE INTO player_alias(player_id, alias) VALUES (?, ?)",
        (pid, old_name),
    )
    conn.execute(
        "INSERT OR IGNORE INTO player_alias(player_id, alias) VALUES (?, ?)",
        (pid, new_name),
    )
    conn.execute(
        "UPDATE game_seat SET player_name = ? WHERE player_id = ?",
        (new_name, pid),
    )
    return True


def apply_renames(conn: sqlite3.Connection, renames: dict[str, str] | None = None) -> list[str]:
    renames = renames or RENAME_CANONICAL
    done: list[str] = []
    for old, new in renames.items():
        if rename_player(conn, old, new):
            done.append(f"{old!r} -> {new!r}")
    return done


def reconcile_manual(db_path: str = db.DEFAULT_DB) -> dict:
    """Merge OCR aliases and apply renames to align with manual stats sheet."""
    merge_results = apply_ocr_merges(db_path)
    renames: list[str] = []
    with db.connect(db_path) as conn:
        renames = apply_renames(conn)
    return {"merges": merge_results, "renames": renames}


def merge_by_names(
    db_path: str,
    keep_name: str,
    merge_names: list[str],
) -> dict:
    with db.connect(db_path) as conn:
        keep_id = resolve_player_id(conn, keep_name)
        merge_ids = [resolve_player_id(conn, name) for name in merge_names]
        return merge_players(conn, keep_id, merge_ids)


def apply_ocr_merges(db_path: str = db.DEFAULT_DB) -> list[dict]:
    """Apply the built-in OCR duplicate merge groups."""
    results: list[dict] = []
    with db.connect(db_path) as conn:
        for keep_name, merge_names in OCR_MERGE_GROUPS:
            present: list[int] = []
            for name in merge_names:
                try:
                    present.append(resolve_player_id(conn, name))
                except ValueError:
                    continue
            if not present:
                continue
            try:
                keep_id = resolve_player_id(conn, keep_name)
            except ValueError:
                keep_id = present[0]
            result = merge_players(conn, keep_id, present)
            if result["merged"]:
                row = conn.execute(
                    "SELECT canonical_name FROM player WHERE id = ?", (keep_id,)
                ).fetchone()
                if row and row["canonical_name"] != keep_name:
                    rename_player(conn, row["canonical_name"], keep_name)
                    result["keep_name"] = keep_name
                results.append(result)
    return results


def suggest_merges(db_path: str = db.DEFAULT_DB, min_ratio: float = 82.0) -> list[dict]:
    """Return likely duplicate player pairs from real (non-demo) games."""
    from rapidfuzz import fuzz

    real_games = stats_real_games_sql()
    with db.connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT p.id, p.canonical_name, COUNT(s.id) AS seats
            FROM player p
            JOIN game_seat s ON s.player_id = p.id
            JOIN game g ON g.id = s.game_id
            WHERE {real_games}
            GROUP BY p.id
            ORDER BY p.canonical_name
            """
        ).fetchall()

    names = [(r["id"], r["canonical_name"], r["seats"]) for r in rows]
    out: list[dict] = []
    for i, (id1, n1, s1) in enumerate(names):
        for id2, n2, s2 in names[i + 1 :]:
            if n1 == n2:
                continue
            ratio = fuzz.ratio(n1.lower(), n2.lower())
            if n1.lower() == n2.lower() or ratio >= min_ratio:
                out.append(
                    {
                        "a": n1,
                        "a_id": id1,
                        "a_seats": s1,
                        "b": n2,
                        "b_id": id2,
                        "b_seats": s2,
                        "ratio": round(ratio, 1),
                    }
                )
    out.sort(key=lambda d: (-d["ratio"], d["a"], d["b"]))
    return out


def purge_non_manual_players(db_path: str = db.DEFAULT_DB) -> dict:
    """Delete OCR players/seats not listed in the manual stats sheet."""
    allowed = manual_player_names()
    if not allowed:
        return {"removed_players": 0, "removed_seats": 0}

    removed_seats = 0
    removed_players = 0
    with db.connect(db_path) as conn:
        rows = conn.execute("SELECT id, canonical_name FROM player").fetchall()
        for row in rows:
            if row["canonical_name"] in allowed:
                continue
            cur = conn.execute("DELETE FROM game_seat WHERE player_id = ?", (row["id"],))
            removed_seats += cur.rowcount
            conn.execute("DELETE FROM player_alias WHERE player_id = ?", (row["id"],))
            conn.execute("DELETE FROM player WHERE id = ?", (row["id"],))
            removed_players += 1
    return {"removed_players": removed_players, "removed_seats": removed_seats, "allowed": len(allowed)}


def stats_real_games_sql() -> str:
    return "(g.external_id IS NULL OR g.external_id NOT LIKE 'demo-%')"
