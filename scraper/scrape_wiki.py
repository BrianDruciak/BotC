"""
Blood on the Clocktower Wiki scraper.

Scrapes https://wiki.bloodontheclocktower.com via the MediaWiki API and produces:
  data/site_meta.json      - site info + statistics + scrape timestamp
  data/pages_index.json    - every (ns=0) article with its categories
  data/pages/*.wiki        - raw wikitext for every article (a full text mirror)
  data/characters.json     - structured character dataset (name, type, edition,
                             alignment, ability, flavour, artist, icon, jinxes)
  data/images/*            - every image hosted on the wiki (icons, logos, art)

Dependency free: uses only the Python standard library.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

API = "https://wiki.bloodontheclocktower.com/api.php"
USER_AGENT = "BotC-Stats-Agent-Scraper/1.0 (educational; contact: local user)"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
PAGES_DIR = os.path.join(DATA, "pages")
IMAGES_DIR = os.path.join(DATA, "images")

# The wiki tags every character page with exactly one "type" category and one or
# more "edition" categories. We use those category memberships as the source of
# truth for classification.
TYPE_CATEGORIES = [
    "Townsfolk",
    "Outsiders",
    "Minions",
    "Demons",
    "Travellers",
    "Fabled",
    "Loric",
]
EDITION_CATEGORIES = [
    "Trouble Brewing",
    "Bad Moon Rising",
    "Sects & Violets",
    "Experimental Characters",
]

# Default alignment implied purely by character type. Travellers can be either
# alignment in a given game, and Fabled/Loric are neutral storyteller pieces, so
# their alignment is left as "variable"/"neutral" and resolved per-game by the
# agent from the grimoire.
TYPE_TO_ALIGNMENT = {
    "Townsfolk": "good",
    "Outsiders": "good",
    "Minions": "evil",
    "Demons": "evil",
    "Travellers": "variable",
    "Fabled": "neutral",
    "Loric": "neutral",
}

# Singular labels used in the structured output.
TYPE_LABEL = {
    "Townsfolk": "townsfolk",
    "Outsiders": "outsider",
    "Minions": "minion",
    "Demons": "demon",
    "Travellers": "traveller",
    "Fabled": "fabled",
    "Loric": "loric",
}

EDITION_LABEL = {
    "Trouble Brewing": "trouble_brewing",
    "Bad Moon Rising": "bad_moon_rising",
    "Sects & Violets": "sects_and_violets",
    "Experimental Characters": "experimental",
}

REQUEST_DELAY_S = 0.2


def api_get(params: dict) -> dict:
    """GET the MediaWiki API with sensible defaults and basic retry."""
    params = {**params, "format": "json", "formatversion": "2"}
    url = API + "?" + urllib.parse.urlencode(params)
    last_err = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            time.sleep(REQUEST_DELAY_S)
            return data
        except Exception as exc:  # noqa: BLE001 - network resilience
            last_err = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"API request failed after retries: {url}\n{last_err}")


def api_get_paged(params: dict, continue_root: str = "continue"):
    """Yield successive API responses, following continuation tokens."""
    params = dict(params)
    while True:
        data = api_get(params)
        yield data
        cont = data.get(continue_root)
        if not cont:
            return
        params.update(cont)


# --------------------------------------------------------------------------- #
# Enumeration
# --------------------------------------------------------------------------- #

def get_all_pages() -> list[str]:
    """Every content (ns=0) page title."""
    titles: list[str] = []
    for data in api_get_paged({
        "action": "query",
        "list": "allpages",
        "apnamespace": "0",
        "aplimit": "500",
    }):
        for p in data["query"]["allpages"]:
            titles.append(p["title"])
    return sorted(set(titles))


def get_site_meta() -> dict:
    data = api_get({
        "action": "query",
        "meta": "siteinfo",
        "siprop": "general|statistics",
    })
    return data["query"]


# --------------------------------------------------------------------------- #
# Content fetching (batched)
# --------------------------------------------------------------------------- #

def fetch_content_batches(titles: list[str]) -> dict[str, dict]:
    """
    Return {title: {"wikitext": str, "categories": [str], "pageid": int}} for
    every title, fetched in batches of 50.
    """
    out: dict[str, dict] = {}
    for i in range(0, len(titles), 50):
        batch = titles[i : i + 50]
        # categories can paginate independently, so follow continuation.
        params = {
            "action": "query",
            "titles": "|".join(batch),
            "prop": "revisions|categories",
            "rvprop": "content",
            "rvslots": "main",
            "cllimit": "500",
            "clshow": "!hidden",
        }
        for data in api_get_paged(params):
            for page in data.get("query", {}).get("pages", []):
                title = page["title"]
                rec = out.setdefault(
                    title,
                    {"pageid": page.get("pageid"), "wikitext": "", "categories": []},
                )
                revs = page.get("revisions")
                if revs:
                    content = revs[0].get("slots", {}).get("main", {}).get("content")
                    if content:
                        rec["wikitext"] = content
                for cat in page.get("categories", []) or []:
                    name = cat["title"].split(":", 1)[-1]
                    if name not in rec["categories"]:
                        rec["categories"].append(name)
        print(f"  fetched content {min(i + 50, len(titles))}/{len(titles)}")
    return out


# --------------------------------------------------------------------------- #
# Parsing helpers
# --------------------------------------------------------------------------- #

FLAVOUR_RE = re.compile(r"flavour'>\s*[\"\u201c](.+?)[\"\u201d]\s*<", re.DOTALL)
ICON_RE = re.compile(r"\[\[File:\s*(icon[^|\]]+?)\s*[|\]]", re.IGNORECASE)
ARTIST_RE = re.compile(
    r"<td>\s*Artist\s*</td>\s*<td>\s*(.+?)\s*</td>", re.IGNORECASE | re.DOTALL
)


def section(wikitext: str, header: str) -> str:
    """Return the body text of a == Header == section, until the next header."""
    pat = re.compile(
        r"^==+\s*" + re.escape(header) + r"\s*==+\s*(.*?)(?=^==+\s|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    m = pat.search(wikitext)
    return m.group(1).strip() if m else ""


def clean_wikitext(text: str) -> str:
    """Strip common wiki/HTML markup down to readable plain text."""
    # {{Good|Chef}} / {{Evil|Imp}} -> Chef / Imp
    text = re.sub(r"\{\{\s*(?:Good|Evil)\s*\|\s*([^}]+?)\s*\}\}", r"\1", text)
    # [[Page#Anchor|Label]] -> Label ; [[Page|Label]] -> Label ; [[Page]] -> Page
    text = re.sub(r"\[\[[^\]|]*\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"'''(.+?)'''", r"\1", text)
    text = re.sub(r"''(.+?)''", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)  # stray html
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def first_quoted_line(text: str) -> str:
    m = re.search(r"[\"\u201c](.+?)[\"\u201d]", text, re.DOTALL)
    return m.group(1).strip() if m else ""


def parse_character(title: str, rec: dict) -> dict | None:
    cats = rec.get("categories", [])
    types = [TYPE_LABEL[c] for c in cats if c in TYPE_CATEGORIES]
    if not types:
        return None  # not a character page

    char_type_cat = next(c for c in cats if c in TYPE_CATEGORIES)
    editions = [EDITION_LABEL[c] for c in cats if c in EDITION_CATEGORIES]
    wt = rec.get("wikitext", "")

    summary = section(wt, "Summary")
    ability = first_quoted_line(summary)
    flavour_m = FLAVOUR_RE.search(wt)
    icon_m = ICON_RE.search(wt)
    artist_m = ARTIST_RE.search(wt)

    icon = icon_m.group(1).strip() if icon_m else ""
    # MediaWiki uppercases the first character of every file name, so the file
    # actually written to data/images is e.g. "Icon_washerwoman.png".
    icon_file = (icon[:1].upper() + icon[1:]) if icon else ""

    return {
        "name": title,
        "id": re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_"),
        "type": TYPE_LABEL[char_type_cat],
        "alignment": TYPE_TO_ALIGNMENT[char_type_cat],
        "editions": editions,
        "ability": ability,
        "summary": clean_wikitext(summary),
        "flavour": flavour_m.group(1).strip() if flavour_m else "",
        "artist": clean_wikitext(artist_m.group(1)) if artist_m else "",
        "icon": icon,
        "icon_file": icon_file,
        "icon_path": f"images/{icon_file}" if icon_file else "",
        "categories": cats,
        "pageid": rec.get("pageid"),
        "wiki_url": "https://wiki.bloodontheclocktower.com/"
        + urllib.parse.quote(title.replace(" ", "_")),
    }


# --------------------------------------------------------------------------- #
# Images
# --------------------------------------------------------------------------- #

def get_all_images() -> list[dict]:
    images: list[dict] = []
    for data in api_get_paged({
        "action": "query",
        "list": "allimages",
        "ailimit": "500",
        "aiprop": "url|size|mediatype",
    }):
        images.extend(data["query"]["allimages"])
    return images


def download_images(images: list[dict]) -> int:
    os.makedirs(IMAGES_DIR, exist_ok=True)
    count = 0
    for img in images:
        name = img.get("name") or img.get("title", "").split(":", 1)[-1]
        url = img.get("url")
        if not name or not url:
            continue
        dest = os.path.join(IMAGES_DIR, sanitize_filename(name))
        if os.path.exists(dest):
            count += 1
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp:
                blob = resp.read()
            with open(dest, "wb") as fh:
                fh.write(blob)
            count += 1
            time.sleep(0.05)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! failed image {name}: {exc}")
    return count


# --------------------------------------------------------------------------- #
# IO helpers
# --------------------------------------------------------------------------- #

def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "_", name).strip()


def write_json(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)


def main() -> int:
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(PAGES_DIR, exist_ok=True)

    print("Fetching site metadata...")
    meta = get_site_meta()

    print("Enumerating all content pages...")
    titles = get_all_pages()
    print(f"  {len(titles)} pages")

    print("Fetching page content (batched)...")
    content = fetch_content_batches(titles)

    print("Writing raw wikitext mirror...")
    pages_index = []
    for title in titles:
        rec = content.get(title, {})
        fname = sanitize_filename(title) + ".wiki"
        with open(os.path.join(PAGES_DIR, fname), "w", encoding="utf-8") as fh:
            fh.write(rec.get("wikitext", ""))
        pages_index.append(
            {
                "title": title,
                "pageid": rec.get("pageid"),
                "categories": rec.get("categories", []),
                "file": f"pages/{fname}",
            }
        )

    print("Parsing characters...")
    characters = []
    for title in titles:
        parsed = parse_character(title, content.get(title, {}))
        if parsed:
            characters.append(parsed)
    characters.sort(key=lambda c: (c["type"], c["name"]))

    print("Enumerating images...")
    images = get_all_images()
    print(f"  {len(images)} images; downloading...")
    downloaded = download_images(images)

    write_json(
        os.path.join(DATA, "site_meta.json"),
        {
            "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": "https://wiki.bloodontheclocktower.com",
            "siteinfo": meta.get("general", {}),
            "statistics": meta.get("statistics", {}),
            "counts": {
                "pages": len(titles),
                "characters": len(characters),
                "images_listed": len(images),
                "images_downloaded": downloaded,
            },
        },
    )
    write_json(os.path.join(DATA, "pages_index.json"), pages_index)
    write_json(os.path.join(DATA, "characters.json"), characters)

    # Summary counts by type/edition for a quick sanity check.
    by_type: dict[str, int] = {}
    by_edition: dict[str, int] = {}
    for c in characters:
        by_type[c["type"]] = by_type.get(c["type"], 0) + 1
        for e in c["editions"]:
            by_edition[e] = by_edition.get(e, 0) + 1

    print("\nDone.")
    print(f"  characters: {len(characters)}")
    print(f"  by type:    {by_type}")
    print(f"  by edition: {by_edition}")
    print(f"  images:     {downloaded}/{len(images)} downloaded")
    print(f"  output dir: {DATA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
