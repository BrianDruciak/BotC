"""Normalize game script labels into display groups for set win-rate stats."""

from __future__ import annotations

# Official edition sort order (custom scripts sort after, by name).
OFFICIAL_ORDER = [
    "Trouble Brewing",
    "Bad Moon Rising",
    "Sects & Violets",
]


def normalize_script(script: str | None) -> str:
    if not script or not str(script).strip():
        return "Unknown"
    raw = str(script).strip()
    low = raw.lower().replace("&", " and ")

    if "trouble brewing" in low or low.replace(" ", "_") == "trouble_brewing":
        return "Trouble Brewing"
    if (
        "bad moon" in low
        or "blood moon" in low
        or low.replace(" ", "_") == "bad_moon_rising"
    ):
        return "Bad Moon Rising"
    if ("sect" in low and "violets" in low) or low.replace(" ", "_") == "sects_and_violets":
        return "Sects & Violets"
    if low == "mixed":
        return "Mixed"
    if "main character syndrome" in low:
        return "Main Character Syndrome"
    return raw
