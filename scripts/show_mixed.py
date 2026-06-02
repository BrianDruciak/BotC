import sqlite3
from app.reference import get_reference

ref = get_reference()
conn = sqlite3.connect("data/games.db")
conn.row_factory = sqlite3.Row
games = conn.execute(
    "SELECT id, winner, player_count, script, notes FROM game WHERE script = 'mixed'"
).fetchall()
for g in games:
    print(f"Game #{g['id']}: {g['winner']} won, {g['player_count']} players")
    if g["notes"]:
        print(f"  notes: {g['notes']}")
    for s in conn.execute(
        "SELECT player_name, character_id, final_alignment FROM game_seat WHERE game_id=? ORDER BY seat_index",
        (g["id"],),
    ):
        c = ref.get(s["character_id"])
        role = c.name if c else s["character_id"]
        editions = ", ".join(c.editions) if c else "?"
        print(f"  {s['player_name']:12} {role:20} {s['final_alignment']:5}  [{editions}]")
