"""One-off: add three manually reported games (2026-06-01)."""

from __future__ import annotations

from app import db, ingest
from app.ingest import ResolvedGame, ResolvedSeat
from app.reference import get_reference

ref = get_reference()


def seat(
    name: str,
    char_id: str,
    alignment: str,
    winner: str,
    *,
    seat_index: int,
    needs_review: bool = False,
    reminder_tokens: list[str] | None = None,
) -> ResolvedSeat:
    c = ref.get(char_id)
    return ResolvedSeat(
        player_name=name,
        seat_index=seat_index,
        character_id=char_id,
        character_name=c.name if c else char_id,
        final_character_id=None,
        final_character_name=None,
        final_alignment=alignment,
        is_alive_at_end=True,
        reminder_tokens=reminder_tokens or [],
        won=alignment == winner,
        confidence=1.0,
        needs_review=needs_review,
    )


GAMES = [
    ResolvedGame(
        winner="evil",
        script="trouble_brewing",
        player_count=6,
        needs_review=False,
        external_id="manual-38",
        notes="Manual entry: Game 1 — evil win",
        seats=[
            seat("PMA", "imp", "evil", "evil", seat_index=0),
            seat("Solomon", "poisoner", "evil", "evil", seat_index=1),
            seat("meiji", "undertaker", "good", "evil", seat_index=2),
            seat("4b", "empath", "good", "evil", seat_index=3),
            seat("Snail", "saint", "good", "evil", seat_index=4),
            seat("Paul", "fortune_teller", "good", "evil", seat_index=5),
        ],
    ),
    ResolvedGame(
        winner="good",
        script="trouble_brewing",
        player_count=6,
        needs_review=False,
        external_id="manual-39",
        notes="Manual entry: Game 2 — good win",
        seats=[
            seat("Seika", "virgin", "good", "good", seat_index=0),
            seat("Solomon", "slayer", "good", "good", seat_index=1),
            seat("Hautp", "saint", "good", "good", seat_index=2),
            seat("Erika", "chef", "good", "good", seat_index=3),
            seat("Tomato", "imp", "evil", "good", seat_index=4),
            seat("Rice", "scarlet_woman", "evil", "good", seat_index=5),
        ],
    ),
    ResolvedGame(
        winner="evil",
        script="trouble_brewing",
        player_count=9,
        needs_review=True,
        external_id="manual-40",
        notes="Manual entry: Game 3 — evil win; Paul role unknown",
        seats=[
            seat("Solomon", "drunk", "good", "evil", seat_index=0, reminder_tokens=["Drunk"]),
            seat("Kaptcha", "washerwoman", "good", "evil", seat_index=1),
            seat("Paul", "unknown:unknown", "good", "evil", seat_index=2, needs_review=True),
            seat("Cube", "chef", "good", "evil", seat_index=3),
            seat("Rice", "soldier", "good", "evil", seat_index=4),
            seat("Rendroken", "virgin", "good", "evil", seat_index=5),
            seat("Marishi", "monk", "good", "evil", seat_index=6),
            seat("Evoker", "imp", "evil", "evil", seat_index=7),
            seat("Cercheo", "spy", "evil", "evil", seat_index=8),
        ],
    ),
]


def main() -> None:
    ids: list[int] = []
    for g in GAMES:
        gid = ingest.commit(g)
        ids.append(gid)
        print(f"Committed game #{gid} ({g.external_id}): {g.winner} won, {g.player_count} seats")
    print("IDs:", ids)


if __name__ == "__main__":
    main()
