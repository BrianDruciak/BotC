"""
Canonical character reference + fuzzy matcher.

Loads the scraped `data/characters.json` and provides a single source of truth for
validating/normalizing character names produced by the vision extractor. Every detected
character string is snapped to one of the 183 canonical characters so stats never get
corrupted by misspellings or hallucinations.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import cached_property

from rapidfuzz import fuzz, process, utils

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
CHARACTERS_JSON = os.path.join(DATA, "characters.json")

# A small set of common nicknames / alternate spellings players use that fuzzy
# matching alone might miss. Maps an alias -> canonical character name.
NAME_ALIASES = {
    "ft": "Fortune Teller",
    "fortuneteller": "Fortune Teller",
    "snake charmer": "Snake Charmer",
    "scarlet woman": "Scarlet Woman",
    "sw": "Scarlet Woman",
    "po": "Po",
    "vortox": "Vortox",
    "al hadikhia": "Al-Hadikhia",
    "alhadikhia": "Al-Hadikhia",
    "lil monsta": "Lil' Monsta",
    "lilmonsta": "Lil' Monsta",
    "village idiot": "Village Idiot",
}


def _norm(s: str) -> str:
    """Aggressive normalization for matching: lowercase alnum only."""
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


@dataclass
class Character:
    id: str
    name: str
    type: str
    alignment: str
    editions: list[str]
    ability: str
    icon_path: str
    wiki_url: str
    summary: str = ""
    flavour: str = ""
    artist: str = ""


@dataclass
class MatchResult:
    character: Character | None
    score: float          # 0..100
    query: str
    matched_name: str | None = None


@dataclass
class Reference:
    characters: list[Character] = field(default_factory=list)

    @classmethod
    def load(cls, path: str = CHARACTERS_JSON) -> "Reference":
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        chars = [
            Character(
                id=c["id"],
                name=c["name"],
                type=c["type"],
                alignment=c["alignment"],
                editions=c.get("editions", []),
                ability=c.get("ability", ""),
                icon_path=c.get("icon_path", ""),
                wiki_url=c.get("wiki_url", ""),
                summary=c.get("summary", ""),
                flavour=c.get("flavour", ""),
                artist=c.get("artist", ""),
            )
            for c in raw
        ]
        return cls(characters=chars)

    # ----------------------------------------------------------------- lookups
    @cached_property
    def by_id(self) -> dict[str, Character]:
        return {c.id: c for c in self.characters}

    @cached_property
    def by_name(self) -> dict[str, Character]:
        return {c.name: c for c in self.characters}

    @cached_property
    def _norm_index(self) -> dict[str, Character]:
        idx = {_norm(c.name): c for c in self.characters}
        for alias, target in NAME_ALIASES.items():
            tgt = self.by_name.get(target)
            if tgt:
                idx.setdefault(_norm(alias), tgt)
        return idx

    @cached_property
    def _choices(self) -> dict[str, Character]:
        """Normalized-name -> Character, the search space for fuzzy matching."""
        return self._norm_index

    def get(self, char_id: str) -> Character | None:
        return self.by_id.get(char_id)

    def match(self, text: str, score_cutoff: float = 0.0) -> MatchResult:
        """Snap a free-text character name to the nearest canonical character."""
        q = _norm(text)
        if not q:
            return MatchResult(None, 0.0, text)
        # Exact normalized hit first (covers aliases too).
        if q in self._norm_index:
            c = self._norm_index[q]
            return MatchResult(c, 100.0, text, c.name)
        result = process.extractOne(
            q,
            list(self._choices.keys()),
            scorer=fuzz.WRatio,
            processor=utils.default_process,
        )
        if result is None:
            return MatchResult(None, 0.0, text)
        choice, score, _ = result
        if score < score_cutoff:
            return MatchResult(None, score, text)
        c = self._choices[choice]
        return MatchResult(c, float(score), text, c.name)

    # ----------------------------------------------------------------- helpers
    def default_alignment(self, char_id: str) -> str:
        c = self.get(char_id)
        return c.alignment if c else "good"

    def stats_eligible(self, char_id: str) -> bool:
        """Fabled/Loric are storyteller pieces, excluded from win-rate stats."""
        c = self.get(char_id)
        return bool(c) and c.type not in ("fabled", "loric")


_singleton: Reference | None = None


def get_reference() -> Reference:
    global _singleton
    if _singleton is None:
        _singleton = Reference.load()
    return _singleton


if __name__ == "__main__":
    ref = get_reference()
    print(f"Loaded {len(ref.characters)} characters")
    for probe in ["Fortune teler", "imp", "scarlet women", "alhadikhia", "washer woman"]:
        m = ref.match(probe)
        name = m.character.name if m.character else "<no match>"
        print(f"  {probe!r:20} -> {name:20} ({m.score:.0f})")
