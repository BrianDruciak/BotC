"""
Extractor interface + the strict data contract returned by the vision step.

The pipeline only ever depends on this interface, so the underlying vision model
(Gemini 3.5 Flash by default) can be swapped freely.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SeatExtraction:
    player_name: str
    character_text: str                 # role shown on the final token
    starting_character_text: str = ""   # inferred starting role if it changed; else == character_text
    alignment_hint: str | None = None   # 'good' | 'evil' | None
    is_alive: bool = True
    reminder_tokens: list[str] = field(default_factory=list)
    confidence: float = 1.0
    seat_index: int | None = None

    def __post_init__(self):
        if not self.starting_character_text:
            self.starting_character_text = self.character_text


@dataclass
class GameExtraction:
    winner: str | None = None           # 'good' | 'evil' | None (taken from sheet if absent)
    script: str | None = None
    seats: list[SeatExtraction] = field(default_factory=list)
    raw: dict | None = None             # raw model output for debugging


class Extractor(ABC):
    """Reads grimoire image bytes and returns a GameExtraction."""

    @abstractmethod
    def extract(self, image_bytes_list: list[bytes], winner_hint: str | None = None) -> GameExtraction:
        ...


def get_extractor(name: str | None = None) -> Extractor:
    """
    Factory. Defaults to Gemini when GEMINI_API_KEY is set, otherwise the stub so the
    full pipeline/UI can run on placeholder data without a key.
    """
    name = (name or os.environ.get("BOTC_EXTRACTOR") or "").lower()
    if not name:
        name = "gemini" if os.environ.get("GEMINI_API_KEY") else "stub"

    if name == "gemini":
        from .gemini import GeminiExtractor
        return GeminiExtractor()
    if name == "stub":
        from .stub import StubExtractor
        return StubExtractor()
    raise ValueError(f"Unknown extractor: {name!r}")
