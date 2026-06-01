"""
FastAPI backend for the interactive stats table.

Run:  python -m app.server      (or: uvicorn app.api:app --reload)
Serves the single-page UI at / and JSON at /api/*. Character icons are served
from the scraped data/images directory.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db, stats
from .reference import get_reference

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WEB_DIR = os.path.join(HERE, "web")
IMAGES_DIR = os.path.join(ROOT, "data", "images")

app = FastAPI(title="BOTC Win-Rate Agent")


@app.get("/api/overview")
def api_overview():
    return stats.overview()


@app.get("/api/characters")
def api_characters(min_games: int = 0):
    return stats.character_stats(min_games=min_games)


@app.get("/api/players")
def api_players(min_games: int = 0):
    return stats.player_stats(min_games=min_games)


@app.get("/api/character/{char_id}")
def api_character(char_id: str):
    ref = get_reference()
    c = ref.get(char_id)
    if not c:
        raise HTTPException(404, "character not found")
    return {
        "character": {
            "id": c.id, "name": c.name, "type": c.type, "alignment": c.alignment,
            "editions": c.editions, "ability": c.ability, "icon_path": c.icon_path,
            "wiki_url": c.wiki_url,
        },
        "games": stats.games_for_character(char_id),
    }


@app.get("/api/player/{player_id}")
def api_player(player_id: int):
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM player WHERE id = ?", (player_id,)).fetchone()
    if not row:
        raise HTTPException(404, "player not found")
    return {"player": dict(row), "games": stats.games_for_player(player_id)}


@app.get("/")
def index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


if os.path.isdir(IMAGES_DIR):
    app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")
