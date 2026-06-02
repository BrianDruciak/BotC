import sqlite3

conn = sqlite3.connect("data/games.db")
real = "(g.external_id IS NULL OR g.external_id NOT LIKE 'demo-%')"
print("ocr-legion-dup seats:", conn.execute(
    f"SELECT COUNT(*) FROM game_seat s JOIN game g ON g.id=s.game_id WHERE character_id='unknown:ocr-legion-dup' AND {real}"
).fetchone()[0])
print("legion seats:", conn.execute(
    f"SELECT COUNT(*) FROM game_seat s JOIN game g ON g.id=s.game_id WHERE character_id='legion' AND {real}"
).fetchone()[0])
print("legion distinct games:", conn.execute(
    f"SELECT COUNT(DISTINCT g.id) FROM game_seat s JOIN game g ON g.id=s.game_id WHERE character_id='legion' AND {real}"
).fetchone()[0])
for gid in conn.execute(
    f"SELECT DISTINCT g.id FROM game_seat s JOIN game g ON g.id=s.game_id WHERE character_id='legion' AND {real} ORDER BY g.id"
):
    n = conn.execute("SELECT COUNT(*) FROM game_seat WHERE game_id=? AND character_id='legion'", (gid[0],)).fetchone()[0]
    print(f"  game #{gid[0]}: {n} legion seats")
