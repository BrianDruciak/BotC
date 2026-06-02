import sqlite3

conn = sqlite3.connect("data/games.db")
conn.row_factory = sqlite3.Row
REAL = "(g.external_id IS NULL OR g.external_id NOT LIKE 'demo-%')"

games = conn.execute(
    f"""
    SELECT g.id, g.winner, g.player_count, g.notes, g.script
    FROM game g
    WHERE g.needs_review = 1 AND {REAL}
    ORDER BY g.id
    """
).fetchall()

seats = conn.execute(
    f"""
    SELECT s.game_id, s.player_name, s.character_id, s.final_alignment
    FROM game_seat s
    JOIN game g ON g.id = s.game_id
    WHERE s.needs_review = 1 AND {REAL}
    ORDER BY s.game_id, s.seat_index
    """
).fetchall()

game_ids = conn.execute(
    f"""
    SELECT DISTINCT g.id
    FROM game g
    LEFT JOIN game_seat s ON s.game_id = g.id
    WHERE (g.needs_review = 1 OR s.needs_review = 1) AND {REAL}
    ORDER BY g.id
    """
).fetchall()

print("=== GAMES FLAGGED FOR REVIEW ===")
for g in games:
    print(f"Game #{g['id']}: {g['winner']} won, {g['player_count']} players")
    if g["notes"]:
        print(f"  notes: {g['notes']}")
    if g["script"]:
        print(f"  script: {g['script']}")

print("\n=== SEATS FLAGGED FOR REVIEW ===")
for s in seats:
    print(
        f"Game #{s['game_id']}: {s['player_name']} — "
        f"{s['character_id']} ({s['final_alignment']})"
    )

print(f"\nTotal games needing review: {len(game_ids)}")

# Games with seat-level review only (game flag clear)
seat_only = conn.execute(
    f"""
    SELECT DISTINCT g.id, g.winner, g.script
    FROM game g
    JOIN game_seat s ON s.game_id = g.id
    WHERE s.needs_review = 1 AND g.needs_review = 0 AND {REAL}
    ORDER BY g.id
    """
).fetchall()
if seat_only:
    print("\n=== GAMES WITH SEAT REVIEW ONLY (game not flagged) ===")
    for g in seat_only:
        print(f"Game #{g['id']}: {g['winner']} won — {g['script'] or 'unknown script'}")
