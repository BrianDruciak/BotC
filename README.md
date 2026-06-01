# Blood on the Clocktower — Win-Rate Agent

Logs character & player win rates from **final grimoire screenshots + a "good/evil won"
note**, supplied as an **Excel sheet**, and shows them in an **interactive running table**.

See [`PLAN.md`](PLAN.md) for the full design. This README is the quickstart.

## What's built

- **`data/`** — scraped reference from the [BOTC wiki](https://wiki.bloodontheclocktower.com):
  183 characters (`characters.json`), 195 images (icons/logos), full wikitext mirror.
- **`scraper/scrape_wiki.py`** — re-scrape the wiki (dependency-free).
- **`app/`** — the agent:
  - `reference.py` — canonical character DB + fuzzy matcher (snaps detected names to the 183).
  - `extract/` — `Extractor` interface, **Gemini 3.5 Flash** vision impl, and an offline **stub**.
  - `ingest.py` — resolve a parsed grimoire → starting-role attribution + win flags → commit.
  - `importer.py` — read the Excel sheet (auto-detect columns, URLs/paths/hyperlinks).
  - `stats.py` — win-rate aggregations (keyed on **starting role**; fabled/loric excluded).
  - `db.py` — SQLite store.
  - `api.py` / `web/` — FastAPI + single-page interactive table UI.

## Install

```bash
pip install -r requirements.txt
```

## Try it now (no API key needed)

The **stub extractor** generates plausible games so you can see the whole pipeline + UI work:

```bash
python -m app.cli demo --games 40     # populate with synthetic games
python -m app.server                  # open http://127.0.0.1:8000
```

## Real usage

1. Set the vision key: `setx GEMINI_API_KEY "..."` (Windows) / `export GEMINI_API_KEY=...`.
2. Put your Excel sheet in `data/` (e.g. `data/games.xlsx`). Each row needs a column whose
   header contains *image/link/url* (the grimoire image link or path) and a *winner/result*
   column containing good/evil. Optional: id, date, script columns are auto-detected.
3. Check detection, then import:

```bash
python -m app.cli inspect data/games.xlsx        # show detected columns + sample
python -m app.cli reset                          # clear demo data first
python -m app.cli import  data/games.xlsx        # uses Gemini when GEMINI_API_KEY is set
python -m app.server                             # browse the running table
```

`python -m app.cli stats --min-games 1` prints the tables in the terminal too.

## Notes

- **Attribution:** win rate is credited to the **starting role** (recovered from reminder
  tokens / review where the role changed mid-game).
- **Review:** seats with low name-match or low model confidence are flagged `needs_review`
  (a review/correction UI is the next step — see `PLAN.md` Phase 6).
