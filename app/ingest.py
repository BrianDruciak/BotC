"""
Ingestion: GameExtraction -> resolved proposal -> committed game.

- Snaps every detected character to the canonical 183 (starting role = attribution key).
- Derives final_alignment (hint > character-type default) and the BOTC `won` flag.
- Flags low-confidence seats / ambiguous alignment for human review.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import db
from .extract.base import GameExtraction
from .reference import Reference, get_reference

#: rapidfuzz WRatio below this => the match is untrusted and the seat needs review.
MATCH_REVIEW_CUTOFF = 85.0
#: per-seat model confidence below this => needs review.
CONF_REVIEW_CUTOFF = 0.80

_BASE_SCRIPTS = {"trouble_brewing", "bad_moon_rising", "sects_and_violets"}


@dataclass
class ResolvedSeat:
    player_name: str
    seat_index: int | None
    character_id: str            # starting role
    character_name: str
    final_character_id: str | None
    final_character_name: str | None
    final_alignment: str         # 'good' | 'evil'
    is_alive_at_end: bool
    reminder_tokens: list[str]
    won: bool
    confidence: float
    needs_review: bool
    review_reasons: list[str] = field(default_factory=list)


@dataclass
class ResolvedGame:
    winner: str | None
    script: str | None
    player_count: int
    seats: list[ResolvedSeat]
    needs_review: bool
    external_id: str | None = None
    played_at: str | None = None
    source_images: list[str] = field(default_factory=list)
    notes: str | None = None


def _infer_script(seats: list[ResolvedSeat], ref: Reference) -> str | None:
    editions = set()
    for s in seats:
        c = ref.get(s.character_id)
        if not c:
            continue
        base = [e for e in c.editions if e in _BASE_SCRIPTS]
        editions.update(base or c.editions)
    base_only = editions & _BASE_SCRIPTS
    if len(base_only) == 1 and not (editions - _BASE_SCRIPTS):
        return next(iter(base_only))
    if not editions:
        return None
    if editions <= {"experimental"}:
        return "experimental"
    return "mixed"


def resolve(extraction: GameExtraction, ref: Reference | None = None) -> ResolvedGame:
    ref = ref or get_reference()
    winner = extraction.winner
    seats: list[ResolvedSeat] = []

    for s in extraction.seats:
        reasons: list[str] = []
        start_m = ref.match(s.starting_character_text)
        final_m = ref.match(s.character_text)

        start_char = start_m.character
        final_char = final_m.character or start_char

        if start_char is None:
            reasons.append(f"unknown starting character '{s.starting_character_text}'")
        if start_m.score < MATCH_REVIEW_CUTOFF:
            reasons.append(f"low name match ({start_m.score:.0f})")
        if s.confidence < CONF_REVIEW_CUTOFF:
            reasons.append(f"low model confidence ({s.confidence:.2f})")

        # Alignment: explicit hint wins, else the (final) character's type default.
        alignment = (s.alignment_hint or "").lower()
        if alignment not in ("good", "evil"):
            ref_align = (final_char.alignment if final_char else "good")
            if ref_align in ("good", "evil"):
                alignment = ref_align
            else:  # traveller / neutral with no hint
                alignment = "good"
                reasons.append("alignment indeterminate (defaulted good)")

        won = bool(winner) and (alignment == winner)
        final_id = (
            final_char.id
            if (final_char and start_char and final_char.id != start_char.id)
            else None
        )

        seats.append(
            ResolvedSeat(
                player_name=s.player_name,
                seat_index=s.seat_index,
                character_id=(start_char.id if start_char else f"unknown:{s.starting_character_text}"),
                character_name=(start_char.name if start_char else s.starting_character_text),
                final_character_id=final_id,
                final_character_name=(ref.get(final_id).name if final_id else None),
                final_alignment=alignment,
                is_alive_at_end=s.is_alive,
                reminder_tokens=s.reminder_tokens,
                won=won,
                confidence=min(s.confidence, max(start_m.score, 0.0) / 100.0),
                needs_review=bool(reasons),
                review_reasons=reasons,
            )
        )

    script = extraction.script or _infer_script(seats, ref)
    game_needs_review = (winner not in ("good", "evil")) or any(s.needs_review for s in seats)

    return ResolvedGame(
        winner=winner,
        script=script,
        player_count=len(seats),
        seats=seats,
        needs_review=game_needs_review,
    )


def commit(resolved: ResolvedGame, db_path: str = db.DEFAULT_DB) -> int:
    """Write a resolved game to the database. Returns the new game id."""
    if resolved.winner not in ("good", "evil"):
        raise ValueError("Cannot commit a game without a valid winner ('good'/'evil').")
    with db.connect(db_path) as conn:
        game_id = db.insert_game(
            conn,
            {
                "external_id": resolved.external_id,
                "played_at": resolved.played_at,
                "script": resolved.script,
                "player_count": resolved.player_count,
                "winner": resolved.winner,
                "source_images": resolved.source_images,
                "notes": resolved.notes,
                "needs_review": resolved.needs_review,
            },
        )
        for s in resolved.seats:
            db.insert_seat(
                conn,
                game_id,
                {
                    "seat_index": s.seat_index,
                    "player_name": s.player_name,
                    "character_id": s.character_id,
                    "final_character_id": s.final_character_id,
                    "final_alignment": s.final_alignment,
                    "is_alive_at_end": s.is_alive_at_end,
                    "reminder_tokens": s.reminder_tokens,
                    "won": s.won,
                    "confidence": s.confidence,
                    "needs_review": s.needs_review,
                },
            )
    return game_id
