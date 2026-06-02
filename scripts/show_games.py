import sqlite3
from app.reference import get_reference

ref = get_reference()
conn = sqlite3.connect("data/games.db")
conn.row_factory = sqlite3.Row

for gid in (5, 10, 14, 29, 31, 32, 40):
    g = conn.execute(
        "SELECT id,winner,player_count,script,notes FROM game WHERE id=?", (gid,)
    ).fetchone()
    print("=" * 60)
    print(f"Game #{g['id']}: {g['winner']} won, {g['player_count']} players")
    print(f"  Script: {g['script']}")
    if g["notes"]:
        print(f"  Notes: {g['notes']}")
    for s in conn.execute(
        """
        SELECT seat_index,player_name,character_id,final_alignment,won,needs_review
        FROM game_seat WHERE game_id=? ORDER BY seat_index
        """,
        (gid,),
    ):
        c = ref.get(s["character_id"])
        role = c.name if c else s["character_id"]
        rev = " [REVIEW]" if s["needs_review"] else ""
        w = "W" if s["won"] else "L"
        print(f"  {s['player_name']:12} {role:22} {s['final_alignment']:5} {w}{rev}")
