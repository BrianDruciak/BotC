"""
Gemini vision extractor.

Default model: Gemini 3.5 Flash (top MMMU-Pro for dense image/OCR, fast + cheap for
batch import). Low-confidence games can be re-run on Gemini 3 Pro by the caller.

Requires:  pip install google-genai   and   env GEMINI_API_KEY=...
Model ids are configurable via env in case Google's published id differs:
    BOTC_GEMINI_MODEL        (default "gemini-3.5-flash")
    BOTC_GEMINI_MODEL_HEAVY  (default "gemini-3-pro")
"""

from __future__ import annotations

import json
import os
import re

from ..reference import get_reference
from .base import Extractor, GameExtraction, SeatExtraction

DEFAULT_MODEL = os.environ.get("BOTC_GEMINI_MODEL", "gemini-2.5-flash")
HEAVY_MODEL = os.environ.get("BOTC_GEMINI_MODEL_HEAVY", "gemini-2.5-pro")

PROMPT = """\
You are reading the FINAL grimoire of a finished game of Blood on the Clocktower.
This is the Storyteller's view, so every token shows the player's TRUE character (no bluffs).

Return STRICT JSON only, matching this schema:
{
  "winner": "good" | "evil" | null,
  "script": string | null,
  "seats": [
    {
      "player_name": string,
      "character_text": string,            // character on the FINAL token
      "starting_character_text": string,   // the role the player STARTED as
      "alignment_hint": "good" | "evil" | null,
      "is_alive": boolean,                 // false if a shroud/death marker is shown
      "reminder_tokens": [string],         // text on reminder tokens near the seat
      "confidence": number                 // 0..1, your confidence for this seat
    }
  ]
}

Rules:
- Read EVERY seat in the ring. player_name is the text label by the seat.
- character_text must be one of the official character names. If unsure, give your best guess.
- starting_character_text: usually equals character_text. BUT if reminder tokens indicate a
  change (e.g. "IS THE DRUNK" means they really started as the Drunk; a star-pass/"became"
  marker, Pit-Hag/role-change markers), report the role they STARTED the game as.
- alignment_hint: infer good/evil. Travellers and a few characters can be either; use the
  token's colour/markers. Use null only if truly indeterminate.
- Output ONLY the JSON object, no prose, no markdown fences.

The official character names are (match against these): {character_list}
"""


class GeminiExtractor(Extractor):
    def __init__(self, model: str | None = None):
        try:
            from google import genai  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "google-genai not installed. Run: pip install google-genai"
            ) from exc
        if not os.environ.get("GEMINI_API_KEY"):
            raise RuntimeError("GEMINI_API_KEY is not set in the environment.")
        from google import genai

        self._genai = genai
        self.client = genai.Client()
        self.model = model or DEFAULT_MODEL

    def _character_list(self) -> str:
        return ", ".join(c.name for c in get_reference().characters)

    def extract(self, image_bytes_list, winner_hint=None) -> GameExtraction:
        from google.genai import types

        prompt = PROMPT.replace("{character_list}", self._character_list())
        parts = [types.Part.from_text(text=prompt)]
        for blob in image_bytes_list:
            mime = _sniff_mime(blob)
            parts.append(types.Part.from_bytes(data=blob, mime_type=mime))

        resp = self.client.models.generate_content(
            model=self.model,
            contents=parts,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )
        data = _parse_json(resp.text)
        return _to_extraction(data, winner_hint)


def _sniff_mime(blob: bytes) -> str:
    if blob[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _parse_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def _to_extraction(data: dict, winner_hint: str | None) -> GameExtraction:
    seats = []
    for i, s in enumerate(data.get("seats", [])):
        seats.append(
            SeatExtraction(
                player_name=str(s.get("player_name", "")).strip(),
                character_text=str(s.get("character_text", "")).strip(),
                starting_character_text=str(
                    s.get("starting_character_text") or s.get("character_text", "")
                ).strip(),
                alignment_hint=(s.get("alignment_hint") or None),
                is_alive=bool(s.get("is_alive", True)),
                reminder_tokens=list(s.get("reminder_tokens", []) or []),
                confidence=float(s.get("confidence", 1.0) or 1.0),
                seat_index=i,
            )
        )
    return GameExtraction(
        winner=winner_hint or data.get("winner"),
        script=data.get("script"),
        seats=seats,
        raw=data,
    )
